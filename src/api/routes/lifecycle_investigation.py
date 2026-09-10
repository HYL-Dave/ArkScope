"""Target-first investigations. Reads neither dispatch providers nor install journals."""

from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from src.api.dependencies import get_ticker_identity_service
from src.api.permissions import require_db_write, require_profile_state_write
from src.api.routes.ticker_identity import _canonical_date
from src.lifecycle_investigation.controller import InvestigationController
from src.lifecycle_investigation.news import LocalNews
from src.lifecycle_investigation.provider_review import provider_decision, prepare_provider_review
from src.lifecycle_investigation.runtime import InvestigationRuntime, RuntimeStore
from src.lifecycle_investigation.store import InvestigationStore, safe_code
from src.lifecycle_investigation.target import TargetPreflight, Target, provider_observations
from src.lifecycle_web_review import prepare, confirm
from src.security_lifecycle_review import project_packet, now
from src.security_lifecycle_provider_scan import run_provider_scan
from src.ticker_identity_service import TickerIdentityConflict
from src.ticker_identity_transition import TransitionOptions

router = APIRouter(prefix="/security-lifecycle/investigations", tags=["security-lifecycle"])


def dispatch_permission():
    require_db_write("lifecycle_investigation", {"scope": "selected_target"})


@lru_cache(maxsize=1)
def get_controller():
    from src.api.dependencies import _local_state_db_path, get_credential_store, get_oauth_token_store, get_oauth_observation_store
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential
    from src.auth_drivers.chatgpt_oauth_login import refresh_if_needed
    from src.market_data_admin import resolve_market_db_path
    from src.sa_capture_store import resolve_sa_db_path

    def load(selected):
        return resolve_web_credential(selected, store=get_credential_store(), token_store=get_oauth_token_store(),
            refresh_chatgpt=lambda **kw: refresh_if_needed(**kw, observation_store=get_oauth_observation_store()))
    return InvestigationController(InvestigationStore(_local_state_db_path()), credential_loader=load,
        news_factory=lambda: LocalNews(resolve_market_db_path(), resolve_sa_db_path()), before_dispatch=dispatch_permission)


def shutdown_controller():
    if get_controller.cache_info().currsize:
        try:
            get_controller().close()
        finally:
            get_controller.cache_clear()


def get_preflight(service=Depends(get_ticker_identity_service)):
    from src.api.dependencies import get_credential_store
    from src.agents.config import task_route
    from src.market_data_admin import resolve_market_db_path
    from src.sa_capture_store import resolve_sa_db_path
    return TargetPreflight(service, credential_store=get_credential_store(), route_loader=lambda: task_route("lifecycle_investigation"),
        market_path=resolve_market_db_path(), sa_path=resolve_sa_db_path())


def operation(call):
    try:
        return call()
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(404, detail={"code": "investigation_not_found"}) from None
    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc) == "execute_on":
            raise HTTPException(422, detail={"code": "execute_on"}) from None
        code = "review_changed" if isinstance(exc, TickerIdentityConflict) else safe_code(exc)
        if code == "web_execution_failed":
            code = "investigation_unavailable"
        conflicts = {"investigation_preflight_changed", "investigation_running", "investigation_request_changed",
            "investigation_not_actionable", "review_changed", "web_review_ineligible", "web_finding_not_complete",
            "web_source_gaps_not_acknowledged", "web_worker_busy", "target_not_tracked",
            "provider_review_ineligible", "provider_snapshot_changed"}
        raise HTTPException(409 if code in conflicts else 503, detail={"code": code}) from None


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preflight_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,180}$")
    language: Literal["en", "zh-Hant"] = "zh-Hant"


class ConfirmRequest(BaseModel):
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


@router.get("/targets")
def targets(service=Depends(get_ticker_identity_service)):
    def read():
        sources = service._read_service.sources_by_ticker()
        if sources is None:
            raise ValueError("tracking_state_unavailable")
        return {"version": 2, "targets": [{"ticker": ticker} for ticker in sorted(sources) if sources[ticker]]}
    return operation(read)


@router.get("/runtime")
def get_runtime(service=Depends(get_ticker_identity_service)):
    return operation(lambda: RuntimeStore(service.profile_db_path).read().model_dump())


@router.put("/runtime")
def put_runtime(body: InvestigationRuntime, service=Depends(get_ticker_identity_service)):
    def write():
        require_profile_state_write("lifecycle_investigation_runtime", {})
        return RuntimeStore(service.profile_db_path).save(body).model_dump()
    return operation(write)


@router.post("/runtime/reset")
def reset_runtime(service=Depends(get_ticker_identity_service)):
    return put_runtime(InvestigationRuntime(), service)


@router.get("/targets/{ticker}/preflight")
def preflight(ticker: str, language: Literal["en", "zh-Hant"] = "zh-Hant", service=Depends(get_preflight)):
    return operation(lambda: service.prepare(ticker, language=language))


@router.get("/targets/{ticker}/providers")
def providers(ticker: str, service=Depends(get_ticker_identity_service)):
    def read():
        Target(ticker=ticker, as_of=now(service)[:10])
        with service._profile_connection(write=False) as conn:
            conn.execute("BEGIN")
            observations, _ = provider_observations(conn, ticker)
            decision = provider_decision(service, ticker, conn=conn)
        return {"version": 2, "ticker": ticker, "observations": observations, "decision": decision}
    return operation(read)


@router.post("/targets/{ticker}/providers/check")
def check_providers(ticker: str, service=Depends(get_ticker_identity_service)):
    def check():
        Target(ticker=ticker, as_of=now(service)[:10])
        sources = service._read_service.sources_by_ticker()
        if sources is None:
            raise ValueError("tracking_state_unavailable")
        if not sources.get(ticker):
            raise ValueError("target_not_tracked")
        require_db_write("lifecycle_investigation_provider_check", {"ticker": ticker})
        require_profile_state_write("lifecycle_investigation_provider_check", {"ticker": ticker})
        run_provider_scan(profile_path=service.profile_db_path, tickers=(ticker,), at=now(service), target_ticker=ticker)
        return providers(ticker, service)
    return operation(check)


class ProviderReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execute_on: str | None = None
    priority_resolution: Literal["source", "successor"] | None = None
    unhide_successor: bool = False


@router.post("/targets/{ticker}/providers/prepare")
def prepare_providers(ticker: str, body: ProviderReviewRequest, service=Depends(get_ticker_identity_service)):
    def before_write():
        require_db_write("lifecycle_provider_review_prepare", {"ticker": ticker})
        require_profile_state_write("lifecycle_provider_review_prepare", {"ticker": ticker})
    return operation(lambda: project_packet(prepare_provider_review(service, ticker, check_sha256=body.check_sha256,
        options=TransitionOptions(execute_on=_canonical_date(body.execute_on), priority_resolution=body.priority_resolution,
            unhide_successor=body.unhide_successor), before_write=before_write)))


@router.get("/actions")
def pending_actions(service=Depends(get_ticker_identity_service)):
    def read():
        with service._profile_connection(write=False) as conn:
            conn.execute("BEGIN")
            rows = conn.execute("SELECT transition_id FROM ticker_identity_transitions WHERE status IN ('approved','needs_review') ORDER BY execute_on,transition_id").fetchall()
            store, actions = service._store(conn), []
            for row in rows:
                action = store.get(row[0])
                actions.append({key: action[key] for key in ("transition_id", "source_ticker", "successor_ticker", "kind", "execute_on", "approved_preview_sha256")} | {
                    "state": "blocked" if action["status"] == "needs_review" else "scheduled" if action["execute_on"] > service._new_york_date() else "approved"})
        return {"version": 2, "actions": actions}
    return operation(read)


@router.post("/targets/{ticker}/runs", status_code=202)
def start(ticker: str, body: StartRequest, preflight=Depends(get_preflight), controller=Depends(get_controller)):
    def execute():
        dispatch_permission()
        request = preflight.validate_start(ticker, preflight_sha256=body.preflight_sha256, language=body.language)
        return controller.start(**request, request_key=body.request_key)
    return operation(execute)


@router.get("/targets/{ticker}/latest")
def latest(ticker: str, controller=Depends(get_controller)):
    return operation(lambda: controller.latest(ticker))


@router.get("/runs/{run_id}")
def read(run_id: str, controller=Depends(get_controller)):
    return operation(lambda: controller.read(run_id))


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, controller=Depends(get_controller)):
    return operation(lambda: controller.cancel(run_id))


@router.get("/runs/{run_id}/review")
def review(run_id: str, execute_on: str | None = None, priority_resolution: Literal["source", "successor"] | None = None,
           unhide_successor: bool = False, service=Depends(get_ticker_identity_service)):
    return operation(lambda: project_packet(prepare(service, run_id, options=TransitionOptions(
        execute_on=_canonical_date(execute_on), priority_resolution=priority_resolution, unhide_successor=unhide_successor))))


@router.post("/runs/{run_id}/confirm")
def adopt(run_id: str, body: ConfirmRequest, service=Depends(get_ticker_identity_service)):
    def before_write():
        require_db_write("lifecycle_investigation_confirm", {"run_id": run_id})
        require_profile_state_write("lifecycle_investigation_confirm", {"run_id": run_id})
    return operation(lambda: confirm(service, run_id, packet_sha256=body.packet_sha256, action=body.action,
        options=TransitionOptions(execute_on=body.execute_on, priority_resolution=body.priority_resolution,
            unhide_successor=body.unhide_successor), before_write=before_write, acknowledge_source_gaps=body.acknowledge_source_gaps))
