"""
Analysis tool functions (6 tools).

14. get_fundamentals_analysis — Fundamental data with derived metrics
16. get_watchlist_overview    — Summary of all watchlist tickers
17. get_morning_brief         — Personalized morning briefing
18. get_detailed_financials   — Explicit unavailable legacy operation
19. get_peer_comparison       — Explicit unavailable legacy operation
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import DetailedFinancials, FinancialStatement, FundamentalsResult

logger = logging.getLogger(__name__)


def _sec_to_financial_statement(obj) -> FinancialStatement:
    """Compatibility delegate for optional legacy SEC callers."""
    from src.fundamentals.adapters import to_financial_statement
    return to_financial_statement(obj)


def _derive_metrics_from_sec(
    income_stmts, balance_sheets, cashflow_stmts, *, source=None,
) -> dict:
    """Use the same period/debt contract for SEC and FD statement inputs."""
    from src.fundamentals.metric_basis import derive_metrics
    return derive_metrics(income_stmts, balance_sheets, cashflow_stmts, source=source)


def _is_fd_enabled(dal: DataAccessLayer) -> bool:
    """Check if Financial Datasets API is enabled and has an API key."""
    if not os.getenv("FINANCIAL_DATASETS_API_KEY"):
        return False
    try:
        profile = dal.get_user_profile()
        paid = profile.get("data_preferences", {}).get("paid_sources", {})
        return paid.get("financial_datasets", {}).get("enabled") is True
    except Exception:
        return False


def _get_fd_cache_days(dal: DataAccessLayer) -> Dict[str, int]:
    from src.fundamentals.adapters import fd_cache_days
    return fd_cache_days(dal)


def _build_result_from_statements(
    ticker: str,
    data_source: str,
    income_stmts,
    balance_sheets,
    cashflow_stmts,
) -> FundamentalsResult:
    """Build FundamentalsResult from statement dataclasses (shared by SEC + FD)."""
    snapshot_date = income_stmts[0].report_period if income_stmts else (
        balance_sheets[0].report_period if balance_sheets else (
            cashflow_stmts[0].report_period if cashflow_stmts else None)
    )
    metrics = _derive_metrics_from_sec(income_stmts, balance_sheets, cashflow_stmts, source=data_source)

    return FundamentalsResult(
        ticker=ticker.upper(),
        snapshot_date=snapshot_date,
        data_source=data_source,
        metric_basis=metrics["metric_basis"],
        metric_gaps=metrics["metric_gaps"],
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
    freshness: str = "auto",
    max_age_seconds: Optional[int] = None,
    source: str = "auto",
    *, currency: str = "USD", statement: Optional[str] = None, end_month: Optional[str] = None,
    observation_id: Optional[str] = None, read_id: Optional[str] = None,
    period_offset: int = 0, period_limit: int = 4,
) -> FundamentalsResult:
    """Read selected SA/FD observations. Stored never acquires; refresh names a source."""
    from pydantic import ValidationError
    from src.fundamentals.contracts import FinancialGap, FinancialQuery
    from src.fundamentals.read_service import read_financials
    try:
        query = FinancialQuery(ticker=ticker, period=period, source=source, freshness=freshness,
            max_age_seconds=max_age_seconds, currency=currency, statement=statement, end_month=end_month,
            observation_id=observation_id, read_id=read_id, period_offset=period_offset, period_limit=period_limit)
    except ValidationError as exc:
        field = exc.errors()[0]["loc"][0]
        code = {"source": "data_source_unsupported", "period": "financial_period_invalid",
                "freshness": "financial_freshness_invalid", "max_age_seconds": "financial_freshness_invalid"}.get(
                    field, "financial_query_invalid")
        return FundamentalsResult(ticker=ticker.strip().upper() if isinstance(ticker, str) else "",
            income_statements=[], balance_sheet=[], cash_flow_statements=[],
            read_gaps=[FinancialGap(provider="financials", code=code)],
            acquisition_gaps=[{"provider": "financials", "code": code}])
    return read_financials(dal, query)


def get_watchlist_overview(
    dal: DataAccessLayer,
) -> dict:
    """
    Generate a summary of all watchlist tickers' current status.

    For each ticker, includes latest price change and raw news count.

    Args:
        dal: DataAccessLayer instance

    Returns:
        Dict with:
            date, ticker_count,
            tickers: list of per-ticker summaries
    """
    from .price_tools import get_price_change

    watchlist = dal.get_watchlist(include_sectors=False)
    try:
        news_rows = dal.get_news_stats(days=7)
        news_by_ticker = {
            str(row.get("ticker", "")).upper(): row
            for row in news_rows
            if row.get("ticker")
        }
    except Exception as e:
        logger.warning("watchlist overview: news stats scan failed: %s", e)
        news_by_ticker = {}

    tickers_summary: List[dict] = []

    for info in watchlist.details:
        t = info.ticker
        summary: dict = {
            "ticker": t,
            "group": info.group,
            "priority": info.priority,
            "latest_close": None,
            "change_7d_pct": None,
            "news_count_7d": 0,
        }

        # Price change (7 days). Avoid a global DISTINCT ticker scan over the
        # full prices table; the watchlist is small, so per-ticker lookups are
        # cheaper and fail independently.
        try:
            change = get_price_change(dal, t, days=7)
            if "error" not in change:
                summary["latest_close"] = change["latest_close"]
                summary["change_7d_pct"] = change["change_pct"]
        except Exception:
            pass

        # Raw news activity (7 days), using one batch stats query for the whole
        # watchlist instead of one article query per ticker.
        stats = news_by_ticker.get(t.upper())
        if stats:
            summary["news_count_7d"] = _as_int(stats.get("article_count"), 0)

        tickers_summary.append(summary)

    return {
        "date": date.today().isoformat(),
        "ticker_count": len(tickers_summary),
        "tickers": tickers_summary,
    }


def get_universe_summaries(dal: DataAccessLayer, days: int = 7) -> Dict[str, dict]:
    """Batch market summary for the whole tracked universe from the LOCAL market DB.

    Returns ``{TICKER: {latest_close, change_pct, total_volume, bars, news_count_7d}}``
    via two aggregate queries over local ``market_data.db``.
    The two domains degrade independently — a news failure keeps price summaries.

    ``dal`` is unused (kept for caller signature compatibility).
    """
    import sqlite3
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from src.market_data_admin import resolve_market_db_path

    path = resolve_market_db_path()
    if not Path(path).exists():
        return {}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days))).strftime(
        "%Y-%m-%dT%H:%M:%S+0000"
    )

    out: Dict[str, dict] = {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        logger.warning("get_universe_summaries failed to open local market DB: %s", e)
        return {}
    try:
        try:
            rows = conn.execute(
                """
                SELECT p.ticker,
                       (SELECT q.close FROM prices q WHERE q.ticker = p.ticker
                          AND q.interval = '15min' AND q.datetime >= :cutoff
                          ORDER BY q.datetime DESC LIMIT 1) AS latest_close,
                       (SELECT q.open FROM prices q WHERE q.ticker = p.ticker
                          AND q.interval = '15min' AND q.datetime >= :cutoff
                          ORDER BY q.datetime ASC LIMIT 1) AS period_open,
                       SUM(p.volume) AS total_volume,
                       COUNT(*) AS bars
                FROM prices p
                WHERE p.interval = '15min' AND p.datetime >= :cutoff
                GROUP BY p.ticker
                """,
                {"cutoff": cutoff},
            ).fetchall()
            for ticker, latest, opened, volume, bars in rows:
                t = str(ticker).upper()
                change = (
                    round((latest - opened) / opened * 100, 2)
                    if latest is not None and opened
                    else None
                )
                out[t] = {
                    "latest_close": round(latest, 2) if latest is not None else None,
                    "change_pct": change,
                    "total_volume": int(volume) if volume is not None else None,
                    "bars": int(bars) if bars is not None else 0,
                    "news_count_7d": 0,
                }
        except sqlite3.Error as e:
            logger.warning("get_universe_summaries prices query failed: %s", e)
        try:
            for ticker, n in conn.execute(
                "SELECT UPPER(ticker), COUNT(*) FROM news "
                "WHERE published_at >= :cutoff GROUP BY UPPER(ticker)",
                {"cutoff": cutoff},
            ):
                t = str(ticker)
                if t in out:
                    out[t]["news_count_7d"] = int(n)
                else:
                    out[t] = {
                        "latest_close": None,
                        "change_pct": None,
                        "total_volume": None,
                        "bars": 0,
                        "news_count_7d": int(n),
                    }
        except sqlite3.Error as e:
            logger.warning("get_universe_summaries news query failed: %s", e)
    finally:
        conn.close()
    return out


def _as_int(value, default: int = 0) -> int:
    """Best-effort int conversion for pandas/DB scalar values."""
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def _as_float(value) -> Optional[float]:
    """Best-effort float conversion for pandas/DB scalar values."""
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


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
    tracked = {info.ticker for info in watchlist.details}
    stats = dal.get_news_stats(days=1)
    notable_news = [
        {
            "ticker": str(row.get("ticker", "")),
            "count": int(row.get("article_count", 0)),
            "latest_date": row.get("latest_date"),
        }
        for row in stats
        if row.get("ticker") in tracked and int(row.get("article_count", 0)) > 0
    ]
    # Stable sorts implement count DESC, latest date DESC, ticker ASC.
    notable_news.sort(key=lambda row: row["ticker"])
    notable_news.sort(
        key=lambda row: str(row.get("latest_date") or ""), reverse=True
    )
    notable_news.sort(key=lambda row: row["count"], reverse=True)

    return {
        "date": today,
        "holdings": holdings_summary,
        "sector_highlights": sector_highlights,
        "notable_news": notable_news[:5],
    }


def get_detailed_financials(
    dal: DataAccessLayer, ticker: str, freshness: str = "auto", max_age_seconds: Optional[int] = None,
) -> DetailedFinancials:
    """Legacy SEC detailed valuation is not a supported SA/FD operation."""
    return DetailedFinancials(ticker=ticker.strip().upper(), data_source="none", status="unavailable",
        error_code="financial_operation_not_ported",
        acquisition_gaps=[{"provider": "financials", "code": "financial_operation_not_ported"}],
        metric_gaps={"detailed_valuation": "qualified_price_and_reviewed_valuation_inputs_required"},
        source_routes=[{"dataset": "detailed_financials", "configured_sources": [],
                        "selected_source": None, "selection_policy": "operation_not_ported"}])


def get_peer_comparison(
    dal, ticker: Optional[str] = None, tickers: Optional[List[str]] = None, sector: Optional[str] = None,
) -> dict:
    """Do not label empty or noncomparable legacy outputs as peer coverage."""
    return {"status": "unavailable", "error_code": "financial_operation_not_ported",
            "target_ticker": ticker.strip().upper() if isinstance(ticker, str) else None,
            "peer_count": 0, "comparison_matrix": {}, "rankings": None, "sector_stats": {},
            "comparison_gaps": {"peer_valuation": {"code": "comparable_same_basis_inputs_required"}},
            "required_action": "use_common_financial_read_with_explicit_source"}
