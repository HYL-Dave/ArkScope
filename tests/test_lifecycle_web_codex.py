import asyncio
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    selection = validate_selection("openai", "chatgpt_oauth", "gpt-5.6-luna", "local:7")
    return replace(ModelCall(selection, "search-1", "search", "Public issuer question", SCHEMA, "high", None, 2, 5.0), **changes)


def _nested(configuration):
    result = {}
    for key, value in configuration.items():
        current = result
        parts = key.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result


def _event(method, **params):
    return {"method": method, "params": {"threadId": "thread-1", "turnId": "turn-1", **params}}


class Session:
    def __init__(self, purpose, poll, *, change=None, stop=None):
        self.purpose, self.poll, self.change, self.stop = purpose, poll, change or {}, stop
        self.calls, self.events = [], []
        self.deadline = 0
        self.interrupts = 0

    def request(self, identity, method, params):
        from src.auth_drivers.codex_web_policy import web_codex_configuration

        self.calls.append((method, params))
        if method == "config/read":
            config = _nested(web_codex_configuration(self.purpose))
            if self.change.get("config"):
                config["web_search"] = "disabled" if self.purpose.endswith("search") else "live"
            return {"config": config, "origins": {}, "layers": None}
        if method == "model/list":
            return {"data": [{"id": "1", "model": self.change.get("listed_model", "gpt-5.6-luna")}], "nextCursor": None}
        if method == "thread/start":
            thread = {"id": "thread-1", "cwd": params["cwd"], "ephemeral": True,
                      "modelProvider": "openai", "parentThreadId": None}
            self.events.append({"method": "thread/started", "params": {"thread": thread}})
            return {"thread": thread, "approvalPolicy": "never", "approvalsReviewer": "user", "cwd": params["cwd"],
                    "model": "gpt-5.6-luna", "modelProvider": "openai", "reasoningEffort": "high",
                    "instructionSources": [], "runtimeWorkspaceRoots": [],
                    "sandbox": {"type": "readOnly", "networkAccess": False}, **self.change.get("thread", {})}
        if method == "turn/start":
            self.events.append(_event("turn/started", turn={"id": "turn-1", "status": "inProgress", "items": []}))
            if self.purpose.endswith("search"):
                self.events.append(_event("item/completed", item={"type": self.change.get("tool", "webSearch"),
                                                                 "id": "web-1", "query": "Issuer Old Inc listing",
                                                                 "action": {"type": "search"}}))
            self.events.extend(self.change.get("extra_events", []))
            self.events.append(_event("item/completed", item={"type": "agentMessage", "id": "final-1",
                                                             "phase": "final_answer", "text": json.dumps(OUTPUT)}))
            self.events.append(_event("turn/completed", turn={"id": "turn-1", "status": "completed", "items": []}))
            if self.stop is not None:
                self.stop()
            return {"turn": {"id": "turn-1", "status": "inProgress", "items": []}}
        if method == "turn/interrupt":
            self.interrupts += 1
            self.events = [] if self.change.get("missing_terminal") else [
                _event("turn/completed", turn={"id": "turn-1", "status": "interrupted", "items": []})]
            return {}
        raise AssertionError(method)

    def next_notification(self):
        self.poll()
        if not self.events:
            from src.auth_drivers.codex_app_server_runtime import CodexAppServerRuntimeError
            raise CodexAppServerRuntimeError("timeout")
        return self.events.pop(0)


def _setup(monkeypatch, tmp_path, **changes):
    from src.auth_drivers import lifecycle_web_codex as mod

    runs, sessions = [], []

    def run(**kwargs):
        runs.append(kwargs)
        context = SimpleNamespace(codex_home=tmp_path, plan_type="prolite", account_id="selected-account")
        session = Session(kwargs["purpose"], kwargs["poll_check"], **changes)
        sessions.append(session)
        return context, kwargs["operation"](session, context)

    monkeypatch.setattr(mod, "run_authenticated_codex_operation", run)
    return mod, runs, sessions


@pytest.mark.anyio
async def test_codex_oauth_web_binds_exact_model_and_restricted_thread(monkeypatch, tmp_path):
    mod, runs, sessions = _setup(monkeypatch, tmp_path)
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    reply = await mod.call_codex_web(request, credential, control)
    assert reply.output == OUTPUT and reply.remote_id == "turn-1"
    assert runs[0]["purpose"] == "lifecycle_web_search" and runs[0]["executable"] is None
    assert runs[0]["record"] is credential.token_record
    calls = dict(sessions[0].calls)
    assert calls["thread/start"]["allowProviderModelFallback"] is False
    assert calls["thread/start"]["dynamicTools"] == [] and calls["thread/start"]["environments"] == []
    assert calls["thread/start"]["runtimeWorkspaceRoots"] == []
    assert calls["thread/start"]["model"] == request.selection.model
    assert calls["thread/start"]["sandbox"] == "read-only" and calls["thread/start"]["approvalPolicy"] == "never"
    assert calls["turn/start"]["effort"] == "high" and calls["turn/start"]["outputSchema"] == SCHEMA
    assert calls["turn/start"]["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    assert control.model_requests == 1 and control.observed_web_actions["search"] == 1
    assert control.terminal_statuses == {"search-1": "completed"}


@pytest.mark.anyio
async def test_codex_analysis_uses_closed_purpose_and_no_new_tool(monkeypatch, tmp_path):
    mod, runs, sessions = _setup(monkeypatch, tmp_path)
    request = _request(phase="analysis", call_id="analysis-1")
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    assert (await mod.call_codex_web(request, credential, control)).output == OUTPUT
    assert runs[0]["purpose"] == "lifecycle_web_analysis"
    assert dict(sessions[0].calls)["thread/start"]["config"]["web_search"] == "disabled"
    assert control.observed_web_actions["search"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize("change", [
    {"listed_model": "other"}, {"config": True}, {"thread": {"model": "gpt-5.6-terra"}},
    {"thread": {"instructionSources": ["/private/AGENTS.md"]}},
    {"thread": {"sandbox": {"type": "dangerFullAccess"}}},
])
async def test_codex_web_invalid_preflight_never_dispatches_a_model(monkeypatch, tmp_path, change):
    mod, _, sessions = _setup(monkeypatch, tmp_path, change=change)
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    with pytest.raises(WebModelError):
        await mod.call_codex_web(request, credential, control)
    assert "turn/start" not in dict(sessions[0].calls) and control.model_requests == 0


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["commandExecution", "fileChange", "mcpToolCall", "collabAgentToolCall", "dynamicToolCall", "imageView"])
async def test_codex_web_denies_all_non_web_tool_items_and_interrupts(monkeypatch, tmp_path, kind):
    mod, _, sessions = _setup(monkeypatch, tmp_path, change={"tool": kind})
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    with pytest.raises(WebModelError, match="unexpected_tool_activity"):
        await mod.call_codex_web(request, credential, control)
    assert sessions[0].interrupts == 1 and control.model_requests == 1
    assert control.terminal_statuses == {"search-1": "interrupted"}


@pytest.mark.anyio
@pytest.mark.parametrize("missing", [False, True])
async def test_codex_interrupt_ack_without_matching_terminal_stays_unknown(monkeypatch, tmp_path, missing):
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    mod, _, sessions = _setup(monkeypatch, tmp_path, change={"missing_terminal": missing}, stop=control.request_stop)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    with pytest.raises(WebModelError, match="stop_requested"):
        await mod.call_codex_web(request, credential, control)
    assert sessions[0].interrupts == 1
    assert control.stop_state == ("remote_outcome_unknown" if missing else "cancelled")


@pytest.mark.anyio
async def test_codex_foreign_turn_cannot_supply_result(monkeypatch, tmp_path):
    event = _event("turn/completed", turnId="foreign", turn={"id": "foreign", "status": "completed", "items": []})
    mod, _, sessions = _setup(monkeypatch, tmp_path, change={"extra_events": [event]})
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    with pytest.raises(WebModelError, match="protocol_incompatible"):
        await mod.call_codex_web(request, WebCredential(request.selection, token_record=StoredTokenRecord("selected-token")), control)
    assert sessions[0].interrupts == 1


@pytest.mark.anyio
@pytest.mark.parametrize("method,params,allowed,code", [
    ("remoteControl/status/changed", {"status": "disabled", "installationId": "local", "serverName": "local"}, True, None),
    ("remoteControl/status/changed", {"status": "connected", "installationId": "local", "serverName": "local"}, False, "unexpected_tool_activity"),
    ("remoteControl/status/changed", {"status": {"state": "disabled"}}, False, "protocol_incompatible"),
    ("account/updated", {"authMode": "apikey"}, False, "execution_identity_changed"),
    ("account/updated", {"authMode": "chatgptAuthTokens", "planType": "prolite"}, True, None),
])
async def test_codex_web_passive_events_do_not_expand_billing_or_remote_surface(monkeypatch, tmp_path, method, params, allowed, code):
    mod, _, sessions = _setup(monkeypatch, tmp_path, change={"extra_events": [{"method": method, "params": params}]})
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    if allowed:
        assert (await mod.call_codex_web(request, credential, control)).output == OUTPUT
    else:
        with pytest.raises(WebModelError, match=code):
            await mod.call_codex_web(request, credential, control)
        assert sessions[0].interrupts == 1
