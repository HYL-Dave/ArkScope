"""
Tests for earnings impact analysis tool (Batch 3c).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# Pure calculation tests
# ============================================================


class TestFindNearestPriceIndex:
    """Test _find_nearest_price_index() helper."""

    def test_exact_match(self):
        from src.tools.earnings_tools import _find_nearest_price_index

        dates = ["2025-10-01", "2025-10-02", "2025-10-03"]
        assert _find_nearest_price_index(dates, "2025-10-02") == 1

    def test_nearest_within_tolerance(self):
        from src.tools.earnings_tools import _find_nearest_price_index

        dates = ["2025-10-01", "2025-10-03", "2025-10-06"]
        # Target 10-04 is 1 day from 10-03 (idx=1)
        assert _find_nearest_price_index(dates, "2025-10-04") == 1

    def test_outside_tolerance(self):
        from src.tools.earnings_tools import _find_nearest_price_index

        dates = ["2025-10-01", "2025-10-02"]
        # Target 10-20 is 18 days away, beyond tolerance=5
        assert _find_nearest_price_index(dates, "2025-10-20") is None


class TestComputeMove:
    """Test _compute_move() helper."""

    def test_basic_move(self):
        from src.tools.earnings_tools import _compute_move

        # 10% up on earnings day
        closes = [90.0, 95.0, 100.0, 110.0, 108.0, 105.0, 103.0, 107.0, 109.0]
        dates = [f"2025-10-0{i+1}" for i in range(9)]

        result = _compute_move(closes, dates, idx=3)  # 100→110 = +10%
        assert result is not None
        assert abs(result["earnings_day_move_pct"] - 10.0) < 0.01
        assert result["pre_drift_5d_pct"] is not None
        assert result["post_drift_5d_pct"] is not None

    def test_index_at_start(self):
        """Index 0 should return None (no previous day)."""
        from src.tools.earnings_tools import _compute_move

        closes = [100.0, 110.0]
        dates = ["2025-10-01", "2025-10-02"]
        assert _compute_move(closes, dates, idx=0) is None

    def test_negative_move(self):
        from src.tools.earnings_tools import _compute_move

        closes = [100.0, 100.0, 95.0, 96.0]
        dates = ["2025-10-01", "2025-10-02", "2025-10-03", "2025-10-04"]

        result = _compute_move(closes, dates, idx=2)  # 100→95 = -5%
        assert result is not None
        assert result["earnings_day_move_pct"] == -5.0


# ============================================================
# Integration test with mock data
# ============================================================


class TestGetEarningsImpact:
    """Test get_earnings_impact() with mocked dependencies."""

    def _make_consensus(self):
        """Create representative analyst consensus data."""
        return {
            "ticker": "NVDA",
            "recommendations": {"current": None, "trend": []},
            "earnings": {
                "history": [
                    {"period": "2025-10-15", "actual": 0.92, "estimate": 0.89, "surprisePercent": 3.37},
                    {"period": "2025-07-15", "actual": 0.85, "estimate": 0.82, "surprisePercent": 3.66},
                    {"period": "2025-04-15", "actual": 0.73, "estimate": 0.78, "surprisePercent": -6.41},
                    {"period": "2025-01-15", "actual": 0.65, "estimate": 0.60, "surprisePercent": 8.33},
                ],
                "upcoming": {
                    "date": "2026-02-26",
                    "hour": "amc",
                    "epsEstimate": 0.98,
                    "revenueEstimate": 38500000000,
                },
            },
            "price_target": None,
        }

    def _make_price_bars(self):
        """Create 365 days of synthetic daily price data."""
        from src.tools.schemas import PriceBar, PriceQueryResult

        bars = []
        base_price = 100.0
        for i in range(365):
            d = f"2025-{((i // 30) + 1):02d}-{((i % 30) + 1):02d}"
            # Simple pattern: price slowly grows
            price = base_price + i * 0.1
            # Add earnings-day jumps on specific dates
            if d == "2025-10-15":
                price += 8.0  # ~8% jump
            elif d == "2025-07-15":
                price += 5.0
            elif d == "2025-04-15":
                price -= 3.0
            elif d == "2025-01-15":
                price += 6.0

            bars.append(PriceBar(
                datetime=d,
                open=price - 0.5,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=1000000,
            ))

        return PriceQueryResult(
            ticker="NVDA",
            interval="1d",
            count=len(bars),
            bars=bars,
            date_range=f"{bars[0].datetime} to {bars[-1].datetime}",
        )

    @patch("src.tools.analyst_tools.get_analyst_consensus")
    def test_basic_earnings_impact(self, mock_consensus):
        from src.tools.earnings_tools import get_earnings_impact

        mock_consensus.return_value = self._make_consensus()

        # Create mock DAL
        dal = MagicMock()
        dal.get_prices.return_value = self._make_price_bars()

        result = get_earnings_impact(dal, "NVDA")

        assert result["ticker"] == "NVDA"
        assert result["quarters_analyzed"] > 0
        assert result["upcoming_earnings"] is not None
        assert "summary" in result
        assert "surprise_analysis" in result
        assert "expected_move" in result

    @patch("src.tools.analyst_tools.get_analyst_consensus")
    def test_directional_bias(self, mock_consensus):
        from src.tools.earnings_tools import get_earnings_impact

        mock_consensus.return_value = self._make_consensus()

        dal = MagicMock()
        dal.get_prices.return_value = self._make_price_bars()

        result = get_earnings_impact(dal, "NVDA")
        summary = result.get("summary", {})

        # Should have up and down counts
        assert "up_count" in summary
        assert "down_count" in summary
        assert summary["up_count"] + summary["down_count"] == result["quarters_analyzed"]

    @patch("src.tools.analyst_tools.get_analyst_consensus")
    def test_no_earnings_data(self, mock_consensus):
        from src.tools.earnings_tools import get_earnings_impact

        mock_consensus.return_value = {
            "ticker": "XYZ",
            "earnings": {"history": [], "upcoming": None},
        }

        dal = MagicMock()
        result = get_earnings_impact(dal, "XYZ")
        assert "error" in result

    @patch("src.tools.analyst_tools.get_analyst_consensus")
    def test_no_price_data(self, mock_consensus):
        from src.tools.earnings_tools import get_earnings_impact
        from src.tools.schemas import PriceQueryResult

        mock_consensus.return_value = self._make_consensus()

        dal = MagicMock()
        dal.get_prices.return_value = PriceQueryResult(
            ticker="NVDA", interval="1d", count=0, bars=[], date_range=None,
        )

        result = get_earnings_impact(dal, "NVDA")
        assert "error" in result

    @patch("src.tools.analyst_tools.get_analyst_consensus")
    def test_surprise_analysis(self, mock_consensus):
        from src.tools.earnings_tools import get_earnings_impact

        mock_consensus.return_value = self._make_consensus()

        dal = MagicMock()
        dal.get_prices.return_value = self._make_price_bars()

        result = get_earnings_impact(dal, "NVDA")
        surprise = result.get("surprise_analysis", {})

        assert "beats" in surprise
        assert "misses" in surprise
        assert surprise["beats"] + surprise["misses"] + surprise["meets"] == result["quarters_analyzed"]


# ============================================================
# Registration test
# ============================================================


class TestEarningsToolRegistration:
    """Verify tool is registered correctly."""

    def test_tool_registered(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        tool = registry.get("get_earnings_impact")
        assert tool is not None
        assert tool.category == "analysis"
        assert tool.requires_dal is True
