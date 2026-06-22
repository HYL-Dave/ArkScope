"""Slice 6a — live-loop credential resolution (api_key wire-in foundation).

resolve_live_auth classifies the active credential per provider: a usable
db_api_key, or an OAuth row that is NOT yet servable by the live loop
(oauth_driver_unwired — explicit, NEVER silent) which falls back to the
env API key, or no active row (env_fallback). live_anthropic_client returns a
SYNC client (the 7 live Anthropic sites are sync); apply_openai_live_client
registers the SDK default for an active db_api_key. FAKE keys only.
"""

from __future__ import annotations

import pytest
from anthropic import Anthropic
from openai import OpenAI

from src.auth_drivers.api_key_drivers import (
    AnthropicApiKeyDriver,
    MissingCredentialError,
    OpenAIApiKeyDriver,
)
from src.auth_drivers import live_resolver as lr
from src.model_credentials import CredentialStore


@pytest.fixture()
def store(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db")


# --- driver client_sync() ----------------------------------------------------
def test_anthropic_driver_client_sync_is_sync_and_cached():
    d = AnthropicApiKeyDriver(api_key="sk-ant-fake123")
    c = d.client_sync()
    assert isinstance(c, Anthropic)  # SYNC client (not AsyncAnthropic)
    assert d.client_sync() is c  # cached


def test_openai_driver_client_sync_is_sync():
    assert isinstance(OpenAIApiKeyDriver(api_key="sk-fake123").client_sync(), OpenAI)


def test_client_sync_raises_without_key():
    with pytest.raises(MissingCredentialError):
        AnthropicApiKeyDriver(api_key=None).client_sync()


# --- resolve_live_auth -------------------------------------------------------
def test_resolve_active_db_api_key(store):
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-fake1111", make_active=True)
    res = lr.resolve_live_auth("openai", store=store)
    assert res.source == "db_api_key" and res.credential_id and res.note is None


def test_resolve_oauth_active_is_oauth_driver_unwired(store):
    store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude", make_active=True)
    res = lr.resolve_live_auth("anthropic", store=store)
    assert res.source == "oauth_driver_unwired"
    # anthropic note = direct-client fail-closed message (no false env fallback claim)
    assert res.note and "direct" in res.note.lower() and "paused" in res.note.lower()


def test_resolve_openai_oauth_note_says_fail_closed(store):
    # OpenAI chatgpt_oauth direct-client paths FAIL CLOSED (no silent env-key billing).
    # Its note is openai-specific + says paused, and must NOT claim an env fallback.
    store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg", make_active=True)
    res = lr.resolve_live_auth("openai", store=store)
    assert res.source == "oauth_driver_unwired"
    assert res.note and "direct" in res.note.lower() and "paused" in res.note.lower()
    assert "env api key fallback" not in res.note.lower()  # the OLD (now false) claim is gone


def test_resolve_no_active_is_env_fallback(store):
    res = lr.resolve_live_auth("openai", store=store)
    assert res.source == "env_fallback" and res.note is None


# --- live_anthropic_client ---------------------------------------------------
def test_live_anthropic_client_uses_db_api_key(store):
    store.add(provider="anthropic", auth_type="api_key", alias="A", secret="sk-ant-fake1", make_active=True)
    assert isinstance(lr.live_anthropic_client(store=store), Anthropic)


def test_live_anthropic_client_oauth_fails_closed(store, monkeypatch):
    # Claude OAuth Research is wired, but this sync SDK-client accessor still cannot
    # use the subscription token. Do NOT silently bill the env API key — FAIL CLOSED
    # with an actionable message. (Env key present so OLD behavior would use it.)
    store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude", make_active=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-envfake")
    with pytest.raises(lr.SubscriptionDriverNotWiredError) as ei:
        lr.live_anthropic_client(store=store)
    msg = str(ei.value)
    assert "API key" in msg and "Settings" in msg  # names the actionable fix
    assert "sk-ant-envfake" not in msg  # never leak the env key


def test_live_anthropic_client_api_key_active_unaffected(store):
    # api-key-active anthropic must STILL work (fail-closed is OAuth-only).
    store.add(provider="anthropic", auth_type="api_key", alias="A", secret="sk-ant-fake1", make_active=True)
    assert isinstance(lr.live_anthropic_client(store=store), Anthropic)


# --- apply_openai_live_client ------------------------------------------------
def test_apply_openai_live_client_sets_default_for_db_key(store, monkeypatch):
    captured = {}
    monkeypatch.setattr(lr, "set_default_openai_client", lambda c: captured.setdefault("client", c))
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-fake1111", make_active=True)
    res = lr.apply_openai_live_client(store=store)
    assert res.source == "db_api_key" and "client" in captured  # SDK default registered


def test_apply_openai_oauth_fails_closed_neutralizing_sticky_global(store, monkeypatch):
    # S3 step 0: an active chatgpt_oauth credential FAILS CLOSED before Runner.run —
    # it must NOT silently bill the env API key. It also neutralizes the sticky
    # process-global FIRST (so a prior db_api_key run is never left usable), THEN raises.
    calls = []
    monkeypatch.setattr(lr, "set_default_openai_client", lambda c: calls.append(c))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-envfake")  # present, but must NOT be used for an oauth-active cred
    lr._warned.clear()
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-dbkey111", make_active=True)
    lr.apply_openai_live_client(store=store)  # call 1: DB client set
    store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg", make_active=True)  # OAuth now active
    with pytest.raises(lr.SubscriptionDriverNotWiredError) as ei:
        lr.apply_openai_live_client(store=store)  # call 2: neutralize sticky global, then raise
    assert "API key" in str(ei.value) and "Settings" in str(ei.value)
    assert "sk-envfake" not in str(ei.value)  # never leak the env key
    assert len(calls) == 2  # the sticky global was RESET (not left as the db client) before raising


def test_apply_openai_env_fallback_no_active_still_uses_env(store, monkeypatch):
    # A genuine env_fallback (NO active credential at all) is NOT fail-closed —
    # the env key is the legitimate default when the user chose no credential.
    calls = []
    monkeypatch.setattr(lr, "set_default_openai_client", lambda c: calls.append(c))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-envfake")
    lr._warned.clear()
    res = lr.apply_openai_live_client(store=store)  # no credentials at all
    assert res.source == "env_fallback" and len(calls) == 1  # env client set, NO raise


def test_apply_openai_env_fallback_no_env_neutralizes_stale_global(store, monkeypatch):
    # no active credential AND no env key → set a non-usable client so a prior
    # db_api_key global is never silently reused (finding #1; env_fallback path).
    calls = []
    monkeypatch.setattr(lr, "set_default_openai_client", lambda c: calls.append(c))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    lr._warned.clear()
    res = lr.apply_openai_live_client(store=store)
    assert res.source == "env_fallback" and len(calls) == 1  # neutralized, not left stale


def test_live_openai_client_uses_db_api_key(store):
    store.add(provider="openai", auth_type="api_key", alias="p", secret="sk-fake1111", make_active=True)
    assert isinstance(lr.live_openai_client(store=store), OpenAI)


def test_live_openai_client_oauth_fails_closed(store, monkeypatch):
    # S3 step 0: the sync OpenAI client sites (card synthesis, code-gen) also fail
    # closed for an active chatgpt_oauth credential — no silent env-key billing.
    store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg", make_active=True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-envfake")  # present; must NOT be silently used
    lr._warned.clear()
    with pytest.raises(lr.SubscriptionDriverNotWiredError) as ei:
        lr.live_openai_client(store=store)
    assert "API key" in str(ei.value) and "Settings" in str(ei.value)
    assert "sk-envfake" not in str(ei.value)


def test_live_openai_client_api_key_active_unaffected(store):
    # api-key-active openai must STILL work (fail-closed is OAuth-only).
    store.add(provider="openai", auth_type="api_key", alias="p", secret="sk-fake1111", make_active=True)
    assert isinstance(lr.live_openai_client(store=store), OpenAI)


def test_live_openai_client_no_active_env_fallback(store, monkeypatch):
    # genuine env fallback (no active credential) still returns a bare env client.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-envfake")
    assert isinstance(lr.live_openai_client(store=store), OpenAI)
