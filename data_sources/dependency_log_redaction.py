"""Context-scoped redaction for credential-bearing dependency HTTP logs."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import contextvars
import logging
import threading
from urllib.parse import quote, quote_plus


_LOG_REDACTIONS: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "dependency_http_log_redactions",
    default=(),
)
_LOG_FILTER_LOCK = threading.Lock()


def dependency_log_redaction_values(values: Iterable[object]) -> tuple[str, ...]:
    variants: list[str] = []
    for value in values:
        if value is None:
            continue
        raw = str(value)
        if not raw:
            continue
        variants.extend((raw, quote(raw, safe=""), quote_plus(raw, safe="")))
    return tuple(dict.fromkeys(variants))


def redact_dependency_log_text(detail: str, redactions: Iterable[str]) -> str:
    for value in redactions:
        detail = detail.replace(value, "[redacted]")
    return detail


class _DependencyLogRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        redactions = _LOG_REDACTIONS.get()
        if redactions:
            record.msg = redact_dependency_log_text(record.getMessage(), redactions)
            record.args = ()
        return True


_LOG_REDACTION_FILTER = _DependencyLogRedactionFilter()


def _ensure_dependency_log_redaction_filter() -> None:
    connectionpool_logger = logging.getLogger("urllib3.connectionpool")
    with _LOG_FILTER_LOCK:
        if _LOG_REDACTION_FILTER not in connectionpool_logger.filters:
            connectionpool_logger.addFilter(_LOG_REDACTION_FILTER)


@contextmanager
def dependency_log_redaction(values: Iterable[object]) -> Iterator[tuple[str, ...]]:
    redactions = dependency_log_redaction_values(values)
    if redactions:
        _ensure_dependency_log_redaction_filter()
    active = tuple(dict.fromkeys((*_LOG_REDACTIONS.get(), *redactions)))
    token = _LOG_REDACTIONS.set(active)
    try:
        yield active
    finally:
        _LOG_REDACTIONS.reset(token)


__all__ = [
    "dependency_log_redaction",
    "dependency_log_redaction_values",
    "redact_dependency_log_text",
]
