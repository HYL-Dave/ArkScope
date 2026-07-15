from __future__ import annotations

from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerAccountRef,
    BrokerCaptureResult,
    CaptureLegResult,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_overview import build_portfolio_overview, safe_portfolio_account_label
from src.portfolio_state import BrokerPosition, PortfolioStore


def captured_account(
    *,
    account: str = "DU123",
    as_of: str = "2026-07-14T05:00:00+00:00",
    realized: float | None = 125,
    unrealized: float | None = -25,
) -> BrokerCaptureResult:
    return BrokerCaptureResult(
        finished_at_utc=as_of,
        discovered_accounts=(BrokerAccountRef(account, "USD"),),
        account_leg=CaptureLegResult("complete"),
        execution_leg=CaptureLegResult("complete"),
        position_leg=CaptureLegResult("complete"),
        account_snapshots=(
            AccountSnapshotObservation(
                broker_account_id=account,
                as_of_utc=as_of,
                base_currency="USD",
                net_liquidation=100_000,
                total_cash_value=10_000,
                settled_cash=9_000,
                gross_position_value=90_000,
                buying_power=25_000,
                available_funds=20_000,
                initial_margin_requirement=15_000,
                maintenance_margin_requirement=12_000,
                daily_realized_pnl=realized,
                daily_unrealized_pnl=unrealized,
            ),
        ),
        positions=(),
        executions=(),
        commissions=(),
    )


def commit_snapshot(
    observations: PortfolioObservationStore, result: BrokerCaptureResult
) -> int:
    run = observations.create_run(trigger="manual", effective_client_id=71)
    observations.commit_capture(run.id, result)
    observations.finish_run(run.id, state="succeeded")
    return run.id


def stores(tmp_path):
    path = tmp_path / "profile_state.db"
    return PortfolioStore(path), PortfolioObservationStore(path)


def test_overview_keeps_every_visible_account_and_marks_missing_snapshots(tmp_path):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    ibkr = portfolio.upsert_broker_account("ibkr", "DU123", "Primary")

    overview = build_portfolio_overview(portfolio, observations)
    rows = {row.id: row for row in overview.accounts}

    assert set(rows) == {manual.id, ibkr.id}
    assert rows[manual.id].latest_snapshot is None
    assert rows[ibkr.id].latest_snapshot is None


def test_overview_joins_latest_values_and_distinct_broker_canonical_times(
    monkeypatch, tmp_path
):
    portfolio, observations = stores(tmp_path)
    run_id = commit_snapshot(observations, captured_account())
    ibkr = next(
        account for account in portfolio.list_accounts() if account.broker == "ibkr"
    )
    monkeypatch.setattr(
        "src.portfolio_state._now", lambda: "2026-07-14T05:01:00+00:00"
    )
    portfolio.apply_broker_positions(
        account_id=ibkr.id,
        positions=[BrokerPosition("ibkr", "DU123", "1", "AAPL", "stock", 1)],
        source="capture",
    )

    overview = build_portfolio_overview(portfolio, observations)
    row = next(item for item in overview.accounts if item.id == ibkr.id)

    assert row.canonical_last_sync_at == "2026-07-14T05:01:00+00:00"
    assert row.latest_snapshot is not None
    assert row.latest_snapshot.capture_run_id == run_id
    assert row.latest_snapshot.as_of_utc == "2026-07-14T05:00:00+00:00"
    assert row.latest_snapshot.net_liquidation == 100_000
    assert row.latest_snapshot.daily_total_pnl == 100


def test_overview_daily_total_requires_both_finite_provider_legs(tmp_path):
    portfolio, observations = stores(tmp_path)
    commit_snapshot(observations, captured_account(realized=125, unrealized=None))

    row = next(
        item
        for item in build_portfolio_overview(portfolio, observations).accounts
        if item.broker == "ibkr"
    )

    assert row.latest_snapshot is not None
    assert row.latest_snapshot.daily_realized_pnl == 125
    assert row.latest_snapshot.daily_unrealized_pnl is None
    assert row.latest_snapshot.daily_total_pnl is None

    commit_snapshot(
        observations,
        captured_account(
            as_of="2026-07-14T05:15:00+00:00",
            realized=1e308,
            unrealized=1e308,
        ),
    )
    overflow_row = next(
        item
        for item in build_portfolio_overview(portfolio, observations).accounts
        if item.broker == "ibkr"
    )
    assert overflow_row.latest_snapshot is not None
    assert overflow_row.latest_snapshot.daily_total_pnl is None


def test_overview_manual_subtotal_uses_only_included_manual_accounts(tmp_path):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    position = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=2, currency="USD"
    )
    with portfolio._connect() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET market_value=500, unrealized_pnl=25 "
            "WHERE id=?",
            (position.id,),
        )

    included = build_portfolio_overview(portfolio, observations).manual_subtotal
    portfolio.update_account(manual.id, include_in_total=False)
    excluded = build_portfolio_overview(portfolio, observations).manual_subtotal

    assert included.included_account_ids == [manual.id]
    assert included.totals.per_currency["USD"].market_value == 500
    assert excluded.included_account_ids == []
    assert excluded.totals.per_currency == {}


def test_overview_manual_subtotal_never_contains_ibkr_positions(tmp_path):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    manual_position = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=2, currency="USD"
    )
    ibkr = portfolio.upsert_broker_account("ibkr", "DU123", "Primary")
    portfolio.apply_broker_positions(
        account_id=ibkr.id,
        positions=[
            BrokerPosition(
                "ibkr",
                "DU123",
                "1",
                "MSFT",
                "stock",
                1,
                currency="USD",
                market_value=999,
            )
        ],
        source="capture",
    )
    with portfolio._connect() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET market_value=500 WHERE id=?",
            (manual_position.id,),
        )

    subtotal = build_portfolio_overview(portfolio, observations).manual_subtotal

    assert subtotal.included_account_ids == [manual.id]
    assert subtotal.totals.per_currency["USD"].position_count == 1
    assert subtotal.totals.per_currency["USD"].market_value == 500


def test_overview_mixed_manual_currencies_remain_per_currency_without_grand_total(
    tmp_path,
):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    usd = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=1, currency="USD"
    )
    twd = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="2330", quantity=10, currency="TWD"
    )
    with portfolio._connect() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET market_value=100 WHERE id=?", (usd.id,)
        )
        conn.execute(
            "UPDATE portfolio_positions SET market_value=10000 WHERE id=?", (twd.id,)
        )

    subtotal = build_portfolio_overview(portfolio, observations).manual_subtotal

    assert subtotal.totals.currency_basis == "per_currency"
    assert set(subtotal.totals.per_currency) == {"USD", "TWD"}
    assert subtotal.totals.broker_base is None


def test_overview_redacts_legacy_label_that_contains_raw_broker_id(tmp_path):
    portfolio, observations = stores(tmp_path)
    account = portfolio.upsert_broker_account("ibkr", "DU123", "IBKR DU123")

    row = next(
        item
        for item in build_portfolio_overview(portfolio, observations).accounts
        if item.id == account.id
    )

    assert row.label == f"IBKR · {account.broker_account_id_hash[:8]}"
    assert safe_portfolio_account_label(account) == row.label
    assert "DU123" not in repr(row)
