"""
data_scheduler — app-owned, per-source data collection scheduling (slice 3e-D v1).

The user directive (2026-06-10/11): the app/sidecar is the ONLY scheduler owner —
no cron, not even as a transition. Each SOURCE is independent (they always were;
daily_update just ran them serially), with its OWN enable flag + interval set in
Settings, executing in parallel where safe.

Sources v1:
  - polygon_news / finnhub_news      — IN-PROCESS adapters (the collector modules
    are import-safe; run_incremental() returns structured stats like new_articles
    instead of an opaque exit code); independent, can run concurrently
  - ibkr_news / ibkr_prices / iv_history — collector SUBPROCESSES, serialized
    behind ONE shared IBKR lock (one Gateway session; client-id hygiene + the
    ib_insync asyncio loop is safer in its own process)
  - local_incremental                 — app-native PG → local market_data.db delta
    (market_data_admin.incremental_update)

After a non-news collector succeeds, its data is synced to PG
(migrate_to_supabase --prices/--iv, serialized behind a global sync lock —
concurrent syncs are idempotent but wasteful), then the local mirror refreshes
(incremental_update, skip-if-busy). News is post-N8a PG-exited: provider fetches
write normalized SQLite and project the legacy local read surface directly.

Write-contention guarantees (the user's explicit SQLite concern):
  - collectors write per-source Parquet dirs — disjoint, safe in parallel;
  - PG writes are idempotent upserts, serialized by _SYNC_LOCK anyway;
  - the local SQLite is written ONLY by incremental_update (WAL + busy_timeout,
    INSERT OR IGNORE) — serialized here by a skip-if-busy lock, and
    financial_cache writes are already serialized by _CACHE_WRITE_LOCK;
  - per-source locks make same-source runs skip (never queue), so a slow run
    cannot pile up behind itself;
  - CROSS-PROCESS: every lock above has a file-lock twin (flock(2) under
    data/locks/). threading.Lock only serializes threads of ONE process, but the
    daily_update CLI is a separate process running this same run_source — without
    the file locks a CLI run could double-fetch a source the app scheduler is
    already collecting (worst: two IBKR sessions fighting the same Gateway).
    flock auto-releases on process death, so a crashed run never wedges the lock.

Config (locked fork F3): namespaced profile_settings keys —
``schedule.<source>.enabled`` ("true"/"false", DEFAULT FALSE: nothing fetches
until the user opts in per source) and ``schedule.<source>.interval_minutes``.
Telemetry: every run is a job_runs row ``collect.<source>`` with
trigger_source='scheduler' | 'api' (Run now). Due-ness is computed from the last
ATTEMPT (any terminal state) so the interval doubles as the retry backoff, seeded
at startup from job_runs (manual daily_update step runs count via the alias map —
a manual run 10 minutes ago means the scheduler does not re-fetch immediately).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COLLECT_DIR = _REPO_ROOT / "scripts" / "collection"
_MIGRATE = _REPO_ROOT / "scripts" / "migrate_to_supabase.py"

TICK_SECONDS = 30
_IBKR_LOCK_TIMEOUT_S = 1800  # one slow IBKR job must not deadlock the others forever
_ERROR_TAIL = 600


@dataclass(frozen=True)
class SourceDef:
    name: str
    label: str
    collector: Optional[List[str]]      # argv after sys.executable; None = no subprocess
    sync_flag: Optional[str]            # migrate_to_supabase flag, None = no PG sync
    ibkr: bool = False                  # serialize behind the shared IBKR lock
    needs_price_scope: bool = False     # resolve active-universe tickers at run time
    default_interval_min: int = 60
    description: str = ""
    # Pass the ACTIVE UNIVERSE (profile DB, read-only) as the explicit ticker
    # list — the collectors' own default is the LEGACY config/tickers_core.json
    # tiers; the universe is the in-app authority (best-effort: falls back to the
    # collector default with a warning when the profile DB is unavailable).
    universe_tickers: bool = False
    # In-process provider adapter: (module, function) resolved lazily at run time.
    # The news collectors are import-safe modules now — calling run_incremental()
    # in-process gives structured stats (new_articles) instead of an opaque exit
    # code, with zero logic duplication. IBKR sources deliberately STAY subprocess:
    # process isolation is a feature there (ib_insync asyncio + client-id hygiene).
    adapter: Optional[tuple] = None
    # v1.3: gap-aware planning. When True, the adapter run computes scope from the
    # trading-day coverage diagnostic (planner) instead of the full universe — bounded
    # tickers + a window that reaches the oldest gap; a budget-bounded run finishes
    # `partial` with a saved continuation. Today only price_backfill.
    gap_planned: bool = False
    # When set ('polygon'|'finnhub'), resolve the Task 1 news write route per source run.
    # NORMALIZED and LEGACY_LOCAL write local DB directly; LEGACY_PG keeps the collector→PG→mirror
    # chain; BLOCKED fails closed before provider work.
    news_direct_source: Optional[str] = None


SOURCES: Dict[str, SourceDef] = {
    s.name: s
    for s in (
        SourceDef(
            "polygon_news", "Polygon 新聞",
            None, "--news",
            adapter=("scripts.collection.collect_polygon_news", "run_incremental"),
            universe_tickers=True, default_interval_min=60, news_direct_source="polygon",
            description="Polygon news incremental → normalized SQLite + legacy local projection (no news PG sync/mirror)",
        ),
        SourceDef(
            "finnhub_news", "Finnhub 新聞",
            None, "--news",
            adapter=("scripts.collection.collect_finnhub_news", "run_incremental"),
            universe_tickers=True, default_interval_min=60, news_direct_source="finnhub",
            description="Finnhub news incremental → normalized SQLite + legacy local projection (no news PG sync/mirror)",
        ),
        SourceDef(
            "ibkr_news", "IBKR 新聞",
            ["collect_ibkr_news.py", "--incremental"], "--news", ibkr=True,
            needs_price_scope=True, default_interval_min=120,
            news_direct_source="ibkr",
            description="IBKR news incremental (Gateway) → normalized SQLite + legacy local projection (no news PG sync/mirror)",
        ),
        SourceDef(
            "ibkr_prices", "IBKR 股價",
            ["collect_ibkr_prices.py", "--incremental", "--minute-only"], "--prices",
            ibkr=True, needs_price_scope=True, default_interval_min=60,
            description="IBKR 15min bars for the active universe → PG → local mirror",
        ),
        SourceDef(
            "iv_history", "IV 歷史",
            ["collect_iv_history.py"], "--iv", ibkr=True,
            needs_price_scope=True, default_interval_min=1440,
            description="ATM IV snapshot (heavy; Gateway) → PG → local mirror",
        ),
        SourceDef(
            "local_incremental", "本地鏡像增量",
            None, None, default_interval_min=15,
            description="PG → market_data.db delta only (no provider fetch)",
        ),
        SourceDef(
            "price_backfill", "本地價格直連補抓",
            None, None, ibkr=True, universe_tickers=True, default_interval_min=360,
            adapter=("src.market_data_direct", "backfill_prices_direct"),
            gap_planned=True,   # v1.3: planner decides scope from coverage, not the full universe
            description="IBKR/Polygon → market_data.db DIRECT (no PG); fills missing "
                        "trading-day gaps for the active universe. sync_flag=None → no PG "
                        "sync AND no _local_refresh (it writes the local DB itself).",
        ),
    )
}

# daily_update step names whose runs count toward a source's last-attempt (a
# manual backfill run suppresses an immediate scheduler re-fetch).
_DAILY_UPDATE_ALIAS = {
    "polygon_news": "daily_update.polygon",
    "finnhub_news": "daily_update.finnhub",
    "ibkr_news": "daily_update.ibkr_news",
    "ibkr_prices": "daily_update.ibkr_prices",
    "iv_history": "daily_update.iv_history",
}

# --- locks (single sidecar process) -------------------------------------------
# The Gateway lock (in-process + cross-process) now lives in src.ibkr_gateway_lock so EVERY
# IBKR consumer — this scheduler, the standalone direct price backfill, and the future intraday
# operation — serializes on the SAME mutex. _FileLock / _lock_dir moved there too (shared infra
# for all the flocks below); imported here so the other flocks keep identical behavior.
from src.ibkr_gateway_lock import (  # noqa: E402
    IBKR_FILE_LOCK as _IBKR_FLOCK,
    IBKR_THREAD_LOCK as _IBKR_LOCK,
    FileLock as _FileLock,
    lock_dir as _lock_dir,
)

_SOURCE_LOCKS: Dict[str, threading.Lock] = {name: threading.Lock() for name in SOURCES}
_SYNC_LOCK = threading.Lock()    # one migrate_to_supabase at a time
_LOCAL_REFRESH_LOCK = threading.Lock()  # one incremental_update at a time (skip-if-busy)

# --- cross-process lock twins (sidecar ⟷ daily_update CLI) ---------------------
_SOURCE_FLOCKS: Dict[str, _FileLock] = {name: _FileLock(f"source_{name}") for name in SOURCES}
_SYNC_FLOCK = _FileLock("pg_sync")
_LOCAL_REFRESH_FLOCK = _FileLock("local_refresh")

# in-memory last-attempt per source (UTC); seeded from job_runs on scheduler start
_LAST_ATTEMPT: Dict[str, datetime] = {}
_LAST_ATTEMPT_LOCK = threading.Lock()

# last run_source OUTCOME per source — including SKIPS, which write no job_runs
# row. Run-now is fire-and-return: the route answers "started" before the thread
# decides, so without this a cross-process skip ("CLI already running it") would
# be invisible to the UI (no job row, running=false → looks like nothing happened).
_LAST_RESULT: Dict[str, Dict[str, Any]] = {}
_LAST_RESULT_LOCK = threading.Lock()


def _record_result(result: Dict[str, Any]) -> Dict[str, Any]:
    with _LAST_RESULT_LOCK:
        _LAST_RESULT[result.get("source", "?")] = {
            **result, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return result

# live per-source progress, fed by the in-process adapters' progress_cb (the
# rough estimate the UI shows: ticker N of TOTAL — only adapter sources have it;
# subprocess sources stay indeterminate)
_PROGRESS: Dict[str, Dict[str, Any]] = {}
_PROGRESS_LOCK = threading.Lock()


def _set_progress(source: str, done: int, total: int, current: str) -> None:
    with _PROGRESS_LOCK:
        _PROGRESS[source] = {"done": done, "total": total, "current": current}


def _clear_progress(source: str) -> None:
    with _PROGRESS_LOCK:
        _PROGRESS.pop(source, None)


def job_name(source: str) -> str:
    return f"collect.{source}"


# --- config (profile_settings; locked F3) --------------------------------------

def _store():
    from src.api.dependencies import get_profile_store

    return get_profile_store()


# v1.2: durable per-source scheduler state in profile_state.db (recoverable + visible-failure).
# Cached singleton; best-effort everywhere (a store error must never break collection).
_SCHED_STATE = None


def _state_store():
    global _SCHED_STATE
    if _SCHED_STATE is None:
        from src.app_records_store import resolve_profile_state_db_path
        from src.scheduler_state import SchedulerStateStore
        _SCHED_STATE = SchedulerStateStore(resolve_profile_state_db_path(None))
    return _SCHED_STATE


# v1.3 gap-aware price_backfill budget (env/profile-overridable later; bounded defaults now).
_BACKFILL_MAX_TICKERS = 30
_BACKFILL_MAX_DAYS = 30
_NORMALIZED_NEWS_MAX_ARTICLES = 50_000
_NORMALIZED_NEWS_MAX_BODY_FETCHES = 50_000
_SANITIZED_WORKER_COUNT_KEYS = (
    "articles_seen",
    "articles_inserted",
    "bodies_fetched",
    "legacy_rows_inserted",
    "legacy_rows_updated",
    "projection_skipped_no_ticker",
)


def _make_normalized_news_provider(source: str):
    """Build the Parquet-free normalized REST provider for a scheduler news source."""
    if source == "polygon":
        from scripts.collection.collect_polygon_news import (
            CollectionConfig,
            PolygonNewsCollector,
            load_env,
        )
        from src.news_normalized.provider_adapters import PolygonNormalizedProvider

        api_key = load_env()
        if not api_key:
            raise RuntimeError("POLYGON_API_KEY not found in config/.env or environment")
        return PolygonNormalizedProvider(PolygonNewsCollector(api_key, CollectionConfig()))
    if source == "finnhub":
        from scripts.collection.collect_finnhub_news import (
            FinnhubConfig,
            FinnhubNewsCollector,
            load_env,
        )
        from src.news_normalized.provider_adapters import FinnhubNormalizedProvider

        api_key = load_env()
        if not api_key:
            raise RuntimeError("FINNHUB_API_KEY not found in config/.env or environment")
        return FinnhubNormalizedProvider(FinnhubNewsCollector(api_key, FinnhubConfig()))
    raise ValueError(f"unknown normalized news source: {source!r}")


def _run_normalized_news_writer(
    source: str,
    scope: List[str],
    *,
    continuation=None,
    progress_cb=None,
) -> Dict[str, Any]:
    """Write Polygon/Finnhub REST news through normalized tables plus legacy projection."""
    import sqlite3

    from src.market_data_admin import resolve_market_db_path
    from src.market_data_direct import market_write_lock
    from src.news_normalized.models import WriterBudget
    from src.news_normalized.store import NormalizedNewsStore
    from src.news_normalized.writer import write_news_batch

    provider = _make_normalized_news_provider(source)
    conn = sqlite3.connect(resolve_market_db_path(), timeout=10.0)
    try:
        with market_write_lock():
            store = NormalizedNewsStore(conn)
            result = write_news_batch(
                store,
                provider,
                scope,
                WriterBudget(
                    max_articles=_NORMALIZED_NEWS_MAX_ARTICLES,
                    max_body_fetches=_NORMALIZED_NEWS_MAX_BODY_FETCHES,
                ),
                project_legacy=True,
                continuation=continuation,
                progress_cb=progress_cb,
            )
        return asdict(result) if hasattr(result, "__dataclass_fields__") else result
    finally:
        conn.close()


def _normalized_news_continuation(continuation: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(continuation, dict):
        return None
    out = {
        "deferred_tickers": list(continuation.get("deferred_tickers") or ()),
        "deferred_body_ids": list(continuation.get("deferred_body_ids") or ()),
        "cursor": continuation.get("cursor"),
    }
    return out if out["deferred_tickers"] or out["deferred_body_ids"] or out["cursor"] else None


def _normalized_writer_continuation(collect: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    continuation = collect.get("continuation") if collect.get("status") == "partial" else None
    return _normalized_news_continuation(continuation)


def _writer_continuation_from_pending(continuation: Optional[Dict[str, Any]]):
    normalized = _normalized_news_continuation(continuation)
    if normalized is None:
        return None
    from src.news_normalized.models import WriterContinuation

    return WriterContinuation(
        deferred_tickers=tuple(normalized["deferred_tickers"]),
        deferred_body_ids=tuple(normalized["deferred_body_ids"]),
        cursor=normalized["cursor"],
    )


def _plan_price_backfill_scope(scope, *, today=None, now_et=None):
    """Gap-aware scope for price_backfill: read local trading-day coverage and plan a bounded
    (tickers, lookback_days) set. GATE 1: coverage is queried with lookback_days =
    _BACKFILL_MAX_DAYS (== the planner's max_days), so every SELECTED gap is reachable by the
    executor's window top-up. GATE 2: coverage['provider_errors'] (LC-style unresolvable tickers)
    feed exclude_tickers, so they never re-enter scheduled work. Read-only (planner is pure).
    ``today``/``now_et`` are passed through to the coverage oracle (default: real now)."""
    from src.market_data_direct import summarize_trading_day_coverage
    from src.scheduler_planner import plan_price_backfill

    cov = summarize_trading_day_coverage(scope, interval="15min",
                                         lookback_days=_BACKFILL_MAX_DAYS,
                                         today=today, now_et=now_et)
    days = cov.get("days") or []
    today_iso = days[0]["date"] if days else None  # newest day in the window = planner reference
    exclude = {e["ticker"]: (e.get("last_error") or "provider error")
               for e in cov.get("provider_errors", [])}
    if today_iso is None:
        from src.scheduler_planner import BackfillPlan
        return BackfillPlan(tickers=[], lookback_days=0)
    return plan_price_backfill(cov, today=today_iso, max_tickers=_BACKFILL_MAX_TICKERS,
                               max_days=_BACKFILL_MAX_DAYS, exclude_tickers=exclude)


def _pending_continuation(source: str):
    """The saved continuation dict from a prior `partial` (deferred scope to resume), or None.
    Best-effort (local state)."""
    try:
        st = _state_store().get(source)
    except Exception:  # noqa: BLE001
        return None
    if not st:
        return None
    status = st.get("last_status")
    cont = st.get("continuation")
    if status == "partial":
        if isinstance(cont, dict):
            if cont.get("deferred"):
                return cont
            normalized = _normalized_news_continuation(cont)
            if normalized is not None:
                return normalized
    source_def = SOURCES.get(source)
    if status == "failed" and source_def is not None and source_def.news_direct_source is not None:
        normalized = _normalized_news_continuation(cont)
        if normalized is not None:
            return normalized
    return None


def _has_pending_continuation(source: str) -> bool:
    """Attended mode (decision 4): a prior `partial` left a saved continuation → the SCHEDULER
    must NOT auto-resume it; only a manual trigger processes it."""
    return _pending_continuation(source) is not None


def source_config(source: str) -> Dict[str, Any]:
    d = SOURCES[source]
    store = _store()
    enabled = (store.get_setting(f"schedule.{source}.enabled") or "").strip().lower() in (
        "1", "true", "yes", "on")
    raw = store.get_setting(f"schedule.{source}.interval_minutes")
    try:
        interval = max(5, min(7 * 24 * 60, int(raw))) if raw else d.default_interval_min
    except ValueError:
        interval = d.default_interval_min
    return {"enabled": enabled, "interval_minutes": interval}


def set_source_config(source: str, *, enabled: Optional[bool] = None,
                      interval_minutes: Optional[int] = None) -> Dict[str, Any]:
    if source not in SOURCES:
        raise KeyError(source)
    store = _store()
    if enabled is not None:
        store.set_setting(f"schedule.{source}.enabled", "true" if enabled else "false")
    if interval_minutes is not None:
        interval_minutes = max(5, min(7 * 24 * 60, int(interval_minutes)))
        store.set_setting(f"schedule.{source}.interval_minutes", str(interval_minutes))
    return source_config(source)


# --- execution ------------------------------------------------------------------

def _run_subprocess(argv: List[str]) -> Dict[str, Any]:
    """Run one child with captured output, repo-root cwd (collectors use
    repo-relative paths), inherited env (config/.env keys via ensure_env_loaded)."""
    proc = subprocess.run(
        argv, cwd=str(_REPO_ROOT), capture_output=True, text=True,
    )
    out = {"returncode": proc.returncode}
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-_ERROR_TAIL:]
        out["error_tail"] = tail
    return out


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_sanitized_worker_stdout(stdout: str) -> Optional[Dict[str, Any]]:
    try:
        raw = json.loads(stdout or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None

    payload: Dict[str, Any] = {"status": str(raw.get("status") or "unknown")}
    for key in _SANITIZED_WORKER_COUNT_KEYS:
        payload[key] = _safe_int(raw.get(key))
    payload["error_count"] = _safe_int(raw.get("error_count"))
    classes = raw.get("error_classes")
    if isinstance(classes, list):
        payload["error_classes"] = [
            str(item)
            for item in classes
            if str(item).replace("_", "").isalnum()
        ]
    else:
        payload["error_classes"] = []
    continuation = raw.get("continuation")
    if isinstance(continuation, dict):
        payload["continuation"] = {
            "deferred_ticker_count": _safe_int(
                continuation.get("deferred_ticker_count")
            ),
            "deferred_body_count": _safe_int(
                continuation.get("deferred_body_count")
            ),
            "has_cursor": bool(continuation.get("has_cursor")),
        }
    return payload


def _run_sanitized_json_subprocess(argv: List[str]) -> Dict[str, Any]:
    """Run a child whose stdout contract is sanitized JSON; never surface stderr."""
    proc = subprocess.run(
        argv, cwd=str(_REPO_ROOT), capture_output=True, text=True,
    )
    payload = _parse_sanitized_worker_stdout(proc.stdout)
    if payload is None:
        payload = {
            "status": "failed",
            "error_count": 1,
            "error_classes": [],
            **{key: 0 for key in _SANITIZED_WORKER_COUNT_KEYS},
        }
        return {"returncode": proc.returncode or 1, "payload": payload}
    return {"returncode": proc.returncode, "payload": payload}


def _sanitized_worker_failure_message(payload: Dict[str, Any]) -> str:
    classes = payload.get("error_classes")
    if isinstance(classes, list) and classes:
        return f"normalized IBKR worker failed ({', '.join(map(str, classes))})"
    return "normalized IBKR worker failed"


def _resolve_price_scope() -> List[str]:
    """Active-universe tickers — delegates to the ONE shared resolver
    (src.universe_scope), same contract as the collectors' --scope flag."""
    from src.universe_scope import resolve_active_universe

    return resolve_active_universe()


def _news_pg_exit_audit_state(db_path: str) -> Optional[bool]:
    """Read the market DB audit marker without creating or mutating it.

    Returns None when the marker cannot be read. News scheduling treats that as
    fail-closed so a transient/corrupt audit read never re-enables PG news.
    """
    path = Path(db_path)
    if not path.exists():
        return False
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                ("news_pg_exit_runs",),
            ).fetchone()
            if not exists:
                return False
            row = conn.execute(
                "SELECT 1 FROM news_pg_exit_runs WHERE status = 'completed' LIMIT 1"
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _news_pg_exit_assume_completed_for_refresh(market_db: str) -> bool:
    from src.news_normalized.routing import NEWS_PG_EXIT_COMPLETED_KEY
    from src.news_providers import parse_news_toggle

    try:
        if parse_news_toggle(_store().get_setting(NEWS_PG_EXIT_COMPLETED_KEY)) is True:
            return True
    except Exception:  # noqa: BLE001 — routing falls back to the DB audit marker
        pass
    audit_state = _news_pg_exit_audit_state(market_db)
    if audit_state is None:
        logger.warning(
            "news PG-exit audit marker could not be read; excluding news from local mirror"
        )
        return True
    return audit_state


def _blocked_news_audit_route():
    from src.news_normalized.routing import NewsWriteMode, NewsWriteRoute

    return NewsWriteRoute(
        NewsWriteMode.BLOCKED,
        "News PG-exit audit marker could not be read; refusing legacy PG news route.",
    )


def _read_profile_news_write_values() -> Optional[dict]:
    from src.news_normalized.routing import (
        NEWS_PG_EXIT_COMPLETED_KEY,
        USE_NORMALIZED_NEWS_WRITES_KEY,
    )
    from src.news_providers import USE_LOCAL_NEWS_KEY

    try:
        store = _store()
        return {
            NEWS_PG_EXIT_COMPLETED_KEY: store.get_setting(NEWS_PG_EXIT_COMPLETED_KEY),
            USE_NORMALIZED_NEWS_WRITES_KEY: store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY),
            USE_LOCAL_NEWS_KEY: store.get_setting(USE_LOCAL_NEWS_KEY),
        }
    except Exception:  # noqa: BLE001 — caller decides whether audit can cover this
        return None


def _read_news_write_route_for_scheduler():
    """Resolve news writer routing with the local market DB audit marker included."""
    from src.market_data_admin import resolve_market_db_path
    from src.news_normalized.routing import (
        ENV_USE_NORMALIZED_NEWS_WRITES,
        NEWS_PG_EXIT_COMPLETED_KEY,
        NewsWriteMode,
        USE_NORMALIZED_NEWS_WRITES_KEY,
        read_news_write_route,
        resolve_news_write_route,
    )
    from src.news_providers import ENV_USE_LOCAL_NEWS, USE_LOCAL_NEWS_KEY

    market_db = resolve_market_db_path()
    audit_state = _news_pg_exit_audit_state(market_db)
    if audit_state is False:
        return read_news_write_route()
    values = _read_profile_news_write_values()
    if values is None and audit_state is None:
        return _blocked_news_audit_route()
    values = values or {}
    exit_completed = values.get(NEWS_PG_EXIT_COMPLETED_KEY)
    normalized = values.get(USE_NORMALIZED_NEWS_WRITES_KEY)
    local = values.get(USE_LOCAL_NEWS_KEY)
    route = resolve_news_write_route(
        exit_completed=True if audit_state is True else exit_completed,
        normalized_value=normalized,
        local_value=local,
        normalized_env=os.environ.get(ENV_USE_NORMALIZED_NEWS_WRITES),
        local_env=os.environ.get(ENV_USE_LOCAL_NEWS),
    )
    if audit_state is None and route.mode not in (NewsWriteMode.NORMALIZED, NewsWriteMode.BLOCKED):
        return _blocked_news_audit_route()
    return route


def _local_refresh() -> Dict[str, Any]:
    """PG → local market_data.db delta. Skip-if-busy (in-process AND cross-process):
    concurrent refreshes are idempotent (INSERT OR IGNORE) but wasteful."""
    if not _LOCAL_REFRESH_LOCK.acquire(blocking=False):
        return {"skipped": "local refresh already running"}
    try:
        if not _LOCAL_REFRESH_FLOCK.acquire():
            return {"skipped": "local refresh already running in another process"}
        try:
            from src.market_data_admin import incremental_update, resolve_market_db_path

            market_db = resolve_market_db_path()
            if not Path(market_db).exists():
                return {"skipped": "no local market DB (bootstrap first)"}
            domains = (
                ("prices", "iv")
                if _news_pg_exit_assume_completed_for_refresh(market_db)
                else None
            )
            res = incremental_update(domains=domains) if domains is not None else incremental_update()
            domain_rows = {}
            skipped_domains = {}
            for key, value in res.items():
                if not isinstance(value, dict):
                    continue
                if value.get("skipped"):
                    domain_rows[key] = None
                    skipped_domains[key] = value["skipped"]
                else:
                    domain_rows[key] = value.get("rows_added")
            out = {"ok": res.get("ok"), "domains": domain_rows}
            if skipped_domains:
                out["skipped_domains"] = skipped_domains
            return out
        finally:
            _LOCAL_REFRESH_FLOCK.release()
    finally:
        _LOCAL_REFRESH_LOCK.release()


def run_source(source: str, trigger_source: str = "scheduler", *,
               tickers: Optional[List[str]] = None,
               skip_sync: bool = False) -> Dict[str, Any]:
    """Execute one source end-to-end (collect → PG sync → local refresh) with
    telemetry. Same-source overlap SKIPS (never queues) — in-process AND
    cross-process (CLI vs sidecar); IBKR sources serialize behind the shared
    Gateway lock (also cross-process). ``skip_sync=True`` = TRUE collect-only for
    DATA stores: Parquet only, no PG sync and no local-mirror refresh (PG was not
    updated, so a refresh would be a pointless delta).

    DELIBERATE exception: job_runs TELEMETRY still runs for collect-only — it is
    metadata (not data), best-effort/swallowed, bounded by connect_timeout, and
    load-bearing: the scheduler seeds last-attempt from these rows, so a manual
    collect-only run SUPPRESSES an immediate scheduled re-fetch of the same
    source. Disabling it for collect-only would re-open the double-provider-fetch
    window it exists to close. Never raises."""
    d = SOURCES.get(source)
    if d is None:
        return {"source": source, "status": "unknown_source"}

    lock = _SOURCE_LOCKS[source]
    if not lock.acquire(blocking=False):
        return _record_result(
            {"source": source, "status": "skipped", "reason": "already running"})
    flock = _SOURCE_FLOCKS[source]
    if not flock.acquire():  # cross-process twin: the CLI may be running this source
        lock.release()
        return _record_result({"source": source, "status": "skipped",
                               "reason": "already running in another process"})

    ibkr_held = False
    ibkr_flock_held = False
    started = datetime.now(timezone.utc)
    with _LAST_ATTEMPT_LOCK:
        _LAST_ATTEMPT[source] = started   # in-mem: interval backoff (incl. for attempted skips)
    # Capture any pending continuation NOW — before record_attempt sets last_status='running'
    # (which would mask the durable 'partial'). Used by attended skip-gates (scheduler) and
    # manual-continue branches (api/cli consume saved deferred work).
    pending_cont = _pending_continuation(source) if (
        d.gap_planned or d.news_direct_source is not None
    ) else None
    news_route = None
    try:
        if d.news_direct_source is not None:
            from src.news_normalized.routing import NewsWriteMode

            news_route = _read_news_write_route_for_scheduler()
        # v1.3 attended (decision 4): a prior `partial` left deferred scope → the SCHEDULER does
        # NOT auto-resume; it skips until a MANUAL trigger (api/cli) processes the continuation.
        # Skip-only gate (before record_attempt → doesn't touch durable state, per v1.2a).
        if d.gap_planned and trigger_source == "scheduler" and pending_cont:
            return _record_result({"source": source, "status": "skipped",
                                   "reason": "partial pending manual continue"})
        normalized_pending_cont = (
            _normalized_news_continuation(pending_cont)
            if d.news_direct_source is not None
            else None
        )
        if (
            d.news_direct_source is not None
            and trigger_source == "scheduler"
            and news_route.mode == NewsWriteMode.NORMALIZED
            and normalized_pending_cont is not None
        ):
            return _record_result({"source": source, "status": "skipped",
                                   "reason": "partial pending manual continue"})
        if d.ibkr:
            ibkr_held = _IBKR_LOCK.acquire(timeout=_IBKR_LOCK_TIMEOUT_S)
            if not ibkr_held:
                return _record_result({"source": source, "status": "skipped",
                                       "reason": "IBKR gateway busy (lock timeout)"})
            # cross-process Gateway serialization (one TWS/Gateway session total)
            ibkr_flock_held = _IBKR_FLOCK.acquire(timeout=_IBKR_LOCK_TIMEOUT_S)
            if not ibkr_flock_held:
                return _record_result(
                    {"source": source, "status": "skipped",
                     "reason": "IBKR gateway busy in another process (lock timeout)"})

        # v1.2 (v1.2a fix): durable run-start recorded ONLY after all skip-only gates pass
        # (per-source + IBKR locks). A lock-busy skip returns above WITHOUT marking durable
        # 'running' — so a skip never overwrites the prior durable outcome (last_status/error).
        try:
            _state_store().record_attempt(source, started)
        except Exception:  # noqa: BLE001 — local state must never break collection
            logger.debug("scheduler_state record_attempt failed for %s", source, exc_info=True)

        # telemetry: running → terminal, visible in /jobs + provider health
        store = None
        run_id = None
        try:
            from src.api.dependencies import get_dal
            from src.service.job_runs_store import JobRunsStore

            store = JobRunsStore(get_dal())
            run_id = store.create_run(job_name(source), trigger_source=trigger_source,
                                      payload={"source": source})
        except Exception as e:  # noqa: BLE001 — telemetry must not block collection
            logger.debug(f"scheduler telemetry unavailable: {e}")

        result: Dict[str, Any] = {"source": source}
        ok = True
        error: Optional[str] = None
        plan = None   # v1.3: the gap-aware BackfillPlan (price_backfill); None for other sources
        writer_continuation = None
        writer_partial = False
        preserve_continuation_on_failure = None
        try:
            collected = False
            local_news_writer = False
            if d.news_direct_source is not None:
                if news_route.mode == NewsWriteMode.BLOCKED:
                    raise RuntimeError(news_route.reason)
                local_news_writer = news_route.mode == NewsWriteMode.NORMALIZED or (
                    news_route.mode == NewsWriteMode.LEGACY_LOCAL
                    and d.news_direct_source != "ibkr"
                )

            if news_route is not None and news_route.mode == NewsWriteMode.NORMALIZED:
                pending_writer_continuation = (
                    pending_cont if trigger_source != "scheduler" else None
                )
                resume_continuation = _writer_continuation_from_pending(
                    pending_writer_continuation
                )
                if resume_continuation is not None:
                    preserve_continuation_on_failure = _normalized_news_continuation(
                        pending_writer_continuation
                    )
                    scope = list(resume_continuation.deferred_tickers)
                else:
                    scope = tickers if tickers is not None else _resolve_price_scope()
                    if not scope:
                        raise RuntimeError("active-universe scope empty/unavailable (profile DB)")
                result["ticker_count"] = len(scope)
                if d.news_direct_source == "ibkr":
                    if resume_continuation is not None:
                        raise RuntimeError(
                            "normalized IBKR continuation cannot be resumed from sanitized "
                            "worker output"
                        )
                    argv = [
                        sys.executable,
                        "-m",
                        "src.news_normalized.ibkr_cli",
                        "--tickers",
                        ",".join(scope),
                        "--gateway-lock-held",
                    ]
                    step = _run_sanitized_json_subprocess(argv)
                    result["collect"] = step["payload"]
                    if step["returncode"] != 0:
                        raise RuntimeError(
                            _sanitized_worker_failure_message(step["payload"])
                        )
                else:
                    result["collect"] = _run_normalized_news_writer(
                        d.news_direct_source,
                        scope,
                        continuation=resume_continuation,
                        progress_cb=lambda done, total, current: _set_progress(
                            source, done, total, current),
                    )
                writer_continuation = _normalized_writer_continuation(result["collect"])
                if writer_continuation is not None:
                    result["collect"]["continuation"] = writer_continuation
                writer_partial = result["collect"].get("status") == "partial"
                collected = True
            elif (
                news_route is not None
                and news_route.mode == NewsWriteMode.LEGACY_LOCAL
                and d.news_direct_source != "ibkr"
            ):
                # LEGACY_LOCAL keeps the direct-local writer (provider→local news+fts,
                # NO Parquet, NO PG sync, NO mirror). Cursored against the local DB (newest stored
                # published_at), not the Parquet timestamp.
                from src.news_direct import backfill_news_direct
                from src.news_providers import make_news_provider
                scope = tickers if tickers is not None else _resolve_price_scope()
                if not scope:
                    raise RuntimeError("active-universe scope empty/unavailable (profile DB)")
                result["ticker_count"] = len(scope)
                result["collect"] = backfill_news_direct(
                    scope, source=d.news_direct_source,
                    provider=make_news_provider(d.news_direct_source),
                    progress_cb=lambda done, total, current: _set_progress(
                        source, done, total, current))
                collected = True
            elif d.adapter is not None:
                # In-process provider adapter (import-safe collector module);
                # resolved lazily so tests can monkeypatch the module function and
                # the sidecar pays the import only when the source actually runs.
                import importlib

                mod = importlib.import_module(d.adapter[0])
                fn = getattr(mod, d.adapter[1])
                kwargs: Dict[str, Any] = {
                    "progress_cb": lambda done, total, current: _set_progress(
                        source, done, total, current),
                }
                if d.gap_planned:
                    # v1.3: planner decides SCOPE from coverage (bounded tickers + window that
                    # reaches the oldest gap), not the full universe. Gates 1+2 in the helper.
                    scope = tickers if tickers is not None else _resolve_price_scope()
                    if not scope:
                        raise RuntimeError("active-universe scope empty/unavailable (profile DB)")
                    # v1.3a: a MANUAL trigger with a pending partial CONSUMES the saved deferred
                    # scope (batch-by-batch), NOT a fresh re-plan — so the saved remainder is
                    # guaranteed to be serviced (the 'manual continue covers the saved remainder'
                    # contract). It carries the unprocessed remainder forward as the next partial;
                    # once the saved backlog is drained, normal coverage planning resumes.
                    pending = pending_cont if trigger_source != "scheduler" else None
                    if pending:
                        from src.scheduler_planner import BackfillPlan
                        deferred = list(pending["deferred"])
                        batch, remainder = (deferred[:_BACKFILL_MAX_TICKERS],
                                            deferred[_BACKFILL_MAX_TICKERS:])
                        plan = BackfillPlan(
                            tickers=batch,
                            lookback_days=int(pending.get("lookback_days") or _BACKFILL_MAX_DAYS),
                            deferred=remainder, candidate_count=len(deferred))
                        result["resumed_continuation"] = True
                    else:
                        plan = _plan_price_backfill_scope(scope)
                    result["plan"] = {"tickers": plan.tickers, "lookback_days": plan.lookback_days,
                                      "candidate_count": plan.candidate_count,
                                      "deferred": plan.deferred, "excluded": plan.excluded}
                    if not plan.tickers:
                        result["collect"] = {"planned": 0, "note": "no fillable gaps"}
                        collected = True   # nothing to do is a success, not a fetch
                    else:
                        kwargs["tickers_arg"] = ",".join(plan.tickers)
                        kwargs["lookback_days"] = plan.lookback_days
                        kwargs["acquire_gateway_lock"] = False  # scheduler holds the Gateway lock
                        result["ticker_count"] = len(plan.tickers)
                        result["collect"] = fn(**kwargs)
                        collected = True
                else:
                    if d.universe_tickers:
                        scope = tickers if tickers is not None else _resolve_price_scope()
                        if not scope:
                            # 3e-E: the collectors' legacy tickers_core default is
                            # retired — no scope means FAIL, not silently-collect-other.
                            raise RuntimeError(
                                "active-universe scope empty/unavailable (profile DB)")
                        kwargs["tickers_arg"] = ",".join(scope)
                        result["ticker_count"] = len(scope)
                    if d.ibkr:
                        # run_source ALREADY holds the shared Gateway lock — tell the IBKR adapter
                        # NOT to re-acquire it (non-reentrant; would self-deadlock).
                        kwargs["acquire_gateway_lock"] = False
                    result["collect"] = fn(**kwargs)  # raises on failure (e.g. missing key)
                    collected = True
            elif d.collector is not None:
                argv = [sys.executable, str(_COLLECT_DIR / d.collector[0]), *d.collector[1:]]
                if d.needs_price_scope:
                    scope = tickers if tickers is not None else _resolve_price_scope()
                    if not scope:
                        raise RuntimeError("no active-universe scope (profile DB empty/unavailable)")
                    argv += ["--tickers", ",".join(scope)]
                    result["ticker_count"] = len(scope)
                step = _run_subprocess(argv)
                result["collect"] = step
                if step["returncode"] != 0:
                    raise RuntimeError(f"collector failed: {step.get('error_tail', '')[:200]}")
                collected = True

            if collected and d.sync_flag and not skip_sync and not local_news_writer:
                with _SYNC_LOCK:
                    # cross-process: a CLI sync may be mid-flight — queue behind it
                    # (in-process semantics are queue-not-skip too), bounded.
                    if not _SYNC_FLOCK.acquire(timeout=_IBKR_LOCK_TIMEOUT_S):
                        raise RuntimeError("PG sync lock busy in another process (timeout)")
                    try:
                        sync = _run_subprocess([sys.executable, str(_MIGRATE), d.sync_flag])
                    finally:
                        _SYNC_FLOCK.release()
                result["sync"] = sync
                if sync["returncode"] != 0:
                    raise RuntimeError(f"PG sync failed: {sync.get('error_tail', '')[:200]}")

            if skip_sync:
                # TRUE collect-only (CLI without --sync-db): PG untouched → a local
                # mirror refresh would pull nothing; do not touch PG or the local DB.
                result["local_refresh"] = {"skipped": "collect-only run (no PG sync)"}
            elif local_news_writer or (d.adapter is not None and d.sync_flag is None):
                # DIRECT local writers already wrote market_data.db themselves — a PG→local mirror
                # would be pointless and could re-pull stale PG news/prices.
                result["local_refresh"] = {"skipped": "direct local writer (no PG mirror)"}
            else:
                result["local_refresh"] = _local_refresh()
        except Exception as e:  # noqa: BLE001
            ok = False
            error = str(e)[:_ERROR_TAIL]
            result["error"] = error
            logger.warning(f"scheduler source {source} failed: {error}")

        # Partial runs persist their continuation so the UI/manual follow-up can surface the
        # unfinished scope instead of clearing it as a success.
        continuation = None
        if ok and writer_partial:
            result["status"] = "partial"
            continuation = writer_continuation
            if continuation is not None:
                result["continuation"] = continuation
        elif ok and plan is not None and plan.deferred:
            result["status"] = "partial"
            continuation = {"deferred": plan.deferred, "lookback_days": plan.lookback_days,
                            "candidate_count": plan.candidate_count}
            result["continuation"] = continuation
        else:
            result["status"] = "succeeded" if ok else "failed"
            if not ok and preserve_continuation_on_failure is not None:
                continuation = preserve_continuation_on_failure
        # v1.2: durable LOCAL outcome (recoverable + visible-failure), best-effort. This is the
        # REAL run outcome (skips return earlier via _record_result and are not persisted here).
        # error=None on success clears any stale last_error; continuation=None clears a prior
        # partial's deferred scope. PG job_runs (below) is unchanged — `partial` lives ONLY in
        # this local store; PG gets succeeded/failed (partial maps to succeeded — it completed
        # its bounded batch without error), never `partial` in job_runs' enum.
        try:
            _state_store().record_outcome(source, status=result["status"], error=error,
                                          result=result, continuation=continuation)
        except Exception:  # noqa: BLE001 — local state must never break collection
            logger.debug("scheduler_state record_outcome failed for %s", source, exc_info=True)
        if store is not None and run_id is not None:
            try:
                store.finish_run(run_id, status="succeeded" if ok else "failed",
                                 message=None if ok else error, error=error, result=result)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"scheduler telemetry finish failed: {e}")
        return _record_result(result)
    finally:
        _clear_progress(source)
        if ibkr_flock_held:
            _IBKR_FLOCK.release()
        if ibkr_held:
            _IBKR_LOCK.release()
        flock.release()
        lock.release()


# --- supervisor loop -------------------------------------------------------------

def _pg_reachable(timeout: float = 3.0) -> bool:
    """Fast TCP probe of the PG host before the seed touches job_runs.

    psycopg2.connect has NO default timeout — an unreachable/filtered PG host can
    hang for the full OS TCP retry window (~2 min), and the seed must never make
    app startup or the scheduler loop depend on PG availability."""
    try:
        from src.tools.db_config import load_database_url

        dsn = load_database_url(_REPO_ROOT / "config" / ".env")
        if not dsn:
            return False
        import socket

        from psycopg2.extensions import parse_dsn

        params = parse_dsn(dsn)
        host = params.get("host") or "localhost"
        port = int(params.get("port") or 5432)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:  # noqa: BLE001 — any failure = treat as unreachable
        return False


def _seed_last_attempts() -> None:
    """Continuity across restarts: seed last-attempt from the LOCAL scheduler_state store first
    (v1.2 — works PG-unreachable), then SUPPLEMENT from PG job_runs for any source without local
    state (transition continuity + manual daily_update runs via the alias map). STRICTLY
    best-effort: losing the seed only means a source may fire one interval early after a restart."""
    # 1. local-primary seed (no PG needed)
    try:
        for source, ts in _state_store().last_attempts().items():
            if source in SOURCES:
                with _LAST_ATTEMPT_LOCK:
                    _LAST_ATTEMPT[source] = ts
    except Exception as e:  # noqa: BLE001 — local seed best-effort
        logger.debug(f"scheduler local seed skipped: {e}")

    # 2. PG supplement (optional, only for sources still missing a local last_attempt)
    if not _pg_reachable():
        logger.info("scheduler PG seed skipped: PG unreachable (local state used; "
                    "any source without local state may fire one interval early)")
        return
    try:
        from src.api.dependencies import get_dal
        from src.service.job_runs_store import JobRunsStore

        latest = JobRunsStore(get_dal()).latest_runs_by_name()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"scheduler PG seed skipped: {e}")
        return
    for source in SOURCES:
        with _LAST_ATTEMPT_LOCK:
            if source in _LAST_ATTEMPT:
                continue  # local state already covers it — PG is only a supplement
        candidates = []
        for name in (job_name(source), _DAILY_UPDATE_ALIAS.get(source)):
            row = latest.get(name) if name else None
            if row:
                ts = row.get("finished_at") or row.get("started_at")
                if isinstance(ts, str):
                    try:
                        candidates.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                    except ValueError:
                        pass
        if candidates:
            with _LAST_ATTEMPT_LOCK:
                _LAST_ATTEMPT[source] = max(candidates)


def _is_due(source: str, now: datetime) -> bool:
    cfg = source_config(source)
    if not cfg["enabled"]:
        return False
    with _LAST_ATTEMPT_LOCK:
        last = _LAST_ATTEMPT.get(source)
    if last is None:
        return True
    return (now - last).total_seconds() >= cfg["interval_minutes"] * 60


def tick_once(now: Optional[datetime] = None, *, fire=None) -> List[str]:
    """One supervisor pass: fire every enabled+due source. Split out of the loop
    for testability; ``fire`` defaults to a thread-offloaded run_source."""
    now = now or datetime.now(timezone.utc)
    fired = []
    for source in SOURCES:
        try:
            if _is_due(source, now):
                fired.append(source)
                if fire is not None:
                    fire(source)
                else:
                    threading.Thread(
                        target=run_source, args=(source, "scheduler"),
                        name=f"sched-{source}", daemon=True,
                    ).start()
        except Exception as e:  # noqa: BLE001 — one source must not kill the tick
            logger.warning(f"scheduler tick error for {source}: {e}")
    return fired


async def scheduler_loop() -> None:
    """The lifespan background task. Cheap when everything is disabled (default):
    one profile_settings read per source per tick."""
    try:
        from src.env_keys import ensure_env_loaded

        ensure_env_loaded()  # collector subprocesses inherit the keys
    except Exception:  # noqa: BLE001
        pass
    # Bounded: the loop must start even if PG hangs past the probe (belt and
    # suspenders — an abandoned seed thread finishes harmlessly in the background).
    try:
        await asyncio.wait_for(asyncio.to_thread(_seed_last_attempts), timeout=15)
    except asyncio.TimeoutError:
        logger.warning("scheduler seed timed out — starting without last-attempt continuity")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"scheduler seed failed ({e}) — starting without continuity")
    logger.info("data scheduler started (all sources opt-in via Settings)")
    while True:
        try:
            await asyncio.to_thread(tick_once)
        except Exception as e:  # noqa: BLE001 — the loop must survive anything
            logger.warning(f"scheduler tick failed: {e}")
        await asyncio.sleep(TICK_SECONDS)


def status_snapshot() -> Dict[str, Any]:
    """Per-source config + runtime state for GET /schedule (pure read)."""
    out = {}
    with _LAST_ATTEMPT_LOCK:
        attempts = dict(_LAST_ATTEMPT)
    with _PROGRESS_LOCK:
        progress = {k: dict(v) for k, v in _PROGRESS.items()}
    with _LAST_RESULT_LOCK:
        last_results = {k: dict(v) for k, v in _LAST_RESULT.items()}
    # v1.4: durable per-source state (last_status / last_error / continuation / last_result)
    # from the local scheduler_state store — survives restarts; the UI shows partial vs skipped.
    # v1.4a: NO-CREATE read — a pure status read must not materialize profile_state.db / its
    # schema (only a real run, via _state_store(), creates it).
    try:
        from src.app_records_store import resolve_profile_state_db_path
        from src.scheduler_state import read_all_if_exists
        durable = read_all_if_exists(resolve_profile_state_db_path(None))
    except Exception:  # noqa: BLE001 — display must never fail on a store hiccup
        durable = {}
    for source, d in SOURCES.items():
        cfg = source_config(source)
        out[source] = {
            "label": d.label,
            "description": d.description,
            "ibkr": d.ibkr,
            "provider_fetch": (d.collector is not None) or (d.adapter is not None),
            "enabled": cfg["enabled"],
            "interval_minutes": cfg["interval_minutes"],
            "default_interval_minutes": d.default_interval_min,
            "running": _SOURCE_LOCKS[source].locked(),
            "progress": progress.get(source),
            "last_attempt_at": attempts.get(source).isoformat() if attempts.get(source) else None,
            # last run_source outcome INCLUDING skips (skips write no job_runs row;
            # without this a cross-process "CLI is running it" skip is invisible)
            "last_result": last_results.get(source),
            "gap_planned": d.gap_planned,   # v1.4: this source uses planner scope + partial/補抓
            # v1.4 durable state (survives restart): {last_status, last_error, continuation,
            # last_result, last_attempt, updated_at}. last_status 'partial' → needs manual 補抓;
            # 'skipped' is transient (not persisted here → absent unless a real run set it).
            "durable_state": durable.get(source),
            "job_name": job_name(source),
        }
    return out
