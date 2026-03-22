"""
Seeking Alpha Alpha Picks tool functions.

5 tools: get_sa_alpha_picks, get_sa_pick_detail, refresh_sa_alpha_picks,
         get_sa_articles, get_sa_article_detail
All require DAL, category="portfolio".
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DISABLED_MSG = (
    "Seeking Alpha Alpha Picks is not enabled. "
    "To enable: set seeking_alpha.enabled: true in config/user_profile.yaml "
    "and install the SA Alpha Picks Chrome extension (see extensions/sa_alpha_picks/)"
)


def _is_sa_enabled() -> bool:
    """Check if SA Alpha Picks is enabled in config."""
    try:
        from src.agents.config import get_agent_config
        return get_agent_config().sa_enabled
    except Exception:
        return False


def _get_client(dal):
    """Create SAAlphaPicksClient with config values."""
    from src.agents.config import get_agent_config
    from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

    config = get_agent_config()
    return SAAlphaPicksClient(
        dal=dal,
        cache_hours=config.sa_cache_hours,
        detail_cache_days=config.sa_detail_cache_days,
    )


def get_sa_alpha_picks(
    dal: Any, status: str = "all", sector: Optional[str] = None
) -> Dict:
    """Get SA Alpha Picks portfolio (cached, auto-refresh if stale).

    Returns current and/or closed picks with freshness metadata.
    is_partial = not (freshness.current.ok and freshness.closed.ok).
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        client = _get_client(dal)
        result = client.get_portfolio()

        if "error" in result and result["error"]:
            return result

        # Filter by status
        response = {}
        if status in ("all", "current"):
            response["current"] = result.get("current", [])
        if status in ("all", "closed"):
            response["closed"] = result.get("closed", [])

        # Filter by sector if specified
        if sector:
            sector_lower = sector.lower()
            for key in ("current", "closed"):
                if key in response:
                    response[key] = [
                        p for p in response[key]
                        if (p.get("sector") or "").lower().startswith(sector_lower)
                    ]

        response["freshness"] = result.get("freshness", {})
        response["is_partial"] = result.get("is_partial", False)
        if result.get("stale_warning"):
            response["stale_warning"] = result["stale_warning"]
        if result.get("refresh_hint"):
            response["refresh_hint"] = result["refresh_hint"]
        return response

    except Exception as e:
        logger.error("get_sa_alpha_picks error: %s", e)
        return {"error": str(e)}


def get_sa_pick_detail(
    dal: Any, symbol: str, picked_date: Optional[str] = None
) -> Dict:
    """Get detail for a specific Alpha Pick.

    picked_date=None: latest current (non-stale first), then stale, then hint.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        client = _get_client(dal)
        result = client.get_pick_detail(symbol, picked_date)

        if result is None:
            # Check if symbol exists in closed
            closed = dal.get_sa_portfolio(portfolio_status="closed", symbol=symbol)
            if closed:
                latest = sorted(closed, key=lambda x: x.get("picked_date", ""), reverse=True)[0]
                return {
                    "error": None,
                    "detail": None,
                    "hint": (
                        f"{symbol} is not in current Alpha Picks. "
                        f"It was picked on {latest.get('picked_date', '?')} (now closed). "
                        f"Use: /ap {symbol} {latest.get('picked_date', '')}"
                    ),
                }
            return {"error": f"{symbol} not found in Alpha Picks"}

        return result

    except Exception as e:
        logger.error("get_sa_pick_detail error: %s", e)
        return {"error": str(e)}


def refresh_sa_alpha_picks(dal: Any) -> Dict:
    """Return current SA data state + refresh instructions.

    Actual refresh is done by the Chrome extension. This returns cached data
    with a refresh_hint directing the user to click the extension.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        client = _get_client(dal)
        return client.refresh_portfolio(sync_tickers=True)
    except Exception as e:
        logger.error("refresh_sa_alpha_picks error: %s", e)
        return {"error": str(e)}


def get_sa_articles(
    dal: Any,
    ticker: Optional[str] = None,
    keyword: Optional[str] = None,
    article_type: Optional[str] = None,
    limit: int = 10,
) -> Dict:
    """Search SA Alpha Picks articles.

    Returns article list with title, date, ticker, type, comments_count.
    Use get_sa_article_detail for full content + comments.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        articles = dal.get_sa_articles(
            ticker=ticker, keyword=keyword,
            article_type=article_type, limit=limit,
        )
        return {"articles": articles, "count": len(articles)}
    except Exception as e:
        logger.error("get_sa_articles error: %s", e)
        return {"error": str(e)}


def get_sa_article_detail(dal: Any, article_id: str) -> Dict:
    """Get full SA article content + comments.

    Returns body_markdown + comment tree for a specific article.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        result = dal.get_sa_article_detail(article_id)
        if not result:
            return {"error": f"Article {article_id} not found"}
        return result
    except Exception as e:
        logger.error("get_sa_article_detail error: %s", e)
        return {"error": str(e)}
