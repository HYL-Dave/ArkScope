from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest


_AT = "2026-08-20T00:00:00Z"
_SOURCE_REF = "0000712515-26-000042"


def _listing_locator(**overrides):
    locator = {
        "locator_kind": "listing_directory_snapshot",
        "adapter": "massive_reference",
        "authority": "massive",
        "directory": None,
        "candidate_ticker": "B",
        "expected_active_state": True,
        "listing_status": "active",
        "market": "stocks",
        "primary_exchange": "XNAS",
        "security_type": "CS",
        "issuer_cik": "0000000001",
        "composite_figi": None,
        "delisted_utc": None,
        "source_as_of": "2026-08-28",
        "provider_last_updated_utc": None,
        "snapshot_complete": True,
        "source_document_sha256": "b" * 64,
        "adapter_version": "listing-authority-v1",
    }
    locator.update(overrides)
    return locator


def _insert_automation_evidence(
    context,
    *,
    evidence_id,
    source_family,
    kind,
    adapter,
    excerpt,
    source_url=None,
    source_document_sha256=None,
    source_locator=None,
):
    run_id = str(context["profile_conn"].execute(
        "SELECT run_id FROM security_lifecycle_automation_runs LIMIT 1"
    ).fetchone()[0])
    context["profile_conn"].execute(
        "INSERT INTO security_lifecycle_evidence "
        "(evidence_id,case_id,run_id,automation_run_id,source_family,kind,"
        "source_url,title,publisher,domain,source_published_at,retrieved_at,"
        "adapter,excerpt,content_sha256,source_document_sha256,"
        "source_locator_json,evidence_dedupe_key,mime_type,document_status,"
        "created_at) VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?)",
        (
            evidence_id,
            context["case_id"],
            run_id,
            source_family,
            kind,
            source_url,
            f"{source_family} fixture",
            f"{source_family} fixture",
            "example.com",
            "2026-08-28",
            _AT,
            adapter,
            excerpt,
            hashlib.sha256(excerpt.encode()).hexdigest(),
            source_document_sha256,
            json.dumps(source_locator or {}, separators=(",", ":"), sort_keys=True),
            f"route-projection:{evidence_id}",
            "application/json",
            _AT,
        ),
    )


def _build_context(
    tmp_path,
    *,
    with_observation=True,
    materialize_profile_case=True,
):
    from src.security_lifecycle import (
        LifecycleObservation,
        ObservationKind,
        SecurityLifecycleStore,
    )
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        case_id_for,
        observation_fingerprint,
    )
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService
    from src.profile_state import ProfileStateStore

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    market_conn = sqlite3.connect(market_path)
    market_store = SecurityLifecycleStore(market_conn)
    observation = None
    if with_observation:
        market_store.upsert_observation(
            LifecycleObservation(
                ticker="EA",
                cik="0000712515",
                issuer_name="Electronic Arts Inc.",
                filing_date="2026-08-04",
                source="sec_edgar",
                source_ref=_SOURCE_REF,
                filing_form="8-K",
                filing_items=("2.01", "3.01"),
                evidence_url="https://www.sec.gov/Archives/example/ea-8k.htm",
                description="Completion of acquisition and listing review.",
                observed_at=_AT,
                kinds=(
                    ObservationKind("acquisition_completed", "2026-08-04"),
                    ObservationKind("listing_status_review", None),
                ),
            )
        )
        observation = market_store.get_observation("sec_edgar", _SOURCE_REF, "EA")
    market_conn.close()

    profile_conn = sqlite3.connect(profile_path, check_same_thread=False)
    profile_store = SecurityLifecycleInvestigationStore(
        profile_conn,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    if materialize_profile_case:
        case_id = profile_store.ensure_case(
            source="sec_edgar",
            source_ref=_SOURCE_REF,
            ticker="EA",
            at=_AT,
        )
    else:
        case_id = case_id_for("sec_edgar", _SOURCE_REF, "EA")
    fingerprint = observation_fingerprint(observation) if observation else ""
    service = SecurityLifecycleReadService(
        market_db_path=str(market_path),
        profile_db_path=str(profile_path),
        source_loader=lambda: {"EA": ("manual_lists",)},
    )
    settings_store = ProfileStateStore(profile_path)
    return {
        "market_path": market_path,
        "profile_path": profile_path,
        "profile_conn": profile_conn,
        "store": profile_store,
        "settings_store": settings_store,
        "service": service,
        "case_id": case_id,
        "fingerprint": fingerprint,
    }


def _client(context, monkeypatch, *, permissions=None):
    from src.api import dependencies
    from src.api.routes import security_lifecycle as routes

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[dependencies.get_security_lifecycle_read_service] = (
        lambda: context["service"]
    )
    app.dependency_overrides[dependencies.get_security_lifecycle_store] = (
        lambda: context["store"]
    )
    app.dependency_overrides[dependencies.get_profile_store] = (
        lambda: context["settings_store"]
    )
    monkeypatch.setattr(routes, "_utc_now", lambda: _AT)
    if permissions is not None:
        monkeypatch.setattr(routes, "require_db_write", permissions)
        monkeypatch.setattr(routes, "require_profile_state_write", permissions)
    return TestClient(app)


def _add_manual(client, case_id):
    response = client.post(
        f"/security-lifecycle/cases/{case_id}/evidence",
        json={"text": "Official issuer evidence.", "url": None},
    )
    assert response.status_code == 200
    return response.json()["evidence_id"]


def _create_draft(client, context, evidence_id):
    response = client.post(
        f"/security-lifecycle/cases/{context['case_id']}/assessments",
        json={
            "relevance": "direct_tracked_security",
            "confidence": "high",
            "conclusion": "The transaction affects the tracked security.",
            "impact_summary": "Review the symbol membership before acting.",
            "outcomes": ["acquisition_stock"],
            "citations": [
                {
                    "reference_kind": "observation",
                    "cited_content_sha256": context["fingerprint"],
                },
                {"reference_kind": "evidence", "evidence_id": evidence_id}
            ],
            "successor_ticker": "EA2",
        },
    )
    assert response.status_code == 200
    return response.json()["assessment_id"]


def _create_automation_draft(context):
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_fact_kernel import (
        AutomationEvidence,
        AutomationFact,
        SecurityLifecycleFactKernel,
    )
    from src.security_lifecycle_investigation import create_automation_assessment

    kernel = SecurityLifecycleFactKernel(context["store"])
    claim = kernel.reserve_run(
        case_id=context["case_id"],
        observation_fingerprint_sha256=context["fingerprint"],
        policy_version=AUTOMATION_POLICY_VERSION,
        mode="historical",
        execution_revision="trusted-lifecycle-execution-r1",
        execution_owner_id="test-routes-owner",
        query_context={"case_id": context["case_id"], "ticker": "EA"},
        diagnostics={"sec_attempts": 0},
        at=_AT,
    )
    excerpt = "The tracked security may continue under ticker EA2."
    evidence = AutomationEvidence(
        evidence_id="sec-evidence",
        source_family="regulator",
        adapter="sec_edgar",
        kind="regulator_excerpt",
        source_url="https://www.sec.gov/Archives/example/ea-8k.htm",
        title="EA filing",
        publisher="SEC EDGAR",
        domain="sec.gov",
        source_published_at="2026-08-20",
        retrieved_at=_AT,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_document_sha256="d" * 64,
        source_locator={"accession": _SOURCE_REF},
        evidence_dedupe_key="sec:route",
    )
    start = excerpt.encode().index(b"EA2")
    fact = AutomationFact(
        evidence_id=evidence.evidence_id,
        fact_type="successor_ticker",
        normalized_value="EA2",
        source_span_start=start,
        source_span_end=start + 3,
        cited_text_sha256=hashlib.sha256(b"EA2").hexdigest(),
        extractor_rule_id="sec.symbol_change",
        extractor_rule_version="1",
    )
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(evidence,),
        facts=(fact,),
        blockers=(),
        decision_tier="review_suggested",
        action_readiness="action_blocked",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_AT,
    )
    return create_automation_assessment(
        store=context["store"],
        run_id=claim.run_id,
        decision={
            "decision_tier": "review_suggested",
            "action_readiness": "action_blocked",
            "relevance": "direct_tracked_security",
            "confidence": "medium",
            "outcomes": ("symbol_changed",),
            "conclusion": "The tracked security may continue under ticker EA2.",
            "impact_summary": "Review the cited identity evidence.",
            "successor_ticker": "EA2",
            "destination_venue": "NASDAQ",
            "effective_date": "2026-08-25",
            "counterparty_name": None,
            "counterparty_ticker": None,
            "counterparty_cik": None,
            "consideration_currency": None,
            "cash_per_security_decimal": None,
            "exchange_ratio_decimal": None,
            "rule_id": "lifecycle.simple_symbol_continuation",
            "rule_version": "1",
            "decision_issues": ("preview:successor_hidden",),
            "transition_requested": False,
        },
        observation_fingerprint_sha256=context["fingerprint"],
        at=_AT,
    )


def test_accept_assessment_route_keeps_action_execution_out_of_scope(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
        assessment_id = _create_draft(client, context, evidence_id)
        response = client.post(
            f"/security-lifecycle/assessments/{assessment_id}/accept"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assessment"]["status"] == "accepted"
        assert payload["assessment"]["acceptance_authority"] == "human"
        assert {item["action_type"] for item in payload["proposals"]} == {
            "archive_manual_memberships",
            "notify",
        }
        assert all(item["status"] == "proposed" for item in payload["proposals"])
        assert not hasattr(context["store"], "apply_action_proposal")
    finally:
        context["profile_conn"].close()


def test_accepting_automation_suggestion_retains_automation_authorship_and_human_authority(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path)
    try:
        assessment_id = _create_automation_draft(context)
        client = _client(context, monkeypatch)

        response = client.post(
            f"/security-lifecycle/assessments/{assessment_id}/accept"
        )

        assert response.status_code == 200
        assessment = response.json()["assessment"]
        assert assessment["status"] == "accepted"
        assert assessment["author"] == "automation"
        assert assessment["acceptance_authority"] == "human"
        assert assessment["automation_method"] == "deterministic_rule"
        assert assessment["automation_run_id"] is not None
        assert assessment["rule_id"] == "lifecycle.simple_symbol_continuation"
        assert response.json()["proposals"]
    finally:
        context["profile_conn"].close()


def test_acknowledge_and_reopen_routes_preserve_distinct_workflow_commands(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client = _client(context, monkeypatch)
        _add_manual(client, context["case_id"])
        acknowledged = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/acknowledgements",
            json={"reason": "evidence_insufficient", "note": "No decisive source."},
        )
        assert acknowledged.status_code == 200
        acknowledgement_id = acknowledged.json()["acknowledgement_id"]
        assert client.get(
            f"/security-lifecycle/cases/{context['case_id']}"
        ).json()["workflow_state"] == "reviewed_inconclusive"
        reopened = client.post(
            f"/security-lifecycle/acknowledgements/{acknowledgement_id}/reopen"
        )
        assert reopened.status_code == 200
        assert reopened.json() == {
            "acknowledgement_id": acknowledgement_id,
            "status": "reopened",
        }
    finally:
        context["profile_conn"].close()


def test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes():
    from src.api.app import create_app

    rows = {
        (method, route.path)
        for route in create_app().routes
        for method in sorted(route.methods or ())
        if method not in {"HEAD", "OPTIONS"}
    }
    expected = {
        ("GET", "/security-lifecycle/automation"),
        ("PUT", "/security-lifecycle/automation"),
        ("GET", "/security-lifecycle/cases"),
        ("GET", "/security-lifecycle/cases/{case_id}"),
        ("POST", "/security-lifecycle/automation/run"),
        ("POST", "/security-lifecycle/cases/{case_id}/automation/run"),
        ("GET", "/security-lifecycle/investigations/{run_id}"),
        ("POST", "/security-lifecycle/acknowledgements/{acknowledgement_id}/reopen"),
        ("POST", "/security-lifecycle/action-proposals/{proposal_id}/dismiss"),
        ("POST", "/security-lifecycle/assessments/{assessment_id}/accept"),
        ("POST", "/security-lifecycle/cases/{case_id}/acknowledgements"),
        ("POST", "/security-lifecycle/cases/{case_id}/assessments"),
        ("POST", "/security-lifecycle/cases/{case_id}/evidence"),
        ("GET", "/security-lifecycle/cases/{case_id}/transition-preview"),
        ("POST", "/security-lifecycle/cases/{case_id}/approve-transition"),
        ("POST", "/security-lifecycle/transitions/{transition_id}/cancel"),
        ("POST", "/security-lifecycle/transitions/{transition_id}/retry"),
        ("POST", "/security-lifecycle/transitions/{transition_id}/reverse"),
        ("GET", "/security-lifecycle/transition-activity"),
        (
            "POST",
            "/security-lifecycle/transition-activity/{activity_id}/acknowledge",
        ),
        (
            "POST",
            "/security-lifecycle/evidence/{evidence_id}/translations",
        ),
    }
    assert expected <= rows
    assert len(rows) == 191
    assert (
        "POST",
        "/security-lifecycle/cases/{case_id}/investigations",
    ) not in rows
    assert {
        ("GET", "/market-data/security-lifecycle"),
        ("PUT", "/market-data/security-lifecycle/events/{event_id}"),
        ("PUT", "/market-data/security-lifecycle/relationships/{relationship_id}"),
    }.isdisjoint(rows)


def test_automation_config_get_defaults_and_put_replaces_all_four_keys(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes

    context = _build_context(tmp_path)
    permission_calls = []
    monkeypatch.setattr(
        routes,
        "_automation_now",
        lambda: datetime(2026, 8, 31, 5, 0, tzinfo=timezone.utc),
    )
    try:
        client = _client(
            context,
            monkeypatch,
            permissions=lambda action, detail: permission_calls.append(
                (action, detail)
            ),
        )

        initial = client.get("/security-lifecycle/automation")
        assert initial.status_code == 200
        assert initial.json()["config_status"] == "valid"
        assert initial.json()["config"] == {
            "enabled": True,
            "interval_minutes": 5,
            "batch_limit": 2,
            "apply_profile_transitions": False,
        }
        assert initial.json()["schedule"] == {
            "status": "due",
            "last_attempt_at": None,
            "next_scheduled_at": "2026-08-31T05:00:00Z",
        }
        assert initial.json()["current_progress"] == []
        assert initial.json()["telemetry_status"] == "absent"
        assert initial.json()["latest_failed_runs"] == []

        replacement = {
            "enabled": False,
            "interval_minutes": 60,
            "batch_limit": 1,
            "apply_profile_transitions": True,
        }
        updated = client.put(
            "/security-lifecycle/automation",
            json=replacement,
        )
        assert updated.status_code == 200
        assert updated.json() == {
            "config_status": "valid",
            "config": replacement,
        }
        after = client.get("/security-lifecycle/automation").json()
        assert after["config_status"] == "valid"
        assert after["config"] == replacement
        assert after["schedule"] == {
            "status": "disabled",
            "last_attempt_at": None,
            "next_scheduled_at": None,
        }
        assert permission_calls == [
            ("security_lifecycle_automation_config_update", replacement)
        ]
    finally:
        context["profile_conn"].close()


def test_automation_status_combines_shared_schedule_durable_truth_and_live_progress(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    context = _build_context(tmp_path)
    registry = LifecycleAutomationProgressRegistry()
    registry.begin(
        trigger="manual_case",
        request_id="slao_status_request",
        case_id=context["case_id"],
        started_at=datetime(2026, 8, 31, 4, 59, tzinfo=timezone.utc),
    )
    registry.advance(
        request_id="slao_status_request",
        case_id=context["case_id"],
        stage="sec",
    )
    latest_result = {
        "status": "partial",
        "reason": "case_processing_failed",
        "selected": 1,
        "processed": 1,
        "accepted": 0,
        "drafted": 0,
        "blocked": 0,
        "failed": 1,
        "skipped_current": 0,
        "case_ids": [context["case_id"]],
        "result_version": 2,
        "case_outcomes": {context["case_id"]: "failed"},
    }
    durable = {
        "telemetry_status": "valid",
        "last_attempt": "2026-08-31T04:55:00Z",
        "last_status": "failed",
        "latest_result": latest_result,
        "active_incident": {
            "case_failures": {
                context["case_id"]: {
                    "run_id": "slar_failed",
                    "recovery": "new_attempt",
                }
            },
            "scheduler_failure": None,
        },
        "latest_failed_runs": [
            {
                "run_id": "slar_failed",
                "case_id": context["case_id"],
                "failure_code": "internal_error",
                "started_at": "2026-08-31T04:55:00Z",
                "finished_at": "2026-08-31T04:55:01Z",
                "updated_at": "2026-08-31T04:55:01Z",
            }
        ],
    }
    monkeypatch.setattr(
        routes,
        "read_security_lifecycle_automation_durable_status",
        lambda _path: durable,
        raising=False,
    )
    monkeypatch.setattr(
        routes,
        "lifecycle_automation_progress_registry",
        lambda: registry,
        raising=False,
    )
    monkeypatch.setattr(
        routes,
        "_automation_now",
        lambda: datetime(2026, 8, 31, 5, 0, tzinfo=timezone.utc),
        raising=False,
    )
    try:
        response = _client(context, monkeypatch).get(
            "/security-lifecycle/automation"
        )

        assert response.status_code == 200
        assert response.json() == {
            "config_status": "valid",
            "config": {
                "enabled": True,
                "interval_minutes": 5,
                "batch_limit": 2,
                "apply_profile_transitions": False,
            },
            "schedule": {
                "status": "due",
                "last_attempt_at": "2026-08-31T04:55:00Z",
                "next_scheduled_at": "2026-08-31T05:00:00Z",
            },
            "telemetry_status": "valid",
            "last_status": "failed",
            "last_result": latest_result,
            "active_incident": durable["active_incident"],
            "latest_failed_runs": durable["latest_failed_runs"],
            "current_progress": [
                {
                    "trigger": "manual_case",
                    "request_id": "slao_status_request",
                    "case_id": context["case_id"],
                    "started_at": "2026-08-31T04:59:00Z",
                    "current_stage": "sec",
                    "completed_stages": ["preparing"],
                    "skipped_stages": [],
                }
            ],
        }
    finally:
        context["profile_conn"].close()


def test_automation_status_after_restart_uses_reconciled_failure_not_fake_stage(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes
    from src.scheduler_state import SchedulerStateStore
    from src.security_lifecycle_fact_kernel import SecurityLifecycleFactKernel
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    context = _build_context(tmp_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(context["profile_path"]))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    JobRunsLocalStore(context["profile_path"])
    claim = SecurityLifecycleFactKernel(context["store"]).reserve_run(
        case_id=context["case_id"],
        observation_fingerprint_sha256=context["fingerprint"],
        policy_version="trusted-lifecycle-automation-v4",
        mode="live",
        execution_revision="trusted-lifecycle-execution-r1",
        execution_owner_id="previous-process-owner",
        query_context={"case_id": context["case_id"], "ticker": "EA"},
        diagnostics={},
        at="2026-08-31T04:55:00Z",
    )
    SchedulerStateStore(context["profile_path"]).record_attempt(
        "security_lifecycle.automation",
        datetime(2026, 8, 31, 4, 55, tzinfo=timezone.utc),
    )
    assert scheduler.reconcile_interrupted_security_lifecycle_automation(
        now=datetime(2026, 8, 31, 5, 0, tzinfo=timezone.utc)
    )["status"] == "reconciled"
    restarted_registry = LifecycleAutomationProgressRegistry()
    monkeypatch.setattr(
        routes,
        "lifecycle_automation_progress_registry",
        lambda: restarted_registry,
    )
    monkeypatch.setattr(
        routes,
        "_automation_now",
        lambda: datetime(2026, 8, 31, 5, 0, tzinfo=timezone.utc),
    )
    try:
        response = _client(context, monkeypatch).get(
            "/security-lifecycle/automation"
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["current_progress"] == []
        assert payload["last_status"] == "failed"
        assert payload["active_incident"]["case_failures"] == {
            context["case_id"]: {
                "run_id": claim.run_id,
                "recovery": "new_attempt",
            }
        }
        assert payload["latest_failed_runs"] == [
            {
                "run_id": claim.run_id,
                "case_id": context["case_id"],
                "failure_code": "internal_error",
                "started_at": "2026-08-31T04:55:00Z",
                "finished_at": "2026-08-31T05:00:00Z",
                "updated_at": "2026-08-31T05:00:00Z",
            }
        ]
    finally:
        context["profile_conn"].close()


@pytest.mark.parametrize(
    "body",
    [
        {
            "enabled": True,
            "interval_minutes": 5,
            "batch_limit": 2,
        },
        {
            "enabled": True,
            "interval_minutes": 5,
            "batch_limit": 2,
            "apply_profile_transitions": False,
            "unexpected": True,
        },
        {
            "enabled": "true",
            "interval_minutes": 5,
            "batch_limit": 2,
            "apply_profile_transitions": False,
        },
    ],
)
def test_automation_config_put_requires_an_exact_strict_body(
    tmp_path,
    monkeypatch,
    body,
):
    context = _build_context(tmp_path)
    try:
        response = _client(context, monkeypatch).put(
            "/security-lifecycle/automation",
            json=body,
        )
        assert response.status_code == 422
        assert context["settings_store"].get_settings_snapshot(
            (
                "security_lifecycle.automation.enabled",
                "security_lifecycle.automation.interval_minutes",
                "security_lifecycle.automation.batch_limit",
                "security_lifecycle.automation.apply_profile_transitions",
            )
        ) == {}
    finally:
        context["profile_conn"].close()


def test_invalid_stored_automation_config_is_visible_and_blocks_manual_run(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes

    context = _build_context(tmp_path)
    context["settings_store"].set_setting(
        "security_lifecycle.automation.interval_minutes",
        "05",
    )
    dispatch_calls = []
    monkeypatch.setattr(
        routes,
        "dispatch_and_record_security_lifecycle_automation",
        lambda **kwargs: dispatch_calls.append(kwargs) or {"status": "started"},
    )
    try:
        client = _client(context, monkeypatch, permissions=lambda *_args: None)
        status = client.get("/security-lifecycle/automation")
        run = client.post("/security-lifecycle/automation/run")

        assert status.status_code == 200
        assert status.json()["config_status"] == "invalid"
        assert status.json()["config"] is None
        assert status.json()["invalid_keys"] == [
            "security_lifecycle.automation.interval_minutes"
        ]
        assert status.json()["schedule"] == {
            "status": "invalid",
            "last_attempt_at": None,
            "next_scheduled_at": None,
        }
        assert status.json()["current_progress"] == []
        assert run.status_code == 409
        assert run.json()["detail"] == {
            "code": "automation_config_invalid",
            "invalid_keys": [
                "security_lifecycle.automation.interval_minutes"
            ],
        }
        assert dispatch_calls == []
    finally:
        context["profile_conn"].close()


@pytest.mark.parametrize(
    "endpoint",
    (
        "/security-lifecycle/automation/run",
        "/security-lifecycle/cases/{case_id}/automation/run",
    ),
)
def test_manual_run_reports_profile_config_store_failure_as_typed_503(
    tmp_path,
    monkeypatch,
    endpoint,
):
    context = _build_context(tmp_path)

    def unavailable(_keys):
        raise sqlite3.OperationalError("private path must not leak")

    monkeypatch.setattr(
        context["settings_store"],
        "get_settings_snapshot",
        unavailable,
    )
    try:
        response = _client(
            context,
            monkeypatch,
            permissions=lambda *_args: None,
        ).post(endpoint.format(case_id=context["case_id"]))

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "code": "security_lifecycle_profile_store_unavailable",
            "store": "profile",
        }
        assert "private path" not in response.text
    finally:
        context["profile_conn"].close()


def test_manual_run_bypasses_disabled_schedule_but_uses_batch_and_live_mutation_gate(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes
    from src.service.security_lifecycle_automation_config import (
        APPLY_PROFILE_TRANSITIONS_KEY,
    )

    context = _build_context(tmp_path)
    context["settings_store"].update_settings(
        {
            "security_lifecycle.automation.enabled": "false",
            "security_lifecycle.automation.interval_minutes": "60",
            "security_lifecycle.automation.batch_limit": "1",
            APPLY_PROFILE_TRANSITIONS_KEY: "false",
        }
    )
    dispatch_calls = []
    monkeypatch.setattr(
        routes,
        "dispatch_and_record_security_lifecycle_automation",
        lambda **kwargs: dispatch_calls.append(kwargs) or {"status": "started"},
    )
    try:
        response = _client(
            context,
            monkeypatch,
            permissions=lambda *_args: None,
        ).post("/security-lifecycle/automation/run")

        assert response.status_code == 200
        assert response.json() == {"scope": "due", "status": "started"}
        assert len(dispatch_calls) == 1
        call = dispatch_calls[0]
        mutation_allowed = call.pop("transition_mutation_allowed")
        assert call == {"limit": 1, "trigger": "manual_due"}
        assert mutation_allowed() is False
        context["settings_store"].set_setting(
            APPLY_PROFILE_TRANSITIONS_KEY,
            "true",
        )
        assert mutation_allowed() is True
    finally:
        context["profile_conn"].close()


def test_global_automation_run_dispatches_the_recorded_due_boundary(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes

    context = _build_context(tmp_path)
    permission_calls = []
    dispatch_calls = []

    try:
        monkeypatch.setattr(
            routes,
            "dispatch_and_record_security_lifecycle_automation",
            lambda **kwargs: dispatch_calls.append(kwargs) or {"status": "started"},
        )
        client = _client(
            context,
            monkeypatch,
            permissions=lambda action, detail: permission_calls.append(
                (action, detail)
            ),
        )

        response = client.post("/security-lifecycle/automation/run")

        assert response.status_code == 200
        assert response.json() == {"scope": "due", "status": "started"}
        mutation_allowed = dispatch_calls[0].pop("transition_mutation_allowed")
        assert mutation_allowed() is False
        assert dispatch_calls == [{"limit": 2, "trigger": "manual_due"}]
        assert permission_calls == [
            ("security_lifecycle_run_automation", {"scope": "due"})
        ]
    finally:
        context["profile_conn"].close()


def test_case_automation_run_dispatches_exact_attended_authority(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes

    context = _build_context(tmp_path)
    dispatch_calls = []

    try:
        monkeypatch.setattr(
            routes,
            "dispatch_and_record_security_lifecycle_automation",
            lambda **kwargs: dispatch_calls.append(kwargs) or {"status": "started"},
        )
        client = _client(context, monkeypatch, permissions=lambda *_args: None)

        response = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/automation/run"
        )

        assert response.status_code == 200
        assert response.json() == {
            "case_id": context["case_id"],
            "scope": "case",
            "status": "started",
        }
        mutation_allowed = dispatch_calls[0].pop("transition_mutation_allowed")
        assert mutation_allowed() is False
        assert dispatch_calls == [
            {
                "allow_new_attempt": True,
                "limit": 1,
                "target_case_id": context["case_id"],
                "trigger": "manual_case",
            }
        ]
    finally:
        context["profile_conn"].close()


def test_case_automation_run_materializes_a_source_only_case_in_the_worker(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes

    context = _build_context(tmp_path, materialize_profile_case=False)

    try:
        monkeypatch.setattr(
            routes,
            "dispatch_and_record_security_lifecycle_automation",
            lambda **_kwargs: {"status": "started"},
        )
        client = _client(context, monkeypatch, permissions=lambda *_args: None)

        response = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/automation/run"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "started"
        assert context["profile_conn"].execute(
            "SELECT COUNT(*) FROM security_lifecycle_cases"
        ).fetchone()[0] == 0
    finally:
        context["profile_conn"].close()


def test_global_automation_run_returns_typed_skip_on_real_flock_collision(
    tmp_path,
    monkeypatch,
):
    from src.api.routes import security_lifecycle as routes
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.security_lifecycle_automation_runtime import (
        lifecycle_automation_execution_lock,
    )

    context = _build_context(tmp_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(context["profile_path"]))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    try:
        monkeypatch.setattr(
            scheduler.threading,
            "Thread",
            lambda **_kwargs: pytest.fail("collision must not start a thread"),
        )
        client = _client(context, monkeypatch, permissions=lambda *_args: None)

        with lifecycle_automation_execution_lock():
            skipped = client.post("/security-lifecycle/automation/run")

        assert skipped.status_code == 200
        assert skipped.json() == {
            "reason": "already_running",
            "scope": "due",
            "status": "skipped",
        }
    finally:
        context["profile_conn"].close()


def test_case_automation_run_returns_409_on_real_flock_collision(
    tmp_path,
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.security_lifecycle_automation_runtime import (
        lifecycle_automation_execution_lock,
    )

    context = _build_context(tmp_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(context["profile_path"]))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    try:
        monkeypatch.setattr(
            scheduler.threading,
            "Thread",
            lambda **_kwargs: pytest.fail("collision must not start a thread"),
        )
        client = _client(context, monkeypatch, permissions=lambda *_args: None)

        with lifecycle_automation_execution_lock():
            response = client.post(
                f"/security-lifecycle/cases/{context['case_id']}/automation/run"
            )

        assert response.status_code == 409
        assert response.json()["detail"] == {
            "case_id": context["case_id"],
            "code": "automation_case_running",
        }
    finally:
        context["profile_conn"].close()


def test_case_automation_run_reconciles_a_stale_running_row_after_lock_acquisition(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_fact_kernel import SecurityLifecycleFactKernel
    from src.service import security_lifecycle_automation_scheduler as scheduler

    context = _build_context(tmp_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(context["profile_path"]))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    running = SecurityLifecycleFactKernel(context["store"]).reserve_run(
        case_id=context["case_id"],
        observation_fingerprint_sha256=context["fingerprint"],
        policy_version="trusted-lifecycle-automation-v4",
        mode="live",
        execution_revision="trusted-lifecycle-execution-r1",
        execution_owner_id="route-running-owner",
        query_context={"case_id": context["case_id"], "ticker": "EA"},
        diagnostics={},
        at=_AT,
    )

    class ImmediateThread:
        def __init__(self, *, target, kwargs, **_ignored):
            self.target = target
            self.kwargs = kwargs

        def start(self):
            self.target(**self.kwargs)

    worker_calls = []

    def run_batch(**kwargs):
        row = context["store"].get_automation_run(running.run_id)
        assert row["status"] == "failed"
        assert row["failure_code"] == "internal_error"
        worker_calls.append(kwargs)
        return {
            "result_version": 2,
            "case_outcomes": {},
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

    try:
        monkeypatch.setattr(scheduler.threading, "Thread", ImmediateThread)
        monkeypatch.setattr(scheduler, "_run_owned_automation_batch", run_batch)
        client = _client(context, monkeypatch, permissions=lambda *_args: None)

        response = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/automation/run"
        )

        assert response.status_code == 200
        payload = response.json()
        request_id = payload.pop("request_id")
        assert request_id.startswith("slao_")
        assert payload == {
            "case_id": context["case_id"],
            "scope": "case",
            "status": "started",
        }
        assert len(worker_calls) == 1
        mutation_allowed = worker_calls[0].pop("transition_mutation_allowed")
        progress_registry = worker_calls[0].pop("progress_registry")
        assert mutation_allowed() is False
        assert (
            progress_registry
            is scheduler.lifecycle_automation_progress_registry()
        )
        assert worker_calls == [
            {
                "limit": 1,
                "at": worker_calls[0]["at"],
                "execution_owner_id": worker_calls[0]["execution_owner_id"],
                "target_case_id": context["case_id"],
                "allow_new_attempt": True,
                "request_id": request_id,
                "trigger": "manual_case",
            }
        ]
        assert context["store"].get_automation_run(running.run_id)["status"] == (
            "failed"
        )
    finally:
        context["profile_conn"].close()


def test_case_detail_separates_source_evidence_assessment_acknowledgement_and_proposal(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        automation_assessment_id = _create_automation_draft(context)
        client = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
        evidence = dict(
            context["profile_conn"].execute(
                "SELECT * FROM security_lifecycle_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
        )
        context["profile_conn"].execute(
            "INSERT INTO security_lifecycle_evidence_translations "
            "(evidence_id,evidence_content_sha256,locale,translated_text,provider,"
            "model,harness,translated_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                evidence_id,
                evidence["content_sha256"],
                "zh-Hant",
                "官方發行人證據。",
                "anthropic",
                "claude-sonnet-5",
                "claude_subscription_structured_output",
                _AT,
            ),
        )
        context["profile_conn"].commit()
        assessment_id = _create_draft(client, context, evidence_id)
        assert client.post(
            f"/security-lifecycle/assessments/{assessment_id}/accept"
        ).status_code == 200
        payload = client.get(
            f"/security-lifecycle/cases/{context['case_id']}"
        ).json()
        assert payload["observation"]["source_ref"] == _SOURCE_REF
        assert payload["observation_fingerprint_sha256"] == context["fingerprint"]
        assert payload["active_sources"] == ["manual_lists"]
        assert len(payload["evidence"]) == 2
        assert {row["source_family"] for row in payload["evidence"]} == {
            "manual",
            "regulator",
        }
        translated = next(
            row for row in payload["evidence"] if row["evidence_id"] == evidence_id
        )
        assert translated["excerpt"] == "Official issuer evidence."
        assert translated["translations"] == [
            {
                "evidence_id": evidence_id,
                "evidence_content_sha256": evidence["content_sha256"],
                "locale": "zh-Hant",
                "translated_text": "官方發行人證據。",
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "harness": "claude_subscription_structured_output",
                "translated_at": _AT,
            }
        ]
        assert payload["current_assessment"]["assessment_id"] == assessment_id
        assert payload["acknowledgement_history"] == []
        assert payload["proposals"]
        assert len(payload["automation_runs"]) == 1
        assert payload["automation_runs"][0]["status"] == "succeeded"
        assert payload["automation_runs"][0]["decision_tier"] == "review_suggested"
        assert payload["automation_runs"][0]["action_readiness"] == "action_blocked"
        assert payload["automation_runs"][0]["blockers"] == []
        assert len(payload["automation_facts"]) == 1
        assert payload["automation_facts"][0]["fact_type"] == "successor_ticker"
        assert payload["automation_facts"][0]["normalized_value"] == "EA2"
        assert payload["automation_facts"][0]["source_family"] == "regulator"
        assert automation_assessment_id in {
            row["assessment_id"] for row in payload["assessment_history"]
        }
    finally:
        context["profile_conn"].close()


def test_active_case_routes_share_closed_projection_and_compact_listing_dto(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path)
    try:
        _create_automation_draft(context)
        for values in (
            {
                "evidence_id": "evidence-listing",
                "source_family": "listing_authority",
                "kind": "listing_directory_snapshot",
                "adapter": "massive_reference",
                "excerpt": '{"listing_status":"active","secret":"canonical-only"}',
                "source_url": "https://api.massive.com/v3/reference/tickers",
                "source_document_sha256": "b" * 64,
                "source_locator": _listing_locator(),
            },
            {
                "evidence_id": "evidence-ibkr",
                "source_family": "market_infrastructure",
                "kind": "market_infrastructure_snapshot",
                "adapter": "ibkr_contract",
                "excerpt": "IBKR exact contract snapshot.",
            },
            {
                "evidence_id": "evidence-publisher",
                "source_family": "publisher",
                "kind": "publisher_excerpt",
                "adapter": "internal_news",
                "excerpt": "Legacy publisher reporting.",
            },
            {
                "evidence_id": "evidence-general-web",
                "source_family": "general_web",
                "kind": "hosted_search_citation",
                "adapter": "hosted_search",
                "excerpt": "Inactive general web result.",
            },
        ):
            _insert_automation_evidence(context, **values)
        context["profile_conn"].commit()
        client = _client(context, monkeypatch)
        _add_manual(client, context["case_id"])

        detail_response = client.get(
            f"/security-lifecycle/cases/{context['case_id']}"
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert {row["source_family"] for row in detail["evidence"]} == {
            "regulator",
            "listing_authority",
            "market_infrastructure",
            "manual",
        }
        assert detail["evidence_count"] == 4
        assert set(detail["source_family_status"]) <= {
            "regulator",
            "listing_authority",
            "market_infrastructure",
            "manual",
        }
        listing = next(
            row
            for row in detail["evidence"]
            if row["source_family"] == "listing_authority"
        )
        assert listing == {
            "evidence_id": "evidence-listing",
            "source_family": "listing_authority",
            "kind": "listing_directory_snapshot",
            "source_url": "https://api.massive.com/v3/reference/tickers",
            "created_at": _AT,
            "listing": {
                "authority": "massive",
                "directory": None,
                "candidate_ticker": "B",
                "listing_status": "active",
                "market": "stocks",
                "primary_exchange": "XNAS",
                "source_as_of": "2026-08-28",
                "provider_last_updated_utc": None,
            },
        }
        assert "canonical-only" not in detail_response.text
        assert next(
            row for row in detail["evidence"] if row["source_family"] == "regulator"
        )["excerpt"] == "The tracked security may continue under ticker EA2."
        assert next(
            row for row in detail["evidence"] if row["source_family"] == "manual"
        )["excerpt"] == "Official issuer evidence."

        listed = client.get("/security-lifecycle/cases").json()["cases"][0]
        assert listed["evidence_count"] == 4
        assert set(listed["source_family_status"]) <= {
            "regulator",
            "listing_authority",
            "market_infrastructure",
            "manual",
        }
        raw_families = [
            row["source_family"]
            for row in context["store"].list_evidence(context["case_id"])
        ]
        assert raw_families.count("publisher") == 1
        assert raw_families.count("general_web") == 1
    finally:
        context["profile_conn"].close()


def test_routes_omit_one_malformed_listing_without_losing_the_case_or_other_evidence(
    tmp_path,
    monkeypatch,
):
    context = _build_context(tmp_path)
    try:
        _create_automation_draft(context)
        _insert_automation_evidence(
            context,
            evidence_id="evidence-listing",
            source_family="listing_authority",
            kind="listing_directory_snapshot",
            adapter="massive_reference",
            excerpt='{"listing_status":"active","secret":"canonical-only"}',
            source_url="https://api.massive.com/v3/reference/tickers",
            source_document_sha256="b" * 64,
            source_locator=_listing_locator(authority="arbitrary_provider"),
        )
        _insert_automation_evidence(
            context,
            evidence_id="evidence-ibkr",
            source_family="market_infrastructure",
            kind="market_infrastructure_snapshot",
            adapter="ibkr_contract",
            excerpt="IBKR exact contract snapshot.",
        )
        context["profile_conn"].commit()
        client = _client(context, monkeypatch)
        _add_manual(client, context["case_id"])

        detail_response = client.get(
            f"/security-lifecycle/cases/{context['case_id']}"
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert {row["source_family"] for row in detail["evidence"]} == {
            "regulator",
            "market_infrastructure",
            "manual",
        }
        assert detail["evidence_count"] == 3
        assert "canonical-only" not in detail_response.text
        assert client.get("/security-lifecycle/cases").json()["cases"][0][
            "evidence_count"
        ] == 3
        raw = context["service"].get_case(context["case_id"])
        assert raw["evidence_count"] == 4
        assert any(
            row["source_family"] == "listing_authority"
            and "canonical-only" in row["excerpt"]
            for row in raw["evidence"]
        )
    finally:
        context["profile_conn"].close()


def test_evidence_translation_route_caches_and_returns_typed_provenance(
    tmp_path, monkeypatch
):
    from src.api.routes import security_lifecycle as routes
    from src.security_lifecycle_translation import EvidenceTranslationResult

    context = _build_context(tmp_path)
    permission_calls: list[str] = []
    translator_calls: list[tuple[str, str]] = []

    def permission(action, _detail):
        permission_calls.append(action)

    def translator(text: str, locale: str):
        translator_calls.append((text, locale))
        return EvidenceTranslationResult(
            translated_text="官方發行人證據。",
            provider="anthropic",
            model="claude-sonnet-5",
            harness="claude_subscription_structured_output",
        )

    try:
        client = _client(context, monkeypatch, permissions=permission)
        monkeypatch.setattr(routes, "_translate_evidence_text", translator)
        evidence_id = _add_manual(client, context["case_id"])

        first = client.post(
            f"/security-lifecycle/evidence/{evidence_id}/translations",
            json={"locale": "zh-Hant"},
        )
        monkeypatch.setattr(
            routes,
            "_translate_evidence_text",
            lambda *_args: (_ for _ in ()).throw(
                AssertionError("cached translation called provider")
            ),
        )
        second = client.post(
            f"/security-lifecycle/evidence/{evidence_id}/translations",
            json={"locale": "zh-Hant"},
        )

        assert first.status_code == 200
        assert first.json() == {
            "evidence_id": evidence_id,
            "evidence_content_sha256": hashlib.sha256(
                b"Official issuer evidence."
            ).hexdigest(),
            "locale": "zh-Hant",
            "translated_text": "官方發行人證據。",
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            "harness": "claude_subscription_structured_output",
            "translated_at": _AT,
            "cached": False,
        }
        assert second.json() == {**first.json(), "cached": True}
        assert permission_calls.count("security_lifecycle_add_evidence") == 1
        assert permission_calls.count("security_lifecycle_translate_evidence") == 1
        assert translator_calls == [("Official issuer evidence.", "zh-Hant")]
    finally:
        context["profile_conn"].close()


def test_evidence_translation_route_validates_before_permission_and_masks_failures(
    tmp_path, monkeypatch
):
    from src.api.routes import security_lifecycle as routes

    context = _build_context(tmp_path)
    permission_calls: list[str] = []
    translator_calls: list[str] = []

    def permission(action, _detail):
        permission_calls.append(action)

    def failed_translator(_text: str, _locale: str):
        translator_calls.append("called")
        raise RuntimeError("credential-secret-must-not-escape")

    try:
        client = _client(context, monkeypatch, permissions=permission)
        monkeypatch.setattr(routes, "_translate_evidence_text", failed_translator)
        evidence_id = _add_manual(client, context["case_id"])
        permission_calls.clear()

        invalid_locale = client.post(
            f"/security-lifecycle/evidence/{evidence_id}/translations",
            json={"locale": "fr"},
        )
        missing = client.post(
            "/security-lifecycle/evidence/missing/translations",
            json={"locale": "zh-Hant"},
        )
        failed = client.post(
            f"/security-lifecycle/evidence/{evidence_id}/translations",
            json={"locale": "zh-Hant"},
        )

        assert invalid_locale.status_code == 422
        assert missing.status_code == 404
        assert failed.status_code == 502
        assert failed.json() == {
            "detail": {
                "code": "translation_provider_error",
                "provider": None,
                "model": None,
                "harness": None,
                "retryable": True,
            }
        }
        assert "credential-secret" not in failed.text
        assert permission_calls == ["security_lifecycle_translate_evidence"]
        assert translator_calls == ["called"]
        assert context["profile_conn"].execute(
            "SELECT COUNT(*) FROM security_lifecycle_evidence_translations"
        ).fetchone()[0] == 0
    finally:
        context["profile_conn"].close()


def test_evidence_translation_route_reports_selected_route_without_fallback(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from src import card_synthesis
    from src.api.routes import security_lifecycle as routes
    from src.auth_drivers.subscription_structured_output import (
        SubscriptionStructuredOutputError,
    )

    context = _build_context(tmp_path)
    selected = SimpleNamespace(
        provider="anthropic",
        model="claude-sonnet-5",
        effort="medium",
    )
    anthropic_calls: list[str] = []
    openai_calls: list[str] = []

    def fail_anthropic(*_args, **_kwargs):
        anthropic_calls.append("called")
        raise SubscriptionStructuredOutputError(
            "reauth_required", "secret-value"
        )

    try:
        client = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
        monkeypatch.setattr(routes, "task_route", lambda _task: selected)
        monkeypatch.setattr(card_synthesis, "task_route", lambda _task: selected)
        monkeypatch.setattr(
            routes,
            "resolve_fixed_task_runtime",
            lambda _task: SimpleNamespace(model_timeout_s=600),
        )
        monkeypatch.setattr(
            "src.auth_drivers.live_resolver.resolve_live_auth",
            lambda _provider: SimpleNamespace(source="oauth_driver_unwired"),
        )
        monkeypatch.setattr(card_synthesis, "_translate_anthropic", fail_anthropic)
        monkeypatch.setattr(
            card_synthesis,
            "_translate_openai",
            lambda *_args, **_kwargs: openai_calls.append("called"),
        )

        response = client.post(
            f"/security-lifecycle/evidence/{evidence_id}/translations",
            json={"locale": "zh-Hant"},
        )

        assert response.status_code == 502
        assert response.json() == {
            "detail": {
                "code": "translation_auth_rejected",
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "harness": "claude_subscription_structured_output",
                "retryable": False,
            }
        }
        assert "secret-value" not in response.text
        assert anthropic_calls == ["called"]
        assert openai_calls == []
    finally:
        context["profile_conn"].close()


def test_evidence_translation_route_reports_unresolvable_route_without_provider_call(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from src.api.routes import security_lifecycle as routes

    context = _build_context(tmp_path)
    provider_calls: list[str] = []

    try:
        client = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
        monkeypatch.setattr(
            routes,
            "task_route",
            lambda _task: SimpleNamespace(
                provider="unsupported-provider",
                model="secret-value",
            ),
        )
        monkeypatch.setattr(
            routes,
            "translate_text",
            lambda *_args, **_kwargs: provider_calls.append("called"),
        )

        response = client.post(
            f"/security-lifecycle/evidence/{evidence_id}/translations",
            json={"locale": "zh-Hant"},
        )

        assert response.status_code == 502
        assert response.json() == {
            "detail": {
                "code": "translation_route_unavailable",
                "provider": None,
                "model": None,
                "harness": None,
                "retryable": False,
            }
        }
        assert "secret-value" not in response.text
        assert provider_calls == []
    finally:
        context["profile_conn"].close()


def test_case_list_composes_both_stores_in_stable_order_without_read_side_writes(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client = _client(context, monkeypatch)
        before = (
            hashlib.sha256(context["market_path"].read_bytes()).hexdigest(),
            hashlib.sha256(context["profile_path"].read_bytes()).hexdigest(),
        )
        response = client.get("/security-lifecycle/cases?limit=50")
        assert response.status_code == 200
        assert [item["case_id"] for item in response.json()["cases"]] == [
            context["case_id"]
        ]
        after = (
            hashlib.sha256(context["market_path"].read_bytes()).hexdigest(),
            hashlib.sha256(context["profile_path"].read_bytes()).hexdigest(),
        )
        assert after == before

        from src.security_lifecycle import (
            LifecycleObservation,
            ObservationKind,
            SecurityLifecycleStore,
        )

        market = sqlite3.connect(context["market_path"])
        market_store = SecurityLifecycleStore(market)
        for index in range(1000):
            market_store.upsert_observation(
                LifecycleObservation(
                    ticker=f"Z{index:04d}",
                    cik=f"{index:010d}",
                    issuer_name=f"Newer issuer {index}",
                    filing_date="2026-08-05",
                    source="bulk_fixture",
                    source_ref=f"bulk-{index:04d}",
                    filing_form="8-K",
                    filing_items=("3.01",),
                    evidence_url=f"https://example.com/filing/{index}",
                    description="Newer listing observation.",
                    observed_at=_AT,
                    kinds=(ObservationKind("listing_status_review", None),),
                )
            )
        market.close()
        limited = client.get("/security-lifecycle/cases?limit=1").json()
        assert len(limited["cases"]) == 1
        assert limited["count"] == 1001
        original = context["service"].get_case(context["case_id"])
        assert original["source_presence"] == "present"
        assert original["observation"]["source_ref"] == _SOURCE_REF
    finally:
        context["profile_conn"].close()


def test_case_write_routes_call_db_write_before_persistence(tmp_path, monkeypatch):
    context = _build_context(tmp_path, materialize_profile_case=False)
    calls: list[str] = []

    def permission(action, _detail):
        calls.append(action)

    try:
        client = _client(context, monkeypatch, permissions=permission)
        assert context["profile_conn"].execute(
            "SELECT COUNT(*) FROM security_lifecycle_cases"
        ).fetchone()[0] == 0
        evidence_id = _add_manual(client, context["case_id"])
        assert context["profile_conn"].execute(
            "SELECT COUNT(*) FROM security_lifecycle_cases"
        ).fetchone()[0] == 1
        assessment_id = _create_draft(client, context, evidence_id)
        accepted = client.post(
            f"/security-lifecycle/assessments/{assessment_id}/accept"
        )
        proposal_id = accepted.json()["proposals"][0]["proposal_id"]
        acknowledged = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/acknowledgements",
            json={"reason": "evidence_insufficient", "note": None},
        )
        acknowledgement_id = acknowledged.json()["acknowledgement_id"]
        assert client.post(
            f"/security-lifecycle/acknowledgements/{acknowledgement_id}/reopen"
        ).status_code == 200
        assert client.post(
            f"/security-lifecycle/action-proposals/{proposal_id}/dismiss"
        ).status_code == 200
        assert calls.count("security_lifecycle_add_evidence") == 1
        assert calls.count("security_lifecycle_create_assessment") == 1
        assert calls.count("security_lifecycle_accept_assessment") == 1
        assert calls.count("security_lifecycle_acknowledge_case") == 1
        assert calls.count("security_lifecycle_reopen_acknowledgement") == 1
        assert calls.count("security_lifecycle_dismiss_proposal") == 1
    finally:
        context["profile_conn"].close()


def test_dismiss_proposal_route_does_not_apply_any_profile_action(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        context["profile_conn"].execute(
            "CREATE TABLE universe_sentinel (ticker TEXT PRIMARY KEY, value TEXT)"
        )
        context["profile_conn"].execute(
            "INSERT INTO universe_sentinel VALUES ('EA','unchanged')"
        )
        context["profile_conn"].commit()
        client = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
        assessment_id = _create_draft(client, context, evidence_id)
        proposal_id = client.post(
            f"/security-lifecycle/assessments/{assessment_id}/accept"
        ).json()["proposals"][0]["proposal_id"]
        response = client.post(
            f"/security-lifecycle/action-proposals/{proposal_id}/dismiss"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "dismissed"
        assert [
            tuple(row)
            for row in context["profile_conn"].execute(
                "SELECT ticker,value FROM universe_sentinel"
            ).fetchall()
        ] == [("EA", "unchanged")]
    finally:
        context["profile_conn"].close()


def test_manual_evidence_route_adds_url_or_text_without_network_access(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    socket_calls: list[object] = []
    permission_calls: list[str] = []
    monkeypatch.setattr(
        "socket.create_connection",
        lambda *args, **kwargs: socket_calls.append((args, kwargs)),
    )
    try:
        client = _client(
            context,
            monkeypatch,
            permissions=lambda action, _detail: permission_calls.append(action),
        )
        text = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/evidence",
            json={"text": "Issuer statement.", "url": None},
        )
        url = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/evidence",
            json={"text": None, "url": "https://example.com/issuer-notice"},
        )
        assert text.status_code == 200
        assert url.status_code == 200
        invalid = [
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/evidence",
                json={"text": None, "url": None},
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/evidence",
                json={"text": "text", "url": "https://example.com/issuer"},
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/evidence",
                json={"text": None, "url": "http://example.com/issuer"},
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/evidence",
                json={"text": "contains\u0000nul", "url": None},
            ),
        ]
        assert [item.status_code for item in invalid] == [422, 422, 422, 422]
        assert permission_calls == [
            "security_lifecycle_add_evidence",
            "security_lifecycle_add_evidence",
        ]
        assert socket_calls == []
    finally:
        context["profile_conn"].close()


def test_old_integer_event_and_relationship_routes_are_absent():
    from src.api.app import create_app

    paths = {route.path for route in create_app().routes}
    assert "/market-data/security-lifecycle" not in paths
    assert "/market-data/security-lifecycle/events/{event_id}" not in paths
    assert "/market-data/security-lifecycle/relationships/{relationship_id}" not in paths


def test_route_failure_is_typed_and_never_falls_back_to_one_store(tmp_path, monkeypatch):
    from src.api import dependencies
    from src.api.routes import security_lifecycle as routes
    from src.security_lifecycle_investigation import LifecycleStoreUnavailable

    class BrokenService:
        def list_cases(self, **_filters):
            raise LifecycleStoreUnavailable("profile")

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[dependencies.get_security_lifecycle_read_service] = (
        BrokenService
    )
    response = TestClient(app).get("/security-lifecycle/cases")
    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "security_lifecycle_profile_store_unavailable",
        "store": "profile",
    }

    from src.security_lifecycle_schema import create_market_schema

    market_path = tmp_path / "market.db"
    market = sqlite3.connect(market_path)
    create_market_schema(market)
    market.close()
    missing_profile = tmp_path / "missing-profile.db"
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_path))
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(missing_profile))
    real_app = FastAPI()
    real_app.include_router(routes.router)
    unavailable = TestClient(real_app).post(
        "/security-lifecycle/cases/slc_missing/assessments",
        json={
            "relevance": "direct_tracked_security",
            "confidence": "high",
            "conclusion": "Bounded conclusion.",
            "impact_summary": "Bounded impact.",
            "outcomes": ["listing_ended"],
            "citations": [
                {
                    "reference_kind": "observation",
                    "cited_content_sha256": "a" * 64,
                }
            ],
        },
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["code"] == (
        "security_lifecycle_profile_store_unavailable"
    )
    assert not missing_profile.exists()

    manual_root = tmp_path / "manual-store-outage"
    manual_root.mkdir()
    context = _build_context(manual_root)
    permission_calls = []
    try:
        context["market_path"].unlink()
        client = _client(
            context,
            monkeypatch,
            permissions=lambda action, _detail: permission_calls.append(action),
        )
        manual = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/evidence",
            json={"text": "Issuer statement.", "url": None},
        )
        assert manual.status_code == 503
        assert manual.json()["detail"] == {
            "code": "security_lifecycle_market_store_unavailable",
            "store": "market",
        }
        assert permission_calls == []
    finally:
        context["profile_conn"].close()


def test_case_list_route_admits_only_closed_queue_buckets():
    from src.api import dependencies
    from src.api.routes import security_lifecycle as routes

    calls = []

    class Service:
        def list_cases(self, **filters):
            calls.append(filters)
            return {
                "cases": [
                    {
                        "ticker": "PENDING",
                        "disposition": "not_confirmed_yet",
                        "queue_bucket": "monitoring",
                    }
                ],
                "count": 1,
                "queue_counts": {
                    "attention": 0,
                    "monitoring": 1,
                    "history": 0,
                },
                "data_integrity": {"source_missing_count": 0},
            }

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[dependencies.get_security_lifecycle_read_service] = (
        Service
    )
    client = TestClient(app)

    response = client.get("/security-lifecycle/cases?queue_bucket=monitoring")
    assert response.status_code == 200
    assert response.json()["cases"][0]["disposition"] == "not_confirmed_yet"
    assert calls[0]["queue_bucket"] == "monitoring"

    invalid = client.get("/security-lifecycle/cases?queue_bucket=unknown")
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": {"code": "queue_bucket"}}
    assert len(calls) == 1


def test_route_writes_do_not_mutate_universe_portfolio_sa_or_market_history(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        context["profile_conn"].executescript(
            "CREATE TABLE universe_rows (value TEXT);"
            "CREATE TABLE portfolio_rows (value TEXT);"
            "CREATE TABLE sa_rows (value TEXT);"
            "INSERT INTO universe_rows VALUES ('u');"
            "INSERT INTO portfolio_rows VALUES ('p');"
            "INSERT INTO sa_rows VALUES ('s');"
        )
        context["profile_conn"].commit()
        market_before = hashlib.sha256(context["market_path"].read_bytes()).hexdigest()
        client = _client(context, monkeypatch)
        _add_manual(client, context["case_id"])
        assert [
            tuple(row)
            for row in context["profile_conn"].execute(
                "SELECT value FROM universe_rows"
            ).fetchall()
        ] == [("u",)]
        assert [
            tuple(row)
            for row in context["profile_conn"].execute(
                "SELECT value FROM portfolio_rows"
            ).fetchall()
        ] == [("p",)]
        assert [
            tuple(row)
            for row in context["profile_conn"].execute(
                "SELECT value FROM sa_rows"
            ).fetchall()
        ] == [("s",)]
        assert hashlib.sha256(context["market_path"].read_bytes()).hexdigest() == market_before
    finally:
        context["profile_conn"].close()


def test_source_missing_case_detail_remains_queryable(tmp_path, monkeypatch):
    context = _build_context(tmp_path, with_observation=False)
    permission_calls: list[str] = []
    try:
        client = _client(
            context,
            monkeypatch,
            permissions=lambda action, _detail: permission_calls.append(action),
        )
        response = client.get(
            f"/security-lifecycle/cases/{context['case_id']}"
        )
        assert response.status_code == 200
        assert response.json()["source_presence"] == "source_missing"
        assert response.json()["observation"] is None
        ordinary = client.get("/security-lifecycle/cases")
        assert ordinary.status_code == 200
        assert ordinary.json()["cases"] == []
        assert ordinary.json()["data_integrity"] == {"source_missing_count": 1}
        integrity = client.get(
            "/security-lifecycle/cases?source_presence=source_missing"
        )
        assert [item["case_id"] for item in integrity.json()["cases"]] == [
            context["case_id"]
        ]
        manual = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/evidence",
            json={"text": "Manual data-integrity note.", "url": None},
        )
        assert manual.status_code == 200
        assert permission_calls == ["security_lifecycle_add_evidence"]

        attempts = [
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    "relevance": "direct_tracked_security",
                    "confidence": "high",
                    "conclusion": "Bounded conclusion.",
                    "impact_summary": "Bounded impact.",
                    "outcomes": ["listing_ended"],
                    "citations": [
                        {
                            "reference_kind": "observation",
                            "cited_content_sha256": "a" * 64,
                        }
                    ],
                },
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/acknowledgements",
                json={"reason": "evidence_insufficient", "note": None},
            ),
        ]
        assert [item.status_code for item in attempts] == [422, 422]
        assert {
            item.json()["detail"]["code"] for item in attempts
        } == {"source_observation_missing"}
        assert permission_calls == ["security_lifecycle_add_evidence"]
    finally:
        context["profile_conn"].close()


def test_unknown_or_conflicting_assessment_payload_is_rejected_before_write(tmp_path, monkeypatch):
    context = _build_context(tmp_path, materialize_profile_case=False)
    permission_calls: list[str] = []
    try:
        client = _client(
            context,
            monkeypatch,
            permissions=lambda action, _detail: permission_calls.append(action),
        )
        base = {
            "relevance": "direct_tracked_security",
            "confidence": "high",
            "conclusion": "Bounded conclusion.",
            "impact_summary": "Bounded impact.",
            "citations": [
                {
                    "reference_kind": "observation",
                    "cited_content_sha256": context["fingerprint"],
                }
            ],
        }
        unknown = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/assessments",
            json={**base, "outcomes": ["made_up_outcome"]},
        )
        conflicting = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/assessments",
            json={**base, "outcomes": ["undetermined", "listing_ended"]},
        )
        legacy = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/assessments",
            json={**base, "outcomes": ["symbol_or_venue_changed"]},
        )
        malformed = [
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    **base,
                    "outcomes": ["listing_ended"],
                    "counterparty_cik": "12AB",
                },
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    **base,
                    "outcomes": ["listing_ended"],
                    "effective_date": "2026-02-30",
                },
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    **base,
                    "outcomes": ["acquisition_cash"],
                    "consideration_currency": "usd",
                    "cash_per_security_decimal": "9" * 5000,
                },
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    **base,
                    "outcomes": ["acquisition_cash"],
                    "cash_per_security_decimal": "1e10000",
                },
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    **base,
                    "outcomes": ["listing_ended"],
                    "citations": [
                        {
                            "reference_kind": "observation",
                            "evidence_id": "sle_wrong_shape",
                            "cited_content_sha256": context["fingerprint"],
                        }
                    ],
                },
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    **base,
                    "outcomes": ["listing_ended"],
                    "conclusion": "   ",
                },
            ),
            client.post(
                f"/security-lifecycle/cases/{context['case_id']}/assessments",
                json={
                    **base,
                    "outcomes": ["listing_ended"],
                    "impact_summary": "contains\u0000nul",
                },
            ),
        ]
        assert {
            unknown.status_code,
            conflicting.status_code,
            legacy.status_code,
            *(item.status_code for item in malformed),
        } == {422}
        assert context["store"].list_assessments(context["case_id"]) == []
        assert permission_calls == []

        missing_evidence = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/assessments",
            json={
                **base,
                "outcomes": ["listing_ended"],
                "citations": [
                    *base["citations"],
                    {
                        "reference_kind": "evidence",
                        "evidence_id": "sle_missing",
                    },
                ],
            },
        )
        assert missing_evidence.status_code == 422
        assert context["profile_conn"].execute(
            "SELECT COUNT(*) FROM security_lifecycle_cases"
        ).fetchone()[0] == 0

        valid = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/assessments",
            json={**base, "outcomes": ["listing_ended"]},
        )
        assert valid.status_code == 200
        assert context["profile_conn"].execute(
            "SELECT COUNT(*) FROM security_lifecycle_cases"
        ).fetchone()[0] == 1
        assert permission_calls == [
            "security_lifecycle_create_assessment",
            "security_lifecycle_create_assessment",
        ]
        source = inspect.getsource(
            __import__(
                "src.api.routes.security_lifecycle",
                fromlist=["AssessmentRequest"],
            ).AssessmentRequest
        )
        assert "extra=\"forbid\"" in source
    finally:
        context["profile_conn"].close()
