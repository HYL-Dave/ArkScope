import json

from fastapi.testclient import TestClient
import pytest

from tests.test_lifecycle_investigation_review import context


def test_current_confirmation_dto_is_owned_by_the_current_route():
    import ast
    import inspect
    from src.api.routes import lifecycle_investigation as api

    assert inspect.signature(api.adopt).parameters["body"].annotation.__module__ == api.__name__
    imports = [node.module for node in ast.walk(ast.parse(inspect.getsource(api)))
               if isinstance(node, ast.ImportFrom)]
    assert "src.api.routes.lifecycle_web" not in imports


def test_real_app_mounts_current_target_routes_without_starting_its_lifespan():
    from src.api.app import create_app

    routes = {(method, route.path) for route in create_app().routes for method in route.methods}
    base = "/security-lifecycle/investigations"
    assert {("GET", base + "/targets"), ("GET", base + "/targets/{ticker}/preflight"),
            ("POST", base + "/targets/{ticker}/runs"), ("GET", base + "/targets/{ticker}/latest"),
            ("GET", base + "/runs/{run_id}"), ("POST", base + "/runs/{run_id}/cancel"),
            ("GET", base + "/runs/{run_id}/review"), ("POST", base + "/runs/{run_id}/confirm")} <= routes


def test_real_app_has_no_case_web_or_web_run_routes():
    from src.api.app import create_app

    paths = {route.path for route in create_app().routes}
    assert not {path for path in paths if "/cases/{case_id}/web-" in path or "/web-runs/" in path}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from src.api.app import create_app
    from src.api.routes import lifecycle_investigation as api, ticker_identity as transitions
    from src.lifecycle_investigation.controller import InvestigationController
    c = context(tmp_path)
    calls = []
    controller = InvestigationController(c["investigation"], credential_loader=lambda selected: calls.append(selected), news_factory=lambda: None)
    app = create_app()
    app.dependency_overrides[api.get_ticker_identity_service] = lambda: c["service"]
    app.dependency_overrides[api.get_controller] = lambda: controller
    monkeypatch.setattr(api, "require_db_write", lambda *a: None)
    monkeypatch.setattr(api, "require_profile_state_write", lambda *a: None)
    monkeypatch.setattr(transitions, "require_profile_state_write", lambda *a: None)
    connection = TestClient(app)
    try:
        yield {**c, "client": connection, "calls": calls}
    finally:
        connection.close()
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
    from src.lifecycle_investigation.review import prepare, confirm
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


@pytest.mark.parametrize("invalid", [
    {"api_key": "synthetic"}, {"packet_sha256": "invalid"}, {"action": "other"},
    {"execute_on": "2026-02-30"}, {"execute_on": "20260908"}, {"priority_resolution": "other"},
    {"unhide_successor": 1}, {"unhide_successor": "true"}, {"acknowledge_source_gaps": None},
    {"acknowledge_source_gaps": 1}, {"acknowledge_source_gaps": "true"},
])
def test_current_confirmation_rejects_unknown_fields_dates_and_coerced_acknowledgements(client, invalid):
    c = client
    base = "/security-lifecycle/investigations/runs/" + c["run_id"]
    packet = c["client"].get(base + "/review").json()
    response = c["client"].post(base + "/confirm", json={"packet_sha256": packet["packet_sha256"],
        "action": packet["action"], **packet["options"], **invalid})
    assert response.status_code == 422
    assert "OLD" in c["sources"]() and c["calls"] == []


@pytest.mark.parametrize("extra", [{"api_key": "synthetic"}, {"model": "other-model"}, {"url": "https://private.example"}])
def test_current_start_rejects_credential_model_and_source_overrides(client, extra):
    from src.api.routes import lifecycle_investigation as api
    client["client"].app.dependency_overrides[api.get_preflight] = lambda: client["preflight"]
    response = client["client"].post("/security-lifecycle/investigations/targets/OLD/runs", json={
        "request_key": "invalid-click", "preflight_sha256": "a" * 64, **extra})
    assert response.status_code == 422 and client["calls"] == []


def test_current_worker_factory_refreshes_only_the_selected_expired_synthetic_credential(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from src.api import dependencies
    from src.api.routes import lifecycle_investigation as api
    from src.auth_drivers import chatgpt_oauth_login
    from src.auth_drivers.token_store import StoredTokenRecord
    from tests.test_lifecycle_web_models import RecordStore, TokenStore, _selection
    row = SimpleNamespace(id=7, provider="openai", auth_type="chatgpt_oauth", secret=None)
    tokens = TokenStore(StoredTokenRecord(access_token="old", expires_at="2000-01-01T00:00:00Z"))
    observation = object()
    monkeypatch.setattr(dependencies, "_local_state_db_path", lambda: tmp_path / "not-installed.db")
    monkeypatch.setattr(dependencies, "get_credential_store", lambda: RecordStore(row))
    monkeypatch.setattr(dependencies, "get_oauth_token_store", lambda: tokens)
    monkeypatch.setattr(dependencies, "get_oauth_observation_store", lambda: observation)
    calls = []
    fresh = StoredTokenRecord(access_token="fresh", expires_at="2099-01-01T00:00:00Z")
    def refresh(**kwargs):
        calls.append(kwargs)
        return fresh
    monkeypatch.setattr(chatgpt_oauth_login, "refresh_if_needed", refresh)
    api.get_controller.cache_clear()
    try:
        service = api.get_controller()
        assert calls == [] and tokens.calls == [] and not (tmp_path / "not-installed.db").exists()
        result = service.credential_loader(_selection("openai", "chatgpt_oauth"))
        assert result.token_record is fresh and result.api_key is None
        assert calls == [{"credential_id": "local:7", "token_store": tokens, "observation_store": observation}]
    finally:
        api.shutdown_controller()
    assert api.get_controller.cache_info().currsize == 0


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
def test_real_app_current_preflight_start_read_replay_and_adoption(client, tmp_path, provider, auth):
    from src.api.routes import lifecycle_investigation as api
    from src.auth_drivers.lifecycle_web_models import WebCredential, credential_generation
    from src.lifecycle_investigation.controller import InvestigationController
    from src.lifecycle_investigation.news import LocalNews
    from src.lifecycle_investigation.target import TargetPreflight
    from tests.lifecycle_investigation_fixtures import completed_runner, synthetic_credentials, wait_done

    c = client
    credentials, rows, route = synthetic_credentials(provider=provider, auth=auth)
    preflight = TargetPreflight(c["service"], credential_store=credentials, route_loader=lambda: route,
        market_path=c["market"], sa_path=c["sa"])
    loads = []

    def load(selected):
        loads.append(selected)
        return WebCredential(selected, api_key="synthetic-secret", generation=credential_generation(rows[0]))

    controller = InvestigationController(c["investigation"], credential_loader=load, runner=completed_runner,
        before_dispatch=api.dispatch_permission, news_factory=lambda: LocalNews(tmp_path / "news.db", None, clock=lambda: c["now"][0]))
    c["client"].app.dependency_overrides[api.get_preflight] = lambda: preflight
    c["client"].app.dependency_overrides[api.get_controller] = lambda: controller
    base = "/security-lifecycle/investigations"
    try:
        preview = c["client"].get(base + "/targets/OLD/preflight?language=en").json()
        assert preview["available"] and preview["limits"]["model_submissions"] == 24
        assert loads == []
        body = {"request_key": "real-app-click", "preflight_sha256": preview["preflight_sha256"], "language": "en"}
        started = c["client"].post(base + "/targets/OLD/runs", json=body)
        assert started.status_code == 202, started.text
        identity = started.json()["run_id"]
        assert wait_done(controller, identity)["status"] == "succeeded"
        run_url = base + "/runs/" + identity
        result = c["client"].get(run_url).json()
        assert result["execution"] == {"provider": provider, "auth_mode": auth, "model": route.model, "effort": "high"}
        assert result["action"] == "terminal_delisting" and result["stats"]["model_submissions"] == 1
        assert "synthetic-secret" not in json.dumps(result) and "local:7" not in json.dumps(result)
        assert c["client"].get(base + "/targets/OLD/latest").json() == result
        assert c["client"].post(base + "/targets/OLD/runs", json=body).json() == {"run_id": identity, "created": False}
        assert c["client"].post(run_url + "/cancel").json()["status"] == "succeeded"
        packet = c["client"].get(run_url + "/review").json()
        assert packet["ready"], packet
        adopted = c["client"].post(run_url + "/confirm", json={"packet_sha256": packet["packet_sha256"],
            "action": packet["action"], **packet["options"]})
        assert adopted.status_code == 200 and adopted.json()["status"] == "applied", adopted.text
        assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
        assert len(loads) == 1 and c["calls"] == []
    finally:
        controller.close()
