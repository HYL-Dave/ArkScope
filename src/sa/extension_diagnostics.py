"""Validation and durable projection for SA extension diagnostics."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from src.sa.extension_run_protocol import REASON_CODES


SCHEMA_VERSION = 1
MAX_ENTRIES = 32
MAX_OMITTED_COUNT = 10_000
MAX_MESSAGE_LENGTH = 240
MAX_CANONICAL_BYTES = 32 * 1024

STAGES = frozenset(
    {
        "tab_navigation",
        "page_readiness",
        "script_injection",
        "content_parse",
        "native_transport",
        "local_persistence",
        "reconciliation",
        "extension_runtime",
    }
)
TARGET_KINDS = frozenset(
    {"article_detail", "article_comments", "market_news_detail", "phase"}
)
DIAGNOSTIC_ONLY_REASON_CODES = frozenset(
    {
        "tab_closed",
        "browser_api_failed",
        "script_injection_failed",
        "native_response_invalid",
        "database_busy",
        "database_integrity_failed",
        "database_write_failed",
    }
)

_NON_FAILURE_REASON_CODES = frozenset(
    {
        "body_saved",
        "body_present_at_freeze",
        "body_present_during_run",
        "source_http_404",
        "source_http_410",
        "source_removed_marker",
        "not_due",
        "already_pending",
        "operator_cancelled",
        "telemetry_unavailable",
    }
)
REASON_CODES_FOR_DIAGNOSTICS = (
    REASON_CODES - _NON_FAILURE_REASON_CODES
) | DIAGNOSTIC_ONLY_REASON_CODES

_ENVELOPE_KEYS = frozenset({"schema_version", "entries", "omitted_count"})
_ENTRY_REQUIRED_KEYS = frozenset(
    {
        "occurred_at",
        "stage",
        "reason_code",
        "target_kind",
        "retryable",
        "attempt_count",
    }
)
_ENTRY_OPTIONAL_KEYS = frozenset({"target_ref", "message"})
_TARGET_REF_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PROHIBITED_TEXT_PATTERNS = (
    re.compile(r"(?:https?|file)://|\bwww\.", re.IGNORECASE),
    re.compile(r"\?[A-Za-z0-9_.%-]+="),
    _EMAIL_RE,
    re.compile(
        r"\b(?:authorization|bearer|cookie|set-cookie|api[_ -]?key|"
        r"access[_ -]?token|refresh[_ -]?token)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?:^|\s)(?:/[A-Za-z0-9._-]+){2,}(?:/|\b)"),
    re.compile(r"\b[A-Za-z]:\\(?:[^\\\s]+\\)+", re.IGNORECASE),
    re.compile(
        r"\b(?:select\s+.+\s+from|insert\s+into|update\s+\w+\s+set|"
        r"delete\s+from|create\s+table|drop\s+table)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btraceback\b|\bFile \".+\", line \d+", re.IGNORECASE),
    re.compile(r"<[^>]+>"),
)

_REJECTED_PROJECTION = {
    "status": "rejected",
    "error_code": "invalid_extension_diagnostics",
}


class _InvalidDiagnostics(ValueError):
    pass


def _parse_aware_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise _InvalidDiagnostics
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _InvalidDiagnostics from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise _InvalidDiagnostics
    return parsed.astimezone(timezone.utc)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _contains_prohibited_text(value: str) -> bool:
    return any(pattern.search(value) for pattern in _PROHIBITED_TEXT_PATTERNS)


def _contains_prohibited_content(value: Any) -> bool:
    if isinstance(value, str):
        return _contains_prohibited_text(value)
    if isinstance(value, Mapping):
        return any(
            _contains_prohibited_content(key) or _contains_prohibited_content(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_prohibited_content(item) for item in value)
    return False


def _validate_entry(raw: Any, *, started: datetime, finished: datetime) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _InvalidDiagnostics
    keys = frozenset(raw)
    if not _ENTRY_REQUIRED_KEYS.issubset(keys) or not keys.issubset(
        _ENTRY_REQUIRED_KEYS | _ENTRY_OPTIONAL_KEYS
    ):
        raise _InvalidDiagnostics

    occurred = _parse_aware_utc(raw["occurred_at"])
    if occurred < started or occurred > finished:
        raise _InvalidDiagnostics
    stage = raw["stage"]
    reason_code = raw["reason_code"]
    target_kind = raw["target_kind"]
    retryable = raw["retryable"]
    attempt_count = raw["attempt_count"]
    if stage not in STAGES:
        raise _InvalidDiagnostics
    if reason_code not in REASON_CODES_FOR_DIAGNOSTICS:
        raise _InvalidDiagnostics
    if target_kind not in TARGET_KINDS:
        raise _InvalidDiagnostics
    if not isinstance(retryable, bool):
        raise _InvalidDiagnostics
    if not _is_int(attempt_count) or not 1 <= attempt_count <= 1000:
        raise _InvalidDiagnostics

    projected: dict[str, Any] = {
        "occurred_at": occurred.isoformat(timespec="milliseconds"),
        "stage": stage,
        "reason_code": reason_code,
        "target_kind": target_kind,
        "retryable": retryable,
        "attempt_count": attempt_count,
    }
    if "target_ref" in raw:
        target_ref = raw["target_ref"]
        if not isinstance(target_ref, str) or not _TARGET_REF_RE.fullmatch(target_ref):
            raise _InvalidDiagnostics
        projected["target_ref"] = target_ref
    if "message" in raw:
        message = raw["message"]
        if (
            not isinstance(message, str)
            or not message
            or len(message) > MAX_MESSAGE_LENGTH
            or _contains_prohibited_text(message)
        ):
            raise _InvalidDiagnostics
        projected["message"] = message
    return projected


def project_extension_diagnostics(
    raw: Any,
    *,
    started_at: Any,
    finished_at: Any,
) -> dict[str, Any]:
    """Return a recorded projection or one fixed rejection marker."""

    try:
        if not isinstance(raw, Mapping) or frozenset(raw) != _ENVELOPE_KEYS:
            raise _InvalidDiagnostics
        if (
            not _is_int(raw["schema_version"])
            or raw["schema_version"] != SCHEMA_VERSION
        ):
            raise _InvalidDiagnostics
        entries = raw["entries"]
        omitted_count = raw["omitted_count"]
        if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
            raise _InvalidDiagnostics
        if (
            not _is_int(omitted_count)
            or not 0 <= omitted_count <= MAX_OMITTED_COUNT
        ):
            raise _InvalidDiagnostics
        if _contains_prohibited_content(raw):
            raise _InvalidDiagnostics
        started = _parse_aware_utc(started_at)
        finished = _parse_aware_utc(finished_at)
        if finished < started:
            raise _InvalidDiagnostics
        projection = {
            "status": "recorded",
            "schema_version": SCHEMA_VERSION,
            "entries": [
                _validate_entry(entry, started=started, finished=finished)
                for entry in entries
            ],
            "omitted_count": omitted_count,
        }
        encoded = json.dumps(
            projection,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_CANONICAL_BYTES:
            raise _InvalidDiagnostics
        return projection
    except (KeyError, TypeError, ValueError):
        return dict(_REJECTED_PROJECTION)


def is_durable_diagnostics_projection(value: Any) -> bool:
    """Validate the closed projection boundary accepted by the local store."""

    if not isinstance(value, dict):
        return False
    status = value.get("status")
    if status == "absent":
        return set(value) == {"status"}
    if status == "rejected":
        return value == _REJECTED_PROJECTION
    if status != "recorded" or set(value) != {
        "status",
        "schema_version",
        "entries",
        "omitted_count",
    }:
        return False
    if value.get("schema_version") != SCHEMA_VERSION:
        return False
    entries = value.get("entries")
    omitted_count = value.get("omitted_count")
    return (
        isinstance(entries, list)
        and len(entries) <= MAX_ENTRIES
        and _is_int(omitted_count)
        and 0 <= omitted_count <= MAX_OMITTED_COUNT
        and len(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        <= MAX_CANONICAL_BYTES
    )


__all__ = [
    "DIAGNOSTIC_ONLY_REASON_CODES",
    "MAX_CANONICAL_BYTES",
    "MAX_ENTRIES",
    "REASON_CODES_FOR_DIAGNOSTICS",
    "STAGES",
    "TARGET_KINDS",
    "is_durable_diagnostics_projection",
    "project_extension_diagnostics",
]
