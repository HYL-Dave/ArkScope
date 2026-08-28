from __future__ import annotations

import sqlite3

import pytest


_AT = "2026-08-25T00:00:00Z"
_HEX_A = "a" * 64
_HEX_B = "b" * 64
_HEX_C = "c" * 64
_V2_AUTOMATION_BLOCKER_CODES = frozenset(
    {
        "sec_identity_unconfigured",
        "sec_governor_unavailable",
        "sec_request_budget_exhausted",
        "sec_rate_limited",
        "sec_access_denied",
        "sec_transport_unavailable",
        "sec_document_unavailable",
        "sec_evidence_insufficient",
        "internal_news_unavailable",
        "internal_news_schema_mismatch",
        "ibkr_gateway_unavailable",
        "ibkr_contract_missing",
        "ibkr_contract_ambiguous",
        "ibkr_entitlement_denied",
        "market_confirmation_missing",
        "source_conflict",
        "impact_context_requested",
        "transition_approval_changed",
        "transition_approval_unavailable",
    }
)
_V3_LISTING_BLOCKER_CODES = frozenset(
    {
        "listing_directory_unavailable",
        "listing_directory_schema_mismatch",
        "listing_directory_stale",
        "listing_status_unresolved",
        "listing_authority_conflict",
        "massive_credential_missing",
        "massive_access_denied",
        "massive_rate_limited",
        "massive_reference_unavailable",
    }
)


def _tables(conn: sqlite3.Connection, prefix: str) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
            (f"{prefix}%",),
        )
    }


def _indexes(conn: sqlite3.Connection, prefix: str) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE ? AND sql IS NOT NULL",
            (f"{prefix}%",),
        )
    }


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]


def _schema_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    assert row is not None
    return str(row[0])


def _insert_case(conn: sqlite3.Connection, case_id: str = "slc_case") -> None:
    conn.execute(
        "INSERT INTO security_lifecycle_cases "
        "(case_id,source,source_ref,ticker,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (case_id, "sec_edgar", "0000000000-26-000001", "OLD", _AT, _AT),
    )


def _insert_automation_run(
    conn: sqlite3.Connection,
    *,
    run_id: str = "sla_run",
    status: str = "running",
) -> None:
    conn.execute(
        "INSERT INTO security_lifecycle_automation_runs "
        "(run_id,case_id,mode,observation_fingerprint_sha256,policy_version,"
        "run_key,status,decision_tier,action_readiness,query_context_json,"
        "diagnostics_json,retry_at,failure_code,started_at,finished_at,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            "slc_case",
            "historical",
            _HEX_A,
            "policy-v1",
            f"run-key:{run_id}",
            status,
            None,
            None,
            "{}",
            "{}",
            None,
            None,
            _AT if status == "running" else None,
            None,
            _AT,
            _AT,
        ),
    )


def _insert_evidence(
    conn: sqlite3.Connection,
    *,
    evidence_id: str,
    source_family: str,
    adapter: str,
    kind: str,
    automation_run_id: str | None,
    source_document_sha256: str | None,
    source_locator_json: str | None,
    content_sha256: str = _HEX_B,
) -> None:
    conn.execute(
        "INSERT INTO security_lifecycle_evidence "
        "(evidence_id,case_id,run_id,automation_run_id,source_family,kind,"
        "source_url,title,publisher,domain,source_published_at,retrieved_at,adapter,"
        "excerpt,content_sha256,source_document_sha256,source_locator_json,"
        "evidence_dedupe_key,mime_type,document_status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            evidence_id,
            "slc_case",
            None,
            automation_run_id,
            source_family,
            kind,
            "https://www.sec.gov/Archives/example.htm",
            "Source title",
            "SEC",
            "www.sec.gov",
            "2026-08-24",
            _AT,
            adapter,
            "Verbatim source excerpt.",
            content_sha256,
            source_document_sha256,
            source_locator_json,
            f"dedupe:{evidence_id}",
            "text/html",
            None,
            _AT,
        ),
    )


def _insert_assessment(
    conn: sqlite3.Connection,
    *,
    assessment_id: str,
    revision: int,
    status: str,
    author: str,
    acceptance_authority: str | None,
    automation_method: str | None = None,
    automation_run_id: str | None = None,
    rule_id: str | None = None,
    rule_version: str | None = None,
    decision_provenance_sha256: str | None = None,
) -> None:
    accepted_at = _AT if status in {"accepted", "superseded"} else None
    superseded_at = _AT if status == "superseded" else None
    conn.execute(
        "INSERT INTO security_lifecycle_assessments "
        "(assessment_id,case_id,revision,status,relevance,confidence,author,"
        "conclusion,impact_summary,observation_fingerprint_sha256,"
        "evidence_set_sha256,created_at,accepted_at,superseded_at,"
        "automation_method,acceptance_authority,automation_run_id,rule_id,"
        "rule_version,decision_provenance_sha256) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            assessment_id,
            "slc_case",
            revision,
            status,
            "direct_tracked_security",
            "high",
            author,
            "The cited evidence supports this conclusion.",
            "Tracking impact is explicit.",
            _HEX_A,
            _HEX_B,
            _AT,
            accepted_at,
            superseded_at,
            automation_method,
            acceptance_authority,
            automation_run_id,
            rule_id,
            rule_version,
            decision_provenance_sha256,
        ),
    )


def _insert_transition(
    conn: sqlite3.Connection,
    *,
    transition_id: str,
    approval_authority: str,
    automation_policy_version: str | None,
    rule_id: str | None,
    rule_version: str | None,
    decision_provenance_sha256: str = _HEX_C,
) -> None:
    conn.execute(
        "INSERT INTO ticker_identity_transitions "
        "(transition_id,case_id,assessment_id,proposal_ids_json,"
        "transition_dedupe_key,kind,status,source_ticker,successor_ticker,"
        "execute_on,priority_resolution,unhide_successor,"
        "approved_observation_fingerprint_sha256,"
        "approved_assessment_fingerprint_sha256,approved_preview_sha256,"
        "approved_preview_json,before_snapshot_json,after_snapshot_sha256,"
        "approved_at,updated_at,applied_at,cancelled_at,reversed_at,"
        "approval_authority,automation_policy_version,rule_id,rule_version,"
        "decision_provenance_sha256) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            transition_id,
            "slc_case",
            "sla_human",
            "[]",
            f"dedupe:{transition_id}",
            "symbol_continuation",
            "approved",
            "OLD",
            "NEW",
            "2026-08-26",
            None,
            0,
            _HEX_A,
            _HEX_B,
            _HEX_C,
            '{"eligible":true}',
            None,
            None,
            _AT,
            _AT,
            None,
            None,
            None,
            approval_authority,
            automation_policy_version,
            rule_id,
            rule_version,
            decision_provenance_sha256,
        ),
    )


def test_current_profile_authority_closes_automation_run_fact_translation_vocabularies(
    tmp_path,
):
    import src.security_lifecycle_schema as schema

    assert getattr(schema, "EVIDENCE_SOURCE_FAMILIES", None) == frozenset(
        {
            "regulator",
            "market_infrastructure",
            "publisher",
            "general_web",
            "manual",
            "listing_authority",
        }
    )
    assert getattr(schema, "EVIDENCE_ADAPTERS", None) == frozenset(
        {
            "sec_edgar",
            "internal_news",
            "ibkr_contract",
            "manual",
            "hosted_search",
            "nasdaq_symbol_directory",
            "massive_reference",
        }
    )
    assert getattr(schema, "AUTOMATION_MODES", None) == frozenset(
        {"live", "historical"}
    )
    assert getattr(schema, "AUTOMATION_RUN_STATUSES", None) == frozenset(
        {"queued", "running", "succeeded", "blocked", "failed", "cancelled"}
    )
    assert getattr(schema, "DECISION_TIERS", None) == frozenset(
        {"verified_automatic", "review_suggested"}
    )
    assert getattr(schema, "ACTION_READINESS", None) == frozenset(
        {
            "not_applicable",
            "waiting_effective_date",
            "waiting_market_confirmation",
            "waiting_transition_revalidation",
            "transition_eligible",
            "action_blocked",
        }
    )
    assert getattr(schema, "FACT_TYPES", None) == frozenset(
        {
            "source_ticker",
            "successor_ticker",
            "source_venue",
            "destination_venue",
            "effective_date",
            "security_class",
            "issuer_cik",
            "transaction_structure",
            "tracked_security_effect",
        }
    )
    assert getattr(schema, "AUTOMATION_BLOCKER_CODES", None) == (
        _V2_AUTOMATION_BLOCKER_CODES | _V3_LISTING_BLOCKER_CODES
    )
    assert getattr(schema, "FACT_SCALAR_TYPES", None) == frozenset(
        getattr(schema, "FACT_TYPES") - {"transaction_structure"}
    )
    assert getattr(schema, "TRANSACTION_TERMS_STATUSES", None) == frozenset(
        {"not_extracted", "partial", "complete"}
    )

    conn = sqlite3.connect(tmp_path / "profile.db")
    try:
        schema.create_profile_schema(conn)
        assert _tables(conn, "security_lifecycle_") == {
            "security_lifecycle_cases",
            "security_lifecycle_investigation_runs",
            "security_lifecycle_automation_runs",
            "security_lifecycle_automation_run_blockers",
            "security_lifecycle_evidence",
            "security_lifecycle_automation_facts",
            "security_lifecycle_evidence_translations",
            "security_lifecycle_assessments",
            "security_lifecycle_assessment_outcomes",
            "security_lifecycle_assessment_evidence",
            "security_lifecycle_case_acknowledgements",
            "security_lifecycle_action_proposals",
            "security_lifecycle_migration_receipts",
        }
        assert _columns(conn, "security_lifecycle_automation_runs") == [
            "run_id",
            "case_id",
            "mode",
            "observation_fingerprint_sha256",
            "policy_version",
            "run_key",
            "status",
            "decision_tier",
            "action_readiness",
            "query_context_json",
            "diagnostics_json",
            "retry_at",
            "failure_code",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        assert _columns(conn, "security_lifecycle_automation_run_blockers") == [
            "automation_run_id",
            "blocker_code",
            "retryable",
            "context_json",
            "created_at",
        ]
        assert _columns(conn, "security_lifecycle_automation_facts") == [
            "fact_id",
            "automation_run_id",
            "case_id",
            "evidence_id",
            "fact_type",
            "normalized_value_json",
            "source_span_start",
            "source_span_end",
            "cited_text_sha256",
            "extractor_rule_id",
            "extractor_rule_version",
            "fact_dedupe_key",
            "created_at",
        ]
        assert _columns(conn, "security_lifecycle_evidence_translations") == [
            "evidence_id",
            "evidence_content_sha256",
            "locale",
            "translated_text",
            "provider",
            "model",
            "harness",
            "translated_at",
        ]
        assert _indexes(conn, "idx_security_lifecycle_") == {
            "idx_security_lifecycle_cases_identity",
            "idx_security_lifecycle_runs_case_created",
            "idx_security_lifecycle_automation_runs_case_created",
            "idx_security_lifecycle_automation_blockers_run",
            "idx_security_lifecycle_evidence_case_created",
            "idx_security_lifecycle_evidence_automation_run",
            "idx_security_lifecycle_facts_run_type",
            "idx_security_lifecycle_translations_evidence_locale",
            "idx_security_lifecycle_assessments_case_revision",
            "idx_security_lifecycle_one_current_ack",
        }
    finally:
        conn.close()


def test_v3_schema_adds_listing_authority_without_removing_v2_values():
    from src.security_lifecycle_schema import create_profile_schema

    conn = sqlite3.connect(":memory:")
    try:
        create_profile_schema(conn)
        sql = _schema_sql(conn, "security_lifecycle_evidence")
        for value in (
            "listing_authority",
            "nasdaq_symbol_directory",
            "massive_reference",
            "listing_directory_snapshot",
            "publisher",
            "internal_news",
            "publisher_excerpt",
        ):
            assert f"'{value}'" in sql

        _insert_case(conn)
        _insert_automation_run(conn)
        for adapter in ("nasdaq_symbol_directory", "massive_reference"):
            _insert_evidence(
                conn,
                evidence_id=f"sle_{adapter}",
                source_family="listing_authority",
                adapter=adapter,
                kind="listing_directory_snapshot",
                automation_run_id="sla_run",
                source_document_sha256=_HEX_C,
                source_locator_json='{"candidate_ticker":"OLD"}',
            )
    finally:
        conn.close()


def test_v2_schema_remains_exact_and_rejects_v3_listing_rows():
    from src.security_lifecycle_schema import (
        PROFILE_INDEX_SQL,
        PROFILE_TABLE_SQL,
        V2_AUTOMATION_BLOCKER_CODES,
        V2_EVIDENCE_ADAPTERS,
        V2_EVIDENCE_KINDS,
        V2_EVIDENCE_SOURCE_FAMILIES,
        V2_PROFILE_INDEX_SQL,
        V2_PROFILE_TABLE_SQL,
        create_v2_profile_schema,
        verify_v2_profile_connection,
    )

    assert V2_PROFILE_INDEX_SQL == PROFILE_INDEX_SQL
    assert V2_AUTOMATION_BLOCKER_CODES == _V2_AUTOMATION_BLOCKER_CODES
    assert V2_EVIDENCE_SOURCE_FAMILIES == frozenset(
        {"regulator", "market_infrastructure", "publisher", "general_web", "manual"}
    )
    assert V2_EVIDENCE_ADAPTERS == frozenset(
        {"sec_edgar", "internal_news", "ibkr_contract", "manual", "hosted_search"}
    )
    assert V2_EVIDENCE_KINDS == frozenset(
        {
            "regulator_excerpt",
            "market_infrastructure_snapshot",
            "publisher_excerpt",
            "hosted_search_citation",
            "manual_url",
            "manual_text",
            "document_reference",
        }
    )
    assert {
        name: sql
        for name, sql in V2_PROFILE_TABLE_SQL.items()
        if name
        not in {
            "security_lifecycle_automation_run_blockers",
            "security_lifecycle_evidence",
        }
    } == {
        name: sql
        for name, sql in PROFILE_TABLE_SQL.items()
        if name
        not in {
            "security_lifecycle_automation_run_blockers",
            "security_lifecycle_evidence",
        }
    }

    conn = sqlite3.connect(":memory:")
    try:
        create_v2_profile_schema(conn)
        verify_v2_profile_connection(conn)
        sql = _schema_sql(conn, "security_lifecycle_evidence")
        for value in (
            "listing_authority",
            "nasdaq_symbol_directory",
            "massive_reference",
            "listing_directory_snapshot",
        ):
            assert f"'{value}'" not in sql

        _insert_case(conn)
        _insert_automation_run(conn)
        blocker_sql = _schema_sql(
            conn, "security_lifecycle_automation_run_blockers"
        )
        for code in _V2_AUTOMATION_BLOCKER_CODES:
            assert f"'{code}'" in blocker_sql
        for code in _V3_LISTING_BLOCKER_CODES:
            assert f"'{code}'" not in blocker_sql
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO security_lifecycle_automation_run_blockers "
                    "VALUES (?,?,?,?,?)",
                    ("sla_run", code, 1, "{}", _AT),
                )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_evidence(
                conn,
                evidence_id="sle_listing",
                source_family="listing_authority",
                adapter="nasdaq_symbol_directory",
                kind="listing_directory_snapshot",
                automation_run_id="sla_run",
                source_document_sha256=_HEX_C,
                source_locator_json='{"candidate_ticker":"OLD"}',
            )
    finally:
        conn.close()


def test_v3_schema_accepts_listing_blockers_and_retains_every_v2_code():
    from src.security_lifecycle_schema import (
        AUTOMATION_BLOCKER_CODES,
        create_profile_schema,
    )

    assert AUTOMATION_BLOCKER_CODES == (
        _V2_AUTOMATION_BLOCKER_CODES | _V3_LISTING_BLOCKER_CODES
    )
    conn = sqlite3.connect(":memory:")
    try:
        create_profile_schema(conn)
        _insert_case(conn)
        _insert_automation_run(conn)
        blocker_sql = _schema_sql(
            conn, "security_lifecycle_automation_run_blockers"
        )
        for code in AUTOMATION_BLOCKER_CODES:
            assert f"'{code}'" in blocker_sql
            conn.execute(
                "INSERT INTO security_lifecycle_automation_run_blockers "
                "VALUES (?,?,?,?,?)",
                ("sla_run", code, 1, "{}", _AT),
            )
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_automation_run_blockers"
        ).fetchone()[0] == len(AUTOMATION_BLOCKER_CODES)
    finally:
        conn.close()


def test_listing_evidence_requires_https_automation_document_digest_and_locator():
    from src.security_lifecycle_schema import create_profile_schema

    conn = sqlite3.connect(":memory:")
    try:
        create_profile_schema(conn)
        _insert_case(conn)
        _insert_automation_run(conn)
        valid = {
            "evidence_id": "sle_listing",
            "source_family": "listing_authority",
            "adapter": "massive_reference",
            "kind": "listing_directory_snapshot",
            "automation_run_id": "sla_run",
            "source_document_sha256": _HEX_C,
            "source_locator_json": '{"candidate_ticker":"OLD"}',
        }
        for column, value in (
            ("source_url", None),
            ("source_url", "http://api.massive.com/v3/reference/tickers"),
            ("automation_run_id", None),
            ("source_document_sha256", None),
            ("source_locator_json", None),
        ):
            conn.execute("SAVEPOINT invalid_listing")
            try:
                if column == "source_url":
                    with pytest.raises(sqlite3.IntegrityError):
                        conn.execute(
                            "INSERT INTO security_lifecycle_evidence "
                            "(evidence_id,case_id,run_id,automation_run_id,source_family,kind,"
                            "source_url,adapter,excerpt,content_sha256,source_document_sha256,"
                            "source_locator_json,evidence_dedupe_key,created_at) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                valid["evidence_id"],
                                "slc_case",
                                None,
                                valid["automation_run_id"],
                                valid["source_family"],
                                valid["kind"],
                                value,
                                valid["adapter"],
                                "Listing record",
                                _HEX_B,
                                valid["source_document_sha256"],
                                valid["source_locator_json"],
                                "dedupe:invalid-source-url",
                                _AT,
                            ),
                        )
                else:
                    with pytest.raises(sqlite3.IntegrityError):
                        _insert_evidence(conn, **{**valid, column: value})
            finally:
                conn.execute("ROLLBACK TO invalid_listing")
                conn.execute("RELEASE invalid_listing")
    finally:
        conn.close()


def test_evidence_requires_source_family_trusted_adapter_and_source_locator_coherence(
    tmp_path,
):
    from src.security_lifecycle_schema import create_profile_schema

    conn = sqlite3.connect(tmp_path / "profile.db")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        create_profile_schema(conn)
        assert _columns(conn, "security_lifecycle_evidence") == [
            "evidence_id",
            "case_id",
            "run_id",
            "automation_run_id",
            "source_family",
            "kind",
            "source_url",
            "title",
            "publisher",
            "domain",
            "source_published_at",
            "retrieved_at",
            "adapter",
            "excerpt",
            "content_sha256",
            "source_document_sha256",
            "source_locator_json",
            "evidence_dedupe_key",
            "mime_type",
            "document_status",
            "created_at",
        ]
        _insert_case(conn)
        _insert_automation_run(conn)
        _insert_evidence(
            conn,
            evidence_id="sle_sec",
            source_family="regulator",
            adapter="sec_edgar",
            kind="regulator_excerpt",
            automation_run_id="sla_run",
            source_document_sha256=_HEX_C,
            source_locator_json='{"accession":"0000000000-26-000001","section":"3.01"}',
        )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_evidence(
                conn,
                evidence_id="sle_wrong_family",
                source_family="publisher",
                adapter="sec_edgar",
                kind="regulator_excerpt",
                automation_run_id="sla_run",
                source_document_sha256=_HEX_C,
                source_locator_json="{}",
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_evidence(
                conn,
                evidence_id="sle_missing_locator",
                source_family="regulator",
                adapter="sec_edgar",
                kind="regulator_excerpt",
                automation_run_id="sla_run",
                source_document_sha256=_HEX_C,
                source_locator_json=None,
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_evidence(
                conn,
                evidence_id="sle_upper_hash",
                source_family="regulator",
                adapter="sec_edgar",
                kind="regulator_excerpt",
                automation_run_id="sla_run",
                source_document_sha256=_HEX_C.upper(),
                source_locator_json="{}",
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_evidence(
                conn,
                evidence_id="sle_retired_kind",
                source_family="general_web",
                adapter="hosted_search",
                kind="web_search_result",
                automation_run_id="sla_run",
                source_document_sha256=None,
                source_locator_json="{}",
            )
    finally:
        conn.close()


def test_automation_assessment_requires_honest_author_method_authority_and_provenance(
    tmp_path,
):
    from src.security_lifecycle_schema import create_profile_schema

    conn = sqlite3.connect(tmp_path / "profile.db")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        create_profile_schema(conn)
        _insert_case(conn)
        _insert_automation_run(conn)
        _insert_assessment(
            conn,
            assessment_id="sla_human_draft",
            revision=1,
            status="draft",
            author="human",
            acceptance_authority=None,
        )
        _insert_assessment(
            conn,
            assessment_id="sla_human",
            revision=2,
            status="accepted",
            author="human",
            acceptance_authority="human",
        )
        _insert_assessment(
            conn,
            assessment_id="sla_automation",
            revision=3,
            status="accepted",
            author="automation",
            acceptance_authority="automation_policy",
            automation_method="deterministic_rule",
            automation_run_id="sla_run",
            rule_id="identity-continuation",
            rule_version="1",
            decision_provenance_sha256=_HEX_C,
        )
        _insert_assessment(
            conn,
            assessment_id="sla_legacy",
            revision=4,
            status="accepted",
            author="legacy_review",
            acceptance_authority="legacy_migration",
        )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_assessment(
                conn,
                assessment_id="sla_missing_authority",
                revision=5,
                status="accepted",
                author="human",
                acceptance_authority=None,
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_assessment(
                conn,
                assessment_id="sla_false_human",
                revision=6,
                status="accepted",
                author="human",
                acceptance_authority="automation_policy",
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_assessment(
                conn,
                assessment_id="sla_missing_automation_provenance",
                revision=7,
                status="draft",
                author="automation",
                acceptance_authority=None,
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_assessment(
                conn,
                assessment_id="sla_model_autoaccepted",
                revision=8,
                status="accepted",
                author="automation",
                acceptance_authority="automation_policy",
                automation_method="model_assisted",
                automation_run_id="sla_run",
                rule_id="model-suggestion",
                rule_version="1",
                decision_provenance_sha256=_HEX_C,
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_assessment(
                conn,
                assessment_id="sla_legacy_claims_human",
                revision=9,
                status="accepted",
                author="legacy_review",
                acceptance_authority="human",
            )
    finally:
        conn.close()


def test_transition_authority_and_activity_schema_are_exact_and_closed(tmp_path):
    from src.security_lifecycle_schema import create_profile_schema
    import src.ticker_identity_schema as identity_schema

    assert getattr(identity_schema, "TRANSITION_APPROVAL_AUTHORITIES", None) == frozenset(
        {"attended_user", "automation_policy"}
    )
    conn = sqlite3.connect(tmp_path / "profile.db")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        create_profile_schema(conn)
        identity_schema.create_ticker_identity_schema(conn)
        assert _tables(conn, "ticker_identity_") == {
            "ticker_identity_transitions",
            "ticker_identity_transition_attempts",
            "ticker_identity_links",
            "ticker_identity_transition_activity",
        }
        assert _columns(conn, "ticker_identity_transitions")[-5:] == [
            "approval_authority",
            "automation_policy_version",
            "rule_id",
            "rule_version",
            "decision_provenance_sha256",
        ]
        assert _columns(conn, "ticker_identity_transition_activity") == [
            "activity_id",
            "transition_id",
            "activity_type",
            "source_ticker",
            "successor_ticker",
            "effective_date",
            "user_owned_changes_json",
            "provider_owned_retained_json",
            "state_sha256",
            "rule_id",
            "rule_version",
            "decision_provenance_sha256",
            "occurred_at",
            "acknowledged_at",
            "created_at",
        ]
        _insert_case(conn)
        _insert_assessment(
            conn,
            assessment_id="sla_human",
            revision=1,
            status="accepted",
            author="human",
            acceptance_authority="human",
        )
        _insert_transition(
            conn,
            transition_id="tit_attended",
            approval_authority="attended_user",
            automation_policy_version=None,
            rule_id=None,
            rule_version=None,
        )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_transition(
                conn,
                transition_id="tit_unproven_automation",
                approval_authority="automation_policy",
                automation_policy_version=None,
                rule_id=None,
                rule_version=None,
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_transition(
                conn,
                transition_id="tit_unknown_authority",
                approval_authority="scheduler",
                automation_policy_version=None,
                rule_id=None,
                rule_version=None,
            )
        conn.execute(
            "INSERT INTO ticker_identity_transition_activity "
            "(activity_id,transition_id,activity_type,source_ticker,successor_ticker,"
            "effective_date,user_owned_changes_json,provider_owned_retained_json,"
            "state_sha256,rule_id,rule_version,decision_provenance_sha256,"
            "occurred_at,acknowledged_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "tiact_1",
                "tit_attended",
                "applied",
                "OLD",
                "NEW",
                "2026-08-26",
                "[]",
                "[]",
                _HEX_A,
                None,
                None,
                _HEX_C,
                _AT,
                None,
                _AT,
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO ticker_identity_transition_activity "
                "(activity_id,transition_id,activity_type,source_ticker,"
                "effective_date,user_owned_changes_json,provider_owned_retained_json,"
                "state_sha256,decision_provenance_sha256,occurred_at,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "tiact_bad",
                    "tit_attended",
                    "dismissed",
                    "OLD",
                    "2026-08-26",
                    "[]",
                    "[]",
                    _HEX_A,
                    _HEX_C,
                    _AT,
                    _AT,
                ),
            )
    finally:
        conn.close()


def test_legacy_v1_schema_authorities_remain_exact_and_explicit(tmp_path):
    import src.security_lifecycle_schema as lifecycle
    import src.ticker_identity_schema as identity

    assert callable(getattr(lifecycle, "create_v1_profile_schema", None))
    assert callable(getattr(lifecycle, "verify_v1_profile_connection", None))
    assert callable(getattr(identity, "create_v1_ticker_identity_schema", None))
    assert callable(getattr(identity, "verify_v1_ticker_identity_connection", None))

    conn = sqlite3.connect(tmp_path / "legacy.db")
    try:
        lifecycle.create_v1_profile_schema(conn)
        identity.create_v1_ticker_identity_schema(conn)
        lifecycle.verify_v1_profile_connection(conn)
        identity.verify_v1_ticker_identity_connection(conn)
        assert _tables(conn, "security_lifecycle_") == {
            "security_lifecycle_cases",
            "security_lifecycle_investigation_runs",
            "security_lifecycle_evidence",
            "security_lifecycle_assessments",
            "security_lifecycle_assessment_outcomes",
            "security_lifecycle_assessment_evidence",
            "security_lifecycle_case_acknowledgements",
            "security_lifecycle_action_proposals",
            "security_lifecycle_migration_receipts",
        }
        assert _columns(conn, "security_lifecycle_evidence") == [
            "evidence_id",
            "case_id",
            "run_id",
            "kind",
            "source_url",
            "title",
            "publisher",
            "domain",
            "source_published_at",
            "retrieved_at",
            "adapter",
            "excerpt",
            "content_sha256",
            "mime_type",
            "document_status",
            "created_at",
        ]
        assert _tables(conn, "ticker_identity_") == {
            "ticker_identity_transitions",
            "ticker_identity_transition_attempts",
            "ticker_identity_links",
        }
        assert "approval_authority" not in _columns(
            conn, "ticker_identity_transitions"
        )
    finally:
        conn.close()


def test_current_and_legacy_verifiers_reject_each_others_schema(tmp_path):
    import src.security_lifecycle_schema as lifecycle
    import src.ticker_identity_schema as identity

    assert callable(getattr(lifecycle, "create_v1_profile_schema", None))
    assert callable(getattr(lifecycle, "verify_v1_profile_connection", None))
    assert callable(getattr(identity, "create_v1_ticker_identity_schema", None))
    assert callable(getattr(identity, "verify_v1_ticker_identity_connection", None))

    legacy = sqlite3.connect(tmp_path / "legacy.db")
    current = sqlite3.connect(tmp_path / "current.db")
    try:
        lifecycle.create_v1_profile_schema(legacy)
        identity.create_v1_ticker_identity_schema(legacy)
        with pytest.raises(lifecycle.LifecycleSchemaMismatch):
            lifecycle.verify_profile_connection(legacy)
        with pytest.raises(identity.TickerIdentitySchemaMismatch):
            identity.verify_ticker_identity_connection(legacy)

        lifecycle.create_profile_schema(current)
        identity.create_ticker_identity_schema(current)
        with pytest.raises(lifecycle.LifecycleSchemaMismatch):
            lifecycle.verify_v1_profile_connection(current)
        with pytest.raises(identity.TickerIdentitySchemaMismatch):
            identity.verify_v1_ticker_identity_connection(current)
    finally:
        legacy.close()
        current.close()
