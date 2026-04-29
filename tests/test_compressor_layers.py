"""Tests for Layers 0-3 + the ContextCompressor orchestrator (P1.4 commit 2).

Locks down per-layer behaviour:

  - Layer 0: budget pass-through, overflow disk write, fail-open paths,
    record reference appended, custom reducer dispatched.
  - Layer 1: minify JSON in old turns; recent turns + non-JSON content
    untouched.
  - Layer 2: scratchpad prepended as marker-wrapped summary; old
    tool_results stubbed; no-op when scratchpad empty.
  - Layer 3: old tool_results replaced with stubs; overflow_record_id
    preserved in stub when present.
  - find_recent_boundary: counts user turns excluding compaction
    summaries; returns 0 when not enough turns.
  - Orchestrator: respects enabled flags, threshold-gated layers,
    emits CompressionEvent telemetry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.shared.compressor import (
    CompressorConfig,
    ContextCompressor,
    OverflowStore,
    ProjectedMessage,
    apply_layer_0,
    apply_layer_1,
    apply_layer_2,
    apply_layer_3,
    find_recent_boundary,
    format_messages_as_transcript,
    total_chars,
    truncate_with_marker,
)


# ============================================================
# find_recent_boundary
# ============================================================


class TestFindRecentBoundary:
    def test_empty_messages(self):
        assert find_recent_boundary([], keep_recent_turns=2) == 0

    def test_keep_zero_returns_end(self):
        msgs = [{"role": "user", "content": "u1"}]
        assert find_recent_boundary(msgs, keep_recent_turns=0) == 1

    def test_keep_negative_raises(self):
        with pytest.raises(ValueError):
            find_recent_boundary([], keep_recent_turns=-1)

    def test_finds_boundary_at_recent_user_turn(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
            {"role": "assistant", "content": "a3"},
        ]
        # keep last 2 user turns → boundary at index 2 (start of u2)
        assert find_recent_boundary(msgs, keep_recent_turns=2) == 2

    def test_not_enough_turns_returns_zero(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ]
        # Only 1 user turn, want 5 → boundary at 0 (keep everything)
        assert find_recent_boundary(msgs, keep_recent_turns=5) == 0

    def test_compaction_summary_not_counted(self):
        msgs = [
            {"role": "user", "content": "summary", "is_compaction_summary": True},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]
        # keep last 2 real user turns: u2 and u1; boundary at index 1 (start of u1)
        assert find_recent_boundary(msgs, keep_recent_turns=2) == 1


class TestFormatTranscript:
    def test_basic_roles_render(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "tool_use", "tool_name": "get_x", "content": "{}"},
            {"role": "tool_result", "tool_name": "get_x", "content": '{"ok": true}'},
        ]
        out = format_messages_as_transcript(msgs)
        assert "[USER]: hi" in out
        assert "[ASSISTANT]: hello" in out
        assert "[TOOL CALL: get_x]" in out
        assert "[TOOL RESULT: get_x]" in out

    def test_compaction_summary_distinct_tag(self):
        msgs = [
            {
                "role": "user",
                "content": "earlier-summary text",
                "is_compaction_summary": True,
            }
        ]
        out = format_messages_as_transcript(msgs)
        assert "[COMPACTION SUMMARY]" in out
        assert "[USER]" not in out  # do not also render as user


# ============================================================
# Layer 0: insertion-time budget + overflow
# ============================================================


class TestLayer0:
    def test_passthrough_when_within_budget(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="s1")
        out, record = apply_layer_0(
            tool_name="t",
            args={},
            payload="small",
            overflow_store=store,
            budget_chars=100,
        )
        assert out == "small"
        assert record is None

    def test_overflow_writes_record_and_truncates(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="s1")
        big = "x" * 50_000
        out, record = apply_layer_0(
            tool_name="t",
            args={"a": 1},
            payload=big,
            overflow_store=store,
            budget_chars=2000,
        )
        assert record is not None
        # Summary fits within budget + ~80 chars for record_id ref line
        assert len(out) <= 2000 + 200
        assert f"overflow_record={record.record_id}" in out
        # Round-trip recovers the original
        retrieved = store.read(record.record_id)
        assert retrieved is not None
        assert retrieved.original_payload == big

    def test_specific_reducer_dispatched_for_known_tool(self, tmp_path):
        """tavily_search payload should hit web_result_reducer (preserves URLs)."""
        store = OverflowStore(tmp_path, session_id="s1")
        payload = json.dumps({
            "query": "find me x",
            "results": [
                {"title": f"R{i}", "url": f"https://e.com/{i}", "content": "y" * 5000}
                for i in range(5)
            ],
        })
        out, record = apply_layer_0(
            tool_name="tavily_search",
            args={"query": "find me x"},
            payload=payload,
            overflow_store=store,
            budget_chars=5000,
        )
        assert record is not None
        # All 5 URLs survive (web_result_reducer keeps them)
        for i in range(5):
            assert f"https://e.com/{i}" in out

    def test_unknown_tool_uses_default_reducer(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="s1")
        big = "AAAAA" + ("x" * 50_000) + "ZZZZZ"
        out, record = apply_layer_0(
            tool_name="unknown_tool",
            args={},
            payload=big,
            overflow_store=store,
            budget_chars=1000,
        )
        assert record is not None
        # Default keeps head and tail
        assert out.startswith("AAAAA")
        # Tail "ZZZZZ" appears before the overflow_record reference line
        assert "ZZZZZ" in out

    def test_failopen_when_disk_write_breaks(self, tmp_path):
        """If overflow store raises, Layer 0 returns the original payload + None."""
        class _BrokenStore:
            def write(self, *a, **kw):
                raise RuntimeError("disk full")

        big = "x" * 10_000
        out, record = apply_layer_0(
            tool_name="t",
            args={},
            payload=big,
            overflow_store=_BrokenStore(),
            budget_chars=1000,
        )
        # Fail-open: original payload returned, no record
        assert out == big
        assert record is None

    def test_failopen_when_reducer_raises(self, tmp_path):
        store = OverflowStore(tmp_path, session_id="s1")

        def broken_reducer(payload, *, budget):
            raise RuntimeError("reducer broke")

        registry = {"weird_tool": broken_reducer}
        big = "x" * 50_000
        out, record = apply_layer_0(
            tool_name="weird_tool",
            args={},
            payload=big,
            overflow_store=store,
            budget_chars=1000,
            registry=registry,
        )
        assert out == big
        assert record is None

    def test_unwraps_tool_output_envelope_before_reducer(self, tmp_path):
        """Bridge wraps tool output as <tool_output tool="X">JSON</tool_output>.
        Layer 0 must unwrap before calling the reducer (otherwise JSON parse
        fails and reducer falls back to truncate_with_marker, losing the
        ability to preserve titles / URLs / etc.)."""
        from src.agents.shared.security import wrap_tool_result

        store = OverflowStore(tmp_path, session_id="s1")
        # Real tavily_search shape, then wrapped by the bridge
        inner = json.dumps({
            "query": "find me NVDA",
            "answer": "NVIDIA reports earnings...",
            "result_count": 3,
            "results": [
                {"title": f"R{i}", "url": f"https://x/{i}", "content": "y" * 10_000}
                for i in range(3)
            ],
        })
        wrapped = wrap_tool_result(inner, "tavily_search")

        out, record = apply_layer_0(
            tool_name="tavily_search",
            args={"query": "find me NVDA"},
            payload=wrapped,
            overflow_store=store,
            budget_chars=4_000,
        )
        assert record is not None
        # Output is re-wrapped — agent's parser still sees the envelope
        assert out.startswith('<tool_output tool="tavily_search">\n')
        assert "</tool_output>" in out
        # The reducer DID run on inner content (URLs preserved)
        for i in range(3):
            assert f"https://x/{i}" in out
        # No 1000-char body runs survived (specific reducer was used,
        # NOT the default head+tail)
        assert out.count("y" * 1000) == 0
        # overflow_record reference appended OUTSIDE the envelope
        assert "[overflow_record=" in out
        ref_idx = out.index("[overflow_record=")
        envelope_end = out.index("</tool_output>")
        assert ref_idx > envelope_end

    def test_overflow_round_trip_preserves_original_wrapped_payload(self, tmp_path):
        """The overflow record stores the EXACT original (wrapped) payload —
        retrieval gives it back byte-for-byte."""
        from src.agents.shared.security import wrap_tool_result

        store = OverflowStore(tmp_path, session_id="s1")
        inner = json.dumps({
            "query": "x",
            "answer": "...",
            "result_count": 1,
            "results": [{"title": "T", "url": "U", "content": "z" * 50_000}],
        })
        wrapped = wrap_tool_result(inner, "tavily_search")

        _out, record = apply_layer_0(
            tool_name="tavily_search",
            args={},
            payload=wrapped,
            overflow_store=store,
            budget_chars=2_000,
        )
        assert record is not None
        retrieved = store.read(record.record_id)
        assert retrieved is not None
        assert retrieved.original_payload == wrapped  # byte-perfect

    def test_no_unwrap_when_payload_not_wrapped(self, tmp_path):
        """If the payload is NOT wrapped, Layer 0 must not insert a
        spurious envelope on the output side."""
        store = OverflowStore(tmp_path, session_id="s1")
        big = "raw plain text " * 5_000
        out, record = apply_layer_0(
            tool_name="unknown_tool",
            args={},
            payload=big,
            overflow_store=store,
            budget_chars=500,
        )
        assert record is not None
        assert "<tool_output" not in out
        assert "</tool_output>" not in out


# ============================================================
# Layer 1: microcompact JSON in old turns
# ============================================================


class TestLayer1:
    def test_minifies_old_tool_results(self):
        big_json = json.dumps({"a": 1, "nested": {"b": 2}}, indent=2)
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "get_x", "content": big_json},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
            {"role": "assistant", "content": "a3"},
        ]
        out = apply_layer_1(msgs, keep_recent_turns=2)
        # Old tool_result minified
        compact = out[1]["content"]
        assert "\n" not in compact
        assert ", " not in compact  # separators=(",", ":")
        # Recent turns untouched
        assert out[2:] == msgs[2:]

    def test_recent_tool_results_unchanged(self):
        formatted = json.dumps({"a": 1}, indent=2)
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "t", "content": formatted},
            {"role": "user", "content": "u2"},
            {"role": "tool_result", "tool_name": "t", "content": formatted},
        ]
        # u2 is the last user turn; keep_recent=1 → boundary=2 → tool_result at idx 3 is recent
        out = apply_layer_1(msgs, keep_recent_turns=1)
        assert out[3]["content"] == formatted  # untouched

    def test_non_json_content_passes_through(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "t", "content": "plain text"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        out = apply_layer_1(msgs, keep_recent_turns=2)
        assert out[1]["content"] == "plain text"

    def test_does_not_mutate_input(self):
        msgs = [{"role": "user", "content": "u1"}]
        out = apply_layer_1(msgs, keep_recent_turns=1)
        assert out is not msgs

    def test_unwraps_envelope_before_minify(self):
        """Production tool_results are wrapped as <tool_output tool="X">JSON</tool_output>.
        Layer 1 must unwrap before json.loads so the minify branch actually
        fires on real bridge output, then re-wrap for the agent's parser."""
        from src.agents.shared.security import wrap_tool_result

        formatted = json.dumps(
            {"results": [{"a": 1, "b": [2, 3]}, {"a": 4, "b": [5, 6]}]},
            indent=2,
        )
        wrapped = wrap_tool_result(formatted, "tavily_search")
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "tavily_search", "content": wrapped},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        out = apply_layer_1(msgs, keep_recent_turns=2)
        new_content = out[1]["content"]
        # Re-wrapped — envelope preserved on output
        assert new_content.startswith('<tool_output tool="tavily_search">\n')
        assert new_content.endswith("\n</tool_output>")
        # Inner JSON minified (no pretty-print indents, no ", " separator)
        inner = new_content[len('<tool_output tool="tavily_search">\n'):-len("\n</tool_output>")]
        assert "\n" not in inner
        assert ", " not in inner
        assert json.loads(inner) == {"results": [{"a": 1, "b": [2, 3]}, {"a": 4, "b": [5, 6]}]}
        # Net size shrunk (the whole point)
        assert len(new_content) < len(wrapped)

    def test_no_envelope_when_input_not_wrapped(self):
        """If the tool_result content is raw JSON (no envelope), Layer 1
        must NOT insert a spurious wrapper."""
        formatted = json.dumps({"a": 1, "b": [1, 2, 3]}, indent=2)
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "t", "content": formatted},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        out = apply_layer_1(msgs, keep_recent_turns=2)
        new_content = out[1]["content"]
        assert "<tool_output" not in new_content
        assert "</tool_output>" not in new_content
        # Still minified
        assert "\n" not in new_content
        assert json.loads(new_content) == {"a": 1, "b": [1, 2, 3]}

    def test_wrapped_non_json_passes_through(self):
        """If the envelope wraps non-JSON text, the content must pass through
        unchanged — including the envelope (no half-rewrite)."""
        from src.agents.shared.security import wrap_tool_result

        wrapped = wrap_tool_result("plain text response, no JSON here", "some_tool")
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "some_tool", "content": wrapped},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        out = apply_layer_1(msgs, keep_recent_turns=2)
        # Pass-through: identical to input
        assert out[1]["content"] == wrapped


# ============================================================
# Layer 2: scratchpad reuse
# ============================================================


class TestLayer2:
    def test_noop_with_empty_scratchpad(self):
        msgs = [{"role": "user", "content": "u1"}]
        assert apply_layer_2(msgs, scratchpad="", keep_recent_turns=2) == msgs

    def test_noop_with_whitespace_scratchpad(self):
        msgs = [{"role": "user", "content": "u1"}]
        assert apply_layer_2(msgs, scratchpad="   \n  ", keep_recent_turns=2) == msgs

    def test_prepends_marker_wrapped_summary(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "user", "content": "u2"},
        ]
        out = apply_layer_2(msgs, scratchpad="prior context", keep_recent_turns=2)
        assert out[0]["role"] == "user"
        assert out[0]["is_compaction_summary"] is True
        assert "prior context" in out[0]["content"]
        assert "<scratchpad_summary>" in out[0]["content"]

    def test_stubs_old_tool_results(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "get_x", "content": "BIG OLD RESULT"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
            {"role": "tool_result", "tool_name": "get_y", "content": "RECENT RESULT"},
        ]
        out = apply_layer_2(msgs, scratchpad="ctx", keep_recent_turns=2)
        # Summary prepended → indices shift by 1
        assert out[0]["is_compaction_summary"] is True
        # Old tool_result (originally idx 1) → stub
        old_tool = out[2]
        assert old_tool["role"] == "tool_result"
        assert "[old get_x result" in old_tool["content"]
        # Recent tool_result preserved
        recent_tool = out[5]
        assert recent_tool["content"] == "RECENT RESULT"

    def test_idempotent_repeated_application_replaces_summary(self):
        """If apply_layer_2 runs twice with different scratchpads, only
        ONE summary item should remain — and it should carry the latest
        scratchpad text, not stack on top of the previous one."""
        original = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "t", "content": "BIG"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        v1 = apply_layer_2(original, scratchpad="v1 ctx", keep_recent_turns=2)
        v2 = apply_layer_2(v1, scratchpad="v2 ctx", keep_recent_turns=2)

        summaries = [m for m in v2 if m.get("is_compaction_summary")]
        assert len(summaries) == 1
        assert "v2 ctx" in summaries[0]["content"]
        assert "v1 ctx" not in summaries[0]["content"]
        # Total length unchanged across the second application
        assert len(v2) == len(v1)

    def test_idempotent_with_same_scratchpad(self):
        """Running with the same scratchpad twice is a no-op effectively
        (summary content same, no extra item)."""
        original = [
            {"role": "user", "content": "u1"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        v1 = apply_layer_2(original, scratchpad="ctx", keep_recent_turns=2)
        v2 = apply_layer_2(v1, scratchpad="ctx", keep_recent_turns=2)
        assert len(v1) == len(v2)
        assert sum(1 for m in v2 if m.get("is_compaction_summary")) == 1


# ============================================================
# Layer 3: progressive truncation
# ============================================================


class TestLayer3:
    def test_stubs_old_tool_results(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "get_x", "content": "BIG"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        out = apply_layer_3(msgs, keep_recent_turns=2)
        assert "[old get_x result" in out[1]["content"]
        # No record_id available → stub says "re-call"
        assert "re-call" in out[1]["content"]

    def test_preserves_overflow_record_id_in_stub(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {
                "role": "tool_result",
                "tool_name": "get_x",
                "content": "summary text",
                "overflow_record_id": "abcd1234ef567890",
            },
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        out = apply_layer_3(msgs, keep_recent_turns=2)
        stub = out[1]["content"]
        assert "abcd1234ef567890" in stub
        assert "record_id=" in stub

    def test_recent_tool_results_unchanged(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "user", "content": "u2"},
            {"role": "tool_result", "tool_name": "t", "content": "RECENT"},
        ]
        out = apply_layer_3(msgs, keep_recent_turns=1)
        # u2 is last user → boundary = 1 → idx 2 is recent
        assert out[2]["content"] == "RECENT"


# ============================================================
# total_chars helper
# ============================================================


class TestTotalChars:
    def test_sums_content_chars(self):
        msgs = [
            {"role": "user", "content": "abc"},
            {"role": "assistant", "content": "wxyz"},
        ]
        assert total_chars(msgs) == 7

    def test_handles_missing_content(self):
        msgs = [{"role": "user"}, {"role": "assistant", "content": "ok"}]
        assert total_chars(msgs) == 2

    def test_empty_list_zero(self):
        assert total_chars([]) == 0


# ============================================================
# ContextCompressor orchestrator
# ============================================================


class TestContextCompressor:
    def test_layer_0_round_trip_via_orchestrator(self, tmp_path):
        c = ContextCompressor(
            session_id="s1",
            overflow_dir=tmp_path,
            config=CompressorConfig(layer_0_budget_chars=2000),
        )
        big = "x" * 10_000
        summary, record = c.process_tool_result("t", {"a": 1}, big)
        assert record is not None
        assert "overflow_record=" in summary
        # Recovery via the helper (NOT agent-exposed)
        assert c.get_overflow_payload(record.record_id) == big

    def test_disabled_master_toggle_passthrough(self, tmp_path):
        c = ContextCompressor(
            session_id="s1",
            overflow_dir=tmp_path,
            config=CompressorConfig(enabled=False),
        )
        big = "x" * 50_000
        summary, record = c.process_tool_result("t", {}, big)
        assert summary == big
        assert record is None

    def test_layer_0_disabled_passthrough(self, tmp_path):
        c = ContextCompressor(
            session_id="s1",
            overflow_dir=tmp_path,
            config=CompressorConfig(layer_0_enabled=False),
        )
        big = "x" * 50_000
        summary, record = c.process_tool_result("t", {}, big)
        assert summary == big
        assert record is None

    def test_compact_pre_call_layer_1_minifies(self, tmp_path):
        c = ContextCompressor(
            session_id="s1",
            overflow_dir=tmp_path,
            config=CompressorConfig(
                layer_2_threshold_chars=1_000_000,  # never triggers
                layer_3_threshold_chars=1_000_000,
            ),
        )
        formatted = json.dumps({"a": 1}, indent=2)
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "t", "content": formatted},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        result = c.compact_pre_call(msgs)
        out = result.messages
        # Layer 1 ran, minified the old tool_result
        assert "\n" not in out[1]["content"]
        # Telemetry recorded
        assert any(e.layer == 1 for e in c.events)
        # Layer 1 path: not a prefix replacement
        assert result.replace_prefix_to is None
        assert result.appended_anchor is False
        assert 1 in result.layers_fired

    def test_compact_pre_call_layer_2_fires_above_threshold(self, tmp_path):
        c = ContextCompressor(
            session_id="s1",
            overflow_dir=tmp_path,
            config=CompressorConfig(
                layer_1_enabled=False,  # isolate Layer 2
                layer_2_threshold_chars=100,
                layer_3_threshold_chars=1_000_000,
            ),
        )
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "t", "content": "x" * 200},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        result = c.compact_pre_call(msgs, scratchpad="here is prior context")
        out = result.messages
        # Layer 2 prepended summary
        assert out[0].get("is_compaction_summary") is True
        assert any(e.layer == 2 for e in c.events)
        assert result.replace_prefix_to is None  # L2 is not L5 prefix replace
        assert 2 in result.layers_fired

    def test_compact_pre_call_layer_3_fires_above_threshold(self, tmp_path):
        c = ContextCompressor(
            session_id="s1",
            overflow_dir=tmp_path,
            config=CompressorConfig(
                layer_1_enabled=False,
                layer_2_threshold_chars=1_000_000,  # never
                layer_3_threshold_chars=100,
            ),
        )
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "tool_result", "tool_name": "t", "content": "x" * 200},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        result = c.compact_pre_call(msgs)
        out = result.messages
        # Old tool_result stubbed
        assert "[old t result" in out[1]["content"]
        assert any(e.layer == 3 for e in c.events)
        assert result.replace_prefix_to is None
        assert 3 in result.layers_fired

    def test_compact_pre_call_no_trigger_below_threshold(self, tmp_path):
        c = ContextCompressor(
            session_id="s1",
            overflow_dir=tmp_path,
            config=CompressorConfig(
                layer_1_enabled=False,  # avoid layer-1 noise
                layer_2_threshold_chars=1_000_000,
                layer_3_threshold_chars=1_000_000,
            ),
        )
        msgs = [
            {"role": "user", "content": "small"},
            {"role": "tool_result", "tool_name": "t", "content": "x"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
        ]
        result = c.compact_pre_call(msgs)
        assert result.messages == msgs
        assert result.replace_prefix_to is None
        assert result.appended_anchor is False
        assert result.layers_fired == []
        assert c.events == []

    def test_circuit_breaker_state_starts_closed(self, tmp_path):
        c = ContextCompressor(session_id="s1", overflow_dir=tmp_path)
        assert c.layer_5_circuit_open is False
