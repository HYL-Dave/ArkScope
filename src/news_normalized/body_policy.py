"""Pure preparation and deterministic ranking for normalized news bodies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Iterable, Optional

from .cleaner import clean_news_body
from .identity import normalize_timestamp


@dataclass(frozen=True)
class PreparedBody:
    body_sha256: str
    raw_body: str
    raw_format: Optional[str]
    body_text: Optional[str]
    cleaner_version: Optional[str]
    clean_error: Optional[str] = None
    retrieval_method: Optional[str] = None
    retrieval_source: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None
    evidence_ref: Optional[str] = None


def prepare_body(
    raw_body: str,
    *,
    raw_format: Optional[str],
    source: str,
    retrieval_method: Optional[str] = None,
    retrieval_source: Optional[str] = None,
    source_url: Optional[str] = None,
    fetched_at: Optional[str] = None,
    evidence_ref: Optional[str] = None,
) -> PreparedBody:
    """Preserve raw evidence and deterministically derive searchable text."""
    if not raw_body:
        raise ValueError("fetched body requires non-empty raw_body")
    digest = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()
    body_text = None
    cleaner_version = None
    clean_error = None
    try:
        cleaned = clean_news_body(raw_body, raw_format=raw_format, source=source)
        body_text = cleaned.text
        cleaner_version = cleaned.version
    except Exception as exc:  # raw evidence must survive cleaner failure
        clean_error = str(exc)
    return PreparedBody(
        body_sha256=digest,
        raw_body=raw_body,
        raw_format=raw_format,
        body_text=body_text,
        cleaner_version=cleaner_version,
        clean_error=clean_error,
        retrieval_method=retrieval_method,
        retrieval_source=retrieval_source,
        source_url=source_url,
        fetched_at=fetched_at,
        evidence_ref=evidence_ref,
    )


def _timestamp_rank(value: Optional[str]) -> float:
    normalized = normalize_timestamp(value or "")
    if not normalized:
        return float("-inf")
    parseable = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError:
        return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _selection_key(item: PreparedBody) -> tuple:
    return (
        -(1 if item.body_text else 0),
        -len(item.body_text or ""),
        -len(item.raw_body),
        -_timestamp_rank(item.fetched_at),
        item.body_sha256,
    )


def choose_active_body(items: Iterable[PreparedBody]) -> PreparedBody:
    unique = {item.body_sha256: item for item in items}
    if not unique:
        raise ValueError("at least one body is required")
    return min(unique.values(), key=_selection_key)
