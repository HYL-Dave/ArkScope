"""
Tests for IV skew analysis tool (Batch 3b).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ============================================================
# Pure calculation tests
# ============================================================


class TestSkewClassification:
    """Test _classify_skew_shape() pure function."""

    def test_put_skew(self):
        from src.tools.iv_skew_tools import _classify_skew_shape

        # OTM puts elevated, calls not
        assert _classify_skew_shape(0.30, 0.38, 0.29) == "put_skew"

    def test_smile(self):
        from src.tools.iv_skew_tools import _classify_skew_shape

        # Both wings elevated
        assert _classify_skew_shape(0.30, 0.38, 0.36) == "smile"

    def test_call_skew(self):
        from src.tools.iv_skew_tools import _classify_skew_shape

        # OTM calls elevated, puts not
        assert _classify_skew_shape(0.30, 0.29, 0.38) == "call_skew"

    def test_flat(self):
        from src.tools.iv_skew_tools import _classify_skew_shape

        # Neither wing elevated
        assert _classify_skew_shape(0.30, 0.31, 0.30) == "flat"

    def test_zero_atm_iv(self):
        from src.tools.iv_skew_tools import _classify_skew_shape

        assert _classify_skew_shape(0.0, 0.30, 0.30) == "flat"


class TestNearestDelta:
    """Test _find_nearest_delta() helper."""

    def test_find_25d_put(self):
        from src.tools.iv_skew_tools import _find_nearest_delta

        quotes = [
            {"delta": -0.40, "iv": 0.35, "strike": 90},
            {"delta": -0.25, "iv": 0.38, "strike": 95},
            {"delta": -0.10, "iv": 0.42, "strike": 85},
        ]
        result = _find_nearest_delta(quotes, -0.25)
        assert result is not None
        assert result["strike"] == 95

    def test_no_delta_data(self):
        from src.tools.iv_skew_tools import _find_nearest_delta

        quotes = [{"delta": None, "iv": 0.35}, {"iv": 0.40}]
        assert _find_nearest_delta(quotes, -0.25) is None


class TestSkewGradient:
    """Test _compute_skew_gradient() pure function."""

    def test_positive_gradient_puts(self):
        """OTM puts further from ATM should have higher IV (put skew)."""
        from src.tools.iv_skew_tools import _compute_skew_gradient

        # Spot = 100, puts below spot with increasing IV as distance grows
        puts = [
            {"strike": 95, "iv": 0.32},
            {"strike": 90, "iv": 0.35},
            {"strike": 85, "iv": 0.38},
        ]
        gradient = _compute_skew_gradient(puts, 100.0, "put")
        assert gradient is not None
        assert gradient > 0  # IV increases with distance

    def test_insufficient_points(self):
        from src.tools.iv_skew_tools import _compute_skew_gradient

        puts = [{"strike": 95, "iv": 0.32}]
        assert _compute_skew_gradient(puts, 100.0, "put") is None


class TestInterpretation:
    """Test _generate_interpretation() helper."""

    def test_put_skew_interpretation(self):
        from src.tools.iv_skew_tools import _generate_interpretation

        text = _generate_interpretation("put_skew", 0.047)
        assert "downside protection" in text

    def test_smile_interpretation(self):
        from src.tools.iv_skew_tools import _generate_interpretation

        text = _generate_interpretation("smile", 0.08)
        assert "tail risk" in text

    def test_extreme_skew(self):
        from src.tools.iv_skew_tools import _generate_interpretation

        text = _generate_interpretation("put_skew", 0.15)
        assert "extreme" in text


# ============================================================
# Integration test with mock option chain
# ============================================================


class TestGetIVSkewAnalysis:
    """Test get_iv_skew_analysis() with mocked option chain."""

    def _make_chain_data(self):
        """Create representative option chain data."""
        return {
            "ticker": "SPY",
            "spot_price": 500.0,
            "selected_expiry": "20260320",
            "selected_dte": 26,
            "chain": {
                "calls": [
                    {"strike": 490.0, "iv": 0.20, "delta": 0.70, "bid": 12.0, "ask": 12.5},
                    {"strike": 495.0, "iv": 0.19, "delta": 0.55, "bid": 8.0, "ask": 8.5},
                    {"strike": 500.0, "iv": 0.18, "delta": 0.50, "bid": 5.0, "ask": 5.5},
                    {"strike": 505.0, "iv": 0.17, "delta": 0.30, "bid": 3.0, "ask": 3.5},
                    {"strike": 510.0, "iv": 0.16, "delta": 0.15, "bid": 1.5, "ask": 2.0},
                ],
                "puts": [
                    {"strike": 490.0, "iv": 0.24, "delta": -0.30, "bid": 3.0, "ask": 3.5},
                    {"strike": 495.0, "iv": 0.22, "delta": -0.40, "bid": 5.0, "ask": 5.5},
                    {"strike": 500.0, "iv": 0.19, "delta": -0.50, "bid": 6.0, "ask": 6.5},
                    {"strike": 505.0, "iv": 0.18, "delta": -0.65, "bid": 9.0, "ask": 9.5},
                    {"strike": 510.0, "iv": 0.17, "delta": -0.80, "bid": 12.0, "ask": 12.5},
                ],
            },
            "term_structure": [
                {"expiry": "20260320", "dte": 26, "atm_iv_call": 0.18, "atm_iv_put": 0.19},
                {"expiry": "20260417", "dte": 54, "atm_iv_call": 0.20, "atm_iv_put": 0.21},
            ],
        }

    @patch("src.tools.option_chain_tools.get_option_chain")
    def test_put_skew_detected(self, mock_chain):
        from src.tools.iv_skew_tools import get_iv_skew_analysis

        mock_chain.return_value = self._make_chain_data()
        result = get_iv_skew_analysis("SPY")

        assert result["ticker"] == "SPY"
        assert result["skew_shape"] == "put_skew"
        assert result["atm_iv"] > 0
        assert result["otm_put_avg_iv"] > result["atm_iv"]
        assert len(result["per_strike_skew"]) > 0
        assert len(result["term_structure_skew"]) == 2

    @patch("src.tools.option_chain_tools.get_option_chain")
    def test_error_passthrough(self, mock_chain):
        from src.tools.iv_skew_tools import get_iv_skew_analysis

        mock_chain.return_value = {"error": "IBKR connection failed", "ticker": "SPY"}
        result = get_iv_skew_analysis("SPY")
        assert "error" in result

    @patch("src.tools.option_chain_tools.get_option_chain")
    def test_25d_skew_computed(self, mock_chain):
        from src.tools.iv_skew_tools import get_iv_skew_analysis

        mock_chain.return_value = self._make_chain_data()
        result = get_iv_skew_analysis("SPY")

        assert result["skew_25d"] is not None
        assert result["skew_25d_detail"] is not None
        assert result["skew_25d"] > 0  # Put IV > Call IV (put skew)


# ============================================================
# Registration test
# ============================================================


class TestIVSkewRegistration:
    """Verify tool is registered correctly."""

    def test_tool_registered(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        tool = registry.get("get_iv_skew_analysis")
        assert tool is not None
        assert tool.category == "options"
        assert tool.requires_dal is False
