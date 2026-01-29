"""
Option Pricing and Mispricing Analysis Module.

This module provides tools for:
1. Historical Volatility (HV) calculation
2. Black-Scholes option pricing
3. Implied Volatility calculation
4. Volatility smile adjustment (practical approximation)
5. Option mispricing detection

Pricing Models Comparison:
--------------------------
| Model          | Volatility   | Use Case                    |
|----------------|--------------|----------------------------|
| Black-Scholes  | Constant     | Baseline, European options |
| Heston         | Stochastic   | Volatility smile/skew      |
| Jump Diffusion | + Jumps      | Extreme moves, crypto      |
| Binomial       | Discrete     | American options           |
| Monte Carlo    | Simulated    | Complex/exotic options     |

References:
- py_vollib: https://vollib.org/ (production-grade, uses Jäckel's algorithm)
- Mibian: https://github.com/yassinemaaroufi/MibianLib
- WorldQuant: https://www.worldquant.com/ideas/beyond-black-scholes/
"""

import math
import logging
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union
from enum import Enum

import numpy as np
from scipy import stats
from scipy.optimize import brentq, newton

logger = logging.getLogger(__name__)


class OptionType(Enum):
    """Option type enumeration."""
    CALL = 'C'
    PUT = 'P'


@dataclass
class VolatilityEstimate:
    """Volatility estimate with metadata."""
    value: float  # Annualized volatility (e.g., 0.25 = 25%)
    method: str  # 'historical', 'parkinson', 'garman_klass', 'implied'
    window_days: int
    data_points: int
    as_of_date: date
    ticker: str


@dataclass
class TheoreticalPrice:
    """Theoretical option price with Greeks."""
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    # Pricing inputs
    spot: float
    strike: float
    time_to_expiry: float  # In years
    risk_free_rate: float
    volatility: float
    option_type: str  # 'C' or 'P'
    # Model info
    model: str = 'black_scholes'


@dataclass
class MispricingSignal:
    """Signal for potentially mispriced option."""
    underlying: str
    expiry: str
    strike: float
    right: str
    # Prices
    theoretical_price: float
    market_bid: float
    market_ask: float
    market_mid: float
    # Analysis
    mispricing_pct: float  # (market_mid - theoretical) / theoretical * 100
    spread_pct: float  # (ask - bid) / mid * 100
    signal: str  # 'BUY', 'SELL', 'NEUTRAL'
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    # Greeks
    delta: float
    iv_market: Optional[float] = None
    hv_used: Optional[float] = None
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# Historical Volatility Calculations
# =============================================================================

def calculate_close_to_close_volatility(
    prices: List[float],
    annualization_factor: float = 252,
) -> float:
    """
    Calculate historical volatility using close-to-close returns.

    This is the most common method but underestimates volatility
    when there are large intraday moves that reverse.

    Args:
        prices: List of closing prices (oldest to newest).
        annualization_factor: Trading days per year (252 for stocks).

    Returns:
        Annualized volatility as decimal (e.g., 0.25 = 25%).
    """
    if len(prices) < 2:
        return 0.0

    # Calculate log returns
    prices = np.array(prices)
    log_returns = np.log(prices[1:] / prices[:-1])

    # Standard deviation of returns, annualized
    daily_vol = np.std(log_returns, ddof=1)
    annualized_vol = daily_vol * np.sqrt(annualization_factor)

    return float(annualized_vol)


def calculate_parkinson_volatility(
    highs: List[float],
    lows: List[float],
    annualization_factor: float = 252,
) -> float:
    """
    Calculate Parkinson volatility using high-low range.

    More efficient than close-to-close, captures intraday volatility.
    Assumes no overnight gaps (underestimates if gaps are common).

    Formula: σ² = (1/4ln2) * mean((ln(H/L))²)

    Args:
        highs: List of high prices.
        lows: List of low prices.
        annualization_factor: Trading days per year.

    Returns:
        Annualized volatility as decimal.
    """
    if len(highs) < 1 or len(highs) != len(lows):
        return 0.0

    highs = np.array(highs)
    lows = np.array(lows)

    # Parkinson estimator
    log_hl = np.log(highs / lows)
    variance = np.mean(log_hl ** 2) / (4 * np.log(2))
    daily_vol = np.sqrt(variance)

    return float(daily_vol * np.sqrt(annualization_factor))


def calculate_garman_klass_volatility(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    annualization_factor: float = 252,
) -> float:
    """
    Calculate Garman-Klass volatility.

    Most efficient estimator using OHLC data. Accounts for both
    intraday range and close-to-close moves.

    Args:
        opens: List of open prices.
        highs: List of high prices.
        lows: List of low prices.
        closes: List of close prices.
        annualization_factor: Trading days per year.

    Returns:
        Annualized volatility as decimal.
    """
    n = len(closes)
    if n < 2:
        return 0.0

    opens = np.array(opens)
    highs = np.array(highs)
    lows = np.array(lows)
    closes = np.array(closes)

    # Garman-Klass estimator
    log_hl = np.log(highs / lows)
    log_co = np.log(closes / opens)

    variance = np.mean(
        0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co ** 2
    )
    daily_vol = np.sqrt(variance)

    return float(daily_vol * np.sqrt(annualization_factor))


def calculate_historical_volatility(
    prices: Union[List[float], List[Dict]],
    method: str = 'close_to_close',
    window: Optional[int] = None,
    annualization_factor: float = 252,
) -> float:
    """
    Calculate historical volatility with specified method.

    Args:
        prices: Either list of close prices, or list of OHLC dicts.
        method: 'close_to_close', 'parkinson', 'garman_klass'.
        window: Use only last N data points (None = all).
        annualization_factor: Trading days per year.

    Returns:
        Annualized volatility as decimal.

    Example:
        >>> closes = [100, 102, 101, 103, 105, 104, 106]
        >>> hv = calculate_historical_volatility(closes)
        >>> print(f"HV: {hv:.1%}")
        HV: 28.5%
    """
    if window and len(prices) > window:
        prices = prices[-window:]

    if not prices:
        return 0.0

    # Handle OHLC dict format
    if isinstance(prices[0], dict):
        if method == 'parkinson':
            return calculate_parkinson_volatility(
                [p['high'] for p in prices],
                [p['low'] for p in prices],
                annualization_factor,
            )
        elif method == 'garman_klass':
            return calculate_garman_klass_volatility(
                [p['open'] for p in prices],
                [p['high'] for p in prices],
                [p['low'] for p in prices],
                [p['close'] for p in prices],
                annualization_factor,
            )
        else:
            prices = [p['close'] for p in prices]

    return calculate_close_to_close_volatility(prices, annualization_factor)


# =============================================================================
# Black-Scholes Model
# =============================================================================

def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate d1 in Black-Scholes formula."""
    if T <= 0 or sigma <= 0:
        return 0.0
    return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate d2 in Black-Scholes formula."""
    return _d1(S, K, T, r, sigma) - sigma * np.sqrt(T)


def black_scholes_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = 'C',
) -> float:
    """
    Calculate Black-Scholes option price.

    Args:
        S: Current stock price (spot).
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free interest rate (e.g., 0.05 = 5%).
        sigma: Volatility (e.g., 0.25 = 25%).
        option_type: 'C' for Call, 'P' for Put.

    Returns:
        Theoretical option price.

    Example:
        >>> price = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
        >>> print(f"ATM Call: ${price:.2f}")
        ATM Call: $4.62
    """
    if T <= 0:
        # At expiration
        if option_type.upper() == 'C':
            return max(S - K, 0)
        else:
            return max(K - S, 0)

    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)

    if option_type.upper() == 'C':
        price = S * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

    return float(price)


def black_scholes_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = 'C',
) -> Dict[str, float]:
    """
    Calculate all Black-Scholes Greeks.

    Args:
        S: Current stock price.
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free rate.
        sigma: Volatility.
        option_type: 'C' or 'P'.

    Returns:
        Dictionary with delta, gamma, theta, vega, rho.
    """
    if T <= 0:
        return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}

    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    sqrt_T = np.sqrt(T)

    # Gamma (same for call and put)
    gamma = stats.norm.pdf(d1) / (S * sigma * sqrt_T)

    # Vega (same for call and put, in % terms)
    vega = S * stats.norm.pdf(d1) * sqrt_T / 100  # Per 1% vol change

    if option_type.upper() == 'C':
        delta = stats.norm.cdf(d1)
        theta = (-S * stats.norm.pdf(d1) * sigma / (2 * sqrt_T)
                 - r * K * np.exp(-r * T) * stats.norm.cdf(d2)) / 365
        rho = K * T * np.exp(-r * T) * stats.norm.cdf(d2) / 100
    else:
        delta = stats.norm.cdf(d1) - 1
        theta = (-S * stats.norm.pdf(d1) * sigma / (2 * sqrt_T)
                 + r * K * np.exp(-r * T) * stats.norm.cdf(-d2)) / 365
        rho = -K * T * np.exp(-r * T) * stats.norm.cdf(-d2) / 100

    return {
        'delta': float(delta),
        'gamma': float(gamma),
        'theta': float(theta),  # Per day
        'vega': float(vega),    # Per 1% vol change
        'rho': float(rho),      # Per 1% rate change
    }


def calculate_theoretical_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = 'C',
    model: str = 'black_scholes',
) -> TheoreticalPrice:
    """
    Calculate theoretical price with full Greeks.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate.
        sigma: Volatility.
        option_type: 'C' or 'P'.
        model: Pricing model (currently only 'black_scholes').

    Returns:
        TheoreticalPrice dataclass with price and Greeks.
    """
    price = black_scholes_price(S, K, T, r, sigma, option_type)
    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)

    return TheoreticalPrice(
        price=price,
        delta=greeks['delta'],
        gamma=greeks['gamma'],
        theta=greeks['theta'],
        vega=greeks['vega'],
        rho=greeks['rho'],
        spot=S,
        strike=K,
        time_to_expiry=T,
        risk_free_rate=r,
        volatility=sigma,
        option_type=option_type,
        model=model,
    )


# =============================================================================
# Implied Volatility
# =============================================================================

def calculate_implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = 'C',
    max_iterations: int = 100,
    precision: float = 1e-6,
) -> Optional[float]:
    """
    Calculate implied volatility from market price using Brent's method.

    Args:
        market_price: Observed market price of the option.
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate.
        option_type: 'C' or 'P'.
        max_iterations: Maximum iterations for solver.
        precision: Target precision.

    Returns:
        Implied volatility or None if cannot converge.
    """
    if T <= 0:
        return None

    # Intrinsic value check
    if option_type.upper() == 'C':
        intrinsic = max(S - K, 0)
    else:
        intrinsic = max(K - S, 0)

    if market_price < intrinsic:
        logger.warning(f"Market price {market_price} below intrinsic {intrinsic}")
        return None

    def objective(sigma):
        return black_scholes_price(S, K, T, r, sigma, option_type) - market_price

    try:
        # Use Brent's method with reasonable bounds
        iv = brentq(objective, 0.001, 5.0, maxiter=max_iterations, xtol=precision)
        return float(iv)
    except ValueError:
        # Try Newton's method as fallback
        try:
            iv = newton(objective, 0.25, maxiter=max_iterations, tol=precision)
            if 0.001 <= iv <= 5.0:
                return float(iv)
        except (RuntimeError, ValueError):
            pass

    return None


# =============================================================================
# Volatility Smile Adjustment (Practical Approximation)
# =============================================================================

def adjust_volatility_for_smile(
    atm_vol: float,
    S: float,
    K: float,
    T: float,
    skew_factor: float = -0.1,
    curvature: float = 0.05,
) -> float:
    """
    Adjust ATM volatility for volatility smile/skew.

    This is a simplified practical approximation. For production,
    consider implementing the SABR model or using market-calibrated surfaces.

    Typical patterns:
    - Equity: Negative skew (OTM puts have higher IV)
    - FX: Smile (both OTM calls and puts higher IV)
    - Commodities: Various patterns

    Args:
        atm_vol: At-the-money implied volatility.
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        skew_factor: Strength of skew (default -0.1 = equity put skew).
        curvature: Strength of smile curvature.

    Returns:
        Adjusted volatility estimate.
    """
    # Moneyness: log(K/S) / sqrt(T)
    if T <= 0:
        T = 1/365  # Minimum 1 day

    moneyness = np.log(K / S) / np.sqrt(T)

    # Simple quadratic approximation
    # IV(K) = ATM_vol + skew * moneyness + curvature * moneyness^2
    adjustment = skew_factor * moneyness + curvature * moneyness ** 2

    adjusted_vol = atm_vol + adjustment

    # Ensure reasonable bounds
    return float(max(0.01, min(adjusted_vol, 3.0)))


# =============================================================================
# Mispricing Detection
# =============================================================================

def analyze_option_mispricing(
    underlying: str,
    expiry: str,
    strike: float,
    right: str,
    market_bid: float,
    market_ask: float,
    spot_price: float,
    historical_vol: float,
    risk_free_rate: float = 0.05,
    days_to_expiry: Optional[int] = None,
    mispricing_threshold_pct: float = 10.0,
    use_smile_adjustment: bool = True,
) -> MispricingSignal:
    """
    Analyze if an option is mispriced relative to theoretical value.

    Args:
        underlying: Stock symbol.
        expiry: Expiration date (YYYYMMDD format).
        strike: Strike price.
        right: 'C' or 'P'.
        market_bid: Current bid price.
        market_ask: Current ask price.
        spot_price: Current stock price.
        historical_vol: Historical volatility to use for pricing.
        risk_free_rate: Risk-free rate (default 5%).
        days_to_expiry: Days until expiration (calculated from expiry if None).
        mispricing_threshold_pct: Threshold for signal generation.
        use_smile_adjustment: Apply volatility smile adjustment.

    Returns:
        MispricingSignal with analysis results.
    """
    # Calculate days to expiry
    if days_to_expiry is None:
        try:
            exp_date = datetime.strptime(expiry, '%Y%m%d').date()
            days_to_expiry = (exp_date - date.today()).days
        except ValueError:
            days_to_expiry = 30  # Default

    T = max(days_to_expiry, 1) / 365.0

    # Adjust volatility for smile if requested
    vol_to_use = historical_vol
    if use_smile_adjustment:
        vol_to_use = adjust_volatility_for_smile(
            historical_vol, spot_price, strike, T
        )

    # Calculate theoretical price
    theo = calculate_theoretical_price(
        S=spot_price,
        K=strike,
        T=T,
        r=risk_free_rate,
        sigma=vol_to_use,
        option_type=right,
    )

    # Market mid price
    market_mid = (market_bid + market_ask) / 2
    spread_pct = (market_ask - market_bid) / market_mid * 100 if market_mid > 0 else 0

    # Mispricing percentage
    if theo.price > 0:
        mispricing_pct = (market_mid - theo.price) / theo.price * 100
    else:
        mispricing_pct = 0

    # Calculate market IV for reference
    iv_market = calculate_implied_volatility(
        market_mid, spot_price, strike, T, risk_free_rate, right
    )

    # Generate signal
    if mispricing_pct > mispricing_threshold_pct:
        signal = 'SELL'  # Overpriced
    elif mispricing_pct < -mispricing_threshold_pct:
        signal = 'BUY'   # Underpriced
    else:
        signal = 'NEUTRAL'

    # Confidence based on spread and mispricing magnitude
    if abs(mispricing_pct) > 2 * mispricing_threshold_pct and spread_pct < 5:
        confidence = 'HIGH'
    elif abs(mispricing_pct) > mispricing_threshold_pct and spread_pct < 10:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'

    return MispricingSignal(
        underlying=underlying,
        expiry=expiry,
        strike=strike,
        right=right,
        theoretical_price=theo.price,
        market_bid=market_bid,
        market_ask=market_ask,
        market_mid=market_mid,
        mispricing_pct=mispricing_pct,
        spread_pct=spread_pct,
        signal=signal,
        confidence=confidence,
        delta=theo.delta,
        iv_market=iv_market,
        hv_used=vol_to_use,
    )


def scan_options_for_mispricing(
    quotes: List[Dict],
    spot_price: float,
    historical_vol: float,
    risk_free_rate: float = 0.05,
    mispricing_threshold_pct: float = 10.0,
    min_confidence: str = 'MEDIUM',
) -> List[MispricingSignal]:
    """
    Scan multiple option quotes for mispricing opportunities.

    Args:
        quotes: List of option quotes with keys:
                underlying, expiry, strike, right, bid, ask
        spot_price: Current stock price.
        historical_vol: Historical volatility.
        risk_free_rate: Risk-free rate.
        mispricing_threshold_pct: Threshold for signals.
        min_confidence: Minimum confidence to include ('LOW', 'MEDIUM', 'HIGH').

    Returns:
        List of MispricingSignal for options meeting criteria.
    """
    confidence_order = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}
    min_conf_level = confidence_order.get(min_confidence, 1)

    signals = []

    for quote in quotes:
        try:
            # Validate quote data
            bid = quote.get('bid', 0)
            ask = quote.get('ask', 0)

            # Skip invalid quotes (bid/ask must be positive)
            if bid <= 0 or ask <= 0:
                logger.debug(f"Skipping invalid quote: bid={bid}, ask={ask}")
                continue

            signal = analyze_option_mispricing(
                underlying=quote.get('underlying', ''),
                expiry=quote.get('expiry', ''),
                strike=quote.get('strike', 0),
                right=quote.get('right', 'C'),
                market_bid=bid,
                market_ask=ask,
                spot_price=spot_price,
                historical_vol=historical_vol,
                risk_free_rate=risk_free_rate,
                mispricing_threshold_pct=mispricing_threshold_pct,
            )

            # Filter by signal and confidence
            if signal.signal != 'NEUTRAL':
                if confidence_order.get(signal.confidence, 0) >= min_conf_level:
                    signals.append(signal)

        except Exception as e:
            logger.warning(f"Error analyzing {quote}: {e}")
            continue

    # Sort by absolute mispricing percentage (most mispriced first)
    signals.sort(key=lambda x: abs(x.mispricing_pct), reverse=True)

    return signals


# =============================================================================
# Utility Functions
# =============================================================================

def get_risk_free_rate(fallback: float = 0.05) -> float:
    """
    Get current risk-free rate.

    In production, this should fetch from Treasury rates (e.g., 3-month T-bill).
    For now, returns a reasonable default.

    Args:
        fallback: Default rate if cannot fetch.

    Returns:
        Risk-free rate as decimal.
    """
    # TODO: Implement Treasury rate fetching
    # Options:
    # 1. FRED API (Federal Reserve Economic Data)
    # 2. Treasury.gov direct
    # 3. Yahoo Finance ^IRX (13-week T-bill)
    return fallback


def calculate_days_to_expiry(expiry_str: str) -> int:
    """
    Calculate trading days to expiration.

    Args:
        expiry_str: Expiration date in YYYYMMDD format.

    Returns:
        Number of calendar days to expiration.
    """
    try:
        exp_date = datetime.strptime(expiry_str, '%Y%m%d').date()
        return (exp_date - date.today()).days
    except ValueError:
        return 30  # Default


if __name__ == '__main__':
    # Quick test
    print("Option Pricing Module Test")
    print("=" * 50)

    # Test Black-Scholes
    S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.20

    call_price = black_scholes_price(S, K, T, r, sigma, 'C')
    put_price = black_scholes_price(S, K, T, r, sigma, 'P')

    print(f"\nATM Option (S=K=${S}, T=3mo, r=5%, σ=20%):")
    print(f"  Call: ${call_price:.2f}")
    print(f"  Put:  ${put_price:.2f}")

    # Test Greeks
    greeks = black_scholes_greeks(S, K, T, r, sigma, 'C')
    print(f"\nCall Greeks:")
    for k, v in greeks.items():
        print(f"  {k}: {v:.4f}")

    # Test IV calculation
    iv = calculate_implied_volatility(call_price, S, K, T, r, 'C')
    print(f"\nImplied Vol (should be ~20%): {iv:.1%}")

    # Test HV calculation
    prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
    hv = calculate_historical_volatility(prices, window=10)
    print(f"\nHistorical Volatility (10-day): {hv:.1%}")

    # Test mispricing
    signal = analyze_option_mispricing(
        underlying='TEST',
        expiry='20260301',
        strike=100,
        right='C',
        market_bid=5.50,
        market_ask=5.80,
        spot_price=100,
        historical_vol=0.25,
        risk_free_rate=0.05,
    )
    print(f"\nMispricing Analysis:")
    print(f"  Theoretical: ${signal.theoretical_price:.2f}")
    print(f"  Market Mid:  ${signal.market_mid:.2f}")
    print(f"  Mispricing:  {signal.mispricing_pct:+.1f}%")
    print(f"  Signal:      {signal.signal} ({signal.confidence})")