"""Track A: shared personalization resolution for research/card routes.

Resolves the Investor Profile into (prompt_context, run_trace). Invalid stance
overrides are a 400 BEFORE any stream/gather starts — never a silent fallback,
or the persisted trace would be ambiguous. The returned context goes to
SYNTHESIS/CHAT only (ProductSpec §2 evidence boundary).
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


def validate_assistant_stance(assistant_stance: Optional[str]) -> None:
    from src.investor_profile import STANCES

    if assistant_stance is not None and assistant_stance not in STANCES:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_assistant_stance", "field": "assistant_stance"},
        )


def resolve_personalization(assistant_stance: Optional[str]) -> tuple[str, dict]:
    from src.investor_profile import personalization_bundle

    validate_assistant_stance(assistant_stance)
    from src.api.dependencies import get_investor_profile_store

    profile = get_investor_profile_store().get()
    return personalization_bundle(profile, override=assistant_stance)
