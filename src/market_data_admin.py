"""
market_data_admin — lifecycle for the local market_data.db (slices 3a / 3b).

Turns the developer migration script into an app-controllable substrate: status,
bootstrap (full rebuild from PG), validation, and an in-process job runner so the
desktop UI can trigger + poll a bootstrap instead of asking the user to run a CLI
(DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md §3/§4/§8).

Domains migrated:
  - 3a  PRICES — the OHLCV bars (15min stored; 1h/1d rolled up on read).
  - 3b  NEWS   — article corpus (NO scores; news_scores deferred) + an FTS5 index
                 for local full-text search. Score-dependent reads fall back to PG.

The bootstrap builds BOTH domains into a single ``.building`` temp file and
atomically swaps it in only after row-count + checksum validation passes, so a
failed rebuild never destroys an existing good DB. ``scripts/migrate_market_to_sqlite.py``
is a thin CLI over this module; the app uses the API. Incremental (delta) updates
are a later slice — this only does full bootstrap.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
USE_LOCAL_MARKET_KEY = "use_local_market"  # profile_settings key for the persisted toggle
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
    id           INTEGER PRIMARY KEY,
    ticker       TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT,
    url          TEXT,
    publisher    TEXT,
    source       TEXT NOT NULL,   -- 'ibkr' | 'polygon' | 'finnhub'
    published_at TEXT NOT NULL,   -- UTC 'YYYY-MM-DDTHH:MM:SS+0000'
    article_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_ticker_pub ON news(ticker, published_at);
CREATE INDEX IF NOT EXISTS idx_news_pub ON news(published_at);
CREATE VIRTUAL TABLE IF NOT EXISTS news_fts
    USING fts5(title, description, content='news', content_rowid='id',
               tokenize='porter unicode61');
"""

_PG_PRICES_SELECT = """
    SELECT
        ticker,
        TO_CHAR(datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
        interval, open, high, low, close, volume
    FROM prices
    ORDER BY ticker, interval, datetime
"""

_PG_NEWS_SELECT = """
    SELECT
        id, ticker, title, description, url, publisher, source,
        TO_CHAR(published_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS published_at,
        article_hash
    FROM news
    ORDER BY id
"""


def resolve_market_db_path() -> str:
    """``ARKSCOPE_MARKET_DB`` or the default ``<repo>/data/market_data.db``."""
    return os.environ.get("ARKSCOPE_MARKET_DB") or str(_PROJECT_ROOT / "data" / "market_data.db")


def env_routing_enabled() -> bool:
    return os.environ.get("ARKSCOPE_USE_LOCAL_MARKET", "").strip().lower() in _TRUTHY


# --- PostgreSQL access (source of the migration) ------------------------------

def _pg_conn():
    """Connect to PG using the project's resolved DSN (config/.env)."""
    from src.tools.data_access import DataAccessLayer
    from src.tools.db_config import load_sslmode

    dsn = DataAccessLayer(db_dsn="auto")._load_env_db_dsn()
    if not dsn:
        raise RuntimeError("No DATABASE_URL in config/.env — cannot read PG market data.")
    import psycopg2

    sslmode = load_sslmode(_PROJECT_ROOT / "config" / ".env", dsn)
    return psycopg2.connect(dsn, sslmode=sslmode)


def _pg_group_counts(cur, sql: str) -> Dict[tuple, int]:
    cur.execute(sql)
    return {tuple(row[:-1]): row[-1] for row in cur.fetchall()}


def _sqlite_group_counts(conn, sql: str) -> Dict[tuple, int]:
    return {tuple(row[:-1]): row[-1] for row in conn.execute(sql).fetchall()}


_PG_PRICE_CHECKSUM = "SELECT ticker, interval, COUNT(*) FROM prices GROUP BY ticker, interval"
_SQ_PRICE_CHECKSUM = _PG_PRICE_CHECKSUM
_PG_NEWS_CHECKSUM = "SELECT source, COUNT(*) FROM news GROUP BY source"
_SQ_NEWS_CHECKSUM = _PG_NEWS_CHECKSUM


def pg_market_counts() -> dict:
    """PG-side row + group counts per domain (the validation target / --dry-run)."""
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        price_rows = cur.fetchone()[0]
        price_groups = len(_pg_group_counts(cur, _PG_PRICE_CHECKSUM))
        cur.execute("SELECT COUNT(*) FROM news")
        news_rows = cur.fetchone()[0]
        news_groups = len(_pg_group_counts(cur, _PG_NEWS_CHECKSUM))
        return {
            "prices": {"rows": price_rows, "groups": price_groups},
            "news": {"rows": news_rows, "groups": news_groups},
        }
    finally:
        pg.close()


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
    }
    if not Path(path).exists():
        return empty
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return {**empty, "exists": True}
    try:
        out = {"exists": True,
               "prices": {"row_count": 0, "ticker_count": 0, "latest_datetime": None},
               "news": {"row_count": 0, "source_count": 0, "latest_published": None}}
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
        return out
    except sqlite3.OperationalError:
        return {**empty, "exists": True}
    finally:
        conn.close()


# --- bootstrap (full rebuild of prices + news) + validate ---------------------

def _copy_table(cur, sconn, select_sql: str, insert_sql: str, total: int,
                progress_cb, base: int, grand_total: int, batch: int) -> int:
    cur.execute(select_sql)
    written = 0
    while True:
        rows = cur.fetchmany(batch)
        if not rows:
            break
        sconn.executemany(insert_sql, rows)
        sconn.commit()
        written += len(rows)
        if progress_cb:
            progress_cb(base + written, grand_total)
    return written


def bootstrap_market(out_path: Optional[str] = None,
                     progress_cb: Optional[Callable[[int, int], None]] = None,
                     batch: int = 20000) -> dict:
    """Full rebuild of the local market DB (prices + news) from PG. Builds to a
    ``.building`` temp and atomically swaps it in ONLY if BOTH domains validate
    (row-count + group checksum), so a failed rebuild leaves any existing DB
    untouched. Returns a per-domain result dict with an overall ``match``."""
    path = out_path or resolve_market_db_path()
    tmp = path + ".building"
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        price_total = cur.fetchone()[0]
        pg_price_sum = _pg_group_counts(cur, _PG_PRICE_CHECKSUM)
        cur.execute("SELECT COUNT(*) FROM news")
        news_total = cur.fetchone()[0]
        pg_news_sum = _pg_group_counts(cur, _PG_NEWS_CHECKSUM)
        grand = price_total + news_total

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(tmp).unlink(missing_ok=True)
        sconn = sqlite3.connect(tmp)
        try:
            sconn.executescript(_PRICES_SCHEMA)
            sconn.executescript(_NEWS_SCHEMA)
            _copy_table(
                cur, sconn, _PG_PRICES_SELECT,
                "INSERT OR IGNORE INTO prices "
                "(ticker, datetime, interval, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                price_total, progress_cb, 0, grand, batch,
            )
            _copy_table(
                cur, sconn, _PG_NEWS_SELECT,
                "INSERT OR IGNORE INTO news "
                "(id, ticker, title, description, url, publisher, source, published_at, article_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                news_total, progress_cb, price_total, grand, batch,
            )
            sconn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")  # build FTS index
            sconn.commit()

            local_prices = sconn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            sq_price_sum = _sqlite_group_counts(sconn, _SQ_PRICE_CHECKSUM)
            local_news = sconn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
            sq_news_sum = _sqlite_group_counts(sconn, _SQ_NEWS_CHECKSUM)
        finally:
            sconn.close()
    finally:
        pg.close()

    prices_match = local_prices == price_total and sq_price_sum == pg_price_sum
    news_match = local_news == news_total and sq_news_sum == pg_news_sum
    match = prices_match and news_match
    if match:
        os.replace(tmp, path)  # atomic swap-in
        try:
            wconn = sqlite3.connect(path)
            try:
                wconn.execute("PRAGMA journal_mode = WAL")
            finally:
                wconn.close()
        except sqlite3.OperationalError:
            pass
    else:
        Path(tmp).unlink(missing_ok=True)  # keep any existing good DB intact
    return {
        "match": match,
        "prices": {"rows": local_prices, "total": price_total, "match": prices_match},
        "news": {"rows": local_news, "total": news_total, "match": news_match},
    }


def validate_market(out_path: Optional[str] = None) -> dict:
    """Compare local prices + news vs PG (row count + group checksum per domain)."""
    path = out_path or resolve_market_db_path()
    if not Path(path).exists():
        return {"exists": False, "match": False}
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        pg_price_rows = cur.fetchone()[0]
        pg_price_sum = _pg_group_counts(cur, _PG_PRICE_CHECKSUM)
        cur.execute("SELECT COUNT(*) FROM news")
        pg_news_rows = cur.fetchone()[0]
        pg_news_sum = _pg_group_counts(cur, _PG_NEWS_CHECKSUM)
    finally:
        pg.close()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        lp = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] if _table_exists(conn, "prices") else 0
        sq_price_sum = _sqlite_group_counts(conn, _SQ_PRICE_CHECKSUM) if _table_exists(conn, "prices") else {}
        ln = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] if _table_exists(conn, "news") else 0
        sq_news_sum = _sqlite_group_counts(conn, _SQ_NEWS_CHECKSUM) if _table_exists(conn, "news") else {}
    finally:
        conn.close()
    prices_match = lp == pg_price_rows and sq_price_sum == pg_price_sum
    news_match = ln == pg_news_rows and sq_news_sum == pg_news_sum
    return {
        "exists": True,
        "match": prices_match and news_match,
        "prices": {"local_rows": lp, "pg_rows": pg_price_rows, "match": prices_match},
        "news": {"local_rows": ln, "pg_rows": pg_news_rows, "match": news_match},
    }


# --- in-process job runner (single sidecar) -----------------------------------

_JOBS: Dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def start_bootstrap_job(out_path: Optional[str] = None) -> dict:
    """Start a background market bootstrap (idempotent while running). Returns the job."""
    path = out_path or resolve_market_db_path()
    with _JOBS_LOCK:
        for j in _JOBS.values():
            if j["kind"] == "bootstrap_market" and j["status"] == "running":
                return dict(j)  # already running → return it (don't double-run)
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "kind": "bootstrap_market", "status": "running",
               "progress": {"written": 0, "total": 0}, "result": None, "error": None}
        _JOBS[job_id] = job

    def _run():
        try:
            def cb(written, total):
                _JOBS[job_id]["progress"] = {"written": written, "total": total}
            res = bootstrap_market(path, progress_cb=cb)
            _JOBS[job_id]["result"] = res
            if res.get("match"):
                _JOBS[job_id]["status"] = "done"
            else:
                _JOBS[job_id]["status"] = "error"
                _JOBS[job_id]["error"] = "validation mismatch (rebuild discarded; existing DB kept)"
        except Exception as e:  # noqa: BLE001 — surface any failure to the UI
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = str(e)

    threading.Thread(target=_run, name=f"bootstrap-{job_id}", daemon=True).start()
    return dict(_JOBS[job_id])


def get_job(job_id: str) -> Optional[dict]:
    j = _JOBS.get(job_id)
    return dict(j) if j else None
