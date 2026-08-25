"""Atomic persistence kernel for trusted lifecycle evidence and cited facts."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore
from src.security_lifecycle_schema import (
    ACTION_READINESS,
    AUTOMATION_BLOCKER_CODES,
    AUTOMATION_FAILURE_CODES,
    AUTOMATION_MODES,
    DECISION_TIERS,
    EVIDENCE_ADAPTERS,
    EVIDENCE_KINDS,
    EVIDENCE_SOURCE_FAMILIES,
    FACT_TYPES,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ADAPTER_SHAPES = {
    "sec_edgar": ("regulator", "regulator_excerpt"),
    "internal_news": ("publisher", "publisher_excerpt"),
    "ibkr_contract": ("market_infrastructure", "market_infrastructure_snapshot"),
    "hosted_search": ("general_web", "hosted_search_citation"),
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
) -> str:
    case = _text("case_id", case_id, max_bytes=200, required=True)
    fingerprint = _sha256(
        "observation_fingerprint_sha256", observation_fingerprint_sha256
    )
    policy = _text("policy_version", policy_version, max_bytes=120, required=True)
    if mode not in AUTOMATION_MODES:
        raise ValueError("mode")
    payload = json.dumps(
        {
            "case_id": case,
            "mode": mode,
            "observation_fingerprint_sha256": fingerprint,
            "policy_version": policy,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "lifecycle-automation-v1:" + hashlib.sha256(payload.encode()).hexdigest()


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
        normalized_value_json = _canonical_json(
            _field(value, "normalized_value", _field(value, "value")),
            name="normalized_value",
            max_bytes=4096,
        )
        if normalized_value_json == "null":
            raise ValueError("normalized_value")
        start = _field(value, "source_span_start", _field(value, "span_start_byte"))
        end = _field(value, "source_span_end", _field(value, "span_end_byte"))
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise ValueError("fact_citation")
        encoded = evidence_row.excerpt.encode("utf-8")
        if end > len(encoded):
            raise ValueError("fact_citation")
        cited = encoded[start:end]
        try:
            cited.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("fact_citation") from exc
        cited_digest = _sha256(
            "fact_citation", _field(value, "cited_text_sha256")
        )
        if hashlib.sha256(cited).hexdigest() != cited_digest:
            raise ValueError("fact_citation")
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


def _normalize_blockers(values: Iterable[object]) -> tuple[tuple[str, bool, str], ...]:
    rows: dict[str, tuple[str, bool, str]] = {}
    for value in values:
        code = str(_field(value, "code") or "")
        if code not in AUTOMATION_BLOCKER_CODES:
            raise ValueError("blocker_code")
        retryable = _field(value, "retryable")
        if type(retryable) is not bool:
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


def _persisted_evidence_rows(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[_EvidenceRow, ...]:
    return tuple(
        _EvidenceRow(
            local_id=str(row["evidence_id"]),
            source_family=str(row["source_family"]),
            adapter=str(row["adapter"]),
            kind=str(row["kind"]),
            source_url=(
                None if row["source_url"] is None else str(row["source_url"])
            ),
            title=None if row["title"] is None else str(row["title"]),
            publisher=(
                None if row["publisher"] is None else str(row["publisher"])
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
        for row in conn.execute(
            "SELECT * FROM security_lifecycle_evidence "
            "WHERE automation_run_id=? ORDER BY evidence_id",
            (run_id,),
        )
    )


def _persisted_fact_rows(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[_FactRow, ...]:
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
        for row in conn.execute(
            "SELECT * FROM security_lifecycle_automation_facts "
            "WHERE automation_run_id=? ORDER BY fact_id",
            (run_id,),
        )
    )


def persisted_decision_provenance_sha256(
    conn: sqlite3.Connection,
    run_id: str,
) -> str:
    row = conn.execute(
        "SELECT case_id,observation_fingerprint_sha256,policy_version,mode "
        "FROM security_lifecycle_automation_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise KeyError("automation_run_not_found")
    return _provenance(
        case_id=str(row[0]),
        observation_fingerprint_sha256=str(row[1]),
        policy_version=str(row[2]),
        mode=str(row[3]),
        evidence=_persisted_evidence_rows(conn, run_id),
        facts=_persisted_fact_rows(conn, run_id),
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

    def reserve_run(
        self,
        *,
        case_id: str,
        observation_fingerprint_sha256: str,
        policy_version: str,
        mode: str,
        query_context: Mapping[str, object],
        diagnostics: Mapping[str, object],
        at: str,
    ) -> AutomationRunClaim:
        self.store.assert_automation_write_available()
        self.store.get_case_identity(case_id)
        run_key = automation_run_key(
            case_id=case_id,
            observation_fingerprint_sha256=observation_fingerprint_sha256,
            policy_version=policy_version,
            mode=mode,
        )
        fingerprint = _sha256(
            "observation_fingerprint_sha256", observation_fingerprint_sha256
        )
        policy = _text(
            "policy_version", policy_version, max_bytes=120, required=True
        )
        assert policy is not None
        query_json = _canonical_json(
            query_context,
            name="query_context",
            max_bytes=16_384,
        )
        diagnostics_json = _diagnostics(diagnostics)
        timestamp = _timestamp("at", at)
        run_digest = run_key.rsplit(":", 1)[1]
        run_id = "slar_" + run_digest[:32]

        with _immediate_transaction(self.conn):
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

            row = self.conn.execute(
                "SELECT * FROM security_lifecycle_automation_runs WHERE run_key=?",
                (run_key,),
            ).fetchone()
            if row is None:
                raise RuntimeError("automation_run_insert_lost")
            existing_id = str(row["run_id"])
            if row["status"] == "blocked" and row["retry_at"] is not None:
                blocker_rows = self.conn.execute(
                    "SELECT retryable FROM security_lifecycle_automation_run_blockers "
                    "WHERE automation_run_id=?",
                    (existing_id,),
                ).fetchall()
                retryable = bool(blocker_rows) and all(
                    int(item["retryable"]) == 1 for item in blocker_rows
                )
                due = _instant(str(row["retry_at"])) <= _instant(timestamp)
                if retryable and due:
                    self.conn.execute(
                        "DELETE FROM security_lifecycle_automation_facts "
                        "WHERE automation_run_id=?",
                        (existing_id,),
                    )
                    self.conn.execute(
                        "DELETE FROM security_lifecycle_evidence "
                        "WHERE automation_run_id=?",
                        (existing_id,),
                    )
                    self.conn.execute(
                        "DELETE FROM security_lifecycle_automation_run_blockers "
                        "WHERE automation_run_id=?",
                        (existing_id,),
                    )
                    self.conn.execute(
                        "UPDATE security_lifecycle_automation_runs SET "
                        "status='running',decision_tier=NULL,action_readiness=NULL,"
                        "query_context_json=?,diagnostics_json=?,retry_at=NULL,"
                        "failure_code=NULL,started_at=?,finished_at=NULL,updated_at=? "
                        "WHERE run_id=?",
                        (
                            query_json,
                            diagnostics_json,
                            timestamp,
                            timestamp,
                            existing_id,
                        ),
                    )
                    return AutomationRunClaim(existing_id, run_key, "running", True)
            return AutomationRunClaim(
                existing_id,
                run_key,
                str(row["status"]),
                False,
            )

    def reserve_readiness_recheck(
        self,
        *,
        run_id: str,
        due_at: str,
        at: str,
    ) -> AutomationRunClaim:
        self.store.assert_automation_write_available()
        due_timestamp = _timestamp("due_at", due_at)
        timestamp = _timestamp("at", at)
        with _immediate_transaction(self.conn):
            row = self.conn.execute(
                "SELECT run_key,status,action_readiness FROM "
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
                not in {"waiting_effective_date", "waiting_market_confirmation"}
                or _instant(timestamp) < _instant(due_timestamp)
            ):
                return AutomationRunClaim(run_id, run_key, status, False)
            self.conn.execute(
                "DELETE FROM security_lifecycle_automation_run_blockers "
                "WHERE automation_run_id=?",
                (run_id,),
            )
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "status='running',decision_tier=NULL,action_readiness=NULL,"
                "retry_at=NULL,failure_code=NULL,started_at=?,finished_at=NULL,"
                "updated_at=? WHERE run_id=?",
                (timestamp, timestamp, run_id),
            )
            return AutomationRunClaim(run_id, run_key, "running", True)

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
    ) -> AutomationRunResult:
        self.store.assert_automation_write_available()
        run = self.store.get_automation_run(run_id)
        if run["status"] != "running":
            raise ValueError("automation_run_not_running")
        normalized_evidence = _normalize_evidence(evidence)
        normalized_facts = _normalize_facts(facts, normalized_evidence)
        normalized_blockers = list(_normalize_blockers(blockers))
        existing_evidence = _persisted_evidence_rows(self.conn, run_id)
        existing_facts = _persisted_fact_rows(self.conn, run_id)
        conflicts = _conflicts((*existing_facts, *normalized_facts))
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

        if decision_tier is not None and decision_tier not in DECISION_TIERS:
            raise ValueError("decision_tier")
        if action_readiness is not None and action_readiness not in ACTION_READINESS:
            raise ValueError("action_readiness")
        timestamp = _timestamp("at", at)
        diagnostics_json = _diagnostics(diagnostics)
        retry_timestamp = (
            None if retry_at is None else _timestamp("retry_at", retry_at)
        )

        terminal_blockers = [
            row for row in normalized_blockers if row[0] != "source_conflict"
        ]
        if terminal_blockers:
            status = "blocked"
            terminal_tier = None
            terminal_readiness = None
            all_retryable = all(row[1] for row in terminal_blockers)
            if all_retryable != (retry_timestamp is not None):
                raise ValueError("retry_at")
            if retry_timestamp is not None and _instant(retry_timestamp) <= _instant(timestamp):
                raise ValueError("retry_at")
        else:
            if not (normalized_evidence or existing_evidence) or not (
                normalized_facts or existing_facts
            ):
                raise ValueError("successful_run_requires_evidence_and_facts")
            if decision_tier is None or action_readiness is None or retry_timestamp is not None:
                raise ValueError("successful_run_terminal_shape")
            status = "succeeded"
            if conflicts:
                terminal_tier = "review_suggested"
                terminal_readiness = "action_blocked"
            else:
                terminal_tier = decision_tier
                terminal_readiness = action_readiness

        persisted_ids: dict[str, str] = {}

        with _immediate_transaction(self.conn):
            current = self.conn.execute(
                "SELECT status FROM security_lifecycle_automation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if current is None or str(current["status"]) != "running":
                raise ValueError("automation_run_not_running")
            for row in normalized_evidence:
                identity_digest = hashlib.sha256(
                    f"{run_id}\0{row.local_id}\0{row.content_sha256}".encode()
                ).hexdigest()
                persisted_id = "sle_" + identity_digest[:32]
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
                        run["case_id"],
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
                    str(run["case_id"]),
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
                        run["case_id"],
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
                    str(run["case_id"]),
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
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET status=?,decision_tier=?,"
                "action_readiness=?,diagnostics_json=?,retry_at=?,failure_code=NULL,"
                "finished_at=?,updated_at=? WHERE run_id=?",
                (
                    status,
                    terminal_tier,
                    terminal_readiness,
                    diagnostics_json,
                    retry_timestamp,
                    timestamp,
                    timestamp,
                    run_id,
                ),
            )

        families = tuple(
            str(row[0])
            for row in self.conn.execute(
                "SELECT DISTINCT source_family FROM security_lifecycle_evidence "
                "WHERE automation_run_id=? ORDER BY source_family",
                (run_id,),
            )
        )
        persisted_evidence = _persisted_evidence_rows(self.conn, run_id)
        persisted_facts = _persisted_fact_rows(self.conn, run_id)
        provenance = persisted_decision_provenance_sha256(self.conn, run_id)
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
                "SELECT status FROM security_lifecycle_automation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if current is None or str(current["status"]) != "running":
                raise ValueError("automation_run_not_running")
            self.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET status='failed',"
                "decision_tier=NULL,action_readiness=NULL,diagnostics_json=?,"
                "retry_at=NULL,failure_code=?,finished_at=?,updated_at=? WHERE run_id=?",
                (diagnostics_json, failure_code, timestamp, timestamp, run_id),
            )
        return self.store.get_automation_run(run_id)
