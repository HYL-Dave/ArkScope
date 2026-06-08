"""
Market-data lifecycle routes (slice 3a.1) — local SQLite bootstrap/status/validate.

Productizes the PG → local market_data.db migration so the desktop app owns it
(no CLI required): status, a background bootstrap job the UI can poll, validation,
and a persisted "use local market" toggle (stored in profile_settings, read by the
DAL at construction). Slice 3a.1 = PRICES only. See
``docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md`` §8.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_profile_store
from src.api.permissions import require_db_write, require_profile_state_write
from src.market_data_admin import (
    USE_LOCAL_MARKET_KEY,
    env_routing_enabled,
    get_job,
    local_prices_stats,
    resolve_market_db_path,
    start_bootstrap_job,
    validate_prices,
)
from src.profile_state import ProfileStateStore

router = APIRouter(tags=["market-data"])

_TRUTHY = ("1", "true", "yes", "on")


def _setting_enabled(store: ProfileStateStore) -> bool:
    return (store.get_setting(USE_LOCAL_MARKET_KEY) or "").strip().lower() in _TRUTHY


@router.get("/market-data/status")
def market_data_status(store: ProfileStateStore = Depends(get_profile_store)):
    """Local market-data status (PURE READ; does not touch PG).

    Reports the local prices DB stats, whether routing is enabled (persisted
    setting or env override), and whether PG fallback is therefore active.
    """
    path = resolve_market_db_path()
    stats = local_prices_stats(path)
    setting_on = _setting_enabled(store)
    env_on = env_routing_enabled()
    # Routing only actually engages when enabled AND the DB exists (DAL guards this).
    routing_enabled = (setting_on or env_on) and stats["exists"]
    return {
        "market_db": path,
        "prices": stats,
        "use_local_market_setting": setting_on,
        "env_override": env_on,
        "routing_enabled": routing_enabled,
        # local-first routing always falls back to PG on a local miss/empty
        "pg_fallback_active": routing_enabled,
    }


@router.post("/market-data/bootstrap-prices")
def bootstrap_prices_route():
    """Start (or attach to) a background full rebuild of the local prices DB.

    Returns the job; poll ``GET /market-data/jobs/{id}`` for progress. Idempotent
    while running. The rebuild validates before atomically swapping in, so a
    failure never destroys an existing good DB.
    """
    require_db_write("market_bootstrap_prices", {"db": resolve_market_db_path()})
    return start_bootstrap_job()


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
    if job.get("kind") == "bootstrap_prices" and job.get("status") == "done":
        from src.api.dependencies import get_dal

        get_dal.cache_clear()
    return job


@router.post("/market-data/validate")
def validate_route():
    """Validate the local prices DB against PG (row count + per-group checksum)."""
    return validate_prices()


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
