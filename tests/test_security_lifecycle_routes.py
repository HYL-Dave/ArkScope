from __future__ import annotations

import hashlib
import inspect
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient


_AT = "2026-08-20T00:00:00Z"
_SOURCE_REF = "0000712515-26-000042"


class _SearchAdapter:
    identity = "tavily"

    def __init__(self):
        self.search_calls: list[tuple[str, int]] = []
        self.fetch_calls: list[str] = []

    def search(self, *, query, max_results):
        self.search_calls.append((query, max_results))
        return {"results": [], "usage": {"search_requests": 1}}

    def fetch(self, *, url, max_bytes, redirect_guard):
        self.fetch_calls.append(url)
        return None


def _build_context(tmp_path, *, with_observation=True):
    from src.security_lifecycle import (
        LifecycleObservation,
        ObservationKind,
        SecurityLifecycleStore,
    )
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
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
    case_id = profile_store.ensure_case(
        source="sec_edgar",
        source_ref=_SOURCE_REF,
        ticker="EA",
        at=_AT,
    )
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


def _client(context, monkeypatch, *, adapter=None, permissions=None):
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
    search_adapter = adapter or _SearchAdapter()
    app.dependency_overrides[dependencies.get_security_lifecycle_search_adapter] = (
        lambda: search_adapter
    )
    app.dependency_overrides[dependencies.get_security_lifecycle_resolver] = (
        lambda: (lambda _host: ("93.184.216.34",))
    )
    monkeypatch.setattr(routes, "_utc_now", lambda: _AT)
    if permissions is not None:
        monkeypatch.setattr(routes, "require_db_write", permissions)
        monkeypatch.setattr(
            routes,
            "require_permission",
            lambda permission, action, detail: permissions(action, detail),
        )
    return TestClient(app), search_adapter


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
                {"reference_kind": "evidence", "evidence_id": evidence_id}
            ],
            "successor_ticker": "EA2",
        },
    )
    assert response.status_code == 200
    return response.json()["assessment_id"]


def test_accept_assessment_route_keeps_action_execution_out_of_scope(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client, _ = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
        assessment_id = _create_draft(client, context, evidence_id)
        response = client.post(
            f"/security-lifecycle/assessments/{assessment_id}/accept"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assessment"]["status"] == "accepted"
        assert {item["action_type"] for item in payload["proposals"]} == {
            "archive_manual_memberships",
            "notify",
            "remap_symbol",
        }
        assert all(item["status"] == "proposed" for item in payload["proposals"])
        assert not hasattr(context["store"], "apply_action_proposal")
    finally:
        context["profile_conn"].close()


def test_acknowledge_and_reopen_routes_preserve_distinct_workflow_commands(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client, _ = _client(context, monkeypatch)
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
        ("POST", "/security-lifecycle/cases/{case_id}/investigations"),
    }
    assert expected <= rows
    assert len(rows) == 180
    assert {
        ("GET", "/market-data/security-lifecycle"),
        ("PUT", "/market-data/security-lifecycle/events/{event_id}"),
        ("PUT", "/market-data/security-lifecycle/relationships/{relationship_id}"),
    }.isdisjoint(rows)


def test_case_detail_separates_source_evidence_assessment_acknowledgement_and_proposal(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client, _ = _client(context, monkeypatch)
        evidence_id = _add_manual(client, context["case_id"])
        assessment_id = _create_draft(client, context, evidence_id)
        assert client.post(
            f"/security-lifecycle/assessments/{assessment_id}/accept"
        ).status_code == 200
        payload = client.get(
            f"/security-lifecycle/cases/{context['case_id']}"
        ).json()
        assert payload["observation"]["source_ref"] == _SOURCE_REF
        assert payload["active_sources"] == ["manual_lists"]
        assert len(payload["evidence"]) == 1
        assert payload["current_assessment"]["assessment_id"] == assessment_id
        assert payload["acknowledgement_history"] == []
        assert payload["proposals"]
    finally:
        context["profile_conn"].close()


def test_case_list_composes_both_stores_in_stable_order_without_read_side_writes(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client, _ = _client(context, monkeypatch)
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
    finally:
        context["profile_conn"].close()


def test_case_write_routes_call_db_write_before_persistence(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    calls: list[str] = []

    def permission(action, _detail):
        calls.append(action)

    try:
        client, _ = _client(context, monkeypatch, permissions=permission)
        evidence_id = _add_manual(client, context["case_id"])
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
        assert client.post(
            f"/security-lifecycle/cases/{context['case_id']}/investigations",
            json={"adapter": "tavily"},
        ).status_code == 200
        assert calls.count("security_lifecycle_add_evidence") == 1
        assert calls.count("security_lifecycle_create_assessment") == 1
        assert calls.count("security_lifecycle_accept_assessment") == 1
        assert calls.count("security_lifecycle_acknowledge_case") == 1
        assert calls.count("security_lifecycle_reopen_acknowledgement") == 1
        assert calls.count("security_lifecycle_dismiss_proposal") == 1
        assert calls.count("security_lifecycle_investigation") == 3
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
        client, _ = _client(context, monkeypatch)
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


def test_investigation_route_requires_one_explicit_attended_command(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        adapter = _SearchAdapter()
        client, _ = _client(context, monkeypatch, adapter=adapter)
        assert context["store"].list_investigation_runs(context["case_id"]) == []
        response = client.post(
            f"/security-lifecycle/cases/{context['case_id']}/investigations",
            json={"adapter": "tavily"},
        )
        assert response.status_code == 200
        assert response.json()["trigger"] == "attended_user"
        assert len(context["store"].list_investigation_runs(context["case_id"])) == 1
        assert len(adapter.search_calls) in {2, 3}
    finally:
        context["profile_conn"].close()


def test_manual_evidence_route_adds_url_or_text_without_network_access(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    socket_calls: list[object] = []
    monkeypatch.setattr(
        "socket.create_connection",
        lambda *args, **kwargs: socket_calls.append((args, kwargs)),
    )
    try:
        client, _ = _client(context, monkeypatch)
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
        assert socket_calls == []
    finally:
        context["profile_conn"].close()


def test_old_integer_event_and_relationship_routes_are_absent():
    from src.api.app import create_app

    paths = {route.path for route in create_app().routes}
    assert "/market-data/security-lifecycle" not in paths
    assert "/market-data/security-lifecycle/events/{event_id}" not in paths
    assert "/market-data/security-lifecycle/relationships/{relationship_id}" not in paths


def test_route_failure_is_typed_and_never_falls_back_to_one_store(monkeypatch):
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
        client, _ = _client(context, monkeypatch)
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
    try:
        client, _ = _client(context, monkeypatch)
        response = client.get(
            f"/security-lifecycle/cases/{context['case_id']}"
        )
        assert response.status_code == 200
        assert response.json()["source_presence"] == "source_missing"
        assert response.json()["observation"] is None
    finally:
        context["profile_conn"].close()


def test_unknown_or_conflicting_assessment_payload_is_rejected_before_write(tmp_path, monkeypatch):
    context = _build_context(tmp_path)
    try:
        client, _ = _client(context, monkeypatch)
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
        assert {unknown.status_code, conflicting.status_code, legacy.status_code} == {422}
        assert context["store"].list_assessments(context["case_id"]) == []
        source = inspect.getsource(
            __import__(
                "src.api.routes.security_lifecycle",
                fromlist=["AssessmentRequest"],
            ).AssessmentRequest
        )
        assert "extra=\"forbid\"" in source
    finally:
        context["profile_conn"].close()
