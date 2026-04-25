"""
Seeking Alpha Alpha Picks tool functions.

7 tools: get_sa_alpha_picks, get_sa_pick_detail, refresh_sa_alpha_picks,
         get_sa_articles, get_sa_article_detail, get_sa_market_news,
         list_high_value_comments
All require DAL. Alpha Picks tools are category="portfolio"; market news + comments are category="news".
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


def get_sa_market_news(
    dal: Any,
    ticker: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
) -> Dict:
    """Search recent Seeking Alpha market-news items.

    Returns metadata-only feed items captured from /market-news: title, URL,
    tickers, publish time text, summary, and comment count. When detail pages
    have been fetched, results also include `body_markdown` and `detail_fetched_at`.
    The Chrome extension performs the refresh; this tool reads the local DB cache.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    try:
        items = dal.get_sa_market_news(ticker=ticker, keyword=keyword, limit=limit)
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error("get_sa_market_news error: %s", e)
        return {"error": str(e)}


def list_high_value_comments(
    dal: Any,
    window_days: int = 7,
    ticker: Optional[str] = None,
    min_score: float = 2.0,
    limit: int = 20,
) -> Dict:
    """List high-scoring SA comments within a time window.

    Reads from sa_comment_signals (rule-based extraction; see
    docs/design/SA_COMMENT_INTELLIGENCE_PLAN.md §5.1). Comments are ranked
    by ``high_value_score`` (0..10 weighted sum of ticker mentions, keyword
    bucket hits, external links, and log(upvotes)).

    Args:
        window_days: lookback window using ``comment_date`` (1..90).
        ticker: optional filter — only comments whose ``ticker_mentions``
            includes this symbol (case-insensitive).
        min_score: cutoff (default 2.0). Anything below is filtered out.
        limit: max comments returned (1..50).

    Returns:
        ``{count, window_days, min_score, comments: [{...}]}`` where each
        comment dict carries: comment_id, article_id, commenter, comment_date,
        upvotes, preview (first 300 chars), high_value_score, ticker_mentions,
        candidate_mentions, keyword_buckets, needs_verification.
    """
    if not _is_sa_enabled():
        return {"message": _DISABLED_MSG}

    backend = getattr(dal, "_backend", None)
    if backend is None or not hasattr(backend, "_get_conn"):
        return {
            "error": "DB unavailable; high-value comments require the database backend.",
            "comments": [],
            "count": 0,
        }

    try:
        window_days = max(1, min(int(window_days), 90))
        limit = max(1, min(int(limit), 50))
        min_score = float(min_score)

        conn = backend._get_conn()
        params: List[Any] = [window_days, min_score]
        ticker_clause = ""
        if ticker:
            ticker_clause = " AND %s = ANY(s.ticker_mentions)"
            params.append(ticker.upper())
        params.append(limit)

        sql = f"""
            SELECT
                c.id AS comment_row_id,
                c.article_id,
                c.comment_id,
                c.commenter,
                c.upvotes,
                c.comment_date,
                LEFT(c.comment_text, 300) AS preview,
                s.high_value_score,
                s.ticker_mentions,
                s.candidate_mentions,
                s.keyword_buckets,
                s.needs_verification
            FROM sa_comment_signals s
            JOIN sa_article_comments c ON c.id = s.comment_row_id
            WHERE c.comment_date >= NOW() - (%s || ' days')::INTERVAL
              AND s.high_value_score >= %s
              {ticker_clause}
            ORDER BY s.high_value_score DESC, c.comment_date DESC
            LIMIT %s
        """
        from psycopg2 import extras as _pg_extras
        with conn.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

        comments: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            cd = d.get("comment_date")
            if cd is not None and hasattr(cd, "isoformat"):
                d["comment_date"] = cd.isoformat()
            score = d.get("high_value_score")
            if score is not None:
                d["high_value_score"] = float(score)
            comments.append(d)

        return {
            "count": len(comments),
            "window_days": window_days,
            "min_score": min_score,
            "ticker_filter": ticker.upper() if ticker else None,
            "comments": comments,
        }
    except Exception as e:
        logger.error("list_high_value_comments error: %s", e)
        return {"error": str(e), "comments": [], "count": 0}
