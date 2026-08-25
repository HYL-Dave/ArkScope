from __future__ import annotations

import hashlib
import inspect
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient


_AT = "2026-08-20T00:00:00Z"
_SOURCE_REF = "0000712515-26-000042"


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
    return {
        "market_path": market_path,
        "profile_path": profile_path,
        "profile_conn": profile_conn,
        "store": profile_store,
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
    monkeypatch.setattr(routes, "_utc_now", lambda: _AT)
    if permissions is not None:
        monkeypatch.setattr(routes, "require_db_write", permissions)
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
        ("GET", "/security-lifecycle/cases"),
        ("GET", "/security-lifecycle/cases/{case_id}"),
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
    }
    assert expected <= rows
    assert len(rows) == 186
    assert (
        "POST",
        "/security-lifecycle/cases/{case_id}/investigations",
    ) not in rows
    assert {
        ("GET", "/market-data/security-lifecycle"),
        ("PUT", "/market-data/security-lifecycle/events/{event_id}"),
        ("PUT", "/market-data/security-lifecycle/relationships/{relationship_id}"),
    }.isdisjoint(rows)


def test_case_detail_separates_source_evidence_assessment_acknowledgement_and_proposal(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        automation_assessment_id = _create_automation_draft(context)
        client = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
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
