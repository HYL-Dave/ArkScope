"""Investor Profile + Assistant Stance routes (Track A).

GET/draft are read-only; PUT is a profile-state write. The context preview is
the exact synthesis/chat block the agent would receive — it is never passed to
evidence gathering (ProductSpec §2 boundary).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_investor_profile_store
from src.api.permissions import require_profile_state_write
from src.investor_profile import (
    InvestorProfile,
    InvestorProfileStore,
    build_personalization_context,
    effective_stance,
    personalization_trace,
)

router = APIRouter(prefix="/profile", tags=["investor_profile"])


class InvestorProfileBody(BaseModel):
    enabled: Optional[bool] = None
    primary_preset: Optional[str] = None
    risk_appetite: Optional[int] = None
    risk_capacity: Optional[int] = None
    holding_horizon: Optional[str] = None
    drawdown_tolerance_pct: Optional[float] = None
    concentration_limit_pct: Optional[float] = None
    preferred_edge: Optional[list[str]] = None
    avoidances: Optional[list[str]] = None
    behavioral_flags: Optional[list[str]] = None
    freeform_notes: Optional[str] = None
    default_stance: Optional[str] = None
    skill_mode: Optional[str] = None

    def payload(self) -> dict:
        """Only fields the client actually sent (merge semantics).

        Uses model_fields_set so an EXPLICIT null clears a field (the UI sends
        null when the user resets e.g. risk_appetite) while omitted fields
        still mean "no change".
        """
        return {k: v for k, v in self.model_dump().items() if k in self.model_fields_set}


def _response(profile: InvestorProfile) -> dict:
    return {
        "profile": asdict(profile),
        "effective_stance": effective_stance(profile),
        "trace": personalization_trace(profile),
        "context_preview": build_personalization_context(profile),
    }


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": "invalid_investor_profile", "message": str(exc)},
    )


@router.get("/investor")
def get_investor_profile(
    store: InvestorProfileStore = Depends(get_investor_profile_store),
):
    """Read-only: current profile + effective stance + context preview."""
    return _response(store.get())


@router.post("/investor/draft")
def draft_investor_profile(
    body: InvestorProfileBody,
    store: InvestorProfileStore = Depends(get_investor_profile_store),
):
    """Deterministic normalization preview — does NOT save, no write gate."""
    try:
        profile = store.draft(body.payload())
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return _response(profile)


@router.put("/investor")
def put_investor_profile(
    body: InvestorProfileBody,
    store: InvestorProfileStore = Depends(get_investor_profile_store),
):
    """Persist the profile — profile-state write, gated."""
    payload = body.payload()
    try:
        # Validate BEFORE the gate so a malformed request never records a
        # permission grant for a write that cannot happen.
        store.draft(payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    require_profile_state_write("investor_profile_update", {"fields": sorted(payload)})
    profile = store.save(payload)
    return _response(profile)
