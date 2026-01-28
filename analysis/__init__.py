"""
Analysis Module for MindfulRL-Intraday.

This module provides analytical tools for options pricing, volatility analysis,
and trading signal generation.

Modules:
    option_pricing: Black-Scholes pricing, Greeks, HV, IV, mispricing detection
"""

from .option_pricing import (
    # Volatility
    calculate_historical_volatility,
    calculate_close_to_close_volatility,
    calculate_parkinson_volatility,
    calculate_garman_klass_volatility,
    calculate_implied_volatility,
    adjust_volatility_for_smile,
    # Pricing
    black_scholes_price,
    black_scholes_greeks,
    calculate_theoretical_price,
    # Mispricing
    analyze_option_mispricing,
    scan_options_for_mispricing,
    # Utilities
    get_risk_free_rate,
    calculate_days_to_expiry,
    # Data classes
    VolatilityEstimate,
    TheoreticalPrice,
    MispricingSignal,
    OptionType,
)

__all__ = [
    # Volatility
    'calculate_historical_volatility',
    'calculate_close_to_close_volatility',
    'calculate_parkinson_volatility',
    'calculate_garman_klass_volatility',
    'calculate_implied_volatility',
    'adjust_volatility_for_smile',
    # Pricing
    'black_scholes_price',
    'black_scholes_greeks',
    'calculate_theoretical_price',
    # Mispricing
    'analyze_option_mispricing',
    'scan_options_for_mispricing',
    # Utilities
    'get_risk_free_rate',
    'calculate_days_to_expiry',
    # Data classes
    'VolatilityEstimate',
    'TheoreticalPrice',
    'MispricingSignal',
    'OptionType',
]

__version__ = '0.1.0'