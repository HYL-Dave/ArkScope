"""
Daily-cached analyst consensus (Finnhub) — the credible replacement for the
old ArkScope LLM "sentiment" score in the cockpit.

Finnhub's recommendation endpoint is per-ticker and throttled (~1/sec), so we
cache each ticker's consensus locally for a day and fill lazily (per visible
row) — the cockpit never blocks fetching the whole universe at once. This is a
local data cache (its own SQLite file under data/cache/), NOT user profile state
and NOT the remote PG.

The summary is derived deterministically from the recommendation distribution
(a standard 1-5 weighted mean → Strong Buy … Strong Sell), and is always
source-labeled "Finnhub" so it is never confused with an ArkScope score.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_TTL_SECONDS = 24 * 3600

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyst_consensus (
    ticker            TEXT PRIMARY KEY,
    rating            TEXT,
    score             REAL,
    buy_ratio         REAL,
    total             INTEGER,
    counts_json       TEXT,
    price_target_json TEXT,
    period            TEXT,
    fetched_at        TEXT NOT NULL
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(ticker: Optional[str]) -> str:
    return (ticker or "").strip().upper()


def derive_consensus(raw: dict) -> dict:
    """Compact, source-labeled summary from get_analyst_consensus output.

    rating: Strong Buy / Buy / Hold / Sell / Strong Sell / None (no coverage),
    via the standard 1-5 weighted mean of the current recommendation row.
    """
    rec = (raw.get("recommendations") or {}).get("current") or {}
    sb = int(rec.get("strongBuy", 0) or 0)
    b = int(rec.get("buy", 0) or 0)
    h = int(rec.get("hold", 0) or 0)
    s = int(rec.get("sell", 0) or 0)
    ss = int(rec.get("strongSell", 0) or 0)
    total = sb + b + h + s + ss
    rating = None
    score = None
    buy_ratio = None
    if total > 0:
        score = (sb * 5 + b * 4 + h * 3 + s * 2 + ss * 1) / total
        buy_ratio = (sb + b) / total
        if score >= 4.5:
            rating = "Strong Buy"
        elif score >= 3.5:
            rating = "Buy"
        elif score >= 2.5:
            rating = "Hold"
        elif score >= 1.5:
            rating = "Sell"
        else:
            rating = "Strong Sell"
    return {
        "rating": rating,
        "score": round(score, 2) if score is not None else None,
        "buy_ratio": round(buy_ratio, 3) if buy_ratio is not None else None,
        "total": total,
        "counts": {"strongBuy": sb, "buy": b, "hold": h, "sell": s, "strongSell": ss},
        "price_target": raw.get("price_target"),
        "period": rec.get("period"),
        "source": "finnhub",
    }


class AnalystConsensusCache:
    """Local SQLite cache of per-ticker analyst consensus, daily TTL."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        with self._write_lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_summary(self, r: sqlite3.Row) -> dict:
        return {
            "ticker": r["ticker"],
            "rating": r["rating"],
            "score": r["score"],
            "buy_ratio": r["buy_ratio"],
            "total": r["total"],
            "counts": json.loads(r["counts_json"]) if r["counts_json"] else {},
            "price_target": json.loads(r["price_target_json"]) if r["price_target_json"] else None,
            "period": r["period"],
            "source": "finnhub",
            "fetched_at": r["fetched_at"],
        }

    def get(self, ticker: str) -> Optional[dict]:
        """Cached summary if present AND fresh (< TTL), else None."""
        t = _norm(ticker)
        with self._connect() as conn:
            r = conn.execute("SELECT * FROM analyst_consensus WHERE ticker = ?", (t,)).fetchone()
        if not r:
            return None
        try:
            age = (_now() - datetime.fromisoformat(r["fetched_at"])).total_seconds()
        except Exception:
            age = _TTL_SECONDS + 1
        if age >= _TTL_SECONDS:
            return None
        return self._row_to_summary(r)

    def put(self, ticker: str, summary: dict) -> dict:
        t = _norm(ticker)
        fetched_at = _now().isoformat(timespec="seconds")
        with self._write_lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analyst_consensus
                    (ticker, rating, score, buy_ratio, total, counts_json,
                     price_target_json, period, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    rating=excluded.rating, score=excluded.score, buy_ratio=excluded.buy_ratio,
                    total=excluded.total, counts_json=excluded.counts_json,
                    price_target_json=excluded.price_target_json, period=excluded.period,
                    fetched_at=excluded.fetched_at
                """,
                (
                    t, summary.get("rating"), summary.get("score"), summary.get("buy_ratio"),
                    summary.get("total"), json.dumps(summary.get("counts") or {}),
                    json.dumps(summary.get("price_target")) if summary.get("price_target") is not None else None,
                    summary.get("period"), fetched_at,
                ),
            )
            conn.commit()
        out = dict(summary)
        out["ticker"] = t
        out["fetched_at"] = fetched_at
        return out

    def get_or_fetch(self, ticker: str, fetcher: Callable[[str], dict]) -> dict:
        """Return cached consensus if fresh; else fetch via ``fetcher`` (e.g.
        get_analyst_consensus), derive, cache, and return. Never raises — a
        fetch failure yields an empty (rating=None) summary, uncached."""
        t = _norm(ticker)
        cached = self.get(t)
        if cached is not None:
            return {**cached, "cached": True}
        try:
            raw = fetcher(t)
            summary = derive_consensus(raw or {})
            stored = self.put(t, summary)
            return {**stored, "cached": False}
        except Exception as exc:  # pragma: no cover - defensive (no key / network)
            return {
                "ticker": t, "rating": None, "score": None, "buy_ratio": None, "total": 0,
                "counts": {}, "price_target": None, "period": None, "source": "finnhub",
                "cached": False, "error": str(exc),
            }
