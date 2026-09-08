"""Validation shared by direct OpenAI Responses consumers, not OAuth transports."""

from datetime import date
from typing import Any

from src.model_capabilities import capability_for


def require_response_model(response: Any, model: str) -> None:
    requested = capability_for(model)
    unpinned = requested is not None and model in (requested.id, *requested.aliases)
    canonical = requested.id if unpinned else model
    observed = response.model
    model_matches = observed in (model, canonical)
    # Reviewed aliases may resolve to dated snapshots. Explicit snapshots and
    # unknown custom IDs must match exactly, never just share a prefix.
    if (not model_matches and unpinned
            and isinstance(observed, str) and observed.startswith(canonical + "-")):
        suffix = observed.removeprefix(canonical + "-")
        try:
            model_matches = date.fromisoformat(suffix).isoformat() == suffix
        except ValueError:
            pass
    if not model_matches:
        raise RuntimeError("OpenAI response returned a different model")


def require_completed_response(response: Any, model: str) -> None:
    require_response_model(response, model)
    if response.status != "completed" or response.error is not None:
        raise RuntimeError("OpenAI response did not complete")


def completed_response_text(response: Any, model: str) -> str:
    require_completed_response(response, model)
    parts = []
    for item in response.output or []:
        if item.type == "reasoning":
            continue
        if item.type != "message" or item.role != "assistant" or item.status != "completed":
            raise RuntimeError("OpenAI response returned an unexpected output item")
        for block in item.content:
            if block.type != "output_text":
                raise RuntimeError("OpenAI response refused or returned non-text output")
            parts.append(block.text)
    text = "".join(parts)
    if not text.strip():
        raise RuntimeError("OpenAI response returned no text")
    return text
