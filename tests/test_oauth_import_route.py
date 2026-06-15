"""S4-prep Step 1: OAuth credential import route (handler-direct, no TestClient).

POST /config/credentials/oauth/import — v1 supports ONLY anthropic +
claude_code_oauth (Claude setup-token). It creates a metadata row (secret NULL)
then saves the token to the token-store; if the token-store write fails it rolls
the metadata row back (no half-built credential). The response returns masked
metadata ONLY — never the token. Uses a FAKE token (no live call).
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from src.api.routes import config_routes as cr
from src.auth_drivers import PlaintextTokenStore
from src.model_credentials import CredentialStore

_TOKEN = "claude-setup-tok-AbCdEf0123456789ZyXwVu"


@pytest.fixture()
def stores(tmp_path):
    cred = CredentialStore(tmp_path / "profile_state.db")
    tok = PlaintextTokenStore(tmp_path / "auth_tokens.json")
    return cred, tok


@pytest.fixture(autouse=True)
def _gate(monkeypatch):
    calls = []
    monkeypatch.setattr(cr, "require_profile_state_write", lambda *a, **k: calls.append((a, k)))
    return calls


def _body(**kw):
    base = dict(provider="anthropic", auth_mode="claude_code_oauth", alias="my claude",
                token=_TOKEN, account_label="Pro plan", expires_at="2027-06-16T00:00:00+00:00", make_active=True)
    base.update(kw)
    return cr.OAuthImport(**base)


def test_import_success_row_has_null_secret(stores):
    cred, tok = stores
    res = cr.import_oauth_credential(_body(), store=cred, token_store=tok)
    cid = res["credential"]["id"]
    row = cred.get(cid)
    assert row.secret is None  # token NOT in the credential DB
    assert row.auth_type == "claude_code_oauth" and row.account_label == "Pro plan" and row.active is True


def test_import_token_lands_in_token_store(stores):
    cred, tok = stores
    res = cr.import_oauth_credential(_body(), store=cred, token_store=tok)
    cid = res["credential"]["id"]
    rec = tok.load(provider="anthropic", auth_mode="claude_code_oauth", credential_id=cid)
    assert rec is not None and rec.access_token == _TOKEN  # the token went to the token-store


def test_import_response_never_echoes_token(stores):
    cred, tok = stores
    res = cr.import_oauth_credential(_body(), store=cred, token_store=tok)
    blob = json.dumps(res) + repr(res)
    assert _TOKEN not in blob
    # no 6+ char fragment of the token leaks either
    frag = _TOKEN[10:20]
    assert frag not in blob
    assert "secret" not in res["credential"] or res["credential"].get("secret") is None


def test_import_rolls_back_credential_row_when_token_store_fails(stores):
    cred, _ = stores

    class BrokenTokenStore:
        def save(self, **k):
            raise RuntimeError("keyring unavailable")

        def load(self, **k):
            return None

    with pytest.raises(HTTPException) as ei:
        cr.import_oauth_credential(_body(), store=cred, token_store=BrokenTokenStore())
    assert ei.value.status_code >= 500 or ei.value.status_code == 502
    assert _TOKEN not in str(ei.value.detail)  # no token in the error
    assert cred.list() == []  # the metadata row was rolled back — no half-built credential


def test_import_write_gate_is_invoked(stores, _gate):
    cred, tok = stores
    cr.import_oauth_credential(_body(), store=cred, token_store=tok)
    assert len(_gate) == 1  # require_profile_state_write called once
    # and the gate detail does NOT carry the token
    assert _TOKEN not in json.dumps(_gate[0], default=str)


def test_import_rejects_cross_provider_and_non_v1_modes(stores):
    cred, tok = stores
    # anthropic + chatgpt_oauth (wrong mode for provider) → rejected
    with pytest.raises(HTTPException) as e1:
        cr.import_oauth_credential(_body(auth_mode="chatgpt_oauth"), store=cred, token_store=tok)
    assert e1.value.status_code == 400
    # openai (not in v1 scope) → rejected
    with pytest.raises(HTTPException) as e2:
        cr.import_oauth_credential(_body(provider="openai", auth_mode="chatgpt_oauth"), store=cred, token_store=tok)
    assert e2.value.status_code == 400
    assert cred.list() == []  # nothing persisted on rejection


def test_import_rejects_blank_token(stores):
    cred, tok = stores
    with pytest.raises(HTTPException) as ei:
        cr.import_oauth_credential(_body(token="   "), store=cred, token_store=tok)
    assert ei.value.status_code == 400
    assert cred.list() == []


def test_probe_route_runs_p3_and_never_echoes_token(stores, monkeypatch):
    # Import a fake token, then probe it. The probe is monkeypatched (no real
    # claude -p / network); the response carries redacted ProbeResults only.
    cred, tok = stores
    res = cr.import_oauth_credential(_body(), store=cred, token_store=tok)
    cid = res["credential"]["id"]

    import src.auth_drivers.claude_oauth_probe as probe_mod
    captured = {}

    def fake_probe(token, **kw):
        captured["token"] = token  # the route must pass the stored token
        return {"passed": True, "probes": [{"name": "P3a", "passed": True, "expected": "x", "observed": "ok", "error": None}]}

    monkeypatch.setattr(probe_mod, "run_claude_code_oauth_probe", fake_probe)
    out = cr.probe_oauth_credential(cid, store=cred, token_store=tok)
    assert out["passed"] is True and out["probes"][0]["name"] == "P3a"
    assert captured["token"] == _TOKEN  # the real stored token reached the probe
    assert _TOKEN not in json.dumps(out)  # but never came back in the response


def test_probe_route_404_when_no_token(stores):
    cred, tok = stores
    # a credential row with no token in the store → 404
    c = cred.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="orphan")
    with pytest.raises(HTTPException) as ei:
        cr.probe_oauth_credential(f"local:{c.id}", store=cred, token_store=tok)
    assert ei.value.status_code == 404


def test_probe_route_422_for_blank_id(stores):
    cred, tok = stores
    with pytest.raises(HTTPException) as ei:
        cr.probe_oauth_credential("   ", store=cred, token_store=tok)
    assert ei.value.status_code == 422


def test_generic_credentials_route_still_rejects_oauth(stores):
    # regression: the API-key endpoint must STILL refuse OAuth modes (no second
    # door into llm_credentials.secret).
    cred, _ = stores
    body = cr.CredentialCreate(provider="anthropic", auth_type="claude_code_oauth", alias="x", secret=_TOKEN, make_active=True)
    with pytest.raises(HTTPException) as ei:
        cr.add_credential(body, store=cred)
    assert ei.value.status_code == 400
    assert cred.list() == []
