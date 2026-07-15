from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass

import pytest

from src.portfolio_activity import PortfolioActivityStore
from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerAccountRef,
    BrokerCaptureResult,
    CaptureLegResult,
    ExecutionObservation,
    PositionObservation,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioStore


@dataclass(frozen=True)
class ActivityTarget:
    activity_id: str


def execution(
    *,
    exec_id: str,
    account: str = "DU123",
    perm_id: int | None,
    quantity: float = 1.0,
) -> ExecutionObservation:
    return ExecutionObservation(
        broker_account_id=account,
        exec_id=exec_id,
        execution_time_utc="2026-07-15T14:30:00+00:00",
        broker_con_id="265598",
        symbol="AAPL",
        asset_class="stock",
        currency="USD",
        exchange="NASDAQ",
        side="BUY",
        quantity=quantity,
        price=200.0,
        order_id=10,
        perm_id=perm_id,
        client_id=30,
        order_ref="activity-test",
        liquidation=0,
        cumulative_quantity=quantity,
        average_price=200.0,
    )


def capture_result(
    *,
    finished_at: str,
    account: str = "DU123",
    quantity: float = 1.0,
    executions: tuple[ExecutionObservation, ...] = (),
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
            ),
        ),
        positions=(
            PositionObservation(
                broker_account_id=account,
                broker_con_id="265598",
                symbol="AAPL",
                asset_class="stock",
                quantity=quantity,
                avg_cost=200.0,
                currency="USD",
            ),
        ),
        executions=executions,
        commissions=(),
    )


def commit_capture(
    observations: PortfolioObservationStore, result: BrokerCaptureResult
) -> int:
    run = observations.create_run(trigger="manual", effective_client_id=61)
    observations.commit_capture(run.id, result)
    observations.finish_run(run.id, state="succeeded")
    return run.id


@pytest.fixture
def stores(tmp_path):
    path = tmp_path / "profile_state.db"
    return PortfolioStore(path), PortfolioObservationStore(path), PortfolioActivityStore(path)


def rows(store: PortfolioActivityStore, sql: str, params=()):
    with store._connect() as conn:
        return conn.execute(sql, params).fetchall()


@pytest.fixture
def targets(stores) -> dict[str, ActivityTarget]:
    portfolio, observations, activity = stores
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:35:00+00:00",
            executions=(
                execution(exec_id="order-fill", perm_id=70001),
                execution(exec_id="ungrouped", perm_id=None),
            ),
        ),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:40:00+00:00",
            executions=(execution(exec_id="ungrouped.01", perm_id=None),),
        ),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:45:00+00:00",
            quantity=3.0,
        ),
    )
    manual = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(account_id=manual.id, symbol="NVDA", quantity=2)

    account_id = int(
        rows(
            activity,
            "SELECT id FROM portfolio_accounts WHERE broker='ibkr'",
        )[0]["id"]
    )
    execution_rows = rows(
        activity,
        "SELECT id, exec_id FROM portfolio_broker_executions ORDER BY id",
    )
    execution_ids = {row["exec_id"]: int(row["id"]) for row in execution_rows}
    unmatched_id = int(
        rows(
            activity,
            "SELECT id FROM portfolio_unmatched_position_changes ORDER BY id",
        )[0]["id"]
    )
    manual_id = int(
        rows(activity, "SELECT id FROM portfolio_manual_adjustments ORDER BY id")[0]["id"]
    )
    return {
        "order": ActivityTarget(f"order:{account_id}:70001"),
        "execution": ActivityTarget(
            f"execution:{account_id}:{execution_ids['ungrouped']}"
        ),
        "unmatched": ActivityTarget(f"unmatched:{unmatched_id}"),
        "manual_adjustment": ActivityTarget(f"manual:{manual_id}"),
    }


def test_activity_schema_has_non_cascading_annotation_fk_and_constraints(stores):
    portfolio, _, activity = stores
    account = portfolio.ensure_manual_account()
    tables = {
        row["name"]
        for row in rows(activity, "SELECT name FROM sqlite_master WHERE type='table'")
    }
    foreign_keys = rows(activity, "PRAGMA foreign_key_list(portfolio_activity_annotations)")
    indexes = rows(activity, "PRAGMA index_list(portfolio_activity_annotations)")
    unique_target_index_exists = any(
        index["unique"]
        and [
            column["name"]
            for column in rows(
                activity,
                f"PRAGMA index_info({index['name']})",
            )
        ]
        == ["target_kind", "portfolio_account_id", "target_ref"]
        for index in indexes
    )

    assert "portfolio_activity_annotations" in tables
    assert all(row["on_delete"].upper() != "CASCADE" for row in foreign_keys)
    assert unique_target_index_exists
    with activity._connect() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO portfolio_activity_annotations(
                target_kind, portfolio_account_id, target_ref, intent_label,
                note, created_at_utc, updated_at_utc
            ) VALUES ('manual_adjustment', ?, '1', 'invalid', '', 'now', 'now')
            """,
            (account.id,),
        )


@pytest.mark.parametrize("target_name", ["order", "execution", "unmatched", "manual_adjustment"])
def test_annotation_round_trips_each_supported_target(targets, stores, target_name):
    _, _, activity = stores
    target = targets[target_name]

    saved = activity.put_annotation(
        target.activity_id,
        intent_label="profit_take",
        note="trimmed exposure",
    )

    assert saved.intent_label == "profit_take"
    assert saved.note == "trimmed exposure"
    assert "DU123" not in json.dumps(asdict(saved), sort_keys=True)


def test_annotation_replacement_is_user_owned_and_does_not_mutate_facts(targets, stores):
    _, _, activity = stores
    target = targets["order"]
    before_execution = rows(
        activity,
        "SELECT exec_id, quantity, price, perm_id FROM portfolio_broker_executions",
    )

    first = activity.put_annotation(
        target.activity_id,
        intent_label="profit_take",
        note=" first note ",
    )
    replacement = activity.put_annotation(
        target.activity_id,
        intent_label="rebalance",
        note=" second note ",
    )

    assert first.note == "first note"
    assert replacement.intent_label == "rebalance"
    assert replacement.note == "second note"
    assert rows(
        activity,
        "SELECT exec_id, quantity, price, perm_id FROM portfolio_broker_executions",
    ) == before_execution
    assert len(rows(activity, "SELECT * FROM portfolio_activity_annotations")) == 1


def test_annotation_rejects_unknown_target_invalid_intent_and_empty_payload(targets, stores):
    _, _, activity = stores
    order = targets["order"]
    account_id = order.activity_id.split(":")[1]
    grouped_execution_id = int(
        rows(
            activity,
            "SELECT id FROM portfolio_broker_executions WHERE perm_id=70001",
        )[0]["id"]
    )
    corrected_execution_id = int(
        rows(
            activity,
            "SELECT id FROM portfolio_broker_executions WHERE exec_id='ungrouped.01'",
        )[0]["id"]
    )

    for target_id in (
        "gap:1:0:2",
        "history:1:2",
        "order:1:0",
        "order:1:+1",
        "order:1:1.0",
        "order:1:1:extra",
        "execution:1:0",
        "unmatched:0",
        "manual:-1",
        "manual:999999",
        f"order:{account_id}:999999",
        f"execution:{account_id}:{grouped_execution_id}",
        f"execution:{account_id}:{corrected_execution_id}",
    ):
        with pytest.raises(ValueError):
            activity.put_annotation(target_id, intent_label="other", note="note")
    with pytest.raises(ValueError, match="intent_label"):
        activity.put_annotation(order.activity_id, intent_label="made_up", note="note")
    with pytest.raises(ValueError, match="intent_label or note"):
        activity.put_annotation(order.activity_id, intent_label=None, note="  ")


def test_annotation_delete_is_idempotent_and_leaves_target_history(targets, stores):
    _, _, activity = stores
    target = targets["manual_adjustment"]
    before_history = rows(
        activity,
        "SELECT id, account_id, position_id, action FROM portfolio_manual_adjustments",
    )
    activity.put_annotation(target.activity_id, intent_label=None, note="manual adjustment")

    assert activity.delete_annotation(target.activity_id) is True
    assert activity.delete_annotation(target.activity_id) is False
    assert rows(
        activity,
        "SELECT id, account_id, position_id, action FROM portfolio_manual_adjustments",
    ) == before_history
    assert rows(activity, "SELECT * FROM portfolio_activity_annotations") == []
