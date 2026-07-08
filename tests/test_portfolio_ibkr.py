from __future__ import annotations

import pytest

from src.portfolio_state import PortfolioStore
from src import portfolio_ibkr
from src.portfolio_ibkr import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    BrokerSnapshot,
    IBKRHoldingsUnavailable,
    preview_or_apply_ibkr_snapshot,
    read_ibkr_portfolio_snapshot,
)


def snapshot_with_pos(
    *,
    account: str = "DU123",
    con_id: int = 1,
    symbol: str = "MSFT",
    quantity: float = 1,
) -> BrokerSnapshot:
    return BrokerSnapshot(
        accounts=[BrokerAccountSnapshot(account_id=account, label=f"IBKR {account}", base_currency="USD")],
        positions=[
            BrokerPositionSnapshot(
                account_id=account,
                con_id=str(con_id),
                symbol=symbol,
                asset_class="stock",
                quantity=quantity,
                currency="USD",
            )
        ],
    )


def test_reader_uses_holdings_client_id_and_readonly(monkeypatch):
    captured = {}

    class FakeSource:
        def __init__(self, *, client_id, readonly):
            captured["client_id"] = client_id
            captured["readonly"] = readonly

        def connect(self):
            captured["connected"] = True
            return True

        def disconnect(self):
            captured["disconnected"] = True

    monkeypatch.setenv("IBKR_CLIENT_ID", "1")
    monkeypatch.setattr(portfolio_ibkr, "IBKRDataSource", FakeSource)
    monkeypatch.setattr(
        portfolio_ibkr,
        "_read_connected_ibkr",
        lambda source: BrokerSnapshot(accounts=[], positions=[]),
    )

    read_ibkr_portfolio_snapshot()

    assert captured == {
        "client_id": 61,
        "readonly": True,
        "connected": True,
        "disconnected": True,
    }


def test_connect_false_raises_unavailable_and_never_reads_positions(monkeypatch):
    class FakeSource:
        def __init__(self, *, client_id, readonly):
            self.client_id = client_id
            self.readonly = readonly

        def connect(self):
            return False

        def disconnect(self):
            pass

    monkeypatch.setattr(portfolio_ibkr, "IBKRDataSource", FakeSource)
    monkeypatch.setattr(
        portfolio_ibkr,
        "_read_connected_ibkr",
        lambda source: (_ for _ in ()).throw(AssertionError("positions read after failed connect")),
    )

    with pytest.raises(IBKRHoldingsUnavailable):
        read_ibkr_portfolio_snapshot()


def test_review_mode_returns_diff_without_writing(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123", sync_mode="ibkr_review")

    diff = preview_or_apply_ibkr_snapshot(store, snapshot_with_pos(account="DU123", con_id=1), apply=False)

    assert diff.changes[0].kind == "add"
    assert store.list_positions(account_id=account.id) == []


def test_auto_mode_applies_broker_owned_fields_only(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123", sync_mode="ibkr_auto")
    preview_or_apply_ibkr_snapshot(
        store,
        snapshot_with_pos(account="DU123", con_id=1, quantity=1),
        apply=True,
    )
    row = store.list_positions(account_id=account.id)[0]
    store.update_position_notes(row.id, notes="do not touch")

    preview_or_apply_ibkr_snapshot(
        store,
        snapshot_with_pos(account="DU123", con_id=1, quantity=2),
        apply=True,
    )

    row = store.get_position(row.id)
    assert row.quantity == 2
    assert row.notes == "do not touch"
