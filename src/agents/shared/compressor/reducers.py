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
# web_result_reducer (tavily_search / tavily_fetch / web_browse / codex_web_research)
# ---------------------------------------------------------------------------


def web_result_reducer(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """For web tools: keep title + URL + snippet per result; drop bodies.

    Expected shape (best-effort): ``{"results": [{"title", "url", "content"}, ...]}``
    or ``{"query": ..., "results": [...]}``.

    On any deviation, falls through to ``truncate_with_marker``.
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
        "result_count": len(results),
        "results": pruned,
    }
    summary = json.dumps(out, ensure_ascii=False)

    # If still over budget, fall through (default reducer will tail-end-trim)
    if len(summary) > budget:
        return truncate_with_marker(summary, budget=budget)

    return summary, {
        "dropped_chars": len(payload) - len(summary),
        "kept_results": len(pruned),
        "snippet_chars": snippet_chars,
    }


# ---------------------------------------------------------------------------
# option_chain_reducer (get_option_chain)
# ---------------------------------------------------------------------------


def option_chain_reducer(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """For option chains: keep ATM ± 5 strikes per expiry; drop deep ITM/OTM.

    Expected shape (best-effort):

    .. code-block:: text

        {
          "ticker": "...",
          "spot": 123.45,
          "expiries": [
            {"date": "2026-05-16", "calls": [{"strike": ..., ...}, ...], "puts": [...]},
            ...
          ]
        }

    Falls through to default reducer on any shape mismatch.
    """
    if len(payload) <= budget:
        return payload, {}

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return truncate_with_marker(payload, budget=budget)

    if not isinstance(data, dict):
        return truncate_with_marker(payload, budget=budget)

    spot = data.get("spot")
    expiries = data.get("expiries")
    if not isinstance(expiries, list) or not isinstance(spot, (int, float)):
        return truncate_with_marker(payload, budget=budget)

    keep_per_side = 5
    pruned_expiries: List[Dict[str, Any]] = []
    total_dropped_strikes = 0

    for exp in expiries:
        if not isinstance(exp, dict):
            continue
        out_exp = {"date": exp.get("date")}
        for side in ("calls", "puts"):
            rows = exp.get(side)
            if not isinstance(rows, list):
                out_exp[side] = []
                continue
            # Keep rows with strike closest to spot, ± keep_per_side
            ranked = sorted(
                (r for r in rows if isinstance(r, dict) and isinstance(r.get("strike"), (int, float))),
                key=lambda r: abs(r["strike"] - spot),
            )
            kept = ranked[: keep_per_side * 2]
            kept_sorted = sorted(kept, key=lambda r: r["strike"])
            out_exp[side] = kept_sorted
            total_dropped_strikes += max(0, len(rows) - len(kept_sorted))
        pruned_expiries.append(out_exp)

    out = {
        "ticker": data.get("ticker"),
        "spot": spot,
        "kept_strikes_per_side": keep_per_side,
        "expiries": pruned_expiries,
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
    """For IV history: keep most recent 30 trading days; drop older.

    Expected shape (best-effort):

    .. code-block:: text

        {
          "ticker": "...",
          "history": [{"date": "...", "iv": ...}, ...],
        }

    Falls through to default on any shape mismatch.
    """
    if len(payload) <= budget:
        return payload, {}

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return truncate_with_marker(payload, budget=budget)

    if not isinstance(data, dict):
        return truncate_with_marker(payload, budget=budget)

    history = data.get("history")
    if not isinstance(history, list):
        return truncate_with_marker(payload, budget=budget)

    keep_days = 30
    kept = history[-keep_days:]
    out = dict(data)
    out["history"] = kept
    out["history_kept_days"] = keep_days
    out["history_dropped_rows"] = max(0, len(history) - len(kept))

    summary = json.dumps(out, ensure_ascii=False)
    if len(summary) > budget:
        return truncate_with_marker(summary, budget=budget)

    return summary, {
        "dropped_chars": len(payload) - len(summary),
        "dropped_rows": out["history_dropped_rows"],
        "kept_days": keep_days,
    }


# ---------------------------------------------------------------------------
# python_output_reducer (execute_python_analysis)
# ---------------------------------------------------------------------------


def python_output_reducer(payload: str, *, budget: int) -> Tuple[str, Dict[str, Any]]:
    """For Python analysis output: keep last 2KB stdout + last 1KB stderr.

    Expected shape (best-effort):

    .. code-block:: text

        {"stdout": "...", "stderr": "...", "ok": true}

    Falls through to default on any shape mismatch.
    """
    if len(payload) <= budget:
        return payload, {}

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return truncate_with_marker(payload, budget=budget)

    if not isinstance(data, dict):
        return truncate_with_marker(payload, budget=budget)

    stdout_keep = 2000
    stderr_keep = 1000
    stdout = str(data.get("stdout") or "")
    stderr = str(data.get("stderr") or "")

    stdout_trimmed = stdout[-stdout_keep:] if len(stdout) > stdout_keep else stdout
    stderr_trimmed = stderr[-stderr_keep:] if len(stderr) > stderr_keep else stderr

    out = dict(data)
    out["stdout"] = stdout_trimmed
    out["stderr"] = stderr_trimmed
    if len(stdout) > stdout_keep:
        out["stdout_dropped_chars"] = len(stdout) - stdout_keep
    if len(stderr) > stderr_keep:
        out["stderr_dropped_chars"] = len(stderr) - stderr_keep

    summary = json.dumps(out, ensure_ascii=False)
    if len(summary) > budget:
        return truncate_with_marker(summary, budget=budget)

    return summary, {
        "dropped_chars": len(payload) - len(summary),
        "stdout_keep_chars": stdout_keep,
        "stderr_keep_chars": stderr_keep,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_DEFAULT_REGISTRY: Dict[str, ToolReducer] = {
    # Web tools (large HTML / markdown bodies)
    "tavily_search":          web_result_reducer,
    "tavily_fetch":           web_result_reducer,
    "web_browse":              web_result_reducer,
    "codex_web_research":      web_result_reducer,
    # Options
    "get_option_chain":        option_chain_reducer,
    # IV history
    "get_iv_history_data":     iv_history_reducer,
    # Python analysis
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
