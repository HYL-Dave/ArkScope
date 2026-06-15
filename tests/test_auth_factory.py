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


# --- routing: every valid (provider, auth_mode) yields a driver placeholder ---
@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("auth_mode", ["api_key", "api_key_pool", "chatgpt_oauth", "claude_code_oauth"])
def test_build_driver_returns_placeholder_carrying_identity(provider, auth_mode):
    d = build_driver(provider=provider, auth_mode=auth_mode, credential=_cred(provider, auth_mode))
    assert isinstance(d, NotImplementedDriver)
    assert d.provider == provider and d.auth_mode == auth_mode


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


# --- conforms to the AuthDriver contract (structural) -----------------------
def test_placeholder_conforms_to_authdriver():
    from src.auth_drivers import AuthDriver

    d = build_driver(provider="openai", auth_mode="api_key", credential=_cred())
    assert isinstance(d, AuthDriver)
