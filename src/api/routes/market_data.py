"""
Market-data lifecycle routes (slice 3a.1) — local SQLite bootstrap/status/validate.

Reports and controls the local market_data.db authority. The old PG
bootstrap/update/validate mirror endpoints are fail-closed; active collection now
uses direct-local providers. Domains: prices, normalized news, IV/fundamentals
legacy inspection, and financial_cache (local-primary).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.dependencies import get_profile_store
from src.api.permissions import require_db_write, require_profile_state_write
from src.market_data_admin import (
    USE_LOCAL_MARKET_KEY,
    USE_LOCAL_MARKET_STRICT_KEY,
    env_routing_enabled,
    env_strict_enabled,
    get_job,
    local_market_stats,
    local_ticker_coverage,
    overlay_price_sync_retired,
    read_sync_meta,
    resolve_market_db_path,
    start_bootstrap_job,
    validate_market,
)
from src.market_data_direct import summarize_trading_day_coverage
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
    """Local market-data status (PURE READ; does not touch PG).

    Reports the local per-domain stats (prices + news + iv + fundamentals + the
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
        "iv": stats["iv"],
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


@router.get("/market-data/jobs/{job_id}")
def market_data_job(job_id: str):
    """Poll a market-data background job (e.g. bootstrap).

    When a bootstrap finishes successfully the market DB has just appeared/changed,
    so we drop the lru_cache'd DAL → the next read re-evaluates routing (covers the
    enable-before-build order without a restart). Idempotent; the client stops
    polling at done, so this fires ~once.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("kind") == "bootstrap_market" and job.get("status") == "done":
        from src.api.dependencies import get_dal

        get_dal.cache_clear()
    return job


@router.get("/market-data/coverage/{ticker}")
def market_data_coverage(ticker: str):
    """Per-domain LOCAL coverage for ``ticker`` (PURE READ; routing-independent).

    Reports whether the local market DB actually holds rows for this ticker in each
    domain — a fact about the local DB, NOT a claim about where a given read was
    served (per-call local-vs-PG provenance is a separate future signal). Powers the
    detail page's honest "本地覆蓋：有/無" hint.
    """
    return local_ticker_coverage(ticker)


@router.get("/market-data/trading-days")
def market_data_trading_days(
    lookback_days: int = Query(10, ge=1, le=120),
    interval: str = Query("15min"),
):
    """READ-ONLY trading-day / price-coverage diagnostics across the active universe.

    For the trailing window: weekend / US-holiday / trading-day per date, session-complete,
    and how many universe tickers are full / partial / missing (+ the ticker lists), plus a
    provider-error summary (e.g. an IBKR contract that won't resolve). PURE READ of
    ``market_data.db`` — no PG, no provider call, no write, no scheduling. Powers the
    Settings → Data Storage coverage panel.
    """
    from src.active_universe import ActiveUniverseUnavailable
    from src.universe_scope import resolve_active_universe

    try:
        universe = list(resolve_active_universe())
    except ActiveUniverseUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.as_dict()) from None
    return summarize_trading_day_coverage(
        universe, interval=interval, lookback_days=lookback_days,
        db_path=resolve_market_db_path(),
    )


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
