"""S2 — standard api_key drivers (OpenAIApiKeyDriver / AnthropicApiKeyDriver).

Scope (user-decided option 1): real auth-state + discover_models()/test()
DELEGATING to the proven model_credentials path (parity by construction) +
get_quota_status(unknown) + a client() accessor (what S5 wire-in needs).
call_llm/stream_llm are gated to S5. Mocked SDK / mocked delegation — no live
LLM, no main-agent wiring.
"""

from __future__ import annotations

import asyncio

import pytest

from src import model_credentials as mc
from src.auth_drivers import AuthDriver, ResearchProviderDriver, build_driver
from src.auth_drivers.api_key_drivers import (
    AnthropicApiKeyDriver,
    MissingCredentialError,
    OpenAIApiKeyDriver,
)
from src.model_credentials import DiscoveredModel, ModelDiscoveryResult, ModelTestResult


def _run(coro):
    return asyncio.run(coro)


# --- auth state -------------------------------------------------------------
def test_is_authenticated_reflects_api_key():
    assert OpenAIApiKeyDriver(api_key="sk-xxxx").is_authenticated is True
    assert OpenAIApiKeyDriver(api_key=None).is_authenticated is False


def test_authenticate_raises_without_credentials():
    with pytest.raises(MissingCredentialError):
        _run(OpenAIApiKeyDriver(api_key=None).authenticate())
    _run(OpenAIApiKeyDriver(api_key="sk-xxxx").authenticate())  # no raise


def test_refresh_if_needed_is_noop():
    assert _run(OpenAIApiKeyDriver(api_key="sk-x").refresh_if_needed()) is None


def test_identity_fields():
    o = OpenAIApiKeyDriver(api_key="sk-x")
    a = AnthropicApiKeyDriver(api_key="sk-x")
    assert (o.provider, o.auth_mode) == ("openai", "api_key")
    assert (a.provider, a.auth_mode) == ("anthropic", "api_key")


# --- discover_models() / test() DELEGATE → parity by construction -----------
def test_discover_models_delegates_to_model_credentials(monkeypatch):
    sentinel = ModelDiscoveryResult(
        provider="openai", credential_id="local:1", status="ok",
        models=[DiscoveredModel(id="gpt-5.4", provider="openai", label="GPT-5.4", source="provider_api")],
    )
    seen = {}

    def fake_discover(provider, credential_id=None, store=None):
        seen.update(provider=provider, credential_id=credential_id, store=store)
        return sentinel

    monkeypatch.setattr(mc, "discover_models", fake_discover)
    d = OpenAIApiKeyDriver(api_key="sk-x", credential_id="local:1", store="STORE")
    out = _run(d.discover_models())
    assert out is sentinel  # exact passthrough = parity with the existing function
    assert seen == {"provider": "openai", "credential_id": "local:1", "store": "STORE"}


def test_test_delegates_with_model_and_default(monkeypatch):
    captured = []

    def fake_test(provider, model, effort="default", credential_id=None, store=None):
        captured.append((provider, model, effort, credential_id))
        return ModelTestResult(provider=provider, credential_id=credential_id, model=model, effort=effort, status="ok")

    monkeypatch.setattr(mc, "test_model", fake_test)
    d = AnthropicApiKeyDriver(api_key="sk-x", credential_id="local:2", store="STORE")
    r = _run(d.test(model="claude-sonnet-4-6"))
    assert r.status == "ok" and r.model == "claude-sonnet-4-6"
    assert captured[-1] == ("anthropic", "claude-sonnet-4-6", "default", "local:2")
    # model=None → a provider default catalog model is chosen (still delegates)
    _run(d.test())
    assert captured[-1][0] == "anthropic" and captured[-1][1]  # some non-empty default model


# --- get_quota_status: honest UNKNOWN ---------------------------------------
def test_get_quota_status_unknown():
    st = _run(OpenAIApiKeyDriver(api_key="sk-x").get_quota_status())
    assert st["status"] == "unknown" and st["auth_mode"] == "api_key" and st["provider"] == "openai"


# --- client() accessor + P1 A-side: STANDARD host (no chatgpt backend) ------
def test_openai_client_targets_standard_api_host():
    c = OpenAIApiKeyDriver(api_key="sk-test").client()
    base = str(c.base_url)
    assert "api.openai.com" in base and "chatgpt.com" not in base  # P1 A-side


def test_anthropic_client_targets_standard_api_host():
    c = AnthropicApiKeyDriver(api_key="sk-test").client()
    assert "api.anthropic.com" in str(c.base_url)


def test_client_raises_without_key():
    with pytest.raises(MissingCredentialError):
        OpenAIApiKeyDriver(api_key=None).client()


def test_injected_client_is_used():
    fake = object()
    d = OpenAIApiKeyDriver(api_key=None, client=fake)
    assert d.is_authenticated is True and d.client() is fake


# --- call_llm / stream_llm gated to S5 --------------------------------------
def test_call_llm_gated_to_s5():
    with pytest.raises(NotImplementedError) as ei:
        _run(OpenAIApiKeyDriver(api_key="sk-x").call_llm(None))
    assert "S5" in str(ei.value)


def test_stream_llm_gated_to_s5():
    with pytest.raises(NotImplementedError) as ei:
        OpenAIApiKeyDriver(api_key="sk-x").stream_llm(None)  # raises on call, before iteration
    assert "S5" in str(ei.value)


def test_logout_clears(monkeypatch):
    d = OpenAIApiKeyDriver(api_key="sk-x")
    d.client()  # populate cached client
    _run(d.logout())
    assert d.is_authenticated is False


# --- contract conformance ---------------------------------------------------
def test_conforms_to_both_contracts():
    d = OpenAIApiKeyDriver(api_key="sk-x")
    assert isinstance(d, AuthDriver) and isinstance(d, ResearchProviderDriver)


# --- build_driver wires api_key → the REAL driver (OAuth still placeholder) -
def test_build_driver_api_key_returns_real_driver():
    from src.auth_drivers.factory import NotImplementedDriver
    from src.model_credentials import StoredCredential

    cred = StoredCredential(id=1, provider="openai", auth_type="api_key", alias="k",
                            secret="sk-real", active=True, created_at="t", updated_at="t")
    d = build_driver(provider="openai", auth_mode="api_key", credential=cred)
    assert isinstance(d, OpenAIApiKeyDriver) and not isinstance(d, NotImplementedDriver)
    assert d.is_authenticated is True  # secret carried from the credential

    acred = StoredCredential(id=2, provider="anthropic", auth_type="api_key", alias="k",
                             secret="sk-real", active=True, created_at="t", updated_at="t")
    assert isinstance(build_driver(provider="anthropic", auth_mode="api_key", credential=acred), AnthropicApiKeyDriver)


def test_build_driver_oauth_still_placeholder():
    from src.auth_drivers.factory import NotImplementedDriver

    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=None)
    assert isinstance(d, NotImplementedDriver)  # OAuth real driver is S3/S4
