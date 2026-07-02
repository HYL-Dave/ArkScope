"""Health and status routes."""

from datetime import datetime

from fastapi import APIRouter, Depends

from src.api.dependencies import get_dal, get_registry
from src.tools.data_access import DataAccessLayer
from src.tools.registry import ToolRegistry

router = APIRouter(tags=["system"])


@router.get("/healthz")
def healthz():
    """Cheap liveness probe for sidecar readiness.

    No DAL, no registry, no agent — safe to poll at high frequency while the
    desktop shell waits for the spawned sidecar to come up. The richer /status
    payload (which touches the DAL) is the dashboard, not the readiness probe.
    """
    return {"status": "ok"}


@router.get("/providers/health")
def providers_health(dal: DataAccessLayer = Depends(get_dal)):
    """Per-provider health (slice 3e-A) — PURE READ, no provider fetches.

    Aggregates every persisted health signal (news/prices/iv freshness,
    financial_cache stats, sa_refresh_meta, job_runs, market_sync_meta) into one
    ProviderRun-compatible DTO per provider with a unified status vocabulary
    (connected | stale | maintenance | no_signal | missing_key | disabled).
    Disabled-by-config is a state in the body, never a 503. Key info is
    presence + source only (read-only; values stay masked, file-backed values
    are import-suggested through Settings).
    """
    from src.service.provider_health import compute_provider_health

    return compute_provider_health(dal)


@router.get("/status")
def status(
    dal: DataAccessLayer = Depends(get_dal),
    registry: ToolRegistry = Depends(get_registry),
):
    """Health check and system status."""
    from src.provider_config_runtime import provider_config_setup_state

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "provider_config": provider_config_setup_state().as_dict(),
        "tools_registered": len(registry.list_all()),
        "tool_categories": {
            cat: len(registry.list_by_category(cat))
            for cat in ["news", "prices", "options", "signals", "analysis"]
        },
        "data_sources": {
            "news_tickers": len(dal.get_available_tickers("news")),
            "price_tickers": len(dal.get_available_tickers("prices")),
            "iv_tickers": len(dal.get_available_tickers("iv_history")),
            "fundamentals_tickers": len(dal.get_available_tickers("fundamentals")),
        },
    }
