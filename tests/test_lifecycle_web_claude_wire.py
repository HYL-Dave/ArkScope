import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk._internal.transport import Transport
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.security_lifecycle_web_contract import RunControl
from tests.test_lifecycle_web_claude import _request, SCHEMA, OUTPUT


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Peer(Transport):
    """Network-free peer below the real SDK's control/message serializers."""

    def __init__(self, options, forbidden):
        self.options = options
        self.forbidden = forbidden
        self.messages = asyncio.Queue()
        self.writes = []
        self.ready = False
        self.closed = False
        self.callback = None

    async def connect(self):
        self.ready = True

    async def write(self, data):
        message = json.loads(data)
        self.writes.append(message)
        session = self.options.session_id
        if message["type"] == "control_request":
            request = message["request"]
            if request["subtype"] == "initialize":
                self.callback = request["hooks"]["PreToolUse"][0]["hookCallbackIds"][0]
            await self.messages.put({"type": "control_response", "response": {
                "subtype": "success", "request_id": message["request_id"], "response": {},
            }})
        elif message["type"] == "user":
            assert message["session_id"] == session
            await self.messages.put({"type": "system", "subtype": "init", "session_id": session,
                                     "model": self.options.model, "apiKeySource": "none",
                                     "tools": list(self.options.tools) + (["StructuredOutput"] if self.options.output_format else []),
                                     "mcp_servers": []})
            await self.messages.put({"type": "rate_limit_event", "uuid": "rate-1", "session_id": session,
                                     "rate_limit_info": {"status": "allowed", "rateLimitType": "five_hour"}})
            if self.options.output_format is None and not self.forbidden:
                await self.messages.put({"type": "assistant", "session_id": session, "message": {
                    "model": self.options.model, "content": [{"type": "text", "text": json.dumps(OUTPUT)}],
                }})
                await self.finish(True)
                return
            name = "Bash" if self.forbidden else ("WebSearch" if "WebSearch" in self.options.tools else "StructuredOutput")
            value = {"query": "Issuer Old Inc listing"} if name == "WebSearch" else OUTPUT
            await self.messages.put({"type": "control_request", "request_id": "gate-1", "request": {
                "subtype": "hook_callback", "callback_id": self.callback, "tool_use_id": "tool-1",
                "input": {"hook_event_name": "PreToolUse", "session_id": session,
                          "tool_name": name, "tool_use_id": "tool-1", "tool_input": value},
            }})
        elif message["type"] == "control_response":
            hook = message["response"]["response"]
            allowed = hook["hookSpecificOutput"]["permissionDecision"] == "allow"
            if allowed and "WebSearch" in self.options.tools:
                await self.messages.put({"type": "assistant", "session_id": session, "message": {
                    "model": self.options.model, "content": [{"type": "tool_use", "id": "tool-1", "name": "WebSearch",
                                                              "input": {"query": "Issuer Old Inc listing"}}],
                }})
            await self.finish(allowed)

    async def finish(self, allowed):
        await self.messages.put({"type": "result", "subtype": "success", "duration_ms": 1, "duration_api_ms": 1,
                                 "is_error": False, "num_turns": 2 if self.options.output_format else 1,
                                 "session_id": self.options.session_id,
                                 "terminal_reason": "completed" if allowed else "aborted_tools",
                                 "structured_output": OUTPUT if allowed and self.options.output_format else None,
                                 "result": json.dumps(OUTPUT) if allowed and self.options.output_format is None else None,
                                 "usage": {"input_tokens": 1, "output_tokens": 2},
                                 "modelUsage": {self.options.model: {"inputTokens": 1, "outputTokens": 2}}})

    async def read_messages(self):
        while True:
            message = await self.messages.get()
            if message is None:
                return
            yield message

    async def close(self):
        self.closed = True
        self.ready = False
        await self.messages.put(None)

    def is_ready(self):
        return self.ready

    async def end_input(self):
        pass


@pytest.mark.anyio
@pytest.mark.parametrize("phase,forbidden", [("search", False), ("analysis", False), ("search", True), ("analysis", True)])
async def test_actual_claude_sdk_serializes_web_hook_and_owned_result(monkeypatch, phase, forbidden):
    from src.auth_drivers import lifecycle_web_claude as mod

    peers = []
    commands = []

    def client(options):
        peer = Peer(options, forbidden)
        peers.append(peer)
        transport = SubprocessCLITransport(prompt="", options=options)
        commands.append(transport._build_command())
        return ClaudeSDKClient(options=options, transport=peer)

    monkeypatch.setattr(mod, "_client", client)
    monkeypatch.setattr(mod, "require_reviewed_claude_agent_runtime",
                        lambda: SimpleNamespace(cli_path=Path("/reviewed/bundled/claude")))
    request = _request(phase=phase)
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    if forbidden:
        with pytest.raises(WebModelError, match="unexpected_tool_activity"):
            await mod.call_claude_web(request, credential, control)
    else:
        assert (await mod.call_claude_web(request, credential, control)).output == OUTPUT
    assert len(peers) == 1 and peers[0].closed
    assert len([message for message in peers[0].writes if message["type"] == "user"]) == 1
    hooks = [message["response"]["response"] for message in peers[0].writes if message["type"] == "control_response"]
    if phase == "search" or forbidden:
        assert len(hooks) == 1
        assert hooks[0]["hookSpecificOutput"]["permissionDecision"] == ("deny" if forbidden else "allow")
    else:
        assert hooks == []
    if forbidden:
        assert hooks[0]["continue"] is False and "continue_" not in hooks[0]
        assert control.stop_state == "cancelled"
    command = commands[0]
    assert command[0] == "/reviewed/bundled/claude"
    assert command[command.index("--tools") + 1] == ("WebSearch" if phase == "search" else "")
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    assert "--setting-sources=" in command
    assert "--strict-mcp-config" in command
    if phase == "search":
        assert json.loads(command[command.index("--json-schema") + 1]) == SCHEMA
    else:
        assert "--json-schema" not in command
