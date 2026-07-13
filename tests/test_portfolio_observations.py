from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerAccountRef,
    BrokerCaptureResult,
    CaptureLegResult,
    CommissionObservation,
    ExecutionObservation,
    PositionObservation,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioStore


@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "profile_state.db"
    portfolio = PortfolioStore(db)
    observations = PortfolioObservationStore(db)
    return portfolio, observations


def execution(
    *,
    exec_id: str = "0001",
    account: str = "DU123",
    quantity: float = 2.0,
    side: str = "BUY",
    price: float = 101.0,
    execution_time: str = "2026-01-05T15:30:00+00:00",
) -> ExecutionObservation:
    return ExecutionObservation(
        broker_account_id=account,
        exec_id=exec_id,
        execution_time_utc=execution_time,
        broker_con_id="265598",
        symbol="AAPL",
        asset_class="stock",
        currency="USD",
        exchange="NASDAQ",
        side=side,
        quantity=quantity,
        price=price,
        order_id=10,
        perm_id=20,
        client_id=30,
        order_ref="capture-test",
        liquidation=0,
        cumulative_quantity=quantity,
        average_price=price,
    )


def complete_result(
    *,
    finished_at: str,
    account: str = "DU123",
    quantity: float = 1.0,
    executions: tuple[ExecutionObservation, ...] = (),
    commissions: tuple[CommissionObservation, ...] = (),
) -> BrokerCaptureResult:
    return BrokerCaptureResult(
        finished_at_utc=finished_at,
        discovered_accounts=(BrokerAccountRef(account, "USD"),),
        account_leg=CaptureLegResult("complete"),
        execution_leg=CaptureLegResult("complete"),
        position_leg=CaptureLegResult("complete"),
        account_snapshots=(
            AccountSnapshotObservation(
                broker_account_id=account,
                as_of_utc=finished_at,
                base_currency="USD",
                net_liquidation=100_000.0,
                total_cash_value=10_000.0,
            ),
        ),
        positions=(
            PositionObservation(
                broker_account_id=account,
                broker_con_id="265598",
                symbol="AAPL",
                asset_class="stock",
                quantity=quantity,
                avg_cost=100.0,
                currency="USD",
            ),
        ),
        executions=executions,
        commissions=commissions,
    )


def commit(
    observations: PortfolioObservationStore,
    result: BrokerCaptureResult,
    *,
    trigger: str = "manual",
):
    run = observations.create_run(trigger=trigger, effective_client_id=61)
    committed = observations.commit_capture(run.id, result)
    observations.finish_run(run.id, state="succeeded")
    return run.id, committed


def rows(observations: PortfolioObservationStore, sql: str, params=()):
    with observations._connect() as conn:
        return conn.execute(sql, params).fetchall()


def test_fresh_schema_creates_capture_tables_with_no_cascade_foreign_keys(stores):
    _, observations = stores
    expected = {
        "portfolio_capture_settings",
        "portfolio_capture_runs",
        "portfolio_capture_run_accounts",
        "portfolio_account_snapshots",
        "portfolio_broker_position_observations",
        "portfolio_broker_executions",
        "portfolio_broker_commission_reports",
        "portfolio_unmatched_position_changes",
    }
    tables = {
        row[0]
        for row in rows(
            observations,
            "SELECT name FROM sqlite_master WHERE type='table'",
        )
    }

    assert expected <= tables
    for table in expected:
        foreign_keys = rows(observations, f"PRAGMA foreign_key_list({table})")
        assert all(foreign_key[6].upper() != "CASCADE" for foreign_key in foreign_keys)
    assert rows(observations, "PRAGMA foreign_key_check") == []


def test_settings_write_is_atomic_and_rejects_interval_outside_5_to_1440(stores):
    _, observations = stores
    assert observations.get_stored_settings() is None
    saved = observations.set_settings(enabled=True, interval_minutes=15)
    assert saved.enabled is True
    assert saved.interval_minutes == 15

    for invalid in (4, 1441):
        with pytest.raises(ValueError, match="interval_minutes"):
            observations.set_settings(enabled=False, interval_minutes=invalid)

    assert observations.get_stored_settings() == saved


def test_run_lifecycle_and_recent_order_are_durable(stores):
    _, observations = stores
    first = observations.create_run(trigger="startup", effective_client_id=61)
    first = observations.finish_run(first.id, state="succeeded")
    second = observations.record_blocked(
        trigger="scheduled",
        effective_client_id=61,
        error_code="provider_unavailable",
        error_detail="Gateway is offline",
    )

    reopened = PortfolioObservationStore(observations.path)
    assert [run.id for run in reopened.list_runs(limit=2)] == [second.id, first.id]
    assert reopened.get_run(first.id).state == "succeeded"
    assert reopened.get_run(second.id).state == "blocked"
    assert reopened.last_successful_finished_at() == datetime.fromisoformat(
        first.finished_at
    ).astimezone(timezone.utc)
    with pytest.raises(ValueError, match="already terminal"):
        reopened.finish_run(first.id, state="failed")


def test_startup_reconciles_stale_running_rows_to_interrupted(stores, monkeypatch):
    _, observations = stores
    first = observations.create_run(trigger="startup", effective_client_id=61)
    second = observations.create_run(trigger="manual", effective_client_id=61)
    endpoint = "2026-01-06T04:59:00+00:00"
    observations.commit_capture(
        second.id,
        replace(
            complete_result(finished_at=endpoint),
            account_snapshots=(),
            positions=(),
        ),
    )
    monkeypatch.setattr(
        "src.portfolio_observations._now",
        lambda: "2026-01-06T05:01:00+00:00",
    )

    assert observations.reconcile_interrupted() == [first.id, second.id]
    assert observations.get_run(first.id).state == "interrupted"
    assert observations.get_run(second.id).state == "interrupted"
    assert observations.get_run(first.id).finished_at == "2026-01-06T05:01:00+00:00"
    assert observations.get_run(second.id).finished_at == endpoint
    assert observations.reconcile_interrupted() == []


def test_identical_account_values_still_create_one_snapshot_per_run(stores):
    _, observations = stores
    first_id, _ = commit(
        observations, complete_result(finished_at="2026-01-05T15:00:00+00:00")
    )
    second_id, _ = commit(
        observations, complete_result(finished_at="2026-01-05T16:00:00+00:00")
    )

    snapshots = rows(
        observations,
        "SELECT capture_run_id, net_liquidation FROM portfolio_account_snapshots ORDER BY id",
    )
    assert [(row[0], row[1]) for row in snapshots] == [
        (first_id, 100_000.0),
        (second_id, 100_000.0),
    ]


def test_duplicate_execution_is_a_noop(stores):
    _, observations = stores
    first_id, first = commit(
        observations,
        complete_result(
            finished_at="2026-01-05T15:00:00+00:00",
            executions=(execution(),),
        ),
    )
    _, duplicate = commit(
        observations,
        complete_result(
            finished_at="2026-01-05T16:00:00+00:00",
            executions=(execution(),),
        ),
    )

    stored = rows(observations, "SELECT * FROM portfolio_broker_executions")
    assert len(stored) == 1
    assert stored[0]["first_observed_run_id"] == first_id
    assert first.inserted_execution_count == 1
    assert duplicate.inserted_execution_count == 0
    assert duplicate.data_conflict_count == 0


def test_changed_duplicate_execution_is_data_conflict_without_overwrite(stores):
    _, observations = stores
    commit(
        observations,
        complete_result(
            finished_at="2026-01-05T15:00:00+00:00",
            executions=(execution(price=101.0),),
        ),
    )
    run = observations.create_run(trigger="manual", effective_client_id=61)
    result = observations.commit_capture(
        run.id,
        complete_result(
            finished_at="2026-01-05T16:00:00+00:00",
            executions=(execution(price=999.0),),
        ),
    )
    terminal = observations.finish_run(
        run.id,
        state="partial",
        error_code="execution_data_conflict",
        error_detail="exec_id 0001 conflicted; account DU123 was redacted",
    )

    stored = rows(observations, "SELECT price FROM portfolio_broker_executions")
    assert [row[0] for row in stored] == [101.0]
    assert result.data_conflict_count == 1
    assert terminal.data_conflict_count == 1
    assert terminal.error_code == "execution_data_conflict"
    assert terminal.error_detail is not None
    assert "DU123" not in terminal.error_detail


def test_identical_commission_is_a_noop_and_changed_content_is_a_revision(stores):
    _, observations = stores
    report = CommissionObservation("DU123", "0001", 1.25, "USD", 8.0)
    _, first = commit(
        observations,
        complete_result(
            finished_at="2026-01-05T15:00:00+00:00",
            executions=(execution(),),
            commissions=(report,),
        ),
    )
    _, duplicate = commit(
        observations,
        complete_result(
            finished_at="2026-01-05T16:00:00+00:00",
            executions=(execution(),),
            commissions=(report,),
        ),
    )
    _, revision = commit(
        observations,
        complete_result(
            finished_at="2026-01-05T17:00:00+00:00",
            executions=(execution(),),
            commissions=(replace(report, commission=1.5),),
        ),
    )

    stored = rows(
        observations,
        "SELECT commission, content_hash FROM portfolio_broker_commission_reports ORDER BY id",
    )
    assert [row[0] for row in stored] == [1.25, 1.5]
    assert stored[0][1] != stored[1][1]
    assert first.inserted_commission_count == 1
    assert duplicate.inserted_commission_count == 0
    assert revision.inserted_commission_count == 1


def test_correction_family_links_previous_and_reconciliation_uses_latest_revision(stores):
    _, observations = stores
    commit(
        observations,
        complete_result(
            finished_at="2026-01-05T15:00:00+00:00", quantity=10.0
        ),
    )
    original = execution(exec_id="fill.1", quantity=5.0)
    correction = replace(
        execution(exec_id="fill.2", quantity=2.0),
        broker_con_id="999999",
        symbol="MSFT",
    )
    corrected_result = complete_result(
        finished_at="2026-01-05T16:00:00+00:00",
        quantity=10.0,
        executions=(original, correction),
    )
    corrected_result = replace(
        corrected_result,
        positions=(
            corrected_result.positions[0],
            replace(
                corrected_result.positions[0],
                broker_con_id="999999",
                symbol="MSFT",
                quantity=2.0,
            ),
        ),
    )
    _, committed = commit(
        observations,
        corrected_result,
    )

    executions = rows(
        observations,
        "SELECT exec_id, correction_family, corrects_exec_id FROM portfolio_broker_executions ORDER BY id",
    )
    assert [tuple(row) for row in executions] == [
        ("fill.1", "fill", None),
        ("fill.2", "fill", "fill.1"),
    ]
    assert committed.unmatched_count == 0
    assert rows(observations, "SELECT * FROM portfolio_unmatched_position_changes") == []


def test_first_complete_position_capture_is_only_a_baseline(stores):
    _, observations = stores
    _, committed = commit(
        observations,
        complete_result(finished_at="2026-01-05T15:00:00+00:00", quantity=7.0),
    )

    assert committed.unmatched_count == 0
    assert rows(observations, "SELECT * FROM portfolio_unmatched_position_changes") == []


def test_complete_same_day_executions_explain_position_change(stores):
    _, observations = stores
    commit(
        observations,
        complete_result(finished_at="2026-01-05T15:00:00+00:00", quantity=1.0),
    )
    _, committed = commit(
        observations,
        complete_result(
            finished_at="2026-01-05T16:00:00+00:00",
            quantity=3.0,
            executions=(execution(quantity=2.0),),
        ),
    )

    assert committed.unmatched_count == 0
    assert rows(observations, "SELECT * FROM portfolio_unmatched_position_changes") == []


def test_unmatched_position_window_is_idempotent(stores):
    _, observations = stores
    commit(
        observations,
        complete_result(finished_at="2026-01-05T15:00:00+00:00", quantity=1.0),
    )
    run = observations.create_run(trigger="manual", effective_client_id=61)
    result = complete_result(
        finished_at="2026-01-05T16:00:00+00:00", quantity=4.0
    )
    first = observations.commit_capture(run.id, result)
    second = observations.commit_capture(run.id, result)

    unmatched = rows(observations, "SELECT * FROM portfolio_unmatched_position_changes")
    assert len(unmatched) == 1
    assert unmatched[0]["residual_quantity"] == 3.0
    assert unmatched[0]["execution_coverage"] == "complete"
    assert unmatched[0]["reason_code"] == "unexplained_position_change"
    assert first.unmatched_count == 1
    assert second.unmatched_count == 0
    assert observations.get_run(run.id).unmatched_count == 1


def test_cross_broker_day_window_is_marked_incomplete(stores):
    _, observations = stores
    commit(
        observations,
        complete_result(finished_at="2026-01-05T15:00:00+00:00", quantity=1.0),
    )
    commit(
        observations,
        complete_result(finished_at="2026-01-06T15:00:00+00:00", quantity=4.0),
    )

    row = rows(observations, "SELECT * FROM portfolio_unmatched_position_changes")[0]
    assert row["execution_coverage"] == "gap"
    assert row["reason_code"] == "execution_coverage_gap"


def test_complete_zero_position_set_differs_from_failed_position_leg(
    stores, monkeypatch
):
    _, observations = stores
    clock = {"now": "2026-01-06T04:58:00+00:00"}
    monkeypatch.setattr(
        "src.portfolio_observations._now", lambda: clock["now"]
    )
    zero = replace(
        complete_result(finished_at="2026-01-06T04:59:00+00:00"),
        account_snapshots=(),
        positions=(),
    )
    complete_run = observations.create_run(trigger="manual", effective_client_id=61)
    observations.commit_capture(complete_run.id, zero)
    assert observations.get_run(complete_run.id).finished_at == zero.finished_at_utc
    assert rows(
        observations,
        "SELECT * FROM portfolio_account_snapshots WHERE capture_run_id=?",
        (complete_run.id,),
    ) == []
    assert rows(
        observations,
        "SELECT * FROM portfolio_broker_position_observations WHERE capture_run_id=?",
        (complete_run.id,),
    ) == []

    clock["now"] = "2026-01-06T05:01:00+00:00"
    terminal = observations.finish_run(complete_run.id, state="succeeded")
    assert terminal.finished_at == zero.finished_at_utc
    assert observations.last_successful_finished_at() == datetime.fromisoformat(
        zero.finished_at_utc
    )

    complete_run_id = complete_run.id
    snapshot = observations.position_snapshot_for_run(complete_run_id)
    assert [account.account_id for account in snapshot.accounts] == ["DU123"]
    assert snapshot.positions == []
    assert observations.latest_reviewable_run_id() == complete_run_id

    clock["now"] = "2026-01-06T05:03:00+00:00"
    next_run_id, next_commit = commit(
        observations,
        complete_result(
            finished_at="2026-01-06T05:02:00+00:00",
            quantity=1.0,
        ),
    )
    assert next_commit.unmatched_count == 1
    unmatched = rows(
        observations,
        "SELECT execution_coverage FROM portfolio_unmatched_position_changes "
        "WHERE from_run_id=? AND to_run_id=?",
        (complete_run_id, next_run_id),
    )
    assert [row["execution_coverage"] for row in unmatched] == ["gap"]
    assert observations.last_successful_finished_at() == datetime.fromisoformat(
        "2026-01-06T05:02:00+00:00"
    )

    failed = replace(
        zero,
        finished_at_utc="2026-01-06T05:04:00+00:00",
        account_leg=CaptureLegResult("failed", "account_failed"),
        position_leg=CaptureLegResult("failed", "position_failed"),
    )
    failed_run_id, _ = commit(observations, failed)
    with pytest.raises(ValueError, match="complete broker-position set"):
        observations.position_snapshot_for_run(failed_run_id)
    assert observations.latest_reviewable_run_id() == next_run_id


def test_non_finite_numeric_input_never_persists_as_zero(stores):
    _, observations = stores
    run = observations.create_run(trigger="manual", effective_client_id=61)
    for invalid_client_id in (
        float("nan"),
        float("inf"),
        float("-inf"),
        61.5,
    ):
        with pytest.raises(ValueError, match="effective_client_id must be an integer"):
            observations.create_run(
                trigger="manual", effective_client_id=invalid_client_id
            )
        with pytest.raises(ValueError, match="effective_client_id must be an integer"):
            observations.record_blocked(
                trigger="scheduled",
                effective_client_id=invalid_client_id,
                error_code="provider_unavailable",
            )

    stored_runs = rows(
        observations,
        "SELECT id, effective_client_id FROM portfolio_capture_runs ORDER BY id",
    )
    assert [tuple(row) for row in stored_runs] == [(run.id, 61)]
    invalid_results = (
        (
            complete_result(
                finished_at="2026-01-05T15:00:00+00:00", quantity=float("nan")
            ),
            "quantity must be a finite number",
        ),
        (
            complete_result(
                finished_at="2026-01-05T15:00:00+00:00",
                executions=(replace(execution(), order_id=float("nan")),),
            ),
            "order_id must be an integer",
        ),
        (
            complete_result(
                finished_at="2026-01-05T15:00:00+00:00",
                executions=(execution(),),
                commissions=(
                    CommissionObservation(
                        "DU123", "0001", 1.0, "USD", 2.0,
                        yield_redemption_date=float("inf"),
                    ),
                ),
            ),
            "yield_redemption_date must be an integer",
        ),
    )

    for invalid, message in invalid_results:
        with pytest.raises(ValueError, match=message):
            observations.commit_capture(run.id, invalid)

    assert rows(observations, "SELECT * FROM portfolio_capture_run_accounts") == []
    assert rows(observations, "SELECT * FROM portfolio_broker_position_observations") == []
    assert rows(observations, "SELECT * FROM portfolio_accounts WHERE broker='ibkr'") == []


def test_unknown_account_creates_review_shell_without_raw_id_in_label(stores):
    portfolio, observations = stores
    _, committed = commit(
        observations,
        complete_result(finished_at="2026-01-05T15:00:00+00:00"),
    )

    assert len(committed.new_account_ids) == 1
    account = portfolio.get_account(committed.new_account_ids[0])
    assert account.label.startswith("IBKR · ")
    assert "DU123" not in account.label
    assert account.broker_account_id == "DU123"
    assert account.sync_mode == "ibkr_review"
    for table in (
        "portfolio_capture_run_accounts",
        "portfolio_account_snapshots",
        "portfolio_broker_position_observations",
        "portfolio_broker_executions",
        "portfolio_broker_commission_reports",
        "portfolio_unmatched_position_changes",
    ):
        columns = {row[1] for row in rows(observations, f"PRAGMA table_info({table})")}
        assert "broker_account_id" not in columns


def test_existing_account_user_fields_and_archive_state_are_not_overwritten(stores):
    portfolio, observations = stores
    account = portfolio.upsert_broker_account(
        "ibkr", "DU123", "My retirement", sync_mode="ibkr_auto", base_currency="CAD"
    )
    archived = portfolio.update_account(
        account.id,
        include_in_total=False,
        archived=True,
    )

    _, committed = commit(
        observations,
        complete_result(finished_at="2026-01-05T15:00:00+00:00"),
    )

    current = portfolio.get_account(account.id)
    assert committed.new_account_ids == ()
    assert committed.archived_activity_account_ids == (account.id,)
    assert current.label == "My retirement"
    assert current.sync_mode == "ibkr_auto"
    assert current.base_currency == "CAD"
    assert current.include_in_total is False
    assert current.archived_at == archived.archived_at


def test_observation_rows_block_account_hard_delete(stores):
    _, observations = stores
    _, committed = commit(
        observations,
        complete_result(finished_at="2026-01-05T15:00:00+00:00"),
    )

    with observations._connect() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "DELETE FROM portfolio_accounts WHERE id=?",
            (committed.discovered_account_ids[0],),
        )
