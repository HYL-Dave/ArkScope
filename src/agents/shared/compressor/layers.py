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
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from .overflow_store import OverflowStore
from .reducers import ToolReducer, get_reducer
from .transcript import find_recent_boundary
from .types import CompressionRecord, ProjectedMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# tool_output envelope helpers (mirrors src/agents/shared/security.py)
# ---------------------------------------------------------------------------

# Anthropic + OpenAI bridges both wrap tool results via wrap_tool_result(),
# producing ``<tool_output tool="X">\n<content>\n</tool_output>``. Reducers
# operate on the inner content; this layer unwraps before reducing and
# re-wraps the summary so the agent's prompt parser keeps seeing the
# expected envelope.
_TOOL_OUTPUT_RE = re.compile(
    r'^<tool_output tool="([^"]+)">\n(.*)\n</tool_output>$',
    re.DOTALL,
)


def _unwrap_tool_output(payload: str) -> Tuple[str, Optional[str]]:
    """Strip ``<tool_output tool="...">\\n...\\n</tool_output>`` envelope.

    Returns ``(inner_content, tool_name)`` if the envelope was present;
    ``(payload_unchanged, None)`` otherwise.
    """
    if not isinstance(payload, str) or not payload.startswith('<tool_output tool="'):
        return payload, None
    m = _TOOL_OUTPUT_RE.match(payload)
    if not m:
        return payload, None
    return m.group(2), m.group(1)


def _rewrap_tool_output(content: str, tool_name: str) -> str:
    """Inverse of :func:`_unwrap_tool_output`. Matches ``security.wrap_tool_result``."""
    return f'<tool_output tool="{tool_name}">\n{content}\n</tool_output>'


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

    # Bridges wrap tool output as <tool_output tool="X">\n...\n</tool_output>;
    # reducers see the inner JSON / text. We re-wrap before returning so the
    # agent's prompt parser still sees the envelope.
    inner, wrapped_tool = _unwrap_tool_output(payload)

    # Reducer step (fail-open)
    reducer = get_reducer(tool_name, registry)
    try:
        summary, _meta = reducer(inner, budget=budget_chars)
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

    # Persist ORIGINAL wrapped payload (overflow round-trip is byte-perfect
    # against what entered Layer 0, including the envelope).
    try:
        record = overflow_store.write(tool_name, args or {}, payload)
    except Exception as exc:
        logger.warning(
            "Layer 0 overflow disk write failed for %s: %s — using original payload",
            tool_name, exc,
        )
        return payload, None

    # Re-wrap the summary if the input had a tool_output envelope.
    if wrapped_tool is not None:
        summary = _rewrap_tool_output(summary, wrapped_tool)

    # Append record reference outside the envelope (it's prompt-side
    # metadata, not tool data — doesn't belong inside <tool_output>).
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

    Mirrors :func:`apply_layer_0` envelope handling: production tool results
    are wrapped as ``<tool_output tool="X">\\n<JSON>\\n</tool_output>`` by the
    bridge. We unwrap before parsing so JSON minification works on real
    payloads, then re-wrap the minified content so the agent's prompt parser
    keeps seeing the expected envelope.

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

        inner, wrapped_tool = _unwrap_tool_output(content)

        try:
            parsed = json.loads(inner)
        except (json.JSONDecodeError, TypeError):
            out.append(dict(msg))
            continue

        try:
            minified = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError):
            out.append(dict(msg))
            continue

        if wrapped_tool is not None:
            minified = _rewrap_tool_output(minified, wrapped_tool)

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

    **Idempotent**: if ``messages[0]`` is already a scratchpad summary
    (``is_compaction_summary=True`` AND content starts with
    ``<scratchpad_summary>``), it is replaced with the new scratchpad
    rather than another summary being prepended on top. This lets
    ``compact_pre_call`` run repeatedly across model calls without
    summaries piling up.

    Behaviour:
      1. Strip any pre-existing scratchpad summary at index 0.
      2. Prepend a single user-shaped message containing the new
         scratchpad, tagged ``is_compaction_summary=True``.
      3. For items strictly older than the boundary AND of role
         ``tool_result``, replace ``content`` with a one-line stub
         ``"[old <tool_name> result, see scratchpad summary]"``.
      4. Recent items pass through verbatim.
    """
    if not isinstance(scratchpad, str) or not scratchpad.strip():
        return list(messages)

    # Idempotency: strip an existing scratchpad summary so we don't
    # stack a fresh one on top.
    msgs = list(messages)
    if (
        msgs
        and isinstance(msgs[0], dict)
        and msgs[0].get("is_compaction_summary")
        and isinstance(msgs[0].get("content"), str)
        and msgs[0]["content"].startswith(_SCRATCHPAD_SUMMARY_MARKER)
    ):
        msgs = msgs[1:]

    summary_item: ProjectedMessage = {
        "role": "user",
        "content": f"{_SCRATCHPAD_SUMMARY_MARKER}\n{scratchpad.strip()}",
        "is_compaction_summary": True,
    }

    if not msgs:
        return [summary_item]

    boundary = find_recent_boundary(msgs, keep_recent_turns=keep_recent_turns)
    out: List[ProjectedMessage] = [summary_item]

    for i, msg in enumerate(msgs):
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


# ---------------------------------------------------------------------------
# Layer 5: LLM full compact (last resort, expensive)
# ---------------------------------------------------------------------------


def apply_layer_5(
    messages: List[ProjectedMessage],
    *,
    keep_recent_turns: int,
    summary_caller,  # SummaryCaller (avoid import cycle here)
    prior_summary: Optional[str] = None,
) -> Tuple[List[ProjectedMessage], int, bool]:
    """Replace ``messages[:boundary]`` with a single compaction summary.

    Returns ``(new_messages, replace_prefix_to, success)``:

      - ``new_messages``: the transformed projected list. On success this is
        ``[summary_item] + messages[boundary:]``. On failure / no-op this is
        a copy of ``messages`` unchanged.
      - ``replace_prefix_to``: the projected boundary index ``B`` used to
        slice. The orchestrator forwards this to the adapter so the native
        prefix can be replaced with ``[{role:user, content:<summary>}]``.
        ``0`` means "Layer 5 chose no-op" — adapter must not slice native
        messages.
      - ``success``: True if the summarizer returned non-None text and the
        replacement actually happened. False on caller failure or no-op.

    No-op cases:
      - Empty messages or boundary at 0 (not enough turns).
      - Caller returns None (LLM failure / empty output).

    Idempotency: ``prior_summary`` is the content string from a previous
    compaction summary (passed in by the adapter when it has detached
    one from the native messages, OR auto-detected here from
    ``messages[0]`` if the projection still contains it). When set, it
    is rendered into the transcript as a ``[PRIOR SUMMARY]`` block so
    the new summary absorbs it rather than stacking on top.

    The output cap (word/char) is applied here in code — never trust the
    LLM to obey the prompt's "≤2000 words" rule.
    """
    from .summary_prompt import (
        build_layer_5_system_prompt,
        build_layer_5_user_prompt,
        cap_summary,
        render_layer_5_transcript,
        wrap_compaction_summary,
    )

    if not messages:
        return list(messages), 0, False

    boundary = find_recent_boundary(messages, keep_recent_turns=keep_recent_turns)
    if boundary == 0:
        # Not enough turns to safely compact — no-op (spec §3.6 step 1).
        return list(messages), 0, False

    # Auto-detect prior summary from messages[0] only if the caller
    # didn't pass one in (the adapter generally has already detached
    # the native summary and forwarded its content).
    body = messages
    auto_detected_offset = 0
    if (
        prior_summary is None
        and boundary > 0
        and isinstance(messages[0], dict)
        and messages[0].get("is_compaction_summary")
        and isinstance(messages[0].get("content"), str)
    ):
        prior_summary = messages[0]["content"]
        body = messages[1:]
        auto_detected_offset = 1
        boundary -= 1
        if boundary <= 0:
            # Only the prior summary was old — no body to compact.
            return list(messages), 0, False

    transcript = render_layer_5_transcript(
        body[:boundary], prior_summary=prior_summary,
    )

    try:
        raw_summary = summary_caller(
            system_prompt=build_layer_5_system_prompt(),
            user_prompt=build_layer_5_user_prompt(transcript),
        )
    except Exception as exc:
        logger.warning("Layer 5 summary_caller raised %s — treating as failure", exc)
        raw_summary = None

    if not isinstance(raw_summary, str) or not raw_summary.strip():
        return list(messages), 0, False

    capped = cap_summary(raw_summary)
    summary_content = wrap_compaction_summary(capped)

    summary_item: ProjectedMessage = {
        "role": "user",
        "content": summary_content,
        "is_compaction_summary": True,
    }
    new_messages = [summary_item] + list(body[boundary:])
    # ``replace_prefix_to`` is reported in the ORIGINAL (un-shifted)
    # ``messages`` index space. If we auto-detected + popped a prior
    # summary at index 0, add 1 back so the adapter sees the same
    # coordinate it passed in.
    replace_prefix_to_orig = boundary + auto_detected_offset
    return new_messages, replace_prefix_to_orig, True


# ---------------------------------------------------------------------------
# Layer 6: post-compact anchor recovery (free, runs after Layer 4 / 5)
# ---------------------------------------------------------------------------


_ANCHOR_BYTE_CAP = 1024
"""spec §3.7: anchor block must be ≤ 1KB to keep cache invalidation cheap."""


def apply_layer_6(
    messages: List[ProjectedMessage],
    *,
    anchor_data: Dict[str, Any],
) -> List[ProjectedMessage]:
    """Append a single anchor item at the END of messages.

    ``anchor_data`` is provider-supplied — typically::

        {
            "tickers": ["NVDA", "TSLA"],
            "recent_record_ids": ["abcd1234deadbeef", ...],
        }

    Empty / falsy ``anchor_data`` → no-op (returns input copy).

    The anchor is wrapped in the canonical ``<anchor>`` marker so that
    re-projection can recognise it via content prefix and
    :func:`find_recent_boundary` can skip it via ``is_anchor=True``.

    Size cap: ≤ 1024 bytes after marker wrapping. Truncation appends
    `` [TRUNCATED:anchor_cap=1024]`` so a reader knows the cut happened.
    """
    from .summary_prompt import wrap_anchor

    if not isinstance(anchor_data, dict) or not anchor_data:
        return list(messages)

    parts: List[str] = []
    tickers = anchor_data.get("tickers")
    if isinstance(tickers, (list, tuple)) and tickers:
        parts.append("tickers: " + ", ".join(str(t) for t in tickers))
    recent_ids = anchor_data.get("recent_record_ids")
    if isinstance(recent_ids, (list, tuple)) and recent_ids:
        parts.append("recent overflow record_ids: " + ", ".join(
            str(r) for r in recent_ids
        ))

    if not parts:
        return list(messages)

    body = "\n".join(parts)
    wrapped = wrap_anchor(body)

    # Hard byte cap (≤ _ANCHOR_BYTE_CAP after marker is appended).
    # Reserve marker bytes BEFORE truncation so the final UTF-8 size
    # stays under the cap — otherwise a max-size truncation + marker
    # append would overshoot by ~28 bytes.
    cap_marker = f" [TRUNCATED:anchor_cap={_ANCHOR_BYTE_CAP}]"
    cap_marker_bytes = len(cap_marker.encode("utf-8"))
    encoded = wrapped.encode("utf-8")
    if len(encoded) > _ANCHOR_BYTE_CAP:
        budget = _ANCHOR_BYTE_CAP - cap_marker_bytes
        cut = encoded[:budget].decode("utf-8", errors="ignore")
        wrapped = cut + cap_marker

    anchor_item: ProjectedMessage = {
        "role": "user",
        "content": wrapped,
        "is_anchor": True,
    }
    return list(messages) + [anchor_item]
