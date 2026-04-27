"""Per-tool result reducers (P1.4 commit 2).

Reducer protocol + a default truncate-with-marker reducer + 4 specific
reducers for the largest-output tools we ship today. See P1_4_SPEC §4.

Every reducer is **fail-open**: if anything goes wrong (JSON parse
error, unexpected shape, etc.), the reducer falls back to the default
``truncate_with_marker``. Callers (Layer 0) never see exceptions from
this module — at worst they get a generic truncation. This is a
deliberate choice: a tool whose output shape changes upstream should
keep working with degraded compression rather than crash.

Reducers receive a ``str`` payload and a ``budget`` (in characters)
and return ``(in_prompt_summary, metadata)``. The summary MUST be
``<= budget`` characters; the metadata dict is for diagnostics and
gets attached alongside the overflow record.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


ToolReducer = Callable[..., Tuple[str, Dict[str, Any]]]
"""Reducer signature: ``reducer(payload: str, *, budget: int) -> (str, dict)``.

Concrete reducers are plain functions; the type alias is documentary.
"""


_TRUNCATION_MARKER_RESERVE = 160  # chars reserved for the "[N chars dropped]" marker


# ---------------------------------------------------------------------------
# Default: truncate with head + tail + marker
# ---------------------------------------------------------------------------


def truncate_with_marker(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """Default reducer: keep first 70% of budget + last 20% + marker.

    If ``len(payload) <= budget`` the payload is returned unchanged with
    empty metadata (no truncation happened). Otherwise the head and
    tail are concatenated with a ``[N chars dropped]`` marker between
    them — the marker reserves ~160 chars so overall output stays
    under budget.

    Why head + tail and not head + middle: tool results often have
    important framing at both ends (header + summary, or query +
    final answer). Dropping the middle is the lowest-information loss.
    """
    if not isinstance(payload, str):
        # Fail-open: stringify and continue
        payload = str(payload)

    if budget <= 0:
        # Pathological budget — just return empty + meta
        return "", {"dropped_chars": len(payload)}

    if len(payload) <= budget:
        return payload, {}

    available = max(1, budget - _TRUNCATION_MARKER_RESERVE)
    head_len = max(1, int(available * 0.7))
    tail_len = max(0, available - head_len)

    head = payload[:head_len]
    tail = payload[-tail_len:] if tail_len > 0 else ""
    dropped = len(payload) - head_len - tail_len

    marker = f"\n... [{dropped} chars dropped] ...\n"
    summary = head + marker + tail

    # Defensive: trim if we somehow overshot budget by reserve estimate
    if len(summary) > budget:
        summary = summary[:budget]

    return summary, {
        "dropped_chars": dropped,
        "head_chars": head_len,
        "tail_chars": tail_len,
    }


# ---------------------------------------------------------------------------
# tavily_search_reducer  (only `tavily_search` — others have non-results shapes)
# ---------------------------------------------------------------------------


def tavily_search_reducer(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """For ``tavily_search``: keep query + answer + per-result title/url/snippet.

    Real shape (from ``src/tools/web_tools.py``):

    .. code-block:: text

        {"query": str, "answer": str, "result_count": int,
         "results": [{"title", "url", "content", ...}, ...]}

    Falls through to ``truncate_with_marker`` on any shape deviation.

    NOTE: ``tavily_fetch`` / ``web_browse`` / ``codex_web_research`` have
    different shapes (single ``content`` field, not a results list); they
    use the default truncate reducer.
    """
    if len(payload) <= budget:
        return payload, {}

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return truncate_with_marker(payload, budget=budget)

    if not isinstance(data, dict):
        return truncate_with_marker(payload, budget=budget)

    results = data.get("results")
    if not isinstance(results, list):
        return truncate_with_marker(payload, budget=budget)

    snippet_chars = 500
    answer_chars = 1000
    pruned: List[Dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        content = str(r.get("content") or "")[:snippet_chars]
        pruned.append({
            "title":   str(r.get("title") or "")[:200],
            "url":     str(r.get("url") or ""),
            "snippet": content,
        })

    out = {
        "query": str(data.get("query") or "")[:200],
        "answer": str(data.get("answer") or "")[:answer_chars],
        "result_count": len(results),
        "results": pruned,
    }
    summary = json.dumps(out, ensure_ascii=False)

    if len(summary) > budget:
        return truncate_with_marker(summary, budget=budget)

    return summary, {
        "dropped_chars": len(payload) - len(summary),
        "kept_results": len(pruned),
        "snippet_chars": snippet_chars,
    }


# Backwards-compat alias (commit 2 used this name)
web_result_reducer = tavily_search_reducer


# ---------------------------------------------------------------------------
# option_chain_reducer (get_option_chain)
# ---------------------------------------------------------------------------


def option_chain_reducer(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """For ``get_option_chain``: keep ATM ± 5 strikes; drop deep ITM/OTM.

    Real shape (from ``src/tools/option_chain_tools.py``):

    .. code-block:: text

        {
          "ticker": "...",
          "spot_price": 123.45,
          "timestamp": "...",
          "selected_expiry": "20260516",
          "selected_dte": 14,
          "expirations_summary": [...],   # list of expiry summary dicts
          "chain": {"calls": [...], "puts": [...]},   # ONE selected expiry
          "metrics": {...},
          "oi_concentration": {"calls": [...], "puts": [...]},
        }

    Strategy:
      - Keep ticker / spot_price / timestamp / selected_expiry / selected_dte
        / metrics / oi_concentration verbatim (small).
      - Slice ``chain.calls`` and ``chain.puts`` to the 5 strikes nearest
        ``spot_price`` on each side.
      - Cap ``expirations_summary`` to 10 rows.

    Falls through to ``truncate_with_marker`` on any shape mismatch
    (key missing, wrong types, etc.).
    """
    if len(payload) <= budget:
        return payload, {}

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return truncate_with_marker(payload, budget=budget)

    if not isinstance(data, dict):
        return truncate_with_marker(payload, budget=budget)

    spot = data.get("spot_price")
    chain = data.get("chain")
    if not isinstance(spot, (int, float)) or not isinstance(chain, dict):
        return truncate_with_marker(payload, budget=budget)

    keep_per_side = 5
    sliced_chain: Dict[str, List[Dict[str, Any]]] = {}
    total_dropped_strikes = 0
    for side in ("calls", "puts"):
        rows = chain.get(side)
        if not isinstance(rows, list):
            sliced_chain[side] = []
            continue
        ranked = sorted(
            (
                r for r in rows
                if isinstance(r, dict) and isinstance(r.get("strike"), (int, float))
            ),
            key=lambda r: abs(r["strike"] - spot),
        )
        kept = ranked[: keep_per_side * 2]
        sliced_chain[side] = sorted(kept, key=lambda r: r["strike"])
        total_dropped_strikes += max(0, len(rows) - len(kept))

    expirations = data.get("expirations_summary")
    capped_expirations = (
        expirations[:10] if isinstance(expirations, list) else expirations
    )

    out = {
        "ticker": data.get("ticker"),
        "spot_price": spot,
        "timestamp": data.get("timestamp"),
        "selected_expiry": data.get("selected_expiry"),
        "selected_dte": data.get("selected_dte"),
        "expirations_summary": capped_expirations,
        "chain": sliced_chain,
        "metrics": data.get("metrics"),
        "oi_concentration": data.get("oi_concentration"),
        "_compressed": {"kept_per_side": keep_per_side},
    }
    summary = json.dumps(out, ensure_ascii=False)
    if len(summary) > budget:
        return truncate_with_marker(summary, budget=budget)

    return summary, {
        "dropped_chars": len(payload) - len(summary),
        "dropped_strikes": total_dropped_strikes,
        "kept_per_side": keep_per_side,
    }


# ---------------------------------------------------------------------------
# iv_history_reducer (get_iv_history_data)
# ---------------------------------------------------------------------------


def iv_history_reducer(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """For ``get_iv_history_data``: keep last 30 days from a list-of-points payload.

    Real shape (from ``src/tools/options_tools.py``):
    a top-level JSON list of :class:`IVHistoryPoint`-shaped dicts:

    .. code-block:: text

        [{"date": "...", "atm_iv": 0.25, "hv_30d": ..., "vrp": ...,
          "spot_price": ..., "num_quotes": ...}, ...]

    Strategy: parse as list, keep last ``keep_days`` rows, re-serialise
    with a ``_compressed`` metadata dict appended.

    Falls through to ``truncate_with_marker`` on shape mismatch.
    """
    if len(payload) <= budget:
        return payload, {}

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return truncate_with_marker(payload, budget=budget)

    # Accept both list and dict-with-history shapes (defensive)
    history: List[Any]
    if isinstance(data, list):
        history = data
    elif isinstance(data, dict) and isinstance(data.get("history"), list):
        history = data["history"]
    else:
        return truncate_with_marker(payload, budget=budget)

    keep_days = 30
    kept = history[-keep_days:]
    dropped = max(0, len(history) - len(kept))

    if isinstance(data, list):
        out: Any = {
            "_compressed": {
                "shape": "list",
                "kept_days": keep_days,
                "dropped_rows": dropped,
            },
            "history": kept,
        }
    else:
        out = dict(data)
        out["history"] = kept
        out["_compressed"] = {
            "shape": "dict.history",
            "kept_days": keep_days,
            "dropped_rows": dropped,
        }

    summary = json.dumps(out, ensure_ascii=False)
    if len(summary) > budget:
        return truncate_with_marker(summary, budget=budget)

    return summary, {
        "dropped_chars": len(payload) - len(summary),
        "dropped_rows": dropped,
        "kept_days": keep_days,
    }


# ---------------------------------------------------------------------------
# python_output_reducer (execute_python_analysis)
# ---------------------------------------------------------------------------


def python_output_reducer(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """For ``execute_python_analysis``: tail-trim ``output`` + ``error`` fields.

    Real shape (from ``CodeExecutionResult`` in
    ``src/tools/code_executor.py``):

    .. code-block:: text

        {"success": bool, "output": str, "error": str,
         "execution_time": float, "output_file": str, "pid": int,
         "generated_code": str}

    Strategy:
      - Keep last 2KB of ``output`` (was named ``stdout`` upstream).
      - Keep last 1KB of ``error`` (was named ``stderr`` upstream).
      - Tail-trim ``generated_code`` to 2KB if present (large generated
        scripts are the second-largest source of bloat).

    Falls through to ``truncate_with_marker`` on shape mismatch.
    """
    if len(payload) <= budget:
        return payload, {}

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return truncate_with_marker(payload, budget=budget)

    if not isinstance(data, dict):
        return truncate_with_marker(payload, budget=budget)

    output_keep = 2000
    error_keep = 1000
    code_keep = 2000
    output = str(data.get("output") or "")
    error = str(data.get("error") or "")
    gen_code = str(data.get("generated_code") or "")

    output_trimmed = output[-output_keep:] if len(output) > output_keep else output
    error_trimmed = error[-error_keep:] if len(error) > error_keep else error
    code_trimmed = gen_code[-code_keep:] if len(gen_code) > code_keep else gen_code

    out = dict(data)
    out["output"] = output_trimmed
    out["error"] = error_trimmed
    if "generated_code" in data:
        out["generated_code"] = code_trimmed

    compressed_meta: Dict[str, Any] = {}
    if len(output) > output_keep:
        compressed_meta["output_dropped_chars"] = len(output) - output_keep
    if len(error) > error_keep:
        compressed_meta["error_dropped_chars"] = len(error) - error_keep
    if len(gen_code) > code_keep:
        compressed_meta["generated_code_dropped_chars"] = len(gen_code) - code_keep
    if compressed_meta:
        out["_compressed"] = compressed_meta

    summary = json.dumps(out, ensure_ascii=False)
    if len(summary) > budget:
        return truncate_with_marker(summary, budget=budget)

    return summary, {
        "dropped_chars": len(payload) - len(summary),
        "output_keep_chars": output_keep,
        "error_keep_chars": error_keep,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_DEFAULT_REGISTRY: Dict[str, ToolReducer] = {
    # tavily_search has a `results: [...]` shape that we know how to slice.
    # tavily_fetch / web_browse / codex_web_research all return a single
    # `content` (or `report`) field — the default head+tail reducer is
    # already a good fit; adding a custom one would just risk shape drift.
    "tavily_search":           tavily_search_reducer,
    # Options
    "get_option_chain":        option_chain_reducer,
    # IV history (top-level list of IVHistoryPoint)
    "get_iv_history_data":     iv_history_reducer,
    # Python analysis (CodeExecutionResult.output / .error / .generated_code)
    "execute_python_analysis": python_output_reducer,
}


def get_reducer(tool_name: str, registry: Dict[str, ToolReducer] | None = None) -> ToolReducer:
    """Return the reducer registered for ``tool_name``, or the default."""
    reg = registry if registry is not None else _DEFAULT_REGISTRY
    return reg.get(tool_name, truncate_with_marker)


def register_reducer(
    tool_name: str,
    reducer: ToolReducer,
    *,
    registry: Dict[str, ToolReducer] | None = None,
) -> None:
    """Register a custom reducer for a tool."""
    reg = registry if registry is not None else _DEFAULT_REGISTRY
    reg[tool_name] = reducer


def default_registry() -> Dict[str, ToolReducer]:
    """Return a copy of the default registry (for tests / customization)."""
    return dict(_DEFAULT_REGISTRY)
