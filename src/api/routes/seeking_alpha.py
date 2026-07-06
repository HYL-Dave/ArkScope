"""Seeking Alpha read-only routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from src.agents.config import get_agent_config
from src.api.dependencies import get_dal
from src.service.sa_extension_health import collect_sa_extension_health
from src.service.sa_market_news_health import compute_market_news_health
from src.tools.sa_tools import (
    _DISABLED_MSG,
    get_sa_alpha_picks,
    get_sa_article_detail,
    get_sa_articles,
    get_sa_feed,
    get_sa_market_news,
    get_sa_pick_detail,
)

router = APIRouter(prefix="/sa", tags=["seeking-alpha"])


def _unwrap_sa_result(result: dict) -> dict:
    """Translate tool-style SA responses into explicit HTTP semantics."""
    message = result.get("message")
    if message == _DISABLED_MSG:
        raise HTTPException(status_code=503, detail=message)

    error = result.get("error")
    if error not in (None, ""):
        text = str(error)
        if "not found" in text.lower():
            raise HTTPException(status_code=404, detail=text)
        raise HTTPException(status_code=500, detail=text)
    return result


@router.get("/feed")
def sa_feed(
    q: Optional[str] = Query(None, description="search terms (FTS5; short/symbol → LIKE)"),
    ticker: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None, pattern="^(article|market_news)$"),
    days: int = Query(30, ge=1, le=3650),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    dal=Depends(get_dal),
):
    """Unified Seeking Alpha evidence feed (articles + market news) for the 新聞·事件
    surface — newest first, paginated, with total + per-type/per-day facets over the
    same filters. Degraded states (e.g. SA not local-first) return available=False
    with an empty_reason, NOT an HTTP error — only the feature-disabled case is 503.
    """
    result = get_sa_feed(dal, q=q, ticker=ticker, item_type=item_type,
                         days=days, limit=limit, offset=offset)
    if result.get("message") == _DISABLED_MSG:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.get("/alpha-picks")
def alpha_picks(
    status: str = Query("all", pattern="^(all|current|closed)$"),
    sector: Optional[str] = Query(None),
    dal=Depends(get_dal),
):
    """Read cached Alpha Picks portfolio data from the backend."""
    return _unwrap_sa_result(get_sa_alpha_picks(dal, status=status, sector=sector))


@router.get("/picks/{symbol}")
def alpha_pick_detail(
    symbol: str,
    picked_date: Optional[str] = Query(None),
    dal=Depends(get_dal),
):
    """Read one cached Alpha Picks detail report."""
    return _unwrap_sa_result(get_sa_pick_detail(dal, symbol=symbol, picked_date=picked_date))


@router.get("/articles")
def alpha_pick_articles(
    ticker: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, min_length=1),
    article_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    dal=Depends(get_dal),
):
    """Search cached Alpha Picks articles."""
    return _unwrap_sa_result(
        get_sa_articles(
            dal,
            ticker=ticker,
            keyword=keyword,
            article_type=article_type,
            limit=limit,
        )
    )


@router.get("/articles/{article_id}")
def alpha_pick_article_detail(
    article_id: str,
    dal=Depends(get_dal),
):
    """Read one cached Alpha Picks article body plus comments."""
    return _unwrap_sa_result(get_sa_article_detail(dal, article_id))


@router.get("/market-news")
def market_news(
    ticker: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, min_length=1),
    limit: int = Query(20, ge=1, le=100),
    dal=Depends(get_dal),
):
    """Read cached Seeking Alpha market-news items."""
    return _unwrap_sa_result(
        get_sa_market_news(dal, ticker=ticker, keyword=keyword, limit=limit)
    )


@router.get("/market-news/health")
def market_news_health(
    response: Response,
    strict: bool = Query(False, description="Return 503 when severity != ok."),
    dal=Depends(get_dal),
):
    """Return SA market-news pipeline health (P0.4).

    Three layers reported separately so callers can tell pipeline staleness
    from feed-content lulls from detail-body gaps:

      - ``freshness``     last fetch / latest published age
      - ``feed_health``   rows in 24h / 7d
      - ``detail_health`` 7d body completeness

    Severity ladder: ``ok`` / ``warning`` / ``critical``. Default returns
    200 with the structured payload regardless. ``?strict=true`` upgrades
    any non-``ok`` severity to HTTP 503 for healthcheck-style probes.
    """
    if not get_agent_config().sa_enabled:
        raise HTTPException(status_code=503, detail=_DISABLED_MSG)

    report = compute_market_news_health(dal)
    if strict and report.get("severity") != "ok":
        response.status_code = 503
    return report


@router.get("/extension-health")
def sa_extension_health(dal=Depends(get_dal)):
    """Return the local SA extension/native-host setup checklist."""
    try:
        return collect_sa_extension_health(dal=dal)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "sa_extension_health_unavailable",
                "message": str(exc),
            },
        ) from exc
