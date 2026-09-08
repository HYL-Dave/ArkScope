"""In-memory execution auth. Never put a binding in durable or public records."""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from src.model_credentials import CredentialStore


class RuntimeAuthUnavailable(ValueError):
    """Bounded failure: selected auth cannot be replaced with current Settings."""


@dataclass(frozen=True)
class RuntimeAuthBinding:
    provider: str
    source: str
    auth_mode: str
    credential_id: str | None = None
    _api_key: str | None = field(default=None, repr=False)
    token_store: Any = field(default=None, repr=False, compare=False)

    def __reduce_ex__(self, protocol):
        raise TypeError("runtime auth bindings cannot be persisted")

    def credential(self):
        """Detached OAuth driver metadata, never an API-key resolver input."""
        if self.auth_mode not in ("chatgpt_oauth", "claude_code_oauth"):
            raise RuntimeAuthUnavailable("runtime_auth_mode_unsupported")
        return SimpleNamespace(
            id=int(self.credential_id.removeprefix("local:")) if self.credential_id else None,
            provider=self.provider, auth_type=self.auth_mode, secret=None,
        )

    def api_client(self, *, asynchronous: bool = False):
        """Explicit per-execution SDK client; never consult env after capture."""
        if self.auth_mode != "api_key" or not self._api_key:
            raise RuntimeAuthUnavailable("runtime_auth_unavailable")
        if self.provider == "openai":
            from openai import AsyncOpenAI, OpenAI

            client = AsyncOpenAI if asynchronous else OpenAI
        else:
            from anthropic import AsyncAnthropic, Anthropic

            client = AsyncAnthropic if asynchronous else Anthropic
        return client(api_key=self._api_key)


_CURRENT: ContextVar[RuntimeAuthBinding | None] = ContextVar("runtime_auth", default=None)


def current_runtime_auth(provider: str) -> RuntimeAuthBinding | None:
    binding = _CURRENT.get()
    if binding is not None and binding.provider != provider:
        raise RuntimeAuthUnavailable("runtime_auth_binding_mismatch")
    return binding


@contextmanager
def activate_runtime_auth(binding: RuntimeAuthBinding):
    """Activate across client construction AND async iteration; resets on exit."""
    if not isinstance(binding, RuntimeAuthBinding):
        raise RuntimeAuthUnavailable("runtime_auth_binding_missing")
    token = _CURRENT.set(binding)
    try:
        yield binding
    finally:
        _CURRENT.reset(token)


def capture_runtime_auth(provider: str, *, store=None, token_store=None) -> RuntimeAuthBinding:
    """Capture one credential row (or genuine env default), before scheduling.

    API keys are snapshotted. OAuth keeps the original credential ID and its
    controlled token store, allowing that credential's normal locked refresh.
    This helper does not read OAuth tokens or refresh/contact a provider.
    """
    existing = current_runtime_auth(provider)
    if existing is not None:
        return existing
    if provider not in ("openai", "anthropic"):
        raise RuntimeAuthUnavailable("runtime_auth_unavailable")
    try:
        store = store if store is not None else CredentialStore()
        active = next((c for c in store.list(provider) if c.active), None)
        if active is None:
            key = os.environ.get("OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY")
            return RuntimeAuthBinding(provider, "env_fallback", "api_key", _api_key=key)
        if active.provider != provider:
            raise RuntimeAuthUnavailable("runtime_auth_unavailable")
        cid = f"local:{active.id}"
        if active.auth_type == "api_key" and active.secret:
            return RuntimeAuthBinding(provider, "db_api_key", "api_key", cid, active.secret)
        oauth = "chatgpt_oauth" if provider == "openai" else "claude_code_oauth"
        if active.auth_type == oauth:
            if token_store is None:
                from src.auth_drivers.token_store import get_token_store

                token_store = get_token_store()
            return RuntimeAuthBinding(provider, "oauth_driver_unwired", oauth, cid, token_store=token_store)
    except Exception:
        raise RuntimeAuthUnavailable("runtime_auth_unavailable") from None
    raise RuntimeAuthUnavailable("runtime_auth_unavailable")


def capture_child_runtime_auth(provider: str, *, store=None, token_store=None) -> RuntimeAuthBinding:
    """Explicit delegation boundary; same-provider children inherit parent auth.

    Only intentional cross-provider children capture another selection. The
    parent's context is restored even if capture fails; normal lookup is strict.
    """
    parent = _CURRENT.get()
    if parent is None or parent.provider == provider:
        return capture_runtime_auth(provider, store=store, token_store=token_store)
    token = _CURRENT.set(None)
    try:
        return capture_runtime_auth(provider, store=store, token_store=token_store)
    finally:
        _CURRENT.reset(token)
