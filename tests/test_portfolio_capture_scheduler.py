from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from src import portfolio_capture_scheduler
from src.portfolio_capture import CaptureStart, PortfolioCaptureService
from src.portfolio_capture_types import (
    BrokerCaptureResult,
    CaptureLegResult,
    ProviderReadiness,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioStore


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class FakeFileLock:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.held = False
        self.acquire_calls: list[float] = []

    def acquire(self, timeout: float = 0.0, poll: float = 5.0) -> bool:
        self.acquire_calls.append(timeout)
        if not self.available or self.held:
            return False
        self.held = True
        return True

    def release(self) -> None:
        assert self.held
        self.held = False


@contextmanager
def available_gateway(timeout: float):
    assert timeout == 0
    yield


def empty_result(
    finished_at: datetime,
    *,
    account_state: str = "complete",
    execution_state: str = "complete",
    position_state: str = "complete",
) -> BrokerCaptureResult:
    return BrokerCaptureResult(
        finished_at_utc=finished_at.isoformat(),
        discovered_accounts=(),
        account_leg=CaptureLegResult(account_state),
        execution_leg=CaptureLegResult(execution_state),
        position_leg=CaptureLegResult(position_state),
        account_snapshots=(),
        positions=(),
        executions=(),
        commissions=(),
    )


def make_service(tmp_path, *, clock: MutableClock, reader=None):
    db = tmp_path / "profile_state.db"
    observations = PortfolioObservationStore(db)
    process_lock = FakeFileLock()
    service = PortfolioCaptureService(
        observations=observations,
        portfolio=PortfolioStore(db),
        reader=reader or (lambda: empty_result(clock.now)),
        provider_readiness=lambda: ProviderReadiness(configured=True),
        write_allowed=lambda action, detail: True,
        capture_process_lock=process_lock,
        gateway_lock=available_gateway,
        clock=clock,
    )
    return service, observations, process_lock


def install_trigger_spy(service: PortfolioCaptureService):
    calls: list[tuple[str, bool]] = []

    def trigger(trigger: str, *, background: bool = True) -> CaptureStart:
        calls.append((trigger, background))
        return CaptureStart(
            accepted=True,
            run=None,
            state="running",
        )

    service.trigger = trigger
    return calls


def test_startup_runs_when_no_success_exists(tmp_path):
    clock = MutableClock(datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc))
    service, observations, _ = make_service(tmp_path, clock=clock)
    stale = observations.create_run(trigger="manual", effective_client_id=71)

    assert service.reconcile_startup() == [stale.id]
    assert observations.get_run(stale.id).state == "interrupted"
    calls = install_trigger_spy(service)

    started = service.scheduler_tick(startup=True, now=clock.now)

    assert started is not None
    assert calls == [("startup", True)]


def test_startup_does_not_run_when_last_success_is_inside_interval(tmp_path):
    clock = MutableClock(datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc))
    service, observations, _ = make_service(tmp_path, clock=clock)
    observations.last_successful_finished_at = lambda: clock.now - timedelta(minutes=5)
    calls = install_trigger_spy(service)

    started = service.scheduler_tick(startup=True, now=clock.now)

    assert started is None
    assert calls == []
    assert service.status().next_due_at == "2026-07-14T04:10:00+00:00"


def test_startup_runs_when_last_success_is_stale(tmp_path):
    clock = MutableClock(datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc))
    service, observations, _ = make_service(tmp_path, clock=clock)
    observations.last_successful_finished_at = lambda: clock.now - timedelta(minutes=20)
    calls = install_trigger_spy(service)

    started = service.scheduler_tick(startup=True, now=clock.now)

    assert started is not None
    assert calls == [("startup", True)]


def test_partial_or_failed_completion_sets_next_due_from_completion(tmp_path):
    cases = (
        ("partial", ("complete", "failed", "failed")),
        ("failed", ("failed", "failed", "failed")),
    )
    for index, (expected_state, states) in enumerate(cases):
        clock = MutableClock(datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc))

        def reader(states=states):
            clock.now += timedelta(minutes=2)
            return empty_result(
                clock.now,
                account_state=states[0],
                execution_state=states[1],
                position_state=states[2],
            )

        service, _, _ = make_service(
            tmp_path / str(index), clock=clock, reader=reader
        )

        started = service.trigger("manual", background=False)

        assert started.state == expected_state
        assert service.status().next_due_at == "2026-07-14T04:17:00+00:00"


def test_successful_manual_run_resets_next_due(tmp_path):
    clock = MutableClock(datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc))

    def reader():
        clock.now += timedelta(minutes=3)
        return empty_result(clock.now)

    service, _, _ = make_service(tmp_path, clock=clock, reader=reader)
    service._next_due_at = clock.now + timedelta(hours=1)

    started = service.trigger("manual", background=False)

    assert started.state == "succeeded"
    assert service.status().next_due_at == "2026-07-14T04:18:00+00:00"


def test_already_running_manual_request_does_not_reset_due(tmp_path):
    clock = MutableClock(datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc))
    service, observations, process_lock = make_service(tmp_path, clock=clock)
    due = clock.now + timedelta(minutes=8)
    service._next_due_at = due
    durable = observations.create_run(trigger="manual", effective_client_id=71)
    assert service._capture_lock.acquire(blocking=False)
    try:
        assert service.reconcile_startup() == []
        assert process_lock.acquire_calls == []
        started = service.trigger("manual", background=False)
    finally:
        service._capture_lock.release()

    assert started.accepted is False
    assert started.error_code == "already_running"
    assert service._next_due_at == due
    assert observations.get_run(durable.id).state == "running"


def test_periodic_disabled_still_allows_manual_trigger(tmp_path):
    clock = MutableClock(datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc))
    reader_calls = 0

    def reader():
        nonlocal reader_calls
        reader_calls += 1
        return empty_result(clock.now)

    service, observations, _ = make_service(tmp_path, clock=clock, reader=reader)
    observations.set_settings(enabled=False, interval_minutes=15)

    assert service.scheduler_tick(startup=True, now=clock.now) is None
    assert reader_calls == 0
    started = service.trigger("manual", background=False)

    assert started.state == "succeeded"
    assert reader_calls == 1


def test_scheduler_loop_survives_one_failed_tick_without_tight_retry(monkeypatch):
    class FakeService:
        def __init__(self) -> None:
            self.startup_values: list[bool] = []

        def scheduler_tick(self, *, startup: bool = False):
            self.startup_values.append(startup)
            if len(self.startup_values) == 1:
                raise RuntimeError("one failed coordinator tick")
            raise asyncio.CancelledError

    sleeps: list[float] = []

    async def fake_sleep(seconds: float):
        sleeps.append(seconds)

    fake = FakeService()
    monkeypatch.setattr(portfolio_capture_scheduler.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            portfolio_capture_scheduler.portfolio_capture_scheduler_loop(
                fake, poll_seconds=15.0
            )
        )

    assert fake.startup_values == [True, False]
    assert sleeps == [15.0]
