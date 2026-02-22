"""
News tool functions (5 tools).

1. get_ticker_news           — Query news articles for a ticker
2. get_news_sentiment_summary — Aggregate sentiment statistics
3. search_news_by_keyword    — Search news by keyword (DB full-text search)
4. get_news_brief            — Lightweight per-ticker news overview (scout tool)
5. search_news_advanced      — Advanced multi-filter news search
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import NewsBrief, NewsArticle, NewsQueryResult

# Maximum characters for article descriptions in tool output.
# Long descriptions bloat the LLM context; callers can fetch full text via URL.
_MAX_DESC_CHARS = 200


def _trim_articles(articles: list[NewsArticle], limit: int) -> list[NewsArticle]:
    """Sort by date descending, take top *limit*, truncate descriptions."""
    # Sort newest first
    articles.sort(key=lambda a: a.date, reverse=True)
    trimmed = articles[:limit]
    for a in trimmed:
        if a.description and len(a.description) > _MAX_DESC_CHARS:
            a.description = a.description[:_MAX_DESC_CHARS] + "..."
    return trimmed


def get_ticker_news(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 30,
    source: str = "auto",
    limit: int = 20,
) -> NewsQueryResult:
    """
    Get recent news articles for a ticker.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period in days
        source: Data source (ibkr, polygon, auto)
        limit: Maximum number of articles to return (default 20, max 500)

    Returns:
        NewsQueryResult with articles, count, and source breakdown
    """
    limit = min(max(limit, 1), 500)
    result = dal.get_news(ticker=ticker, days=days, source=source, scored_only=False)
    result.articles = _trim_articles(result.articles, limit)
    # count reflects total available; articles is the trimmed subset
    return result


def get_news_sentiment_summary(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 7,
) -> dict:
    """
    Get aggregated sentiment statistics for a ticker.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period in days

    Returns:
        Dict with:
            ticker, days, article_count,
            sentiment_mean, sentiment_median,
            risk_mean, risk_median,
            bullish_count, bearish_count, neutral_count,
            bullish_ratio, bearish_ratio
    """
    result = dal.get_news(ticker=ticker, days=days, scored_only=True)

    sentiments = [
        a.sentiment_score for a in result.articles
        if a.sentiment_score is not None
    ]
    risks = [
        a.risk_score for a in result.articles
        if a.risk_score is not None
    ]

    # Classify: on 1-5 scale, >=4 is bullish, <=2 is bearish, 3 is neutral
    bullish = sum(1 for s in sentiments if s >= 4)
    bearish = sum(1 for s in sentiments if s <= 2)
    neutral = sum(1 for s in sentiments if 2 < s < 4)
    total = len(sentiments)

    return {
        "ticker": ticker.upper(),
        "days": days,
        "article_count": result.count,
        "scored_count": total,
        "sentiment_mean": round(sum(sentiments) / total, 2) if total else None,
        "sentiment_median": round(sorted(sentiments)[total // 2], 2) if total else None,
        "risk_mean": round(sum(risks) / len(risks), 2) if risks else None,
        "risk_median": round(sorted(risks)[len(risks) // 2], 2) if risks else None,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "bullish_ratio": round(bullish / total, 3) if total else 0,
        "bearish_ratio": round(bearish / total, 3) if total else 0,
    }


def search_news_by_keyword(
    dal: DataAccessLayer,
    keyword: str,
    days: int = 30,
    ticker: Optional[str] = None,
    limit: int = 20,
) -> NewsQueryResult:
    """
    Search news articles by keyword using DB-level full-text search.

    Uses PostgreSQL tsvector/GIN index for efficient matching.
    Falls back to Python-level filtering for FileBackend.

    Args:
        dal: DataAccessLayer instance
        keyword: Search keyword (case-insensitive, supports multi-word)
        days: Lookback period in days
        ticker: Optionally filter by ticker first
        limit: Maximum number of articles to return (default 20, max 500)

    Returns:
        NewsQueryResult with matching articles
    """
    limit = min(max(limit, 1), 500)
    result = dal.search_news(
        query=keyword, ticker=ticker, days=days,
        limit=limit, scored_only=False,
    )
    # Trim descriptions for LLM context
    result.articles = _trim_articles(result.articles, limit)
    return result


def get_news_brief(
    dal: DataAccessLayer,
    tickers: Optional[List[str]] = None,
    days: int = 7,
) -> dict:
    """
    Lightweight news overview for one or many tickers (scout tool).

    Call this FIRST before get_ticker_news() to understand which tickers
    have noteworthy news activity. Returns ~2K chars even for 30 tickers.

    Args:
        dal: DataAccessLayer instance
        tickers: List of ticker symbols (default: watchlist from config)
        days: Lookback period in days (default: 7)

    Returns:
        Dict with:
            days: int
            ticker_count: int
            briefs: List[NewsBrief] — per-ticker stats
    """
    # Resolve tickers from watchlist if not provided
    if not tickers:
        try:
            watchlist = dal.get_watchlist(include_sectors=False)
            tickers = watchlist.tickers
        except Exception:
            tickers = []

    if not tickers:
        return {"days": days, "ticker_count": 0, "briefs": []}

    # Fetch stats — single query per ticker or batch
    all_stats = []
    for t in tickers:
        stats = dal.get_news_stats(ticker=t, days=days)
        if stats:
            all_stats.extend(stats)

    briefs = []
    for s in all_stats:
        briefs.append(NewsBrief(
            ticker=s.get("ticker", ""),
            article_count=int(s.get("article_count", 0)),
            scored_count=int(s.get("scored_count", 0)),
            earliest_date=s.get("earliest_date"),
            latest_date=s.get("latest_date"),
            avg_sentiment=float(s["avg_sentiment"]) if s.get("avg_sentiment") is not None else None,
            avg_risk=float(s["avg_risk"]) if s.get("avg_risk") is not None else None,
            bullish_count=int(s.get("bullish_count", 0)),
            bearish_count=int(s.get("bearish_count", 0)),
        ).model_dump())

    # Sort by article count descending
    briefs.sort(key=lambda b: b.get("article_count", 0), reverse=True)

    return {
        "days": days,
        "ticker_count": len(briefs),
        "briefs": briefs,
    }


def search_news_advanced(
    dal: DataAccessLayer,
    query: str = "",
    tickers: Optional[List[str]] = None,
    days: int = 30,
    scored_only: bool = False,
    min_sentiment: Optional[int] = None,
    max_risk: Optional[int] = None,
    limit: int = 20,
) -> NewsQueryResult:
    """
    Advanced news search combining full-text search + multi-ticker + score filters.

    All filtering happens at DB level for efficiency.

    Args:
        dal: DataAccessLayer instance
        query: Full-text search query (supports multi-word)
        tickers: Filter by multiple tickers (searched in order)
        days: Lookback period in days
        scored_only: Only return scored articles
        min_sentiment: Minimum sentiment score (1-5)
        max_risk: Maximum risk score (1-5)
        limit: Max articles to return (default 20, max 500)

    Returns:
        NewsQueryResult with matching articles
    """
    limit = min(max(limit, 1), 500)

    if tickers:
        # Multi-ticker: search each, merge results
        all_articles: list[NewsArticle] = []
        all_sources: dict = {}
        per_ticker_limit = max(5, limit // len(tickers))

        for t in tickers:
            result = dal.search_news(
                query=query, ticker=t, days=days,
                limit=per_ticker_limit, scored_only=scored_only,
            )
            all_articles.extend(result.articles)
            for src, cnt in result.source_breakdown.items():
                all_sources[src] = all_sources.get(src, 0) + cnt
    else:
        result = dal.search_news(
            query=query, ticker=None, days=days,
            limit=limit, scored_only=scored_only,
        )
        all_articles = result.articles
        all_sources = result.source_breakdown

    # Apply score filters (post-DB, lightweight)
    if min_sentiment is not None:
        all_articles = [
            a for a in all_articles
            if a.sentiment_score is not None and a.sentiment_score >= min_sentiment
        ]
    if max_risk is not None:
        all_articles = [
            a for a in all_articles
            if a.risk_score is not None and a.risk_score <= max_risk
        ]

    trimmed = _trim_articles(all_articles, limit)
    ticker_label = ",".join(tickers) if tickers else "ALL"

    return NewsQueryResult(
        ticker=ticker_label,
        count=len(all_articles),
        articles=trimmed,
        source_breakdown=all_sources,
        query_days=days,
    )