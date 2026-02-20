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

from .schemas import FinancialStatement, FundamentalsResult, SECFiling

logger = logging.getLogger(__name__)


def _dataclass_to_dict(obj) -> dict:
    """Convert a dataclass to dict, dropping None values."""
    from dataclasses import asdict
    return {k: v for k, v in asdict(obj).items()
            if v is not None and k not in ("ticker", "report_period", "fiscal_period",
                                            "period", "currency")}


def _sec_to_financial_statement(obj) -> FinancialStatement:
    """Convert SEC EDGAR dataclass to FinancialStatement schema."""
    return FinancialStatement(
        report_period=obj.report_period,
        fiscal_period=getattr(obj, "fiscal_period", None),
        period_type=getattr(obj, "period", "quarterly"),
        data=_dataclass_to_dict(obj),
    )


def _derive_metrics_from_sec(
    income_stmts, balance_sheets, cashflow_stmts,
) -> dict:
    """Calculate key financial ratios from SEC EDGAR statements."""
    metrics: dict = {}

    if income_stmts:
        latest = income_stmts[0]
        rev = latest.revenue
        if rev and rev > 0:
            if latest.gross_profit is not None:
                metrics["gross_margin"] = round(latest.gross_profit / rev, 4)
            if latest.operating_income is not None:
                metrics["operating_margin"] = round(latest.operating_income / rev, 4)
            if latest.net_income is not None:
                metrics["net_margin"] = round(latest.net_income / rev, 4)

        # Revenue growth (YoY)
        if len(income_stmts) >= 2:
            prev = income_stmts[1]
            if prev.revenue and prev.revenue > 0 and rev:
                metrics["revenue_growth"] = round(
                    (rev - prev.revenue) / abs(prev.revenue), 4
                )
        # Earnings growth
        if len(income_stmts) >= 2:
            curr_ni = latest.net_income
            prev_ni = income_stmts[1].net_income
            if curr_ni is not None and prev_ni is not None and prev_ni != 0:
                metrics["earnings_growth"] = round(
                    (curr_ni - prev_ni) / abs(prev_ni), 4
                )

    if balance_sheets:
        bs = balance_sheets[0]
        metrics["cash_and_equivalents"] = bs.cash_and_equivalents
        metrics["total_debt"] = bs.total_debt
        # Current ratio
        if bs.current_assets and bs.current_liabilities and bs.current_liabilities > 0:
            metrics["current_ratio"] = round(
                bs.current_assets / bs.current_liabilities, 2
            )
        # Debt to equity
        if bs.total_liabilities and bs.shareholders_equity and bs.shareholders_equity > 0:
            metrics["debt_to_equity"] = round(
                bs.total_liabilities / bs.shareholders_equity, 2
            )
        # ROE (annualized from latest quarter)
        if income_stmts and bs.shareholders_equity and bs.shareholders_equity > 0:
            ni = income_stmts[0].net_income
            period = income_stmts[0].period
            if ni is not None:
                annualized = ni * 4 if period == "quarterly" else ni
                metrics["roe"] = round(annualized / bs.shareholders_equity, 4)
        # ROA
        if income_stmts and bs.total_assets and bs.total_assets > 0:
            ni = income_stmts[0].net_income
            period = income_stmts[0].period
            if ni is not None:
                annualized = ni * 4 if period == "quarterly" else ni
                metrics["roa"] = round(annualized / bs.total_assets, 4)

    if cashflow_stmts:
        cf = cashflow_stmts[0]
        metrics["free_cash_flow"] = cf.free_cash_flow

    return metrics


def get_fundamentals_analysis(
    dal: DataAccessLayer,
    ticker: str,
    period: str = "annual",
) -> FundamentalsResult:
    """
    Get fundamental analysis for a ticker.

    Data source priority:
    1. DB/File backend (IBKR snapshot) — fast, pre-computed metrics (annual only)
    2. SEC EDGAR XBRL API (free, real-time) — structured financial statements

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        period: 'annual' or 'quarterly'

    Returns:
        FundamentalsResult with financial metrics and statements
    """
    # 1. Try DB/File backend (IBKR snapshot) — only for annual
    if period == "annual":
        result = dal.get_fundamentals(ticker)
        if result.snapshot_date:
            result.data_source = "ibkr"
            return result
    else:
        result = FundamentalsResult(ticker=ticker.upper())

    # 2. Fallback: SEC EDGAR XBRL (free, covers all US public companies)
    try:
        from data_sources.sec_edgar_financials import SECEdgarFinancials
        sec = SECEdgarFinancials()

        if period == "quarterly":
            n = 4  # 4 most recent quarters
        else:
            n = 2  # 2 most recent years
        income_stmts = sec.get_income_statement(ticker, years=n, period=period)[:n]
        balance_sheets = sec.get_balance_sheet(ticker, years=1, period=period)[:1]
        cashflow_stmts = sec.get_cash_flow_statement(ticker, years=n, period=period)[:n]
    except Exception as e:
        logger.warning(f"SEC EDGAR fallback failed for {ticker}: {e}")
        return result  # Return empty result

    if not income_stmts and not balance_sheets:
        return result

    # 3. Build result from SEC data
    snapshot_date = income_stmts[0].report_period if income_stmts else (
        balance_sheets[0].report_period if balance_sheets else None
    )

    # Derive key metrics
    metrics = _derive_metrics_from_sec(income_stmts, balance_sheets, cashflow_stmts)

    return FundamentalsResult(
        ticker=ticker.upper(),
        snapshot_date=snapshot_date,
        data_source="sec_edgar",
        roe=metrics.get("roe"),
        roa=metrics.get("roa"),
        debt_to_equity=metrics.get("debt_to_equity"),
        current_ratio=metrics.get("current_ratio"),
        revenue_growth=metrics.get("revenue_growth"),
        earnings_growth=metrics.get("earnings_growth"),
        gross_margin=metrics.get("gross_margin"),
        operating_margin=metrics.get("operating_margin"),
        net_margin=metrics.get("net_margin"),
        free_cash_flow=metrics.get("free_cash_flow"),
        cash_and_equivalents=metrics.get("cash_and_equivalents"),
        total_debt=metrics.get("total_debt"),
        income_statements=[_sec_to_financial_statement(s) for s in income_stmts],
        balance_sheet=[_sec_to_financial_statement(s) for s in balance_sheets],
        cash_flow_statements=[_sec_to_financial_statement(s) for s in cashflow_stmts],
    )


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