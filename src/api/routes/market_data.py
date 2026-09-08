"""Market-data status, coverage, review, and fail-closed admin routes."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query
from pydantic import BaseModel, ConfigDict, Field

from src.api.dependencies import get_profile_store
from src.api.permissions import require_db_write, require_profile_state_write
from src.market_data_admin import (
    USE_LOCAL_MARKET_KEY,
    USE_LOCAL_MARKET_STRICT_KEY,
    env_routing_enabled,
    env_strict_enabled,
    local_market_stats,
    local_ticker_coverage,
    overlay_price_authority,
    read_sync_meta,
    resolve_market_db_path,
)
from src.market_coverage.models import TradingDayCoverageV2
from src.market_coverage.service import TradingDayCoverageService
from src.news_sync_status import overlay_news_sync_status
from src.profile_state import ProfileStateStore
from src.price_defaults import DEFAULT_PRICE_LOOKBACK_DAYS

router = APIRouter(tags=["market-data"])

_TRUTHY = ("1", "true", "yes", "on")


def _setting_truthy(store: ProfileStateStore, key: str) -> bool:
    return (store.get_setting(key) or "").strip().lower() in _TRUTHY


def _manual_update_domains(store: ProfileStateStore) -> tuple[str, ...] | None:
    return ()


def _setting_enabled(store: ProfileStateStore) -> bool:
    return _setting_truthy(store, USE_LOCAL_MARKET_KEY)


def _strict_setting_enabled(store: ProfileStateStore) -> bool:
    return _setting_truthy(store, USE_LOCAL_MARKET_STRICT_KEY)


@router.get("/market-data/status")
def market_data_status(store: ProfileStateStore = Depends(get_profile_store)):
    """Return current local market-data facts without provider work."""
    path = resolve_market_db_path()
    stats = local_market_stats(path)
    setting_on = _setting_enabled(store)
    env_on = env_routing_enabled()
    strict_setting_on = _strict_setting_enabled(store)
    strict_env_on = env_strict_enabled()
    # The local layer returns honest-empty rows until collection creates the file.
    routing_enabled = True
    strict_enabled = True
    sync = overlay_price_authority(overlay_news_sync_status(read_sync_meta(path), path))
    return {
        "market_db": path,
        "exists": stats["exists"],
        "prices": stats["prices"],
        "prices_authority": "local",
        "news": stats["news"],
        "fundamentals": stats["fundamentals"],
        "financial_cache": stats["financial_cache"],  # 3c-C local-primary cache (rows/valid/expired)
        "fundamentals_mode": "local_cache_refetch",
        "sync": sync,  # mirror domains + direct-news telemetry when its writer is active
        "use_local_market_setting": setting_on,
        "env_override": env_on,
        "local_market_strict_setting": strict_setting_on,
        "strict_env_override": strict_env_on,
        "strict_enabled": strict_enabled,
        "routing_enabled": routing_enabled,
    }


@router.post("/market-data/bootstrap")
def bootstrap_route():
    """Reject unsupported bulk bootstrap requests."""
    require_db_write("market_bootstrap", {"db": resolve_market_db_path()})
    raise _unavailable_market_admin_http_error("bootstrap_route")


@router.post("/market-data/update")
def update_route(store: ProfileStateStore = Depends(get_profile_store)):
    """Reject unsupported bulk update requests."""
    require_db_write("market_update", {"db": resolve_market_db_path()})
    _manual_update_domains(store)
    raise _unavailable_market_update_http_error()


@router.get("/market-data/coverage/{ticker}")
def market_data_coverage(ticker: str):
    """Per-domain LOCAL coverage for ``ticker`` (PURE READ; routing-independent).

    Reports whether the local market database holds rows for this ticker in each
    domain. This is independent of the source used for an individual read.
    """
    return local_ticker_coverage(ticker)


@router.get(
    "/market-data/trading-days",
    response_model=TradingDayCoverageV2,
)
def market_data_trading_days(
    lookback_days: int = Query(DEFAULT_PRICE_LOOKBACK_DAYS, ge=1, le=120),
    interval: Literal["15min"] = Query("15min"),
) -> TradingDayCoverageV2:
    """Return read-only RTH session truth for the current active universe.

    Calendar, observation, and provider health remain independent facts. This
    path reads local SQLite only and never schedules collection or repair work.
    """
    from src.active_universe import ActiveUniverseUnavailable
    from src.universe_scope import resolve_active_universe

    try:
        universe = list(resolve_active_universe())
    except ActiveUniverseUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.as_dict()) from None
    return TradingDayCoverageService(
        db_path=resolve_market_db_path(),
    ).get_coverage(
        universe=universe,
        interval=interval,
        lookback_days=lookback_days,
    )


@router.post("/market-data/validate")
def validate_route():
    """Reject unsupported bulk validation requests."""
    require_db_write("market_validate", {"db": resolve_market_db_path()})
    raise _unavailable_market_admin_http_error("validate_route")


@router.get("/market-data/price-repair/preview")
def price_repair_preview(lookback_days: int = Query(DEFAULT_PRICE_LOOKBACK_DAYS, ge=1, le=120)):
    from src.market_coverage.repair import preview_price_repair
    try:
        return preview_price_repair(market_data_trading_days(lookback_days=lookback_days, interval="15min"))
    except ValueError:
        raise HTTPException(status_code=409, detail={"code": "price_coverage_unavailable"}) from None


@router.get("/market-data/price-repair/operations")
def price_repair_operations(limit: int = Query(5, ge=1, le=20), offset: int = Query(0, ge=0)):
    from src.active_universe import ActiveUniverseUnavailable
    from src.price_repair_status import list_price_repairs
    from src.price_repair_execution import PriceRepairError
    from src.universe_scope import resolve_active_universe
    try:
        return list_price_repairs(resolve_market_db_path(), universe=resolve_active_universe(), limit=limit, offset=offset)
    except ActiveUniverseUnavailable as exc:
        raise HTTPException(503, detail=exc.as_dict()) from None
    except (PriceRepairError, OSError, ValueError):
        raise HTTPException(503, detail={"code": "price_repair_status_unavailable"}) from None


class PriceRepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lookback_days: int = Field(ge=1, le=120, strict=True)
    preview_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.get("/market-data/price-repair/{repair_id}")
def price_repair_operation(repair_id: str = PathParam(pattern=r"^[a-f0-9]{32}$")):
    from src.active_universe import ActiveUniverseUnavailable
    from src.price_repair_status import price_repair_status
    from src.universe_scope import resolve_active_universe
    try:
        return price_repair_status(resolve_market_db_path(), repair_id, universe=resolve_active_universe())
    except ActiveUniverseUnavailable as exc:
        raise HTTPException(503, detail=exc.as_dict()) from None


@router.post("/market-data/price-repair")
def price_repair(body: PriceRepairRequest):
    from src.market_coverage.repair import validate_price_repair
    from src.price_repair_execution import build_repair_plan, RepairJournal, repair_directory, PriceRepairError
    from src.service.data_scheduler import run_source
    import threading
    import uuid

    require_db_write("price_coverage_repair", {"lookback_days": body.lookback_days})
    require_profile_state_write("price_coverage_repair", {})
    try:
        coverage = market_data_trading_days(lookback_days=body.lookback_days, interval="15min")
        plan = validate_price_repair(coverage, body.preview_sha256)
    except ValueError as exc:
        code = "price_repair_preview_changed" if str(exc) == "price_repair_preview_changed" else "price_coverage_unavailable"
        raise HTTPException(status_code=409, detail={"code": code}) from None
    if not plan["tickers"]:
        return {"status": "nothing_to_repair", "tickers": []}
    repair_id = uuid.uuid4().hex
    try:
        prepared = build_repair_plan(coverage, resolve_market_db_path())
        journal = RepairJournal(repair_directory(resolve_market_db_path(), repair_id), prepared)
        journal.close()
    except (PriceRepairError, OSError, sqlite3.Error):
        raise HTTPException(409, {"code": "price_repair_preparation_failed"}) from None
    threading.Thread(target=run_source, args=("ibkr_prices", "api"), kwargs={
        "tickers": plan["tickers"], "price_lookback_days": body.lookback_days, "price_as_of_date": plan["as_of_date"],
        "price_repair_id": repair_id,
    }, daemon=True).start()
    return {"status": "accepted", "tickers": plan["tickers"], "repair_id": repair_id}


@router.post("/market-data/price-repair/{repair_id}/resume")
def resume_price_repair(repair_id: str):
    from src.active_universe import ActiveUniverseUnavailable
    from src.price_repair_execution import load_repair_plan, repair_directory, PriceRepairError
    from src.price_repair_status import price_repair_status
    from src.service.data_scheduler import run_source
    from src.universe_scope import resolve_active_universe
    import threading

    require_db_write("price_coverage_repair", {"repair_id": repair_id})
    require_profile_state_write("price_coverage_repair", {})
    try:
        prepared = load_repair_plan(repair_directory(resolve_market_db_path(), repair_id))
        if prepared["market_db"] != str(Path(resolve_market_db_path()).resolve()):
            raise PriceRepairError("price_repair_plan_changed")
        state = price_repair_status(resolve_market_db_path(), repair_id, universe=resolve_active_universe())
        if state["state"] == "complete":
            return {"status": "nothing_to_repair", "tickers": []}
        if not state["resume"]["available"]:
            raise PriceRepairError("price_repair_resume_unavailable")
    except ActiveUniverseUnavailable as exc:
        raise HTTPException(503, detail=exc.as_dict()) from None
    except (PriceRepairError, OSError):
        raise HTTPException(409, {"code": "price_repair_resume_unavailable"}) from None
    plan = prepared["preview"]
    threading.Thread(target=run_source, args=("ibkr_prices", "api"), kwargs={
        "tickers": plan["tickers"], "price_lookback_days": plan["lookback_days"], "price_as_of_date": plan["as_of_date"],
        "price_repair_id": repair_id,
    }, daemon=True).start()
    return {"status": "accepted", "tickers": plan["tickers"], "repair_id": repair_id}


def _unavailable_market_admin_http_error(operation: str) -> HTTPException:
    from src.market_data_admin import unavailable_market_admin_result

    return HTTPException(
        status_code=409,
        detail=unavailable_market_admin_result(operation),
    )


def _unavailable_market_update_http_error() -> HTTPException:
    from src.market_data_admin import unavailable_price_update_result

    detail = unavailable_price_update_result("update_route")
    detail["code"] = "market_update_unavailable"
    return HTTPException(status_code=409, detail=detail)


class LocalMarketToggle(BaseModel):
    enabled: bool


@router.put("/market-data/settings")
def set_local_market(
    body: LocalMarketToggle,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Persist the local market-data preference."""
    require_profile_state_write("set_use_local_market", {"enabled": body.enabled})
    store.set_setting(USE_LOCAL_MARKET_KEY, "true" if body.enabled else "false")
    # The DAL reads this setting at construction and is an lru_cache singleton, so
    # drop it → the next request rebuilds the DAL with the new routing (no restart).
    from src.api.dependencies import get_dal

    get_dal.cache_clear()
    return {"use_local_market_setting": body.enabled}
