"""Raw-news tool functions."""

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
    result = dal.get_news(ticker=ticker, days=days, source=source)
    result.articles = _trim_articles(result.articles, limit)
    # count reflects total available; articles is the trimmed subset
    return result


def search_news_by_keyword(
    dal: DataAccessLayer,
    keyword: str,
    days: int = 30,
    ticker: Optional[str] = None,
    limit: int = 20,
) -> NewsQueryResult:
    """
    Search news articles by keyword using DB-level full-text search.

    Uses the local search capability for matching.
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
        limit=limit,
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
            earliest_date=s.get("earliest_date"),
            latest_date=s.get("latest_date"),
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
    limit: int = 20,
) -> NewsQueryResult:
    """
    Advanced raw-news search combining full-text search and multiple tickers.

    All filtering happens at DB level for efficiency.

    Args:
        dal: DataAccessLayer instance
        query: Full-text search query (supports multi-word)
        tickers: Filter by multiple tickers (searched in order)
        days: Lookback period in days
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
                limit=per_ticker_limit,
            )
            all_articles.extend(result.articles)
            for src, cnt in result.source_breakdown.items():
                all_sources[src] = all_sources.get(src, 0) + cnt
    else:
        result = dal.search_news(
            query=query, ticker=None, days=days,
            limit=limit,
        )
        all_articles = result.articles
        all_sources = result.source_breakdown

    trimmed = _trim_articles(all_articles, limit)
    ticker_label = ",".join(tickers) if tickers else "ALL"

    return NewsQueryResult(
        ticker=ticker_label,
        count=len(all_articles),
        articles=trimmed,
        source_breakdown=all_sources,
        query_days=days,
    )
