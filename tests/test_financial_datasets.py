"""
Tests for Financial Datasets API client and fallback integration.

Uses mocks to avoid real API calls and DB connections.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_sources.financial_datasets_client import FinancialDatasetsClient
from data_sources.sec_edgar_financials import IncomeStatement, BalanceSheet


# ============================================================
# Mock API response data
# ============================================================

MOCK_INCOME_RESPONSE = {
    "income_statements": [
        {
            "ticker": "AAPL",
            "report_period": "2025-09-27",
            "fiscal_period": "2025-FY",
            "period": "annual",
            "currency": "USD",
            "revenue": 416161000000.0,
            "cost_of_revenue": 220960000000.0,
            "gross_profit": 195201000000.0,
            "operating_income": 133050000000.0,
            "net_income": 112010000000.0,
            "earnings_per_share": 7.49,
            "earnings_per_share_diluted": 7.46,
        }
    ]
}

MOCK_BALANCE_RESPONSE = {
    "balance_sheets": [
        {
            "ticker": "AAPL",
            "report_period": "2025-09-27",
            "fiscal_period": "2025-FY",
            "period": "annual",
            "currency": "USD",
            "total_assets": 400000000000.0,
            "current_assets": 150000000000.0,
            "cash_and_equivalents": 30000000000.0,
            "total_liabilities": 280000000000.0,
            "current_liabilities": 130000000000.0,
            "shareholders_equity": 120000000000.0,
        }
    ]
}

MOCK_CASHFLOW_RESPONSE = {
    "cash_flow_statements": [
        {
            "ticker": "AAPL",
            "report_period": "2025-09-27",
            "fiscal_period": "2025-FY",
            "period": "annual",
            "currency": "USD",
            "net_cash_flow_from_operations": 120000000000.0,
            "capital_expenditure": -12000000000.0,
            "free_cash_flow": 108000000000.0,
        }
    ]
}


# ============================================================
# FinancialDatasetsClient tests
# ============================================================

class TestFinancialDatasetsClient:

    def setup_method(self):
        self.client = FinancialDatasetsClient(api_key="test-key")
        self.client._db_url = None  # Disable DB cache for unit tests

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_api_call_returns_dataclass(self, mock_get):
        """API response should be converted to dataclass instances."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_INCOME_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        stmts = self.client.get_income_statements("AAPL", period="annual", limit=1)
        assert len(stmts) == 1
        assert isinstance(stmts[0], IncomeStatement)
        assert stmts[0].ticker == "AAPL"
        assert stmts[0].revenue == 416161000000.0
        assert stmts[0].net_income == 112010000000.0

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_balance_sheet_returns_dataclass(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_BALANCE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        stmts = self.client.get_balance_sheets("AAPL", period="annual", limit=1)
        assert len(stmts) == 1
        assert isinstance(stmts[0], BalanceSheet)
        assert stmts[0].total_assets == 400000000000.0

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_cache_hit_skips_api(self, mock_get):
        """When file cache has fresh data, API should not be called."""
        # Pre-populate file cache
        cache_dir = Path("data/cache/financial_datasets")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "income_AAPL_annual.json"
        cache_file.write_text(json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            "ticker": "AAPL",
            "data": MOCK_INCOME_RESPONSE,
        }))

        try:
            stmts = self.client.get_income_statements("AAPL", period="annual", limit=1)
            # API should NOT have been called
            mock_get.assert_not_called()
            # Should still return data from cache
            assert len(stmts) == 1
            assert stmts[0].revenue == 416161000000.0
        finally:
            cache_file.unlink(missing_ok=True)

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_cache_expired_calls_api(self, mock_get):
        """When file cache is expired, API should be called."""
        cache_dir = Path("data/cache/financial_datasets")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "income_AAPL_annual.json"
        cache_file.write_text(json.dumps({
            "fetched_at": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "ticker": "AAPL",
            "data": MOCK_INCOME_RESPONSE,
        }))

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_INCOME_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        try:
            self.client.get_income_statements("AAPL", period="annual", limit=1)
            # API should have been called because cache expired
            mock_get.assert_called_once()
        finally:
            cache_file.unlink(missing_ok=True)

    def test_no_api_key_returns_empty(self):
        """Without API key, should return empty list (no error)."""
        client = FinancialDatasetsClient(api_key=None)
        client._db_url = None
        # Ensure no env var
        with patch.dict("os.environ", {}, clear=False):
            if "FINANCIAL_DATASETS_API_KEY" in os.environ:
                del os.environ["FINANCIAL_DATASETS_API_KEY"]
            client_no_key = FinancialDatasetsClient(api_key=None)
            client_no_key._db_url = None
            stmts = client_no_key.get_income_statements("AAPL")
            assert stmts == []

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_api_error_returns_empty(self, mock_get):
        """API errors should return empty list, not raise."""
        import requests as req
        mock_get.side_effect = req.RequestException("Connection error")

        stmts = self.client.get_income_statements("AAPL")
        assert stmts == []

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_extra_fields_ignored(self, mock_get):
        """FD API may return extra fields not in our dataclass — should be ignored."""
        response = {
            "income_statements": [{
                "ticker": "AAPL",
                "report_period": "2025-09-27",
                "fiscal_period": "2025-FY",
                "period": "annual",
                "currency": "USD",
                "revenue": 100.0,
                "net_income_discontinued_operations": 0.0,  # Not in our dataclass
                "consolidated_income": 100.0,  # Not in our dataclass
            }]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        stmts = self.client.get_income_statements("AAPL", limit=1)
        assert len(stmts) == 1
        assert stmts[0].revenue == 100.0


# ============================================================
# Fallback integration tests
# ============================================================

import os
from src.tools.analysis_tools import (
    _is_fd_enabled,
    _build_result_from_statements,
)


class TestFDFallbackConditions:

    def test_fd_disabled_no_api_key(self):
        """FD should be disabled when no API key is set."""
        dal = MagicMock()
        with patch.dict("os.environ", {}, clear=False):
            env = os.environ.copy()
            env.pop("FINANCIAL_DATASETS_API_KEY", None)
            with patch.dict("os.environ", env, clear=True):
                assert _is_fd_enabled(dal) is False

    def test_fd_disabled_in_config(self):
        """FD should be disabled when config says enabled: false."""
        dal = MagicMock()
        dal.get_user_profile.return_value = {
            "data_preferences": {
                "paid_sources": {
                    "financial_datasets": {"enabled": False}
                }
            }
        }
        with patch.dict("os.environ", {"FINANCIAL_DATASETS_API_KEY": "test"}):
            assert _is_fd_enabled(dal) is False

    def test_fd_enabled_with_key_and_config(self):
        """FD should be enabled when API key exists and config says enabled."""
        dal = MagicMock()
        dal.get_user_profile.return_value = {
            "data_preferences": {
                "paid_sources": {
                    "financial_datasets": {"enabled": True}
                }
            }
        }
        with patch.dict("os.environ", {"FINANCIAL_DATASETS_API_KEY": "test"}):
            assert _is_fd_enabled(dal) is True


class TestBuildResult:

    def test_builds_from_statements(self):
        """_build_result_from_statements should produce a valid FundamentalsResult."""
        income = IncomeStatement(
            ticker="AAPL", report_period="2025-09-27",
            fiscal_period="2025-FY", period="annual", currency="USD",
            revenue=400e9, net_income=100e9, gross_profit=200e9,
            operating_income=130e9,
        )
        balance = BalanceSheet(
            ticker="AAPL", report_period="2025-09-27",
            fiscal_period="2025-FY", period="annual", currency="USD",
            total_assets=400e9, shareholders_equity=120e9,
            total_liabilities=280e9,
        )
        result = _build_result_from_statements(
            "AAPL", "financial_datasets", [income], [balance], [],
        )
        assert result.data_source == "financial_datasets"
        assert result.ticker == "AAPL"
        assert result.gross_margin == 0.5  # 200/400
        assert result.roe is not None
        assert result.debt_to_equity is not None

    def test_empty_statements_returns_minimal(self):
        """Empty statements should still produce a result."""
        result = _build_result_from_statements("AAPL", "sec_edgar", [], [], [])
        assert result.ticker == "AAPL"
        assert result.snapshot_date is None