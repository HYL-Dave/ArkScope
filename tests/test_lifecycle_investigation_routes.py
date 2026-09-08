import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from tests.test_lifecycle_investigation_review import context


@pytest.fixture
def client(tmp_path, monkeypatch):
    from src.api.routes import lifecycle_investigation as api, ticker_identity as transitions
    from src.lifecycle_investigation.controller import InvestigationController
    c = context(tmp_path)
    calls = []
    controller = InvestigationController(c["investigation"], credential_loader=lambda selected: calls.append(selected), news_factory=lambda: None)
    app = FastAPI()
    app.include_router(api.router)
    app.include_router(transitions.router)
    app.dependency_overrides[api.get_ticker_identity_service] = lambda: c["service"]
    app.dependency_overrides[api.get_controller] = lambda: controller
    monkeypatch.setattr(api, "require_db_write", lambda *a: None)
    monkeypatch.setattr(api, "require_profile_state_write", lambda *a: None)
    monkeypatch.setattr(transitions, "require_profile_state_write", lambda *a: None)
    with TestClient(app) as connection:
        yield {**c, "client": connection, "calls": calls}
    controller.close()


def test_target_routes_read_and_adopt_without_dispatch_or_legacy_queue(client):
    c = client
    base = "/security-lifecycle/investigations"
    targets = c["client"].get(base + "/targets").json()
    assert "OLD" in [row["ticker"] for row in targets["targets"]]
    result = c["client"].get(base + "/runs/" + c["run_id"])
    assert result.status_code == 200 and result.json()["status"] == "succeeded"
    assert result.json()["action"] == "terminal_delisting"
    assert "local:" not in result.text and "header_json" not in result.text
    assert c["client"].get(base + "/targets/OLD/latest").json()["run_id"] == c["run_id"]
    packet = c["client"].get(base + "/runs/" + c["run_id"] + "/review").json()
    assert packet["ready"], packet
    response = c["client"].post(base + "/runs/" + c["run_id"] + "/confirm", json={
        "packet_sha256": packet["packet_sha256"], "action": packet["action"], **packet["options"]})
    assert response.status_code == 200 and response.json()["status"] == "applied", response.text
    reloaded = c["client"].get(base + "/runs/" + c["run_id"]).json()
    assert reloaded["action"] is None and reloaded["finding"] == result.json()["finding"]
    assert c["client"].get(base + "/targets/OLD/latest").json()["action"] is None
    assert c["calls"] == []


@pytest.mark.parametrize("later_change", ("none", "unrelated", "affected"))
def test_investigation_activity_reports_current_reverse_readiness_without_legacy_cases(client, later_change):
    from src.profile_state import ProfileStateStore
    c = client
    base = "/security-lifecycle/investigations/runs/" + c["run_id"]
    packet = c["client"].get(base + "/review").json()
    applied = c["client"].post(base + "/confirm", json={
        "packet_sha256": packet["packet_sha256"], "action": packet["action"], **packet["options"]})
    assert applied.status_code == 200 and applied.json()["status"] == "applied"
    if later_change != "none":
        ProfileStateStore(c["profile"]).set_priority("OLD" if later_change == "affected" else "LIVE", "high")
    response = c["client"].get("/security-lifecycle/transition-activity")
    assert response.status_code == 200
    item, = response.json()["items"]
    assert item["reverse_readiness"] == {
        "reversible": later_change != "affected",
        "block_reasons": ["reverse_state_changed"] if later_change == "affected" else [],
    }
    reversed_response = c["client"].post("/security-lifecycle/transitions/" + item["transition_id"] + "/reverse")
    assert reversed_response.status_code == 200
    assert reversed_response.json()["status"] == ("blocked" if later_change == "affected" else "reversed")
    assert ("OLD" in c["sources"]()) is (later_change != "affected")
    assert "LIVE" in c["sources"]() and c["calls"] == []
    if later_change != "affected":
        history = c["client"].get("/security-lifecycle/transition-activity").json()["items"]
        assert {row["activity_type"] for row in history} == {"applied", "reversed"}
        assert all(row["reverse_readiness"] == {"reversible": False, "block_reasons": []} for row in history)
        assert c["client"].get(base).json()["action"] is None


def test_runtime_routes_roundtrip_unknown_fields_reject_and_reset(client):
    c = client
    url = "/security-lifecycle/investigations/runtime"
    initial = c["client"].get(url).json()
    assert initial["model_submissions"] == 24
    invalid = c["client"].put(url, json={**initial, "fallback": True})
    assert invalid.status_code == 422
    assert c["client"].put(url, json={**initial, "model_submissions": 48}).json()["model_submissions"] == 48
    assert c["client"].get(url).json()["model_submissions"] == 48
    assert c["client"].post(url + "/reset").json() == initial
    assert c["calls"] == []


def test_unknown_failures_are_closed_and_contain_no_private_data(client, monkeypatch):
    from src.api.routes import lifecycle_investigation as api
    monkeypatch.setattr(api, "prepare", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("private-token")))
    response = client["client"].get("/security-lifecycle/investigations/runs/" + client["run_id"] + "/review")
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "investigation_unavailable"}}


def test_saved_provider_observations_are_dated_readonly_and_refresh_is_target_scoped(client, monkeypatch):
    from src.api.routes import lifecycle_investigation as api
    c = client
    reads = []
    monkeypatch.setattr(api, "run_provider_scan", lambda **kw: reads.append(kw))
    url = "/security-lifecycle/investigations/targets/OLD/providers"
    response = c["client"].get(url)
    assert response.status_code == 200
    assert response.json()["observations"]["observed_at"] == c["now"][0]
    assert reads == [] and c["calls"] == []
    assert c["client"].post(url + "/check").status_code == 200
    assert len(reads) == 1 and reads[0]["tickers"] == ("OLD",) and reads[0]["target_ticker"] == "OLD"
    assert c["client"].post(url.replace("OLD", "UNKNOWN") + "/check").status_code == 409
    assert len(reads) == 1


def test_pending_confirmed_actions_remain_visible_without_the_legacy_queue(client):
    from src.lifecycle_web_review import prepare, confirm
    from src.ticker_identity_transition import TransitionOptions
    c = client
    options = TransitionOptions(execute_on="2026-09-10")
    packet = prepare(c["service"], c["run_id"], options=options)
    receipt = confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
        options=options, before_write=lambda: None)
    response = c["client"].get("/security-lifecycle/investigations/actions")
    assert response.status_code == 200
    action, = response.json()["actions"]
    assert action["transition_id"] == receipt["transition_id"]
    assert action["state"] == "scheduled" and action["execute_on"] == "2026-09-10"
    assert "approved_preview" not in action
    c["service"].cancel_transition(receipt["transition_id"], before_write=lambda: None)
    assert c["client"].get("/security-lifecycle/investigations/actions").json()["actions"] == []


def test_provider_preparation_api_is_bound_to_the_selected_snapshot_without_dispatch(client, monkeypatch):
    from dataclasses import replace
    import sqlite3
    from src.api.routes import lifecycle_investigation as api
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import terminal_records
    c = client
    c["now"][0] = "2026-09-08T01:00:01Z"
    material = tuple(_evidence(replace(row, retrieved_at=c["now"][0])) for row in terminal_records())
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=material, diagnostics={})
    monkeypatch.setattr(api, "run_provider_scan", lambda **kwargs: pytest.fail("preparation must use only saved observations"))
    url = "/security-lifecycle/investigations/targets/OLD/providers"
    decision = c["client"].get(url).json()["decision"]
    assert decision["action"] == "terminal_delisting"
    response = c["client"].post(url + "/prepare", json={"check_sha256": decision["check_sha256"]})
    assert response.status_code == 200 and response.json()["ready"], response.text
    assert response.json()["source_ticker"] == "OLD"
    assert c["calls"] == [] and "OLD" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transitions").fetchone()[0] == 0
    changed = c["client"].post(url + "/prepare", json={"check_sha256": "0" * 64})
    assert changed.status_code == 409 and changed.json()["detail"]["code"] == "provider_snapshot_changed"
    invalid = c["client"].post(url + "/prepare", json={"check_sha256": decision["check_sha256"], "execute_on": "September 8"})
    assert invalid.status_code == 422
