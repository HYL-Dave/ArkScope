"""Service-level job catalog and manual execution helpers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from src.agents.config import AgentConfig, get_agent_config
from src.analysis import AnalysisRequest, run_analysis_request, save_analysis_run
from src.monitor.engine import MonitorEngine
from src.service.job_runs_store import JobRunsStore

logger = logging.getLogger(__name__)

JobSource = Literal["api", "chrome_extension"]
JobState = Literal["never_run", "running", "succeeded", "failed"]


class UnknownJobError(KeyError):
    """Raised when the caller refers to an unknown job name."""


class JobNotRunnableError(RuntimeError):
    """Raised when a job exists but is not backend-runnable."""


class JobDisabledError(RuntimeError):
    """Raised when a job is feature-flagged off."""


@dataclass(frozen=True)
class JobDefinition:
    """Static metadata for one service job."""

    name: str
    description: str
    source: JobSource
    runnable_via_api: bool
    feature_flag: Optional[str] = None
    default_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobExecutionState:
    """Last known execution state for one process-local job."""

    last_status: JobState = "never_run"
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_message: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None


@dataclass
class JobRunResult:
    """Normalized response after executing one job."""

    name: str
    status: JobState
    message: str
    started_at: str
    finished_at: str
    result: Dict[str, Any]


_JOB_DEFINITIONS: Dict[str, JobDefinition] = {
    "analysis_watchlist_batch": JobDefinition(
        name="analysis_watchlist_batch",
        description="Run the Phase D analysis pipeline across the configured watchlist or an explicit ticker subset.",
        source="api",
        runnable_via_api=True,
        feature_flag="analysis_pipeline_enabled",
        default_params={"depth": "standard", "persist_reports": False},
    ),
    "monitor_watchlist_scan": JobDefinition(
        name="monitor_watchlist_scan",
        description="Run one monitor scan across the watchlist and return alert summaries.",
        source="api",
        runnable_via_api=True,
        default_params={"notify": False},
    ),
    "sa_alpha_picks_refresh": JobDefinition(
        name="sa_alpha_picks_refresh",
        description="Refresh the Alpha Picks portfolio and article cache. Currently managed by the SA Chrome extension.",
        source="chrome_extension",
        runnable_via_api=False,
        feature_flag="sa_enabled",
    ),
    "sa_market_news_refresh": JobDefinition(
        name="sa_market_news_refresh",
        description="Refresh recent Seeking Alpha market-news metadata and detail pages. Currently managed by the SA Chrome extension.",
        source="chrome_extension",
        runnable_via_api=False,
        feature_flag="sa_enabled",
    ),
}

_JOB_STATE: Dict[str, JobExecutionState] = {
    name: JobExecutionState() for name in _JOB_DEFINITIONS
}


def _utcnow_iso() -> str:
    """Return the current UTC timestamp as ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def _get_job_definition(name: str) -> JobDefinition:
    """Return one job definition or raise."""
    try:
        return _JOB_DEFINITIONS[name]
    except KeyError as exc:
        raise UnknownJobError(name) from exc


def _watchlist_tickers(dal: Any) -> List[str]:
    """Return normalized watchlist tickers from DAL config."""
    watchlist = dal.get_watchlist(include_sectors=False)
    return list(getattr(watchlist, "tickers", []) or [])


def _normalize_tickers(raw: Any) -> List[str]:
    """Normalize a ticker input into uppercased unique symbols."""
    if raw is None:
        return []
    if isinstance(raw, str):
        values = [part.strip() for part in raw.split(",")]
    else:
        values = [str(part).strip() for part in raw]
    normalized: List[str] = []
    seen = set()
    for ticker in values:
        if not ticker:
            continue
        upper = ticker.upper()
        if upper in seen:
            continue
        seen.add(upper)
        normalized.append(upper)
    return normalized


def _availability_reason(job: JobDefinition, config: AgentConfig) -> Optional[str]:
    """Return why a job is unavailable, if applicable."""
    if job.feature_flag and not getattr(config, job.feature_flag):
        if job.feature_flag == "analysis_pipeline_enabled":
            return "Enable analysis_pipeline.enabled to run this job."
        if job.feature_flag == "sa_enabled":
            return "Enable seeking_alpha.enabled to expose this job."
    if not job.runnable_via_api:
        return "This job is currently managed by the SA Chrome extension, not the backend API."
    return None


def list_jobs_status(
    dal: Any,
    *,
    config: Optional[AgentConfig] = None,
) -> List[Dict[str, Any]]:
    """Return job metadata merged with last known execution state.

    Last-state preference: DB-backed ``job_runs`` (sql/011) when available,
    falling back to the process-local ``_JOB_STATE`` cache when the store
    cannot be reached. This keeps the UI honest after process restarts and
    when other processes (Chrome extension, scheduler) record runs.
    """
    cfg = config or get_agent_config()
    watchlist_count = len(_watchlist_tickers(dal))
    store = JobRunsStore(dal)
    db_latest = store.latest_runs_by_name() if store.is_available() else {}

    jobs: List[Dict[str, Any]] = []
    for name, definition in _JOB_DEFINITIONS.items():
        reason = _availability_reason(definition, cfg)
        last = _resolve_last_state(name, db_latest)
        jobs.append(
            {
                "name": definition.name,
                "description": definition.description,
                "source": definition.source,
                "runnable_via_api": definition.runnable_via_api,
                "enabled": reason is None,
                "availability_reason": reason,
                "default_params": dict(definition.default_params),
                "watchlist_ticker_count": watchlist_count,
                "last_status": last["last_status"],
                "last_started_at": last["last_started_at"],
                "last_finished_at": last["last_finished_at"],
                "last_message": last["last_message"],
                "last_result": last["last_result"],
            }
        )
    return jobs


def _resolve_last_state(
    job_name: str,
    db_latest: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Pick DB-backed last state if present, else fall back to process-local."""
    db_row = db_latest.get(job_name)
    if db_row:
        return {
            "last_status": db_row["status"],
            "last_started_at": db_row.get("started_at"),
            "last_finished_at": db_row.get("finished_at"),
            "last_message": db_row.get("message") or db_row.get("error"),
            "last_result": db_row.get("result"),
        }
    state = _JOB_STATE[job_name]
    return {
        "last_status": state.last_status,
        "last_started_at": state.last_started_at,
        "last_finished_at": state.last_finished_at,
        "last_message": state.last_message,
        "last_result": state.last_result,
    }


def _mark_running(job_name: str) -> str:
    """Mark one job as running and return the start timestamp."""
    started_at = _utcnow_iso()
    state = _JOB_STATE[job_name]
    state.last_status = "running"
    state.last_started_at = started_at
    state.last_finished_at = None
    state.last_message = None
    state.last_result = None
    return started_at


def _mark_finished(
    job_name: str,
    *,
    status: JobState,
    message: str,
    result: Dict[str, Any],
    finished_at: str,
) -> None:
    """Persist the last finished state for one job."""
    state = _JOB_STATE[job_name]
    state.last_status = status
    state.last_finished_at = finished_at
    state.last_message = message
    state.last_result = result


def _run_analysis_watchlist_batch(
    dal: Any,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the Phase D pipeline across a ticker batch."""
    requested = _normalize_tickers(params.get("tickers")) or _watchlist_tickers(dal)
    limit = params.get("limit")
    if limit is not None:
        limit = int(limit)
        if limit <= 0:
            raise ValueError("limit must be >= 1")
        requested = requested[:limit]

    depth = str(params.get("depth", "standard")).lower()
    if depth not in {"quick", "standard", "full"}:
        raise ValueError("depth must be one of: quick, standard, full")

    persist_reports = bool(params.get("persist_reports", False))
    items: List[Dict[str, Any]] = []
    persisted_count = 0
    for ticker in requested:
        try:
            output = run_analysis_request(
                AnalysisRequest(
                    ticker=ticker,
                    depth=depth,
                    source="scheduled",
                    mode="batch",
                ),
                dal=dal,
                render_format="markdown",
            )
            item = {
                "ticker": ticker,
                "status": "ok",
                "integrity_status": output.integrity.status,
                "action": output.artifact.final_decision.get("action"),
            }
            if persist_reports:
                saved = save_analysis_run(
                    dal,
                    output,
                    title=f"{ticker} Scheduled Analysis",
                )
                item["saved_report_id"] = saved.id
                item["saved_report_path"] = saved.file_path
                persisted_count += 1
            items.append(item)
        except Exception as exc:  # pragma: no cover - defensive in batch loop
            items.append(
                {
                    "ticker": ticker,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    success_count = sum(1 for item in items if item["status"] == "ok")
    return {
        "requested_count": len(requested),
        "processed_count": len(items),
        "success_count": success_count,
        "failure_count": len(items) - success_count,
        "persisted_count": persisted_count,
        "items": items,
    }


def _serialize_alert(alert: Any) -> Dict[str, Any]:
    """Serialize one monitor alert for API responses."""
    timestamp = getattr(alert, "timestamp", None)
    return {
        "alert_type": getattr(alert, "alert_type", None),
        "severity": getattr(alert, "severity", None),
        "ticker": getattr(alert, "ticker", None),
        "title": getattr(alert, "title", None),
        "message": getattr(alert, "message", None),
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else None,
        "data": dict(getattr(alert, "data", {}) or {}),
    }


def _run_monitor_watchlist_scan(
    dal: Any,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute one monitor scan and summarize the alert mix."""
    explicit_tickers = _normalize_tickers(params.get("tickers"))
    notify = bool(params.get("notify", False))
    engine = MonitorEngine(dal=dal)
    alerts = asyncio.run(
        engine.scan_once(
            tickers=explicit_tickers or None,
            notify=notify,
        )
    )

    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for alert in alerts:
        by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1
        by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1

    return {
        "requested_count": len(explicit_tickers or engine.default_tickers),
        "alert_count": len(alerts),
        "notified": notify,
        "scan_metrics": engine.last_scan_metrics,
        "by_type": by_type,
        "by_severity": by_severity,
        "alerts": [_serialize_alert(alert) for alert in alerts],
    }


def run_job(
    name: str,
    *,
    dal: Any,
    params: Optional[Dict[str, Any]] = None,
    config: Optional[AgentConfig] = None,
    trigger_source: str = "api",
) -> JobRunResult:
    """Execute one backend job, persist a job_runs row, update process-local state."""
    job = _get_job_definition(name)
    cfg = config or get_agent_config()
    unavailable_reason = _availability_reason(job, cfg)
    if job.feature_flag and unavailable_reason:
        raise JobDisabledError(unavailable_reason)
    if not job.runnable_via_api:
        raise JobNotRunnableError(unavailable_reason or "Job is not backend-runnable.")

    payload = dict(job.default_params)
    if params:
        payload.update(params)

    started_at = _mark_running(job.name)
    store = JobRunsStore(dal)
    run_id = store.create_run(
        job.name, trigger_source=trigger_source, payload=payload,
    )

    try:
        if job.name == "analysis_watchlist_batch":
            result = _run_analysis_watchlist_batch(dal, payload)
        elif job.name == "monitor_watchlist_scan":
            result = _run_monitor_watchlist_scan(dal, payload)
        else:  # pragma: no cover - defensive branch
            raise UnknownJobError(job.name)

        finished_at = _utcnow_iso()
        message = _summarize_result(job.name, result)
        _mark_finished(
            job.name,
            status="succeeded",
            message=message,
            result=result,
            finished_at=finished_at,
        )
        if run_id is not None:
            store.finish_run(
                run_id,
                status="succeeded",
                message=message,
                result=result,
            )
        return JobRunResult(
            name=job.name,
            status="succeeded",
            message=message,
            started_at=started_at,
            finished_at=finished_at,
            result=result,
        )
    except Exception as exc:
        finished_at = _utcnow_iso()
        error_str = str(exc)
        result = {"error": error_str}
        _mark_finished(
            job.name,
            status="failed",
            message=error_str,
            result=result,
            finished_at=finished_at,
        )
        if run_id is not None:
            store.finish_run(
                run_id,
                status="failed",
                message=error_str,
                error=error_str,
                result=result,
            )
        raise


def _summarize_result(job_name: str, result: Dict[str, Any]) -> str:
    """Compose a short success message suitable for ``last_message`` UI fields.

    Per-job summary heuristics; falls back to a generic line when the
    result shape is unexpected.
    """
    if not isinstance(result, dict):
        return "Job completed successfully."
    if job_name == "analysis_watchlist_batch":
        ok = result.get("success_count")
        total = result.get("processed_count")
        persisted = result.get("persisted_count")
        if ok is not None and total is not None:
            base = f"Analysis pipeline ok={ok}/{total}"
            if persisted:
                base += f", {persisted} report(s) persisted"
            return base
    if job_name == "monitor_watchlist_scan":
        alerts = result.get("alert_count")
        if alerts is not None:
            return f"Monitor scan emitted {alerts} alert(s)"
    return "Job completed successfully."
