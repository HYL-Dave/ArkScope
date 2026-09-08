import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential, credential_generation
from src.lifecycle_web_controller import LifecycleWebController
from src.lifecycle_web_preflight import LifecycleWebPreflight
from src.lifecycle_web_store import LifecycleWebStore
from src.security_lifecycle_web_contract import validate_selection
from tests.test_lifecycle_web_controller import completed_runner, wait_done
from tests.test_lifecycle_web_review import context
from tests.test_security_lifecycle_web_finding import public_input


@pytest.fixture
def web_route(tmp_path, monkeypatch):
    from src.api.routes import lifecycle_web as api

    c = context(tmp_path)
    row = SimpleNamespace(id=7, provider="openai", auth_type="api_key", active=True, alias="Chosen account",
                          secret="private-key-do-not-export", updated_at="2026-09-06T01:00:00Z")
    route = SimpleNamespace(provider="openai", model="gpt-5.6-luna", effort="high")
    credentials = SimpleNamespace(list=lambda provider: [row] if row.provider == provider else [])
    preflight = LifecycleWebPreflight(c["service"], credential_store=credentials, route_loader=lambda: route,
                                     sa_db_path=c["sa"], output_limit_loader=lambda: 16384)
    monkeypatch.setattr(preflight, "_public_input", lambda *args, **kwargs: public_input().model_copy(update={"composite_figi": None}))
    calls = []
    def load(selected):
        calls.append(selected)
        return WebCredential(selected, api_key="private-key-do-not-export", generation=credential_generation(row))
    controller = LifecycleWebController(LifecycleWebStore(c["profile"], clock=lambda: c["now"][0]),
                                        credential_loader=load, runner=completed_runner)
    permissions = []
    monkeypatch.setattr(api, "require_db_write", lambda action, detail: permissions.append(("db", action)))
    monkeypatch.setattr(api, "require_profile_state_write", lambda action, detail: permissions.append(("profile", action)))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_web_preflight] = lambda: preflight
    app.dependency_overrides[api.get_web_controller] = lambda: controller
    app.dependency_overrides[api.get_ticker_identity_service] = lambda: c["service"]
    with TestClient(app) as client:
        yield {**c, "client": client, "controller": controller, "preflight": preflight,
               "credential": row, "route": route, "calls": calls, "permissions": permissions}
    controller.close()


def path(c):
    return f"/security-lifecycle/cases/{c['case_id']}"


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
def test_web_routes_prepare_start_read_and_confirm_all_four_channels(web_route, provider, auth):
    c = web_route
    c["credential"].provider, c["credential"].auth_type = provider, auth
    c["route"].provider = provider
    c["route"].model = "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5"
    preview = c["client"].get(path(c) + "/web-preflight?question=listing_status")
    assert preview.status_code == 200 and preview.json()["available"]
    assert c["calls"] == [] and c["permissions"] == []
    body = {"question": "listing_status", "preflight_sha256": preview.json()["preflight_sha256"], "request_key": "route-click"}
    started = c["client"].post(path(c) + "/web-runs", json=body)
    assert started.status_code == 202, started.text
    identity = started.json()["run_id"]
    wait_done(c["controller"], identity)
    result = c["client"].get(f"/security-lifecycle/web-runs/{identity}").json()
    assert result["execution"]["auth_mode"] == auth and result["status"] == "succeeded"
    assert result["finding"]["citations"] and result["model_submissions"] == 2
    assert "private-key" not in json.dumps(result) and "local:7" not in json.dumps(result)
    assert c["client"].get(path(c) + "/web-runs/latest").json()["run_id"] == identity
    # Reopening, cancellation after completion and repeated request IDs cost no work.
    assert c["client"].post(path(c) + "/web-runs", json=body).json() == {"run_id": identity, "created": False}
    assert c["client"].post(f"/security-lifecycle/web-runs/{identity}/cancel").json()["status"] == "succeeded"
    assert len(c["calls"]) == 1
    packet = c["client"].get(f"/security-lifecycle/web-runs/{identity}/review").json()
    assert packet["ready"], packet
    confirmed = c["client"].post(f"/security-lifecycle/web-runs/{identity}/confirm", json={
        "packet_sha256": packet["packet_sha256"], "action": packet["action"], **packet["options"]})
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "applied", confirmed.text
    assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    assert any(scope == "profile" for scope, _ in c["permissions"])


def test_web_preflight_is_not_a_dispatch_and_rejects_changed_selected_credential(web_route):
    c = web_route
    preview = c["client"].get(path(c) + "/web-preflight?question=listing_status").json()
    c["credential"].secret = "changed-key"
    result = c["client"].post(path(c) + "/web-runs", json={"question": "listing_status", "request_key": "click-changed",
        "preflight_sha256": preview["preflight_sha256"]})
    assert result.status_code == 409 and result.json()["detail"]["code"] == "web_preflight_changed"
    assert c["calls"] == []


@pytest.mark.parametrize("extra", [{"api_key": "do-not-accept"}, {"model": "other-model"}, {"url": "https://private.example"}])
def test_web_start_has_no_credential_model_or_arbitrary_source_override(web_route, extra):
    c = web_route
    result = c["client"].post(path(c) + "/web-runs", json={"question": "listing_status", "request_key": "x",
        "preflight_sha256": "a" * 64, **extra})
    assert result.status_code == 422 and c["calls"] == []


def test_web_request_failure_never_exports_raw_exception_or_starts_a_provider(web_route, monkeypatch):
    c = web_route
    def unavailable(*args, **kwargs):
        raise RuntimeError("token=must-remain-private")
    monkeypatch.setattr(c["controller"], "latest", unavailable)
    response = c["client"].get(path(c) + "/web-runs/latest")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "web_operation_unavailable"
    assert "must-remain-private" not in response.text and c["calls"] == []


def test_web_journal_is_never_auto_installed_by_opening_the_page(web_route, monkeypatch):
    from src.lifecycle_web_schema import WebJournalError
    c = web_route
    def absent(*args, **kwargs):
        raise WebJournalError("web_schema_absent")
    monkeypatch.setattr(c["preflight"], "_material", absent)
    result = c["client"].get(path(c) + "/web-preflight?question=listing_status")
    assert result.status_code == 200 and result.json()["available"] is False
    assert result.json()["reason"] == "web_schema_absent" and c["calls"] == []


def test_production_web_worker_wires_scoped_refresh_only_when_an_expired_token_is_loaded(tmp_path, monkeypatch):
    from src.api import dependencies
    from src.api.routes import lifecycle_web as api
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
    api.get_web_controller.cache_clear()
    try:
        service = api.get_web_controller()
        assert calls == [] and tokens.calls == [] and not (tmp_path / "not-installed.db").exists()
        result = service.credential_loader(_selection("openai", "chatgpt_oauth"))
        assert result.token_record is fresh and result.api_key is None
        assert calls == [{"credential_id": "local:7", "token_store": tokens, "observation_store": observation}]
    finally:
        api.shutdown_web_controller()
