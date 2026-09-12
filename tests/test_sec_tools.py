"""
Tests for SEC data tools (Phase 11a).

All SEC EDGAR HTTP calls are mocked — no network requests needed.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.tools.sec_tools import get_insider_trades


class TestSecReplacement:
    def test_catalog_only_api_removed_but_facts_mapper_remains(self):
        from src.tools import sec_tools
        from data_sources import sec_edgar_financials, base
        assert not hasattr(sec_tools, "get_sec_filings")
        assert not hasattr(sec_edgar_financials, "get_filings_list")
        assert not hasattr(sec_edgar_financials, "FilingInfo")
        assert not hasattr(sec_edgar_financials.SECEdgarFinancials, "get_filings_list")
        assert callable(sec_edgar_financials.SECEdgarFinancials.get_income_statement)
        assert base.SECFiling

    def test_new_catalog_uses_real_tool_service(self, tmp_path, monkeypatch):
        from tests.test_sec_research_tool_adapters import tool_fixture, wire, CIK
        from src.tools.registry import create_default_registry
        fixture = tool_fixture.__wrapped__(tmp_path)
        wire(monkeypatch, fixture.service)
        registry = create_default_registry()
        result = registry.get("list_sec_filings").function(issuer=CIK, forms=["10-Q"])
        assert len(result["data"]) == 1 and result["data"][0]["form"] == "10-Q"
        assert result["data"][0]["sources"][0]["source"]["pointer"]


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
        """Registry includes SEC plus macro/calendar, SA, and coverage tools."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_all()) == 56

    def test_analysis_category_6(self):
        """Analysis category has 13 tools (incl. macro snapshot + coverage diagnostics)."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_by_category("analysis")) == 17

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
