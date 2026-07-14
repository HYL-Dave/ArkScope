from __future__ import annotations

import pytest

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

    assert store.list_accounts(ensure_manual=False) == []

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


def test_update_manual_position_changes_financial_and_user_fields(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(
        account_id=account.id,
        symbol="NVDA",
        quantity=3,
        avg_cost=100,
        currency="USD",
        notes="original",
    )

    updated = store.update_position(
        row.id,
        fields={
            "symbol": "amd ",
            "asset_class": "ETF",
            "quantity": -2,
            "avg_cost": 55.5,
            "currency": "twd",
            "notes": "rewritten",
            "thesis": "cycle bet",
            "tags": ["swing", "semis"],
        },
    )

    assert updated.symbol == "AMD"
    assert updated.asset_class == "etf"
    assert updated.quantity == -2
    assert updated.avg_cost == 55.5
    assert updated.currency == "TWD"
    assert updated.notes == "rewritten"
    assert updated.thesis == "cycle bet"
    assert updated.tags == ["swing", "semis"]


def test_update_manual_position_explicit_null_clears_avg_cost(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(
        account_id=account.id, symbol="NVDA", quantity=3, avg_cost=100
    )

    omitted = store.update_position(row.id, fields={"quantity": 4})
    assert omitted.avg_cost == 100

    cleared = store.update_position(row.id, fields={"avg_cost": None})
    assert cleared.avg_cost is None
    assert cleared.quantity == 4


def test_update_manual_position_rejects_invalid_values(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=3)

    import pytest

    with pytest.raises(ValueError):
        store.update_position(row.id, fields={"quantity": 0})
    with pytest.raises(ValueError):
        store.update_position(row.id, fields={"quantity": None})
    with pytest.raises(ValueError):
        store.update_position(row.id, fields={"symbol": "  "})
    with pytest.raises(ValueError):
        store.update_position(row.id, fields={"avg_cost": -1})
    with pytest.raises(ValueError):
        store.update_position(row.id, fields={"unknown_field": 1})
    assert store.get_position(row.id).quantity == 3


def test_update_broker_position_allows_user_fields(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    row = store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1, symbol="AAPL", quantity=1)],
        source="test",
    )[0]

    updated = store.update_position(
        row.id,
        fields={"notes": "keep", "thesis": "moat", "tags": ["core"]},
    )

    assert updated.notes == "keep"
    assert updated.thesis == "moat"
    assert updated.tags == ["core"]
    assert updated.quantity == 1


def test_update_broker_position_rejects_manual_fields_without_partial_write(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    row = store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1, symbol="AAPL", quantity=1)],
        source="test",
    )[0]

    import pytest

    from src.portfolio_state import BrokerPositionManagedBySync

    with pytest.raises(BrokerPositionManagedBySync):
        store.update_position(
            row.id,
            fields={"quantity": 99, "notes": "should not land"},
        )

    after = store.get_position(row.id)
    assert after.quantity == 1
    assert after.notes == ""


def test_manual_soft_close_preserves_user_fields_and_is_visible_when_requested(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(
        account_id=account.id, symbol="NVDA", quantity=3, notes="thesis intact"
    )

    closed = store.close_position(row.id)
    assert closed.closed_at is not None
    assert closed.notes == "thesis intact"

    again = store.close_position(row.id)
    assert again.closed_at == closed.closed_at

    assert store.list_positions(account_id=account.id) == []
    visible = store.list_positions(account_id=account.id, include_closed=True)
    assert [p.id for p in visible] == [row.id]
    assert visible[0].notes == "thesis intact"

    edited = store.update_position(row.id, fields={"avg_cost": 12.5})
    assert edited.avg_cost == 12.5
    assert edited.closed_at == closed.closed_at


def test_broker_position_cannot_be_manually_closed(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    row = store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1, symbol="AAPL", quantity=1)],
        source="test",
    )[0]

    import pytest

    from src.portfolio_state import BrokerPositionManagedBySync

    with pytest.raises(BrokerPositionManagedBySync):
        store.close_position(row.id)

    assert store.get_position(row.id).closed_at is None


def test_nullable_user_fields_distinguish_omitted_from_explicit_null(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=3)
    store.update_position(
        row.id,
        fields={"strategy_bucket": "core", "target_allocation": 0.2},
    )

    untouched = store.update_position(row.id, fields={"notes": "hi"})
    assert untouched.strategy_bucket == "core"
    assert untouched.target_allocation == 0.2

    cleared = store.update_position(
        row.id,
        fields={"strategy_bucket": None, "target_allocation": None},
    )
    assert cleared.strategy_bucket is None
    assert cleared.target_allocation is None


def test_totals_always_exclude_closed_rows_even_when_visible(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(
        account_id=account.id, symbol="NVDA", quantity=3, currency="USD"
    )
    store.close_position(row.id)

    default_view = store.snapshot()
    closed_view = store.snapshot(include_closed=True)

    assert default_view.positions == []
    assert [p.id for p in closed_view.positions] == [row.id]
    assert closed_view.totals == default_view.totals
    assert "USD" not in closed_view.totals.per_currency


def test_last_position_sync_time_survives_complete_liquidation(monkeypatch, tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account(
        "ibkr", "DU123", "IBKR", base_currency="USD"
    )
    monkeypatch.setattr(
        "src.portfolio_state._now", lambda: "2026-07-14T05:00:00+00:00"
    )
    store.apply_broker_positions(
        account_id=account.id,
        positions=[BrokerPosition("ibkr", "DU123", "1", "AAPL", "stock", 1)],
        source="capture",
    )
    monkeypatch.setattr(
        "src.portfolio_state._now", lambda: "2026-07-14T06:00:00+00:00"
    )
    store.apply_broker_positions(
        account_id=account.id, positions=[], source="capture"
    )

    assert store.list_positions(account_id=account.id) == []
    assert store.last_position_sync_at_by_account({account.id}) == {
        account.id: "2026-07-14T06:00:00+00:00"
    }


def test_totals_for_accounts_reuses_open_position_currency_rules_and_exact_ids(
    tmp_path,
):
    store = PortfolioStore(tmp_path / "profile_state.db")
    manual = store.ensure_manual_account()
    included = store.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=2, currency="USD"
    )
    excluded_account = store.upsert_broker_account("ibkr", "DU123", "IBKR")
    store.apply_broker_positions(
        account_id=excluded_account.id,
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
    with store._connect() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET market_value=250 WHERE id=?",
            (included.id,),
        )

    totals = store.totals_for_accounts({manual.id})

    assert totals.currency_basis == "per_currency"
    assert totals.per_currency["USD"].position_count == 1
    assert totals.per_currency["USD"].market_value == 250


def test_totals_for_accounts_empty_set_never_falls_back_to_all_positions(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    manual = store.ensure_manual_account()
    store.upsert_manual_position(account_id=manual.id, symbol="AAPL", quantity=1)

    totals = store.totals_for_accounts(set())

    assert totals.per_currency == {}
    assert totals.broker_base is None


def _adjustment_change_count(store: PortfolioStore) -> int:
    with store._connect() as conn:
        return int(
            conn.execute("SELECT COUNT(*) FROM portfolio_manual_adjustment_changes").fetchone()[0]
        )


def test_manual_create_records_field_level_adjustment(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()

    row = store.upsert_manual_position(
        account_id=account.id,
        symbol=" nvda ",
        asset_class="ETF",
        quantity=3,
        avg_cost=100,
        currency="twd",
        notes="not journaled",
    )

    adjustments = store.list_manual_adjustments(position_id=row.id)
    assert len(adjustments) == 1
    adjustment = adjustments[0]
    assert adjustment.account_id == account.id
    assert adjustment.position_id == row.id
    assert adjustment.action == "create"
    assert adjustment.note is None
    assert adjustment.source == "manual"
    assert adjustment.occurred_at_utc
    assert [(change.field, change.before, change.after) for change in adjustment.changes] == [
        ("asset_class", None, "etf"),
        ("avg_cost", None, 100.0),
        ("currency", None, "TWD"),
        ("quantity", None, 3.0),
        ("symbol", None, "NVDA"),
    ]

    for value in (float("nan"), float("inf"), -float("inf"), 0):
        with pytest.raises(ValueError):
            store.upsert_manual_position(
                account_id=account.id, symbol="BAD", quantity=value
            )
    with pytest.raises(ValueError):
        store.upsert_manual_position(
            account_id=account.id, symbol="BAD", quantity=1, avg_cost=-1
        )
    with pytest.raises(ValueError):
        store.upsert_manual_position(
            account_id=account.id, symbol="BAD", quantity=1, currency=" "
        )
    assert [position.id for position in store.list_positions(include_closed=True)] == [row.id]
    assert _adjustment_change_count(store) == 5


def test_manual_update_journals_only_changed_financial_fields(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(
        account_id=account.id, symbol="NVDA", quantity=3, avg_cost=100
    )

    store.update_position(
        row.id,
        fields={"symbol": "amd ", "quantity": -2, "notes": "not journaled"},
    )

    adjustments = store.list_manual_adjustments(position_id=row.id)
    assert len(adjustments) == 2
    assert adjustments[-1].action == "update"
    assert [(change.field, change.before, change.after) for change in adjustments[-1].changes] == [
        ("quantity", 3.0, -2.0),
        ("symbol", "NVDA", "AMD"),
    ]


def test_manual_avg_cost_clear_records_explicit_null(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(
        account_id=account.id, symbol="NVDA", quantity=3, avg_cost=100
    )

    store.update_position(row.id, fields={"avg_cost": None})

    adjustment = store.list_manual_adjustments(position_id=row.id)[-1]
    assert adjustment.action == "update"
    assert [(change.field, change.before, change.after) for change in adjustment.changes] == [
        ("avg_cost", 100.0, None),
    ]


def test_manual_close_records_one_idempotent_adjustment(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=3)
    before_count = _adjustment_change_count(store)

    closed = store.close_position(row.id)
    again = store.close_position(row.id)

    adjustments = store.list_manual_adjustments(position_id=row.id)
    close_adjustments = [adjustment for adjustment in adjustments if adjustment.action == "close"]
    assert again.closed_at == closed.closed_at
    assert len(close_adjustments) == 1
    assert [(change.field, change.before, change.after) for change in close_adjustments[0].changes] == [
        ("closed_at", None, closed.closed_at),
    ]
    assert _adjustment_change_count(store) == before_count + 1


def test_note_only_update_does_not_create_manual_adjustment(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=3)
    before_count = _adjustment_change_count(store)

    updated = store.update_position(row.id, fields={"notes": "not journaled"})

    assert updated.notes == "not journaled"
    assert _adjustment_change_count(store) == before_count


def test_manual_create_rolls_back_when_journal_insert_fails(tmp_path, monkeypatch):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    before_positions = store.list_positions(include_closed=True)
    before_changes = _adjustment_change_count(store)

    def fail_journal(*args, **kwargs):
        raise RuntimeError("journal insert failed")

    monkeypatch.setattr(store, "_record_manual_adjustment", fail_journal)
    with pytest.raises(RuntimeError, match="journal insert failed"):
        store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=3)

    assert store.list_positions(include_closed=True) == before_positions
    assert _adjustment_change_count(store) == before_changes


def test_manual_update_and_note_change_roll_back_when_journal_insert_fails(tmp_path, monkeypatch):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(
        account_id=account.id, symbol="NVDA", quantity=3, notes="original"
    )
    before = store.get_position(row.id)
    before_changes = _adjustment_change_count(store)

    def fail_journal(*args, **kwargs):
        raise RuntimeError("journal insert failed")

    monkeypatch.setattr(store, "_record_manual_adjustment", fail_journal)
    with pytest.raises(RuntimeError, match="journal insert failed"):
        store.update_position(row.id, fields={"quantity": 4, "notes": "changed"})

    assert store.get_position(row.id) == before
    assert _adjustment_change_count(store) == before_changes


def test_manual_close_rolls_back_when_journal_insert_fails(tmp_path, monkeypatch):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    row = store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=3)
    before = store.get_position(row.id)
    before_changes = _adjustment_change_count(store)

    def fail_journal(*args, **kwargs):
        raise RuntimeError("journal insert failed")

    monkeypatch.setattr(store, "_record_manual_adjustment", fail_journal)
    with pytest.raises(RuntimeError, match="journal insert failed"):
        store.close_position(row.id)

    assert store.get_position(row.id) == before
    assert _adjustment_change_count(store) == before_changes
