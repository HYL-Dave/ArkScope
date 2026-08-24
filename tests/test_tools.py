"""
Integration tests for tool functions and ToolRegistry.

Tests run against real data to verify each tool produces correct output.
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.data_access import DataAccessLayer
from src.tools.schemas import (
    FundamentalsResult,
    NewsQueryResult,
    PriceQueryResult,
    SECFiling,
)
from src.tools.registry import ToolRegistry, create_default_registry


@pytest.fixture(scope="module")
def dal():
    return DataAccessLayer(base_path=project_root)


_HERMETIC_NEWS_ROWS = [
    {
        "date": "2026-07-30T14:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA earnings beat expectations",
        "source": "polygon",
        "url": "https://example.test/nvda-earnings",
        "publisher": "Example Wire",
        "description": "NVIDIA reported stronger earnings.",
    },
    {
        "date": "2026-07-30T13:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA product update",
        "source": "ibkr",
        "url": "https://example.test/nvda-product",
        "publisher": "Example Desk",
        "description": "NVIDIA announced a product update.",
    },
    {
        "date": "2026-07-30T12:00:00+0000",
        "ticker": "AMD",
        "title": "AMD earnings preview",
        "source": "finnhub",
        "url": "https://example.test/amd-earnings",
        "publisher": "Example Wire",
        "description": "Analysts preview AMD earnings.",
    },
]

_HERMETIC_PRICE_ROWS = {
    ("NVDA", "15min"): [
        ("2026-07-30T13:30:00+0000", 100.0, 102.0, 99.0, 101.0, 100),
        ("2026-07-30T13:45:00+0000", 101.0, 106.0, 100.0, 105.0, 120),
    ],
    ("NVDA", "1d"): [
        ("2026-07-29T00:00:00+0000", 100.0, 106.0, 99.0, 105.0, 1000),
        ("2026-07-30T00:00:00+0000", 105.0, 112.0, 104.0, 110.0, 1200),
    ],
    ("AMD", "15min"): [
        ("2026-07-30T13:30:00+0000", 50.0, 52.0, 49.0, 51.0, 200),
        ("2026-07-30T13:45:00+0000", 51.0, 53.0, 50.0, 52.0, 220),
    ],
    ("AMD", "1d"): [
        ("2026-07-29T00:00:00+0000", 50.0, 53.0, 49.0, 52.0, 2000),
        ("2026-07-30T00:00:00+0000", 52.0, 53.0, 50.0, 51.0, 2200),
    ],
}

_PRICE_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


class _HermeticMarketBackend:
    def query_news(
        self,
        ticker=None,
        days=30,
        source="auto",
    ):
        del days
        frame = pd.DataFrame(_HERMETIC_NEWS_ROWS)
        if ticker:
            frame = frame[frame["ticker"] == ticker.upper()]
        if source not in ("", "auto", None):
            frame = frame[frame["source"] == source]
        return frame.reset_index(drop=True)

    def query_news_search(self, query="", ticker=None, days=30, limit=20):
        frame = self.query_news(ticker=ticker, days=days, source="auto")
        needle = str(query or "").casefold()
        if needle:
            haystack = (
                frame["title"].fillna("").astype(str)
                + "\n"
                + frame["description"].fillna("").astype(str)
            ).str.casefold()
            frame = frame[haystack.str.contains(needle, regex=False)]
        return frame.head(max(0, int(limit))).reset_index(drop=True)

    def query_prices(self, ticker, interval="15min", days=30):
        del days
        rows = _HERMETIC_PRICE_ROWS.get((ticker.upper(), interval), [])
        return pd.DataFrame(rows, columns=_PRICE_COLUMNS)

    def query_fundamentals(self, ticker):
        if ticker.upper() != "NVDA":
            return {}
        return {
            "collected_at": "2026-07-30T00:00:00+0000",
            "snapshot": {
                "market_cap": 1_500_000_000_000.0,
                "pe_ratio": 30.0,
                "price_to_sales": 15.0,
                "price_to_book": 25.0,
            },
        }

    def get_financial_cache(self, cache_key):
        if cache_key != "fundamentals_analysis:sec_edgar:NVDA:annual:v1":
            return None
        return FundamentalsResult(
            ticker="NVDA",
            snapshot_date="2025-12-31",
            data_source="sec_edgar",
            roe=0.31,
            revenue_growth=0.25,
            free_cash_flow=500_000.0,
        ).model_dump()

    def get_available_tickers(self, data_type):
        return {
            "news": ["AMD", "NVDA"],
            "prices": ["AMD", "NVDA"],
            "fundamentals": ["NVDA"],
        }.get(data_type, [])


@pytest.fixture()
def hermetic_dal():
    return DataAccessLayer(
        base_path=project_root,
        backend=_HermeticMarketBackend(),
    )


def _install_fundamentals_provider_spies(monkeypatch):
    calls = []

    def _record_sec(*args, **kwargs):
        del args, kwargs
        calls.append("sec_edgar")
        raise RuntimeError("SEC provider fallback reached")

    def _record_fd(*args, **kwargs):
        del args, kwargs
        calls.append("financial_datasets")
        return False

    monkeypatch.setattr(
        "data_sources.sec_edgar_financials.SECEdgarFinancials",
        _record_sec,
    )
    monkeypatch.setattr(
        "src.tools.analysis_tools._is_fd_enabled",
        _record_fd,
    )
    return calls




@pytest.fixture(scope="module")
def registry():
    return create_default_registry()


# ============================================================
# Registry
# ============================================================

class TestRegistry:
    def test_register_all(self, registry):
        """All tools should be registered (incl. P1.2 macro_calendar)."""
        assert len(registry.list_all()) == 50

    def test_tool_names(self, registry):
        """All expected tool names should exist."""
        names = registry.list_names()
        expected = {
            "get_ticker_news", "search_news_by_keyword",
            "get_ticker_prices", "get_current_quote", "get_price_change", "get_sector_performance",
            "get_ticker_data_coverage",
            "calculate_greeks", "get_option_chain", "get_iv_skew_analysis",
            "detect_news_volume_anomaly", "detect_event_chains",
            "get_fundamentals_analysis", "get_sec_filings",
            "get_watchlist_overview", "get_morning_brief",
            "get_portfolio_holdings",
            "get_security_lifecycle_case",
            "list_security_lifecycle_cases",
            "execute_python_analysis",
        }
        retired = {"get_iv_analysis", "get_iv_history_data", "scan_mispricing"}
        assert expected <= set(names)
        assert retired.isdisjoint(names)

    def test_categories(self, registry):
        """Tools should be properly categorized."""
        assert len(registry.list_by_category("news")) == 11
        assert len(registry.list_by_category("prices")) == 4
        assert len(registry.list_by_category("options")) == 3
        assert len(registry.list_by_category("signals")) == 0
        assert len(registry.list_by_category("analysis")) == 15
        assert len(registry.list_by_category("portfolio")) == 7
        assert len(registry.list_by_category("execution")) == 1

    def test_openai_schema(self, registry):
        """OpenAI schema export should produce valid function definitions."""
        schema = registry.to_openai_schema()
        assert len(schema) == 50
        for tool in schema:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
            assert tool["function"]["parameters"]["type"] == "object"

    def test_anthropic_schema(self, registry):
        """Anthropic schema export should produce valid tool definitions."""
        schema = registry.to_anthropic_schema()
        assert len(schema) == 50
        for tool in schema:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_tool_catalog_live_table_matches_registry(self, registry):
        """The canonical Tool Catalog live table must match ToolRegistry."""
        catalog = (project_root / "docs/design/ARKSCOPE_TOOL_CATALOG.md").read_text()
        live_tables = catalog.split("### 1.4 Retire-adapt", 1)[0]
        catalog_names = set(re.findall(r"^\| `([^`]+)` \|", live_tables, re.MULTILINE))
        assert catalog_names == set(registry.list_names())

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
    def test_get_ticker_news(self, hermetic_dal):
        from src.tools.news_tools import get_ticker_news
        result = get_ticker_news(hermetic_dal, ticker="NVDA", days=9999)
        assert isinstance(result, NewsQueryResult)
        assert result.ticker == "NVDA"
        assert result.count == 2
        assert result.source_breakdown == {"polygon": 1, "ibkr": 1}

    def test_search_news_by_keyword(self, hermetic_dal):
        from src.tools.news_tools import search_news_by_keyword
        result = search_news_by_keyword(
            hermetic_dal,
            keyword="earnings",
            days=9999,
        )
        assert isinstance(result, NewsQueryResult)
        assert result.count == 2
        assert {article.ticker for article in result.articles} == {"NVDA", "AMD"}

    def test_search_news_keyword_case_insensitive(self, dal):
        from src.tools.news_tools import search_news_by_keyword
        r1 = search_news_by_keyword(dal, keyword="NVIDIA", days=9999)
        r2 = search_news_by_keyword(dal, keyword="nvidia", days=9999)
        assert r1.count == r2.count


# ============================================================
# Price Tools (4-6)
# ============================================================

class TestPriceTools:
    def test_get_ticker_prices(self, hermetic_dal):
        from src.tools.price_tools import get_ticker_prices
        result = get_ticker_prices(
            hermetic_dal,
            ticker="NVDA",
            interval="15min",
            days=7,
        )
        assert isinstance(result, PriceQueryResult)
        assert result.ticker == "NVDA"
        assert result.count == 2
        assert [bar.close for bar in result.bars] == [101.0, 105.0]

    def test_get_price_change(self, hermetic_dal):
        from src.tools.price_tools import get_price_change
        result = get_price_change(hermetic_dal, ticker="NVDA", days=30)
        assert result["ticker"] == "NVDA"
        assert result["bar_count"] == 2
        assert result["change_pct"] == 10.0
        assert result["period_high"] == 112.0
        assert result["period_low"] == 99.0
        assert result["total_volume"] == 2200

    def test_get_sector_performance(self, hermetic_dal):
        from src.tools.price_tools import get_sector_performance
        result = get_sector_performance(
            hermetic_dal,
            sector="AI_CHIPS",
            days=30,
        )
        assert result["sector"] == "AI_CHIPS"
        assert result["ticker_count"] == 2
        assert result["avg_change_pct"] == 6.0
        assert result["best_ticker"] == "NVDA"
        assert result["worst_ticker"] == "AMD"

    def test_get_sector_performance_unknown(self, dal):
        from src.tools.price_tools import get_sector_performance
        result = get_sector_performance(dal, sector="NONEXISTENT", days=7)
        assert "error" in result


# ============================================================
# Retained options tools
# ============================================================

class TestOptionsTools:
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

# ============================================================
# Analysis Tools (14-17)
# ============================================================

class TestAnalysisTools:
    def test_get_fundamentals_analysis(self, hermetic_dal, monkeypatch):
        from src.tools.analysis_tools import get_fundamentals_analysis
        provider_calls = _install_fundamentals_provider_spies(monkeypatch)
        result = get_fundamentals_analysis(hermetic_dal, ticker="NVDA")
        assert provider_calls == []
        assert isinstance(result, FundamentalsResult)
        assert result.ticker == "NVDA"
        assert result.data_source == "sec_edgar"
        assert result.snapshot_date == "2025-12-31"
        assert result.roe == 0.31
        assert result.revenue_growth == 0.25
        assert result.market_cap is None
        assert result.pe_ratio is None

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

    def test_get_morning_brief_orders_raw_news_deterministically(self):
        from unittest.mock import MagicMock

        from types import SimpleNamespace

        from src.tools.analysis_tools import get_morning_brief

        details = [
            SimpleNamespace(ticker=ticker, group="interested", priority="medium")
            for ticker in ("ZZZ", "AAA", "BBB", "CCC", "DDD", "EEE")
        ]
        dal = MagicMock()
        dal.get_user_profile.return_value = {"watchlists": {}}
        dal.get_watchlist.return_value = SimpleNamespace(details=details)
        dal.get_available_tickers.return_value = []
        dal.get_news_stats.return_value = [
            {"ticker": "AAA", "article_count": 4, "latest_date": "2026-08-08"},
            {"ticker": "ZZZ", "article_count": 4, "latest_date": "2026-08-08"},
            {"ticker": "BBB", "article_count": 4, "latest_date": "2026-08-09"},
            {"ticker": "CCC", "article_count": 3, "latest_date": "2026-08-09"},
            {"ticker": "DDD", "article_count": 2, "latest_date": "2026-08-09"},
            {"ticker": "EEE", "article_count": 1, "latest_date": "2026-08-09"},
            {"ticker": "ZERO", "article_count": 0, "latest_date": None},
        ]

        result = get_morning_brief(dal)

        dal.get_news_stats.assert_called_once_with(days=1)
        assert result["notable_news"] == [
            {"ticker": "BBB", "count": 4, "latest_date": "2026-08-09"},
            {"ticker": "AAA", "count": 4, "latest_date": "2026-08-08"},
            {"ticker": "ZZZ", "count": 4, "latest_date": "2026-08-08"},
            {"ticker": "CCC", "count": 3, "latest_date": "2026-08-09"},
            {"ticker": "DDD", "count": 2, "latest_date": "2026-08-09"},
        ]
