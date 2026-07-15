from __future__ import annotations

import base64
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import pytest

from src.portfolio_activity import ActivityFilters, PortfolioActivityStore
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


@dataclass(frozen=True)
class ActivityTarget:
    activity_id: str


def execution(
    *,
    exec_id: str,
    account: str = "DU123",
    perm_id: int | None,
    order_id: int,
    con_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    execution_time: str,
    currency: str = "USD",
) -> ExecutionObservation:
    return ExecutionObservation(
        broker_account_id=account,
        exec_id=exec_id,
        execution_time_utc=execution_time,
        broker_con_id=con_id,
        symbol=symbol,
        asset_class="stock",
        currency=currency,
        exchange="NASDAQ",
        side=side,
        quantity=quantity,
        price=price,
        order_id=order_id,
        perm_id=perm_id,
        client_id=30,
        order_ref="activity-test",
        liquidation=0,
        cumulative_quantity=quantity,
        average_price=price,
    )


def position(
    *,
    account: str = "DU123",
    con_id: str,
    symbol: str,
    quantity: float,
    currency: str = "USD",
) -> PositionObservation:
    return PositionObservation(
        broker_account_id=account,
        broker_con_id=con_id,
        symbol=symbol,
        asset_class="stock",
        quantity=quantity,
        avg_cost=200.0,
        currency=currency,
    )


def capture_result(
    *,
    finished_at: str,
    account: str = "DU123",
    quantity: float = 1.0,
    executions: tuple[ExecutionObservation, ...] = (),
    commissions: tuple[CommissionObservation, ...] = (),
    positions: tuple[PositionObservation, ...] | None = None,
    execution_leg: str = "complete",
) -> BrokerCaptureResult:
    if positions is None:
        positions = (
            position(
                account=account,
                con_id="265598",
                symbol="AAPL",
                quantity=quantity,
            ),
        )
    return BrokerCaptureResult(
        finished_at_utc=finished_at,
        discovered_accounts=(BrokerAccountRef(account, "USD"),),
        account_leg=CaptureLegResult("complete"),
        execution_leg=CaptureLegResult(execution_leg),
        position_leg=CaptureLegResult("complete"),
        account_snapshots=(
            AccountSnapshotObservation(
                broker_account_id=account,
                as_of_utc=finished_at,
                base_currency="USD",
                net_liquidation=100_000.0,
            ),
        ),
        positions=positions,
        executions=executions,
        commissions=commissions,
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
    portfolio = PortfolioStore(path)
    portfolio.ensure_manual_account()
    return portfolio, PortfolioObservationStore(path), PortfolioActivityStore(path)


def rows(store: PortfolioActivityStore, sql: str, params=()):
    with store._connect() as conn:
        return conn.execute(sql, params).fetchall()


def broker_account_id(activity: PortfolioActivityStore, raw_id: str = "DU123") -> int:
    return int(
        rows(
            activity,
            "SELECT id FROM portfolio_accounts WHERE broker_account_id=?",
            (raw_id,),
        )[0]["id"]
    )


@pytest.fixture
def targets(stores) -> dict[str, ActivityTarget]:
    portfolio, observations, activity = stores
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:35:00+00:00",
            executions=(
                execution(
                    exec_id="order-fill", perm_id=70001, order_id=10,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=1.0,
                    price=200.0, execution_time="2026-07-15T14:30:00+00:00",
                ),
                execution(
                    exec_id="ungrouped", perm_id=None, order_id=11,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=1.0,
                    price=200.0, execution_time="2026-07-15T14:31:00+00:00",
                ),
            ),
        ),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:40:00+00:00",
            executions=(
                execution(
                    exec_id="ungrouped.01", perm_id=None, order_id=11,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=1.0,
                    price=200.0, execution_time="2026-07-15T14:31:00+00:00",
                ),
            ),
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


def test_same_account_perm_id_groups_effective_fills_but_never_crosses_accounts(stores):
    _, observations, activity = stores
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:35:00+00:00",
            executions=(
                execution(
                    exec_id="same-order-a", perm_id=70001, order_id=10,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=1.0,
                    price=200.0, execution_time="2026-07-15T14:30:00+00:00",
                ),
                execution(
                    exec_id="same-order-b", perm_id=70001, order_id=10,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=2.0,
                    price=201.0, execution_time="2026-07-15T14:31:00+00:00",
                ),
            ),
        ),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:36:00+00:00",
            account="DU456",
            executions=(
                execution(
                    exec_id="other-account", account="DU456", perm_id=70001,
                    order_id=10, con_id="265598", symbol="AAPL", side="BUY",
                    quantity=4.0, price=202.0,
                    execution_time="2026-07-15T14:32:00+00:00",
                ),
            ),
        ),
    )

    account_id = broker_account_id(activity)
    page = activity.list_activity(ActivityFilters(account_id=account_id))

    assert account_id == 2
    assert [item.id for item in page.items if item.kind == "order"] == [
        "order:2:70001"
    ]
    order = next(item for item in page.items if item.kind == "order")
    assert len(order.fills) == 2
    other_page = activity.list_activity(
        ActivityFilters(account_id=broker_account_id(activity, "DU456"))
    )
    other_order = next(item for item in other_page.items if item.kind == "order")
    assert len(other_order.fills) == 1


def test_missing_perm_id_keeps_same_order_id_as_independent_execution_rows(stores):
    _, observations, activity = stores
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:35:00+00:00",
            executions=(
                execution(
                    exec_id="no-perm", perm_id=None, order_id=77,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=1.0,
                    price=200.0, execution_time="2026-07-15T14:30:00+00:00",
                ),
                execution(
                    exec_id="zero-perm", perm_id=0, order_id=77,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=2.0,
                    price=201.0, execution_time="2026-07-15T14:31:00+00:00",
                ),
            ),
        ),
    )
    account_id = broker_account_id(activity)
    execution_rows = rows(
        activity,
        "SELECT id, exec_id FROM portfolio_broker_executions ORDER BY id",
    )
    roots = {row["exec_id"]: int(row["id"]) for row in execution_rows}

    page = activity.list_activity(ActivityFilters(account_id=account_id))

    assert {item.id for item in page.items if item.kind == "execution"} == {
        f"execution:{account_id}:{roots['no-perm']}",
        f"execution:{account_id}:{roots['zero-perm']}",
    }
    executions = [item for item in page.items if item.kind == "execution"]
    assert all(len(item.fills) == 1 for item in executions)


def test_correction_selects_latest_effective_revision_and_preserves_lineage(stores):
    _, observations, activity = stores
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:35:00+00:00",
            executions=(
                execution(
                    exec_id="0001", perm_id=70001, order_id=10,
                    con_id="265598", symbol="AAPL", side="BUY", quantity=5.0,
                    price=200.0, execution_time="2026-07-15T14:30:00+00:00",
                ),
            ),
        ),
    )
    corrected_quantity = 2.0
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:40:00+00:00",
            executions=(
                execution(
                    exec_id="0001.01", perm_id=70001, order_id=10,
                    con_id="265598", symbol="AAPL", side="BUY",
                    quantity=corrected_quantity, price=201.0,
                    execution_time="2026-07-15T14:30:00+00:00",
                ),
            ),
        ),
    )

    page = activity.list_activity(
        ActivityFilters(account_id=broker_account_id(activity))
    )
    order = next(item for item in page.items if item.kind == "order")
    fill = order.fills[0]

    assert [revision.exec_id for revision in fill.revisions] == ["0001", "0001.01"]
    assert [revision.is_effective for revision in fill.revisions] == [False, True]
    assert order.objective.quantity == corrected_quantity
    assert order.objective.gross_notional == corrected_quantity * 201.0


def test_late_commission_revisions_join_exact_execution_without_mutating_it(stores):
    _, observations, activity = stores
    fill = execution(
        exec_id="commission-fill", perm_id=70001, order_id=10,
        con_id="265598", symbol="AAPL", side="SELL", quantity=2.0,
        price=210.0, execution_time="2026-07-15T14:30:00+00:00",
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:35:00+00:00",
            executions=(fill,),
            commissions=(
                CommissionObservation("DU123", "commission-fill", 1.0, "USD", 8.0),
            ),
        ),
    )
    before = rows(activity, "SELECT * FROM portfolio_broker_executions")
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:45:00+00:00",
            commissions=(
                CommissionObservation("DU123", "commission-fill", 1.5, "USD", 9.0),
            ),
        ),
    )

    order = next(
        item
        for item in activity.list_activity(ActivityFilters()).items
        if item.kind == "order"
    )
    revisions = order.fills[0].revisions[0].commission_revisions

    assert rows(activity, "SELECT * FROM portfolio_broker_executions") == before
    assert [revision.commission for revision in revisions] == [1.0, 1.5]
    assert [revision.is_latest for revision in revisions] == [False, True]
    assert order.objective.commission == 1.5
    assert order.objective.realized_pnl == 9.0


def test_group_totals_require_every_effective_provider_leg_and_one_currency(stores):
    _, observations, activity = stores
    fills = (
        execution(exec_id="flat-a", perm_id=70001, order_id=1, con_id="1", symbol="AAPL", side="SELL", quantity=1.0, price=10.0, execution_time="2026-07-15T14:30:00+00:00"),
        execution(exec_id="flat-b", perm_id=70001, order_id=1, con_id="1", symbol="AAPL", side="SELL", quantity=1.0, price=10.0, execution_time="2026-07-15T14:31:00+00:00"),
        execution(exec_id="missing-a", perm_id=70002, order_id=2, con_id="2", symbol="MSFT", side="SELL", quantity=1.0, price=20.0, execution_time="2026-07-15T14:32:00+00:00"),
        execution(exec_id="missing-b", perm_id=70002, order_id=2, con_id="2", symbol="MSFT", side="SELL", quantity=1.0, price=20.0, execution_time="2026-07-15T14:33:00+00:00"),
        execution(exec_id="mixed-a", perm_id=70003, order_id=3, con_id="3", symbol="NVDA", side="SELL", quantity=1.0, price=30.0, execution_time="2026-07-15T14:34:00+00:00"),
        execution(exec_id="mixed-b", perm_id=70003, order_id=3, con_id="3", symbol="NVDA", side="SELL", quantity=1.0, price=30.0, execution_time="2026-07-15T14:35:00+00:00"),
        execution(exec_id="conflict-a", perm_id=70004, order_id=4, con_id="4", symbol="AAPL", side="SELL", quantity=1.0, price=40.0, execution_time="2026-07-15T14:36:00+00:00", currency="USD"),
        execution(exec_id="conflict-b", perm_id=70004, order_id=4, con_id="5", symbol="TSLA", side="SELL", quantity=1.0, price=40.0, execution_time="2026-07-15T14:37:00+00:00", currency="CAD"),
    )
    commissions = (
        CommissionObservation("DU123", "flat-a", 0.0, "USD", 0.0),
        CommissionObservation("DU123", "flat-b", 0.0, "USD", 0.0),
        CommissionObservation("DU123", "missing-a", 1.0, "USD", 2.0),
        CommissionObservation("DU123", "missing-b", None, "USD", None),
        CommissionObservation("DU123", "mixed-a", 1.0, "USD", 2.0),
        CommissionObservation("DU123", "mixed-b", 1.0, "CAD", 2.0),
        CommissionObservation("DU123", "conflict-a", 1.0, "USD", 2.0),
        CommissionObservation("DU123", "conflict-b", 1.0, "CAD", 2.0),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:40:00+00:00",
            executions=fills,
            commissions=commissions,
        ),
    )

    page = activity.list_activity(ActivityFilters())
    orders = {item.id.rsplit(":", 1)[1]: item for item in page.items}
    flat = orders["70001"]
    missing = orders["70002"]
    mixed = orders["70003"]
    conflict = orders["70004"]

    assert (flat.objective.commission, flat.objective.realized_pnl) == (0.0, 0.0)
    assert flat.state == "realized_flat"
    assert missing.objective.commission is None
    assert missing.objective.realized_pnl is None
    assert missing.state == "outcome_unknown"
    assert mixed.objective.commission is None
    assert mixed.objective.commission_currency is None
    assert conflict.symbol is None
    assert conflict.currency is None
    assert conflict.objective.commission is None
    assert conflict.objective.realized_pnl is None
    assert len(conflict.fills) == 2
    assert [item.id for item in activity.list_activity(ActivityFilters(state="realized_flat")).items] == [flat.id]
    unknown_ids = {
        item.id for item in activity.list_activity(ActivityFilters(state="outcome_unknown")).items
    }
    assert {missing.id, mixed.id, conflict.id} <= unknown_ids


def test_group_arithmetic_returns_null_on_float_overflow_instead_of_zero(stores):
    _, observations, activity = stores
    maximum = 1.7976931348623157e308
    fills = tuple(
        execution(
            exec_id=f"overflow-{suffix}", perm_id=70001, order_id=1,
            con_id="1", symbol="AAPL", side="SELL", quantity=1.0,
            price=maximum, execution_time=f"2026-07-15T14:3{suffix}:00+00:00",
        )
        for suffix in (0, 1)
    )
    commissions = tuple(
        CommissionObservation("DU123", fill.exec_id, maximum, "USD", maximum)
        for fill in fills
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:40:00+00:00",
            executions=fills,
            commissions=commissions,
        ),
    )

    order = activity.list_activity(ActivityFilters(state="outcome_unknown")).items[0]

    assert order.objective.average_price is None
    assert order.objective.gross_notional is None
    assert order.objective.commission is None
    assert order.objective.realized_pnl is None
    assert order.state == "outcome_unknown"
    assert activity.list_activity(ActivityFilters(state="realized_gain")).items == []


def test_complete_unambiguous_position_windows_classify_direction_and_close_scope(stores):
    _, observations, activity = stores
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:00:00+00:00",
            positions=(
                position(con_id="1", symbol="AAPL", quantity=10.0),
                position(con_id="2", symbol="MSFT", quantity=5.0),
            ),
        ),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T15:00:00+00:00",
            positions=(
                position(con_id="1", symbol="AAPL", quantity=5.0),
                position(con_id="3", symbol="NVDA", quantity=3.0),
            ),
            executions=(
                execution(exec_id="partial-close", perm_id=70001, order_id=1, con_id="1", symbol="AAPL", side="SELL", quantity=5.0, price=210.0, execution_time="2026-07-15T14:30:00+00:00"),
                execution(exec_id="complete-close", perm_id=70002, order_id=2, con_id="2", symbol="MSFT", side="SELL", quantity=5.0, price=310.0, execution_time="2026-07-15T14:31:00+00:00"),
                execution(exec_id="increase", perm_id=70003, order_id=3, con_id="3", symbol="NVDA", side="BUY", quantity=3.0, price=410.0, execution_time="2026-07-15T14:32:00+00:00"),
            ),
        ),
    )

    orders = {
        item.id.rsplit(":", 1)[1]: item.objective
        for item in activity.list_activity(ActivityFilters()).items
        if item.kind in {"order", "execution"}
    }

    assert (orders["70001"].position_direction, orders["70001"].close_scope, orders["70001"].position_context) == ("reduce", "partial", "complete")
    assert (orders["70002"].position_direction, orders["70002"].close_scope, orders["70002"].position_context) == ("reduce", "complete", "complete")
    assert (orders["70003"].position_direction, orders["70003"].close_scope, orders["70003"].position_context) == ("increase", "none", "complete")


def test_incomplete_ambiguous_or_sign_flip_context_keeps_position_effect_unknown(stores):
    _, observations, activity = stores
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T14:00:00+00:00",
            positions=(position(con_id="1", symbol="AAPL", quantity=5.0),),
        ),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T15:00:00+00:00",
            positions=(),
            execution_leg="partial",
            executions=(execution(exec_id="incomplete", perm_id=70001, order_id=1, con_id="1", symbol="AAPL", side="SELL", quantity=5.0, price=10.0, execution_time="2026-07-15T14:30:00+00:00"),),
        ),
    )
    commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T14:00:00+00:00", account="DU456", positions=(position(account="DU456", con_id="2", symbol="MSFT", quantity=10.0),)),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T15:00:00+00:00", account="DU456",
            positions=(position(account="DU456", con_id="2", symbol="MSFT", quantity=8.0),),
            executions=(
                execution(exec_id="ambiguous-a", account="DU456", perm_id=70002, order_id=2, con_id="2", symbol="MSFT", side="SELL", quantity=1.0, price=20.0, execution_time="2026-07-15T14:31:00+00:00"),
                execution(exec_id="ambiguous-b", account="DU456", perm_id=70003, order_id=3, con_id="2", symbol="MSFT", side="SELL", quantity=1.0, price=20.0, execution_time="2026-07-15T14:32:00+00:00"),
            ),
        ),
    )
    commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T14:00:00+00:00", account="DU789", positions=(position(account="DU789", con_id="3", symbol="NVDA", quantity=2.0),)),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T15:00:00+00:00", account="DU789",
            positions=(position(account="DU789", con_id="3", symbol="NVDA", quantity=-1.0),),
            executions=(execution(exec_id="sign-flip", account="DU789", perm_id=70004, order_id=4, con_id="3", symbol="NVDA", side="SELL", quantity=3.0, price=30.0, execution_time="2026-07-15T14:33:00+00:00"),),
        ),
    )

    objectives = [
        item.objective
        for item in activity.list_activity(ActivityFilters()).items
        if item.kind in {"order", "execution"}
    ]

    assert len(objectives) == 4
    assert all(objective.position_direction == "unknown" for objective in objectives)
    assert all(objective.close_scope == "unknown" for objective in objectives)
    assert all(objective.position_context == "unknown" for objective in objectives)


def test_manual_adjustment_projection_replays_historical_symbol_and_field_changes(
    stores, monkeypatch
):
    portfolio, _, activity = stores
    clock = {"now": "2026-07-13T14:00:00+00:00"}
    monkeypatch.setattr("src.portfolio_state._now", lambda: clock["now"])
    account = portfolio.ensure_manual_account()
    manual_position = portfolio.upsert_manual_position(
        account_id=account.id,
        symbol="AAPL",
        quantity=2.0,
        avg_cost=190.0,
    )
    clock["now"] = "2026-07-14T14:00:00+00:00"
    portfolio.update_position(manual_position.id, fields={"symbol": "HAPN"})
    clock["now"] = "2026-07-15T14:00:00+00:00"
    portfolio.update_position(manual_position.id, fields={"quantity": 3.0})

    items = activity.list_activity(ActivityFilters(source="manual")).items

    assert [item.symbol for item in items] == ["HAPN", "HAPN", "AAPL"]
    assert [(change.field, change.before, change.after) for change in items[0].changes] == [
        ("quantity", 2.0, 3.0)
    ]
    assert [(change.field, change.before, change.after) for change in items[1].changes] == [
        ("symbol", "AAPL", "HAPN")
    ]
    assert [item.id for item in activity.list_activity(ActivityFilters(symbol=" aapl ")).items] == [
        items[2].id
    ]
    assert [item.id for item in activity.list_activity(ActivityFilters(symbol="hapn")).items] == [
        items[0].id,
        items[1].id,
    ]


def test_manual_adjustment_never_claims_execution_price_commission_or_realized_pnl(
    stores
):
    portfolio, _, activity = stores
    account = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(
        account_id=account.id,
        symbol="NVDA",
        quantity=2.0,
        avg_cost=125.0,
    )

    item = activity.list_activity(ActivityFilters(source="manual")).items[0]
    activity.put_annotation(item.id, intent_label="rebalance", note="manual trim")
    item = activity.list_activity(ActivityFilters(source="manual")).items[0]

    assert item.kind == "manual_adjustment"
    assert item.source == "manual"
    assert item.state == "manual_adjustment"
    assert item.annotation.intent_label == "rebalance"
    assert not hasattr(item, "objective")
    assert not hasattr(item, "fills")
    assert not hasattr(item, "price")
    assert not hasattr(item, "commission")
    assert not hasattr(item, "realized_pnl")


def test_unmatched_projection_exposes_before_after_expected_residual_window_and_coverage(
    stores
):
    _, observations, activity = stores
    from_run_id = commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T14:00:00+00:00", quantity=1.0),
    )
    to_run_id = commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T15:00:00+00:00", quantity=4.0),
    )

    page = activity.list_activity(ActivityFilters(state="unmatched"))
    item = page.items[0]

    assert item.kind == "unmatched"
    assert item.id.startswith("unmatched:")
    assert item.source == "broker"
    assert item.state == "unmatched"
    assert (item.from_run_id, item.to_run_id) == (from_run_id, to_run_id)
    assert (item.from_as_of_utc, item.to_as_of_utc) == (
        "2026-07-15T14:00:00+00:00",
        "2026-07-15T15:00:00+00:00",
    )
    assert (
        item.before_quantity,
        item.after_quantity,
        item.expected_quantity,
        item.residual_quantity,
    ) == (1.0, 4.0, 1.0, 3.0)
    assert item.execution_coverage == "complete"
    assert item.reason_code == "unexplained_position_change"
    assert page.summary.unmatched_count == 1


def test_first_successful_complete_capture_creates_history_start_not_a_fake_trade(stores):
    _, observations, activity = stores
    succeeded_run_id = commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T14:00:00+00:00", account="DU123"),
    )
    partial_run = observations.create_run(trigger="manual", effective_client_id=61)
    observations.commit_capture(
        partial_run.id,
        capture_result(finished_at="2026-07-15T14:05:00+00:00", account="DU456"),
    )
    observations.finish_run(partial_run.id, state="partial")

    page = activity.list_activity(ActivityFilters())
    history = [item for item in page.items if item.kind == "history_start"]

    assert {item.capture_run_id for item in history} == {
        succeeded_run_id,
        partial_run.id,
    }
    assert all(item.source == "system" and item.state == "history_start" for item in history)
    assert not [item for item in page.items if item.kind in {"order", "execution"}]
    assert page.history_started_at_utc == "2026-07-15T14:00:00+00:00"


def test_failed_or_incomplete_execution_leg_creates_explicit_gap_marker(stores):
    _, observations, activity = stores
    from_run_id = commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T14:00:00+00:00"),
    )
    running = observations.create_run(trigger="manual", effective_client_id=61)
    observations.commit_capture(
        running.id,
        capture_result(
            finished_at="2026-07-15T14:30:00+00:00",
            execution_leg="partial",
        ),
    )
    terminal = observations.create_run(trigger="manual", effective_client_id=61)
    observations.commit_capture(
        terminal.id,
        capture_result(
            finished_at="2026-07-15T15:00:00+00:00",
            execution_leg="partial",
        ),
    )
    observations.finish_run(terminal.id, state="partial")
    global_failed = observations.create_run(trigger="manual", effective_client_id=61)
    observations.finish_run(global_failed.id, state="failed")
    account_id = broker_account_id(activity)

    page = activity.list_activity(ActivityFilters(account_id=account_id))
    markers = [item for item in page.items if item.kind == "coverage_gap"]

    assert {marker.to_run_id for marker in markers} == {terminal.id, global_failed.id}
    assert {marker.id for marker in markers} == {
        f"gap:{account_id}:{from_run_id}:{terminal.id}",
        f"gap:global:0:{global_failed.id}",
    }
    assert running.id not in {marker.to_run_id for marker in markers}
    assert all(marker.reason_code == "execution_leg_incomplete" for marker in markers)
    assert any(marker.account is None for marker in markers)
    assert rows(
        activity,
        "SELECT name FROM sqlite_master WHERE name='portfolio_activity_events'",
    ) == []


def test_cross_et_day_complete_runs_create_gap_without_rewriting_empty_activity(stores):
    _, observations, activity = stores
    first_run_id = commit_capture(
        observations,
        capture_result(finished_at="2026-07-14T20:00:00+00:00"),
    )
    second_run_id = commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T14:00:00+00:00"),
    )

    page = activity.list_activity(ActivityFilters(state="coverage_gap"))
    marker = page.items[0]

    assert marker.kind == "coverage_gap"
    assert marker.id == f"gap:{marker.account.id}:{first_run_id}:{second_run_id}"
    assert marker.reason_code == "broker_day_gap"
    assert (marker.from_run_id, marker.to_run_id) == (first_run_id, second_run_id)
    assert (marker.from_as_of_utc, marker.to_as_of_utc) == (
        "2026-07-14T20:00:00+00:00",
        "2026-07-15T14:00:00+00:00",
    )
    assert rows(activity, "SELECT * FROM portfolio_broker_executions") == []
    assert rows(
        activity,
        "SELECT name FROM sqlite_master WHERE name='portfolio_activity_events'",
    ) == []


def test_activity_filters_date_account_symbol_source_and_state_independently(
    stores, monkeypatch
):
    portfolio, observations, activity = stores
    monkeypatch.setattr(
        "src.portfolio_state._now", lambda: "2026-07-14T14:00:00+00:00"
    )
    manual = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(
        account_id=manual.id,
        symbol="HAPN",
        quantity=2.0,
    )
    commit_capture(
        observations,
        capture_result(finished_at="2026-07-15T14:00:00+00:00", quantity=1.0),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T15:00:00+00:00",
            quantity=3.0,
            executions=(
                execution(
                    exec_id="filter-fill",
                    perm_id=90001,
                    order_id=1,
                    con_id="265598",
                    symbol="AAPL",
                    side="BUY",
                    quantity=1.0,
                    price=200.0,
                    execution_time="2026-07-15T14:30:00+00:00",
                ),
            ),
            commissions=(
                CommissionObservation("DU123", "filter-fill", 1.0, "USD", 5.0),
            ),
        ),
    )
    account_id = broker_account_id(activity)
    portfolio.update_account(account_id, archived=True)
    all_items = activity.list_activity(ActivityFilters()).items
    order = next(item for item in all_items if item.kind == "order")
    manual_item = next(item for item in all_items if item.kind == "manual_adjustment")
    unmatched = next(item for item in all_items if item.kind == "unmatched")

    cases = [
        (ActivityFilters(date_from_et="2026-07-15", date_to_et="2026-07-15"), order.id, manual_item.id),
        (ActivityFilters(account_id=account_id), order.id, manual_item.id),
        (ActivityFilters(symbol=" aapl "), order.id, manual_item.id),
        (ActivityFilters(source="manual"), manual_item.id, order.id),
        (ActivityFilters(state="realized_gain"), order.id, unmatched.id),
    ]
    for filters, included_id, excluded_id in cases:
        ids = {item.id for item in activity.list_activity(filters).items}
        assert included_id in ids
        assert excluded_id not in ids

    archived_order = next(
        item
        for item in activity.list_activity(ActivityFilters(account_id=account_id)).items
        if item.id == order.id
    )
    assert archived_order.account.archived is True
    assert "DU123" not in json.dumps(asdict(archived_order), sort_keys=True)


def test_activity_cursor_is_deterministic_and_recent_scope_uses_seven_et_dates(stores):
    _, observations, activity = stores
    fills = (
        execution(
            exec_id="old",
            perm_id=80000,
            order_id=0,
            con_id="1",
            symbol="OLD",
            side="BUY",
            quantity=1.0,
            price=1.0,
            execution_time="2026-07-08T15:00:00+00:00",
        ),
        execution(
            exec_id="boundary",
            perm_id=80001,
            order_id=1,
            con_id="2",
            symbol="BOUNDARY",
            side="BUY",
            quantity=1.0,
            price=1.0,
            execution_time="2026-07-09T15:00:00+00:00",
        ),
        *tuple(
            execution(
                exec_id=f"same-{index}",
                perm_id=80001 + index,
                order_id=1 + index,
                con_id=str(2 + index),
                symbol=f"SAME{index}",
                side="BUY",
                quantity=1.0,
                price=1.0,
                execution_time="2026-07-15T14:30:00+00:00",
            )
            for index in range(1, 4)
        ),
    )
    commit_capture(
        observations,
        capture_result(
            finished_at="2026-07-15T15:00:00+00:00",
            executions=fills,
        ),
    )
    now = datetime(2026, 7, 15, 16, 0, tzinfo=timezone.utc)

    first = activity.list_activity(
        ActivityFilters(
            source="broker",
            state="outcome_unknown",
            recent=True,
            limit=2,
        ),
        now_utc=now,
    )
    second = activity.list_activity(
        ActivityFilters(
            source="broker",
            state="outcome_unknown",
            recent=True,
            limit=2,
            cursor=first.next_cursor,
        ),
        now_utc=now,
    )
    recent_all = activity.list_activity(
        ActivityFilters(
            source="broker",
            state="outcome_unknown",
            recent=True,
            limit=200,
        ),
        now_utc=now,
    )

    paged_ids = [item.id for item in first.items + second.items]
    assert paged_ids == [item.id for item in recent_all.items]
    assert len(paged_ids) == len(set(paged_ids)) == 4
    assert first.next_cursor is not None
    assert second.next_cursor is None
    assert recent_all.summary.recent_window_days == 7
    assert not any(item.symbol == "OLD" for item in recent_all.items)
    assert any(item.symbol == "BOUNDARY" for item in recent_all.items)

    noncanonical_cursor = base64.urlsafe_b64encode(
        json.dumps(
            {
                "activity_id": first.items[-1].id,
                "occurred_at_utc": "2026-07-15T10:30:00-04:00",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii").rstrip("=")

    for invalid in (
        ActivityFilters(source="BROKER"),
        ActivityFilters(state="gain"),
        ActivityFilters(date_from_et=""),
        ActivityFilters(date_from_et="07-15-2026"),
        ActivityFilters(date_from_et="2026-07-16", date_to_et="2026-07-15"),
        ActivityFilters(date_from_et="2026-07-15", recent=True),
        ActivityFilters(limit=0),
        ActivityFilters(limit=201),
        ActivityFilters(cursor="not-a-cursor"),
        ActivityFilters(cursor=noncanonical_cursor),
    ):
        with pytest.raises(ValueError):
            activity.list_activity(invalid, now_utc=now)
