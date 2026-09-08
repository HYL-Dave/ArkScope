"""Selected-credential, single-request model boundaries for Lifecycle Web work.

API adapters live here; OAuth adapters use the same call/result contract without
falling through to these clients. This module never changes profile tracking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import time
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from src.model_capabilities import capability_for
from src.security_lifecycle_web_contract import ExecutionSelection, RunControl, validate_selection


_STOP_GRACE_SECONDS = 2.0
_EMIT_TOOL = "emit_lifecycle_result"


class WebModelError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelCall:
    selection: ExecutionSelection
    call_id: str
    phase: str
    prompt: str = field(repr=False)
    output_schema: dict = field(repr=False)
    effort: str | None
    output_token_limit: int | None
    max_search_uses: int
    timeout_seconds: float
    retain_rejected_output: bool = False

    def __post_init__(self) -> None:
        validate_selection(self.selection.provider, self.selection.auth_mode,
                           self.selection.model, self.selection.credential_id)
        capability = capability_for(self.selection.model)
        if (type(self.retain_rejected_output) is not bool or self.phase not in {"search", "analysis"} or not isinstance(self.call_id, str)
                or not self.call_id.strip() or not isinstance(self.prompt, str) or not self.prompt.strip()
                or type(self.max_search_uses) is not int or self.max_search_uses <= 0
                or type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise WebModelError("model_call_invalid")
        if self.effort is not None and self.effort not in capability.effort_options:
            raise WebModelError("model_effort_unsupported")
        limit = self.output_token_limit
        if (limit is not None and (type(limit) is not int or limit <= 0)):
            raise WebModelError("model_output_limit_invalid")
        if self.selection.auth_mode == "api_key":
            if limit is None or capability.max_output is None or limit > capability.max_output:
                raise WebModelError("model_output_limit_invalid")
        try:
            Draft202012Validator.check_schema(self.output_schema)
            encoded = json.dumps(self.output_schema, allow_nan=False)
        except (SchemaError, ValueError, TypeError):
            raise WebModelError("model_output_schema_invalid") from None
        if not isinstance(self.output_schema, dict) or self.output_schema.get("type") != "object":
            raise WebModelError("model_output_schema_invalid")
        # These schemas are code-owned. Do not give their validator a network path.
        def check_refs(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"$ref", "$dynamicRef"} and (not isinstance(child, str) or not child.startswith("#")):
                        raise WebModelError("model_output_schema_invalid")
                    check_refs(child)
            elif isinstance(value, list):
                for child in value:
                    check_refs(child)
        check_refs(json.loads(encoded))


@dataclass(frozen=True)
class WebCredential:
    selection: ExecutionSelection
    api_key: str | None = field(default=None, repr=False)
    token_record: Any = field(default=None, repr=False)
    generation: str | None = field(default=None, repr=False)


def credential_generation(row) -> str:
    material = [row.id, getattr(row, "updated_at", None), row.secret, getattr(row, "active", None)]
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _token_expiry(record):
    token = getattr(record, "access_token", None)
    if not isinstance(token, str) or not token or any(ord(ch) < 33 or ord(ch) == 127 for ch in token):
        raise WebModelError("reauth_required")
    expires = getattr(record, "expires_at", None)
    if expires is None:
        return None
    try:
        expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            raise ValueError("timezone")
        return expiry
    except (ValueError, TypeError, AttributeError):
        raise WebModelError("reauth_required") from None


def resolve_web_credential(selection: ExecutionSelection, *, store, token_store, refresh_chatgpt=None) -> WebCredential:
    validate_selection(selection.provider, selection.auth_mode, selection.model, selection.credential_id)
    row = store.get(selection.credential_id)
    if (row is None or f"local:{row.id}" != selection.credential_id or row.provider != selection.provider
            or row.auth_type != selection.auth_mode):
        raise WebModelError("selected_credential_unavailable")
    if selection.auth_mode == "api_key":
        key = row.secret
        if not isinstance(key, str) or not key or any(ord(ch) < 32 or ord(ch) == 127 for ch in key):
            raise WebModelError("selected_credential_unavailable")
        return WebCredential(selection, api_key=key, generation=credential_generation(row))
    record = token_store.load(provider=selection.provider, auth_mode=selection.auth_mode,
                              credential_id=selection.credential_id)
    expiry = _token_expiry(record)
    if (selection.auth_mode == "chatgpt_oauth" and refresh_chatgpt is not None and expiry is not None
            and expiry <= datetime.now(timezone.utc) + timedelta(minutes=5)):
        try:
            record = refresh_chatgpt(credential_id=selection.credential_id, token_store=token_store)
        except Exception as exc:
            raise WebModelError("reauth_required" if getattr(exc, "reauth_required", False) else "selected_credential_unavailable") from None
        expiry = _token_expiry(record)
    if expiry is not None and expiry <= datetime.now(timezone.utc):
        raise WebModelError("reauth_required")
    return WebCredential(selection, token_record=record, generation=credential_generation(row))


@dataclass(frozen=True)
class ModelReply:
    remote_id: str
    output: Any
    usage: dict[str, int | None]
    usage_observation: dict | None = None
    output_error: str | None = None


def _field(value: Any, name: str, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def require_response_model(value: Any, selected: str) -> None:
    actual = _field(value, "model")
    expected_capability = capability_for(selected)
    actual_capability = capability_for(actual) if isinstance(actual, str) else None
    if (actual_capability is None or expected_capability is None
            or actual_capability.id != expected_capability.id):
        raise WebModelError("execution_identity_changed")


def validate_output(value: Any, schema: dict) -> dict:
    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result

    def invalid_constant(value):
        raise ValueError("invalid JSON constant")

    try:
        if isinstance(value, str):
            value = json.loads(value, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        if not isinstance(value, dict):
            raise ValueError("not an object")
        json.dumps(value, allow_nan=False)
        Draft202012Validator(schema).validate(value)
    except (ValueError, TypeError, ValidationError):
        raise WebModelError("model_output_invalid") from None
    return value


def normalized_usage(value: Any) -> dict[str, int | None]:
    result = {}
    for name in ("input_tokens", "output_tokens"):
        count = _field(value, name)
        if count is not None and (type(count) is not int or count < 0):
            raise WebModelError("model_usage_invalid")
        result[name] = count
    return result


def completed_reply(call, remote_id, output, usage, observation=None):
    """Keep an owned completed rejection distinct from a transport retry."""
    usage = normalized_usage(usage)
    try:
        output = validate_output(output, call.output_schema)
    except WebModelError:
        if not call.retain_rejected_output:
            raise
        return ModelReply(remote_id, output, usage, observation, "model_output_invalid")
    return ModelReply(remote_id, output, usage, observation)


def _check_call(call: ModelCall, credential: WebCredential, control: RunControl, provider: str) -> None:
    call.__post_init__()
    if (call.selection != credential.selection or call.selection != control.selection
            or call.selection.provider != provider or call.selection.auth_mode != "api_key"
            or not credential.api_key or credential.token_record is not None):
        raise WebModelError("execution_identity_changed")


async def _wait(awaitable, control: RunControl, deadline: float):
    task = asyncio.ensure_future(awaitable)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=0.05)
            if done:
                return task.result()
            if control.stop_state != "running":
                raise WebModelError("stop_requested")
            if time.monotonic() >= deadline:
                control.request_stop()
                raise WebModelError("timeout")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def _openai_client(*, http_client=None, **kwargs):
    import httpx
    from openai import AsyncOpenAI

    client = AsyncOpenAI(**kwargs, organization="", project="", admin_api_key="", webhook_secret="",
                         http_client=http_client or httpx.AsyncClient(trust_env=False, follow_redirects=False))
    # Both SDKs merge *_CUSTOM_HEADERS from the process even with explicit auth.
    # Clear that SDK-owned map before any request; real-wire tests own this boundary.
    client._custom_headers = {}
    return client


def _anthropic_client(*, http_client=None, **kwargs):
    from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

    client = AsyncAnthropic(**kwargs, auth_token="", webhook_key="",
                            http_client=http_client or DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False))
    client.auth_token = None
    client._custom_headers = {}
    return client


def _failure(exc: Exception) -> WebModelError:
    if isinstance(exc, WebModelError):
        return exc
    status = getattr(exc, "status_code", None)
    if status in {401, 403}:
        return WebModelError("credential_rejected")
    if status == 429:
        return WebModelError("provider_rate_limited")
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and _field(body.get("error", body), "code") in {"context_length_exceeded", "context_window_exceeded"}:
        return WebModelError("context_window_exceeded")
    return WebModelError("provider_call_failed")


def _bind_response(response, call, control) -> str:
    remote_id = _field(response, "id")
    if not isinstance(remote_id, str) or not remote_id:
        raise WebModelError("execution_identity_changed")
    control.bind_remote_id(call.call_id, remote_id)
    require_response_model(response, call.selection.model)
    return remote_id


def _observe_openai_terminal(response, call, control) -> str | None:
    remote_id = _bind_response(response, call, control)
    status = _field(response, "status")
    if status in {"queued", "in_progress"}:
        return None
    if status not in {"completed", "cancelled", "failed", "incomplete"}:
        raise WebModelError("model_result_incomplete")
    terminal = "failed" if status == "incomplete" else status
    control.observe_terminal(call.call_id, response_id=remote_id, status=terminal, selection=call.selection)
    return status


async def _cancel_openai(client, call, control, remote_id: str) -> None:
    deadline = time.monotonic() + _STOP_GRACE_SECONDS
    try:
        response = await asyncio.wait_for(client.responses.cancel(remote_id, timeout=_STOP_GRACE_SECONDS), _STOP_GRACE_SECONDS)
        control.observe_interrupt_ack(call.call_id, remote_id)
        while _observe_openai_terminal(response, call, control) is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(0.1, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            response = await asyncio.wait_for(client.responses.retrieve(remote_id, timeout=remaining), remaining)
    except Exception:
        pass
    if call.call_id not in control.terminal_statuses:
        control.observe_transport_loss(call.call_id)


async def call_openai_web(call: ModelCall, credential: WebCredential, control: RunControl) -> ModelReply:
    _check_call(call, credential, control, "openai")
    client = _openai_client(api_key=credential.api_key, max_retries=0,
                            base_url="https://api.openai.com/v1", timeout=call.timeout_seconds)
    dispatched = False
    remote_id = None
    try:
        control.reserve_model_request(call.call_id)
        dispatched = True
        deadline = time.monotonic() + call.timeout_seconds
        kwargs = {
            "model": call.selection.model, "input": call.prompt,
            "background": True, "store": True, "max_output_tokens": call.output_token_limit,
            "tools": [{"type": "web_search"}] if call.phase == "search" else [],
            "text": {"format": {"type": "json_schema", "name": "lifecycle_web_result", "strict": True,
                                "schema": call.output_schema}},
        }
        if call.phase == "search":
            kwargs["max_tool_calls"] = call.max_search_uses
        if call.effort is not None:
            kwargs["reasoning"] = {"effort": call.effort}
        response = await _wait(client.responses.create(**kwargs), control, deadline)
        remote_id = _bind_response(response, call, control)
        status = _observe_openai_terminal(response, call, control)
        while status is None:
            if control.stop_state != "running":
                raise WebModelError("stop_requested")
            if time.monotonic() >= deadline:
                control.request_stop()
                raise WebModelError("timeout")
            await asyncio.sleep(min(0.25, max(0, deadline - time.monotonic())))
            response = await _wait(client.responses.retrieve(remote_id, timeout=max(0.01, deadline - time.monotonic())), control, deadline)
            status = _observe_openai_terminal(response, call, control)
        if control.stop_state != "running":
            raise WebModelError("stop_requested")
        if status != "completed":
            raise WebModelError("model_result_incomplete")
        for item in _field(response, "output", []):
            kind = _field(item, "type")
            if kind in {"message", "reasoning"}:
                continue
            if kind != "web_search_call" or call.phase != "search":
                raise WebModelError("unexpected_tool_activity")
            if _field(item, "status") != "completed":
                raise WebModelError("search_result_incomplete")
            action = _field(_field(item, "action"), "type")
            control.observe_web_action(call.call_id, _field(item, "id"), action)
        return completed_reply(call, remote_id, _field(response, "output_text"), _field(response, "usage"))
    except asyncio.CancelledError:
        control.request_stop()
        if dispatched and remote_id and call.call_id not in control.terminal_statuses:
            await _cancel_openai(client, call, control, remote_id)
        elif dispatched and call.call_id not in control.terminal_statuses:
            control.observe_transport_loss(call.call_id)
        raise
    except Exception as exc:
        control.request_stop()
        if dispatched and remote_id and call.call_id not in control.terminal_statuses:
            await _cancel_openai(client, call, control, remote_id)
        elif dispatched and call.call_id not in control.terminal_statuses:
            control.observe_transport_loss(call.call_id)
        raise _failure(exc) from None
    finally:
        await client.close()


async def call_anthropic_web(call: ModelCall, credential: WebCredential, control: RunControl) -> ModelReply:
    _check_call(call, credential, control, "anthropic")
    client = _anthropic_client(api_key=credential.api_key, max_retries=0,
                               base_url="https://api.anthropic.com", timeout=call.timeout_seconds)
    dispatched = False
    try:
        control.reserve_model_request(call.call_id)
        dispatched = True
        tools = ([{"type": "web_search_20250305", "name": "web_search", "max_uses": call.max_search_uses}]
                 if call.phase == "search" else [])
        tools.append({"name": _EMIT_TOOL, "description": "Return the structured investigation result.",
                      "input_schema": call.output_schema, "strict": True})
        kwargs = {
            "model": call.selection.model, "max_tokens": call.output_token_limit,
            "messages": [{"role": "user", "content": call.prompt}], "tools": tools,
            "tool_choice": {"type": "auto"},
        }
        if call.effort is not None:
            kwargs["output_config"] = {"effort": call.effort}
        response = await _wait(client.messages.create(**kwargs), control, time.monotonic() + call.timeout_seconds)
        remote_id = _bind_response(response, call, control)
        reason = _field(response, "stop_reason")
        if reason is None:
            raise WebModelError("model_result_incomplete")
        status = "completed" if reason in {"end_turn", "tool_use"} else "failed"
        control.observe_terminal(call.call_id, response_id=remote_id, status=status, selection=call.selection)
        if control.stop_state != "running":
            raise WebModelError("stop_requested")
        if reason == "refusal":
            raise WebModelError("provider_refused")
        if status != "completed":
            raise WebModelError("model_result_incomplete")
        emissions = []
        for item in _field(response, "content", []):
            kind = _field(item, "type")
            if kind in {"text", "thinking", "redacted_thinking"}:
                continue
            if kind == "server_tool_use" and _field(item, "name") == "web_search" and call.phase == "search":
                control.observe_web_action(call.call_id, _field(item, "id"), "search")
            elif kind == "web_search_tool_result" and call.phase == "search":
                content = _field(item, "content")
                if not isinstance(content, list):
                    code = _field(content, "error_code")
                    raise WebModelError("search_budget_exhausted" if code == "max_uses_exceeded" else "search_unavailable")
            elif kind == "tool_use" and _field(item, "name") == _EMIT_TOOL:
                emissions.append(_field(item, "input"))
            else:
                raise WebModelError("unexpected_tool_activity")
        if len(emissions) != 1 and not call.retain_rejected_output:
            raise WebModelError("model_output_invalid")
        return completed_reply(call, remote_id, emissions[0] if len(emissions) == 1 else None,
                               _field(response, "usage"))
    except asyncio.CancelledError:
        control.request_stop()
        if dispatched and call.call_id not in control.terminal_statuses:
            control.observe_transport_loss(call.call_id)
        raise
    except Exception as exc:
        control.request_stop()
        if dispatched and call.call_id not in control.terminal_statuses:
            control.observe_transport_loss(call.call_id)
        raise _failure(exc) from None
    finally:
        await client.close()
