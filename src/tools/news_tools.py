"""
News tool functions (3 tools).

1. get_ticker_news      — Query news articles for a ticker
2. get_news_sentiment_summary — Aggregate sentiment statistics
3. search_news_by_keyword     — Search news by keyword in titles
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import NewsArticle, NewsQueryResult

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
    limit: int = 50,
) -> NewsQueryResult:
    """
    Get recent news articles for a ticker.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period in days
        source: Data source (ibkr, polygon, auto)
        limit: Maximum number of articles to return (default 20, max 50)

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
    limit: int = 50,
) -> NewsQueryResult:
    """
    Search news articles by keyword in titles.

    Args:
        dal: DataAccessLayer instance
        keyword: Search keyword (case-insensitive)
        days: Lookback period in days
        ticker: Optionally filter by ticker first
        limit: Maximum number of articles to return (default 20, max 50)

    Returns:
        NewsQueryResult with matching articles
    """
    limit = min(max(limit, 1), 500)
    result = dal.get_news(ticker=ticker, days=days, scored_only=False)
    keyword_lower = keyword.lower()

    matched = [
        a for a in result.articles
        if keyword_lower in (a.title or "").lower()
        or keyword_lower in (a.description or "").lower()
    ]

    source_counts: dict = {}
    for a in matched:
        source_counts[a.source] = source_counts.get(a.source, 0) + 1

    trimmed = _trim_articles(matched, limit)

    return NewsQueryResult(
        ticker=ticker or "ALL",
        count=len(matched),
        articles=trimmed,
        source_breakdown=source_counts,
        query_days=days,
    )