"""Standard api_key drivers — S2 (parity surface + client accessor).

OpenAIApiKeyDriver / AnthropicApiKeyDriver fold the EXISTING api_key behavior into
the AuthDriver contract:

- discover_models() / test() DELEGATE to the proven model_credentials functions →
  parity by construction (the driver returns exactly what Settings gets today).
- client() returns a configured SDK client (the STANDARD provider host — never the
  ChatGPT-OAuth backend). This is what the S5 wire-in consumes.
- call_llm() / stream_llm() are gated to S5 — ArkScope's main loop consumes the
  client (plan §11: "a driver wraps client construction only"), not these
  Novelloom-style primitives, so building them now would be unconsumed.

api keys have no OAuth lifecycle: authenticate() just checks presence,
refresh_if_needed() is a no-op, get_quota_status() is honest UNKNOWN. No live LLM
here; tests mock the SDK / the delegated functions. Design: LLM_AUTH_DRIVER_PLAN.md
§3 (A row) / §4.
"""

from __future__ import annotations

from typing import Any, Optional

from src import model_credentials as _mc

from .protocol import LLMRequest, LLMResponse

_S5 = "call_llm/stream_llm are gated to S5 wire-in (the main loop consumes client(), not these)"


class MissingCredentialError(RuntimeError):
    """No usable API key for this driver."""


class _ApiKeyDriver:
    """Shared api_key behavior; subclasses set provider + build the SDK client."""

    provider: str = ""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        auth_mode: str = "api_key",
        credential_id: Optional[str] = None,
        store: Any = None,
        client: Any = None,
    ):
        # api_key_pool collapses to the same driver behavior, but we remember the
        # mode we were built for so identity is honest (pool = env-compat concept).
        self.auth_mode = auth_mode
        self._api_key = api_key
        self._credential_id = credential_id
        self._store = store
        self._client = client
        self._sync_client = None

    # --- auth state ------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return self._client is not None or bool(self._api_key) or bool(self._resolve_secret())

    async def authenticate(self) -> None:
        if not self.is_authenticated:
            raise MissingCredentialError(f"no API key configured for {self.provider}")

    async def refresh_if_needed(self) -> None:  # api keys do not refresh
        return None

    async def logout(self) -> None:
        # INSTANCE-LOCAL: clears this driver's cached key/client only. It does NOT
        # delete the stored credential — a store-backed driver re-resolves and
        # stays authenticated. Credential deletion is a CredentialStore concern.
        self._api_key = None
        self._client = None

    async def get_quota_status(self) -> dict[str, Any]:
        # Honest UNKNOWN — an API key has no subscription-remaining probe either.
        return {"provider": self.provider, "auth_mode": self.auth_mode, "status": "unknown"}

    # --- model discovery / test → DELEGATE (parity) ----------------------
    # Synchronous delegation (NOT asyncio.to_thread): discover/test are not a hot
    # path and the goal here is Settings parity. Revisit threadpool offloading at
    # S5 if/when these run on the async server request path.
    async def discover_models(self):
        return _mc.discover_models(self.provider, self._credential_id, self._store)

    async def test(self, model: Optional[str] = None, effort: str = "default"):
        model = model or _default_model(self.provider)
        return _mc.test_model(self.provider, model, effort, self._credential_id, self._store)

    # --- client accessor (STANDARD host) — consumed by S5 ----------------
    def client(self) -> Any:
        if self._client is None:
            key = self._api_key or self._resolve_secret()
            if not key:
                raise MissingCredentialError(f"no API key configured for {self.provider}")
            self._client = self._make_client(key)
        return self._client

    def _resolve_secret(self) -> Optional[str]:
        if not self._credential_id:
            return None
        try:
            r = _mc._resolve_api_credential(self.provider, self._credential_id, self._store)
        except Exception:  # noqa: BLE001 — resolution is best-effort for is_authenticated
            return None
        return r.secret if r else None

    def client_sync(self) -> Any:
        """A SYNCHRONOUS SDK client (STANDARD host). The live Anthropic call
        sites construct a sync ``Anthropic()`` (not ``AsyncAnthropic``), so the
        wire-in needs a sync client from the driver — ``client()`` returns async."""
        if self._sync_client is None:
            key = self._api_key or self._resolve_secret()
            if not key:
                raise MissingCredentialError(f"no API key configured for {self.provider}")
            self._sync_client = self._make_sync_client(key)
        return self._sync_client

    def _make_client(self, api_key: str) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def _make_sync_client(self, api_key: str) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    # --- LLM-call primitives gated to S5 ---------------------------------
    async def call_llm(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError(_S5)

    def stream_llm(self, request: LLMRequest):
        raise NotImplementedError(_S5)


class OpenAIApiKeyDriver(_ApiKeyDriver):
    provider = "openai"

    def _make_client(self, api_key: str) -> Any:
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=api_key)  # default base_url = api.openai.com (STANDARD)

    def _make_sync_client(self, api_key: str) -> Any:
        from openai import OpenAI

        return OpenAI(api_key=api_key)


class AnthropicApiKeyDriver(_ApiKeyDriver):
    provider = "anthropic"

    def _make_client(self, api_key: str) -> Any:
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=api_key)  # default base_url = api.anthropic.com

    def _make_sync_client(self, api_key: str) -> Any:
        from anthropic import Anthropic

        return Anthropic(api_key=api_key)  # default base_url = api.anthropic.com


def _default_model(provider: str) -> str:
    """A sensible default model for test() when none is given (first catalog id)."""
    from src.model_routing import MODEL_CATALOG

    return next((m.id for m in MODEL_CATALOG if m.provider == provider), "")
