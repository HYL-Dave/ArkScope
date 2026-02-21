"""
Analysis tool functions (6 tools).

14. get_fundamentals_analysis — Fundamental data with derived metrics
15. get_sec_filings           — SEC filing metadata
16. get_watchlist_overview    — Summary of all watchlist tickers
17. get_morning_brief         — Personalized morning briefing
18. get_detailed_financials   — Comprehensive valuation + tech metrics
19. get_peer_comparison       — Peer comparison with sector rankings
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import DetailedFinancials, FinancialStatement, FundamentalsResult, SECFiling

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


def _is_fd_enabled(dal: DataAccessLayer) -> bool:
    """Check if Financial Datasets API is enabled and has an API key."""
    if not os.getenv("FINANCIAL_DATASETS_API_KEY"):
        return False
    try:
        profile = dal.get_user_profile()
        paid = profile.get("data_preferences", {}).get("paid_sources", {})
        return paid.get("financial_datasets", {}).get("enabled", False)
    except Exception:
        return False


def _get_fd_cache_days(dal: DataAccessLayer) -> Dict[str, int]:
    """Read cache TTL settings from config."""
    try:
        profile = dal.get_user_profile()
        paid = profile.get("data_preferences", {}).get("paid_sources", {})
        fd_config = paid.get("financial_datasets", {})
        result = {}
        if "cache_days_annual" in fd_config:
            result["annual"] = fd_config["cache_days_annual"]
        if "cache_days_quarterly" in fd_config:
            result["quarterly"] = fd_config["cache_days_quarterly"]
        return result
    except Exception:
        return {}


def _build_result_from_statements(
    ticker: str,
    data_source: str,
    income_stmts,
    balance_sheets,
    cashflow_stmts,
) -> FundamentalsResult:
    """Build FundamentalsResult from statement dataclasses (shared by SEC + FD)."""
    snapshot_date = income_stmts[0].report_period if income_stmts else (
        balance_sheets[0].report_period if balance_sheets else None
    )
    metrics = _derive_metrics_from_sec(income_stmts, balance_sheets, cashflow_stmts)

    return FundamentalsResult(
        ticker=ticker.upper(),
        snapshot_date=snapshot_date,
        data_source=data_source,
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
    3. Financial Datasets API (paid, cached) — Q4, TTM, most complete

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
    income_stmts = []
    balance_sheets = []
    cashflow_stmts = []
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

    # If SEC EDGAR has sufficient data, use it
    if income_stmts or balance_sheets:
        return _build_result_from_statements(
            ticker, "sec_edgar", income_stmts, balance_sheets, cashflow_stmts,
        )

    # 3. Financial Datasets API (paid, cached)
    if _is_fd_enabled(dal):
        try:
            from data_sources.financial_datasets_client import FinancialDatasetsClient
            cache_days = _get_fd_cache_days(dal)
            fd = FinancialDatasetsClient(cache_days=cache_days)

            n = 4 if period == "quarterly" else 2
            fd_income = fd.get_income_statements(ticker, period=period, limit=n)
            fd_balance = fd.get_balance_sheets(ticker, period=period, limit=1)
            fd_cashflow = fd.get_cash_flow_statements(ticker, period=period, limit=n)

            if fd_income or fd_balance:
                return _build_result_from_statements(
                    ticker, "financial_datasets",
                    fd_income, fd_balance, fd_cashflow,
                )
        except Exception as e:
            logger.warning(f"Financial Datasets fallback failed for {ticker}: {e}")

    return result


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


def get_detailed_financials(
    dal: DataAccessLayer,
    ticker: str,
) -> DetailedFinancials:
    """
    Comprehensive financial metrics with layered data sources.

    Layer 1: SEC EDGAR cached metrics (quarterly, stored in financial_data_cache)
             — EV/EBITDA, EV/Revenue, margins, growth, SBC, R&D, Rule of 40
    Layer 2: IBKR real-time (optional, requires TWS)
             — PE, PB, PS, market_cap override with live prices
    Layer 3: Finnhub earnings surprise (last 4 quarters + upcoming)

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol

    Returns:
        DetailedFinancials with all available metrics
    """
    ticker = ticker.upper()
    cache_key = f"metrics_{ticker}_annual"

    # --- Layer 1: SEC EDGAR metrics (cached) ---
    cached = None
    try:
        if hasattr(dal._backend, "get_financial_cache"):
            cached = dal._backend.get_financial_cache(cache_key)
    except Exception as e:
        logger.debug(f"Cache read failed for {ticker}: {e}")

    if cached:
        metrics = cached.get("standard", {})
        tech = cached.get("tech", {})
        logger.info(f"{ticker}: Using cached financial metrics")
    else:
        # Calculate fresh from SEC EDGAR
        try:
            from data_sources.financial_metrics_calculator import FinancialMetricsCalculator

            calc = FinancialMetricsCalculator(ticker)
            metrics = calc.get_metrics_dict()
            tech = calc.get_tech_metrics()

            # Cache to DB
            try:
                if hasattr(dal._backend, "set_financial_cache"):
                    dal._backend.set_financial_cache(
                        cache_key, ticker,
                        {"standard": metrics, "tech": tech},
                        ttl_days=90, source="sec_edgar",
                    )
            except Exception as e:
                logger.debug(f"Cache write failed for {ticker}: {e}")

        except Exception as e:
            logger.warning(f"SEC EDGAR metrics failed for {ticker}: {e}")
            metrics = {}
            tech = {}

    # --- Layer 2: IBKR real-time enrichment (optional) ---
    ibkr_pe = None
    ibkr_pb = None
    ibkr_ps = None
    ibkr_mktcap = None

    try:
        fundamentals = dal.get_fundamentals(ticker)
        if fundamentals and fundamentals.snapshot:
            snap = fundamentals.snapshot
            ibkr_pe = snap.get("pe_ratio")
            ibkr_pb = snap.get("price_to_book")
            ibkr_ps = snap.get("price_to_sales")
            ibkr_mktcap = snap.get("market_cap")
    except Exception as e:
        logger.debug(f"IBKR enrichment failed for {ticker}: {e}")

    # --- Layer 3: Finnhub earnings surprise ---
    earnings_history = None
    upcoming = None
    try:
        from .analyst_tools import _fetch_earnings_history, _fetch_upcoming_earnings
        earnings_history = _fetch_earnings_history(ticker) or None
        upcoming = _fetch_upcoming_earnings(ticker)
    except Exception as e:
        logger.debug(f"Finnhub earnings failed for {ticker}: {e}")

    # --- Build result (IBKR overrides SEC for price-based metrics) ---
    return DetailedFinancials(
        ticker=ticker,
        report_date=metrics.get("report_date"),
        data_source="ibkr+sec_edgar" if ibkr_pe else "sec_edgar",
        # Valuation — EV-based (SEC)
        market_cap=ibkr_mktcap or metrics.get("market_cap"),
        enterprise_value=metrics.get("enterprise_value"),
        ev_to_ebitda=metrics.get("enterprise_value_to_ebitda_ratio"),
        ev_to_revenue=metrics.get("enterprise_value_to_revenue_ratio"),
        fcf_yield=metrics.get("free_cash_flow_yield"),
        peg_ratio=metrics.get("peg_ratio"),
        # Valuation — price-based (IBKR preferred)
        pe_ratio=ibkr_pe or metrics.get("price_to_earnings_ratio"),
        pb_ratio=ibkr_pb or metrics.get("price_to_book_ratio"),
        ps_ratio=ibkr_ps or metrics.get("price_to_sales_ratio"),
        # Profitability
        gross_margin=metrics.get("gross_margin"),
        operating_margin=metrics.get("operating_margin"),
        net_margin=metrics.get("net_margin"),
        roe=metrics.get("return_on_equity"),
        roa=metrics.get("return_on_assets"),
        roic=metrics.get("return_on_invested_capital"),
        # Tech-specific
        sbc_to_revenue=tech.get("sbc_to_revenue"),
        rd_to_revenue=tech.get("rd_to_revenue"),
        rule_of_40=tech.get("rule_of_40"),
        sbc_absolute=tech.get("sbc_absolute"),
        rd_absolute=tech.get("rd_absolute"),
        # Growth
        revenue_growth=metrics.get("revenue_growth"),
        earnings_growth=metrics.get("earnings_growth"),
        fcf_growth=metrics.get("free_cash_flow_growth"),
        ebitda_growth=metrics.get("ebitda_growth"),
        # Leverage & Liquidity
        debt_to_equity=metrics.get("debt_to_equity"),
        current_ratio=metrics.get("current_ratio"),
        interest_coverage=metrics.get("interest_coverage"),
        # Cash (from balance sheet / cash flow in metrics calculator)
        free_cash_flow=None,
        cash_and_equivalents=None,
        total_debt=None,
        # Per-share
        eps=metrics.get("earnings_per_share"),
        fcf_per_share=metrics.get("free_cash_flow_per_share"),
        # Earnings surprise
        earnings_surprises=earnings_history,
        upcoming_earnings=upcoming,
    )


# ============================================================
# 19. get_peer_comparison
# ============================================================

# Metrics to compare: (field_name, display_name, higher_is_better)
# None = neutral (no "better" direction)
_COMPARISON_METRICS = [
    ("pe_ratio", "P/E", False),
    ("ev_to_ebitda", "EV/EBITDA", False),
    ("ev_to_revenue", "EV/Revenue", False),
    ("ps_ratio", "P/S", False),
    ("pb_ratio", "P/B", False),
    ("peg_ratio", "PEG", False),
    ("fcf_yield", "FCF Yield", True),
    ("gross_margin", "Gross Margin", True),
    ("operating_margin", "Op Margin", True),
    ("net_margin", "Net Margin", True),
    ("roe", "ROE", True),
    ("roic", "ROIC", True),
    ("revenue_growth", "Rev Growth", True),
    ("earnings_growth", "EPS Growth", True),
    ("debt_to_equity", "D/E", False),
    ("current_ratio", "Current Ratio", True),
    ("rule_of_40", "Rule of 40", True),
    ("rd_to_revenue", "R&D/Rev", None),
]


def _percentile_rank(value: float, values: List[float]) -> float:
    """Calculate percentile rank of value among values (0-100)."""
    if not values or len(values) < 2:
        return 50.0
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return round((below + equal * 0.5) / len(values) * 100, 1)


def get_peer_comparison(
    dal,
    ticker: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    sector: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compare a ticker against sector peers on key financial metrics.

    Three input modes:
    1. ticker only — auto-detect sector from sectors.yaml
    2. sector only — compare all tickers in that sector
    3. tickers — explicit custom peer group

    Uses get_detailed_financials() internally (SEC EDGAR cached 90 days).

    Args:
        dal: DataAccessLayer instance.
        ticker: Target ticker to rank vs peers.
        tickers: Explicit list of peer tickers.
        sector: Sector name from sectors.yaml.

    Returns:
        Dict with comparison matrix, rankings, and sector statistics.
    """
    from statistics import mean, median

    # ── Step 1: Resolve peer list ──────────────────────────
    target = None
    resolved_sector = "custom"

    if tickers:
        peer_list = [t.upper() for t in tickers]
        if ticker:
            target = ticker.upper()
    elif sector:
        peer_list = dal.get_sector_tickers(sector)
        resolved_sector = sector
        if ticker:
            target = ticker.upper()
    elif ticker:
        target = ticker.upper()
        all_sectors = dal.get_all_sectors()
        matching = [s for s, ticks in all_sectors.items() if target in ticks]
        if not matching:
            return {
                "error": f"{target} not found in any sector in sectors.yaml",
                "ticker": target,
            }
        resolved_sector = matching[0]
        peer_list = dal.get_sector_tickers(resolved_sector)
    else:
        return {"error": "Must provide ticker, tickers, or sector"}

    if not peer_list:
        return {"error": f"No tickers found for sector '{sector}'"}

    # Ensure target is in peer list
    if target and target not in peer_list:
        peer_list.append(target)

    # ── Step 2: Fetch financials for all peers ─────────────
    financials: Dict[str, Any] = {}
    errors = []

    for t in peer_list:
        try:
            result = get_detailed_financials(dal, t)
            financials[t] = result
        except Exception as e:
            logger.warning(f"Failed to get financials for {t}: {e}")
            errors.append({"ticker": t, "error": str(e)})

    if not financials:
        return {"error": "Could not fetch financials for any peer"}

    # ── Step 3: Build comparison matrix ────────────────────
    comparison_matrix = {}
    for t, fin in financials.items():
        row = {}
        for field, _, _ in _COMPARISON_METRICS:
            val = getattr(fin, field, None)
            if val is not None:
                row[field] = round(val, 4) if isinstance(val, float) else val
            else:
                row[field] = None
        comparison_matrix[t] = row

    # ── Step 4: Compute sector statistics ──────────────────
    sector_stats = {}
    for field, display, _ in _COMPARISON_METRICS:
        values = [
            comparison_matrix[t][field]
            for t in comparison_matrix
            if comparison_matrix[t][field] is not None
        ]
        if values:
            sector_stats[field] = {
                "median": round(median(values), 4),
                "mean": round(mean(values), 4),
                "count": len(values),
            }
        else:
            sector_stats[field] = {"median": None, "mean": None, "count": 0}

    # ── Step 5: Compute rankings for target ────────────────
    rankings = None
    if target and target in comparison_matrix:
        rankings = {}
        for field, _, higher_is_better in _COMPARISON_METRICS:
            target_val = comparison_matrix[target][field]
            if target_val is None:
                continue
            values = [
                comparison_matrix[t][field]
                for t in comparison_matrix
                if comparison_matrix[t][field] is not None
            ]
            if not values:
                continue

            # Rank (1 = best)
            if higher_is_better is True:
                sorted_vals = sorted(values, reverse=True)
                direction = "higher_better"
            elif higher_is_better is False:
                sorted_vals = sorted(values)
                direction = "lower_better"
            else:
                sorted_vals = sorted(values)
                direction = "neutral"

            rank = sorted_vals.index(target_val) + 1 if target_val in sorted_vals else len(values)
            pct = _percentile_rank(target_val, values)
            # For "lower is better", invert percentile for intuition
            if higher_is_better is False:
                pct = round(100 - pct, 1)

            rankings[field] = {
                "value": target_val,
                "rank": rank,
                "of": len(values),
                "percentile": pct,
                "direction": direction,
            }

    return {
        "target_ticker": target,
        "sector": resolved_sector,
        "peer_count": len(financials),
        "comparison_matrix": comparison_matrix,
        "rankings": rankings,
        "sector_stats": sector_stats,
        "data_quality": {
            "peers_with_data": len(financials),
            "peers_failed": [e["ticker"] for e in errors],
            "data_source": "sec_edgar",
        },
    }