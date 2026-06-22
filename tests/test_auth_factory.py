"""S1 piece-3: build_driver factory SKELETON.

Strict scope: routing + explicit errors + optional token_store injection. No real
driver bodies (S2 builds api_key; S3/S4 the OAuth ones behind probes), no
main-agent wiring, no Settings UI, no live provider calls.
"""

from __future__ import annotations

import pytest

from src.auth_drivers import PlaintextTokenStore
from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.factory import NotImplementedDriver, build_driver


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


# Every product combo now resolves to a REAL driver: api_key/api_key_pool (S2),
# anthropic+claude_code_oauth (7B SDK driver), openai+chatgpt_oauth (S3 step 1 —
# real for discovery; its EXECUTION stays gated inside the driver until step 4).
# No (provider, auth_mode) in the valid matrix is a NotImplementedDriver anymore.
_REAL_COMBOS = [("openai", "api_key"), ("openai", "api_key_pool"), ("openai", "chatgpt_oauth"),
                ("anthropic", "api_key"), ("anthropic", "api_key_pool"), ("anthropic", "claude_code_oauth")]


# --- routing: every VALID (provider, auth_mode) yields a driver carrying identity
@pytest.mark.parametrize("provider,auth_mode", _VALID_COMBOS)
def test_build_driver_carries_identity(provider, auth_mode):
    d = build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert d.provider == provider and d.auth_mode == auth_mode


@pytest.mark.parametrize("provider,auth_mode", _REAL_COMBOS)
def test_all_product_modes_are_real_drivers_not_placeholders(provider, auth_mode):
    # Every valid product combo resolves to a REAL driver now (incl. chatgpt_oauth,
    # S3 step 1). NotImplementedDriver is no longer returned for any valid combo.
    d = build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert not isinstance(d, NotImplementedDriver)


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

    with pytest.raises(MissingCredentialError):
        asyncio.run(d.call_llm(None))


def test_chatgpt_oauth_execution_driver_is_wired():
    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert callable(d.stream_llm)


def test_claude_code_oauth_is_the_sdk_driver_not_placeholder():
    # 7B-5: the factory returns the Agent-SDK driver. The experimental 7A
    # `claude -p --bare` driver is superseded and no longer wired here.
    from src.auth_drivers.claude_code_sdk_driver import AnthropicClaudeCodeSdkDriver
    d = build_driver(provider="anthropic", auth_mode="claude_code_oauth", credential=_cred(auth_type="claude_code_oauth"))
    assert isinstance(d, AnthropicClaudeCodeSdkDriver) and not isinstance(d, NotImplementedDriver)


def test_claude_code_oauth_factory_passes_max_turns():
    d = build_driver(
        provider="anthropic",
        auth_mode="claude_code_oauth",
        credential=_cred(auth_type="claude_code_oauth"),
        max_turns=42,
    )
    assert d._max_turns == 42


def test_chatgpt_oauth_factory_passes_registry_dal_and_max_turns():
    registry = object()
    dal = object()
    d = build_driver(
        provider="openai",
        auth_mode="chatgpt_oauth",
        credential=_cred(auth_type="chatgpt_oauth"),
        registry=registry,
        dal=dal,
        max_turns=33,
    )
    assert d._registry is registry
    assert d._dal is dal
    assert d._max_turns == 33


# --- explicit errors for unknown provider / auth_mode -----------------------
def test_unknown_provider_raises_valueerror():
    with pytest.raises(ValueError) as ei:
        build_driver(provider="gemini", auth_mode="api_key", credential=_cred("gemini"))
    assert "gemini" in str(ei.value)


def test_unknown_auth_mode_raises_valueerror():
    with pytest.raises(ValueError) as ei:
        build_driver(provider="openai", auth_mode="psychic", credential=_cred(auth_type="api_key"))
    assert "psychic" in str(ei.value)


# --- OAuth modes must NOT be silently treated as api_key --------------------
def test_oauth_mode_is_not_api_key_path():
    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert d.auth_mode == "chatgpt_oauth"  # identity preserved, not collapsed to api_key
    import asyncio

    # Without a token-store token it fails closed; it never falls through to api_key.
    with pytest.raises(MissingCredentialError):
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


# --- the OAuth placeholder conforms to BOTH contracts -----------------------
def test_placeholder_conforms_to_authdriver_and_research_driver():
    from src.auth_drivers import AuthDriver, ResearchProviderDriver

    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert isinstance(d, AuthDriver)
    assert isinstance(d, ResearchProviderDriver)  # placeholder has discover_models() + test()


def test_chatgpt_oauth_discovery_is_real_not_gated():
    # S3 step 1: discover_models/test now RETURN (they no longer raise). With no
    # token-store, discovery honestly degrades to missing_credential + the seed list.
    import asyncio

    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    disc = asyncio.run(d.discover_models())
    assert disc.provider == "openai" and disc.status == "missing_credential" and len(disc.models) > 0
    res = asyncio.run(d.test())
    assert res.status in ("missing_credential", "error")  # honest deferral, never a fake "ok"
