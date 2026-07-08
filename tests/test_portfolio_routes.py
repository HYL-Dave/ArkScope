from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.data_provider_config import DataProviderConfigStore
from src.portfolio_ibkr import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    BrokerSnapshot,
    IBKRHoldingsUnavailable,
)
from src.portfolio_state import PortfolioStore
from src.api.routes import portfolio as routes


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


def _configured_provider_store(tmp_path, monkeypatch) -> DataProviderConfigStore:
    monkeypatch.setenv("IBKR_HOST", "127.0.0.1")
    monkeypatch.setenv("IBKR_PORT", "4002")
    return DataProviderConfigStore(tmp_path / "provider_state.db")


def test_portfolio_router_mounts_on_real_app():
    from src.api.app import create_app

    paths = {getattr(route, "path", None) for route in create_app().routes}

    assert "/portfolio" in paths
    assert "/portfolio/positions" in paths
    assert "/portfolio/ibkr/preview" in paths


def test_get_portfolio_returns_manual_account_for_fresh_profile(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")

    out = routes.get_portfolio(store=store)

    assert out["accounts"][0]["label"] == "Manual"
    assert out["totals"]["currency_basis"] == "per_currency"


def test_manual_position_mutation_requires_profile_state_write(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )
    store = PortfolioStore(tmp_path / "profile_state.db")
    body = routes.ManualPositionBody(
        account_id=store.ensure_manual_account().id,
        symbol="NVDA",
        quantity=1,
    )

    routes.upsert_manual_position(body, store=store)

    assert calls == [("portfolio_position_write", {"source": "manual"})]


def test_ibkr_preview_does_not_write(monkeypatch, tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    provider_store = _configured_provider_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "read_ibkr_portfolio_snapshot", lambda: snapshot_with_pos())

    out = routes.preview_ibkr_sync(store=store, data_provider_store=provider_store)

    assert out["changes"]
    assert store.list_positions() == []


def test_ibkr_apply_requires_profile_state_write(monkeypatch, tmp_path):
    calls = []
    store = PortfolioStore(tmp_path / "profile_state.db")
    provider_store = _configured_provider_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "read_ibkr_portfolio_snapshot", lambda: snapshot_with_pos())
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )

    routes.apply_ibkr_sync(store=store, data_provider_store=provider_store)

    assert calls == [("portfolio_ibkr_sync", {"mode": "apply"})]


def test_ibkr_unavailable_returns_503_and_store_is_unchanged(monkeypatch, tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    provider_store = _configured_provider_store(tmp_path, monkeypatch)
    before = store.snapshot()
    monkeypatch.setattr(
        routes,
        "read_ibkr_portfolio_snapshot",
        lambda: (_ for _ in ()).throw(IBKRHoldingsUnavailable("IBKR Gateway connection failed")),
    )

    with pytest.raises(HTTPException) as exc:
        routes.preview_ibkr_sync(store=store, data_provider_store=provider_store)

    assert exc.value.status_code == 503
    assert store.snapshot() == before


def test_ibkr_missing_config_returns_provider_config_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("IBKR_HOST", raising=False)
    monkeypatch.delenv("IBKR_PORT", raising=False)
    store = PortfolioStore(tmp_path / "profile_state.db")
    provider_store = DataProviderConfigStore(tmp_path / "provider_state.db")

    with pytest.raises(HTTPException) as exc:
        routes.preview_ibkr_sync(store=store, data_provider_store=provider_store)

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "provider_config_missing"
    assert exc.value.detail["status"] == "not_configured"
    assert exc.value.detail["provider"] == "ibkr"
    assert exc.value.detail["field"] in {"host", "port"}
