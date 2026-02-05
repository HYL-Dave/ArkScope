"""
FastAPI application factory for MindfulRL.

Usage:
    uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8420
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .dependencies import get_dal, get_registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup: warm up singletons
    dal = get_dal()
    registry = get_registry()
    logger.info(
        f"MindfulRL API ready — "
        f"{len(registry.list_all())} tools, "
        f"{len(dal.get_available_tickers('prices'))} price tickers"
    )
    yield
    # Shutdown
    dal.clear_cache()
    logger.info("MindfulRL API shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="MindfulRL API",
        description="Data access and analysis API for MindfulRL-Intraday",
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

    app.include_router(news_router)
    app.include_router(prices_router)
    app.include_router(options_router)
    app.include_router(signals_router)
    app.include_router(scan_router)
    app.include_router(fundamentals_router)
    app.include_router(config_router)
    app.include_router(health_router)
    app.include_router(query_router)

    return app