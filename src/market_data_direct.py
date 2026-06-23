"""Direct provider→SQLite market-data backfill (PG-exit slice #2).

Sibling of ``market_data_admin.py`` — that module's ``incremental_update`` is the
PG→SQLite MIRROR; this module writes the local ``prices`` table DIRECTLY from a
provider (IBKR primary / Polygon fallback) so local freshness no longer depends on
PG. No runtime PG dependency lives here.

This file is slice #2a: the hermetic, PG-free, no-Gateway CORE —
- ``backup_market_db``        : WAL-safe backup (SQLite backup API, NOT shutil.copyfile);
- ``preflight_canonicalize``  : local-only create+seed ticker_aliases + fold existing
                                rows (reuses slice-1 helpers); regularizes the live DB
                                BEFORE any direct write, without touching PG;
- ``_normalize_utc``          : exchange-local/aware datetime → the byte-identical UTC PK
                                string PG produces (the load-bearing dedup invariant);
- ``detect_price_gaps``       : per-ticker MISSING TRADING DAYS (day-presence; weekend +
                                US-holiday aware — NOT a per-day bar-count completeness
                                claim, see the naming note below);
- ``provider_sync_runs`` / ``provider_sync_meta`` tables + helpers (NEW; never
  ``market_sync_meta``, which means "PG mirror").

The provider fetch (IBKR/Polygon), the canonicalize-before-insert write path, the
scheduler ``price_backfill`` source, the run_source guard, the market-write lock, and
the live smoke are slice #2b — NOT in this file yet.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from src.market_data_admin import (
    _canonicalize_table_tickers,
    _ensure_ticker_aliases,
    _load_ticker_aliases,
    _now,
    resolve_market_db_path,
)
from src.tools.data_coverage_tools import _market_day_status

logger = logging.getLogger(__name__)

_CANON_DOMAINS = ("prices", "news", "iv_history", "fundamentals")
_EXCHANGE_TZ = "America/New_York"
# JobRunsStore (PG telemetry) only accepts these — provider_sync_runs mirrors that set
# so a run status can round-trip without a separate validation contract.
_VALID_RUN_STATUSES = frozenset({"running", "succeeded", "failed"})

_INTERVAL_DB = {"15min": "15min", "15 mins": "15min"}  # provider label → stored label


# --- UTC PK normalization (the byte-match invariant) -------------------------------

def _normalize_utc(dt: datetime, exchange_tz: str = _EXCHANGE_TZ) -> str:
    """Return the byte-identical UTC string PG produces via
    ``TO_CHAR(... AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000')``, e.g.
    ``'2026-06-22T13:30:00+0000'``.

    A NAIVE datetime is assumed exchange-local (IBKR ``formatDate=1`` bars) and
    localized via ZoneInfo (DST-correct per instant — NOT a fixed offset). An
    aware datetime is converted as-is. Polygon callers must pass an ALREADY-UTC-aware
    datetime (``datetime.fromtimestamp(t/1000, timezone.utc)`` from the RAW epoch — do
    NOT reuse polygon_source's local-naive ``item['datetime']``)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(exchange_tz))
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")


# --- WAL-safe backup ---------------------------------------------------------------

def backup_market_db(src_path: str, dest_path: str) -> Optional[str]:
    """WAL-safe snapshot of the market DB via the SQLite backup API (NOT a raw file
    copy — a ``.db`` copy can miss rows still in an uncheckpointed ``-wal`` sidecar).
    Returns dest_path on success, None if src is missing."""
    if not Path(src_path).exists():
        return None
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(dest_path).unlink(missing_ok=True)
    src = sqlite3.connect(src_path, timeout=10.0)
    try:
        dst = sqlite3.connect(dest_path)
        try:
            src.backup(dst)  # online backup — captures committed WAL pages too
        finally:
            dst.close()
    finally:
        src.close()
    return dest_path


# --- local-only preflight (regularize the live DB; reuse slice-1 helpers) ----------

def preflight_canonicalize(db_path: Optional[str] = None) -> dict:
    """LOCAL-ONLY (zero PG): create+seed ``ticker_aliases`` and PK-safely fold existing
    rows to canonical in the live market DB, so the read-side ``_canon`` stops being a
    no-op and a direct write can never introduce an alias spelling. Idempotent. Safe on a
    missing DB (no-op success) and a DB that already has aliases. MUST run before the
    first direct backfill (lock 8) — it does NOT lean on a PG incremental to create the
    table. Returns ``{ok, exists, created_aliases, folded:{table:count}}``."""
    path = db_path or resolve_market_db_path()
    if not Path(path).exists():
        return {"ok": True, "exists": False, "created_aliases": False, "folded": {},
                "note": "no local DB — nothing to regularize"}
    conn = sqlite3.connect(path, timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout = 10000")
        had = bool(conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ticker_aliases'"
        ).fetchone())
        _ensure_ticker_aliases(conn)
        folded: Dict[str, int] = {}
        for table in _CANON_DOMAINS:
            try:
                folded[table] = _canonicalize_table_tickers(conn, table)
            except sqlite3.OperationalError:
                folded[table] = 0  # table absent on a partial DB — tolerate (as incremental does)
        conn.commit()
        return {"ok": True, "exists": True, "created_aliases": not had, "folded": folded}
    finally:
        conn.close()


# --- gap detection (MISSING TRADING DAYS — day-presence, not bar-count) ------------

def detect_price_gaps(
    tickers: List[str],
    interval: str = "15min",
    lookback_days: int = 30,
    db_path: Optional[str] = None,
    *,
    today: Optional[date] = None,
) -> Dict[str, List[date]]:
    """Per-ticker MISSING TRADING DAYS over the trailing ``lookback_days`` window.

    A day is "missing" iff it is a US-equity TRADING day (weekends + US market holidays
    excluded via ``data_coverage_tools._market_day_status``) AND the local ``prices``
    table has ZERO bars for the (canonical) ticker at ``interval`` that day.

    This is DAY-PRESENCE, not completeness — a single bar marks a day present; partial-day
    bar-quality (early closes etc.) is intentionally out of scope (see 2b). The query
    ticker is resolved through ``ticker_aliases`` so an alias spelling finds canonical rows.
    Read-only; an absent prices table ⇒ every expected trading day is reported missing."""
    if not tickers:
        return {}
    end = today or datetime.now(timezone.utc).date()
    start = end - timedelta(days=lookback_days)
    expected = [d for d in _daterange(start, end) if _market_day_status(d)["is_trading_day"]]
    path = db_path or resolve_market_db_path()
    db_interval = _INTERVAL_DB.get(interval, interval)

    out: Dict[str, List[date]] = {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return {t: list(expected) for t in tickers}
    try:
        aliases = _load_ticker_aliases(conn)
        has_prices = bool(conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'").fetchone())
        for t in tickers:
            canon = aliases.get(t.upper(), t.upper())
            present: set = set()
            if has_prices:
                rows = conn.execute(
                    "SELECT DISTINCT substr(datetime, 1, 10) FROM prices "
                    "WHERE ticker = ? AND interval = ?", (canon, db_interval)).fetchall()
                present = {r[0] for r in rows}
            out[t] = [d for d in expected if d.isoformat() not in present]
    finally:
        conn.close()
    return out


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# --- provider_sync telemetry (NEW tables — NOT market_sync_meta) -------------------

_PROVIDER_SYNC_SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_sync_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider        TEXT NOT NULL,        -- 'ibkr' | 'polygon'
    domain          TEXT NOT NULL DEFAULT 'prices',
    interval        TEXT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    tickers_scanned INTEGER DEFAULT 0,
    gaps_found      INTEGER DEFAULT 0,
    rows_added      INTEGER DEFAULT 0,
    -- closed enum (matches JobRunsStore) — CHECK enforces it at the schema, not only the
    -- _finish_provider_run Python guard. provider/domain are intentionally NOT CHECK'd
    -- (extensible — more providers/domains likely; a CHECK there would force a migration).
    status          TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    error           TEXT
);
CREATE TABLE IF NOT EXISTS provider_sync_meta (
    provider          TEXT NOT NULL,
    ticker            TEXT NOT NULL,      -- CANONICAL spelling only
    interval          TEXT NOT NULL,
    last_success      TEXT,
    last_bar_datetime TEXT,
    last_error        TEXT,
    rows_added        INTEGER DEFAULT 0,
    updated_at        TEXT NOT NULL,
    PRIMARY KEY (provider, ticker, interval)
);
"""


def _ensure_provider_sync_tables(conn) -> None:
    """Idempotent create of provider_sync_runs + provider_sync_meta. Distinct from
    market_sync_meta (the PG-mirror status) — these record DIRECT provider→SQLite syncs."""
    conn.executescript(_PROVIDER_SYNC_SCHEMA)


def _start_provider_run(conn, *, provider: str, interval: str, domain: str = "prices") -> int:
    cur = conn.execute(
        "INSERT INTO provider_sync_runs (provider, domain, interval, started_at, status) "
        "VALUES (?, ?, ?, ?, 'running')",
        (provider, domain, interval, _now()))
    conn.commit()
    return int(cur.lastrowid)


def _finish_provider_run(conn, run_id: int, *, status: str, tickers_scanned: int,
                         gaps_found: int, rows_added: int, error: Optional[str]) -> None:
    if status not in _VALID_RUN_STATUSES or status == "running":
        raise ValueError(f"invalid terminal run status: {status!r} (allowed: succeeded|failed)")
    conn.execute(
        "UPDATE provider_sync_runs SET finished_at = ?, status = ?, tickers_scanned = ?, "
        "gaps_found = ?, rows_added = ?, error = ? WHERE id = ?",
        (_now(), status, tickers_scanned, gaps_found, rows_added, error, run_id))
    conn.commit()


def _upsert_provider_meta(conn, *, provider: str, ticker: str, interval: str,
                          last_bar_datetime: Optional[str], rows_added: int,
                          error: Optional[str]) -> None:
    """Per-(provider,ticker,interval) frontier. ``last_success`` advances only on a
    success (error is None); an error preserves the prior ``last_success``. ``ticker``
    must already be canonical (the caller canonicalizes before insert — lock 2)."""
    now = _now()
    last_success = None if error else now
    conn.execute(
        "INSERT INTO provider_sync_meta "
        "(provider, ticker, interval, last_success, last_bar_datetime, last_error, rows_added, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(provider, ticker, interval) DO UPDATE SET "
        "  last_success = COALESCE(excluded.last_success, provider_sync_meta.last_success), "
        "  last_bar_datetime = COALESCE(excluded.last_bar_datetime, provider_sync_meta.last_bar_datetime), "
        "  last_error = excluded.last_error, rows_added = excluded.rows_added, updated_at = excluded.updated_at",
        (provider, ticker, interval, last_success, last_bar_datetime, error, rows_added, now))
    conn.commit()
