"""Job control routes for backend-runnable service tasks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.api.dependencies import get_dal
from src.sa.extension_run_protocol import ProtocolError, derive_run_result
from src.service.job_runs_store import get_job_runs_store
from src.service.jobs import (
    JobDisabledError,
    JobNotRunnableError,
    UnknownJobError,
    list_jobs_status,
    run_job,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
_MARKET_NEWS_REPAIR_JOB_NAME = "sa_market_news_repair"


def project_job_run_for_public_history(row: Dict[str, Any]) -> Dict[str, Any]:
    """Remove frozen target descriptors from generic repair history surfaces."""

    if row.get("job_name") != _MARKET_NEWS_REPAIR_JOB_NAME:
        return row
    projected = dict(row)
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
    fingerprint = str(payload.get("manifest_hash") or "")
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    projected["payload"] = {
        "kind": manifest.get("kind"),
        "manifest_hash_prefix": fingerprint[:12] or None,
        "target_count": len(manifest.get("targets") or []),
    }
    projected["result"] = {
        "lifecycle_state": result.get("lifecycle_state"),
        "derived_outcome": result.get("derived_outcome"),
        "reason_code": result.get("reason_code"),
        "counts": result.get("counts") if isinstance(result.get("counts"), dict) else {},
        "manifest_hash_prefix": fingerprint[:12] or None,
    }
    projected["message"] = result.get("derived_outcome") or result.get(
        "lifecycle_state"
    )
    projected["error"] = (
        row.get("error")
        if row.get("error")
        in {"repair_retryable", "operator_cancelled", "manifest_invalid"}
        else None
    )
    return projected


class JobStatusItem(BaseModel):
    """One job entry returned by GET /jobs/status."""

    name: str
    description: str
    source: Literal["api", "chrome_extension"]
    runnable_via_api: bool
    enabled: bool
    availability_reason: Optional[str] = None
    default_params: Dict[str, Any] = Field(default_factory=dict)
    watchlist_ticker_count: int
    last_status: str
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_message: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None


class JobsStatusResponse(BaseModel):
    """Response body for GET /jobs/status."""

    count: int
    jobs: List[JobStatusItem]


class JobRunRequest(BaseModel):
    """Optional request body for POST /jobs/run/{job_name}.

    Field set is union-of-all-jobs; per-job dispatchers in
    ``src/service/jobs.py`` consume only the keys they recognise.
    """

    # analysis_watchlist_batch / monitor_watchlist_scan
    tickers: Optional[List[str]] = None
    # limit: per-job semantic. analysis_watchlist_batch caps tickers
    # processed; fetch_fred_release_dates sets FRED page size (FRED's hard
    # cap is 1000). le=1000 covers both ranges.
    limit: Optional[int] = Field(default=None, ge=1, le=1000)
    depth: Literal["quick", "standard", "full"] = "standard"
    persist_reports: bool = False
    notify: bool = False
    # extract_sa_comment_signals
    batch_size: Optional[int] = Field(default=None, ge=1, le=5000)
    max_extracted: Optional[int] = Field(default=None, ge=1)
    # macro_calendar Finnhub jobs (commit 4)
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    years_back: Optional[int] = Field(default=None, ge=1)
    symbols: Optional[List[str]] = None
    # macro_calendar FRED jobs
    series_ids: Optional[List[str]] = None
    release_ids: Optional[List[int]] = None
    full_refresh: Optional[bool] = None


class JobRunResponse(BaseModel):
    """Response body for POST /jobs/run/{job_name}."""

    name: str
    status: str
    message: str
    started_at: str
    finished_at: str
    result: Dict[str, Any]


class JobRunRow(BaseModel):
    """One row from GET /jobs/history."""

    id: int
    job_name: str
    status: Literal["running", "succeeded", "failed"]
    trigger_source: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: str
    updated_at: str


class JobsHistoryResponse(BaseModel):
    """Response body for GET /jobs/history."""

    count: int
    limit: int
    offset: int
    runs: List[JobRunRow]


class ExtensionJobRecordRequest(BaseModel):
    """Completed SA extension job telemetry submitted by the sidecar-owned endpoint."""

    model_config = ConfigDict(extra="forbid")

    client_event_id: str = Field(min_length=1, max_length=160)
    started_at: str
    finished_at: str
    result: Dict[str, Any]


class ExtensionJobRecordResponse(BaseModel):
    """Sanitized response for native-host best-effort recording."""

    status: Literal["ok", "error"]
    run_id: Optional[int] = None
    persisted: bool = False
    error_code: Optional[str] = None


@router.get("/status", response_model=JobsStatusResponse)
def jobs_status(dal=Depends(get_dal)):
    """List available jobs plus last known process-local execution state."""
    jobs = list_jobs_status(dal)
    repair = get_job_runs_store(dal).get_market_news_repair()
    if repair is not None:
        public = project_job_run_for_public_history(repair)
        jobs = [job for job in jobs if job.get("name") != _MARKET_NEWS_REPAIR_JOB_NAME]
        jobs.append(
            {
                "name": _MARKET_NEWS_REPAIR_JOB_NAME,
                "description": "Audited Seeking Alpha Market News detail repair",
                "source": "chrome_extension",
                "runnable_via_api": False,
                "enabled": True,
                "availability_reason": None,
                "default_params": {},
                "watchlist_ticker_count": 0,
                "last_status": public["status"],
                "last_started_at": public["started_at"],
                "last_finished_at": public["finished_at"],
                "last_message": public["message"],
                "last_result": public["result"],
            }
        )
    return JobsStatusResponse(count=len(jobs), jobs=jobs)


@router.post("/run/{job_name}", response_model=JobRunResponse)
def run_named_job(
    job_name: str,
    request: Optional[JobRunRequest] = None,
    dal=Depends(get_dal),
):
    """Execute one backend-runnable job inline and return the summary."""
    params = request.model_dump(exclude_none=True) if request is not None else {}
    try:
        result = run_job(job_name, dal=dal, params=params, trigger_source="api")
    except UnknownJobError:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}")
    except JobDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except JobNotRunnableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JobRunResponse(
        name=result.name,
        status=result.status,
        message=result.message,
        started_at=result.started_at,
        finished_at=result.finished_at,
        result=result.result,
    )


@router.get("/history", response_model=JobsHistoryResponse)
def jobs_history(
    name: Optional[str] = Query(default=None, description="Filter by job_name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    dal=Depends(get_dal),
):
    """Paginated history of recorded job runs (newest first).

    Reads from the ``job_runs`` table (sql/011). When DB is unavailable
    or the DAL is on FileBackend, returns an empty list with count=0.
    """
    store = get_job_runs_store(dal)
    rows = [
        project_job_run_for_public_history(row)
        for row in store.list_runs(job_name=name, limit=limit, offset=offset)
    ]
    return JobsHistoryResponse(
        count=len(rows),
        limit=limit,
        offset=offset,
        runs=rows,
    )


@router.post("/extension-record", response_model=ExtensionJobRecordResponse)
def record_extension_job(
    request: ExtensionJobRecordRequest,
    dal=Depends(get_dal),
):
    """Best-effort extension job telemetry recording.

    The endpoint owns app-state writes so SA native hosts do not open
    ``profile_state.db`` directly.
    """
    try:
        client_event_id = request.client_event_id.strip()
        started = _extension_timestamp(request.started_at)
        finished = _extension_timestamp(request.finished_at)
        if not client_event_id or started is None or finished is None or finished < started:
            raise ValueError("invalid_extension_event")
        result = derive_run_result(request.result)
        event_document = {
            "client_event_id": client_event_id,
            "started_at": started.isoformat(timespec="milliseconds"),
            "finished_at": finished.isoformat(timespec="milliseconds"),
            "result": result,
        }
        event_hash = hashlib.sha256(
            json.dumps(
                event_document,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        duration_ms = max(0, int((finished - started).total_seconds() * 1000))
    except ProtocolError as exc:
        return ExtensionJobRecordResponse(
            status="error", persisted=False, error_code=exc.code
        )
    except (TypeError, ValueError):
        return ExtensionJobRecordResponse(
            status="error", persisted=False, error_code="invalid_extension_event"
        )

    store = get_job_runs_store(dal)
    try:
        run_id = store.record_extension_event_once(
            client_event_id=client_event_id,
            event_hash=event_hash,
            job_name=result["job_name"],
            status=result["db_status"],
            started_at=event_document["started_at"],
            finished_at=event_document["finished_at"],
            result=result,
            duration_ms=duration_ms,
        )
    except ValueError as exc:
        code = str(exc)
        return ExtensionJobRecordResponse(
            status="error",
            persisted=False,
            error_code=(
                code
                if code in {"event_conflict", "invalid_extension_event"}
                else "invalid_extension_event"
            ),
        )
    except Exception:
        return ExtensionJobRecordResponse(
            status="error",
            persisted=False,
            error_code="extension_persistence_unavailable",
        )
    return ExtensionJobRecordResponse(
        status="ok",
        run_id=run_id,
        persisted=run_id is not None,
    )


def _extension_timestamp(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)
