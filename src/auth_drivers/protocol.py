"""LLM Auth Driver contract — Layer S0 (PURE INTERFACE; no production consumer).

Design: docs/design/LLM_AUTH_DRIVER_PLAN.md §4. Borrows Novelloom's AuthDriver
Protocol FORM (provider + auth_mode + driver), adapted for ArkScope.

KEY ADAPTATION: `stream_llm` yields the EXISTING `AgentEvent` vocabulary
(`src.agents.shared.events`) — reused, NOT a parallel "ArkStreamEvent" type — so
the C-2 Research surface (live trace, tool trace, thread persistence) consumes a
driver's stream with zero changes to the reducer / query.py.

Nothing imports or wires these drivers in yet. Wiring (S5) is a SEPARATE plan;
this module is interface + tests only.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from src.agents.shared.events import AgentEvent  # the stream event vocabulary — reused
# Reuse the EXISTING discovery/test result DTOs (not weaker parallel shapes) so
# S1/S2 drivers and the Settings/API layer need no conversion. These are keyed by
# credential_id → each is inherently PER (provider, auth_mode).
from src.model_credentials import DiscoveredModel, ModelDiscoveryResult, ModelTestResult

# Distinct, explicit auth modes (plan §5.1). Do NOT collapse the two OpenAI OAuth
# realities or the Anthropic setup-token path into a generic "oauth".
Provider = Literal["openai", "anthropic"]
AuthMode = Literal["api_key", "api_key_pool", "chatgpt_oauth", "claude_code_oauth"]


class _StrictModel(BaseModel):
    """extra='forbid' so a typo'd field fails loudly rather than silently dropping."""

    model_config = ConfigDict(extra="forbid")


class TokenUsage(_StrictModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class LLMRequest(_StrictModel):
    model: str
    instructions: str | None = None
    input_messages: list[dict] = Field(default_factory=list)
    reasoning_effort: str | None = None
    max_output_tokens: int | None = None
    tools: list[dict] = Field(default_factory=list)
    response_format: dict | None = None


class LLMResponse(_StrictModel):
    text: str = ""
    tool_calls: list[dict] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw_response: Any = None


@runtime_checkable
class AuthDriver(Protocol):
    """Provider/auth-mode-neutral client+strategy. One driver per (provider, auth_mode)."""

    provider: str
    auth_mode: str

    @property
    def is_authenticated(self) -> bool: ...

    async def authenticate(self) -> None: ...

    # Called BEFORE every call_llm/stream_llm; refreshes a rotating OAuth token.
    async def refresh_if_needed(self) -> None: ...

    async def call_llm(self, request: LLMRequest) -> LLMResponse: ...

    # GOTCHA: a sync `def` returning an async generator — do NOT `await` the call;
    # iterate it (`async for`). Yields the canonical AgentEvent vocabulary.
    def stream_llm(self, request: LLMRequest) -> AsyncIterator[AgentEvent]: ...

    # Honest UNKNOWN by default — there is no real subscription-remaining probe
    # (plan §4.2.4). Surface login-state + session tallies, never a fake "X% left".
    async def get_quota_status(self) -> dict[str, Any]: ...

    async def logout(self) -> None: ...


@runtime_checkable
class ResearchProviderDriver(AuthDriver, Protocol):
    """ArkScope's research-surface driver: adds model discovery + a verify test.

    Discovery and test are PER (provider, auth_mode) — a driver instance is one
    auth mode, so its results are auth-mode-specific. NEVER assume parity across
    auth modes: the api_key model/capability set differs from chatgpt_oauth
    (nonstandard ChatGPT-backend list) and from claude_code_oauth. Both methods
    return the canonical model_credentials result DTOs (keyed by credential_id).
    """

    async def discover_models(self) -> ModelDiscoveryResult: ...

    async def test(self) -> ModelTestResult: ...
