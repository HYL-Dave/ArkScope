"""Market-data status, coverage, review, and fail-closed admin routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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
    lookback_days: int = Query(10, ge=1, le=120),
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
