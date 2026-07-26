"""Pure option-pricing tool functions."""

from __future__ import annotations

from typing import Dict


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "C",
    model: str = "american",
    dividend_yield: float = 0.0,
) -> Dict[str, float]:
    """
    Calculate option Greeks.

    Pure calculation — no data access needed.

    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (e.g. 0.05 for 5%)
        sigma: Volatility (e.g. 0.30 for 30%)
        option_type: 'C' for call, 'P' for put
        model: 'american' (Bjerksund-Stensland 2002) or 'black_scholes'
        dividend_yield: Continuous dividend yield (for 'american' model)

    Returns:
        Dict with delta, gamma, theta, vega, rho, model
    """
    if model == "american":
        from src.options_math import american_greeks
        greeks = american_greeks(S, K, T, r, sigma, dividend_yield, option_type)
    else:
        from src.options_math import black_scholes_greeks
        greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)

    return {
        "spot": S,
        "strike": K,
        "time_to_expiry": T,
        "risk_free_rate": r,
        "volatility": sigma,
        "option_type": option_type,
        "model": model,
        "dividend_yield": dividend_yield,
        "delta": round(greeks["delta"], 6),
        "gamma": round(greeks["gamma"], 6),
        "theta": round(greeks["theta"], 6),
        "vega": round(greeks["vega"], 6),
        "rho": round(greeks["rho"], 6),
    }
