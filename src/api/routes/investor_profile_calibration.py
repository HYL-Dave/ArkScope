"""Investor Profile calibration chat routes (Track A.5).

Mutations are profile-state writes. Raw calibration text never enters research
prompt assembly; these routes only store journal messages and inert proposals.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_investor_calibration_store, get_investor_profile_store
from src.api.permissions import require_profile_state_write
from src.investor_profile import InvestorProfileStore
from src.investor_profile_calibration import CalibrationStore
from src.investor_profile_calibration_agent import (
    live_calibration_responder as default_calibration_responder,
    unavailable_responder,
)

router = APIRouter(prefix="/profile/investor/calibration", tags=["investor_profile"])
_default_responder = default_calibration_responder
_PROFILE_PROVENANCE_FIELDS = (
    "enabled",
    "primary_preset",
    "risk_appetite",
    "risk_capacity",
    "risk_mismatch",
    "holding_horizon",
    "drawdown_tolerance_pct",
    "concentration_limit_pct",
    "preferred_edge",
    "avoidances",
    "behavioral_flags",
    "freeform_notes",
    "default_stance",
    "skill_mode",
)


class StartCalibrationBody(BaseModel):
    supersede_active: bool = False


class CalibrationMessageBody(BaseModel):
    session_id: Optional[str] = None
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None


class ApproveProposalBody(BaseModel):
    profile_patch: Optional[dict] = None


def _session(s):
    return asdict(s) if s else None


def _message(m):
    return asdict(m)


def _proposal(p):
    return asdict(p) if p else None


def _bad(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _state(store: CalibrationStore, session_id: str | None = None) -> dict:
    active = store.get_active_session()
    sid = session_id or (active.id if active else None)
    messages = store.list_messages(sid) if sid else []
    proposal = store.latest_proposal(sid) if sid else None
    return {
        "active_session": _session(active),
        "sessions": [_session(s) for s in store.list_sessions()],
        "messages": [_message(m) for m in messages],
        "latest_proposal": _proposal(proposal),
    }


@router.get("")
def get_calibration_state(
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    return _state(store)


@router.post("/sessions")
def start_calibration_session(
    body: StartCalibrationBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write(
        "investor_profile_calibration_start", {"supersede_active": body.supersede_active}
    )
    try:
        sess = store.start_session(supersede_active=body.supersede_active)
    except ValueError as exc:
        if str(exc) == "calibration_session_active":
            raise _bad(409, "calibration_session_active", "an active calibration session already exists") from exc
        raise _bad(400, "invalid_calibration_session", str(exc)) from exc
    return _state(store, sess.id)


@router.post("/sessions/{session_id}/close")
def close_calibration_session(
    session_id: str,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write("investor_profile_calibration_close", {"session_id": session_id})
    try:
        sess = store.close_session(session_id)
    except ValueError as exc:
        raise _bad(404, "calibration_session_not_found", str(exc)) from exc
    return _state(store, sess.id)


@router.post("/messages")
async def send_calibration_message(
    body: CalibrationMessageBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    active = store.get_active_session()
    sid = body.session_id or (active.id if active else None)
    if not sid:
        raise _bad(409, "calibration_session_required", "start a calibration session first")
    require_profile_state_write("investor_profile_calibration_message", {"session_id": sid})
    try:
        store.append_message(sid, role="user", content=body.content)
        messages = [{"role": m.role, "content": m.content} for m in store.list_messages(sid)]
        result = await _default_responder(messages=messages, provider=body.provider, model=body.model)
        store.append_message(sid, role="assistant", content=result.assistant_message)
        if result.profile_patch is not None:
            store.create_proposal(session_id=sid, profile_patch=result.profile_patch, rationales=result.rationales)
    except ValueError as exc:
        raise _bad(400, "invalid_calibration_message", str(exc)) from exc
    return _state(store, sid)


@router.post("/proposals/{proposal_id}/approve")
def approve_calibration_proposal(
    proposal_id: str,
    body: ApproveProposalBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
    profile_store: InvestorProfileStore = Depends(get_investor_profile_store),
):
    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        raise _bad(404, "proposal_not_found", "proposal not found")
    payload = body.profile_patch if body.profile_patch is not None else proposal.profile_patch
    try:
        profile_store.draft(payload)
    except ValueError as exc:
        raise _bad(400, "invalid_investor_profile", str(exc)) from exc
    require_profile_state_write("investor_profile_calibration_approve", {"proposal_id": proposal_id})
    before = asdict(profile_store.get())
    profile = profile_store.save(payload)
    after = asdict(profile)
    changed = sorted(k for k in _PROFILE_PROVENANCE_FIELDS if before.get(k) != after.get(k))
    approved = store.mark_proposal_approved(proposal_id, changed_fields=changed)
    return {"profile": after, "proposal": _proposal(approved)}


@router.post("/proposals/{proposal_id}/reject")
def reject_calibration_proposal(
    proposal_id: str,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write("investor_profile_calibration_reject", {"proposal_id": proposal_id})
    try:
        proposal = store.reject_proposal(proposal_id)
    except ValueError as exc:
        raise _bad(400, "invalid_calibration_proposal", str(exc)) from exc
    return {"proposal": _proposal(proposal)}
