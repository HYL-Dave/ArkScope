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

from .dependencies import get_dal, get_registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup: warm up singletons
    dal = get_dal()
    registry = get_registry()
    logger.info(
        f"ArkScope API ready — "
        f"{len(registry.list_all())} tools, "
        f"{len(dal.get_available_tickers('prices'))} price tickers"
    )
    yield
    # Shutdown
    dal.clear_cache()
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
