"""
Analysis tool functions (6 tools).

14. get_fundamentals_analysis — Fundamental data with derived metrics
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

import pandas as pd

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import DetailedFinancials, FinancialStatement, FundamentalsResult
from src.fundamentals.reuse import (
    ReuseFailure, cached_dataset, configured_age, policy, read_entry,
)

logger = logging.getLogger(__name__)


_DETAILED_VALUATION_FIELD_MAP = {
    "market_cap": "market_cap",
    "enterprise_value": "enterprise_value",
    "pe_ratio": "price_to_earnings_ratio",
    "pb_ratio": "price_to_book_ratio",
    "ps_ratio": "price_to_sales_ratio",
    "ev_to_ebitda": "enterprise_value_to_ebitda_ratio",
    "ev_to_revenue": "enterprise_value_to_revenue_ratio",
    "fcf_yield": "free_cash_flow_yield",
    "peg_ratio": "peg_ratio",
}


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
        currency=getattr(obj, "currency", None),
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
        return paid.get("financial_datasets", {}).get("enabled") is True
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
        balance_sheets[0].report_period if balance_sheets else (
            cashflow_stmts[0].report_period if cashflow_stmts else None)
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
    freshness: str = "auto",
    max_age_seconds: Optional[int] = None,
    source: str = "auto",
) -> FundamentalsResult:
    """Reuse dated local SEC/FD statements before acquiring a provider response.

    Auto uses the configured financial reuse window unless explicitly overridden.
    Stored never fetches or writes. Refresh bypasses old observations; FD still
    requires separate paid admission. Financial period is not a freshness proof.
    """
    from src.fundamentals.cache import (
        fundamentals_analysis_cache_key,
        validate_positive_annual_sec_payload,
    )
    from src.data_source_routing import DataSourcePolicyFailure, load_route

    ticker = ticker.strip().upper()
    result = FundamentalsResult(ticker=ticker)
    try:
        reuse_policy = _financial_policy(dal, freshness, max_age_seconds)
        if period not in ("annual", "quarterly"):
            raise ReuseFailure("financial_period_invalid")
        route = load_route("fundamentals_analysis", dal)
        result.source_routes = [route.describe(source)]
        sources = route.candidates(source)
    except (ReuseFailure, DataSourcePolicyFailure) as exc:
        result.acquisition_gaps = [{"provider": "financials", "code": exc.code}]
        return result

    backend = getattr(dal, "_backend", None)
    key = fundamentals_analysis_cache_key(ticker, period)

    def validate(data):
        valid = validate_positive_annual_sec_payload(data, ticker=ticker)
        return valid.model_dump() if valid is not None else None

    def sec_result(observation):
        answer = FundamentalsResult.model_validate(observation.data)
        answer.source_observations = [observation.describe("sec_edgar", "financial_statements", reuse_policy,
            period=period, report_periods=[answer.snapshot_date])]
        return answer

    def finish(answer):
        answer.source_routes = [route.describe(source, answer.data_source if answer.data_source != "none" else None)]
        return answer

    local_gaps, partial = [], None
    if freshness != "refresh":
        for provider in sources:
            if provider == "sec_edgar":
                saved = read_entry(backend, key, provider, ticker, validate, reuse_policy.max_age_seconds)
                if saved is not None:
                    return finish(sec_result(saved))
                local_gaps.append({"provider": provider, "code": "financial_stored_data_unavailable"})
            else:
                saved_fd = _fd_financials(dal, ticker, period, reuse_policy, local_only=True)
                if saved_fd.source_observations:
                    if not saved_fd.acquisition_gaps:
                        return finish(saved_fd)
                    partial = saved_fd
                local_gaps.extend(saved_fd.acquisition_gaps)
        if partial is not None:
            return finish(partial if freshness == "stored" else _fd_financials(dal, ticker, period, reuse_policy))
        if freshness == "stored":
            result.acquisition_gaps = local_gaps
            return finish(result)

    def fetch_sec():
        try:
            from data_sources.sec_edgar_financials import SECEdgarFinancials
            sec = SECEdgarFinancials()
            n = 4 if period == "quarterly" else 2
            income = sec.get_income_statement(ticker, years=n, period=period)[:n]
            balance = sec.get_balance_sheet(ticker, years=1, period=period)[:1]
            cashflow = sec.get_cash_flow_statement(ticker, years=n, period=period)[:n]
            if not (income or balance or cashflow):
                raise ReuseFailure("sec_financials_unavailable")
            return _build_result_from_statements(ticker, "sec_edgar", income, balance, cashflow).model_dump()
        except ReuseFailure:
            raise
        except Exception as exc:
            raise ReuseFailure("sec_financials_acquisition_failed") from exc

    acquisition_gaps = []
    for provider in sources:
        if provider == "financial_datasets":
            answer = _fd_financials(dal, ticker, period, reuse_policy)
        else:
            try:
                answer = sec_result(cached_dataset(backend, key, provider, ticker, reuse_policy, validate, fetch_sec,
                                                    ttl_days=30 if period == "quarterly" else 90))
            except ReuseFailure as exc:
                acquisition_gaps.append({"provider": provider, "code": exc.code})
                continue
        if answer.source_observations:
            answer.acquisition_gaps = acquisition_gaps + answer.acquisition_gaps
            return finish(answer)
        acquisition_gaps.extend(answer.acquisition_gaps)
    result.acquisition_gaps = acquisition_gaps
    return finish(result)


def _financial_profile(dal):
    try:
        profile = dal.get_user_profile()
        return profile if isinstance(profile, dict) else {}
    except Exception:
        return {}


def _financial_policy(dal, freshness, maximum, *, earnings=False):
    default = configured_age(_financial_profile(dal), earnings=earnings) if freshness == "auto" and maximum is None else 0
    return policy(freshness, maximum, default_age=default)


def _fd_financials(dal, ticker, period, reuse_policy, *, local_only=False):
    from data_sources.financial_datasets_client import FinancialDatasetsClient
    from data_sources.financial_datasets_governance import FinancialDatasetsFailure
    from src.data_source_routing import DataSourcePolicyFailure, FD_POLICY_KEY, fd_policy_from_settings, read_setting

    config, policy_failure = None, None
    if not local_only and reuse_policy.mode != "stored":
        try:
            config = fd_policy_from_settings(read_setting(FD_POLICY_KEY, dal), _financial_profile(dal))
        except DataSourcePolicyFailure as exc:
            policy_failure = exc.code
    fd = FinancialDatasetsClient(cache_days=_get_fd_cache_days(dal), cache_backend=getattr(dal, "_backend", None),
                                request_policy=config)
    n = 4 if period == "quarterly" else 2
    readers = (("income_statements", fd.get_income_statements, n),
               ("balance_sheets", fd.get_balance_sheets, 1),
               ("cash_flow_statements", fd.get_cash_flow_statements, n))
    statements, gaps = {}, {}
    if reuse_policy.mode != "refresh":
        for dataset, read, limit in readers:
            try:
                statements[dataset] = read(ticker, period=period, limit=limit, freshness="stored",
                                           max_age_seconds=reuse_policy.max_age_seconds)
            except FinancialDatasetsFailure as exc:
                gaps[dataset] = exc.code
    if not local_only and reuse_policy.mode != "stored":
        refusal = None
        for dataset, read, limit in readers:
            if dataset in statements:
                continue
            if refusal is not None:
                gaps[dataset] = "financial_datasets_not_attempted_after_refusal"
                continue
            try:
                if policy_failure is not None:
                    raise FinancialDatasetsFailure(policy_failure)
                statements[dataset] = read(ticker, period=period, limit=limit, freshness=reuse_policy.mode,
                                           max_age_seconds=reuse_policy.max_age_seconds)
                gaps.pop(dataset, None)
            except FinancialDatasetsFailure as exc:
                refusal = gaps[dataset] = exc.code
    result = (_build_result_from_statements(ticker, "financial_datasets",
        statements.get("income_statements", []), statements.get("balance_sheets", []),
        statements.get("cash_flow_statements", [])) if statements else FundamentalsResult(ticker=ticker))
    result.acquisition_gaps = [{"provider": "financial_datasets", "dataset": name, "code": code}
                              for name, code in gaps.items()]
    result.source_observations = [{**item, "freshness_mode": reuse_policy.mode} for item in fd.observations]
    return result



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
    dal: DataAccessLayer,
    ticker: str,
    freshness: str = "auto",
    max_age_seconds: Optional[int] = None,
) -> DetailedFinancials:
    """
    Combine cached SEC facts with a request-time qualified local price.

    Static SEC facts plus a qualified local completed-session price, or typed unavailable.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol

    Returns:
        DetailedFinancials with all available metrics
    """
    from data_sources.financial_metrics_calculator import (
        FinancialMetricsCalculator,
        calculate_valuation_metrics,
    )
    from src.fundamentals.cache import (
        detailed_financials_cache_key,
        validate_detailed_financials_static_payload,
    )
    from src.valuation_price import get_valuation_price_basis
    from src.data_source_routing import DataSourcePolicyFailure, load_route

    ticker = ticker.strip().upper()
    years_for_growth = 2
    cache_key = detailed_financials_cache_key(ticker)
    backend = getattr(dal, "_backend", None)
    observations, gaps, routes = [], [], []
    try:
        reuse_policy = _financial_policy(dal, freshness, max_age_seconds)
        earnings_policy = _financial_policy(dal, freshness, max_age_seconds, earnings=True)
    except ReuseFailure as exc:
        return DetailedFinancials(ticker=ticker, acquisition_gaps=[{"provider": "financials", "code": exc.code}])

    def fetch_static():
        try:
            calc = FinancialMetricsCalculator(ticker, years_for_growth=years_for_growth)
            metrics = calc.get_static_metrics_dict()
            tech = calc.get_tech_metrics()
            valuation_inputs = calc.get_valuation_inputs()
            candidate = {
                "version": 2,
                "ticker": ticker,
                "period": "annual",
                "years_for_growth": years_for_growth,
                "data_source": "sec_edgar",
                "report_date": metrics.get("report_date"),
                "static_metrics": metrics,
                "tech_metrics": tech,
                "valuation_inputs": valuation_inputs,
            }
            return candidate if candidate["report_date"] else None
        except Exception as exc:
            raise ReuseFailure("sec_financials_acquisition_failed") from exc

    def validate_static(data):
        valid = validate_detailed_financials_static_payload(data, ticker=ticker)
        if valid is None:
            return None
        try:
            if date.fromisoformat(valid["report_date"]).isoformat() != valid["report_date"]:
                return None
        except (TypeError, ValueError):
            return None
        return valid

    try:
        static_route = load_route("detailed_financials", dal)
        routes.append(static_route.describe())
        static_route.candidates()
        observation = cached_dataset(backend, cache_key, "sec_edgar", ticker, reuse_policy,
                                     validate_static, fetch_static)
        payload = observation.data
        observations.append(observation.describe("sec_edgar", "detailed_financials", reuse_policy,
            period="annual", report_periods=[payload.get("report_date")]))
        routes[-1] = static_route.describe(selected="sec_edgar")
    except (ReuseFailure, DataSourcePolicyFailure) as exc:
        gaps.append({"provider": "sec_edgar", "code": exc.code})
        payload = None

    if payload is None:
        payload = {
            "report_date": None,
            "static_metrics": {},
            "tech_metrics": {},
            "valuation_inputs": {},
        }

    metrics = payload["static_metrics"]
    tech = payload["tech_metrics"]
    valuation_inputs = payload["valuation_inputs"]
    price_basis = get_valuation_price_basis(ticker)
    valuation = calculate_valuation_metrics(
        price=price_basis.price if price_basis.available else None,
        valuation_inputs=valuation_inputs,
    )
    detailed_valuation = {
        product_field: valuation[calculator_field]
        for product_field, calculator_field in _DETAILED_VALUATION_FIELD_MAP.items()
    }

    try:
        earnings_route = load_route("earnings_supplements", dal)
        routes.append(earnings_route.describe())
        earnings_route.candidates()
        earnings, earnings_observations, earnings_gaps = _detailed_earnings(backend, ticker, earnings_policy)
        if earnings_observations:
            routes[-1] = earnings_route.describe(selected="finnhub")
    except DataSourcePolicyFailure as exc:
        earnings, earnings_observations = {}, []
        earnings_gaps = [{"provider": "finnhub", "code": exc.code}]

    return DetailedFinancials(
        ticker=ticker,
        report_date=payload.get("report_date"),
        data_source="sec_edgar" if observations else "none",
        valuation_price_basis=price_basis,
        source_observations=observations + earnings_observations,
        source_routes=routes,
        acquisition_gaps=gaps + earnings_gaps,
        **detailed_valuation,
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
        # SEC-derived balance-sheet and cash-flow facts
        free_cash_flow=valuation_inputs.get("free_cash_flow"),
        cash_and_equivalents=valuation_inputs.get("cash_and_equivalents"),
        total_debt=valuation_inputs.get("total_debt"),
        # Per-share
        eps=metrics.get("earnings_per_share"),
        fcf_per_share=metrics.get("free_cash_flow_per_share"),
        # Earnings surprise
        earnings_surprises=earnings.get("history") or None,
        upcoming_earnings=earnings.get("upcoming"),
    )


def _detailed_earnings(backend, ticker, reuse_policy):
    from datetime import datetime, timezone
    from .analyst_tools import _fetch_earnings_history, _fetch_upcoming_earnings

    today = datetime.now(timezone.utc).date().isoformat()
    values, observations, gaps = {}, [], []
    for dataset, query, fetch in (
        ("history", "last4", lambda: _fetch_earnings_history(ticker, require_success=True)),
        ("upcoming", f"from:{today}", lambda: _fetch_upcoming_earnings(ticker, require_success=True, from_date=today)),
    ):
        def validate(data):
            if not isinstance(data, dict) or set(data) != {dataset}:
                return None
            value = data[dataset]
            if dataset == "history":
                valid = isinstance(value, list) and all(isinstance(item, dict) for item in value)
            else:
                valid = value is None or isinstance(value, dict)
            return data if valid else None

        def acquire():
            try:
                return {dataset: fetch()}
            except Exception as exc:
                raise ReuseFailure("finnhub_earnings_unavailable") from exc

        try:
            observation = cached_dataset(backend, f"finnhub_earnings:v1:{ticker}:{dataset}:{query}",
                "finnhub", ticker, reuse_policy, validate, acquire)
            values[dataset] = observation.data[dataset]
            observations.append(observation.describe("finnhub", f"earnings_{dataset}", reuse_policy))
        except ReuseFailure as exc:
            gaps.append({"provider": "finnhub", "dataset": f"earnings_{dataset}", "code": exc.code})
    return values, observations, gaps


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

    Uses get_detailed_financials() with the configured acquisition-age policy.

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

    unavailable_tickers = []
    unavailable_reasons: Dict[str, int] = {}
    for peer_ticker, financial in financials.items():
        price_basis = financial.valuation_price_basis
        if price_basis.available:
            continue
        unavailable_tickers.append(peer_ticker)
        if price_basis.empty_reason is not None:
            reason = price_basis.empty_reason
            unavailable_reasons[reason] = unavailable_reasons.get(reason, 0) + 1

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
            "valuation_price_unavailable_count": len(unavailable_tickers),
            "valuation_price_unavailable_tickers": sorted(unavailable_tickers),
            "valuation_price_empty_reason_counts": dict(
                sorted(unavailable_reasons.items())
            ),
        },
    }
