from __future__ import annotations

import sqlite3

import pytest


MARKET_TABLES = {
    "security_lifecycle_observations",
    "security_lifecycle_observation_kinds",
}

PROFILE_TABLES = {
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


def _component_tables(conn):
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'security_lifecycle_%'"
        )
    }


def _columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_market_schema_matches_the_exact_observation_and_kind_contract(tmp_path):
    from src.security_lifecycle_schema import create_market_schema, verify_market_schema

    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    try:
        create_market_schema(conn)
        assert _component_tables(conn) == MARKET_TABLES
        assert _columns(conn, "security_lifecycle_observations") == [
            "id",
            "ticker",
            "cik",
            "issuer_name",
            "filing_date",
            "source",
            "source_ref",
            "filing_form",
            "filing_items_json",
            "evidence_url",
            "description",
            "first_observed_at",
            "last_observed_at",
        ]
        assert _columns(conn, "security_lifecycle_observation_kinds") == [
            "observation_id",
            "event_type",
            "effective_date",
        ]
        index_names = {
            row[1]
            for row in conn.execute(
                "SELECT type, name FROM sqlite_master WHERE type='index' "
                "AND sql IS NOT NULL"
            )
        }
        assert index_names == {
            "idx_security_lifecycle_ticker_date",
            "idx_security_lifecycle_source_identity",
        }
    finally:
        conn.close()
    verify_market_schema(path)


def test_profile_schema_matches_the_exact_case_evidence_and_proposal_contract(tmp_path):
    from src.security_lifecycle_schema import create_profile_schema, verify_profile_schema

    path = tmp_path / "profile_state.db"
    conn = sqlite3.connect(path)
    try:
        create_profile_schema(conn)
        assert _component_tables(conn) == PROFILE_TABLES
        assert _columns(conn, "security_lifecycle_cases") == [
            "case_id",
            "source",
            "source_ref",
            "ticker",
            "created_at",
            "updated_at",
        ]
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
        assert _columns(conn, "security_lifecycle_migration_receipts") == [
            "migration_key",
            "market_snapshot_sha256",
            "legacy_mapping_sha256",
            "phase",
            "expected_legacy_rows",
            "expected_observations",
            "expected_kinds",
            "expected_legacy_assessments",
            "started_at",
            "updated_at",
            "completed_at",
        ]
    finally:
        conn.close()
    verify_profile_schema(path)


def test_profile_foreign_keys_and_closed_vocabularies_reject_invalid_rows(tmp_path):
    from src.security_lifecycle_schema import create_profile_schema

    conn = sqlite3.connect(tmp_path / "profile_state.db")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        create_profile_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO security_lifecycle_investigation_runs "
                "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
                "fetch_count,usage_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "run_x",
                    "slc_missing",
                    "background",
                    "manual",
                    "queued",
                    "[]",
                    0,
                    0,
                    "{}",
                    "2026-08-20T00:00:00Z",
                ),
            )
        conn.execute(
            "INSERT INTO security_lifecycle_cases VALUES (?,?,?,?,?,?)",
            (
                "slc_case",
                "sec_edgar",
                "ref",
                "EA",
                "2026-08-20T00:00:00Z",
                "2026-08-20T00:00:00Z",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO security_lifecycle_investigation_runs "
                "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
                "result_count,fetch_count,usage_json,failure_code,finished_at,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "run_retired",
                    "slc_case",
                    "attended_user",
                    "tavily",
                    "failed",
                    "[]",
                    0,
                    None,
                    0,
                    "{}",
                    "adapter_unavailable",
                    "2026-08-20T00:00:00Z",
                    "2026-08-20T00:00:00Z",
                ),
            )
        conn.execute(
            "INSERT INTO security_lifecycle_investigation_runs "
            "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
            "result_count,fetch_count,usage_json,failure_code,finished_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "run_manual_failure",
                "slc_case",
                "attended_user",
                "manual",
                "failed",
                "[]",
                0,
                None,
                0,
                "{}",
                "adapter_unavailable",
                "2026-08-20T00:00:00Z",
                "2026-08-20T00:00:00Z",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO security_lifecycle_investigation_runs "
                "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
                "result_count,fetch_count,usage_json,failure_code,finished_at,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "run_unknown",
                    "slc_case",
                    "attended_user",
                    "manual",
                    "failed",
                    "[]",
                    0,
                    None,
                    0,
                    "{}",
                    "quotaish_unknown",
                    "2026-08-20T00:00:00Z",
                    "2026-08-20T00:00:00Z",
                ),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO security_lifecycle_case_acknowledgements "
                "(acknowledgement_id,case_id,reason,author,"
                "observation_fingerprint_sha256,evidence_set_sha256,acknowledged_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    "ack_x",
                    "slc_case",
                    "cleared",
                    "human",
                    "a" * 64,
                    "b" * 64,
                    "2026-08-20T00:00:00Z",
                ),
            )
    finally:
        conn.close()


def test_schema_verifier_rejects_partial_extra_or_drifted_artifacts(tmp_path):
    from src.security_lifecycle_schema import (
        LifecycleSchemaMismatch,
        create_market_schema,
        verify_market_schema,
    )

    partial = tmp_path / "partial.db"
    conn = sqlite3.connect(partial)
    conn.execute("CREATE TABLE security_lifecycle_observations (id INTEGER)")
    conn.commit()
    conn.close()
    with pytest.raises(LifecycleSchemaMismatch):
        verify_market_schema(partial)

    extra = tmp_path / "extra.db"
    conn = sqlite3.connect(extra)
    create_market_schema(conn)
    conn.execute("CREATE TABLE security_lifecycle_shadow (id INTEGER)")
    conn.commit()
    conn.close()
    with pytest.raises(LifecycleSchemaMismatch):
        verify_market_schema(extra)

    drifted = tmp_path / "drifted.db"
    conn = sqlite3.connect(drifted)
    create_market_schema(conn)
    conn.execute("DROP INDEX idx_security_lifecycle_ticker_date")
    conn.commit()
    conn.close()
    with pytest.raises(LifecycleSchemaMismatch):
        verify_market_schema(drifted)


def test_schema_verifiers_do_not_create_missing_databases(tmp_path):
    from src.security_lifecycle_schema import (
        LifecycleSchemaUnavailable,
        verify_market_schema,
        verify_profile_schema,
    )

    market = tmp_path / "missing" / "market_data.db"
    profile = tmp_path / "missing" / "profile_state.db"
    with pytest.raises(LifecycleSchemaUnavailable):
        verify_market_schema(market)
    with pytest.raises(LifecycleSchemaUnavailable):
        verify_profile_schema(profile)
    assert not market.exists()
    assert not profile.exists()
    assert not market.parent.exists()
