"""Bounded provider-free execution of approved ticker identity transitions."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
from typing import Mapping
from zoneinfo import ZoneInfo

from src.api.permissions import require_profile_state_write
from src.ticker_identity_service import (
    TICKER_IDENTITY_STORE_UNAVAILABLE_REASONS,
    TickerIdentityService,
    TickerIdentityStoreUnavailable,
)


logger = logging.getLogger(__name__)
_DEFAULT_LIMIT = 10
_JOB_NAME = "ticker_identity.transitions"
_RUNNER_STATUSES = frozenset(
    {"succeeded", "partial", "unavailable", "not_installed"}
)
_RUNNER_REASONS = TICKER_IDENTITY_STORE_UNAVAILABLE_REASONS | frozenset(
    {"ticker_identity_scheduler_failed", "transition_execution_failed"}
)


def _service() -> TickerIdentityService:
    from src.app_records_store import resolve_profile_state_db_path
    from src.market_data_admin import resolve_market_db_path

    return TickerIdentityService(
        market_db_path=resolve_market_db_path(),
        profile_db_path=resolve_profile_state_db_path(None),
    )


def _new_york_date(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    return now.astimezone(ZoneInfo("America/New_York")).date().isoformat()


def _empty_summary(
    *, status: str = "succeeded", reason: str | None = None
) -> dict:
    return {
        "status": status,
        "reason": reason,
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
    }


def ticker_identity_scheduler_failure(reason: str) -> dict:
    """Return the bounded unavailable shape used by the parent scheduler."""

    if reason not in _RUNNER_REASONS:
        raise ValueError("reason")
    return _empty_summary(status="unavailable", reason=reason)


def _job_store():
    """Open existing telemetry only; failure reporting must never create storage."""

    from src.app_records_store import resolve_profile_state_db_path
    from src.service.job_runs_store import JobRunsLocalStore

    path = Path(resolve_profile_state_db_path(None))
    if not path.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as conn:
            present = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_runs'"
            ).fetchone()
    except (OSError, sqlite3.Error):
        return None
    if present is None:
        return None
    return JobRunsLocalStore(path)


def _bounded_result(result: Mapping[str, object]) -> dict:
    status = str(result.get("status") or "")
    if status not in _RUNNER_STATUSES:
        raise ValueError("status")
    raw_reason = result.get("reason")
    reason = None if raw_reason is None else str(raw_reason)
    if status in {"partial", "unavailable", "not_installed"}:
        if reason not in _RUNNER_REASONS:
            raise ValueError("reason")
    elif reason is not None:
        raise ValueError("reason")

    bounded: dict[str, object] = {"status": status, "reason": reason}
    for key in ("due", "applied", "needs_review", "already_applied"):
        value = result.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10:
            raise ValueError(key)
        bounded[key] = value
    for key in ("transition_ids", "failed_transition_ids"):
        raw_ids = result.get(key)
        if not isinstance(raw_ids, list) or len(raw_ids) > 10:
            raise ValueError(key)
        ids: list[str] = []
        for raw_id in raw_ids:
            if not isinstance(raw_id, str):
                raise ValueError(key)
            value = raw_id
            if not value or len(value) > 128 or "\0" in value:
                raise ValueError(key)
            ids.append(value)
        if len(ids) != len(set(ids)):
            raise ValueError(key)
        bounded[key] = ids
    failed_ids = set(bounded["failed_transition_ids"])
    transition_ids = set(bounded["transition_ids"])
    if not failed_ids.issubset(transition_ids):
        raise ValueError("failed_transition_ids")
    if status == "partial" and not failed_ids:
        raise ValueError("failed_transition_ids")
    if status != "partial" and failed_ids:
        raise ValueError("failed_transition_ids")
    if status in {"unavailable", "not_installed"} and (
        bounded["due"] != 0 or transition_ids
    ):
        raise ValueError("transition_ids")
    return bounded


def record_ticker_identity_scheduler_result(
    result: Mapping[str, object],
    *,
    now: datetime,
) -> bool:
    """Persist one deduplicated failure or recovery when telemetry is writable."""

    bounded = _bounded_result(result)
    status = str(bounded["status"])
    if status == "not_installed":
        return True

    try:
        store = _job_store()
    except Exception:  # telemetry must not stop provider scheduling
        store = None
    if store is None:
        if status in {"partial", "unavailable"}:
            logger.warning(
                "ticker identity scheduler witness unavailable status=%s reason=%s "
                "failed_transition_ids=%s",
                status,
                bounded["reason"],
                ",".join(bounded["failed_transition_ids"]),
            )
            return False
        return True

    latest_rows = store.list_runs(job_name=_JOB_NAME, limit=1)
    latest = latest_rows[0] if latest_rows else None
    if status in {"partial", "unavailable"}:
        if (
            latest is not None
            and latest.get("status") == "failed"
            and latest.get("error") == bounded["reason"]
            and latest.get("result") == bounded
        ):
            return True
        run_id = store.record_completed_run(
            _JOB_NAME,
            status="failed",
            started_at=now,
            finished_at=now,
            trigger_source="scheduler",
            result=bounded,
            message="ticker_identity_scheduler_failure",
            error=str(bounded["reason"]),
        )
        if run_id is None:
            logger.warning(
                "ticker identity scheduler witness unavailable status=%s reason=%s "
                "failed_transition_ids=%s",
                status,
                bounded["reason"],
                ",".join(bounded["failed_transition_ids"]),
            )
            return False
        return True

    if latest is None or latest.get("status") != "failed":
        return True
    run_id = store.record_completed_run(
        _JOB_NAME,
        status="succeeded",
        started_at=now,
        finished_at=now,
        trigger_source="scheduler",
        result=bounded,
        message="ticker_identity_scheduler_recovered",
    )
    if run_id is None:
        logger.warning(
            "ticker identity scheduler recovery witness unavailable reason=%s",
            latest.get("error"),
        )
        return False
    return True


def run_due_ticker_identity_transitions(
    *,
    limit: int = _DEFAULT_LIMIT,
    now: datetime | None = None,
) -> dict:
    """Run a bounded due batch without importing or calling data providers."""

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("limit")
    instant = now or datetime.now(timezone.utc)
    on_date = _new_york_date(instant)
    service = _service()
    try:
        due = service.list_due_transitions(on_date=on_date, limit=limit)
    except TickerIdentityStoreUnavailable as exc:
        status = (
            "not_installed"
            if exc.reason == "identity_schema_absent"
            else "unavailable"
        )
        return _empty_summary(status=status, reason=exc.reason)

    summary = _empty_summary()
    summary["due"] = len(due)
    summary["transition_ids"] = [str(row["transition_id"]) for row in due]
    for transition in due:
        transition_id = str(transition["transition_id"])
        try:
            result = service.execute_transition(
                transition_id,
                preview_sha256=str(transition["approved_preview_sha256"]),
                trigger="scheduler",
                before_write=lambda transition_id=transition_id: (
                    require_profile_state_write(
                        "execute_approved_ticker_transition",
                        {"transition_id": transition_id},
                    )
                ),
            )
        except Exception as exc:  # one plan must never stop later plans
            logger.warning(
                "ticker transition execution failed transition_id=%s code=%s",
                transition_id,
                type(exc).__name__,
            )
            summary["failed_transition_ids"].append(transition_id)
            continue
        status = str(result.get("status") or "")
        if status == "applied":
            summary["applied"] += 1
        elif status == "already_applied":
            summary["already_applied"] += 1
        elif (
            status == "blocked"
            and result.get("transition", {}).get("status") == "needs_review"
        ):
            summary["needs_review"] += 1
        else:
            logger.warning(
                "ticker transition returned unsupported status transition_id=%s",
                transition_id,
            )
            summary["failed_transition_ids"].append(transition_id)
    if summary["failed_transition_ids"]:
        summary["status"] = "partial"
        summary["reason"] = "transition_execution_failed"
    return summary


__all__ = [
    "record_ticker_identity_scheduler_result",
    "run_due_ticker_identity_transitions",
    "ticker_identity_scheduler_failure",
]
