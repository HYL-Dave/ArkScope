"""Slice 6 — resolve the live loop's LLM client from the active DB credential.

This is the api_key live wire-in ONLY. The live agents historically construct a
bare SDK client that reads the key implicitly from ``os.environ``; this module
lets them instead obtain a client built from the *active* credential row, so a
manual key switch in Settings takes effect on the next query.

Hard rule: when an OAuth credential is ACTIVE but the current call site is a
direct SDK-client path that cannot use that OAuth mode, FAIL CLOSED — never
silently bill the env API key. Research streaming and structured card tasks
intercept the resolution and use explicit subscription adapters; unrelated
direct-client sites such as code generation remain fail-closed. A genuine
env_fallback (NO active credential chosen) still uses the env key — that is the
legitimate default, not a pretense.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from agents import set_default_openai_client  # SDK process-global default client

from src.auth_drivers.factory import build_driver
from src.model_credentials import CredentialStore

logger = logging.getLogger(__name__)


class SubscriptionDriverNotWiredError(RuntimeError):
    """Raised when an OAuth/subscription credential is the ACTIVE one but its
    current direct-client call site cannot use it. We FAIL CLOSED rather than
    silently bill the env API key — picking an OAuth credential must never quietly
    meter an API key the user didn't intend to spend."""


# Anthropic-specific, actionable. (resolve_live_auth's .note stays
# provider-generic — OpenAI chatgpt_oauth also yields oauth_driver_unwired
# and must NOT inherit this Anthropic/Slice-7 wording.)
_ANTHROPIC_OAUTH_FAILCLOSED_MSG = (
    "Claude OAuth (claude_code_oauth) is the active Anthropic credential. AI "
    "Research and structured card tasks have subscription adapters, but this direct Anthropic SDK "
    "client path cannot use that subscription token. The call is paused rather "
    "than silently billing the env API key — switch the active Anthropic credential "
    "to an API key in Settings for this feature."
)

_OPENAI_OAUTH_FAILCLOSED_MSG = (
    "ChatGPT OAuth (chatgpt_oauth) is the active OpenAI credential. AI Research and "
    "structured card tasks have ChatGPT backend adapters, but this direct OpenAI SDK client path cannot "
    "use that subscription token. The call is paused rather than silently billing "
    "the env API key — switch the active OpenAI credential to an API key in Settings "
    "for this feature."
)

# The OAuth→env fallback must be EXPLICIT but not spammy: WARNING once per
# (provider, source) per process; thereafter DEBUG. The structured
# LiveAuthResolution remains the queryable surface for the UI/Settings.
_warned: set = set()


def _signal_fallback(res: "LiveAuthResolution") -> None:
    if not res.note:
        return
    key = f"{res.provider}:{res.source}"
    if key in _warned:
        logger.debug("%s", res.note)
    else:
        _warned.add(key)
        logger.warning("%s", res.note)


@dataclass(frozen=True)
class LiveAuthResolution:
    """How the live loop resolved auth for a provider — surfaceable to logs/UI."""

    provider: str
    source: str  # "db_api_key" | "oauth_driver_unwired" | "env_fallback"
    credential_id: Optional[str] = None
    note: Optional[str] = None  # human message for the OAuth-pending fallback


def _active(provider: str, store: CredentialStore):
    return next((c for c in store.list(provider) if c.active), None)


def resolve_live_auth(provider: str, *, store: Optional[CredentialStore] = None) -> LiveAuthResolution:
    """Classify the active credential for the live loop (no client built here)."""
    store = store or CredentialStore()
    active = _active(provider, store)
    if active is not None and active.auth_type == "api_key" and active.secret:
        return LiveAuthResolution(provider, "db_api_key", f"local:{active.id}")
    if active is not None and active.auth_type in ("claude_code_oauth", "chatgpt_oauth"):
        # An OAuth credential is active. Research streaming may intercept this
        # classifier and route to an OAuth driver; direct SDK-client call sites use
        # the note below and fail closed instead of silently using an env API key.
        note = _ANTHROPIC_OAUTH_FAILCLOSED_MSG if provider == "anthropic" else _OPENAI_OAUTH_FAILCLOSED_MSG
        return LiveAuthResolution(provider, "oauth_driver_unwired", f"local:{active.id}", note)
    return LiveAuthResolution(provider, "env_fallback")


def live_anthropic_client(*, store: Optional[CredentialStore] = None) -> Any:
    """A SYNC ``Anthropic`` client for the live Anthropic call sites.

    db_api_key → built from the active row via the driver. OAuth-active →
    FAIL CLOSED (this sync client path cannot use the subscription token; don't
    silently bill the env key). No active credential → env fallback (bare
    ``Anthropic()``).
    """
    from anthropic import Anthropic

    store = store or CredentialStore()
    res = resolve_live_auth("anthropic", store=store)
    if res.source == "db_api_key":
        cred = store.get(res.credential_id)
        return build_driver(provider="anthropic", auth_mode="api_key", credential=cred).client_sync()
    if res.source == "oauth_driver_unwired":
        # 7A-0: never silently meter the env API key when the user chose OAuth.
        raise SubscriptionDriverNotWiredError(_ANTHROPIC_OAUTH_FAILCLOSED_MSG)
    return Anthropic()  # genuinely no active credential → env fallback


def live_openai_client(*, store: Optional[CredentialStore] = None) -> Any:
    """A SYNC ``OpenAI`` client for the direct (non-Agents-SDK) OpenAI call sites
    (including code generation and API-key card calls). db_api_key → built from the active row via the
    driver; chatgpt_oauth-active → FAIL CLOSED (S3 step 0; don't silently bill the
    env key); no active credential → env fallback (bare ``OpenAI()``)."""
    from openai import OpenAI

    store = store or CredentialStore()
    res = resolve_live_auth("openai", store=store)
    if res.source == "db_api_key":
        cred = store.get(res.credential_id)
        return build_driver(provider="openai", auth_mode="api_key", credential=cred).client_sync()
    if res.source == "oauth_driver_unwired":
        # S3 step 0: the user chose chatgpt_oauth; never silently meter the env key.
        raise SubscriptionDriverNotWiredError(_OPENAI_OAUTH_FAILCLOSED_MSG)
    _signal_fallback(res)
    return OpenAI()  # genuinely no active credential → env fallback (OPENAI_API_KEY)


def apply_openai_live_client(*, store: Optional[CredentialStore] = None) -> LiveAuthResolution:
    """Register the SDK default OpenAI client from the active credential.

    Call once per run BEFORE ``Runner.run`` (the Agents-SDK Runner takes no client
    arg; the global default is the only injection point). db_api_key → set the
    default to a client built from the active row. On fallback we NEVER leave a
    stale global: with ``OPENAI_API_KEY`` present → reset to an env-backed client;
    without → set a non-usable client so a previously-set DB credential is not
    silently reused (OpenAI calls then fail clearly rather than on the wrong key).

    NOTE: ``set_default_openai_client`` is a PROCESS-GLOBAL. Set it immediately
    before ``Runner.run``; concurrent OpenAI runs in one process share it.
    """
    import os

    from openai import AsyncOpenAI

    _NEUTRAL = "ARKSCOPE-NO-OPENAI-CREDENTIAL"  # a non-usable key so a stale global can't be reused

    store = store or CredentialStore()
    res = resolve_live_auth("openai", store=store)
    if res.source == "db_api_key":
        cred = store.get(res.credential_id)
        set_default_openai_client(build_driver(provider="openai", auth_mode="api_key", credential=cred).client())
        return res
    if res.source == "oauth_driver_unwired":
        # The user chose chatgpt_oauth, but this Agents-SDK global-client path is
        # not the ChatGPT-backend Research driver — FAIL CLOSED. Neutralize the
        # sticky process-global FIRST (so a prior db_api_key run is never left
        # usable, even though we're about to raise), then raise. The env key is
        # NOT used here, by design.
        set_default_openai_client(AsyncOpenAI(api_key=_NEUTRAL))
        raise SubscriptionDriverNotWiredError(_OPENAI_OAUTH_FAILCLOSED_MSG)
    # env_fallback: genuinely no active credential chosen. NEVER leave a stale DB
    # global — with OPENAI_API_KEY → reset to an env client; without → neutralize.
    _signal_fallback(res)
    if os.environ.get("OPENAI_API_KEY", "").strip():
        set_default_openai_client(AsyncOpenAI())
    else:
        set_default_openai_client(AsyncOpenAI(api_key=_NEUTRAL))
    return res
