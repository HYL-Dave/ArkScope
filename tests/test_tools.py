"""
Integration tests for the 17 tool functions + ToolRegistry.

Tests run against real data to verify each tool produces correct output.
"""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.data_access import DataAccessLayer
from src.tools.schemas import (
    FundamentalsResult,
    IVAnalysisResult,
    IVHistoryPoint,
    MispricingResult,
    NewsQueryResult,
    PriceQueryResult,
    SECFiling,
    TradingSignal,
)
from src.tools.registry import ToolRegistry, create_default_registry


@pytest.fixture(scope="module")
def dal():
    return DataAccessLayer(base_path=project_root)


@pytest.fixture(scope="module")
def registry():
    return create_default_registry()


# ============================================================
# Registry
# ============================================================

class TestRegistry:
    def test_register_all(self, registry):
        """All 17 tools should be registered."""
        assert len(registry.list_all()) == 17

    def test_tool_names(self, registry):
        """All expected tool names should exist."""
        names = registry.list_names()
        expected = [
            "get_ticker_news", "get_news_sentiment_summary", "search_news_by_keyword",
            "get_ticker_prices", "get_price_change", "get_sector_performance",
            "get_iv_analysis", "get_iv_history_data", "scan_mispricing", "calculate_greeks",
            "detect_anomalies", "detect_event_chains", "synthesize_signal",
            "get_fundamentals_analysis", "get_sec_filings",
            "get_watchlist_overview", "get_morning_brief",
        ]
        for name in expected:
            assert name in names, f"Missing tool: {name}"

    def test_categories(self, registry):
        """Tools should be properly categorized."""
        assert len(registry.list_by_category("news")) == 3
        assert len(registry.list_by_category("prices")) == 3
        assert len(registry.list_by_category("options")) == 4
        assert len(registry.list_by_category("signals")) == 3
        assert len(registry.list_by_category("analysis")) == 4

    def test_openai_schema(self, registry):
        """OpenAI schema export should produce valid function definitions."""
        schema = registry.to_openai_schema()
        assert len(schema) == 17
        for tool in schema:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
            assert tool["function"]["parameters"]["type"] == "object"

    def test_anthropic_schema(self, registry):
        """Anthropic schema export should produce valid tool definitions."""
        schema = registry.to_anthropic_schema()
        assert len(schema) == 17
        for tool in schema:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_get_tool(self, registry):
        """Lookup by name should return correct tool."""
        tool = registry.get("calculate_greeks")
        assert tool is not None
        assert tool.name == "calculate_greeks"
        assert tool.requires_dal is False

    def test_tool_has_parameters(self, registry):
        """Tools should have parameter definitions."""
        tool = registry.get("get_ticker_news")
        assert len(tool.parameters) >= 1
        ticker_param = tool.parameters[0]
        assert ticker_param.name == "ticker"
        assert ticker_param.type == "string"
        assert ticker_param.required is True


# ============================================================
# News Tools (1-3)
# ============================================================

class TestNewsTools:
    def test_get_ticker_news(self, dal):
        from src.tools.news_tools import get_ticker_news
        result = get_ticker_news(dal, ticker="NVDA", days=9999)
        assert isinstance(result, NewsQueryResult)
        assert result.ticker == "NVDA"
        assert result.count > 0

    def test_get_news_sentiment_summary(self, dal):
        from src.tools.news_tools import get_news_sentiment_summary
        result = get_news_sentiment_summary(dal, ticker="NVDA", days=9999)
        assert isinstance(result, dict)
        assert result["ticker"] == "NVDA"
        assert result["scored_count"] > 0
        assert result["sentiment_mean"] is not None
        assert 1 <= result["sentiment_mean"] <= 5
        assert 0 <= result["bullish_ratio"] <= 1

    def test_search_news_by_keyword(self, dal):
        from src.tools.news_tools import search_news_by_keyword
        result = search_news_by_keyword(dal, keyword="earnings", days=9999)
        assert isinstance(result, NewsQueryResult)
        # Should find some articles about earnings
        assert result.count > 0

    def test_search_news_keyword_case_insensitive(self, dal):
        from src.tools.news_tools import search_news_by_keyword
        r1 = search_news_by_keyword(dal, keyword="NVIDIA", days=9999)
        r2 = search_news_by_keyword(dal, keyword="nvidia", days=9999)
        assert r1.count == r2.count


# ============================================================
# Price Tools (4-6)
# ============================================================

class TestPriceTools:
    def test_get_ticker_prices(self, dal):
        from src.tools.price_tools import get_ticker_prices
        result = get_ticker_prices(dal, ticker="NVDA", interval="15min", days=7)
        assert isinstance(result, PriceQueryResult)
        assert result.ticker == "NVDA"
        assert result.count > 0

    def test_get_price_change(self, dal):
        from src.tools.price_tools import get_price_change
        result = get_price_change(dal, ticker="NVDA", days=30)
        assert isinstance(result, dict)
        assert result["ticker"] == "NVDA"
        assert result["bar_count"] > 0
        assert "change_pct" in result
        assert "period_high" in result
        assert result["period_high"] >= result["period_low"]

    def test_get_sector_performance(self, dal):
        from src.tools.price_tools import get_sector_performance
        result = get_sector_performance(dal, sector="AI_CHIPS", days=30)
        assert isinstance(result, dict)
        assert result["sector"] == "AI_CHIPS"
        assert result["ticker_count"] > 0
        assert "avg_change_pct" in result
        assert "best_ticker" in result
        assert "worst_ticker" in result

    def test_get_sector_performance_unknown(self, dal):
        from src.tools.price_tools import get_sector_performance
        result = get_sector_performance(dal, sector="NONEXISTENT", days=7)
        assert "error" in result


# ============================================================
# Options Tools (7-10)
# ============================================================

class TestOptionsTools:
    def test_get_iv_analysis(self, dal):
        from src.tools.options_tools import get_iv_analysis
        result = get_iv_analysis(dal, ticker="AMD")
        assert isinstance(result, IVAnalysisResult)
        assert result.ticker == "AMD"
        assert result.history_days >= 1
        assert result.current_iv is not None
        assert result.current_iv > 0

    def test_get_iv_analysis_no_data(self, dal):
        from src.tools.options_tools import get_iv_analysis
        result = get_iv_analysis(dal, ticker="XXXNOTREAL")
        assert isinstance(result, IVAnalysisResult)
        assert result.history_days == 0
        assert result.signal in ("NO_DATA", "NO_IV_DATA")

    def test_get_iv_history_data(self, dal):
        from src.tools.options_tools import get_iv_history_data
        result = get_iv_history_data(dal, ticker="AMD")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], IVHistoryPoint)

    def test_calculate_greeks(self):
        from src.tools.options_tools import calculate_greeks
        result = calculate_greeks(S=150, K=155, T=0.25, r=0.05, sigma=0.30, option_type="C")
        assert isinstance(result, dict)
        assert "delta" in result
        assert "gamma" in result
        assert "theta" in result
        assert "vega" in result
        assert "rho" in result
        # Call delta should be between 0 and 1
        assert 0 <= result["delta"] <= 1

    def test_calculate_greeks_put(self):
        from src.tools.options_tools import calculate_greeks
        result = calculate_greeks(S=150, K=155, T=0.25, r=0.05, sigma=0.30, option_type="P")
        # Put delta should be between -1 and 0
        assert -1 <= result["delta"] <= 0

    def test_scan_mispricing_no_quotes(self, dal):
        from src.tools.options_tools import scan_mispricing
        # Without cached quotes, should return empty list
        result = scan_mispricing(dal, tickers=["AMD"])
        assert isinstance(result, list)
        assert len(result) == 0


# ============================================================
# Signal Tools (11-13)
# ============================================================

class TestSignalTools:
    def test_detect_anomalies(self, dal):
        from src.tools.signal_tools import detect_anomalies
        result = detect_anomalies(dal, ticker="NVDA", days=9999)
        assert isinstance(result, dict)
        assert result["ticker"] == "NVDA"
        # Should have either results or error
        assert "sentiment_anomaly" in result or "error" in result

    def test_detect_event_chains(self, dal):
        from src.tools.signal_tools import detect_event_chains
        result = detect_event_chains(dal, ticker="NVDA", days=9999)
        assert isinstance(result, list)
        # May or may not have chains depending on data
        if result:
            chain = result[0]
            assert "pattern" in chain
            assert "impact_score" in chain
            assert "events" in chain

    def test_synthesize_signal(self, dal):
        from src.tools.signal_tools import synthesize_signal
        result = synthesize_signal(dal, ticker="NVDA", days=9999)
        assert isinstance(result, TradingSignal)
        assert result.ticker == "NVDA"
        assert result.action in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")
        assert 0 <= result.confidence <= 1
        assert 1 <= result.risk_level <= 5


# ============================================================
# Analysis Tools (14-17)
# ============================================================

class TestAnalysisTools:
    def test_get_fundamentals_analysis(self, dal):
        from src.tools.analysis_tools import get_fundamentals_analysis
        result = get_fundamentals_analysis(dal, ticker="NVDA")
        assert isinstance(result, FundamentalsResult)
        assert result.ticker == "NVDA"
        assert result.market_cap is not None

    def test_get_sec_filings(self, dal):
        from src.tools.analysis_tools import get_sec_filings
        result = get_sec_filings(dal, ticker="NVDA")
        assert isinstance(result, list)
        # FileBackend returns empty

    def test_get_watchlist_overview(self, dal):
        from src.tools.analysis_tools import get_watchlist_overview
        result = get_watchlist_overview(dal)
        assert isinstance(result, dict)
        assert "tickers" in result
        assert result["ticker_count"] > 0
        # Each ticker should have at least ticker and group
        for t in result["tickers"]:
            assert "ticker" in t
            assert "group" in t

    def test_get_morning_brief(self, dal):
        from src.tools.analysis_tools import get_morning_brief
        result = get_morning_brief(dal)
        assert isinstance(result, dict)
        assert "date" in result
        assert "holdings" in result
        assert isinstance(result["holdings"], list)