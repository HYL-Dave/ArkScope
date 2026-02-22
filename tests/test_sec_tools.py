"""
Tests for SEC data tools (Phase 11a).

All SEC EDGAR HTTP calls are mocked — no network requests needed.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.tools.sec_tools import get_sec_filings, get_insider_trades


# ============================================================
# get_sec_filings
# ============================================================

class TestGetSecFilings:
    @patch("src.tools.sec_tools.get_filings_list", create=True)
    def test_basic(self, mock_get):
        """Delegates to sec_edgar_financials.get_filings_list()."""
        # We need to patch at the point of import inside the function
        with patch("data_sources.sec_edgar_financials.get_filings_list") as mock_fn:
            mock_fn.return_value = [
                {
                    "cik": 1045810,
                    "accession_number": "0001045810-25-000012",
                    "filing_type": "10-K",
                    "report_date": "2025-01-28",
                    "ticker": "NVDA",
                    "url": "https://www.sec.gov/...",
                    "xbrl_url": None,
                },
            ]
            result = get_sec_filings("NVDA", filing_types=["10-K"], limit=5)
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["filing_type"] == "10-K"
            mock_fn.assert_called_once_with(
                "NVDA", filing_types=["10-K"], limit=5
            )

    def test_returns_list(self):
        """Return type is always a list."""
        with patch("data_sources.sec_edgar_financials.get_filings_list") as mock_fn:
            mock_fn.return_value = []
            result = get_sec_filings("FAKE")
            assert isinstance(result, list)
            assert len(result) == 0

    def test_error_returns_empty(self):
        """Exceptions are caught and return empty list."""
        with patch("data_sources.sec_edgar_financials.get_filings_list") as mock_fn:
            mock_fn.side_effect = Exception("Network error")
            result = get_sec_filings("NVDA")
            assert result == []

    def test_default_limit(self):
        """Default limit is 10."""
        with patch("data_sources.sec_edgar_financials.get_filings_list") as mock_fn:
            mock_fn.return_value = []
            get_sec_filings("NVDA")
            mock_fn.assert_called_once_with("NVDA", filing_types=None, limit=10)


# ============================================================
# get_insider_trades
# ============================================================

class TestGetInsiderTrades:
    def test_basic(self):
        """Returns structured dict with ticker, count, trades."""
        with patch("data_sources.sec_insider_trades.get_insider_trades") as mock_fn:
            mock_fn.return_value = [
                {
                    "ticker": "AAPL",
                    "name": "Tim Cook",
                    "title": "CEO",
                    "transaction_date": "2025-01-15",
                    "transaction_shares": -50000,
                    "transaction_price_per_share": 230.50,
                    "transaction_value": -11525000,
                    "shares_owned_after_transaction": 3280000,
                    "filing_date": "2025-01-17",
                },
            ]
            result = get_insider_trades("AAPL", limit=5)
            assert result["ticker"] == "AAPL"
            assert result["count"] == 1
            assert len(result["trades"]) == 1
            assert result["trades"][0]["name"] == "Tim Cook"
            assert result["trades"][0]["transaction_shares"] == -50000

    def test_ticker_uppercased(self):
        """Ticker is uppercased in result."""
        with patch("data_sources.sec_insider_trades.get_insider_trades") as mock_fn:
            mock_fn.return_value = []
            result = get_insider_trades("aapl")
            assert result["ticker"] == "AAPL"

    def test_empty_trades(self):
        """No trades returns count=0."""
        with patch("data_sources.sec_insider_trades.get_insider_trades") as mock_fn:
            mock_fn.return_value = []
            result = get_insider_trades("FAKE")
            assert result["count"] == 0
            assert result["trades"] == []

    def test_error_returns_empty(self):
        """Exceptions are caught and return empty trades."""
        with patch("data_sources.sec_insider_trades.get_insider_trades") as mock_fn:
            mock_fn.side_effect = Exception("CIK not found")
            result = get_insider_trades("FAKE")
            assert result["ticker"] == "FAKE"
            assert result["count"] == 0
            assert result["trades"] == []

    def test_json_serializable(self):
        """Result is JSON-serializable."""
        with patch("data_sources.sec_insider_trades.get_insider_trades") as mock_fn:
            mock_fn.return_value = [
                {
                    "ticker": "NVDA",
                    "name": "Jensen Huang",
                    "title": "CEO",
                    "transaction_date": "2025-01-10",
                    "transaction_shares": -100000,
                    "transaction_price_per_share": 140.0,
                    "transaction_value": -14000000,
                    "shares_owned_after_transaction": 70000000,
                    "filing_date": "2025-01-12",
                },
            ]
            result = get_insider_trades("NVDA")
            serialized = json.dumps(result)
            assert '"ticker": "NVDA"' in serialized
            assert '"Jensen Huang"' in serialized


# ============================================================
# Bridge integration (tool counts)
# ============================================================

class TestBridgeIntegration:
    def test_registry_23(self):
        """Registry has 30 tools."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_all()) == 39

    def test_analysis_category_6(self):
        """Analysis category has 9 tools."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_by_category("analysis")) == 9

    def test_anthropic_includes_insider_trades(self):
        """Anthropic bridge includes get_insider_trades."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = {t["name"] for t in tools}
        assert "get_insider_trades" in names

    def test_openai_includes_insider_trades(self):
        """OpenAI bridge includes get_insider_trades."""
        from src.tools.data_access import DataAccessLayer
        from src.agents.openai_agent.tools import create_openai_tools
        dal = DataAccessLayer()
        tools = create_openai_tools(dal)
        names = {t.name for t in tools}
        assert "tool_get_insider_trades" in names