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


def test_broker_sync_closes_positions_missing_from_complete_snapshot(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    kept, removed = store.apply_broker_positions(
        account_id=account.id,
        positions=[
            broker_pos(con_id=1, symbol="AAPL", quantity=2),
            broker_pos(con_id=2, symbol="MSFT", quantity=3),
        ],
        source="test",
    )

    store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1, symbol="AAPL", quantity=2)],
        source="test",
    )

    assert [row.id for row in store.list_positions(account_id=account.id)] == [kept.id]
    closed = store.get_position(removed.id)
    assert closed.closed_at is not None
    assert closed.notes == ""


def test_snapshot_totals_exclude_accounts_disabled_from_aggregate(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    manual = store.ensure_manual_account()
    excluded = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    store.upsert_manual_position(
        account_id=manual.id,
        symbol="NVDA",
        quantity=1,
        currency="USD",
    )
    store.apply_broker_positions(
        account_id=excluded.id,
        positions=[
            broker_pos(
                con_id=1,
                symbol="MSFT",
                quantity=2,
                market_value=200,
            )
        ],
        source="test",
    )
    store.update_account(excluded.id, include_in_total=False)

    snapshot = store.snapshot()

    assert snapshot.included_account_ids == [manual.id]
    assert snapshot.totals.per_currency["USD"].position_count == 1
    assert {row.symbol for row in snapshot.positions} == {"NVDA", "MSFT"}


def test_update_account_targets_local_id_and_can_archive(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    first = store.upsert_broker_account("ibkr", "DU111", "First")
    second = store.upsert_broker_account("ibkr", "DU222", "Second")

    updated = store.update_account(
        first.id,
        label="Primary",
        sync_mode="ibkr_auto",
        base_currency="CAD",
        include_in_total=False,
        archived=True,
    )

    assert updated.id == first.id
    assert updated.label == "Primary"
    assert updated.sync_mode == "ibkr_auto"
    assert updated.base_currency == "CAD"
    assert updated.include_in_total is False
    assert updated.archived_at is not None
    assert store.get_account(second.id).label == "Second"


def test_store_configures_sqlite_for_cross_process_contention(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")

    with store._connect() as conn:
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert busy_timeout == 5000
    assert journal_mode.lower() == "wal"


def test_fresh_schema_does_not_create_deferred_sync_history_tables(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")

    with store._connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert "portfolio_sync_runs" not in tables
    assert "portfolio_sync_diffs" not in tables
