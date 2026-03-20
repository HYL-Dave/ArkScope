"""
Tests for Agent SDK integration.

These tests verify:
1. Tool definitions and schemas
2. Tool execution dispatch
3. Config loading
4. API endpoint availability

Note: Actual LLM calls are NOT tested here (require API keys).
Use integration tests or manual testing for full agent flows.
"""

import json
import re

import pytest


def _unwrap(result: str) -> str:
    """Strip <tool_output> wrapping (Phase 15) to get raw JSON."""
    m = re.search(r"<tool_output[^>]*>\n(.*)\n</tool_output>", result, re.DOTALL)
    return m.group(1) if m else result

from src.agents.config import AgentConfig, get_agent_config
from src.agents.shared.prompts import SYSTEM_PROMPT
from src.tools.data_access import DataAccessLayer


# ============================================================
# Config Tests
# ============================================================

class TestAgentConfig:
    def test_default_config(self):
        """Default config has expected values."""
        config = AgentConfig()
        assert config.openai_model == "gpt-5.2"
        assert config.anthropic_model == "claude-opus-4-6"
        assert config.reasoning_effort in ("none", "minimal", "low", "medium", "high", "xhigh")
        assert config.max_tool_calls > 0
        assert config.max_tokens > 0

    def test_anthropic_effort_default(self):
        """Anthropic effort is None by default (don't send)."""
        config = AgentConfig()
        assert config.anthropic_effort is None

    def test_anthropic_thinking_default(self):
        """Anthropic thinking is off by default."""
        config = AgentConfig()
        assert config.anthropic_thinking is False

    def test_context_management_defaults(self):
        """Context management config has sensible defaults."""
        config = AgentConfig()
        assert 0 < config.context_threshold_ratio <= 1.0
        assert config.context_keep_recent_turns >= 1
        assert config.context_preview_chars > 0

    def test_get_agent_config(self):
        """get_agent_config returns cached config."""
        config1 = get_agent_config()
        config2 = get_agent_config()
        # Should return same cached instance
        assert config1 is config2


# ============================================================
# Prompts Tests
# ============================================================

class TestPrompts:
    def test_system_prompt_exists(self):
        """System prompt is non-empty."""
        assert SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_mentions_tools(self):
        """System prompt describes available tools."""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "news" in prompt_lower
        assert "price" in prompt_lower
        assert "option" in prompt_lower or "iv" in prompt_lower


# ============================================================
# Anthropic Tool Schema Tests
# ============================================================

class TestAnthropicToolSchemas:
    def test_tool_count(self):
        """All tools are defined (base + web + analyst + insider + delegate + report + memory + smart search + freshness + rl)."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        assert len(tools) == 50

    def test_tool_schema_structure(self):
        """Each tool has required fields."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_tool_names(self):
        """All expected tool names exist."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        tool_names = {t["name"] for t in tools}

        expected = {
            "get_ticker_news",
            "get_news_sentiment_summary",
            "search_news_by_keyword",
            "get_news_brief",
            "search_news_advanced",
            "get_ticker_prices",
            "get_price_change",
            "get_sector_performance",
            "get_iv_analysis",
            "get_iv_history_data",
            "scan_mispricing",
            "calculate_greeks",
            "detect_anomalies",
            "detect_event_chains",
            "synthesize_signal",
            "get_fundamentals_analysis",
            "get_sec_filings",
            "get_watchlist_overview",
            "get_morning_brief",
            "get_insider_trades",
            "get_analyst_consensus",
            "execute_python_analysis",
            "delegate_to_subagent",
            "tavily_search",
            "tavily_fetch",
            "web_browse",
            "codex_web_research",
            "save_report",
            "list_reports",
            "get_report",
            "save_memory",
            "recall_memories",
            "list_memories",
            "delete_memory",
            "get_detailed_financials",
            "get_option_chain",
            "get_peer_comparison",
            "get_iv_skew_analysis",
            "get_portfolio_analysis",
            "get_earnings_impact",
            "scan_alerts",
            "check_data_freshness",
            "get_rl_model_status",
            "get_rl_prediction",
            "get_rl_backtest_report",
            "get_sa_alpha_picks",
            "get_sa_pick_detail",
            "refresh_sa_alpha_picks",
            "get_sa_articles",
            "get_sa_article_detail",
        }
        assert tool_names == expected


# ============================================================
# Anthropic Tool Execution Tests
# ============================================================

class TestAnthropicToolExecution:
    @pytest.fixture
    def dal(self):
        return DataAccessLayer()

    def test_execute_get_ticker_news(self, dal):
        """execute_tool dispatches to get_ticker_news."""
        from src.agents.anthropic_agent.tools import execute_tool

        result = execute_tool(
            "get_ticker_news",
            {"ticker": "NVDA", "days": 9999},
            dal
        )

        data = json.loads(_unwrap(result))
        assert data["ticker"] == "NVDA"
        assert data["count"] > 0

    def test_execute_get_price_change(self, dal):
        """execute_tool dispatches to get_price_change."""
        from src.agents.anthropic_agent.tools import execute_tool

        result = execute_tool(
            "get_price_change",
            {"ticker": "NVDA", "days": 30},
            dal
        )

        data = json.loads(_unwrap(result))
        assert data["ticker"] == "NVDA"
        assert "change_pct" in data

    def test_execute_calculate_greeks(self, dal):
        """execute_tool dispatches to calculate_greeks (no DAL needed)."""
        from src.agents.anthropic_agent.tools import execute_tool

        result = execute_tool(
            "calculate_greeks",
            {"S": 100, "K": 105, "T": 0.25, "r": 0.05, "sigma": 0.20},
            dal
        )

        data = json.loads(_unwrap(result))
        assert "delta" in data
        assert "gamma" in data
        assert 0 <= data["delta"] <= 1

    def test_execute_unknown_tool(self, dal):
        """Unknown tool returns error."""
        from src.agents.anthropic_agent.tools import execute_tool

        result = execute_tool("unknown_tool", {}, dal)
        data = json.loads(result)
        assert "error" in data


# ============================================================
# OpenAI Tool Creation Tests
# ============================================================

class TestOpenAIToolCreation:
    @pytest.fixture
    def dal(self):
        return DataAccessLayer()

    def test_create_tools_count(self, dal):
        """Creates tools (base + web + analyst + insider + delegate + report + memory + smart search + freshness + rl)."""
        from src.agents.openai_agent.tools import create_openai_tools
        tools = create_openai_tools(dal)
        assert len(tools) == 50

    def test_tools_have_names(self, dal):
        """All tools have names (FunctionTool objects)."""
        from src.agents.openai_agent.tools import create_openai_tools
        tools = create_openai_tools(dal)

        for tool in tools:
            # OpenAI SDK wraps functions as FunctionTool objects
            assert hasattr(tool, "name")
            assert tool.name.startswith("tool_")


# ============================================================
# OpenAI max_tokens Tests
# ============================================================

class TestOpenAIMaxTokens:
    def test_reasoning_effort_uses_model_max(self):
        """With reasoning effort != 'none', max_tokens = model max output."""
        from src.agents.openai_agent.agent import _build_agent
        agent = _build_agent("gpt-5.2", [], reasoning_effort="xhigh")
        assert agent.model_settings.max_tokens == 128000

    def test_reasoning_none_uses_config_max(self):
        """With reasoning effort == 'none', max_tokens = config.max_tokens."""
        from src.agents.openai_agent.agent import _build_agent
        agent = _build_agent("gpt-5.2", [], reasoning_effort="none", max_tokens=16384)
        assert agent.model_settings.max_tokens == 16384

    def test_model_max_output_lookup(self):
        """All GPT-5.x models map to 128K."""
        from src.agents.openai_agent.agent import _get_openai_max_output
        assert _get_openai_max_output("gpt-5.2") == 128000
        assert _get_openai_max_output("gpt-5.2-codex") == 128000
        # Unknown models get default 128K
        assert _get_openai_max_output("gpt-5-future") == 128000
        # Unknown model gets default
        assert _get_openai_max_output("gpt-4.1") == 128000


# ============================================================
# OpenAI _extract_tool_info Tests
# ============================================================

class TestExtractToolInfo:
    """Tests for _extract_tool_info() item type dispatch and fallback paths."""

    @pytest.fixture
    def pad(self, tmp_path):
        from src.agents.shared.scratchpad import Scratchpad
        return Scratchpad(query="test", provider="openai", model="test",
                          base_dir=tmp_path)

    @pytest.fixture
    def tracker(self):
        from src.agents.shared.token_tracker import TokenTracker
        return TokenTracker()

    def _make_result(self, items_per_response):
        """Build a mock Runner result with given output items per response."""
        from unittest.mock import MagicMock
        result = MagicMock()
        result.raw_responses = []
        for items in items_per_response:
            resp = MagicMock()
            resp.output = items
            result.raw_responses.append(resp)
        # Prevent record_openai_result from failing
        del result.usage
        return result

    def _make_call(self, name="get_ticker_news", args='{"ticker":"NVDA"}',
                   call_id="call_1", item_type="function_call"):
        from unittest.mock import MagicMock
        item = MagicMock()
        item.type = item_type
        item.name = name
        item.arguments = args
        item.call_id = call_id
        return item

    def _make_output(self, output="result_data", call_id="call_1",
                     item_type="function_call_output"):
        from unittest.mock import MagicMock
        item = MagicMock()
        item.type = item_type
        item.output = output
        item.call_id = call_id
        # Ensure no 'name' attr for output items to mimic real SDK
        del item.name
        del item.arguments
        return item

    def test_typed_call_and_output(self, pad, tracker):
        """Standard typed items: function_call + function_call_output."""
        from src.agents.openai_agent.agent import _extract_tool_info
        call = self._make_call()
        out = self._make_output()
        result = self._make_result([[call, out]])

        ext = _extract_tool_info(result, pad, tracker, "test")
        assert ext.tools_used == ["get_ticker_news"]
        assert len(ext.tool_calls_detail) == 1
        assert ext.tool_calls_detail[0]["result_preview"] == "result_data"
        assert "NVDA" in ext.tickers

    def test_untyped_fallback_with_call_id(self, pad, tracker):
        """Fallback: type=None, hasattr(output) + hasattr(call_id)."""
        from src.agents.openai_agent.agent import _extract_tool_info
        call = self._make_call(item_type=None)
        out = self._make_output(item_type=None)
        result = self._make_result([[call, out]])

        ext = _extract_tool_info(result, pad, tracker, "test")
        assert ext.tools_used == ["get_ticker_news"]
        assert ext.tool_calls_detail[0]["result_preview"] == "result_data"

    def test_untyped_output_without_call_id(self, pad, tracker):
        """Fallback: type=None, has output but NO call_id → positional fallback."""
        from src.agents.openai_agent.agent import _extract_tool_info
        from unittest.mock import MagicMock

        call = self._make_call(item_type=None)
        # Output item with no call_id
        out = MagicMock()
        out.type = None
        out.output = "orphan_result"
        del out.call_id
        del out.name
        del out.arguments
        result = self._make_result([[call, out]])

        ext = _extract_tool_info(result, pad, tracker, "test")
        assert ext.tools_used == ["get_ticker_news"]
        # Should still be captured via positional fallback
        assert ext.tool_calls_detail[0]["result_preview"] == "orphan_result"

    def test_call_id_mapping(self, pad, tracker):
        """Results matched to correct calls via call_id, not position."""
        from src.agents.openai_agent.agent import _extract_tool_info
        call_a = self._make_call(name="get_ticker_news", call_id="id_a",
                                 args='{"ticker":"AAPL"}')
        call_b = self._make_call(name="get_price_change", call_id="id_b",
                                 args='{"ticker":"MSFT","days":30}')
        # Results in reverse order
        out_b = self._make_output(output="price_result", call_id="id_b")
        out_a = self._make_output(output="news_result", call_id="id_a")
        result = self._make_result([[call_a, call_b, out_b, out_a]])

        ext = _extract_tool_info(result, pad, tracker, "test")
        assert ext.tools_used == ["get_ticker_news", "get_price_change"]
        assert ext.tool_calls_detail[0]["result_preview"] == "news_result"
        assert ext.tool_calls_detail[1]["result_preview"] == "price_result"
        assert ext.tickers == {"AAPL", "MSFT"}

    def test_tickers_from_list_param(self, pad, tracker):
        """Tickers extracted from list-type 'tickers' parameter."""
        from src.agents.openai_agent.agent import _extract_tool_info
        call = self._make_call(name="get_news_brief",
                               args='{"tickers":["NVDA","AMD","INTC"]}',
                               call_id="call_1")
        result = self._make_result([[call]])

        ext = _extract_tool_info(result, pad, tracker, "test")
        assert ext.tickers == {"NVDA", "AMD", "INTC"}

    def test_no_raw_responses(self, pad, tracker):
        """Result without raw_responses returns empty extraction."""
        from src.agents.openai_agent.agent import _extract_tool_info
        from unittest.mock import MagicMock
        result = MagicMock(spec=[])  # no raw_responses attr

        ext = _extract_tool_info(result, pad, tracker, "test")
        assert ext.tools_used == []
        assert ext.tool_calls_detail == []
        assert ext.tickers == set()

    def test_orphan_output_no_calls(self, pad, tracker):
        """Output item with no preceding call → skipped, unmatched counter."""
        from src.agents.openai_agent.agent import _extract_tool_info
        out = self._make_output(output="orphan", call_id="no_match")
        result = self._make_result([[out]])

        ext = _extract_tool_info(result, pad, tracker, "test")
        assert ext.tools_used == []
        assert ext.tool_calls_detail == []


# ============================================================
# API Endpoint Tests (without actual LLM calls)
# ============================================================

class TestQueryEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        app = create_app()
        with TestClient(app) as c:
            yield c

    def test_providers_endpoint(self, client):
        """GET /query/providers returns provider info."""
        r = client.get("/query/providers")
        assert r.status_code == 200
        data = r.json()
        assert "providers" in data
        assert "openai" in data["providers"]
        assert "anthropic" in data["providers"]

    def test_query_endpoint_bad_provider(self, client):
        """POST /query with unknown provider returns 400."""
        r = client.post(
            "/query",
            json={"question": "Test", "provider": "unknown"}
        )
        assert r.status_code == 400
        assert "Unknown provider" in r.json()["detail"]


# ============================================================
# Registry Integration Tests
# ============================================================

class TestRegistrySchemaExport:
    def test_to_openai_schema(self):
        """Registry exports OpenAI-compatible schemas."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        schemas = registry.to_openai_schema()

        assert len(schemas) == 49
        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]

    def test_to_anthropic_schema(self):
        """Registry exports Anthropic-compatible schemas."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        schemas = registry.to_anthropic_schema()

        assert len(schemas) == 49
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema