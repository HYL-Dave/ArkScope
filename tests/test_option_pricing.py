#!/usr/bin/env python3
"""
Unit tests for option pricing module.

These tests do NOT require IBKR connection - they test the pure math functions.

Run with:
    pytest tests/test_option_pricing.py -v

Or directly:
    python tests/test_option_pricing.py
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import math
from analysis.option_pricing import (
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
)


class TestBlackScholes:
    """Test Black-Scholes pricing and Greeks."""

    def test_atm_call_price(self):
        """ATM call should have predictable price."""
        # S=K=100, T=0.25 (3 months), r=5%, sigma=20%
        price = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='C')
        # Expected ~4.61 based on standard BS
        assert 4.5 < price < 4.8, f"ATM call price {price} out of expected range"

    def test_atm_put_price(self):
        """ATM put should satisfy put-call parity."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.20
        call = black_scholes_price(S, K, T, r, sigma, 'C')
        put = black_scholes_price(S, K, T, r, sigma, 'P')

        # Put-call parity: C - P = S - K*e^(-rT)
        parity_diff = call - put
        expected_diff = S - K * math.exp(-r * T)

        assert abs(parity_diff - expected_diff) < 0.01, "Put-call parity violated"

    def test_deep_itm_call(self):
        """Deep ITM call should be close to intrinsic value."""
        # S=150, K=100 (deep ITM)
        price = black_scholes_price(S=150, K=100, T=0.25, r=0.05, sigma=0.20, option_type='C')
        intrinsic = 150 - 100  # 50

        assert price > intrinsic, "ITM call should be worth more than intrinsic"
        assert price < intrinsic + 5, "ITM call time value should be small"

    def test_deep_otm_call(self):
        """Deep OTM call should be close to zero."""
        # S=50, K=100 (deep OTM)
        price = black_scholes_price(S=50, K=100, T=0.25, r=0.05, sigma=0.20, option_type='C')

        assert price < 0.01, f"Deep OTM call should be nearly zero, got {price}"

    def test_expired_option(self):
        """Expired option should return intrinsic value."""
        # ITM at expiration
        call_itm = black_scholes_price(S=110, K=100, T=0, r=0.05, sigma=0.20, option_type='C')
        assert call_itm == 10, "Expired ITM call should equal intrinsic"

        # OTM at expiration
        call_otm = black_scholes_price(S=90, K=100, T=0, r=0.05, sigma=0.20, option_type='C')
        assert call_otm == 0, "Expired OTM call should be zero"

    def test_greeks_delta_range(self):
        """Delta should be between 0 and 1 for calls, -1 to 0 for puts."""
        greeks = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='C')

        assert 0 < greeks['delta'] < 1, f"Call delta {greeks['delta']} out of range"
        assert greeks['gamma'] > 0, "Gamma should be positive"
        assert greeks['theta'] < 0, "Theta should be negative (time decay)"
        assert greeks['vega'] > 0, "Vega should be positive"

    def test_greeks_atm_delta(self):
        """ATM call delta should be close to 0.5."""
        greeks = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type='C')

        # ATM delta is slightly above 0.5 due to drift
        assert 0.5 < greeks['delta'] < 0.6, f"ATM delta {greeks['delta']} unexpected"


class TestImpliedVolatility:
    """Test implied volatility calculation."""

    def test_iv_recovery(self):
        """IV calculation should recover the original volatility."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.25

        # Calculate price with known vol
        price = black_scholes_price(S, K, T, r, sigma, 'C')

        # Recover IV
        iv = calculate_implied_volatility(price, S, K, T, r, 'C')

        assert iv is not None, "IV calculation failed"
        assert abs(iv - sigma) < 0.001, f"IV {iv} doesn't match original {sigma}"

    def test_iv_various_strikes(self):
        """IV should be recoverable across strike range."""
        S, T, r, sigma = 100, 0.25, 0.05, 0.30

        for K in [80, 90, 100, 110, 120]:
            price = black_scholes_price(S, K, T, r, sigma, 'C')
            iv = calculate_implied_volatility(price, S, K, T, r, 'C')

            if iv is not None:
                assert abs(iv - sigma) < 0.01, f"IV mismatch at K={K}"

    def test_iv_put(self):
        """IV should work for puts too."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.25

        price = black_scholes_price(S, K, T, r, sigma, 'P')
        iv = calculate_implied_volatility(price, S, K, T, r, 'P')

        assert iv is not None
        assert abs(iv - sigma) < 0.001


class TestHistoricalVolatility:
    """Test historical volatility calculations."""

    def test_close_to_close_hv(self):
        """Close-to-close HV should be reasonable."""
        # Simulate 30 days of 1% daily moves
        prices = [100]
        for i in range(30):
            prices.append(prices[-1] * (1 + 0.01 * (1 if i % 2 == 0 else -1)))

        hv = calculate_close_to_close_volatility(prices)

        # 1% daily vol * sqrt(252) ≈ 15.9% annual
        assert 0.10 < hv < 0.25, f"HV {hv} out of expected range"

    def test_hv_with_ohlc(self):
        """Garman-Klass should work with OHLC data."""
        ohlc_data = [
            {'open': 100, 'high': 102, 'low': 99, 'close': 101},
            {'open': 101, 'high': 103, 'low': 100, 'close': 102},
            {'open': 102, 'high': 104, 'low': 101, 'close': 103},
            {'open': 103, 'high': 105, 'low': 102, 'close': 104},
            {'open': 104, 'high': 106, 'low': 103, 'close': 105},
        ]

        hv = calculate_historical_volatility(ohlc_data, method='garman_klass')

        assert hv > 0, "HV should be positive"
        assert hv < 1.0, "HV should be reasonable"

    def test_hv_empty_input(self):
        """HV should handle empty input gracefully."""
        hv = calculate_historical_volatility([])
        assert hv == 0.0

    def test_parkinson_vs_close_to_close(self):
        """Parkinson should capture more volatility when there are ranges."""
        # Data with significant intraday ranges
        ohlc_data = [
            {'open': 100, 'high': 105, 'low': 95, 'close': 100},  # Big range, close unchanged
            {'open': 100, 'high': 106, 'low': 94, 'close': 100},
            {'open': 100, 'high': 107, 'low': 93, 'close': 100},
            {'open': 100, 'high': 108, 'low': 92, 'close': 100},
            {'open': 100, 'high': 109, 'low': 91, 'close': 100},
        ]

        hv_cc = calculate_historical_volatility(ohlc_data, method='close_to_close')
        hv_park = calculate_historical_volatility(ohlc_data, method='parkinson')

        # Parkinson should capture the range volatility, close-to-close won't
        assert hv_park > hv_cc, "Parkinson should capture range volatility"


class TestVolatilitySmile:
    """Test volatility smile adjustment."""

    def test_atm_no_adjustment(self):
        """ATM should have minimal adjustment."""
        atm_vol = 0.25
        adj_vol = adjust_volatility_for_smile(atm_vol, S=100, K=100, T=0.25)

        # Should be close to original
        assert abs(adj_vol - atm_vol) < 0.02, "ATM shouldn't change much"

    def test_otm_put_skew(self):
        """OTM puts should have higher IV (typical equity skew)."""
        atm_vol = 0.25

        # OTM put (K < S)
        otm_put_vol = adjust_volatility_for_smile(atm_vol, S=100, K=90, T=0.25)

        # With default negative skew, OTM puts should have higher IV
        assert otm_put_vol > atm_vol, "OTM put should have skew premium"


class TestMispricingAnalysis:
    """Test mispricing detection."""

    def test_overpriced_option(self):
        """Should detect overpriced option."""
        signal = analyze_option_mispricing(
            underlying='TEST',
            expiry='20260301',
            strike=100,
            right='C',
            market_bid=8.0,
            market_ask=8.5,
            spot_price=100,
            historical_vol=0.20,
            risk_free_rate=0.05,
            days_to_expiry=30,
            mispricing_threshold_pct=10.0,
        )

        # With 20% vol, ATM 30-day call is ~$3.30
        # Market is $8.25 mid - significantly overpriced
        assert signal.signal == 'SELL', f"Should be SELL signal, got {signal.signal}"
        assert signal.mispricing_pct > 50, "Should be significantly mispriced"

    def test_underpriced_option(self):
        """Should detect underpriced option."""
        signal = analyze_option_mispricing(
            underlying='TEST',
            expiry='20260301',
            strike=100,
            right='C',
            market_bid=1.0,
            market_ask=1.5,
            spot_price=100,
            historical_vol=0.30,
            risk_free_rate=0.05,
            days_to_expiry=30,
            mispricing_threshold_pct=10.0,
        )

        # With 30% vol, ATM 30-day call is ~$4.80
        # Market is $1.25 mid - significantly underpriced
        assert signal.signal == 'BUY', f"Should be BUY signal, got {signal.signal}"
        assert signal.mispricing_pct < -50, "Should be significantly underpriced"

    def test_fair_priced_option(self):
        """Should be neutral for fairly priced option."""
        # First calculate theoretical price
        S, K, T, r, sigma = 100, 100, 30/365, 0.05, 0.25
        theo = black_scholes_price(S, K, T, r, sigma, 'C')

        signal = analyze_option_mispricing(
            underlying='TEST',
            expiry='20260301',
            strike=100,
            right='C',
            market_bid=theo - 0.10,
            market_ask=theo + 0.10,
            spot_price=100,
            historical_vol=0.25,
            risk_free_rate=0.05,
            days_to_expiry=30,
            mispricing_threshold_pct=10.0,
            use_smile_adjustment=False,  # Disable smile for fair comparison
        )

        assert signal.signal == 'NEUTRAL', f"Should be NEUTRAL, got {signal.signal}"
        assert abs(signal.mispricing_pct) < 10, "Should be within threshold"

    def test_scan_multiple_options(self):
        """Should scan and filter multiple options."""
        quotes = [
            {'underlying': 'TEST', 'expiry': '20260301', 'strike': 100, 'right': 'C', 'bid': 8.0, 'ask': 8.5},  # Overpriced
            {'underlying': 'TEST', 'expiry': '20260301', 'strike': 100, 'right': 'P', 'bid': 3.0, 'ask': 3.5},  # Fair
            {'underlying': 'TEST', 'expiry': '20260301', 'strike': 105, 'right': 'C', 'bid': 0.5, 'ask': 1.0},  # Maybe underpriced
        ]

        signals = scan_options_for_mispricing(
            quotes=quotes,
            spot_price=100,
            historical_vol=0.20,
            risk_free_rate=0.05,
            mispricing_threshold_pct=10.0,
            min_confidence='LOW',
        )

        assert len(signals) >= 1, "Should find at least one signal"
        # First signal should be the most mispriced
        assert signals[0].right == 'C' and signals[0].strike == 100


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_time_to_expiry(self):
        """Should handle T=0 gracefully."""
        price = black_scholes_price(S=100, K=100, T=0, r=0.05, sigma=0.20, option_type='C')
        assert price == 0, "ATM at expiration should be 0"

        greeks = black_scholes_greeks(S=100, K=100, T=0, r=0.05, sigma=0.20, option_type='C')
        assert greeks['delta'] == 0

    def test_very_high_volatility(self):
        """Should handle extreme volatility."""
        price = black_scholes_price(S=100, K=100, T=0.25, r=0.05, sigma=2.0, option_type='C')
        assert price > 0 and price < 100, "Price should be reasonable even with 200% vol"

    def test_negative_price_iv(self):
        """IV calculation should handle invalid prices."""
        # Price below intrinsic
        iv = calculate_implied_volatility(
            market_price=5,  # Below intrinsic of 10
            S=110, K=100, T=0.25, r=0.05, option_type='C'
        )
        assert iv is None, "Should return None for invalid price"


def run_quick_test():
    """Run a quick sanity check without pytest."""
    print("Running quick sanity tests...")
    print("=" * 50)

    # Test 1: Black-Scholes
    print("\n1. Black-Scholes ATM pricing:")
    call = black_scholes_price(100, 100, 0.25, 0.05, 0.20, 'C')
    put = black_scholes_price(100, 100, 0.25, 0.05, 0.20, 'P')
    print(f"   Call: ${call:.2f}, Put: ${put:.2f}")
    assert 4 < call < 5, "Call price unexpected"
    print("   ✓ Pass")

    # Test 2: Greeks
    print("\n2. Greeks calculation:")
    greeks = black_scholes_greeks(100, 100, 0.25, 0.05, 0.20, 'C')
    print(f"   Delta: {greeks['delta']:.3f}, Gamma: {greeks['gamma']:.4f}")
    assert 0.5 < greeks['delta'] < 0.6, "Delta unexpected"
    print("   ✓ Pass")

    # Test 3: IV recovery
    print("\n3. Implied Volatility recovery:")
    iv = calculate_implied_volatility(call, 100, 100, 0.25, 0.05, 'C')
    print(f"   Original: 20%, Recovered: {iv:.1%}")
    assert abs(iv - 0.20) < 0.001, "IV recovery failed"
    print("   ✓ Pass")

    # Test 4: Historical Volatility
    print("\n4. Historical Volatility:")
    prices = [100 + i * 0.5 for i in range(30)]
    hv = calculate_historical_volatility(prices)
    print(f"   HV (trending data): {hv:.1%}")
    assert hv > 0, "HV should be positive"
    print("   ✓ Pass")

    # Test 5: Mispricing
    print("\n5. Mispricing detection:")
    signal = analyze_option_mispricing(
        'TEST', '20260301', 100, 'C',
        market_bid=8.0, market_ask=8.5,
        spot_price=100, historical_vol=0.20
    )
    print(f"   Signal: {signal.signal} ({signal.confidence})")
    print(f"   Mispricing: {signal.mispricing_pct:+.1f}%")
    assert signal.signal == 'SELL', "Should detect overpricing"
    print("   ✓ Pass")

    print("\n" + "=" * 50)
    print("All quick tests passed! ✓")
    print("\nFor full test suite, run: pytest tests/test_option_pricing.py -v")


if __name__ == '__main__':
    run_quick_test()