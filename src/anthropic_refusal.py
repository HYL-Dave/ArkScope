"""Shared structured-refusal handling for Anthropic models (P2.7 Task 5B).

Claude Fable-class models return classifier refusals as a SUCCESSFUL HTTP 200
with ``stop_reason: "refusal"`` (pre-output refusals carry an empty content
array; ``stop_details`` may be null even on a refusal — branch on stop_reason
only, per the official refusals-and-fallback contract). Before this module the
agent loop treated any non-tool_use stop as a final answer, so a refusal
surfaced as a successful EMPTY answer.

Consumers (the three seams): the anthropic agent loop, card synthesis, and
card translation. No hidden model fallback anywhere — a refusal is surfaced as
a typed failure the caller/UI must see.
"""

from __future__ import annotations

from typing import Any


class AnthropicRefusalError(RuntimeError):
    """A model declined the request via stop_reason=refusal (HTTP 200)."""

    def __init__(self, model: str, stop_details: Any = None):
        self.model = model
        self.stop_details = _details_dict(stop_details)
        category = self.stop_details.get("category")
        suffix = f" (category: {category})" if category else ""
        super().__init__(f"model {model} refused the request{suffix}")


def is_refusal(message: Any) -> bool:
    """Branch on stop_reason ONLY (stop_details may be null on real refusals)."""
    return getattr(message, "stop_reason", None) == "refusal"


def _details_dict(stop_details: Any) -> dict:
    if isinstance(stop_details, dict):
        return stop_details
    if stop_details is None:
        return {}
    # SDK objects expose attributes; keep only the documented display fields.
    out = {}
    for key in ("type", "category", "explanation"):
        value = getattr(stop_details, key, None)
        if value is not None:
            out[key] = value
    return out
