"""
Tests for detailed financials tool (tech metrics, EV-based valuation, DB cache).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# Tech Metrics Calculator
# ============================================================

class TestTechMetrics:
    """Test FinancialMetricsCalculator.get_tech_metrics()."""

    def _make_calculator(self, income_data, cashflow_data):
        """Create a calculator with mocked SEC data."""
        from data_sources.financial_metrics_calculator import FinancialMetricsCalculator

        calc = FinancialMetricsCalculator.__new__(FinancialMetricsCalculator)
        calc.ticker = "TEST"
        calc.sec = MagicMock()
        calc.years_for_growth = 2
        calc.ibkr_data_path = MagicMock()
        calc._income_statements = income_data
        calc._balance_sheets = None
        calc._cash_flow_statements = cashflow_data
        calc._ibkr_data = None
        return calc

    def test_sbc_to_revenue(self):
        income = [{"revenue": 100_000, "research_and_development": 10_000}]
        cashflow = [{"share_based_compensation": 5_000, "free_cash_flow": 30_000}]
        calc = self._make_calculator(income, cashflow)
        tech = calc.get_tech_metrics()
        assert tech["sbc_to_revenue"] == 0.05
        assert tech["sbc_absolute"] == 5_000

    def test_rd_to_revenue(self):
        income = [{"revenue": 200_000, "research_and_development": 30_000}]
        cashflow = [{"share_based_compensation": None, "free_cash_flow": 50_000}]
        calc = self._make_calculator(income, cashflow)
        tech = calc.get_tech_metrics()
        assert tech["rd_to_revenue"] == 0.15
        assert tech["rd_absolute"] == 30_000
        assert tech["sbc_to_revenue"] is None

    def test_rule_of_40(self):
        # Two years of income for growth calculation
        income = [
            {"revenue": 120_000, "research_and_development": 10_000,
             "net_income": 40_000, "operating_income": 50_000,
             "earnings_per_share": 2.0},
            {"revenue": 100_000, "research_and_development": 8_000,
             "net_income": 30_000, "operating_income": 40_000,
             "earnings_per_share": 1.5},
        ]
        cashflow = [
            {"share_based_compensation": 5_000, "free_cash_flow": 36_000,
             "depreciation_and_amortization": 10_000},
            {"share_based_compensation": 4_000, "free_cash_flow": 25_000,
             "depreciation_and_amortization": 8_000},
        ]
        calc = self._make_calculator(income, cashflow)
        # Need balance sheets for growth calc
        calc._balance_sheets = [
            {"shareholders_equity": 200_000},
            {"shareholders_equity": 180_000},
        ]
        tech = calc.get_tech_metrics()
        # revenue_growth = (120000 - 100000) / 100000 = 0.2 (20%)
        # fcf_margin = 36000 / 120000 = 0.3 (30%)
        # rule_of_40 = (0.2 + 0.3) * 100 = 50.0
        assert tech["rule_of_40"] == 50.0

    def test_no_revenue_returns_none(self):
        income = [{"revenue": 0}]
        cashflow = [{"share_based_compensation": 5_000, "free_cash_flow": 10_000}]
        calc = self._make_calculator(income, cashflow)
        tech = calc.get_tech_metrics()
        assert tech["sbc_to_revenue"] is None
        assert tech["rd_to_revenue"] is None

    def test_empty_statements(self):
        calc = self._make_calculator([], [])
        tech = calc.get_tech_metrics()
        assert all(v is None for v in tech.values())


# ============================================================
# DetailedFinancials Schema
# ============================================================

class TestDetailedFinancialsSchema:
    """Test DetailedFinancials Pydantic model."""

    def test_minimal_creation(self):
        from src.tools.schemas import DetailedFinancials
        df = DetailedFinancials(ticker="TEST")
        assert df.ticker == "TEST"
        assert df.data_source == "sec_edgar"
        assert df.ev_to_ebitda is None

    def test_full_creation(self):
        from src.tools.schemas import DetailedFinancials
        df = DetailedFinancials(
            ticker="NVDA",
            ev_to_ebitda=55.0,
            sbc_to_revenue=0.036,
            rd_to_revenue=0.099,
            rule_of_40=160.8,
        )
        assert df.ev_to_ebitda == 55.0
        assert df.rule_of_40 == 160.8

    def test_model_dump(self):
        from src.tools.schemas import DetailedFinancials
        df = DetailedFinancials(ticker="TEST", pe_ratio=25.0)
        d = df.model_dump()
        assert d["ticker"] == "TEST"
        assert d["pe_ratio"] == 25.0


# ============================================================
# DB Cache
# ============================================================

class TestFinancialCache:
    """Test financial cache read/write in DB backend."""

    def test_cache_miss_returns_none(self):
        """Mock DB returning no rows."""
        from src.tools.backends.db_backend import DatabaseBackend
        backend = DatabaseBackend.__new__(DatabaseBackend)
        backend._conn = None
        backend._dsn = "mock"
        backend._sslmode = "prefer"

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(backend, '_get_conn', return_value=mock_conn):
            result = backend.get_financial_cache("metrics_TEST_annual")
            assert result is None

    def test_cache_hit_returns_data(self):
        """Mock DB returning cached data."""
        from src.tools.backends.db_backend import DatabaseBackend
        backend = DatabaseBackend.__new__(DatabaseBackend)
        backend._conn = None
        backend._dsn = "mock"
        backend._sslmode = "prefer"

        cached_data = {"standard": {"revenue_growth": 0.2}, "tech": {"sbc_to_revenue": 0.05}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (cached_data,)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(backend, '_get_conn', return_value=mock_conn):
            result = backend.get_financial_cache("metrics_TEST_annual")
            assert result == cached_data


# ============================================================
# Integration: get_detailed_financials
# ============================================================

class TestGetDetailedFinancials:
    """Test the tool function integration."""

    def test_returns_detailed_financials_type(self):
        """Should return DetailedFinancials even with all mocked/empty data."""
        from src.tools.schemas import DetailedFinancials
        from src.tools.analysis_tools import get_detailed_financials

        mock_dal = MagicMock()
        mock_dal._backend = MagicMock()
        mock_dal._backend.get_financial_cache.return_value = None
        mock_dal.get_fundamentals.return_value = MagicMock(snapshot=None)

        with patch(
            "src.tools.analysis_tools.get_detailed_financials.__module__",
            create=True,
        ):
            # Mock the FinancialMetricsCalculator
            with patch("data_sources.financial_metrics_calculator.FinancialMetricsCalculator") as MockCalc:
                mock_calc = MagicMock()
                mock_calc.get_metrics_dict.return_value = {
                    "report_date": "2025-01-31",
                    "enterprise_value_to_ebitda_ratio": 55.0,
                    "revenue_growth": 0.94,
                    "gross_margin": 0.75,
                }
                mock_calc.get_tech_metrics.return_value = {
                    "sbc_to_revenue": 0.036,
                    "rd_to_revenue": 0.099,
                    "rule_of_40": 160.8,
                    "sbc_absolute": 4737000000,
                    "rd_absolute": 12914000000,
                }
                MockCalc.return_value = mock_calc

                # Mock Finnhub
                with patch("src.tools.analyst_tools._fetch_earnings_history", return_value=[]):
                    with patch("src.tools.analyst_tools._fetch_upcoming_earnings", return_value=None):
                        result = get_detailed_financials(mock_dal, "NVDA")

            assert isinstance(result, DetailedFinancials)
            assert result.ticker == "NVDA"
            assert result.ev_to_ebitda == 55.0
            assert result.sbc_to_revenue == 0.036
            assert result.rule_of_40 == 160.8
            assert result.revenue_growth == 0.94

    def test_ibkr_enrichment_overrides(self):
        """IBKR PE/PB/PS should override SEC-calculated values."""
        from src.tools.analysis_tools import get_detailed_financials

        mock_dal = MagicMock()
        mock_dal._backend = MagicMock()
        # Return cached SEC data
        mock_dal._backend.get_financial_cache.return_value = {
            "standard": {
                "price_to_earnings_ratio": 30.0,
                "price_to_book_ratio": 10.0,
            },
            "tech": {},
        }
        # IBKR returns different (more current) values
        mock_fundamentals = MagicMock()
        mock_fundamentals.snapshot = {
            "pe_ratio": 35.0,
            "price_to_book": 12.0,
            "price_to_sales": 20.0,
            "market_cap": 3500000000000,
        }
        mock_dal.get_fundamentals.return_value = mock_fundamentals

        with patch("src.tools.analyst_tools._fetch_earnings_history", return_value=[]):
            with patch("src.tools.analyst_tools._fetch_upcoming_earnings", return_value=None):
                result = get_detailed_financials(mock_dal, "TEST")

        # IBKR values should win
        assert result.pe_ratio == 35.0
        assert result.pb_ratio == 12.0
        assert result.ps_ratio == 20.0
        assert result.market_cap == 3500000000000


# ============================================================
# Live tests (skip without network)
# ============================================================

class TestLiveTechMetrics:
    """Live tests against SEC EDGAR (requires network)."""

    @pytest.mark.skipif(
        True,  # Set to False to run manually
        reason="Live SEC EDGAR test — run manually"
    )
    def test_nvda_tech_metrics(self):
        from data_sources.financial_metrics_calculator import FinancialMetricsCalculator
        calc = FinancialMetricsCalculator("NVDA")
        tech = calc.get_tech_metrics()
        # NVDA should have meaningful SBC and R&D
        assert tech["sbc_to_revenue"] is not None
        assert tech["rd_to_revenue"] is not None
        assert tech["rule_of_40"] is not None
        # NVDA Rule of 40 should be very high
        assert tech["rule_of_40"] > 50
