from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from src.data_provider_config import DataProviderConfigStore
from src.portfolio_ibkr import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    BrokerSnapshot,
    IBKRHoldingsUnavailable,
)
from src.portfolio_observations import PortfolioObservationStore
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


def test_portfolio_overview_router_mounts_on_real_app():
    from src.api.app import create_app

    paths = {getattr(route, "path", None) for route in create_app().routes}

    assert "/portfolio/overview" in paths


def test_get_portfolio_overview_fresh_profile_is_truthful(tmp_path):
    path = tmp_path / "profile_state.db"

    out = routes.get_portfolio_overview(
        store=PortfolioStore(path),
        observations=PortfolioObservationStore(path),
    )

    assert out["accounts"] == [
        {
            "id": 1,
            "label": "Manual",
            "broker": "manual",
            "broker_account_id_hash": None,
            "sync_mode": "manual",
            "base_currency": "USD",
            "include_in_total": True,
            "canonical_last_sync_at": None,
            "latest_snapshot": None,
        }
    ]
    assert out["manual_subtotal"]["totals"]["per_currency"] == {}


def test_get_portfolio_overview_never_serializes_raw_broker_id(tmp_path):
    path = tmp_path / "profile_state.db"
    store = PortfolioStore(path)
    store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")

    out = routes.get_portfolio_overview(
        store=store,
        observations=PortfolioObservationStore(path),
    )

    encoded = json.dumps(out, sort_keys=True)
    assert all("broker_account_id" not in account for account in out["accounts"])
    assert "DU123" not in encoded
    assert "broker_account_id_hash" in out["accounts"][1]


def test_get_portfolio_overview_never_calls_gateway_or_checks_write_permission(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("write gate called")
        ),
    )
    monkeypatch.setattr(
        routes,
        "_read_ibkr_snapshot_or_503",
        lambda: (_ for _ in ()).throw(AssertionError("IBKR read called")),
    )
    path = tmp_path / "profile_state.db"

    out = routes.get_portfolio_overview(
        store=PortfolioStore(path),
        observations=PortfolioObservationStore(path),
    )

    assert out["accounts"][0]["broker"] == "manual"


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
    assert [a for a in store.list_accounts() if a.broker == "ibkr"] == []


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


def test_patch_account_updates_path_target_and_aggregate_flag(monkeypatch, tmp_path):
    calls = []
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "Before")
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )

    out = routes.update_account(
        account.id,
        routes.PortfolioAccountUpdateBody(
            label="After",
            sync_mode="ibkr_auto",
            include_in_total=False,
        ),
        store=store,
    )

    assert out["id"] == account.id
    assert out["label"] == "After"
    assert out["include_in_total"] is False
    assert calls == [("portfolio_account_write", {"account_id": account.id})]


def test_patch_missing_account_returns_404(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")

    with pytest.raises(HTTPException) as exc:
        routes.update_account(
            999,
            routes.PortfolioAccountUpdateBody(label="Missing"),
            store=store,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "portfolio_account_not_found"


def test_invalid_account_sync_mode_returns_400(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "Before")

    with pytest.raises(HTTPException) as exc:
        routes.update_account(
            account.id,
            routes.PortfolioAccountUpdateBody(sync_mode="invalid"),
            store=store,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_portfolio_account"


def test_patch_missing_position_returns_404(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")

    with pytest.raises(HTTPException) as exc:
        routes.update_position(
            999,
            routes.PositionUpdateBody(notes="missing"),
            store=store,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "portfolio_position_not_found"


def _manual_row(store, **overrides):
    account = store.ensure_manual_account()
    params = {
        "account_id": account.id,
        "symbol": "NVDA",
        "quantity": 3,
        "avg_cost": 100,
        "currency": "USD",
        "notes": "start",
    }
    params.update(overrides)
    return store.upsert_manual_position(**params)


def _ibkr_row(store):
    from tests.test_portfolio_state import broker_pos

    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    return store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1, symbol="AAPL", quantity=1)],
        source="test",
    )[0]


def test_patch_position_updates_manual_and_user_fields_atomically(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _manual_row(store)

    out = routes.update_position(
        row.id,
        routes.PositionUpdateBody(
            symbol="amd",
            quantity=-2,
            avg_cost=55.5,
            currency="twd",
            notes="rewritten",
            thesis="cycle",
            tags=["swing"],
        ),
        store=store,
    )

    assert calls == [("portfolio_position_write", {"position_id": row.id})]
    assert out["symbol"] == "AMD"
    assert out["quantity"] == -2
    assert out["avg_cost"] == 55.5
    assert out["currency"] == "TWD"
    assert out["notes"] == "rewritten"
    assert out["thesis"] == "cycle"
    assert out["tags"] == ["swing"]


def test_patch_position_explicit_null_clears_avg_cost(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _manual_row(store)

    omitted = routes.update_position(
        row.id, routes.PositionUpdateBody(quantity=4), store=store
    )
    assert omitted["avg_cost"] == 100

    cleared = routes.update_position(
        row.id,
        routes.PositionUpdateBody.model_validate({"avg_cost": None}),
        store=store,
    )
    assert cleared["avg_cost"] is None
    assert cleared["quantity"] == 4


def test_patch_ibkr_position_rejects_manual_fields_without_partial_note_write(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _ibkr_row(store)

    with pytest.raises(HTTPException) as exc:
        routes.update_position(
            row.id,
            routes.PositionUpdateBody(quantity=99, notes="should not land"),
            store=store,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "broker_position_managed_by_sync"
    after = store.get_position(row.id)
    assert after.quantity == 1
    assert after.notes == ""


def test_patch_ibkr_position_updates_user_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _ibkr_row(store)

    out = routes.update_position(
        row.id,
        routes.PositionUpdateBody(notes="keep", thesis="moat", tags=["core"]),
        store=store,
    )

    assert out["notes"] == "keep"
    assert out["thesis"] == "moat"
    assert out["tags"] == ["core"]
    assert out["quantity"] == 1


def test_patch_position_invalid_value_returns_400(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _manual_row(store)

    with pytest.raises(HTTPException) as exc:
        routes.update_position(
            row.id, routes.PositionUpdateBody(quantity=0), store=store
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_portfolio_position"


def test_delete_manual_position_soft_closes_and_requires_write_gate(
    monkeypatch, tmp_path
):
    calls = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail=None: calls.append((action, detail)),
    )
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _manual_row(store)

    out = routes.close_manual_position(row.id, store=store)

    assert calls == [
        ("portfolio_position_write", {"position_id": row.id, "action": "close"})
    ]
    assert out["closed_at"] is not None
    assert out["notes"] == "start"
    assert store.list_positions() == []


def test_delete_ibkr_position_returns_managed_by_sync(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _ibkr_row(store)

    with pytest.raises(HTTPException) as exc:
        routes.close_manual_position(row.id, store=store)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "broker_position_managed_by_sync"
    assert store.get_position(row.id).closed_at is None


def test_delete_missing_position_returns_404(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    store = PortfolioStore(tmp_path / "profile_state.db")

    with pytest.raises(HTTPException) as exc:
        routes.close_manual_position(999, store=store)

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "portfolio_position_not_found"


def test_get_portfolio_include_closed_threads_to_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    store = PortfolioStore(tmp_path / "profile_state.db")
    row = _manual_row(store)
    routes.close_manual_position(row.id, store=store)

    default_view = routes.get_portfolio(store=store)
    assert default_view["positions"] == []

    closed_view = routes.get_portfolio(include_closed=True, store=store)
    assert [p["id"] for p in closed_view["positions"]] == [row.id]
    assert closed_view["positions"][0]["notes"] == "start"
