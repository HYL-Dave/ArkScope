"""Job control routes for backend-runnable service tasks."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_dal
from src.service.jobs import (
    JobDisabledError,
    JobNotRunnableError,
    UnknownJobError,
    list_jobs_status,
    run_job,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
    """Optional request body for POST /jobs/run/{job_name}."""

    tickers: Optional[List[str]] = None
    limit: Optional[int] = Field(default=None, ge=1, le=200)
    depth: Literal["quick", "standard", "full"] = "standard"
    persist_reports: bool = False
    notify: bool = False


class JobRunResponse(BaseModel):
    """Response body for POST /jobs/run/{job_name}."""

    name: str
    status: str
    message: str
    started_at: str
    finished_at: str
    result: Dict[str, Any]


@router.get("/status", response_model=JobsStatusResponse)
def jobs_status(dal=Depends(get_dal)):
    """List available jobs plus last known process-local execution state."""
    jobs = list_jobs_status(dal)
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
        result = run_job(job_name, dal=dal, params=params)
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
