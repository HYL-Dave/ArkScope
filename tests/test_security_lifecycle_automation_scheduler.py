"""Tests for the bounded lifecycle-automation scheduler boundary."""

from __future__ import annotations

from contextlib import contextmanager
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


def test_scheduler_reports_schema_absent_as_not_installed(tmp_path, monkeypatch):
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    real_worker = scheduler._worker

    class Worker:
        def run(self, limit, mode):
            del limit, mode
            raise scheduler.LifecycleAutomationNotInstalled()

    monkeypatch.setattr(scheduler, "_worker", Worker)

    result = scheduler.run_security_lifecycle_automation(now=_NOW)

    assert result == _summary(
        status="not_installed",
        reason="automation_schema_absent",
    )
    profile_path = tmp_path / "missing" / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    assert scheduler.record_security_lifecycle_automation_result(
        result,
        now=_NOW,
    )
    assert not profile_path.exists()

    pre_cutover_path = tmp_path / "pre-cutover.db"
    JobRunsLocalStore(pre_cutover_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(pre_cutover_path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "market.db"))
    monkeypatch.setattr(scheduler, "_worker", real_worker)
    monkeypatch.setattr(
        scheduler,
        "_load_sources",
        lambda: (_ for _ in ()).throw(
            AssertionError("source loader reached before schema gate")
        ),
    )

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


def test_scheduler_uses_real_provider_free_transition_preflight_and_approver(
    monkeypatch,
):
    from src import ticker_identity_service, ticker_identity_transition
    from src.service import security_lifecycle_automation_scheduler as scheduler

    calls = []
    marker = object()

    @contextmanager
    def profile_connection():
        yield marker

    def build_preflight(conn, *, case, request, sources):
        calls.append(("preview", conn, case, request, sources))
        return {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": request["transition_kind"],
        }

    class Service:
        def __init__(self, **kwargs):
            calls.append(("service", kwargs))

        def approve_automation_case(self, case_id, *, request):
            calls.append(("approve", case_id, request))
            return {
                "transition_id": "tit_1",
                "status": "approved",
                "approval_authority": "automation_policy",
            }

    captured_worker = {}

    class Worker:
        def __init__(self, **kwargs):
            captured_worker.update(kwargs)

    monkeypatch.setattr(scheduler, "_profile_connection", profile_connection)
    monkeypatch.setattr(
        ticker_identity_transition,
        "build_automation_transition_preflight",
        build_preflight,
    )
    monkeypatch.setattr(ticker_identity_service, "TickerIdentityService", Service)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: "/profile.db")
    monkeypatch.setattr(scheduler, "_market_path", lambda: "/market.db")
    monkeypatch.setattr(scheduler, "_load_sources", lambda: {"OLD": ("manual_lists",)})
    monkeypatch.setattr(scheduler, "_assert_automation_installed", lambda: None)
    monkeypatch.setattr(scheduler, "LifecycleAutomationWorker", Worker)

    case = {"case_id": "slc_1", "ticker": "OLD"}
    request = {
        "transition_kind": "symbol_continuation",
        "source_ticker": "OLD",
        "successor_ticker": "NEW",
        "effective_date": "2026-08-25",
        "outcomes": ("symbol_changed",),
    }
    assert scheduler._transition_preview(
        case=case,
        request=request,
        sources=("manual_lists",),
    )["eligible"] is True
    assert scheduler._transition_approver(
        case=case,
        request=request,
        sources=("manual_lists",),
    )["transition_id"] == "tit_1"

    scheduler._worker()
    assert captured_worker["transition_preview"] is scheduler._transition_preview
    assert captured_worker["transition_approver"] is scheduler._transition_approver
    assert calls[0][0] == "preview"
    assert calls[-1] == ("approve", "slc_1", request)
