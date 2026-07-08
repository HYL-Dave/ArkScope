"""Portfolio and holdings routes."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_data_provider_store, get_portfolio_store
from src.api.permissions import require_profile_state_write
from src.data_provider_config import (
    DataProviderConfigStore,
    ProviderConfigMissing,
    require_provider_configured,
)
from src.portfolio_ibkr import (
    IBKRHoldingsUnavailable,
    preview_or_apply_ibkr_snapshot,
    read_ibkr_portfolio_snapshot,
)
from src.portfolio_state import PortfolioStore

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class ManualPositionBody(BaseModel):
    account_id: int | None = None
    symbol: str
    asset_class: str = "stock"
    quantity: float
    avg_cost: float | None = None
    currency: str = "USD"
    notes: str = ""


class PositionNotesBody(BaseModel):
    notes: str | None = None
    thesis: str | None = None
    tags: list[str] | None = None
    strategy_bucket: str | None = None
    target_allocation: float | None = None


class PortfolioAccountBody(BaseModel):
    label: str
    broker: str = "manual"
    broker_account_id: str | None = None
    sync_mode: str = "manual"
    base_currency: str | None = None


@router.get("")
def get_portfolio(
    store: PortfolioStore = Depends(get_portfolio_store),
) -> dict[str, Any]:
    return _to_json(store.snapshot())


@router.get("/accounts")
def list_accounts(
    store: PortfolioStore = Depends(get_portfolio_store),
) -> dict[str, Any]:
    return {"accounts": [_to_json(account) for account in store.list_accounts()]}


@router.post("/accounts")
def create_account(
    body: PortfolioAccountBody,
    store: PortfolioStore = Depends(get_portfolio_store),
) -> dict[str, Any]:
    require_profile_state_write("portfolio_account_write", {"broker": body.broker})
    if body.broker == "manual":
        return _to_json(store.ensure_manual_account())
    if not body.broker_account_id:
        raise HTTPException(status_code=400, detail={"code": "broker_account_id_required"})
    return _to_json(
        store.upsert_broker_account(
            body.broker,
            body.broker_account_id,
            body.label,
            sync_mode=body.sync_mode,
            base_currency=body.base_currency,
        )
    )


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: int,
    body: PortfolioAccountBody,
    store: PortfolioStore = Depends(get_portfolio_store),
) -> dict[str, Any]:
    require_profile_state_write("portfolio_account_write", {"account_id": account_id})
    if body.broker == "manual":
        return _to_json(store.ensure_manual_account())
    if not body.broker_account_id:
        raise HTTPException(status_code=400, detail={"code": "broker_account_id_required"})
    return _to_json(
        store.upsert_broker_account(
            body.broker,
            body.broker_account_id,
            body.label,
            sync_mode=body.sync_mode,
            base_currency=body.base_currency,
        )
    )


@router.get("/positions")
def list_positions(
    account_id: int | None = None,
    include_closed: bool = False,
    store: PortfolioStore = Depends(get_portfolio_store),
) -> dict[str, Any]:
    return {
        "positions": [
            _to_json(position)
            for position in store.list_positions(account_id=account_id, include_closed=include_closed)
        ]
    }


@router.post("/positions")
def upsert_manual_position(
    body: ManualPositionBody,
    store: PortfolioStore = Depends(get_portfolio_store),
) -> dict[str, Any]:
    require_profile_state_write("portfolio_position_write", {"source": "manual"})
    account_id = body.account_id or store.ensure_manual_account().id
    position = store.upsert_manual_position(
        account_id=account_id,
        symbol=body.symbol,
        asset_class=body.asset_class,
        quantity=body.quantity,
        avg_cost=body.avg_cost,
        currency=body.currency,
        notes=body.notes,
    )
    return _to_json(position)


@router.patch("/positions/{position_id}")
def update_position_notes(
    position_id: int,
    body: PositionNotesBody,
    store: PortfolioStore = Depends(get_portfolio_store),
) -> dict[str, Any]:
    require_profile_state_write("portfolio_position_write", {"position_id": position_id})
    return _to_json(
        store.update_position_notes(
            position_id,
            notes=body.notes,
            thesis=body.thesis,
            tags=body.tags,
            strategy_bucket=body.strategy_bucket,
            target_allocation=body.target_allocation,
        )
    )


@router.post("/ibkr/preview")
def preview_ibkr_sync(
    store: PortfolioStore = Depends(get_portfolio_store),
    data_provider_store: DataProviderConfigStore = Depends(get_data_provider_store),
) -> dict[str, Any]:
    _require_ibkr_config(data_provider_store)
    snapshot = _read_ibkr_snapshot_or_503()
    return _to_json(preview_or_apply_ibkr_snapshot(store, snapshot, apply=False))


@router.post("/ibkr/apply")
def apply_ibkr_sync(
    store: PortfolioStore = Depends(get_portfolio_store),
    data_provider_store: DataProviderConfigStore = Depends(get_data_provider_store),
) -> dict[str, Any]:
    _require_ibkr_config(data_provider_store)
    snapshot = _read_ibkr_snapshot_or_503()
    require_profile_state_write("portfolio_ibkr_sync", {"mode": "apply"})
    return _to_json(preview_or_apply_ibkr_snapshot(store, snapshot, apply=True))


def _require_ibkr_config(store: DataProviderConfigStore) -> None:
    try:
        require_provider_configured("ibkr", store)
    except ProviderConfigMissing as exc:
        raise HTTPException(status_code=503, detail=exc.as_dict()) from exc


def _read_ibkr_snapshot_or_503():
    try:
        return read_ibkr_portfolio_snapshot()
    except IBKRHoldingsUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "ibkr_holdings_unavailable", "detail": str(exc)},
        ) from exc


def _to_json(value: Any) -> Any:
    if is_dataclass(value):
        return _to_json(asdict(value))
    if isinstance(value, dict):
        return {str(k): _to_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    return value
