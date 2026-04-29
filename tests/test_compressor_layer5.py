"""P1.4 commit 5 — Layer 5 + Layer 6 tests.

Locks the new contracts:

  * ``compact_pre_call`` returns :class:`CompactionResult` with
    ``replace_prefix_to`` set when Layer 5 fires; ``None`` for
    Layer 1-3-only paths.
  * Layer 5 prefix-replacement: native cut respects safe-cut rule
    (back up only when target is a user-tool_result group).
  * Boundary edge cases: ``replace_prefix_to == 0`` → no-op;
    ``replace_prefix_to >= len(anchors)`` → no-op + warn (lock #1).
  * Force-flag (``/compact`` one-shot): consumed + cleared
    UNCONDITIONALLY at top of every ``compact_pre_call`` (lock #2).
  * /compact rejected when ``compaction.enabled=False`` (lock #2 + #3).
  * Layer 6 anchor: appended only when L5 fired AND
    ``anchor_data_provider`` returned non-empty; ≤ 1KB; not counted as
    a user turn by ``find_recent_boundary``; replaced (not stacked) on
    re-compaction.
  * Output cap: word + char cap applied IN CODE, not just prompt
    (lock #5). Char cap is a hard guarantee
    (``len(cap_summary(s)) <= LAYER_5_CHAR_CAP`` after marker reservation).
  * Reasoning passthrough (HIGH 2 / A4): projection labels thinking
    blocks; renderer emits ``[REASONING (verbatim)]`` /
    ``[REASONING DROPPED]``; LLM caller output is attached as a
    ``<compaction_summary>`` user message, NEVER as a thinking block.
  * Circuit breaker: 3 consecutive caller failures open the circuit;
    a successful call resets the counter to 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.shared.compressor import (
    AnthropicSummaryCaller,
    CompactionResult,
    CompressorConfig,
    ContextCompressor,
    FakeSummaryCaller,
    LAYER_5_CHAR_CAP,
    LAYER_5_WORD_CAP,
    apply_layer_5,
    apply_layer_6,
    build_layer_5_system_prompt,
    cap_summary,
    render_layer_5_transcript,
    wrap_anchor,
    wrap_compaction_summary,
)
from src.agents.shared.context_manager import (
    ContextManager,
    _apply_layer_5_prefix_replacement,
    _detach_anchor_msg,
    _detach_summary_msg,
    _extract_assistant_text,
    _find_safe_native_cut,
    build_anchor_from_messages,
)


# ============================================================
# Helpers
# ============================================================


class _FakeToolUseBlock:
    """Mimics SDK tool_use ContentBlock: .type/.id/.name/.input."""

    def __init__(self, *, id, name, input):
        self.type = "tool_use"
        self.id = id
        self.name = name
        self.input = input


class _FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeThinkingBlock:
    """Mimics Anthropic ThinkingBlock: .type=='thinking', .thinking=<str>."""

    def __init__(self, thinking: str):
        self.type = "thinking"
        self.thinking = thinking


class _FakeRedactedThinkingBlock:
    def __init__(self):
        self.type = "redacted_thinking"


def _make_compressor(tmp_path, **cfg_kwargs):
    """ContextCompressor with FakeSummaryCaller defaults — tests opt
    in to specific Layer 5 behaviour by passing different fakes."""
    config = CompressorConfig(**cfg_kwargs)
    return ContextCompressor(
        session_id="layer5-test",
        overflow_dir=tmp_path,
        config=config,
    )


# ============================================================
# Layer 5 prompt + transcript renderer (A4)
# ============================================================


class TestLayer5Prompt:
    def test_seven_sections_present_in_system_prompt(self):
        """spec §3.6.1: the system prompt MUST list all seven sections."""
        prompt = build_layer_5_system_prompt()
        for section in (
            "Active context",
            "Tool calls made",
            "Findings",
            "Open hypotheses",
            "Errors / data gaps",
            "Subagent results",
            "Pending tool calls",
        ):
            assert section in prompt, f"missing section: {section!r}"

    def test_prompt_locks_record_id_preservation(self):
        prompt = build_layer_5_system_prompt()
        assert "record_id" in prompt.lower()
        assert "preserve" in prompt.lower()

    def test_prompt_forbids_reasoning_passthrough(self):
        """spec A4: prompt rules must instruct the summarizer not to
        copy [REASONING (verbatim)] blocks into the summary."""
        prompt = build_layer_5_system_prompt()
        assert "[REASONING (verbatim)]" in prompt
        assert "do not" in prompt.lower() or "not be" in prompt.lower()

    def test_render_transcript_includes_prior_summary_tag(self):
        prior = "<compaction_summary>\nold facts about NVDA"
        transcript = render_layer_5_transcript(
            [{"role": "user", "content": "Q"}],
            prior_summary=prior,
        )
        assert "[PRIOR SUMMARY]" in transcript
        # Marker stripped — body included verbatim
        assert "old facts about NVDA" in transcript
        assert "<compaction_summary>" not in transcript


# ============================================================
# Reasoning passthrough — HIGH 2 / A4
# ============================================================


class TestReasoningPassthrough:
    def test_projection_does_not_paraphrase_thinking_as_assistant_text(self):
        """A4: thinking + text in an assistant message project as a
        single string with the thinking wrapped in
        ``[REASONING (verbatim)]...[/REASONING]`` — never merged into
        prose, never dropped."""
        content = [
            _FakeThinkingBlock("the agent is reasoning about NVDA"),
            _FakeTextBlock("Here is the answer."),
        ]
        out = _extract_assistant_text(content)
        assert "[REASONING (verbatim)]" in out
        assert "the agent is reasoning about NVDA" in out
        assert "[/REASONING]" in out
        assert "Here is the answer." in out
        # Order preserved (thinking before text)
        assert out.index("[REASONING (verbatim)]") < out.index("Here is the answer.")

    def test_projection_renders_redacted_thinking_as_dropped(self):
        """A4: redacted thinking → ``[REASONING DROPPED]`` marker only.
        We never invent the redacted content."""
        content = [
            _FakeRedactedThinkingBlock(),
            _FakeTextBlock("Public answer."),
        ]
        out = _extract_assistant_text(content)
        assert "[REASONING DROPPED]" in out
        assert "Public answer." in out

    def test_projection_handles_dict_form_thinking(self):
        """Anthropic SDK sometimes returns dicts (e.g. from JSON
        serialization round-trips). Both shapes must work identically."""
        content = [
            {"type": "thinking", "thinking": "dict-form reasoning"},
            {"type": "text", "text": "answer"},
        ]
        out = _extract_assistant_text(content)
        assert "[REASONING (verbatim)]" in out
        assert "dict-form reasoning" in out
        assert "answer" in out

    def test_summary_caller_output_attached_as_user_summary_not_reasoning(self, tmp_path):
        """Even if the summarizer LLM returns prose that LOOKS like
        reasoning, our pipe attaches it as a ``<compaction_summary>``
        user message — never as a thinking/reasoning block on the next
        turn. This is the only piece we control; we cannot control what
        the LLM emits."""
        fake_caller = FakeSummaryCaller([
            "the agent appears to think NVDA is bullish; users should buy",
        ])
        c = _make_compressor(
            tmp_path,
            layer_1_enabled=False,
            layer_5_enabled=True,
            layer_5_threshold_chars=1,
        )
        c._summary_caller = fake_caller
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
        ]
        result = c.compact_pre_call(msgs)
        # The summary IS at messages[0] but as a user message with
        # ``<compaction_summary>`` marker — NOT a thinking block
        # masquerading as agent reasoning.
        assert result.replace_prefix_to is not None
        assert result.messages[0]["role"] == "user"
        assert result.messages[0]["content"].startswith("<compaction_summary>")
        # The reasoning-flavoured prose IS in the content (the caller
        # returned it) but it lives inside a user message, not a
        # ContentBlock with type=thinking.
        for m in result.messages:
            # No projected message has a thinking shape — that would be
            # a security problem since the agent's own reasoning is
            # signature-protected by the SDK.
            assert m.get("role") != "thinking"


# ============================================================
# cap_summary — MED 5 (hard cap in code, not prompt)
# ============================================================


class TestCapSummary:
    def test_word_cap_truncates_with_marker(self):
        # Use single-char words so total chars stay under char cap; this
        # isolates the word-cap path (otherwise char cap fires first for
        # any realistic 2500-word string).
        long = " ".join(["x"] * (LAYER_5_WORD_CAP + 500))
        capped = cap_summary(long)
        assert "[TRUNCATED:word_cap=" in capped
        # First LAYER_5_WORD_CAP tokens after split() are still 'x'
        body_words = capped.split()[:LAYER_5_WORD_CAP]
        assert all(w == "x" for w in body_words)

    def test_char_cap_is_hard(self):
        """Marker bytes reserved BEFORE truncation so the final size is
        always ≤ LAYER_5_CHAR_CAP. Fuzz a few sizes."""
        for over in (1, 100, 5_000, 50_000):
            input_text = "x" * (LAYER_5_CHAR_CAP + over)
            capped = cap_summary(input_text)
            assert len(capped) <= LAYER_5_CHAR_CAP, (
                f"char cap violated: {len(capped)} > {LAYER_5_CHAR_CAP} "
                f"for input over=+{over}"
            )
            assert "[TRUNCATED:char_cap=" in capped

    def test_no_cap_for_compliant_summary(self):
        compliant = "short summary"
        assert cap_summary(compliant) == compliant


# ============================================================
# Layer 5 firing + circuit breaker
# ============================================================


class TestLayer5Firing:
    def test_layer_5_default_off(self, tmp_path):
        """Without explicit layer_5_enabled, even huge messages don't
        trigger L5 — Layer 3 stub is the fallback."""
        c = _make_compressor(
            tmp_path,
            layer_5_enabled=False,
            layer_5_threshold_chars=1,
            layer_3_threshold_chars=10**9,
        )
        c._summary_caller = FakeSummaryCaller(["should-not-be-called"])
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "a" * 5_000},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
        ]
        result = c.compact_pre_call(msgs)
        assert result.replace_prefix_to is None
        # Caller queue intact — never invoked
        assert c._summary_caller.calls == []

    def test_layer_5_fires_when_enabled_and_threshold_exceeded(self, tmp_path):
        c = _make_compressor(
            tmp_path,
            layer_1_enabled=False,
            layer_5_enabled=True,
            layer_5_threshold_chars=1,
        )
        c._summary_caller = FakeSummaryCaller(["compact summary v1"])
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
        ]
        result = c.compact_pre_call(msgs)
        assert result.replace_prefix_to is not None
        assert 5 in result.layers_fired
        assert result.messages[0]["content"].startswith("<compaction_summary>")
        assert "compact summary v1" in result.messages[0]["content"]

    def test_circuit_breaker_after_3_failures(self, tmp_path):
        """spec §3.6: 3 consecutive caller-None responses open the
        circuit; subsequent calls skip Layer 5 and rely on L3."""
        c = _make_compressor(
            tmp_path,
            layer_1_enabled=False,
            layer_5_enabled=True,
            layer_5_threshold_chars=1,
            circuit_breaker_max_failures=3,
        )
        c._summary_caller = FakeSummaryCaller([None, None, None, "should-not-fire"])
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
        ]
        for _ in range(3):
            res = c.compact_pre_call(msgs)
            assert res.replace_prefix_to is None  # all failed
        assert c.layer_5_circuit_open is True
        # Fourth call: circuit open → caller NOT invoked
        res4 = c.compact_pre_call(msgs)
        # FakeSummaryCaller.calls count records ONLY actually-invoked
        # calls; on the 4th compact_pre_call, the gating check skipped it.
        assert len(c._summary_caller.calls) == 3

    def test_circuit_resets_on_success(self, tmp_path):
        c = _make_compressor(
            tmp_path,
            layer_1_enabled=False,
            layer_5_enabled=True,
            layer_5_threshold_chars=1,
            circuit_breaker_max_failures=3,
        )
        # Fail twice, then succeed — counter should reset to 0
        c._summary_caller = FakeSummaryCaller([None, None, "ok summary"])
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
        ]
        c.compact_pre_call(msgs)
        c.compact_pre_call(msgs)
        assert c._layer_5_consecutive_failures == 2
        # On success, the prefix replacement happens — feed a fresh msgs
        # so we have something to compact (Q3 was kept "recent").
        c.compact_pre_call(msgs)
        assert c._layer_5_consecutive_failures == 0
        assert c.layer_5_circuit_open is False


# ============================================================
# Force-flag — lock #2 (consume + clear UNDER ALL CONDITIONS)
# ============================================================


class TestForceLayer5Flag:
    def _msgs(self):
        return [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
        ]

    def test_force_flag_consumed_on_success(self, tmp_path):
        c = _make_compressor(
            tmp_path, layer_1_enabled=False,
            layer_5_enabled=False,  # auto path off
            layer_5_threshold_chars=10**9,  # auto path also off
        )
        c._summary_caller = FakeSummaryCaller(["forced summary"])
        c.force_layer_5_once = True
        result = c.compact_pre_call(self._msgs())
        assert result.replace_prefix_to is not None  # forced fire happened
        assert c.force_layer_5_once is False  # cleared

    def test_force_flag_cleared_when_caller_missing(self, tmp_path):
        """Lock #2: caller missing → flag still consumed + cleared."""
        c = _make_compressor(
            tmp_path, layer_1_enabled=False,
            layer_5_enabled=False, layer_5_threshold_chars=10**9,
        )
        # No summary_caller set — c._summary_caller stays None
        assert c._summary_caller is None
        c.force_layer_5_once = True
        result = c.compact_pre_call(self._msgs())
        assert result.replace_prefix_to is None  # didn't fire
        assert c.force_layer_5_once is False  # but flag cleared

    def test_force_flag_cleared_when_circuit_open(self, tmp_path):
        c = _make_compressor(
            tmp_path, layer_1_enabled=False,
            layer_5_enabled=False, layer_5_threshold_chars=10**9,
            circuit_breaker_max_failures=1,
        )
        c._summary_caller = FakeSummaryCaller([None, "should-not-fire"])
        # Trigger one failure to open circuit
        c.force_layer_5_once = True
        c.compact_pre_call(self._msgs())
        assert c.layer_5_circuit_open is True
        # Re-arm — flag should still be cleared even though circuit blocks fire
        c.force_layer_5_once = True
        result = c.compact_pre_call(self._msgs())
        assert result.replace_prefix_to is None
        assert c.force_layer_5_once is False

    def test_force_flag_cleared_when_master_disabled(self, tmp_path):
        c = _make_compressor(
            tmp_path, enabled=False,  # master OFF
            layer_5_enabled=False, layer_5_threshold_chars=10**9,
        )
        c._summary_caller = FakeSummaryCaller(["should-not-fire"])
        c.force_layer_5_once = True
        result = c.compact_pre_call(self._msgs())
        assert result.replace_prefix_to is None
        assert c.force_layer_5_once is False  # cleared even on master-off path


# ============================================================
# Boundary edge cases — lock #1
# ============================================================


class TestPrefixReplacementBoundary:
    def test_replace_prefix_to_zero_is_noop(self, tmp_path):
        """Layer 5 returning replace_prefix_to=0 → adapter no-op."""
        body_messages = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "a"},
        ]
        result = CompactionResult(
            messages=[{"role": "user", "content": "<compaction_summary>\nfoo"}],
            replace_prefix_to=0,
        )
        anchors = [(0, -1, ""), (1, -1, "")]
        compressed = result.messages
        out = _apply_layer_5_prefix_replacement(
            body_messages, result, anchors, compressed,
        )
        assert out == body_messages

    def test_replace_prefix_to_out_of_range_is_noop(self, tmp_path):
        """B >= len(anchors) → bail to no-op + warn (no IndexError)."""
        body_messages = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "a"},
        ]
        result = CompactionResult(
            messages=[{"role": "user", "content": "<compaction_summary>\nfoo"}],
            replace_prefix_to=99,
        )
        anchors = [(0, -1, ""), (1, -1, "")]
        out = _apply_layer_5_prefix_replacement(
            body_messages, result, anchors, result.messages,
        )
        assert out == body_messages


# ============================================================
# Safe-cut — lock #2 (back up only for tool_result groups)
# ============================================================


class TestSafeNativeCut:
    def test_back_up_for_tool_result_group(self):
        """If target is user-with-tool_results, back up to include the
        prior assistant (which holds the matching tool_use blocks)."""
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [
                _FakeToolUseBlock(id="t1", name="x", input={}),
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "RES"},
            ]},
            {"role": "assistant", "content": "a3"},
            {"role": "user", "content": "Q4"},
        ]
        # Target: index 2 (user-tool_result)
        cut = _find_safe_native_cut(msgs, 2)
        # Backed up to include the prior assistant
        assert cut == 1

    def test_no_back_up_for_plain_user_text(self):
        msgs = [
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "plain question"},
        ]
        cut = _find_safe_native_cut(msgs, 1)
        assert cut == 1  # cut AT the user message, no back-up

    def test_no_back_up_for_attachment_user_msg(self):
        """User messages with attachments + text (list-content but NO
        tool_result blocks) should NOT trigger the back-up rule."""
        msgs = [
            {"role": "assistant", "content": "intro"},
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "data": "..."}},
                {"type": "text", "text": "What's in this chart?"},
            ]},
        ]
        cut = _find_safe_native_cut(msgs, 1)
        assert cut == 1  # not a tool_result group → no back-up

    def test_no_back_up_at_index_zero(self):
        msgs = [{"role": "user", "content": "Q"}]
        assert _find_safe_native_cut(msgs, 0) == 0


# ============================================================
# Layer 6 anchor
# ============================================================


class TestLayer6Anchor:
    def test_anchor_appended_with_tickers_and_record_ids(self):
        msgs = [{"role": "user", "content": "Q"}]
        anchor_data = {
            "tickers": ["NVDA", "TSLA"],
            "recent_record_ids": ["abcd1234deadbeef", "1111222233334444"],
        }
        out = apply_layer_6(msgs, anchor_data=anchor_data)
        assert len(out) == 2
        anchor = out[-1]
        assert anchor.get("is_anchor") is True
        assert anchor["content"].startswith("<anchor>")
        assert "NVDA" in anchor["content"]
        assert "TSLA" in anchor["content"]
        assert "abcd1234deadbeef" in anchor["content"]

    def test_anchor_block_under_1kb(self):
        """Even with absurdly long tickers, the anchor stays ≤ 1024 bytes."""
        msgs = [{"role": "user", "content": "Q"}]
        anchor_data = {
            "tickers": [f"TICKER{i:04d}" for i in range(200)],
            "recent_record_ids": [f"{i:016x}" for i in range(50)],
        }
        out = apply_layer_6(msgs, anchor_data=anchor_data)
        anchor = out[-1]
        encoded = anchor["content"].encode("utf-8")
        assert len(encoded) <= 1024, f"anchor exceeded 1KB: {len(encoded)}"
        assert "[TRUNCATED:anchor_cap=1024]" in anchor["content"]

    def test_anchor_no_op_for_empty_data(self):
        msgs = [{"role": "user", "content": "Q"}]
        out = apply_layer_6(msgs, anchor_data={})
        assert out == msgs

    def test_anchor_no_op_for_data_without_useful_keys(self):
        """``anchor_data`` may have unrelated keys; without tickers or
        record_ids there's nothing to anchor on."""
        msgs = [{"role": "user", "content": "Q"}]
        out = apply_layer_6(msgs, anchor_data={"random": "noise"})
        assert out == msgs

    def test_anchor_not_counted_as_user_turn(self):
        """``find_recent_boundary`` must skip anchors (lock #4) so they
        don't inflate the recent-turn count after Layer 5 fires."""
        from src.agents.shared.compressor import find_recent_boundary
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "<anchor>\ntickers: NVDA", "is_anchor": True},
        ]
        # 2 real user turns (u1, u2); keep 2 → boundary at u1's index 0
        assert find_recent_boundary(msgs, keep_recent_turns=2) == 0


# ============================================================
# Anchor + summary detach helpers (idempotency, lock #4)
# ============================================================


class TestDetachHelpers:
    def test_detach_recognises_compaction_summary(self):
        msgs = [
            {"role": "user", "content": "<compaction_summary>\nfacts"},
            {"role": "assistant", "content": "a"},
        ]
        summary, body = _detach_summary_msg(msgs)
        assert summary is not None
        assert summary["content"].startswith("<compaction_summary>")
        assert body == [{"role": "assistant", "content": "a"}]

    def test_detach_recognises_scratchpad_summary(self):
        msgs = [
            {"role": "user", "content": "<scratchpad_summary>\nfacts"},
            {"role": "assistant", "content": "a"},
        ]
        summary, body = _detach_summary_msg(msgs)
        assert summary is not None
        assert summary["content"].startswith("<scratchpad_summary>")

    def test_detach_anchor_strips_tail(self):
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "<anchor>\ntickers: NVDA"},
        ]
        anchor, body = _detach_anchor_msg(msgs)
        assert anchor is not None
        assert anchor["content"].startswith("<anchor>")
        assert body == [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "a"},
        ]

    def test_detach_anchor_no_op_when_not_present(self):
        msgs = [{"role": "user", "content": "Q"}]
        anchor, body = _detach_anchor_msg(msgs)
        assert anchor is None
        assert body == msgs


# ============================================================
# build_anchor_from_messages — Layer 6 data provider
# ============================================================


class TestBuildAnchorFromMessages:
    def test_extracts_ticker_from_tool_use_blocks(self):
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": [
                _FakeToolUseBlock(id="t1", name="get_x", input={"ticker": "NVDA"}),
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
            ]},
        ]
        data = build_anchor_from_messages(msgs)
        assert "NVDA" in data["tickers"]

    def test_extracts_tickers_list_from_tool_use(self):
        msgs = [
            {"role": "assistant", "content": [
                _FakeToolUseBlock(
                    id="t1", name="x", input={"tickers": ["AAPL", "MSFT"]},
                ),
            ]},
        ]
        data = build_anchor_from_messages(msgs)
        assert "AAPL" in data["tickers"] and "MSFT" in data["tickers"]

    def test_extracts_record_ids_from_tool_result_markers(self):
        msgs = [
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t1",
                "content": (
                    "summary text\n[overflow_record=abcd1234deadbeef, "
                    "original_size=10000]"
                ),
            }]},
        ]
        data = build_anchor_from_messages(msgs)
        assert "abcd1234deadbeef" in data["recent_record_ids"]

    def test_caps_tickers_and_record_ids(self):
        many_tickers = [f"T{i:03d}" for i in range(20)]
        msgs = [{"role": "assistant", "content": [
            _FakeToolUseBlock(id="t", name="x", input={"tickers": many_tickers}),
        ]}]
        data = build_anchor_from_messages(msgs, max_tickers=5)
        assert len(data["tickers"]) <= 5

    def test_empty_messages_returns_empty_dict(self):
        assert build_anchor_from_messages([]) == {}

    def test_messages_without_tickers_or_records_returns_empty(self):
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "answer"},
        ]
        assert build_anchor_from_messages(msgs) == {}


# ============================================================
# Layer 5 idempotency (re-compaction)
# ============================================================


class TestLayer5Idempotency:
    def test_repeated_compact_does_not_stack_summaries(self, tmp_path):
        """Two consecutive Layer 5 firings → only ONE
        ``<compaction_summary>`` user message remains. The second fire
        absorbs the first via the [PRIOR SUMMARY] tag.

        Models the real flow: round 1 collapses the prefix to a summary
        + tail, then the conversation continues (more user/assistant
        turns added), THEN round 2 fires and must replace the v1 summary
        rather than stack v2 on top of it.
        """
        c = _make_compressor(
            tmp_path,
            layer_1_enabled=False,
            layer_5_enabled=True,
            layer_5_threshold_chars=1,
        )
        c._summary_caller = FakeSummaryCaller(["v1 summary", "v2 summary"])
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "a3"},
            {"role": "user", "content": "Q4"},
            {"role": "assistant", "content": "a4"},
            {"role": "user", "content": "Q5"},
        ]
        r1 = c.compact_pre_call(msgs)
        # First fire: messages start with summary
        assert r1.messages[0]["content"].startswith("<compaction_summary>")
        assert "v1 summary" in r1.messages[0]["content"]

        # Continue the conversation: add more turns so round 2 has
        # enough tail to compact.
        round_2_input = list(r1.messages) + [
            {"role": "assistant", "content": "a5"},
            {"role": "user", "content": "Q6"},
            {"role": "assistant", "content": "a6"},
            {"role": "user", "content": "Q7"},
        ]
        r2 = c.compact_pre_call(round_2_input)
        # Still exactly one summary at index 0
        summaries = [
            m for m in r2.messages
            if isinstance(m, dict)
            and isinstance(m.get("content"), str)
            and m["content"].startswith("<compaction_summary>")
        ]
        assert len(summaries) == 1
        # And it's the v2 summary, not v1 stacked on top
        assert "v2 summary" in summaries[0]["content"]
        assert "v1 summary" not in summaries[0]["content"]

    def test_prior_summary_passed_to_caller(self, tmp_path):
        """Re-compaction passes the prior summary to the caller via the
        user prompt (transcript renderer adds [PRIOR SUMMARY] tag)."""
        c = _make_compressor(
            tmp_path,
            layer_1_enabled=False,
            layer_5_enabled=True,
            layer_5_threshold_chars=1,
        )
        c._summary_caller = FakeSummaryCaller(["v1", "v2"])
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "a3"},
            {"role": "user", "content": "Q4"},
            {"role": "assistant", "content": "a4"},
            {"role": "user", "content": "Q5"},
        ]
        r1 = c.compact_pre_call(msgs)
        # Continue the conversation so round 2 has tail to compact.
        round_2_input = list(r1.messages) + [
            {"role": "assistant", "content": "a5"},
            {"role": "user", "content": "Q6"},
            {"role": "assistant", "content": "a6"},
            {"role": "user", "content": "Q7"},
        ]
        c.compact_pre_call(round_2_input)
        # Second call's user prompt MUST contain [PRIOR SUMMARY]
        assert len(c._summary_caller.calls) >= 2, (
            f"expected 2 caller invocations, got {len(c._summary_caller.calls)}"
        )
        second_call = c._summary_caller.calls[1]
        assert "[PRIOR SUMMARY]" in second_call["user_prompt"]
        assert "v1" in second_call["user_prompt"]


# ============================================================
# Marker wrappers
# ============================================================


class TestMarkerWrappers:
    def test_wrap_compaction_summary_idempotent(self):
        wrapped = wrap_compaction_summary("body text")
        assert wrapped.startswith("<compaction_summary>\n")
        # Wrapping twice doesn't double-marker
        assert wrap_compaction_summary(wrapped) == wrapped

    def test_wrap_anchor_idempotent(self):
        wrapped = wrap_anchor("tickers: NVDA")
        assert wrapped.startswith("<anchor>\n")
        assert wrap_anchor(wrapped) == wrapped


# ============================================================
# AnthropicSummaryCaller — lightweight smoke
# ============================================================


class TestAnthropicSummaryCaller:
    def test_failure_returns_none_not_raise(self):
        """spec: caller MUST swallow exceptions and return None so the
        circuit breaker can advance the counter."""

        class _BoomClient:
            class messages:
                @staticmethod
                def stream(*a, **kw):
                    raise RuntimeError("API exploded")

        caller = AnthropicSummaryCaller(client=_BoomClient())
        out = caller(system_prompt="sys", user_prompt="usr")
        assert out is None

    def test_empty_response_returns_none(self):
        """spec: empty text → None (caller doesn't return blank
        summaries that would be wrapped + injected)."""

        class _Resp:
            content = []

        class _Stream:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def get_final_message(self_inner):
                return _Resp()

        class _Client:
            class messages:
                @staticmethod
                def stream(*a, **kw):
                    return _Stream()

        caller = AnthropicSummaryCaller(client=_Client())
        assert caller(system_prompt="s", user_prompt="u") is None

    def test_concatenates_text_blocks(self):
        class _Block:
            def __init__(self, text):
                self.text = text

        class _Resp:
            content = [_Block("part 1 "), _Block("part 2")]

        class _Stream:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def get_final_message(self_inner):
                return _Resp()

        class _Client:
            class messages:
                @staticmethod
                def stream(*a, **kw):
                    return _Stream()

        caller = AnthropicSummaryCaller(client=_Client())
        result = caller(system_prompt="s", user_prompt="u")
        assert result == "part 1 part 2"


# ============================================================
# /compact CLI handler — gating
# ============================================================


class TestCompactCommand:
    def test_compact_armed_when_master_enabled(self, monkeypatch):
        """/compact sets state.force_layer_5_next when compaction is on."""
        from src.agents.config import AgentConfig
        from src.agents.cli import handle_compact_command, SessionState

        cfg = AgentConfig()
        cfg.compaction_enabled = True
        monkeypatch.setattr("src.agents.cli.get_agent_config", lambda: cfg)
        # Suppress console output during test
        from rich.console import Console as _C
        recording = _C(record=True, force_terminal=False, width=80)
        monkeypatch.setattr("src.agents.cli.console", recording)

        state = SessionState(
            provider="anthropic", model=None, reasoning_effort=None,
            no_history=False, verbose=False,
        )
        assert state.force_layer_5_next is False
        handle_compact_command(state, "")
        assert state.force_layer_5_next is True
        out = recording.export_text()
        assert "armed" in out.lower()

    def test_compact_rejected_when_master_disabled(self, monkeypatch):
        """When compaction.enabled=False, /compact MUST refuse — flag
        stays False so a mistakenly-armed force can't sit forever."""
        from src.agents.config import AgentConfig
        from src.agents.cli import handle_compact_command, SessionState

        cfg = AgentConfig()
        cfg.compaction_enabled = False
        monkeypatch.setattr("src.agents.cli.get_agent_config", lambda: cfg)
        from rich.console import Console as _C
        recording = _C(record=True, force_terminal=False, width=80)
        monkeypatch.setattr("src.agents.cli.console", recording)

        state = SessionState(
            provider="anthropic", model=None, reasoning_effort=None,
            no_history=False, verbose=False,
        )
        handle_compact_command(state, "")
        assert state.force_layer_5_next is False
        out = recording.export_text()
        assert "rejected" in out.lower() or "off" in out.lower()

    def test_compact_rejected_for_openai_provider(self, monkeypatch):
        from src.agents.config import AgentConfig
        from src.agents.cli import handle_compact_command, SessionState

        cfg = AgentConfig()
        cfg.compaction_enabled = True
        monkeypatch.setattr("src.agents.cli.get_agent_config", lambda: cfg)
        from rich.console import Console as _C
        recording = _C(record=True, force_terminal=False, width=80)
        monkeypatch.setattr("src.agents.cli.console", recording)

        state = SessionState(
            provider="openai", model=None, reasoning_effort=None,
            no_history=False, verbose=False,
        )
        handle_compact_command(state, "")
        assert state.force_layer_5_next is False
        out = recording.export_text()
        assert "anthropic" in out.lower()

    def test_compact_idempotent_when_already_armed(self, monkeypatch):
        from src.agents.config import AgentConfig
        from src.agents.cli import handle_compact_command, SessionState

        cfg = AgentConfig()
        cfg.compaction_enabled = True
        monkeypatch.setattr("src.agents.cli.get_agent_config", lambda: cfg)
        from rich.console import Console as _C
        recording = _C(record=True, force_terminal=False, width=80)
        monkeypatch.setattr("src.agents.cli.console", recording)

        state = SessionState(
            provider="anthropic", model=None, reasoning_effort=None,
            no_history=False, verbose=False, force_layer_5_next=True,
        )
        handle_compact_command(state, "")
        assert state.force_layer_5_next is True
        out = recording.export_text()
        assert "already armed" in out.lower()


# ============================================================
# ContextManager — request_force_layer_5 helper
# ============================================================


class TestRequestForceLayer5:
    def test_returns_false_when_no_compressor(self):
        """ContextManager without compaction → can't force L5."""
        cm = ContextManager()
        assert cm.compressor is None
        assert cm.request_force_layer_5() is False

    def test_returns_true_and_sets_flag(self, tmp_path):
        cm = ContextManager(
            session_id="t",
            overflow_dir=tmp_path,
            compaction_config=CompressorConfig(enabled=True),
        )
        assert cm.compressor is not None
        assert cm.request_force_layer_5() is True
        assert cm.compressor.force_layer_5_once is True