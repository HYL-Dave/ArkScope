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
import pytest

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
        assert config.anthropic_model == "claude-sonnet-4-5-20250929"
        assert config.reasoning_effort in ("none", "minimal", "low", "medium", "high", "xhigh")
        assert config.max_tool_calls > 0
        assert config.max_tokens > 0

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
        """All 17 tools are defined."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        assert len(tools) == 17

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

        data = json.loads(result)
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

        data = json.loads(result)
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

        data = json.loads(result)
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
        """Creates 17 tools."""
        from src.agents.openai_agent.tools import create_openai_tools
        tools = create_openai_tools(dal)
        assert len(tools) == 17

    def test_tools_have_names(self, dal):
        """All tools have names (FunctionTool objects)."""
        from src.agents.openai_agent.tools import create_openai_tools
        tools = create_openai_tools(dal)

        for tool in tools:
            # OpenAI SDK wraps functions as FunctionTool objects
            assert hasattr(tool, "name")
            assert tool.name.startswith("tool_")


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

        assert len(schemas) == 17
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

        assert len(schemas) == 17
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema