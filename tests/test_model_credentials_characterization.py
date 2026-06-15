"""S1 characterization tests — PIN the CURRENT LLM CredentialStore + config-route
behavior BEFORE the auth_type schema delta, so the regression gate ("old api_key
behavior unchanged") becomes provable. These must be GREEN on today's code = the
baseline.

A few assertions intentionally document behavior S1 WILL change (the legacy
`oauth`/`setup_token` auth_type values; the route allow-set that currently rejects
the explicit modes). Those are marked CURRENT-BASELINE and get updated in the
schema-delta step; the api_key CRUD / discovery / _resolve ones must STAY green.
"""

from __future__ import annotations

import pytest

from src.model_credentials import (
    CredentialStore,
    _resolve_api_credential,
    discover_models,
    provider_credentials,
)
# aliased: the function is literally named test_model → pytest would mis-collect it
from src.model_credentials import test_model as run_model_test

_ENV_KEYS = (
    "OPENAI_API_KEY", "OPENAI_API_KEYS", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS",
    "OPENAI_OAUTH_TOKEN", "ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_SETUP_TOKEN",
)


@pytest.fixture()
def store(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db")


@pytest.fixture()
def clean_env(monkeypatch):
    """Hermetic: don't load config/.env, and clear provider env keys so discovery
    has no ambient credential (→ no network)."""
    monkeypatch.setattr("src.model_credentials.ensure_env_loaded", lambda: None)
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


# --- CredentialStore CRUD (api_key; pure SQLite, the load-bearing path) ------
def test_add_api_key_returns_stored_credential(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k1", secret="sk-AAAA1111BBBB")
    assert c.provider == "openai" and c.auth_type == "api_key" and c.alias == "k1"
    assert c.secret == "sk-AAAA1111BBBB" and c.active is True
    assert isinstance(c.id, int)
    assert isinstance(c.created_at, str) and c.created_at == c.updated_at


def test_list_and_get(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k1", secret="sk-xxxxxxxxxxxx")
    assert [x.id for x in store.list()] == [c.id]
    assert store.list(provider="anthropic") == []
    assert store.get(f"local:{c.id}").alias == "k1"
    assert store.get("local:9999") is None
    assert store.get("not-a-local-id") is None  # non-local id → None


def test_single_active_per_provider(store):
    a = store.add(provider="openai", auth_type="api_key", alias="a", secret="sk-aaaaaaaaaa11")
    b = store.add(provider="openai", auth_type="api_key", alias="b", secret="sk-bbbbbbbbbb22")
    active = {x.alias: x.active for x in store.list(provider="openai")}
    assert active == {"a": False, "b": True}  # newest make_active wins; single active
    an = store.add(provider="anthropic", auth_type="api_key", alias="an", secret="sk-ant-cccccccc")
    assert an.active is True
    assert store.get(f"local:{b.id}").active is True  # anthropic active independent of openai


def test_update_alias_secret_active_reactivates(store):
    a = store.add(provider="openai", auth_type="api_key", alias="a", secret="sk-aaaaaaaaaa11", make_active=False)
    b = store.add(provider="openai", auth_type="api_key", alias="b", secret="sk-bbbbbbbbbb22", make_active=True)
    upd = store.update(f"local:{a.id}", alias="a2", active=True)
    assert upd.alias == "a2" and upd.active is True
    assert store.get(f"local:{b.id}").active is False  # activating a deactivates b
    assert store.update("local:9999", alias="x") is None  # missing → None


def test_delete(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-xxxxxxxxxxxx")
    assert store.delete(f"local:{c.id}") is True
    assert store.delete(f"local:{c.id}") is False
    assert store.delete("bad") is False


def test_row_dto_observable_fields(store):
    c = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-xxxxxxxxxxxx")
    got = store.get(f"local:{c.id}")
    # pin the observable api_key fields (subset → survives additive S1 columns)
    assert (got.id, got.provider, got.auth_type, got.alias, got.secret, got.active) == (
        c.id, "openai", "api_key", "k", "sk-xxxxxxxxxxxx", True,
    )


# --- provider_credentials() masked inventory --------------------------------
def test_provider_credentials_local_api_key_row(store, clean_env):
    store.add(provider="openai", auth_type="api_key", alias="local-oa", secret="sk-realkeyvalue9")
    oa = provider_credentials(store)["openai"]
    local = next(c for c in oa if c.id.startswith("local:"))
    assert local.auth_type == "api_key" and local.editable is True
    assert local.can_discover_models is True and local.can_test_models is True
    assert local.masked and "sk-realkeyvalue9" not in (local.masked or "")  # secret never leaked


def test_provider_credentials_legacy_oauth_setup_token_placeholders(store, clean_env):
    # CURRENT-BASELINE: the env placeholder rows carry the legacy auth_type values.
    # S1 normalizes these to chatgpt_oauth / claude_code_oauth — this test updates then.
    inv = provider_credentials(store)
    oa = {c.id: c for c in inv["openai"]}
    an = {c.id: c for c in inv["anthropic"]}
    assert oa["openai:OPENAI_OAUTH_TOKEN"].auth_type == "oauth"
    assert an["anthropic:ANTHROPIC_OAUTH_TOKEN"].auth_type == "oauth"
    assert an["anthropic:ANTHROPIC_SETUP_TOKEN"].auth_type == "setup_token"
    # placeholders are not directly usable
    assert oa["openai:OPENAI_OAUTH_TOKEN"].can_discover_models is False


# --- discovery / test on the api_key path (no-network paths) -----------------
def test_discover_models_missing_credential_falls_back_to_seed(store, clean_env):
    res = discover_models("openai", credential_id=None, store=store)
    assert res.status == "missing_credential"
    assert len(res.models) > 0 and all(m.source == "seed" for m in res.models)  # no network


def test_run_model_test_missing_credential(store, clean_env):
    res = run_model_test("openai", "gpt-5.4", credential_id=None, store=store)
    assert res.status == "missing_credential" and res.model == "gpt-5.4"


def test_resolve_api_credential_picks_api_key(store, clean_env):
    api = store.add(provider="openai", auth_type="api_key", alias="k", secret="sk-realkeyvalue9", make_active=True)
    r = _resolve_api_credential("openai", f"local:{api.id}", store)
    assert r is not None and r.secret == "sk-realkeyvalue9" and r.auth_type == "api_key"


def test_resolve_api_credential_ignores_non_apikey_rows(store, clean_env):
    # CURRENT-BASELINE: an 'oauth' row does NOT resolve as a usable API credential
    # (only api_key/api_key_pool). S1's normalization revisits this.
    o = store.add(provider="anthropic", auth_type="oauth", alias="o", secret="tok-value-1234", make_active=False)
    assert _resolve_api_credential("anthropic", f"local:{o.id}", store) is None


# --- config route allow-set (handler-direct; not TestClient) -----------------
def test_route_rejects_unknown_auth_type(store):
    from fastapi import HTTPException

    from src.api.routes.config_routes import CredentialCreate, add_credential

    body = CredentialCreate(provider="openai", auth_type="bogus", alias="k", secret="sk-x", make_active=True)
    with pytest.raises(HTTPException) as ei:
        add_credential(body, store=store)
    assert ei.value.status_code == 400


def test_route_currently_rejects_explicit_oauth_modes(store):
    # CURRENT-BASELINE: allow-set = {api_key, oauth, setup_token}. The explicit
    # modes are NOT accepted yet — S1 flips this to accept them.
    from fastapi import HTTPException

    from src.api.routes.config_routes import CredentialCreate, add_credential

    for mode in ("chatgpt_oauth", "claude_code_oauth"):
        body = CredentialCreate(provider="openai", auth_type=mode, alias="k", secret="sk-x", make_active=True)
        with pytest.raises(HTTPException) as ei:
            add_credential(body, store=store)
        assert ei.value.status_code == 400


def test_route_accepts_api_key(store, monkeypatch, clean_env):
    from src.api.routes import config_routes as cr

    monkeypatch.setattr(cr, "require_profile_state_write", lambda *a, **k: None)  # neutralize write gate
    body = cr.CredentialCreate(provider="openai", auth_type="api_key", alias="k", secret="sk-realkeyvalue9", make_active=True)
    res = cr.add_credential(body, store=store)
    assert res["credential"]["auth_type"] == "api_key" and res["credential"]["id"].startswith("local:")
