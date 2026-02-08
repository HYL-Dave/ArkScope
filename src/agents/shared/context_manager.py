"""
Context management for agent message history (Phase 3).

Monitors token usage and compacts old tool results when context grows
too large. Follows §2.1 design principles:
- Simple queries: no compaction needed
- Records retrieval method (tool name + params) before discarding content
- Ephemeral content (tool results) compacted; persistent content
  (user intent, agent conclusions) preserved
- Recent turns always kept intact

Only applicable to Anthropic agent (manual messages loop).
OpenAI agent runs via SDK black box — no mid-run intervention.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# Model context window sizes (input tokens)
# Order matters: more specific prefixes first (prefix match)
_MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # Anthropic — https://docs.anthropic.com/en/docs/about-claude/models
    "claude-opus-4-6": 1_000_000,   # 2026-02, 1M context / 128K output
    "claude-opus-4-5": 200_000,     # 200K context / 64K output
    "claude-sonnet-4-5": 200_000,   # 200K context / 64K output
    "claude-sonnet-4": 200_000,
    "claude-opus-4": 200_000,
    "claude-haiku": 200_000,
    # OpenAI — https://platform.openai.com/docs/models
    "gpt-5.2": 400_000,             # 400K context / 128K output
    "gpt-5": 400_000,               # 400K context / 128K output
    "gpt-4": 128_000,
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

        ctx = ContextManager(model="claude-sonnet-4-5-20250929")

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
    ) -> None:
        """
        Args:
            model: Model name for context limit lookup.
            threshold_ratio: Compact when input_tokens > limit * ratio.
            keep_recent_turns: Number of recent turns to preserve fully.
                Each turn = 1 assistant message + 1 user/tool_result message.
            preview_chars: Characters to keep as preview in compacted results.
        """
        self.model = model
        self.threshold_ratio = threshold_ratio
        self.keep_recent_turns = keep_recent_turns
        self.preview_chars = preview_chars
        self._compaction_count = 0
        self._total_chars_saved = 0

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