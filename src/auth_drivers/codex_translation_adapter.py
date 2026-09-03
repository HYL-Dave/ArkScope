"""Single-turn structured translation over the bundled Codex app-server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from src.auth_drivers.codex_app_server_runtime import (
    CodexAppServerRuntimeError,
    CodexAuthenticatedContext,
    CodexJsonlSession,
    run_authenticated_codex_operation,
)
from src.subscription_plan import normalize_subscription_plan


SPARK_MODEL = "gpt-5.3-codex-spark"
_SPARK_EFFORTS = frozenset({"low", "medium", "high", "xhigh"})
_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_MAX_STDOUT_BYTES = 16 * 1024 * 1024
_MAX_STDERR_BYTES = 256 * 1024
_ALLOWED_NOTIFICATIONS = frozenset(
    {
        "item/agentMessage/delta",
        "item/completed",
        "item/started",
        "thread/started",
        "turn/completed",
        "turn/started",
    }
)
_SAFE_ITEM_TYPES = frozenset({"agentMessage", "reasoning", "userMessage"})
_TOOL_ITEM_TYPES = frozenset(
    {
        "collabAgentToolCall",
        "commandExecution",
        "dynamicToolCall",
        "fileChange",
        "imageGeneration",
        "imageView",
        "mcpToolCall",
        "subAgentActivity",
        "webSearch",
    }
)


PROTOCOL_PROJECTION = {
    "allowed_notifications": sorted(_ALLOWED_NOTIFICATIONS),
    "requests": {
        "account/login/start": [
            "accessToken",
            "chatgptAccountId",
            "chatgptPlanType",
            "type",
        ],
        "account/read": ["refreshToken"],
        "initialize": ["capabilities", "clientInfo"],
        "model/list": ["cursor", "includeHidden", "limit"],
        "thread/start": [
            "allowProviderModelFallback",
            "approvalPolicy",
            "approvalsReviewer",
            "baseInstructions",
            "cwd",
            "developerInstructions",
            "dynamicTools",
            "environments",
            "ephemeral",
            "model",
            "runtimeWorkspaceRoots",
            "sandbox",
            "selectedCapabilityRoots",
        ],
        "turn/start": [
            "effort",
            "input",
            "outputSchema",
            "sandboxPolicy",
            "threadId",
        ],
    },
    "responses": {
        "account/login/start": ["type"],
        "account/read": ["account", "requiresOpenaiAuth"],
        "initialize": ["codexHome"],
        "model/list": ["data", "nextCursor"],
        "thread/start": [
            "approvalPolicy",
            "approvalsReviewer",
            "cwd",
            "instructionSources",
            "model",
            "modelProvider",
            "reasoningEffort",
            "runtimeWorkspaceRoots",
            "sandbox",
            "thread",
        ],
        "turn/start": ["turn"],
    },
    "notification_fields": {
        "item/agentMessage/delta": ["delta", "itemId", "threadId", "turnId"],
        "item/completed": ["item", "threadId", "turnId"],
        "item/started": ["item", "threadId", "turnId"],
        "thread/started": ["thread"],
        "turn/completed": ["threadId", "turn"],
        "turn/started": ["threadId", "turn"],
    },
    "nested_fields": {
        "account": ["planType", "type"],
        "agent_message": ["id", "text", "type"],
        "model": ["model"],
        "sandbox_policy": ["networkAccess", "type"],
        "thread": ["cwd", "ephemeral", "id", "modelProvider", "parentThreadId"],
        "turn": ["error", "id", "status"],
    },
}


class CodexTranslationError(RuntimeError):
    """Closed translation-adapter failure safe for higher-level mapping."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str) -> CodexTranslationError:
    return CodexTranslationError(code)


def _require_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("protocol_incompatible")
    return value


def _require_identifier(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise _fail("protocol_incompatible")
    return value


def _require_plan(value: Any) -> str:
    normalized = normalize_subscription_plan(value)
    if normalized is None:
        raise _fail("subscription_plan_unverified")
    if normalized != "pro":
        raise _fail("subscription_plan_required")
    return "pro"


def _require_exact_model(models: dict[str, Any], model: str) -> None:
    rows = models.get("data")
    if not isinstance(rows, list):
        raise _fail("protocol_incompatible")
    discovered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise _fail("protocol_incompatible")
        value = row.get("model")
        if not isinstance(value, str) or not value or len(value) > 256:
            raise _fail("protocol_incompatible")
        discovered.append(value)
    cursor = models.get("nextCursor")
    if cursor is not None and not isinstance(cursor, str):
        raise _fail("protocol_incompatible")
    if model not in discovered:
        raise _fail("model_unavailable")


def _thread_identity(thread: Any, *, cwd: str) -> str:
    row = _require_mapping(thread)
    thread_id = _require_identifier(row.get("id"))
    if (
        row.get("cwd") != cwd
        or row.get("ephemeral") is not True
        or row.get("modelProvider") != "openai"
        or row.get("parentThreadId") is not None
    ):
        raise _fail("protocol_incompatible")
    return thread_id


def _validate_thread_response(
    result: dict[str, Any],
    *,
    cwd: str,
    model: str,
) -> str:
    if (
        result.get("approvalPolicy") != "never"
        or result.get("approvalsReviewer") != "user"
        or result.get("cwd") != cwd
        or result.get("model") != model
        or result.get("modelProvider") != "openai"
        or result.get("instructionSources") != []
        or result.get("runtimeWorkspaceRoots") != []
        or result.get("sandbox")
        != {"type": "readOnly", "networkAccess": False}
    ):
        raise _fail("protocol_incompatible")
    return _thread_identity(result.get("thread"), cwd=cwd)


def _validate_thread_started(
    notification: dict[str, Any],
    *,
    expected_id: str,
    cwd: str,
) -> None:
    if notification.get("method") != "thread/started":
        raise _fail("protocol_incompatible")
    params = _require_mapping(notification.get("params"))
    observed_id = _thread_identity(params.get("thread"), cwd=cwd)
    if observed_id != expected_id:
        raise _fail("protocol_incompatible")


def _validate_turn_start(result: dict[str, Any]) -> str:
    turn = _require_mapping(result.get("turn"))
    turn_id = _require_identifier(turn.get("id"))
    if turn.get("status") != "inProgress" or turn.get("items") != []:
        raise _fail("protocol_incompatible")
    return turn_id


def _validate_event_identity(
    params: dict[str, Any],
    *,
    thread_id: str,
    turn_id: str,
) -> None:
    if params.get("threadId") != thread_id:
        raise _fail("protocol_incompatible")
    observed_turn = params.get("turnId")
    if observed_turn is None:
        turn = _require_mapping(params.get("turn"))
        observed_turn = turn.get("id")
    if observed_turn != turn_id:
        raise _fail("protocol_incompatible")


def _turn_error_code(turn: dict[str, Any]) -> str:
    error = turn.get("error")
    info = error.get("codexErrorInfo") if isinstance(error, dict) else None
    if info == "contextWindowExceeded":
        return "context_window_exceeded"
    if info == "usageLimitExceeded":
        return "subscription_usage_unavailable"
    if info == "unauthorized":
        return "reauth_required"
    return "provider_call_failed"


def _validate_output(payload: Any, schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(payload)
    except (SchemaError, ValidationError):
        raise _fail("structured_output_invalid") from None


def _parse_output(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(
            text,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        raise _fail("structured_output_invalid") from None
    if not isinstance(payload, dict):
        raise _fail("structured_output_invalid")
    _validate_output(payload, schema)
    return payload


def _run_turn(
    session: CodexJsonlSession,
    context: CodexAuthenticatedContext,
    *,
    model: str,
    effort: str,
    system: str,
    user: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    _require_plan(context.plan_type)
    models = session.request(
        4,
        "model/list",
        {"cursor": None, "includeHidden": True, "limit": 100},
    )
    _require_exact_model(models, model)

    cwd_path = context.codex_home / "translation-workspace"
    cwd_path.mkdir(mode=0o700)
    cwd = str(cwd_path)
    thread_result = session.request(
        5,
        "thread/start",
        {
            "allowProviderModelFallback": False,
            "approvalPolicy": "never",
            "approvalsReviewer": "user",
            "baseInstructions": system,
            "cwd": cwd,
            "developerInstructions": None,
            "dynamicTools": [],
            "environments": [],
            "ephemeral": True,
            "model": model,
            "runtimeWorkspaceRoots": [],
            "sandbox": "read-only",
            "selectedCapabilityRoots": [],
        },
    )
    thread_id = _validate_thread_response(thread_result, cwd=cwd, model=model)
    _validate_thread_started(
        session.next_notification(),
        expected_id=thread_id,
        cwd=cwd,
    )
    if any(cwd_path.iterdir()):
        raise _fail("protocol_incompatible")

    turn_result = session.request(
        6,
        "turn/start",
        {
            "effort": effort,
            "input": [{"type": "text", "text": user}],
            "outputSchema": schema,
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            "threadId": thread_id,
        },
    )
    turn_id = _validate_turn_start(turn_result)
    final_messages: list[str] = []
    saw_started = False
    while True:
        notification = session.next_notification()
        method = notification.get("method")
        params = _require_mapping(notification.get("params"))
        if method == "turn/started":
            if saw_started:
                raise _fail("protocol_incompatible")
            _validate_event_identity(
                params,
                thread_id=thread_id,
                turn_id=turn_id,
            )
            turn = _require_mapping(params.get("turn"))
            if turn.get("status") != "inProgress":
                raise _fail("protocol_incompatible")
            saw_started = True
            continue
        if method in {"item/started", "item/completed"}:
            _validate_event_identity(
                params,
                thread_id=thread_id,
                turn_id=turn_id,
            )
            item = _require_mapping(params.get("item"))
            item_type = item.get("type")
            if item_type in _TOOL_ITEM_TYPES:
                raise _fail("unexpected_tool_activity")
            if item_type not in _SAFE_ITEM_TYPES:
                raise _fail("protocol_incompatible")
            if method == "item/completed" and item_type == "agentMessage":
                text = item.get("text")
                if not isinstance(text, str):
                    raise _fail("protocol_incompatible")
                final_messages.append(text)
                if len(final_messages) > 1:
                    raise _fail("structured_output_invalid")
            continue
        if method == "item/agentMessage/delta":
            _validate_event_identity(
                params,
                thread_id=thread_id,
                turn_id=turn_id,
            )
            if not isinstance(params.get("itemId"), str) or not isinstance(
                params.get("delta"), str
            ):
                raise _fail("protocol_incompatible")
            continue
        if method != "turn/completed":
            raise _fail("protocol_incompatible")
        _validate_event_identity(
            params,
            thread_id=thread_id,
            turn_id=turn_id,
        )
        turn = _require_mapping(params.get("turn"))
        if turn.get("status") != "completed":
            raise _fail(_turn_error_code(turn))
        if not saw_started:
            raise _fail("protocol_incompatible")
        if not final_messages:
            raise _fail("structured_output_missing")
        if any(cwd_path.iterdir()):
            raise _fail("unexpected_tool_activity")
        return _parse_output(final_messages[0], schema)


def run_codex_translation(
    *,
    credential_id: str,
    record: Any,
    model: str,
    effort: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    timeout_s: float,
    executable: str | Path | None = None,
    plan_observer: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run one exact-model translation without retry or transport fallback."""
    if not isinstance(credential_id, str) or not credential_id or len(credential_id) > 512:
        raise _fail("adapter_unavailable")
    if model != SPARK_MODEL:
        raise _fail("model_unavailable")
    if effort not in _SPARK_EFFORTS:
        raise _fail("model_effort_unsupported")
    if not isinstance(system, str) or not isinstance(user, str):
        raise _fail("structured_output_invalid")
    if not isinstance(schema, dict):
        raise _fail("structured_output_invalid")
    stored_plan = normalize_subscription_plan(getattr(record, "plan_type", None))
    if stored_plan is not None:
        _require_plan(stored_plan)
    elif plan_observer is None:
        raise _fail("subscription_plan_unverified")

    def operation(session: CodexJsonlSession, context: CodexAuthenticatedContext):
        if plan_observer is not None:
            plan_observer(context.plan_type)
        return _run_turn(
            session,
            context,
            model=model,
            effort=effort,
            system=system,
            user=user,
            schema=schema,
        )

    try:
        _, result = run_authenticated_codex_operation(
            record=record,
            client_name="arkscope-translation",
            timeout_seconds=timeout_s,
            executable=executable,
            allowed_notifications=_ALLOWED_NOTIFICATIONS,
            operation=operation,
            max_request_bytes=_MAX_REQUEST_BYTES,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
        )
        return result
    except CodexTranslationError:
        raise
    except CodexAppServerRuntimeError as exc:
        if exc.code == "account_plan_unavailable":
            raise _fail("subscription_plan_unverified") from None
        raise _fail(exc.code) from None
