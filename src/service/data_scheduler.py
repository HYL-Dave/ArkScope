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

After a collector succeeds, its data is synced to PG (migrate_to_supabase
--news/--prices/--iv, serialized behind a global sync lock — concurrent syncs are
idempotent but wasteful), then the local mirror refreshes (incremental_update,
skip-if-busy). So one scheduled source run = collect → PG → local, end to end.

Write-contention guarantees (the user's explicit SQLite concern):
  - collectors write per-source Parquet dirs — disjoint, safe in parallel;
  - PG writes are idempotent upserts, serialized by _SYNC_LOCK anyway;
  - the local SQLite is written ONLY by incremental_update (WAL + busy_timeout,
    INSERT OR IGNORE) — serialized here by a skip-if-busy lock, and
    financial_cache writes are already serialized by _CACHE_WRITE_LOCK;
  - per-source locks make same-source runs skip (never queue), so a slow run
    cannot pile up behind itself.

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
import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
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


SOURCES: Dict[str, SourceDef] = {
    s.name: s
    for s in (
        SourceDef(
            "polygon_news", "Polygon 新聞",
            None, "--news",
            adapter=("scripts.collection.collect_polygon_news", "run_incremental"),
            universe_tickers=True, default_interval_min=60,
            description="Polygon news incremental（進程內）→ PG → local mirror",
        ),
        SourceDef(
            "finnhub_news", "Finnhub 新聞",
            None, "--news",
            adapter=("scripts.collection.collect_finnhub_news", "run_incremental"),
            universe_tickers=True, default_interval_min=60,
            description="Finnhub news incremental（進程內）→ PG → local mirror",
        ),
        SourceDef(
            "ibkr_news", "IBKR 新聞",
            ["collect_ibkr_news.py", "--incremental"], "--news", ibkr=True,
            default_interval_min=120,
            description="IBKR news incremental (Gateway) → PG → local mirror",
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
            default_interval_min=1440,
            description="ATM IV snapshot (heavy; Gateway) → PG → local mirror",
        ),
        SourceDef(
            "local_incremental", "本地鏡像增量",
            None, None, default_interval_min=15,
            description="PG → market_data.db delta only (no provider fetch)",
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
_SOURCE_LOCKS: Dict[str, threading.Lock] = {name: threading.Lock() for name in SOURCES}
_IBKR_LOCK = threading.Lock()    # one Gateway session — IBKR jobs never overlap
_SYNC_LOCK = threading.Lock()    # one migrate_to_supabase at a time
_LOCAL_REFRESH_LOCK = threading.Lock()  # one incremental_update at a time (skip-if-busy)

# in-memory last-attempt per source (UTC); seeded from job_runs on scheduler start
_LAST_ATTEMPT: Dict[str, datetime] = {}
_LAST_ATTEMPT_LOCK = threading.Lock()

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


def _resolve_price_scope() -> List[str]:
    """Active-universe tickers from the local profile DB — physically read-only
    (same contract as daily_update's --scope active-universe)."""
    import sqlite3

    db_path = os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        _REPO_ROOT / "data" / "profile_state.db")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT DISTINCT ticker FROM watchlist_memberships ORDER BY ticker"
            ).fetchall()
        finally:
            conn.close()
        return [r[0] for r in rows]
    except sqlite3.OperationalError as e:
        logger.warning(f"scheduler: active-universe scope unavailable ({e})")
        return []


def _local_refresh() -> Dict[str, Any]:
    """PG → local market_data.db delta. Skip-if-busy: concurrent refreshes are
    idempotent (INSERT OR IGNORE) but wasteful."""
    if not _LOCAL_REFRESH_LOCK.acquire(blocking=False):
        return {"skipped": "local refresh already running"}
    try:
        from src.market_data_admin import incremental_update, resolve_market_db_path

        if not Path(resolve_market_db_path()).exists():
            return {"skipped": "no local market DB (bootstrap first)"}
        res = incremental_update()
        return {"ok": res.get("ok"), "domains": {
            k: (v or {}).get("rows_added") for k, v in res.items() if isinstance(v, dict)}}
    finally:
        _LOCAL_REFRESH_LOCK.release()


def run_source(source: str, trigger_source: str = "scheduler") -> Dict[str, Any]:
    """Execute one source end-to-end (collect → PG sync → local refresh) with
    telemetry. Same-source overlap SKIPS (never queues); IBKR sources serialize
    behind the shared Gateway lock. Never raises."""
    d = SOURCES.get(source)
    if d is None:
        return {"source": source, "status": "unknown_source"}

    lock = _SOURCE_LOCKS[source]
    if not lock.acquire(blocking=False):
        return {"source": source, "status": "skipped", "reason": "already running"}

    ibkr_held = False
    started = datetime.now(timezone.utc)
    with _LAST_ATTEMPT_LOCK:
        _LAST_ATTEMPT[source] = started
    try:
        if d.ibkr:
            ibkr_held = _IBKR_LOCK.acquire(timeout=_IBKR_LOCK_TIMEOUT_S)
            if not ibkr_held:
                return {"source": source, "status": "skipped",
                        "reason": "IBKR gateway busy (lock timeout)"}

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
        try:
            collected = False
            if d.adapter is not None:
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
                    tickers = _resolve_price_scope()
                    if tickers:
                        kwargs["tickers_arg"] = ",".join(tickers)
                        result["ticker_count"] = len(tickers)
                    else:
                        logger.warning(
                            f"{source}: active universe unavailable — falling back "
                            "to the collector's default list")
                result["collect"] = fn(**kwargs)  # raises on failure (e.g. missing key)
                collected = True
            elif d.collector is not None:
                argv = [sys.executable, str(_COLLECT_DIR / d.collector[0]), *d.collector[1:]]
                if d.needs_price_scope:
                    tickers = _resolve_price_scope()
                    if not tickers:
                        raise RuntimeError("no active-universe scope (profile DB empty/unavailable)")
                    argv += ["--tickers", ",".join(tickers)]
                    result["ticker_count"] = len(tickers)
                step = _run_subprocess(argv)
                result["collect"] = step
                if step["returncode"] != 0:
                    raise RuntimeError(f"collector failed: {step.get('error_tail', '')[:200]}")
                collected = True

            if collected and d.sync_flag:
                with _SYNC_LOCK:
                    sync = _run_subprocess([sys.executable, str(_MIGRATE), d.sync_flag])
                result["sync"] = sync
                if sync["returncode"] != 0:
                    raise RuntimeError(f"PG sync failed: {sync.get('error_tail', '')[:200]}")

            result["local_refresh"] = _local_refresh()
        except Exception as e:  # noqa: BLE001
            ok = False
            error = str(e)[:_ERROR_TAIL]
            result["error"] = error
            logger.warning(f"scheduler source {source} failed: {error}")

        result["status"] = "succeeded" if ok else "failed"
        if store is not None and run_id is not None:
            try:
                store.finish_run(run_id, status="succeeded" if ok else "failed",
                                 message=None if ok else error, error=error, result=result)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"scheduler telemetry finish failed: {e}")
        return result
    finally:
        _clear_progress(source)
        if ibkr_held:
            _IBKR_LOCK.release()
        lock.release()


# --- supervisor loop -------------------------------------------------------------

def _seed_last_attempts() -> None:
    """Continuity across restarts: seed last-attempt from job_runs (scheduler runs
    AND manual daily_update step runs via the alias map)."""
    try:
        from src.api.dependencies import get_dal
        from src.service.job_runs_store import JobRunsStore

        latest = JobRunsStore(get_dal()).latest_runs_by_name()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"scheduler seed skipped: {e}")
        return
    for source in SOURCES:
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
    await asyncio.to_thread(_seed_last_attempts)
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
            "job_name": job_name(source),
        }
    return out
