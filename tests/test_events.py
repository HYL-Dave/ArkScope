"""Tests for AgentEvent streaming (Phase 4 of agent evolution)."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.shared.events import AgentEvent, EventType


# ── EventType tests ───────────────────────────────────────────


class TestEventType:
    def test_all_types_defined(self):
        expected = {"thinking", "thinking_content", "text", "tool_start", "tool_end", "error", "done"}
        assert {e.value for e in EventType} == expected

    def test_thinking_content_type(self):
        assert EventType.thinking_content == "thinking_content"
        assert EventType("thinking_content") is EventType.thinking_content

    def test_str_enum(self):
        assert EventType.thinking == "thinking"
        assert EventType.done == "done"

    def test_value_access(self):
        assert EventType("tool_start") is EventType.tool_start


# ── AgentEvent tests ──────────────────────────────────────────


class TestAgentEvent:
    def test_basic_construction(self):
        event = AgentEvent(type=EventType.thinking, data={"turn": 1})
        assert event.type == EventType.thinking
        assert event.data == {"turn": 1}
        assert isinstance(event.timestamp, float)

    def test_default_data(self):
        event = AgentEvent(type=EventType.done)
        assert event.data == {}

    def test_to_sse_format(self):
        event = AgentEvent(type=EventType.done, data={"answer": "hello"})
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        payload = json.loads(sse[len("data: "):].strip())
        assert payload["type"] == "done"
        assert payload["data"]["answer"] == "hello"

    def test_to_sse_unicode(self):
        event = AgentEvent(type=EventType.text, data={"content": "NVDA 分析"})
        sse = event.to_sse()
        # ensure_ascii=False preserves unicode
        assert "NVDA 分析" in sse

    def test_to_dict(self):
        event = AgentEvent(type=EventType.tool_start, data={"tool": "get_ticker_news"})
        d = event.to_dict()
        assert d["type"] == "tool_start"
        assert d["data"]["tool"] == "get_ticker_news"
        assert "timestamp" in d


# ── Anthropic stream tests ────────────────────────────────────


def _make_mock_response(stop_reason="end_turn", content_blocks=None):
    """Create a mock Anthropic response."""
    response = MagicMock()
    response.stop_reason = stop_reason

    if content_blocks is None:
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Final answer here."
        content_blocks = [text_block]

    response.content = content_blocks

    # Mock usage for TokenTracker
    response.usage = MagicMock()
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    response.model = "claude-opus-4-6"

    return response


def _make_tool_use_block(tool_name, tool_input, tool_id="tool_123"):
    """Create a mock tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    # Ensure hasattr(block, "text") returns False for tool blocks
    del block.text
    return block


def _make_stream_cm(response):
    """Create a mock context manager for client.messages.stream().

    Usage: client.messages.stream.return_value = _make_stream_cm(response)
    Simulates: with client.messages.stream(...) as s: s.get_final_message() → response
    """
    stream = MagicMock()
    stream.get_final_message.return_value = response
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=stream)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestAnthropicStream:
    """Test event sequence from run_query_stream (Anthropic)."""

    @pytest.fixture
    def mock_deps(self):
        """Patch Anthropic client, tools, and DAL."""
        with patch("anthropic.Anthropic") as mock_cls, \
             patch("src.agents.anthropic_agent.tools.get_anthropic_tools") as mock_tools, \
             patch("src.agents.anthropic_agent.tools.execute_tool") as mock_exec, \
             patch("src.agents.config.get_agent_config") as mock_config:

            # Config
            config = MagicMock()
            config.anthropic_model = "claude-opus-4-6"
            config.max_tokens = 16384
            config.max_tool_calls = 20
            config.context_threshold_ratio = 0.7
            config.context_keep_recent_turns = 2
            config.context_preview_chars = 200
            config.anthropic_effort = None
            config.anthropic_thinking = False
            mock_config.return_value = config

            # Tools
            mock_tools.return_value = []

            # Client
            client = MagicMock()
            mock_cls.return_value = client

            # Execute tool
            mock_exec.return_value = '{"result": "ok"}'

            yield {
                "client": client,
                "mock_tools": mock_tools,
                "mock_exec": mock_exec,
                "config": config,
            }

    def _collect_events(self, stream_coro):
        """Run async generator and collect all events."""
        async def _gather():
            events = []
            async for event in stream_coro:
                events.append(event)
            return events
        return asyncio.run(_gather())

    def test_no_tool_calls(self, mock_deps):
        """Direct answer: thinking → done."""
        mock_deps["client"].messages.stream.return_value = _make_stream_cm(_make_mock_response())

        from src.agents.anthropic_agent.agent import run_query_stream
        events = self._collect_events(
            run_query_stream("What is NVDA?", dal=MagicMock())
        )

        types = [e.type for e in events]
        assert types == [EventType.thinking, EventType.done]
        assert events[-1].data["answer"] == "Final answer here."
        assert events[-1].data["provider"] == "anthropic"

    def test_one_tool_call(self, mock_deps):
        """One tool call: thinking → text → tool_start → tool_end → thinking → done."""
        tool_block = _make_tool_use_block("get_ticker_news", {"ticker": "NVDA"})
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Let me check the news."

        # First call: tool_use response
        tool_response = _make_mock_response(
            stop_reason="tool_use",
            content_blocks=[text_block, tool_block],
        )
        # Second call: final answer
        final_response = _make_mock_response()

        mock_deps["client"].messages.stream.side_effect = [_make_stream_cm(tool_response), _make_stream_cm(final_response)]

        from src.agents.anthropic_agent.agent import run_query_stream
        events = self._collect_events(
            run_query_stream("NVDA news?", dal=MagicMock())
        )

        types = [e.type for e in events]
        assert types == [
            EventType.thinking,     # Turn 1 API call
            EventType.text,         # "Let me check the news."
            EventType.tool_start,   # get_ticker_news starts
            EventType.tool_end,     # get_ticker_news ends
            EventType.thinking,     # Turn 2 API call
            EventType.done,         # Final answer
        ]

        # Verify tool events have correct data
        tool_start = next(e for e in events if e.type == EventType.tool_start)
        assert tool_start.data["tool"] == "get_ticker_news"
        assert tool_start.data["input"] == {"ticker": "NVDA"}

        tool_end = next(e for e in events if e.type == EventType.tool_end)
        assert tool_end.data["tool"] == "get_ticker_news"
        assert "chars" in tool_end.data

    def test_done_event_has_tools_used(self, mock_deps):
        """Done event includes tools_used list."""
        tool_block = _make_tool_use_block("get_price_change", {"ticker": "AMD", "days": 7})

        tool_response = _make_mock_response(
            stop_reason="tool_use",
            content_blocks=[tool_block],
        )
        final_response = _make_mock_response()
        mock_deps["client"].messages.stream.side_effect = [_make_stream_cm(tool_response), _make_stream_cm(final_response)]

        from src.agents.anthropic_agent.agent import run_query_stream
        events = self._collect_events(
            run_query_stream("AMD price?", dal=MagicMock())
        )

        done_event = next(e for e in events if e.type == EventType.done)
        assert "get_price_change" in done_event.data["tools_used"]
        assert "token_usage" in done_event.data

    def test_max_turns_yields_done(self, mock_deps):
        """Max turns still yields a done event."""
        mock_deps["config"].max_tool_calls = 1

        tool_block = _make_tool_use_block("get_ticker_news", {"ticker": "NVDA"})
        tool_response = _make_mock_response(
            stop_reason="tool_use",
            content_blocks=[tool_block],
        )
        mock_deps["client"].messages.stream.return_value = _make_stream_cm(tool_response)

        from src.agents.anthropic_agent.agent import run_query_stream
        events = self._collect_events(
            run_query_stream("NVDA?", dal=MagicMock())
        )

        types = [e.type for e in events]
        assert EventType.done in types
        done_event = next(e for e in events if e.type == EventType.done)
        assert "Maximum tool calls" in done_event.data["answer"]

    def test_with_thinking_blocks(self, mock_deps):
        """Response with thinking blocks emits thinking_content events."""
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = "Let me analyze NVDA stock..."
        del thinking_block.text  # thinking blocks don't have .text

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "NVDA is doing well."

        response = _make_mock_response(
            stop_reason="end_turn",
            content_blocks=[thinking_block, text_block],
        )
        mock_deps["client"].messages.stream.return_value = _make_stream_cm(response)

        from src.agents.anthropic_agent.agent import run_query_stream
        events = self._collect_events(
            run_query_stream("NVDA?", dal=MagicMock())
        )

        types = [e.type for e in events]
        assert EventType.thinking_content in types
        tc_event = next(e for e in events if e.type == EventType.thinking_content)
        assert tc_event.data["thinking"] == "Let me analyze NVDA stock..."

    def test_effort_kwarg_passed(self, mock_deps):
        """Effort override is passed to API as output_config."""
        mock_deps["client"].messages.stream.return_value = _make_stream_cm(_make_mock_response())

        from src.agents.anthropic_agent.agent import run_query_stream
        # Pass model directly — Opus 4.6 supports effort
        self._collect_events(
            run_query_stream("Test", model="claude-opus-4-6", dal=MagicMock(), effort="medium")
        )

        call_kwargs = mock_deps["client"].messages.stream.call_args
        assert call_kwargs.kwargs.get("output_config") == {"effort": "medium"}

    def test_thinking_kwarg_adaptive(self, mock_deps):
        """Thinking override with Opus 4.6 uses adaptive mode + model max output."""
        mock_deps["client"].messages.stream.return_value = _make_stream_cm(_make_mock_response())

        from src.agents.anthropic_agent.agent import run_query_stream
        # Pass model directly — Opus 4.6 uses adaptive thinking
        self._collect_events(
            run_query_stream("Test", model="claude-opus-4-6", dal=MagicMock(), thinking=True)
        )

        call_kwargs = mock_deps["client"].messages.stream.call_args
        assert call_kwargs.kwargs.get("thinking") == {"type": "adaptive"}
        # max_tokens = Opus 4.6 max output
        assert call_kwargs.kwargs.get("max_tokens") == 128000

    def test_thinking_kwarg_enabled_for_non_opus(self, mock_deps):
        """Thinking override with non-Opus model uses enabled + auto-derived budget."""
        mock_deps["client"].messages.stream.return_value = _make_stream_cm(_make_mock_response())

        from src.agents.anthropic_agent.agent import run_query_stream
        # Non-Opus model: fallback max_output=64000, budget = 64000 - 16384 = 47616
        self._collect_events(
            run_query_stream(
                "Test", model="claude-sonnet-5-20260501",
                dal=MagicMock(), thinking=True,
            )
        )

        call_kwargs = mock_deps["client"].messages.stream.call_args
        thinking_param = call_kwargs.kwargs.get("thinking")
        assert thinking_param["type"] == "enabled"
        # budget = model_max_output (64000 fallback) - config.max_tokens (16384) = 47616
        assert thinking_param["budget_tokens"] == 64000 - 16384
        # max_tokens = model max output (fallback)
        assert call_kwargs.kwargs.get("max_tokens") == 64000

    def test_no_effort_for_unsupported_model(self, mock_deps):
        """Effort is not sent for models that don't support it."""
        mock_deps["client"].messages.stream.return_value = _make_stream_cm(_make_mock_response())

        from src.agents.anthropic_agent.agent import run_query_stream
        # Non-Opus model doesn't support effort
        self._collect_events(
            run_query_stream(
                "Test", model="claude-sonnet-5-20260501",
                dal=MagicMock(), effort="medium",
            )
        )

        call_kwargs = mock_deps["client"].messages.stream.call_args
        assert "output_config" not in call_kwargs.kwargs


# ── run_query backward compatibility ──────────────────────────


class TestRunQueryBackwardCompat:
    """Verify run_query() still returns a dict (backward compatible)."""

    def test_run_query_returns_dict(self):
        """run_query() should return a dict, not an async generator."""
        with patch("anthropic.Anthropic") as mock_cls, \
             patch("src.agents.anthropic_agent.tools.get_anthropic_tools") as mock_tools, \
             patch("src.agents.config.get_agent_config") as mock_config:

            config = MagicMock()
            config.anthropic_model = "claude-opus-4-6"
            config.max_tokens = 16384
            config.max_tool_calls = 20
            config.context_threshold_ratio = 0.7
            config.context_keep_recent_turns = 2
            config.context_preview_chars = 200
            config.anthropic_effort = None
            config.anthropic_thinking = False
            mock_config.return_value = config
            mock_tools.return_value = []

            client = MagicMock()
            mock_cls.return_value = client
            client.messages.stream.return_value = _make_stream_cm(_make_mock_response())

            from src.agents.anthropic_agent.agent import run_query
            result = run_query("Test question", dal=MagicMock())

            assert isinstance(result, dict)
            assert "answer" in result
            assert "tools_used" in result
            assert "provider" in result
            assert result["provider"] == "anthropic"


# ── SSE endpoint test ─────────────────────────────────────────


class TestSSEEndpoint:
    """Test the /query/stream endpoint returns SSE content-type."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        app = create_app()
        with TestClient(app) as c:
            yield c

    def test_stream_bad_provider(self, client):
        """POST /query/stream with unknown provider returns error event."""
        r = client.post(
            "/query/stream",
            json={"question": "Test", "provider": "unknown"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        # Should contain an error event
        body = r.text
        assert '"type": "error"' in body