import asyncio
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, ToolUseBlock

from src.auth_drivers.lifecycle_web_models import ModelCall, WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.security_lifecycle_web_contract import RunControl, validate_selection


@pytest.fixture
def anyio_backend():
    return "asyncio"


SCHEMA = {"type": "object", "properties": {"sources": {"type": "array", "items": {"type": "string"}}},
          "required": ["sources"], "additionalProperties": False}
OUTPUT = {"sources": ["https://ir.example.com/notice"]}


def _request(**changes):
    selection = validate_selection("anthropic", "claude_code_oauth", "claude-opus-5", "local:7")
    request = ModelCall(selection, "search-1", "search", "Investigate only public Issuer Old Inc.",
                        SCHEMA, "high", None, 2, 5.0)
    return replace(request, **changes)


def _result(session, **changes):
    return ResultMessage(**{
        "subtype": "success", "duration_ms": 100, "duration_api_ms": 50, "is_error": False,
        "num_turns": 2, "session_id": session, "stop_reason": "end_turn", "terminal_reason": "completed",
        "structured_output": OUTPUT, "usage": {"input_tokens": 100, "output_tokens": 50},
        "model_usage": {"claude-opus-5": {"inputTokens": 100, "outputTokens": 50}}, **changes,
    })


class Client:
    def __init__(self, options, *, init=None, result=None, before_result=None, omit_hook=False):
        self.options = options
        self.init_changes = init or {}
        self.result_changes = result or {}
        self.before_result = before_result
        self.omit_hook = omit_hook
        self.connected = self.closed = False
        self.queries = []
        self.interrupts = 0
        self.interrupted = asyncio.Event()
        self.hook_output = None
        self._transport = None

    async def connect(self):
        self.connected = True

    async def query(self, prompt, session_id):
        self.queries.append((prompt, session_id))

    async def interrupt(self):
        self.interrupts += 1
        self.interrupted.set()

    async def disconnect(self):
        self.closed = True

    async def receive_response(self):
        session = self.options.session_id
        yield SystemMessage(subtype="init", data={
            "session_id": session, "apiKeySource": "none", "model": "claude-opus-5",
            "tools": list(self.options.tools) + (["StructuredOutput"] if self.options.output_format else []), "mcp_servers": [],
            **self.init_changes,
        })
        if "WebSearch" in self.options.tools:
            if not self.omit_hook:
                self.hook_output = await self.options.hooks["PreToolUse"][0].hooks[0]({
                    "hook_event_name": "PreToolUse", "session_id": session,
                    "tool_name": "WebSearch", "tool_input": {"query": "Issuer Old Inc listing notice"},
                    "tool_use_id": "web-1",
                }, "web-1", {})
            yield AssistantMessage(content=[ToolUseBlock(id="web-1", name="WebSearch",
                                                         input={"query": "Issuer Old Inc listing notice"})], model="claude-opus-5")
        if self.before_result is not None:
            async for item in self.before_result(self):
                yield item
            return
        response = {} if self.options.output_format else {"structured_output": None, "result": json.dumps(OUTPUT)}
        yield _result(session, **{**response, **self.result_changes})


def _setup(monkeypatch, **changes):
    from src.auth_drivers import lifecycle_web_claude as mod

    clients = []
    monkeypatch.setattr(mod, "require_reviewed_claude_agent_runtime",
                        lambda: SimpleNamespace(cli_path=Path("/reviewed/bundled/claude")))

    def factory(options):
        client = Client(options, **changes)
        clients.append(client)
        return client

    monkeypatch.setattr(mod, "_client", factory)
    return mod, clients


@pytest.mark.anyio
async def test_claude_oauth_web_uses_exact_bundled_scope_and_subscription_witness(monkeypatch):
    mod, clients = _setup(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-key")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "ambient-token")
    request = _request()
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    control = RunControl(selection=request.selection, max_model_requests=2)
    reply = await mod.call_claude_web(request, credential, control)
    client = clients[0]
    options = client.options
    assert reply.output == OUTPUT and control.all_requests_terminal
    assert options.tools == ["WebSearch"] and options.allowed_tools == ["WebSearch"]
    assert {"Bash", "Read", "Write", "Edit", "WebFetch", "Task", "Skill"}.issubset(options.disallowed_tools)
    assert "WebSearch" not in options.disallowed_tools
    assert options.permission_mode == "dontAsk" and options.strict_mcp_config is True
    assert options.setting_sources == [] and options.mcp_servers == {}
    assert options.cli_path == "/reviewed/bundled/claude"
    assert options.env["CLAUDE_CODE_OAUTH_TOKEN"] == "selected-token"
    assert options.env.get("ANTHROPIC_API_KEY", "") == ""
    assert options.env["CLAUDE_CODE_MAX_RETRIES"] == "0"
    assert options.env["DISABLE_AUTO_COMPACT"] == "1"
    assert options.model == "claude-opus-5" and options.effort == "high" and options.fallback_model is None
    assert options.output_format == {"type": "json_schema", "schema": SCHEMA}
    assert options.max_turns == 4
    assert not Path(options.cwd).exists() and not Path(options.env["CLAUDE_CONFIG_DIR"]).exists()
    assert client.closed and len(client.queries) == 1
    assert client.hook_output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert control.observed_web_actions["search"] == 1


@pytest.mark.anyio
async def test_claude_analysis_has_no_web_or_filesystem_tools(monkeypatch):
    mod, clients = _setup(monkeypatch)
    request = _request(phase="analysis", call_id="analysis-1")
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    control = RunControl(selection=request.selection, max_model_requests=1)
    assert (await mod.call_claude_web(request, credential, control)).output == OUTPUT
    assert clients[0].options.tools == [] and "WebSearch" in clients[0].options.disallowed_tools
    assert clients[0].options.max_turns == 2
    assert control.observed_web_actions["search"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["search", "analysis"])
async def test_claude_web_pins_internal_helper_models_to_exact_selected_model(monkeypatch, phase):
    monkeypatch.setenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "ambient-helper-model")
    monkeypatch.setenv("ANTHROPIC_SMALL_FAST_MODEL", "ambient-legacy-helper")
    mod, clients = _setup(monkeypatch)
    request = _request(phase=phase, call_id=phase + "-1")
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    control = RunControl(selection=request.selection, max_model_requests=2)
    await mod.call_claude_web(request, credential, control)
    environment = clients[0].options.env
    assert environment["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == request.selection.model
    assert environment["ANTHROPIC_SMALL_FAST_MODEL"] == request.selection.model
    assert clients[0].options.fallback_model is None


@pytest.mark.anyio
@pytest.mark.parametrize("result,code", [
    ({"model_usage": {"claude-opus-5": {}, "claude-haiku-4-5-20251001": {}}}, "execution_identity_changed"),
    ({"model_usage": []}, "model_usage_invalid"),
    ({"num_turns": 100}, "model_result_incomplete"),
    ({"permission_denials": [{"tool_name": "Bash"}]}, "unexpected_tool_activity"),
])
async def test_claude_owned_completed_result_rejection_does_not_erase_remote_terminal(monkeypatch, result, code):
    mod, clients = _setup(monkeypatch, result=result)
    request = _request()
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    control = RunControl(selection=request.selection, max_model_requests=2)
    with pytest.raises(WebModelError, match=code):
        await mod.call_claude_web(request, credential, control)
    assert control.terminal_statuses == {"search-1": "completed"}
    assert control.all_requests_terminal
    with pytest.raises(ValueError, match="stop_requested"):
        control.reserve_model_request("analysis-1")
    assert clients[0].closed and control.model_requests == 1


@pytest.mark.anyio
@pytest.mark.parametrize("result", [{"session_id": "foreign"}, {"terminal_reason": None}])
async def test_claude_unowned_or_absent_terminal_still_leaves_remote_outcome_unknown(monkeypatch, result):
    mod, clients = _setup(monkeypatch, result=result)
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    with pytest.raises(WebModelError):
        await mod.call_claude_web(request, credential, control)
    assert control.terminal_statuses == {}
    assert control.stop_state == "remote_outcome_unknown"
    assert clients[0].closed and control.model_requests == 1


def test_claude_mixed_model_result_is_durable_failure_without_analysis_or_fallback(monkeypatch, tmp_path):
    from src.security_lifecycle_web_pipeline import investigate
    from tests.test_lifecycle_web_controller import controller, launch, wait_done

    mod, clients = _setup(monkeypatch, result={
        "model_usage": {"claude-opus-5": {}, "claude-haiku-4-5-20251001": {}}})
    selected = _request().selection
    service, store, loads = controller(tmp_path, runner=investigate,
        loader=lambda selected: WebCredential(selected, token_record=StoredTokenRecord("selected-token")))
    try:
        run = launch(service, selected=selected)
        result = wait_done(service, run["run_id"])
        assert result["status"] == "failed"
        assert result["failure_code"] == "execution_identity_changed"
        assert result["finding"] is None and result["model_submissions"] == 1
        calls = store.read(run["run_id"])["calls"]
        assert set(calls) == {"search-1"} and calls["search-1"]["terminal"] == "completed"
        assert len(clients) == 1 and len(loads) == 1
    finally:
        service.close()


@pytest.mark.anyio
@pytest.mark.parametrize("init", [
    {"apiKeySource": None}, {"apiKeySource": "ANTHROPIC_API_KEY"},
    {"model": "claude-sonnet-5"}, {"session_id": "foreign"},
    {"tools": ["WebSearch", "Bash"]}, {"mcp_servers": [{"name": "foreign"}]},
])
async def test_claude_web_rejects_changed_init_and_never_falls_back(monkeypatch, init):
    mod, clients = _setup(monkeypatch, init=init)
    request = _request()
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    control = RunControl(selection=request.selection, max_model_requests=2)
    with pytest.raises(WebModelError):
        await mod.call_claude_web(request, credential, control)
    assert len(clients) == 1 and clients[0].closed and len(clients[0].queries) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("result,code", [
    ({"session_id": "foreign"}, "execution_identity_changed"),
    ({"terminal_reason": "max_turns", "is_error": True}, "model_result_incomplete"),
    ({"terminal_reason": None}, "model_result_incomplete"),
    ({"model_usage": {"claude-sonnet-5": {}}}, "execution_identity_changed"),
    ({"structured_output": {"sources": [], "write_profile": True}}, "model_output_invalid"),
])
async def test_claude_web_requires_owned_terminal_and_exact_output(monkeypatch, result, code):
    mod, clients = _setup(monkeypatch, result=result)
    request = _request()
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    control = RunControl(selection=request.selection, max_model_requests=2)
    with pytest.raises(WebModelError, match=code):
        await mod.call_claude_web(request, credential, control)
    assert clients[0].closed and control.model_requests == 1


@pytest.mark.anyio
async def test_claude_observed_web_call_without_pretool_reservation_is_rejected(monkeypatch):
    mod, clients = _setup(monkeypatch, omit_hook=True)
    request = _request()
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    control = RunControl(selection=request.selection, max_model_requests=2)
    with pytest.raises(WebModelError, match="tool_admission_missing"):
        await mod.call_claude_web(request, credential, control)
    assert clients[0].closed


@pytest.mark.anyio
async def test_claude_pretool_gate_denies_files_subagents_and_budget_excess():
    from src.auth_drivers.lifecycle_web_claude import WebToolGate

    request = _request(max_search_uses=1)
    for forbidden in ("Bash", "Read", "WebFetch", "Task", "Skill", "mcp__foreign__read"):
        control = RunControl(selection=request.selection, max_model_requests=1)
        gate = WebToolGate(request, control, "session-1")
        result = await gate.pre_tool({"hook_event_name": "PreToolUse", "session_id": "session-1",
                                     "tool_name": forbidden, "tool_input": {}, "tool_use_id": "bad"}, "bad", {})
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert gate.failure == "unexpected_tool_activity"
    control = RunControl(selection=request.selection, max_model_requests=1)
    gate = WebToolGate(request, control, "session-1")
    args = {"hook_event_name": "PreToolUse", "session_id": "session-1", "tool_name": "WebSearch",
            "tool_input": {"query": "Issuer Old Inc listing"}, "tool_use_id": "web-1"}
    assert (await gate.pre_tool(args, "web-1", {}))["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert (await gate.pre_tool(args, "web-1", {}))["hookSpecificOutput"]["permissionDecision"] == "allow"
    args["tool_use_id"] = "web-2"
    assert (await gate.pre_tool(args, "web-2", {}))["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert gate.failure == "search_budget_exhausted"
    assert gate.search_reservations == {"web-1"}


@pytest.mark.anyio
@pytest.mark.parametrize("terminal", [True, False])
async def test_claude_interrupt_ack_and_local_cleanup_are_not_remote_cancellation(monkeypatch, terminal):
    ready = asyncio.Event()

    async def hold(client):
        ready.set()
        await client.interrupted.wait()
        if terminal:
            yield _result(client.options.session_id, terminal_reason="aborted_streaming", structured_output=None)
        else:
            await asyncio.Event().wait()

    mod, clients = _setup(monkeypatch, before_result=hold)
    monkeypatch.setattr(mod, "_STOP_GRACE_SECONDS", 0.1)
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    task = asyncio.create_task(mod.call_claude_web(request, credential, control))
    await asyncio.wait_for(ready.wait(), 1)
    control.request_stop()
    with pytest.raises(WebModelError, match="stop_requested"):
        await asyncio.wait_for(task, 1)
    assert clients[0].interrupts == 1 and clients[0].closed
    assert control.stop_state == ("cancelled" if terminal else "remote_outcome_unknown")


@pytest.mark.anyio
@pytest.mark.parametrize("status,session,code", [
    ("allowed", None, None), ("allowed_warning", None, None),
    ("rejected", None, "provider_rate_limited"),
    ("allowed", "foreign-session", "execution_identity_changed"),
    ("unknown", None, "protocol_incompatible"),
])
async def test_claude_web_handles_owned_rate_limit_events(monkeypatch, status, session, code):
    from claude_agent_sdk import RateLimitEvent, RateLimitInfo

    async def events(client):
        yield RateLimitEvent(rate_limit_info=RateLimitInfo(status=status), uuid="limit-1",
                             session_id=session or client.options.session_id)
        yield _result(client.options.session_id)

    mod, clients = _setup(monkeypatch, before_result=events)
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    if code is None:
        assert (await mod.call_claude_web(request, credential, control)).output == OUTPUT
    else:
        with pytest.raises(WebModelError, match=code):
            await mod.call_claude_web(request, credential, control)
    assert clients[0].closed and control.model_requests == 1
