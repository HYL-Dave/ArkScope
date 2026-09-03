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
    closed_codex_config_overrides,
    run_authenticated_codex_operation,
)


SPARK_MODEL = "gpt-5.3-codex-spark"
_SPARK_EFFORTS = frozenset({"low", "medium", "high", "xhigh"})
_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_MAX_STDOUT_BYTES = 16 * 1024 * 1024
_MAX_STDERR_BYTES = 256 * 1024
_MAX_MODEL_PAGES = 8
_MAX_MODELS = 256
_MAX_PASSIVE_NOTIFICATIONS = 16
_PASSIVE_ACCOUNT_NOTIFICATIONS = frozenset(
    {
        "account/login/completed",
        "account/rateLimits/updated",
        "account/updated",
        "remoteControl/status/changed",
    }
)
_TRANSLATION_NOTIFICATIONS = frozenset(
    {
        "item/agentMessage/delta",
        "item/completed",
        "item/started",
        "thread/started",
        "turn/completed",
        "turn/started",
    }
)
_TURN_TELEMETRY_NOTIFICATIONS = frozenset(
    {
        "item/reasoning/summaryPartAdded",
        "item/reasoning/summaryTextDelta",
        "item/reasoning/textDelta",
        "thread/settings/updated",
        "thread/status/changed",
        "thread/tokenUsage/updated",
    }
)
_TURN_CONTROL_NOTIFICATIONS = frozenset(
    {
        "error",
        "model/rerouted",
        "model/safetyBuffering/updated",
        "model/verification",
        "thread/name/updated",
        "turn/moderationMetadata",
    }
)
_ALLOWED_NOTIFICATIONS = (
    _PASSIVE_ACCOUNT_NOTIFICATIONS
    | _TRANSLATION_NOTIFICATIONS
    | _TURN_TELEMETRY_NOTIFICATIONS
    | _TURN_CONTROL_NOTIFICATIONS
)
_REJECTED_NOTIFICATIONS = {
    "mcpServer/startupStatus/updated": "unexpected_tool_activity",
}
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
            "config",
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
    "rejected_notifications": sorted(_REJECTED_NOTIFICATIONS),
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
        "account/login/completed": [
            "error",
            "loginId",
            "onboardingEntrypoint",
            "success",
        ],
        "account/rateLimits/updated": ["rateLimits"],
        "account/updated": ["authMode", "planType"],
        "error": ["error", "threadId", "turnId", "willRetry"],
        "item/agentMessage/delta": ["delta", "itemId", "threadId", "turnId"],
        "item/completed": ["item", "threadId", "turnId"],
        "item/reasoning/summaryPartAdded": [
            "itemId",
            "summaryIndex",
            "threadId",
            "turnId",
        ],
        "item/reasoning/summaryTextDelta": [
            "delta",
            "itemId",
            "summaryIndex",
            "threadId",
            "turnId",
        ],
        "item/reasoning/textDelta": [
            "contentIndex",
            "delta",
            "itemId",
            "threadId",
            "turnId",
        ],
        "item/started": ["item", "threadId", "turnId"],
        "mcpServer/startupStatus/updated": [
            "error",
            "failureReason",
            "name",
            "status",
            "threadId",
        ],
        "model/rerouted": [
            "fromModel",
            "reason",
            "threadId",
            "toModel",
            "turnId",
        ],
        "model/safetyBuffering/updated": [
            "fasterModel",
            "model",
            "reasons",
            "showBufferingUi",
            "threadId",
            "turnId",
            "useCases",
        ],
        "model/verification": ["threadId", "turnId", "verifications"],
        "remoteControl/status/changed": [
            "environmentId",
            "installationId",
            "serverName",
            "status",
        ],
        "thread/name/updated": ["threadId", "threadName"],
        "thread/settings/updated": ["threadId", "threadSettings"],
        "thread/started": ["thread"],
        "thread/status/changed": ["status", "threadId"],
        "thread/tokenUsage/updated": ["threadId", "tokenUsage", "turnId"],
        "turn/completed": ["threadId", "turn"],
        "turn/moderationMetadata": ["metadata", "threadId", "turnId"],
        "turn/started": ["threadId", "turn"],
    },
    "nested_fields": {
        "account": ["planType", "type"],
        "agent_message": ["id", "text", "type"],
        "error": ["additionalDetails", "codexErrorInfo", "message"],
        "model": ["model"],
        "sandbox_policy": ["networkAccess", "type"],
        "thread": ["cwd", "ephemeral", "id", "modelProvider", "parentThreadId"],
        "thread_settings": [
            "approvalPolicy",
            "approvalsReviewer",
            "cwd",
            "effort",
            "model",
            "modelProvider",
            "sandboxPolicy",
        ],
        "thread_status": ["activeFlags", "type"],
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


def _model_page(models: Any) -> tuple[list[str], str | None]:
    models = _require_mapping(models)
    rows = models.get("data")
    if not isinstance(rows, list) or len(rows) > 100:
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
    if cursor is not None and (
        not isinstance(cursor, str) or not cursor or len(cursor) > 512
    ):
        raise _fail("protocol_incompatible")
    return discovered, cursor


def _require_exact_model(
    session: CodexJsonlSession,
    model: str,
) -> int:
    cursor: str | None = None
    seen_cursors: set[str] = set()
    seen_models: set[str] = set()
    for page_index in range(_MAX_MODEL_PAGES):
        request_id = 4 + page_index
        models = session.request(
            request_id,
            "model/list",
            {"cursor": cursor, "includeHidden": True, "limit": 100},
        )
        page, next_cursor = _model_page(models)
        for discovered_model in page:
            if discovered_model in seen_models:
                raise _fail("protocol_incompatible")
            seen_models.add(discovered_model)
        if len(seen_models) > _MAX_MODELS:
            raise _fail("protocol_incompatible")
        if model in seen_models:
            return request_id + 1
        if next_cursor is None:
            raise _fail("model_unavailable")
        if next_cursor in seen_cursors:
            raise _fail("protocol_incompatible")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise _fail("protocol_incompatible")


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


def _next_translation_notification(
    session: CodexJsonlSession,
) -> dict[str, Any]:
    passive_count = 0
    while True:
        notification = session.next_notification()
        if notification.get("method") not in _PASSIVE_ACCOUNT_NOTIFICATIONS:
            return notification
        passive_count += 1
        if passive_count > _MAX_PASSIVE_NOTIFICATIONS:
            raise _fail("protocol_resource_exhausted")


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


def _require_nonnegative_index(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("protocol_incompatible")


def _require_optional_string(value: Any, *, max_length: int = 512) -> None:
    if value is not None and (
        not isinstance(value, str) or len(value) > max_length
    ):
        raise _fail("protocol_incompatible")


def _require_bounded_strings(value: Any) -> None:
    if not isinstance(value, list) or len(value) > 32:
        raise _fail("protocol_incompatible")
    for item in value:
        if not isinstance(item, str) or len(item) > 512:
            raise _fail("protocol_incompatible")


def _validate_turn_telemetry(
    notification: dict[str, Any],
    *,
    thread_id: str,
    turn_id: str,
    cwd: str,
    model: str,
    effort: str,
) -> bool:
    method = notification.get("method")
    if method not in _TURN_TELEMETRY_NOTIFICATIONS:
        return False
    params = _require_mapping(notification.get("params"))

    if method == "thread/settings/updated":
        if params.get("threadId") != thread_id:
            raise _fail("protocol_incompatible")
        settings = _require_mapping(params.get("threadSettings"))
        if (
            settings.get("approvalPolicy") != "never"
            or settings.get("approvalsReviewer") != "user"
            or settings.get("cwd") != cwd
            or settings.get("effort") != effort
            or settings.get("model") != model
            or settings.get("modelProvider") != "openai"
            or settings.get("sandboxPolicy")
            != {"type": "readOnly", "networkAccess": False}
        ):
            raise _fail("protocol_incompatible")
        return True

    if method == "thread/status/changed":
        if params.get("threadId") != thread_id:
            raise _fail("protocol_incompatible")
        status = _require_mapping(params.get("status"))
        status_type = status.get("type")
        if status_type == "active":
            if status.get("activeFlags") != []:
                raise _fail("unexpected_tool_activity")
        elif status_type == "systemError":
            raise _fail("provider_call_failed")
        elif status_type != "idle":
            raise _fail("protocol_incompatible")
        return True

    _validate_event_identity(params, thread_id=thread_id, turn_id=turn_id)
    if method == "thread/tokenUsage/updated":
        _require_mapping(params.get("tokenUsage"))
        return True

    _require_identifier(params.get("itemId"))
    if method in {
        "item/reasoning/summaryPartAdded",
        "item/reasoning/summaryTextDelta",
    }:
        _require_nonnegative_index(params.get("summaryIndex"))
    else:
        _require_nonnegative_index(params.get("contentIndex"))
    if method != "item/reasoning/summaryPartAdded" and not isinstance(
        params.get("delta"), str
    ):
        raise _fail("protocol_incompatible")
    return True


def _error_info_code(value: Any) -> str:
    if value is None:
        return "provider_call_failed"
    if isinstance(value, str):
        if value == "contextWindowExceeded":
            return "context_window_exceeded"
        if value in {"sessionBudgetExceeded", "usageLimitExceeded"}:
            return "subscription_usage_unavailable"
        if value == "unauthorized":
            return "reauth_required"
        if value in {
            "badRequest",
            "cyberPolicy",
            "internalServerError",
            "other",
            "sandboxError",
            "serverOverloaded",
            "threadRollbackFailed",
        }:
            return "provider_call_failed"
        raise _fail("protocol_incompatible")
    if not isinstance(value, dict) or len(value) != 1:
        raise _fail("protocol_incompatible")
    kind, detail = next(iter(value.items()))
    if kind == "activeTurnNotSteerable":
        detail = _require_mapping(detail)
        if detail.get("turnKind") not in {"review", "compact"}:
            raise _fail("protocol_incompatible")
        return "provider_call_failed"
    if kind not in {
        "httpConnectionFailed",
        "responseStreamConnectionFailed",
        "responseStreamDisconnected",
        "responseTooManyFailedAttempts",
    }:
        raise _fail("protocol_incompatible")
    detail = _require_mapping(detail)
    status = detail.get("httpStatusCode")
    if status is not None and (
        isinstance(status, bool)
        or not isinstance(status, int)
        or not 0 <= status <= 65535
    ):
        raise _fail("protocol_incompatible")
    return "provider_call_failed"


def _error_payload_code(value: Any) -> str:
    error = _require_mapping(value)
    message = error.get("message")
    if not isinstance(message, str):
        raise _fail("protocol_incompatible")
    _require_optional_string(error.get("additionalDetails"), max_length=16_384)
    return _error_info_code(error.get("codexErrorInfo"))


def _validate_turn_control(
    notification: dict[str, Any],
    *,
    thread_id: str,
    turn_id: str,
    model: str,
) -> bool:
    method = notification.get("method")
    if method not in _TURN_CONTROL_NOTIFICATIONS:
        return False
    params = _require_mapping(notification.get("params"))

    if method == "thread/name/updated":
        if params.get("threadId") != thread_id:
            raise _fail("protocol_incompatible")
        _require_optional_string(params.get("threadName"))
        return True

    _validate_event_identity(params, thread_id=thread_id, turn_id=turn_id)
    if method == "turn/moderationMetadata":
        if "metadata" not in params:
            raise _fail("protocol_incompatible")
        return True
    if method == "model/safetyBuffering/updated":
        if params.get("model") != model:
            raise _fail("protocol_incompatible")
        _require_bounded_strings(params.get("reasons"))
        _require_bounded_strings(params.get("useCases"))
        if not isinstance(params.get("showBufferingUi"), bool):
            raise _fail("protocol_incompatible")
        _require_optional_string(params.get("fasterModel"), max_length=256)
        return True
    if method == "model/verification":
        verifications = params.get("verifications")
        if not isinstance(verifications, list) or len(verifications) > 8:
            raise _fail("protocol_incompatible")
        if any(value != "trustedAccessForCyber" for value in verifications):
            raise _fail("protocol_incompatible")
        if verifications:
            raise _fail("model_unavailable")
        return True
    if method == "model/rerouted":
        if (
            params.get("fromModel") != model
            or not isinstance(params.get("toModel"), str)
            or not params.get("toModel")
            or len(params["toModel"]) > 256
            or params.get("reason") != "highRiskCyberActivity"
        ):
            raise _fail("protocol_incompatible")
        raise _fail("model_unavailable")
    if not isinstance(params.get("willRetry"), bool):
        raise _fail("protocol_incompatible")
    raise _fail(_error_payload_code(params.get("error")))


def _turn_error_code(turn: dict[str, Any]) -> str:
    error = turn.get("error")
    if error is None:
        return "provider_call_failed"
    return _error_payload_code(error)


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
    next_request_id = _require_exact_model(session, model)

    cwd_path = context.codex_home / "translation-workspace"
    cwd_path.mkdir(mode=0o700)
    cwd = str(cwd_path)
    thread_result = session.request(
        next_request_id,
        "thread/start",
        {
            "allowProviderModelFallback": False,
            "approvalPolicy": "never",
            "approvalsReviewer": "user",
            "baseInstructions": system,
            "config": closed_codex_config_overrides(),
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
        _next_translation_notification(session),
        expected_id=thread_id,
        cwd=cwd,
    )
    if any(cwd_path.iterdir()):
        raise _fail("protocol_incompatible")

    turn_result = session.request(
        next_request_id + 1,
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
        notification = _next_translation_notification(session)
        method = notification.get("method")
        params = _require_mapping(notification.get("params"))
        if _validate_turn_telemetry(
            notification,
            thread_id=thread_id,
            turn_id=turn_id,
            cwd=cwd,
            model=model,
            effort=effort,
        ):
            continue
        if _validate_turn_control(
            notification,
            thread_id=thread_id,
            turn_id=turn_id,
            model=model,
        ):
            continue
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
    def operation(session: CodexJsonlSession, context: CodexAuthenticatedContext):
        if plan_observer is not None and context.plan_type is not None:
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
            rejected_notifications=_REJECTED_NOTIFICATIONS,
            operation=operation,
            max_request_bytes=_MAX_REQUEST_BYTES,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
        )
        return result
    except CodexTranslationError:
        raise
    except CodexAppServerRuntimeError as exc:
        raise _fail(exc.code) from None
