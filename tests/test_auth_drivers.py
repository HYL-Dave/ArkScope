"""S0 — AuthDriver contract (pure interface; no production consumer).

Design: docs/design/LLM_AUTH_DRIVER_PLAN.md §4. Borrows Novelloom's AuthDriver
Protocol FORM; ArkScope adaptation = stream_llm yields the EXISTING AgentEvent
vocabulary (reused, not duplicated) so the C-2 Research surface consumes driver
output unchanged. Nothing wires this in yet (S5 is a separate plan).
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from src.agents.shared.events import AgentEvent, EventType
from src.auth_drivers import (
    AuthDriver,
    DiscoveredModel,
    LLMRequest,
    LLMResponse,
    ModelDiscoveryResult,
    ModelTestResult,
    ResearchProviderDriver,
    TokenUsage,
)


# --- DTO models (Pydantic v2, extra=forbid) --------------------------------
def test_llm_request_defaults():
    r = LLMRequest(model="gpt-5.4")
    assert r.instructions is None and r.max_output_tokens is None
    assert r.input_messages == [] and r.tools == [] and r.response_format is None


def test_llm_request_rejects_unknown_field():
    with pytest.raises(ValidationError):
        LLMRequest(model="gpt-5.4", bogus=1)  # extra=forbid


def test_llm_response_defaults_have_token_usage():
    resp = LLMResponse()
    assert resp.text == "" and resp.tool_calls == []
    assert isinstance(resp.usage, TokenUsage) and resp.usage.total_tokens == 0


def test_token_usage_rejects_unknown_field():
    with pytest.raises(ValidationError):
        TokenUsage(input_tokens=1, nope=2)


def test_default_factories_are_not_shared():
    a, b = LLMRequest(model="m"), LLMRequest(model="m")
    a.tools.append({"x": 1})
    assert b.tools == []  # independent default lists (not a shared mutable)


# --- a reference stub that satisfies the contract --------------------------
class _StubDriver:
    provider = "openai"
    auth_mode = "api_key"

    @property
    def is_authenticated(self) -> bool:
        return True

    async def authenticate(self) -> None: ...
    async def refresh_if_needed(self) -> None: ...

    async def call_llm(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="ok", usage=TokenUsage(total_tokens=1))

    async def stream_llm(self, request: LLMRequest):  # async generator → yields AgentEvent
        yield AgentEvent(EventType.done, {"answer": "ok", "tools_used": [], "provider": "openai", "model": "m", "token_usage": {}})

    async def get_quota_status(self) -> dict:
        return {"status": "unknown"}  # honest UNKNOWN (plan §4.2.4)

    async def logout(self) -> None: ...


class _ResearchStub(_StubDriver):
    # discover_models / test reuse the existing model_credentials result DTOs
    # (not weaker parallel shapes) so Settings/API need no conversion layer.
    async def discover_models(self) -> ModelDiscoveryResult:
        return ModelDiscoveryResult(
            provider="openai", credential_id="local:1", status="ok",
            models=[DiscoveredModel(id="gpt-5.4", provider="openai", label="GPT-5.4", source="seed")],
        )

    async def test(self) -> ModelTestResult:
        return ModelTestResult(provider="openai", credential_id="local:1", model="gpt-5.4", effort="medium", status="ok")


class _Incomplete:
    provider = "openai"
    auth_mode = "api_key"
    # deliberately missing the methods


def test_stub_conforms_to_authdriver():
    assert isinstance(_StubDriver(), AuthDriver)  # @runtime_checkable, structural


def test_research_stub_conforms_to_both():
    s = _ResearchStub()
    assert isinstance(s, AuthDriver)
    assert isinstance(s, ResearchProviderDriver)


def test_incomplete_is_not_an_authdriver():
    assert not isinstance(_Incomplete(), AuthDriver)
    assert not isinstance(_Incomplete(), ResearchProviderDriver)


# --- the load-bearing adaptation: stream yields the CANONICAL AgentEvent ----
def test_stream_llm_yields_existing_agentevent_vocab():
    async def drain():
        return [e async for e in _StubDriver().stream_llm(LLMRequest(model="m"))]

    events = asyncio.run(drain())  # NOTE: stream_llm is NOT awaited — it's an async gen
    assert len(events) == 1
    assert isinstance(events[0], AgentEvent) and events[0].type == EventType.done


def test_contract_reuses_canonical_event_vocab_not_a_parallel_type():
    # S0 must NOT invent a parallel stream-event type; it reuses the 7-value
    # EventType so the C-2 reducer/query.py keep working unchanged.
    assert {e.value for e in EventType} == {
        "thinking", "thinking_content", "text", "tool_start", "tool_end", "error", "done",
    }


# --- availability/capability is PER auth_mode, never assumed shared ----------
# (api_key and OAuth expose different model sets; a driver instance IS one
# (provider, auth_mode), so its discovery/test result is auth-mode-specific.)
class _ApiKeyStub(_StubDriver):
    auth_mode = "api_key"

    async def discover_models(self) -> ModelDiscoveryResult:
        return ModelDiscoveryResult(
            provider="openai", credential_id="local:1", status="ok",
            models=[DiscoveredModel(id="gpt-4o", provider="openai", label="GPT-4o", source="provider_api")],
        )

    async def test(self) -> ModelTestResult:
        return ModelTestResult(provider="openai", credential_id="local:1", model="gpt-4o", effort="none", status="ok")


class _OAuthStub(_StubDriver):
    auth_mode = "chatgpt_oauth"

    async def discover_models(self) -> ModelDiscoveryResult:
        return ModelDiscoveryResult(
            provider="openai", credential_id="local:2", status="ok",
            models=[DiscoveredModel(id="gpt-5.4", provider="openai", label="GPT-5.4 (codex backend)", source="provider_api")],
        )

    async def test(self) -> ModelTestResult:
        return ModelTestResult(provider="openai", credential_id="local:2", model="gpt-5.4", effort="none", status="ok")


def test_discovery_and_test_are_per_auth_mode_not_shared():
    a = asyncio.run(_ApiKeyStub().discover_models())
    o = asyncio.run(_OAuthStub().discover_models())
    # distinct credential rows → distinct results; the available model sets differ
    assert a.credential_id != o.credential_id
    assert {m.id for m in a.models} != {m.id for m in o.models}
    # both still conform to the research-driver contract
    assert isinstance(_ApiKeyStub(), ResearchProviderDriver)
    assert isinstance(_OAuthStub(), ResearchProviderDriver)
