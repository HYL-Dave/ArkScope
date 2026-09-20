"""Strict public error classification for server-owned AI Research runs."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from src.auth_drivers.runtime_binding import RuntimeAuthBinding, sanitize_runtime_error


# Existing run rows retain their public codes; SEC admission now belongs to
# the SEC tool, not a global gate before every Research provider request.
_LEGACY_SEC_ADMISSION_CODES = frozenset({
    "sec_research_operation_busy", "capture_platform_unsupported", "capture_path_unsafe",
    "sec_research_operation_invalid", "storage_space_insufficient", "capture_store_write_failed",
})


RESEARCH_ERROR_CODES = frozenset(
    {
        "reauth_required",
        "missing_credential",
        "model_refusal",
        "model_timeout",
        "tool_limit_reached",
        "provider_call_failed",
        "run_cancelled",
        "run_interrupted",
        "run_persistence_failed",
        "run_completion_unverified",
        *_LEGACY_SEC_ADMISSION_CODES,
    }
)

_ANTHROPIC_TOOL_LIMIT = "Maximum tool calls reached. Please try a simpler query."
_OPENAI_TOOL_LIMIT_PREFIX = "MaxTurnsExceeded:"
_CHATGPT_TOOL_LIMIT = re.compile(r"Reached maximum number of turns \(\d+\)\Z")
_OWNED_TIMEOUTS = tuple(
    re.compile(pattern)
    for pattern in (
        r"ChatGPT OAuth driver timed out after \d+(?:\.\d+)?s\Z",
        r"claude agent-sdk timed out after \d+(?:\.\d+)?s\Z",
        r"claude -p timed out after \d+(?:\.\d+)?s\Z",
    )
)
_DIRECT_TIMEOUT_PREFIXES = ("APITimeoutError:", "TimeoutError:")


@dataclass(frozen=True)
class ResearchFailure:
    code: str
    detail: str


RUN_PERSISTENCE_FAILURE = ResearchFailure(
    "run_persistence_failed",
    "Research output could not be saved locally. Check local storage before continuing. "
    "The model request has not been sent again.",
)
RUN_COMPLETION_UNVERIFIED = ResearchFailure(
    "run_completion_unverified",
    "The saved research records do not establish a complete result. "
    "Existing output has been retained without claiming completion.",
)


class ResearchRunPersistenceError(RuntimeError):
    """A local write failed; never reclassify it as a provider failure."""

    def __init__(self):
        super().__init__(RUN_PERSISTENCE_FAILURE.code)


def sanitize_research_detail(value: Any, *, binding: RuntimeAuthBinding | None = None) -> str:
    """Return the bounded, redacted detail allowed in durable/public state."""
    return sanitize_runtime_error(value, binding=binding)


def public_research_error_code(value: Any) -> str | None:
    return value if isinstance(value, str) and value in RESEARCH_ERROR_CODES else None


def require_research_error_code(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in RESEARCH_ERROR_CODES:
        raise ValueError(f"unsupported research error code: {value}")
    return value


def _exception_chain_contains_timeout(value: Any) -> bool:
    if not isinstance(value, BaseException):
        return False
    seen: set[int] = set()
    current: BaseException | None = value
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (asyncio.TimeoutError, TimeoutError)):
            return True
        if type(current).__name__ == "APITimeoutError" and type(current).__module__.split(".")[0] in {
            "openai",
            "anthropic",
        }:
            return True
        current = current.__cause__ or current.__context__
    return False


def _code_from_exact_shape(detail: str) -> str:
    if (
        detail == _ANTHROPIC_TOOL_LIMIT
        or detail.startswith(_OPENAI_TOOL_LIMIT_PREFIX)
        or _CHATGPT_TOOL_LIMIT.fullmatch(detail) is not None
    ):
        return "tool_limit_reached"
    if detail.startswith(_DIRECT_TIMEOUT_PREFIXES) or any(
        pattern.fullmatch(detail) is not None for pattern in _OWNED_TIMEOUTS
    ):
        return "model_timeout"
    return "provider_call_failed"


def classify_research_failure(
    value: Any,
    *,
    explicit_code: Any = None,
    binding: RuntimeAuthBinding | None = None,
) -> ResearchFailure:
    """Classify only reviewed types/shapes; unknown prose stays generic."""
    try:
        shape = value if isinstance(value, str) else str(value)
    except Exception:  # a hostile __str__ is never allowed to escape
        shape = ""
    detail = sanitize_research_detail(value, binding=binding) or "research run failed"
    code = public_research_error_code(explicit_code)
    if code in {RUN_PERSISTENCE_FAILURE.code, RUN_COMPLETION_UNVERIFIED.code}:
        code = None  # Only local storage/recovery can attest these states.
    if code is None:
        code = (
            "model_timeout"
            if _exception_chain_contains_timeout(value)
            else _code_from_exact_shape(shape)
        )
    return ResearchFailure(code=code, detail=detail)
