"""Derived NEWS body availability shared by Python and SQL read paths."""

from __future__ import annotations

from typing import Literal

ContentAvailability = Literal["full", "headline_only", "unknown"]
ContentRecovery = Literal["retryable", "terminal"]
ContentFilter = Literal["all", "full", "headline_only", "unknown"]

RECOVERY_CAPABLE_BODY_SOURCES = frozenset({"ibkr"})

_FETCHED_BODY_STATUSES = frozenset({"fetched"})
_RETRYABLE_BODY_STATUSES = frozenset({"pending", "failed"})
_TERMINAL_BODY_STATUSES = frozenset({"empty", "unavailable", "expired"})
_HEADLINE_ONLY_BODY_STATUSES = (
    _RETRYABLE_BODY_STATUSES | _TERMINAL_BODY_STATUSES
)


def classify_news_content(
    body_status: str | None,
    source: str | None,
) -> tuple[ContentAvailability, ContentRecovery | None]:
    if body_status in _FETCHED_BODY_STATUSES:
        return "full", None
    if body_status in _RETRYABLE_BODY_STATUSES:
        recovery: ContentRecovery = (
            "retryable" if source in RECOVERY_CAPABLE_BODY_SOURCES else "terminal"
        )
        return "headline_only", recovery
    if body_status in _TERMINAL_BODY_STATUSES:
        return "headline_only", "terminal"
    return "unknown", None


def _sql_values(values: frozenset[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in sorted(values))


def news_content_sql(
    body_status_sql: str,
    source_sql: str,
) -> tuple[str, str]:
    """Return CASE expressions for trusted internal SQL column expressions."""

    fetched = _sql_values(_FETCHED_BODY_STATUSES)
    headline_only = _sql_values(_HEADLINE_ONLY_BODY_STATUSES)
    retryable = _sql_values(_RETRYABLE_BODY_STATUSES)
    terminal = _sql_values(_HEADLINE_ONLY_BODY_STATUSES)
    recovery_sources = _sql_values(RECOVERY_CAPABLE_BODY_SOURCES)

    availability_sql = (
        "CASE "
        f"WHEN {body_status_sql} IN ({fetched}) THEN 'full' "
        f"WHEN {body_status_sql} IN ({headline_only}) THEN 'headline_only' "
        "ELSE 'unknown' END"
    )
    recovery_sql = (
        "CASE "
        f"WHEN {body_status_sql} IN ({retryable}) "
        f"AND {source_sql} IN ({recovery_sources}) THEN 'retryable' "
        f"WHEN {body_status_sql} IN ({terminal}) THEN 'terminal' "
        "ELSE NULL END"
    )
    return availability_sql, recovery_sql


def empty_content_counts() -> dict[str, int]:
    return {"full": 0, "headline_only": 0, "unknown": 0}
