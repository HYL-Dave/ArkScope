"""
Analysis tool functions (4 tools).

14. get_fundamentals_analysis — Fundamental data with derived metrics
15. get_sec_filings           — SEC filing metadata
16. get_watchlist_overview    — Summary of all watchlist tickers
17. get_morning_brief         — Personalized morning briefing
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import FundamentalsResult, SECFiling

logger = logging.getLogger(__name__)


def get_fundamentals_analysis(
    dal: DataAccessLayer,
    ticker: str,
) -> FundamentalsResult:
    """
    Get fundamental analysis for a ticker.

    Returns key financial metrics from IBKR snapshot data.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol

    Returns:
        FundamentalsResult with market_cap, pe_ratio, roe, etc.
    """
    return dal.get_fundamentals(ticker)


def get_sec_filings(
    dal: DataAccessLayer,
    ticker: str,
    filing_types: Optional[List[str]] = None,
) -> List[SECFiling]:
    """
    Get SEC filing metadata for a ticker.

    Returns filing metadata (type, date, URL), not full text content.
    With FileBackend this returns empty; will be populated when
    DatabaseBackend or SEC Edgar API integration is active.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        filing_types: Filter by type (10-K, 10-Q, 8-K, etc.)

    Returns:
        List of SECFiling with metadata
    """
    return dal.get_sec_filings(ticker, filing_types)


def get_watchlist_overview(
    dal: DataAccessLayer,
) -> dict:
    """
    Generate a summary of all watchlist tickers' current status.

    For each ticker, includes latest price change, news count,
    and sentiment if available.

    Args:
        dal: DataAccessLayer instance

    Returns:
        Dict with:
            date, ticker_count,
            tickers: list of per-ticker summaries
    """
    from .price_tools import get_price_change
    from .news_tools import get_news_sentiment_summary

    watchlist = dal.get_watchlist(include_sectors=False)
    available_prices = set(dal.get_available_tickers("prices"))

    tickers_summary: List[dict] = []

    for info in watchlist.details:
        t = info.ticker
        summary: dict = {
            "ticker": t,
            "group": info.group,
            "priority": info.priority,
        }

        # Price change (7 days)
        if t in available_prices:
            try:
                change = get_price_change(dal, t, days=7)
                if "error" not in change:
                    summary["latest_close"] = change["latest_close"]
                    summary["change_7d_pct"] = change["change_pct"]
            except Exception:
                pass

        # News sentiment (7 days)
        try:
            sent = get_news_sentiment_summary(dal, t, days=7)
            summary["news_count_7d"] = sent["article_count"]
            summary["sentiment_mean"] = sent["sentiment_mean"]
            summary["bullish_ratio"] = sent["bullish_ratio"]
        except Exception:
            pass

        # IV (latest)
        try:
            iv_points = dal.get_iv_history(t)
            if iv_points:
                summary["latest_iv"] = round(iv_points[-1].atm_iv, 4)
                summary["latest_vrp"] = (
                    round(iv_points[-1].vrp, 4)
                    if iv_points[-1].vrp is not None else None
                )
        except Exception:
            pass

        tickers_summary.append(summary)

    return {
        "date": date.today().isoformat(),
        "ticker_count": len(tickers_summary),
        "tickers": tickers_summary,
    }


def get_morning_brief(
    dal: DataAccessLayer,
) -> dict:
    """
    Generate a personalized morning briefing.

    Combines watchlist overview with sector performance and
    notable signals for a quick daily summary.

    Args:
        dal: DataAccessLayer instance

    Returns:
        Dict with:
            date, watchlist_summary, sector_highlights,
            notable_signals, market_context
    """
    from .price_tools import get_sector_performance
    from .news_tools import get_news_sentiment_summary

    profile = dal.get_user_profile()
    today = date.today().isoformat()

    # 1. Watchlist summary (compact)
    watchlist = dal.get_watchlist(include_sectors=False)
    available_prices = set(dal.get_available_tickers("prices"))

    holdings_summary: List[dict] = []
    for info in watchlist.details:
        if info.group != "core_holdings":
            continue
        t = info.ticker
        entry: dict = {"ticker": t}
        if t in available_prices:
            try:
                from .price_tools import get_price_change
                change = get_price_change(dal, t, days=1)
                if "error" not in change:
                    entry["close"] = change["latest_close"]
                    entry["change_1d_pct"] = change["change_pct"]
            except Exception:
                pass
        holdings_summary.append(entry)

    # 2. Sector highlights (watched sectors only)
    sector_highlights: List[dict] = []
    watched_sectors = (
        profile.get("watchlists", {})
        .get("sector_watch", {})
        .get("sectors", [])
    )
    for sector in watched_sectors:
        try:
            perf = get_sector_performance(dal, sector, days=7)
            if "error" not in perf:
                sector_highlights.append({
                    "sector": sector,
                    "avg_change_7d": perf["avg_change_pct"],
                    "best": perf.get("best_ticker"),
                    "worst": perf.get("worst_ticker"),
                })
        except Exception:
            pass

    # 3. Notable news (high-volume tickers)
    notable_news: List[dict] = []
    for info in watchlist.details[:10]:
        try:
            sent = get_news_sentiment_summary(dal, info.ticker, days=1)
            if sent["article_count"] > 0:
                notable_news.append({
                    "ticker": info.ticker,
                    "count": sent["article_count"],
                    "sentiment_mean": sent["sentiment_mean"],
                })
        except Exception:
            pass

    # Sort by news count descending
    notable_news.sort(key=lambda x: x["count"], reverse=True)

    return {
        "date": today,
        "holdings": holdings_summary,
        "sector_highlights": sector_highlights,
        "notable_news": notable_news[:5],
    }