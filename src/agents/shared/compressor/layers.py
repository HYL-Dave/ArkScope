"""Deterministic Layer 0-3 implementations (P1.4 commit 2).

Each layer is a pure function operating on :class:`ProjectedMessage`
lists (Layers 1-3) or on a single tool payload (Layer 0). The
orchestrator in :mod:`context_compressor` decides which layers to
fire based on size thresholds + per-layer toggles.

All layers are **fail-open**: if anything raises mid-transformation,
the layer logs and returns the input unchanged so agent progress is
never blocked. This is a deliberate choice from spec §1.2 #5 +
§3.1 fail-open principle.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from .overflow_store import OverflowStore
from .reducers import ToolReducer, get_reducer
from .transcript import find_recent_boundary
from .types import CompressionRecord, ProjectedMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer 0: insertion-time tool result budget + overflow disk
# ---------------------------------------------------------------------------


def apply_layer_0(
    *,
    tool_name: str,
    args: Optional[Dict[str, Any]],
    payload: str,
    overflow_store: OverflowStore,
    budget_chars: int,
    registry: Optional[Dict[str, ToolReducer]] = None,
) -> Tuple[str, Optional[CompressionRecord]]:
    """Run a tool result through the per-tool reducer; persist on overflow.

    Returns ``(in_prompt_payload, optional_record)``:

      - If ``len(payload) <= budget_chars``: returns ``(payload, None)``
        unchanged. No reducer run, no disk write.
      - If overflowed and reducer + persist succeed: returns
        ``(summary_with_record_ref, CompressionRecord)``. The summary
        has a tail line ``"\\n[overflow_record=...]\\n"`` so the agent
        / debug tools can find the original.
      - If anything in the budget path fails (reducer raises, disk
        write fails, etc.): returns ``(payload, None)`` — fail-open.
        A warning is logged but agent progress is not blocked.
    """
    if not isinstance(payload, str):
        # Stringify and continue — we still want to attempt budgeting
        try:
            payload = str(payload)
        except Exception:
            return "", None

    if len(payload) <= budget_chars:
        return payload, None

    # Reducer step (fail-open)
    reducer = get_reducer(tool_name, registry)
    try:
        summary, _meta = reducer(payload, budget=budget_chars)
    except Exception as exc:
        logger.warning(
            "Layer 0 reducer for %s raised %s — using original payload",
            tool_name, exc,
        )
        return payload, None

    if not isinstance(summary, str):
        logger.warning(
            "Layer 0 reducer for %s returned non-str — using original payload",
            tool_name,
        )
        return payload, None

    # Persist original (fail-open on disk error)
    try:
        record = overflow_store.write(tool_name, args or {}, payload)
    except Exception as exc:
        logger.warning(
            "Layer 0 overflow disk write failed for %s: %s — using original payload",
            tool_name, exc,
        )
        return payload, None

    # Append record reference to summary
    summary_with_ref = (
        summary
        + f"\n[overflow_record={record.record_id}, "
        + f"original_size={record.original_size}]"
    )
    # If the appended line pushed us over budget, accept the ~80-char
    # overshoot — losing the reference is worse than the budget breach.
    return summary_with_ref, record


# ---------------------------------------------------------------------------
# Layer 1: microcompact (minify JSON in old turns)
# ---------------------------------------------------------------------------


def apply_layer_1(
    messages: List[ProjectedMessage],
    *,
    keep_recent_turns: int,
) -> List[ProjectedMessage]:
    """Minify JSON-shaped tool result content for items older than the boundary.

    Items at index < boundary that have ``role == "tool_result"`` and
    JSON-parseable ``content`` get rewritten with
    ``json.dumps(parsed, separators=(",", ":"))``. Non-JSON content is
    left unchanged. Recent items (>= boundary) are passed through
    verbatim — protecting the prompt cache.

    Returns a NEW list; input is not mutated.
    """
    if not messages:
        return list(messages)

    boundary = find_recent_boundary(messages, keep_recent_turns=keep_recent_turns)
    out: List[ProjectedMessage] = []

    for i, msg in enumerate(messages):
        if i >= boundary:
            out.append(dict(msg))
            continue

        if not isinstance(msg, dict):
            out.append(msg)
            continue

        if msg.get("role") != "tool_result":
            out.append(dict(msg))
            continue

        content = msg.get("content")
        if not isinstance(content, str):
            out.append(dict(msg))
            continue

        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            out.append(dict(msg))
            continue

        try:
            minified = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError):
            out.append(dict(msg))
            continue

        new_msg = dict(msg)
        new_msg["content"] = minified
        out.append(new_msg)

    return out


# ---------------------------------------------------------------------------
# Layer 2: scratchpad reuse (prepend summary, stub old tool_results)
# ---------------------------------------------------------------------------


_SCRATCHPAD_SUMMARY_MARKER = "<scratchpad_summary>"


def apply_layer_2(
    messages: List[ProjectedMessage],
    *,
    scratchpad: str,
    keep_recent_turns: int,
) -> List[ProjectedMessage]:
    """Prepend scratchpad as a marker-wrapped summary; stub old tool_results.

    No-op when ``scratchpad`` is empty / whitespace.

    Behaviour:
      1. Prepend a single user-shaped message containing the scratchpad,
         tagged ``is_compaction_summary=True`` so Layer 5 + boundary
         finder treat it as a prior summary.
      2. For items strictly older than the boundary AND of role
         ``tool_result``, replace ``content`` with a one-line stub
         ``"[old <tool_name> result, see scratchpad summary]"``.
      3. Recent items pass through verbatim.
    """
    if not isinstance(scratchpad, str) or not scratchpad.strip():
        return list(messages)

    summary_item: ProjectedMessage = {
        "role": "user",
        "content": f"{_SCRATCHPAD_SUMMARY_MARKER}\n{scratchpad.strip()}",
        "is_compaction_summary": True,
    }

    if not messages:
        return [summary_item]

    boundary = find_recent_boundary(messages, keep_recent_turns=keep_recent_turns)
    out: List[ProjectedMessage] = [summary_item]

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            out.append(msg)
            continue

        if i >= boundary:
            out.append(dict(msg))
            continue

        if msg.get("role") == "tool_result":
            tool = msg.get("tool_name") or "tool"
            stub = f"[old {tool} result, see scratchpad summary]"
            new_msg = dict(msg)
            new_msg["content"] = stub
            out.append(new_msg)
        else:
            out.append(dict(msg))

    return out


# ---------------------------------------------------------------------------
# Layer 3: progressive truncation (stub old tool_results, no scratchpad)
# ---------------------------------------------------------------------------


def apply_layer_3(
    messages: List[ProjectedMessage],
    *,
    keep_recent_turns: int,
) -> List[ProjectedMessage]:
    """Replace old tool_results with one-line stubs; preserve overflow_record_id.

    The stub format is ``"[old <tool_name> result; record_id=<id>]"``
    when an overflow_record_id is available, else
    ``"[old <tool_name> result; re-call to get a fresh copy]"``.

    Recent items pass through unchanged (cache-stable).
    """
    if not messages:
        return list(messages)

    boundary = find_recent_boundary(messages, keep_recent_turns=keep_recent_turns)
    out: List[ProjectedMessage] = []

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            out.append(msg)
            continue

        if i >= boundary:
            out.append(dict(msg))
            continue

        if msg.get("role") != "tool_result":
            out.append(dict(msg))
            continue

        new_msg = dict(msg)
        tool = msg.get("tool_name") or "tool"
        record_id = msg.get("overflow_record_id")
        if record_id:
            new_msg["content"] = f"[old {tool} result; record_id={record_id}]"
        else:
            new_msg["content"] = f"[old {tool} result; re-call to get a fresh copy]"
        out.append(new_msg)

    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def total_chars(messages: List[ProjectedMessage]) -> int:
    """Sum of len(content) across all messages — for threshold comparisons."""
    total = 0
    for msg in messages:
        if isinstance(msg, dict):
            total += len(str(msg.get("content") or ""))
    return total
