"""Profile-side case identity, history, and cross-store read composition."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Mapping, Optional
import uuid

from src.security_lifecycle import read_market_observations
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    LifecycleWritesUnavailable,
    ACKNOWLEDGEMENT_REASONS,
    ASSESSMENT_AUTHORS,
    ASSESSMENT_CONFIDENCE,
    ASSESSMENT_OUTCOMES,
    ASSESSMENT_RELEVANCE,
    AUTOMATION_METHODS,
    DOCUMENT_STATUSES,
    EVIDENCE_ADAPTERS,
    EVIDENCE_KINDS,
    EVIDENCE_SOURCE_FAMILIES,
    PROPOSAL_ACTIONS,
    RUN_ADAPTERS,
    RUN_FAILURE_CODES,
    RUN_TRIGGERS,
    assert_lifecycle_writes_available,
    create_profile_schema,
    verify_profile_connection,
)


class LifecycleStoreUnavailable(RuntimeError):
    def __init__(self, store: str):
        super().__init__(f"security_lifecycle_{store}_store_unavailable")
        self.store = store


def _identity_value(name: str, value: object) -> str:
    text = str(value or "")
    if not text or "\0" in text:
        raise ValueError("embedded_nul" if "\0" in text else name)
    return text


def case_id_for(source: str, source_ref: str, ticker: str) -> str:
    parts = (
        "security-lifecycle-case-v1",
        _identity_value("source", source),
        _identity_value("source_ref", source_ref),
        _identity_value("ticker", ticker),
    )
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return f"slc_{digest}"


def observation_fingerprint(observation: dict) -> str:
    payload = {
        key: observation.get(key)
        for key in (
            "ticker",
            "cik",
            "issuer_name",
            "filing_date",
            "source",
            "source_ref",
            "filing_form",
            "filing_items",
            "evidence_url",
            "description",
        )
    }
    payload["kinds"] = sorted(
        [
            {
                "event_type": str(item["event_type"]),
                "effective_date": item.get("effective_date"),
            }
            for item in observation.get("kinds", [])
        ],
        key=lambda item: (item["event_type"], item["effective_date"] or ""),
    )
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def empty_evidence_set_sha256() -> str:
    return hashlib.sha256(b"").hexdigest()


def _bounded_text(
    name: str,
    value: object,
    *,
    max_length: int,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise ValueError(name)
        return None
    text = str(value).strip()
    if (required and not text) or len(text) > max_length or "\0" in text:
        raise ValueError(name)
    return text or None


def _canonical_json(value: object, *, max_bytes: int, name: str) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(name) from exc
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError(name)
    return encoded


def canonical_assessment_decimal(value: object, *, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name}_decimal")
    if not value.strip() or len(value) > 128:
        raise ValueError(f"{name}_decimal")
    try:
        number = Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name}_decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name}_decimal")
    if number.is_zero():
        return "0"
    parts = number.as_tuple()
    digit_count = len(parts.digits)
    exponent = int(parts.exponent)
    if exponent >= 0:
        rendered_length = digit_count + exponent
    elif digit_count + exponent > 0:
        rendered_length = digit_count + 1
    else:
        rendered_length = 2 - exponent
    rendered_length += int(parts.sign)
    if rendered_length > 128:
        raise ValueError(f"{name}_decimal")
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in {"-0", ""}:
        rendered = "0"
    if len(rendered) > 128:
        raise ValueError(f"{name}_decimal")
    return rendered


def _canonical_date(value: object, *, name: str) -> str | None:
    text = _bounded_text(name, value, max_length=10)
    if text is None:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(name) from exc
    if parsed.isoformat() != text:
        raise ValueError(name)
    return text


def _canonical_cik(value: object) -> str | None:
    text = _bounded_text("counterparty_cik", value, max_length=10)
    if text is not None and (
        len(text) != 10 or not text.isascii() or not text.isdigit()
    ):
        raise ValueError("counterparty_cik")
    return text


def _canonical_currency(value: object) -> str | None:
    text = _bounded_text("consideration_currency", value, max_length=3)
    if text is not None and (
        len(text) != 3
        or not text.isascii()
        or not text.isalpha()
        or text != text.upper()
    ):
        raise ValueError("consideration_currency")
    return text


def _canonical_sha256(name: str, value: object) -> str:
    text = str(value or "")
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError(name)
    return text


def _digest_rows(rows: Iterable[tuple[str, str]]) -> str:
    ordered = sorted((str(row_id), str(digest)) for row_id, digest in rows)
    payload = "" if not ordered else "".join(
        f"{row_id}\t{digest}\n" for row_id, digest in ordered
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assessment_fingerprint(assessment: Mapping[str, object]) -> str:
    return hashlib.sha256(
        "\0".join(
            (
                str(assessment["assessment_id"]),
                str(assessment["observation_fingerprint_sha256"]),
                str(assessment["evidence_set_sha256"]),
            )
        ).encode("utf-8")
    ).hexdigest()


def _component_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'security_lifecycle_%'"
        )
    }


class SecurityLifecycleInvestigationStore:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        id_factory: Optional[Callable[[str, int], str]] = None,
        allow_incomplete_migration: bool = False,
    ):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if not _component_tables(conn):
            create_profile_schema(conn)
        else:
            verify_profile_connection(conn)
        self._id_factory = id_factory
        self._allow_incomplete_migration = allow_incomplete_migration
        self._id_ordinals: dict[str, int] = {}

    def _assert_write(self) -> None:
        if not self._allow_incomplete_migration:
            assert_lifecycle_writes_available(self.conn)

    def assert_automation_write_available(self) -> None:
        """Expose the existing lifecycle receipt guard to the automation kernel."""
        self._assert_write()

    def _new_id(self, prefix: str) -> str:
        ordinal = self._id_ordinals.get(prefix, 0) + 1
        self._id_ordinals[prefix] = ordinal
        if self._id_factory is not None:
            return self._id_factory(prefix, ordinal)
        return f"{prefix}_{uuid.uuid4().hex}"

    def _case_identity_for_write(
        self,
        case_id: str,
        case_identity: Mapping[str, object] | None,
    ) -> tuple[str, str, str] | None:
        if case_identity is None:
            self._case_row(case_id)
            return None
        source = _identity_value("source", case_identity.get("source"))
        source_ref = _identity_value("source_ref", case_identity.get("source_ref"))
        ticker = _identity_value("ticker", case_identity.get("ticker"))
        if case_id_for(source, source_ref, ticker) != case_id:
            raise ValueError("case_identity")
        return source, source_ref, ticker

    def _upsert_case_row(
        self,
        case_id: str,
        identity: tuple[str, str, str],
        *,
        at: str,
    ) -> None:
        source, source_ref, ticker = identity
        self.conn.execute(
            "INSERT INTO security_lifecycle_cases "
            "(case_id,source,source_ref,ticker,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(case_id) DO UPDATE SET updated_at=excluded.updated_at",
            (case_id, source, source_ref, ticker, at, at),
        )

    def ensure_case(
        self,
        *,
        source: str,
        source_ref: str,
        ticker: str,
        at: str,
    ) -> str:
        self._assert_write()
        source = _identity_value("source", source)
        source_ref = _identity_value("source_ref", source_ref)
        ticker = _identity_value("ticker", ticker)
        case_id = case_id_for(source, source_ref, ticker)
        with self.conn:
            self._upsert_case_row(case_id, (source, source_ref, ticker), at=at)
        return case_id

    def _case_row(self, case_id: str) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT * FROM security_lifecycle_cases WHERE case_id=?", (case_id,)
        ).fetchone()
        if row is None:
            raise KeyError("case_not_found")
        return row

    def get_case_identity(self, case_id: str) -> dict:
        return dict(self._case_row(case_id))

    def _evidence_set_sha256(self, case_id: str) -> str:
        return _digest_rows(
            (
                str(row["evidence_id"]),
                str(row["content_sha256"]),
            )
            for row in self.conn.execute(
                "SELECT evidence_id,content_sha256 "
                "FROM security_lifecycle_evidence WHERE case_id=?",
                (case_id,),
            )
        )

    def create_investigation_run(
        self,
        *,
        case_id: str,
        trigger: str,
        adapter: str,
        query_plan: Iterable[str],
        at: str,
        case_identity: Mapping[str, object] | None = None,
    ) -> str:
        self._assert_write()
        identity = self._case_identity_for_write(case_id, case_identity)
        if trigger not in RUN_TRIGGERS:
            raise ValueError("trigger")
        if adapter not in RUN_ADAPTERS:
            raise ValueError("adapter")
        queries = [
            _bounded_text("query", query, max_length=1800, required=True)
            for query in query_plan
        ]
        if len(queries) > 3:
            raise ValueError("query_count")
        run_id = self._new_id("slr")
        with self.conn:
            if identity is not None:
                self._upsert_case_row(case_id, identity, at=at)
            self.conn.execute(
                "INSERT INTO security_lifecycle_investigation_runs "
                "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
                "result_count,fetch_count,usage_json,failure_code,started_at,"
                "finished_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    case_id,
                    trigger,
                    adapter,
                    "queued",
                    _canonical_json(queries, max_bytes=6000, name="query_plan"),
                    len(queries),
                    None,
                    0,
                    "{}",
                    None,
                    None,
                    None,
                    at,
                ),
            )
        return run_id

    def get_investigation_run(self, run_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM security_lifecycle_investigation_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError("investigation_run_not_found")
        return dict(row)

    def list_investigation_runs(self, case_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM security_lifecycle_investigation_runs "
                "WHERE case_id=? ORDER BY created_at DESC,run_id DESC",
                (case_id,),
            )
        ]

    def get_automation_run(self, run_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM security_lifecycle_automation_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError("automation_run_not_found")
        result = dict(row)
        result["blockers"] = [
            dict(blocker)
            for blocker in self.conn.execute(
                "SELECT * FROM security_lifecycle_automation_run_blockers "
                "WHERE automation_run_id=? ORDER BY blocker_code",
                (run_id,),
            )
        ]
        return result

    def list_automation_runs(self, case_id: str) -> list[dict]:
        self._case_row(case_id)
        rows = self.conn.execute(
            "SELECT run_id FROM security_lifecycle_automation_runs "
            "WHERE case_id=? ORDER BY created_at DESC,rowid DESC",
            (case_id,),
        ).fetchall()
        return [self.get_automation_run(str(row["run_id"])) for row in rows]

    def start_investigation_run(self, run_id: str, *, at: str) -> None:
        self._assert_write()
        row = self.get_investigation_run(run_id)
        if row["status"] != "queued":
            raise ValueError("terminal_or_invalid_run_transition")
        with self.conn:
            self.conn.execute(
                "UPDATE security_lifecycle_investigation_runs "
                "SET status='running',started_at=? WHERE run_id=?",
                (at, run_id),
            )

    def succeed_investigation_run(
        self,
        run_id: str,
        *,
        result_count: int,
        fetch_count: int,
        usage: Mapping[str, object],
        at: str,
    ) -> dict:
        self._assert_write()
        row = self.get_investigation_run(run_id)
        if row["status"] != "running":
            raise ValueError("terminal_or_invalid_run_transition")
        if int(result_count) < 0:
            raise ValueError("result_count")
        if not 0 <= int(fetch_count) <= 5:
            raise ValueError("fetch_count")
        usage_json = _canonical_json(dict(usage), max_bytes=4096, name="usage")
        with self.conn:
            self.conn.execute(
                "UPDATE security_lifecycle_investigation_runs SET "
                "status='succeeded',result_count=?,fetch_count=?,usage_json=?,"
                "failure_code=NULL,finished_at=? WHERE run_id=?",
                (int(result_count), int(fetch_count), usage_json, at, run_id),
            )
        return self.get_investigation_run(run_id)

    def fail_investigation_run(
        self,
        run_id: str,
        *,
        failure_code: str,
        usage: Mapping[str, object],
        at: str,
        fetch_count: int = 0,
    ) -> dict:
        self._assert_write()
        row = self.get_investigation_run(run_id)
        if row["status"] != "running":
            raise ValueError("terminal_or_invalid_run_transition")
        if failure_code not in RUN_FAILURE_CODES:
            raise ValueError("failure_code")
        if not 0 <= int(fetch_count) <= 5:
            raise ValueError("fetch_count")
        usage_json = _canonical_json(dict(usage), max_bytes=4096, name="usage")
        with self.conn:
            self.conn.execute(
                "UPDATE security_lifecycle_investigation_runs SET "
                "status='failed',result_count=NULL,fetch_count=?,usage_json=?,failure_code=?,"
                "finished_at=? WHERE run_id=?",
                (int(fetch_count), usage_json, failure_code, at, run_id),
            )
        return self.get_investigation_run(run_id)

    def add_evidence(
        self,
        *,
        case_id: str,
        run_id: str | None,
        kind: str,
        adapter: str,
        excerpt: str,
        source_url: str | None,
        title: str | None,
        publisher: str | None,
        domain: str | None,
        source_published_at: str | None,
        retrieved_at: str | None,
        mime_type: str | None,
        document_status: str | None,
        at: str,
        case_identity: Mapping[str, object] | None = None,
        source_family: str | None = None,
        automation_run_id: str | None = None,
        source_document_sha256: str | None = None,
        source_locator: Mapping[str, object] | None = None,
        evidence_dedupe_key: str | None = None,
    ) -> str:
        self._assert_write()
        identity = self._case_identity_for_write(case_id, case_identity)
        if kind not in EVIDENCE_KINDS:
            raise ValueError("evidence_kind")
        if adapter not in EVIDENCE_ADAPTERS or adapter == "hosted_search":
            raise ValueError("adapter")
        adapter_contract = {
            "manual": ("manual", {"manual_url", "manual_text", "document_reference"}),
            "sec_edgar": ("regulator", {"regulator_excerpt"}),
            "internal_news": ("publisher", {"publisher_excerpt"}),
            "ibkr_contract": (
                "market_infrastructure",
                {"market_infrastructure_snapshot"},
            ),
        }
        expected_family, expected_kinds = adapter_contract[adapter]
        family = source_family or expected_family
        if family not in EVIDENCE_SOURCE_FAMILIES or family != expected_family:
            raise ValueError("source_family")
        if kind not in expected_kinds:
            raise ValueError("evidence_kind")
        if document_status is not None and document_status not in DOCUMENT_STATUSES:
            raise ValueError("document_status")
        if kind == "document_reference" and document_status is None:
            raise ValueError("document_status")
        if kind != "document_reference" and document_status is not None:
            raise ValueError("document_status")
        if run_id is not None:
            run = self.get_investigation_run(run_id)
            if run["case_id"] != case_id or run["adapter"] != "manual":
                raise ValueError("run_case")
        if automation_run_id is not None:
            run = self.conn.execute(
                "SELECT case_id FROM security_lifecycle_automation_runs WHERE run_id=?",
                (automation_run_id,),
            ).fetchone()
            if run is None or str(run["case_id"]) != case_id:
                raise ValueError("automation_run_case")
        if run_id is not None and automation_run_id is not None:
            raise ValueError("run_identity")
        if adapter == "manual" and automation_run_id is not None:
            raise ValueError("automation_run_id")
        if adapter != "manual" and (run_id is not None or automation_run_id is None):
            raise ValueError("automation_run_id")
        excerpt_text = _bounded_text(
            "excerpt", excerpt, max_length=16000, required=True
        )
        source_url_text = _bounded_text("source_url", source_url, max_length=1000)
        if source_url_text is not None and not source_url_text.startswith("https://"):
            raise ValueError("source_url")
        evidence_id = self._new_id("sle")
        excerpt_sha256 = hashlib.sha256(excerpt_text.encode("utf-8")).hexdigest()
        document_sha256 = (
            None
            if source_document_sha256 is None
            else _canonical_sha256("source_document_sha256", source_document_sha256)
        )
        locator_json = (
            None
            if source_locator is None
            else _canonical_json(source_locator, max_bytes=4096, name="source_locator")
        )
        if adapter == "sec_edgar" and (
            document_sha256 is None or locator_json is None
        ):
            raise ValueError("source_locator")
        dedupe_key = _bounded_text(
            "evidence_dedupe_key",
            evidence_dedupe_key or f"evidence:{evidence_id}",
            max_length=500,
            required=True,
        )
        with self.conn:
            if identity is not None:
                self._upsert_case_row(case_id, identity, at=at)
            self.conn.execute(
                "INSERT INTO security_lifecycle_evidence "
                "(evidence_id,case_id,run_id,automation_run_id,source_family,kind,"
                "source_url,title,publisher,domain,source_published_at,retrieved_at,"
                "adapter,excerpt,content_sha256,source_document_sha256,"
                "source_locator_json,evidence_dedupe_key,mime_type,document_status,"
                "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    evidence_id,
                    case_id,
                    run_id,
                    automation_run_id,
                    family,
                    kind,
                    source_url_text,
                    _bounded_text("title", title, max_length=500),
                    _bounded_text("publisher", publisher, max_length=240),
                    _bounded_text("domain", domain, max_length=253),
                    source_published_at,
                    retrieved_at,
                    adapter,
                    excerpt_text,
                    excerpt_sha256,
                    document_sha256,
                    locator_json,
                    dedupe_key,
                    _bounded_text("mime_type", mime_type, max_length=127),
                    document_status,
                    at,
                ),
            )
        return evidence_id

    def list_evidence(self, case_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM security_lifecycle_evidence "
                "WHERE case_id=? ORDER BY created_at,evidence_id",
                (case_id,),
            )
        ]

    def create_assessment(
        self,
        *,
        case_id: str,
        relevance: str,
        confidence: str,
        author: str,
        conclusion: str,
        impact_summary: str,
        outcomes: Iterable[str],
        citations: Iterable[Mapping[str, object]],
        observation_fingerprint_sha256: str,
        at: str,
        counterparty_name: str | None = None,
        counterparty_ticker: str | None = None,
        counterparty_cik: str | None = None,
        successor_ticker: str | None = None,
        destination_venue: str | None = None,
        effective_date: str | None = None,
        consideration_currency: str | None = None,
        cash_per_security_decimal: object = None,
        exchange_ratio_decimal: object = None,
        case_identity: Mapping[str, object] | None = None,
        automation_method: str | None = None,
        automation_run_id: str | None = None,
        rule_id: str | None = None,
        rule_version: str | None = None,
        decision_provenance_sha256: str | None = None,
    ) -> str:
        self._assert_write()
        identity = self._case_identity_for_write(case_id, case_identity)
        if relevance not in ASSESSMENT_RELEVANCE:
            raise ValueError("relevance")
        if confidence not in ASSESSMENT_CONFIDENCE:
            raise ValueError("confidence")
        if author not in ASSESSMENT_AUTHORS:
            raise ValueError("author")
        if author == "automation":
            if automation_method not in AUTOMATION_METHODS:
                raise ValueError("automation_method")
            run = self.conn.execute(
                "SELECT case_id FROM security_lifecycle_automation_runs WHERE run_id=?",
                (automation_run_id,),
            ).fetchone()
            if run is None or str(run["case_id"]) != case_id:
                raise ValueError("automation_run_id")
            automation_rule_id = _bounded_text(
                "rule_id", rule_id, max_length=160, required=True
            )
            automation_rule_version = _bounded_text(
                "rule_version", rule_version, max_length=120, required=True
            )
            automation_provenance = _canonical_sha256(
                "decision_provenance", decision_provenance_sha256
            )
        else:
            if any(
                value is not None
                for value in (
                    automation_method,
                    automation_run_id,
                    rule_id,
                    rule_version,
                    decision_provenance_sha256,
                )
            ):
                raise ValueError("automation_provenance")
            automation_rule_id = None
            automation_rule_version = None
            automation_provenance = None
        outcome_values = tuple(sorted(set(str(value) for value in outcomes)))
        if not outcome_values or any(value not in ASSESSMENT_OUTCOMES for value in outcome_values):
            raise ValueError("outcome")
        if "symbol_or_venue_changed" in outcome_values:
            raise ValueError("legacy_outcome")
        citation_values: list[dict[str, str | None]] = []
        for citation in citations:
            reference_kind = str(citation.get("reference_kind") or "")
            if reference_kind == "observation":
                if citation.get("evidence_id") is not None:
                    raise ValueError("citation")
                cited_hash = _canonical_sha256(
                    "citation", citation.get("cited_content_sha256")
                )
                citation_values.append(
                    {
                        "reference_kind": "observation",
                        "evidence_id": None,
                        "cited_content_sha256": cited_hash,
                    }
                )
            elif reference_kind == "evidence":
                evidence_id = str(citation.get("evidence_id") or "")
                row = self.conn.execute(
                    "SELECT case_id,content_sha256 FROM security_lifecycle_evidence "
                    "WHERE evidence_id=?",
                    (evidence_id,),
                ).fetchone()
                if row is None or row["case_id"] != case_id:
                    raise ValueError("citation")
                citation_values.append(
                    {
                        "reference_kind": "evidence",
                        "evidence_id": evidence_id,
                        "cited_content_sha256": str(row["content_sha256"]),
                    }
                )
            else:
                raise ValueError("citation")
        revision = int(
            self.conn.execute(
                "SELECT COALESCE(MAX(revision),0)+1 "
                "FROM security_lifecycle_assessments WHERE case_id=?",
                (case_id,),
            ).fetchone()[0]
        )
        assessment_id = self._new_id("sla")
        with self.conn:
            if identity is not None:
                self._upsert_case_row(case_id, identity, at=at)
            self.conn.execute(
                "INSERT INTO security_lifecycle_assessments "
                "(assessment_id,case_id,revision,status,relevance,confidence,author,"
                "conclusion,impact_summary,counterparty_name,counterparty_ticker,"
                "counterparty_cik,successor_ticker,destination_venue,effective_date,"
                "consideration_currency,cash_per_security_decimal,"
                "exchange_ratio_decimal,observation_fingerprint_sha256,"
                "evidence_set_sha256,created_at,accepted_at,superseded_at,"
                "automation_method,acceptance_authority,automation_run_id,rule_id,"
                "rule_version,decision_provenance_sha256) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    assessment_id,
                    case_id,
                    revision,
                    "draft",
                    relevance,
                    confidence,
                    author,
                    _bounded_text("conclusion", conclusion, max_length=4000, required=True),
                    _bounded_text("impact_summary", impact_summary, max_length=4000, required=True),
                    _bounded_text("counterparty_name", counterparty_name, max_length=240),
                    _bounded_text("counterparty_ticker", counterparty_ticker, max_length=20),
                    _canonical_cik(counterparty_cik),
                    _bounded_text("successor_ticker", successor_ticker, max_length=20),
                    _bounded_text("destination_venue", destination_venue, max_length=120),
                    _canonical_date(effective_date, name="effective_date"),
                    _canonical_currency(consideration_currency),
                    canonical_assessment_decimal(
                        cash_per_security_decimal, name="cash_per_security"
                    ),
                    canonical_assessment_decimal(
                        exchange_ratio_decimal, name="exchange_ratio"
                    ),
                    _canonical_sha256(
                        "observation_fingerprint", observation_fingerprint_sha256
                    ),
                    self._evidence_set_sha256(case_id),
                    at,
                    None,
                    None,
                    automation_method,
                    None,
                    automation_run_id,
                    automation_rule_id,
                    automation_rule_version,
                    automation_provenance,
                ),
            )
            self.conn.executemany(
                "INSERT INTO security_lifecycle_assessment_outcomes "
                "(assessment_id,outcome) VALUES (?,?)",
                [(assessment_id, outcome) for outcome in outcome_values],
            )
            self.conn.executemany(
                "INSERT INTO security_lifecycle_assessment_evidence "
                "(assessment_id,reference_kind,evidence_id,cited_content_sha256) "
                "VALUES (?,?,?,?)",
                [
                    (
                        assessment_id,
                        item["reference_kind"],
                        item["evidence_id"],
                        item["cited_content_sha256"],
                    )
                    for item in citation_values
                ],
            )
        return assessment_id

    def get_assessment(self, assessment_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM security_lifecycle_assessments WHERE assessment_id=?",
            (assessment_id,),
        ).fetchone()
        if row is None:
            raise KeyError("assessment_not_found")
        item = dict(row)
        item["outcomes"] = [
            str(value[0])
            for value in self.conn.execute(
                "SELECT outcome FROM security_lifecycle_assessment_outcomes "
                "WHERE assessment_id=? ORDER BY outcome",
                (assessment_id,),
            )
        ]
        item["citations"] = [
            dict(value)
            for value in self.conn.execute(
                "SELECT reference_kind,evidence_id,cited_content_sha256 "
                "FROM security_lifecycle_assessment_evidence "
                "WHERE assessment_id=? ORDER BY id",
                (assessment_id,),
            )
        ]
        return item

    def list_assessments(self, case_id: str) -> list[dict]:
        return [
            self.get_assessment(str(row[0]))
            for row in self.conn.execute(
                "SELECT assessment_id FROM security_lifecycle_assessments "
                "WHERE case_id=? ORDER BY revision DESC",
                (case_id,),
            )
        ]

    def accept_assessment(
        self,
        assessment_id: str,
        *,
        observation_fingerprint_sha256: str,
        at: str,
    ) -> dict:
        self._assert_write()
        assessment = self.get_assessment(assessment_id)
        if assessment["status"] != "draft":
            raise ValueError("assessment_not_draft")
        if assessment["author"] not in ASSESSMENT_AUTHORS:
            raise ValueError("author")
        if assessment["relevance"] == "undetermined" or not any(
            outcome != "undetermined" for outcome in assessment["outcomes"]
        ):
            raise ValueError("conclusive assessment required")
        if not assessment["citations"]:
            raise ValueError("citation required")
        observation_citations = [
            citation
            for citation in assessment["citations"]
            if citation["reference_kind"] == "observation"
        ]
        if not observation_citations:
            raise ValueError("observation_citation_required")
        if assessment["observation_fingerprint_sha256"] != observation_fingerprint_sha256:
            raise ValueError("stale_assessment")
        if any(
            citation["cited_content_sha256"] != observation_fingerprint_sha256
            for citation in observation_citations
        ):
            raise ValueError("stale_citation")
        if assessment["evidence_set_sha256"] != self._evidence_set_sha256(
            assessment["case_id"]
        ):
            raise ValueError("stale_assessment")
        with self.conn:
            acceptance_authority = (
                "legacy_migration"
                if assessment["author"] == "legacy_review"
                else "human"
            )
            self.conn.execute(
                "UPDATE security_lifecycle_assessments SET status='superseded',"
                "superseded_at=? WHERE case_id=? AND status='accepted'",
                (at, assessment["case_id"]),
            )
            self.conn.execute(
                "UPDATE security_lifecycle_assessments SET status='accepted',"
                "accepted_at=?,acceptance_authority=? WHERE assessment_id=?",
                (at, acceptance_authority, assessment_id),
            )
        return self.get_assessment(assessment_id)

    def acknowledge_case(
        self,
        *,
        case_id: str,
        reason: str,
        note: str | None,
        author: str,
        observation_fingerprint_sha256: str,
        at: str,
    ) -> str:
        self._assert_write()
        self._case_row(case_id)
        if reason not in ACKNOWLEDGEMENT_REASONS:
            raise ValueError("reason")
        if author != "human":
            raise ValueError("author")
        has_manual = self.conn.execute(
            "SELECT 1 FROM security_lifecycle_evidence "
            "WHERE case_id=? AND adapter='manual' LIMIT 1",
            (case_id,),
        ).fetchone()
        has_success = self.conn.execute(
            "SELECT 1 FROM security_lifecycle_investigation_runs "
            "WHERE case_id=? AND status='succeeded' LIMIT 1",
            (case_id,),
        ).fetchone()
        if has_manual is None and has_success is None:
            raise ValueError("investigation evidence required")
        acknowledgement_id = self._new_id("slk")
        with self.conn:
            self.conn.execute(
                "INSERT INTO security_lifecycle_case_acknowledgements "
                "(acknowledgement_id,case_id,reason,note,author,"
                "observation_fingerprint_sha256,evidence_set_sha256,"
                "acknowledged_at,reopened_at) VALUES (?,?,?,?,?,?,?,?,NULL)",
                (
                    acknowledgement_id,
                    case_id,
                    reason,
                    _bounded_text("note", note, max_length=2000),
                    author,
                    observation_fingerprint_sha256,
                    self._evidence_set_sha256(case_id),
                    at,
                ),
            )
        return acknowledgement_id

    def reopen_acknowledgement(self, acknowledgement_id: str, *, at: str) -> None:
        self._assert_write()
        row = self.conn.execute(
            "SELECT reopened_at FROM security_lifecycle_case_acknowledgements "
            "WHERE acknowledgement_id=?",
            (acknowledgement_id,),
        ).fetchone()
        if row is None:
            raise KeyError("acknowledgement_not_found")
        if row["reopened_at"] is not None:
            raise ValueError("acknowledgement_already_reopened")
        with self.conn:
            self.conn.execute(
                "UPDATE security_lifecycle_case_acknowledgements "
                "SET reopened_at=? WHERE acknowledgement_id=?",
                (at, acknowledgement_id),
            )

    def _acknowledgements(
        self,
        case_id: str,
        *,
        observation_fingerprint_sha256: str,
    ) -> list[dict]:
        evidence_digest = self._evidence_set_sha256(case_id)
        return [
            {
                **dict(row),
                "stale": (
                    row["observation_fingerprint_sha256"]
                    != observation_fingerprint_sha256
                    or row["evidence_set_sha256"] != evidence_digest
                ),
            }
            for row in self.conn.execute(
                "SELECT * FROM security_lifecycle_case_acknowledgements "
                "WHERE case_id=? ORDER BY acknowledged_at DESC,acknowledgement_id DESC",
                (case_id,),
            )
        ]

    def project_case_state(
        self,
        case_id: str,
        *,
        observation_fingerprint_sha256: str,
    ) -> dict:
        self._case_row(case_id)
        evidence = self.list_evidence(case_id)
        runs = self.list_investigation_runs(case_id)
        assessments = self.list_assessments(case_id)
        evidence_digest = self._evidence_set_sha256(case_id)
        rendered_assessments = [
            {
                **assessment,
                "stale": (
                    assessment["observation_fingerprint_sha256"]
                    != observation_fingerprint_sha256
                    or assessment["evidence_set_sha256"] != evidence_digest
                ),
            }
            for assessment in assessments
        ]
        current_assessment = next(
            (
                assessment
                for assessment in rendered_assessments
                if assessment["status"] == "accepted" and not assessment["stale"]
            ),
            None,
        )
        acknowledgements = self._acknowledgements(
            case_id,
            observation_fingerprint_sha256=observation_fingerprint_sha256,
        )
        current_acknowledgement = next(
            (
                acknowledgement
                for acknowledgement in acknowledgements
                if acknowledgement["reopened_at"] is None
                and not acknowledgement["stale"]
            ),
            None,
        )
        if current_assessment is not None:
            workflow_state = "resolved"
        elif current_acknowledgement is not None:
            workflow_state = "reviewed_inconclusive"
        elif any(run["status"] in {"queued", "running"} for run in runs):
            workflow_state = "investigating"
        elif evidence or any(run["status"] == "succeeded" for run in runs):
            workflow_state = "evidence_ready"
        else:
            workflow_state = "unresolved"
        return {
            "workflow_state": workflow_state,
            "current_assessment": current_assessment,
            "assessment_history": rendered_assessments,
            "current_acknowledgement": current_acknowledgement,
            "acknowledgement_history": acknowledgements,
        }

    def _current_accepted_assessment(
        self,
        case_id: str,
        *,
        observation_fingerprint_sha256: str,
    ) -> dict | None:
        return self.project_case_state(
            case_id,
            observation_fingerprint_sha256=observation_fingerprint_sha256,
        )["current_assessment"]

    def generate_action_proposals(
        self,
        *,
        case_id: str,
        observation_fingerprint_sha256: str,
        sources_by_ticker: Mapping[str, Iterable[str]] | None,
        at: str,
    ) -> dict:
        self._assert_write()
        case = self._case_row(case_id)
        assessment = self._current_accepted_assessment(
            case_id,
            observation_fingerprint_sha256=observation_fingerprint_sha256,
        )
        if assessment is None:
            has_accepted = self.conn.execute(
                "SELECT 1 FROM security_lifecycle_assessments "
                "WHERE case_id=? AND status='accepted'",
                (case_id,),
            ).fetchone()
            return {
                "proposals": [],
                "block_reason": "stale_assessment" if has_accepted else None,
            }
        if sources_by_ticker is None:
            return {"proposals": [], "block_reason": "source_context_unavailable"}
        sources = tuple(sorted(set(sources_by_ticker.get(str(case["ticker"]), ()))))
        source_json = _canonical_json(list(sources), max_bytes=4096, name="sources")
        outcomes = set(assessment["outcomes"])
        action_rows: list[tuple[str, str | None, str | None]] = []
        if assessment["relevance"] == "issuer_related":
            action_rows = [("notify", None, None), ("keep_tracking", None, None)]
        elif assessment["relevance"] == "unrelated":
            action_rows = [("no_action", None, None)]
        elif assessment["relevance"] == "direct_tracked_security":
            action_rows.append(("notify", None, None))
            if "portfolio_open" in sources:
                action_rows.append(
                    ("review_portfolio_position", None, "portfolio_position_open")
                )
            successor_ticker = str(assessment["successor_ticker"] or "").strip()
            if (
                "symbol_changed" in outcomes
                and not outcomes
                & {
                    "acquisition_cash",
                    "acquisition_stock",
                    "acquisition_mixed",
                    "acquisition_terms_unknown",
                    "listing_ended",
                    "symbol_or_venue_changed",
                    "undetermined",
                }
                and successor_ticker
                and successor_ticker.upper() != str(case["ticker"]).upper()
            ):
                action_rows.append(("remap_symbol", successor_ticker, None))
            if outcomes == {"venue_transfer"}:
                action_rows.append(("keep_tracking", None, None))
            if "portfolio_open" not in sources:
                if outcomes & {
                    "listing_ended",
                    "acquisition_cash",
                    "acquisition_stock",
                    "acquisition_mixed",
                    "acquisition_terms_unknown",
                }:
                    if "manual_lists" in sources:
                        action_rows.append(("archive_manual_memberships", None, None))
                    if sources and set(sources) & {
                        "sa_alpha_picks_current",
                        "legacy_config_seed",
                    }:
                        action_rows.append(("hide_from_active_universe", None, None))
        current_assessment_fingerprint = assessment_fingerprint(assessment)
        created: list[dict] = []
        for action_type, replacement_ticker, block_reason in action_rows:
            if action_type not in PROPOSAL_ACTIONS:
                raise ValueError("proposal_action")
            dedupe_key = "\0".join(
                (
                    assessment["assessment_id"],
                    action_type,
                    str(case["ticker"]),
                    replacement_ticker or "",
                )
            )
            existing = self.conn.execute(
                "SELECT proposal_id FROM security_lifecycle_action_proposals "
                "WHERE proposal_dedupe_key=?",
                (dedupe_key,),
            ).fetchone()
            if existing is None:
                proposal_id = self._new_id("slp")
                with self.conn:
                    self.conn.execute(
                        "INSERT INTO security_lifecycle_action_proposals "
                        "(proposal_id,case_id,assessment_id,action_type,status,"
                        "source_ticker,replacement_ticker,source_snapshot_json,reason,"
                        "block_reason,assessment_fingerprint_sha256,proposal_dedupe_key,"
                        "created_at,dismissed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
                        (
                            proposal_id,
                            case_id,
                            assessment["assessment_id"],
                            action_type,
                            "proposed",
                            case["ticker"],
                            replacement_ticker,
                            source_json,
                            f"Derived from accepted assessment revision {assessment['revision']}.",
                            block_reason,
                            current_assessment_fingerprint,
                            dedupe_key,
                            at,
                        ),
                    )
            else:
                proposal_id = str(existing["proposal_id"])
            created.append(self.get_proposal(proposal_id))
        return {"proposals": created, "block_reason": None}

    def get_proposal(self, proposal_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM security_lifecycle_action_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError("proposal_not_found")
        return dict(row)

    def list_proposals(self, case_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM security_lifecycle_action_proposals "
                "WHERE case_id=? ORDER BY created_at,proposal_id",
                (case_id,),
            )
        ]

    def dismiss_proposal(self, proposal_id: str, *, at: str) -> dict:
        self._assert_write()
        proposal = self.get_proposal(proposal_id)
        if proposal["status"] != "proposed":
            raise ValueError("proposal_not_proposed")
        with self.conn:
            self.conn.execute(
                "UPDATE security_lifecycle_action_proposals "
                "SET status='dismissed',dismissed_at=? WHERE proposal_id=?",
                (at, proposal_id),
            )
        return self.get_proposal(proposal_id)

    def project_proposals(
        self,
        case_id: str,
        *,
        observation_fingerprint_sha256: str,
    ) -> list[dict]:
        evidence_digest = self._evidence_set_sha256(case_id)
        current_assessment = self._current_accepted_assessment(
            case_id,
            observation_fingerprint_sha256=observation_fingerprint_sha256,
        )
        rendered = []
        for proposal in self.list_proposals(case_id):
            assessment = self.get_assessment(str(proposal["assessment_id"]))
            stale = (
                current_assessment is None
                or assessment["assessment_id"]
                != current_assessment["assessment_id"]
                or assessment["observation_fingerprint_sha256"]
                != observation_fingerprint_sha256
                or assessment["evidence_set_sha256"] != evidence_digest
                or proposal["assessment_fingerprint_sha256"]
                != assessment_fingerprint(assessment)
            )
            rendered.append(
                {
                    **proposal,
                    "projected_block_reason": (
                        "stale_assessment" if stale else proposal["block_reason"]
                    ),
                }
            )
        return rendered


def _read_profile(
    path: Path,
    *,
    observation_fingerprints: Mapping[str, str],
) -> tuple[list[dict], dict[str, dict]]:
    if not path.is_file():
        return [], {}
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if not _component_tables(conn):
            raise LifecycleSchemaMismatch("profile lifecycle schema is absent")
        verify_profile_connection(conn)
        cases = [
            dict(row)
            for row in conn.execute(
                "SELECT case_id,source,source_ref,ticker FROM security_lifecycle_cases "
                "ORDER BY source,source_ref,ticker"
            )
        ]
        store = SecurityLifecycleInvestigationStore(conn)
        projections: dict[str, dict] = {}
        for case in cases:
            case_id = str(case["case_id"])
            fingerprint = observation_fingerprints.get(case_id, "")
            state = store.project_case_state(
                case_id,
                observation_fingerprint_sha256=fingerprint,
            )
            runs = store.list_investigation_runs(case_id)
            evidence = store.list_evidence(case_id)
            proposals = store.project_proposals(
                case_id,
                observation_fingerprint_sha256=fingerprint,
            )
            has_history = any(
                (
                    runs,
                    evidence,
                    state["assessment_history"],
                    state["acknowledgement_history"],
                    proposals,
                )
            )
            if has_history:
                projections[case_id] = {
                    **state,
                    "investigation_runs": runs,
                    "evidence": evidence,
                    "proposals": proposals,
                }
        return cases, projections
    finally:
        conn.close()


def compose_security_lifecycle(market_db_path: str, profile_db_path: str) -> dict:
    try:
        observations = read_market_observations(market_db_path, limit=None)
    except (OSError, sqlite3.Error, LifecycleSchemaMismatch):
        raise LifecycleStoreUnavailable("market") from None
    by_case: dict[str, dict] = {}
    fingerprints: dict[str, str] = {}
    for observation in observations:
        case_id = case_id_for(
            observation["source"], observation["source_ref"], observation["ticker"]
        )
        fingerprints[case_id] = observation_fingerprint(observation)
        by_case[case_id] = {
            "case_id": case_id,
            "source": observation["source"],
            "source_ref": observation["source_ref"],
            "ticker": observation["ticker"],
            "source_presence": "present",
            "workflow_state": "unresolved",
            "observation": observation,
            "current_assessment": None,
        }
    try:
        profile_cases, profile_projections = _read_profile(
            Path(profile_db_path),
            observation_fingerprints=fingerprints,
        )
    except (OSError, sqlite3.Error, LifecycleSchemaMismatch):
        raise LifecycleStoreUnavailable("profile") from None
    for case in profile_cases:
        by_case.setdefault(
            case["case_id"],
            {
                **case,
                "source_presence": "source_missing",
                "workflow_state": "unresolved",
                "observation": None,
                "current_assessment": None,
            },
        )

    for case_id, projection in profile_projections.items():
        if case_id not in by_case:
            continue
        by_case[case_id].update(projection)

    cases = sorted(
        by_case.values(),
        key=lambda item: (
            -(int(str(item["observation"]["filing_date"]).replace("-", "")) if item["observation"] else 0),
            item["case_id"],
        ),
    )
    return {"cases": cases}


__all__ = [
    "LifecycleStoreUnavailable",
    "LifecycleWritesUnavailable",
    "SecurityLifecycleInvestigationStore",
    "canonical_assessment_decimal",
    "case_id_for",
    "compose_security_lifecycle",
    "observation_fingerprint",
]
