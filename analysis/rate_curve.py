"""
Treasury yield curve abstraction with DTE-based interpolation.

B1: Infrastructure — RateCurve dataclass + linear interpolation.
B2 (deferred): Replace get_yield_curve() internals with real multi-tenor
source (FRED API, yfinance T-bill ladder, etc.).

Usage:
    from analysis.rate_curve import get_rate_for_dte, get_yield_curve

    curve = get_yield_curve()
    r_30d = get_rate_for_dte(30, curve)   # interpolated rate for 30 DTE
    r_180d = get_rate_for_dte(180, curve)  # interpolated rate for 180 DTE
"""

from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RateCurve:
    """Yield curve represented as (DTE, annualized rate) pairs.

    Tenors and rates must be the same length and tenors must be sorted
    ascending. All rates are annualized decimals (e.g. 0.043 = 4.3%).
    """

    tenors: List[int]       # DTE values (sorted ascending, e.g. [30, 91, 182, 365])
    rates: List[float]      # corresponding annualized rates
    fetched_at: str = ""    # ISO timestamp of when the curve was fetched
    source: str = ""        # e.g. "yfinance", "fred", "flat"

    def __post_init__(self):
        if len(self.tenors) != len(self.rates):
            raise ValueError(
                f"tenors ({len(self.tenors)}) and rates ({len(self.rates)}) "
                f"must have the same length"
            )
        if len(self.tenors) == 0:
            raise ValueError("RateCurve must have at least one tenor")
        # Verify sorted
        for i in range(1, len(self.tenors)):
            if self.tenors[i] <= self.tenors[i - 1]:
                raise ValueError(
                    f"tenors must be strictly ascending: "
                    f"{self.tenors[i - 1]} >= {self.tenors[i]} at index {i}"
                )

    @property
    def short_rate(self) -> float:
        """The shortest-tenor rate on the curve."""
        return self.rates[0]

    @property
    def long_rate(self) -> float:
        """The longest-tenor rate on the curve."""
        return self.rates[-1]

    @property
    def is_flat(self) -> bool:
        """True if all rates are identical (flat curve)."""
        return len(set(self.rates)) == 1


def get_rate_for_dte(dte: int, curve: RateCurve) -> float:
    """Interpolate risk-free rate for a given DTE from the yield curve.

    Interpolation strategy:
    - dte <= shortest tenor: flat extrapolation (use shortest rate)
    - dte >= longest tenor: flat extrapolation (use longest rate)
    - between two tenors: linear interpolation

    Args:
        dte: Days to expiration (must be >= 0)
        curve: RateCurve with tenor/rate pairs

    Returns:
        Annualized risk-free rate as decimal (e.g. 0.043)
    """
    if dte < 0:
        raise ValueError(f"dte must be >= 0, got {dte}")

    tenors = curve.tenors
    rates = curve.rates

    # Single-point curve → always that rate
    if len(tenors) == 1:
        return rates[0]

    # Flat extrapolation at boundaries
    if dte <= tenors[0]:
        return rates[0]
    if dte >= tenors[-1]:
        return rates[-1]

    # Find bracketing tenors via bisect
    idx = bisect.bisect_right(tenors, dte)
    # tenors[idx-1] < dte <= tenors[idx]
    t_lo, t_hi = tenors[idx - 1], tenors[idx]
    r_lo, r_hi = rates[idx - 1], rates[idx]

    # Linear interpolation
    frac = (dte - t_lo) / (t_hi - t_lo)
    return r_lo + frac * (r_hi - r_lo)


def make_flat_curve(rate: float, source: str = "flat") -> RateCurve:
    """Create a flat yield curve from a single rate.

    Useful as a bridge: existing code that only has one rate can wrap it
    into a RateCurve and pass it to get_rate_for_dte() (which will always
    return the same rate regardless of DTE).

    Args:
        rate: Annualized risk-free rate as decimal
        source: Label for the rate source

    Returns:
        RateCurve with a single tenor at 91 days (13-week T-bill standard)
    """
    return RateCurve(
        tenors=[91],
        rates=[rate],
        fetched_at=datetime.now().isoformat(),
        source=source,
    )


# ── Yield curve fetching ──────────────────────────────────────

# In-memory cache: (curve, fetched_datetime, ttl_seconds)
_curve_cache: dict[str, Tuple[RateCurve, datetime, int]] = {}
_CACHE_TTL_SECONDS = 86_400         # 24 hours (live curve)
_FALLBACK_CACHE_TTL_SECONDS = 600   # 10 minutes (fallback / degraded curve)

# Treasury tickers available on yfinance:
#   ^IRX  = 13-week T-bill  (~91 DTE)
#   ^FVX  = 5-year note     (~1825 DTE)
#   ^TNX  = 10-year note    (~3650 DTE)
#   ^TYX  = 30-year bond    (~10950 DTE)
# B2 will add more tenors (1m, 3m, 6m, 1y, 2y, etc.) via FRED API.

_TREASURY_TICKERS: List[Tuple[str, int]] = [
    ("^IRX", 91),       # 13-week
    ("^FVX", 1825),     # 5-year
    ("^TNX", 3650),     # 10-year
    ("^TYX", 10950),    # 30-year
]


def get_yield_curve(fallback_rate: float = 0.05) -> RateCurve:
    """Fetch Treasury yield curve from yfinance.

    Currently fetches 4 tenors: 13-week, 5-year, 10-year, 30-year.
    Falls back to flat curve at fallback_rate if fetching fails.

    Resolution order:
        1. In-memory cache (< 24h)
        2. Live fetch from yfinance
        3. Flat curve from existing get_risk_free_rate()
        4. Flat curve at hardcoded fallback

    Args:
        fallback_rate: Default rate if all sources fail.

    Returns:
        RateCurve with available Treasury tenors.
    """
    cache_key = "treasury_curve"
    now = datetime.now()

    # 1. In-memory cache (TTL varies: live curve = 24h, fallback = 10min)
    if cache_key in _curve_cache:
        cached_curve, cached_at, ttl = _curve_cache[cache_key]
        if (now - cached_at).total_seconds() < ttl:
            return cached_curve

    # 2. Live fetch from yfinance
    curve = _fetch_treasury_curve()
    if curve is not None:
        _curve_cache[cache_key] = (curve, now, _CACHE_TTL_SECONDS)
        return curve

    # 3. Fallback to existing single-rate fetcher (short TTL so we retry soon)
    try:
        from .option_pricing import get_risk_free_rate
        rate = get_risk_free_rate(fallback=fallback_rate)
        flat = make_flat_curve(rate, source="irx_fallback")
        _curve_cache[cache_key] = (flat, now, _FALLBACK_CACHE_TTL_SECONDS)
        return flat
    except Exception:
        pass

    # 4. Hardcoded fallback (short TTL)
    logger.warning("No curve source available — using flat %.2f%%", fallback_rate * 100)
    flat = make_flat_curve(fallback_rate, source="hardcoded_fallback")
    _curve_cache[cache_key] = (flat, now, _FALLBACK_CACHE_TTL_SECONDS)
    return flat


def _fetch_treasury_curve() -> Optional[RateCurve]:
    """Fetch multi-tenor Treasury rates from yfinance.

    Returns None if fetching fails or no data available.
    """
    try:
        import yfinance as yf
        import tempfile

        yf.set_tz_cache_location(tempfile.gettempdir())
    except ImportError:
        logger.debug("yfinance not installed — skipping curve fetch")
        return None

    tenors: List[int] = []
    rates: List[float] = []

    for symbol, dte in _TREASURY_TICKERS:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if hist.empty:
                continue
            close = float(hist["Close"].dropna().iloc[-1])
            rate = close / 100.0  # All ^I/F/T tickers quote in percent
            tenors.append(dte)
            rates.append(rate)
        except Exception as e:
            logger.debug("Failed to fetch %s: %s", symbol, e)
            continue

    if not tenors:
        logger.warning("Could not fetch any Treasury rates")
        return None

    curve = RateCurve(
        tenors=tenors,
        rates=rates,
        fetched_at=datetime.now().isoformat(),
        source="yfinance",
    )
    logger.info(
        "Treasury curve fetched: %s",
        ", ".join(f"{t}d={r:.3%}" for t, r in zip(tenors, rates)),
    )
    return curve
