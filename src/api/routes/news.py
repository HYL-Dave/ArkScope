"""News read routes plus direct-local ingest routing settings."""

import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from src.api.dependencies import get_dal, get_profile_store
from src.api.permissions import require_profile_state_write
from src.market_data_admin import local_market_stats, resolve_market_db_path
from src.news_content_availability import ContentFilter
from src.news_providers import (
    ENV_USE_LOCAL_NEWS,
    USE_LOCAL_NEWS_KEY,
    parse_news_toggle,
    resolve_use_local_news,
)
from src.news_normalized.routing import (
    ENV_USE_NORMALIZED_NEWS_WRITES,
    NEWS_PG_EXIT_COMPLETED_KEY,
    USE_NORMALIZED_NEWS_WRITES_KEY,
    resolve_news_write_route,
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


class NormalizedNewsWritesToggle(BaseModel):
    enabled: bool


def _news_pg_exit_audit_completed(db_path: str) -> bool:
    """Read the market DB audit marker without creating or mutating it."""
    path = Path(db_path)
    if not path.exists():
        return False
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                ("news_pg_exit_runs",),
            ).fetchone()
            if not exists:
                return False
            row = conn.execute(
                "SELECT 1 FROM news_pg_exit_runs WHERE status = 'completed' LIMIT 1"
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def _news_pg_exit_completed(store: ProfileStateStore, market_db: str) -> bool:
    profile_value = parse_news_toggle(store.get_setting(NEWS_PG_EXIT_COMPLETED_KEY))
    return profile_value is True or _news_pg_exit_audit_completed(market_db)


def _reject_pg_retired_setting() -> None:
    raise HTTPException(
        status_code=409,
        detail="PG news route is retired after exit; this setting cannot select PG.",
    )


@router.get("/status")
def news_status(store: ProfileStateStore = Depends(get_profile_store)):
    """Read direct-news routing, local coverage, and telemetry without writes."""
    path = resolve_market_db_path()
    stats = local_market_stats(path)
    profile_value = store.get_setting(USE_LOCAL_NEWS_KEY)
    env_raw = os.environ.get(ENV_USE_LOCAL_NEWS)
    env_value = parse_news_toggle(env_raw)
    normalized_profile_value = store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY)
    normalized_setting = parse_news_toggle(normalized_profile_value)
    normalized_env_raw = os.environ.get(ENV_USE_NORMALIZED_NEWS_WRITES)
    normalized_env_value = parse_news_toggle(normalized_env_raw)
    exit_profile_value = store.get_setting(NEWS_PG_EXIT_COMPLETED_KEY)
    audit_exit_completed = _news_pg_exit_audit_completed(path)
    news_pg_exit_completed = (
        parse_news_toggle(exit_profile_value) is True or audit_exit_completed
    )
    route_exit_value = True if audit_exit_completed else exit_profile_value
    write_route = resolve_news_write_route(
        exit_completed=route_exit_value,
        normalized_value=normalized_profile_value,
        local_value=profile_value,
        normalized_env=normalized_env_raw,
        local_env=env_raw,
    )
    return {
        "market_db": path,
        "exists": stats["exists"],
        "news": stats["news"],
        "use_local_news_setting": resolve_use_local_news(profile_value),
        "setting_explicit": parse_news_toggle(profile_value) is not None,
        "env_override": env_value is not None,
        "env_value": env_value,
        "direct_active": resolve_use_local_news(profile_value, env_raw),
        "normalized_writes_setting": normalized_setting is True,
        "normalized_writes_setting_explicit": normalized_setting is not None,
        "normalized_writes_env_override": normalized_env_value is not None,
        "normalized_writes_env_value": normalized_env_value,
        "write_route": write_route.mode.value,
        "write_route_reason": write_route.reason,
        "news_pg_exit_completed": news_pg_exit_completed,
        "news_hard_local": news_pg_exit_completed,
        "pg_news_route_available": not news_pg_exit_completed,
        "sync": read_news_sync_status(path),
    }


@router.put("/settings")
def set_local_news(
    body: LocalNewsToggle,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Persist the explicit direct-local routing value; scheduler reads it live."""
    if not body.enabled and _news_pg_exit_completed(store, resolve_market_db_path()):
        _reject_pg_retired_setting()
    require_profile_state_write("set_use_local_news", {"enabled": body.enabled})
    store.set_setting(USE_LOCAL_NEWS_KEY, "true" if body.enabled else "false")
    return {"use_local_news_setting": body.enabled}


@router.put("/settings/normalized-writes")
def set_normalized_news_writes(
    body: NormalizedNewsWritesToggle,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Persist normalized-writer routing unless the PG route has been retired."""
    if not body.enabled and _news_pg_exit_completed(store, resolve_market_db_path()):
        _reject_pg_retired_setting()
    require_profile_state_write("set_normalized_news_writes", {"enabled": body.enabled})
    store.set_setting(
        USE_NORMALIZED_NEWS_WRITES_KEY,
        "true" if body.enabled else "false",
    )
    return {"normalized_writes_setting": body.enabled}


@router.get("/feed")
def news_feed(
    q: Optional[str] = Query(None, description="search terms (AND of tokens)"),
    ticker: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(auto|ibkr|polygon|finnhub)$"),
    content: ContentFilter = Query("all"),
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
    return dal.get_news_feed(
        q=q,
        ticker=ticker,
        source=source,
        content=content,
        days=days,
        limit=limit,
        offset=offset,
    )


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
