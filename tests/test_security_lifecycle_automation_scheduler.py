"""Tests for the bounded lifecycle-automation scheduler boundary."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from types import SimpleNamespace


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


def test_scheduler_identity_context_uses_bounded_local_aliases_and_ibkr_conids(
    tmp_path,
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
        conn.executemany(
            "INSERT INTO ticker_aliases VALUES (?,?)",
            (("LC", "HAPN"), ("HAPN.PRE", "LC"), ("OLD", "OTHER")),
        )
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )
        conn.executemany(
            "INSERT INTO portfolio_positions VALUES (?,?,?)",
            (
                ("ibkr", "1001", "HAPN"),
                ("ibkr", "1002", "LC"),
                ("ibkr", "2001", "QBTS"),
                ("manual", "ignored", "HAPN"),
            ),
        )
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (market_path, profile_path)
    }

    hints = scheduler._load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=("HAPN", "QBTS"),
    )

    assert hints == {
        "HAPN": {
            "ticker_aliases": ("HAPN", "HAPN.PRE", "LC"),
            "ibkr_conids": (1001, 1002),
        },
        "QBTS": {
            "ticker_aliases": ("QBTS",),
            "ibkr_conids": (2001,),
        },
    }
    case = {
        "case_id": "case-hapn",
        "source": "sec_edgar",
        "ticker": "HAPN",
        "ticker_aliases": hints["HAPN"]["ticker_aliases"],
        "ibkr_conids": hints["HAPN"]["ibkr_conids"],
        "observation": {
            "ticker": "HAPN",
            "cik": "0001409970",
            "issuer_name": "Happen, Inc.",
            "filing_date": "2026-06-18",
            "source_ref": "0001409970-26-000131",
            "filing_form": "25",
            "filing_items": [],
            "kinds": [
                {"event_type": "listing_removal_notice", "effective_date": None}
            ],
        },
    }
    monkeypatch.setattr(scheduler, "_market_path", lambda: market_path)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: profile_path)
    monkeypatch.setattr(scheduler, "_automation_schema_state", lambda _conn: None)
    monkeypatch.setattr(
        scheduler,
        "compose_security_lifecycle",
        lambda _market, _profile: {"cases": [case]},
    )

    loaded = scheduler._load_cases()
    assert len(loaded) == 1
    context = scheduler._identity_context(loaded[0])
    assert context.ticker_aliases == ("HAPN", "HAPN.PRE", "LC")
    assert context.ibkr_conids == (1001, 1002)
    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (market_path, profile_path)
    } == before


def test_sec_transport_byte_diagnostic_is_safe_for_kernel_persistence(monkeypatch):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.security_lifecycle_fact_kernel import _diagnostics
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Transport:
        def diagnostics(self, _budget):
            return {
                "attempt_count": 2,
                "document_count": 1,
                "body_bytes": 4096,
                "governor_wait_ms": 25,
                "rate_limit_retries": 0,
            }

        def close(self):
            pass

    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(),
            facts=(),
            blockers=("sec_evidence_insufficient",),
        ),
    )
    monkeypatch.setattr(
        scheduler,
        "_local_news_evidence",
        lambda _context, at: ((), (), {"news_evidence_count": 0}),
    )
    case = {
        "case_id": "slc_diag",
        "ticker": "DIAG",
        "ticker_aliases": ("DIAG",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "DIAG",
            "cik": "0000000001",
            "issuer_name": "Diagnostic Issuer",
            "filing_date": "2026-08-25",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "kinds": [
                {"event_type": "listing_status_review", "effective_date": None}
            ],
        },
    }

    bundle = scheduler._load_evidence(case, mode="live", at="2026-08-26T00:00:00Z")

    assert _diagnostics(bundle.diagnostics) == (
        '{"ibkr_requests":0,"news_evidence_count":0,"sec_attempt_count":2,'
        '"sec_document_count":1,"sec_governor_wait_ms":25,'
        '"sec_payload_bytes":4096,"sec_rate_limit_retries":0}'
    )


def test_pending_event_monitoring_uses_explicit_dates_and_final_source_check():
    from src.security_lifecycle_sec_evidence import SecSourceDeadline
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "observation": {
            "kinds": [{"event_type": "merger_agreement", "effective_date": None}]
        }
    }
    facts = (
        SimpleNamespace(fact_type="effective_date", value="2026-09-05"),
        SimpleNamespace(
            fact_type="transaction_structure",
            value={"kind": "stock", "terms_status": "complete"},
        ),
    )
    deadline = SecSourceDeadline(
        date="2026-10-15",
        evidence_id="sle_deadline",
        span_start_byte=10,
        span_end_byte=80,
        cited_text="The merger may be terminated by October 15, 2026.",
        cited_text_sha256="a" * 64,
        rule_id="sec.explicit_transaction_termination_date",
        rule_version="4",
    )

    before_effective = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "publisher": "available",
        },
        source_deadlines=(deadline,),
        at="2026-08-26T00:00:00Z",
    )
    assert before_effective is not None
    assert before_effective.retryable is True
    assert before_effective.context["monitoring_reason"] == (
        "event_completion_not_confirmed"
    )
    assert before_effective.context["next_check_at"] == "2026-09-05T00:00:00Z"

    daily = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={},
        source_deadlines=(deadline,),
        at="2026-09-10T00:00:00Z",
    )
    assert daily is not None
    assert daily.context["next_check_at"] == "2026-09-11T00:00:00Z"

    weekly = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={},
        source_deadlines=(deadline,),
        at="2026-09-13T00:00:00Z",
    )
    assert weekly is not None
    assert weekly.context["next_check_at"] == "2026-09-20T00:00:00Z"

    deadline = replace(deadline, date="2026-04-01", rule_version="4")
    final = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "publisher": "available",
        },
        source_deadlines=(deadline,),
        at="2026-08-27T12:00:00Z",
    )
    assert final is not None
    assert final.retryable is False
    assert final.context["monitoring_reason"] == "not_confirmed_as_of"
    assert final.context["source_deadline"] == "2026-04-01"
    assert final.context["as_of"] == "2026-08-27"
    assert final.context["source_deadline_evidence_id"] == "sle_deadline"
    assert final.context["source_deadline_rule_version"] == "4"

    unavailable_final_check = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "publisher": "unavailable",
        },
        source_deadlines=(deadline,),
        at="2026-10-15T12:00:00Z",
    )
    assert unavailable_final_check is not None
    assert unavailable_final_check.retryable is True
    assert unavailable_final_check.context["monitoring_reason"] == (
        "event_completion_not_confirmed"
    )
    assert unavailable_final_check.context["next_check_at"] == (
        "2026-10-22T12:00:00Z"
    )


def test_pending_without_source_deadline_never_becomes_timeless_negative():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "observation": {
            "kinds": [{"event_type": "merger_proxy", "effective_date": None}]
        }
    }
    blocker = scheduler._pending_event_monitoring(
        case,
        (),
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "publisher": "available",
        },
        source_deadlines=(),
        at="2027-08-26T00:00:00Z",
    )
    assert blocker is not None
    assert blocker.retryable is True
    assert blocker.context == {
        "monitoring_reason": "event_completion_not_confirmed",
        "next_check_at": "2027-09-02T00:00:00Z",
    }


def test_effective_date_never_substitutes_for_source_termination_deadline():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "observation": {
            "kinds": [{"event_type": "merger_proxy", "effective_date": None}]
        }
    }
    facts = (SimpleNamespace(fact_type="effective_date", value="2026-09-05"),)

    blocker = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "publisher": "available",
        },
        source_deadlines=(),
        at="2027-08-26T00:00:00Z",
    )

    assert blocker is not None
    assert blocker.retryable is True
    assert blocker.context == {
        "monitoring_reason": "event_completion_not_confirmed",
        "effective_date": "2026-09-05",
        "next_check_at": "2027-09-02T00:00:00Z",
    }


def test_completed_or_resolved_event_does_not_create_monitoring_blocker():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    completed = {
        "observation": {
            "kinds": [{"event_type": "acquisition_completed", "effective_date": None}]
        }
    }
    assert scheduler._pending_event_monitoring(
        completed,
        (),
        source_family_results={},
        source_deadlines=(),
        at="2026-08-26T00:00:00Z",
    ) is None

    resolved = {
        "observation": {
            "kinds": [{"event_type": "merger_agreement", "effective_date": None}]
        }
    }
    facts = (
        SimpleNamespace(
            fact_type="tracked_security_effect",
            value="no_identity_change",
        ),
    )
    assert scheduler._pending_event_monitoring(
        resolved,
        facts,
        source_family_results={},
        source_deadlines=(),
        at="2026-08-26T00:00:00Z",
    ) is None


def test_blocker_normalization_preserves_typed_context_and_retry_schedule():
    from src.security_lifecycle_fact_kernel import AutomationBlocker
    from src.service import security_lifecycle_automation_scheduler as scheduler

    pending = AutomationBlocker(
        code="sec_evidence_insufficient",
        retryable=True,
        context={
            "monitoring_reason": "event_completion_not_confirmed",
            "next_check_at": "2026-09-05T00:00:00Z",
        },
    )
    blockers, retry_at = scheduler._blockers([pending], at="2026-08-26T00:00:00Z")
    assert blockers == (pending,)
    assert retry_at == "2026-09-05T00:00:00Z"
