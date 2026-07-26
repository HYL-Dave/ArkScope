"""Current local market-data schemas, status readers, and canonicalization helpers."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Optional

from src.news_identity import apply_news_identity_plan, plan_news_identity_repair

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
USE_LOCAL_MARKET_KEY = "use_local_market"  # profile_settings key for the persisted toggle
USE_LOCAL_MARKET_STRICT_KEY = "use_local_market_strict"  # modifier: local market on + DB exists → no PG fallback
_TRUTHY = ("1", "true", "yes", "on")

_PRICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    datetime  TEXT NOT NULL,   -- UTC 'YYYY-MM-DDTHH:MM:SS+0000' (matches PG TO_CHAR)
    interval  TEXT NOT NULL,   -- '15min' | '1h' | '1d'
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    volume    INTEGER,
    PRIMARY KEY (ticker, datetime, interval)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_interval_dt ON prices(ticker, interval, datetime);
"""

# News: articles only (no scores/embedding/search_vector). id mirrors PG's id so
# it is the rowid the FTS5 external-content index keys on.
_NEWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id              INTEGER PRIMARY KEY,
    ticker          TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    url             TEXT,
    publisher       TEXT,
    source          TEXT NOT NULL,   -- 'ibkr' | 'polygon' | 'finnhub'
    published_at    TEXT NOT NULL,   -- UTC 'YYYY-MM-DDTHH:MM:SS+0000'
    article_hash    TEXT,
    -- news_scores RETIRED (DATA_COLLECTION plan §4 decision 2026-06-23): sentiment is
    -- local-first + OPTIONAL. sentiment_score is the 1-5 LLM score written on-demand by
    -- analysis (NULL until then). The CHECK makes the 1-5 scale ENFORCED, not merely
    -- conventional: a provider's native polarity (-1/0/+1) physically CANNOT be written
    -- here, so it can never poison the 1-5 consumers (get_news_sentiment_summary,
    -- min_sentiment). A provider polarity, if ever carried, needs its OWN column.
    sentiment_score  REAL CHECK (sentiment_score IS NULL OR sentiment_score BETWEEN 1 AND 5),
    sentiment_source TEXT,           -- who produced the score: 'llm' | …
    sentiment_scale  TEXT            -- documents the score's scale (currently '1-5')
);
CREATE INDEX IF NOT EXISTS idx_news_ticker_pub ON news(ticker, published_at);
CREATE INDEX IF NOT EXISTS idx_news_pub ON news(published_at);
CREATE VIRTUAL TABLE IF NOT EXISTS news_fts
    USING fts5(title, description, content='news', content_rowid='id',
               tokenize='porter unicode61');
"""

def _ensure_news_sentiment_columns(conn) -> None:
    """Idempotent: add the optional local sentiment columns to a pre-sentiment ``news``
    table (CREATE TABLE IF NOT EXISTS won't alter an existing one). No-op when the news
    table is absent or already has them. news_scores is RETIRED — these are the local-first
    home for an on-demand 1-5 LLM score + scale-tagged provider sentiment."""
    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='news'"
    ).fetchone():
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(news)").fetchall()}
    # sentiment_score carries the SAME 1-5 CHECK as a fresh _NEWS_SCHEMA so an upgraded
    # pre-existing DB enforces the scale invariant identically (born NULL → CHECK passes).
    for col, decl in (
        ("sentiment_score", "REAL CHECK (sentiment_score IS NULL OR sentiment_score BETWEEN 1 AND 5)"),
        ("sentiment_source", "TEXT"),
        ("sentiment_scale", "TEXT"),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE news ADD COLUMN {col} {decl}")


# Ticker canonicalization (strict-readiness slice #1): one canonical spelling per company
# so prices/news/fundamentals/iv join across domains. ``canonical`` is the spelling the
# prices table already uses (the 2.27M-row history) — space form for class shares — so
# canonicalizing never rewrites prices history. Seeded with the known BRK split; grows as
# more aliases surface. Lives in market_data.db (locked topology). NOT for provider-sync
# state (that is provider_sync_*; this is identity mapping only).
_TICKER_ALIASES_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticker_aliases (
    alias     TEXT PRIMARY KEY,
    canonical TEXT NOT NULL
);
"""
_SEED_TICKER_ALIASES = (
    ("BRK.B", "BRK B"),
    ("BRK-B", "BRK B"),
    # LendingClub → Nasdaq HAPN rename (2026-06-22). Unlike the BRK spelling-variants
    # (canonical == existing-history spelling), this is a true rename: the canonical (HAPN)
    # is the NEW symbol new bars arrive under, so canonicalize stitches LC's history under
    # HAPN. Read paths fold LC→HAPN; the coverage panel shows one HAPN row, not an LC gap.
    ("LC", "HAPN"),
)


def _ensure_ticker_aliases(conn) -> None:
    """Idempotent: create ticker_aliases + seed the known splits (INSERT OR IGNORE so a
    re-run never dups or clobbers an operator-edited mapping)."""
    conn.executescript(_TICKER_ALIASES_SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO ticker_aliases (alias, canonical) VALUES (?, ?)",
        _SEED_TICKER_ALIASES,
    )


# PG-exit 2b — news identity + FTS sync. UNIQUE(article_hash) lets every writer INSERT OR IGNORE
# to dedup; the external-content news_fts is kept in sync by triggers so NO writer needs a manual
# fts insert. Triggers are deliberately NOT in _NEWS_SCHEMA: the bulk bootstrap copy uses a one-shot
# news_fts('rebuild') and would be slowed to a crawl by per-row triggers — bootstrap adds them AFTER
# the rebuild; incremental/direct writers (small batches) get them up front.
_NEWS_HASH_UNIQUE = "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_article_hash ON news(article_hash)"
_NEWS_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS news_ai AFTER INSERT ON news BEGIN
  INSERT INTO news_fts(rowid, title, description) VALUES (new.id, new.title, new.description);
END;
CREATE TRIGGER IF NOT EXISTS news_ad AFTER DELETE ON news BEGIN
  INSERT INTO news_fts(news_fts, rowid, title, description) VALUES('delete', old.id, old.title, old.description);
END;
CREATE TRIGGER IF NOT EXISTS news_au AFTER UPDATE ON news BEGIN
  INSERT INTO news_fts(news_fts, rowid, title, description) VALUES('delete', old.id, old.title, old.description);
  INSERT INTO news_fts(rowid, title, description) VALUES (new.id, new.title, new.description);
END;
"""


def _ensure_news_hash_unique(conn) -> None:
    """Idempotent UNIQUE index on news.article_hash so INSERT OR IGNORE dedups (PG-exit 2b).
    Safe to add to the live table because it has no dup/null article_hash rows (verified)."""
    conn.execute(_NEWS_HASH_UNIQUE)


def _ensure_news_fts_triggers(conn) -> None:
    """Idempotent AFTER INSERT/DELETE/UPDATE triggers keeping the external-content news_fts in
    sync (PG-exit 2b) — replaces the per-row manual fts inserts in the direct + mirror writers.
    NOT part of _NEWS_SCHEMA (see the note above): apply where per-row sync is wanted, never around
    the bulk bootstrap copy."""
    conn.executescript(_NEWS_FTS_TRIGGERS)


def _canonicalize_news_tickers(conn, aliases) -> int:
    """Fold current alias rows while updating their ticker-derived identity atomically."""
    overrides: dict[int, str] = {}
    spellings: set[str] = set()
    for alias, canonical in aliases:
        if alias == canonical:
            continue
        ids = conn.execute("SELECT id FROM news WHERE ticker = ?", (alias,)).fetchall()
        if not ids:
            continue
        spellings.add(alias)
        overrides.update({int(row[0]): canonical for row in ids})
    if overrides:
        plan = plan_news_identity_repair(
            conn,
            ticker_overrides=overrides,
            only_ids=set(overrides),
        )
        apply_news_identity_plan(conn, plan)
    return len(spellings)


def _canonicalize_table_tickers(conn, table: str) -> int:
    """One-time PK-SAFE reconcile of EXISTING rows in ``table`` whose ticker is an alias →
    its canonical spelling. Returns the number of DISTINCT alias spellings that had ≥1 row
    reconciled (not the row count).

    PK-safe (the load-bearing discipline): an alias row may collide with an already-present
    canonical row (e.g. news has BOTH 'BRK B' and 'BRK.B'; prices may have a same-PK dup).
    So per alias we UPDATE OR IGNORE (rename rows that DON'T collide) then DELETE whatever
    alias rows remain (the collisions — a canonical row already exists, so the dup is
    redundant). Never raises a PK IntegrityError, never loses a canonical row. Read paths
    still resolve through the alias table, so this is cleanup, not a correctness dependency."""
    aliases = conn.execute("SELECT alias, canonical FROM ticker_aliases").fetchall()
    table_columns = {
        str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    }
    if table == "news" and "article_hash" in table_columns:
        reconciled = _canonicalize_news_tickers(conn, aliases)
        conn.commit()
        return reconciled
    reconciled = 0
    for alias, canonical in aliases:
        if alias == canonical:
            continue
        before = conn.execute(
            "SELECT COUNT(*) FROM {} WHERE ticker = ?".format(table), (alias,)).fetchone()[0]
        if not before:
            continue
        # rename the non-colliding alias rows; OR IGNORE leaves a colliding row untouched
        conn.execute(
            "UPDATE OR IGNORE {} SET ticker = ? WHERE ticker = ?".format(table),
            (canonical, alias))
        # drop any alias rows that survived (they collided → canonical already exists)
        conn.execute("DELETE FROM {} WHERE ticker = ?".format(table), (alias,))
        reconciled += 1
    conn.commit()
    return reconciled


_PRICE_INSERT = ("INSERT OR IGNORE INTO prices "
                 "(ticker, datetime, interval, open, high, low, close, volume) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")

# 3c-C/S-H2: financial_cache — LOCAL-PRIMARY (NOT a PG mirror). SqliteBackend.set
# writes here; .get is local-only. cache_key-keyed
# with a TTL via expires_at (UTC ISO 'YYYY-MM-DDTHH:MM:SS+00:00' strings, which are
# lexicographically comparable so expiry is a string compare). Because it is
# local-primary it is independent of the retired PG mirror. financial_datasets_client
# routes its paid-path cache through here via cache_backend — source
# 'financial_datasets'; standalone/no-backend usage keeps its legacy env-PG+file.)
_FIN_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS financial_cache (
    cache_key   TEXT PRIMARY KEY,
    source      TEXT NOT NULL DEFAULT 'financial_datasets',
    ticker      TEXT NOT NULL,
    data        TEXT NOT NULL,        -- JSON (JSONB in PG)
    fetched_at  TEXT NOT NULL,        -- UTC ISO 'YYYY-MM-DDTHH:MM:SS+00:00'
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fin_cache_ticker ON financial_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_fin_cache_expires ON financial_cache(expires_at);
"""
# Serializes local-primary financial-cache writes within the sidecar.
_CACHE_WRITE_LOCK = threading.Lock()

RETIRED_MARKET_MIRROR_DOMAINS = ["news", "iv", "fundamentals"]
RETIRED_PRICE_MIRROR_MESSAGE = "prices PG mirror retired by P0-C"


def retired_market_mirror_result(operation: str) -> dict:
    return {
        "ok": False,
        "match": False,
        "code": "pg_market_bootstrap_retired",
        "operation": operation,
        "retired_domains": list(RETIRED_MARKET_MIRROR_DOMAINS),
        "error": (
            "The old all-domain PG market mirror bootstrap/validation path is retired. "
            "News, IV, fundamentals, scores, and financial_cache are local/refetch "
            "authorities; prices migration remains a separate PG-exit slice."
        ),
    }


def retired_price_mirror_result(operation: str = "incremental_update") -> dict:
    return {
        "ok": False,
        "rows_added": 0,
        "error": RETIRED_PRICE_MIRROR_MESSAGE,
        "skipped": RETIRED_PRICE_MIRROR_MESSAGE,
        "operation": operation,
        "retired_domains": ["prices"],
        "message": "Use the direct-local IBKR prices writer instead of the PG mirror.",
    }


def overlay_price_sync_retired(sync: dict | None) -> dict:
    out = dict(sync or {})
    prices = dict(out.get("prices") or {})
    prices.update(
        {
            "retired": True,
            "authority": "local",
            "message": "Prices are served from local market_data.db; PG mirror sync is retired.",
        }
    )
    out["prices"] = prices
    return out

def _now() -> str:
    """UTC ISO-8601 timestamp (seconds). Imported lazily to keep this off the hot path."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_market_db_path() -> str:
    """``ARKSCOPE_MARKET_DB`` or the default ``<repo>/data/market_data.db``."""
    return os.environ.get("ARKSCOPE_MARKET_DB") or str(_PROJECT_ROOT / "data" / "market_data.db")


def env_routing_enabled() -> bool:
    return os.environ.get("ARKSCOPE_USE_LOCAL_MARKET", "").strip().lower() in _TRUTHY


def env_strict_enabled() -> bool:
    return os.environ.get("ARKSCOPE_LOCAL_MARKET_STRICT", "").strip().lower() in _TRUTHY


def _load_ticker_aliases(conn) -> Dict[str, str]:
    """alias→canonical map from a SQLite conn; {} if the table is absent (pre-canon DB)."""
    try:
        return {a: c for a, c in conn.execute("SELECT alias, canonical FROM ticker_aliases").fetchall()}
    except sqlite3.OperationalError:
        return {}


# --- local DB stats (read-only; never needs PG) -------------------------------

def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)
    ).fetchone() is not None


def local_market_stats(out_path: Optional[str] = None) -> dict:
    """Read-only per-domain stats for the local market DB (does NOT touch PG)."""
    path = out_path or resolve_market_db_path()
    empty = {
        "exists": False,
        "prices": {"row_count": 0, "ticker_count": 0, "latest_datetime": None},
        "news": {"row_count": 0, "source_count": 0, "latest_published": None},
        "fundamentals": {"row_count": 0, "ticker_count": 0, "latest_date": None},
        # local-primary cache (3c-C): valid vs expired by expires_at, plus latest fetch
        "financial_cache": {"row_count": 0, "valid_count": 0, "expired_count": 0,
                            "latest_fetched_at": None},
    }
    if not Path(path).exists():
        return empty
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return {**empty, "exists": True}
    try:
        out = {**{k: dict(v) for k, v in empty.items() if k != "exists"}, "exists": True}
        if _table_exists(conn, "prices"):
            out["prices"] = {
                "row_count": conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0],
                "ticker_count": conn.execute("SELECT COUNT(DISTINCT ticker) FROM prices").fetchone()[0],
                "latest_datetime": conn.execute("SELECT MAX(datetime) FROM prices").fetchone()[0],
            }
        if _table_exists(conn, "news"):
            out["news"] = {
                "row_count": conn.execute("SELECT COUNT(*) FROM news").fetchone()[0],
                "source_count": conn.execute("SELECT COUNT(DISTINCT source) FROM news").fetchone()[0],
                "latest_published": conn.execute("SELECT MAX(published_at) FROM news").fetchone()[0],
            }
        if _table_exists(conn, "fundamentals"):
            out["fundamentals"] = {
                "row_count": conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0],
                "ticker_count": conn.execute("SELECT COUNT(DISTINCT ticker) FROM fundamentals").fetchone()[0],
                "latest_date": conn.execute("SELECT MAX(snapshot_date) FROM fundamentals").fetchone()[0],
            }
        if _table_exists(conn, "financial_cache"):
            now = _now()  # same UTC ISO-seconds format the cache stores expires_at in
            total = conn.execute("SELECT COUNT(*) FROM financial_cache").fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM financial_cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]
            out["financial_cache"] = {
                "row_count": total,
                "valid_count": valid,
                "expired_count": total - valid,
                "latest_fetched_at": conn.execute("SELECT MAX(fetched_at) FROM financial_cache").fetchone()[0],
            }
        return out
    except sqlite3.OperationalError:
        return {**empty, "exists": True}
    finally:
        conn.close()


def local_ticker_coverage(ticker: str, out_path: Optional[str] = None) -> dict:
    """Whether the LOCAL market DB has any rows for ``ticker`` per domain (read-only,
    routing-independent — a fact about the local DB, NOT a claim about where a given
    read was served from). Powers the detail page's local-coverage hint."""
    path = out_path or resolve_market_db_path()
    cov = {"exists": False, "prices": False, "news": False, "fundamentals": False}
    if not Path(path).exists():
        return cov
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return cov
    # resolve the alias spelling to canonical so coverage of e.g. 'BRK.B' reports the
    # rows that live under the canonical 'BRK B' (consistent with the read paths' _canon).
    t = _load_ticker_aliases(conn).get(ticker.upper(), ticker.upper())
    try:
        cov["exists"] = True
        for domain, table in (("prices", "prices"), ("news", "news"),
                              ("fundamentals", "fundamentals")):
            if _table_exists(conn, table):
                cov[domain] = conn.execute(
                    f"SELECT 1 FROM {table} WHERE ticker = ? LIMIT 1", (t,)
                ).fetchone() is not None
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return cov



def read_sync_meta(out_path: Optional[str] = None) -> dict:
    """Read surviving legacy sync telemetry without reviving retired domains."""
    path = out_path or resolve_market_db_path()
    out = {"prices": None, "news": None, "fundamentals": None}
    if not Path(path).exists():
        return out
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return out
    try:
        if not _table_exists(conn, "market_sync_meta"):
            return out
        for r in conn.execute(
            "SELECT domain, last_success, last_error, rows_added, updated_at FROM market_sync_meta"
        ).fetchall():
            if r[0] in out:
                out[r[0]] = {"last_success": r[1], "last_error": r[2],
                             "rows_added": r[3], "updated_at": r[4]}
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return out
