"""News read routes plus direct-local ingest routing settings."""

import os

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional

from src.api.dependencies import get_dal, get_profile_store
from src.api.permissions import require_profile_state_write
from src.market_data_admin import local_market_stats, resolve_market_db_path
from src.news_providers import (
    ENV_USE_LOCAL_NEWS,
    USE_LOCAL_NEWS_KEY,
    parse_news_toggle,
    resolve_use_local_news,
)
from src.news_sync_status import read_news_sync_status
from src.profile_state import ProfileStateStore
from src.tools.data_access import DataAccessLayer
from src.tools.news_tools import (
    get_ticker_news,
    get_news_sentiment_summary,
    search_news_by_keyword,
)

router = APIRouter(prefix="/news", tags=["news"])


class LocalNewsToggle(BaseModel):
    enabled: bool


@router.get("/status")
def news_status(store: ProfileStateStore = Depends(get_profile_store)):
    """Read direct-news routing, local coverage, and telemetry without writes."""
    path = resolve_market_db_path()
    stats = local_market_stats(path)
    profile_value = store.get_setting(USE_LOCAL_NEWS_KEY)
    env_raw = os.environ.get(ENV_USE_LOCAL_NEWS)
    env_value = parse_news_toggle(env_raw)
    return {
        "market_db": path,
        "exists": stats["exists"],
        "news": stats["news"],
        "use_local_news_setting": resolve_use_local_news(profile_value),
        "setting_explicit": parse_news_toggle(profile_value) is not None,
        "env_override": env_value is not None,
        "env_value": env_value,
        "direct_active": resolve_use_local_news(profile_value, env_raw),
        "sync": read_news_sync_status(path),
    }


@router.put("/settings")
def set_local_news(
    body: LocalNewsToggle,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Persist the explicit direct-local routing value; scheduler reads it live."""
    require_profile_state_write("set_use_local_news", {"enabled": body.enabled})
    store.set_setting(USE_LOCAL_NEWS_KEY, "true" if body.enabled else "false")
    return {"use_local_news_setting": body.enabled}


@router.get("/feed")
def news_feed(
    q: Optional[str] = Query(None, description="search terms (AND of tokens)"),
    ticker: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(auto|ibkr|polygon|finnhub)$"),
    days: int = Query(30, ge=1, le=3650),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Score-free news feed for the 新聞·事件 surface (local-first; full
    published_at timestamps, newest first, paginated, with total / per-source /
    per-day facets over the same filters). NOTE: declared before /{ticker} —
    /news/feed must not be captured as ticker='feed'.
    """
    return dal.get_news_feed(q=q, ticker=ticker, source=source, days=days,
                             limit=limit, offset=offset)


@router.get("/{ticker}")
def news_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    source: str = Query("auto", pattern="^(auto|ibkr|polygon|finnhub)$"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get recent news articles for a ticker."""
    result = get_ticker_news(dal, ticker=ticker, days=days, source=source)
    return result.model_dump()


@router.get("/{ticker}/sentiment")
def news_sentiment(
    ticker: str,
    days: int = Query(7, ge=1, le=9999),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get aggregated sentiment statistics for a ticker."""
    return get_news_sentiment_summary(dal, ticker=ticker, days=days)


@router.get("/search/keyword")
def news_search(
    keyword: str = Query(..., min_length=1),
    days: int = Query(30, ge=1, le=9999),
    ticker: Optional[str] = Query(None),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Search news articles by keyword in titles and descriptions."""
    result = search_news_by_keyword(dal, keyword=keyword, days=days, ticker=ticker)
    return result.model_dump()
