"""Profile-side case identity, history, and cross-store read composition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Callable, Optional
import uuid

from src.security_lifecycle import read_market_observations
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    LifecycleWritesUnavailable,
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

    def _new_id(self, prefix: str) -> str:
        ordinal = self._id_ordinals.get(prefix, 0) + 1
        self._id_ordinals[prefix] = ordinal
        if self._id_factory is not None:
            return self._id_factory(prefix, ordinal)
        return f"{prefix}_{uuid.uuid4().hex}"

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
            self.conn.execute(
                "INSERT INTO security_lifecycle_cases "
                "(case_id,source,source_ref,ticker,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(case_id) DO UPDATE SET updated_at=excluded.updated_at",
                (case_id, source, source_ref, ticker, at, at),
            )
        return case_id

    def insert_legacy_assessment(
        self,
        *,
        source: str,
        source_ref: str,
        ticker: str,
        reviewed_state: str,
        reviewed_at: str,
        observation_fingerprint_sha256: str,
        assessment_id: str | None = None,
    ) -> str:
        self._assert_write()
        mapping = {
            "inactive_confirmed": (
                "listing_ended",
                "Legacy review marked the tracked security inactive.",
                "The legacy review did not retain supporting rationale.",
            ),
            "renamed_or_transferred": (
                "symbol_or_venue_changed",
                "Legacy review marked a symbol or venue change.",
                "The legacy label did not distinguish renaming from transfer.",
            ),
        }
        if reviewed_state not in mapping:
            raise ValueError("reviewed_state")
        outcome, conclusion, impact = mapping[reviewed_state]
        case_id = self.ensure_case(
            source=source,
            source_ref=source_ref,
            ticker=ticker,
            at=reviewed_at,
        )
        row = self.conn.execute(
            "SELECT COALESCE(MAX(revision),0)+1 FROM security_lifecycle_assessments "
            "WHERE case_id=?",
            (case_id,),
        ).fetchone()
        revision = int(row[0])
        assessment_id = assessment_id or self._new_id("sla")
        with self.conn:
            self.conn.execute(
                "INSERT INTO security_lifecycle_assessments "
                "(assessment_id,case_id,revision,status,relevance,confidence,author,"
                "conclusion,impact_summary,observation_fingerprint_sha256,"
                "evidence_set_sha256,created_at,accepted_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    assessment_id,
                    case_id,
                    revision,
                    "accepted",
                    "direct_tracked_security",
                    "unknown",
                    "legacy_review",
                    conclusion,
                    impact,
                    observation_fingerprint_sha256,
                    empty_evidence_set_sha256(),
                    reviewed_at,
                    reviewed_at,
                ),
            )
            self.conn.execute(
                "INSERT INTO security_lifecycle_assessment_outcomes "
                "(assessment_id,outcome) VALUES (?,?)",
                (assessment_id, outcome),
            )
            self.conn.execute(
                "INSERT INTO security_lifecycle_assessment_evidence "
                "(assessment_id,reference_kind,evidence_id,cited_content_sha256) "
                "VALUES (?,'observation',NULL,?)",
                (assessment_id, observation_fingerprint_sha256),
            )
        return assessment_id


def _read_profile(path: Path) -> tuple[list[dict], dict[str, list[dict]]]:
    if not path.is_file():
        return [], {}
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if not _component_tables(conn):
            return [], {}
        verify_profile_connection(conn)
        cases = [
            dict(row)
            for row in conn.execute(
                "SELECT case_id,source,source_ref,ticker FROM security_lifecycle_cases "
                "ORDER BY source,source_ref,ticker"
            )
        ]
        histories: dict[str, list[dict]] = {}
        rows = conn.execute(
            "SELECT * FROM security_lifecycle_assessments "
            "ORDER BY case_id,revision DESC"
        ).fetchall()
        for row in rows:
            item = dict(row)
            item["outcomes"] = [
                str(outcome[0])
                for outcome in conn.execute(
                    "SELECT outcome FROM security_lifecycle_assessment_outcomes "
                    "WHERE assessment_id=? ORDER BY outcome",
                    (item["assessment_id"],),
                )
            ]
            histories.setdefault(str(item["case_id"]), []).append(item)
        return cases, histories
    finally:
        conn.close()


def compose_security_lifecycle(market_db_path: str, profile_db_path: str) -> dict:
    try:
        observations = read_market_observations(market_db_path)
    except (OSError, sqlite3.Error, LifecycleSchemaMismatch):
        raise LifecycleStoreUnavailable("market") from None
    try:
        profile_cases, histories = _read_profile(Path(profile_db_path))
    except (OSError, sqlite3.Error, LifecycleSchemaMismatch):
        raise LifecycleStoreUnavailable("profile") from None

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

    for case_id, history in histories.items():
        if case_id not in by_case:
            continue
        fingerprint = fingerprints.get(case_id)
        rendered_history = []
        current = None
        for assessment in history:
            stale = (
                fingerprint is None
                or assessment["observation_fingerprint_sha256"] != fingerprint
            )
            rendered = {**assessment, "stale": stale}
            rendered_history.append(rendered)
            if assessment["status"] == "accepted" and not stale and current is None:
                current = rendered
        by_case[case_id]["assessment_history"] = rendered_history
        by_case[case_id]["current_assessment"] = current
        if current is not None:
            by_case[case_id]["workflow_state"] = "resolved"

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
    "case_id_for",
    "compose_security_lifecycle",
    "observation_fingerprint",
]
