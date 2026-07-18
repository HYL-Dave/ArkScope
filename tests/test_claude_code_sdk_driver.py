"""Slice 7B-4 — tests for AnthropicClaudeCodeSdkDriver (SDK-backed, subscription).

NO LIVE CALLS. We monkeypatch ``claude_agent_sdk.query`` with an async generator
that yields canned SDK message objects (the REAL dataclasses), and we use a FAKE
ToolRegistry + FAKE DAL — the real ToolRegistry/DAL would hit PG/network and hang
the sandbox.

Behaviors covered (see the module docstring + BUILD REPORT):
  - happy-path mapping (AssistantMessage/UserMessage/ResultMessage -> events)
  - is_error ResultMessage -> single error terminal
  - EOF without ResultMessage -> synthesized error
  - overall timeout -> error terminal
  - exactly-one-terminal invariant
  - bridge: off-allowlist veto, BaseException catch + token redaction, oversized
    truncation marker, per-tool timeout
  - token handling: options.env carries the token + ANTHROPIC_API_KEY=="" and the
    token never appears in any yielded AgentEvent
  - config: permission_mode=="dontAsk", tools==[], allowed_tools all mcp__ark__,
    setting_sources==[]
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

import pytest

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from src.agents.shared.events import AgentEvent, EventType
from src.auth_drivers import claude_code_sdk_driver as mod
from src.auth_drivers.claude_code_sdk_driver import (
    AnthropicClaudeCodeSdkDriver,
    _RESEARCH_READONLY_TOOLS,
    build_ark_mcp_server,
)
from src.auth_drivers.protocol import LLMRequest


# ---------------------------------------------------------------------------
# Fakes — a token store, a tool registry, and a DAL. NONE touch PG/network.
# ---------------------------------------------------------------------------
TOKEN = "sk-ant-oat01-FAKEoauthTOKENvalue1234567890abcdefABCDEF"


@dataclass
class _FakeRecord:
    access_token: str


class _FakeTokenStore:
    def __init__(self, token: Optional[str] = TOKEN):
        self._token = token
        self.loaded_with: list[dict] = []

    def load(self, *, provider, auth_mode, credential_id):
        self.loaded_with.append(
            {"provider": provider, "auth_mode": auth_mode, "credential_id": credential_id}
        )
        return _FakeRecord(self._token) if self._token else None


@dataclass
class _FakeCredential:
    id: int = 1


@dataclass
class _FakeParam:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: Optional[list] = None


@dataclass
class _FakeToolDef:
    name: str
    description: str
    function: Any
    parameters: list = field(default_factory=list)
    requires_dal: bool = True


class _FakeRegistry:
    """Minimal stand-in for ToolRegistry: only get()/has the tools we register."""

    def __init__(self, tools: dict[str, _FakeToolDef]):
        self._tools = tools

    def get(self, name: str) -> Optional[_FakeToolDef]:
        return self._tools.get(name)


def _full_fake_registry(handler_overrides: Optional[dict] = None) -> _FakeRegistry:
    """A registry that has EVERY allow-listed tool (so build-time fail-fast passes).

    Each handler echoes its kwargs unless overridden.
    """
    overrides = handler_overrides or {}
    tools = {}
    for name in _RESEARCH_READONLY_TOOLS:
        fn = overrides.get(name)
        if fn is None:
            def fn(dal, _n=name, **kwargs):  # default: small echo
                return {"tool": _n, "args": kwargs, "ok": True}
        tools[name] = _FakeToolDef(
            name=name,
            description=f"{name} (fake)",
            function=fn,
            parameters=[_FakeParam(name="ticker")],
        )
    return _FakeRegistry(tools)


class _FakeDAL:
    pass


def _make_driver(
    *,
    token: Optional[str] = TOKEN,
    registry: Optional[_FakeRegistry] = None,
    max_turns: int = 60,
    timeout_s: float = 180.0,
    per_tool_timeout_s: float = 45.0,
) -> AnthropicClaudeCodeSdkDriver:
    return AnthropicClaudeCodeSdkDriver(
        credential=_FakeCredential(),
        token_store=_FakeTokenStore(token),
        registry=registry if registry is not None else _full_fake_registry(),
        dal=_FakeDAL(),
        max_turns=max_turns,
        timeout_s=timeout_s,
        per_tool_timeout_s=per_tool_timeout_s,
    )


# ---------------------------------------------------------------------------
# A fake query() — an async generator yielding canned messages. We also CAPTURE
# the options the driver built so config/token assertions can read them.
# ---------------------------------------------------------------------------
def _install_fake_query(monkeypatch, messages: List[Any], capture: dict):
    async def fake_query(*, prompt, options):
        capture["prompt"] = prompt
        capture["options"] = options
        for m in messages:
            await asyncio.sleep(0)
            yield m

    monkeypatch.setattr(mod, "query", fake_query)
    return capture


def _result_msg(*, is_error=False, subtype="success", result="final answer", usage=None, model_usage=None):
    return ResultMessage(
        subtype=subtype,
        duration_ms=10,
        duration_api_ms=8,
        is_error=is_error,
        num_turns=1,
        session_id="s1",
        total_cost_usd=0.0123,
        usage=usage if usage is not None else {"input_tokens": 11, "output_tokens": 7},
        result=result,
        model_usage=model_usage,
    )


async def _collect(driver, request) -> List[AgentEvent]:
    out = []
    async for ev in driver.stream_llm(request):
        out.append(ev)
    return out


_REQ = LLMRequest(
    model="claude-sonnet-4-6",
    instructions="You are a terse research assistant.",
    input_messages=[{"role": "user", "content": "SA feed for AAPL"}],
)


# ===========================================================================
# 1. Happy-path message -> AgentEvent mapping
# ===========================================================================
def test_happy_path_mapping(monkeypatch):
    capture: dict = {}
    msgs = [
        SystemMessage(subtype="init", data={"apiKeySource": "none", "tools": ["mcp__ark__get_sa_feed"]}),
        AssistantMessage(
            content=[ToolUseBlock(id="tu1", name="mcp__ark__get_sa_feed", input={"ticker": "AAPL"})],
            model="claude-sonnet-4-6",
        ),
        UserMessage(
            content=[ToolResultBlock(tool_use_id="tu1", content="3 articles for AAPL", is_error=False)],
        ),
        AssistantMessage(content=[TextBlock(text="Here is the AAPL summary.")], model="claude-sonnet-4-6"),
        _result_msg(),
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))

    kinds = [e.type for e in events]
    assert kinds == [EventType.tool_start, EventType.tool_end, EventType.text, EventType.done]

    start = events[0]
    assert start.data["tool"] == "mcp__ark__get_sa_feed"
    assert start.data["input"] == {"ticker": "AAPL"}

    end = events[1]
    assert end.data["tool"] == "mcp__ark__get_sa_feed"
    assert end.data["summary"].startswith("3 articles for AAPL")
    assert end.data["chars"] == len("3 articles for AAPL")

    txt = events[2]
    assert txt.data["content"] == "Here is the AAPL summary."

    done = events[3]
    assert done.data["answer"] == "final answer"
    assert done.data["provider"] == "anthropic"
    assert done.data["model"] == "claude-sonnet-4-6"
    assert done.data["tools_used"] == ["mcp__ark__get_sa_feed"]
    assert done.data["token_usage"]["input_tokens"] == 11
    assert done.data["token_usage"]["output_tokens"] == 7
    assert done.data["token_usage"]["total_tokens"] == 18
    assert done.data["token_usage"]["cost_usd"] == 0.0123


def test_result_usage_preserves_cache_token_counters(monkeypatch):
    capture: dict = {}
    msgs = [
        _result_msg(usage={
            "input_tokens": 10000,
            "output_tokens": 300,
            "cache_creation_input_tokens": 2048,
            "cache_read_input_tokens": 8192,
        }),
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))

    usage = events[-1].data["token_usage"]
    assert usage["input_tokens"] == 10000
    assert usage["output_tokens"] == 300
    assert usage["total_tokens"] == 10300
    assert usage["cache_creation_tokens"] == 2048
    assert usage["cache_read_tokens"] == 8192


def test_result_model_usage_aggregates_cache_tokens_when_top_level_missing(monkeypatch):
    capture: dict = {}
    msgs = [
        _result_msg(
            usage={},
            model_usage={
                "claude-sonnet-4-6": {
                    "input_tokens": 6000,
                    "output_tokens": 100,
                    "cache_read_input_tokens": 4096,
                },
                "claude-opus-4-8": {
                    "input_tokens": 2000,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 1024,
                },
            },
        ),
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))

    usage = events[-1].data["token_usage"]
    assert usage["input_tokens"] == 8000
    assert usage["output_tokens"] == 150
    assert usage["total_tokens"] == 8150
    assert usage["cache_creation_tokens"] == 1024
    assert usage["cache_read_tokens"] == 4096


# ===========================================================================
# 2. is_error ResultMessage -> single error terminal
# ===========================================================================
def test_is_error_result_single_error_terminal(monkeypatch):
    for subtype, expected_code in (
        ("error", None),
        ("error_max_turns", "tool_limit_reached"),
    ):
        capture: dict = {}
        msgs = [
            SystemMessage(subtype="init", data={"apiKeySource": "none"}),
            _result_msg(is_error=True, subtype=subtype, result="rate limited"),
        ]
        _install_fake_query(monkeypatch, msgs, capture)
        events = asyncio.run(_collect(_make_driver(), _REQ))

        assert len(events) == 1
        assert events[0].type == EventType.error
        assert events[0].data["error"] == "rate limited"
        assert events[0].data["provider"] == "anthropic"
        if expected_code is None:
            assert "code" not in events[0].data
        else:
            assert events[0].data["code"] == expected_code


def test_is_error_true_but_subtype_success_still_error(monkeypatch):
    # GOTCHA from 7A: subtype can be 'success' while is_error is True.
    capture: dict = {}
    msgs = [_result_msg(is_error=True, subtype="success", result="boom")]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))
    assert [e.type for e in events] == [EventType.error]


# ===========================================================================
# 3. EOF without a ResultMessage -> synthesized single error
# ===========================================================================
def test_eof_without_result_synthesizes_error(monkeypatch):
    capture: dict = {}
    msgs = [
        SystemMessage(subtype="init", data={"apiKeySource": "none"}),
        AssistantMessage(content=[TextBlock(text="partial")], model="claude-sonnet-4-6"),
        # no ResultMessage
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))

    assert events[-1].type == EventType.error
    assert "without a result" in events[-1].data["error"]
    # exactly one terminal
    assert sum(1 for e in events if e.type in (EventType.done, EventType.error)) == 1


# ===========================================================================
# 4. Overall timeout -> error terminal
# ===========================================================================
def test_overall_timeout(monkeypatch):
    capture: dict = {}

    async def slow_query(*, prompt, options):
        capture["options"] = options
        await asyncio.sleep(5.0)  # exceeds the tiny timeout below
        yield _result_msg()

    monkeypatch.setattr(mod, "query", slow_query)
    driver = _make_driver(timeout_s=0.05)
    events = asyncio.run(_collect(driver, _REQ))

    assert events[-1].type == EventType.error
    assert "timed out" in events[-1].data["error"]
    assert sum(1 for e in events if e.type in (EventType.done, EventType.error)) == 1


def test_driver_default_max_turns_is_not_hidden_eight():
    assert _make_driver()._max_turns == 60


def test_zero_timeout_disables_overall_timeout(monkeypatch):
    async def slow_but_finishes_query(*, prompt, options):
        await asyncio.sleep(0.01)
        yield _result_msg()

    monkeypatch.setattr(mod, "query", slow_but_finishes_query)
    driver = _make_driver(timeout_s=0)
    events = asyncio.run(_collect(driver, _REQ))

    assert events[-1].type == EventType.done


def test_zero_max_turns_omits_sdk_max_turns(monkeypatch):
    capture: dict = {}
    _install_fake_query(monkeypatch, [_result_msg()], capture)
    req = LLMRequest(
        model="claude-opus-4-8",
        instructions="You are a terse research assistant.",
        input_messages=[{"role": "user", "content": "hard question"}],
    )

    events = asyncio.run(_collect(_make_driver(max_turns=0), req))

    assert events[-1].type == EventType.done
    assert capture["options"].max_turns is None


# ===========================================================================
# 5. SDK exception while streaming -> single error terminal (redacted)
# ===========================================================================
def test_sdk_exception_while_streaming(monkeypatch):
    async def boom_query(*, prompt, options):
        if False:
            yield None  # make it a generator
        raise RuntimeError("connection died token=" + TOKEN)

    monkeypatch.setattr(mod, "query", boom_query)
    events = asyncio.run(_collect(_make_driver(), _REQ))

    assert events[-1].type == EventType.error
    assert TOKEN not in events[-1].data["error"]
    assert sum(1 for e in events if e.type in (EventType.done, EventType.error)) == 1


# ===========================================================================
# 6. Exactly-one-terminal: extra messages after ResultMessage are not emitted
# ===========================================================================
def test_exactly_one_terminal_stops_after_done(monkeypatch):
    capture: dict = {}
    msgs = [
        _result_msg(),
        AssistantMessage(content=[TextBlock(text="late text")], model="m"),  # must be ignored
        _result_msg(),  # second terminal must be ignored
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))
    assert [e.type for e in events] == [EventType.done]


# ===========================================================================
# 7. Config posture: dontAsk, tools=[], allowed_tools mcp__ark__, setting_sources=[]
# ===========================================================================
def test_options_config_posture(monkeypatch):
    capture: dict = {}
    _install_fake_query(monkeypatch, [_result_msg()], capture)
    asyncio.run(_collect(_make_driver(), _REQ))

    opts = capture["options"]
    assert opts.permission_mode == "dontAsk"
    assert opts.tools == []
    assert opts.setting_sources == []
    assert opts.model == "claude-sonnet-4-6"
    assert opts.system_prompt == "You are a terse research assistant."
    # allowed_tools are exactly the mcp__ark__ names for the allowlist
    assert set(opts.allowed_tools) == {"mcp__ark__" + n for n in _RESEARCH_READONLY_TOOLS}
    assert all(t.startswith("mcp__ark__") for t in opts.allowed_tools)


# ===========================================================================
# 8. Token handling: env carries token + ANTHROPIC_API_KEY=="" ; never in events
# ===========================================================================
def test_token_in_env_not_in_events(monkeypatch):
    capture: dict = {}
    # A tool result + answer that try to echo the token; it must never reach events.
    msgs = [
        SystemMessage(subtype="init", data={"apiKeySource": "none"}),
        AssistantMessage(
            content=[ToolUseBlock(id="t1", name="mcp__ark__get_sa_feed", input={"secret": TOKEN})],
            model="m",
        ),
        UserMessage(content=[ToolResultBlock(tool_use_id="t1", content="leak " + TOKEN, is_error=False)]),
        AssistantMessage(content=[TextBlock(text="answer " + TOKEN)], model="m"),
        _result_msg(result="done " + TOKEN),
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))

    opts = capture["options"]
    assert opts.env["CLAUDE_CODE_OAUTH_TOKEN"] == TOKEN
    assert opts.env["ANTHROPIC_API_KEY"] == ""
    assert "CLAUDE_CONFIG_DIR" in opts.env

    # the token must NOT appear in ANY yielded event (args echo redacted; result
    # redacted). NOTE: done.answer is the model's text and is exact-token scrubbed.
    for ev in events:
        blob = repr(ev.data)
        assert TOKEN not in blob, f"token leaked in {ev.type}: {blob[:120]}"


def test_token_never_read_from_credential_secret(monkeypatch):
    # The driver must read the token from token_store, NEVER credential.secret.
    capture: dict = {}
    _install_fake_query(monkeypatch, [_result_msg()], capture)

    class _CredWithSecret:
        id = 1
        secret = "sk-ant-CREDENTIAL-SECRET-must-not-be-used"

    store = _FakeTokenStore(TOKEN)
    driver = AnthropicClaudeCodeSdkDriver(
        credential=_CredWithSecret(),
        token_store=store,
        registry=_full_fake_registry(),
        dal=_FakeDAL(),
    )
    asyncio.run(_collect(driver, _REQ))
    assert capture["options"].env["CLAUDE_CODE_OAUTH_TOKEN"] == TOKEN
    # the credential.secret value must never be the injected token
    assert capture["options"].env["CLAUDE_CODE_OAUTH_TOKEN"] != _CredWithSecret.secret


# ===========================================================================
# 9. apiKeySource guard: a non-"none" apiKeySource aborts with one error
# ===========================================================================
def test_apikeysource_guard_aborts(monkeypatch):
    capture: dict = {}
    msgs = [
        SystemMessage(subtype="init", data={"apiKeySource": "ANTHROPIC_API_KEY"}),
        _result_msg(),  # should never be reached as a done
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))
    assert events[-1].type == EventType.error
    assert "subscription" in events[-1].data["error"].lower()
    assert sum(1 for e in events if e.type in (EventType.done, EventType.error)) == 1


# ===========================================================================
# 10. Pre-flight: no token -> raises on first iteration (MissingCredentialError)
# ===========================================================================
def test_no_token_raises(monkeypatch):
    _install_fake_query(monkeypatch, [_result_msg()], {})
    driver = _make_driver(token=None)
    with pytest.raises(Exception) as ei:
        asyncio.run(_collect(driver, _REQ))
    assert "token" in str(ei.value).lower() or "credential" in str(ei.value).lower()


# ===========================================================================
# BRIDGE TESTS — exercise the SdkMcpTool wrappers directly (no query()).
# ===========================================================================
def _build_server_and_handlers(registry, dal, per_tool_timeout_s=45.0):
    server, sdk_tools = build_ark_mcp_server(
        registry=registry, dal=dal, token=TOKEN, per_tool_timeout_s=per_tool_timeout_s
    )
    handlers = {t.name: t.handler for t in sdk_tools}
    return server, sdk_tools, handlers


def test_bridge_builds_one_tool_per_allowlisted_name():
    _, sdk_tools, _ = _build_server_and_handlers(_full_fake_registry(), _FakeDAL())
    names = {t.name for t in sdk_tools}
    assert names == set(_RESEARCH_READONLY_TOOLS)


def test_current_quote_is_research_readonly_allowlisted():
    from src.auth_drivers.chatgpt_oauth_driver import (
        _RESEARCH_READONLY_TOOLS as openai_tools,
    )

    assert "get_current_quote" in _RESEARCH_READONLY_TOOLS
    assert "get_current_quote" in openai_tools


def test_bridge_fail_fast_on_missing_registry_tool():
    # Drop one allow-listed tool from the registry -> build must raise.
    reg = _full_fake_registry()
    reg._tools.pop(next(iter(_RESEARCH_READONLY_TOOLS)))
    with pytest.raises(Exception):
        build_ark_mcp_server(registry=reg, dal=_FakeDAL(), token=TOKEN)


def test_bridge_happy_invoke_returns_content():
    name = "get_sa_feed"
    _, _, handlers = _build_server_and_handlers(_full_fake_registry(), _FakeDAL())
    out = asyncio.run(handlers[name]({"ticker": "AAPL"}))
    assert "content" in out
    assert out["content"][0]["type"] == "text"
    assert not out.get("is_error")
    assert "AAPL" in out["content"][0]["text"]


def test_bridge_handler_raises_with_token_is_redacted():
    name = "get_ticker_news"

    def raiser(dal, **kwargs):
        raise RuntimeError("downstream error key=" + TOKEN)

    reg = _full_fake_registry({name: raiser})
    _, _, handlers = _build_server_and_handlers(reg, _FakeDAL())
    out = asyncio.run(handlers[name]({"ticker": "X"}))

    assert out["is_error"] is True
    text = out["content"][0]["text"]
    assert TOKEN not in text
    # no 8+-char contiguous substring of the token either
    assert not any(TOKEN[i : i + 8] in text for i in range(0, len(TOKEN) - 7))


def test_bridge_off_allowlist_name_vetoed():
    # The Python-side veto: a wrapper asked to run a non-allowlisted name returns
    # is_error and NEVER calls the handler.
    called = {"hit": False}

    def should_not_run(dal, **kwargs):
        called["hit"] = True
        return {"ran": True}

    # Inject a tool whose registry name is NOT in the allowlist, but route it
    # through the bridge's per-name wrapper builder to assert the veto.
    out = asyncio.run(
        mod._invoke_bridged_tool(
            name="save_report",  # NOT in _RESEARCH_READONLY_TOOLS
            registry=_FakeRegistry({"save_report": _FakeToolDef("save_report", "x", should_not_run)}),
            dal=_FakeDAL(),
            token=TOKEN,
            per_tool_timeout_s=45.0,
            args={},
        )
    )
    assert out["is_error"] is True
    assert called["hit"] is False
    assert "not allowed" in out["content"][0]["text"].lower() or "allowlist" in out["content"][0]["text"].lower()


def test_bridge_oversized_result_truncated_with_marker():
    name = "get_news_brief"
    big = "A" * 50_000

    def huge(dal, **kwargs):
        return {"blob": big}

    reg = _full_fake_registry({name: huge})
    _, _, handlers = _build_server_and_handlers(reg, _FakeDAL())
    out = asyncio.run(handlers[name]({"ticker": "X"}))
    text = out["content"][0]["text"]
    assert len(text) <= mod._BRIDGE_RESULT_BUDGET + 200
    assert "chars dropped" in text  # the truncate_with_marker marker


def test_bridge_per_tool_timeout():
    # An async handler the bridge will await-wrap; asyncio.wait_for can cancel it
    # cleanly (a blocking sync sleep would orphan a thread and stall the suite).
    name = "get_economic_calendar"

    async def slow(dal, **kwargs):
        await asyncio.sleep(5.0)
        return {"ok": True}

    out = asyncio.run(
        mod._invoke_bridged_tool(
            name=name,
            registry=_FakeRegistry({name: _FakeToolDef(name, "x", slow)}),
            dal=_FakeDAL(),
            token=TOKEN,
            per_tool_timeout_s=0.05,
            args={},
        )
    )
    assert out["is_error"] is True
    assert "timed out" in out["content"][0]["text"].lower()


def test_bridge_sk_ant_secret_in_result_is_redacted():
    # OQ-5 STRICT: a non-OAuth secret (sk-ant...) in the FULL model-facing body
    # must be regex-redacted too.
    name = "get_fundamentals_analysis"
    leaked = "sk-ant-api03-" + "a" * 40

    def leaker(dal, **kwargs):
        return {"note": "here is a secret " + leaked}

    reg = _full_fake_registry({name: leaker})
    _, _, handlers = _build_server_and_handlers(reg, _FakeDAL())
    out = asyncio.run(handlers[name]({"ticker": "X"}))
    assert leaked not in out["content"][0]["text"]


# ===========================================================================
# call_llm / discover_models / test / get_quota_status
# ===========================================================================
def test_call_llm_not_implemented():
    with pytest.raises(NotImplementedError):
        asyncio.run(_make_driver().call_llm(_REQ))


def test_discover_models_static_list():
    res = asyncio.run(_make_driver().discover_models())
    assert res.provider == "anthropic"
    assert res.status == "ok"
    assert len(res.models) > 0


def test_test_returns_non_ok_without_live_call():
    res = asyncio.run(_make_driver().test())
    # Honest: NO live call here, so test() must NEVER report a fake "ok".
    assert res.provider == "anthropic"
    assert res.status != "ok"
    assert res.status == "error"
    assert res.warning and "deferred" in res.warning


def test_test_missing_credential_without_token():
    res = asyncio.run(_make_driver(token=None).test())
    assert res.status == "missing_credential"


def test_get_quota_status_unknown():
    res = asyncio.run(_make_driver().get_quota_status())
    assert res["status"] == "unknown"
    assert res["provider"] == "anthropic"


def test_build_options_passes_reasoning_effort_to_claude_sdk(monkeypatch):
    capture: dict = {}
    _install_fake_query(monkeypatch, [_result_msg()], capture)
    req = LLMRequest(
        model="claude-opus-4-8",
        instructions="You are a terse research assistant.",
        input_messages=[{"role": "user", "content": "hard question"}],
        reasoning_effort="max",
    )

    events = asyncio.run(_collect(_make_driver(), req))

    assert events[-1].type == EventType.done
    assert capture["options"].effort == "max"


def test_build_options_omits_default_reasoning_effort(monkeypatch):
    capture: dict = {}
    _install_fake_query(monkeypatch, [_result_msg()], capture)
    req = LLMRequest(
        model="claude-opus-4-8",
        instructions="You are a terse research assistant.",
        input_messages=[{"role": "user", "content": "normal question"}],
        reasoning_effort="default",
    )

    events = asyncio.run(_collect(_make_driver(), req))

    assert events[-1].type == EventType.done
    assert capture["options"].effort is None


def test_implements_research_provider_protocol():
    from src.auth_drivers.protocol import ResearchProviderDriver

    assert isinstance(_make_driver(), ResearchProviderDriver)


# ===========================================================================
# Extra coverage — schema, block-type mappings, and the redaction-vs-prose call.
# ===========================================================================
def test_bridge_input_schema_preserves_optional_args():
    # §4: the JSON-Schema passthrough must NOT mark optional params as required.
    reg = _full_fake_registry()
    name = "get_ticker_news"
    reg._tools[name] = _FakeToolDef(
        name=name,
        description="x",
        function=lambda dal, **kw: {"ok": True},
        parameters=[
            _FakeParam(name="ticker", required=True),
            _FakeParam(name="days", type="integer", required=False),
        ],
    )
    _, sdk_tools, _ = _build_server_and_handlers(reg, _FakeDAL())
    t = next(t for t in sdk_tools if t.name == name)
    schema = t.input_schema
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"ticker", "days"}
    assert schema["required"] == ["ticker"]  # days is NOT required
    assert schema["properties"]["days"]["type"] == "integer"


def test_thinking_block_maps_to_thinking_content(monkeypatch):
    from claude_agent_sdk import ThinkingBlock

    capture: dict = {}
    msgs = [
        AssistantMessage(
            content=[ThinkingBlock(thinking="let me think", signature="sig")],
            model="m",
        ),
        AssistantMessage(content=[TextBlock(text="done thinking")], model="m"),
        _result_msg(),
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))
    kinds = [e.type for e in events]
    assert EventType.thinking_content in kinds
    tc = next(e for e in events if e.type == EventType.thinking_content)
    assert tc.data["thinking"] == "let me think"
    assert "signature" not in tc.data  # signature dropped


def test_tool_end_is_error_flag_is_not_terminal(monkeypatch):
    # A tool_result with is_error=True is NOT a terminal; the run continues to done.
    capture: dict = {}
    msgs = [
        AssistantMessage(
            content=[ToolUseBlock(id="t1", name="mcp__ark__get_ticker_news", input={})], model="m"
        ),
        UserMessage(content=[ToolResultBlock(tool_use_id="t1", content="boom", is_error=True)]),
        _result_msg(),
    ]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))
    end = next(e for e in events if e.type == EventType.tool_end)
    assert end.data["is_error"] is True
    assert events[-1].type == EventType.done  # not terminated by the tool error


def test_done_answer_not_overredacted(monkeypatch):
    # The token-only scrub on model prose must NOT mangle a legitimate base64-ish
    # chart blob in the answer (the deliberate prose-vs-bridge redaction split).
    capture: dict = {}
    chart = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5"  # base64-shaped, benign
    msgs = [_result_msg(result="Chart: " + chart)]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))
    assert events[-1].type == EventType.done
    assert chart in events[-1].data["answer"]  # preserved, not [REDACTED]


def test_streaming_and_ratelimit_events_ignored(monkeypatch):
    from claude_agent_sdk import StreamEvent

    capture: dict = {}
    se = StreamEvent(uuid="u", session_id="s", event={"type": "x"}, parent_tool_use_id=None)
    # RateLimitInfo shape is opaque; building a stand-in is risky, so only assert
    # StreamEvent is ignored (RateLimitEvent shares the same catch-all-ignore policy).
    msgs = [se, AssistantMessage(content=[TextBlock(text="hi")], model="m"), _result_msg()]
    _install_fake_query(monkeypatch, msgs, capture)
    events = asyncio.run(_collect(_make_driver(), _REQ))
    kinds = [e.type for e in events]
    assert kinds == [EventType.text, EventType.done]  # StreamEvent produced nothing


# ===========================================================================
# 12. 7B-6 follow-ups: multi-turn history folding + temp-config-dir cleanup
# ===========================================================================
def test_compose_input_single_user_returns_bare_content():
    assert mod._compose_input([{"role": "user", "content": "SA feed for AAPL"}]) == "SA feed for AAPL"


def test_compose_input_folds_multi_turn_history_and_drops_system():
    msgs = [
        {"role": "system", "content": "you are terse"},
        {"role": "user", "content": "what about NVDA?"},
        {"role": "assistant", "content": "NVDA looks strong"},
        {"role": "user", "content": "and AAPL?"},
    ]
    prompt = mod._compose_input(msgs)
    # every non-system turn is preserved (NOT collapsed to the last — the v1 regression)
    assert "what about NVDA?" in prompt and "NVDA looks strong" in prompt and "and AAPL?" in prompt
    assert "you are terse" not in prompt  # system goes to options.system_prompt, not the prompt
    assert "User:" in prompt and "Assistant:" in prompt  # role-labeled


def test_compose_input_empty_is_empty_string():
    assert mod._compose_input([]) == ""
    assert mod._compose_input([{"role": "system", "content": "x"}]) == ""


def test_stream_removes_temp_config_dir(monkeypatch):
    # The per-call CLAUDE_CONFIG_DIR temp dir must be rmtree'd on stream teardown
    # (else /tmp/ark_claude_cfg_* accumulates). Wrap the real mkdtemp to capture it.
    created = {}
    real_mkdtemp = mod.tempfile.mkdtemp

    def rec_mkdtemp(*a, **k):
        d = real_mkdtemp(*a, **k)
        created["dir"] = d
        return d

    monkeypatch.setattr(mod.tempfile, "mkdtemp", rec_mkdtemp)
    _install_fake_query(monkeypatch, [_result_msg()], {})
    events = asyncio.run(_collect(_make_driver(), _REQ))
    assert events[-1].type is EventType.done
    assert created.get("dir") and not os.path.exists(created["dir"])  # cleaned up


def test_stream_folds_multi_turn_prompt_into_query(monkeypatch):
    # Integration: a multi-turn request reaches query() with BOTH turns in the prompt.
    capture: dict = {}
    _install_fake_query(monkeypatch, [_result_msg()], capture)
    req = LLMRequest(
        model="claude-sonnet-4-6",
        instructions="terse",
        input_messages=[
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "second question"},
        ],
    )
    asyncio.run(_collect(_make_driver(), req))
    assert "first question" in capture["prompt"] and "second question" in capture["prompt"]
