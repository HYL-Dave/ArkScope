"""Health and status routes."""

from datetime import datetime

from fastapi import APIRouter, Depends

from src.api.dependencies import get_dal, get_registry
from src.tools.data_access import DataAccessLayer
from src.tools.registry import ToolRegistry

router = APIRouter(tags=["system"])


@router.get("/status")
def status(
    dal: DataAccessLayer = Depends(get_dal),
    registry: ToolRegistry = Depends(get_registry),
):
    """Health check and system status."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
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