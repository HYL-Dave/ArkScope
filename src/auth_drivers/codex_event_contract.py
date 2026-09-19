"""Closed Codex app-server event contracts used by lifecycle investigation."""

from __future__ import annotations

from typing import Any


_PASSIVE_ACCOUNT_NOTIFICATIONS = frozenset(
    {
        "account/login/completed",
        "account/rateLimits/updated",
        "account/updated",
        "remoteControl/status/changed",
    }
)


_TURN_NOTIFICATIONS = frozenset(
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
    | _TURN_NOTIFICATIONS
    | _TURN_TELEMETRY_NOTIFICATIONS
    | _TURN_CONTROL_NOTIFICATIONS
)


_REJECTED_NOTIFICATIONS = {
    "mcpServer/startupStatus/updated": "unexpected_tool_activity",
}


class CodexEventError(RuntimeError):
    """Closed event-contract failure safe for higher-level mapping."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str) -> CodexEventError:
    return CodexEventError(code)


def _require_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("protocol_incompatible")
    return value


def _require_identifier(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise _fail("protocol_incompatible")
    return value


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
