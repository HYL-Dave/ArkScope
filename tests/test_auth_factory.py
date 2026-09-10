"""Auth factory routing, explicit errors and dependency injection, without live calls."""

from __future__ import annotations

import pytest

from src.auth_drivers import PlaintextTokenStore
from src.auth_drivers.api_key_drivers import AnthropicApiKeyDriver, OpenAIApiKeyDriver
from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
from src.auth_drivers.claude_code_sdk_driver import AnthropicClaudeCodeSdkDriver
from src.auth_drivers.factory import build_driver


def _cred(provider="openai", auth_type="api_key", cid="local:1"):
    # minimal credential-like object the factory reads (id/provider/auth_type)
    from src.model_credentials import StoredCredential

    return StoredCredential(
        id=int(cid.split(":")[1]), provider=provider, auth_type=auth_type,
        alias="k", secret="sk-x", active=True, created_at="t", updated_at="t",
    )


# Provider-specific valid modes (S1.2): the product matrix is api_key +
# the provider's OWN OAuth mode; api_key_pool is an internal/env-compat mode.
_VALID_COMBOS = [
    ("openai", "api_key"), ("openai", "api_key_pool"), ("openai", "chatgpt_oauth"),
    ("anthropic", "api_key"), ("anthropic", "api_key_pool"), ("anthropic", "claude_code_oauth"),
]
_INVALID_COMBOS = [
    ("openai", "claude_code_oauth"),   # OpenAI can't use Claude's OAuth
    ("anthropic", "chatgpt_oauth"),    # Anthropic can't use ChatGPT's OAuth
]


_REAL_COMBOS = [
    ("openai", "api_key", OpenAIApiKeyDriver),
    ("openai", "api_key_pool", OpenAIApiKeyDriver),
    ("openai", "chatgpt_oauth", OpenAIChatGPTOAuthDriver),
    ("anthropic", "api_key", AnthropicApiKeyDriver),
    ("anthropic", "api_key_pool", AnthropicApiKeyDriver),
    ("anthropic", "claude_code_oauth", AnthropicClaudeCodeSdkDriver),
]


# --- routing: every VALID (provider, auth_mode) yields a driver carrying identity
@pytest.mark.parametrize("provider,auth_mode", _VALID_COMBOS)
def test_build_driver_carries_identity(provider, auth_mode):
    d = build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert d.provider == provider and d.auth_mode == auth_mode


@pytest.mark.parametrize("provider,auth_mode,expected_type", _REAL_COMBOS)
def test_all_product_modes_resolve_expected_driver(provider, auth_mode, expected_type):
    d = build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert type(d) is expected_type


@pytest.mark.parametrize("provider,auth_mode", _INVALID_COMBOS)
def test_build_driver_rejects_cross_provider_oauth(provider, auth_mode):
    # the matrix is provider-specific — a provider's wrong OAuth mode is rejected,
    # not silently accepted (the old cartesian-product bug).
    with pytest.raises(ValueError) as ei:
        build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert auth_mode in str(ei.value) and provider in str(ei.value)


def test_chatgpt_oauth_without_token_fails_closed():
    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    import asyncio

    # S3 D4: fail-closed is now ONE classified error event (this is the WIRING
    # arm — a driver built with no token-store; re-login cannot fix it, so the
    # code is missing_credential, not reauth). call_llm re-raises it; nothing
    # ever falls through to a backend call. (Previously a bare
    # MissingCredentialError raise before the stream started.)
    with pytest.raises(RuntimeError, match="missing its token store"):
        asyncio.run(d.call_llm(None))


def test_chatgpt_oauth_execution_driver_is_wired():
    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert callable(d.stream_llm)


def test_claude_code_oauth_is_the_sdk_driver():
    from src.auth_drivers.oauth_status import OAuthObservationStore
    d = build_driver(provider="anthropic", auth_mode="claude_code_oauth", credential=_cred(auth_type="claude_code_oauth"))
    assert type(d) is AnthropicClaudeCodeSdkDriver
    assert isinstance(d._observation_store, OAuthObservationStore)


def test_claude_code_oauth_factory_passes_max_turns():
    d = build_driver(
        provider="anthropic",
        auth_mode="claude_code_oauth",
        credential=_cred(auth_type="claude_code_oauth"),
        max_turns=42,
    )
    assert d._max_turns == 42


def test_chatgpt_oauth_factory_passes_registry_dal_and_runtime_limits():
    registry = object()
    dal = object()
    d = build_driver(
        provider="openai",
        auth_mode="chatgpt_oauth",
        credential=_cred(auth_type="chatgpt_oauth"),
        registry=registry,
        dal=dal,
        max_turns=33,
        timeout_s=444,
        per_tool_timeout_s=12,
    )
    assert d._registry is registry
    assert d._dal is dal
    assert d._max_turns == 33
    assert d._timeout_s == 444
    assert d._per_tool_timeout_s == 12


# --- explicit errors for unknown provider / auth_mode -----------------------
def test_unknown_provider_raises_valueerror():
    with pytest.raises(ValueError) as ei:
        build_driver(provider="gemini", auth_mode="api_key", credential=_cred("gemini"))
    assert "gemini" in str(ei.value)


def test_unknown_auth_mode_raises_valueerror():
    with pytest.raises(ValueError) as ei:
        build_driver(provider="openai", auth_mode="psychic", credential=_cred(auth_type="api_key"))
    assert "psychic" in str(ei.value)


def test_unhandled_admitted_mode_fails_closed(monkeypatch):
    from src.auth_drivers import factory

    monkeypatch.setitem(factory._ALLOWED_MODES, "openai", frozenset({"future_mode"}))
    with pytest.raises(RuntimeError, match="unhandled admitted driver: openai/future_mode"):
        build_driver(provider="openai", auth_mode="future_mode", credential=_cred())


# --- OAuth modes must NOT be silently treated as api_key --------------------
def test_oauth_mode_is_not_api_key_path():
    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert d.auth_mode == "chatgpt_oauth"  # identity preserved, not collapsed to api_key
    import asyncio

    # Without a token-store it fails closed via the classified missing_credential
    # error (S3 D4); it never falls through to the api_key path.
    with pytest.raises(RuntimeError, match="missing its token store"):
        asyncio.run(d.call_llm(None))


# --- optional token_store injection -----------------------------------------
def test_token_store_optional_and_injected(tmp_path):
    # the chatgpt_oauth driver loads its token from the token-store ONLY (never
    # credential.secret); the factory injects it (the driver holds it privately).
    d0 = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert d0._token_store is None
    ts = PlaintextTokenStore(tmp_path / "t.json")
    d1 = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"), token_store=ts)
    assert d1._token_store is ts


# --- the concrete OAuth driver conforms to BOTH contracts -------------------
def test_chatgpt_oauth_driver_conforms_to_authdriver_and_research_driver():
    from src.auth_drivers import AuthDriver, ResearchProviderDriver

    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert isinstance(d, AuthDriver)
    assert isinstance(d, ResearchProviderDriver)


def test_chatgpt_oauth_discovery_is_real_not_gated():
    # S3 step 1: discover_models/test now RETURN (they no longer raise). With no
    # token-store, discovery honestly degrades to missing_credential + the seed list.
    import asyncio

    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    disc = asyncio.run(d.discover_models())
    assert disc.provider == "openai" and disc.status == "missing_credential" and len(disc.models) > 0
    res = asyncio.run(d.test())
    assert res.status in ("missing_credential", "error")  # honest deferral, never a fake "ok"
