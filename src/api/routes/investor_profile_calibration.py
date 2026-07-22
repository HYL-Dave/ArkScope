"""Typed routes for the durable guided Investor Profile calibration flow."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.dependencies import get_investor_calibration_store, get_investor_profile_store
from src.api.permissions import require_profile_state_write
from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.probe_harness import redact
from src.investor_profile import InvestorProfile, InvestorProfileStore
from src.investor_profile_calibration import (
    CalibrationOperationError,
    CalibrationStore,
    ProposalConflictError,
    ProviderWork,
)
from src.investor_profile_calibration_agent import (
    live_calibration_responder as default_calibration_responder,
    unavailable_responder,
)
from src.investor_profile_calibration_policy import CALIBRATION_TOPIC_IDS, OPENING_PROMPTS
from src.research_errors import sanitize_research_detail

router = APIRouter(prefix="/profile/investor/calibration", tags=["investor_profile"])
_default_responder = default_calibration_responder

_PROFILE_RESPONSE_FIELDS = (
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
    "last_reviewed_at",
    "updated_at",
)


class StartCalibrationBody(BaseModel):
    supersede_active: bool = False


class CalibrationMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: str
    session_id: Optional[str] = None
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None


class CalibrationRetryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Optional[str] = None
    model: Optional[str] = None


class CalibrationProposalRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: str
    session_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ApproveProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _session(value):
    return value.to_dict() if value else None


def _message(value):
    return value.to_dict()


def _turn(value):
    return value.to_dict() if value else None


def _proposal(value):
    return value.to_dict() if value else None


def _profile(value: InvestorProfile) -> dict:
    return {field: getattr(value, field) for field in _PROFILE_RESPONSE_FIELDS}


def _bad(
    status: int,
    code: str,
    message: str,
    *,
    diagnostic: str | None = None,
) -> HTTPException:
    detail = {"code": code, "message": message}
    if diagnostic is not None:
        detail["diagnostic"] = diagnostic
    return HTTPException(status_code=status, detail=detail)


def _latest_retryable_turn(store: CalibrationStore, session_id: str):
    turns = store.list_turns(session_id)
    if not turns or turns[-1].status not in {"pending", "failed", "interrupted"}:
        return None
    return turns[-1]


def _state(store: CalibrationStore, session_id: str | None = None) -> dict:
    active = store.get_active_session()
    sid = session_id or (active.id if active else None)
    messages = store.list_messages(sid) if sid else []
    pending_turn = _latest_retryable_turn(store, sid) if sid else None
    proposal = store.latest_proposal(sid) if sid else None
    return {
        "active_session": _session(active),
        "sessions": [_session(session) for session in store.list_sessions()],
        "messages": [_message(message) for message in messages],
        "pending_turn": _turn(pending_turn),
        "latest_proposal": _proposal(proposal),
        "topic_catalog": list(CALIBRATION_TOPIC_IDS),
    }


def _canonical_messages(messages) -> list[dict]:
    canonical: list[dict] = []
    for message in messages:
        content = message.content
        if message.role == "assistant" and message.prompt_id in OPENING_PROMPTS:
            content = OPENING_PROMPTS[message.prompt_id]
        canonical.append({"role": message.role, "content": content})
    return canonical


def _provider_diagnostic(*, missing_credential: bool = False) -> str:
    source = (
        "Provider api_key=missing"
        if missing_credential
        else "Provider call failed."
    )
    return sanitize_research_detail(redact(source))


def _turn_input_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code == "calibration_session_not_found":
        return _bad(404, code, "Calibration session not found.")
    if code == "calibration_turn_not_found":
        return _bad(404, code, "Calibration turn not found.")
    if code in {
        "calibration_session_not_active",
        "calibration_turn_id_conflict",
        "calibration_turn_pending",
        "calibration_turn_retry_required",
        "calibration_turn_not_retryable",
        "calibration_turn_identity_changed",
    }:
        return _bad(409, code, "Calibration turn state changed; reload and retry.")
    if code in {
        "calibration_turn_id_required",
        "content is required",
        "invalid_calibration_turn_kind",
    }:
        return _bad(400, code, "Calibration turn input is invalid.")
    return _bad(400, "invalid_calibration_turn", "Calibration turn input is invalid.")


def _completion_error(store: CalibrationStore, work: ProviderWork, exc: CalibrationOperationError):
    failed = store.get_turn(work.turn.id)
    diagnostic = failed.diagnostic if failed is not None else exc.diagnostic
    if exc.code == "calibration_catalog_validation_failed":
        message = "Calibration response failed catalog validation. Retry this turn."
    elif exc.code == "calibration_proposal_pending":
        message = "Review the pending calibration proposal before creating another."
    else:
        message = "Calibration response failed validation. Retry this turn."
    return _bad(400, exc.code, message, diagnostic=diagnostic)


async def _complete_provider_work(
    store: CalibrationStore,
    work: ProviderWork,
) -> dict:
    session_id = work.turn.session_id
    if not work.call_provider:
        return _state(store, session_id)

    try:
        result = await _default_responder(
            messages=_canonical_messages(work.messages),
            current_topic_id=work.current_topic_id,
            covered_topics=work.covered_topics,
            request_proposal=work.request_proposal,
            provider=work.provider,
            model=work.model,
        )
    except MissingCredentialError as exc:
        failed = store.fail_turn(
            work.turn.id,
            error_code="provider_config_missing",
            diagnostic=_provider_diagnostic(missing_credential=True),
        )
        raise _bad(
            503,
            "provider_config_missing",
            "Configure an AI provider before retrying this calibration turn.",
            diagnostic=failed.diagnostic,
        ) from exc
    except Exception as exc:
        failed = store.fail_turn(
            work.turn.id,
            error_code="calibration_responder_failed",
            diagnostic=_provider_diagnostic(),
        )
        raise _bad(
            502,
            "calibration_responder_failed",
            "Calibration responder failed. Retry this turn.",
            diagnostic=failed.diagnostic,
        ) from exc

    try:
        store.complete_turn(work.turn.id, result=result)
    except CalibrationOperationError as exc:
        raise _completion_error(store, work, exc) from exc
    except ValueError as exc:
        raise _turn_input_error(exc) from exc
    return _state(store, session_id)


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
        session = store.start_session(supersede_active=body.supersede_active)
    except ValueError as exc:
        if str(exc) == "calibration_session_active":
            raise _bad(
                409,
                "calibration_session_active",
                "An active calibration session already exists.",
            ) from exc
        raise _bad(400, "invalid_calibration_session", "Calibration session is invalid.") from exc
    return _state(store, session.id)


@router.post("/sessions/{session_id}/close")
def close_calibration_session(
    session_id: str,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write("investor_profile_calibration_close", {"session_id": session_id})
    try:
        session = store.close_session(session_id)
    except ValueError as exc:
        raise _bad(404, "calibration_session_not_found", "Calibration session not found.") from exc
    return _state(store, session.id)


@router.post("/messages")
async def send_calibration_message(
    body: CalibrationMessageBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    active = store.get_active_session()
    session_id = body.session_id or (active.id if active else None)
    if not session_id:
        raise _bad(409, "calibration_session_required", "Start a calibration session first.")
    require_profile_state_write(
        "investor_profile_calibration_message",
        {"session_id": session_id, "turn_id": body.turn_id},
    )
    try:
        work = store.begin_answer_turn(
            session_id=session_id,
            turn_id=body.turn_id,
            answer=body.content,
            provider=body.provider,
            model=body.model,
        )
    except ValueError as exc:
        raise _turn_input_error(exc) from exc
    return await _complete_provider_work(store, work)


@router.post("/turns/{turn_id}/retry")
async def retry_calibration_turn(
    turn_id: str,
    body: CalibrationRetryBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write(
        "investor_profile_calibration_retry", {"turn_id": turn_id}
    )
    try:
        work = store.retry_turn(turn_id, provider=body.provider, model=body.model)
    except ValueError as exc:
        raise _turn_input_error(exc) from exc
    return await _complete_provider_work(store, work)


@router.post("/proposals/request")
async def request_calibration_proposal(
    body: CalibrationProposalRequestBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    active = store.get_active_session()
    session_id = body.session_id or (active.id if active else None)
    if not session_id:
        raise _bad(409, "calibration_session_required", "Start a calibration session first.")
    require_profile_state_write(
        "investor_profile_calibration_proposal_request",
        {"session_id": session_id, "turn_id": body.turn_id},
    )
    try:
        work = store.begin_proposal_turn(
            session_id=session_id,
            turn_id=body.turn_id,
            provider=body.provider,
            model=body.model,
        )
    except ValueError as exc:
        raise _turn_input_error(exc) from exc
    return await _complete_provider_work(store, work)


@router.post("/proposals/{proposal_id}/approve")
def approve_calibration_proposal(
    proposal_id: str,
    body: ApproveProposalBody,
    store: CalibrationStore = Depends(get_investor_calibration_store),
    profile_store: InvestorProfileStore = Depends(get_investor_profile_store),
):
    del body
    require_profile_state_write(
        "investor_profile_calibration_approve", {"proposal_id": proposal_id}
    )
    try:
        profile, proposal = store.approve_proposal(
            proposal_id, profile_store=profile_store
        )
    except ProposalConflictError as exc:
        raise _bad(
            409,
            "proposal_conflict",
            "The calibration proposal conflicts with the current profile.",
            diagnostic=exc.diagnostic,
        ) from exc
    except ValueError as exc:
        code = str(exc)
        if code == "proposal_not_found":
            raise _bad(404, code, "Calibration proposal not found.") from exc
        if code == "proposal_not_draft":
            raise _bad(409, code, "Calibration proposal is no longer pending.") from exc
        raise _bad(400, "invalid_calibration_proposal", "Calibration proposal is invalid.") from exc
    return {"profile": _profile(profile), "proposal": _proposal(proposal)}


@router.post("/proposals/{proposal_id}/reject")
def reject_calibration_proposal(
    proposal_id: str,
    store: CalibrationStore = Depends(get_investor_calibration_store),
):
    require_profile_state_write(
        "investor_profile_calibration_reject", {"proposal_id": proposal_id}
    )
    try:
        proposal = store.reject_proposal(proposal_id)
    except ValueError as exc:
        code = str(exc)
        if code == "proposal_not_found":
            raise _bad(404, code, "Calibration proposal not found.") from exc
        if code == "proposal_not_draft":
            raise _bad(409, code, "Calibration proposal is no longer pending.") from exc
        raise _bad(400, "invalid_calibration_proposal", "Calibration proposal is invalid.") from exc
    return {"proposal": _proposal(proposal)}
