"""
Tests for Anthropic prompt caching helpers.

Verifies _prepare_cached_system() and _prepare_cached_tools() produce
correct cache_control structures for Anthropic API.
"""

import pytest

from src.agents.anthropic_agent.agent import (
    _prepare_cached_system,
    _prepare_cached_tools,
)


# ============================================================
# _prepare_cached_system Tests
# ============================================================

class TestPrepareCachedSystem:
    def test_returns_list(self):
        result = _prepare_cached_system("You are a helpful assistant.")
        assert isinstance(result, list)

    def test_single_block(self):
        result = _prepare_cached_system("System prompt text.")
        assert len(result) == 1

    def test_block_type_is_text(self):
        result = _prepare_cached_system("Test prompt.")
        assert result[0]["type"] == "text"

    def test_block_contains_text(self):
        prompt = "You are a senior financial analyst."
        result = _prepare_cached_system(prompt)
        assert result[0]["text"] == prompt

    def test_block_has_cache_control(self):
        result = _prepare_cached_system("Test.")
        assert "cache_control" in result[0]
        assert result[0]["cache_control"] == {"type": "ephemeral"}

    def test_empty_string_still_creates_block(self):
        result = _prepare_cached_system("")
        assert len(result) == 1
        assert result[0]["text"] == ""
        assert "cache_control" in result[0]

    def test_multiline_prompt(self):
        prompt = "Line 1\nLine 2\nLine 3"
        result = _prepare_cached_system(prompt)
        assert result[0]["text"] == prompt


# ============================================================
# _prepare_cached_tools Tests
# ============================================================

class TestPrepareCachedTools:
    def test_empty_list_returns_empty(self):
        result = _prepare_cached_tools([])
        assert result == []

    def test_single_tool_gets_cache_control(self):
        tools = [{"name": "tool_a", "description": "A tool", "input_schema": {}}]
        result = _prepare_cached_tools(tools)
        assert len(result) == 1
        assert result[0]["cache_control"] == {"type": "ephemeral"}

    def test_last_tool_gets_cache_control(self):
        tools = [
            {"name": "tool_a", "description": "First", "input_schema": {}},
            {"name": "tool_b", "description": "Second", "input_schema": {}},
            {"name": "tool_c", "description": "Third", "input_schema": {}},
        ]
        result = _prepare_cached_tools(tools)
        assert "cache_control" not in result[0]
        assert "cache_control" not in result[1]
        assert result[2]["cache_control"] == {"type": "ephemeral"}

    def test_does_not_mutate_original(self):
        tools = [
            {"name": "tool_a", "description": "First", "input_schema": {}},
            {"name": "tool_b", "description": "Last", "input_schema": {}},
        ]
        result = _prepare_cached_tools(tools)
        # Original should not have cache_control
        assert "cache_control" not in tools[-1]
        # Result should have it
        assert "cache_control" in result[-1]

    def test_preserves_tool_fields(self):
        tools = [{
            "name": "get_ticker_news",
            "description": "Get news",
            "input_schema": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
            },
        }]
        result = _prepare_cached_tools(tools)
        assert result[0]["name"] == "get_ticker_news"
        assert result[0]["description"] == "Get news"
        assert "input_schema" in result[0]

    def test_server_tool_gets_cache_control(self):
        """Server tools (like web_search) should also get cache_control."""
        tools = [
            {"name": "regular_tool", "description": "A", "input_schema": {}},
            {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
        ]
        result = _prepare_cached_tools(tools)
        assert "cache_control" not in result[0]
        assert result[1]["cache_control"] == {"type": "ephemeral"}

    def test_many_tools(self):
        """Verify with a realistic number of tools."""
        tools = [
            {"name": f"tool_{i}", "description": f"Tool {i}", "input_schema": {}}
            for i in range(27)
        ]
        result = _prepare_cached_tools(tools)
        assert len(result) == 27
        # Only last has cache_control
        for i in range(26):
            assert "cache_control" not in result[i]
        assert result[26]["cache_control"] == {"type": "ephemeral"}