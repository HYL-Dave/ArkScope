"""Driver factory — S1 piece-3 (SKELETON).

`build_driver(provider, auth_mode, credential, token_store=None)` resolves the
concrete driver for a (provider, auth_mode). In this slice every mode returns an
inert `NotImplementedDriver` that carries identity + the injected token store but
raises `NotImplementedError` (naming the gating slice) when actually called:

- api_key / api_key_pool  → built for real in S2 (standard drivers, parity).
- chatgpt_oauth           → S3, gated on probe P2 (ChatGPT-backend compatibility).
- claude_code_oauth       → S4, gated on probe P3 (Claude Agent SDK / claude -p).

Unknown provider / auth_mode → explicit ValueError. NOT wired to the main agent
loop, no Settings UI, no live provider calls. Design: LLM_AUTH_DRIVER_PLAN.md §7.3.
"""

from __future__ import annotations

from typing import Any, Optional

from .protocol import LLMRequest, LLMResponse

_PROVIDERS = frozenset({"openai", "anthropic"})
# auth_mode → the slice that builds the real driver + the message hint.
_MODE_SLICE = {
    "api_key": "S2 (standard api_key drivers, parity)",
    "api_key_pool": "S2 (standard api_key drivers, parity)",
    "chatgpt_oauth": "S3 — requires probe P2 (ChatGPT-backend compatibility)",
    "claude_code_oauth": "S4 — requires probe P3 (Claude Agent SDK / claude -p)",
}


class NotImplementedDriver:
    """Inert placeholder conforming to the AuthDriver contract. Carries identity +
    token store; every operation raises NotImplementedError naming its slice."""

    def __init__(self, *, provider: str, auth_mode: str, credential: Any = None, token_store: Any = None):
        self.provider = provider
        self.auth_mode = auth_mode
        self.credential = credential
        self.token_store = token_store

    def _todo(self) -> NotImplementedError:
        return NotImplementedError(
            f"auth driver for ({self.provider}, {self.auth_mode}) is not built yet — "
            f"see {_MODE_SLICE[self.auth_mode]}."
        )

    @property
    def is_authenticated(self) -> bool:
        return False

    async def authenticate(self) -> None:
        raise self._todo()

    async def refresh_if_needed(self) -> None:
        raise self._todo()

    async def call_llm(self, request: LLMRequest) -> LLMResponse:
        raise self._todo()

    def stream_llm(self, request: LLMRequest):
        raise self._todo()

    async def get_quota_status(self) -> dict[str, Any]:
        raise self._todo()

    async def logout(self) -> None:
        raise self._todo()


def build_driver(
    *,
    provider: str,
    auth_mode: str,
    credential: Any = None,
    token_store: Optional[Any] = None,
) -> NotImplementedDriver:
    """Resolve the driver for a (provider, auth_mode). Skeleton: returns an inert
    placeholder; unknown provider/mode raise ValueError (never silently coerced)."""
    if provider not in _PROVIDERS:
        raise ValueError(f"unknown provider: {provider!r} (expected one of {sorted(_PROVIDERS)})")
    if auth_mode not in _MODE_SLICE:
        raise ValueError(f"unknown auth_mode: {auth_mode!r} (expected one of {sorted(_MODE_SLICE)})")
    return NotImplementedDriver(
        provider=provider, auth_mode=auth_mode, credential=credential, token_store=token_store,
    )
