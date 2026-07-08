from __future__ import annotations

from src.portfolio_state import BrokerPosition, PortfolioStore


def broker_pos(
    *,
    con_id: int,
    symbol: str,
    quantity: float,
    account_id: str = "DU123",
    asset_class: str = "stock",
    currency: str = "USD",
    avg_cost: float | None = None,
    market_value: float | None = None,
    unrealized_pnl: float | None = None,
) -> BrokerPosition:
    return BrokerPosition(
        broker="ibkr",
        broker_account_id=account_id,
        broker_con_id=str(con_id),
        symbol=symbol,
        asset_class=asset_class,
        quantity=quantity,
        avg_cost=avg_cost,
        currency=currency,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
    )


def test_fresh_store_creates_manual_account(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    accounts = store.list_accounts()
    assert [a.label for a in accounts] == ["Manual"]
    assert accounts[0].broker == "manual"
    assert accounts[0].sync_mode == "manual"


def test_manual_position_round_trip_and_totals(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    store.upsert_manual_position(
        account_id=account.id,
        symbol="NVDA",
        asset_class="stock",
        quantity=3,
        avg_cost=100,
        currency="USD",
        notes="long-term core",
    )

    snapshot = store.snapshot()

    assert snapshot.positions[0].symbol == "NVDA"
    assert snapshot.positions[0].notes == "long-term core"
    assert snapshot.totals.currency_basis == "per_currency"
    assert snapshot.totals.per_currency["USD"].position_count == 1


def test_ibkr_position_identity_uses_conid_not_symbol(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account(
        broker="ibkr",
        broker_account_id="DU123",
        label="IBKR DU123",
        sync_mode="ibkr_auto",
        base_currency="USD",
    )
    store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1001, symbol="LC", quantity=5)],
        source="test",
    )
    store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1001, symbol="HAPN", quantity=5)],
        source="test",
    )

    positions = store.list_positions(account_id=account.id)

    assert len(positions) == 1
    assert positions[0].broker_con_id == "1001"
    assert positions[0].symbol == "HAPN"


def test_broker_sync_does_not_overwrite_user_fields(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    first = store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=2002, symbol="AAPL", quantity=1)],
        source="test",
    )[0]
    store.update_position_notes(first.id, notes="my thesis", tags=["core"])
    store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=2002, symbol="AAPL", quantity=2)],
        source="test",
    )

    row = store.get_position(first.id)

    assert row.quantity == 2
    assert row.notes == "my thesis"
    assert row.tags == ["core"]
