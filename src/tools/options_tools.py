"""
Options / IV tool functions (4 tools).

7.  get_iv_analysis     — Full IV environment analysis (rank, percentile, signal)
8.  get_iv_history_data — Raw IV history data points
9.  scan_mispricing     — Option mispricing scanner (requires IBKR quotes)
10. calculate_greeks    — Black-Scholes Greeks calculator (pure math)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import IVAnalysisResult, IVHistoryPoint, MispricingResult

logger = logging.getLogger(__name__)


def get_iv_analysis(
    dal: DataAccessLayer,
    ticker: str,
) -> IVAnalysisResult:
    """
    Perform full IV environment analysis for a ticker.

    Combines IV history data with analysis module functions to produce
    IV rank, percentile, VRP, and a trading signal.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol

    Returns:
        IVAnalysisResult with current_iv, hv, vrp, iv_rank, iv_percentile, signal
    """
    from analysis import (
        analyze_iv_environment,
        calculate_iv_percentile,
        calculate_iv_rank,
    )

    points = dal.get_iv_history(ticker)
    if not points:
        return IVAnalysisResult(
            ticker=ticker.upper(),
            history_days=0,
            signal="NO_DATA",
        )

    latest = points[-1]
    iv_values = [p.atm_iv for p in points if p.atm_iv is not None]

    if not iv_values or latest.atm_iv is None:
        return IVAnalysisResult(
            ticker=ticker.upper(),
            history_days=len(points),
            signal="NO_IV_DATA",
        )

    current_iv = latest.atm_iv
    hv = latest.hv_30d
    vrp = latest.vrp
    spot = latest.spot_price

    # Calculate rank and percentile if enough history
    iv_rank = None
    iv_percentile = None
    signal = "NEUTRAL"

    if len(iv_values) >= 5:
        try:
            iv_rank = calculate_iv_rank(current_iv, iv_values)
            iv_percentile = calculate_iv_percentile(current_iv, iv_values)
        except Exception as e:
            logger.warning(f"IV rank/percentile calculation failed for {ticker}: {e}")

    # Use analyze_iv_environment for signal if we have HV
    if hv is not None:
        try:
            analysis = analyze_iv_environment(
                ticker=ticker,
                current_iv=current_iv,
                hv=hv,
                iv_history=iv_values if len(iv_values) >= 5 else None,
            )
            signal = analysis.signal
            # Use analysis values if our local calc failed
            if iv_rank is None and analysis.iv_rank is not None:
                iv_rank = analysis.iv_rank
            if iv_percentile is None and analysis.iv_percentile is not None:
                iv_percentile = analysis.iv_percentile
        except Exception as e:
            logger.warning(f"IV environment analysis failed for {ticker}: {e}")

    return IVAnalysisResult(
        ticker=ticker.upper(),
        current_iv=round(current_iv, 4),
        hv_30d=round(hv, 4) if hv is not None else None,
        vrp=round(vrp, 4) if vrp is not None else None,
        iv_rank=round(iv_rank, 1) if iv_rank is not None else None,
        iv_percentile=round(iv_percentile, 1) if iv_percentile is not None else None,
        spot_price=round(spot, 2) if spot is not None else None,
        history_days=len(points),
        signal=signal,
    )


def get_iv_history_data(
    dal: DataAccessLayer,
    ticker: str,
) -> List[IVHistoryPoint]:
    """
    Get raw IV history data points for a ticker.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol

    Returns:
        List of IVHistoryPoint with date, atm_iv, hv_30d, vrp, etc.
    """
    return dal.get_iv_history(ticker)


def scan_mispricing(
    dal: DataAccessLayer,
    tickers: List[str],
    mispricing_threshold_pct: float = 10.0,
    min_confidence: str = "MEDIUM",
) -> List[MispricingResult]:
    """
    Scan for mispriced options using theoretical vs market prices.

    NOTE: This tool requires live or cached option quotes. With FileBackend
    alone (no IBKR connection), it returns an empty list. It will work
    when option quotes are available in the database or via live API.

    Args:
        dal: DataAccessLayer instance
        tickers: List of tickers to scan
        mispricing_threshold_pct: Minimum mispricing % to report
        min_confidence: Minimum confidence level (HIGH, MEDIUM, LOW)

    Returns:
        List of MispricingResult for options exceeding the threshold
    """
    from analysis import scan_options_for_mispricing

    results: List[MispricingResult] = []

    for ticker in tickers:
        ticker = ticker.upper()

        # We need: spot price, HV, and option quotes
        # Get HV from IV history (which stores hv_30d)
        iv_points = dal.get_iv_history(ticker)
        if not iv_points:
            logger.debug(f"{ticker}: No IV history for mispricing scan")
            continue

        latest = iv_points[-1]
        spot = latest.spot_price
        hv = latest.hv_30d

        if spot is None or hv is None:
            logger.debug(f"{ticker}: Missing spot or HV for mispricing scan")
            continue

        # Option quotes need to come from cache or live API
        # Check DAL cache for recent quotes
        cache_key = f"option_quotes_{ticker}"
        quotes = dal.get_from_cache(cache_key, max_age_minutes=60)
        if not quotes:
            logger.debug(f"{ticker}: No cached option quotes for mispricing scan")
            continue

        try:
            signals = scan_options_for_mispricing(
                quotes=quotes,
                spot_price=spot,
                historical_vol=hv,
                mispricing_threshold_pct=mispricing_threshold_pct,
                min_confidence=min_confidence,
            )

            for sig in signals:
                results.append(MispricingResult(
                    underlying=sig.underlying,
                    expiry=sig.expiry,
                    strike=sig.strike,
                    right=sig.right,
                    theoretical_price=round(sig.theoretical_price, 4),
                    market_mid=round(sig.market_mid, 4),
                    mispricing_pct=round(sig.mispricing_pct, 2),
                    signal=sig.signal,
                    confidence=1.0 if sig.confidence == "HIGH" else 0.6 if sig.confidence == "MEDIUM" else 0.3,
                    delta=round(sig.delta, 4) if sig.delta else None,
                ))
        except Exception as e:
            logger.warning(f"{ticker}: Mispricing scan error: {e}")

    return results


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "C",
) -> Dict[str, float]:
    """
    Calculate Black-Scholes Greeks for an option.

    Pure calculation — no data access needed.

    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (e.g. 0.05 for 5%)
        sigma: Volatility (e.g. 0.30 for 30%)
        option_type: 'C' for call, 'P' for put

    Returns:
        Dict with delta, gamma, theta, vega, rho
    """
    from analysis import black_scholes_greeks

    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)

    return {
        "spot": S,
        "strike": K,
        "time_to_expiry": T,
        "risk_free_rate": r,
        "volatility": sigma,
        "option_type": option_type,
        "delta": round(greeks["delta"], 6),
        "gamma": round(greeks["gamma"], 6),
        "theta": round(greeks["theta"], 6),
        "vega": round(greeks["vega"], 6),
        "rho": round(greeks["rho"], 6),
    }