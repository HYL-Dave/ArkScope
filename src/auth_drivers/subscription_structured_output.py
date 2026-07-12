"""Bounded structured-output calls over provider subscription credentials.

This module is deliberately separate from the public API-key SDK clients.  A
subscription call receives an explicit credential id and token-store record,
uses only that provider's subscription transport, and never falls back to an
environment API key, another provider, or another model.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timezone
import inspect
import json
import os
import shutil
import tempfile
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    ServerToolUseBlock,
    SystemMessage,
    ToolUseBlock,
    query as _claude_query,
)
from claude_agent_sdk._internal.transport.subprocess_cli import (
    SubprocessCLITransport,
)

from src.auth_drivers.chatgpt_oauth_login import ChatGPTOAuthLoginError
from src.auth_drivers.chatgpt_oauth_login import provider_error_requires_reauth
from src.auth_drivers.chatgpt_oauth_login import refresh_if_needed
from src.auth_drivers.chatgpt_oauth_probe import (
    CHATGPT_BACKEND_BASE_URL,
    _event_output_item,
    _iter_output_items,
    _to_dict,
)
from src.auth_drivers.probe_harness import redact
from src.auth_drivers.token_store import get_token_store


class SubscriptionStructuredOutputError(RuntimeError):
    """Classified subscription-output failure safe to surface through routes."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


_CLAUDE_INHERITED_BILLING_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_FOUNDRY_API_KEY",
    "ANTHROPIC_AWS_API_KEY",
    "ANTHROPIC_BEDROCK_MANTLE_API_KEY",
    "AWS_BEARER_TOKEN_BEDROCK",
    "ANTHROPIC_AWS_AUTH",
    "ANTHROPIC_IDENTITY_TOKEN",
    "ANTHROPIC_IDENTITY_TOKEN_FILE",
    "ANTHROPIC_PROFILE",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
    "ANTHROPIC_FOUNDRY_BASE_URL",
    "ANTHROPIC_AWS_BASE_URL",
    "ANTHROPIC_BEDROCK_MANTLE_BASE_URL",
    "ANTHROPIC_UNIX_SOCKET",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_USE_ANTHROPIC_AWS",
    "CLAUDE_CODE_USE_MANTLE",
    "CLAUDE_CODE_USE_GATEWAY",
)
# The SDK's own close path budgets 5s graceful + 5s SIGTERM before SIGKILL.
# Leave enough outer margin for the final waitpid/reap instead of cancelling
# cleanup after the child exits but before it is collected.
_CLAUDE_SHUTDOWN_TIMEOUT_S = 20.0


def _openai_client(token: str, base_url: str, timeout_s: float) -> Any:  # test seam
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=token,
        base_url=base_url,
        timeout=timeout_s,
        max_retries=0,
    )


def _refresh_chatgpt_token(*, credential_id: str, token_store: Any):  # test seam
    return refresh_if_needed(credential_id=credential_id, token_store=token_store)


def _claude_transport(*, prompt: str, options: ClaudeAgentOptions) -> Any:
    """Build the pinned SDK transport while retaining ownership of its PID."""
    return SubprocessCLITransport(prompt=prompt, options=options)


def _transport_child_pid(transport: Any) -> int | None:
    process = getattr(transport, "_process", None)
    pid = getattr(process, "pid", None)
    return pid if isinstance(pid, int) and pid > 0 else None


async def _reap_owned_child(pid: int | None, *, timeout_s: float = 5.0) -> None:
    """Reap only this adapter's child if it exits just after SDK close."""
    if pid is None:
        return
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(float(timeout_s), 0.0)
    while True:
        try:
            waited_pid, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            # The SDK/asyncio child watcher already reaped it.
            return
        except OSError:
            # Cleanup must not replace the provider result.
            return
        if waited_pid == pid:
            return
        remaining = deadline - loop.time()
        if remaining <= 0:
            return
        await asyncio.sleep(min(0.05, remaining))


def _safe_message(exc: BaseException, token: str | None = None) -> str:
    try:
        message = str(exc)
    except Exception:  # noqa: BLE001
        message = type(exc).__name__
    if token:
        message = message.replace(token, "[REDACTED]")
    return redact(message)[:500]


async def _close_quietly(value: Any, *, timeout_s: float = 1.0) -> None:
    if value is None:
        return
    close = getattr(value, "aclose", None) or getattr(value, "close", None)
    if close is None:
        return
    try:
        result = close()
        if inspect.isawaitable(result):
            await asyncio.wait_for(result, timeout=max(float(timeout_s), 0.001))
    except BaseException:  # noqa: BLE001 - cleanup must not replace provider result
        pass


def _remaining(deadline: float) -> float:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise asyncio.TimeoutError
    return remaining


def _cleanup_budget(deadline: float) -> float:
    """Use the call's remaining budget, with a tiny best-effort cancellation slot."""
    remaining = deadline - asyncio.get_running_loop().time()
    return min(1.0, max(remaining, 0.005))


async def _await_with_deadline(value: Any, deadline: float) -> Any:
    if not inspect.isawaitable(value):
        _remaining(deadline)
        return value
    return await asyncio.wait_for(value, timeout=_remaining(deadline))


_STREAM_END = object()


async def _next_with_deadline(iterator: Any, deadline: float) -> Any:
    if hasattr(iterator, "__anext__"):
        return await asyncio.wait_for(iterator.__anext__(), timeout=_remaining(deadline))
    _remaining(deadline)
    item = next(iterator, _STREAM_END)
    if item is _STREAM_END:
        raise StopAsyncIteration
    return item


async def _run_sync_preflight(call, *, deadline: float, label: str) -> Any:
    """Bound keyring/refresh work without moving a provider call off-loop.

    A timed-out worker may finish credential maintenance later, but it never owns
    an LLM client and therefore cannot continue model usage after the route returns.
    """
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="ark-subscription-preflight",
    )
    future = loop.run_in_executor(pool, call)
    try:
        return await asyncio.wait_for(future, timeout=_remaining(deadline))
    except asyncio.TimeoutError as exc:
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            f"{label} preflight timed out before any model call.",
        ) from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


async def _openai_structured_output_async(
    *,
    credential_id: str,
    model: str,
    system: str,
    user: str,
    output_name: str,
    output_description: str,
    schema: dict[str, Any],
    effort: str,
    token_store: Any,
    timeout_s: float,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + max(float(timeout_s), 0.001)
    token: str | None = None
    try:
        record = await _run_sync_preflight(
            lambda: _refresh_chatgpt_token(
                credential_id=credential_id,
                token_store=token_store,
            ),
            deadline=deadline,
            label="ChatGPT credential",
        )
        token = getattr(record, "access_token", None)
    except ChatGPTOAuthLoginError as exc:
        code = "reauth_required" if getattr(exc, "reauth_required", False) else "provider_call_failed"
        raise SubscriptionStructuredOutputError(code, _safe_message(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise SubscriptionStructuredOutputError("provider_call_failed", _safe_message(exc)) from exc
    if not token:
        raise SubscriptionStructuredOutputError(
            "reauth_required",
            "No ChatGPT OAuth token is available; re-login from Settings.",
        )

    client = None
    stream = None
    try:
        client = _openai_client(token, CHATGPT_BACKEND_BASE_URL, timeout_s)
        kwargs: dict[str, Any] = {
            "model": model,
            "input": [{"role": "user", "content": user}],
            "instructions": system,
            "tools": [
                {
                    "type": "function",
                    "name": output_name,
                    "description": output_description,
                    "parameters": schema,
                }
            ],
            "stream": True,
            "store": False,
        }
        if effort not in ("", "default"):
            kwargs["reasoning"] = {"effort": effort}
        stream = await _await_with_deadline(client.responses.create(**kwargs), deadline)

        terminal = None
        call_items: list[dict[str, Any]] = []
        arg_fallback: dict[str, str] = {}
        iterator = stream.__aiter__() if hasattr(stream, "__aiter__") else iter(stream)
        while True:
            try:
                event = await _next_with_deadline(iterator, deadline)
            except StopAsyncIteration:
                break
            raw = _to_dict(event)
            event_type = raw.get("type")
            if event_type == "response.function_call_arguments.done":
                call_id = raw.get("call_id") or raw.get("item_id")
                arguments = raw.get("arguments")
                if isinstance(call_id, str) and isinstance(arguments, str):
                    arg_fallback[call_id] = arguments
            item = _event_output_item(raw)
            if isinstance(item, dict) and item.get("type") == "function_call":
                call_items.append(item)
            if event_type == "response.completed":
                terminal = raw.get("response")
            elif event_type in {"response.failed", "response.incomplete"}:
                detail = raw.get("error") or raw.get("response") or event_type
                raise SubscriptionStructuredOutputError(
                    "provider_call_failed",
                    _safe_message(RuntimeError(str(detail)), token),
                )

        # Streaming emits ``output_item.added`` before the completed item. Prefer
        # terminal output; otherwise inspect streamed items newest-first so a
        # placeholder without arguments cannot mask the completed call.
        items = _iter_output_items(terminal) or list(reversed(call_items))
        for item in items:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            if item.get("name") != output_name:
                continue
            arguments = item.get("arguments")
            if not isinstance(arguments, str):
                call_id = item.get("call_id") or item.get("id")
                arguments = arg_fallback.get(call_id, "") if isinstance(call_id, str) else ""
            try:
                payload = json.loads(arguments)
            except (TypeError, ValueError) as exc:
                raise SubscriptionStructuredOutputError(
                    "provider_call_failed",
                    f"ChatGPT subscription returned invalid {output_name} arguments.",
                ) from exc
            if not isinstance(payload, dict):
                raise SubscriptionStructuredOutputError(
                    "provider_call_failed",
                    f"ChatGPT subscription returned a non-object {output_name} payload.",
                )
            return payload
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            f"ChatGPT subscription did not return the {output_name} function call.",
        )
    except SubscriptionStructuredOutputError:
        raise
    except asyncio.TimeoutError as exc:
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            f"ChatGPT subscription structured call timed out after {timeout_s:g} seconds.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        code = (
            "reauth_required"
            if provider_error_requires_reauth(exc)
            else "provider_call_failed"
        )
        raise SubscriptionStructuredOutputError(
            code,
            _safe_message(exc, token),
        ) from exc
    finally:
        await _close_quietly(stream, timeout_s=_cleanup_budget(deadline))
        await _close_quietly(client, timeout_s=_cleanup_budget(deadline))


async def _claude_structured_output_async(
    *,
    credential_id: str,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    effort: str,
    token_store: Any,
    timeout_s: float,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + max(float(timeout_s), 0.001)
    try:
        record = await _run_sync_preflight(
            lambda: token_store.load(
                provider="anthropic",
                auth_mode="claude_code_oauth",
                credential_id=credential_id,
            ),
            deadline=deadline,
            label="Claude credential",
        )
    except Exception as exc:  # noqa: BLE001
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            _safe_message(exc),
        ) from exc
    token = getattr(record, "access_token", None) if record is not None else None
    if not token:
        raise SubscriptionStructuredOutputError(
            "reauth_required",
            "No Claude subscription token is available; import it from Settings.",
        )
    expires_at = getattr(record, "expires_at", None)
    if isinstance(expires_at, str) and expires_at.strip():
        try:
            parsed_expiry = datetime.fromisoformat(
                expires_at.strip().replace("Z", "+00:00")
            )
            if parsed_expiry.tzinfo is None:
                parsed_expiry = parsed_expiry.replace(tzinfo=timezone.utc)
        except ValueError:
            parsed_expiry = None
        if parsed_expiry is not None and datetime.now(timezone.utc) >= parsed_expiry:
            raise SubscriptionStructuredOutputError(
                "reauth_required",
                "The Claude subscription token has expired; import it again from Settings.",
            )

    config_dir = tempfile.mkdtemp(prefix="ark_claude_structured_")
    agen = None
    transport = None
    child_pid = None
    try:
        selected_effort = None if effort in ("", "default") else effort
        options = ClaudeAgentOptions(
            model=model,
            effort=selected_effort,
            system_prompt=system,
            output_format={"type": "json_schema", "schema": schema},
            mcp_servers={},
            allowed_tools=[],
            tools=[],
            setting_sources=[],
            strict_mcp_config=True,
            permission_mode="dontAsk",
            # The internal StructuredOutput tool call consumes the first turn;
            # the terminal ResultMessage with structured_output needs a second.
            max_turns=2,
            env={
                **{name: "" for name in _CLAUDE_INHERITED_BILLING_ENV},
                "CLAUDE_CODE_OAUTH_TOKEN": token,
                "CLAUDE_CONFIG_DIR": config_dir,
            },
        )
        transport = _claude_transport(prompt=user, options=options)
        agen = _claude_query(prompt=user, options=options, transport=transport)
        iterator = agen.__aiter__()
        subscription_auth_verified = False
        while True:
            try:
                message = await _next_with_deadline(iterator, deadline)
            except StopAsyncIteration:
                break
            if isinstance(message, SystemMessage):
                if message.subtype == "init":
                    source = (message.data or {}).get("apiKeySource")
                    if source not in (None, "none"):
                        raise SubscriptionStructuredOutputError(
                            "provider_call_failed",
                            "Claude subscription auth is not active "
                            f"(apiKeySource={source!r}); refusing to bill another source.",
                        )
                    subscription_auth_verified = True
                continue
            if isinstance(message, AssistantMessage):
                if getattr(message, "error", None) == "authentication_failed":
                    raise SubscriptionStructuredOutputError(
                        "reauth_required",
                        "Claude subscription authentication failed; import the token again.",
                    )
                for block in message.content or []:
                    if isinstance(block, ToolUseBlock) and block.name == "StructuredOutput":
                        continue
                    if isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                        raise SubscriptionStructuredOutputError(
                            "provider_call_failed",
                            "Claude subscription attempted an unexpected tool call.",
                        )
                continue
            if not isinstance(message, ResultMessage):
                continue
            if not subscription_auth_verified:
                raise SubscriptionStructuredOutputError(
                    "provider_call_failed",
                    "Claude subscription result arrived without verified auth source evidence.",
                )
            if message.is_error or message.subtype == "error":
                detail = message.result or message.errors or "Claude subscription returned an error."
                raise SubscriptionStructuredOutputError(
                    "provider_call_failed",
                    _safe_message(RuntimeError(str(detail)), token),
                )
            payload = message.structured_output
            if not isinstance(payload, dict):
                raise SubscriptionStructuredOutputError(
                    "provider_call_failed",
                    "Claude subscription did not return the requested structured output.",
                )
            return payload
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            "Claude subscription stream ended without a structured result.",
        )
    except SubscriptionStructuredOutputError:
        raise
    except asyncio.TimeoutError as exc:
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            f"Claude subscription structured call timed out after {timeout_s:g} seconds.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            _safe_message(exc, token),
        ) from exc
    finally:
        # The pinned SDK can spend 5s on graceful exit and another 5s escalating
        # SIGTERM to SIGKILL. Do not abandon the child after the provider deadline.
        child_pid = _transport_child_pid(transport)
        await _close_quietly(agen, timeout_s=_CLAUDE_SHUTDOWN_TIMEOUT_S)
        await _reap_owned_child(child_pid)
        shutil.rmtree(config_dir, ignore_errors=True)


async def run_subscription_structured_output_async(
    *,
    provider: str,
    auth_mode: str,
    credential_id: str,
    model: str,
    system: str,
    user: str,
    output_name: str,
    output_description: str,
    schema: dict[str, Any],
    effort: str = "default",
    token_store: Any = None,
    timeout_s: float,
) -> dict[str, Any]:
    """Execute one deadline-bound subscription result without fallback."""
    openai_oauth = provider == "openai" and auth_mode == "chatgpt_oauth"
    claude_oauth = provider == "anthropic" and auth_mode == "claude_code_oauth"
    if not (openai_oauth or claude_oauth):
        raise SubscriptionStructuredOutputError(
            "task_auth_mode_unsupported",
            f"Subscription structured output is not wired for {provider}/{auth_mode}.",
        )
    token_store = token_store or get_token_store()
    if openai_oauth:
        return await _openai_structured_output_async(
            credential_id=credential_id,
            model=model,
            system=system,
            user=user,
            output_name=output_name,
            output_description=output_description,
            schema=schema,
            effort=effort,
            token_store=token_store,
            timeout_s=timeout_s,
        )
    if claude_oauth:
        return await _claude_structured_output_async(
            credential_id=credential_id,
            model=model,
            system=system,
            user=user,
            schema=schema,
            effort=effort,
            token_store=token_store,
            timeout_s=timeout_s,
        )
    raise AssertionError("validated subscription auth mode was not dispatched")


def run_subscription_structured_output(
    *,
    provider: str,
    auth_mode: str,
    credential_id: str,
    model: str,
    system: str,
    user: str,
    output_name: str,
    output_description: str,
    schema: dict[str, Any],
    effort: str = "default",
    token_store: Any = None,
    timeout_s: float,
) -> dict[str, Any]:
    """Synchronous facade for FastAPI worker-thread card routes."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_subscription_structured_output_async(
                provider=provider,
                auth_mode=auth_mode,
                credential_id=credential_id,
                model=model,
                system=system,
                user=user,
                output_name=output_name,
                output_description=output_description,
                schema=schema,
                effort=effort,
                token_store=token_store,
                timeout_s=timeout_s,
            )
        )
    raise RuntimeError(
        "run_subscription_structured_output cannot run inside an active event loop; "
        "await run_subscription_structured_output_async instead"
    )
