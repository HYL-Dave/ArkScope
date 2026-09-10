"""Closed one-command API; real profile fixtures and no provider execution."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.security_lifecycle_review import _result
from tests.test_security_lifecycle_review import context, deny_network, rows


def client(c, monkeypatch, calls):
    from src.api.dependencies import get_ticker_identity_service
    from src.api.routes import ticker_identity as routes

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_ticker_identity_service] = lambda: c["service"]
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail: calls.append("profile"))
    monkeypatch.setattr(routes, "require_db_write", lambda action, detail: calls.append("database"), raising=False)
    return TestClient(app)


def get_packet(browser, c):
    response = browser.get(f"/security-lifecycle/cases/{c['case_id']}/review", params={"assessment_id": c["assessment_id"], "execute_on": c["ended"]})
    assert response.status_code == 200, response.text
    return response.json()


def body(packet):
    return {"assessment_id": packet["assessment_id"], "packet_sha256": packet["packet_sha256"], "action": packet["action"], **packet["options"]}


def test_review_api_prepares_without_writes_and_confirms_with_one_post(tmp_path, monkeypatch):
    c = context(tmp_path)
    calls = []
    browser = client(c, monkeypatch, calls)
    before = rows(c)
    packet = get_packet(browser, c)
    assert packet["ready"] and calls == [] and rows(c) == before
    assert not {"provenance", "profile_state_sha256", "provider_check_sha256", "evidence_set_sha256", "observation_fingerprint_sha256"} & packet.keys()
    result = browser.post(f"/security-lifecycle/cases/{c['case_id']}/confirm-review", json=body(packet))
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "applied"
    assert "database" in calls and "profile" in calls
    after = rows(c)
    readback = _result(c["service"], result.json()["transition_id"])
    assert readback["status"] == "applied"
    assert rows(c) == after


@pytest.mark.parametrize("extra", ({"accepted": True}, {"effects": {}}, {"actor": "automation_policy"}, {"facts": {}}, {"execute_on": "tomorrow"}, {"unhide_successor": "false"}))
def test_confirmation_request_refuses_client_authority_and_malformed_options(tmp_path, monkeypatch, extra):
    c = context(tmp_path)
    calls = []
    browser = client(c, monkeypatch, calls)
    packet = get_packet(browser, c)
    before = rows(c)
    result = browser.post(f"/security-lifecycle/cases/{c['case_id']}/confirm-review", json={**body(packet), **extra})
    assert result.status_code == 422
    assert rows(c) == before and calls == []


def test_review_api_reports_changed_packet_without_writes(tmp_path, monkeypatch):
    from src.profile_state import ProfileStateStore

    c = context(tmp_path)
    browser = client(c, monkeypatch, [])
    packet = get_packet(browser, c)
    ProfileStateStore(c["profile"]).set_universe_hidden("OLD", True)
    before = rows(c)
    result = browser.post(f"/security-lifecycle/cases/{c['case_id']}/confirm-review", json=body(packet))
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "review_changed"
    assert rows(c) == before


@pytest.mark.parametrize("permission", ("require_db_write", "require_profile_state_write"))
def test_review_api_denial_is_not_partial_acceptance(tmp_path, monkeypatch, permission):
    from src.api.routes import ticker_identity as routes

    c = context(tmp_path)
    browser = client(c, monkeypatch, [])
    packet = get_packet(browser, c)
    def denied(*args, **kwargs):
        raise HTTPException(status_code=403, detail={"code": "denied"})
    monkeypatch.setattr(routes, permission, denied)
    before = rows(c)
    result = browser.post(f"/security-lifecycle/cases/{c['case_id']}/confirm-review", json=body(packet))
    assert result.status_code == 403 and rows(c) == before


def test_review_projection_has_no_raw_membership_or_future_columns(tmp_path):
    from copy import deepcopy
    from src.security_lifecycle_review import project_packet
    from tests.test_security_lifecycle_review import prepare

    packet = deepcopy(prepare(context(tmp_path)))
    packet["future_private_column"] = "not-public"
    packet["finding"]["future_private_column"] = "not-public"
    packet["options"]["future_private_column"] = "not-public"
    effects = packet["effects"]
    effects["future_private_column"] = "not-public"
    effects["sa_tracking_memberships"][0]["future_private_column"] = "not-public"
    effects["watchlists"]["archive"][0]["future_private_column"] = "not-public"
    public = project_packet(packet)
    encoded = str(public)
    assert "future_private_column" not in encoded
    assert not {"membership_id", "accepted_at", "updated_at", "observation_sha256", "removed_at", "current_suppressed_at"} & public["effects"]["sa_tracking_memberships"][0].keys()
    assert public["effects"]["watchlists"]["archive"] == [{"list_name": "Manual", "ticker": "OLD"}]
    assert public["packet_sha256"] == packet["packet_sha256"]


@pytest.mark.parametrize("channel", ("case_api", "audit_local", "research"))
def test_existing_case_readers_do_not_export_private_confirmation(tmp_path, monkeypatch, channel):
    from src.api.dependencies import get_security_lifecycle_read_service
    from src.api.routes import security_lifecycle as routes
    from src.tools import security_lifecycle_tools as tools
    from tests.test_security_lifecycle_review import stage_approval

    c = context(tmp_path)
    packet, transition_id = stage_approval(c, monkeypatch)
    before = rows(c)
    if channel == "research":
        monkeypatch.setattr(tools, "SecurityLifecycleReadService", lambda **kwargs: c["service"]._read_service)
        result = tools.get_security_lifecycle_case(c["case_id"])
        assert result["status"] == "ok"
        payload = result["case"]
    elif channel == "audit_local":
        payload = c["service"]._read_service.get_case_audit(c["case_id"])
    else:
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[get_security_lifecycle_read_service] = lambda: c["service"]._read_service
        response = TestClient(app).get(f"/security-lifecycle/cases/{c['case_id']}")
        assert response.status_code == 200, response.text
        payload = response.json()
    assert payload["case_id"] == c["case_id"]
    assert "review_confirmation" not in str(payload)
    assert packet["packet_sha256"] not in str(payload)
    if channel != "audit_local":
        transition = payload["ticker_transition"]
        assert transition["transition_id"] == transition_id
        assert transition["status"] == "approved"
        assert transition["approved_preview"]["effects"]["suppression"]["hide_source"] is True
    assert rows(c) == before
    with c["service"]._profile_connection(write=False) as conn:
        stored = c["service"]._store(conn).get(transition_id)
        assert stored["approved_preview"]["review_confirmation"]["packet"] == packet


@pytest.mark.parametrize("command", ("cancel", "retry", "reverse"))
def test_legacy_transition_commands_close_their_response(tmp_path, monkeypatch, command):
    from tests.test_security_lifecycle_review import stage_approval

    c = context(tmp_path)
    _, transition_id = stage_approval(c, monkeypatch)
    with c["service"]._profile_connection(write=False) as conn:
        digest = c["service"]._store(conn).get(transition_id)["approved_preview_sha256"]
    if command == "reverse":
        applied = c["service"].execute_transition(transition_id, preview_sha256=digest, before_write=lambda: None)
        assert applied["status"] == "applied"
        assert "review_confirmation" in applied["transition"]["approved_preview"]
    browser = client(c, monkeypatch, [])
    response = browser.post(f"/security-lifecycle/transitions/{transition_id}/{command}",
                            json={"preview_sha256": digest} if command == "retry" else None)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == {"cancel": "cancelled", "retry": "applied", "reverse": "reversed"}[command]
    if command != "cancel":
        assert set(payload) == {"status", "block_reasons", "transition"}
    transition = payload if command == "cancel" else payload["transition"]
    assert set(transition) == {"transition_id", "kind", "status", "source_ticker", "successor_ticker",
                               "execute_on", "approved_preview_sha256", "updated_at"}
    assert transition["transition_id"] == transition_id and transition["approved_preview_sha256"] == digest
    assert "review_confirmation" not in response.text and "snapshot_json" not in response.text


def test_case_transition_preview_is_recursively_closed_without_changing_receipt(tmp_path, monkeypatch):
    from copy import deepcopy
    from src.tools.security_lifecycle_tools import _project_transition
    from tests.test_security_lifecycle_review import stage_approval

    c = context(tmp_path)
    _, transition_id = stage_approval(c, monkeypatch)
    with c["service"]._profile_connection(write=False) as conn:
        stored = c["service"]._store(conn).get(transition_id)
    value = deepcopy(stored)
    preview = value["approved_preview"]
    preview["future_private_column"] = "private"
    preview["effects"]["future_private_column"] = "private"
    preview["effects"]["sa_tracking_memberships"][0]["future_private_column"] = "private"
    preview["effects"]["watchlists"]["archive"][0]["future_private_column"] = "private"
    projected = _project_transition(value)
    assert "future_private_column" not in str(projected)
    assert "review_confirmation" not in str(projected)
    member = projected["approved_preview"]["effects"]["sa_tracking_memberships"][0]
    assert set(member) == {"membership_id", "ticker", "picked_date", "portfolio_status"}
    assert projected["approved_preview_sha256"] == stored["approved_preview_sha256"]
    assert projected["approved_preview"]["preview_sha256"] == stored["approved_preview_sha256"]
    assert projected["approved_preview"]["effects"]["watchlists"]["archive"][0]["list_name"] == "Manual"
    assert "review_confirmation" in stored["approved_preview"]


@pytest.mark.parametrize("state", ("scheduled", "cancelled", "reversed", "applied_state_changed"))
def test_legacy_retry_does_not_claim_an_incomplete_review_action_completed(tmp_path, monkeypatch, state):
    from src.profile_state import ProfileStateStore
    from src.ticker_identity_transition import TransitionOptions
    from tests.test_security_lifecycle_review import stage_approval

    c = context(tmp_path)
    if state == "scheduled":
        c["options"] = TransitionOptions(execute_on="2026-09-06")
    _, transition_id = stage_approval(c, monkeypatch)
    with c["service"]._profile_connection(write=False) as conn:
        digest = c["service"]._store(conn).get(transition_id)["approved_preview_sha256"]
    if state == "cancelled":
        c["service"].cancel_transition(transition_id, before_write=lambda: None)
    elif state in {"reversed", "applied_state_changed"}:
        c["service"].execute_transition(transition_id, preview_sha256=digest, before_write=lambda: None)
        if state == "reversed":
            c["service"].reverse_transition(transition_id, before_write=lambda: None)
        else:
            ProfileStateStore(c["profile"]).set_universe_hidden("OLD", False)
    before = rows(c)
    browser = client(c, monkeypatch, [])
    response = browser.post(f"/security-lifecycle/transitions/{transition_id}/retry", json={"preview_sha256": digest})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "transition_preview_changed"
    readback = _result(c["service"], transition_id)
    assert readback["status"] == state
    assert rows(c) == before
