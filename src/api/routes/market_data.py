"""
Market-data lifecycle routes (slice 3a.1) — local SQLite bootstrap/status/validate.

Reports and controls the local market_data.db authority. The old PG
bootstrap/update/validate mirror endpoints are fail-closed; active collection now
uses direct-local providers.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
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
    overlay_price_sync_retired,
    read_sync_meta,
    resolve_market_db_path,
)
from src.market_coverage.models import TradingDayCoverageV2
from src.market_coverage.service import TradingDayCoverageService
from src.news_sync_status import overlay_news_sync_status
from src.profile_state import ProfileStateStore
from src.security_lifecycle import SecurityLifecycleStore, read_security_lifecycle

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
    """Local market-data status (PURE READ; does not touch PG).

    Reports the local per-domain stats (prices + news + fundamentals + the
    local-primary financial_cache). Post-PG-exit local authority is the default:
    the legacy persisted/env routing fields are exposed for provenance only, not
    as live PG fallback controls.
    """
    path = resolve_market_db_path()
    stats = local_market_stats(path)
    setting_on = _setting_enabled(store)
    env_on = env_routing_enabled()
    strict_setting_on = _strict_setting_enabled(store)
    strict_env_on = env_strict_enabled()
    # Local authority is the post-PG-exit default even before the DB file exists.
    # The SQLite layer returns honest-empty rows until ingestion creates it.
    routing_enabled = True
    strict_enabled = True
    sync = overlay_price_sync_retired(overlay_news_sync_status(read_sync_meta(path), path))
    return {
        "market_db": path,
        "exists": stats["exists"],
        "prices": stats["prices"],
        "prices_authority": "local",
        "price_mirror_retired": True,
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
        "pg_fallback_active": False,
    }


@router.post("/market-data/bootstrap")
def bootstrap_route():
    """Reject the retired all-domain PG mirror rebuild path.

    N9 batch-1 retires the old PG ``news``/``iv_history``/``fundamentals`` mirror
    tables. Prices migration is a separate PG-exit slice, so this route must not
    start the legacy all-domain bootstrap.
    """
    require_db_write("market_bootstrap", {"db": resolve_market_db_path()})
    raise _retired_market_mirror_http_error("bootstrap_route")


@router.post("/market-data/update")
def update_route(store: ProfileStateStore = Depends(get_profile_store)):
    """Reject the retired PG incremental mirror path.

    P0-C routes scheduled price collection through the direct-local IBKR writer.
    The legacy manual update endpoint used the PG mirror path, so it must fail
    closed instead of creating a background mirror job.
    """
    require_db_write("market_update", {"db": resolve_market_db_path()})
    _manual_update_domains(store)
    raise _retired_market_update_http_error()


@router.get("/market-data/coverage/{ticker}")
def market_data_coverage(ticker: str):
    """Per-domain LOCAL coverage for ``ticker`` (PURE READ; routing-independent).

    Reports whether the local market DB actually holds rows for this ticker in each
    domain — a fact about the local DB, NOT a claim about where a given read was
    served (per-call local-vs-PG provenance is a separate future signal). Powers the
    detail page's honest "本地覆蓋：有/無" hint.
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


@router.get("/market-data/security-lifecycle")
def security_lifecycle_status(
    limit: int = Query(200, ge=1, le=1000),
):
    """Return local SEC/exchange lifecycle evidence without provider work."""
    return read_security_lifecycle(resolve_market_db_path(), limit=limit)


class CorporateRelationshipReview(BaseModel):
    status: Literal["confirmed", "rejected"]


@router.put("/market-data/security-lifecycle/relationships/{relationship_id}")
def review_corporate_relationship(
    relationship_id: int,
    body: CorporateRelationshipReview,
):
    """Persist an explicit human review; never changes active-universe membership."""
    payload = {"relationship_id": relationship_id, "status": body.status}
    require_db_write("review_corporate_relationship", payload)
    db_path = resolve_market_db_path()
    if not Path(db_path).is_file():
        raise HTTPException(status_code=404, detail="relationship_not_found")
    from datetime import datetime, timezone
    from src.market_data_direct import market_write_lock

    reviewed_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    with market_write_lock():
        conn = sqlite3.connect(db_path, timeout=10.0)
        try:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='corporate_action_relationships'"
            ).fetchone()
            if table_exists is None:
                raise HTTPException(status_code=404, detail="relationship_not_found")
            SecurityLifecycleStore(conn).review_relationship(
                relationship_id,
                status=body.status,
                reviewed_at=reviewed_at,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="relationship_not_found") from None
        finally:
            conn.close()
    return {"id": relationship_id, "status": body.status}


@router.post("/market-data/validate")
def validate_route():
    """Reject the retired all-domain PG mirror validation path."""
    require_db_write("market_validate", {"db": resolve_market_db_path()})
    raise _retired_market_mirror_http_error("validate_route")


def _retired_market_mirror_http_error(operation: str) -> HTTPException:
    from src.market_data_admin import retired_market_mirror_result

    return HTTPException(
        status_code=409,
        detail=retired_market_mirror_result(operation),
    )


def _retired_market_update_http_error() -> HTTPException:
    from src.market_data_admin import retired_price_mirror_result

    detail = retired_price_mirror_result("update_route")
    detail["code"] = "pg_market_update_retired"
    return HTTPException(status_code=409, detail=detail)


class LocalMarketToggle(BaseModel):
    enabled: bool


@router.put("/market-data/settings")
def set_local_market(
    body: LocalMarketToggle,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Persist the "use local market data" toggle (read by the DAL at startup).

    Note: routing only engages once ``market_data.db`` exists — enabling the
    toggle without a bootstrap simply keeps PG (status reflects that).
    """
    require_profile_state_write("set_use_local_market", {"enabled": body.enabled})
    store.set_setting(USE_LOCAL_MARKET_KEY, "true" if body.enabled else "false")
    # The DAL reads this setting at construction and is an lru_cache singleton, so
    # drop it → the next request rebuilds the DAL with the new routing (no restart).
    from src.api.dependencies import get_dal

    get_dal.cache_clear()
    return {"use_local_market_setting": body.enabled}
