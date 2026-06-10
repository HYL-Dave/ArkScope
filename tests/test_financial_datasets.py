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

    @patch("data_sources.financial_datasets_client._FILE_CACHE_DIR",
           Path("/tmp/_fd_test_nonexistent_cache"))
    def test_no_api_key_returns_empty(self):
        """Without API key and no cache, should return empty list."""
        # config/.env may have the key loaded into os.environ — must patch it out
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("FINANCIAL_DATASETS_API_KEY", None)
            client = FinancialDatasetsClient(api_key=None)
            client._db_url = None
            stmts = client.get_income_statements("AAPL")
            assert stmts == []

    @patch("data_sources.financial_datasets_client._FILE_CACHE_DIR",
           Path("/tmp/_fd_test_nonexistent_cache"))
    @patch("data_sources.financial_datasets_client.requests.get")
    def test_api_error_returns_empty(self, mock_get):
        """API errors with no cache should return empty list, not raise."""
        import requests as req
        mock_get.side_effect = req.RequestException("Connection error")

        client = FinancialDatasetsClient(api_key="test-key")
        client._db_url = None
        stmts = client.get_income_statements("AAPL")
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

# ============================================================
# cache_backend mode (3c-C unification: paid cache → local-primary)
# ============================================================

class _FakeCacheBackend:
    """Duck-typed DAL backend: get/set_financial_cache."""

    def __init__(self, store=None):
        self.store = dict(store or {})
        self.set_calls = []

    def get_financial_cache(self, cache_key):
        return self.store.get(cache_key)

    def set_financial_cache(self, cache_key, ticker, data, ttl_days=90, source="sec_edgar"):
        self.set_calls.append({"cache_key": cache_key, "ticker": ticker,
                               "ttl_days": ttl_days, "source": source})
        self.store[cache_key] = data
        return True


class TestCacheBackendMode:

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_backend_hit_skips_api(self, mock_get, tmp_path):
        backend = _FakeCacheBackend({"income_AAPL_annual": MOCK_INCOME_RESPONSE})
        with patch("data_sources.financial_datasets_client._FILE_CACHE_DIR", tmp_path):
            client = FinancialDatasetsClient(api_key="k", cache_backend=backend)
            stmts = client.get_income_statements("AAPL", period="annual", limit=1)
        mock_get.assert_not_called()
        assert len(stmts) == 1 and stmts[0].revenue == 416161000000.0

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_api_result_written_to_backend_only(self, mock_get, tmp_path, monkeypatch):
        # backend+file miss → API → the write goes ONLY to the backend (no file, and
        # the client's own env-PG path must not be touched even if DATABASE_URL set).
        monkeypatch.setenv("DATABASE_URL", "postgresql://must-not-be-used/db")
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_INCOME_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        backend = _FakeCacheBackend()
        with patch("data_sources.financial_datasets_client._FILE_CACHE_DIR", tmp_path):
            client = FinancialDatasetsClient(api_key="k", cache_backend=backend)
            client._db_upsert = lambda *a, **k: (_ for _ in ()).throw(AssertionError("env-PG used"))
            stmts = client.get_income_statements("AAPL", period="annual", limit=1)
        assert len(stmts) == 1
        assert backend.set_calls == [{"cache_key": "income_AAPL_annual", "ticker": "AAPL",
                                      "ttl_days": 180, "source": "financial_datasets"}]
        assert list(tmp_path.glob("*.json")) == []  # no new file writes in backend mode

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_file_hit_promoted_to_backend(self, mock_get, tmp_path):
        # backend miss + fresh legacy file → returned, API not called, AND promoted
        # into the backend with the file's remaining TTL (file cache migrates local).
        fetched = datetime.now(timezone.utc) - timedelta(days=30)  # 30d into a 180d TTL
        (tmp_path / "income_AAPL_annual.json").write_text(json.dumps({
            "fetched_at": fetched.isoformat(),
            "expires_at": (fetched + timedelta(days=180)).isoformat(),
            "ticker": "AAPL",
            "data": MOCK_INCOME_RESPONSE,
        }))
        backend = _FakeCacheBackend()
        with patch("data_sources.financial_datasets_client._FILE_CACHE_DIR", tmp_path):
            client = FinancialDatasetsClient(api_key="k", cache_backend=backend)
            stmts = client.get_income_statements("AAPL", period="annual", limit=1)
        mock_get.assert_not_called()
        assert len(stmts) == 1
        assert len(backend.set_calls) == 1
        promo = backend.set_calls[0]
        assert promo["source"] == "financial_datasets" and promo["ticker"] == "AAPL"
        assert promo["ttl_days"] == 150  # 180 - 30 elapsed → remaining TTL preserved

    def test_backend_without_cache_methods_is_ignored(self):
        # e.g. a FileBackend (no get/set_financial_cache) → legacy mode, not a crash
        client = FinancialDatasetsClient(api_key="k", cache_backend=object())
        assert client._cache_backend is None

    @patch("data_sources.financial_datasets_client.requests.get")
    def test_backend_write_failure_falls_back_to_file(self, mock_get, tmp_path, caplog):
        # Single-sink risk (review finding): if the backend write fails, the PAID
        # response must still be cached SOMEWHERE — legacy file fallback — and the
        # next call must hit it (no re-pay). Healthy path stays file-write-free
        # (test_api_result_written_to_backend_only).
        import logging
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_INCOME_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        class _RejectingBackend(_FakeCacheBackend):
            def set_financial_cache(self, *a, **k):
                super().set_financial_cache(*a, **k)
                self.store.clear()        # simulate: write reported ok=False, nothing stored
                return False

        backend = _RejectingBackend()
        with patch("data_sources.financial_datasets_client._FILE_CACHE_DIR", tmp_path):
            client = FinancialDatasetsClient(api_key="k", cache_backend=backend)
            with caplog.at_level(logging.WARNING):
                stmts = client.get_income_statements("AAPL", period="annual", limit=1)
            assert len(stmts) == 1
            assert mock_get.call_count == 1
            # paid response landed in the file fallback + the failure is observable
            assert (tmp_path / "income_AAPL_annual.json").exists()
            assert "NOT cached by the backend" in caplog.text
            # second call: backend still misses → FILE serves it → NO second paid call
            stmts2 = client.get_income_statements("AAPL", period="annual", limit=1)
        assert len(stmts2) == 1
        assert mock_get.call_count == 1  # still one paid call total
