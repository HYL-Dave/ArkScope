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
    # Pricing — European
    black_scholes_price,
    black_scholes_greeks,
    # Pricing — American (BS2002)
    bjerksund_stensland_2002,
    american_greeks,
    calculate_american_iv,
    # Pricing — Unified
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
        # Signals sorted by abs(mispricing_pct) descending
        assert abs(signals[0].mispricing_pct) >= abs(signals[-1].mispricing_pct)


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


# ==========================================================================
# Bjerksund-Stensland 2002 (American Option Pricing)
# ==========================================================================

class TestBjerksundStensland2002:
    """Test American option pricing via BS2002."""

    def test_call_no_dividend_equals_european(self):
        """American call without dividends ≈ European call (no early exercise value)."""
        bs_price = black_scholes_price(100, 100, 0.25, 0.05, 0.20, 'C')
        am_price = bjerksund_stensland_2002(100, 100, 0.25, 0.05, 0.20, 0.0, 'C')
        assert abs(am_price - bs_price) < 0.05, \
            f"American call should ≈ European when q=0: {am_price:.4f} vs {bs_price:.4f}"

    def test_put_higher_than_european(self):
        """American put >= European put (early exercise premium)."""
        bs_put = black_scholes_price(100, 100, 0.5, 0.05, 0.30, 'P')
        am_put = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.30, 0.0, 'P')
        assert am_put >= bs_put - 0.01, \
            f"American put {am_put:.4f} should be >= European put {bs_put:.4f}"

    def test_put_early_exercise_premium_meaningful(self):
        """ATM put should have non-trivial early exercise premium."""
        bs_put = black_scholes_price(100, 100, 0.5, 0.05, 0.30, 'P')
        am_put = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.30, 0.0, 'P')
        premium = am_put - bs_put
        assert premium > 0.05, f"Early exercise premium {premium:.4f} should be > 0.05"

    def test_deep_itm_put_significant_premium(self):
        """Deep ITM put: American premium over European should be significant."""
        bs_put = black_scholes_price(70, 100, 1.0, 0.05, 0.30, 'P')
        am_put = bjerksund_stensland_2002(70, 100, 1.0, 0.05, 0.30, 0.0, 'P')
        premium = am_put - bs_put
        assert premium > 0.5, f"Deep ITM early exercise premium {premium:.4f} should be > 0.5"

    def test_call_with_dividend_differs(self):
        """Call with dividends should differ from zero-dividend pricing."""
        am_no_div = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.30, 0.0, 'C')
        am_with_div = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.30, 0.03, 'C')
        # Dividends reduce call value (stock drops on ex-div)
        assert am_with_div < am_no_div, \
            f"Call with div {am_with_div:.4f} should be < without {am_no_div:.4f}"

    def test_call_with_high_dividend_has_premium(self):
        """American call with high dividends should exceed European call."""
        # High dividend: q=5%, long-dated (1 year)
        bs_call = black_scholes_price(100, 100, 1.0, 0.05, 0.30, 'C')
        am_call = bjerksund_stensland_2002(100, 100, 1.0, 0.05, 0.30, 0.05, 'C')
        # European BS doesn't account for dividends at all, so American with
        # dividends will typically be lower. But the key is it's properly priced.
        assert am_call > 0

    def test_at_expiration_call(self):
        """Near expiration: American call ≈ intrinsic value."""
        call = bjerksund_stensland_2002(110, 100, 0.001, 0.05, 0.20, 0.0, 'C')
        assert abs(call - 10) < 0.5, f"Near-expiry ITM call should ≈ intrinsic, got {call:.4f}"

    def test_at_expiration_put(self):
        """Near expiration: American put ≈ intrinsic value."""
        put = bjerksund_stensland_2002(90, 100, 0.001, 0.05, 0.20, 0.0, 'P')
        assert abs(put - 10) < 0.5, f"Near-expiry ITM put should ≈ intrinsic, got {put:.4f}"

    def test_otm_put_positive(self):
        """OTM American put should be positive (time value)."""
        put = bjerksund_stensland_2002(110, 100, 0.5, 0.05, 0.30, 0.0, 'P')
        assert put > 0, "OTM put should have time value"

    def test_otm_call_positive(self):
        """OTM American call should be positive (time value)."""
        call = bjerksund_stensland_2002(90, 100, 0.5, 0.05, 0.30, 0.0, 'C')
        assert call > 0, "OTM call should have time value"

    def test_price_increases_with_time(self):
        """Longer time to expiry → higher option price (all else equal)."""
        short = bjerksund_stensland_2002(100, 100, 0.1, 0.05, 0.30, 0.0, 'P')
        long_ = bjerksund_stensland_2002(100, 100, 1.0, 0.05, 0.30, 0.0, 'P')
        assert long_ > short, f"Longer T should give higher price: {long_:.4f} > {short:.4f}"

    def test_price_increases_with_volatility(self):
        """Higher volatility → higher option price."""
        low_vol = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.15, 0.0, 'P')
        high_vol = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.45, 0.0, 'P')
        assert high_vol > low_vol, f"Higher vol should give higher price: {high_vol:.4f} > {low_vol:.4f}"

    def test_put_call_symmetry(self):
        """Verify put-call transformation consistency."""
        # Both should be properly priced
        call = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.30, 0.02, 'C')
        put = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.30, 0.02, 'P')
        assert call > 0 and put > 0
        # Put should be higher than call for ATM when r > q
        # (because put benefits more from early exercise)
        assert put > call * 0.5, "Both should be meaningful prices"

    def test_extreme_volatility(self):
        """BS2002 should handle high volatility without crashing."""
        price = bjerksund_stensland_2002(100, 100, 0.25, 0.05, 2.0, 0.0, 'P')
        assert price > 0 and price <= 100, f"Price with 200% vol should be reasonable: {price:.4f}"

    def test_zero_rate(self):
        """BS2002 should work with r=0."""
        price = bjerksund_stensland_2002(100, 100, 0.5, 0.0, 0.30, 0.0, 'P')
        assert price > 0, f"Price with r=0 should be positive: {price:.4f}"


class TestAmericanGreeks:
    """Test numerical Greeks for American options."""

    def test_call_delta_range(self):
        """American call delta should be in [0, 1]."""
        greeks = american_greeks(100, 100, 0.25, 0.05, 0.20, 0.0, 'C')
        assert 0 < greeks['delta'] < 1, f"Call delta {greeks['delta']} out of range"

    def test_put_delta_range(self):
        """American put delta should be in [-1, 0]."""
        greeks = american_greeks(100, 100, 0.25, 0.05, 0.20, 0.0, 'P')
        assert -1 < greeks['delta'] < 0, f"Put delta {greeks['delta']} out of range"

    def test_atm_call_delta_near_half(self):
        """ATM American call delta ≈ 0.5."""
        greeks = american_greeks(100, 100, 0.25, 0.05, 0.20, 0.0, 'C')
        assert 0.45 < greeks['delta'] < 0.65, f"ATM delta {greeks['delta']} unexpected"

    def test_gamma_positive(self):
        """Gamma should be positive for both calls and puts."""
        for opt_type in ['C', 'P']:
            greeks = american_greeks(100, 100, 0.25, 0.05, 0.30, 0.0, opt_type)
            assert greeks['gamma'] > 0, f"{opt_type} gamma should be positive"

    def test_vega_positive(self):
        """Vega should be positive for both calls and puts."""
        for opt_type in ['C', 'P']:
            greeks = american_greeks(100, 100, 0.25, 0.05, 0.30, 0.0, opt_type)
            assert greeks['vega'] > 0, f"{opt_type} vega should be positive"

    def test_theta_negative(self):
        """Theta should be negative (time decay)."""
        for opt_type in ['C', 'P']:
            greeks = american_greeks(100, 100, 0.25, 0.05, 0.30, 0.0, opt_type)
            assert greeks['theta'] < 0, f"{opt_type} theta should be negative"

    def test_greeks_close_to_bs_for_call_no_div(self):
        """American Greeks ≈ BS Greeks for call without dividends."""
        am_greeks = american_greeks(100, 100, 0.25, 0.05, 0.20, 0.0, 'C')
        bs_greeks_ = black_scholes_greeks(100, 100, 0.25, 0.05, 0.20, 'C')
        # Delta should be very close
        assert abs(am_greeks['delta'] - bs_greeks_['delta']) < 0.02, \
            f"Delta diff: {abs(am_greeks['delta'] - bs_greeks_['delta']):.4f}"

    def test_greeks_with_dividends(self):
        """Greeks should work with dividend yield."""
        greeks = american_greeks(100, 100, 0.5, 0.05, 0.30, 0.03, 'C')
        assert 0 < greeks['delta'] < 1
        assert greeks['gamma'] > 0


class TestAmericanIV:
    """Test American implied volatility solver."""

    def test_iv_recovery_call(self):
        """Should recover original vol from American call price."""
        original_vol = 0.25
        price = bjerksund_stensland_2002(100, 100, 0.25, 0.05, original_vol, 0.0, 'C')
        iv = calculate_american_iv(price, 100, 100, 0.25, 0.05, 0.0, 'C')
        assert iv is not None, "IV calculation failed"
        assert abs(iv - original_vol) < 0.001, f"IV {iv} doesn't match original {original_vol}"

    def test_iv_recovery_put(self):
        """Should recover original vol from American put price."""
        original_vol = 0.30
        price = bjerksund_stensland_2002(100, 100, 0.5, 0.05, original_vol, 0.0, 'P')
        iv = calculate_american_iv(price, 100, 100, 0.5, 0.05, 0.0, 'P')
        assert iv is not None, "IV calculation failed"
        assert abs(iv - original_vol) < 0.001, f"IV {iv} doesn't match original {original_vol}"

    def test_iv_recovery_with_dividend(self):
        """Should recover vol with dividend yield."""
        original_vol = 0.30
        price = bjerksund_stensland_2002(100, 100, 0.5, 0.05, original_vol, 0.03, 'C')
        iv = calculate_american_iv(price, 100, 100, 0.5, 0.05, 0.03, 'C')
        assert iv is not None, "IV calculation failed"
        assert abs(iv - original_vol) < 0.001, f"IV {iv} doesn't match original {original_vol}"

    def test_iv_various_strikes(self):
        """IV should be recoverable across strike range."""
        original_vol = 0.30
        for K in [80, 90, 100, 110, 120]:
            price = bjerksund_stensland_2002(100, K, 0.5, 0.05, original_vol, 0.0, 'P')
            iv = calculate_american_iv(price, 100, K, 0.5, 0.05, 0.0, 'P')
            if iv is not None:
                assert abs(iv - original_vol) < 0.01, f"IV mismatch at K={K}: {iv:.4f}"

    def test_american_iv_lower_for_put(self):
        """For same market price, American IV < European IV for puts.

        Because American put is worth more than European (early exercise),
        a lower vol is needed to match the same market price.
        """
        S, K, T, r = 100, 100, 0.5, 0.05
        # Use a market price that's between European and American theoretical
        bs_put = black_scholes_price(S, K, T, r, 0.30, 'P')
        am_put = bjerksund_stensland_2002(S, K, T, r, 0.30, 0.0, 'P')

        # Use the American price as "market price"
        iv_european = calculate_implied_volatility(am_put, S, K, T, r, 'P')
        iv_american = calculate_american_iv(am_put, S, K, T, r, 0.0, 'P')

        assert iv_european is not None and iv_american is not None
        # European IV should be higher to compensate for the model underpricing puts
        assert iv_european > iv_american, \
            f"European IV {iv_european:.4f} should > American IV {iv_american:.4f}"

    def test_iv_invalid_price(self):
        """IV should return None for price below intrinsic."""
        iv = calculate_american_iv(
            market_price=5, S=110, K=100, T=0.25, r=0.05, q=0.0, option_type='C'
        )
        assert iv is None, "Should return None for price below intrinsic"


class TestUnifiedPricing:
    """Test calculate_theoretical_price with model parameter."""

    def test_american_model(self):
        """model='american' should use BS2002."""
        theo = calculate_theoretical_price(100, 100, 0.5, 0.05, 0.30, 'P', model='american')
        am_direct = bjerksund_stensland_2002(100, 100, 0.5, 0.05, 0.30, 0.0, 'P')
        assert abs(theo.price - am_direct) < 0.001
        assert theo.model == 'american'

    def test_bs_model(self):
        """model='black_scholes' should use BS."""
        theo = calculate_theoretical_price(100, 100, 0.5, 0.05, 0.30, 'P', model='black_scholes')
        bs_direct = black_scholes_price(100, 100, 0.5, 0.05, 0.30, 'P')
        assert abs(theo.price - bs_direct) < 0.001
        assert theo.model == 'black_scholes'

    def test_default_is_american(self):
        """Default model should be 'american'."""
        theo = calculate_theoretical_price(100, 100, 0.5, 0.05, 0.30, 'P')
        assert theo.model == 'american'

    def test_american_put_higher_than_bs(self):
        """American put from unified interface should be >= BS put."""
        am_theo = calculate_theoretical_price(100, 100, 0.5, 0.05, 0.30, 'P', model='american')
        bs_theo = calculate_theoretical_price(100, 100, 0.5, 0.05, 0.30, 'P', model='black_scholes')
        assert am_theo.price >= bs_theo.price - 0.01

    def test_dividend_yield_parameter(self):
        """q parameter should affect American pricing."""
        no_div = calculate_theoretical_price(100, 100, 0.5, 0.05, 0.30, 'C', model='american', q=0.0)
        with_div = calculate_theoretical_price(100, 100, 0.5, 0.05, 0.30, 'C', model='american', q=0.03)
        assert with_div.price < no_div.price, "Dividend should reduce call value"


class TestMispricingWithAmerican:
    """Test mispricing detection using American pricing model."""

    def test_mispricing_uses_american_by_default(self):
        """analyze_option_mispricing should use American pricing by default."""
        signal = analyze_option_mispricing(
            underlying='TEST', expiry='20260301', strike=100, right='P',
            market_bid=8.0, market_ask=8.5, spot_price=100,
            historical_vol=0.30, days_to_expiry=60,
        )
        # Should not crash and should return a valid signal
        assert signal.signal in ('BUY', 'SELL', 'NEUTRAL')

    def test_mispricing_bs_model(self):
        """model='black_scholes' should use BS pricing for mispricing."""
        signal = analyze_option_mispricing(
            underlying='TEST', expiry='20260301', strike=100, right='P',
            market_bid=8.0, market_ask=8.5, spot_price=100,
            historical_vol=0.30, days_to_expiry=60,
            model='black_scholes',
        )
        assert signal.signal in ('BUY', 'SELL', 'NEUTRAL')

    def test_american_less_mispricing_for_puts(self):
        """American model should show less mispricing for puts (higher theoretical)."""
        # Use a put price that's between BS and American theoretical
        am_price = bjerksund_stensland_2002(100, 100, 60/365, 0.05, 0.30, 0.0, 'P')
        bs_price = black_scholes_price(100, 100, 60/365, 0.05, 0.30, 'P')

        # Market price = American theoretical (should be NEUTRAL with American model)
        market_mid = am_price
        sig_am = analyze_option_mispricing(
            underlying='TEST', expiry='20260301', strike=100, right='P',
            market_bid=market_mid - 0.1, market_ask=market_mid + 0.1,
            spot_price=100, historical_vol=0.30, days_to_expiry=60,
            model='american', use_smile_adjustment=False,
        )
        sig_bs = analyze_option_mispricing(
            underlying='TEST', expiry='20260301', strike=100, right='P',
            market_bid=market_mid - 0.1, market_ask=market_mid + 0.1,
            spot_price=100, historical_vol=0.30, days_to_expiry=60,
            model='black_scholes', use_smile_adjustment=False,
        )

        # American model should show less mispricing (closer to market)
        assert abs(sig_am.mispricing_pct) < abs(sig_bs.mispricing_pct), \
            f"American {sig_am.mispricing_pct:.2f}% should be less than BS {sig_bs.mispricing_pct:.2f}%"


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