"""S1 piece-3: build_driver factory SKELETON.

Strict scope: routing + explicit errors + optional token_store injection. No real
driver bodies (S2 builds api_key; S3/S4 the OAuth ones behind probes), no
main-agent wiring, no Settings UI, no live provider calls.
"""

from __future__ import annotations

import pytest

from src.auth_drivers import PlaintextTokenStore
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


# --- routing: every VALID (provider, auth_mode) yields a driver placeholder ---
@pytest.mark.parametrize("provider,auth_mode", _VALID_COMBOS)
def test_build_driver_returns_placeholder_carrying_identity(provider, auth_mode):
    d = build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert isinstance(d, NotImplementedDriver)
    assert d.provider == provider and d.auth_mode == auth_mode


@pytest.mark.parametrize("provider,auth_mode", _INVALID_COMBOS)
def test_build_driver_rejects_cross_provider_oauth(provider, auth_mode):
    # the matrix is provider-specific — a provider's wrong OAuth mode is rejected,
    # not silently accepted (the old cartesian-product bug).
    with pytest.raises(ValueError) as ei:
        build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert auth_mode in str(ei.value) and provider in str(ei.value)


# --- the placeholder is inert: calling it raises NotImplementedError (slice ref)
def test_api_key_placeholder_not_callable_yet():
    d = build_driver(provider="openai", auth_mode="api_key", credential=_cred())
    import asyncio

    with pytest.raises(NotImplementedError) as ei:
        asyncio.run(d.call_llm(None))
    assert "S2" in str(ei.value)  # api_key drivers come in S2


def test_oauth_modes_reference_their_probe_slice():
    for mode, slice_tag in [("chatgpt_oauth", "S3"), ("claude_code_oauth", "S4")]:
        d = build_driver(provider=("openai" if mode == "chatgpt_oauth" else "anthropic"), auth_mode=mode, credential=_cred(auth_type=mode))
        import asyncio

        with pytest.raises(NotImplementedError) as ei:
            asyncio.run(d.call_llm(None))
        msg = str(ei.value)
        assert slice_tag in msg and "probe" in msg.lower()  # message names the gating probe


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

    # an api_key-style call must not succeed via an OAuth placeholder
    with pytest.raises(NotImplementedError):
        asyncio.run(d.call_llm(None))


# --- optional token_store injection -----------------------------------------
def test_token_store_optional_and_injected(tmp_path):
    # default: no token store
    d0 = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    assert d0.token_store is None
    # injected: carried onto the driver (OAuth drivers will need it in S3/S4)
    ts = PlaintextTokenStore(tmp_path / "t.json")
    d1 = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"), token_store=ts)
    assert d1.token_store is ts


# --- conforms to BOTH contracts (the factory is a research-driver factory) ---
def test_placeholder_conforms_to_authdriver_and_research_driver():
    from src.auth_drivers import AuthDriver, ResearchProviderDriver

    d = build_driver(provider="openai", auth_mode="api_key", credential=_cred())
    assert isinstance(d, AuthDriver)
    assert isinstance(d, ResearchProviderDriver)  # has discover_models() + test()


def test_discover_and_test_are_gated_with_slice_message():
    import asyncio

    d = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=_cred(auth_type="chatgpt_oauth"))
    with pytest.raises(NotImplementedError) as ei1:
        asyncio.run(d.discover_models())
    with pytest.raises(NotImplementedError) as ei2:
        asyncio.run(d.test())
    assert "S3" in str(ei1.value) and "S3" in str(ei2.value)  # names the gating slice
