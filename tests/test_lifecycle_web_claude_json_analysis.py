import json

import pytest
from claude_agent_sdk import AssistantMessage, SystemMessage, TextBlock, ToolUseBlock

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.security_lifecycle_web_contract import RunControl
from tests.test_lifecycle_web_claude import Client, OUTPUT, SCHEMA, _request, _result, _setup


@pytest.fixture
def anyio_backend():
    return "asyncio"


def setup(monkeypatch, *, result=None, init=None, tool=None):
    mod, _ = _setup(monkeypatch)
    clients = []

    class JSONClient(Client):
        async def receive_response(self):
            session = self.options.session_id
            yield SystemMessage(subtype="init", data={"session_id": session, "apiKeySource": "none",
                "model": "claude-opus-5", "tools": [], "mcp_servers": [], **(init or {})})
            if tool:
                yield AssistantMessage(content=[ToolUseBlock(id="unexpected", name=tool, input={})], model="claude-opus-5")
            yield AssistantMessage(content=[TextBlock(text=json.dumps(OUTPUT))], model="claude-opus-5")
            yield _result(session, **{"num_turns": 1, "structured_output": None,
                                     "result": json.dumps(OUTPUT), **(result or {})})

    def factory(options):
        client = JSONClient(options)
        clients.append(client)
        return client

    monkeypatch.setattr(mod, "_client", factory)
    return mod, clients


async def invoke(mod, *, schema=SCHEMA):
    call = _request(phase="analysis", call_id="analysis-1", output_schema=schema)
    control = RunControl(selection=call.selection, max_model_requests=1)
    credential = WebCredential(call.selection, token_record=StoredTokenRecord("selected-token"))
    return await mod.call_claude_web(call, credential, control), control


@pytest.mark.anyio
async def test_claude_analysis_declares_final_json_without_native_output_tool(monkeypatch):
    mod, clients = setup(monkeypatch)
    reply, control = await invoke(mod)
    assert reply.output == OUTPUT and control.terminal_statuses == {"analysis-1": "completed"}
    options = clients[0].options
    assert options.output_format is None
    assert options.tools == options.allowed_tools == [] and "StructuredOutput" in options.disallowed_tools
    assert options.mcp_servers == {} and options.setting_sources == [] and options.strict_mcp_config is True
    assert options.fallback_model is None and options.max_turns == 2
    assert options.env["CLAUDE_CODE_MAX_RETRIES"] == "0"
    instructions, separator, encoded = options.system_prompt.partition("\nOutput schema:\n")
    assert separator and json.loads(encoded) == SCHEMA
    assert "final response" in instructions and "JSON object" in instructions
    assert "StructuredOutput" not in instructions
    assert clients[0].queries == [(_request().prompt, options.session_id)] and clients[0].closed


@pytest.mark.anyio
@pytest.mark.parametrize("value", [
    None, OUTPUT, "", "null", "[]", "true", "{", json.dumps({"result": OUTPUT}),
    "```json\n" + json.dumps(OUTPUT) + "\n```", json.dumps(OUTPUT) + " explanation",
    json.dumps(OUTPUT) + json.dumps(OUTPUT), '{"sources":[],"sources":["valid"]}',
    '{"sources":[],"number":NaN}', '{"sources":[],"number":Infinity}',
    json.dumps({"sources": [], "write_profile": True}), '{"sources":"wrong shape"}',
])
async def test_claude_analysis_rejects_invalid_final_json_without_repair_or_retry(monkeypatch, value):
    mod, clients = setup(monkeypatch, result={"result": value})
    call = _request(phase="analysis", call_id="analysis-1")
    control = RunControl(selection=call.selection, max_model_requests=1)
    with pytest.raises(WebModelError, match="^model_output_invalid$"):
        await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("selected-token")), control)
    assert control.terminal_statuses == {"analysis-1": "completed"}
    assert len(clients) == 1 and len(clients[0].queries) == 1 and clients[0].closed


@pytest.mark.anyio
@pytest.mark.parametrize("duplicate", [False, True])
async def test_claude_analysis_nested_json_duplicate_keys_are_not_last_value_wins(monkeypatch, duplicate):
    schema = {"type": "object", "properties": {"nested": {"type": "object", "properties": {"value": {"type": "string"}},
        "required": ["value"], "additionalProperties": False}}, "required": ["nested"], "additionalProperties": False}
    value = '{"nested":{"value":"first","value":"last"}}' if duplicate else '{"nested":{"value":"last"}}'
    mod, _ = setup(monkeypatch, result={"result": value})
    if duplicate:
        with pytest.raises(WebModelError, match="^model_output_invalid$"):
            await invoke(mod, schema=schema)
    else:
        reply, _ = await invoke(mod, schema=schema)
        assert reply.output == {"nested": {"value": "last"}}


@pytest.mark.anyio
async def test_claude_analysis_never_chooses_between_native_and_final_json(monkeypatch):
    mod, _ = setup(monkeypatch, result={"structured_output": OUTPUT})
    with pytest.raises(WebModelError, match="^model_output_invalid$"):
        await invoke(mod)


@pytest.mark.anyio
@pytest.mark.parametrize("boundary", ["pretool", "init", "notification"])
async def test_claude_analysis_denies_structured_output_tool_at_every_boundary(monkeypatch, boundary):
    from src.auth_drivers.lifecycle_web_claude import WebToolGate

    call = _request(phase="analysis", call_id="analysis-1")
    if boundary == "pretool":
        control = RunControl(selection=call.selection, max_model_requests=1)
        gate = WebToolGate(call, control, "owned")
        reply = await gate.pre_tool({"hook_event_name": "PreToolUse", "session_id": "owned",
            "tool_name": "StructuredOutput", "tool_use_id": "invalid", "tool_input": OUTPUT}, "invalid", {})
        assert reply["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert gate.failure == "unexpected_tool_activity"
    else:
        mod, _ = setup(monkeypatch, init={"tools": ["StructuredOutput"]} if boundary == "init" else None,
                       tool="StructuredOutput" if boundary == "notification" else None)
        with pytest.raises(WebModelError, match="^unexpected_tool_activity$"):
            await invoke(mod)


@pytest.mark.anyio
@pytest.mark.parametrize("changes,code,terminal", [
    ({"session_id": "foreign"}, "execution_identity_changed", {}),
    ({"is_error": True, "subtype": "error_max_turns", "terminal_reason": "max_turns"},
     "model_result_incomplete", {"analysis-1": "failed"}),
    ({"terminal_reason": "aborted_streaming"}, "model_result_incomplete", {"analysis-1": "interrupted"}),
    ({"model_usage": {"claude-sonnet-5": {}}}, "execution_identity_changed", {"analysis-1": "completed"}),
])
async def test_claude_analysis_json_does_not_bypass_terminal_or_identity_guards(monkeypatch, changes, code, terminal):
    mod, clients = setup(monkeypatch, result=changes)
    call = _request(phase="analysis", call_id="analysis-1")
    control = RunControl(selection=call.selection, max_model_requests=1)
    with pytest.raises(WebModelError, match="^" + code + "$"):
        await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("selected-token")), control)
    assert control.terminal_statuses == terminal and clients[0].closed
    assert control.model_requests == 1


@pytest.mark.anyio
async def test_claude_search_does_not_fall_back_to_analysis_json_mode(monkeypatch):
    mod, clients = _setup(monkeypatch, result={"structured_output": None, "result": json.dumps(OUTPUT)})
    call = _request()
    with pytest.raises(WebModelError, match="^model_output_invalid$"):
        await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("selected-token")),
                                  RunControl(selection=call.selection, max_model_requests=1))
    assert clients[0].options.output_format == {"type": "json_schema", "schema": SCHEMA}
    assert len(clients[0].queries) == 1
