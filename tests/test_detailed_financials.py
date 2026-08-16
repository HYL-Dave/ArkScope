"""
Tests for detailed financials tool (tech metrics, EV-based valuation, DB cache).
"""

from __future__ import annotations

import copy
import json
from unittest.mock import MagicMock, patch

import pytest


_PRODUCT_DYNAMIC_FIELDS = (
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "ev_to_ebitda",
    "ev_to_revenue",
    "fcf_yield",
    "peg_ratio",
)

_CALCULATOR_DYNAMIC_FIELDS = (
    "market_cap",
    "enterprise_value",
    "price_to_earnings_ratio",
    "price_to_book_ratio",
    "price_to_sales_ratio",
    "enterprise_value_to_ebitda_ratio",
    "enterprise_value_to_revenue_ratio",
    "free_cash_flow_yield",
    "peg_ratio",
)

_STATIC_METRICS = {
    "report_date": "2025-12-31",
    "gross_margin": 0.40,
    "operating_margin": 0.20,
    "net_margin": 0.12,
    "return_on_equity": 0.30,
    "return_on_assets": 0.15,
    "return_on_invested_capital": 0.18,
    "revenue_growth": 0.25,
    "earnings_growth": 0.20,
    "free_cash_flow_growth": 0.10,
    "ebitda_growth": 0.15,
    "debt_to_equity": 0.50,
    "current_ratio": 2.0,
    "interest_coverage": 8.0,
    "earnings_per_share": 1.0,
    "free_cash_flow_per_share": 0.25,
}

_TECH_METRICS = {
    "sbc_to_revenue": 0.03,
    "rd_to_revenue": 0.08,
    "rule_of_40": 35.0,
    "sbc_absolute": 150_000.0,
    "rd_absolute": 400_000.0,
}

_VALUATION_INPUTS = {
    "outstanding_shares": 2_000_000.0,
    "cash_and_equivalents": 1_000_000.0,
    "total_debt": 3_000_000.0,
    "revenue": 5_000_000.0,
    "ebitda": 2_500_000.0,
    "free_cash_flow": 500_000.0,
    "shareholders_equity": 4_000_000.0,
    "net_income": 2_000_000.0,
    "earnings_per_share": 1.0,
    "earnings_growth": 0.20,
}


def _static_cache_payload(ticker="TEST"):
    return {
        "version": 2,
        "ticker": ticker,
        "period": "annual",
        "years_for_growth": 2,
        "data_source": "sec_edgar",
        "report_date": "2025-12-31",
        "static_metrics": copy.deepcopy(_STATIC_METRICS),
        "tech_metrics": copy.deepcopy(_TECH_METRICS),
        "valuation_inputs": copy.deepcopy(_VALUATION_INPUTS),
    }


def _price_basis(price=10.0, ticker_date="2026-07-31"):
    from src.tools.schemas import ValuationPriceBasis

    return ValuationPriceBasis(
        available=True,
        source="local_market_db",
        interval="15min",
        required_market_date=ticker_date,
        market_date=ticker_date,
        timestamp=f"{ticker_date}T19:45:00+00:00",
        price=price,
        empty_reason=None,
    )


def _missing_price_basis(ticker_date="2026-07-31"):
    from src.tools.schemas import ValuationPriceBasis

    return ValuationPriceBasis(required_market_date=ticker_date)


class _RecordingCacheBackend:
    def __init__(self, rows=None):
        self.rows = copy.deepcopy(rows or {})
        self.read_keys = []
        self.writes = []

    def get_financial_cache(self, cache_key):
        self.read_keys.append(cache_key)
        return copy.deepcopy(self.rows.get(cache_key))

    def set_financial_cache(
        self,
        cache_key,
        ticker,
        data,
        ttl_days=90,
        source="sec_edgar",
    ):
        record = {
            "cache_key": cache_key,
            "ticker": ticker,
            "data": copy.deepcopy(data),
            "ttl_days": ttl_days,
            "source": source,
        }
        self.writes.append(record)
        self.rows[cache_key] = copy.deepcopy(data)
        return True


class _StaticCalculatorDouble:
    constructions = []

    def __init__(self, ticker, years_for_growth=2):
        self.ticker = ticker
        self.years_for_growth = years_for_growth
        type(self).constructions.append((ticker, years_for_growth))

    def get_static_metrics_dict(self):
        return copy.deepcopy(_STATIC_METRICS)

    def get_tech_metrics(self):
        return copy.deepcopy(_TECH_METRICS)

    def get_valuation_inputs(self):
        return copy.deepcopy(_VALUATION_INPUTS)

    def get_metrics_dict(self):
        metrics = self.get_static_metrics_dict()
        metrics.update({field: 999.0 for field in _CALCULATOR_DYNAMIC_FIELDS})
        return metrics


class _ForbiddenCalculator:
    def __init__(self, *_args, **_kwargs):
        raise AssertionError("static cache hit must not construct SEC calculator")


def _detailed_dal(backend, snapshot=None):
    dal = MagicMock()
    dal._backend = backend
    dal.get_fundamentals.return_value = MagicMock(snapshot=snapshot)
    return dal


def _run_detailed(dal, bases, calculator=_StaticCalculatorDouble):
    from src.tools.analysis_tools import get_detailed_financials

    basis_values = bases if isinstance(bases, list) else [bases]
    with patch(
        "data_sources.financial_metrics_calculator.FinancialMetricsCalculator",
        calculator,
    ), patch(
        "src.valuation_price.get_valuation_price_basis",
        side_effect=basis_values,
    ) as selector, patch(
        "src.tools.analyst_tools._fetch_earnings_history",
        return_value=[],
    ) as earnings_history, patch(
        "src.tools.analyst_tools._fetch_upcoming_earnings",
        return_value=None,
    ) as upcoming:
        results = [get_detailed_financials(dal, "test") for _ in basis_values]
    return results, selector, earnings_history, upcoming


def _assert_no_forbidden_cache_keys(value):
    exact_forbidden = {
        "price",
        "timestamp",
        "market_date",
        "valuation_price_basis",
        *_PRODUCT_DYNAMIC_FIELDS,
        *_CALCULATOR_DYNAMIC_FIELDS,
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            assert normalized not in exact_forbidden
            assert "price" not in normalized
            _assert_no_forbidden_cache_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_no_forbidden_cache_keys(nested)


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
        calc._income_statements = income_data
        calc._balance_sheets = None
        calc._cash_flow_statements = cashflow_data
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
        assert df.valuation_price_basis.available is False
        assert df.valuation_price_basis.empty_reason == "no_qualified_price"

    def test_full_creation(self):
        from src.tools.schemas import DetailedFinancials
        df = DetailedFinancials(
            ticker="NVDA",
            ev_to_ebitda=55.0,
            sbc_to_revenue=0.036,
            rd_to_revenue=0.099,
            rule_of_40=160.8,
            valuation_price_basis={
                "available": True,
                "source": "local_market_db",
                "interval": "15min",
                "required_market_date": "2026-06-23",
                "market_date": "2026-06-23",
                "timestamp": "2026-06-23T20:00:00+00:00",
                "price": 107.0,
                "empty_reason": None,
            },
        )
        assert df.ev_to_ebitda == 55.0
        assert df.rule_of_40 == 160.8
        assert df.valuation_price_basis.price == 107.0
        assert df.valuation_price_basis.source == "local_market_db"

    def test_model_dump(self):
        from src.tools.schemas import DetailedFinancials
        df = DetailedFinancials(ticker="TEST", pe_ratio=25.0)
        d = df.model_dump()
        assert d["ticker"] == "TEST"
        assert d["pe_ratio"] == 25.0
        assert d["valuation_price_basis"] == {
            "available": False,
            "source": None,
            "interval": None,
            "required_market_date": None,
            "market_date": None,
            "timestamp": None,
            "price": None,
            "empty_reason": "no_qualified_price",
        }


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



# ============================================================
# Integration: get_detailed_financials
# ============================================================

class TestGetDetailedFinancials:
    """Test the tool function integration."""

    def test_returns_detailed_financials_type(self):
        """Should return DetailedFinancials even with all mocked/empty data."""
        from src.tools.schemas import DetailedFinancials

        backend = _RecordingCacheBackend()
        result = _run_detailed(_detailed_dal(backend), _price_basis())[0][0]

        assert isinstance(result, DetailedFinancials)
        assert result.ticker == "TEST"
        assert result.gross_margin == 0.40
        assert result.sbc_to_revenue == 0.03
        assert result.market_cap == 20_000_000.0
        assert result.valuation_price_basis.model_dump() == {
            "available": True,
            "source": "local_market_db",
            "interval": "15min",
            "required_market_date": "2026-07-31",
            "market_date": "2026-07-31",
            "timestamp": "2026-07-31T19:45:00+00:00",
            "price": 10.0,
            "empty_reason": None,
        }

    def test_old_metrics_cache_key_is_ignored(self):
        old_key = "metrics_TEST_annual_y2"
        backend = _RecordingCacheBackend({
            old_key: {
                "standard": {"gross_margin": 9.0, "market_cap": 999.0},
                "tech": {"rule_of_40": 999.0},
            }
        })
        _StaticCalculatorDouble.constructions.clear()

        result = _run_detailed(_detailed_dal(backend), _price_basis())[0][0]

        assert backend.read_keys == [
            "detailed_financials:v2:sec_edgar:TEST:annual:y2"
        ]
        assert old_key not in backend.read_keys
        assert _StaticCalculatorDouble.constructions == [("TEST", 2)]
        assert result.gross_margin == 0.40
        assert result.rule_of_40 == 35.0
        assert result.market_cap == 20_000_000.0

    def test_v2_static_cache_excludes_price_and_dynamic_fields(self):
        from src.fundamentals.cache import (
            validate_detailed_financials_static_payload,
        )

        backend = _RecordingCacheBackend()
        _run_detailed(_detailed_dal(backend), _price_basis())

        assert len(backend.writes) == 1
        write = backend.writes[0]
        assert write["cache_key"] == (
            "detailed_financials:v2:sec_edgar:TEST:annual:y2"
        )
        assert write["ticker"] == "TEST"
        assert write["ttl_days"] == 90
        assert write["source"] == "sec_edgar"
        assert set(write["data"]) == {
            "version",
            "ticker",
            "period",
            "years_for_growth",
            "data_source",
            "report_date",
            "static_metrics",
            "tech_metrics",
            "valuation_inputs",
        }
        _assert_no_forbidden_cache_keys(write["data"])
        assert validate_detailed_financials_static_payload(
            write["data"], ticker="TEST"
        ) == write["data"]

        for forbidden in (
            "price",
            "timestamp",
            "market_date",
            "valuation_price_basis",
            *_PRODUCT_DYNAMIC_FIELDS,
            *_CALCULATOR_DYNAMIC_FIELDS,
        ):
            invalid = copy.deepcopy(write["data"])
            invalid["static_metrics"]["nested"] = {forbidden: 1.0}
            assert validate_detailed_financials_static_payload(
                invalid, ticker="TEST"
            ) is None

    def test_static_cache_hit_recomputes_dynamic_metrics_without_static_refetch(self):
        key = "detailed_financials:v2:sec_edgar:TEST:annual:y2"
        backend = _RecordingCacheBackend({key: _static_cache_payload()})
        dal = _detailed_dal(backend)
        dal.get_fundamentals.side_effect = AssertionError(
            "legacy fundamentals must not be read"
        )

        results, selector, earnings_history, upcoming = _run_detailed(
            dal,
            [_price_basis(10.0), _price_basis(20.0)],
            calculator=_ForbiddenCalculator,
        )

        assert [result.market_cap for result in results] == [
            20_000_000.0,
            40_000_000.0,
        ]
        assert [result.pe_ratio for result in results] == [10.0, 20.0]
        assert [result.gross_margin for result in results] == [0.40, 0.40]
        assert backend.read_keys == [key, key]
        assert backend.writes == []
        assert selector.call_count == 2
        assert earnings_history.call_count == 2
        assert upcoming.call_count == 2
        dal.get_fundamentals.assert_not_called()

    def test_no_qualified_price_preserves_static_and_nulls_dynamic_fields(self):
        key = "detailed_financials:v2:sec_edgar:TEST:annual:y2"
        backend = _RecordingCacheBackend({key: _static_cache_payload()})

        result = _run_detailed(
            _detailed_dal(backend),
            _missing_price_basis(),
            calculator=_ForbiddenCalculator,
        )[0][0]

        assert result.gross_margin == 0.40
        assert result.revenue_growth == 0.25
        assert result.cash_and_equivalents == 1_000_000.0
        assert result.total_debt == 3_000_000.0
        assert result.free_cash_flow == 500_000.0
        assert result.eps == 1.0
        assert all(getattr(result, field) is None for field in _PRODUCT_DYNAMIC_FIELDS)
        assert result.valuation_price_basis.model_dump() == {
            "available": False,
            "source": None,
            "interval": None,
            "required_market_date": "2026-07-31",
            "market_date": None,
            "timestamp": None,
            "price": None,
            "empty_reason": "no_qualified_price",
        }

    def test_legacy_ibkr_snapshot_cannot_override_sec_or_price_basis(self):
        backend = _RecordingCacheBackend()
        dal = _detailed_dal(backend, snapshot={
            "pe_ratio": 999.0,
            "price_to_book": 999.0,
            "price_to_sales": 999.0,
            "market_cap": 349_866.1,
        })

        result = _run_detailed(dal, _price_basis(10.0))[0][0]

        assert result.market_cap == 20_000_000.0
        assert result.pe_ratio == 10.0
        assert result.pb_ratio == 5.0
        assert result.ps_ratio == 4.0
        assert result.data_source == "sec_edgar"
        assert result.valuation_price_basis.price == 10.0
        dal.get_fundamentals.assert_not_called()

    def test_data_source_remains_static_sec_source(self):
        backend = _RecordingCacheBackend()
        dal = _detailed_dal(backend, snapshot={"pe_ratio": 999.0})

        result = _run_detailed(dal, _price_basis(10.0))[0][0]

        assert result.data_source == "sec_edgar"
        assert result.valuation_price_basis.source == "local_market_db"
        assert result.pe_ratio == 10.0


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
