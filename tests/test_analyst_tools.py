"""
Tests for analyst consensus tools (Phase 11b).

All Finnhub API calls are mocked — no network requests needed.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.tools.analyst_tools import (
    _finnhub_get,
    _fetch_recommendations,
    _fetch_earnings_history,
    _fetch_upcoming_earnings,
    _fetch_price_target,
    get_analyst_consensus,
)


# ============================================================
# _finnhub_get
# ============================================================

class TestFinnhubGet:
    def test_no_api_key(self):
        """Missing API key raises ValueError."""
        import src.tools.analyst_tools as mod
        mod._session = None
        mod._api_key = None
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="FINNHUB_API_KEY"):
                _finnhub_get("/test")
        # Reset for other tests
        mod._session = None
        mod._api_key = None

    @patch("src.tools.analyst_tools._get_finnhub_session")
    def test_request_error(self, mock_session):
        """Network error returns None."""
        import requests
        session = MagicMock()
        session.get.side_effect = requests.RequestException("timeout")
        mock_session.return_value = (session, "fake-key")

        result = _finnhub_get("/stock/recommendation", {"symbol": "NVDA"})
        assert result is None

    @patch("src.tools.analyst_tools._get_finnhub_session")
    def test_403_graceful(self, mock_session):
        """403 (premium endpoint) returns None gracefully."""
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 403
        session.get.return_value = resp
        mock_session.return_value = (session, "fake-key")

        result = _finnhub_get("/stock/price-target", {"symbol": "NVDA"})
        assert result is None

    @patch("src.tools.analyst_tools._get_finnhub_session")
    def test_200_success(self, mock_session):
        """200 response returns parsed JSON."""
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status.return_value = None
        resp.json.return_value = [{"buy": 10}]
        session.get.return_value = resp
        mock_session.return_value = (session, "fake-key")

        result = _finnhub_get("/stock/recommendation", {"symbol": "NVDA"})
        assert result == [{"buy": 10}]


# ============================================================
# _fetch_recommendations
# ============================================================

class TestRecommendations:
    @patch("src.tools.analyst_tools._finnhub_get")
    def test_basic(self, mock_get):
        """Parses current + trend from recommendation data."""
        mock_get.return_value = [
            {"strongBuy": 13, "buy": 24, "hold": 7, "sell": 1, "strongSell": 0, "period": "2025-03-01"},
            {"strongBuy": 12, "buy": 23, "hold": 8, "sell": 1, "strongSell": 0, "period": "2025-02-01"},
            {"strongBuy": 11, "buy": 22, "hold": 9, "sell": 2, "strongSell": 0, "period": "2025-01-01"},
        ]
        result = _fetch_recommendations("NVDA")
        assert result["current"]["strongBuy"] == 13
        assert result["current"]["period"] == "2025-03-01"
        assert len(result["trend"]) == 2
        assert result["trend"][0]["strongBuy"] == 12

    @patch("src.tools.analyst_tools._finnhub_get")
    def test_empty(self, mock_get):
        """Empty API response returns null current."""
        mock_get.return_value = []
        result = _fetch_recommendations("FAKE")
        assert result["current"] is None
        assert result["trend"] == []


# ============================================================
# _fetch_earnings_history
# ============================================================

class TestEarningsHistory:
    @patch("src.tools.analyst_tools._finnhub_get")
    def test_4_quarters(self, mock_get):
        """Parses last 4 quarters earnings data."""
        mock_get.return_value = [
            {"period": "2024-12-31", "actual": 0.89, "estimate": 0.85, "surprisePercent": 4.71},
            {"period": "2024-09-30", "actual": 0.81, "estimate": 0.75, "surprisePercent": 8.0},
            {"period": "2024-06-30", "actual": 0.68, "estimate": 0.65, "surprisePercent": 4.62},
            {"period": "2024-03-31", "actual": 0.60, "estimate": 0.58, "surprisePercent": 3.45},
        ]
        result = _fetch_earnings_history("NVDA")
        assert len(result) == 4
        assert result[0]["period"] == "2024-12-31"
        assert result[0]["actual"] == 0.89
        assert result[0]["surprisePercent"] == 4.71

    @patch("src.tools.analyst_tools._finnhub_get")
    def test_empty(self, mock_get):
        """No earnings data returns empty list."""
        mock_get.return_value = None
        result = _fetch_earnings_history("FAKE")
        assert result == []


# ============================================================
# _fetch_upcoming_earnings
# ============================================================

class TestUpcomingEarnings:
    @patch("src.tools.analyst_tools._finnhub_get")
    def test_found(self, mock_get):
        """Finds upcoming earnings for ticker."""
        mock_get.return_value = {
            "earningsCalendar": [
                {
                    "symbol": "NVDA",
                    "date": "2025-04-25",
                    "hour": "amc",
                    "epsEstimate": 0.92,
                    "revenueEstimate": 44200000000,
                },
                {
                    "symbol": "AMD",
                    "date": "2025-04-28",
                    "hour": "bmo",
                    "epsEstimate": 1.05,
                    "revenueEstimate": 7100000000,
                },
            ]
        }
        result = _fetch_upcoming_earnings("NVDA")
        assert result is not None
        assert result["date"] == "2025-04-25"
        assert result["epsEstimate"] == 0.92

    @patch("src.tools.analyst_tools._finnhub_get")
    def test_no_upcoming(self, mock_get):
        """No upcoming earnings returns None."""
        mock_get.return_value = {"earningsCalendar": []}
        result = _fetch_upcoming_earnings("FAKE")
        assert result is None


# ============================================================
# _fetch_price_target
# ============================================================

class TestPriceTarget:
    @patch("src.tools.analyst_tools._finnhub_get")
    def test_premium_403(self, mock_get):
        """Premium endpoint returns None on 403."""
        mock_get.return_value = None
        result = _fetch_price_target("NVDA")
        assert result is None

    @patch("src.tools.analyst_tools._finnhub_get")
    def test_available(self, mock_get):
        """Returns price target data when available."""
        mock_get.return_value = {
            "targetHigh": 200.0,
            "targetLow": 120.0,
            "targetMean": 165.5,
            "targetMedian": 170.0,
            "lastUpdated": "2025-03-15",
        }
        result = _fetch_price_target("NVDA")
        assert result is not None
        assert result["targetMean"] == 165.5
        assert result["targetMedian"] == 170.0


# ============================================================
# get_analyst_consensus (full aggregation)
# ============================================================

class TestConsensus:
    @patch("src.tools.analyst_tools._fetch_price_target")
    @patch("src.tools.analyst_tools._fetch_upcoming_earnings")
    @patch("src.tools.analyst_tools._fetch_earnings_history")
    @patch("src.tools.analyst_tools._fetch_recommendations")
    def test_full_aggregation(self, mock_rec, mock_earn, mock_up, mock_pt):
        """Aggregates all 4 endpoints into structured dict."""
        mock_rec.return_value = {
            "current": {"strongBuy": 5, "buy": 10, "hold": 3, "sell": 0, "strongSell": 0, "period": "2025-03"},
            "trend": [],
        }
        mock_earn.return_value = [{"period": "2024-12", "actual": 1.0, "estimate": 0.9, "surprisePercent": 11.1}]
        mock_up.return_value = {"date": "2025-04-25", "hour": "amc", "epsEstimate": 1.1, "revenueEstimate": 50e9}
        mock_pt.return_value = None

        result = get_analyst_consensus("nvda")
        assert result["ticker"] == "NVDA"
        assert result["recommendations"]["current"]["strongBuy"] == 5
        assert len(result["earnings"]["history"]) == 1
        assert result["earnings"]["upcoming"]["epsEstimate"] == 1.1
        assert result["price_target"] is None

    @patch("src.tools.analyst_tools._fetch_price_target")
    @patch("src.tools.analyst_tools._fetch_upcoming_earnings")
    @patch("src.tools.analyst_tools._fetch_earnings_history")
    @patch("src.tools.analyst_tools._fetch_recommendations")
    def test_ticker_uppercase(self, mock_rec, mock_earn, mock_up, mock_pt):
        """Ticker is uppercased in result."""
        mock_rec.return_value = {"current": None, "trend": []}
        mock_earn.return_value = []
        mock_up.return_value = None
        mock_pt.return_value = None

        result = get_analyst_consensus("aapl")
        assert result["ticker"] == "AAPL"

    @patch("src.tools.analyst_tools._fetch_price_target")
    @patch("src.tools.analyst_tools._fetch_upcoming_earnings")
    @patch("src.tools.analyst_tools._fetch_earnings_history")
    @patch("src.tools.analyst_tools._fetch_recommendations")
    def test_json_serializable(self, mock_rec, mock_earn, mock_up, mock_pt):
        """Result is JSON-serializable."""
        mock_rec.return_value = {"current": None, "trend": []}
        mock_earn.return_value = []
        mock_up.return_value = None
        mock_pt.return_value = None

        result = get_analyst_consensus("TSLA")
        serialized = json.dumps(result)
        assert '"ticker": "TSLA"' in serialized


# ============================================================
# Bridge integration (tool counts)
# ============================================================

class TestBridgeIntegration:
    def test_registry_23(self):
        """Registry has 41 tools (including check_data_freshness)."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_all()) == 41

    def test_analysis_category_6(self):
        """Analysis category has 10 tools (including check_data_freshness)."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_by_category("analysis")) == 10

    def test_anthropic_includes(self):
        """Anthropic bridge includes get_analyst_consensus."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = {t["name"] for t in tools}
        assert "get_analyst_consensus" in names

    def test_openai_includes(self):
        """OpenAI bridge includes get_analyst_consensus."""
        from src.tools.data_access import DataAccessLayer
        from src.agents.openai_agent.tools import create_openai_tools
        dal = DataAccessLayer()
        tools = create_openai_tools(dal)
        names = {t.name for t in tools}
        assert "tool_get_analyst_consensus" in names