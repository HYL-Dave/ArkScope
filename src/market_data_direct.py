"""Direct provider→SQLite market-data backfill (PG-exit slice #2).

Sibling of ``market_data_admin.py`` — that module's ``incremental_update`` is the
PG→SQLite MIRROR; this module writes the local ``prices`` table DIRECTLY from a
provider (IBKR primary / Polygon fallback) so local freshness no longer depends on
PG. No runtime PG dependency lives here.

Slice #2 COMPLETE — #2a (hermetic core) + #2b·1 (write lock) + #2b·2 (provider fetch +
write path) + #2c (completed-days-only gap rule). The scheduler ``price_backfill`` source
+ ``run_source`` guard live in ``src/service/data_scheduler.py``.
- ``backup_market_db``        : WAL-safe backup (SQLite backup API, NOT shutil.copyfile);
- ``preflight_canonicalize``  : local-only create+seed ticker_aliases + fold existing
                                rows (reuses slice-1 helpers); regularizes the live DB
                                BEFORE any direct write, without touching PG. Does NOT
                                take the write lock — its caller holds it (no nested flock);
- ``_normalize_utc``          : exchange-local/aware datetime → the byte-identical UTC PK
                                string PG produces (the load-bearing dedup invariant);
- ``market_write_lock``       : flocks the shared ``local_refresh.lock`` so a direct
                                write never races the PG→local mirror (2b·1);
- ``detect_price_gaps``       : per-ticker MISSING TRADING DAYS among COMPLETE days
                                (day-presence; weekend + US-holiday aware; the in-progress
                                ET day is excluded until close — 2c — NOT a per-day
                                bar-count completeness claim, see the naming note below);
- ``provider_sync_runs`` / ``provider_sync_meta`` tables + helpers (NEW; never
  ``market_sync_meta``, which means "PG mirror");
- ``_ibkr_bars_to_rows`` / ``_polygon_results_to_rows`` + ``backfill_prices_direct``
  (2b·2): IBKR-primary / Polygon-fallback fetch → canonicalize-before-insert →
  INSERT OR IGNORE → provider_sync telemetry, under ``market_write_lock``.

Deferred (B): bar-count completeness / early-close session model to HEAL an already-
partial day — day-presence only marks a complete day present once it has ≥1 bar.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime  # aliased — `time` (stdlib module) is used for monotonic()
from pathlib import Path
from typing import Any, Dict, List, Optional
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
# A US trading day counts as "complete" (eligible for gap-fill) only after this ET time —
# the RTH close (16:00) + a small settle buffer. Conservatively uses the REGULAR close even
# on early-close days (a half-day is then considered complete a few hours "late", which is
# harmless for a gap filler). Per-day bar-count completeness is deferred (see the docstring).
_RTH_COMPLETE_AFTER_ET = dtime(16, 30)
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


# --- trading-day completeness (shared by gap detection + top-up backfill) ----------

def _norm_now_et(now_et: Optional[datetime]) -> datetime:
    """Resolve the ET clock: None → now(ET); naive → assume ET; aware → convert to ET."""
    et = ZoneInfo(_EXCHANGE_TZ)
    if now_et is None:
        return datetime.now(et)
    if now_et.tzinfo is None:
        return now_et.replace(tzinfo=et)
    return now_et.astimezone(et)


def _is_session_complete(d: date, now_et: datetime) -> bool:
    """A US trading day is COMPLETE iff strictly before the current ET date, or it IS the
    current ET date and ET-now is past the close buffer (2c). A future ET day is never
    complete. Judged in America/New_York (NOT a UTC date)."""
    today_et = now_et.date()
    if d < today_et:
        return True
    if d == today_et:
        return now_et.timetz().replace(tzinfo=None) >= _RTH_COMPLETE_AFTER_ET
    return False


def _complete_trading_days(start: date, end: date, now_et: datetime) -> List[date]:
    """Complete US trading days in [start, end] — weekends + US holidays excluded,
    in-progress day excluded until close. The set a top-up backfill fetches over."""
    return [d for d in _daterange(start, end)
            if _market_day_status(d)["is_trading_day"] and _is_session_complete(d, now_et)]


# --- gap detection (MISSING TRADING DAYS — day-presence, not bar-count) ------------

def detect_price_gaps(
    tickers: List[str],
    interval: str = "15min",
    lookback_days: int = 30,
    db_path: Optional[str] = None,
    *,
    today: Optional[date] = None,
    now_et: Optional[datetime] = None,
    include_incomplete_today: bool = False,
) -> Dict[str, List[date]]:
    """Per-ticker MISSING TRADING DAYS over the trailing ``lookback_days`` window.

    A day is "missing" iff it is a US-equity TRADING day (weekends + US market holidays
    excluded via ``data_coverage_tools._market_day_status``), is COMPLETE (see below), AND
    the local ``prices`` table has ZERO bars for the (canonical) ticker at ``interval``.

    COMPLETED-DAYS-ONLY (2c): the in-progress US trading day is NOT a gap candidate until
    the session has closed — judged in **America/New_York** (NOT a UTC date, which would
    misclassify around the Taipei-morning / UTC-rollover boundary). A day is complete iff
    it is strictly before the current ET date, or it IS the current ET date and ET-now is
    past ``_RTH_COMPLETE_AFTER_ET``. This stops a mid-session run from filling a PARTIAL day
    (10 of ~26 bars) that day-presence would then freeze as "present" forever.
    ``include_incomplete_today=True`` opts out (counts the in-progress day too).

    Still DAY-PRESENCE among complete days, NOT bar-count completeness — a single bar marks
    a complete day present; healing an already-partial day (bar-count / early-close session
    model) is a deferred follow-up (B), intentionally out of scope here. The query ticker is
    resolved through ``ticker_aliases``. Read-only; an absent prices table ⇒ every expected
    (complete) trading day is reported missing."""
    if not tickers:
        return {}
    now_et = _norm_now_et(now_et)
    end = today or now_et.date()
    start = end - timedelta(days=lookback_days)
    expected = [
        d for d in _daterange(start, end)
        if _market_day_status(d)["is_trading_day"]
        and (include_incomplete_today or _is_session_complete(d, now_et))
    ]
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


# Conservative per-interval "thin day" threshold (A.1): below this many bars on a COMPLETE
# trading day, the whole day's coverage is suspiciously low (flagged 'thin' / 疑似不足, NOT a
# hard error). 15min regular RTH = 26 bars; <20 is clearly short. An interval with no entry is
# never flagged thin. NOTE: this is a blunt rule — a legitimate half-day / early close (~13-14
# 15min bars) will read as 'thin' until a proper early-close calendar lands (deferred B+).
_THIN_BAR_THRESHOLD = {"15min": 20}


def summarize_trading_day_coverage(
    tickers: List[str],
    interval: str = "15min",
    lookback_days: int = 10,
    db_path: Optional[str] = None,
    *,
    today: Optional[date] = None,
    now_et: Optional[datetime] = None,
    max_errors: int = 50,
) -> Dict[str, Any]:
    """READ-ONLY per-day universe price-coverage diagnostics — the operator view of "what's
    missing, can it be filled, is it even a trading day". NO PG, NO provider call, NO writes
    (opens ``market_data.db`` ``mode=ro``); it does not heal or schedule anything.

    For each calendar day in the trailing ``lookback_days`` window (newest-first) it reports:
      - weekend / US-market-holiday / regular trading day (``data_coverage_tools._market_day_status``);
      - ``session_complete`` for trading days (``_is_session_complete`` in America/New_York — the
        in-progress day is flagged, not counted as a gap);
      - across the (alias-canonicalized) universe: ``full`` / ``partial`` / ``missing`` counts +
        the missing & partial ticker lists. full/partial are RELATIVE to ``max_observed_bar_count``
        = the per-day MAX bar count across the universe — i.e. a per-ticker OUTLIER signal (which
        tickers lag the best-covered ones that day), NOT an absolute-completeness claim;
        ``missing`` = zero bars on that day.
      - ``coverage_status`` (the UI-facing label, A.1): ``non_trading`` / ``in_progress`` /
        ``missing`` (complete day, zero coverage) / ``thin`` (complete day but max bars below
        ``_THIN_BAR_THRESHOLD`` — 疑似不足, guards the trap where a uniformly-thin day's relative
        full/partial would otherwise read as complete) / ``complete_like``.
    Plus a ``provider_errors`` summary from ``provider_sync_meta.last_error`` (e.g. an IBKR
    contract that won't resolve — LC), so a recurring failure is visible instead of silently
    retried. Non-trading days carry null coverage. An absent DB ⇒ every trading day all-missing
    (honest), non-trading days still marked."""
    now_et = _norm_now_et(now_et)
    end = today or now_et.date()
    start = end - timedelta(days=lookback_days)
    db_interval = _INTERVAL_DB.get(interval, interval)
    path = db_path or resolve_market_db_path()

    aliases: Dict[str, str] = {}
    counts_by_day: Dict[str, Dict[str, int]] = {}
    provider_errors: List[Dict[str, Any]] = []
    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        conn = None
    if conn is not None:
        try:
            aliases = _load_ticker_aliases(conn)
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'").fetchone():
                for d, tk, n in conn.execute(
                    "SELECT substr(datetime,1,10) AS d, ticker, COUNT(*) AS n FROM prices "
                    "WHERE interval = ? AND substr(datetime,1,10) >= ? GROUP BY d, ticker",
                    (db_interval, start.isoformat())):
                    counts_by_day.setdefault(d, {})[tk] = int(n)
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='provider_sync_meta'").fetchone():
                provider_errors = [
                    {"ticker": r[0], "interval": r[1], "last_error": r[2], "updated_at": r[3]}
                    for r in conn.execute(
                        "SELECT ticker, interval, last_error, updated_at FROM provider_sync_meta "
                        "WHERE last_error IS NOT NULL AND interval = ? ORDER BY updated_at DESC LIMIT ?",
                        (db_interval, max_errors))]
        finally:
            conn.close()

    canon_universe = sorted({aliases.get(t.upper(), t.upper()) for t in tickers})

    days: List[Dict[str, Any]] = []
    for d in sorted(_daterange(start, end), reverse=True):
        iso = d.isoformat()
        mds = _market_day_status(d)
        if not mds["is_trading_day"]:
            days.append({
                "date": iso, "is_trading_day": False, "reason": mds["reason"],
                "holiday": mds["holiday"], "session_complete": None,
                "coverage_status": "non_trading", "max_observed_bar_count": None,
                "full": None, "partial": None, "missing": None, "covered": None,
                "missing_tickers": [], "partial_tickers": [],
            })
            continue
        complete = _is_session_complete(d, now_et)
        present = {t: counts_by_day.get(iso, {}).get(t, 0) for t in canon_universe}
        present = {t: n for t, n in present.items() if n > 0}
        day_max = max(present.values()) if present else 0
        partial = sorted(
            ({"ticker": t, "bars": n} for t, n in present.items() if 0 < n < day_max),
            key=lambda x: x["ticker"])
        missing = sorted(t for t in canon_universe if t not in present)
        if not complete:
            status = "in_progress"                       # session not closed → don't judge thin
        elif not present:
            status = "missing"                           # complete trading day, zero coverage
        elif day_max < _THIN_BAR_THRESHOLD.get(db_interval, 0):
            status = "thin"                              # data present but suspiciously low
        else:
            status = "complete_like"
        days.append({
            "date": iso, "is_trading_day": True, "reason": mds["reason"], "holiday": None,
            "session_complete": complete,
            "coverage_status": status,
            "max_observed_bar_count": day_max,
            "full": sum(1 for n in present.values() if day_max and n >= day_max),
            "partial": len(partial),
            "missing": len(missing),
            "covered": len(present),
            "missing_tickers": missing,
            "partial_tickers": partial,
        })

    return {
        "interval": interval,
        "lookback_days": lookback_days,
        "universe_count": len(canon_universe),
        "generated_at_et": now_et.isoformat(),
        "days": days,
        "provider_errors": provider_errors,
    }


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

_IBKR_CONNECT_TIMEOUT_S = 15  # short cold-connect timeout (default 60 churned ~5min when down)


def _default_ibkr_src():  # pragma: no cover - exercised live (or via monkeypatch in tests)
    from data_sources.ibkr_source import IBKRDataSource
    return IBKRDataSource(timeout=_IBKR_CONNECT_TIMEOUT_S)


def _default_polygon_src():  # pragma: no cover - exercised live (or via monkeypatch in tests)
    from data_sources.polygon_source import PolygonDataSource
    return PolygonDataSource()


def _fetch_rows_for_gaps(canon, fetch_days, interval, provider, ibkr_src, polygon_src) -> List[tuple]:
    """Provider bars for the COMPLETE-day window → canonical rows (top-up; ``fetch_days`` is
    every complete trading day to cover, not just zero-bar gaps). IBKR primary fetches the
    CONTIGUOUS [min,max] span in one request (auto-chunked; INSERT OR IGNORE dedupes).

    Polygon fallback (per day) engages whenever IBKR returns NO bars for the span. Note the
    failure granularity of ``IBKRDataSource.fetch_historical_intraday`` (verified):
      - a COLD-CONNECT failure (Gateway down/unreachable at first connect) RAISES
        ``ConnectionError`` → propagates out → recorded as a per-ticker error (loud). Polygon
        is NOT reached.
      - a REQUEST-LEVEL failure once connected (mid-session disconnect, pacing rejection,
        timeout, no-data/error-162) is swallowed by the adapter (logs + continues) and
        returns an EMPTY result, NOT a raise. So it is INDISTINGUISHABLE here from "symbol
        genuinely absent on IBKR" — both fall through to Polygon. A real IBKR hiccup is
        therefore masked as a Polygon substitution (data stays correct — Polygon rows
        byte-match the UTC PK + INSERT OR IGNORE — but provider_sync_meta won't flag the IBKR
        problem). Distinguishing the two needs the adapter to surface per-chunk errors; that
        observability fix is a DEFERRED follow-up (best done with the recurring scheduler)."""
    start, end = min(fetch_days), max(fetch_days)
    rows: List[tuple] = []
    if provider == "ibkr" and ibkr_src is not None:
        by_ticker = ibkr_src.fetch_historical_intraday([canon], start, end, interval="15 mins")
        bars = by_ticker.get(canon, []) if isinstance(by_ticker, dict) else []
        rows = _ibkr_bars_to_rows(canon, bars, interval)
    if not rows and polygon_src is not None:  # IBKR reachable-but-empty → Polygon (NOT on a raise)
        for day in fetch_days:
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
    now_et: Optional[datetime] = None,
) -> dict:
    """Direct provider→SQLite price backfill (FULL-WINDOW TOP-UP, 2d) — heal sparse/partial
    days in the local ``prices`` table from a provider (IBKR primary / Polygon fallback), no PG.

    TOP-UP not zero-bar-gap (the canary finding): a day with 1 of 26 bars is day-presence
    "present" yet actually broken (IBKR has the full day). So this fetches EVERY COMPLETE
    trading day in the lookback window per ticker and ``INSERT OR IGNORE``s — present bars
    dedupe on the PK, missing bars fill. Heals sparse days (1→26) and tops up partial days on
    a later run once the provider has them, with NO bar-count/early-close session model. The
    in-progress ET day is excluded (2c) so we don't churn today every run; a partial today
    completes on a later run after close. NOTE: INSERT OR IGNORE only ADDS missing bars — it
    does not correct an existing wrong OHLCV value (out of scope; the problem is missing/sparse).

    Holds ``market_write_lock`` ONCE (serializes vs the PG→local mirror); inside it
    ``preflight_canonicalize`` (does NOT re-take the lock — no nested flock) → per-ticker
    fetch → canonical-row INSERT OR IGNORE → telemetry. Tickers canonicalized + deduped
    before fetch/insert. Per-ticker failure isolated (never aborts the batch); EMPTY scope
    fails loud. ``ibkr_src``/``polygon_src`` injectable for tests, else lazily constructed.
    Scheduler adapter calls with ``tickers_arg`` (CSV) + ``progress_cb``."""
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

    # 2e PREFLIGHT: for the IBKR path, verify the Gateway API handshake BEFORE taking the
    # market write lock. A cold-connect failure fails the run FAST and LOUD here — never
    # holding the DB write lock while churning (the unattended-scheduler hazard the live
    # re-canary exposed), never creating a dangling 'running' provider_sync_runs row. Only
    # gates IBKR; provider='polygon' has no Gateway dependency. Best-effort connect() probe;
    # if the source has no connect() (older/test doubles) the preflight is skipped.
    if provider == "ibkr" and ibkr_src is not None and hasattr(ibkr_src, "connect"):
        try:
            ok = ibkr_src.connect()
        except Exception as e:  # noqa: BLE001 — surface as a loud run failure
            raise RuntimeError(f"IBKR preflight connect failed: {e}") from e
        if not ok:
            raise RuntimeError(
                "IBKR preflight connect failed: Gateway API handshake not established "
                "(TCP may be open but the API session is down — check login / API enabled / "
                "client-id). Run aborted before acquiring the market write lock.")

    now_et = _norm_now_et(now_et)
    end = today or now_et.date()
    start = end - timedelta(days=lookback_days)
    fetch_days = _complete_trading_days(start, end, now_et)  # the top-up window (2c-gated)
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
                        # TOP-UP: fetch the WHOLE complete-day window (not just zero-bar days)
                        # so sparse/partial days heal. INSERT OR IGNORE dedupes present bars.
                        # zero-bar days are still counted for reporting (informative only).
                        zero_bar = detect_price_gaps([canon], interval=interval,
                                                     lookback_days=lookback_days, db_path=path,
                                                     today=end, now_et=now_et)[canon]
                        rollup["gaps_found"] += len(zero_bar)
                        if fetch_days:
                            rows = _fetch_rows_for_gaps(canon, fetch_days, interval, provider,
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
