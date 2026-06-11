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
import logging
import os
import subprocess
import sys
import threading
import time
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
            needs_price_scope=True, default_interval_min=120,
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
            needs_price_scope=True, default_interval_min=1440,
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


# --- cross-process lock twins (sidecar ⟷ daily_update CLI) ---------------------

def _lock_dir() -> Path:
    """Lock-file directory (env-overridable so tests never collide with a live
    sidecar's locks)."""
    return Path(os.environ.get("ARKSCOPE_LOCK_DIR") or (_REPO_ROOT / "data" / "locks"))


class _FileLock:
    """flock(2) twin of a threading.Lock: serializes the sidecar against the
    daily_update CLI (separate PROCESSES calling the same run_source — a
    threading.Lock cannot see across them). The kernel releases flock when the
    fd closes OR the process dies, so a crashed run never wedges the lock.

    Each instance is only ever acquired while its threading twin is held, so the
    instance itself needs no thread-safety. Non-POSIX (no fcntl) degrades to
    in-process-only locking with a one-time warning."""

    _warned = False

    def __init__(self, name: str):
        self._name = name
        self._fh = None

    def acquire(self, timeout: float = 0.0, poll: float = 5.0) -> bool:
        """timeout 0 → single non-blocking try; >0 → poll until the deadline."""
        try:
            import fcntl
        except ImportError:  # non-POSIX
            if not _FileLock._warned:
                logger.warning("fcntl unavailable — cross-process locks degraded "
                               "to in-process only")
                _FileLock._warned = True
            return True
        path = _lock_dir() / f"{self._name}.lock"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(path, "a+")
        except OSError as e:
            # A broken lock dir must not brick collection: degrade, don't skip.
            logger.warning(f"file lock {path.name} unavailable ({e}); "
                           "cross-process exclusion degraded for this run")
            return True
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fh = fh
                return True
            except OSError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    fh.close()
                    return False
                time.sleep(min(poll, max(0.1, remaining)))

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:  # noqa: BLE001 — close below still drops the lock
            pass
        try:
            self._fh.close()
        finally:
            self._fh = None


_SOURCE_FLOCKS: Dict[str, _FileLock] = {name: _FileLock(f"source_{name}") for name in SOURCES}
_IBKR_FLOCK = _FileLock("ibkr_gateway")
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
    """Active-universe tickers — delegates to the ONE shared resolver
    (src.universe_scope), same contract as the collectors' --scope flag."""
    from src.universe_scope import resolve_active_universe

    return resolve_active_universe()


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

            if not Path(resolve_market_db_path()).exists():
                return {"skipped": "no local market DB (bootstrap first)"}
            res = incremental_update()
            return {"ok": res.get("ok"), "domains": {
                k: (v or {}).get("rows_added") for k, v in res.items() if isinstance(v, dict)}}
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
        _LAST_ATTEMPT[source] = started
    try:
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
                    scope = tickers if tickers is not None else _resolve_price_scope()
                    if not scope:
                        # 3e-E: the collectors' legacy tickers_core default is
                        # retired — no scope means FAIL, not silently-collect-other.
                        raise RuntimeError(
                            "active-universe scope empty/unavailable (profile DB)")
                    kwargs["tickers_arg"] = ",".join(scope)
                    result["ticker_count"] = len(scope)
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

            if collected and d.sync_flag and not skip_sync:
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
            else:
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
    """Continuity across restarts: seed last-attempt from job_runs (scheduler runs
    AND manual daily_update step runs via the alias map). STRICTLY best-effort:
    bounded by the TCP probe above + the wait_for in scheduler_loop — losing the
    seed only means a source may fire one interval early after a restart."""
    if not _pg_reachable():
        logger.info("scheduler seed skipped: PG unreachable (starting without "
                    "last-attempt continuity)")
        return
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
            "job_name": job_name(source),
        }
    return out
