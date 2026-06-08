"""
market_data_admin — lifecycle for the local market_data.db (slice 3a.1).

Turns the developer migration script into an app-controllable substrate: status,
bootstrap (full rebuild from PG), validation, and an in-process job runner so the
desktop UI can trigger + poll a bootstrap instead of asking the user to run a CLI
(DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md §3/§4/§8). Slice 3a.1 = PRICES only.

The bootstrap builds to a ``.building`` temp file and atomically swaps it in only
after row-count + per-(ticker,interval) checksum validation passes, so a failed
rebuild never destroys an existing good DB. ``scripts/migrate_market_to_sqlite.py``
is a thin CLI over this module (operator/backfill/debug); the app uses the API.
Incremental (delta) updates are a later slice — this only does full bootstrap.
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

_SCHEMA = """
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

# Same UTC string format SqliteBackend expects and PG's query_prices emits.
_PG_SELECT = """
    SELECT
        ticker,
        TO_CHAR(datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
        interval, open, high, low, close, volume
    FROM prices
    ORDER BY ticker, interval, datetime
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
        raise RuntimeError("No DATABASE_URL in config/.env — cannot read PG prices.")
    import psycopg2

    sslmode = load_sslmode(_PROJECT_ROOT / "config" / ".env", dsn)
    return psycopg2.connect(dsn, sslmode=sslmode)


def _pg_checksum(cur) -> Dict[tuple, int]:
    cur.execute("SELECT ticker, interval, COUNT(*) FROM prices GROUP BY ticker, interval")
    return {(t, iv): n for t, iv, n in cur.fetchall()}


def _sqlite_checksum(conn) -> Dict[tuple, int]:
    rows = conn.execute(
        "SELECT ticker, interval, COUNT(*) FROM prices GROUP BY ticker, interval"
    ).fetchall()
    return {(t, iv): n for t, iv, n in rows}


def pg_price_counts() -> dict:
    """PG-side row + group counts (the validation target). For --dry-run / status."""
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        total = cur.fetchone()[0]
        groups = len(_pg_checksum(cur))
        return {"rows": total, "groups": groups}
    finally:
        pg.close()


# --- local DB stats (read-only; never needs PG) -------------------------------

def local_prices_stats(out_path: Optional[str] = None) -> dict:
    """Read-only stats for the local prices table (does NOT touch PG)."""
    path = out_path or resolve_market_db_path()
    if not Path(path).exists():
        return {"exists": False, "row_count": 0, "ticker_count": 0, "latest_datetime": None}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return {"exists": True, "row_count": 0, "ticker_count": 0, "latest_datetime": None}
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        ticker_count = conn.execute("SELECT COUNT(DISTINCT ticker) FROM prices").fetchone()[0]
        latest = conn.execute("SELECT MAX(datetime) FROM prices").fetchone()[0]
        return {"exists": True, "row_count": row_count, "ticker_count": ticker_count,
                "latest_datetime": latest}
    except sqlite3.OperationalError:
        return {"exists": True, "row_count": 0, "ticker_count": 0, "latest_datetime": None}
    finally:
        conn.close()


# --- bootstrap (full rebuild) + validate --------------------------------------

def bootstrap_prices(out_path: Optional[str] = None,
                     progress_cb: Optional[Callable[[int, int], None]] = None,
                     batch: int = 20000) -> dict:
    """Full rebuild of the local prices table from PG. Builds to a ``.building``
    temp and atomically swaps it in ONLY if validation passes (a failed rebuild
    leaves any existing DB untouched). Returns a result dict with ``match``."""
    path = out_path or resolve_market_db_path()
    tmp = path + ".building"
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        total = cur.fetchone()[0]
        pg_sum = _pg_checksum(cur)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(tmp).unlink(missing_ok=True)
        sconn = sqlite3.connect(tmp)  # default journal (single-file build → clean swap)
        try:
            sconn.executescript(_SCHEMA)
            cur.execute(_PG_SELECT)
            written = 0
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                sconn.executemany(
                    "INSERT OR IGNORE INTO prices "
                    "(ticker, datetime, interval, open, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                sconn.commit()
                written += len(rows)
                if progress_cb:
                    progress_cb(written, total)
            local_rows = sconn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            sq_sum = _sqlite_checksum(sconn)
        finally:
            sconn.close()
    finally:
        pg.close()

    match = local_rows == total and sq_sum == pg_sum
    if match:
        os.replace(tmp, path)  # atomic swap-in
        # set WAL on the live DB for concurrent reads during later incremental use
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
    return {"rows": local_rows, "total": total, "groups": len(sq_sum),
            "pg_groups": len(pg_sum), "match": match}


def validate_prices(out_path: Optional[str] = None) -> dict:
    """Compare local prices vs PG (row count + per-(ticker,interval) checksum)."""
    path = out_path or resolve_market_db_path()
    if not Path(path).exists():
        return {"exists": False, "match": False, "local_rows": 0, "pg_rows": None}
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        pg_rows = cur.fetchone()[0]
        pg_sum = _pg_checksum(cur)
    finally:
        pg.close()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        local_rows = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        sq_sum = _sqlite_checksum(conn)
    finally:
        conn.close()
    match = local_rows == pg_rows and sq_sum == pg_sum
    return {"exists": True, "match": match, "local_rows": local_rows, "pg_rows": pg_rows,
            "local_groups": len(sq_sum), "pg_groups": len(pg_sum)}


# --- in-process job runner (single sidecar) -----------------------------------

_JOBS: Dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def start_bootstrap_job(out_path: Optional[str] = None) -> dict:
    """Start a background bootstrap (idempotent while running). Returns the job dict."""
    path = out_path or resolve_market_db_path()
    with _JOBS_LOCK:
        for j in _JOBS.values():
            if j["kind"] == "bootstrap_prices" and j["status"] == "running":
                return dict(j)  # already running → return it (don't double-run)
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "kind": "bootstrap_prices", "status": "running",
               "progress": {"written": 0, "total": 0}, "result": None, "error": None}
        _JOBS[job_id] = job

    def _run():
        try:
            def cb(written, total):
                _JOBS[job_id]["progress"] = {"written": written, "total": total}
            res = bootstrap_prices(path, progress_cb=cb)
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
