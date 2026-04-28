"""
Context management for agent message history (Phase 3 + P1.4 commit 3).

Monitors token usage and compacts old tool results when context grows
too large. Follows §2.1 design principles:
- Simple queries: no compaction needed
- Records retrieval method (tool name + params) before discarding content
- Ephemeral content (tool results) compacted; persistent content
  (user intent, agent conclusions) preserved
- Recent turns always kept intact

Only applicable to Anthropic agent (manual messages loop).
OpenAI agent runs via SDK black box — no mid-run intervention.

P1.4 commit 3: when ``compaction_config`` is supplied with ``enabled=True``,
``compact_messages`` delegates to :class:`ContextCompressor` (Layers 0-3 lib).
The legacy single-layer path is preserved verbatim when the flag is off, so
existing tests in ``tests/test_context_manager.py`` keep passing.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .compressor import (
    CompressorConfig,
    ContextCompressor,
    ProjectedMessage,
)
from .compressor.layers import _SCRATCHPAD_SUMMARY_MARKER  # type: ignore[attr-defined]
from .token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# Matches the marker Layer 0 appends to summaries:
#   "...]\n[overflow_record=<16-hex>, original_size=<int>]"
_OVERFLOW_RECORD_RE = re.compile(r"\[overflow_record=([0-9a-f]{16})")

# Model context window sizes (input tokens)
# Order matters: more specific prefixes first (prefix match)
_MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # Anthropic — 1M context GA (no beta header, standard pricing)
    "claude-opus-4-7": 1_000_000,   # 1M context / 128K output ($5/$25)
    "claude-sonnet-4-6": 1_000_000, # 1M context / 64K output ($3/$15)
    "claude-haiku": 200_000,        # Haiku 4.5: 200K context / 64K output
    # OpenAI — https://developers.openai.com/api/docs/models
    "gpt-5.4-mini": 400_000,        # 400K context / 128K output ($0.75/$4.50)
    "gpt-5.4-nano": 400_000,        # 400K context / 128K output ($0.20/$1.25)
    "gpt-5.4": 1_050_000,           # 1M context / 128K output ($2.50/$15)
    "gpt-5.2": 400_000,             # 400K context / 128K output (legacy)
}

_DEFAULT_CONTEXT_LIMIT = 200_000

_COMPACT_MARKER = "[Compacted]"


def get_model_context_limit(model: str) -> int:
    """Get the context window size for a model (prefix match)."""
    for prefix, limit in _MODEL_CONTEXT_LIMITS.items():
        if model.startswith(prefix):
            return limit
    return _DEFAULT_CONTEXT_LIMIT


class ContextManager:
    """
    Smart context management for Anthropic agent message history.

    Monitors token usage via TokenTracker and compacts old tool results
    when the context approaches the model's limit.

    Usage::

        ctx = ContextManager(model="claude-opus-4-7")

        for turn in range(max_turns):
            response = client.messages.create(model=..., messages=messages)
            tracker.record_anthropic(response)

            # ... process response, append tool results to messages ...

            if ctx.should_compact(tracker):
                messages, stats = ctx.compact_messages(messages)
    """

    def __init__(
        self,
        model: str = "",
        threshold_ratio: float = 0.7,
        keep_recent_turns: int = 2,
        preview_chars: int = 200,
        *,
        session_id: str = "",
        overflow_dir: Optional[Path] = None,
        compaction_config: Optional[CompressorConfig] = None,
        scratchpad: str = "",
    ) -> None:
        """
        Args:
            model: Model name for context limit lookup.
            threshold_ratio: Compact when input_tokens > limit * ratio.
            keep_recent_turns: Number of recent turns to preserve fully.
                Each turn = 1 assistant message + 1 user/tool_result message.
            preview_chars: Characters to keep as preview in compacted results.
            session_id: Per-session id for overflow store partitioning. When
                empty AND ``compaction_config.enabled`` is True, the compressor
                is NOT instantiated (legacy path runs). Tests pass an explicit
                value; production wires ``pad.session_id`` through.
            overflow_dir: Disk root for L0 overflow records. Tests inject
                ``tmp_path``; production passes ``Path("data/overflow")``.
                Required when ``compaction_config.enabled`` is True.
            compaction_config: When provided AND ``enabled=True``, switches
                ``compact_messages`` to delegate Layers 0-3 to
                :class:`ContextCompressor`. None / disabled → legacy path.
            scratchpad: String passed to Layer 2. Default ``""`` keeps Layer 2
                a no-op in production (semantic summary builder is deferred).
                Tests pass explicit text to exercise L2.
        """
        self.model = model
        self.threshold_ratio = threshold_ratio
        self.keep_recent_turns = keep_recent_turns
        self.preview_chars = preview_chars
        self._compaction_count = 0
        self._total_chars_saved = 0

        # P1.4: instantiate ContextCompressor only when both flag is on AND we
        # have the bits we need (session id + overflow dir). Missing bits with
        # enabled=True is a config error — fall back to legacy and log loudly.
        self._scratchpad = scratchpad
        self._compressor: Optional[ContextCompressor] = None
        if compaction_config is not None and compaction_config.enabled:
            if not session_id or overflow_dir is None:
                logger.warning(
                    "ContextManager: compaction_config.enabled=True but "
                    "session_id=%r overflow_dir=%r; falling back to legacy path",
                    session_id, overflow_dir,
                )
            else:
                self._compressor = ContextCompressor(
                    session_id=session_id,
                    overflow_dir=Path(overflow_dir),
                    config=compaction_config,
                )

    @property
    def token_threshold(self) -> int:
        """Token count that triggers compaction."""
        return int(get_model_context_limit(self.model) * self.threshold_ratio)

    def should_compact(self, tracker: TokenTracker) -> bool:
        """
        Check if messages should be compacted.

        Returns True when there are enough turns to compact AND
        the last observed input token count exceeds the threshold.
        Simple queries (few turns) never trigger compaction.
        """
        # Need at least keep_recent + 1 turns to have something to compact
        if tracker.turn_count <= self.keep_recent_turns:
            return False
        return tracker.last_input_tokens > self.token_threshold

    def compact_messages(
        self,
        messages: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Compact old tool results in message history.

        Routes to one of two implementations:

          - Legacy single-layer (default): preview-based replacement, in-place
            mutation, behaviour unchanged from Phase 3.
          - P1.4 compressor (when ``compaction_config.enabled``): delegates to
            :class:`ContextCompressor` (Layers 1-3 via patch-based projection
            adapter). Returns a NEW list; native assistant ContentBlock objects
            are never mutated.

        Stats shape is conservative across both paths — the four legacy keys
        (``compacted``, ``chars_saved``, ``compaction_count``,
        ``total_chars_saved``) are always present so existing logging/callers
        don't break. The compressor path additionally emits ``events`` (a
        list of dicts mirroring :class:`CompressionEvent`).
        """
        if self._compressor is not None:
            return self._compact_messages_compressor(messages)
        return self._compact_messages_legacy(messages)

    # ── L0 hook (shared by agent.py and cli.py) ──────────────────

    def maybe_apply_layer_0(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        result: Any,
    ) -> str:
        """Run Layer 0 budget at tool_result insertion time.

        Returns the (possibly compressed) result string. When the compressor
        is not instantiated (flag off), returns ``str(result)`` unchanged so
        callers can use this helper unconditionally. The record_id, when one
        is written, is embedded inside the returned content via the
        ``[overflow_record=<id>, original_size=<n>]`` marker — callers do NOT
        need to attach it as a separate field on the tool_result block (and
        SHOULD NOT, since unknown keys may be rejected by the API).
        """
        result_str = result if isinstance(result, str) else str(result)
        if self._compressor is None:
            return result_str
        compressed, _record = self._compressor.process_tool_result(
            tool_name, tool_input, result_str,
        )
        return compressed

    @property
    def compressor(self) -> Optional[ContextCompressor]:
        """Underlying ContextCompressor (None when compaction disabled)."""
        return self._compressor

    # ── Legacy single-layer path (Phase 3, behaviour-frozen) ─────

    def _compact_messages_legacy(
        self,
        messages: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Compact old tool results in message history.

        Message structure (Anthropic):
          [0] user question (PERSISTENT — always kept)
          [1] assistant (turn 1: TextBlock + ToolUseBlock)
          [2] user/tool_results (turn 1 results — EPHEMERAL)
          [3] assistant (turn 2)
          [4] user/tool_results (turn 2 results — EPHEMERAL)
          ...
          [-2] assistant (latest turn)
          [-1] user/tool_results (latest turn results)

        Compaction zone: messages[1 : -keep_recent*2]
        Within this zone, only tool_result content is replaced.
        Assistant messages (with tool_use refs) are kept intact.

        Returns:
            (messages, stats) — messages list is modified in-place.
        """
        # Minimum messages to have something to compact:
        # 1 (user question) + keep_recent*2 (preserved tail) + at least 2 (one old turn)
        min_messages = 1 + self.keep_recent_turns * 2 + 2
        if len(messages) < min_messages:
            return messages, {"compacted": 0, "chars_saved": 0}

        keep_tail = self.keep_recent_turns * 2
        compact_end = len(messages) - keep_tail

        chars_saved = 0
        results_compacted = 0

        for i in range(1, compact_end):
            msg = messages[i]
            if msg["role"] != "user":
                continue

            content = msg.get("content")
            if not isinstance(content, list):
                continue

            # Get tool info from preceding assistant message
            tool_info = _extract_tool_info(messages, i)

            new_content = []
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_result":
                    new_content.append(item)
                    continue

                original = item.get("content", "")
                if not isinstance(original, str):
                    original = str(original)

                # Skip already-compacted results
                if original.startswith(_COMPACT_MARKER):
                    new_content.append(item)
                    continue

                original_len = len(original)

                # Build compact representation with retrieval method
                tool_id = item.get("tool_use_id", "")
                info = tool_info.get(tool_id, {})
                tool_name = info.get("name", "unknown_tool")
                tool_input = info.get("input", {})

                compact = _build_compact_summary(
                    tool_name, tool_input, original, self.preview_chars,
                )

                new_item = dict(item)
                new_item["content"] = compact
                new_content.append(new_item)

                saved = original_len - len(compact)
                if saved > 0:
                    chars_saved += saved
                    results_compacted += 1

            messages[i] = dict(msg, content=new_content)

        self._compaction_count += 1
        self._total_chars_saved += chars_saved

        stats = {
            "compacted": results_compacted,
            "chars_saved": chars_saved,
            "compaction_count": self._compaction_count,
            "total_chars_saved": self._total_chars_saved,
        }

        if results_compacted > 0:
            logger.info(
                f"Context compacted: {results_compacted} tool results, "
                f"~{chars_saved:,} chars saved"
            )

        return messages, stats

    # ── P1.4 compressor delegation path ──────────────────────────

    def _compact_messages_compressor(
        self,
        messages: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Delegate to :class:`ContextCompressor` (Layers 1-3) via patch-based
        projection. Returns a new list; native ContentBlock objects on
        assistant messages are preserved by identity (never mutated).

        Summary handling lives at this layer (NOT in the projection adapter)
        so the projection ↔ patch-back alignment stays 1:1 even across
        repeated compact_messages calls. The flow is:

          1. Detach a pre-existing summary at messages[0] if present.
          2. Project + compress the remaining body.
          3. Detach Layer-2-prepended summary from compressed (if any).
          4. Patch the body back; project anchors and body align 1:1.
          5. Re-attach the summary: a freshly-prepended one wins; else the
             pre-existing one is preserved; else no summary.
        """
        assert self._compressor is not None  # narrow

        # Snapshot events length so we report only THIS call's events.
        events_before = len(self._compressor.events)

        before_total = _native_total_chars(messages)

        # Step 1: detach pre-existing summary
        existing_summary, body_messages = _detach_summary_msg(messages)

        # Step 2: project + compress body
        projected, anchors = _project_for_compression(body_messages)
        compressed = self._compressor.compact_pre_call(
            projected, scratchpad=self._scratchpad,
        )

        # Step 3: detach Layer-2-prepended summary
        new_summary_str: Optional[str] = None
        compressed_body = compressed
        if compressed and compressed[0].get("is_compaction_summary"):
            new_summary_str = compressed[0].get("content", "")
            compressed_body = compressed[1:]

        # Step 4: patch body back
        new_body = _apply_compression_back(body_messages, compressed_body, anchors)

        # Step 5: re-attach summary
        if new_summary_str is not None:
            new_messages = [
                {"role": "user", "content": new_summary_str}
            ] + new_body
        elif existing_summary is not None:
            new_messages = [existing_summary] + new_body
        else:
            new_messages = new_body

        after_total = _native_total_chars(new_messages)
        chars_saved = max(0, before_total - after_total)

        compacted = _count_changed_tool_results(projected, compressed_body)

        self._compaction_count += 1
        self._total_chars_saved += chars_saved

        new_events = [
            {"layer": e.layer, "before_chars": e.before_chars,
             "after_chars": e.after_chars, "note": e.note}
            for e in self._compressor.events[events_before:]
        ]

        stats: Dict[str, Any] = {
            "compacted": compacted,
            "chars_saved": chars_saved,
            "compaction_count": self._compaction_count,
            "total_chars_saved": self._total_chars_saved,
            "events": new_events,
        }

        if new_events:
            layers = ",".join(str(e["layer"]) for e in new_events)
            logger.info(
                "Context compacted (compressor): layers=[%s] "
                "tool_results=%d ~%d chars saved",
                layers, compacted, chars_saved,
            )

        return new_messages, stats

    def summary(self) -> Dict[str, Any]:
        """Return compaction statistics."""
        return {
            "compaction_count": self._compaction_count,
            "total_chars_saved": self._total_chars_saved,
            "model": self.model,
            "threshold_tokens": self.token_threshold,
        }

    def __repr__(self) -> str:
        return (
            f"ContextManager(model={self.model}, "
            f"compactions={self._compaction_count}, "
            f"saved={self._total_chars_saved:,} chars)"
        )


# ── Internal helpers ──────────────────────────────────────────


def _extract_tool_info(
    messages: List[Dict[str, Any]], tool_result_idx: int,
) -> Dict[str, Dict[str, Any]]:
    """
    Extract tool name/input from the assistant message preceding a tool_result.

    Returns {tool_use_id: {"name": ..., "input": ...}}
    """
    if tool_result_idx < 1:
        return {}

    prev = messages[tool_result_idx - 1]
    if prev.get("role") != "assistant":
        return {}

    prev_content = prev.get("content", [])
    if not isinstance(prev_content, (list, tuple)):
        return {}

    info = {}
    for block in prev_content:
        # Anthropic SDK ContentBlock objects have .type, .id, .name, .input
        if getattr(block, "type", None) == "tool_use":
            block_id = getattr(block, "id", "")
            info[block_id] = {
                "name": getattr(block, "name", "unknown"),
                "input": getattr(block, "input", {}),
            }
    return info


def _build_compact_summary(
    tool_name: str,
    tool_input: Dict[str, Any],
    original: str,
    preview_chars: int,
) -> str:
    """Build a compact representation of a tool result."""
    params_str = ", ".join(
        f"{k}={_compact_value(v)}" for k, v in tool_input.items()
    ) if tool_input else ""

    preview = original[:preview_chars].replace("\n", " ").strip()
    if len(original) > preview_chars:
        preview += "..."

    return (
        f"{_COMPACT_MARKER} {tool_name}({params_str}) → {len(original)} chars.\n"
        f"Preview: {preview}"
    )


def _compact_value(v: Any) -> str:
    """Compact a value for parameter display."""
    if isinstance(v, str):
        if len(v) > 30:
            return f'"{v[:27]}..."'
        return f'"{v}"'
    return str(v)


# ── P1.4 patch-based projection adapter ──────────────────────────
#
# Anthropic native messages have heterogeneous content shapes:
#   {"role": "user", "content": "<question string>"}
#   {"role": "assistant", "content": [TextBlock, ToolUseBlock, ...]}
#   {"role": "user", "content": [{"type": "tool_result", ...}, ...]}
#
# The compressor library (Layers 1-3) operates on a flat
# ProjectedMessage list. We map both directions WITHOUT reconstructing
# assistant ContentBlock objects:
#
#   project: native -> ProjectedMessage list + anchors describing how
#            to patch back tool_result content strings.
#   apply:   take the (possibly transformed) ProjectedMessage list and
#            patch ONLY tool_result.content strings in user messages,
#            and (if Layer 2 prepended a summary) prepend a fresh
#            user message at the front. Assistant blocks are passed
#            through by identity.

_AnchorTuple = Tuple[int, int, str]
"""(msg_idx, content_idx, tool_use_id). content_idx == -1 means "this
projected message corresponds to a non-tool_result item — no patch back"."""


def _native_total_chars(messages: List[Dict[str, Any]]) -> int:
    """Sum content sizes across native messages (string OR list[block])."""
    total = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    inner = item.get("content") or item.get("text") or ""
                    if isinstance(inner, str):
                        total += len(inner)
                else:
                    text = getattr(item, "text", None)
                    if isinstance(text, str):
                        total += len(text)
    return total


def _extract_assistant_text(content: Any) -> str:
    """Pull plaintext from an assistant message's content for projection.

    Used only to give find_recent_boundary a stable ProjectedMessage to
    iterate over — we never patch this back into the native message.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: List[str] = []
    for item in content:
        # SDK ContentBlock objects expose .text on TextBlock
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
            continue
        if isinstance(item, dict) and item.get("type") == "text":
            t = item.get("text")
            if isinstance(t, str):
                parts.append(t)
    return "\n".join(parts)


def _project_for_compression(
    messages: List[Dict[str, Any]],
) -> Tuple[List[ProjectedMessage], List[_AnchorTuple]]:
    """Project Anthropic native messages to ProjectedMessage + anchors.

    Each native message produces 1+ projected messages:
      - user(string content): 1 ``{role:"user", content:<string>}``. Doubles
        as the boundary-counting marker for the question turn.
      - user(list with tool_result blocks): 1 synthetic
        ``{role:"user", content:""}`` marker (for ``find_recent_boundary``
        to count this as a user turn — Anthropic flow only has 1 natural
        user turn, but each tool_result group is a turn boundary), then
        1 ``{role:"tool_result", ...}`` per tool_result block.
      - user(list with non-tool_result blocks, e.g. attachments + text):
        1 ``{role:"user", content:<text>}`` extracted from the text blocks.
      - assistant: 1 ``{role:"assistant", content:<text>}`` (used only for
        boundary counting; never patched back).

    Anchors record ``(msg_idx, content_idx, tool_use_id)`` so the apply
    step knows where to drop transformed content strings back.
    ``content_idx == -1`` marks "no patch back required" (assistant text,
    user question, synthetic marker).

    Re-projection idempotency: a user-string message whose content starts
    with ``<scratchpad_summary>`` is projected with
    ``is_compaction_summary=True`` so find_recent_boundary skips it (and so
    apply_layer_2 replaces it instead of stacking another on top).
    """
    projected: List[ProjectedMessage] = []
    anchors: List[_AnchorTuple] = []

    # Build a tool_use_id -> tool_name map by walking once. This avoids the
    # per-message _extract_tool_info loop in the legacy path.
    tool_name_by_id: Dict[str, str] = {}
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, (list, tuple)):
            continue
        for block in content:
            if getattr(block, "type", None) == "tool_use":
                bid = getattr(block, "id", "") or ""
                bname = getattr(block, "name", "unknown") or "unknown"
                if bid:
                    tool_name_by_id[bid] = bname
            elif isinstance(block, dict) and block.get("type") == "tool_use":
                bid = block.get("id", "") or ""
                bname = block.get("name", "unknown") or "unknown"
                if bid:
                    tool_name_by_id[bid] = bname

    for msg_idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")

        if role == "user" and isinstance(content, str):
            pm: ProjectedMessage = {"role": "user", "content": content}
            if content.startswith(_SCRATCHPAD_SUMMARY_MARKER):
                pm["is_compaction_summary"] = True
            projected.append(pm)
            anchors.append((msg_idx, -1, ""))
            continue

        if role == "user" and isinstance(content, list):
            has_tool_results = any(
                isinstance(item, dict) and item.get("type") == "tool_result"
                for item in content
            )
            if has_tool_results:
                # Synthetic boundary marker — counted as a user turn by
                # find_recent_boundary. Layer 1/2/3 skip it (role != tool_result).
                projected.append({"role": "user", "content": ""})
                anchors.append((msg_idx, -1, ""))
                for ci, item in enumerate(content):
                    if not (isinstance(item, dict) and item.get("type") == "tool_result"):
                        continue
                    tool_use_id = item.get("tool_use_id", "") or ""
                    tool_name = tool_name_by_id.get(tool_use_id, "unknown")
                    content_str = item.get("content", "")
                    if not isinstance(content_str, str):
                        content_str = str(content_str)
                    pm = {
                        "role": "tool_result",
                        "tool_name": tool_name,
                        "content": content_str,
                    }
                    m = _OVERFLOW_RECORD_RE.search(content_str)
                    if m:
                        pm["overflow_record_id"] = m.group(1)
                    projected.append(pm)
                    anchors.append((msg_idx, ci, tool_use_id))
            else:
                # Attachments + text question — extract text portion only
                text_parts: List[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        t = item.get("text")
                        if isinstance(t, str):
                            text_parts.append(t)
                projected.append({"role": "user", "content": "\n".join(text_parts)})
                anchors.append((msg_idx, -1, ""))
            continue

        if role == "assistant":
            text = _extract_assistant_text(content)
            projected.append({"role": "assistant", "content": text})
            anchors.append((msg_idx, -1, ""))
            continue

    return projected, anchors


def _detach_summary_msg(
    messages: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """If ``messages[0]`` is a scratchpad summary user message, split it off.

    Returns ``(existing_summary, body_messages)``. The body is what the
    projection adapter walks; the summary is re-attached after Layer 2 has
    had a chance to prepend a fresh one (or kept as-is if Layer 2 didn't
    fire). This decoupling keeps the projection ↔ patch-back alignment
    1:1 even after repeated compact_messages calls.
    """
    if not messages or not isinstance(messages[0], dict):
        return None, list(messages)
    m0 = messages[0]
    if (m0.get("role") == "user"
            and isinstance(m0.get("content"), str)
            and m0["content"].startswith(_SCRATCHPAD_SUMMARY_MARKER)):
        return m0, list(messages[1:])
    return None, list(messages)


def _apply_compression_back(
    messages: List[Dict[str, Any]],
    compressed_body: List[ProjectedMessage],
    anchors: List[_AnchorTuple],
) -> List[Dict[str, Any]]:
    """Apply compressed ProjectedMessage body back to native messages.

    Only tool_result.content STRINGS are patched. Native ContentBlock
    objects (assistant tool_use, text blocks) and synthetic projection
    items (user-question, assistant text, synthetic markers) pass
    through unchanged.

    Note: this function does NOT handle the Layer 2 prepended summary —
    that's the caller's job (see ``_compact_messages_compressor``). Here,
    ``compressed_body`` is expected to align 1:1 with ``anchors``.
    """
    if len(compressed_body) != len(anchors):
        logger.warning(
            "Projection shape drift: body=%d anchors=%d — skipping patch back",
            len(compressed_body), len(anchors),
        )
        return list(messages)

    patches_by_msg: Dict[int, Dict[int, str]] = {}
    for anchor, pm in zip(anchors, compressed_body):
        msg_idx, content_idx, _ = anchor
        if content_idx < 0:
            continue
        if pm.get("role") != "tool_result":
            continue
        new_content = pm.get("content")
        if not isinstance(new_content, str):
            continue
        patches_by_msg.setdefault(msg_idx, {})[content_idx] = new_content

    out: List[Dict[str, Any]] = []
    for i, msg in enumerate(messages):
        if i in patches_by_msg and isinstance(msg.get("content"), list):
            patches = patches_by_msg[i]
            new_content_list = list(msg["content"])
            for ci, new_str in patches.items():
                if 0 <= ci < len(new_content_list) and isinstance(new_content_list[ci], dict):
                    item_copy = dict(new_content_list[ci])
                    item_copy["content"] = new_str
                    new_content_list[ci] = item_copy
            out.append({**msg, "content": new_content_list})
        else:
            out.append(msg)

    return out


def _count_changed_tool_results(
    projected: List[ProjectedMessage],
    compressed: List[ProjectedMessage],
) -> int:
    """Count tool_result projections whose content changed after compression.

    Accepts Layer 2's prepended summary (alignment offset of +1) without
    falsely counting it as a change. Cap at min(len) to avoid index errors.
    """
    offset = 0
    if compressed and compressed[0].get("is_compaction_summary"):
        offset = 1
    n = min(len(projected), len(compressed) - offset)
    if n <= 0:
        return 0
    changed = 0
    for i in range(n):
        a = projected[i]
        b = compressed[i + offset]
        if a.get("role") != "tool_result" or b.get("role") != "tool_result":
            continue
        if a.get("content") != b.get("content"):
            changed += 1
    return changed