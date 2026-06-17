"""Slice 6a — live-loop credential resolution (api_key wire-in foundation).

resolve_live_auth classifies the active credential per provider: a usable
db_api_key, or an OAuth row that is NOT yet servable by the live loop
(oauth_pending_env_fallback — explicit, NEVER silent) which falls back to the
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


def test_resolve_oauth_active_is_explicit_pending_fallback(store):
    store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude", make_active=True)
    res = lr.resolve_live_auth("anthropic", store=store)
    assert res.source == "oauth_pending_env_fallback"
    assert res.note and "not wired" in res.note.lower()  # explicit, non-silent


def test_resolve_no_active_is_env_fallback(store):
    res = lr.resolve_live_auth("openai", store=store)
    assert res.source == "env_fallback" and res.note is None


# --- live_anthropic_client ---------------------------------------------------
def test_live_anthropic_client_uses_db_api_key(store):
    store.add(provider="anthropic", auth_type="api_key", alias="A", secret="sk-ant-fake1", make_active=True)
    assert isinstance(lr.live_anthropic_client(store=store), Anthropic)


def test_live_anthropic_client_oauth_falls_back_to_env_with_warning(store, monkeypatch, caplog):
    store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude", make_active=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-envfake")  # so the env-fallback Anthropic() can construct
    lr._warned.clear()  # reset the once-per-process throttle so the WARNING fires here
    with caplog.at_level("WARNING"):
        c = lr.live_anthropic_client(store=store)
    assert isinstance(c, Anthropic)
    assert any("not wired" in r.message.lower() for r in caplog.records)  # fallback is LOGGED, not silent


# --- apply_openai_live_client ------------------------------------------------
def test_apply_openai_live_client_sets_default_for_db_key(store, monkeypatch):
    captured = {}
    monkeypatch.setattr(lr, "set_default_openai_client", lambda c: captured.setdefault("client", c))
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-fake1111", make_active=True)
    res = lr.apply_openai_live_client(store=store)
    assert res.source == "db_api_key" and "client" in captured  # SDK default registered


def test_apply_openai_fallback_resets_sticky_global_to_env(store, monkeypatch):
    # the SDK default client is a sticky process-global: after a db_api_key run
    # set it, a later fallback MUST reset it to an env client — not leave the
    # stale DB client (finding #1). With OPENAI_API_KEY present, the fallback
    # calls set_default_openai_client again (env-backed), not just logs.
    calls = []
    monkeypatch.setattr(lr, "set_default_openai_client", lambda c: calls.append(c))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-envfake")
    lr._warned.clear()
    store.add(provider="openai", auth_type="api_key", alias="primary", secret="sk-dbkey111", make_active=True)
    lr.apply_openai_live_client(store=store)  # call 1: DB client set
    store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg", make_active=True)  # OAuth now active
    res = lr.apply_openai_live_client(store=store)  # call 2: must RESET to env
    assert res.source == "oauth_pending_env_fallback"
    assert len(calls) == 2  # reset to an env client, NOT left stale


def test_apply_openai_fallback_no_env_leaves_default(store, monkeypatch):
    # if env has no key, there is no OpenAI auth to fall back to — leave the
    # default (constructing AsyncOpenAI() would raise); only log.
    calls = []
    monkeypatch.setattr(lr, "set_default_openai_client", lambda c: calls.append(c))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    lr._warned.clear()
    store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg", make_active=True)
    res = lr.apply_openai_live_client(store=store)
    assert res.source == "oauth_pending_env_fallback" and calls == []  # nothing set (no env key)


def test_live_openai_client_uses_db_api_key(store):
    store.add(provider="openai", auth_type="api_key", alias="p", secret="sk-fake1111", make_active=True)
    assert isinstance(lr.live_openai_client(store=store), OpenAI)


def test_live_openai_client_oauth_falls_back_to_env(store, monkeypatch):
    store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg", make_active=True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-envfake")
    lr._warned.clear()
    assert isinstance(lr.live_openai_client(store=store), OpenAI)  # sync env client
