"""Shared macro execution, telemetry, and writer-lock contracts."""

from __future__ import annotations

import builtins
import os
import subprocess
import sys
import time
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
    assert calls[0][:3] == ("fetch_fred_series", dal, {})
    assert calls[0][3] is not None
    assert [name for name, _ in telemetry.created] == ["fetch_fred_series"]
    assert len(telemetry.finished) == 1
    assert telemetry.finished[0][1]["status"] == "succeeded"
    assert len(state.attempts) == 1
    assert len(state.outcomes) == 1
