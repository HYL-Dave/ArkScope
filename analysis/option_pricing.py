"""
Option Pricing and Mispricing Analysis Module.

This module provides tools for:
1. Historical Volatility (HV) calculation
2. Black-Scholes option pricing (European)
3. Bjerksund-Stensland 2002 option pricing (American)
4. Implied Volatility calculation (European + American)
5. Volatility smile adjustment (practical approximation)
6. Option mispricing detection

Pricing Models:
--------------
| Model                      | Type     | Use Case                          |
|----------------------------|----------|-----------------------------------|
| Black-Scholes              | European | Baseline, no early exercise       |
| Bjerksund-Stensland 2002   | American | US equity options (default)       |
| Heston / Jump Diffusion    | Either   | Future: stochastic vol            |
| Trinomial Tree / FDM       | American | Future: higher accuracy           |

References:
- Bjerksund & Stensland (2002), "Closed Form Valuation of American Options"
- dbrojas/optlib: https://github.com/dbrojas/optlib (cross-validation reference)
- py_vollib: https://vollib.org/ (production-grade, uses Jäckel's algorithm)
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
    model: str = 'american',
    q: float = 0.0,
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
        model: Pricing model — 'american' (BS2002, default) or 'black_scholes'.
        q: Continuous dividend yield (used by 'american' model). Default 0.

    Returns:
        TheoreticalPrice dataclass with price and Greeks.
    """
    if model == 'american':
        price = bjerksund_stensland_2002(S, K, T, r, sigma, q, option_type)
        greeks = american_greeks(S, K, T, r, sigma, q, option_type)
    else:
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
# Bjerksund-Stensland 2002 (American Option Pricing)
# =============================================================================
#
# Reference: Bjerksund & Stensland (2002), "Closed Form Valuation of American Options"
# Cross-validated against dbrojas/optlib implementation.
#
# Key differences from Black-Scholes:
# - Accounts for early exercise premium (significant for puts, calls with dividends)
# - Uses optimal exercise boundary approximation at two time points
# - Put pricing via put-call transformation
#
# Cost of carry convention: b = r - q (for stock options)
#   b = r       → non-dividend stock (q=0)
#   b = r - q   → continuous dividend yield q
#   b = 0       → futures option
# =============================================================================


def _cbnd(a: float, b: float, rho: float) -> float:
    """Cumulative bivariate normal distribution P(X <= a, Y <= b | correlation=rho)."""
    from scipy.stats import multivariate_normal
    mean = [0.0, 0.0]
    cov = [[1.0, rho], [rho, 1.0]]
    return float(multivariate_normal(mean=mean, cov=cov).cdf([a, b]))


def _gbs_price(
    S: float, K: float, T: float, r: float, b: float, sigma: float,
    option_type: str = 'C',
) -> float:
    """
    Generalized Black-Scholes price (European).

    Uses cost-of-carry parameter b:
      b = r - q  for stocks with continuous dividend yield q
      b = r      for non-dividend stocks
      b = 0      for futures options

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry (years).
        r: Risk-free rate.
        b: Cost of carry.
        sigma: Volatility.
        option_type: 'C' or 'P'.

    Returns:
        European option price.
    """
    if T <= 0:
        if option_type.upper() == 'C':
            return max(S - K, 0.0)
        else:
            return max(K - S, 0.0)

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (b + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if option_type.upper() == 'C':
        return float(
            S * math.exp((b - r) * T) * stats.norm.cdf(d1)
            - K * math.exp(-r * T) * stats.norm.cdf(d2)
        )
    else:
        return float(
            K * math.exp(-r * T) * stats.norm.cdf(-d2)
            - S * math.exp((b - r) * T) * stats.norm.cdf(-d1)
        )


def _bs2002_phi(
    S: float, T: float, gamma: float, H: float, I: float,
    r: float, b: float, sigma: float,
) -> float:
    """
    BS2002 Phi function — single-barrier auxiliary.

    Formula:
        exp(λT) · S^γ · [N(d1) - (I/S)^κ · N(d2)]
    where:
        λ = -r + γb + 0.5γ(γ-1)σ²
        κ = 2b/σ² + 2γ - 1
    """
    v2 = sigma ** 2
    sqrt_T = sigma * math.sqrt(T)

    lambda1 = -r + gamma * b + 0.5 * gamma * (gamma - 1) * v2
    kappa = 2 * b / v2 + (2 * gamma - 1)

    d1 = -(math.log(S / H) + (b + (gamma - 0.5) * v2) * T) / sqrt_T
    d2 = d1 - 2 * math.log(I / S) / sqrt_T

    # Use log-space to protect against overflow in (I/S)**kappa and S**gamma
    log_prefix = lambda1 * T + gamma * math.log(S)
    log_ratio = kappa * math.log(I / S)

    if log_prefix > 500 or log_prefix < -500:
        return 0.0

    prefix = math.exp(log_prefix)
    nd1 = stats.norm.cdf(d1)

    if abs(log_ratio) > 500:
        ratio_term = 0.0
    else:
        ratio_term = math.exp(log_ratio) * stats.norm.cdf(d2)

    return float(prefix * (nd1 - ratio_term))


def _bs2002_psi(
    S: float, T2: float, gamma: float, H: float, I2: float,
    I1: float, T1: float, r: float, b: float, sigma: float,
) -> float:
    """
    BS2002 Psi function — two-time-point auxiliary (2002 improvement over 1993).

    Uses bivariate normal CDF to combine expectations across T1 and T2.
    Correlation: tau = sqrt(T1/T2).
    """
    v2 = sigma ** 2
    vsqrt_t1 = sigma * math.sqrt(T1)
    vsqrt_t2 = sigma * math.sqrt(T2)

    bgamma_t1 = (b + (gamma - 0.5) * v2) * T1
    bgamma_t2 = (b + (gamma - 0.5) * v2) * T2

    d1 = (math.log(S / I1) + bgamma_t1) / vsqrt_t1
    d2 = (math.log(I2 ** 2 / (S * I1)) + bgamma_t1) / vsqrt_t1
    d3 = (math.log(S / I1) - bgamma_t1) / vsqrt_t1
    d4 = (math.log(I2 ** 2 / (S * I1)) - bgamma_t1) / vsqrt_t1

    e1 = (math.log(S / H) + bgamma_t2) / vsqrt_t2
    e2 = (math.log(I2 ** 2 / (S * H)) + bgamma_t2) / vsqrt_t2
    e3 = (math.log(I1 ** 2 / (S * H)) + bgamma_t2) / vsqrt_t2
    e4 = (math.log(S * I1 ** 2 / (H * I2 ** 2)) + bgamma_t2) / vsqrt_t2

    tau = math.sqrt(T1 / T2)
    lambda1 = -r + gamma * b + 0.5 * gamma * (gamma - 1) * v2
    kappa = 2 * b / v2 + (2 * gamma - 1)

    # Use log-space for overflow protection
    log_prefix = lambda1 * T2 + gamma * math.log(S)
    if log_prefix > 500 or log_prefix < -500:
        return 0.0

    prefix = math.exp(log_prefix)

    def _safe_pow(base, exp_val):
        """Compute base**exp_val safely via log-space."""
        if base <= 0:
            return 0.0
        log_val = exp_val * math.log(base)
        if log_val > 500 or log_val < -500:
            return 0.0
        return math.exp(log_val)

    term1 = _cbnd(-d1, -e1, tau)
    term2 = _safe_pow(I2 / S, kappa) * _cbnd(-d2, -e2, tau)
    term3 = _safe_pow(I1 / S, kappa) * _cbnd(-d3, -e3, -tau)
    term4 = _safe_pow(I1 / I2, kappa) * _cbnd(-d4, -e4, -tau)

    return float(prefix * (term1 - term2 - term3 + term4))


def _bs2002_call(
    S: float, K: float, T: float, r: float, b: float, sigma: float,
) -> float:
    """
    BS2002 American call price (internal).

    When b >= r (no dividends for calls), American call = European call
    (early exercise never optimal). Otherwise, computes optimal exercise
    boundary at two time points and combines phi/psi terms.
    """
    # European price as lower bound
    e_price = _gbs_price(S, K, T, r, b, sigma, 'C')

    # When b >= r, American call = European call (no early exercise benefit)
    if b >= r:
        return e_price

    v2 = sigma ** 2

    # Two time points: t1 and t2 = T
    t1 = 0.5 * (math.sqrt(5) - 1) * T  # Golden ratio split
    t2 = T

    # Beta: critical boundary parameter
    beta_inside = (b / v2 - 0.5) ** 2 + 2 * r / v2
    beta = (0.5 - b / v2) + math.sqrt(abs(beta_inside))

    # Boundary values
    b_infinity = (beta / (beta - 1)) * K
    b_zero = max(K, (r / (r - b)) * K)

    denom = (b_infinity - b_zero) * b_zero
    if abs(denom) < 1e-15:
        return e_price

    h1 = -(b * t1 + 2 * sigma * math.sqrt(t1)) * (K ** 2 / denom)
    h2 = -(b * t2 + 2 * sigma * math.sqrt(t2)) * (K ** 2 / denom)

    # Protect against overflow in exp() — clamp to prevent math range error
    h1 = max(min(h1, 500), -500)
    h2 = max(min(h2, 500), -500)

    i1 = b_zero + (b_infinity - b_zero) * (1 - math.exp(h1))
    i2 = b_zero + (b_infinity - b_zero) * (1 - math.exp(h2))

    # Use log-space for power operations to prevent overflow
    def _safe_pow(base, exp_val):
        if base <= 0:
            return 0.0
        log_val = exp_val * math.log(base)
        if log_val > 500 or log_val < -500:
            return 0.0
        return math.exp(log_val)

    alpha1 = (i1 - K) * _safe_pow(i1, -beta)
    alpha2 = (i2 - K) * _safe_pow(i2, -beta)

    # Immediate exercise check
    if S >= i2:
        return S - K

    # Main approximation formula
    value = (
        alpha2 * _safe_pow(S, beta)
        - alpha2 * _bs2002_phi(S, t1, beta, i2, i2, r, b, sigma)
        + _bs2002_phi(S, t1, 1, i2, i2, r, b, sigma)
        - _bs2002_phi(S, t1, 1, i1, i2, r, b, sigma)
        - K * _bs2002_phi(S, t1, 0, i2, i2, r, b, sigma)
        + K * _bs2002_phi(S, t1, 0, i1, i2, r, b, sigma)
        + alpha1 * _bs2002_phi(S, t1, beta, i1, i2, r, b, sigma)
        - alpha1 * _bs2002_psi(S, t2, beta, i1, i2, i1, t1, r, b, sigma)
        + _bs2002_psi(S, t2, 1, i1, i2, i1, t1, r, b, sigma)
        - _bs2002_psi(S, t2, 1, K, i2, i1, t1, r, b, sigma)
        - K * _bs2002_psi(S, t2, 0, i1, i2, i1, t1, r, b, sigma)
        + K * _bs2002_psi(S, t2, 0, K, i2, i1, t1, r, b, sigma)
    )

    # American price is at least the European price
    return max(value, e_price)


def bjerksund_stensland_2002(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    option_type: str = 'C',
) -> float:
    """
    Bjerksund-Stensland 2002 American option price.

    Closed-form approximation that handles early exercise for both calls
    and puts, including continuous dividend yield.

    For calls: Direct BS2002 formula with b = r - q.
    For puts: Put-call transformation — price American put by pricing an
              American call with swapped S↔K and r↔q.

    Args:
        S: Current stock price (spot).
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free interest rate (e.g., 0.05 = 5%).
        sigma: Volatility (e.g., 0.25 = 25%).
        q: Continuous dividend yield (e.g., 0.02 = 2%). Default 0.
        option_type: 'C' for Call, 'P' for Put.

    Returns:
        American option price.

    References:
        Bjerksund & Stensland (2002), "Closed Form Valuation of American Options"

    Example:
        >>> # American put on non-dividend stock
        >>> price = bjerksund_stensland_2002(S=100, K=100, T=0.5, r=0.05, sigma=0.30, q=0.0, option_type='P')
        >>> # Should be slightly higher than European BS put (~8.48 vs ~8.08)
    """
    if T <= 0:
        if option_type.upper() == 'C':
            return max(S - K, 0.0)
        else:
            return max(K - S, 0.0)

    if sigma <= 0:
        if option_type.upper() == 'C':
            return max(S * math.exp(-q * T) - K * math.exp(-r * T), max(S - K, 0.0))
        else:
            return max(K * math.exp(-r * T) - S * math.exp(-q * T), max(K - S, 0.0))

    b = r - q  # Cost of carry for stocks with continuous dividend yield

    if option_type.upper() == 'C':
        return _bs2002_call(S, K, T, r, b, sigma)
    else:
        # Put-call transformation:
        # American Put(S, K, T, r, q, σ) = American Call(K, S, T, q, r, σ)
        # In cost-of-carry terms: swap S↔K, r→q, b→-b, new_r = r-b = q
        return _bs2002_call(K, S, T, r - b, -b, sigma)


def american_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    option_type: str = 'C',
) -> Dict[str, float]:
    """
    Greeks for American options via central finite differences on BS2002 price.

    This is standard practice — even QuantLib uses numerical differentiation
    for Bjerksund-Stensland Greeks, as analytical derivatives of the BS2002
    formula are mathematically intractable.

    Args:
        S, K, T, r, sigma, q, option_type: Same as bjerksund_stensland_2002.

    Returns:
        Dictionary with delta, gamma, theta, vega, rho.
    """
    if T <= 0:
        return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}

    def price(S_=S, K_=K, T_=T, r_=r, sigma_=sigma, q_=q):
        return bjerksund_stensland_2002(S_, K_, T_, r_, sigma_, q_, option_type)

    p0 = price()

    # Delta: ∂V/∂S (central difference)
    h_s = S * 0.01  # 1% of spot
    delta = (price(S_=S + h_s) - price(S_=S - h_s)) / (2 * h_s)

    # Gamma: ∂²V/∂S² (central second difference)
    gamma = (price(S_=S + h_s) - 2 * p0 + price(S_=S - h_s)) / (h_s ** 2)

    # Vega: ∂V/∂σ per 1% vol change
    h_v = 0.001  # 0.1% vol bump
    vega = (price(sigma_=sigma + h_v) - price(sigma_=sigma - h_v)) / (2 * h_v) / 100

    # Theta: -∂V/∂T per calendar day (forward difference to avoid T < 0)
    h_t = 1.0 / 365.0
    if T > h_t:
        theta = -(price(T_=T) - price(T_=T - h_t)) / h_t / 365
    else:
        theta = -(price(T_=T) - price(T_=max(T - h_t, 0.0001))) / h_t / 365

    # Rho: ∂V/∂r per 1% rate change
    h_r = 0.001
    rho = (price(r_=r + h_r) - price(r_=r - h_r)) / (2 * h_r) / 100

    return {
        'delta': float(delta),
        'gamma': float(gamma),
        'theta': float(theta),
        'vega': float(vega),
        'rho': float(rho),
    }


def calculate_american_iv(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    option_type: str = 'C',
    max_iterations: int = 100,
    precision: float = 1e-6,
) -> Optional[float]:
    """
    Calculate implied volatility using Bjerksund-Stensland 2002 as pricing model.

    For American options, IV from this function is more accurate than BS IV
    because the pricing model properly accounts for early exercise.

    Args:
        market_price: Observed market price.
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate.
        q: Continuous dividend yield.
        option_type: 'C' or 'P'.
        max_iterations: Max iterations for solver.
        precision: Target precision.

    Returns:
        American implied volatility, or None if cannot converge.
    """
    if T <= 0 or market_price <= 0:
        return None

    # Intrinsic value check
    if option_type.upper() == 'C':
        intrinsic = max(S - K, 0.0)
    else:
        intrinsic = max(K - S, 0.0)

    if market_price < intrinsic - 0.01:  # Small tolerance for numerical noise
        logger.warning(f"Market price {market_price:.4f} below intrinsic {intrinsic:.4f}")
        return None

    def objective(sigma):
        return bjerksund_stensland_2002(S, K, T, r, sigma, q, option_type) - market_price

    try:
        iv = brentq(objective, 0.001, 5.0, maxiter=max_iterations, xtol=precision)
        return float(iv)
    except ValueError:
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
    model: str = 'american',
    dividend_yield: float = 0.0,
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
        model: Pricing model — 'american' (default) or 'black_scholes'.
        dividend_yield: Continuous dividend yield (for 'american' model).

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
        model=model,
        q=dividend_yield,
    )

    # Market mid price
    market_mid = (market_bid + market_ask) / 2
    spread_pct = (market_ask - market_bid) / market_mid * 100 if market_mid > 0 else 0

    # Mispricing percentage
    if theo.price > 0:
        mispricing_pct = (market_mid - theo.price) / theo.price * 100
    else:
        mispricing_pct = 0

    # Calculate market IV for reference (use matching model)
    if model == 'american':
        iv_market = calculate_american_iv(
            market_mid, spot_price, strike, T, risk_free_rate, dividend_yield, right
        )
    else:
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

_rfr_cache: Dict[str, Tuple[float, datetime]] = {}


def get_risk_free_rate(fallback: float = 0.05) -> float:
    """
    Get current risk-free rate from 13-week T-bill (^IRX via Yahoo Finance).

    Caches the result for 24 hours.  Falls back to *fallback* if the fetch
    fails (network error, market holiday, etc.).

    Args:
        fallback: Default rate if cannot fetch.

    Returns:
        Risk-free rate as decimal (e.g. 0.043 for 4.3%).
    """
    cache_key = "irx"
    now = datetime.now()

    # Return cached value if fresh (< 24 h)
    if cache_key in _rfr_cache:
        cached_rate, cached_at = _rfr_cache[cache_key]
        if (now - cached_at).total_seconds() < 86_400:
            return cached_rate

    try:
        import yfinance as yf

        # Suppress yfinance's sqlite cache errors on read-only filesystems
        import os
        old_cache = os.environ.get("YF_CACHE_DIR")
        try:
            import tempfile
            os.environ["YF_CACHE_DIR"] = tempfile.gettempdir()
            ticker = yf.Ticker("^IRX")
            hist = ticker.history(period="5d")
        finally:
            if old_cache is not None:
                os.environ["YF_CACHE_DIR"] = old_cache
            else:
                os.environ.pop("YF_CACHE_DIR", None)

        if hist.empty:
            logger.warning("^IRX history empty, using fallback rate %.2f%%", fallback * 100)
            return fallback

        # ^IRX quotes the annualised discount rate in percent (e.g. 4.3)
        latest_close = float(hist["Close"].dropna().iloc[-1])
        rate = latest_close / 100.0  # convert to decimal
        _rfr_cache[cache_key] = (rate, now)
        logger.info("Risk-free rate (13-week T-bill): %.3f%%", rate * 100)
        return rate
    except ImportError:
        logger.warning("yfinance not installed — using fallback rate %.2f%%", fallback * 100)
        return fallback
    except Exception as e:
        logger.warning("Failed to fetch ^IRX: %s — using fallback %.2f%%", e, fallback * 100)
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


# =============================================================================
# IV Percentile Rank Analysis
# =============================================================================

@dataclass
class IVAnalysis:
    """IV analysis result for a ticker."""
    ticker: str
    current_iv: float  # Current ATM IV
    hv: float  # Historical volatility
    vrp: float  # Volatility Risk Premium (IV - HV)
    # IV Percentile (requires historical IV data)
    iv_rank: Optional[float] = None  # (current - min) / (max - min) * 100
    iv_percentile: Optional[float] = None  # % of days IV was lower
    iv_min: Optional[float] = None  # Min IV in lookback
    iv_max: Optional[float] = None  # Max IV in lookback
    iv_mean: Optional[float] = None  # Mean IV in lookback
    lookback_days: Optional[int] = None
    # Interpretation
    signal: str = 'NEUTRAL'  # 'IV_HIGH', 'IV_LOW', 'NEUTRAL'
    as_of_date: date = field(default_factory=date.today)


def calculate_iv_rank(
    current_iv: float,
    iv_history: List[float],
) -> float:
    """
    Calculate IV Rank: where current IV sits relative to its range.

    Formula: (current - min) / (max - min) * 100

    Args:
        current_iv: Current implied volatility.
        iv_history: List of historical IV values.

    Returns:
        IV Rank as percentage (0-100).
        0 = at historical low, 100 = at historical high.

    Example:
        >>> iv_history = [0.20, 0.25, 0.30, 0.35, 0.40]
        >>> calculate_iv_rank(0.30, iv_history)
        50.0
    """
    if not iv_history:
        return 50.0  # No data, assume middle

    iv_min = min(iv_history)
    iv_max = max(iv_history)

    if iv_max == iv_min:
        return 50.0

    return float((current_iv - iv_min) / (iv_max - iv_min) * 100)


def calculate_iv_percentile(
    current_iv: float,
    iv_history: List[float],
) -> float:
    """
    Calculate IV Percentile: what % of historical days had lower IV.

    Args:
        current_iv: Current implied volatility.
        iv_history: List of historical IV values.

    Returns:
        IV Percentile as percentage (0-100).
        90 means current IV is higher than 90% of historical values.

    Example:
        >>> iv_history = [0.20, 0.25, 0.30, 0.35, 0.40]
        >>> calculate_iv_percentile(0.35, iv_history)
        60.0
    """
    if not iv_history:
        return 50.0

    below_count = sum(1 for iv in iv_history if iv < current_iv)
    return float(below_count / len(iv_history) * 100)


def analyze_iv_environment(
    ticker: str,
    current_iv: float,
    hv: float,
    iv_history: Optional[List[float]] = None,
    high_threshold: float = 80.0,
    low_threshold: float = 20.0,
) -> IVAnalysis:
    """
    Analyze the IV environment for a ticker.

    Provides VRP measurement and, if historical IV data is available,
    IV rank and percentile analysis.

    Args:
        ticker: Stock symbol.
        current_iv: Current ATM implied volatility.
        hv: Historical (realized) volatility.
        iv_history: Optional list of historical daily ATM IV values.
        high_threshold: IV percentile above this → IV_HIGH signal.
        low_threshold: IV percentile below this → IV_LOW signal.

    Returns:
        IVAnalysis with signal and metrics.
    """
    vrp = current_iv - hv

    result = IVAnalysis(
        ticker=ticker,
        current_iv=current_iv,
        hv=hv,
        vrp=vrp,
    )

    if iv_history and len(iv_history) >= 20:
        result.iv_rank = calculate_iv_rank(current_iv, iv_history)
        result.iv_percentile = calculate_iv_percentile(current_iv, iv_history)
        result.iv_min = min(iv_history)
        result.iv_max = max(iv_history)
        result.iv_mean = sum(iv_history) / len(iv_history)
        result.lookback_days = len(iv_history)

        # Generate signal based on IV percentile
        if result.iv_percentile >= high_threshold:
            result.signal = 'IV_HIGH'  # Options expensive → favor selling
        elif result.iv_percentile <= low_threshold:
            result.signal = 'IV_LOW'  # Options cheap → favor buying
        else:
            result.signal = 'NEUTRAL'
    else:
        # Without IV history, use VRP as rough guide
        # VRP > 1.5x typical → IV likely elevated
        if vrp > hv * 0.8:  # IV > 1.8x HV
            result.signal = 'IV_HIGH'
        elif vrp < hv * 0.1:  # IV barely above HV
            result.signal = 'IV_LOW'

    return result


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