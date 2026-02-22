"""
Tests for portfolio analysis tool (Batch 3a).
"""

from __future__ import annotations

import pytest
import numpy as np


# ============================================================
# Pure calculation tests
# ============================================================


class TestBetaCalculation:
    """Test _compute_beta() pure function."""

    def test_beta_equals_one_for_spy(self):
        """SPY vs SPY should have beta ≈ 1.0."""
        from src.tools.portfolio_tools import _compute_beta

        returns = [0.01, -0.005, 0.02, -0.01, 0.015] * 12  # 60 days
        result = _compute_beta(returns, returns, window=60)
        assert result is not None
        assert abs(result["beta_60d"] - 1.0) < 0.001

    def test_beta_two_x_leverage(self):
        """2x leveraged returns should have beta ≈ 2.0."""
        from src.tools.portfolio_tools import _compute_beta

        spy_returns = [0.01, -0.005, 0.02, -0.01, 0.015] * 12
        ticker_returns = [r * 2 for r in spy_returns]
        result = _compute_beta(ticker_returns, spy_returns, window=60)
        assert result is not None
        assert abs(result["beta_60d"] - 2.0) < 0.01

    def test_beta_insufficient_data(self):
        """Should return None if too few data points."""
        from src.tools.portfolio_tools import _compute_beta

        result = _compute_beta([0.01, 0.02], [0.01, 0.02], window=60)
        assert result is None


class TestCorrelationMatrix:
    """Test _compute_correlation_matrix() pure function."""

    def test_perfect_correlation(self):
        """Identical returns should have correlation = 1.0."""
        from src.tools.portfolio_tools import _compute_correlation_matrix

        returns = {
            "AAPL": [0.01, -0.005, 0.02, -0.01, 0.015] * 4,
            "MSFT": [0.01, -0.005, 0.02, -0.01, 0.015] * 4,
        }
        result = _compute_correlation_matrix(returns, ["AAPL", "MSFT"])
        assert "AAPL" in result
        assert result["AAPL"]["MSFT"] == 1.0

    def test_diagonal_is_one(self):
        """Self-correlation should always be 1.0."""
        from src.tools.portfolio_tools import _compute_correlation_matrix

        returns = {
            "AAPL": [0.01, -0.02, 0.03, -0.01, 0.005] * 4,
            "MSFT": [0.005, 0.01, -0.01, 0.02, -0.005] * 4,
        }
        result = _compute_correlation_matrix(returns, ["AAPL", "MSFT"])
        assert result["AAPL"]["AAPL"] == 1.0
        assert result["MSFT"]["MSFT"] == 1.0

    def test_symmetry(self):
        """Correlation matrix should be symmetric."""
        from src.tools.portfolio_tools import _compute_correlation_matrix

        returns = {
            "A": [0.01, -0.02, 0.03, -0.01, 0.005] * 4,
            "B": [0.005, 0.01, -0.01, 0.02, -0.005] * 4,
            "C": [-0.01, 0.02, -0.03, 0.01, -0.005] * 4,
        }
        result = _compute_correlation_matrix(returns, ["A", "B", "C"])
        assert result["A"]["B"] == result["B"]["A"]
        assert result["A"]["C"] == result["C"]["A"]
        assert result["B"]["C"] == result["C"]["B"]

    def test_empty_returns(self):
        """Should handle empty or single ticker gracefully."""
        from src.tools.portfolio_tools import _compute_correlation_matrix

        assert _compute_correlation_matrix({}, []) == {}
        assert _compute_correlation_matrix({"A": [0.01]}, ["A"]) == {}


class TestPnL:
    """Test _compute_pnl() pure function."""

    def test_basic_pnl(self):
        """Test P&L with known values."""
        from src.tools.portfolio_tools import _compute_pnl

        holdings = {
            "NVDA": {"qty": 100, "entry_price": 100.0},
            "AAPL": {"qty": 50, "entry_price": 200.0},
        }
        latest_prices = {"NVDA": 120.0, "AAPL": 190.0}

        result = _compute_pnl(holdings, latest_prices)
        assert result is not None

        # NVDA: (120-100)*100 = 2000
        nvda_pos = next(p for p in result["positions"] if p["ticker"] == "NVDA")
        assert nvda_pos["unrealized_pnl"] == 2000.0
        assert nvda_pos["pnl_pct"] == 20.0

        # AAPL: (190-200)*50 = -500
        aapl_pos = next(p for p in result["positions"] if p["ticker"] == "AAPL")
        assert aapl_pos["unrealized_pnl"] == -500.0

        # Total: 12000+9500=21500, cost=10000+10000=20000
        assert result["total_pnl"] == 1500.0

    def test_no_price_data(self):
        """Should return None if no prices available."""
        from src.tools.portfolio_tools import _compute_pnl

        result = _compute_pnl({"NVDA": {"qty": 10, "entry_price": 100}}, {})
        assert result is None


class TestHHI:
    """Test HHI concentration via _compute_portfolio_metrics."""

    def test_equal_weights(self):
        """Equal weights across 4 positions → HHI = 0.25."""
        from src.tools.portfolio_tools import _compute_portfolio_metrics

        holdings = {
            "A": {"qty": 100, "entry_price": 100},
            "B": {"qty": 100, "entry_price": 100},
            "C": {"qty": 100, "entry_price": 100},
            "D": {"qty": 100, "entry_price": 100},
        }
        prices = {"A": 100.0, "B": 100.0, "C": 100.0, "D": 100.0}
        betas = {}

        result = _compute_portfolio_metrics(holdings, prices, betas, {})
        assert result is not None
        assert abs(result["hhi_concentration"] - 0.25) < 0.001

    def test_single_position(self):
        """Single position → HHI = 1.0."""
        from src.tools.portfolio_tools import _compute_portfolio_metrics

        holdings = {"NVDA": {"qty": 100, "entry_price": 100}}
        prices = {"NVDA": 100.0}

        result = _compute_portfolio_metrics(holdings, prices, {}, {})
        assert result is not None
        assert result["hhi_concentration"] == 1.0


class TestAlignReturns:
    """Test _align_returns() helper."""

    def test_basic_alignment(self):
        """Should align by date intersection."""
        from src.tools.portfolio_tools import _align_returns

        closes = {
            "A": {"2025-01-01": 100.0, "2025-01-02": 102.0, "2025-01-03": 101.0},
            "B": {"2025-01-01": 50.0, "2025-01-02": 51.0, "2025-01-03": 50.5},
        }
        dates, returns = _align_returns(closes)
        assert len(returns["A"]) == 2  # 3 dates → 2 returns
        assert len(returns["B"]) == 2


# ============================================================
# Integration test with registry
# ============================================================


class TestPortfolioToolRegistration:
    """Verify tool is registered correctly."""

    def test_tool_registered(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        tool = registry.get("get_portfolio_analysis")
        assert tool is not None
        assert tool.category == "portfolio"
        assert tool.requires_dal is True
        assert len(registry.list_all()) == 36
