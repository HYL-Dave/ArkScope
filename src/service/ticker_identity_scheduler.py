"""Bounded provider-free execution of approved ticker identity transitions."""

from __future__ import annotations

from collections.abc import Mapping
import json
from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
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


def _job_runs_connection() -> sqlite3.Connection | None:
    """Open existing telemetry without any create-capable filesystem operation."""

    from src.app_records_store import resolve_profile_state_db_path

    path = Path(resolve_profile_state_db_path(None))
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=rw",
            uri=True,
            timeout=5.0,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
    except (OSError, sqlite3.Error):
        if conn is not None:
            conn.close()
        return None
    return conn


def _bounded_result(result: Mapping[str, object]) -> dict:
    if not isinstance(result, Mapping):
        raise ValueError("result")
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
    if bounded["due"] != len(transition_ids):
        raise ValueError("due")
    terminal_count = (
        bounded["applied"]
        + bounded["needs_review"]
        + bounded["already_applied"]
        + len(failed_ids)
    )
    if bounded["due"] != terminal_count:
        raise ValueError("due")
    return bounded


def _failure_incident_key(result: Mapping[str, object]) -> tuple:
    return (
        result["status"],
        result["reason"],
        tuple(sorted(result["failed_transition_ids"])),
    )


def _stored_result(raw: object) -> dict | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return _bounded_result(parsed)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _iso_at(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _witness_started_at(value: datetime, not_before: object) -> str:
    candidate = value
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)
    candidate = candidate.astimezone(timezone.utc)
    if isinstance(not_before, str):
        try:
            boundary = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
            if boundary.tzinfo is None:
                boundary = boundary.replace(tzinfo=timezone.utc)
            boundary = boundary.astimezone(timezone.utc)
            if boundary > candidate:
                candidate = boundary
        except ValueError:
            pass
    return _iso_at(candidate)


def _insert_witness(
    conn: sqlite3.Connection,
    *,
    bounded: Mapping[str, object],
    now: datetime,
    not_before: object,
) -> None:
    failed = bounded["status"] in {"partial", "unavailable"}
    at = _witness_started_at(now, not_before)
    conn.execute(
        """
        INSERT INTO job_runs (
            job_name,status,trigger_source,payload,result,message,error,
            started_at,finished_at,duration_ms,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            _JOB_NAME,
            "failed" if failed else "succeeded",
            "scheduler",
            "{}",
            json.dumps(bounded, sort_keys=True, separators=(",", ":")),
            (
                "ticker_identity_scheduler_failure"
                if failed
                else "ticker_identity_scheduler_recovered"
            ),
            str(bounded["reason"]) if failed else None,
            at,
            at,
            None,
            at,
            at,
        ),
    )


def _log_witness_unavailable(bounded: Mapping[str, object]) -> None:
    logger.warning(
        "ticker identity scheduler witness unavailable status=%s reason=%s "
        "failed_transition_ids=%s",
        bounded["status"],
        bounded["reason"],
        ",".join(bounded["failed_transition_ids"]),
    )


def record_ticker_identity_scheduler_result(
    result: Mapping[str, object],
    *,
    now: datetime,
) -> bool:
    """Persist one deduplicated failure or recovery when telemetry is writable."""

    try:
        bounded = _bounded_result(result)
    except Exception:  # malformed runner output must become a typed witness
        logger.warning("ticker identity scheduler returned an invalid result")
        bounded = ticker_identity_scheduler_failure(
            "ticker_identity_scheduler_failed"
        )
    status = str(bounded["status"])
    if status == "not_installed":
        return True

    conn = _job_runs_connection()
    if conn is None:
        _log_witness_unavailable(bounded)
        return False

    try:
        conn.execute("BEGIN IMMEDIATE")
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_runs'"
        ).fetchone()
        if present is None:
            conn.rollback()
            if status in {"partial", "unavailable"}:
                _log_witness_unavailable(bounded)
                return False
            return True
        latest = conn.execute(
            "SELECT status,result,started_at FROM job_runs WHERE job_name=? "
            "ORDER BY id DESC LIMIT 1",
            (_JOB_NAME,),
        ).fetchone()
        failed = status in {"partial", "unavailable"}
        if failed:
            latest_result = (
                _stored_result(latest["result"])
                if latest is not None and latest["status"] == "failed"
                else None
            )
            if (
                latest_result is not None
                and _failure_incident_key(latest_result)
                == _failure_incident_key(bounded)
            ):
                conn.commit()
                return True
            _insert_witness(
                conn,
                bounded=bounded,
                now=now,
                not_before=latest["started_at"] if latest is not None else None,
            )
            conn.commit()
            return True

        if latest is None or latest["status"] != "failed":
            conn.commit()
            return True
        _insert_witness(
            conn,
            bounded=bounded,
            now=now,
            not_before=latest["started_at"],
        )
        conn.commit()
        return True
    except (OSError, sqlite3.Error):
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        _log_witness_unavailable(bounded)
        return False
    finally:
        conn.close()


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
            if not isinstance(result, Mapping):
                raise ValueError("unsupported_transition_result")
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
                raise ValueError("unsupported_transition_result")
        except Exception as exc:  # one plan must never stop later plans
            logger.warning(
                "ticker transition execution failed transition_id=%s code=%s",
                transition_id,
                type(exc).__name__,
            )
            summary["failed_transition_ids"].append(transition_id)
            continue
    if summary["failed_transition_ids"]:
        summary["status"] = "partial"
        summary["reason"] = "transition_execution_failed"
    return summary


__all__ = [
    "record_ticker_identity_scheduler_result",
    "run_due_ticker_identity_transitions",
    "ticker_identity_scheduler_failure",
]
