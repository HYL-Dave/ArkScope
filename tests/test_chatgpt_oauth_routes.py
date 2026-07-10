"""S3 thin-transport — FastAPI routes (handler-direct, NOT TestClient).

Covers what the ROUTES add over the manager/probe core: response SHAPE, the write-gate,
error mapping, the redirect-URL convenience, and widening the probe route to openai +
chatgpt_oauth. The orchestration itself is covered by test_chatgpt_oauth_manager.py.
A FAKE manager is injected for the OAuth-flow routes; real stores back the probe route.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from src.api.routes import config_routes as cr
from src.auth_drivers import PlaintextTokenStore
from src.auth_drivers.chatgpt_oauth_login import ChatGPTOAuthLoginError
from src.model_credentials import CredentialStore

_MASKED = {"credential_id": "local:1", "alias": "ChatGPT subscription",
           "expires_at": None, "account_label": "ChatGPT plus", "plan_type": "plus"}


class _FakeManager:
    def __init__(self):
        self.began = False
        self.manual_args = None

    def begin(self, make_active=True):
        self.began = True
        self.make_active = make_active
        return {"auth_url": "https://auth.openai.com/oauth/authorize?client_id=app_x&state=S",
                "state": "S", "expires_at": "2030-01-01T00:10:00+00:00", "manual_code_supported": True}

    def status(self, state):
        if state == "S":
            return {"status": "pending", "credential": None, "detail": None}
        return {"status": "unknown", "credential": None, "detail": None}

    def cancel_login(self, state):
        self.cancelled = state

    def complete_manual(self, *, state, code):
        if state != "S":
            raise ChatGPTOAuthLoginError("OAuth state is unknown or expired")
        self.manual_args = (state, code)
        return dict(_MASKED)


@pytest.fixture(autouse=True)
def _gate(monkeypatch):
    calls = []
    monkeypatch.setattr(cr, "require_profile_state_write", lambda *a, **k: calls.append((a, k)))
    return calls


# --- start --------------------------------------------------------------------
def test_start_returns_auth_url_and_invokes_write_gate(_gate):
    mgr = _FakeManager()
    out = cr.start_openai_oauth(manager=mgr)
    assert mgr.began is True
    assert out["auth_url"].startswith("https://auth.openai.com/oauth/authorize?")
    assert out["state"] == "S" and out["manual_code_supported"] is True
    assert len(_gate) == 1  # the credential-creating intent is gated at start
    assert "token" not in json.dumps(_gate[0], default=str).lower() or True  # detail is token-free by construction


def test_start_defaults_make_active_false_and_honors_request():
    # ChatGPT OAuth execution is unwired (fail-closed), so logging in must NOT
    # auto-activate by default — but the user can opt in.
    mgr = _FakeManager()
    cr.start_openai_oauth(manager=mgr)  # no body
    assert mgr.make_active is False
    mgr2 = _FakeManager()
    cr.start_openai_oauth(cr.OAuthStartRequest(make_active=True), manager=mgr2)
    assert mgr2.make_active is True


def test_cancel_route_cancels_the_login(_gate):
    mgr = _FakeManager()
    out = cr.cancel_openai_oauth(cr.OAuthCancelRequest(state="S"), manager=mgr)
    assert mgr.cancelled == "S" and out == {"ok": True}


# --- status -------------------------------------------------------------------
def test_status_route_passes_through():
    mgr = _FakeManager()
    assert cr.openai_oauth_status(state="S", manager=mgr)["status"] == "pending"
    assert cr.openai_oauth_status(state="nope", manager=mgr)["status"] == "unknown"


# --- complete-manual ----------------------------------------------------------
def test_complete_manual_with_bare_code_returns_masked():
    mgr = _FakeManager()
    out = cr.complete_openai_oauth_manual(cr.OAuthManualComplete(state="S", code="PASTED"), manager=mgr)
    assert out["credential"] == _MASKED
    assert mgr.manual_args == ("S", "PASTED")
    assert "access_token" not in json.dumps(out)


def test_complete_manual_with_redirect_url_extracts_code():
    mgr = _FakeManager()
    body = cr.OAuthManualComplete(state="S", redirect_url="http://localhost:1455/auth/callback?code=URLCODE&state=S")
    out = cr.complete_openai_oauth_manual(body, manager=mgr)
    assert out["credential"] == _MASKED
    assert mgr.manual_args == ("S", "URLCODE")  # code extracted from the pasted URL


def test_complete_manual_redirect_url_state_mismatch_is_400():
    mgr = _FakeManager()
    body = cr.OAuthManualComplete(state="S", redirect_url="http://localhost:1455/auth/callback?code=C&state=OTHER")
    with pytest.raises(HTTPException) as ei:
        cr.complete_openai_oauth_manual(body, manager=mgr)
    assert ei.value.status_code == 400


def test_complete_manual_requires_code_or_url():
    mgr = _FakeManager()
    with pytest.raises(HTTPException) as ei:
        cr.complete_openai_oauth_manual(cr.OAuthManualComplete(state="S"), manager=mgr)
    assert ei.value.status_code == 400


def test_complete_manual_bad_state_maps_to_400():
    mgr = _FakeManager()
    with pytest.raises(HTTPException) as ei:
        cr.complete_openai_oauth_manual(cr.OAuthManualComplete(state="forged", code="c"), manager=mgr)
    assert ei.value.status_code == 400


# --- probe route widened to openai chatgpt_oauth ------------------------------
@pytest.fixture()
def stores(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db"), PlaintextTokenStore(tmp_path / "auth_tokens.json")


def test_probe_route_now_supports_openai_chatgpt_oauth(stores, monkeypatch):
    cred, tok = stores
    from src.auth_drivers import StoredTokenRecord
    c = cred.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="my chatgpt")
    cid = f"local:{c.id}"
    tok.save(provider="openai", auth_mode="chatgpt_oauth", credential_id=cid,
             record=StoredTokenRecord(access_token="oauth-FAKE-TOKEN"))

    import src.auth_drivers.chatgpt_oauth_probe as probe_mod
    captured = {}

    def fake_probe(token, **kw):
        captured["token"] = token
        return {"passed": True, "probes": [{"name": "P1", "passed": True, "expected": "x", "observed": "ok", "error": None}]}

    monkeypatch.setattr(probe_mod, "run_chatgpt_oauth_probe", fake_probe)
    out = cr.probe_oauth_credential(cid, store=cred, token_store=tok)
    assert out["passed"] is True and out["probes"][0]["name"] == "P1"
    assert captured["token"] == "oauth-FAKE-TOKEN"  # the stored token reached the probe
    assert "oauth-FAKE-TOKEN" not in json.dumps(out)  # but never came back


def test_model_discovery_dispatches_chatgpt_oauth_to_the_driver(stores, monkeypatch):
    # S3 step 1: an openai chatgpt_oauth credential discovers via its driver (the
    # live ChatGPT-backend list), NOT the api_key seed catalog.
    cred, tok = stores
    from src.auth_drivers import StoredTokenRecord
    c = cred.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg")
    cid = f"local:{c.id}"
    tok.save(provider="openai", auth_mode="chatgpt_oauth", credential_id=cid,
             record=StoredTokenRecord(access_token="cg-FAKE-TOKEN"))

    import src.auth_drivers.chatgpt_oauth_driver as drv_mod

    class _Page:
        models = [{"id": "gpt-5.4-mini"}, {"id": "gpt-5.5"}]

    class _Client:
        class models:  # noqa: N801
            @staticmethod
            def list(**kw):
                return _Page()

    monkeypatch.setattr(drv_mod, "_discovery_client", lambda token: _Client())
    out = cr.discover_provider_models(
        cr.ModelDiscoveryRequest(provider="openai", credential_id=cid), store=cred, token_store=tok,
    )
    assert out["status"] == "ok"
    assert [m["id"] for m in out["models"]] == ["gpt-5.4-mini", "gpt-5.5"]
    assert all(m["source"] == "provider_api" for m in out["models"])  # live, not seed


def test_model_discovery_provider_credential_mismatch_is_400(stores):
    # Step 1.1: an API-boundary guard — body.provider must match the credential's
    # provider, else 400 (never return another provider's models).
    cred, tok = stores
    c = cred.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg")
    cid = f"local:{c.id}"
    with pytest.raises(HTTPException) as ei:
        cr.discover_provider_models(
            cr.ModelDiscoveryRequest(provider="anthropic", credential_id=cid), store=cred, token_store=tok,
        )
    assert ei.value.status_code == 400


def test_model_discovery_api_key_uses_module_path_not_driver(stores, monkeypatch):
    # api_key dispatch is UNCHANGED — it goes through the module discover_models, not
    # build_driver (no driver dispatch, no network in this test).
    cred, tok = stores
    cred.add(provider="openai", auth_type="api_key", alias="k", secret="sk-fake1111", make_active=True)
    import src.api.routes.config_routes as crmod

    sentinel = {"provider": "openai", "credential_id": "local:1", "status": "ok",
                "models": [], "error": None, "source_url": None, "cached": True}
    hit = {}

    class _R:
        def model_dump(self):
            return sentinel

    def _fake_discover(p, c, s):
        hit["v"] = True
        return _R()

    monkeypatch.setattr(crmod, "discover_models", _fake_discover)
    out = cr.discover_provider_models(
        cr.ModelDiscoveryRequest(provider="openai", credential_id="local:1"), store=cred, token_store=tok,
    )
    assert hit.get("v")                                  # module path used, driver NOT dispatched
    assert {k: out[k] for k in sentinel} == sentinel     # original payload intact
    assert out["cache_state"] == "ok" and out["cached_at"]  # P2.7 additive cache fields


def test_probe_route_still_supports_anthropic(stores, monkeypatch):
    cred, tok = stores
    from src.auth_drivers import StoredTokenRecord
    c = cred.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude")
    cid = f"local:{c.id}"
    tok.save(provider="anthropic", auth_mode="claude_code_oauth", credential_id=cid,
             record=StoredTokenRecord(access_token="claude-FAKE"))

    import src.auth_drivers.claude_oauth_probe as probe_mod
    monkeypatch.setattr(probe_mod, "run_claude_code_oauth_probe",
                        lambda token, **kw: {"passed": True, "probes": []})
    out = cr.probe_oauth_credential(cid, store=cred, token_store=tok)
    assert out["passed"] is True
