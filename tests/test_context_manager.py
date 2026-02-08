"""Tests for ContextManager (Phase 3 of agent evolution)."""

from types import SimpleNamespace

import pytest

from src.agents.shared.context_manager import (
    ContextManager,
    _build_compact_summary,
    _compact_value,
    _extract_tool_info,
    _COMPACT_MARKER,
    get_model_context_limit,
)
from src.agents.shared.token_tracker import TokenTracker


# ── Helpers ───────────────────────────────────────────────────


def _make_tool_use_block(tool_id, name, tool_input):
    """Create a mock Anthropic ToolUseBlock."""
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)


def _make_text_block(text):
    """Create a mock Anthropic TextBlock."""
    return SimpleNamespace(type="text", text=text)


def _make_messages(num_turns, result_size=500):
    """
    Build a realistic Anthropic messages list with `num_turns` tool call turns.

    Structure:
      [0] user question
      [1] assistant (turn 1: text + tool_use)
      [2] user/tool_results (turn 1)
      [3] assistant (turn 2)
      [4] user/tool_results (turn 2)
      ...
    """
    messages = [{"role": "user", "content": "分析 NVDA 近期走勢"}]

    for t in range(num_turns):
        tool_id = f"tu_{t:03d}"
        tool_name = f"tool_{t}"
        tool_input = {"ticker": "NVDA", "turn": t}

        # Assistant message with text + tool_use
        messages.append({
            "role": "assistant",
            "content": [
                _make_text_block(f"Let me use {tool_name}."),
                _make_tool_use_block(tool_id, tool_name, tool_input),
            ],
        })

        # User message with tool_result
        result_content = f"Data from {tool_name}: " + "x" * result_size
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result_content,
            }],
        })

    return messages


def _make_tracker(turn_count, last_input_tokens):
    """Create a TokenTracker with simulated usage."""
    tracker = TokenTracker()
    for i in range(turn_count):
        inp = last_input_tokens if i == turn_count - 1 else 1000
        tracker.record("anthropic", "claude", input_tokens=inp, output_tokens=200)
    return tracker


# ── get_model_context_limit ───────────────────────────────────


class TestModelContextLimit:
    def test_claude_sonnet(self):
        assert get_model_context_limit("claude-sonnet-4-5-20250929") == 200_000

    def test_claude_opus(self):
        assert get_model_context_limit("claude-opus-4-5-20251101") == 200_000

    def test_gpt5(self):
        assert get_model_context_limit("gpt-5.2") == 128_000

    def test_unknown_model(self):
        assert get_model_context_limit("some-unknown-model") == 128_000

    def test_claude_haiku(self):
        assert get_model_context_limit("claude-haiku-3.5") == 200_000


# ── _compact_value ────────────────────────────────────────────


class TestCompactValue:
    def test_short_string(self):
        assert _compact_value("NVDA") == '"NVDA"'

    def test_long_string(self):
        long = "a" * 50
        result = _compact_value(long)
        assert result.startswith('"')
        assert '..."' in result
        assert len(result) < 50

    def test_number(self):
        assert _compact_value(42) == "42"

    def test_bool(self):
        assert _compact_value(True) == "True"


# ── _build_compact_summary ────────────────────────────────────


class TestBuildCompactSummary:
    def test_basic(self):
        result = _build_compact_summary(
            "get_news", {"ticker": "NVDA"}, "Some news data here", 200,
        )
        assert result.startswith(_COMPACT_MARKER)
        assert "get_news" in result
        assert 'ticker="NVDA"' in result
        assert "19 chars" in result
        assert "Some news data here" in result

    def test_long_content_truncated(self):
        long_content = "x" * 1000
        result = _build_compact_summary("tool", {}, long_content, 100)
        assert "1000 chars" in result
        assert "..." in result
        # Preview should be around 100 chars, not the full 1000
        assert len(result) < 300

    def test_empty_params(self):
        result = _build_compact_summary("tool", {}, "data", 200)
        assert "tool()" in result

    def test_multiple_params(self):
        result = _build_compact_summary(
            "get_prices", {"ticker": "AAPL", "days": 30}, "price data", 200,
        )
        assert 'ticker="AAPL"' in result
        assert "days=30" in result


# ── _extract_tool_info ────────────────────────────────────────


class TestExtractToolInfo:
    def test_extracts_from_assistant(self):
        messages = [
            {"role": "user", "content": "question"},
            {
                "role": "assistant",
                "content": [
                    _make_text_block("Thinking..."),
                    _make_tool_use_block("tu_001", "get_news", {"ticker": "NVDA"}),
                ],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "tu_001", "content": "data"}],
            },
        ]
        info = _extract_tool_info(messages, 2)
        assert "tu_001" in info
        assert info["tu_001"]["name"] == "get_news"
        assert info["tu_001"]["input"] == {"ticker": "NVDA"}

    def test_no_preceding_assistant(self):
        messages = [{"role": "user", "content": "question"}]
        info = _extract_tool_info(messages, 0)
        assert info == {}

    def test_multiple_tool_uses(self):
        messages = [
            {"role": "user", "content": "question"},
            {
                "role": "assistant",
                "content": [
                    _make_tool_use_block("tu_a", "tool_a", {"x": 1}),
                    _make_tool_use_block("tu_b", "tool_b", {"y": 2}),
                ],
            },
            {"role": "user", "content": []},
        ]
        info = _extract_tool_info(messages, 2)
        assert len(info) == 2
        assert info["tu_a"]["name"] == "tool_a"
        assert info["tu_b"]["name"] == "tool_b"


# ── ContextManager.should_compact ─────────────────────────────


class TestShouldCompact:
    def test_too_few_turns(self):
        ctx = ContextManager(model="claude-sonnet-4-5-20250929", keep_recent_turns=2)
        tracker = _make_tracker(2, last_input_tokens=100_000)
        assert not ctx.should_compact(tracker)

    def test_below_threshold(self):
        ctx = ContextManager(model="claude-sonnet-4-5-20250929", threshold_ratio=0.4)
        # 200K * 0.4 = 80K threshold
        tracker = _make_tracker(5, last_input_tokens=50_000)
        assert not ctx.should_compact(tracker)

    def test_above_threshold(self):
        ctx = ContextManager(model="claude-sonnet-4-5-20250929", threshold_ratio=0.4)
        tracker = _make_tracker(5, last_input_tokens=90_000)
        assert ctx.should_compact(tracker)

    def test_exactly_at_threshold(self):
        ctx = ContextManager(model="claude-sonnet-4-5-20250929", threshold_ratio=0.4)
        # 200K * 0.4 = 80K — at threshold, not above
        tracker = _make_tracker(5, last_input_tokens=80_000)
        assert not ctx.should_compact(tracker)

    def test_single_turn_never_compacts(self):
        ctx = ContextManager(model="claude-sonnet-4-5-20250929", keep_recent_turns=2)
        tracker = _make_tracker(1, last_input_tokens=200_000)
        assert not ctx.should_compact(tracker)

    def test_custom_threshold(self):
        ctx = ContextManager(model="gpt-5.2", threshold_ratio=0.2)
        # 128K * 0.2 = 25.6K
        tracker = _make_tracker(5, last_input_tokens=30_000)
        assert ctx.should_compact(tracker)


# ── ContextManager.token_threshold ────────────────────────────


class TestTokenThreshold:
    def test_claude_default(self):
        ctx = ContextManager(model="claude-sonnet-4-5-20250929", threshold_ratio=0.4)
        assert ctx.token_threshold == 80_000

    def test_gpt_custom(self):
        ctx = ContextManager(model="gpt-5.2", threshold_ratio=0.5)
        assert ctx.token_threshold == 64_000

    def test_unknown_model(self):
        ctx = ContextManager(model="unknown", threshold_ratio=0.4)
        assert ctx.token_threshold == 51_200  # 128K * 0.4


# ── ContextManager.compact_messages ───────────────────────────


class TestCompactMessages:
    def test_not_enough_messages(self):
        """Short conversations should not be compacted."""
        ctx = ContextManager(keep_recent_turns=2)
        messages = _make_messages(2)  # 5 messages total (1 + 2*2)
        result, stats = ctx.compact_messages(messages)
        assert stats["compacted"] == 0
        assert stats["chars_saved"] == 0

    def test_compacts_old_tool_results(self):
        """Old tool results should be compacted, recent ones preserved."""
        ctx = ContextManager(keep_recent_turns=2, preview_chars=50)
        messages = _make_messages(5, result_size=1000)
        # 11 messages: [0]=user, [1-2]=turn1, [3-4]=turn2, [5-6]=turn3, [7-8]=turn4, [9-10]=turn5

        result, stats = ctx.compact_messages(messages)

        # Turns 1-3 compacted (messages[2], [4], [6]), turns 4-5 preserved
        assert stats["compacted"] == 3
        assert stats["chars_saved"] > 0

        # Verify compacted results
        for idx in [2, 4, 6]:  # old turns
            content = result[idx]["content"][0]["content"]
            assert content.startswith(_COMPACT_MARKER)
            assert "chars" in content

        # Verify preserved results (recent turns)
        for idx in [8, 10]:  # recent turns
            content = result[idx]["content"][0]["content"]
            assert not content.startswith(_COMPACT_MARKER)

    def test_user_question_preserved(self):
        ctx = ContextManager(keep_recent_turns=1)
        messages = _make_messages(4)
        ctx.compact_messages(messages)
        assert messages[0]["content"] == "分析 NVDA 近期走勢"

    def test_assistant_messages_preserved(self):
        """Assistant messages (with tool_use blocks) should not be modified."""
        ctx = ContextManager(keep_recent_turns=1, preview_chars=50)
        messages = _make_messages(4, result_size=1000)

        original_assistant_1 = messages[1]["content"]
        ctx.compact_messages(messages)

        # Assistant content should be the same objects
        assert messages[1]["content"] is original_assistant_1

    def test_already_compacted_skipped(self):
        """Results that are already compacted should not be re-compacted."""
        ctx = ContextManager(keep_recent_turns=1, preview_chars=50)
        messages = _make_messages(4, result_size=1000)

        # First compaction
        _, stats1 = ctx.compact_messages(messages)
        saved1 = stats1["chars_saved"]

        # Second compaction — nothing new to compact
        _, stats2 = ctx.compact_messages(messages)
        assert stats2["compacted"] == 0
        assert stats2["chars_saved"] == 0

    def test_compaction_retains_tool_info(self):
        """Compacted results should include tool name and params."""
        ctx = ContextManager(keep_recent_turns=1, preview_chars=50)
        messages = _make_messages(3, result_size=500)

        ctx.compact_messages(messages)

        # Check first compacted result (turn 1)
        compacted = messages[2]["content"][0]["content"]
        assert "tool_0" in compacted
        assert "NVDA" in compacted

    def test_compaction_retains_preview(self):
        """Compacted results should include a content preview."""
        ctx = ContextManager(keep_recent_turns=1, preview_chars=100)
        messages = _make_messages(3, result_size=500)

        ctx.compact_messages(messages)

        compacted = messages[2]["content"][0]["content"]
        assert "Preview:" in compacted
        assert "Data from tool_0" in compacted

    def test_stats_tracking(self):
        """Compaction stats should accumulate across calls."""
        ctx = ContextManager(keep_recent_turns=1, preview_chars=50)

        # First session
        messages1 = _make_messages(4, result_size=1000)
        _, stats1 = ctx.compact_messages(messages1)
        assert stats1["compaction_count"] == 1

        # Second session
        messages2 = _make_messages(4, result_size=1000)
        _, stats2 = ctx.compact_messages(messages2)
        assert stats2["compaction_count"] == 2
        assert stats2["total_chars_saved"] > stats1["total_chars_saved"]

    def test_non_tool_result_content_preserved(self):
        """Non-tool_result items in user messages should be untouched."""
        ctx = ContextManager(keep_recent_turns=1)
        messages = _make_messages(3, result_size=500)

        # Add a plain text item to an old user message
        messages[2]["content"].append({"type": "text", "text": "additional info"})

        ctx.compact_messages(messages)

        # The text item should still be there
        items = messages[2]["content"]
        text_items = [i for i in items if i.get("type") == "text"]
        assert len(text_items) == 1
        assert text_items[0]["text"] == "additional info"

    def test_multiple_tool_results_in_one_message(self):
        """Messages with multiple tool results should all be compacted."""
        ctx = ContextManager(keep_recent_turns=1, preview_chars=50)

        messages = [
            {"role": "user", "content": "question"},
            {
                "role": "assistant",
                "content": [
                    _make_tool_use_block("tu_a", "tool_a", {"x": 1}),
                    _make_tool_use_block("tu_b", "tool_b", {"y": 2}),
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_a", "content": "a" * 500},
                    {"type": "tool_result", "tool_use_id": "tu_b", "content": "b" * 500},
                ],
            },
            # Recent turn (preserved)
            {
                "role": "assistant",
                "content": [_make_tool_use_block("tu_c", "tool_c", {})],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_c", "content": "recent data"},
                ],
            },
        ]

        _, stats = ctx.compact_messages(messages)
        assert stats["compacted"] == 2  # Both tu_a and tu_b compacted

        for item in messages[2]["content"]:
            assert item["content"].startswith(_COMPACT_MARKER)


# ── ContextManager summary / repr ─────────────────────────────


class TestContextManagerMeta:
    def test_summary(self):
        ctx = ContextManager(model="claude-sonnet-4-5-20250929")
        s = ctx.summary()
        assert s["compaction_count"] == 0
        assert s["model"] == "claude-sonnet-4-5-20250929"
        assert s["threshold_tokens"] == 80_000

    def test_repr(self):
        ctx = ContextManager(model="gpt-5.2")
        r = repr(ctx)
        assert "ContextManager" in r
        assert "gpt-5.2" in r

    def test_repr_after_compaction(self):
        ctx = ContextManager(keep_recent_turns=1, preview_chars=50)
        messages = _make_messages(4, result_size=1000)
        ctx.compact_messages(messages)
        r = repr(ctx)
        assert "compactions=1" in r
        assert "saved=" in r


# ── Full integration scenario ─────────────────────────────────


class TestIntegrationScenario:
    def test_simulated_growing_context(self):
        """
        Simulate an Anthropic agent session where context grows over 5 turns.
        ContextManager should compact old results when threshold is hit.
        """
        ctx = ContextManager(
            model="claude-sonnet-4-5-20250929",
            threshold_ratio=0.4,
            keep_recent_turns=2,
            preview_chars=100,
        )
        tracker = TokenTracker()
        messages = [{"role": "user", "content": "分析 NVDA"}]

        # Simulate turns with growing context
        input_tokens_per_turn = [800, 2_000, 5_000, 20_000, 85_000]

        for turn_idx, input_tokens in enumerate(input_tokens_per_turn):
            # Simulate API response
            tracker.record("anthropic", "claude", input_tokens=input_tokens, output_tokens=500)

            # Add tool call + result
            tool_id = f"tu_{turn_idx}"
            messages.append({
                "role": "assistant",
                "content": [
                    _make_tool_use_block(tool_id, f"tool_{turn_idx}", {"turn": turn_idx}),
                ],
            })
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": f"Result data for turn {turn_idx}: " + "x" * 2000,
                }],
            })

            # Check and compact
            if ctx.should_compact(tracker):
                messages, stats = ctx.compact_messages(messages)

        # After 5 turns, the last one (85K) exceeded 80K threshold
        assert ctx._compaction_count >= 1

        # Recent 2 turns (turns 3, 4) should be preserved
        assert not messages[-1]["content"][0]["content"].startswith(_COMPACT_MARKER)
        assert not messages[-3]["content"][0]["content"].startswith(_COMPACT_MARKER)

        # Old turns should be compacted
        assert messages[2]["content"][0]["content"].startswith(_COMPACT_MARKER)

    def test_simple_query_no_compaction(self):
        """Simple 2-turn queries should never trigger compaction."""
        ctx = ContextManager(
            model="claude-sonnet-4-5-20250929",
            threshold_ratio=0.4,
            keep_recent_turns=2,
        )
        tracker = TokenTracker()

        # 2 turns, even with high token count
        tracker.record("anthropic", "claude", input_tokens=100_000, output_tokens=500)
        tracker.record("anthropic", "claude", input_tokens=150_000, output_tokens=500)

        assert not ctx.should_compact(tracker)