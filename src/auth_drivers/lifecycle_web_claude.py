"""Purpose-specific Claude subscription Web search, not a Research tool change."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from claude_agent_sdk import (
    AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher,
    RateLimitEvent, ResultMessage, ServerToolUseBlock, SystemMessage, ToolUseBlock, UserMessage,
)

from src.auth_drivers.claude_agent_sdk_runtime import (
    REVIEWED_DISALLOWED_TOOLS, build_claude_child_environment,
    discard_claude_sdk_stderr, require_reviewed_claude_agent_runtime,
    require_subscription_auth_source,
)
from src.auth_drivers.lifecycle_web_models import (
    ModelCall, ModelReply, WebCredential, WebModelError,
    require_response_model, validate_output, completed_reply,
)
from src.auth_drivers.lifecycle_web_usage import TOKEN_FIELDS, claude_usage_observation
from src.auth_drivers.subscription_structured_output import _reap_owned_child, _transport_child_pid
from src.security_lifecycle_web_contract import RunControl


_STOP_GRACE_SECONDS = 2.0


class WebToolGate:
    """Admission happens before tool execution; output notifications are not gates."""

    def __init__(self, call: ModelCall, control: RunControl, session_id: str):
        self.call, self.control, self.session_id = call, control, session_id
        self._search: dict[str, str] = {}
        self.failure: str | None = None

    @property
    def search_reservations(self) -> set[str]:
        return set(self._search)

    def reject(self, code: str) -> dict:
        self.failure = self.failure or code
        self.control.request_stop()
        return {"continue_": False, "stopReason": self.failure,
                "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": self.failure}}

    async def pre_tool(self, data, tool_use_id, context):
        if self.control.stop_state != "running":
            return self.reject(self.failure or "stop_requested")
        if (not isinstance(data, dict) or data.get("hook_event_name") != "PreToolUse"
                or data.get("session_id") != self.session_id):
            return self.reject("execution_identity_changed")
        identity = data.get("tool_use_id")
        if not isinstance(identity, str) or not identity or tool_use_id not in (None, identity):
            return self.reject("execution_identity_changed")
        name = data.get("tool_name")
        value = data.get("tool_input")
        if not isinstance(value, dict):
            return self.reject("unexpected_tool_activity")
        if name == "WebSearch" and self.call.phase == "search":
            try:
                signature = json.dumps(value, sort_keys=True, allow_nan=False)
            except (ValueError, TypeError):
                return self.reject("unexpected_tool_activity")
            if identity in self._search:
                if self._search[identity] != signature:
                    return self.reject("execution_identity_changed")
            elif len(self._search) >= self.call.max_search_uses:
                return self.reject("search_budget_exhausted")
            else:
                self._search[identity] = signature
        elif name != "StructuredOutput" or self.call.phase != "search":
            return self.reject("unexpected_tool_activity")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}


def _client(options: ClaudeAgentOptions):
    return ClaudeSDKClient(options=options)


def _validate_init(message: SystemMessage, *, call: ModelCall, session_id: str) -> None:
    data = message.data
    if not isinstance(data, dict) or data.get("session_id") != session_id:
        raise WebModelError("execution_identity_changed")
    try:
        require_subscription_auth_source(data)
    except Exception:
        raise WebModelError("subscription_auth_unverified") from None
    require_response_model(data, call.selection.model)
    tools = data.get("tools")
    expected = {"StructuredOutput", "WebSearch"} if call.phase == "search" else set()
    if (not isinstance(tools, list) or any(not isinstance(name, str) for name in tools)
            or not set(tools).issubset(expected) or (call.phase == "search" and "WebSearch" not in tools)
            or data.get("mcp_servers") != []):
        raise WebModelError("unexpected_tool_activity")


def _result_status(message: ResultMessage, *, call: ModelCall, session_id: str) -> str:
    if message.session_id != session_id:
        raise WebModelError("execution_identity_changed")
    reason = message.terminal_reason
    if reason in {"aborted_streaming", "aborted_tools"}:
        return "interrupted"
    if reason != "completed" or message.is_error or message.subtype != "success":
        if reason is None:
            raise WebModelError("model_result_incomplete")
        return "failed"
    return "completed"


def _tool_round_trip_limit(call: ModelCall) -> int:
    return call.max_search_uses + 2 if call.phase == "search" else 2


def _validate_result(message: ResultMessage, *, call: ModelCall, status: str) -> None:
    usage = message.model_usage
    if usage is not None:
        if not isinstance(usage, dict):
            raise WebModelError("model_usage_invalid")
        for model in usage:
            require_response_model({"model": model}, call.selection.model)
    if status != "completed":
        return
    # max_turns bounds tool round trips; num_turns also includes completion.
    max_total_turns = _tool_round_trip_limit(call) + 1
    if type(message.num_turns) is not int or not 0 < message.num_turns <= max_total_turns:
        raise WebModelError("model_result_incomplete")
    if message.permission_denials or message.deferred_tool_use:
        raise WebModelError("unexpected_tool_activity")


async def call_claude_web(call: ModelCall, credential: WebCredential, control: RunControl) -> ModelReply:
    call.__post_init__()
    token = getattr(credential.token_record, "access_token", None)
    if (call.selection != credential.selection or call.selection != control.selection
            or call.selection.provider != "anthropic" or call.selection.auth_mode != "claude_code_oauth"
            or credential.api_key is not None or not isinstance(token, str) or not token):
        raise WebModelError("execution_identity_changed")
    if control.stop_state != "running":
        raise WebModelError("stop_requested")
    try:
        runtime = require_reviewed_claude_agent_runtime()
    except Exception:
        raise WebModelError("adapter_unavailable") from None
    deadline = time.monotonic() + call.timeout_seconds
    session_id = str(uuid4())
    gate = WebToolGate(call, control, session_id)
    with tempfile.TemporaryDirectory(prefix="ark-lifecycle-web-claude-") as directory:
        config = Path(directory) / "config"
        cwd = Path(directory) / "work"
        config.mkdir(mode=0o700)
        cwd.mkdir(mode=0o700)
        environment = build_claude_child_environment(token=token, config_dir=str(config))
        environment.update(CLAUDE_CODE_MAX_RETRIES="0", DISABLE_AUTO_COMPACT="1")
        # The reviewed CLI's WebSearch can use its small/fast helper independently
        # of --model. Bind both current and legacy overrides, including ambient ones.
        environment.update(ANTHROPIC_DEFAULT_HAIKU_MODEL=call.selection.model,
                           ANTHROPIC_SMALL_FAST_MODEL=call.selection.model)
        tools = ["WebSearch"] if call.phase == "search" else []
        disallowed = set(REVIEWED_DISALLOWED_TOOLS) - set(tools)
        system_prompt = "Investigate only the supplied public listing question. Return structured source candidates or findings. Do not perform unrelated tasks."
        if call.phase == "analysis":
            # Toolless native StructuredOutput can emit template placeholders.
            # Declare final JSON up front, with the same strict host validator.
            disallowed.add("StructuredOutput")
            system_prompt += (
                " Your final response must be exactly one JSON object matching the schema below. "
                "Use its exact property names and value types, including nested objects. "
                "Do not wrap the object in a function call, Markdown fences, or explanatory text. "
                "Do not search, read files, execute commands, or call any tool.\nOutput schema:\n"
                + json.dumps(call.output_schema, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            )
        options = ClaudeAgentOptions(
            model=call.selection.model, effort=call.effort, fallback_model=None,
            system_prompt=system_prompt,
            output_format={"type": "json_schema", "schema": call.output_schema} if call.phase == "search" else None,
            tools=tools, allowed_tools=tools, disallowed_tools=sorted(disallowed),
            mcp_servers={}, setting_sources=[], strict_mcp_config=True, permission_mode="dontAsk",
            hooks={"PreToolUse": [HookMatcher(hooks=[gate.pre_tool], timeout=1.0)]},
            max_turns=_tool_round_trip_limit(call), session_id=session_id,
            cli_path=str(runtime.cli_path), cwd=str(cwd), env=environment,
            stderr=discard_claude_sdk_stderr,
        )
        client = _client(options)
        dispatched = False
        initialized = False
        stop_sent = False
        stop_deadline = None
        failure: WebModelError | None = None
        pending = None
        iterator = None
        observed_search = set()
        try:
            await asyncio.wait_for(client.connect(), max(0.01, deadline - time.monotonic()))
            control.reserve_model_request(call.call_id)
            dispatched = True
            await asyncio.wait_for(client.query(call.prompt, session_id=session_id), max(0.01, deadline - time.monotonic()))
            iterator = client.receive_response().__aiter__()
            while True:
                if gate.failure is not None and failure is None:
                    failure = WebModelError(gate.failure)
                if control.stop_state != "running" or time.monotonic() >= deadline or failure is not None:
                    if failure is None:
                        failure = WebModelError("stop_requested" if control.stop_state != "running" else "timeout")
                    control.request_stop()
                    if not stop_sent:
                        stop_sent = True
                        stop_deadline = time.monotonic() + _STOP_GRACE_SECONDS
                        try:
                            await asyncio.wait_for(client.interrupt(), _STOP_GRACE_SECONDS)
                            if initialized:
                                control.observe_interrupt_ack(call.call_id, session_id)
                        except Exception:
                            pass
                    if time.monotonic() >= stop_deadline:
                        raise failure
                if pending is None:
                    pending = asyncio.create_task(iterator.__anext__())
                done, _ = await asyncio.wait({pending}, timeout=0.05)
                if not done:
                    continue
                try:
                    message = pending.result()
                except StopAsyncIteration:
                    raise failure or WebModelError("model_result_incomplete") from None
                finally:
                    pending = None
                try:
                    if isinstance(message, SystemMessage):
                        if message.subtype == "init":
                            _validate_init(message, call=call, session_id=session_id)
                            control.bind_remote_id(call.call_id, session_id)
                            initialized = True
                        elif message.subtype.startswith(("task_", "compact")):
                            raise WebModelError("unexpected_tool_activity")
                    elif isinstance(message, AssistantMessage):
                        if not initialized or message.parent_tool_use_id is not None:
                            raise WebModelError("execution_identity_changed")
                        require_response_model(message, call.selection.model)
                        if message.error is not None:
                            raise WebModelError("provider_call_failed")
                        for block in message.content:
                            if isinstance(block, ToolUseBlock) and block.name == "WebSearch" and call.phase == "search":
                                observed_search.add(block.id)
                                control.observe_web_action(call.call_id, block.id, "search")
                            elif isinstance(block, ToolUseBlock) and block.name == "StructuredOutput" and call.phase == "search":
                                continue
                            elif isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                                raise WebModelError("unexpected_tool_activity")
                    elif isinstance(message, ResultMessage):
                        if not initialized:
                            raise WebModelError("subscription_auth_unverified")
                        status = _result_status(message, call=call, session_id=session_id)
                        # Remote completion and acceptance are separate facts. A
                        # rejected owned result must not become an orphaned call.
                        control.observe_terminal(call.call_id, response_id=session_id, status=status, selection=call.selection)
                        _validate_result(message, call=call, status=status)
                        if failure is not None:
                            raise failure
                        if not observed_search.issubset(gate.search_reservations):
                            raise WebModelError("tool_admission_missing")
                        if status != "completed":
                            raise WebModelError("model_result_incomplete")
                        if call.phase == "analysis":
                            if message.structured_output is not None or not isinstance(message.result, str):
                                raise WebModelError("model_output_invalid")
                            value = message.result
                        else:
                            value = message.structured_output
                        usage = claude_usage_observation(message, call.selection.model)
                        return completed_reply(call, session_id, value, {key: usage["values"][key] for key in TOKEN_FIELDS}, usage)
                    elif isinstance(message, UserMessage):
                        if message.parent_tool_use_id is not None:
                            raise WebModelError("unexpected_tool_activity")
                    elif isinstance(message, RateLimitEvent):
                        if message.session_id != session_id:
                            raise WebModelError("execution_identity_changed")
                        status = message.rate_limit_info.status
                        if status == "rejected":
                            raise WebModelError("provider_rate_limited")
                        if status not in {"allowed", "allowed_warning"}:
                            raise WebModelError("protocol_incompatible")
                    else:
                        raise WebModelError("protocol_incompatible")
                except WebModelError as exc:
                    failure = failure or exc
                    control.request_stop()
                    if isinstance(message, ResultMessage):
                        raise failure
        except asyncio.CancelledError:
            control.request_stop()
            if dispatched and call.call_id not in control.terminal_statuses:
                try:
                    await asyncio.wait_for(client.interrupt(), _STOP_GRACE_SECONDS)
                except Exception:
                    pass
                control.observe_transport_loss(call.call_id)
            raise
        except Exception as exc:
            control.request_stop()
            if dispatched and call.call_id not in control.terminal_statuses:
                control.observe_transport_loss(call.call_id)
            raise exc if isinstance(exc, WebModelError) else WebModelError("provider_call_failed") from None
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if iterator is not None:
                await iterator.aclose()
            child_pid = _transport_child_pid(getattr(client, "_transport", None))
            try:
                await asyncio.wait_for(client.disconnect(), 25.0)
            finally:
                await _reap_owned_child(child_pid)
