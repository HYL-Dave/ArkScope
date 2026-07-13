"""Guarded, redacted Portfolio capture controls."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_portfolio_capture_service
from src.api.permissions import require_profile_state_write
from src.portfolio_capture import (
    CaptureReviewPreview,
    CaptureStart,
    PortfolioCaptureService,
    PortfolioCaptureStatus,
)
from src.portfolio_capture_types import (
    CaptureRun,
    CaptureRunNotReviewable,
    CaptureRunSuperseded,
    PortfolioCaptureBusy,
    ProviderReadiness,
)


router = APIRouter(prefix="/portfolio/capture", tags=["portfolio"])


class CaptureSettingsBody(BaseModel):
    enabled: bool
    interval_minutes: int = Field(ge=5, le=1440)


class CaptureRunBody(BaseModel):
    trigger: Literal["manual"] = "manual"


@router.get("")
def get_capture_status(
    service: PortfolioCaptureService = Depends(get_portfolio_capture_service),
) -> dict[str, Any]:
    return _status_to_json(service.status())


@router.put("/settings")
def put_capture_settings(
    body: CaptureSettingsBody,
    service: PortfolioCaptureService = Depends(get_portfolio_capture_service),
) -> dict[str, Any]:
    detail = {
        "enabled": body.enabled,
        "interval_minutes": body.interval_minutes,
    }
    require_profile_state_write("portfolio_capture_settings_write", detail)
    return _status_to_json(
        service.update_settings(
            enabled=body.enabled,
            interval_minutes=body.interval_minutes,
        )
    )


@router.post("/runs")
def start_capture_run(
    body: CaptureRunBody,
    service: PortfolioCaptureService = Depends(get_portfolio_capture_service),
) -> dict[str, Any]:
    return _start_to_json(service.trigger(body.trigger, background=True))


@router.post("/runs/{run_id}/apply")
def apply_capture_run(
    run_id: int,
    service: PortfolioCaptureService = Depends(get_portfolio_capture_service),
) -> dict[str, Any]:
    require_profile_state_write("portfolio_capture_apply", {"run_id": run_id})
    try:
        return _review_to_json(service.apply_review_run(run_id))
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "capture_run_not_found", "run_id": run_id},
        ) from exc
    except CaptureRunNotReviewable as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "capture_run_not_reviewable", "run_id": run_id},
        ) from exc
    except CaptureRunSuperseded as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "capture_run_superseded", "run_id": run_id},
        ) from exc
    except PortfolioCaptureBusy as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "portfolio_capture_busy", "run_id": run_id},
        ) from exc


def _status_to_json(status: PortfolioCaptureStatus) -> dict[str, Any]:
    return {
        "settings": {
            "enabled": status.settings.enabled,
            "interval_minutes": status.settings.interval_minutes,
            "source": status.settings.source,
            "provider_configured": status.settings.provider_configured,
        },
        "provider_issue": _provider_issue_to_json(status.provider_issue),
        "running": status.running,
        "next_due_at": status.next_due_at,
        "latest_run": _run_to_json(status.latest_run),
        "recent_runs": [_run_to_json(run) for run in status.recent_runs],
        "review": _review_to_json(status.review),
    }


def _provider_issue_to_json(
    readiness: ProviderReadiness | None,
) -> dict[str, str | None] | None:
    if readiness is None:
        return None
    return {
        "code": readiness.code,
        "status": readiness.status,
        "provider": readiness.provider,
        "field": readiness.field,
    }


def _run_to_json(run: CaptureRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "trigger": run.trigger,
        "state": run.state,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "account_leg_state": run.account_leg_state,
        "execution_leg_state": run.execution_leg_state,
        "position_leg_state": run.position_leg_state,
        "discovered_account_count": run.discovered_account_count,
        "new_account_count": run.new_account_count,
        "archived_activity_count": run.archived_activity_count,
        "inserted_execution_count": run.inserted_execution_count,
        "inserted_commission_count": run.inserted_commission_count,
        "unmatched_count": run.unmatched_count,
        "data_conflict_count": run.data_conflict_count,
        "error_code": run.error_code,
        "error_detail": run.error_detail,
    }


def _start_to_json(start: CaptureStart) -> dict[str, Any]:
    return {
        "accepted": start.accepted,
        "state": start.state,
        "run": _run_to_json(start.run),
        "error_code": start.error_code,
        "error_detail": start.error_detail,
    }


def _review_to_json(
    review: CaptureReviewPreview | None,
) -> dict[str, Any] | None:
    if review is None:
        return None
    return {
        "run_id": review.run_id,
        "changes": [
            {
                "kind": change.kind,
                "account_id": change.account_id,
                "account_label": change.account_label,
                "broker_account_id_hash": change.broker_account_id_hash,
                "broker_con_id": change.broker_con_id,
                "symbol": change.symbol,
                "quantity": change.quantity,
                "before": change.before,
                "after": change.after,
            }
            for change in review.changes
        ],
        "applies": review.applies,
    }
