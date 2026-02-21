"""
Tests for option chain analysis tool (Batch 2a).
"""

from __future__ import annotations

import pytest


# ============================================================
# Pure calculation tests (no IBKR required)
# ============================================================

class TestMaxPain:
    """Test _calculate_max_pain() pure function."""

    def test_basic_max_pain(self):
        from src.tools.option_chain_tools import _calculate_max_pain

        calls = [
            {"strike": 100.0, "oi": 500},
            {"strike": 105.0, "oi": 1000},
            {"strike": 110.0, "oi": 200},
        ]
        puts = [
            {"strike": 100.0, "oi": 300},
            {"strike": 105.0, "oi": 800},
            {"strike": 110.0, "oi": 100},
        ]
        strikes = [100.0, 105.0, 110.0]
        result = _calculate_max_pain(calls, puts, strikes)
        assert result is not None
        assert result in strikes

    def test_max_pain_favors_high_oi(self):
        """Max pain should be near the strike with highest combined OI."""
        from src.tools.option_chain_tools import _calculate_max_pain

        calls = [
            {"strike": 90.0, "oi": 100},
            {"strike": 100.0, "oi": 5000},
            {"strike": 110.0, "oi": 100},
        ]
        puts = [
            {"strike": 90.0, "oi": 100},
            {"strike": 100.0, "oi": 5000},
            {"strike": 110.0, "oi": 100},
        ]
        strikes = [90.0, 100.0, 110.0]
        result = _calculate_max_pain(calls, puts, strikes)
        # With massive OI at 100, max pain should be at or near 100
        assert result == 100.0

    def test_empty_data(self):
        from src.tools.option_chain_tools import _calculate_max_pain

        assert _calculate_max_pain([], [], []) is None
        assert _calculate_max_pain([], [], [100.0]) is None

    def test_none_oi_treated_as_zero(self):
        from src.tools.option_chain_tools import _calculate_max_pain

        calls = [{"strike": 100.0, "oi": None}]
        puts = [{"strike": 100.0, "oi": None}]
        result = _calculate_max_pain(calls, puts, [100.0])
        assert result == 100.0


class TestExpirySelection:
    """Test _select_nearest_expiry()."""

    def test_picks_nearest_valid(self):
        from src.tools.option_chain_tools import _select_nearest_expiry
        from datetime import date, timedelta

        today = date.today()
        exps = [
            (today + timedelta(days=3)).strftime("%Y%m%d"),   # too close (< 7 DTE)
            (today + timedelta(days=10)).strftime("%Y%m%d"),  # valid
            (today + timedelta(days=30)).strftime("%Y%m%d"),  # valid but farther
        ]
        result = _select_nearest_expiry(exps, min_dte=7)
        assert result == exps[1]

    def test_fallback_if_all_too_close(self):
        from src.tools.option_chain_tools import _select_nearest_expiry
        from datetime import date, timedelta

        today = date.today()
        exps = [
            (today + timedelta(days=2)).strftime("%Y%m%d"),
            (today + timedelta(days=5)).strftime("%Y%m%d"),
        ]
        result = _select_nearest_expiry(exps, min_dte=7)
        # Should fallback to nearest positive DTE
        assert result == exps[0]

    def test_empty_list(self):
        from src.tools.option_chain_tools import _select_nearest_expiry

        assert _select_nearest_expiry([]) is None


class TestATMStrikes:
    """Test _select_atm_strikes()."""

    def test_selects_around_spot(self):
        from src.tools.option_chain_tools import _select_atm_strikes

        strikes = [90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0]
        result = _select_atm_strikes(strikes, spot=102.0, num_strikes=2)
        # Should pick 2 above and 2 below ATM (100 is closest)
        assert 100.0 in result
        assert 105.0 in result
        assert len(result) <= 5  # 2 below + ATM + 2 above

    def test_edge_at_boundary(self):
        from src.tools.option_chain_tools import _select_atm_strikes

        strikes = [100.0, 105.0, 110.0]
        result = _select_atm_strikes(strikes, spot=100.0, num_strikes=5)
        # Should return all available even if fewer than requested
        assert result == [100.0, 105.0, 110.0]


class TestFormatQuote:
    """Test _format_quote()."""

    def test_basic_formatting(self):
        from src.tools.option_chain_tools import _format_quote
        from dataclasses import dataclass
        from typing import Optional

        @dataclass
        class MockQuote:
            strike: float = 100.0
            bid: Optional[float] = 2.0
            ask: Optional[float] = 2.20
            last: Optional[float] = 2.10
            volume: Optional[int] = 500
            open_interest: Optional[int] = 1000
            implied_vol: Optional[float] = 0.35
            delta: Optional[float] = 0.55

        q = MockQuote()
        result = _format_quote(q)
        assert result["strike"] == 100.0
        assert result["bid"] == 2.0
        assert result["ask"] == 2.20
        assert result["volume"] == 500
        assert result["oi"] == 1000
        assert result["iv"] == 0.35
        assert result["delta"] == 0.55
        assert result["spread_pct"] is not None
        # spread = (2.20 - 2.0) / 2.10 * 100 ≈ 9.52%
        assert 9.0 < result["spread_pct"] < 10.0


class TestTermStructureExpiries:
    """Test _select_term_structure_expiries()."""

    def test_even_spacing(self):
        from src.tools.option_chain_tools import _select_term_structure_expiries
        from datetime import date, timedelta

        today = date.today()
        exps = [
            (today + timedelta(days=d)).strftime("%Y%m%d")
            for d in range(7, 180, 7)  # Weekly for ~6 months
        ]
        result = _select_term_structure_expiries(exps, max_count=4)
        assert len(result) == 4

    def test_fewer_than_max(self):
        from src.tools.option_chain_tools import _select_term_structure_expiries
        from datetime import date, timedelta

        today = date.today()
        exps = [(today + timedelta(days=d)).strftime("%Y%m%d") for d in [7, 14]]
        result = _select_term_structure_expiries(exps, max_count=6)
        assert len(result) == 2


# ============================================================
# Live tests (skip without IBKR)
# ============================================================

class TestLiveOptionChain:
    @pytest.mark.skipif(
        True,  # Set to False to run manually
        reason="Live IBKR test — run manually"
    )
    def test_spy_option_chain(self):
        from src.tools.option_chain_tools import get_option_chain

        result = get_option_chain("SPY", num_strikes=5)
        assert "error" not in result
        assert result["ticker"] == "SPY"
        assert result["spot_price"] > 0
        assert "chain" in result
        assert "metrics" in result
        assert "term_structure" in result
        assert result["metrics"]["max_pain_strike"] is not None
