"""
FastAPI application factory for ArkScope.

Usage:
    uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8420
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .dependencies import get_dal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Keep startup cheap. The desktop shell polls /healthz while launching; that
    # readiness path must not depend on DB availability or expensive data scans.
    # The data scheduler is a single asyncio task that is near-free while every
    # source is disabled (the default) — it must be IN-PROCESS (the app owns
    # scheduling; single-sidecar locks like _CACHE_WRITE_LOCK assume one process).
    import asyncio

    from src.service.data_scheduler import (
        reconcile_interrupted_runtime_state,
        scheduler_loop,
    )
    from src.portfolio_capture_scheduler import portfolio_capture_scheduler_loop

    # Apply app-managed provider keys / IBKR host+port into os.environ BEFORE the
    # scheduler exists: the sidecar is the parent of every collector subprocess, so
    # one injection here reaches all call sites (in-process getenv + children).
    provider_config_ready = True
    try:
        from src.data_provider_config import apply_env
        from src.provider_config_runtime import clear_provider_config_setup_required

        from .dependencies import get_data_provider_store

        apply_env(get_data_provider_store())
        clear_provider_config_setup_required()
    except Exception as e:  # noqa: BLE001 — setup-only, never silent pure-.env runtime
        from src.provider_config_runtime import mark_provider_config_setup_required

        provider_config_ready = False
        mark_provider_config_setup_required(str(e))
        logger.warning("data-provider env bridge failed; booting setup-only: %s", e)
    try:
        reconcile_interrupted_runtime_state()
    except Exception as e:  # noqa: BLE001 — stale telemetry repair must not block startup
        logger.debug("interrupted scheduler/provider reconciliation failed: %s", e)

    # Test hygiene: TestClient(create_app()) runs this lifespan, and the scheduler's
    # seed/tick threads reach the real PG/network — tests/conftest.py disables it so
    # unit tests stay hermetic (a stalled seed thread otherwise hangs pytest at the
    # executor's atexit join in PG-less environments).
    scheduler_enabled = (
        os.environ.get("ARKSCOPE_DISABLE_SCHEDULER", "").strip().lower()
        not in ("1", "true", "yes", "on")
    )
    capture_service = None
    portfolio_sched_task = None
    if provider_config_ready:
        from .dependencies import get_portfolio_capture_service

        capture_service = get_portfolio_capture_service()
        capture_service.reconcile_startup()

    sched_task = None
    if provider_config_ready and scheduler_enabled:
        sched_task = asyncio.create_task(scheduler_loop(), name="data-scheduler")
        portfolio_sched_task = asyncio.create_task(
            portfolio_capture_scheduler_loop(capture_service),
            name="portfolio-capture-scheduler",
        )
    elif not provider_config_ready:
        logger.warning("data scheduler disabled: provider config setup required")
    else:
        logger.info("data scheduler disabled via ARKSCOPE_DISABLE_SCHEDULER")
    logger.info("ArkScope API ready — DAL and registry initialize lazily")
    yield
    # Shutdown
    scheduler_tasks = tuple(
        task for task in (sched_task, portfolio_sched_task) if task is not None
    )
    for task in scheduler_tasks:
        task.cancel()
    for task in scheduler_tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 — shutdown best-effort
            pass
    if get_dal.cache_info().currsize:
        get_dal().clear_cache()
    logger.info("ArkScope API shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="ArkScope API",
        description="Data access and analysis API for ArkScope",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Register all route modules
    from .routes.news import router as news_router
    from .routes.prices import router as prices_router
    from .routes.options import router as options_router
    from .routes.signals import router as signals_router
    from .routes.scan import router as scan_router
    from .routes.fundamentals import router as fundamentals_router
    from .routes.config_routes import router as config_router
    from .routes.health import router as health_router
    from .routes.query import router as query_router
    from .routes.analysis import router as analysis_router
    from .routes.jobs import router as jobs_router
    from .routes.seeking_alpha import router as seeking_alpha_router
    from .routes.reports import router as reports_router
    from .routes.macro_calendar import router as macro_calendar_router
    from .routes.profile import router as profile_router
    from .routes.investor_profile import router as investor_profile_router
    from .routes.investor_profile_calibration import router as investor_profile_calibration_router
    from .routes.analysis_cards import router as analysis_cards_router
    from .routes.symbols import router as symbols_router
    from .routes.consensus import router as consensus_router
    from .routes.market_data import router as market_data_router
    from .routes.schedule import router as schedule_router
    from .routes.providers_config import router as providers_config_router
    from .routes.research import router as research_router
    from .routes.app_records import router as app_records_router
    from .routes.portfolio import router as portfolio_router
    from .routes.portfolio_capture import router as portfolio_capture_router

    app.include_router(news_router)
    app.include_router(prices_router)
    app.include_router(options_router)
    app.include_router(signals_router)
    app.include_router(scan_router)
    app.include_router(fundamentals_router)
    app.include_router(config_router)
    app.include_router(health_router)
    app.include_router(query_router)
    app.include_router(analysis_router)
    app.include_router(jobs_router)
    app.include_router(seeking_alpha_router)
    app.include_router(reports_router)
    app.include_router(macro_calendar_router)
    app.include_router(profile_router)
    app.include_router(investor_profile_router)
    app.include_router(investor_profile_calibration_router)
    app.include_router(analysis_cards_router)
    app.include_router(symbols_router)
    app.include_router(consensus_router)
    app.include_router(market_data_router)
    app.include_router(schedule_router)
    app.include_router(providers_config_router)
    app.include_router(research_router)
    app.include_router(app_records_router)
    app.include_router(portfolio_router)
    app.include_router(portfolio_capture_router)

    # --- Desktop-shell sidecar hardening (opt-in; no effect on existing flows) ---
    # Optional localhost token, enforced ONLY when ARKSCOPE_API_TOKEN is set (the
    # Electron shell sets a per-run token). Unset = existing dev/test behaviour,
    # unchanged. Exemptions:
    #   - /healthz stays open so readiness probing needs no token.
    #   - OPTIONS (CORS preflight) is never token-checked: browsers send no
    #     custom headers on preflight, so gating it would 401 the preflight and
    #     break every cross-origin renderer fetch ("Failed to fetch").
    @app.middleware("http")
    async def _token_guard(request: Request, call_next):
        token = os.environ.get("ARKSCOPE_API_TOKEN")
        if token and request.method != "OPTIONS" and request.url.path != "/healthz":
            if request.headers.get("x-arkscope-token") != token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "invalid or missing API token"},
                )
        return await call_next(request)

    # CORS is added LAST so it is the OUTERMOST middleware (Starlette applies the
    # most-recently-added middleware first). That lets it answer the preflight
    # and stamp Access-Control-Allow-Origin on every response — including the
    # token guard's 401. The API is local-only (127.0.0.1) and token-gated under
    # the shell, so permissive CORS is acceptable for the desktop renderer / Vite
    # dev origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app
