"""News routes."""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.news_tools import (
    get_ticker_news,
    get_news_sentiment_summary,
    search_news_by_keyword,
)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/{ticker}")
def news_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    source: str = Query("auto", pattern="^(auto|ibkr|polygon)$"),
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