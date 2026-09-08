"""Explicit Web investigations; reads cannot launch models or install storage."""

from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from src.api.dependencies import get_ticker_identity_service
from src.api.permissions import require_db_write, require_profile_state_write
from src.api.routes.ticker_identity import _canonical_date
from src.auth_drivers.lifecycle_web_models import resolve_web_credential
from src.lifecycle_web_controller import LifecycleWebController, _failure_code
from src.lifecycle_web_preflight import LifecycleWebPreflight
from src.lifecycle_web_review import prepare, confirm
from src.lifecycle_web_store import LifecycleWebStore
from src.security_lifecycle_review import project_packet
from src.ticker_identity_service import TickerIdentityConflict
from src.ticker_identity_transition import TransitionOptions


router = APIRouter(prefix="/security-lifecycle", tags=["security-lifecycle"])
Question = Literal["listing_status", "symbol_continuation"]


def _dispatch_permission():
    require_db_write("security_lifecycle_web_investigation", {"scope": "selected_case"})


@lru_cache(maxsize=1)
def get_web_controller():
    from src.api.dependencies import _local_state_db_path, get_credential_store, get_oauth_token_store, get_oauth_observation_store
    from src.auth_drivers.chatgpt_oauth_login import refresh_if_needed

    def load(selected):
        return resolve_web_credential(selected, store=get_credential_store(), token_store=get_oauth_token_store(),
            refresh_chatgpt=lambda **kwargs: refresh_if_needed(**kwargs, observation_store=get_oauth_observation_store()))
    return LifecycleWebController(LifecycleWebStore(_local_state_db_path()), before_dispatch=_dispatch_permission,
        credential_loader=load)


def shutdown_web_controller():
    if get_web_controller.cache_info().currsize:
        try:
            get_web_controller().close()
        finally:
            get_web_controller.cache_clear()


def get_web_preflight(service=Depends(get_ticker_identity_service)):
    from src.agents.config import task_route, get_agent_config
    from src.api.dependencies import get_credential_store
    from src.sa_capture_store import resolve_sa_db_path

    return LifecycleWebPreflight(service, credential_store=get_credential_store(), route_loader=lambda: task_route("lifecycle_investigation"),
        sa_db_path=resolve_sa_db_path(), output_limit_loader=lambda: get_agent_config().max_tokens)


class StartWebRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question
    preflight_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,180}$")


class ConfirmWebRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: Literal["terminal_delisting", "symbol_continuation"]
    execute_on: str | None = None
    priority_resolution: Literal["source", "successor"] | None = None
    unhide_successor: StrictBool = False
    acknowledge_source_gaps: StrictBool = False

    @field_validator("execute_on")
    @classmethod
    def validate_date(cls, value):
        return _canonical_date(value)


def _operation(call):
    try:
        return call()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(404, detail={"code": "web_record_not_found"}) from None
    except Exception as exc:
        code = _failure_code(exc)
        if isinstance(exc, TickerIdentityConflict):
            code = "review_changed"
        if isinstance(exc, ValueError) and str(exc) in {
            "web_preflight_changed", "review_changed", "web_review_ineligible", "web_finding_not_complete",
            "web_acceptance_already_recorded", "execute_on", "review_action", "review_digest",
        }:
            code = str(exc)
        if code == "web_execution_failed":
            code = "web_operation_unavailable"
        status = 409 if code in {"web_preflight_changed", "review_changed", "web_investigation_running",
                                 "web_request_identity_changed", "web_worker_busy", "web_review_ineligible",
                                 "web_finding_not_complete", "web_acceptance_already_recorded", "web_source_gaps_not_acknowledged"} else 503
        if code in {"execute_on", "review_action", "review_digest"}:
            status = 422
        raise HTTPException(status, detail={"code": code}) from None


@router.get("/cases/{case_id}/web-preflight")
def web_preflight(case_id: str, question: Question, preflight=Depends(get_web_preflight)):
    return _operation(lambda: preflight.prepare(case_id, question=question))


@router.post("/cases/{case_id}/web-runs", status_code=202)
def start_web(case_id: str, body: StartWebRequest, preflight=Depends(get_web_preflight), controller=Depends(get_web_controller)):
    def start():
        _dispatch_permission()
        from src.lifecycle_investigation.retirement import cutover_active
        if cutover_active(preflight.service.profile_db_path):
            raise HTTPException(410, detail={"code": "legacy_lifecycle_intake_retired"})
        request = preflight.validate_start(case_id, question=body.question, preflight_sha256=body.preflight_sha256)
        return controller.start(**request, request_key=body.request_key)
    return _operation(start)


@router.get("/cases/{case_id}/web-runs/latest")
def latest_web(case_id: str, controller=Depends(get_web_controller)):
    return _operation(lambda: controller.latest(case_id))


@router.get("/web-runs/{run_id}")
def get_web(run_id: str, controller=Depends(get_web_controller)):
    return _operation(lambda: controller.read(run_id))


@router.post("/web-runs/{run_id}/cancel")
def cancel_web(run_id: str, controller=Depends(get_web_controller)):
    # Cancellation is permitted after launch authority is withdrawn: otherwise
    # disabling writes could strand a provider request that the user wants stopped.
    return _operation(lambda: controller.cancel(run_id))


@router.get("/web-runs/{run_id}/review")
def web_review(run_id: str, execute_on: str | None = None, priority_resolution: Literal["source", "successor"] | None = None,
               unhide_successor: bool = False, service=Depends(get_ticker_identity_service)):
    return _operation(lambda: project_packet(prepare(service, run_id, options=TransitionOptions(
        execute_on=_canonical_date(execute_on), priority_resolution=priority_resolution, unhide_successor=unhide_successor))))


@router.post("/web-runs/{run_id}/confirm")
def confirm_web(run_id: str, body: ConfirmWebRequest, service=Depends(get_ticker_identity_service)):
    def before_write():
        require_db_write("security_lifecycle_confirm_web", {"run_id": run_id})
        require_profile_state_write("security_lifecycle_confirm_web", {"run_id": run_id})
    return _operation(lambda: confirm(service, run_id, packet_sha256=body.packet_sha256, action=body.action,
        options=TransitionOptions(execute_on=body.execute_on, priority_resolution=body.priority_resolution,
                                  unhide_successor=body.unhide_successor), before_write=before_write,
        acknowledge_source_gaps=body.acknowledge_source_gaps))
