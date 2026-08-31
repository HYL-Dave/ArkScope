"""Atomic persistence kernel for trusted lifecycle evidence and cited facts."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.security_lifecycle_investigation import (
    SecurityLifecycleInvestigationStore,
    evidence_rows_sha256,
)
from src.security_lifecycle_schema import (
    ACTION_READINESS,
    AUTOMATION_BLOCKER_CODES,
    AUTOMATION_FAILURE_CODES,
    AUTOMATION_MODES,
    DECISION_TIERS,
    EVIDENCE_ADAPTERS,
    EVIDENCE_KINDS,
    EVIDENCE_SOURCE_FAMILIES,
    FACT_SCALAR_TYPES,
    FACT_TYPES,
    TRANSACTION_STRUCTURE_KINDS,
    TRANSACTION_TERMS_STATUSES,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_EXECUTION_OWNER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_CIK = re.compile(r"^\d{10}$")
_DECIMAL = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
_ADAPTER_SHAPES = {
    "sec_edgar": ("regulator", "regulator_excerpt"),
    "internal_news": ("publisher", "publisher_excerpt"),
    "ibkr_contract": ("market_infrastructure", "market_infrastructure_snapshot"),
    "hosted_search": ("general_web", "hosted_search_citation"),
    "nasdaq_symbol_directory": (
        "listing_authority",
        "listing_directory_snapshot",
    ),
    "massive_reference": ("listing_authority", "listing_directory_snapshot"),
}
_SECRET_KEY_MARKERS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "cookie",
    "user_agent",
    "contact_email",
)
_DIAGNOSTIC_CONTENT_MARKERS = (
    "url",
    "body",
    "content",
    "excerpt",
    "message",
    "prompt",
    "contact",
)
_SOURCE_DEADLINE_CONTEXT_FIELDS = frozenset(
    {
        "source_deadline",
        "source_deadline_evidence_id",
        "source_deadline_span_start_byte",
        "source_deadline_span_end_byte",
        "source_deadline_cited_text_sha256",
        "source_deadline_rule_id",
        "source_deadline_rule_version",
    }
)
_QUERY_CONTEXT_LIMIT = 16_384
_TERMINAL_DECISION_KEY = "terminal_decision"
_TERMINAL_PROVENANCE_KEY = "terminal_decision_provenance_sha256"
_TERMINAL_FINALIZED_KEY = "terminal_finalized_decision_provenance_sha256"
_TERMINAL_FINALIZATION_FAILURE_KEY = "terminal_finalization_failure"
_AUTOMATIC_RETRY_KEY = "automatic_retry"
_LATEST_ATTEMPT_REVISION_KEY = "latest_attempt_execution_revision"
_EXECUTION_OWNER_KEY = "execution_owner_id"
_READINESS_RECHECK_DUE_AT_KEY = "readiness_recheck_due_at"
_DUE_REFRESH_CONTRACT_KEY = "due_refresh_contract"
_MATERIAL_EVIDENCE_IDS_KEY = "material_evidence_ids"
_TERMINAL_EVIDENCE_IDS_KEY = "terminal_evidence_ids"
_TERMINAL_FINALIZATION_FAILURE_CODES = frozenset({"finalization_failed"})
_TERMINAL_FINALIZATION_RETRY_DELAYS = (
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
)
_MAX_TERMINAL_FINALIZATION_FAILURES = (
    len(_TERMINAL_FINALIZATION_RETRY_DELAYS) + 1
)
_AUTOMATIC_RETRY_DELAYS = {
    "persistence_failed": (
        timedelta(minutes=15),
        timedelta(hours=1),
        timedelta(hours=6),
    ),
    "source_payload_invalid": (timedelta(hours=1),),
    "internal_error": (timedelta(hours=1),),
}
_MAX_PREDECESSOR_CHAIN = 32


@dataclass(frozen=True)
class AutomationEvidence:
    evidence_id: str
    source_family: str
    adapter: str
    kind: str
    excerpt: str
    content_sha256: str
    source_url: str | None = None
    title: str | None = None
    publisher: str | None = None
    domain: str | None = None
    source_published_at: str | None = None
    retrieved_at: str | None = None
    source_document_sha256: str | None = None
    source_locator: Mapping[str, Any] | None = None
    evidence_dedupe_key: str | None = None


@dataclass(frozen=True)
class AutomationFact:
    evidence_id: str
    fact_type: str
    normalized_value: Any
    source_span_start: int
    source_span_end: int
    cited_text_sha256: str
    extractor_rule_id: str
    extractor_rule_version: str


@dataclass(frozen=True)
class AutomationBlocker:
    code: str
    retryable: bool
    context: Mapping[str, Any]


@dataclass(frozen=True)
class AutomationRunClaim:
    run_id: str
    run_key: str
    status: str
    should_execute: bool


@dataclass(frozen=True)
class AutomationPriorMaterial:
    run_id: str
    observation_fingerprint_sha256: str
    evidence: tuple[Mapping[str, object], ...]
    facts: tuple[Mapping[str, object], ...]
    blockers: tuple[Mapping[str, object], ...]
    refresh_contract_required: bool = False


@dataclass(frozen=True)
class AutomationRunResult:
    run_id: str
    status: str
    decision_tier: str | None
    action_readiness: str | None
    source_families: tuple[str, ...]
    corroboration_family_count: int
    evidence_count: int
    fact_count: int
    conflicts: Mapping[str, tuple[str, ...]]
    decision_provenance_sha256: str


@dataclass(frozen=True)
class _EvidenceRow:
    local_id: str
    source_family: str
    adapter: str
    kind: str
    source_url: str | None
    title: str | None
    publisher: str | None
    domain: str | None
    source_published_at: str | None
    retrieved_at: str
    excerpt: str
    content_sha256: str
    source_document_sha256: str | None
    source_locator_json: str
    evidence_dedupe_key: str


@dataclass(frozen=True)
class _FactRow:
    local_evidence_id: str
    fact_type: str
    normalized_value_json: str
    source_span_start: int
    source_span_end: int
    cited_text_sha256: str
    extractor_rule_id: str
    extractor_rule_version: str


def _field(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _text(
    name: str,
    value: object,
    *,
    max_bytes: int,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise ValueError(name)
        return None
    text = str(value).strip()
    if "\0" in text or len(text.encode("utf-8")) > max_bytes:
        raise ValueError(name)
    if required and not text:
        raise ValueError(name)
    return text or None


def _sha256(name: str, value: object) -> str:
    text = str(value or "")
    if not _SHA256.fullmatch(text):
        raise ValueError(name)
    return text


def _execution_owner_id(value: object) -> str:
    if type(value) is not str or _EXECUTION_OWNER_ID.fullmatch(value) is None:
        raise ValueError(_EXECUTION_OWNER_KEY)
    return value


def _timestamp(name: str, value: object) -> str:
    text = _text(name, value, max_bytes=64, required=True)
    assert text is not None
    parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise ValueError(name) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(name)
    return text


def _instant(value: str) -> datetime:
    parseable = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(parseable)
    return parsed.astimezone(timezone.utc)


def _safe_key(key: object, *, diagnostics: bool) -> str:
    if not isinstance(key, str) or not key or "\0" in key or len(key) > 120:
        raise ValueError("json_key")
    normalized = key.casefold().replace("-", "_")
    if any(marker in normalized for marker in _SECRET_KEY_MARKERS):
        raise ValueError("secret_json_key")
    if diagnostics and any(marker in normalized for marker in _DIAGNOSTIC_CONTENT_MARKERS):
        raise ValueError("diagnostic_content_key")
    return key


def _safe_json_value(value: object, *, diagnostics: bool, depth: int = 0) -> Any:
    if depth > 8:
        raise ValueError("json_depth")
    if isinstance(value, Mapping):
        if len(value) > 100:
            raise ValueError("json_mapping_size")
        return {
            _safe_key(key, diagnostics=diagnostics): _safe_json_value(
                item, diagnostics=diagnostics, depth=depth + 1
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        if len(value) > 100:
            raise ValueError("json_sequence_size")
        return [
            _safe_json_value(item, diagnostics=diagnostics, depth=depth + 1)
            for item in value
        ]
    if value is None or isinstance(value, bool):
        return value
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise ValueError("json_integer")
        return value
    if isinstance(value, str):
        if "\0" in value or len(value.encode("utf-8")) > 8000:
            raise ValueError("json_string")
        return value
    raise ValueError("json_value")


def _canonical_json(
    value: object,
    *,
    name: str,
    max_bytes: int,
    diagnostics: bool = False,
) -> str:
    safe = _safe_json_value(value, diagnostics=diagnostics)
    encoded = json.dumps(
        safe,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError(name)
    return encoded


def _query_context_value(value: object) -> dict[str, object]:
    if not isinstance(value, str) or len(value.encode("utf-8")) > _QUERY_CONTEXT_LIMIT:
        raise ValueError("query_context")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("query_context") from exc
    safe = _safe_json_value(decoded, diagnostics=False)
    if not isinstance(safe, dict):
        raise ValueError("query_context")
    return safe


def _query_context_json(value: Mapping[str, object]) -> str:
    return _canonical_json(
        value,
        name="query_context",
        max_bytes=_QUERY_CONTEXT_LIMIT,
    )


def _evidence_id_index(
    context: Mapping[str, object],
    key: str,
) -> tuple[str, ...] | None:
    value = context.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError(key)
    normalized: list[str] = []
    for item in value:
        evidence_id = _text(key, item, max_bytes=200, required=True)
        assert evidence_id is not None
        normalized.append(evidence_id)
    if len(set(normalized)) != len(normalized) or normalized != sorted(normalized):
        raise ValueError(key)
    return tuple(normalized)


def _terminal_finalization_pending(context: Mapping[str, object]) -> bool:
    decision = context.get(_TERMINAL_DECISION_KEY)
    provenance = context.get(_TERMINAL_PROVENANCE_KEY)
    return (
        isinstance(decision, Mapping)
        and isinstance(provenance, str)
        and _SHA256.fullmatch(provenance) is not None
        and context.get(_TERMINAL_FINALIZED_KEY) != provenance
    )


def normalize_terminal_finalization_failure(
    value: object,
) -> dict[str, object] | None:
    """Validate the closed, provider-neutral terminal-finalization state."""

    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "attempt_count",
        "code",
        "failed_at",
        "retry_not_before",
    }:
        raise ValueError(_TERMINAL_FINALIZATION_FAILURE_KEY)
    attempt_count = value.get("attempt_count")
    if (
        type(attempt_count) is not int
        or not 1 <= attempt_count <= _MAX_TERMINAL_FINALIZATION_FAILURES
    ):
        raise ValueError(_TERMINAL_FINALIZATION_FAILURE_KEY)
    code = value.get("code")
    if code not in _TERMINAL_FINALIZATION_FAILURE_CODES:
        raise ValueError(_TERMINAL_FINALIZATION_FAILURE_KEY)
    failed_at = _timestamp(
        _TERMINAL_FINALIZATION_FAILURE_KEY,
        value.get("failed_at"),
    )
    retry_value = value.get("retry_not_before")
    retry_not_before = (
        None
        if retry_value is None
        else _timestamp(_TERMINAL_FINALIZATION_FAILURE_KEY, retry_value)
    )
    if attempt_count < _MAX_TERMINAL_FINALIZATION_FAILURES:
        if (
            retry_not_before is None
            or _instant(retry_not_before) <= _instant(failed_at)
        ):
            raise ValueError(_TERMINAL_FINALIZATION_FAILURE_KEY)
    elif retry_not_before is not None:
        raise ValueError(_TERMINAL_FINALIZATION_FAILURE_KEY)
    return {
        "attempt_count": attempt_count,
        "code": code,
        "failed_at": failed_at,
        "retry_not_before": retry_not_before,
    }


def _normalize_automatic_retry(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "class",
        "retry_not_before",
    }:
        raise ValueError(_AUTOMATIC_RETRY_KEY)
    retry_class = value.get("class")
    if retry_class not in _AUTOMATIC_RETRY_DELAYS:
        raise ValueError(_AUTOMATIC_RETRY_KEY)
    raw_not_before = value.get("retry_not_before")
    retry_not_before = (
        None
        if raw_not_before is None
        else _timestamp(_AUTOMATIC_RETRY_KEY, raw_not_before)
    )
    return {
        "class": retry_class,
        "retry_not_before": retry_not_before,
    }


_TRANSACTION_TERM_FIELDS = frozenset(
    {
        "cash_per_security_decimal",
        "consideration_currency",
        "counterparty_cik",
        "counterparty_name",
        "counterparty_ticker",
        "exchange_ratio_decimal",
    }
)


def _fact_scalar(fact_type: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError("fact_value_shape")
    normalized = value.strip()
    if (
        not normalized
        or "\0" in normalized
        or len(normalized.encode("utf-8")) > 512
    ):
        raise ValueError("fact_value_shape")
    if fact_type in {"source_ticker", "successor_ticker"}:
        normalized = normalized.upper()
        if not _TICKER.fullmatch(normalized):
            raise ValueError("fact_value_shape")
    elif fact_type == "issuer_cik":
        if not _CIK.fullmatch(normalized):
            raise ValueError("fact_value_shape")
    elif fact_type == "effective_date":
        try:
            if date.fromisoformat(normalized).isoformat() != normalized:
                raise ValueError
        except ValueError as exc:
            raise ValueError("fact_value_shape") from exc
    return normalized


def _transaction_structure(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("fact_value_shape")
    allowed = {"kind", "terms_status", *_TRANSACTION_TERM_FIELDS}
    if set(value) - allowed:
        raise ValueError("fact_value_shape")
    kind = _fact_scalar("transaction_structure", value.get("kind"))
    status = _fact_scalar("transaction_structure", value.get("terms_status"))
    if kind not in TRANSACTION_STRUCTURE_KINDS or status not in TRANSACTION_TERMS_STATUSES:
        raise ValueError("fact_value_shape")
    normalized = {"kind": kind, "terms_status": status}
    for field in sorted(_TRANSACTION_TERM_FIELDS):
        item = value.get(field)
        if item is None:
            continue
        text = _fact_scalar("transaction_structure", item)
        if field == "counterparty_ticker":
            text = text.upper()
            if not _TICKER.fullmatch(text):
                raise ValueError("fact_value_shape")
        elif field == "counterparty_cik":
            if not _CIK.fullmatch(text):
                raise ValueError("fact_value_shape")
        elif field == "consideration_currency":
            text = text.upper()
            if not re.fullmatch(r"[A-Z]{3}", text):
                raise ValueError("fact_value_shape")
        elif field in {"cash_per_security_decimal", "exchange_ratio_decimal"}:
            if not _DECIMAL.fullmatch(text):
                raise ValueError("fact_value_shape")
        normalized[field] = text
    populated_terms = set(normalized) - {"kind", "terms_status"}
    if status == "not_extracted" and populated_terms:
        raise ValueError("fact_value_shape")
    if status in {"partial", "complete"} and not populated_terms:
        raise ValueError("fact_value_shape")
    return normalized


def normalize_automation_fact_value(fact_type: str, value: object) -> object:
    """Validate and normalize the closed value shape for one persisted fact."""

    if fact_type not in FACT_TYPES:
        raise ValueError("fact_type")
    if fact_type in FACT_SCALAR_TYPES:
        return _fact_scalar(fact_type, value)
    if fact_type == "transaction_structure":
        return _transaction_structure(value)
    raise ValueError("fact_value_shape")


def _diagnostics(value: Mapping[str, object]) -> str:
    if not isinstance(value, Mapping):
        raise ValueError("diagnostics")
    normalized: dict[str, int] = {}
    for key, item in value.items():
        safe_key = _safe_key(key, diagnostics=True)
        if not _IDENTIFIER.fullmatch(safe_key) or type(item) is not int:
            raise ValueError("diagnostics")
        if not 0 <= item <= 2**31 - 1:
            raise ValueError("diagnostics")
        normalized[safe_key] = item
    return _canonical_json(
        normalized,
        name="diagnostics",
        max_bytes=8192,
        diagnostics=True,
    )


def automation_run_key(
    *,
    case_id: str,
    observation_fingerprint_sha256: str,
    policy_version: str,
    mode: str,
    input_evidence_set_sha256: str,
) -> str:
    case = _text("case_id", case_id, max_bytes=200, required=True)
    fingerprint = _sha256(
        "observation_fingerprint_sha256", observation_fingerprint_sha256
    )
    policy = _text("policy_version", policy_version, max_bytes=120, required=True)
    input_evidence = _sha256(
        "input_evidence_set_sha256",
        input_evidence_set_sha256,
    )
    if mode not in AUTOMATION_MODES:
        raise ValueError("mode")
    payload = json.dumps(
        {
            "case_id": case,
            "input_evidence_set_sha256": input_evidence,
            "mode": mode,
            "observation_fingerprint_sha256": fingerprint,
            "policy_version": policy,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "lifecycle-automation-v1:" + hashlib.sha256(payload.encode()).hexdigest()


def _execution_run_key(
    *,
    semantic_run_key: str,
    execution_revision: str,
    predecessor_run_id: str | None,
) -> str:
    payload = {
        "execution_revision": execution_revision,
        "predecessor_run_id": predecessor_run_id,
        "semantic_run_key": semantic_run_key,
    }
    return "lifecycle-automation-execution-v1:" + hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _predecessor_run_id(context: Mapping[str, object]) -> str | None:
    current = context.get("predecessor_run_id")
    legacy = context.get("predecessor_failed_run_id")
    if current is not None and legacy is not None and current != legacy:
        raise ValueError("automation_predecessor_chain")
    value = current if current is not None else legacy
    if value is None:
        return None
    if (
        type(value) is not str
        or not value.startswith("slar_")
        or len(value.encode("utf-8")) > 80
        or "\0" in value
    ):
        raise ValueError("automation_predecessor_chain")
    return value


def _attempt_chain(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[sqlite3.Row, ...]:
    rows: list[sqlite3.Row] = []
    visited: set[str] = set()
    current_id: str | None = run_id
    identity: tuple[str, str, str, str, str, str] | None = None
    while current_id is not None:
        if current_id in visited:
            raise ValueError("automation_predecessor_cycle")
        if len(rows) >= _MAX_PREDECESSOR_CHAIN:
            raise ValueError("automation_predecessor_chain_limit")
        visited.add(current_id)
        row = conn.execute(
            "SELECT run_id,case_id,observation_fingerprint_sha256,policy_version,"
            "mode,status,failure_code,query_context_json "
            "FROM security_lifecycle_automation_runs WHERE run_id=?",
            (current_id,),
        ).fetchone()
        if row is None:
            raise ValueError("automation_predecessor_chain")
        context = _query_context_value(row["query_context_json"])
        input_evidence_digest = _sha256(
            "automation_predecessor_input_evidence_set_sha256",
            context.get("input_evidence_set_sha256"),
        )
        canonical_semantic_run_key = automation_run_key(
            case_id=str(row["case_id"]),
            observation_fingerprint_sha256=str(
                row["observation_fingerprint_sha256"]
            ),
            policy_version=str(row["policy_version"]),
            mode=str(row["mode"]),
            input_evidence_set_sha256=input_evidence_digest,
        )
        stored_semantic_run_key = context.get("semantic_run_key")
        if (
            type(stored_semantic_run_key) is not str
            or stored_semantic_run_key != canonical_semantic_run_key
        ):
            raise ValueError("automation_predecessor_semantic_run_key")
        row_identity = (
            str(row["case_id"]),
            str(row["observation_fingerprint_sha256"]),
            str(row["policy_version"]),
            str(row["mode"]),
            input_evidence_digest,
            canonical_semantic_run_key,
        )
        if identity is None:
            identity = row_identity
        elif row_identity != identity:
            raise ValueError("automation_predecessor_semantic_identity")
        rows.append(row)
        current_id = _predecessor_run_id(context)
    return tuple(rows)


def _automatic_retry_for_failure(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    failure_code: str,
    failed_at: str,
) -> dict[str, object] | None:
    delays = _AUTOMATIC_RETRY_DELAYS.get(failure_code)
    if delays is None:
        return None
    try:
        chain = _attempt_chain(conn, run_id)
    except ValueError as exc:
        if exc.args != ("automation_predecessor_chain_limit",):
            raise
        return {
            "class": failure_code,
            "retry_not_before": None,
        }
    prior_failures = sum(
        1
        for row in chain[1:]
        if row["status"] == "failed" and row["failure_code"] == failure_code
    )
    retry_not_before = None
    if prior_failures < len(delays):
        retry_not_before = (
            _instant(failed_at) + delays[prior_failures]
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "class": failure_code,
        "retry_not_before": retry_not_before,
    }


def _input_evidence_set_sha256(
    conn: sqlite3.Connection,
    case_id: str,
) -> str:
    rows = (
        (str(row[0]), str(row[1]))
        for row in conn.execute(
            "SELECT evidence_id,content_sha256 FROM security_lifecycle_evidence "
            "WHERE case_id=? AND automation_run_id IS NULL",
            (case_id,),
        )
    )
    return evidence_rows_sha256(rows)


def _normalize_evidence(values: Iterable[object]) -> tuple[_EvidenceRow, ...]:
    rows: list[_EvidenceRow] = []
    seen_ids: set[str] = set()
    seen_dedupe_keys: set[str] = set()
    for value in values:
        local_id = _text(
            "evidence_id", _field(value, "evidence_id"), max_bytes=200, required=True
        )
        assert local_id is not None
        if local_id in seen_ids:
            raise ValueError("duplicate_evidence_id")
        seen_ids.add(local_id)

        adapter = str(_field(value, "adapter") or "")
        family = str(_field(value, "source_family") or "")
        kind = str(_field(value, "kind") or "")
        if adapter not in EVIDENCE_ADAPTERS or adapter not in _ADAPTER_SHAPES:
            raise ValueError("evidence_adapter")
        expected_family, expected_kind = _ADAPTER_SHAPES[adapter]
        if family not in EVIDENCE_SOURCE_FAMILIES or family != expected_family:
            raise ValueError("evidence_source_family")
        if kind not in EVIDENCE_KINDS or kind != expected_kind:
            raise ValueError("evidence_kind")

        excerpt = _text(
            "evidence_excerpt",
            _field(value, "excerpt"),
            max_bytes=16_000,
            required=True,
        )
        assert excerpt is not None
        content_digest = _sha256(
            "evidence_content_sha256", _field(value, "content_sha256")
        )
        if hashlib.sha256(excerpt.encode()).hexdigest() != content_digest:
            raise ValueError("evidence_content_sha256")

        source_url = _text(
            "evidence_source_url", _field(value, "source_url"), max_bytes=1000
        )
        if source_url is not None and not source_url.startswith("https://"):
            raise ValueError("evidence_source_url")
        if adapter == "sec_edgar" and source_url is None:
            raise ValueError("evidence_source_url")
        source_document = _field(value, "source_document_sha256")
        if source_document is None:
            source_document = _field(value, "document_sha256")
        document_digest = (
            None
            if source_document is None
            else _sha256("source_document_sha256", source_document)
        )
        if adapter == "sec_edgar" and document_digest is None:
            raise ValueError("source_document_sha256")

        locator = _field(value, "source_locator")
        if not isinstance(locator, Mapping):
            raise ValueError("source_locator")
        locator_json = _canonical_json(
            locator,
            name="source_locator",
            max_bytes=4096,
        )
        dedupe_key = _text(
            "evidence_dedupe_key",
            _field(value, "evidence_dedupe_key")
            or f"{adapter}:{local_id}:{content_digest}",
            max_bytes=500,
            required=True,
        )
        assert dedupe_key is not None
        if dedupe_key in seen_dedupe_keys:
            raise ValueError("duplicate_evidence_dedupe_key")
        seen_dedupe_keys.add(dedupe_key)
        rows.append(
            _EvidenceRow(
                local_id=local_id,
                source_family=family,
                adapter=adapter,
                kind=kind,
                source_url=source_url,
                title=_text(
                    "evidence_title", _field(value, "title"), max_bytes=500
                ),
                publisher=_text(
                    "evidence_publisher",
                    _field(value, "publisher"),
                    max_bytes=240,
                ),
                domain=_text(
                    "evidence_domain", _field(value, "domain"), max_bytes=253
                ),
                source_published_at=_text(
                    "source_published_at",
                    _field(value, "source_published_at"),
                    max_bytes=64,
                ),
                retrieved_at=_timestamp(
                    "evidence_retrieved_at", _field(value, "retrieved_at")
                ),
                excerpt=excerpt,
                content_sha256=content_digest,
                source_document_sha256=document_digest,
                source_locator_json=locator_json,
                evidence_dedupe_key=dedupe_key,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.local_id, row.content_sha256)))


def _validate_citation(
    *,
    error_name: str,
    evidence: _EvidenceRow,
    start: object,
    end: object,
    cited_text_sha256: object,
) -> None:
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError(error_name)
    encoded = evidence.excerpt.encode("utf-8")
    if end > len(encoded):
        raise ValueError(error_name)
    cited = encoded[start:end]
    try:
        cited.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(error_name) from exc
    digest = _sha256(error_name, cited_text_sha256)
    if hashlib.sha256(cited).hexdigest() != digest:
        raise ValueError(error_name)


def _normalize_facts(
    values: Iterable[object], evidence: tuple[_EvidenceRow, ...]
) -> tuple[_FactRow, ...]:
    evidence_by_id = {row.local_id: row for row in evidence}
    rows: dict[tuple[object, ...], _FactRow] = {}
    for value in values:
        local_evidence_id = _text(
            "fact_evidence_id",
            _field(value, "evidence_id"),
            max_bytes=200,
            required=True,
        )
        assert local_evidence_id is not None
        evidence_row = evidence_by_id.get(local_evidence_id)
        if evidence_row is None:
            raise ValueError("fact_evidence_id")
        fact_type = str(_field(value, "fact_type") or "")
        if fact_type not in FACT_TYPES:
            raise ValueError("fact_type")
        normalized_value = normalize_automation_fact_value(
            fact_type,
            _field(value, "normalized_value", _field(value, "value")),
        )
        normalized_value_json = _canonical_json(
            normalized_value,
            name="normalized_value",
            max_bytes=4096,
        )
        if normalized_value_json == "null":
            raise ValueError("normalized_value")
        start = _field(value, "source_span_start", _field(value, "span_start_byte"))
        end = _field(value, "source_span_end", _field(value, "span_end_byte"))
        cited_text_sha256 = _field(value, "cited_text_sha256")
        _validate_citation(
            error_name="fact_citation",
            evidence=evidence_row,
            start=start,
            end=end,
            cited_text_sha256=cited_text_sha256,
        )
        cited_digest = str(cited_text_sha256)
        rule_id = _text(
            "extractor_rule_id",
            _field(value, "extractor_rule_id", _field(value, "rule_id")),
            max_bytes=160,
            required=True,
        )
        rule_version = _text(
            "extractor_rule_version",
            _field(
                value,
                "extractor_rule_version",
                _field(value, "rule_version"),
            ),
            max_bytes=120,
            required=True,
        )
        assert rule_id is not None and rule_version is not None
        row = _FactRow(
            local_evidence_id=local_evidence_id,
            fact_type=fact_type,
            normalized_value_json=normalized_value_json,
            source_span_start=start,
            source_span_end=end,
            cited_text_sha256=cited_digest,
            extractor_rule_id=rule_id,
            extractor_rule_version=rule_version,
        )
        key = (
            row.local_evidence_id,
            row.fact_type,
            row.normalized_value_json,
            row.source_span_start,
            row.source_span_end,
            row.cited_text_sha256,
            row.extractor_rule_id,
            row.extractor_rule_version,
        )
        rows[key] = row
    return tuple(rows[key] for key in sorted(rows))


def validate_automation_material(
    *,
    evidence: Iterable[object],
    facts: Iterable[object],
) -> None:
    """Validate evidence identity and every fact citation without persisting."""

    normalized_evidence = _normalize_evidence(evidence)
    _normalize_facts(facts, normalized_evidence)


def _normalize_blockers(values: Iterable[object]) -> tuple[tuple[str, bool, str], ...]:
    rows: dict[str, tuple[str, bool, str]] = {}
    for value in values:
        code = str(_field(value, "code") or "")
        if code not in AUTOMATION_BLOCKER_CODES:
            raise ValueError("blocker_code")
        retryable = _field(value, "retryable")
        if type(retryable) is not bool:
            raise ValueError("blocker_retryable")
        if code == "massive_credential_missing" and retryable:
            raise ValueError("blocker_retryable")
        context = _field(value, "context")
        if not isinstance(context, Mapping):
            raise ValueError("blocker_context")
        context_json = _canonical_json(
            context,
            name="blocker_context",
            max_bytes=4096,
            diagnostics=True,
        )
        if code in rows:
            raise ValueError("duplicate_blocker_code")
        rows[code] = (code, retryable, context_json)
    return tuple(rows[code] for code in sorted(rows))


def _persisted_evidence_id(run_id: str, evidence: _EvidenceRow) -> str:
    identity_digest = hashlib.sha256(
        f"{run_id}\0{evidence.local_id}\0{evidence.content_sha256}".encode()
    ).hexdigest()
    return "sle_" + identity_digest[:32]


def _citation_date(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _normalize_deadline_blockers(
    *,
    run_id: str,
    blockers: Iterable[tuple[str, bool, str]],
    current_evidence: tuple[_EvidenceRow, ...],
    existing_evidence: tuple[_EvidenceRow, ...],
) -> tuple[tuple[str, bool, str], ...]:
    current_by_id = {
        row.local_id: (row, _persisted_evidence_id(run_id, row))
        for row in current_evidence
    }
    existing_by_id = {row.local_id: (row, row.local_id) for row in existing_evidence}
    normalized: list[tuple[str, bool, str]] = []
    for code, retryable, context_json in blockers:
        context = json.loads(context_json)
        has_deadline_fields = bool(
            _SOURCE_DEADLINE_CONTEXT_FIELDS.intersection(context)
        )
        if (
            context.get("monitoring_reason") == "not_confirmed_as_of"
            and not has_deadline_fields
        ):
            raise ValueError("blocker_citation")
        if not has_deadline_fields:
            normalized.append((code, retryable, context_json))
            continue
        if not _SOURCE_DEADLINE_CONTEXT_FIELDS.issubset(context):
            raise ValueError("blocker_citation")
        if not _citation_date(context["source_deadline"]):
            raise ValueError("blocker_citation")
        if (
            context["source_deadline_rule_id"]
            != "sec.explicit_transaction_termination_date"
            or context["source_deadline_rule_version"] != "4"
        ):
            raise ValueError("blocker_citation")
        evidence_id = context["source_deadline_evidence_id"]
        if type(evidence_id) is not str:
            raise ValueError("blocker_citation")
        resolved = current_by_id.get(evidence_id) or existing_by_id.get(evidence_id)
        if resolved is None:
            raise ValueError("blocker_citation")
        evidence, persisted_id = resolved
        _validate_citation(
            error_name="blocker_citation",
            evidence=evidence,
            start=context["source_deadline_span_start_byte"],
            end=context["source_deadline_span_end_byte"],
            cited_text_sha256=context["source_deadline_cited_text_sha256"],
        )
        if context.get("monitoring_reason") == "not_confirmed_as_of" and not (
            _citation_date(context.get("as_of"))
        ):
            raise ValueError("blocker_citation")
        rewritten = dict(context)
        rewritten["source_deadline_evidence_id"] = persisted_id
        normalized.append(
            (
                code,
                retryable,
                _canonical_json(
                    rewritten,
                    name="blocker_context",
                    max_bytes=4096,
                    diagnostics=True,
                ),
            )
        )
    return tuple(normalized)


def validate_automation_deadline_citations(
    *,
    evidence: Iterable[object],
    contexts: Iterable[Mapping[str, object]],
) -> None:
    """Validate every persisted deadline context against retained evidence."""

    normalized_evidence = _normalize_evidence(evidence)
    blockers = tuple(
        (
            "sec_evidence_insufficient",
            False,
            _canonical_json(
                context,
                name="blocker_context",
                max_bytes=4096,
                diagnostics=True,
            ),
        )
        for context in contexts
    )
    _normalize_deadline_blockers(
        run_id="retained-validation",
        blockers=blockers,
        current_evidence=(),
        existing_evidence=normalized_evidence,
    )


def _conflicts(facts: Iterable[_FactRow]) -> dict[str, tuple[str, ...]]:
    values: dict[str, set[str]] = {}
    for fact in facts:
        values.setdefault(fact.fact_type, set()).add(fact.normalized_value_json)
    return {
        fact_type: tuple(sorted(found))
        for fact_type, found in sorted(values.items())
        if len(found) > 1
    }


def _provenance(
    *,
    case_id: str,
    observation_fingerprint_sha256: str,
    policy_version: str,
    mode: str,
    evidence: tuple[_EvidenceRow, ...],
    facts: tuple[_FactRow, ...],
) -> str:
    evidence_refs: dict[str, str] = {}
    evidence_payload: list[dict[str, object]] = []
    for row in evidence:
        material = {
            "adapter": row.adapter,
            "content_sha256": row.content_sha256,
            "kind": row.kind,
            "source_document_sha256": row.source_document_sha256,
            "source_family": row.source_family,
            "source_locator_json": row.source_locator_json,
            "source_url": row.source_url,
        }
        reference = hashlib.sha256(
            json.dumps(
                material,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        evidence_refs[row.local_id] = reference
        evidence_payload.append({"evidence_ref": reference, **material})

    payload = {
        "case_id": case_id,
        "mode": mode,
        "observation_fingerprint_sha256": observation_fingerprint_sha256,
        "policy_version": policy_version,
        "evidence": sorted(
            evidence_payload,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        ),
        "facts": [
            {
                "cited_text_sha256": row.cited_text_sha256,
                "evidence_ref": evidence_refs[row.local_evidence_id],
                "extractor_rule_id": row.extractor_rule_id,
                "extractor_rule_version": row.extractor_rule_version,
                "fact_type": row.fact_type,
                "normalized_value_json": row.normalized_value_json,
                "source_span_end": row.source_span_end,
                "source_span_start": row.source_span_start,
            }
            for row in sorted(
                facts,
                key=lambda item: (
                    item.fact_type,
                    item.normalized_value_json,
                    evidence_refs[item.local_evidence_id],
                    item.source_span_start,
                    item.source_span_end,
                    item.extractor_rule_id,
                    item.extractor_rule_version,
                ),
            )
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapped_rows(cursor: sqlite3.Cursor) -> tuple[dict[str, Any], ...]:
    names = tuple(str(item[0]) for item in cursor.description or ())
    return tuple(
        {name: row[index] for index, name in enumerate(names)}
        for row in cursor.fetchall()
    )


def _persisted_evidence_rows(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[_EvidenceRow, ...]:
    cursor = conn.execute(
        "SELECT * FROM security_lifecycle_evidence "
        "WHERE automation_run_id=? ORDER BY evidence_id",
        (run_id,),
    )
    return tuple(
        _EvidenceRow(
            local_id=str(row["evidence_id"]),
            source_family=str(row["source_family"]),
            adapter=str(row["adapter"]),
            kind=str(row["kind"]),
            source_url=(
                None
                if row["source_url"] is None
                else str(row["source_url"])
            ),
            title=None if row["title"] is None else str(row["title"]),
            publisher=(
                None
                if row["publisher"] is None
                else str(row["publisher"])
            ),
            domain=None if row["domain"] is None else str(row["domain"]),
            source_published_at=(
                None
                if row["source_published_at"] is None
                else str(row["source_published_at"])
            ),
            retrieved_at=str(row["retrieved_at"]),
            excerpt=str(row["excerpt"]),
            content_sha256=str(row["content_sha256"]),
            source_document_sha256=(
                None
                if row["source_document_sha256"] is None
                else str(row["source_document_sha256"])
            ),
            source_locator_json=str(row["source_locator_json"]),
            evidence_dedupe_key=str(row["evidence_dedupe_key"]),
        )
        for row in _mapped_rows(cursor)
    )


def _persisted_fact_rows(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[_FactRow, ...]:
    cursor = conn.execute(
        "SELECT * FROM security_lifecycle_automation_facts "
        "WHERE automation_run_id=? ORDER BY fact_id",
        (run_id,),
    )
    return tuple(
        _FactRow(
            local_evidence_id=str(row["evidence_id"]),
            fact_type=str(row["fact_type"]),
            normalized_value_json=str(row["normalized_value_json"]),
            source_span_start=int(row["source_span_start"]),
            source_span_end=int(row["source_span_end"]),
            cited_text_sha256=str(row["cited_text_sha256"]),
            extractor_rule_id=str(row["extractor_rule_id"]),
            extractor_rule_version=str(row["extractor_rule_version"]),
        )
        for row in _mapped_rows(cursor)
    )


def _indexed_persisted_material(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    context: Mapping[str, object],
    key: str,
) -> tuple[tuple[_EvidenceRow, ...], tuple[_FactRow, ...]]:
    evidence = _persisted_evidence_rows(conn, run_id)
    facts = _persisted_fact_rows(conn, run_id)
    indexed = _evidence_id_index(context, key)
    if indexed is None:
        return evidence, facts
    available = {row.local_id for row in evidence}
    if not set(indexed).issubset(available):
        raise ValueError(key)
    selected = set(indexed)
    return (
        tuple(row for row in evidence if row.local_id in selected),
        tuple(row for row in facts if row.local_evidence_id in selected),
    )


def persisted_decision_evidence_ids(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[str, ...]:
    row = conn.execute(
        "SELECT query_context_json FROM security_lifecycle_automation_runs "
        "WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise KeyError("automation_run_not_found")
    context = _query_context_value(row[0])
    evidence, _facts = _indexed_persisted_material(
        conn,
        run_id,
        context=context,
        key=_TERMINAL_EVIDENCE_IDS_KEY,
    )
    return tuple(row.local_id for row in evidence)


def persisted_decision_provenance_sha256(
    conn: sqlite3.Connection,
    run_id: str,
) -> str:
    row = conn.execute(
        "SELECT case_id,observation_fingerprint_sha256,policy_version,mode,"
        "query_context_json "
        "FROM security_lifecycle_automation_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise KeyError("automation_run_not_found")
    evidence, facts = _indexed_persisted_material(
        conn,
        run_id,
        context=_query_context_value(row[4]),
        key=_TERMINAL_EVIDENCE_IDS_KEY,
    )
    return _provenance(
        case_id=str(row[0]),
        observation_fingerprint_sha256=str(row[1]),
        policy_version=str(row[2]),
        mode=str(row[3]),
        evidence=evidence,
        facts=facts,
    )


def decision_provenance_sha256(
    *,
    case_id: str,
    observation_fingerprint_sha256: str,
    policy_version: str,
    mode: str,
    evidence: Iterable[object],
    facts: Iterable[object],
) -> str:
    case = _text("case_id", case_id, max_bytes=200, required=True)
    fingerprint = _sha256(
        "observation_fingerprint_sha256", observation_fingerprint_sha256
    )
    policy = _text("policy_version", policy_version, max_bytes=120, required=True)
    if mode not in AUTOMATION_MODES:
        raise ValueError("mode")
    normalized_evidence = _normalize_evidence(evidence)
    normalized_facts = _normalize_facts(facts, normalized_evidence)
    assert case is not None and policy is not None
    return _provenance(
        case_id=case,
        observation_fingerprint_sha256=fingerprint,
        policy_version=policy,
        mode=mode,
        evidence=normalized_evidence,
        facts=normalized_facts,
    )


@contextmanager
def _immediate_transaction(conn: sqlite3.Connection):
    if conn.in_transaction:
        raise RuntimeError("automation_kernel_requires_transaction_boundary")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


class SecurityLifecycleFactKernel:
    def __init__(self, store: SecurityLifecycleInvestigationStore):
        self.store = store
        self.conn = store.conn

    def prior_material(self, run_id: str) -> AutomationPriorMaterial:
        current = self.conn.execute(
            "SELECT run_id,status,observation_fingerprint_sha256,query_context_json FROM "
            "security_lifecycle_automation_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if current is None or str(current["status"]) != "running":
            raise ValueError("automation_run_not_running")
        context = _query_context_value(current["query_context_json"])
        indexed_evidence, _indexed_facts = _indexed_persisted_material(
            self.conn,
            run_id,
            context=context,
            key=_MATERIAL_EVIDENCE_IDS_KEY,
        )
        material_ids = {row.local_id for row in indexed_evidence}
        evidence = tuple(
            row
            for row in _mapped_rows(
                self.conn.execute(
                    "SELECT * FROM security_lifecycle_evidence "
                    "WHERE automation_run_id=? ORDER BY evidence_id",
                    (run_id,),
                )
            )
            if str(row["evidence_id"]) in material_ids
        )
        facts = _mapped_rows(
            self.conn.execute(
                "SELECT * FROM security_lifecycle_automation_facts "
                "WHERE automation_run_id=? AND evidence_id IN "
                "(SELECT evidence_id FROM security_lifecycle_evidence "
                "WHERE automation_run_id=?) ORDER BY fact_id",
                (run_id, run_id),
            )
        )
        facts = tuple(
            row for row in facts if str(row["evidence_id"]) in material_ids
        )
        blockers = _mapped_rows(
            self.conn.execute(
                "SELECT * FROM security_lifecycle_automation_run_blockers "
                "WHERE automation_run_id=? ORDER BY blocker_code",
                (run_id,),
            )
        )
        return AutomationPriorMaterial(
            run_id=str(current["run_id"]),
            observation_fingerprint_sha256=str(
                current["observation_fingerprint_sha256"]
            ),
            evidence=evidence,
            facts=facts,
            blockers=blockers,
            refresh_contract_required=(
                _DUE_REFRESH_CONTRACT_KEY in context
                or _READINESS_RECHECK_DUE_AT_KEY in context
            ),
        )

    def reserve_run(
        self,
        *,
        case_id: str,
        observation_fingerprint_sha256: str,
        policy_version: str,
        mode: str,
        execution_revision: str,
        execution_owner_id: str,
        query_context: Mapping[str, object],
        diagnostics: Mapping[str, object],
        at: str,
        allow_due_failed_retry: bool = False,
        allow_new_attempt: bool = False,
    ) -> AutomationRunClaim:
        self.store.assert_automation_write_available()
        self.store.get_case_identity(case_id)
        input_evidence_digest = _input_evidence_set_sha256(self.conn, case_id)
        semantic_run_key = automation_run_key(
            case_id=case_id,
            observation_fingerprint_sha256=observation_fingerprint_sha256,
            policy_version=policy_version,
            mode=mode,
            input_evidence_set_sha256=input_evidence_digest,
        )
        fingerprint = _sha256(
            "observation_fingerprint_sha256", observation_fingerprint_sha256
        )
        policy = _text(
            "policy_version", policy_version, max_bytes=120, required=True
        )
        execution = _text(
            "execution_revision",
            execution_revision,
            max_bytes=120,
            required=True,
        )
        owner_id = _execution_owner_id(execution_owner_id)
        assert policy is not None and execution is not None
        if type(allow_due_failed_retry) is not bool:
            raise ValueError("allow_due_failed_retry")
        if type(allow_new_attempt) is not bool:
            raise ValueError("allow_new_attempt")
        if not isinstance(query_context, Mapping):
            raise ValueError("query_context")
        if any(
            key in query_context
            for key in (
                "semantic_run_key",
                "execution_revision",
                _EXECUTION_OWNER_KEY,
                _LATEST_ATTEMPT_REVISION_KEY,
                "predecessor_run_id",
                "predecessor_failed_run_id",
                _AUTOMATIC_RETRY_KEY,
                _TERMINAL_DECISION_KEY,
                _TERMINAL_PROVENANCE_KEY,
                _TERMINAL_FINALIZED_KEY,
                _TERMINAL_FINALIZATION_FAILURE_KEY,
                _READINESS_RECHECK_DUE_AT_KEY,
                _DUE_REFRESH_CONTRACT_KEY,
                _MATERIAL_EVIDENCE_IDS_KEY,
                _TERMINAL_EVIDENCE_IDS_KEY,
            )
        ):
            raise ValueError("reserved_query_context")
        caller_digest = query_context.get("input_evidence_set_sha256")
        if caller_digest is not None and caller_digest != input_evidence_digest:
            raise ValueError("input_evidence_set_sha256")
        diagnostics_json = _diagnostics(diagnostics)
        timestamp = _timestamp("at", at)

        def query_json_for(predecessor_run_id: str | None) -> str:
            context = {
                **dict(query_context),
                "semantic_run_key": semantic_run_key,
                "execution_revision": execution,
                _EXECUTION_OWNER_KEY: owner_id,
                _LATEST_ATTEMPT_REVISION_KEY: execution,
                "input_evidence_set_sha256": input_evidence_digest,
            }
            if predecessor_run_id is not None:
                context["predecessor_run_id"] = predecessor_run_id
            return _query_context_json(context)

        def stored_context(row: sqlite3.Row) -> Mapping[str, object] | None:
            try:
                context = _query_context_value(row["query_context_json"])
            except (TypeError, ValueError):
                return None
            return context

        with _immediate_transaction(self.conn):
            rows = self.conn.execute(
                "SELECT * FROM security_lifecycle_automation_runs "
                "WHERE case_id=? AND observation_fingerprint_sha256=? "
                "AND policy_version=? AND mode=? "
                "ORDER BY created_at DESC,rowid DESC",
                (case_id, fingerprint, policy, mode),
            ).fetchall()
            row: sqlite3.Row | None = None
            context: Mapping[str, object] | None = None
            for candidate in rows:
                candidate_context = stored_context(candidate)
                if (
                    candidate_context is not None
                    and candidate_context.get("input_evidence_set_sha256")
                    == input_evidence_digest
                ):
                    row = candidate
                    context = candidate_context
                    break

            predecessor_run_id: str | None = None
            if row is not None:
                assert context is not None
                existing_id = str(row["run_id"])
                existing_run_key = str(row["run_key"])
                existing_status = str(row["status"])
                existing_revision = str(
                    context.get(
                        _LATEST_ATTEMPT_REVISION_KEY,
                        context.get("execution_revision", "unknown"),
                    )
                )
                if existing_status == "succeeded" and _terminal_finalization_pending(
                    context
                ):
                    if allow_new_attempt:
                        return AutomationRunClaim(
                            existing_id, existing_run_key, "succeeded", True
                        )
                    failure = normalize_terminal_finalization_failure(
                        context.get(_TERMINAL_FINALIZATION_FAILURE_KEY)
                    )
                    if failure is not None:
                        retry_not_before = failure["retry_not_before"]
                        if retry_not_before is None or _instant(timestamp) < _instant(
                            str(retry_not_before)
                        ):
                            return AutomationRunClaim(
                                existing_id,
                                existing_run_key,
                                "succeeded",
                                False,
                            )
                    return AutomationRunClaim(
                        existing_id, existing_run_key, "succeeded", True
                    )
                if allow_new_attempt and existing_status in {
                    "failed",
                    "blocked",
                    "succeeded",
                }:
                    _attempt_chain(self.conn, existing_id)
                    predecessor_run_id = existing_id
                elif existing_status == "blocked" and row["retry_at"] is not None:
                    blocker_rows = self.conn.execute(
                        "SELECT blocker_code,retryable FROM "
                        "security_lifecycle_automation_run_blockers "
                        "WHERE automation_run_id=?",
                        (existing_id,),
                    ).fetchall()
                    retryable = bool(blocker_rows) and all(
                        int(item["retryable"]) == 1
                        and str(item["blocker_code"])
                        != "massive_credential_missing"
                        for item in blocker_rows
                    )
                    due = _instant(str(row["retry_at"])) <= _instant(timestamp)
                    if retryable and due:
                        retry_context = dict(context)
                        retry_context[_EXECUTION_OWNER_KEY] = owner_id
                        retry_context[_LATEST_ATTEMPT_REVISION_KEY] = execution
                        retry_context[_DUE_REFRESH_CONTRACT_KEY] = str(
                            row["retry_at"]
                        )
                        self.conn.execute(
                            "UPDATE security_lifecycle_automation_runs SET "
                            "status='running',decision_tier=NULL,action_readiness=NULL,"
                            "query_context_json=?,diagnostics_json=?,retry_at=NULL,"
                            "failure_code=NULL,started_at=?,finished_at=NULL,updated_at=? "
                            "WHERE run_id=?",
                            (
                                _query_context_json(retry_context),
                                diagnostics_json,
                                timestamp,
                                timestamp,
                                existing_id,
                            ),
                        )
                        return AutomationRunClaim(
                            existing_id, existing_run_key, "running", True
                        )
                    return AutomationRunClaim(
                        existing_id, existing_run_key, existing_status, False
                    )
                elif existing_status == "failed":
                    due_failed_retry = False
                    if allow_due_failed_retry:
                        retry = _normalize_automatic_retry(
                            context.get(_AUTOMATIC_RETRY_KEY)
                        )
                        if retry is not None:
                            chain = _attempt_chain(self.conn, existing_id)
                            retry_class = str(retry["class"])
                            retry_count = sum(
                                1
                                for item in chain
                                if item["status"] == "failed"
                                and item["failure_code"] == retry_class
                            )
                            retry_not_before = retry["retry_not_before"]
                            due_failed_retry = (
                                row["failure_code"] == retry_class
                                and retry_count
                                <= len(_AUTOMATIC_RETRY_DELAYS[retry_class])
                                and retry_not_before is not None
                                and _instant(timestamp)
                                >= _instant(str(retry_not_before))
                            )
                    if due_failed_retry or existing_revision != execution:
                        _attempt_chain(self.conn, existing_id)
                        predecessor_run_id = existing_id
                    else:
                        return AutomationRunClaim(
                            existing_id,
                            existing_run_key,
                            existing_status,
                            False,
                        )
                elif predecessor_run_id is None:
                    return AutomationRunClaim(
                        existing_id,
                        existing_run_key,
                        existing_status,
                        False,
                    )

            run_key = _execution_run_key(
                semantic_run_key=semantic_run_key,
                execution_revision=execution,
                predecessor_run_id=predecessor_run_id,
            )
            run_id = "slar_" + run_key.rsplit(":", 1)[1][:32]
            query_json = query_json_for(predecessor_run_id)
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO security_lifecycle_automation_runs "
                "(run_id,case_id,mode,observation_fingerprint_sha256,policy_version,"
                "run_key,status,decision_tier,action_readiness,query_context_json,"
                "diagnostics_json,retry_at,failure_code,started_at,finished_at,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,'running',NULL,NULL,?,?,NULL,NULL,?,NULL,?,?)",
                (
                    run_id,
                    case_id,
                    mode,
                    fingerprint,
                    policy,
                    run_key,
                    query_json,
                    diagnostics_json,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            if cursor.rowcount == 1:
                return AutomationRunClaim(run_id, run_key, "running", True)

            existing = self.conn.execute(
                "SELECT * FROM security_lifecycle_automation_runs WHERE run_key=?",
                (run_key,),
            ).fetchone()
            if existing is None:
                raise RuntimeError("automation_run_insert_lost")
            return AutomationRunClaim(
                str(existing["run_id"]),
                str(existing["run_key"]),
                str(existing["status"]),
                False,
            )

    def reserve_readiness_recheck(
        self,
        *,
        run_id: str,
        due_at: str,
        at: str,
        execution_owner_id: str,
    ) -> AutomationRunClaim:
        self.store.assert_automation_write_available()
        owner_id = _execution_owner_id(execution_owner_id)
        due_timestamp = _timestamp("due_at", due_at)
        timestamp = _timestamp("at", at)
        with _immediate_transaction(self.conn):
            row = self.conn.execute(
                "SELECT run_key,status,action_readiness,query_context_json FROM "
                "security_lifecycle_automation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("automation_run_not_found")
            run_key = str(row["run_key"])
            status = str(row["status"])
            readiness = row["action_readiness"]
            if (
                status != "succeeded"
                or readiness
                not in {
                    "waiting_effective_date",
                    "waiting_market_confirmation",
                    "waiting_transition_revalidation",
                }
                or _instant(timestamp) < _instant(due_timestamp)
            ):
                return AutomationRunClaim(run_id, run_key, status, False)
            if readiness == "waiting_transition_revalidation":
                self.conn.execute(
                    "UPDATE security_lifecycle_automation_runs SET updated_at=? "
                    "WHERE run_id=?",
                    (timestamp, run_id),
                )
                return AutomationRunClaim(run_id, run_key, status, True)
            query_context = _query_context_value(row["query_context_json"])
            query_context[_EXECUTION_OWNER_KEY] = owner_id
            query_context[_READINESS_RECHECK_DUE_AT_KEY] = due_timestamp
            self.conn.execute(
                "DELETE FROM security_lifecycle_automation_run_blockers "
                "WHERE automation_run_id=?",
                (run_id,),
            )
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "status='running',decision_tier=NULL,action_readiness=NULL,"
                "query_context_json=?,retry_at=NULL,failure_code=NULL,"
                "started_at=?,finished_at=NULL,"
                "updated_at=? WHERE run_id=?",
                (
                    _query_context_json(query_context),
                    timestamp,
                    timestamp,
                    run_id,
                ),
            )
            return AutomationRunClaim(run_id, run_key, "running", True)

    def defer_transition_revalidation(
        self,
        *,
        run_id: str,
        blocker_code: str,
        at: str,
    ) -> None:
        self.store.assert_automation_write_available()
        if blocker_code not in {
            "transition_approval_changed",
            "transition_approval_unavailable",
        }:
            raise ValueError("blocker_code")
        timestamp = _timestamp("at", at)
        with _immediate_transaction(self.conn):
            row = self.conn.execute(
                "SELECT status,action_readiness FROM "
                "security_lifecycle_automation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("automation_run_not_found")
            if (
                str(row["status"]) != "succeeded"
                or str(row["action_readiness"])
                not in {
                    "transition_eligible",
                    "waiting_transition_revalidation",
                }
            ):
                raise ValueError("transition_revalidation_source_state")
            self.conn.execute(
                "DELETE FROM security_lifecycle_automation_run_blockers "
                "WHERE automation_run_id=?",
                (run_id,),
            )
            self.conn.execute(
                "INSERT INTO security_lifecycle_automation_run_blockers "
                "(automation_run_id,blocker_code,retryable,context_json,created_at) "
                "VALUES (?,?,1,'{}',?)",
                (run_id, blocker_code, timestamp),
            )
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "action_readiness='waiting_transition_revalidation',updated_at=? "
                "WHERE run_id=?",
                (timestamp, run_id),
            )

    def complete_transition_revalidation(self, *, run_id: str, at: str) -> None:
        self.store.assert_automation_write_available()
        timestamp = _timestamp("at", at)
        with _immediate_transaction(self.conn):
            row = self.conn.execute(
                "SELECT status,action_readiness FROM "
                "security_lifecycle_automation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("automation_run_not_found")
            if (
                str(row["status"]) != "succeeded"
                or str(row["action_readiness"])
                != "waiting_transition_revalidation"
            ):
                raise ValueError("transition_revalidation_source_state")
            self.conn.execute(
                "DELETE FROM security_lifecycle_automation_run_blockers "
                "WHERE automation_run_id=? AND blocker_code IN "
                "('transition_approval_changed','transition_approval_unavailable')",
                (run_id,),
            )
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "action_readiness='transition_eligible',updated_at=? WHERE run_id=?",
                (timestamp, run_id),
            )

    def complete_run(
        self,
        *,
        run_id: str,
        evidence: Iterable[object],
        facts: Iterable[object],
        blockers: Iterable[object],
        decision_tier: str | None,
        action_readiness: str | None,
        retry_at: str | None,
        diagnostics: Mapping[str, object],
        at: str,
        terminal_decision: Mapping[str, object] | None = None,
        retained_evidence: Iterable[object] = (),
        retained_facts: Iterable[object] = (),
        preserved_evidence: Iterable[object] = (),
        preserved_facts: Iterable[object] = (),
        refreshed_source_families: Iterable[str] | None = None,
    ) -> AutomationRunResult:
        self.store.assert_automation_write_available()
        run = self.store.get_automation_run(run_id)
        if run["status"] != "running":
            raise ValueError("automation_run_not_running")
        normalized_evidence = _normalize_evidence(evidence)
        normalized_facts = _normalize_facts(facts, normalized_evidence)
        normalized_retained_evidence = _normalize_evidence(retained_evidence)
        normalized_retained_facts = _normalize_facts(
            retained_facts,
            normalized_retained_evidence,
        )
        normalized_preserved_evidence = _normalize_evidence(preserved_evidence)
        normalized_preserved_facts = _normalize_facts(
            preserved_facts,
            normalized_preserved_evidence,
        )
        retained_local_ids = {
            row.local_id for row in normalized_retained_evidence
        }
        preserved_local_ids = {
            row.local_id for row in normalized_preserved_evidence
        }
        if retained_local_ids.intersection(preserved_local_ids):
            raise ValueError("preserved_evidence")
        refreshed_families = (
            None
            if refreshed_source_families is None
            else tuple(sorted(set(refreshed_source_families)))
        )
        if refreshed_families is None and (
            normalized_retained_evidence
            or normalized_retained_facts
            or normalized_preserved_evidence
            or normalized_preserved_facts
        ):
            raise ValueError("refreshed_source_families")
        if refreshed_families is not None:
            if any(
                type(family) is not str or family not in EVIDENCE_SOURCE_FAMILIES
                for family in refreshed_families
            ):
                raise ValueError("refreshed_source_families")
            if any(
                row.source_family not in refreshed_families
                for row in normalized_evidence
            ):
                raise ValueError("refreshed_source_families")
            if any(
                row.source_family in refreshed_families
                for row in normalized_retained_evidence
            ):
                raise ValueError("retained_source_family_refreshed")
        structurally_normalized_blockers = _normalize_blockers(blockers)

        if decision_tier is not None and decision_tier not in DECISION_TIERS:
            raise ValueError("decision_tier")
        if action_readiness is not None and action_readiness not in ACTION_READINESS:
            raise ValueError("action_readiness")
        timestamp = _timestamp("at", at)
        diagnostics_json = _diagnostics(diagnostics)
        retry_timestamp = (
            None if retry_at is None else _timestamp("retry_at", retry_at)
        )
        normalized_terminal_decision = (
            None
            if terminal_decision is None
            else _safe_json_value(terminal_decision, diagnostics=False)
        )
        if normalized_terminal_decision is not None and not isinstance(
            normalized_terminal_decision, Mapping
        ):
            raise ValueError("terminal_decision")

        with _immediate_transaction(self.conn):
            current = self.conn.execute(
                "SELECT status,case_id,observation_fingerprint_sha256,policy_version,"
                "mode,query_context_json FROM security_lifecycle_automation_runs "
                "WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if current is None or str(current["status"]) != "running":
                raise ValueError("automation_run_not_running")
            query_context = _query_context_value(current["query_context_json"])
            all_existing_evidence = _persisted_evidence_rows(self.conn, run_id)
            all_existing_facts = _persisted_fact_rows(self.conn, run_id)
            indexed_material = _evidence_id_index(
                query_context,
                _MATERIAL_EVIDENCE_IDS_KEY,
            )
            if indexed_material is None:
                candidate_ids = {
                    row.local_id for row in all_existing_evidence
                }
            else:
                candidate_ids = set(indexed_material)
                if not candidate_ids.issubset(
                    {row.local_id for row in all_existing_evidence}
                ):
                    raise ValueError(_MATERIAL_EVIDENCE_IDS_KEY)
            candidate_evidence = tuple(
                row
                for row in all_existing_evidence
                if row.local_id in candidate_ids
            )
            candidate_facts = tuple(
                row
                for row in all_existing_facts
                if row.local_evidence_id in candidate_ids
            )
            refresh_contract_required = (
                _DUE_REFRESH_CONTRACT_KEY in query_context
                or _READINESS_RECHECK_DUE_AT_KEY in query_context
            )
            if refreshed_families is None:
                if (
                    candidate_evidence
                    or candidate_facts
                    or refresh_contract_required
                ):
                    raise ValueError("refreshed_source_families")
                retained_ids: set[str] = set()
                preserved_ids: set[str] = set()
                existing_evidence = ()
                existing_facts = ()
            else:
                retained_ids = {
                    row.local_id for row in normalized_retained_evidence
                }
                preserved_ids = {
                    row.local_id for row in normalized_preserved_evidence
                }
                if not retained_ids.union(preserved_ids).issubset(candidate_ids):
                    raise ValueError("retained_evidence")
                existing_evidence = tuple(
                    row
                    for row in candidate_evidence
                    if row.local_id in retained_ids
                )
                existing_facts = tuple(
                    row
                    for row in candidate_facts
                    if row.local_evidence_id in retained_ids
                )
                existing_preserved_evidence = tuple(
                    row
                    for row in candidate_evidence
                    if row.local_id in preserved_ids
                )
                existing_preserved_facts = tuple(
                    row
                    for row in candidate_facts
                    if row.local_evidence_id in preserved_ids
                )
                if (
                    set(existing_evidence) != set(normalized_retained_evidence)
                    or len(existing_evidence) != len(normalized_retained_evidence)
                ):
                    raise ValueError("retained_evidence")
                if (
                    set(existing_facts) != set(normalized_retained_facts)
                    or len(existing_facts) != len(normalized_retained_facts)
                ):
                    raise ValueError("retained_facts")
                if (
                    set(existing_preserved_evidence)
                    != set(normalized_preserved_evidence)
                    or len(existing_preserved_evidence)
                    != len(normalized_preserved_evidence)
                ):
                    raise ValueError("preserved_evidence")
                if (
                    set(existing_preserved_facts)
                    != set(normalized_preserved_facts)
                    or len(existing_preserved_facts)
                    != len(normalized_preserved_facts)
                ):
                    raise ValueError("preserved_facts")
                if any(
                    row.source_family not in refreshed_families
                    for row in candidate_evidence
                    if row.local_id not in retained_ids.union(preserved_ids)
                ):
                    raise ValueError("unowned_existing_source_family")
            normalized_blockers = list(
                _normalize_deadline_blockers(
                    run_id=run_id,
                    blockers=structurally_normalized_blockers,
                    current_evidence=normalized_evidence,
                    existing_evidence=existing_evidence,
                )
            )
            conflicts = _conflicts((*existing_facts, *normalized_facts))
            explicit_conflicts = [
                row for row in normalized_blockers if row[0] == "source_conflict"
            ]
            normalized_blockers = [
                row for row in normalized_blockers if row[0] != "source_conflict"
            ]
            if conflicts:
                normalized_blockers.append(
                    (
                        "source_conflict",
                        False,
                        _canonical_json(
                            {"fact_types": sorted(conflicts)},
                            name="blocker_context",
                            max_bytes=4096,
                            diagnostics=True,
                        ),
                    )
                )
                normalized_blockers.sort(key=lambda row: row[0])
            elif explicit_conflicts:
                normalized_blockers.append(explicit_conflicts[0])
                normalized_blockers.sort(key=lambda row: row[0])

            terminal_blockers = [
                row for row in normalized_blockers if row[0] != "source_conflict"
            ]
            has_conflict = any(
                row[0] == "source_conflict" for row in normalized_blockers
            )
            if terminal_blockers:
                status = "blocked"
                terminal_tier = "review_suggested" if has_conflict else None
                terminal_readiness = "action_blocked" if has_conflict else None
                if has_conflict and (
                    decision_tier != terminal_tier
                    or action_readiness != terminal_readiness
                ):
                    raise ValueError("blocked_conflict_terminal_shape")
                all_retryable = all(row[1] for row in normalized_blockers)
                if all_retryable != (retry_timestamp is not None):
                    raise ValueError("retry_at")
                if retry_timestamp is not None and _instant(
                    retry_timestamp
                ) <= _instant(timestamp):
                    raise ValueError("retry_at")
            else:
                if not (normalized_evidence or existing_evidence) or not (
                    normalized_facts or existing_facts
                ):
                    raise ValueError("successful_run_requires_evidence_and_facts")
                if (
                    decision_tier is None
                    or action_readiness is None
                    or retry_timestamp is not None
                ):
                    raise ValueError("successful_run_terminal_shape")
                status = "succeeded"
                if has_conflict:
                    terminal_tier = "review_suggested"
                    terminal_readiness = "action_blocked"
                else:
                    terminal_tier = decision_tier
                    terminal_readiness = action_readiness
                if normalized_terminal_decision is not None and (
                    normalized_terminal_decision.get("decision_tier")
                    != terminal_tier
                    or normalized_terminal_decision.get("action_readiness")
                    != terminal_readiness
                ):
                    raise ValueError("terminal_decision_shape")

            self.conn.execute(
                "DELETE FROM security_lifecycle_automation_run_blockers "
                "WHERE automation_run_id=?",
                (run_id,),
            )
            cited_ids = {
                str(row[0])
                for row in self.conn.execute(
                    "SELECT DISTINCT ae.evidence_id FROM "
                    "security_lifecycle_assessment_evidence ae "
                    "JOIN security_lifecycle_evidence e "
                    "ON e.evidence_id=ae.evidence_id "
                    "WHERE e.automation_run_id=? AND ae.evidence_id IS NOT NULL",
                    (run_id,),
                )
            }
            physical_keep_ids = retained_ids.union(preserved_ids, cited_ids)
            if refreshed_families is None:
                pass
            elif physical_keep_ids:
                placeholders = ",".join("?" for _ in physical_keep_ids)
                retained_parameters = tuple(sorted(physical_keep_ids))
                self.conn.execute(
                    "DELETE FROM security_lifecycle_automation_facts "
                    "WHERE automation_run_id=? AND evidence_id NOT IN "
                    f"({placeholders})",
                    (run_id, *retained_parameters),
                )
                self.conn.execute(
                    "DELETE FROM security_lifecycle_evidence "
                    "WHERE automation_run_id=? AND evidence_id NOT IN "
                    f"({placeholders})",
                    (run_id, *retained_parameters),
                )
            else:
                self.conn.execute(
                    "DELETE FROM security_lifecycle_automation_facts "
                    "WHERE automation_run_id=?",
                    (run_id,),
                )
                self.conn.execute(
                    "DELETE FROM security_lifecycle_evidence "
                    "WHERE automation_run_id=?",
                    (run_id,),
                )

            persisted_ids: dict[str, str] = {}
            for row in normalized_evidence:
                persisted_id = _persisted_evidence_id(run_id, row)
                persisted_ids[row.local_id] = persisted_id
                dedupe_digest = hashlib.sha256(
                    row.evidence_dedupe_key.encode("utf-8")
                ).hexdigest()
                persisted_dedupe_key = f"automation:{run_id}:{dedupe_digest}"
                self.conn.execute(
                    "INSERT OR IGNORE INTO security_lifecycle_evidence "
                    "(evidence_id,case_id,run_id,automation_run_id,source_family,kind,"
                    "source_url,title,publisher,domain,source_published_at,retrieved_at,"
                    "adapter,excerpt,content_sha256,source_document_sha256,"
                    "source_locator_json,evidence_dedupe_key,mime_type,document_status,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        persisted_id,
                        current["case_id"],
                        None,
                        run_id,
                        row.source_family,
                        row.kind,
                        row.source_url,
                        row.title,
                        row.publisher,
                        row.domain,
                        row.source_published_at,
                        row.retrieved_at,
                        row.adapter,
                        row.excerpt,
                        row.content_sha256,
                        row.source_document_sha256,
                        row.source_locator_json,
                        persisted_dedupe_key,
                        None,
                        None,
                        timestamp,
                    ),
                )
                persisted = self.conn.execute(
                    "SELECT case_id,automation_run_id,source_family,adapter,kind,"
                    "content_sha256,source_document_sha256,source_locator_json,"
                    "evidence_dedupe_key FROM security_lifecycle_evidence "
                    "WHERE evidence_id=?",
                    (persisted_id,),
                ).fetchone()
                expected = (
                    str(current["case_id"]),
                    run_id,
                    row.source_family,
                    row.adapter,
                    row.kind,
                    row.content_sha256,
                    row.source_document_sha256,
                    row.source_locator_json,
                    persisted_dedupe_key,
                )
                if persisted is None or tuple(persisted) != expected:
                    raise RuntimeError("automation_evidence_identity_conflict")
            for row in normalized_facts:
                material = json.dumps(
                    {
                        "evidence_id": persisted_ids[row.local_evidence_id],
                        "fact_type": row.fact_type,
                        "normalized_value_json": row.normalized_value_json,
                        "rule_id": row.extractor_rule_id,
                        "rule_version": row.extractor_rule_version,
                        "span": [row.source_span_start, row.source_span_end],
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                fact_digest = hashlib.sha256(
                    f"{run_id}\0{material}".encode()
                ).hexdigest()
                fact_id = "slf_" + fact_digest[:32]
                fact_dedupe_key = f"automation:{run_id}:fact:{fact_digest}"
                self.conn.execute(
                    "INSERT OR IGNORE INTO security_lifecycle_automation_facts "
                    "(fact_id,automation_run_id,case_id,evidence_id,fact_type,"
                    "normalized_value_json,source_span_start,source_span_end,"
                    "cited_text_sha256,extractor_rule_id,extractor_rule_version,"
                    "fact_dedupe_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        fact_id,
                        run_id,
                        current["case_id"],
                        persisted_ids[row.local_evidence_id],
                        row.fact_type,
                        row.normalized_value_json,
                        row.source_span_start,
                        row.source_span_end,
                        row.cited_text_sha256,
                        row.extractor_rule_id,
                        row.extractor_rule_version,
                        fact_dedupe_key,
                        timestamp,
                    ),
                )
                persisted = self.conn.execute(
                    "SELECT automation_run_id,case_id,evidence_id,fact_type,"
                    "normalized_value_json,source_span_start,source_span_end,"
                    "cited_text_sha256,extractor_rule_id,extractor_rule_version,"
                    "fact_dedupe_key FROM security_lifecycle_automation_facts "
                    "WHERE fact_id=?",
                    (fact_id,),
                ).fetchone()
                expected = (
                    run_id,
                    str(current["case_id"]),
                    persisted_ids[row.local_evidence_id],
                    row.fact_type,
                    row.normalized_value_json,
                    row.source_span_start,
                    row.source_span_end,
                    row.cited_text_sha256,
                    row.extractor_rule_id,
                    row.extractor_rule_version,
                    fact_dedupe_key,
                )
                if persisted is None or tuple(persisted) != expected:
                    raise RuntimeError("automation_fact_identity_conflict")
            for code, retryable, context_json in normalized_blockers:
                self.conn.execute(
                    "INSERT INTO security_lifecycle_automation_run_blockers "
                    "(automation_run_id,blocker_code,retryable,context_json,created_at) "
                    "VALUES (?,?,?,?,?)",
                    (run_id, code, int(retryable), context_json, timestamp),
                )
            all_persisted_evidence = _persisted_evidence_rows(self.conn, run_id)
            all_persisted_facts = _persisted_fact_rows(self.conn, run_id)
            active_evidence_ids = retained_ids.union(persisted_ids.values())
            material_evidence_ids = active_evidence_ids.union(preserved_ids)
            if len(material_evidence_ids) > 100 or len(active_evidence_ids) > 100:
                raise ValueError(_MATERIAL_EVIDENCE_IDS_KEY)
            persisted_evidence = tuple(
                row
                for row in all_persisted_evidence
                if row.local_id in active_evidence_ids
            )
            persisted_facts = tuple(
                row
                for row in all_persisted_facts
                if row.local_evidence_id in active_evidence_ids
            )
            provenance = _provenance(
                case_id=str(current["case_id"]),
                observation_fingerprint_sha256=str(
                    current["observation_fingerprint_sha256"]
                ),
                policy_version=str(current["policy_version"]),
                mode=str(current["mode"]),
                evidence=persisted_evidence,
                facts=persisted_facts,
            )
            query_context[_MATERIAL_EVIDENCE_IDS_KEY] = sorted(
                material_evidence_ids
            )
            query_context.pop(_READINESS_RECHECK_DUE_AT_KEY, None)
            query_context.pop(_DUE_REFRESH_CONTRACT_KEY, None)
            if status == "succeeded":
                query_context[_TERMINAL_EVIDENCE_IDS_KEY] = sorted(
                    active_evidence_ids
                )
            if status == "succeeded" and normalized_terminal_decision is not None:
                query_context[_TERMINAL_DECISION_KEY] = dict(
                    normalized_terminal_decision
                )
                query_context[_TERMINAL_PROVENANCE_KEY] = provenance
                query_context.pop(_TERMINAL_FINALIZED_KEY, None)
                query_context.pop(_TERMINAL_FINALIZATION_FAILURE_KEY, None)
            elif status != "succeeded":
                query_context.pop(_TERMINAL_DECISION_KEY, None)
                query_context.pop(_TERMINAL_PROVENANCE_KEY, None)
                query_context.pop(_TERMINAL_FINALIZED_KEY, None)
                query_context.pop(_TERMINAL_FINALIZATION_FAILURE_KEY, None)
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET status=?,decision_tier=?,"
                "action_readiness=?,query_context_json=?,diagnostics_json=?,retry_at=?,failure_code=NULL,"
                "finished_at=?,updated_at=? WHERE run_id=?",
                (
                    status,
                    terminal_tier,
                    terminal_readiness,
                    _query_context_json(query_context),
                    diagnostics_json,
                    retry_timestamp,
                    timestamp,
                    timestamp,
                    run_id,
                ),
            )

        families = tuple(sorted({row.source_family for row in persisted_evidence}))
        return AutomationRunResult(
            run_id=run_id,
            status=status,
            decision_tier=terminal_tier,
            action_readiness=terminal_readiness,
            source_families=families,
            corroboration_family_count=len(families),
            evidence_count=len(persisted_evidence),
            fact_count=len(persisted_facts),
            conflicts=_conflicts(persisted_facts),
            decision_provenance_sha256=provenance,
        )

    def complete_terminal_finalization(
        self,
        *,
        run_id: str,
        decision_provenance_sha256: str,
    ) -> None:
        """Durably acknowledge idempotent post-run decision finalization."""

        self.store.assert_automation_write_available()
        provenance = _sha256(
            "decision_provenance_sha256",
            decision_provenance_sha256,
        )
        with _immediate_transaction(self.conn):
            row = self.conn.execute(
                "SELECT status,query_context_json FROM "
                "security_lifecycle_automation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("automation_run_not_found")
            if str(row["status"]) != "succeeded":
                raise ValueError("automation_run_not_succeeded")
            context = _query_context_value(row["query_context_json"])
            if context.get(_TERMINAL_PROVENANCE_KEY) != provenance:
                raise ValueError("terminal_decision_provenance_changed")
            if persisted_decision_provenance_sha256(self.conn, run_id) != provenance:
                raise ValueError("terminal_decision_provenance_changed")
            if not isinstance(context.get(_TERMINAL_DECISION_KEY), Mapping):
                raise ValueError("terminal_decision_missing")
            already_finalized = context.get(_TERMINAL_FINALIZED_KEY) == provenance
            failure_removed = (
                context.pop(_TERMINAL_FINALIZATION_FAILURE_KEY, None) is not None
            )
            if already_finalized and not failure_removed:
                return
            context[_TERMINAL_FINALIZED_KEY] = provenance
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "query_context_json=? WHERE run_id=?",
                (_query_context_json(context), run_id),
            )

    def record_terminal_finalization_failure(
        self,
        *,
        run_id: str,
        code: str,
        at: str,
    ) -> dict[str, object]:
        """Persist bounded retry state without changing a succeeded run."""

        self.store.assert_automation_write_available()
        if code not in _TERMINAL_FINALIZATION_FAILURE_CODES:
            raise ValueError("terminal_finalization_failure_code")
        timestamp = _timestamp("at", at)
        with _immediate_transaction(self.conn):
            row = self.conn.execute(
                "SELECT status,query_context_json FROM "
                "security_lifecycle_automation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("automation_run_not_found")
            if str(row["status"]) != "succeeded":
                raise ValueError("automation_run_not_succeeded")
            context = _query_context_value(row["query_context_json"])
            if not _terminal_finalization_pending(context):
                raise ValueError("terminal_finalization_not_pending")
            assessment_present = self.conn.execute(
                "SELECT 1 FROM security_lifecycle_assessments "
                "WHERE automation_run_id=? LIMIT 1",
                (run_id,),
            ).fetchone()
            if assessment_present is None:
                raise ValueError("terminal_finalization_assessment_missing")
            previous = normalize_terminal_finalization_failure(
                context.get(_TERMINAL_FINALIZATION_FAILURE_KEY)
            )
            previous_count = 0 if previous is None else int(
                previous["attempt_count"]
            )
            attempt_count = min(
                previous_count + 1,
                _MAX_TERMINAL_FINALIZATION_FAILURES,
            )
            retry_not_before = None
            if attempt_count <= len(_TERMINAL_FINALIZATION_RETRY_DELAYS):
                retry_not_before = (
                    _instant(timestamp)
                    + _TERMINAL_FINALIZATION_RETRY_DELAYS[attempt_count - 1]
                ).isoformat(timespec="seconds").replace("+00:00", "Z")
            failure = normalize_terminal_finalization_failure(
                {
                    "attempt_count": attempt_count,
                    "code": code,
                    "failed_at": timestamp,
                    "retry_not_before": retry_not_before,
                }
            )
            assert failure is not None
            context[_TERMINAL_FINALIZATION_FAILURE_KEY] = failure
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "query_context_json=?,updated_at=? WHERE run_id=?",
                (_query_context_json(context), timestamp, run_id),
            )
        return failure

    def reconcile_running_runs(
        self,
        *,
        at: str,
        execution_owner_id: str | None = None,
    ) -> tuple[str, ...]:
        """Fail interrupted running rows, optionally limited to one owner."""

        self.store.assert_automation_write_available()
        requested_owner = (
            None
            if execution_owner_id is None
            else _execution_owner_id(execution_owner_id)
        )
        timestamp = _timestamp("at", at)
        diagnostics_json = _diagnostics({"interrupted_execution": 1})
        unclassifiable_diagnostics_json = _diagnostics(
            {
                "interrupted_execution": 1,
                "reconciliation_unclassifiable": 1,
            }
        )
        reconciled: list[str] = []
        with _immediate_transaction(self.conn):
            rows = self.conn.execute(
                "SELECT run_id,query_context_json FROM "
                "security_lifecycle_automation_runs WHERE status='running' "
                "ORDER BY created_at,rowid"
            ).fetchall()
            for row in rows:
                run_id = str(row["run_id"])
                try:
                    context = _query_context_value(row["query_context_json"])
                    persisted_owner = context.get(_EXECUTION_OWNER_KEY)
                    if persisted_owner is None:
                        if requested_owner is not None:
                            continue
                    else:
                        normalized_owner = _execution_owner_id(persisted_owner)
                        if (
                            requested_owner is not None
                            and normalized_owner != requested_owner
                        ):
                            continue
                    automatic_retry = _automatic_retry_for_failure(
                        self.conn,
                        run_id=run_id,
                        failure_code="internal_error",
                        failed_at=timestamp,
                    )
                    assert automatic_retry is not None
                    context[_AUTOMATIC_RETRY_KEY] = automatic_retry
                    query_context_json = _query_context_json(context)
                except ValueError:
                    cursor = self.conn.execute(
                        "UPDATE security_lifecycle_automation_runs SET "
                        "status='failed',decision_tier=NULL,action_readiness=NULL,"
                        "diagnostics_json=?,retry_at=NULL,"
                        "failure_code='internal_error',finished_at=?,updated_at=? "
                        "WHERE run_id=? AND status='running'",
                        (
                            unclassifiable_diagnostics_json,
                            timestamp,
                            timestamp,
                            run_id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError("automation_run_reconciliation_lost")
                    continue
                cursor = self.conn.execute(
                    "UPDATE security_lifecycle_automation_runs SET "
                    "status='failed',decision_tier=NULL,action_readiness=NULL,"
                    "diagnostics_json=?,query_context_json=?,retry_at=NULL,"
                    "failure_code='internal_error',finished_at=?,updated_at=? "
                    "WHERE run_id=? AND status='running'",
                    (
                        diagnostics_json,
                        query_context_json,
                        timestamp,
                        timestamp,
                        run_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("automation_run_reconciliation_lost")
                reconciled.append(run_id)
        return tuple(reconciled)

    def fail_run(
        self,
        *,
        run_id: str,
        failure_code: str,
        diagnostics: Mapping[str, object],
        at: str,
    ) -> dict:
        self.store.assert_automation_write_available()
        if failure_code not in AUTOMATION_FAILURE_CODES:
            raise ValueError("failure_code")
        diagnostics_json = _diagnostics(diagnostics)
        timestamp = _timestamp("at", at)
        with _immediate_transaction(self.conn):
            current = self.conn.execute(
                "SELECT status,started_at,query_context_json FROM "
                "security_lifecycle_automation_runs "
                "WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if current is None or str(current["status"]) not in {
                "running",
                "succeeded",
            }:
                raise ValueError("automation_run_not_running")
            if str(current["status"]) == "succeeded":
                started_at = _instant(str(current["started_at"]))
                assessment_times = self.conn.execute(
                    "SELECT created_at FROM security_lifecycle_assessments "
                    "WHERE automation_run_id=?",
                    (run_id,),
                ).fetchall()
                if any(
                    _instant(str(row["created_at"])) >= started_at
                    for row in assessment_times
                ):
                    raise ValueError("automation_run_has_current_assessment")
            query_context = _query_context_value(current["query_context_json"])
            automatic_retry = _automatic_retry_for_failure(
                self.conn,
                run_id=run_id,
                failure_code=failure_code,
                failed_at=timestamp,
            )
            if automatic_retry is None:
                query_context.pop(_AUTOMATIC_RETRY_KEY, None)
            else:
                query_context[_AUTOMATIC_RETRY_KEY] = automatic_retry
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET status='failed',"
                "decision_tier=NULL,action_readiness=NULL,diagnostics_json=?,"
                "query_context_json=?,retry_at=NULL,failure_code=?,finished_at=?,"
                "updated_at=? WHERE run_id=?",
                (
                    diagnostics_json,
                    _query_context_json(query_context),
                    failure_code,
                    timestamp,
                    timestamp,
                    run_id,
                ),
            )
        return self.store.get_automation_run(run_id)
