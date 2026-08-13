"""Shared macro execution, telemetry, and writer-lock contracts."""

from __future__ import annotations

import builtins
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


MACRO_JOBS = (
    "fetch_fred_series",
    "fetch_fred_release_dates",
    "fetch_economic_calendar_recent",
    "fetch_economic_calendar_backfill",
    "fetch_earnings_calendar",
    "fetch_ipo_calendar",
)


class _Telemetry:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.finished: list[tuple[int, dict[str, Any]]] = []

    def create_run(self, name: str, **kwargs: Any) -> int:
        self.created.append((name, kwargs))
        return len(self.created)

    def finish_run(self, run_id: int, **kwargs: Any) -> bool:
        self.finished.append((run_id, kwargs))
        return True


class _SchedulerState:
    def __init__(self) -> None:
        self.attempts: list[tuple[str, Any]] = []
        self.outcomes: list[tuple[str, dict[str, Any]]] = []

    def record_attempt(self, source: str, started: Any) -> None:
        self.attempts.append((source, started))

    def record_outcome(self, source: str, **kwargs: Any) -> None:
        self.outcomes.append((source, kwargs))


def _enabled_macro_config() -> SimpleNamespace:
    return SimpleNamespace(macro_calendar_enabled=True)


def _install_macro_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import src.service.data_scheduler as scheduler

    source = "fred_series"
    definition = scheduler.SourceDef(
        name=source,
        label="FRED series",
        default_interval_min=1440,
        backend_job_name="fetch_fred_series",
        writes_macro_db=True,
        source_mode="provider_fetch",
        write_target="macro_calendar.db",
    )
    monkeypatch.setitem(scheduler.SOURCES, source, definition)
    monkeypatch.setitem(scheduler._SOURCE_LOCKS, source, __import__("threading").Lock())
    monkeypatch.setitem(scheduler._SOURCE_FLOCKS, source, scheduler._FileLock(f"source_{source}"))
    monkeypatch.setattr(scheduler, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(scheduler, "_LAST_RESULT", {})
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(
        "src.provider_config_runtime.provider_config_setup_state",
        lambda: SimpleNamespace(required=False, reason=None, code=None),
    )
    monkeypatch.setattr(
        scheduler,
        "_provider_config_missing_for_source",
        lambda source: None,
    )
    state = _SchedulerState()
    monkeypatch.setattr(scheduler, "_state_store", lambda: state)
    return scheduler, source, state


def test_all_six_macro_jobs_share_one_writer_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    from src.macro_calendar.execution import execute_macro_job
    from src.macro_calendar.write_lock import MacroCalendarBusy, macro_calendar_writer

    with macro_calendar_writer():
        for job_name in MACRO_JOBS:
            with pytest.raises(MacroCalendarBusy, match="macro_calendar_busy"):
                execute_macro_job(job_name, object(), {})


def test_direct_job_failure_records_one_failed_canonical_row(monkeypatch):
    import src.macro_calendar.execution as execution
    import src.service.jobs as jobs

    telemetry = _Telemetry()
    monkeypatch.setattr(jobs, "get_job_runs_store", lambda dal: telemetry)
    monkeypatch.setattr(
        execution,
        "execute_macro_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider failed")),
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        jobs.run_job(
            "fetch_fred_series",
            dal=object(),
            config=_enabled_macro_config(),
        )

    assert [name for name, _ in telemetry.created] == ["fetch_fred_series"]
    assert len(telemetry.finished) == 1
    assert telemetry.finished[0][1]["status"] == "failed"
    assert telemetry.finished[0][1]["error"] == "provider failed"


def test_direct_job_uses_shared_execution_and_records_one_canonical_row(monkeypatch):
    import src.macro_calendar.execution as execution
    import src.service.jobs as jobs

    telemetry = _Telemetry()
    calls: list[tuple[str, Any, dict[str, Any], Any]] = []

    def _execute(job_name, dal, params, *, writer_lease=None):
        calls.append((job_name, dal, params, writer_lease))
        return {"series_processed": 2, "observations_upserted": 4}

    monkeypatch.setattr(jobs, "get_job_runs_store", lambda dal: telemetry)
    monkeypatch.setattr(execution, "execute_macro_job", _execute)
    dal = object()
    result = jobs.run_job(
        "fetch_fred_series",
        dal=dal,
        params={"full_refresh": False},
        config=_enabled_macro_config(),
    )

    assert calls == [("fetch_fred_series", dal, {"full_refresh": False}, None)]
    assert result.status == "succeeded"
    assert [name for name, _ in telemetry.created] == ["fetch_fred_series"]
    assert len(telemetry.finished) == 1
    assert telemetry.finished[0][1]["status"] == "succeeded"


def test_macro_lock_busy_records_one_non_success_row_without_provider_work(
    tmp_path, monkeypatch
):
    import src.service.jobs as jobs
    from src.macro_calendar.write_lock import MacroCalendarBusy, macro_calendar_writer

    telemetry = _Telemetry()
    provider_calls: list[str] = []
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(jobs, "get_job_runs_store", lambda dal: telemetry)
    monkeypatch.setattr(
        "src.macro_calendar.fred_ingestion.fetch_fred_series",
        lambda *args, **kwargs: provider_calls.append("called"),
    )

    with macro_calendar_writer():
        with pytest.raises(MacroCalendarBusy, match="macro_calendar_busy"):
            jobs.run_job(
                "fetch_fred_series",
                dal=object(),
                config=_enabled_macro_config(),
            )

    assert provider_calls == []
    assert [name for name, _ in telemetry.created] == ["fetch_fred_series"]
    assert len(telemetry.finished) == 1
    assert telemetry.finished[0][1]["status"] == "failed"
    assert telemetry.finished[0][1]["error"] == "macro_calendar_busy"


def test_macro_writer_lock_releases_descriptors_after_success_and_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    from src.macro_calendar.write_lock import MacroCalendarBusy, macro_calendar_writer

    fd_root = Path("/proc/self/fd")
    if not fd_root.is_dir():
        pytest.skip("/proc/self/fd is required for the descriptor contract")

    baseline = len(list(fd_root.iterdir()))
    with macro_calendar_writer():
        pass
    assert len(list(fd_root.iterdir())) == baseline

    with pytest.raises(RuntimeError, match="inside critical section"):
        with macro_calendar_writer():
            raise RuntimeError("inside critical section")
    assert len(list(fd_root.iterdir())) == baseline

    lock_file = tmp_path / "locks" / "macro_calendar_writer.lock"
    lock_file.unlink()
    symlink_target = tmp_path / "must-not-open"
    symlink_target.write_text("sentinel", encoding="ascii")
    lock_file.symlink_to(symlink_target)
    with pytest.raises(MacroCalendarBusy, match="macro_calendar_busy"):
        with macro_calendar_writer():
            pytest.fail("symlink lock must never be admitted")
    assert symlink_target.read_text(encoding="ascii") == "sentinel"
    assert len(list(fd_root.iterdir())) == baseline

    lock_file.unlink()
    real_import = builtins.__import__

    def _without_fcntl(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError("test fcntl absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _without_fcntl)
    with pytest.raises(MacroCalendarBusy, match="macro_calendar_busy"):
        with macro_calendar_writer():
            pytest.fail("missing fcntl must never degrade to unlocked execution")
    assert len(list(fd_root.iterdir())) == baseline


def test_macro_writer_lock_serializes_two_real_processes(tmp_path):
    lock_dir = tmp_path / "locks"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    script = """
import os
import sys
import time
from pathlib import Path
from src.macro_calendar.write_lock import MacroCalendarBusy, macro_calendar_writer

mode, ready_path, release_path = sys.argv[1:]
if mode == "hold":
    with macro_calendar_writer():
        Path(ready_path).write_text("ready", encoding="ascii")
        deadline = time.monotonic() + 10
        while not Path(release_path).exists():
            if time.monotonic() >= deadline:
                raise SystemExit(9)
            time.sleep(0.02)
elif mode == "busy":
    try:
        with macro_calendar_writer():
            raise SystemExit(7)
    except MacroCalendarBusy:
        raise SystemExit(0)
elif mode == "acquire":
    with macro_calendar_writer():
        pass
"""
    env = {
        **os.environ,
        "ARKSCOPE_LOCK_DIR": str(lock_dir),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    }
    holder = subprocess.Popen(
        [sys.executable, "-c", script, "hold", str(ready), str(release)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and holder.poll() is None:
            if time.monotonic() >= deadline:
                pytest.fail("holder process did not acquire the writer lock")
            time.sleep(0.02)
        assert holder.poll() is None
        blocked = subprocess.run(
            [sys.executable, "-c", script, "busy", str(ready), str(release)],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            check=False,
        )
        assert blocked.returncode == 0
    finally:
        release.write_text("release", encoding="ascii")
        holder.wait(timeout=10)
    assert holder.returncode == 0
    acquired = subprocess.run(
        [sys.executable, "-c", script, "acquire", str(ready), str(release)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
    )
    assert acquired.returncode == 0


def test_schedule_failure_records_one_failed_canonical_row(
    tmp_path, monkeypatch
):
    import src.macro_calendar.execution as execution
    import src.service.jobs as jobs

    scheduler, source, state = _install_macro_source(monkeypatch, tmp_path)
    telemetry = _Telemetry()
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: object())
    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store", lambda dal: telemetry
    )
    monkeypatch.setattr(
        execution,
        "execute_macro_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("scheduled failure")),
    )
    monkeypatch.setattr(
        jobs,
        "run_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("scheduler must not call run_job")
        ),
    )

    result = scheduler.run_source(source, trigger_source="scheduler")

    assert result["status"] == "failed"
    assert result["error"] == "scheduled failure"
    assert [name for name, _ in telemetry.created] == ["fetch_fred_series"]
    assert len(telemetry.finished) == 1
    assert telemetry.finished[0][1]["status"] == "failed"
    assert len(state.attempts) == 1
    assert len(state.outcomes) == 1


def test_schedule_uses_shared_execution_and_records_one_canonical_row(
    tmp_path, monkeypatch
):
    import src.macro_calendar.execution as execution
    import src.service.jobs as jobs

    scheduler, source, state = _install_macro_source(monkeypatch, tmp_path)
    telemetry = _Telemetry()
    calls: list[tuple[str, Any, dict[str, Any], Any]] = []

    def _execute(job_name, dal, params, *, writer_lease=None):
        calls.append((job_name, dal, params, writer_lease))
        return {"series_processed": 1, "observations_upserted": 3}

    dal = object()
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: dal)
    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store", lambda value: telemetry
    )
    monkeypatch.setattr(execution, "execute_macro_job", _execute)
    monkeypatch.setattr(
        jobs,
        "run_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("scheduler must not call run_job")
        ),
    )

    result = scheduler.run_source(source, trigger_source="scheduler")

    assert result["status"] == "succeeded"
    assert result["collect"]["observations_upserted"] == 3
    assert len(calls) == 1
    assert calls[0][:3] == (
        "fetch_fred_series",
        dal,
        {"full_refresh": False},
    )
    assert calls[0][3] is not None
    assert [name for name, _ in telemetry.created] == ["fetch_fred_series"]
    assert len(telemetry.finished) == 1
    assert telemetry.finished[0][1]["status"] == "succeeded"
    assert len(state.attempts) == 1
    assert len(state.outcomes) == 1


def test_backfill_job_is_not_a_recurring_schedule_source():
    import src.service.data_scheduler as scheduler

    expected = {
        "fred_series",
        "fred_release_dates",
        "finnhub_economic_calendar",
        "finnhub_earnings_calendar",
        "finnhub_ipo_calendar",
    }
    assert expected.issubset(scheduler.SOURCES)
    assert "fetch_economic_calendar_backfill" not in {
        definition.backend_job_name for definition in scheduler.SOURCES.values()
    }
    assert "finnhub_economic_calendar_backfill" not in scheduler.SOURCES


def test_fred_series_schedule_is_incremental_and_cannot_request_full_refresh(
    tmp_path, monkeypatch
):
    import src.macro_calendar.execution as execution
    import src.service.data_scheduler as scheduler

    telemetry = _Telemetry()
    state = _SchedulerState()
    params_seen: list[dict[str, Any]] = []
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(scheduler, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(scheduler, "_LAST_RESULT", {})
    monkeypatch.setattr(scheduler, "_state_store", lambda: state)
    monkeypatch.setattr(scheduler, "_provider_config_missing_for_source", lambda source: None)
    monkeypatch.setattr(
        "src.provider_config_runtime.provider_config_setup_state",
        lambda: SimpleNamespace(required=False, reason=None, code=None),
    )
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: object())
    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store", lambda dal: telemetry
    )

    def _execute(job_name, dal, params, *, writer_lease=None):
        params_seen.append(dict(params))
        return {"series_processed": 1, "observations_upserted": 0}

    monkeypatch.setattr(execution, "execute_macro_job", _execute)
    result = scheduler.run_source("fred_series", trigger_source="scheduler")

    assert result["status"] == "succeeded"
    assert params_seen == [{"full_refresh": False}]
    assert telemetry.created[0][1]["payload"] == {"source": "fred_series"}
    assert "full_refresh" not in telemetry.created[0][1]["payload"]


def test_interrupted_macro_state_is_not_reconciled_as_success(tmp_path, monkeypatch):
    import src.service.data_scheduler as scheduler
    from src.scheduler_state import SchedulerStateStore

    state = SchedulerStateStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(scheduler, "_state_store", lambda: state)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "absent-market.db"))
    state.record_attempt(
        "fred_series", datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc)
    )

    result = scheduler.reconcile_interrupted_runtime_state(
        now=datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc)
    )

    assert result["scheduler_sources"] == ["fred_series"]
    durable = state.get("fred_series")
    assert durable is not None
    assert durable["last_status"] == "failed"
    assert "restarted" in durable["last_error"]


def test_macro_and_market_writer_groups_may_fire_in_the_same_tick(monkeypatch):
    import src.service.data_scheduler as scheduler

    due = {"polygon_news", "fred_series", "fred_release_dates"}
    fired: list[str] = []
    recorded: list[dict[str, Any]] = []
    monkeypatch.setattr(scheduler, "_is_due", lambda source, now: source in due)
    monkeypatch.setattr(
        scheduler,
        "_record_result",
        lambda result: recorded.append(result) or result,
    )

    result = scheduler.tick_once(
        datetime(2026, 8, 13, tzinfo=timezone.utc), fire=fired.append
    )

    assert result == fired == ["polygon_news", "fred_series"]
    assert all(row.get("source") != "fred_release_dates" for row in recorded)


def test_macro_source_registry_has_exact_ids_jobs_providers_and_defaults():
    import src.service.data_scheduler as scheduler

    macro_ids = (
        "fred_series",
        "fred_release_dates",
        "finnhub_economic_calendar",
        "finnhub_earnings_calendar",
        "finnhub_ipo_calendar",
    )
    assert tuple(scheduler.SOURCES)[-5:] == macro_ids
    expected = {
        "fred_series": ("fetch_fred_series", "fred", 1440),
        "fred_release_dates": ("fetch_fred_release_dates", "fred", 10080),
        "finnhub_economic_calendar": (
            "fetch_economic_calendar_recent",
            "finnhub",
            60,
        ),
        "finnhub_earnings_calendar": ("fetch_earnings_calendar", "finnhub", 240),
        "finnhub_ipo_calendar": ("fetch_ipo_calendar", "finnhub", 1440),
    }
    assert {
        source: (
            scheduler.SOURCES[source].backend_job_name,
            scheduler._SOURCE_PROVIDER_CONFIG[source],
            scheduler.SOURCES[source].default_interval_min,
        )
        for source in macro_ids
    } == expected
    for source in macro_ids:
        definition = scheduler.SOURCES[source]
        assert definition.writes_macro_db is True
        assert definition.writes_market_db is False
        assert definition.write_target == "macro_calendar.db"
        assert scheduler.job_name(source) == expected[source][0]


def test_macro_sources_default_disabled_while_manual_run_remains_available(
    tmp_path, monkeypatch
):
    import src.service.data_scheduler as scheduler
    from src.profile_state import ProfileStateStore
    from src.service.jobs import _JOB_DEFINITIONS

    store = ProfileStateStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(scheduler, "_store", lambda: store)
    macro_ids = tuple(scheduler.SOURCES)[-5:]
    assert macro_ids == (
        "fred_series",
        "fred_release_dates",
        "finnhub_economic_calendar",
        "finnhub_earnings_calendar",
        "finnhub_ipo_calendar",
    )
    for source in macro_ids:
        assert scheduler.source_config(source)["enabled"] is False
        job = _JOB_DEFINITIONS[scheduler.SOURCES[source].backend_job_name]
        assert job.runnable_via_api is True


def test_missing_provider_config_fails_before_shared_execution(tmp_path, monkeypatch):
    import src.macro_calendar.execution as execution
    import src.service.data_scheduler as scheduler

    telemetry = _Telemetry()
    state = _SchedulerState()
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(scheduler, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(scheduler, "_LAST_RESULT", {})
    monkeypatch.setattr(scheduler, "_state_store", lambda: state)
    monkeypatch.setattr(
        "src.provider_config_runtime.provider_config_setup_state",
        lambda: SimpleNamespace(required=False, reason=None, code=None),
    )
    monkeypatch.setattr(
        scheduler,
        "_provider_config_missing_for_source",
        lambda source: {
            "source": source,
            "status": "not_configured",
            "code": "provider_config_missing",
            "provider": "fred",
            "field": "api_key",
        },
    )
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: object())
    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store", lambda dal: telemetry
    )
    monkeypatch.setattr(
        execution,
        "execute_macro_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("provider execution must not run")
        ),
    )

    result = scheduler.run_source("fred_series", trigger_source="scheduler")

    assert result["status"] == "failed"
    assert result["code"] == "provider_config_missing"
    assert [name for name, _ in telemetry.created] == ["fetch_fred_series"]
    assert telemetry.finished[0][1]["status"] == "failed"
    assert len(state.attempts) == 1
    assert len(state.outcomes) == 1


def test_schedule_reads_do_not_create_macro_calendar_database(tmp_path, monkeypatch):
    import src.service.data_scheduler as scheduler
    from src.api.routes import macro_calendar as macro_routes
    from src.profile_state import ProfileStateStore

    profile_db = tmp_path / "profile_state.db"
    macro_db = tmp_path / "macro_calendar.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_db))
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(macro_db))

    automation = scheduler.read_macro_schedule_automation()
    snapshot = macro_routes.macro_snapshot()

    assert automation == {
        "fred_series": False,
        "fred_release_dates": False,
        "finnhub_economic_calendar": False,
        "finnhub_earnings_calendar": False,
        "finnhub_ipo_calendar": False,
    }
    assert "auto_refresh_enabled" not in snapshot
    assert not profile_db.exists()
    assert not macro_db.exists()

    invalid_profile_db = tmp_path / "not-a-database"
    invalid_profile_db.write_text("not sqlite", encoding="ascii")
    assert scheduler.read_macro_schedule_automation(invalid_profile_db) is None
    profile_directory = tmp_path / "profile-directory"
    profile_directory.mkdir()
    assert scheduler.read_macro_schedule_automation(profile_directory) is None

    populated_profile_db = tmp_path / "populated-profile.db"
    store = ProfileStateStore(populated_profile_db)
    store.set_setting("schedule.fred_series.enabled", "true")
    store.set_setting("schedule.finnhub_earnings_calendar.enabled", "1")
    assert scheduler.read_macro_schedule_automation(populated_profile_db) == {
        "fred_series": True,
        "fred_release_dates": False,
        "finnhub_economic_calendar": False,
        "finnhub_earnings_calendar": True,
        "finnhub_ipo_calendar": False,
    }


def test_scheduler_deferral_keeps_other_macro_sources_due_without_success(
    tmp_path, monkeypatch
):
    import src.service.data_scheduler as scheduler
    from src.macro_calendar.write_lock import macro_calendar_writer

    macro_ids = ("fred_series", "fred_release_dates")
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(scheduler, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(scheduler, "_LAST_RESULT", {})
    monkeypatch.setattr(scheduler, "_provider_config_missing_for_source", lambda source: None)
    monkeypatch.setattr(
        "src.provider_config_runtime.provider_config_setup_state",
        lambda: SimpleNamespace(required=False, reason=None, code=None),
    )
    state = _SchedulerState()
    telemetry = _Telemetry()
    monkeypatch.setattr(scheduler, "_state_store", lambda: state)
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: object())
    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store", lambda dal: telemetry
    )
    monkeypatch.setattr(
        scheduler,
        "source_config",
        lambda source: {"enabled": source in macro_ids, "interval_minutes": 60},
    )
    monkeypatch.setattr(scheduler, "_is_due", lambda source, now: source in macro_ids)

    fired: list[str] = []
    scheduler.tick_once(
        datetime(2026, 8, 13, tzinfo=timezone.utc), fire=fired.append
    )
    assert fired == ["fred_series"]
    assert "fred_release_dates" not in scheduler._LAST_ATTEMPT
    assert "fred_release_dates" not in scheduler._LAST_RESULT

    with macro_calendar_writer():
        result = scheduler.run_source("fred_release_dates", trigger_source="scheduler")
    assert result == {
        "source": "fred_release_dates",
        "status": "deferred",
        "reason": "macro_calendar_busy",
    }
    assert "fred_release_dates" not in scheduler._LAST_ATTEMPT
    assert "fred_release_dates" not in scheduler._LAST_RESULT
    assert state.attempts == [] and state.outcomes == []
    assert telemetry.created == [] and telemetry.finished == []

    ready = tmp_path / "holder-ready"
    release = tmp_path / "holder-release"
    script = """
import sys
import time
from pathlib import Path
from src.macro_calendar.write_lock import macro_calendar_writer
ready, release = map(Path, sys.argv[1:])
with macro_calendar_writer():
    ready.write_text("ready", encoding="ascii")
    deadline = time.monotonic() + 10
    while not release.exists():
        if time.monotonic() >= deadline:
            raise SystemExit(9)
        time.sleep(0.02)
"""
    env = {
        **os.environ,
        "ARKSCOPE_LOCK_DIR": str(tmp_path / "locks"),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    }
    holder = subprocess.Popen(
        [sys.executable, "-c", script, str(ready), str(release)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and holder.poll() is None:
            if time.monotonic() >= deadline:
                pytest.fail("file-lock holder did not become ready")
            time.sleep(0.02)
        assert holder.poll() is None
        result = scheduler.run_source("fred_release_dates", trigger_source="scheduler")
        assert result["status"] == "deferred"
        assert "fred_release_dates" not in scheduler._LAST_ATTEMPT
        assert "fred_release_dates" not in scheduler._LAST_RESULT
        assert state.attempts == [] and state.outcomes == []
        assert telemetry.created == [] and telemetry.finished == []
    finally:
        release.write_text("release", encoding="ascii")
        holder.wait(timeout=10)
    assert holder.returncode == 0


def test_scheduler_fires_at_most_one_due_macro_writer_per_tick(monkeypatch):
    import src.service.data_scheduler as scheduler

    macro_ids = {
        "fred_series",
        "fred_release_dates",
        "finnhub_economic_calendar",
        "finnhub_earnings_calendar",
        "finnhub_ipo_calendar",
    }
    fired: list[str] = []
    recorded: list[dict[str, Any]] = []
    monkeypatch.setattr(scheduler, "_is_due", lambda source, now: source in macro_ids)
    monkeypatch.setattr(
        scheduler,
        "_record_result",
        lambda result: recorded.append(result) or result,
    )

    result = scheduler.tick_once(
        datetime(2026, 8, 13, tzinfo=timezone.utc), fire=fired.append
    )

    assert result == fired == ["fred_series"]
    assert recorded == []
