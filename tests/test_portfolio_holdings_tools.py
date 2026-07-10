from __future__ import annotations

from src.portfolio_state import PortfolioStore
from src.tools.portfolio_holdings_tools import get_portfolio_holdings


def test_get_portfolio_holdings_reads_local_store(tmp_path, monkeypatch):
    db = tmp_path / "profile_state.db"
    store = PortfolioStore(db)
    account = store.ensure_manual_account()
    store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=2, currency="USD")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))

    out = get_portfolio_holdings()

    assert out["accounts"][0]["label"] == "Manual"
    assert out["positions"][0]["symbol"] == "NVDA"
    assert out["totals"]["currency_basis"] == "per_currency"


def test_get_portfolio_holdings_never_touches_ibkr(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setattr(
        "src.portfolio_ibkr.read_ibkr_portfolio_snapshot",
        lambda: (_ for _ in ()).throw(AssertionError("IBKR touched")),
    )

    out = get_portfolio_holdings()

    assert out["source"] == "local_profile"


def test_get_portfolio_holdings_redacts_raw_broker_account_id(tmp_path, monkeypatch):
    db = tmp_path / "profile_state.db"
    store = PortfolioStore(db)
    account = store.upsert_broker_account("ibkr", "U7654321", "Primary IBKR")
    store.apply_broker_positions(
        account_id=account.id,
        positions=[],
        source="test",
    )
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))

    out = get_portfolio_holdings()

    assert out["accounts"][0]["label"] in {"Manual", "Primary IBKR"}
    assert all("broker_account_id" not in row for row in out["accounts"])
    assert "U7654321" not in str(out)


def test_get_portfolio_holdings_scope_and_totals_match_requested_rows(tmp_path, monkeypatch):
    db = tmp_path / "profile_state.db"
    store = PortfolioStore(db)
    manual = store.ensure_manual_account()
    other = store.upsert_broker_account("ibkr", "DU123", "Other")
    store.upsert_manual_position(
        account_id=manual.id,
        symbol="OPEN",
        quantity=1,
        currency="USD",
    )
    closed = store.upsert_manual_position(
        account_id=manual.id,
        symbol="CLOSED",
        quantity=1,
        currency="USD",
    )
    store.close_position(closed.id)
    store.update_account(other.id, include_in_total=False)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))

    out = get_portfolio_holdings(account_id=manual.id, include_closed=True)

    assert [row["id"] for row in out["accounts"]] == [manual.id]
    assert {row["symbol"] for row in out["positions"]} == {"OPEN", "CLOSED"}
    # Totals count open holdings only, even when closed rows are displayed.
    assert out["totals"]["per_currency"]["USD"]["position_count"] == 1
    assert out["included_account_ids"] == [manual.id]
