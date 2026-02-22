"""
Portfolio analysis tool (Batch 3a).

Provides get_portfolio_analysis() — portfolio-level metrics:
- P&L tracking (when holdings provided)
- Beta vs SPY (rolling 60-day)
- Pairwise correlation matrix
- Portfolio metrics (weighted beta, HHI concentration, sector diversification)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

logger = logging.getLogger(__name__)

_MAX_CORRELATION_TICKERS = 20
_BETA_WINDOW = 60  # trading days
_PRICE_LOOKBACK_DAYS = 90


def _fetch_daily_closes(
    dal: "DataAccessLayer", tickers: List[str], days: int = _PRICE_LOOKBACK_DAYS,
) -> Dict[str, Dict[str, float]]:
    """
    Fetch daily close prices for each ticker.

    Returns {ticker: {date_str: close_price}}.
    """
    result: Dict[str, Dict[str, float]] = {}
    for t in tickers:
        try:
            pr = dal.get_prices(t, interval="1d", days=days)
            if pr.bars:
                result[t] = {
                    bar.datetime[:10]: bar.close for bar in pr.bars
                }
        except Exception as e:
            logger.debug("Price fetch failed for %s: %s", t, e)
    return result


def _align_returns(
    closes: Dict[str, Dict[str, float]],
) -> tuple[List[str], Dict[str, List[float]]]:
    """
    Align daily closes by date intersection, compute returns.

    Returns (sorted_dates, {ticker: [return_day1, return_day2, ...]}).
    """
    if not closes:
        return [], {}

    # Find common dates across all tickers
    date_sets = [set(dates.keys()) for dates in closes.values()]
    common_dates = sorted(set.intersection(*date_sets)) if date_sets else []

    if len(common_dates) < 2:
        return common_dates, {}

    returns: Dict[str, List[float]] = {}
    for ticker, date_prices in closes.items():
        ticker_returns = []
        for i in range(1, len(common_dates)):
            prev_close = date_prices[common_dates[i - 1]]
            curr_close = date_prices[common_dates[i]]
            if prev_close > 0:
                ticker_returns.append((curr_close - prev_close) / prev_close)
            else:
                ticker_returns.append(0.0)
        returns[ticker] = ticker_returns

    return common_dates, returns


def _compute_beta(
    ticker_returns: List[float], spy_returns: List[float], window: int = _BETA_WINDOW,
) -> Optional[Dict[str, Any]]:
    """Compute rolling beta vs SPY over the last `window` days."""
    n = min(len(ticker_returns), len(spy_returns), window)
    if n < 10:
        return None

    tr = np.array(ticker_returns[-n:])
    sr = np.array(spy_returns[-n:])

    var_spy = np.var(sr, ddof=1)
    if var_spy == 0:
        return None

    cov = np.cov(tr, sr, ddof=1)[0, 1]
    beta = cov / var_spy

    return {
        "beta_60d": round(float(beta), 3),
        "data_points": n,
    }


def _compute_correlation_matrix(
    returns: Dict[str, List[float]], tickers: List[str],
) -> Dict[str, Dict[str, float]]:
    """Compute pairwise correlation matrix."""
    if len(tickers) < 2:
        return {}

    # Cap tickers for matrix size
    tickers = tickers[:_MAX_CORRELATION_TICKERS]

    # Build numpy array
    n = min(len(r) for r in returns.values() if r)
    if n < 5:
        return {}

    arr = np.array([returns[t][-n:] for t in tickers if t in returns])
    if arr.shape[0] < 2:
        return {}

    corr = np.corrcoef(arr)

    actual_tickers = [t for t in tickers if t in returns]
    matrix: Dict[str, Dict[str, float]] = {}
    for i, t1 in enumerate(actual_tickers):
        matrix[t1] = {}
        for j, t2 in enumerate(actual_tickers):
            matrix[t1][t2] = round(float(corr[i, j]), 3)

    return matrix


def _compute_pnl(
    holdings: Dict[str, Dict[str, float]],
    latest_prices: Dict[str, float],
) -> Optional[Dict[str, Any]]:
    """Compute P&L for each position and total."""
    positions = []
    total_market_value = 0.0
    total_cost = 0.0

    for ticker, h in holdings.items():
        qty = h.get("qty", 0)
        entry_price = h.get("entry_price", 0)
        current_price = latest_prices.get(ticker.upper())

        if current_price is None or qty == 0:
            continue

        market_value = current_price * qty
        cost = entry_price * qty
        unrealized_pnl = market_value - cost
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        positions.append({
            "ticker": ticker.upper(),
            "qty": qty,
            "entry_price": round(entry_price, 2),
            "current_price": round(current_price, 2),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

        total_market_value += market_value
        total_cost += cost

    if not positions:
        return None

    return {
        "positions": positions,
        "total_market_value": round(total_market_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_market_value - total_cost, 2),
        "total_return_pct": round(
            ((total_market_value - total_cost) / total_cost * 100) if total_cost > 0 else 0, 2
        ),
    }


def _compute_portfolio_metrics(
    holdings: Dict[str, Dict[str, float]],
    latest_prices: Dict[str, float],
    betas: Dict[str, Dict[str, Any]],
    sectors: Dict[str, List[str]],
) -> Optional[Dict[str, Any]]:
    """Compute portfolio-level metrics: weighted beta, HHI, sector breakdown."""
    # Calculate weights by market value
    weights: Dict[str, float] = {}
    total_mv = 0.0
    for ticker, h in holdings.items():
        t = ticker.upper()
        price = latest_prices.get(t)
        if price and h.get("qty", 0) > 0:
            mv = price * h["qty"]
            weights[t] = mv
            total_mv += mv

    if total_mv == 0:
        return None

    # Normalize weights
    for t in weights:
        weights[t] /= total_mv

    # Weighted beta
    weighted_beta = 0.0
    beta_coverage = 0
    for t, w in weights.items():
        if t in betas and betas[t] is not None:
            weighted_beta += w * betas[t]["beta_60d"]
            beta_coverage += 1

    # HHI (Herfindahl-Hirschman Index)
    hhi = sum(w ** 2 for w in weights.values())

    # Sector breakdown
    ticker_to_sector: Dict[str, str] = {}
    for sector_name, sector_tickers in sectors.items():
        for st in sector_tickers:
            ticker_to_sector[st.upper()] = sector_name

    sector_breakdown: Dict[str, int] = {}
    for t in weights:
        sec = ticker_to_sector.get(t, "unknown")
        sector_breakdown[sec] = sector_breakdown.get(sec, 0) + 1

    return {
        "weighted_beta": round(weighted_beta, 3) if beta_coverage > 0 else None,
        "hhi_concentration": round(hhi, 4),
        "sector_count": len(sector_breakdown),
        "sector_breakdown": sector_breakdown,
    }


# ── Main tool function ──────────────────────────────────────


def get_portfolio_analysis(
    dal: "DataAccessLayer",
    tickers: Optional[List[str]] = None,
    holdings: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    Analyze portfolio or watchlist: P&L, beta vs SPY, correlation, portfolio metrics.

    Args:
        dal: DataAccessLayer instance.
        tickers: List of ticker symbols (default: watchlist from config).
        holdings: Holdings dict, e.g. {"NVDA": {"qty": 100, "entry_price": 120.50}}.

    Returns:
        Dict with pnl, beta, correlation_matrix, and portfolio_metrics.
    """
    # Resolve ticker list
    if holdings:
        analysis_tickers = [t.upper() for t in holdings.keys()]
        mode = "holdings"
    elif tickers:
        analysis_tickers = [t.upper() for t in tickers]
        mode = "watchlist"
    else:
        try:
            wl = dal.get_watchlist()
            analysis_tickers = [t.upper() for t in wl.tickers] if wl.tickers else []
        except Exception as e:
            return {"error": f"Failed to get watchlist: {e}"}
        mode = "watchlist"

    if not analysis_tickers:
        return {"error": "No tickers provided or found in watchlist"}

    # Fetch daily closes for all tickers + SPY
    all_tickers = list(set(analysis_tickers + ["SPY"]))
    closes = _fetch_daily_closes(dal, all_tickers)

    if not closes:
        return {
            "error": "No price data available for any ticker",
            "tickers": analysis_tickers,
        }

    errors = [t for t in analysis_tickers if t not in closes]

    # Latest prices
    latest_prices: Dict[str, float] = {}
    for t, date_prices in closes.items():
        if date_prices:
            latest_date = max(date_prices.keys())
            latest_prices[t] = date_prices[latest_date]

    # Align returns (include SPY for beta)
    _, all_returns = _align_returns(closes)

    # Beta vs SPY
    spy_returns = all_returns.get("SPY")
    betas: Dict[str, Any] = {}
    for t in analysis_tickers:
        if t in all_returns and spy_returns:
            betas[t] = _compute_beta(all_returns[t], spy_returns)
        else:
            betas[t] = None

    # Correlation matrix (analysis tickers only, no SPY)
    corr_tickers = [t for t in analysis_tickers if t in all_returns]
    correlation_matrix = _compute_correlation_matrix(all_returns, corr_tickers)

    # P&L
    pnl = None
    if holdings:
        pnl = _compute_pnl(holdings, latest_prices)

    # Portfolio metrics
    portfolio_metrics = None
    if holdings:
        try:
            sectors = dal.get_all_sectors()
        except Exception:
            sectors = {}
        portfolio_metrics = _compute_portfolio_metrics(
            holdings, latest_prices, betas, sectors,
        )

    result: Dict[str, Any] = {
        "tickers": analysis_tickers,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "pnl": pnl,
        "beta": {t: betas.get(t) for t in analysis_tickers},
        "correlation_matrix": correlation_matrix,
        "portfolio_metrics": portfolio_metrics,
    }

    if errors:
        result["data_errors"] = [f"No price data for {t}" for t in errors]

    return result
