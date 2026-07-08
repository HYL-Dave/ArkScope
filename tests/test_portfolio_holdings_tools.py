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
