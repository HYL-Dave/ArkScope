from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import threading

import pytest

from src.portfolio_capture import PortfolioCaptureService
from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerAccountRef,
    BrokerCaptureResult,
    CaptureLegResult,
    CaptureRunSuperseded,
    PositionObservation,
    ProviderReadiness,
)
from src.portfolio_ibkr import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    BrokerSnapshot,
    preview_or_apply_ibkr_snapshot,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioStore


NOW = datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc)


class FakeFileLock:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.held = False
        self.acquire_calls: list[float] = []
        self.release_calls = 0
        self.released = threading.Event()

    def acquire(self, timeout: float = 0.0, poll: float = 5.0) -> bool:
        self.acquire_calls.append(timeout)
        if not self.available or self.held:
            return False
        self.held = True
        return True

    def release(self) -> None:
        assert self.held
        self.held = False
        self.release_calls += 1
        self.released.set()


@contextmanager
def available_gateway(timeout: float):
    assert timeout == 0
    yield


def capture_result(
    *,
    accounts: tuple[str, ...] = ("DU123",),
    quantities: tuple[float, ...] | None = None,
    account_state: str = "complete",
    execution_state: str = "complete",
    position_state: str = "complete",
    finished_at: str = "2026-07-14T04:00:00+00:00",
) -> BrokerCaptureResult:
    if quantities is None:
        quantities = tuple(float(index + 1) for index in range(len(accounts)))
    snapshots = (
        tuple(
            AccountSnapshotObservation(
                broker_account_id=account,
                as_of_utc=finished_at,
                base_currency="USD",
                net_liquidation=100_000.0 + index,
            )
            for index, account in enumerate(accounts)
        )
        if account_state in {"complete", "partial"}
        else ()
    )
    positions = (
        tuple(
            PositionObservation(
                broker_account_id=account,
                broker_con_id=str(1000 + index),
                symbol=f"T{index}",
                asset_class="stock",
                quantity=quantity,
                avg_cost=10.0,
                currency="USD",
            )
            for index, (account, quantity) in enumerate(zip(accounts, quantities))
        )
        if position_state in {"complete", "partial"}
        else ()
    )
    return BrokerCaptureResult(
        finished_at_utc=finished_at,
        discovered_accounts=tuple(BrokerAccountRef(account, "USD") for account in accounts),
        account_leg=CaptureLegResult(account_state),
        execution_leg=CaptureLegResult(execution_state),
        position_leg=CaptureLegResult(position_state),
        account_snapshots=snapshots,
        positions=positions,
        executions=(),
        commissions=(),
    )


def service_for(
    tmp_path,
    *,
    reader,
    readiness: ProviderReadiness | None = None,
    write_allowed=lambda action, detail: True,
    process_lock: FakeFileLock | None = None,
    gateway_lock=available_gateway,
):
    db = tmp_path / "profile_state.db"
    portfolio = PortfolioStore(db)
    observations = PortfolioObservationStore(db)
    lock = process_lock or FakeFileLock()
    provider = readiness or ProviderReadiness(configured=True)
    service = PortfolioCaptureService(
        observations=observations,
        portfolio=portfolio,
        reader=reader,
        provider_readiness=lambda: provider,
        write_allowed=write_allowed,
        capture_process_lock=lock,
        gateway_lock=gateway_lock,
        clock=lambda: NOW,
    )
    return service, portfolio, observations, lock


def seed_position(
    store: PortfolioStore,
    *,
    account: str,
    con_id: str,
    quantity: float,
) -> None:
    preview_or_apply_ibkr_snapshot(
        store,
        BrokerSnapshot(
            accounts=[
                BrokerAccountSnapshot(
                    account_id=account,
                    label=f"IBKR {account}",
                    base_currency="USD",
                )
            ],
            positions=[
                BrokerPositionSnapshot(
                    account_id=account,
                    con_id=con_id,
                    symbol="OLD",
                    asset_class="stock",
                    quantity=quantity,
                )
            ],
        ),
        apply=True,
    )


def test_permission_denied_is_ephemeral_blocked_and_calls_no_provider(tmp_path):
    calls: list[str] = []
    lock = FakeFileLock()
    db = tmp_path / "profile_state.db"
    observations = PortfolioObservationStore(db)
    service = PortfolioCaptureService(
        observations=observations,
        portfolio=PortfolioStore(db),
        reader=lambda: (_ for _ in ()).throw(AssertionError("reader called")),
        provider_readiness=lambda: (_ for _ in ()).throw(
            AssertionError("provider readiness called")
        ),
        write_allowed=lambda action, detail: calls.append(action) or False,
        capture_process_lock=lock,
        gateway_lock=available_gateway,
        clock=lambda: NOW,
    )

    started = service.trigger("manual", background=False)

    assert started.accepted is False
    assert started.state == "blocked"
    assert started.error_code == "permission_denied"
    assert started.run is None
    assert calls
    assert observations.list_runs() == []
    assert lock.acquire_calls == []


def test_missing_provider_records_blocked_and_calls_no_reader(tmp_path):
    service, _, observations, lock = service_for(
        tmp_path,
        reader=lambda: (_ for _ in ()).throw(AssertionError("reader called")),
        readiness=ProviderReadiness(
            configured=False,
            code="provider_config_missing",
            status="not_configured",
            field="host",
        ),
    )

    started = service.trigger("manual", background=False)

    assert started.accepted is True
    assert started.state == "blocked"
    assert started.error_code == "provider_config_missing"
    assert started.run == observations.get_run(started.run.id)
    assert started.run.state == "blocked"
    assert lock.acquire_calls == []
    assert service.status().next_due_at == "2026-07-14T04:15:00+00:00"


def test_concurrent_trigger_is_already_running_and_opens_no_second_reader(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    reader_calls = 0

    def reader():
        nonlocal reader_calls
        reader_calls += 1
        entered.set()
        assert release.wait(timeout=2)
        return capture_result()

    service, _, observations, lock = service_for(tmp_path, reader=reader)
    original_finish = observations.finish_run

    def finish(*args, **kwargs):
        try:
            return original_finish(*args, **kwargs)
        finally:
            finished.set()

    observations.finish_run = finish
    first = service.trigger("manual", background=True)
    assert first.accepted is True
    assert first.state == "running"
    assert entered.wait(timeout=2)

    second = service.trigger("manual", background=False)

    assert second.accepted is False
    assert second.state == "blocked"
    assert second.error_code == "already_running"
    assert len(observations.list_runs()) == 1
    assert reader_calls == 1
    release.set()
    assert finished.wait(timeout=2)
    assert lock.released.wait(timeout=2)
    assert lock.held is False

    failed_service, _, failed_observations, failed_lock = service_for(
        tmp_path / "thread-start-failure", reader=lambda: capture_result()
    )

    def fail_thread_start(self):
        raise RuntimeError("thread creation failed")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(threading.Thread, "start", fail_thread_start)
        failed_start = failed_service.trigger("manual", background=True)

    assert failed_start.accepted is True
    assert failed_start.state == "failed"
    assert failed_start.error_code == "capture_thread_start_failed"
    assert failed_observations.get_run(failed_start.run.id).state == "failed"
    assert failed_lock.held is False
    assert failed_service._capture_lock.locked() is False

    other_db = tmp_path / "other.db"
    other_observations = PortfolioObservationStore(other_db)
    durable_running = other_observations.create_run(
        trigger="startup", effective_client_id=71
    )
    held_elsewhere = FakeFileLock(available=False)
    other = PortfolioCaptureService(
        observations=other_observations,
        portfolio=PortfolioStore(other_db),
        reader=lambda: (_ for _ in ()).throw(AssertionError("second reader called")),
        provider_readiness=lambda: ProviderReadiness(configured=True),
        write_allowed=lambda action, detail: True,
        capture_process_lock=held_elsewhere,
        gateway_lock=available_gateway,
        clock=lambda: NOW,
    )

    assert other.reconcile_startup() == []
    assert other_observations.get_run(durable_running.id).state == "running"
    cross_process = other.trigger("manual", background=False)
    assert cross_process.accepted is False
    assert cross_process.error_code == "already_running"
    assert len(other_observations.list_runs()) == 1


def test_gateway_busy_finishes_blocked_without_reader_call(tmp_path):
    @contextmanager
    def busy_gateway(timeout: float):
        assert timeout == 0
        raise TimeoutError("held by another IBKR job")
        yield

    service, _, observations, lock = service_for(
        tmp_path,
        reader=lambda: (_ for _ in ()).throw(AssertionError("reader called")),
        gateway_lock=busy_gateway,
    )

    started = service.trigger("manual", background=False)

    assert started.accepted is True
    assert started.state == "blocked"
    assert started.error_code == "gateway_busy"
    assert observations.get_run(started.run.id).state == "blocked"
    assert service.status().next_due_at == "2026-07-14T04:15:00+00:00"
    assert lock.held is False


def test_observation_commit_happens_before_auto_apply(tmp_path):
    events: list[str] = []

    def reader():
        events.append("read")
        return capture_result()

    service, portfolio, observations, _ = service_for(tmp_path, reader=reader)
    portfolio.upsert_broker_account(
        "ibkr", "DU123", "Auto", sync_mode="ibkr_auto"
    )
    original_commit = observations.commit_capture
    original_apply = portfolio.apply_broker_positions
    original_finish = observations.finish_run

    def commit(*args, **kwargs):
        events.append("commit")
        return original_commit(*args, **kwargs)

    def apply(*args, **kwargs):
        events.append("apply")
        return original_apply(*args, **kwargs)

    def finish(*args, **kwargs):
        events.append("finish")
        return original_finish(*args, **kwargs)

    observations.commit_capture = commit
    portfolio.apply_broker_positions = apply
    observations.finish_run = finish

    started = service.trigger("manual", background=False)

    assert started.state == "succeeded"
    assert events == ["read", "commit", "apply", "finish"]


def test_observation_commit_failure_prevents_canonical_apply(tmp_path):
    service, portfolio, observations, _ = service_for(
        tmp_path, reader=lambda: capture_result()
    )
    portfolio.upsert_broker_account(
        "ibkr", "DU123", "Auto", sync_mode="ibkr_auto"
    )
    observations.commit_capture = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("database unavailable")
    )
    apply_calls: list[int] = []
    portfolio.apply_broker_positions = lambda **kwargs: apply_calls.append(
        kwargs["account_id"]
    )

    started = service.trigger("manual", background=False)

    assert started.state == "failed"
    assert started.error_code == "observation_commit_failed"
    assert apply_calls == []
    assert observations.get_run(started.run.id).state == "failed"


def test_auto_mode_applies_only_complete_position_leg_and_auto_accounts(tmp_path):
    service, portfolio, _, _ = service_for(
        tmp_path,
        reader=lambda: capture_result(
            accounts=("DUAUTO", "DUREVIEW"), quantities=(7.0, 9.0)
        ),
    )
    auto = portfolio.upsert_broker_account(
        "ibkr", "DUAUTO", "Auto", sync_mode="ibkr_auto"
    )
    archived = portfolio.update_account(auto.id, archived=True)
    review = portfolio.upsert_broker_account(
        "ibkr", "DUREVIEW", "Review", sync_mode="ibkr_review"
    )

    started = service.trigger("manual", background=False)

    assert started.state == "succeeded"
    assert [p.quantity for p in portfolio.list_positions(account_id=auto.id)] == [7.0]
    assert portfolio.list_positions(account_id=review.id) == []
    assert portfolio.get_account(auto.id).archived_at == archived.archived_at


def test_incomplete_position_leg_never_closes_canonical_positions(tmp_path):
    service, portfolio, _, _ = service_for(
        tmp_path,
        reader=lambda: capture_result(position_state="failed"),
    )
    account = portfolio.upsert_broker_account(
        "ibkr", "DU123", "Auto", sync_mode="ibkr_auto"
    )
    seed_position(portfolio, account="DU123", con_id="existing", quantity=3)
    original_apply = portfolio.apply_broker_positions
    apply_calls: list[int] = []

    def unexpected_apply(**kwargs):
        apply_calls.append(kwargs["account_id"])
        return original_apply(**kwargs)

    portfolio.apply_broker_positions = unexpected_apply

    started = service.trigger("manual", background=False)

    assert started.state == "partial"
    assert apply_calls == []
    assert portfolio.list_positions(account_id=account.id)[0].closed_at is None


def test_review_mode_persists_observations_without_canonical_write(tmp_path):
    service, portfolio, observations, _ = service_for(
        tmp_path, reader=lambda: capture_result()
    )
    account = portfolio.upsert_broker_account(
        "ibkr", "DU123", "Review", sync_mode="ibkr_review"
    )
    apply_calls: list[int] = []
    portfolio.apply_broker_positions = lambda **kwargs: apply_calls.append(
        kwargs["account_id"]
    )

    started = service.trigger("manual", background=False)

    stored = observations.position_snapshot_for_run(started.run.id)
    assert [position.quantity for position in stored.positions] == [1.0]
    assert apply_calls == []
    assert portfolio.list_positions(account_id=account.id) == []


def test_manual_mode_persists_observations_without_canonical_write(tmp_path):
    service, portfolio, observations, _ = service_for(
        tmp_path, reader=lambda: capture_result()
    )
    account = portfolio.upsert_broker_account(
        "ibkr", "DU123", "Locally managed", sync_mode="manual"
    )
    apply_calls: list[int] = []
    portfolio.apply_broker_positions = lambda **kwargs: apply_calls.append(
        kwargs["account_id"]
    )

    started = service.trigger("manual", background=False)

    stored = observations.position_snapshot_for_run(started.run.id)
    assert [position.quantity for position in stored.positions] == [1.0]
    assert apply_calls == []
    assert portfolio.list_positions(account_id=account.id) == []


def test_canonical_apply_failure_keeps_observations_and_finishes_partial(tmp_path):
    service, portfolio, observations, _ = service_for(
        tmp_path, reader=lambda: capture_result()
    )
    account = portfolio.upsert_broker_account(
        "ibkr", "DU123", "Auto", sync_mode="ibkr_auto"
    )
    portfolio.apply_broker_positions = lambda **kwargs: (_ for _ in ()).throw(
        RuntimeError("canonical write failed")
    )

    started = service.trigger("manual", background=False)

    stored = observations.position_snapshot_for_run(started.run.id)
    assert [position.quantity for position in stored.positions] == [1.0]
    assert observations.get_run(started.run.id).state == "partial"
    assert started.error_code == "canonical_apply_failed"
    assert portfolio.list_positions(account_id=account.id) == []


def test_partial_capture_persists_valid_legs(tmp_path):
    service, portfolio, observations, _ = service_for(
        tmp_path,
        reader=lambda: capture_result(
            execution_state="failed",
            position_state="partial",
        ),
    )

    started = service.trigger("manual", background=False)

    assert started.state == "partial"
    assert started.run.account_leg_state == "complete"
    assert started.run.execution_leg_state == "failed"
    assert started.run.position_leg_state == "partial"
    with observations._connect() as conn:
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM portfolio_account_snapshots WHERE capture_run_id=?",
            (started.run.id,),
        ).fetchone()[0]
        position_count = conn.execute(
            "SELECT COUNT(*) FROM portfolio_broker_position_observations "
            "WHERE capture_run_id=?",
            (started.run.id,),
        ).fetchone()[0]
    assert (snapshot_count, position_count) == (1, 1)
    assert portfolio.list_positions() == []


def test_review_preview_is_derived_from_run_and_is_zero_write(tmp_path):
    reader_calls = 0

    def reader():
        nonlocal reader_calls
        reader_calls += 1
        return capture_result()

    service, portfolio, _, _ = service_for(tmp_path, reader=reader)
    account = portfolio.upsert_broker_account(
        "ibkr", "DU123", "Legacy IBKR DU123", sync_mode="ibkr_review"
    )
    started = service.trigger("manual", background=False)

    preview = service.preview_run(started.run.id)
    status = service.status()

    assert preview.run_id == started.run.id
    assert preview.applies is False
    assert len(preview.changes) == 1
    assert preview.changes[0].account_id == account.id
    assert preview.changes[0].account_label == f"IBKR · {account.broker_account_id_hash[:8]}"
    assert preview.changes[0].broker_account_id_hash == account.broker_account_id_hash
    assert "DU123" not in repr(preview)
    assert "DU123" not in repr(status)
    assert status.review_run_id == started.run.id
    assert status.review == preview
    assert portfolio.get_account(account.id).label == "Legacy IBKR DU123"
    assert portfolio.list_positions(account_id=account.id) == []
    assert [
        row.broker
        for row in portfolio.list_accounts(
            include_archived=True,
            ensure_manual=False,
        )
    ] == ["ibkr"]
    assert reader_calls == 1


def test_apply_review_requires_latest_complete_run_and_never_rereads_gateway(tmp_path):
    quantities = iter((1.0, 2.0))
    reader_calls = 0

    def reader():
        nonlocal reader_calls
        reader_calls += 1
        return capture_result(quantities=(next(quantities),))

    service, portfolio, observations, process_lock = service_for(
        tmp_path, reader=reader
    )
    account = portfolio.upsert_broker_account(
        "ibkr", "DU123", "Review", sync_mode="ibkr_review"
    )
    first = service.trigger("manual", background=False).run
    second = service.trigger("manual", background=False).run

    with pytest.raises(CaptureRunSuperseded):
        service.apply_review_run(first.id)

    original_latest = observations.latest_reviewable_run_id
    lock_checks: list[tuple[bool, bool]] = []

    def latest_while_owned():
        lock_checks.append((service._capture_lock.locked(), process_lock.held))
        return original_latest()

    observations.latest_reviewable_run_id = latest_while_owned
    applied = service.apply_review_run(second.id)

    assert applied.run_id == second.id
    assert applied.applies is True
    assert lock_checks == [(True, True)]
    assert [position.quantity for position in portfolio.list_positions(account_id=account.id)] == [2.0]
    assert reader_calls == 2
