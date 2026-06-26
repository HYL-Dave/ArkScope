"""Direct-local news writer (PG-exit Step 2a) — provider → market_data.db `news` + `news_fts`.

The first direct-local ingest collector after price_backfill, reusing its machinery: holds
``market_write_lock`` (serializes vs the PG→local mirror), records ``provider_sync_runs`` /
``provider_sync_meta`` telemetry (``domain='news'``, ``interval='news'``), per-ticker failure
isolation, and idempotent ``INSERT OR IGNORE``. No PG, no Parquet round-trip for the local read
path. Mirrors `backfill_prices_direct`.

Dedup is on the opaque ``article_hash`` (MD5 today — treated as a STABLE KEY, not assumed
SHA-256). ``published_at`` is normalized to the local UTC format ``'YYYY-MM-DDTHH:MM:SS+0000'``.
``news_fts`` (external-content FTS5, ``content_rowid='id'``) is kept in sync by an explicit
per-row insert here — the SAME approach the PG→local mirror uses today; Step 2b converts BOTH to
AFTER-INSERT triggers (and removes these manual inserts to avoid double-write). The incremental
cursor is the newest local ``published_at`` for THIS source (source-scoped, optionally
ticker-scoped) so Polygon/Finnhub don't clobber each other's frontier.

2a is the writer only — NO scheduler routing (use_local_news), NO live-DB schema migration. The
``article_hash`` UNIQUE index is created here for the hermetic temp DB; the live additive
migration + triggers are Step 2b.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.market_data_admin import _NEWS_SCHEMA, resolve_market_db_path
from src.market_data_direct import (
    _ensure_provider_sync_tables,
    _finish_provider_run,
    _start_provider_run,
    _upsert_provider_meta,
    market_write_lock,
)

logger = logging.getLogger(__name__)

# UNIQUE on the opaque article_hash → INSERT OR IGNORE dedups. (2a creates it for the temp DB;
# 2b adds it to the live DB as a tolerant additive migration.)
_NEWS_HASH_UNIQUE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_article_hash ON news(article_hash)")

_NEWS_REQUIRED = ("ticker", "title", "published_at", "article_hash")


def _norm_published(s: str) -> Optional[str]:
    """Parse a provider ISO timestamp → local UTC 'YYYY-MM-DDTHH:MM:SS+0000'. Handles a trailing
    'Z', explicit offsets, and fractional seconds. None on unparseable input (row skipped)."""
    if not s:
        return None
    t = s.strip()
    try:
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        dt = datetime.fromisoformat(t)
    except ValueError:
        # tolerate 'YYYY-MM-DD HH:MM:SS' (space) and date-only
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(t[:19] if len(t) >= 19 else t, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")


def _article_row(article: Dict[str, Any], source: str) -> Optional[tuple]:
    """Map a raw provider article dict → the news row tuple, or None if it lacks a required
    field or has an unparseable timestamp (skipped, not fatal)."""
    if any(not article.get(k) for k in _NEWS_REQUIRED):
        return None
    pub = _norm_published(article["published_at"])
    if pub is None:
        return None
    return (
        article["ticker"].upper(),
        article["title"],
        article.get("description") or "",
        article.get("url") or "",
        article.get("publisher") or "",
        source,
        pub,
        article["article_hash"],
    )


def _ensure_news_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_NEWS_SCHEMA)   # news + indexes + news_fts (external content)
    conn.execute(_NEWS_HASH_UNIQUE)
    conn.commit()


def _latest_published(conn: sqlite3.Connection, source: str, ticker: str) -> Optional[str]:
    """Source-scoped (+ticker) incremental cursor: newest local published_at, or None."""
    row = conn.execute(
        "SELECT MAX(published_at) FROM news WHERE source = ? AND ticker = ?",
        (source, ticker.upper())).fetchone()
    return row[0] if row and row[0] else None


def _insert_article(conn: sqlite3.Connection, row: tuple) -> bool:
    """INSERT OR IGNORE one article (dedup on article_hash); on a genuine insert, sync news_fts
    (external content → must be written explicitly). Returns True iff a new row was inserted."""
    before = conn.total_changes
    cur = conn.execute(
        "INSERT OR IGNORE INTO news (ticker, title, description, url, publisher, source, "
        "published_at, article_hash) VALUES (?,?,?,?,?,?,?,?)", row)
    if conn.total_changes == before:
        return False  # IGNORE'd duplicate (article_hash already present)
    conn.execute("INSERT INTO news_fts (rowid, title, description) VALUES (?, ?, ?)",
                 (cur.lastrowid, row[1], row[2]))   # row[1]=title, row[2]=description
    return True


def backfill_news_direct(
    tickers: List[str],
    *,
    source: str,
    provider: Any,
    db_path: Optional[str] = None,
    progress_cb=None,
) -> Dict[str, Any]:
    """Direct-local news ingest for ``tickers`` from ``provider`` (``.fetch_news(ticker,
    since_iso)`` → raw article dicts), into the local ``news`` table tagged ``source``. Per-ticker:
    cursor = newest local published_at for this source+ticker → fetch since +that → INSERT OR
    IGNORE (dedup on article_hash) + FTS sync → provider_sync_meta. Per-ticker failure isolated;
    fatal setup failure marks the run failed + re-raises. Returns a rollup dict."""
    path = db_path or resolve_market_db_path()
    rollup: Dict[str, Any] = {"source": source, "tickers_scanned": 0, "articles_added": 0,
                              "errors": {}}
    with market_write_lock():
        conn = sqlite3.connect(path, timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout = 10000")
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            _ensure_news_schema(conn)
            _ensure_provider_sync_tables(conn)
            run_id = _start_provider_run(conn, provider=source, interval="news", domain="news")
            total = len(tickers)
            try:
                for i, ticker in enumerate(tickers, 1):
                    rollup["tickers_scanned"] += 1
                    canon = ticker.upper()
                    try:
                        since = _latest_published(conn, source, canon)
                        articles = provider.fetch_news(canon, since_iso=since) or []
                        added = 0
                        newest = since
                        for art in articles:
                            row = _article_row(art, source)
                            if row is None:
                                continue
                            if _insert_article(conn, row):
                                added += 1
                            if newest is None or row[6] > newest:
                                newest = row[6]   # row[6] = normalized published_at
                        conn.commit()
                        rollup["articles_added"] += added
                        _upsert_provider_meta(conn, provider=source, ticker=canon,
                                              interval="news", last_bar_datetime=newest,
                                              rows_added=added, error=None)
                    except Exception as e:  # noqa: BLE001 — per-ticker isolation, never fatal
                        rollup["errors"][canon] = str(e)
                        try:
                            _upsert_provider_meta(conn, provider=source, ticker=canon,
                                                  interval="news", last_bar_datetime=None,
                                                  rows_added=0, error=str(e))
                        except Exception:  # noqa: BLE001
                            logger.warning("provider_sync_meta write failed for %s (news per-ticker "
                                           "recovery); continuing", canon, exc_info=True)
                    if progress_cb:
                        progress_cb(i, total, canon)
            except Exception as e:  # a non-per-ticker failure fails the whole run
                try:
                    _finish_provider_run(conn, run_id, status="failed",
                                         tickers_scanned=rollup["tickers_scanned"], gaps_found=0,
                                         rows_added=rollup["articles_added"], error=str(e))
                except Exception:  # noqa: BLE001
                    logger.warning("provider_sync_runs failed-finalize write failed", exc_info=True)
                raise
            _finish_provider_run(conn, run_id, status="succeeded",
                                 tickers_scanned=rollup["tickers_scanned"], gaps_found=0,
                                 rows_added=rollup["articles_added"], error=None)
        finally:
            conn.close()
    return rollup
