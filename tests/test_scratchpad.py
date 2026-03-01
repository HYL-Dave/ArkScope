"""Tests for Scratchpad + ChatHistory."""

import json
import time
from pathlib import Path

import pytest

from src.agents.shared.scratchpad import (
    ChatHistory,
    Scratchpad,
    _make_session_id,
    _safe_serialize,
    _try_parse_json,
    read_scratchpad,
)


# ── Helper utilities ──────────────────────────────────────────


class TestMakeSessionId:
    def test_deterministic(self):
        sid1 = _make_session_id("hello", 1000.0)
        sid2 = _make_session_id("hello", 1000.0)
        assert sid1 == sid2

    def test_different_inputs(self):
        sid1 = _make_session_id("hello", 1000.0)
        sid2 = _make_session_id("world", 1000.0)
        assert sid1 != sid2

    def test_length(self):
        sid = _make_session_id("test", 12345.0)
        assert len(sid) == 8

    def test_hex_chars(self):
        sid = _make_session_id("test", 12345.0)
        assert all(c in "0123456789abcdef" for c in sid)


class TestTryParseJson:
    def test_valid_json_dict(self):
        result = _try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_list(self):
        result = _try_parse_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_invalid_json_returns_string(self):
        result = _try_parse_json("not json at all")
        assert result == "not json at all"

    def test_empty_string(self):
        result = _try_parse_json("")
        assert result == ""

    def test_none_returns_none(self):
        result = _try_parse_json(None)
        assert result is None


class TestSafeSerialize:
    def test_primitives(self):
        assert _safe_serialize("hello") == "hello"
        assert _safe_serialize(42) == 42
        assert _safe_serialize(3.14) == 3.14
        assert _safe_serialize(True) is True
        assert _safe_serialize(None) is None

    def test_dict(self):
        assert _safe_serialize({"a": 1, "b": "c"}) == {"a": 1, "b": "c"}

    def test_list(self):
        assert _safe_serialize([1, "two", 3.0]) == [1, "two", 3.0]

    def test_non_serializable(self):
        result = _safe_serialize(Path("/tmp/test"))
        assert isinstance(result, str)
        assert "tmp" in result

    def test_nested(self):
        obj = {"path": Path("/foo"), "items": [Path("/bar"), 42]}
        result = _safe_serialize(obj)
        assert isinstance(result["path"], str)
        assert isinstance(result["items"][0], str)
        assert result["items"][1] == 42


# ── Scratchpad basics ─────────────────────────────────────────


class TestScratchpadInit:
    def test_creates_file(self, tmp_path):
        pad = Scratchpad("test query", "anthropic", "claude", base_dir=tmp_path)
        assert pad.filepath is not None
        assert pad.filepath.exists()
        assert pad.filepath.suffix == ".jsonl"
        pad.close()

    def test_filename_format(self, tmp_path):
        pad = Scratchpad("test", "anthropic", "claude", base_dir=tmp_path)
        name = pad.filepath.name
        # Format: YYYY-MM-DD-HHMMSS_{hash}.jsonl
        assert name.endswith(".jsonl")
        parts = name.replace(".jsonl", "").split("_")
        assert len(parts) == 2
        assert len(parts[1]) == 8  # session hash
        pad.close()

    def test_init_event_written(self, tmp_path):
        pad = Scratchpad("my query", "openai", "gpt-5.2", base_dir=tmp_path)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 1
        assert events[0]["type"] == "init"
        assert events[0]["seq"] == 1
        assert events[0]["data"]["query"] == "my query"
        assert events[0]["data"]["provider"] == "openai"
        assert events[0]["data"]["model"] == "gpt-5.2"
        assert "session" in events[0]
        assert "ts" in events[0]

    def test_session_id_set(self, tmp_path):
        pad = Scratchpad("test", "anthropic", "claude", base_dir=tmp_path)
        assert len(pad.session_id) == 8
        pad.close()

    def test_disabled(self, tmp_path):
        pad = Scratchpad("test", "anthropic", "claude", base_dir=tmp_path, enabled=False)
        assert pad.filepath is None
        assert not pad.enabled
        # Should not crash when logging
        pad.log_tool_call("some_tool", {"key": "value"})
        pad.log_tool_result("get_news", result_data="data")
        pad.log_final_answer("answer")
        pad.close()

    def test_creates_base_dir(self, tmp_path):
        deep_dir = tmp_path / "a" / "b" / "c"
        pad = Scratchpad("test", "anthropic", "claude", base_dir=deep_dir)
        assert deep_dir.exists()
        pad.close()


# ── Logging methods ───────────────────────────────────────────


class TestScratchpadLogging:
    def test_log_tool_call(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_call("get_news", {"ticker": "NVDA", "days": 30})
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2  # init + tool_call
        tc = events[1]
        assert tc["type"] == "tool_call"
        assert tc["seq"] == 2
        assert tc["data"]["tool"] == "get_news"
        assert tc["data"]["input"]["ticker"] == "NVDA"

    def test_log_tool_call_with_token_usage(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        usage = {"total_tokens": 1200, "input_tokens": 1000, "output_tokens": 200}
        pad.log_tool_call("get_news", {}, token_usage=usage)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert events[1]["token_usage"] == usage

    def test_log_tool_result_full_data(self, tmp_path):
        """tool_result stores full result data (not truncated)."""
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        full_result = '{"articles": [{"title": "NVDA surges"}], "count": 5}'
        pad.log_tool_result("get_news", result_data=full_result)
        pad.close()

        events = read_scratchpad(pad.filepath)
        tr = events[1]
        assert tr["type"] == "tool_result"
        assert tr["data"]["tool"] == "get_news"
        # Result is parsed as JSON object (not string)
        assert tr["data"]["result"]["count"] == 5
        assert tr["data"]["result_chars"] == len(full_result)

    def test_log_tool_result_with_args(self, tmp_path):
        """tool_result can include tool_input for combined event (like Dexter)."""
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_result(
            "get_news",
            result_data='{"count": 3}',
            tool_input={"ticker": "NVDA", "days": 7},
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        tr = events[1]
        assert tr["data"]["args"]["ticker"] == "NVDA"
        assert tr["data"]["result"]["count"] == 3

    def test_log_tool_result_non_json_string(self, tmp_path):
        """Non-JSON result is stored as plain string."""
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_result("tool", result_data="plain text result")
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert events[1]["data"]["result"] == "plain text result"

    def test_log_tool_result_large_data_not_truncated(self, tmp_path):
        """Full result is stored even for large data."""
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        large_result = json.dumps({"data": "x" * 5000})
        pad.log_tool_result("tool", result_data=large_result)
        pad.close()

        events = read_scratchpad(pad.filepath)
        # Should NOT be truncated
        assert "truncated" not in str(events[1]["data"]["result"])
        assert events[1]["data"]["result"]["data"] == "x" * 5000

    def test_log_final_answer_full(self, tmp_path):
        """Final answer stores full text (not truncated)."""
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        full_answer = "NVDA shows bullish momentum " * 50  # ~1400 chars
        usage = {"total_tokens": 5000}
        pad.log_final_answer(
            full_answer,
            token_usage=usage,
            tools_used=["get_news", "get_price"],
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        fa = events[1]
        assert fa["type"] == "final_answer"
        # Full answer preserved, not truncated
        assert fa["data"]["answer"] == full_answer
        assert fa["data"]["tools_used"] == ["get_news", "get_price"]
        assert fa["data"]["elapsed_seconds"] >= 0
        assert fa["token_usage"] == usage

    def test_log_max_turns(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_max_turns(tools_used=["tool_a", "tool_b"])
        pad.close()

        events = read_scratchpad(pad.filepath)
        mt = events[1]
        assert mt["type"] == "max_turns"
        assert mt["data"]["tools_used"] == ["tool_a", "tool_b"]
        assert mt["data"]["elapsed_seconds"] >= 0


# ── Full session simulation ───────────────────────────────────


class TestScratchpadSession:
    def test_full_session_combined_events(self, tmp_path):
        """Simulate session using combined tool_result events (Dexter-style)."""
        pad = Scratchpad("分析 NVDA", "anthropic", "claude-sonnet-4", base_dir=tmp_path)

        pad.log_tool_result(
            "get_ticker_news",
            result_data='{"articles": [{"title": "NVDA up"}], "count": 3}',
            tool_input={"ticker": "NVDA", "days": 7},
        )
        pad.log_tool_result(
            "get_price_history",
            result_data='{"rows": 22, "data": []}',
            tool_input={"ticker": "NVDA", "period": "1mo"},
        )
        pad.log_final_answer(
            "NVDA 近期表現強勁...",
            token_usage={"total_tokens": 8000},
            tools_used=["get_ticker_news", "get_price_history"],
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 4  # init + 2*tool_result + final
        types = [e["type"] for e in events]
        assert types == ["init", "tool_result", "tool_result", "final_answer"]
        # Sequential numbering
        assert [e["seq"] for e in events] == [1, 2, 3, 4]
        # All same session
        assert len(set(e["session"] for e in events)) == 1
        # Full results preserved
        assert events[1]["data"]["result"]["count"] == 3
        assert events[1]["data"]["args"]["ticker"] == "NVDA"

    def test_context_manager(self, tmp_path):
        with Scratchpad("test", "openai", "gpt", base_dir=tmp_path) as pad:
            pad.log_tool_call("tool", {"a": 1})
            filepath = pad.filepath

        # File should be closed after context manager
        events = read_scratchpad(filepath)
        assert len(events) == 2

    def test_unicode_content(self, tmp_path):
        pad = Scratchpad("分析台積電走勢", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_result(
            "get_news",
            result_data='{"articles": [{"title": "台積電營收創新高"}]}',
            tool_input={"ticker": "TSM", "query": "台積電"},
        )
        pad.log_final_answer("台積電近期營收創新高，AI 需求持續推升...")
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert events[0]["data"]["query"] == "分析台積電走勢"
        assert "台積電" in events[2]["data"]["answer"]

    def test_non_serializable_input(self, tmp_path):
        """Tool input with non-JSON-safe types should be handled gracefully."""
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_call("tool", {"path": Path("/tmp/data"), "date": object()})
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2  # Should not crash


# ── ChatHistory ───────────────────────────────────────────────


class TestChatHistory:
    def test_append_and_read(self, tmp_path):
        path = tmp_path / "chat.jsonl"
        history = ChatHistory(path=path)
        history.append(
            user_message="分析 NVDA",
            agent_response="NVDA 近期表現強勁...",
            provider="anthropic",
            model="claude-sonnet-4",
            tools_used=["get_news"],
            elapsed_seconds=12.5,
        )

        entries = ChatHistory.read_recent(path=path)
        assert len(entries) == 1
        e = entries[0]
        assert e["userMessage"] == "分析 NVDA"
        assert e["agentResponse"] == "NVDA 近期表現強勁..."
        assert e["provider"] == "anthropic"
        assert e["model"] == "claude-sonnet-4"
        assert e["tools_used"] == ["get_news"]
        assert e["elapsed_seconds"] == 12.5
        assert "timestamp" in e

    def test_multiple_entries(self, tmp_path):
        path = tmp_path / "chat.jsonl"
        history = ChatHistory(path=path)
        for i in range(5):
            history.append(
                user_message=f"Question {i}",
                agent_response=f"Answer {i}",
                provider="openai",
                model="gpt-5.2",
            )

        entries = ChatHistory.read_recent(path=path)
        assert len(entries) == 5
        assert entries[0]["userMessage"] == "Question 0"
        assert entries[4]["userMessage"] == "Question 4"

    def test_read_recent_limit(self, tmp_path):
        path = tmp_path / "chat.jsonl"
        history = ChatHistory(path=path)
        for i in range(20):
            history.append(
                user_message=f"Q{i}",
                agent_response=f"A{i}",
                provider="anthropic",
                model="claude",
            )

        entries = ChatHistory.read_recent(path=path, limit=5)
        assert len(entries) == 5
        # Should be the LAST 5
        assert entries[0]["userMessage"] == "Q15"
        assert entries[4]["userMessage"] == "Q19"

    def test_read_empty_file(self, tmp_path):
        path = tmp_path / "chat.jsonl"
        path.write_text("")
        entries = ChatHistory.read_recent(path=path)
        assert entries == []

    def test_read_nonexistent_file(self, tmp_path):
        path = tmp_path / "does_not_exist.jsonl"
        entries = ChatHistory.read_recent(path=path)
        assert entries == []

    def test_optional_fields_omitted(self, tmp_path):
        path = tmp_path / "chat.jsonl"
        history = ChatHistory(path=path)
        history.append(
            user_message="Hello",
            agent_response="Hi",
            provider="anthropic",
            model="claude",
            # No tools_used, no elapsed_seconds
        )

        entries = ChatHistory.read_recent(path=path)
        assert "tools_used" not in entries[0]
        assert "elapsed_seconds" not in entries[0]

    def test_creates_parent_dir(self, tmp_path):
        path = tmp_path / "a" / "b" / "chat.jsonl"
        history = ChatHistory(path=path)
        history.append(
            user_message="test",
            agent_response="ok",
            provider="openai",
            model="gpt",
        )
        assert path.exists()

    def test_unicode_content(self, tmp_path):
        path = tmp_path / "chat.jsonl"
        history = ChatHistory(path=path)
        history.append(
            user_message="台積電走勢如何？",
            agent_response="台積電近期表現強勁",
            provider="anthropic",
            model="claude",
        )
        entries = ChatHistory.read_recent(path=path)
        assert entries[0]["userMessage"] == "台積電走勢如何？"


# ── read_scratchpad ───────────────────────────────────────────


class TestReadScratchpad:
    def test_read_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        assert read_scratchpad(f) == []

    def test_read_with_blank_lines(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text('{"a": 1}\n\n{"b": 2}\n\n')
        events = read_scratchpad(f)
        assert len(events) == 2


# ── repr ──────────────────────────────────────────────────────


# ── Error logging (Item G: fault tolerance) ─────────────────


class TestScratchpadLogError:
    def test_log_error_basic(self, tmp_path):
        """log_error writes structured error event to scratchpad."""
        pad = Scratchpad("test", "anthropic", "claude-opus-4-6", base_dir=tmp_path)
        pad.log_error(
            error_type="APIError",
            message="context_length_exceeded: max 200000 tokens",
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2  # init + error
        err = events[1]
        assert err["type"] == "error"
        assert err["data"]["error_type"] == "APIError"
        assert "context_length_exceeded" in err["data"]["message"]
        assert err["data"]["elapsed_seconds"] >= 0
        assert err["data"]["tools_used"] == []

    def test_log_error_with_full_context(self, tmp_path):
        """log_error captures turn, tools_used, traceback, token_usage."""
        pad = Scratchpad("分析 NVDA", "openai", "gpt-5.2", base_dir=tmp_path)
        pad.log_error(
            error_type="ContextLengthExceeded",
            message="max tokens exceeded",
            traceback_str="Traceback (most recent call last):\n  File ...\nError",
            turn=5,
            tools_used=["get_ticker_news", "get_price_history"],
            token_usage={"total_tokens": 150000},
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        err = events[1]
        assert err["data"]["turn"] == 5
        assert err["data"]["tools_used"] == ["get_ticker_news", "get_price_history"]
        assert "Traceback" in err["data"]["traceback"]
        assert err["token_usage"] == {"total_tokens": 150000}

    def test_log_error_message_truncated(self, tmp_path):
        """Long error messages are truncated to 2000 chars."""
        pad = Scratchpad("test", "anthropic", "claude", base_dir=tmp_path)
        long_msg = "x" * 5000
        pad.log_error(error_type="RuntimeError", message=long_msg)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events[1]["data"]["message"]) <= 2000

    def test_log_error_traceback_truncated(self, tmp_path):
        """Long tracebacks are truncated to 5000 chars."""
        pad = Scratchpad("test", "anthropic", "claude", base_dir=tmp_path)
        long_tb = "frame\n" * 2000
        pad.log_error(error_type="Error", message="boom", traceback_str=long_tb)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events[1]["data"]["traceback"]) <= 5000

    def test_log_error_disabled(self, tmp_path):
        """log_error is a no-op when scratchpad is disabled."""
        pad = Scratchpad("test", "anthropic", "claude", base_dir=tmp_path, enabled=False)
        pad.log_error(error_type="Error", message="should not crash")
        pad.close()
        # No file created, no error — just silently ignored

    def test_error_after_tool_results(self, tmp_path):
        """Full session: init → tool_result → tool_result → error."""
        pad = Scratchpad("分析 TSLA", "anthropic", "claude-opus-4-6", base_dir=tmp_path)
        pad.log_tool_result("get_ticker_news", result_data='{"count": 5}',
                            tool_input={"ticker": "TSLA"})
        pad.log_tool_result("get_price_history", result_data='{"rows": 10}',
                            tool_input={"ticker": "TSLA"})
        pad.log_error(
            error_type="BadRequestError",
            message="context_length_exceeded",
            turn=3,
            tools_used=["get_ticker_news", "get_price_history"],
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        types = [e["type"] for e in events]
        assert types == ["init", "tool_result", "tool_result", "error"]
        assert [e["seq"] for e in events] == [1, 2, 3, 4]
        # Error event has the tool state at failure
        assert events[3]["data"]["tools_used"] == ["get_ticker_news", "get_price_history"]
        assert events[3]["data"]["turn"] == 3


# ── New event types (Phase: Scratchpad Enhancement) ──────────


class TestScratchpadNewEvents:
    def test_log_thinking(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude-opus-4-6", base_dir=tmp_path)
        pad.log_thinking(preview="Let me analyze...", full_length=2500)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2  # init + thinking
        ev = events[1]
        assert ev["type"] == "thinking"
        assert ev["data"]["preview"] == "Let me analyze..."
        assert ev["data"]["full_length"] == 2500

    def test_log_thinking_preview_truncated(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        long_preview = "x" * 1000
        pad.log_thinking(preview=long_preview)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events[1]["data"]["preview"]) <= 500

    def test_log_pause_turn(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_pause_turn()
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2
        assert events[1]["type"] == "pause_turn"

    def test_log_compaction(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_compaction(source="server")
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2
        assert events[1]["type"] == "compaction"
        assert events[1]["data"]["source"] == "server"

    def test_log_retry(self, tmp_path):
        pad = Scratchpad("q", "openai", "gpt-5.2", base_dir=tmp_path)
        pad.log_retry(
            attempt=1, error_message="No tool output found",
            max_retries=2, retryable=True, reason_code="no_tool_output",
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2
        ev = events[1]
        assert ev["type"] == "retry"
        assert ev["data"]["attempt"] == 1
        assert ev["data"]["max_retries"] == 2
        assert ev["data"]["retryable"] is True
        assert ev["data"]["reason_code"] == "no_tool_output"
        assert "No tool output" in ev["data"]["error"]

    def test_log_retry_error_truncated(self, tmp_path):
        pad = Scratchpad("q", "openai", "gpt", base_dir=tmp_path)
        pad.log_retry(attempt=1, error_message="x" * 1000)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events[1]["data"]["error"]) <= 500

    def test_full_session_with_new_events(self, tmp_path):
        """Session with thinking + retry + tool + final."""
        pad = Scratchpad("test", "anthropic", "claude-opus-4-6", base_dir=tmp_path)
        pad.log_thinking(preview="Analyzing...", full_length=800)
        pad.log_tool_result("get_news", result_data='{"count": 5}')
        pad.log_compaction(source="server")
        pad.log_pause_turn()
        pad.log_retry(attempt=1, error_message="transient error")
        pad.log_final_answer("Done.", tools_used=["get_news"])
        pad.close()

        events = read_scratchpad(pad.filepath)
        types = [e["type"] for e in events]
        assert types == [
            "init", "thinking", "tool_result", "compaction",
            "pause_turn", "retry", "final_answer",
        ]
        assert [e["seq"] for e in events] == [1, 2, 3, 4, 5, 6, 7]


class TestScratchpadRepr:
    def test_repr(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_call("tool", {})
        r = repr(pad)
        assert "Scratchpad" in r
        assert pad.session_id in r
        assert "events=2" in r
        pad.close()