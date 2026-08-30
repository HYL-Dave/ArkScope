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
  - ibkr_news                         — sanitized src.news_normalized.ibkr_cli
    subprocess, serialized behind ONE shared IBKR lock (one Gateway session;
    client-id hygiene + the ib_insync asyncio loop is safer in its own process)
  - ibkr_prices                       — direct-local adapter into market_data.db
  - sec_corporate_actions             — SEC filing metadata and bounded filing
    evidence → local lifecycle/M&A review observations

Active writers write local stores directly. Provider fetches write normalized
records and project the compatibility read surface where required.

Write-contention guarantees (the user's explicit SQLite concern):
  - provider fetches happen outside market_data.db write locks where possible;
  - active market writes go through direct-local writers;
  - the local SQLite is written by direct-local writers only; financial_cache
    writes are already serialized by _CACHE_WRITE_LOCK;
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from src.service.ticker_identity_scheduler import (
    record_ticker_identity_scheduler_result,
    run_due_ticker_identity_transitions,
    ticker_identity_scheduler_failure,
)
from src.service.security_lifecycle_automation_scheduler import (
    record_security_lifecycle_automation_result,
    run_and_record_security_lifecycle_automation,
    security_lifecycle_automation_failure,
)
from src.service.security_lifecycle_automation_config import (
    SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS,
    SecurityLifecycleAutomationConfigState,
    calculate_security_lifecycle_automation_schedule,
    parse_security_lifecycle_automation_config,
)

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

TICK_SECONDS = 30
_IBKR_LOCK_TIMEOUT_S = 1800  # one slow IBKR job must not deadlock the others forever
_IBKR_NEWS_WORKER_TIMEOUT_S = 3600
_RUNNING_STALE_AFTER = timedelta(hours=2)
_ERROR_TAIL = 600


@dataclass(frozen=True)
class SourceDef:
    name: str
    label: str
    ibkr: bool = False                  # serialize behind the shared IBKR lock
    needs_price_scope: bool = False     # resolve active-universe tickers at run time
    default_interval_min: int = 60
    description: str = ""
    # Pass the ACTIVE UNIVERSE (profile DB, read-only) as the explicit ticker
    # list; the universe is the in-app authority.
    universe_tickers: bool = False
    # In-process provider adapter: (module, function) resolved lazily at run time.
    # The news collectors are import-safe modules now — calling run_incremental()
    # in-process gives structured stats (new_articles) instead of an opaque exit
    # code, with zero logic duplication. IBKR sources deliberately STAY subprocess:
    # process isolation is a feature there (ib_insync asyncio + client-id hygiene).
    adapter: Optional[tuple] = None
    # Direct-local prices worker: run through a sanitized subprocess so ib_insync
    # stays out of scheduler worker threads.
    prices_worker: bool = False
    # Sources that write market_data.db. Scheduler ticks start at most one of these
    # per pass; other due writers are deferred to avoid local SQLite lock storms.
    writes_market_db: bool = False
    # Canonical service job used by macro schedule sources. The scheduler calls
    # the telemetry-free dispatcher directly so it still owns exactly one row.
    backend_job_name: Optional[str] = None
    writes_macro_db: bool = False
    # When set ('polygon'|'finnhub'), resolve the current local news route per run.
    # NORMALIZED and LEGACY_LOCAL write locally; BLOCKED fails before provider work.
    news_direct_source: Optional[str] = None
    # Presentation-only status metadata for Settings/Data Sources. These fields
    # do not affect execution.
    source_mode: str = "provider_fetch"
    write_target: str = "market_data.db"
    source_badges: tuple[str, ...] = ()


SOURCES: Dict[str, SourceDef] = {
    s.name: s
    for s in (
        SourceDef(
            "polygon_news", "Massive 新聞",
            adapter=("src.collectors.polygon_news", "run_incremental"),
            universe_tickers=True, default_interval_min=60, news_direct_source="polygon",
            writes_market_db=True,
            source_badges=("Massive", "直寫本地"),
            description="Massive news incremental → normalized local records + compatibility projection",
        ),
        SourceDef(
            "finnhub_news", "Finnhub 新聞",
            adapter=("src.collectors.finnhub_news", "run_incremental"),
            universe_tickers=True, default_interval_min=60, news_direct_source="finnhub",
            writes_market_db=True,
            source_badges=("Finnhub", "直寫本地"),
            description="Finnhub news incremental → normalized local records + compatibility projection",
        ),
        SourceDef(
            "ibkr_news", "IBKR 新聞",
            ibkr=True,
            needs_price_scope=True, default_interval_min=120,
            news_direct_source="ibkr",
            writes_market_db=True,
            source_badges=("IBKR", "直寫本地"),
            description="IBKR news incremental (Gateway) → normalized local records + compatibility projection",
        ),
        SourceDef(
            "ibkr_prices", "IBKR 股價",
            ibkr=True, universe_tickers=True, default_interval_min=60,
            prices_worker=True, writes_market_db=True,
            source_mode="direct_local",
            write_target="market_data.db",
            source_badges=("IBKR", "直寫本地"),
            description="IBKR/Massive 15min bars for the active universe → market_data.db",
        ),
        SourceDef(
            "sec_corporate_actions", "SEC 公司事件",
            adapter=("src.collectors.sec_corporate_actions", "run_incremental"),
            universe_tickers=True, default_interval_min=1440,
            writes_market_db=True,
            source_mode="direct_local",
            source_badges=("SEC", "官方申報"),
            description=(
                "SEC filings → local delisting/listing-status and M&A review observations; "
                "never removes an active-universe ticker automatically"
            ),
        ),
        SourceDef(
            "fred_series", "FRED 序列",
            default_interval_min=1440,
            backend_job_name="fetch_fred_series",
            writes_macro_db=True,
            source_mode="provider_fetch",
            write_target="macro_calendar.db",
            source_badges=("FRED", "macro_calendar.db"),
            description=(
                "FRED series incremental refresh → local macro_calendar.db"
            ),
        ),
        SourceDef(
            "fred_release_dates", "FRED 發布日期",
            default_interval_min=10080,
            backend_job_name="fetch_fred_release_dates",
            writes_macro_db=True,
            source_mode="provider_fetch",
            write_target="macro_calendar.db",
            source_badges=("FRED", "macro_calendar.db"),
            description=(
                "FRED release dates for configured releases → local "
                "macro_calendar.db"
            ),
        ),
        SourceDef(
            "finnhub_economic_calendar", "Finnhub 經濟日曆",
            default_interval_min=60,
            backend_job_name="fetch_economic_calendar_recent",
            writes_macro_db=True,
            source_mode="provider_fetch",
            write_target="macro_calendar.db",
            source_badges=("Finnhub", "macro_calendar.db"),
            description=(
                "Finnhub economic calendar, 7 days back through 14 days ahead "
                "→ local macro_calendar.db"
            ),
        ),
        SourceDef(
            "finnhub_earnings_calendar", "Finnhub 財報日曆",
            default_interval_min=240,
            backend_job_name="fetch_earnings_calendar",
            writes_macro_db=True,
            source_mode="provider_fetch",
            write_target="macro_calendar.db",
            source_badges=("Finnhub", "macro_calendar.db"),
            description=(
                "Finnhub earnings calendar for the next 30 days → local "
                "macro_calendar.db"
            ),
        ),
        SourceDef(
            "finnhub_ipo_calendar", "Finnhub IPO 日曆",
            default_interval_min=1440,
            backend_job_name="fetch_ipo_calendar",
            writes_macro_db=True,
            source_mode="provider_fetch",
            write_target="macro_calendar.db",
            source_badges=("Finnhub", "macro_calendar.db"),
            description=(
                "Finnhub IPO calendar, 30 days back through 90 days ahead → "
                "local macro_calendar.db"
            ),
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

# --- cross-process lock twins (sidecar ⟷ daily_update CLI) ---------------------
_SOURCE_FLOCKS: Dict[str, _FileLock] = {name: _FileLock(f"source_{name}") for name in SOURCES}

# in-memory last-attempt per source (UTC); seeded from job_runs on scheduler start
_LAST_ATTEMPT: Dict[str, datetime] = {}
_LAST_ATTEMPT_LOCK = threading.Lock()

# last run_source OUTCOME per source — including SKIPS, which write no job_runs
# row. Run-now is fire-and-return: the route answers "started" before the thread
# decides, so without this a cross-process skip ("CLI already running it") would
# be invisible to the UI (no job row, running=false → looks like nothing happened).
_LAST_RESULT: Dict[str, Dict[str, Any]] = {}
_LAST_RESULT_LOCK = threading.Lock()

_SOURCE_PROVIDER_CONFIG = {
    "polygon_news": "massive",
    "finnhub_news": "finnhub",
    "ibkr_news": "ibkr",
    "ibkr_prices": "ibkr",
    "sec_corporate_actions": "sec_edgar",
    "fred_series": "fred",
    "fred_release_dates": "fred",
    "finnhub_economic_calendar": "finnhub",
    "finnhub_earnings_calendar": "finnhub",
    "finnhub_ipo_calendar": "finnhub",
}

_MACRO_SCHEDULE_SOURCES = (
    "fred_series",
    "fred_release_dates",
    "finnhub_economic_calendar",
    "finnhub_earnings_calendar",
    "finnhub_ipo_calendar",
)


def _record_result(result: Dict[str, Any]) -> Dict[str, Any]:
    with _LAST_RESULT_LOCK:
        _LAST_RESULT[result.get("source", "?")] = {
            **result, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return result


def _provider_config_missing_for_source(source: str) -> dict[str, Any] | None:
    provider = _SOURCE_PROVIDER_CONFIG.get(source)
    if not provider:
        return None
    from src.data_provider_config import ProviderConfigMissing, require_provider_configured

    try:
        require_provider_configured(provider)
        return None
    except ProviderConfigMissing as exc:
        return {"source": source, **exc.as_dict()}


def _provider_preflight_failure(source: str) -> dict[str, Any] | None:
    from src.provider_config_runtime import provider_config_setup_state

    setup_state = provider_config_setup_state()
    if setup_state.required:
        return {
            "source": source,
            "status": "failed",
            "error": setup_state.reason or "provider config setup required",
            "code": setup_state.code,
        }
    return _provider_config_missing_for_source(source)

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
    definition = SOURCES.get(source)
    if definition is not None and definition.backend_job_name is not None:
        return definition.backend_job_name
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


def _security_lifecycle_automation_config_state(
) -> SecurityLifecycleAutomationConfigState:
    snapshot = _store().get_settings_snapshot(
        SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS
    )
    return parse_security_lifecycle_automation_config(snapshot)


def _security_lifecycle_profile_mutation_allowed() -> bool:
    try:
        return (
            _security_lifecycle_automation_config_state()
            .effective_apply_profile_transitions
        )
    except Exception:
        return False


def _security_lifecycle_automation_is_due(
    state: SecurityLifecycleAutomationConfigState,
    *,
    now: datetime,
) -> bool:
    if not state.valid or state.config is None or not state.config.enabled:
        return False
    row = _state_store().get("security_lifecycle.automation") or {}
    schedule = calculate_security_lifecycle_automation_schedule(
        last_attempt=row.get("last_attempt"),
        interval_minutes=state.config.interval_minutes,
        now=now,
    )
    return schedule.valid and schedule.due


_NORMALIZED_NEWS_MAX_ARTICLES = 50_000
_NORMALIZED_NEWS_MAX_BODY_FETCHES = 50_000
_SANITIZED_WORKER_COUNT_KEYS = (
    "articles_seen",
    "articles_inserted",
    "bodies_fetched",
    "legacy_rows_inserted",
    "legacy_rows_updated",
    "projection_skipped_no_ticker",
    "retry_bodies_attempted",
    "retry_bodies_fetched",
    "tickers_scanned",
    "headline_pages_requested",
    "headline_saturated_tickers",
    "headline_incomplete_tickers",
)
_SANITIZED_WORKER_LEG_STATUSES = frozenset({"succeeded", "partial", "failed"})
_PROVIDER_WORKER_ERROR_CODES = frozenset({"ibkr_gateway_unavailable"})


def _make_normalized_news_provider(source: str):
    """Build the Parquet-free normalized REST provider for a scheduler news source."""
    if source == "polygon":
        from src.collectors.polygon_news import (
            CollectionConfig,
            PolygonNewsCollector,
            load_env,
        )
        from src.news_normalized.provider_adapters import PolygonNormalizedProvider

        api_key = load_env()
        if not api_key:
            raise RuntimeError(
                "MASSIVE_API_KEY is not configured in Settings or the process environment"
            )
        return PolygonNormalizedProvider(PolygonNewsCollector(api_key, CollectionConfig()))
    if source == "finnhub":
        from src.collectors.finnhub_news import (
            FinnhubConfig,
            FinnhubNewsCollector,
            load_env,
        )
        from src.news_normalized.provider_adapters import FinnhubNormalizedProvider

        api_key = load_env()
        if not api_key:
            raise RuntimeError("FINNHUB_API_KEY is not configured in app/env")
        return FinnhubNormalizedProvider(FinnhubNewsCollector(api_key, FinnhubConfig()))
    raise ValueError(f"unknown normalized news source: {source!r}")


def _run_normalized_news_writer(
    source: str,
    scope: List[str],
    *,
    continuation=None,
    progress_cb=None,
) -> Dict[str, Any]:
    """Write Massive/Finnhub REST news through normalized tables plus legacy projection."""
    import sqlite3

    from src.market_data_admin import resolve_market_db_path
    from src.market_data_direct import market_write_lock
    from src.news_normalized.models import WriterBudget
    from src.news_normalized.store import NormalizedNewsStore
    from src.news_normalized.writer import write_news_batch

    provider = _make_normalized_news_provider(source)
    conn = sqlite3.connect(resolve_market_db_path(), timeout=10.0)
    try:
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
            write_lock_factory=market_write_lock,
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


def read_macro_schedule_automation(
    profile_db: str | Path | None = None,
) -> Optional[Dict[str, bool]]:
    """Read macro schedule enablement without creating the profile database.

    A missing database/table is the default-disabled state. An unreadable
    database is unknown, represented by ``None`` rather than guessed enabled or
    disabled.
    """
    from src.app_records_store import resolve_profile_state_db_path

    path = Path(profile_db or resolve_profile_state_db_path(None))
    defaults = {source: False for source in _MACRO_SCHEDULE_SOURCES}
    try:
        if not path.exists():
            return defaults
        if not path.is_file():
            return None
        uri = f"{path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            conn.execute("PRAGMA query_only = ON")
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                ("profile_settings",),
            ).fetchone()
            if table is None:
                return defaults
            keys = tuple(f"schedule.{source}.enabled" for source in _MACRO_SCHEDULE_SOURCES)
            placeholders = ",".join("?" for _ in keys)
            rows = conn.execute(
                f"SELECT key, value FROM profile_settings WHERE key IN ({placeholders})",
                keys,
            ).fetchall()
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return None

    for key, value in rows:
        source = str(key)[len("schedule."):-len(".enabled")]
        if source in defaults:
            defaults[source] = str(value or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
    return defaults


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


def _safe_nonnegative_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_iso_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 64:
        return None
    parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(parseable)
    except ValueError:
        return None
    return text


def _parse_body_backlog(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    if value.get("status") == "unavailable":
        return {"status": "unavailable"}
    if value.get("status") != "ok":
        return None
    counts = {
        key: _safe_nonnegative_int(value.get(key))
        for key in ("due_now", "scheduled_later", "never_attempted")
    }
    if any(item is None for item in counts.values()):
        return {"status": "unavailable"}
    provider_not_entitled = None
    if "provider_not_entitled" in value:
        provider_not_entitled = _safe_nonnegative_int(
            value.get("provider_not_entitled")
        )
        if provider_not_entitled is None:
            return {"status": "unavailable"}
    earliest = _safe_iso_timestamp(value.get("earliest_next_retry_at"))
    if value.get("earliest_next_retry_at") is not None and earliest is None:
        return {"status": "unavailable"}
    result = {
        "status": "ok",
        **counts,
        "earliest_next_retry_at": earliest,
    }
    if provider_not_entitled is not None:
        result["provider_not_entitled"] = provider_not_entitled
    return result


def _parse_worker_legs(value: Any) -> Optional[Dict[str, str]]:
    if not isinstance(value, dict):
        return None
    retry = value.get("retry")
    fresh = value.get("fresh")
    if (
        retry not in _SANITIZED_WORKER_LEG_STATUSES
        or fresh not in _SANITIZED_WORKER_LEG_STATUSES
    ):
        return None
    return {"retry": retry, "fresh": fresh}


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
    error = str(raw.get("error") or "").strip()
    payload["error"] = error[:_ERROR_TAIL] if error else ""
    payload["retryable"] = raw.get("retryable") is True
    error_code = raw.get("error_code")
    if error_code is not None:
        if error_code not in _PROVIDER_WORKER_ERROR_CODES:
            return None
        payload["error_code"] = error_code
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
    legs = _parse_worker_legs(raw.get("legs"))
    if legs is not None:
        payload["legs"] = legs
    body_backlog = _parse_body_backlog(raw.get("body_backlog"))
    if body_backlog is not None:
        payload["body_backlog"] = body_backlog
    return payload


def _run_sanitized_json_subprocess(argv: List[str]) -> Dict[str, Any]:
    """Run a child whose stdout contract is sanitized JSON; never surface stderr."""
    try:
        proc = subprocess.run(
            argv,
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=_IBKR_NEWS_WORKER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        payload = {
            "status": "failed",
            "error_count": 1,
            "error_classes": ["TimeoutExpired"],
            **{key: 0 for key in _SANITIZED_WORKER_COUNT_KEYS},
        }
        return {"returncode": 1, "payload": payload}
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
    error_code = payload.get("error_code")
    if error_code in _PROVIDER_WORKER_ERROR_CODES:
        return str(error_code)
    classes = payload.get("error_classes")
    if isinstance(classes, list) and classes:
        return f"normalized IBKR worker failed ({', '.join(map(str, classes))})"
    return "normalized IBKR worker failed"


_PRICES_WORKER_STATUSES = frozenset({"succeeded", "partial", "failed"})
_PRICES_WORKER_COUNT_KEYS = (
    "tickers_scanned",
    "succeeded_ticker_count",
    "gaps_found",
    "rows_added",
    "error_count",
    "unresolved_after_fetch_count",
)


def _parse_price_ticker_ids(value: Any) -> Optional[List[str]]:
    if (
        not isinstance(value, list)
        or len(value) > 25
        or any(not isinstance(item, str) for item in value)
    ):
        return None
    normalized = sorted({item.strip().upper() for item in value})
    if any(
        not item
        or len(item) > 12
        or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-" for ch in item)
        for item in normalized
    ):
        return None
    return normalized


def _parse_sanitized_prices_worker_stdout(stdout: str) -> Optional[Dict[str, Any]]:
    """Allowlist parse for src.prices_runtime stdout (the news-worker parser strips
    the prices fields, which killed retryable-skip classification and telemetry)."""
    try:
        raw = json.loads(stdout or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    status = raw.get("status")
    if status not in _PRICES_WORKER_STATUSES:
        return None

    has_structured_counts = any(key in raw for key in _PRICES_WORKER_COUNT_KEYS)
    error_class = str(raw.get("error_class") or "")
    safe_error_class = (
        error_class if error_class.replace("_", "").isalnum() else ""
    )
    if status == "failed" and not has_structured_counts:
        error_code = raw.get("error_code")
        if (
            error_code is not None
            and error_code not in _PROVIDER_WORKER_ERROR_CODES
        ):
            return None
        payload = {
            "status": "failed",
            "provider": None,
            **{key: 0 for key in _PRICES_WORKER_COUNT_KEYS},
            "error_tickers": [],
            "unresolved_after_fetch_tickers": [],
            "error_class": safe_error_class,
            "error": str(raw.get("error") or "")[:_ERROR_TAIL],
            "retryable": raw.get("retryable") is True,
        }
        if error_code is not None:
            payload["error_code"] = error_code
        return payload

    provider = raw.get("provider")
    if provider not in {"ibkr", "polygon"}:
        return None
    counts: Dict[str, int] = {}
    for key in _PRICES_WORKER_COUNT_KEYS:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        counts[key] = value
    error_tickers = _parse_price_ticker_ids(raw.get("error_tickers"))
    unresolved_tickers = _parse_price_ticker_ids(
        raw.get("unresolved_after_fetch_tickers")
    )
    if error_tickers is None or unresolved_tickers is None:
        return None
    if len(error_tickers) != min(counts["error_count"], 25):
        return None
    if len(unresolved_tickers) != min(
        counts["unresolved_after_fetch_count"], 25
    ):
        return None
    if counts["succeeded_ticker_count"] != (
        counts["tickers_scanned"] - counts["error_count"]
    ):
        return None
    if counts["unresolved_after_fetch_count"] > counts["error_count"]:
        return None
    if (
        counts["error_count"] <= 25
        and not set(unresolved_tickers).issubset(error_tickers)
    ):
        return None
    scanned = counts["tickers_scanned"]
    error_count = counts["error_count"]
    expected = (
        "succeeded" if error_count == 0
        else "failed" if scanned > 0 and error_count == scanned
        else "partial"
    )
    if scanned <= 0 or status != expected:
        return None
    return {
        "status": status,
        "provider": provider,
        **counts,
        "error_tickers": error_tickers,
        "unresolved_after_fetch_tickers": unresolved_tickers,
        "error_class": "",
        "error": "",
        "retryable": False,
    }


def _run_sanitized_prices_worker_subprocess(argv: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(argv, cwd=str(_REPO_ROOT), capture_output=True, text=True)
    payload = _parse_sanitized_prices_worker_stdout(proc.stdout)
    if payload is None:
        payload = {
            "status": "failed",
            "error": "prices worker produced no parsable output",
            "error_class": "",
            "retryable": False,
            "provider": None,
            "error_tickers": [],
            "unresolved_after_fetch_tickers": [],
            **{key: 0 for key in _PRICES_WORKER_COUNT_KEYS},
        }
        return {"returncode": proc.returncode or 1, "payload": payload}
    return {"returncode": proc.returncode, "payload": payload}


def _sanitized_prices_worker_failure_message(payload: Dict[str, Any]) -> str:
    error_code = payload.get("error_code")
    if error_code in _PROVIDER_WORKER_ERROR_CODES:
        return str(error_code)
    error = str(payload.get("error") or "").strip()
    if error:
        return error[:_ERROR_TAIL]
    klass = str(payload.get("error_class") or "").strip()
    if klass:
        return f"prices worker failed ({klass})"
    return "prices worker failed"


def _market_write_lock_busy_reason(error: Any) -> Optional[str]:
    text = str(error or "").strip()
    if "market_data.db write lock busy" not in text:
        return None
    return text[:_ERROR_TAIL] or "market_data.db write lock busy (timeout)"


def _prices_worker_retryable_skip_reason(payload: Dict[str, Any]) -> Optional[str]:
    if payload.get("retryable") is not True:
        return None
    return _market_write_lock_busy_reason(payload.get("error"))


def _normalized_worker_retryable_skip_reason(payload: Dict[str, Any]) -> Optional[str]:
    if payload.get("retryable") is not True:
        return None
    return _market_write_lock_busy_reason(payload.get("error"))


def _resolve_price_scope() -> List[str]:
    """Active-universe tickers — delegates to the ONE shared resolver
    (src.universe_scope), same contract as the collectors' --scope flag.

    ``ActiveUniverseUnavailable`` deliberately propagates to ``run_source``'s
    existing failure boundary; an unavailable snapshot must never become ``[]``.
    """
    from src.universe_scope import resolve_active_universe

    return resolve_active_universe()


def _read_news_write_route_for_scheduler(source: str):
    """Resolve the current local writer policy for one scheduler source."""
    from src.news_normalized.routing import read_news_write_route

    return read_news_write_route(normalized_required=source == "ibkr_news")


NewsExecutionMode = Literal["direct_local", "reject"]


class UnsupportedNewsWriteMode(RuntimeError):
    pass


def _classify_news_write_mode(mode: object) -> NewsExecutionMode:
    from src.news_normalized.routing import NewsWriteMode

    if mode is NewsWriteMode.NORMALIZED:
        return "direct_local"
    if mode is NewsWriteMode.LEGACY_LOCAL:
        return "direct_local"
    if mode is NewsWriteMode.BLOCKED:
        return "reject"
    raise UnsupportedNewsWriteMode("unsupported_news_write_mode")


def run_source(source: str, trigger_source: str = "scheduler", *,
               tickers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Execute one direct-local source with durable state and telemetry.

    Same-source overlap skips rather than queues across both threads and
    processes. IBKR sources additionally serialize behind the shared Gateway
    lock. Never raises.
    """
    d = SOURCES.get(source)
    if d is None:
        return {"source": source, "status": "unknown_source"}

    news_route = None
    news_execution_mode: Optional[NewsExecutionMode] = None
    if d.news_direct_source is not None:
        from src.news_normalized.routing import NewsWriteMode

        news_route = _read_news_write_route_for_scheduler(source)
        try:
            news_execution_mode = _classify_news_write_mode(news_route.mode)
        except UnsupportedNewsWriteMode:
            return {
                "source": source,
                "status": "failed",
                "code": "unsupported_news_write_mode",
                "reason_code": "unsupported_news_write_mode",
            }

    if not d.writes_macro_db:
        preflight_failure = _provider_preflight_failure(source)
        if preflight_failure is not None:
            return _record_result(preflight_failure)

    lock = _SOURCE_LOCKS[source]
    if not lock.acquire(blocking=False):
        return _record_result(
            {"source": source, "status": "skipped", "reason": "already running"})
    flock = _SOURCE_FLOCKS[source]
    if not flock.acquire():  # cross-process twin: the CLI may be running this source
        lock.release()
        return _record_result({"source": source, "status": "skipped",
                               "reason": "already running in another process"})

    macro_writer_context = None
    macro_writer_lease = None
    if d.writes_macro_db:
        from src.macro_calendar.write_lock import (
            MacroCalendarBusy,
            macro_calendar_writer,
        )

        macro_writer_context = macro_calendar_writer()
        try:
            macro_writer_lease = macro_writer_context.__enter__()
        except MacroCalendarBusy:
            flock.release()
            lock.release()
            if trigger_source in {"api", "cli", "manual"}:
                result = {
                    "source": source,
                    "status": "skipped",
                    "code": "macro_calendar_busy",
                    "reason": "macro_calendar_busy",
                }
                try:
                    from src.api.dependencies import get_dal
                    from src.service.job_runs_store import get_job_runs_store

                    store = get_job_runs_store(get_dal())
                    run_id = store.create_run(
                        job_name(source),
                        trigger_source=trigger_source,
                        payload={"source": source},
                    )
                    store.finish_run(
                        run_id,
                        status="failed",
                        message="macro_calendar_busy",
                        error="macro_calendar_busy",
                        result=result,
                    )
                except Exception:  # noqa: BLE001 — visibility remains best-effort
                    logger.debug(
                        "attended macro busy telemetry unavailable for %s",
                        source,
                        exc_info=True,
                    )
                return _record_result(result)
            return {
                "source": source,
                "status": "deferred",
                "reason": "macro_calendar_busy",
            }

    ibkr_held = False
    ibkr_flock_held = False
    started = datetime.now(timezone.utc)
    with _LAST_ATTEMPT_LOCK:
        _LAST_ATTEMPT[source] = started   # in-mem: interval backoff (incl. for attempted skips)
    # Capture any pending continuation NOW — before record_attempt sets last_status='running'
    # (which would mask the durable 'partial'). Used by attended skip-gates (scheduler) and
    # manual-continue branches (api/cli consume saved deferred work).
    pending_cont = (
        _pending_continuation(source)
        if d.news_direct_source is not None
        else None
    )
    try:
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
        runtime_dal = None
        try:
            from src.api.dependencies import get_dal
            from src.service.job_runs_store import get_job_runs_store

            runtime_dal = get_dal()
            store = get_job_runs_store(runtime_dal)
            run_id = store.create_run(job_name(source), trigger_source=trigger_source,
                                      payload={"source": source})
        except Exception as e:  # noqa: BLE001 — telemetry must not block collection
            logger.debug(f"scheduler telemetry unavailable: {e}")

        result: Dict[str, Any] = {"source": source}
        ok = True
        error: Optional[str] = None
        writer_continuation = None
        writer_partial = False
        price_partial = False
        adapter_partial = False
        price_audit_error: Optional[str] = None
        preserve_continuation_on_failure = None
        try:
            macro_preflight_failure = (
                _provider_preflight_failure(source) if d.writes_macro_db else None
            )
            if macro_preflight_failure is not None:
                result.update(macro_preflight_failure)
                result["status"] = "failed"
                error = str(
                    macro_preflight_failure.get("error")
                    or macro_preflight_failure.get("code")
                    or "provider preflight failed"
                )[:_ERROR_TAIL]
                result["error"] = error
                ok = False
            elif d.news_direct_source is not None:
                if news_execution_mode == "reject" and news_route.mode == NewsWriteMode.BLOCKED:
                    raise RuntimeError(news_route.reason)
                if (
                    d.news_direct_source == "ibkr"
                    and news_route.mode is not NewsWriteMode.NORMALIZED
                ):
                    raise RuntimeError(
                        "IBKR news requires the normalized writer policy"
                    )

            if d.writes_macro_db and macro_preflight_failure is None:
                from src.api.dependencies import get_dal
                from src.macro_calendar.execution import execute_macro_job

                if d.backend_job_name is None or macro_writer_lease is None:
                    raise RuntimeError("macro source missing canonical execution authority")
                if runtime_dal is None:
                    runtime_dal = get_dal()
                result["collect"] = execute_macro_job(
                    d.backend_job_name,
                    runtime_dal,
                    (
                        {"full_refresh": False}
                        if d.backend_job_name == "fetch_fred_series"
                        else {}
                    ),
                    writer_lease=macro_writer_lease,
                )
            elif news_route is not None and news_route.mode == NewsWriteMode.NORMALIZED:
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
                        reason = _normalized_worker_retryable_skip_reason(step["payload"])
                        if reason is not None:
                            result.update({
                                "status": "skipped",
                                "reason": reason,
                                "skip_kind": "skipped_lock_busy",
                            })
                        else:
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
            elif (
                news_route is not None
                and news_route.mode == NewsWriteMode.LEGACY_LOCAL
                and d.news_direct_source != "ibkr"
            ):
                # LEGACY_LOCAL keeps the direct-local writer (provider→local news+fts,
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
            elif d.prices_worker:
                scope = tickers if tickers is not None else _resolve_price_scope()
                if not scope:
                    raise RuntimeError("active-universe scope empty/unavailable (profile DB)")
                result["ticker_count"] = len(scope)
                argv = [
                    sys.executable,
                    "-m",
                    "src.prices_runtime",
                    "--tickers",
                    ",".join(scope),
                    "--provider",
                    "ibkr",
                    "--gateway-lock-held",
                ]
                step = _run_sanitized_prices_worker_subprocess(argv)
                result["collect"] = step["payload"]
                price_status = step["payload"]["status"]
                if price_status == "partial" and step["returncode"] == 0:
                    price_partial = True
                    price_audit_error = "price_collection_partial"
                elif price_status == "failed":
                    reason = _prices_worker_retryable_skip_reason(step["payload"])
                    if reason is not None:
                        result.update({
                            "status": "skipped",
                            "reason": reason,
                            "skip_kind": "skipped_lock_busy",
                        })
                    else:
                        error_code = step["payload"].get("error_code")
                        raise RuntimeError(
                            str(error_code)
                            if error_code in _PROVIDER_WORKER_ERROR_CODES
                            else "price_collection_failed"
                        )
                elif price_status != "succeeded" or step["returncode"] != 0:
                    raise RuntimeError(
                        _sanitized_prices_worker_failure_message(step["payload"])
                    )
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
                if d.universe_tickers:
                    scope = tickers if tickers is not None else _resolve_price_scope()
                    if not scope:
                        # No implicit collector universe remains: an empty
                        # scope must fail rather than collect something else.
                        raise RuntimeError(
                            "active-universe scope empty/unavailable (profile DB)")
                    kwargs["tickers_arg"] = ",".join(scope)
                    result["ticker_count"] = len(scope)
                if d.ibkr:
                    # run_source ALREADY holds the shared Gateway lock — tell the IBKR adapter
                    # NOT to re-acquire it (non-reentrant; would self-deadlock).
                    kwargs["acquire_gateway_lock"] = False
                result["collect"] = fn(**kwargs)  # raises on failure (e.g. missing key)
                adapter_partial = (
                    isinstance(result["collect"], dict)
                    and result["collect"].get("status") == "partial"
                )
        except Exception as e:  # noqa: BLE001
            lock_busy_reason = (
                _market_write_lock_busy_reason(e)
                if d.news_direct_source is not None
                else None
            )
            if lock_busy_reason is not None:
                result.update({
                    "status": "skipped",
                    "reason": lock_busy_reason,
                    "skip_kind": "skipped_lock_busy",
                })
                ok = True
                error = None
            else:
                ok = False
                error = str(e)[:_ERROR_TAIL]
                result["error"] = error
                logger.warning(f"scheduler source {source} failed: {error}")

        # Partial runs persist their continuation so the UI/manual follow-up can surface the
        # unfinished scope instead of clearing it as a success.
        continuation = None
        if result.get("status") == "skipped":
            continuation = pending_cont if pending_cont is not None else None
        elif ok and (writer_partial or price_partial or adapter_partial):
            result["status"] = "partial"
            continuation = writer_continuation if writer_partial else None
            if continuation is not None:
                result["continuation"] = continuation
        else:
            result["status"] = "succeeded" if ok else "failed"
            if not ok and preserve_continuation_on_failure is not None:
                continuation = preserve_continuation_on_failure
        # Durable local state remains the user-facing recovery source; telemetry is
        # best-effort and cannot block collection.
        try:
            _state_store().record_outcome(
                source,
                status=result["status"],
                error=error,
                result=result,
                continuation=continuation,
            )
        except Exception:  # noqa: BLE001 — local state must never break collection
            logger.debug("scheduler_state record_outcome failed for %s", source, exc_info=True)
        if store is not None and run_id is not None:
            try:
                audit_failed = (not ok) or price_partial
                audit_error = price_audit_error if price_partial else error
                store.finish_run(
                    run_id,
                    status="failed" if audit_failed else "succeeded",
                    message=audit_error if audit_failed else None,
                    error=audit_error if audit_failed else None,
                    result=result,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(f"scheduler telemetry finish failed: {e}")
        return _record_result(result)
    finally:
        _clear_progress(source)
        if ibkr_flock_held:
            _IBKR_FLOCK.release()
        if ibkr_held:
            _IBKR_LOCK.release()
        try:
            if macro_writer_context is not None:
                macro_writer_context.__exit__(None, None, None)
        finally:
            flock.release()
            lock.release()


# --- supervisor loop -------------------------------------------------------------

def _sqlite_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def reconcile_interrupted_runtime_state(
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Repair durable ``running`` rows left by a previous sidecar/worker lifetime.

    Scheduler-state rows are process-owned, so any ``running`` row at boot is
    interrupted. Provider-sync rows can be written by subprocesses, so only rows
    older than the stale threshold are terminalized.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    scheduler_sources: list[str] = []
    provider_run_ids: list[int] = []
    scheduler_error = "sidecar restarted before scheduler source reached a terminal outcome"
    provider_error = "provider worker interrupted before terminal telemetry"
    try:
        scheduler_sources = _state_store().reconcile_interrupted_running(
            error=scheduler_error,
        )
    except Exception:  # noqa: BLE001 — startup repair must not block app boot
        logger.debug("scheduler_state interrupted-running reconciliation failed", exc_info=True)
    try:
        from src.market_data_admin import resolve_market_db_path
        from src.market_data_direct import _reconcile_interrupted_provider_runs

        market_db = Path(resolve_market_db_path())
        if market_db.exists():
            conn = sqlite3.connect(str(market_db), timeout=10.0)
            try:
                if _sqlite_table_exists(conn, "provider_sync_runs"):
                    cutoff = (now - _RUNNING_STALE_AFTER).isoformat(timespec="seconds")
                    provider_run_ids = _reconcile_interrupted_provider_runs(
                        conn,
                        started_before=cutoff,
                        error=provider_error,
                    )
            finally:
                conn.close()
    except Exception:  # noqa: BLE001 — startup repair must not block app boot
        logger.debug("provider_sync interrupted-running reconciliation failed", exc_info=True)
    if scheduler_sources or provider_run_ids:
        logger.warning(
            "reconciled interrupted scheduler/provider runs: scheduler=%s provider_runs=%s",
            scheduler_sources,
            provider_run_ids,
        )
    return {"scheduler_sources": scheduler_sources, "provider_run_ids": provider_run_ids}


def _seed_from_local_job_history(missing_sources: tuple[str, ...]) -> None:
    if not missing_sources:
        return
    from src.app_records_store import resolve_profile_state_db_path
    from src.service.job_runs_store import JobRunsLocalStore

    latest = JobRunsLocalStore(
        resolve_profile_state_db_path(None)
    ).latest_runs_by_name()
    for source in missing_sources:
        candidates = []
        for name in (job_name(source), _DAILY_UPDATE_ALIAS.get(source)):
            row = latest.get(name) if name else None
            if row:
                timestamp = row.get("finished_at") or row.get("started_at")
                if isinstance(timestamp, str):
                    try:
                        candidates.append(
                            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        )
                    except ValueError:
                        pass
        if candidates:
            with _LAST_ATTEMPT_LOCK:
                _LAST_ATTEMPT[source] = max(candidates)


def _seed_last_attempts() -> None:
    """Seed restart continuity from current local stores, in authority order."""
    try:
        for source, ts in _state_store().last_attempts().items():
            if source in SOURCES:
                with _LAST_ATTEMPT_LOCK:
                    _LAST_ATTEMPT[source] = ts
    except Exception as e:  # noqa: BLE001 — local seed best-effort
        logger.debug(f"scheduler local seed skipped: {e}")

    with _LAST_ATTEMPT_LOCK:
        missing_sources = tuple(
            source for source in SOURCES if source not in _LAST_ATTEMPT
        )
    try:
        _seed_from_local_job_history(missing_sources)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"scheduler job-history seed skipped: {e}")


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
    try:
        automation_state = _security_lifecycle_automation_config_state()
        if _security_lifecycle_automation_is_due(automation_state, now=now):
            assert automation_state.config is not None
            run_and_record_security_lifecycle_automation(
                limit=automation_state.config.batch_limit,
                now=now,
                transition_mutation_allowed=(
                    _security_lifecycle_profile_mutation_allowed
                ),
            )
    except Exception as exc:  # lifecycle work must not stop later schedulers
        logger.warning(
            "security lifecycle automation tick failed code=%s",
            type(exc).__name__,
        )
        automation_result = security_lifecycle_automation_failure(
            "automation_scheduler_failed"
        )
        try:
            record_security_lifecycle_automation_result(automation_result, now=now)
        except Exception as record_exc:  # telemetry must not stop later schedulers
            logger.warning(
                "security lifecycle automation result recording failed code=%s",
                type(record_exc).__name__,
            )
    try:
        transition_mutation_allowed = (
            _security_lifecycle_profile_mutation_allowed
        )
        transition_result = run_due_ticker_identity_transitions(
            now=now,
            allow_automation_approved=transition_mutation_allowed(),
            transition_mutation_allowed=transition_mutation_allowed,
        )
    except Exception as exc:  # lifecycle work must not stop provider scheduling
        logger.warning(
            "ticker identity scheduler tick failed code=%s",
            type(exc).__name__,
        )
        transition_result = ticker_identity_scheduler_failure(
            "ticker_identity_scheduler_failed"
        )
    try:
        record_ticker_identity_scheduler_result(transition_result, now=now)
    except Exception as exc:  # telemetry must not stop provider scheduling
        logger.warning(
            "ticker identity scheduler result recording failed code=%s",
            type(exc).__name__,
        )
    market_writer_fired = False
    macro_writer_fired = False
    for source, d in SOURCES.items():
        try:
            if _is_due(source, now):
                if d.writes_market_db and market_writer_fired:
                    _record_result({
                        "source": source,
                        "status": "skipped",
                        "reason": "market_data.db writer already scheduled this tick",
                        "skip_kind": "market_writer_backpressure",
                    })
                    continue
                if d.writes_macro_db and macro_writer_fired:
                    continue
                fired.append(source)
                if d.writes_market_db:
                    market_writer_fired = True
                if d.writes_macro_db:
                    macro_writer_fired = True
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
    # Bounded: a damaged local store must not block scheduler startup.
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
    now = datetime.now(timezone.utc)
    for source, d in SOURCES.items():
        cfg = source_config(source)
        source_running = _SOURCE_LOCKS[source].locked()
        durable_state = durable.get(source)
        if durable_state is not None:
            durable_state = _annotate_durable_state_for_snapshot(
                durable_state,
                source_running=source_running,
                now=now,
            )
        out[source] = {
            "label": d.label,
            "description": d.description,
            "ibkr": d.ibkr,
            "provider_fetch": (
                d.adapter is not None
                or d.news_direct_source is not None
                or d.prices_worker
                or d.writes_macro_db
            ),
            "source_mode": d.source_mode,
            "write_target": d.write_target,
            "source_badges": list(d.source_badges),
            "enabled": cfg["enabled"],
            "interval_minutes": cfg["interval_minutes"],
            "default_interval_minutes": d.default_interval_min,
            "running": source_running,
            "progress": progress.get(source),
            "last_attempt_at": attempts.get(source).isoformat() if attempts.get(source) else None,
            # last run_source outcome INCLUDING skips (skips write no job_runs row;
            # without this a cross-process "CLI is running it" skip is invisible)
            "last_result": last_results.get(source),
            # v1.4 durable state (survives restart): {last_status, last_error, continuation,
            # last_result, last_attempt, updated_at}. last_status 'partial' → needs manual 補抓;
            # 'skipped' is transient (not persisted here → absent unless a real run set it).
            "durable_state": durable_state,
            "job_name": job_name(source),
        }
    return out


def _parse_scheduler_state_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        elif len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":
            text = text[:-2] + ":" + text[-2:]
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _annotate_durable_state_for_snapshot(
    durable_state: Dict[str, Any],
    *,
    source_running: bool,
    now: datetime,
) -> Dict[str, Any]:
    out = dict(durable_state)
    if out.get("last_status") != "running":
        return out
    started = _parse_scheduler_state_time(out.get("last_attempt") or out.get("updated_at"))
    age_seconds = None
    stale = not source_running
    reason = "running without an in-process scheduler lock" if stale else None
    if started is not None:
        age_seconds = max(0, int((now - started).total_seconds()))
        if age_seconds >= int(_RUNNING_STALE_AFTER.total_seconds()):
            stale = True
            reason = "running longer than configured stale threshold"
    out["running_for_seconds"] = age_seconds
    out["running_stale"] = stale
    out["running_stale_reason"] = reason
    return out
