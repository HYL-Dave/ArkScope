"""Tests for Scratchpad (Phase 2 of agent evolution)."""

import json
import time
from pathlib import Path

import pytest

from src.agents.shared.scratchpad import (
    Scratchpad,
    _make_session_id,
    _safe_serialize,
    _truncate,
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


class TestTruncate:
    def test_short_text(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length(self):
        assert _truncate("12345", 5) == "12345"

    def test_long_text(self):
        result = _truncate("abcdefghij", 5)
        assert result.startswith("abcde")
        assert "5 chars truncated" in result

    def test_default_max(self):
        short = "x" * 500
        assert _truncate(short) == short
        long = "x" * 600
        assert "100 chars truncated" in _truncate(long)


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

    def test_log_tool_result(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_result("get_news", result_summary="5 articles found", chars=2400)
        pad.close()

        events = read_scratchpad(pad.filepath)
        tr = events[1]
        assert tr["type"] == "tool_result"
        assert tr["data"]["tool"] == "get_news"
        assert tr["data"]["summary"] == "5 articles found"
        assert tr["data"]["result_chars"] == 2400

    def test_log_tool_result_truncates_summary(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        long_summary = "x" * 500
        pad.log_tool_result("tool", result_summary=long_summary, chars=500)
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events[1]["data"]["summary"]) < 500
        assert "truncated" in events[1]["data"]["summary"]

    def test_log_final_answer(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        usage = {"total_tokens": 5000}
        pad.log_final_answer(
            "NVDA shows bullish momentum",
            token_usage=usage,
            tools_used=["get_news", "get_price"],
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        fa = events[1]
        assert fa["type"] == "final_answer"
        assert fa["data"]["answer_preview"] == "NVDA shows bullish momentum"
        assert fa["data"]["answer_chars"] == len("NVDA shows bullish momentum")
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
    def test_full_session(self, tmp_path):
        """Simulate a complete agent session with multiple tool calls."""
        pad = Scratchpad("分析 NVDA", "anthropic", "claude-sonnet-4", base_dir=tmp_path)

        pad.log_tool_call("get_ticker_news", {"ticker": "NVDA", "days": 7})
        pad.log_tool_result("get_ticker_news", result_summary="3 articles", chars=1500)

        pad.log_tool_call("get_price_history", {"ticker": "NVDA", "period": "1mo"})
        pad.log_tool_result("get_price_history", result_summary="22 rows", chars=800)

        pad.log_final_answer(
            "NVDA 近期表現強勁...",
            token_usage={"total_tokens": 8000},
            tools_used=["get_ticker_news", "get_price_history"],
        )
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 6  # init + 2*(call+result) + final
        types = [e["type"] for e in events]
        assert types == [
            "init", "tool_call", "tool_result",
            "tool_call", "tool_result", "final_answer",
        ]
        # Sequential numbering
        assert [e["seq"] for e in events] == [1, 2, 3, 4, 5, 6]
        # All same session
        assert len(set(e["session"] for e in events)) == 1

    def test_context_manager(self, tmp_path):
        with Scratchpad("test", "openai", "gpt", base_dir=tmp_path) as pad:
            pad.log_tool_call("tool", {"a": 1})
            filepath = pad.filepath

        # File should be closed after context manager
        events = read_scratchpad(filepath)
        assert len(events) == 2

    def test_unicode_content(self, tmp_path):
        pad = Scratchpad("分析台積電走勢", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_call("get_news", {"ticker": "TSM", "query": "台積電"})
        pad.log_final_answer("台積電近期營收創新高，AI 需求持續推升...")
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert events[0]["data"]["query"] == "分析台積電走勢"
        assert "台積電" in events[2]["data"]["answer_preview"]

    def test_non_serializable_input(self, tmp_path):
        """Tool input with non-JSON-safe types should be handled gracefully."""
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_call("tool", {"path": Path("/tmp/data"), "date": object()})
        pad.close()

        events = read_scratchpad(pad.filepath)
        assert len(events) == 2  # Should not crash


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


class TestScratchpadRepr:
    def test_repr(self, tmp_path):
        pad = Scratchpad("q", "anthropic", "claude", base_dir=tmp_path)
        pad.log_tool_call("tool", {})
        r = repr(pad)
        assert "Scratchpad" in r
        assert pad.session_id in r
        assert "events=2" in r
        pad.close()