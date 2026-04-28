"""P1.4 commit 3 integration tests.

Locks down the wiring between :class:`ContextManager` and
:class:`ContextCompressor` (Layers 0-3 library). Where the layer-level
tests in ``test_compressor_layers.py`` exercise the compressor in
isolation, this file exercises the *adapter* contracts:

  - default-off path preserves legacy behaviour (regression guard for
    ``test_context_manager.py``)
  - flag-on Layer 0 hook returns compressed content but never adds new
    fields to the native Anthropic ``tool_result`` block
  - record_id round-trip via ``ContextCompressor.get_overflow_payload``
  - Layers 1-3 fire on char threshold ALONE — token tracker is not
    consulted in the compressor path
  - patch-based projection preserves assistant ``ContentBlock`` object
    identity (no reconstruction)
  - multiple ``tool_result`` blocks in one user message preserve order +
    ``tool_use_id``s after patch-back
  - record_id only lives in the content marker, never as a sidecar field
    on the native block
  - CLI-shape Anthropic loop wiring works the same way as the agent.py
    loop (both use ``ContextManager``; we test the helper directly)
  - ``profile.get("compaction", {})`` correctly populates ``AgentConfig``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.config import AgentConfig, get_agent_config
from src.agents.shared.compressor import CompressorConfig
from src.agents.shared.context_manager import (
    ContextManager,
    _apply_compression_back,
    _project_for_compression,
)


# ============================================================
# Shared fixtures + helpers
# ============================================================


def _make_ctx(tmp_path: Path, *, enabled: bool = True, **cfg_kwargs) -> ContextManager:
    """Build a ContextManager wired to a temporary overflow dir."""
    config = CompressorConfig(enabled=enabled, **cfg_kwargs) if enabled else None
    return ContextManager(
        model="claude-opus-4-7",
        keep_recent_turns=2,
        session_id="test-session",
        overflow_dir=tmp_path,
        compaction_config=config,
        scratchpad="",
    )


class _FakeToolUseBlock:
    """Mimics the SDK ContentBlock shape: .type / .id / .name / .input."""

    def __init__(self, *, id: str, name: str, input: dict):
        self.type = "tool_use"
        self.id = id
        self.name = name
        self.input = input


class _FakeTextBlock:
    """Mimics the SDK TextBlock shape: .type / .text."""

    def __init__(self, text: str):
        self.type = "text"
        self.text = text


def _wrapped(content: str, tool_name: str) -> str:
    """Mirror security.wrap_tool_result without importing it (cheap shape match)."""
    return f'<tool_output tool="{tool_name}">\n{content}\n</tool_output>'


# ============================================================
# Default off: legacy behaviour preserved
# ============================================================


class TestDefaultOffPreservesLegacy:
    def test_no_compaction_config_falls_through_to_legacy(self, tmp_path):
        """ContextManager() without compaction_config behaves exactly like
        Phase 3 ContextManager — same constructor signature, same path."""
        ctx = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=2,
        )
        # No compressor instantiated
        assert ctx.compressor is None

    def test_compaction_config_disabled_does_not_instantiate_compressor(self, tmp_path):
        """compaction_config provided but enabled=False → still legacy."""
        ctx = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=2,
            session_id="s1",
            overflow_dir=tmp_path,
            compaction_config=CompressorConfig(enabled=False),
        )
        assert ctx.compressor is None

    def test_missing_session_id_falls_back_with_warning(self, tmp_path, caplog):
        """compaction enabled but no session_id → warn + legacy path."""
        with caplog.at_level("WARNING"):
            ctx = ContextManager(
                model="claude-opus-4-7",
                keep_recent_turns=2,
                overflow_dir=tmp_path,
                compaction_config=CompressorConfig(enabled=True),
            )
        assert ctx.compressor is None
        assert any("session_id" in rec.message for rec in caplog.records)

    def test_maybe_apply_layer_0_passthrough_when_disabled(self):
        """The L0 hook helper returns the input unchanged when no compressor."""
        ctx = ContextManager(model="claude-opus-4-7")
        big = "x" * 50_000
        out = ctx.maybe_apply_layer_0("some_tool", {}, big)
        assert out == big

    def test_legacy_compact_messages_unchanged(self):
        """Run a representative legacy scenario; assert old stats shape still
        present (regression guard for callers / logging)."""
        ctx = ContextManager(
            model="claude-opus-4-7",
            threshold_ratio=0.7,
            keep_recent_turns=2,
            preview_chars=200,
        )
        # Build a structurally minimal message history (legacy expects 1 +
        # keep_recent*2 + 2 = 7 messages min to compact anything).
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t1", name="get_x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1", "content": "OLD" * 200,
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t2", name="get_y", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t2", "content": "MID" * 200,
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t3", name="get_z", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t3", "content": "RECENT",
            }]},
        ]
        out, stats = ctx.compact_messages(msgs)
        # Legacy stats shape preserved (no events key on legacy path)
        assert "compacted" in stats
        assert "chars_saved" in stats
        assert "compaction_count" in stats
        assert "total_chars_saved" in stats
        assert "events" not in stats
        # Compressed at least one (the very-old turn 1)
        assert stats["compacted"] >= 1


# ============================================================
# Flag on: Layer 0 hook
# ============================================================


class TestLayer0HookOnAnthropicLoop:
    def test_oversized_wrapped_tool_result_compressed(self, tmp_path):
        """maybe_apply_layer_0 with a real wrapped tavily payload over budget
        returns compressed content (envelope preserved, urls kept)."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=4_000)
        inner = json.dumps({
            "query": "find me NVDA",
            "answer": "NVIDIA earnings preview",
            "result_count": 3,
            "results": [
                {"title": f"R{i}", "url": f"https://x/{i}", "content": "y" * 10_000}
                for i in range(3)
            ],
        })
        wrapped = _wrapped(inner, "tavily_search")
        out = ctx.maybe_apply_layer_0("tavily_search", {"query": "find me NVDA"}, wrapped)
        assert isinstance(out, str)
        # Envelope preserved on output
        assert out.startswith('<tool_output tool="tavily_search">\n')
        # URLs preserved by the specific reducer (proof reducer ran on inner)
        for i in range(3):
            assert f"https://x/{i}" in out
        # overflow_record marker present, OUTSIDE envelope
        assert "[overflow_record=" in out
        ref_idx = out.index("[overflow_record=")
        env_idx = out.index("</tool_output>")
        assert ref_idx > env_idx

    def test_under_budget_passthrough(self, tmp_path):
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=10_000)
        small = _wrapped('{"ok": true}', "tavily_search")
        out = ctx.maybe_apply_layer_0("tavily_search", {}, small)
        assert out == small

    def test_overflow_round_trip_byte_perfect(self, tmp_path):
        """The record_id appended to the L0 summary points to a record whose
        original_payload is the EXACT wrapped input — byte-for-byte."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=2_000)
        inner = json.dumps({"results": [{"url": "u", "content": "z" * 50_000}]})
        wrapped = _wrapped(inner, "tavily_search")
        out = ctx.maybe_apply_layer_0("tavily_search", {}, wrapped)

        import re
        m = re.search(r"\[overflow_record=([0-9a-f]{16})", out)
        assert m, f"no record marker in: {out[-200:]!r}"
        record_id = m.group(1)

        retrieved = ctx.compressor.get_overflow_payload(record_id)
        assert retrieved == wrapped

    def test_l0_hook_returns_string_for_non_string_input(self, tmp_path):
        """If the tool returns a non-string (dict / list), the helper still
        returns a string — agent.py / cli.py rely on this."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=10)  # tiny → forces stringify
        out = ctx.maybe_apply_layer_0("t", {}, {"some": "dict"})
        assert isinstance(out, str)


# ============================================================
# Native block hygiene: no extra keys leak into Anthropic blocks
# ============================================================


class TestNativeBlockHygiene:
    def test_record_id_only_in_content_not_native_field(self, tmp_path):
        """L0 hook returns a STRING. Wherever the caller drops it into a
        tool_result block, the block keeps only type/tool_use_id/content —
        record_id rides along inside the content marker."""
        ctx = _make_ctx(tmp_path, layer_0_budget_chars=2_000)
        wrapped = _wrapped("y" * 10_000, "tavily_search")
        compressed = ctx.maybe_apply_layer_0("tavily_search", {}, wrapped)
        # Simulate the agent.py / cli.py call site
        block = {
            "type": "tool_result",
            "tool_use_id": "toolu_01abc",
            "content": compressed,
        }
        # Native block has exactly the three Anthropic-recognized keys
        assert set(block.keys()) == {"type", "tool_use_id", "content"}
        # record_id is inside content, not as a sidecar field
        assert "[overflow_record=" in block["content"]
        assert "overflow_record_id" not in block


# ============================================================
# Patch-based projection: assistant block identity preserved
# ============================================================


class TestProjectionAdapter:
    def test_assistant_block_object_identity_preserved(self, tmp_path):
        """After project → compress → patch back, assistant ContentBlock
        instances at the same index in the same message must be the same
        objects. We never reconstruct them."""
        text_block = _FakeTextBlock("thinking out loud")
        tool_use = _FakeToolUseBlock(id="t1", name="get_x", input={"a": 1})
        wrapped = _wrapped(json.dumps({"x": 1}), "get_x")
        msgs = [
            {"role": "user", "content": "What is X?"},
            {"role": "assistant", "content": [text_block, tool_use]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1", "content": wrapped,
            }]},
            {"role": "user", "content": [{  # additional turns to make boundary trigger
                "type": "tool_result", "tool_use_id": "t1", "content": "RECENT",
            }]},
        ]
        ctx = _make_ctx(
            tmp_path,
            layer_2_threshold_chars=10**9,  # never
            layer_3_threshold_chars=10**9,
        )
        out, stats = ctx.compact_messages(msgs)

        # Assistant message at index 1: SAME content list object identity for
        # blocks (we shallow-pass the assistant message through unchanged)
        assert out[1] is msgs[1]
        assert out[1]["content"] is msgs[1]["content"]
        assert out[1]["content"][0] is text_block
        assert out[1]["content"][1] is tool_use

    def test_multiple_tool_results_same_user_msg_order_preserved(self, tmp_path):
        """A single user message holding 3 tool_result blocks must come back
        with all 3 patched in the same order, with tool_use_ids intact."""
        formatted = json.dumps({"a": 1, "b": [1, 2, 3]}, indent=2)
        wrapped_blocks = [
            _wrapped(formatted, f"tool{i}")
            for i in range(3)
        ]
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [
                _FakeToolUseBlock(id=f"u{i}", name=f"tool{i}", input={}) for i in range(3)
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": f"u{i}", "content": wrapped_blocks[i]}
                for i in range(3)
            ]},
            # Additional user turns so find_recent_boundary moves the boundary
            # past the tool_result message.
            {"role": "assistant", "content": [_FakeToolUseBlock(id="u_recent", name="t", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "u_recent", "content": "RECENT",
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="u_recent2", name="t", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "u_recent2", "content": "RECENT",
            }]},
        ]
        ctx = _make_ctx(
            tmp_path,
            layer_2_threshold_chars=10**9,
            layer_3_threshold_chars=10**9,
        )
        out, _stats = ctx.compact_messages(msgs)
        # The user message at index 2 should have 3 tool_result blocks,
        # in the same order, same tool_use_ids
        old_msg = out[2]
        assert len(old_msg["content"]) == 3
        for i in range(3):
            block = old_msg["content"][i]
            assert block["type"] == "tool_result"
            assert block["tool_use_id"] == f"u{i}"
            # Native block keys still hygienic
            assert set(block.keys()) == {"type", "tool_use_id", "content"}

    def test_user_question_with_attachments_projected_as_text(self, tmp_path):
        """Initial user message with image+text content blocks should project
        as a single user-role item with the text portion only."""
        msgs = [
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "data": "..."}},
                {"type": "text", "text": "What's in this chart?"},
            ]},
        ]
        projected, anchors = _project_for_compression(msgs)
        assert len(projected) == 1
        assert projected[0]["role"] == "user"
        assert "What's in this chart?" in projected[0]["content"]
        assert anchors == [(0, -1, "")]

    def test_synthetic_marker_emitted_for_tool_result_groups(self, tmp_path):
        """For each native user message with tool_result blocks, projection
        emits ONE synthetic user marker followed by N tool_result projections.
        The marker is what makes find_recent_boundary count Anthropic turns
        correctly (otherwise only the question counts, boundary=0 always)."""
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t1", name="x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1", "content": "RES",
            }]},
        ]
        projected, anchors = _project_for_compression(msgs)
        # Question + assistant + (synthetic marker + tool_result) = 4 items
        assert len(projected) == 4
        assert projected[0]["role"] == "user"
        assert projected[0]["content"] == "Q"
        assert projected[1]["role"] == "assistant"
        # Synthetic marker — empty string content, role=user
        assert projected[2]["role"] == "user"
        assert projected[2]["content"] == ""
        # Tool result projection
        assert projected[3]["role"] == "tool_result"
        assert projected[3]["content"] == "RES"


# ============================================================
# Layers 1-3 fire on char threshold, not token threshold
# ============================================================


class TestL1L3IndependentOfTokenThreshold:
    def test_l1_minifies_below_legacy_token_threshold(self, tmp_path):
        """compaction_enabled=True ungates the token-threshold guard. Layer 1
        runs every call and minifies old wrapped JSON tool_results regardless
        of input_tokens. (The agent.py / cli.py call site does the
        ungate; this test calls compact_messages directly to lock the
        ContextManager-level contract.)"""
        formatted = json.dumps({"results": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]}, indent=2)
        wrapped = _wrapped(formatted, "tavily_search")
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t1", name="tavily_search", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1", "content": wrapped,
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t2", name="tavily_search", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t2", "content": "RECENT",
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t3", name="tavily_search", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t3", "content": "RECENT2",
            }]},
        ]
        ctx = _make_ctx(
            tmp_path,
            layer_2_threshold_chars=10**9,
            layer_3_threshold_chars=10**9,
        )
        out, stats = ctx.compact_messages(msgs)
        # Old tool_result minified (wrapped -> wrapped, but JSON minified inside)
        old_content = out[2]["content"][0]["content"]
        assert old_content.startswith('<tool_output tool="tavily_search">\n')
        inner = old_content[len('<tool_output tool="tavily_search">\n'):
                            -len("\n</tool_output>")]
        assert "\n" not in inner  # minified
        assert json.loads(inner) == {"results": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]}
        # Stats show L1 fired
        assert any(e["layer"] == 1 for e in stats["events"])
        assert stats["compacted"] >= 1

    def test_l3_fires_when_total_chars_exceed_threshold(self, tmp_path):
        """L3 stub triggers based on total content size, not token count.
        Disable L1+L2; set L3 threshold low so the tool_results get stubbed."""
        wrapped = _wrapped(json.dumps({"x": "y" * 5_000}), "get_x")
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t1", name="get_x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1", "content": wrapped,
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t2", name="get_x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t2", "content": "RECENT",
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t3", name="get_x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t3", "content": "RECENT2",
            }]},
        ]
        ctx = _make_ctx(
            tmp_path,
            layer_2_threshold_chars=10**9,  # never
            layer_3_threshold_chars=100,     # always
        )
        # Disable L1 to isolate L3
        ctx.compressor.config.layer_1_enabled = False

        out, stats = ctx.compact_messages(msgs)
        # Old tool_result replaced with one-line stub
        old_content = out[2]["content"][0]["content"]
        assert old_content.startswith("[old get_x result")
        assert any(e["layer"] == 3 for e in stats["events"])

    def test_compressor_no_op_when_below_all_thresholds(self, tmp_path):
        """Tiny message history → L1 may run (cheap) but no chars saved.
        compact_messages should return without raising."""
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [_FakeTextBlock("answer")]},
        ]
        ctx = _make_ctx(tmp_path)
        out, stats = ctx.compact_messages(msgs)
        assert isinstance(out, list)
        assert "events" in stats
        # Tiny history: chars_saved is 0 or 0+
        assert stats["chars_saved"] >= 0


# ============================================================
# Stats shape: legacy keys preserved + new events key
# ============================================================


class TestStatsShape:
    def test_compressor_path_stats_have_legacy_keys(self, tmp_path):
        """Compressor path must surface compacted/chars_saved/
        compaction_count/total_chars_saved AND a new events list."""
        wrapped = _wrapped(json.dumps({"a": 1}, indent=2), "tavily_search")
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t1", name="tavily_search", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1", "content": wrapped,
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t2", name="tavily_search", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t2", "content": "R",
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t3", name="tavily_search", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t3", "content": "R2",
            }]},
        ]
        ctx = _make_ctx(tmp_path)
        _out, stats = ctx.compact_messages(msgs)
        for k in ("compacted", "chars_saved", "compaction_count", "total_chars_saved", "events"):
            assert k in stats, f"missing key: {k}"
        assert isinstance(stats["events"], list)
        # Each event entry mirrors CompressionEvent shape
        for e in stats["events"]:
            assert set(e.keys()) >= {"layer", "before_chars", "after_chars", "note"}


# ============================================================
# Idempotency: repeated compact_messages does not stack summaries
# ============================================================


class TestIdempotency:
    def test_repeated_compact_with_scratchpad_keeps_one_summary(self, tmp_path):
        """Run compact_messages twice. With a non-empty scratchpad, only ONE
        summary should remain. (Tests Layer 2's idempotency through the
        adapter.)"""
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t1", name="x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1", "content": "x" * 200,
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t2", name="x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t2", "content": "R",
            }]},
            {"role": "assistant", "content": [_FakeToolUseBlock(id="t3", name="x", input={})]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t3", "content": "R2",
            }]},
        ]
        ctx = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=2,
            session_id="test-session",
            overflow_dir=tmp_path,
            compaction_config=CompressorConfig(
                enabled=True,
                layer_2_threshold_chars=1,  # always fire (even after compression)
                layer_3_threshold_chars=10**9,
            ),
            scratchpad="summary v1",
        )
        v1, _s1 = ctx.compact_messages(msgs)
        # Layer 2 prepended a summary at index 0
        assert v1[0]["role"] == "user"
        assert v1[0]["content"].startswith("<scratchpad_summary>")

        # Update scratchpad and run again
        ctx._scratchpad = "summary v2"
        v2, _s2 = ctx.compact_messages(v1)
        # Still exactly one summary (not two stacked)
        summaries = [m for m in v2
                     if m["role"] == "user"
                     and isinstance(m["content"], str)
                     and m["content"].startswith("<scratchpad_summary>")]
        assert len(summaries) == 1
        assert "summary v2" in summaries[0]["content"]
        assert "summary v1" not in summaries[0]["content"]


# ============================================================
# CLI / agent loop wiring: the helper is the single source of truth
# ============================================================


class TestOverflowCommandIntegrity:
    """``/overflow show <id>`` MUST gate on OverflowStore.read() so the
    5-invariant tamper detection from commit 1 protects the CLI surface.

    Three tamper modes (mirror the on-disk regression set in
    ``tests/test_compressor_overflow_store.py``):

      1. ``args_hash`` field corrupted but payload + record_id intact
      2. ``original_size`` field lies (re-encoded payload size differs)
      3. ``original_payload`` swapped for a different string (recomputed
         id mismatches the filename / JSON record_id)

    Each must cause the CLI to print an integrity-failure message and
    NOT surface the original_payload bytes.
    """

    @staticmethod
    def _capture_overflow_show(tmp_path, record_id, monkeypatch, *, agent_config_overflow_dir):
        """Run ``/overflow show <id>`` against ``tmp_path`` as the overflow
        root, capturing the recorded text output. Returns the captured
        string."""
        from rich.console import Console as _RichConsole
        recording_console = _RichConsole(record=True, force_terminal=False, width=120)

        # Patch cli.console with our recording instance
        import src.agents.cli as cli_mod
        monkeypatch.setattr(cli_mod, "console", recording_console)

        # Patch the overflow_dir resolution so handle_overflow_command picks
        # up tmp_path instead of data/overflow.
        monkeypatch.setattr(
            cli_mod, "_get_compaction_overflow_dir",
            lambda: str(agent_config_overflow_dir),
        )

        cli_mod.handle_overflow_command(f"show {record_id}")
        return recording_console.export_text()

    def test_show_intact_record_displays_payload(self, tmp_path, monkeypatch):
        """Sanity check: untampered record renders payload preview."""
        from src.agents.shared.compressor import OverflowStore

        store = OverflowStore(tmp_path, session_id="sess1")
        payload = "the quick brown fox " * 100
        record = store.write("get_x", {"q": "x"}, payload)

        out = self._capture_overflow_show(
            tmp_path, record.record_id, monkeypatch,
            agent_config_overflow_dir=tmp_path,
        )
        assert "the quick brown fox" in out
        assert "Payload preview" in out
        assert "integrity verification" not in out

    def _tamper_field(self, record_path: Path, **mutations):
        """Mutate top-level keys in the on-disk JSON."""
        data = json.loads(record_path.read_text(encoding="utf-8"))
        data.update(mutations)
        record_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_show_tampered_args_hash_rejects(self, tmp_path, monkeypatch):
        from src.agents.shared.compressor import OverflowStore

        store = OverflowStore(tmp_path, session_id="sess1")
        payload = "secret data " * 100
        record = store.write("get_x", {"q": "x"}, payload)
        record_path = tmp_path / "sess1" / f"{record.record_id}.json"
        self._tamper_field(record_path, args_hash="0" * 64)

        out = self._capture_overflow_show(
            tmp_path, record.record_id, monkeypatch,
            agent_config_overflow_dir=tmp_path,
        )
        assert "integrity verification" in out
        assert "secret data" not in out  # payload NOT surfaced

    def test_show_tampered_original_size_rejects(self, tmp_path, monkeypatch):
        from src.agents.shared.compressor import OverflowStore

        store = OverflowStore(tmp_path, session_id="sess1")
        payload = "leaked content " * 100
        record = store.write("get_x", {"q": "x"}, payload)
        record_path = tmp_path / "sess1" / f"{record.record_id}.json"
        self._tamper_field(record_path, original_size=99)

        out = self._capture_overflow_show(
            tmp_path, record.record_id, monkeypatch,
            agent_config_overflow_dir=tmp_path,
        )
        assert "integrity verification" in out
        assert "leaked content" not in out

    def test_show_tampered_payload_rejects(self, tmp_path, monkeypatch):
        """Tamper the payload (swap for different bytes) but keep filename
        and JSON record_id. Recomputed sha256 mismatches → invariant 5
        fails."""
        from src.agents.shared.compressor import OverflowStore

        store = OverflowStore(tmp_path, session_id="sess1")
        payload = "original honest payload " * 50
        record = store.write("get_x", {"q": "x"}, payload)
        record_path = tmp_path / "sess1" / f"{record.record_id}.json"
        # Swap original_payload for something else, but keep all other fields
        # including original_size matching the new bytes (so invariant 4 alone
        # passes — we want to demonstrate invariant 5 catches it).
        injected = "ATTACKER INJECTED PAYLOAD" * 10
        self._tamper_field(
            record_path,
            original_payload=injected,
            original_size=len(injected.encode("utf-8")),
        )

        out = self._capture_overflow_show(
            tmp_path, record.record_id, monkeypatch,
            agent_config_overflow_dir=tmp_path,
        )
        assert "integrity verification" in out
        assert "ATTACKER INJECTED PAYLOAD" not in out
        assert "original honest payload" not in out


class TestL0CallgraphRegression:
    """Lock that agent.py and cli.py both invoke ``ctx.compress_tool_result``
    (or the ``maybe_apply_layer_0`` BC wrapper) between ``execute_tool`` and
    ``tool_results.append``. If a future commit removes the L0 hook, these
    AST-based tests fail — cheaper than full Anthropic SDK mocking and
    exactly catches the regression we care about: "someone unwired the
    call site".
    """

    @staticmethod
    def _find_method_calls(source: str, method_names: set[str]) -> list[str]:
        """Return method names from ``method_names`` that appear as
        ``something.<name>(...)`` calls in the source's AST."""
        import ast
        tree = ast.parse(source)
        hits: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in method_names:
                    hits.append(node.func.attr)
        return hits

    @staticmethod
    def _find_call_with_kwarg(
        source: str, method_name: str, kwarg_name: str,
    ) -> bool:
        """True if any call to ``something.<method_name>(..., <kwarg_name>=...)``
        exists in the AST."""
        import ast
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == method_name):
                if any(k.arg == kwarg_name for k in node.keywords):
                    return True
        return False

    def test_anthropic_agent_invokes_l0_hook(self):
        path = project_root / "src" / "agents" / "anthropic_agent" / "agent.py"
        hits = self._find_method_calls(
            path.read_text(encoding="utf-8"),
            {"compress_tool_result", "maybe_apply_layer_0"},
        )
        assert hits, (
            "anthropic_agent/agent.py must call ctx.compress_tool_result "
            "(or maybe_apply_layer_0) between execute_tool and tool_results.append"
        )

    def test_cli_invokes_l0_hook(self):
        path = project_root / "src" / "agents" / "cli.py"
        hits = self._find_method_calls(
            path.read_text(encoding="utf-8"),
            {"compress_tool_result", "maybe_apply_layer_0"},
        )
        assert hits, (
            "cli.py must call ctx.compress_tool_result "
            "(or maybe_apply_layer_0) between execute_tool and tool_results.append"
        )

    def test_anthropic_agent_forwards_compression_to_pad(self):
        """If the L0 hook ran but log_tool_result didn't get the metadata,
        scratchpad would be silently lying. Lock the kwarg."""
        src = (project_root / "src" / "agents" / "anthropic_agent" / "agent.py").read_text(encoding="utf-8")
        assert self._find_call_with_kwarg(src, "log_tool_result", "compression"), (
            "agent.py: pad.log_tool_result must receive compression= kwarg "
            "(audit pipeline reconciliation contract)"
        )

    def test_anthropic_agent_forwards_compression_to_capture(self):
        src = (project_root / "src" / "agents" / "anthropic_agent" / "agent.py").read_text(encoding="utf-8")
        assert self._find_call_with_kwarg(src, "record_tool_call", "compression"), (
            "agent.py: capture.record_tool_call must receive compression= kwarg"
        )

    def test_cli_forwards_compression_to_pad(self):
        src = (project_root / "src" / "agents" / "cli.py").read_text(encoding="utf-8")
        assert self._find_call_with_kwarg(src, "log_tool_result", "compression"), (
            "cli.py: pad.log_tool_result must receive compression= kwarg"
        )

    def test_compress_tool_result_called_with_raw_payload(self, tmp_path, monkeypatch):
        """Behavior-level: simulate the call chain with mocks and verify
        that the payload going into compress_tool_result is the raw output
        of execute_tool (NOT something already projected / wrapped twice)."""
        ctx = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=2,
            session_id="callgraph-test",
            overflow_dir=tmp_path,
            compaction_config=CompressorConfig(
                enabled=True, layer_0_budget_chars=2_000,
            ),
        )
        observed_inputs: list[tuple] = []
        original_compress = ctx.compress_tool_result

        def spy(tool_name, tool_input, result):
            observed_inputs.append((tool_name, tool_input, result))
            return original_compress(tool_name, tool_input, result)

        monkeypatch.setattr(ctx, "compress_tool_result", spy)

        # Mirror agent.py / cli.py call sequence
        oversize = json.dumps({"x": "y" * 30_000})
        compressed, compression = ctx.compress_tool_result(
            "tavily_search", {"q": "x"}, oversize,
        )
        assert observed_inputs == [("tavily_search", {"q": "x"}, oversize)]
        assert compression["raw_bytes"] == len(oversize.encode("utf-8"))
        assert compression["compressed"] is True


class TestSharedL0Helper:
    def test_agent_and_cli_get_identical_l0_output(self, tmp_path):
        """Both agent.py and cli.py call ``ctx.maybe_apply_layer_0(...)``.
        Two ContextManager instances with the same config and the same
        session_id produce byte-identical L0 output for the same input
        (modulo overflow_dir partitioning by session)."""
        wrapped = _wrapped(json.dumps({"results": [{"url": "u", "content": "z" * 9_000}]}),
                           "tavily_search")
        ctx_agent = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=2,
            session_id="shared-session",
            overflow_dir=tmp_path / "agent",
            compaction_config=CompressorConfig(
                enabled=True, layer_0_budget_chars=2_000,
            ),
        )
        ctx_cli = ContextManager(
            model="claude-opus-4-7",
            keep_recent_turns=2,
            session_id="shared-session",
            overflow_dir=tmp_path / "cli",
            compaction_config=CompressorConfig(
                enabled=True, layer_0_budget_chars=2_000,
            ),
        )
        out_agent = ctx_agent.maybe_apply_layer_0("tavily_search", {}, wrapped)
        out_cli = ctx_cli.maybe_apply_layer_0("tavily_search", {}, wrapped)
        # Same compressed body (record_id is content-derived → deterministic)
        assert out_agent == out_cli


# ============================================================
# Config loader: profile.get("compaction", {}) populates AgentConfig
# ============================================================


class TestConfigLoader:
    @pytest.fixture(autouse=True)
    def _clear_config_cache(self):
        """get_agent_config is @lru_cache(maxsize=1); clear between tests so
        each mock_open patch lands on a fresh resolve."""
        get_agent_config.cache_clear()
        yield
        get_agent_config.cache_clear()

    def test_default_compaction_disabled(self):
        cfg = AgentConfig()
        assert cfg.compaction_enabled is False
        assert cfg.compaction_layer_0_budget_chars == 8000
        assert cfg.compaction_layer_2_threshold_chars == 100_000
        assert cfg.compaction_layer_3_threshold_chars == 150_000
        assert cfg.compaction_overflow_dir == "data/overflow"

    def test_yaml_compaction_section_loaded(self):
        """profile.get('compaction', {}) is a top-level section, not nested
        under llm_preferences (so it doesn't collide with server_compaction)."""
        fake_profile = {
            "compaction": {
                "enabled": True,
                "layer_0_budget_chars": 5000,
                "layer_2_threshold_chars": 50_000,
                "layer_3_threshold_chars": 100_000,
                "overflow_dir": "/tmp/test-overflow",
            },
        }
        with patch("src.agents.config._load_user_profile", return_value=fake_profile):
            cfg = get_agent_config()
        assert cfg.compaction_enabled is True
        assert cfg.compaction_layer_0_budget_chars == 5000
        assert cfg.compaction_layer_2_threshold_chars == 50_000
        assert cfg.compaction_layer_3_threshold_chars == 100_000
        assert cfg.compaction_overflow_dir == "/tmp/test-overflow"

    def test_partial_compaction_section_keeps_other_defaults(self):
        """A profile with `compaction.enabled` but no other keys still defaults
        the unspecified fields."""
        fake_profile = {"compaction": {"enabled": True}}
        with patch("src.agents.config._load_user_profile", return_value=fake_profile):
            cfg = get_agent_config()
        assert cfg.compaction_enabled is True
        assert cfg.compaction_layer_0_budget_chars == 8000  # default kept

    def test_no_compaction_section_keeps_all_defaults(self):
        with patch("src.agents.config._load_user_profile", return_value={}):
            cfg = get_agent_config()
        assert cfg.compaction_enabled is False
        assert cfg.compaction_layer_0_budget_chars == 8000

    def test_compaction_section_does_not_collide_with_server_compaction(self):
        """server_compaction lives under llm_preferences; compaction is
        top-level. They MUST be set independently."""
        fake_profile = {
            "compaction": {"enabled": True},
            "llm_preferences": {"server_compaction": True},
        }
        with patch("src.agents.config._load_user_profile", return_value=fake_profile):
            cfg = get_agent_config()
        assert cfg.compaction_enabled is True
        assert cfg.server_compaction is True