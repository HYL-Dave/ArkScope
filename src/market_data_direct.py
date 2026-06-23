"""Direct provider→SQLite market-data backfill (PG-exit slice #2).

Sibling of ``market_data_admin.py`` — that module's ``incremental_update`` is the
PG→SQLite MIRROR; this module writes the local ``prices`` table DIRECTLY from a
provider (IBKR primary / Polygon fallback) so local freshness no longer depends on
PG. No runtime PG dependency lives here.

Slice #2a (hermetic core) + #2b·1 (write lock) + #2b·2 (provider fetch + write path):
- ``backup_market_db``        : WAL-safe backup (SQLite backup API, NOT shutil.copyfile);
- ``preflight_canonicalize``  : local-only create+seed ticker_aliases + fold existing
                                rows (reuses slice-1 helpers); regularizes the live DB
                                BEFORE any direct write, without touching PG. Does NOT
                                take the write lock — its caller holds it (no nested flock);
- ``_normalize_utc``          : exchange-local/aware datetime → the byte-identical UTC PK
                                string PG produces (the load-bearing dedup invariant);
- ``market_write_lock``       : flocks the shared ``local_refresh.lock`` so a direct
                                write never races the PG→local mirror (2b·1);
- ``detect_price_gaps``       : per-ticker MISSING TRADING DAYS (day-presence; weekend +
                                US-holiday aware — NOT a per-day bar-count completeness
                                claim, see the naming note below);
- ``provider_sync_runs`` / ``provider_sync_meta`` tables + helpers (NEW; never
  ``market_sync_meta``, which means "PG mirror");
- ``_ibkr_bars_to_rows`` / ``_polygon_results_to_rows`` + ``backfill_prices_direct``
  (2b·2): IBKR-primary / Polygon-fallback fetch → canonicalize-before-insert →
  INSERT OR IGNORE → provider_sync telemetry, under ``market_write_lock``.

Still slice #2b·3 (NOT in this file yet): the scheduler ``price_backfill`` source +
``run_source`` guard (skip ``_local_refresh`` for a ``sync_flag=None`` adapter) + live smoke.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from src.market_data_admin import (
    _PRICE_INSERT,
    _PRICES_SCHEMA,
    _canonicalize_table_tickers,
    _ensure_ticker_aliases,
    _load_ticker_aliases,
    _now,
    resolve_market_db_path,
)
from src.tools.data_coverage_tools import _market_day_status

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
# SAME flock file the scheduler's _LOCAL_REFRESH_FLOCK uses ("local_refresh") — so a
# direct backfill and the PG→local mirror (data_scheduler._local_refresh) can NEVER write
# market_data.db concurrently. flock-per-FD mutexes both same-process and cross-process
# (verified), so no shared threading.Lock / data_scheduler import is needed.
_MARKET_WRITE_LOCK_NAME = "local_refresh"

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


# --- market-write lock (serialize vs the PG→local mirror) --------------------------

def _market_lock_path() -> Path:
    """The flock file market writes serialize on — identical to data_scheduler._lock_dir()
    / 'local_refresh.lock' (env ARKSCOPE_LOCK_DIR override, else <repo>/data/locks), so the
    direct backfill and the scheduler's mirror share ONE cross-process lock."""
    base = Path(os.environ.get("ARKSCOPE_LOCK_DIR") or (_PROJECT_ROOT / "data" / "locks"))
    return base / f"{_MARKET_WRITE_LOCK_NAME}.lock"


@contextmanager
def market_write_lock(timeout: float = 30.0, poll: float = 0.5):
    """Serialize market_data.db WRITES (direct backfill, preflight) against the PG→local
    mirror by flocking the shared ``local_refresh.lock``. flock-per-FD mutexes same-process
    AND cross-process; the kernel frees it on close/crash so a dead writer never wedges it.
    Raises TimeoutError if the lock can't be taken within ``timeout``. Degrades to a no-op
    (with a one-time warning) where fcntl is unavailable (non-POSIX), matching _FileLock."""
    try:
        import fcntl
    except ImportError:  # non-POSIX
        logger.warning("fcntl unavailable — market_write_lock degraded to no-op")
        yield
        return
    path = _market_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("market_data.db write lock busy (timeout)")
                time.sleep(poll)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:  # noqa: BLE001 — close drops the lock regardless
            pass
        fh.close()


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


# --- 2b·2: provider bar → canonical prices-row mappers -----------------------------

def _safe_ohlcv(o, h, l, c, v):
    """(o,h,l,c,int(v)) with floats, or None if any OHLC is missing/NaN (unusable bar).
    Volume NaN/None → 0 (a low-liquidity 0-volume bar is valid; a NaN is not a number)."""
    for x in (o, h, l, c):
        if x is None or (isinstance(x, float) and x != x):  # None or NaN
            return None
    try:
        vol = int(v) if (v is not None and v == v) else 0
    except (TypeError, ValueError):
        vol = 0
    return (float(o), float(h), float(l), float(c), vol)


def _ibkr_bars_to_rows(canon: str, bars, interval: str) -> List[tuple]:
    """IBKR IntradayBar list → prices rows under the CANONICAL ticker. formatDate=1 bars
    carry an exchange-local NAIVE datetime → _normalize_utc localizes to the UTC PK string.
    Bars with NaN/None OHLC are dropped."""
    db_interval = _INTERVAL_DB.get(interval, interval)
    rows = []
    for b in bars:
        ohlcv = _safe_ohlcv(b.open, b.high, b.low, b.close, b.volume)
        if ohlcv is None:
            continue
        rows.append((canon, _normalize_utc(b.datetime), db_interval, *ohlcv))
    return rows


def _polygon_results_to_rows(canon: str, results, interval: str) -> List[tuple]:
    """Polygon raw agg results → prices rows. Uses the RAW epoch-ms ``t`` (UTC) → an
    aware-UTC datetime — NOT polygon_source's mutated ``item['datetime']`` (LOCAL-naive,
    which would mis-stamp the PK). ``o/h/l/c/v`` are the agg keys."""
    db_interval = _INTERVAL_DB.get(interval, interval)
    rows = []
    for r in results:
        t = r.get("t")
        if t is None:
            continue
        dt = datetime.fromtimestamp(t / 1000, timezone.utc)
        ohlcv = _safe_ohlcv(r.get("o"), r.get("h"), r.get("l"), r.get("c"), r.get("v"))
        if ohlcv is None:
            continue
        rows.append((canon, _normalize_utc(dt), db_interval, *ohlcv))
    return rows


# --- 2b·2: backfill orchestration --------------------------------------------------

def _default_ibkr_src():  # pragma: no cover - exercised live (or via monkeypatch in tests)
    from data_sources.ibkr_source import IBKRDataSource
    return IBKRDataSource()


def _default_polygon_src():  # pragma: no cover - exercised live (or via monkeypatch in tests)
    from data_sources.polygon_source import PolygonDataSource
    return PolygonDataSource()


def _fetch_rows_for_gaps(canon, gaps, interval, provider, ibkr_src, polygon_src) -> List[tuple]:
    """Provider bars for a ticker's gap days → canonical rows. IBKR primary fetches the
    CONTIGUOUS [min,max] gap span (auto-chunked; INSERT OR IGNORE drops the over-fetch).

    Polygon fallback (per gap-day) engages ONLY when IBKR is REACHABLE but RETURNS NO
    bars (e.g. the symbol isn't on IBKR / no data for those days). A Gateway/API
    CONNECTION failure makes ``fetch_historical_intraday`` RAISE — that propagates out of
    here and is handled as a per-ticker error upstream (recorded in provider_sync_meta),
    NOT silently masked by Polygon. So a misconfigured/down Gateway fails LOUD, by design;
    it does not quietly switch providers."""
    start, end = min(gaps), max(gaps)
    rows: List[tuple] = []
    if provider == "ibkr" and ibkr_src is not None:
        by_ticker = ibkr_src.fetch_historical_intraday([canon], start, end, interval="15 mins")
        bars = by_ticker.get(canon, []) if isinstance(by_ticker, dict) else []
        rows = _ibkr_bars_to_rows(canon, bars, interval)
    if not rows and polygon_src is not None:  # IBKR reachable-but-empty → Polygon (NOT on a raise)
        for day in gaps:
            results = polygon_src.fetch_intraday_prices(canon, day, multiplier=15, timespan="minute")
            rows.extend(_polygon_results_to_rows(canon, results or [], interval))
    return rows


def _insert_rows(conn, rows) -> int:
    """INSERT OR IGNORE the canonical rows; return how many were ACTUALLY inserted
    (total_changes delta — IGNORE'd duplicates don't count)."""
    if not rows:
        return 0
    before = conn.total_changes
    conn.executemany(_PRICE_INSERT, rows)
    conn.commit()
    return conn.total_changes - before


def backfill_prices_direct(
    tickers_arg: Optional[str] = None,
    interval: str = "15min",
    lookback_days: int = 5,
    provider: str = "ibkr",
    db_path: Optional[str] = None,
    progress_cb=None,
    *,
    ibkr_src=None,
    polygon_src=None,
    today: Optional[date] = None,
) -> dict:
    """Direct provider→SQLite price backfill: fill MISSING TRADING DAYS in the local
    ``prices`` table from a provider (IBKR primary / Polygon fallback) — no PG.

    Holds ``market_write_lock`` ONCE at the outer level (serializes vs the PG→local
    mirror); inside it: ``preflight_canonicalize`` (regularizes the live DB — does NOT
    re-take the lock, so no nested-flock self-block), then per-ticker gap-detect → fetch →
    canonical-row INSERT OR IGNORE → telemetry. Tickers are canonicalized + deduped BEFORE
    fetch/insert (lock 2). A per-ticker failure is recorded and isolated (never aborts the
    batch); an EMPTY scope fails loud. ``ibkr_src``/``polygon_src`` are injectable for
    tests; unset → lazily constructed (live). The scheduler adapter calls this with
    ``tickers_arg`` (CSV) + ``progress_cb`` (drop-in like collect_polygon_news)."""
    path = db_path or resolve_market_db_path()
    if tickers_arg is not None:
        raw = [t.strip() for t in tickers_arg.split(",") if t.strip()]
    else:
        from src.universe_scope import resolve_active_universe
        raw = list(resolve_active_universe() or [])
    if not raw:
        raise RuntimeError("backfill_prices_direct: empty ticker scope (active universe unavailable)")

    if provider == "ibkr":
        if ibkr_src is None:
            ibkr_src = _default_ibkr_src()
        if polygon_src is None:
            # IBKR primary + Polygon FALLBACK (the documented design) — also on the live
            # path, not just when a test injects polygon_src. Best-effort: a missing
            # POLYGON_API_KEY (construction raises) must NOT break the IBKR-only backfill.
            try:
                polygon_src = _default_polygon_src()
            except Exception:  # noqa: BLE001
                logger.info("Polygon fallback unavailable (e.g. no API key); IBKR-only backfill")
                polygon_src = None
    elif provider == "polygon" and polygon_src is None:
        polygon_src = _default_polygon_src()

    end = today or datetime.now(timezone.utc).date()
    rollup = {"provider": provider, "tickers_scanned": 0, "gaps_found": 0,
              "rows_added": 0, "errors": {}}

    with market_write_lock():
        preflight_canonicalize(path)  # local-only regularize; does NOT take the lock
        conn = sqlite3.connect(path, timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout = 10000")
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            # Setup (schema / ensure-tables / load-aliases / _start_provider_run) runs
            # BEFORE the run is recorded, so a failure here is intentionally fail-loud with
            # NO provider_sync_runs audit row — it cannot be: the run/table don't exist yet.
            # The conn is still closed + the lock released (outer try/finally + the `with`).
            conn.executescript(_PRICES_SCHEMA)  # tolerate a fresh DB
            _ensure_provider_sync_tables(conn)
            aliases = _load_ticker_aliases(conn)
            # canonicalize + dedupe scope (lock 2: never fetch/insert an alias spelling)
            scope, seen = [], set()
            for t in raw:
                c = aliases.get(t.upper(), t.upper())
                if c not in seen:
                    seen.add(c)
                    scope.append(c)
            run_id = _start_provider_run(conn, provider=provider, interval=interval)
            total = len(scope)
            try:
                for i, canon in enumerate(scope, 1):
                    rollup["tickers_scanned"] += 1
                    try:
                        gaps = detect_price_gaps([canon], interval=interval,
                                                 lookback_days=lookback_days, db_path=path,
                                                 today=end)[canon]
                        if gaps:
                            rollup["gaps_found"] += len(gaps)
                            rows = _fetch_rows_for_gaps(canon, gaps, interval, provider,
                                                        ibkr_src, polygon_src)
                            added = _insert_rows(conn, rows)
                            rollup["rows_added"] += added
                            last_bar = rows[-1][1] if rows else None
                            _upsert_provider_meta(conn, provider=provider, ticker=canon,
                                                  interval=interval, last_bar_datetime=last_bar,
                                                  rows_added=added, error=None)
                        else:
                            _upsert_provider_meta(conn, provider=provider, ticker=canon,
                                                  interval=interval, last_bar_datetime=None,
                                                  rows_added=0, error=None)
                    except Exception as e:  # noqa: BLE001 — per-ticker isolation, never fatal
                        rollup["errors"][canon] = str(e)
                        # The recovery telemetry write must itself be best-effort: if it
                        # raises (same conn already faulting — disk/lock), it must NOT escape
                        # to the outer handler and reclassify a per-ticker error as a fatal
                        # batch abort (that would defeat the isolation guarantee).
                        try:
                            _upsert_provider_meta(conn, provider=provider, ticker=canon,
                                                  interval=interval, last_bar_datetime=None,
                                                  rows_added=0, error=str(e))
                        except Exception:  # noqa: BLE001
                            logger.warning("provider_sync_meta write failed for %s (per-ticker "
                                           "error recovery); continuing", canon, exc_info=True)
                    if progress_cb:
                        progress_cb(i, total, canon)
            except Exception as e:  # a non-per-ticker failure (rare) fails the whole run
                # Best-effort finalize: if the 'failed' write itself raises, it must NOT
                # mask the original error (the bare `raise` re-propagates it + its traceback).
                try:
                    _finish_provider_run(conn, run_id, status="failed",
                                         tickers_scanned=rollup["tickers_scanned"],
                                         gaps_found=rollup["gaps_found"],
                                         rows_added=rollup["rows_added"], error=str(e))
                except Exception:  # noqa: BLE001
                    logger.warning("provider_sync_runs failed-finalize write failed; "
                                   "run row may stay 'running'", exc_info=True)
                raise
            _finish_provider_run(conn, run_id, status="succeeded",
                                 tickers_scanned=rollup["tickers_scanned"],
                                 gaps_found=rollup["gaps_found"],
                                 rows_added=rollup["rows_added"], error=None)
        finally:
            conn.close()
    return rollup
