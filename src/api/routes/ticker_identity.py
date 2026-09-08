"""Attended ticker identity transition routes."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from src.api.dependencies import get_ticker_identity_service
from src.api.permissions import require_db_write, require_profile_state_write
from src.security_lifecycle_investigation import LifecycleStoreUnavailable
from src.ticker_identity_service import (
    TickerIdentityConflict,
    TickerIdentityService,
    TickerIdentityStoreUnavailable,
)
from src.ticker_identity_transition import TransitionOptions


router = APIRouter(prefix="/security-lifecycle", tags=["security-lifecycle"])


def _canonical_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("execute_on") from exc
    if parsed.isoformat() != value:
        raise ValueError("execute_on")
    return value


class ApproveTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execute_on: str
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    priority_resolution: Literal["source", "successor"] | None = None
    unhide_successor: bool = False

    @field_validator("execute_on")
    @classmethod
    def validate_execute_on(cls, value):
        return _canonical_date(value)


class RetryTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ConfirmReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(min_length=1, max_length=160)
    packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: Literal["terminal_delisting", "symbol_continuation"]
    execute_on: str | None = None
    priority_resolution: Literal["source", "successor"] | None = None
    unhide_successor: StrictBool = False

    @field_validator("execute_on")
    @classmethod
    def validate_execute_on(cls, value):
        return _canonical_date(value)


def _store_error(exc: Exception) -> HTTPException:
    store = getattr(exc, "store", "profile")
    return HTTPException(
        status_code=503,
        detail={
            "code": f"ticker_identity_{store}_store_unavailable",
            "store": store,
        },
    )


def _not_found(exc: KeyError) -> HTTPException:
    code = str(exc.args[0]) if exc.args else "ticker_identity_not_found"
    return HTTPException(status_code=404, detail={"code": code})


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": str(exc)})


def _conflict(exc: TickerIdentityConflict) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": exc.code})


def _transition_record(value: dict) -> dict:
    return {key: value[key] for key in (
        "transition_id", "kind", "status", "source_ticker", "successor_ticker",
        "execute_on", "approved_preview_sha256", "updated_at",
    )}


def _transition_attempt(value: dict, *, reversing: bool = False) -> dict:
    completed = {"reversed"} if reversing else {"applied", "already_applied"}
    if value["status"] not in completed | {"blocked"}:
        raise TickerIdentityConflict("transition_preview_changed")
    return {"status": value["status"], "block_reasons": value["block_reasons"],
            "transition": _transition_record(value["transition"])}


@router.get("/cases/{case_id}/review")
def prepare_review(
    case_id: str,
    assessment_id: str = Query(min_length=1, max_length=160),
    execute_on: str | None = Query(default=None),
    priority_resolution: Literal["source", "successor"] | None = Query(default=None),
    unhide_successor: bool = Query(default=False),
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    from src.security_lifecycle_review import project_packet

    try:
        packet = service.prepare_review(case_id, assessment_id=assessment_id, options=TransitionOptions(
            execute_on=_canonical_date(execute_on), priority_resolution=priority_resolution, unhide_successor=unhide_successor))
        return project_packet(packet)
    except (TickerIdentityStoreUnavailable, LifecycleStoreUnavailable) as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.post("/cases/{case_id}/confirm-review")
def confirm_review(
    case_id: str,
    body: ConfirmReviewRequest,
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    def before_write():
        detail = {"case_id": case_id}
        require_db_write("security_lifecycle_confirm_review", detail)
        require_profile_state_write("security_lifecycle_confirm_review", detail)

    try:
        return service.confirm_review(case_id, assessment_id=body.assessment_id, packet_sha256=body.packet_sha256,
            action=body.action, options=TransitionOptions(execute_on=body.execute_on,
                priority_resolution=body.priority_resolution, unhide_successor=body.unhide_successor), before_write=before_write)
    except (TickerIdentityStoreUnavailable, LifecycleStoreUnavailable) as exc:
        raise _store_error(exc) from None
    except TickerIdentityConflict as exc:
        raise _conflict(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.get("/review-confirmations/{transition_id}")
def review_confirmation(
    transition_id: str,
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return service.get_review_confirmation(transition_id)
    except (TickerIdentityStoreUnavailable, LifecycleStoreUnavailable) as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.get("/transition-activity")
def list_transition_activity(
    limit: int = Query(default=50, ge=1, le=100),
    unacknowledged_only: bool = Query(default=False),
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return service.list_transition_activity(
            limit=limit,
            unacknowledged_only=unacknowledged_only,
        )
    except TickerIdentityStoreUnavailable as exc:
        raise _store_error(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.post("/transition-activity/{activity_id}/acknowledge")
def acknowledge_transition_activity(
    activity_id: str,
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return service.acknowledge_transition_activity(
            activity_id,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_acknowledge_transition_activity",
                {"activity_id": activity_id},
            ),
        )
    except TickerIdentityStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.get("/cases/{case_id}/transition-preview")
def transition_preview(
    case_id: str,
    execute_on: str | None = Query(default=None),
    priority_resolution: Literal["source", "successor"] | None = Query(
        default=None
    ),
    unhide_successor: bool = Query(default=False),
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return service.preview_case(
            case_id,
            options=TransitionOptions(
                execute_on=_canonical_date(execute_on),
                priority_resolution=priority_resolution,
                unhide_successor=unhide_successor,
            ),
        )
    except (TickerIdentityStoreUnavailable, LifecycleStoreUnavailable) as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.post("/cases/{case_id}/approve-transition")
def approve_transition(
    case_id: str,
    body: ApproveTransitionRequest,
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return _transition_record(service.approve_case(
            case_id,
            options=TransitionOptions(
                execute_on=body.execute_on,
                priority_resolution=body.priority_resolution,
                unhide_successor=body.unhide_successor,
            ),
            preview_sha256=body.preview_sha256,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_approve_ticker_transition",
                {"case_id": case_id},
            ),
        ))
    except (TickerIdentityStoreUnavailable, LifecycleStoreUnavailable) as exc:
        raise _store_error(exc) from None
    except TickerIdentityConflict as exc:
        raise _conflict(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.post("/transitions/{transition_id}/cancel")
def cancel_transition(
    transition_id: str,
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return _transition_record(service.cancel_transition(
            transition_id,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_cancel_ticker_transition",
                {"transition_id": transition_id},
            ),
        ))
    except TickerIdentityStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.post("/transitions/{transition_id}/retry")
def retry_transition(
    transition_id: str,
    body: RetryTransitionRequest,
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return _transition_attempt(service.execute_transition(
            transition_id,
            preview_sha256=body.preview_sha256,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_retry_ticker_transition",
                {"transition_id": transition_id},
            ),
        ))
    except (TickerIdentityStoreUnavailable, LifecycleStoreUnavailable) as exc:
        raise _store_error(exc) from None
    except TickerIdentityConflict as exc:
        raise _conflict(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.post("/transitions/{transition_id}/reverse")
def reverse_transition(
    transition_id: str,
    service: TickerIdentityService = Depends(get_ticker_identity_service),
):
    try:
        return _transition_attempt(service.reverse_transition(
            transition_id,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_reverse_ticker_transition",
                {"transition_id": transition_id},
            ),
        ), reversing=True)
    except TickerIdentityStoreUnavailable as exc:
        raise _store_error(exc) from None
    except TickerIdentityConflict as exc:
        raise _conflict(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


__all__ = ["router"]
