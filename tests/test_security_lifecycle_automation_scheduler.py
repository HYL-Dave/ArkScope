"""Tests for the bounded lifecycle-automation scheduler boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import json


_NOW = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)


def _summary(**overrides):
    result = {
        "status": "succeeded",
        "reason": None,
        "selected": 0,
        "processed": 0,
        "accepted": 0,
        "drafted": 0,
        "blocked": 0,
        "failed": 0,
        "skipped_current": 0,
        "case_ids": [],
    }
    result.update(overrides)
    return result


def test_scheduler_runs_bounded_worker_batch_and_returns_sanitized_summary(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    calls = []

    class Worker:
        def run(self, limit, mode):
            calls.append((limit, mode))
            return {
                **_summary(
                    selected=2,
                    processed=2,
                    accepted=1,
                    drafted=1,
                    case_ids=["slc_a", "slc_b"],
                ),
                "private_payload": {
                    "url": "https://private.invalid",
                    "contact": "secret@example.invalid",
                },
            }

    monkeypatch.setattr(scheduler, "_worker", Worker)

    result = scheduler.run_security_lifecycle_automation(limit=2, now=_NOW)

    assert calls == [(2, "live")]
    assert result == _summary(
        selected=2,
        processed=2,
        accepted=1,
        drafted=1,
        case_ids=["slc_a", "slc_b"],
    )
    assert "private" not in json.dumps(result)


def test_scheduler_reports_schema_absent_as_not_installed(monkeypatch):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Worker:
        def run(self, limit, mode):
            del limit, mode
            raise scheduler.LifecycleAutomationNotInstalled()

    monkeypatch.setattr(scheduler, "_worker", Worker)

    assert scheduler.run_security_lifecycle_automation(now=_NOW) == _summary(
        status="not_installed",
        reason="automation_schema_absent",
    )


def test_scheduler_witness_deduplicates_failure_and_records_recovery(
    tmp_path,
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    telemetry = JobRunsLocalStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    failure = _summary(
        status="partial",
        reason="case_processing_failed",
        selected=2,
        processed=2,
        accepted=1,
        failed=1,
        case_ids=["slc_ok", "slc_failed"],
    )
    recovery = _summary()

    assert scheduler.record_security_lifecycle_automation_result(
        failure,
        now=_NOW,
    )
    assert scheduler.record_security_lifecycle_automation_result(
        failure,
        now=_NOW,
    )
    assert scheduler.record_security_lifecycle_automation_result(
        recovery,
        now=_NOW,
    )
    assert scheduler.record_security_lifecycle_automation_result(
        recovery,
        now=_NOW,
    )

    runs = telemetry.list_runs(job_name="security_lifecycle.automation", limit=10)
    assert [(row["status"], row["message"]) for row in runs] == [
        ("succeeded", "security_lifecycle_automation_recovered"),
        ("failed", "security_lifecycle_automation_failure"),
    ]
    assert runs[1]["result"] == failure
    assert runs[0]["result"] == recovery


def test_scheduler_program_error_is_typed_without_raw_detail(monkeypatch):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Worker:
        def run(self, limit, mode):
            del limit, mode
            raise RuntimeError(
                "/private/profile_state.db https://secret.invalid token@example.invalid"
            )

    monkeypatch.setattr(scheduler, "_worker", Worker)

    result = scheduler.run_security_lifecycle_automation(now=_NOW)

    assert result == _summary(
        status="unavailable",
        reason="automation_scheduler_failed",
    )
    rendered = json.dumps(result)
    assert "private" not in rendered
    assert "invalid" not in rendered
    assert "@" not in rendered
