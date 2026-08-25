"""Attended ticker identity transition routes."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.dependencies import get_ticker_identity_service
from src.api.permissions import require_profile_state_write
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
        return service.approve_case(
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
        )
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
        return service.cancel_transition(
            transition_id,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_cancel_ticker_transition",
                {"transition_id": transition_id},
            ),
        )
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
        return service.execute_transition(
            transition_id,
            preview_sha256=body.preview_sha256,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_retry_ticker_transition",
                {"transition_id": transition_id},
            ),
        )
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
        return service.reverse_transition(
            transition_id,
            before_write=lambda: require_profile_state_write(
                "security_lifecycle_reverse_ticker_transition",
                {"transition_id": transition_id},
            ),
        )
    except TickerIdentityStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


__all__ = ["router"]
