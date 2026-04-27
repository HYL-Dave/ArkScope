"""Message transcript helpers (P1.4 commit 2 + 5).

Pure functions used by Layers 3 and 5:

  - :func:`find_recent_boundary` — given a list of projected messages
    and a ``keep_recent_turns`` count, return the index that splits
    "old" from "recent". Used by Layers 3 and 5 to know which slice
    to leave alone.
  - :func:`format_messages_as_transcript` — render a projected message
    list as a plain-text transcript suitable for an LLM summary prompt
    (Layer 5; used by tests in commit 2 to verify output shape).

Both functions treat compaction-summary items (``is_compaction_summary=True``)
specially: they're never counted toward "user turns" and they render
under a distinct ``[COMPACTION SUMMARY]`` tag — matching the marker
pattern from ``~/PycharmProjects/AI_Agent_Researcher`` so future
incremental compaction reads earlier markers as ground truth.
"""

from __future__ import annotations

from typing import Iterable, List

from .types import ProjectedMessage


def find_recent_boundary(
    messages: List[ProjectedMessage],
    *,
    keep_recent_turns: int,
) -> int:
    """Return the index that splits old (compactable) from recent (kept verbatim).

    Algorithm: scan backwards from the end of ``messages``, counting
    user turns (excluding compaction-summary items). Return the index
    of the ``keep_recent_turns``-th-most-recent user message — i.e. the
    index where the recent slice starts. Items at indices < boundary
    are eligible for compaction; items at indices >= boundary must
    pass through verbatim.

    If there are fewer than ``keep_recent_turns`` user messages in
    the list, return 0 — keep everything (nothing is old enough to
    compact safely).

    Args:
        messages: list of :class:`ProjectedMessage` dicts. Each must
            have a ``role`` key.
        keep_recent_turns: number of recent user turns to preserve
            verbatim. Must be >= 0; 0 means "no recent turns
            preserved" (boundary == len(messages)).
    """
    if keep_recent_turns < 0:
        raise ValueError("keep_recent_turns must be >= 0")
    if not messages:
        return 0
    if keep_recent_turns == 0:
        return len(messages)

    user_count = 0
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        if msg.get("is_compaction_summary"):
            # Compaction summaries are user-shaped but not counted
            continue
        user_count += 1
        if user_count >= keep_recent_turns:
            return i

    # Not enough user turns — keep everything
    return 0


def format_messages_as_transcript(messages: Iterable[ProjectedMessage]) -> str:
    """Render projected messages as a plain-text transcript.

    Used by Layer 5 (commit 5) to feed history into a summary LLM call.
    Compaction-summary items render under a distinct tag so the
    summarizer doesn't confuse them with ordinary user messages.

    The transcript is **read-only friendly**: it does not include
    overflow_record_id pointers, since the summarizer can't dereference
    them. Layer 0 already inserted the record id into the message
    content; if the summarizer needs that, it sees it inline.
    """
    parts: List[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            parts.append(f"[ITEM]: {str(msg)[:300]}")
            continue

        role = str(msg.get("role") or "unknown")
        content = str(msg.get("content") or "")

        if msg.get("is_compaction_summary"):
            parts.append(f"[COMPACTION SUMMARY]:\n{content}")
            continue

        if role == "tool_use":
            tool = str(msg.get("tool_name") or "?")
            parts.append(f"[TOOL CALL: {tool}]: {content[:300]}")
        elif role == "tool_result":
            tool = str(msg.get("tool_name") or "?")
            parts.append(f"[TOOL RESULT: {tool}]: {content[:500]}")
        elif role == "user":
            parts.append(f"[USER]: {content}")
        elif role == "assistant":
            parts.append(f"[ASSISTANT]: {content}")
        elif role == "system":
            parts.append(f"[SYSTEM]: {content}")
        else:
            parts.append(f"[{role.upper()}]: {content[:300]}")

    return "\n\n".join(parts)
