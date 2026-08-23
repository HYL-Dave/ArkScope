from __future__ import annotations

import sqlite3

import pytest


IDENTITY_TABLES = {
    "ticker_identity_links",
    "ticker_identity_transition_attempts",
    "ticker_identity_transitions",
}

IDENTITY_INDEXES = {
    "idx_ticker_identity_attempts_transition",
    "idx_ticker_identity_links_source",
    "idx_ticker_identity_links_successor",
    "idx_ticker_identity_transitions_due",
}


def _component_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'ticker_identity_%'"
        )
    }


def _component_indexes(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_ticker_identity_%' AND sql IS NOT NULL"
        )
    }


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]


def _seed_case_and_assessment(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO security_lifecycle_cases "
        "(case_id,source,source_ref,ticker,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            "slc_case",
            "sec_edgar",
            "0000000000-26-000001",
            "OLD",
            "2026-08-23T00:00:00Z",
            "2026-08-23T00:00:00Z",
        ),
    )
    conn.execute(
        "INSERT INTO security_lifecycle_assessments "
        "(assessment_id,case_id,revision,status,relevance,confidence,author,"
        "conclusion,impact_summary,successor_ticker,effective_date,"
        "observation_fingerprint_sha256,evidence_set_sha256,created_at,accepted_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "sla_1",
            "slc_case",
            1,
            "accepted",
            "direct_tracked_security",
            "high",
            "human",
            "The tracked security continues under NEW.",
            "Tracking should continue under the successor ticker.",
            "NEW",
            "2026-08-24",
            "a" * 64,
            "b" * 64,
            "2026-08-23T00:00:00Z",
            "2026-08-23T00:00:00Z",
        ),
    )


def _insert_transition(
    conn: sqlite3.Connection,
    *,
    transition_id: str = "tit_1",
    kind: str = "symbol_continuation",
    status: str = "approved",
    successor_ticker: str | None = "NEW",
    before_snapshot_json: str | None = None,
    after_snapshot_sha256: str | None = None,
    applied_at: str | None = None,
    cancelled_at: str | None = None,
    reversed_at: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO ticker_identity_transitions "
        "(transition_id,case_id,assessment_id,proposal_ids_json,"
        "transition_dedupe_key,kind,status,source_ticker,successor_ticker,"
        "execute_on,priority_resolution,unhide_successor,"
        "approved_observation_fingerprint_sha256,"
        "approved_assessment_fingerprint_sha256,approved_preview_sha256,"
        "approved_preview_json,before_snapshot_json,after_snapshot_sha256,"
        "approved_at,updated_at,applied_at,cancelled_at,reversed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            transition_id,
            "slc_case",
            "sla_1",
            '["slp_1"]',
            f"dedupe:{transition_id}",
            kind,
            status,
            "OLD",
            successor_ticker,
            "2026-08-24",
            None,
            0,
            "a" * 64,
            "c" * 64,
            "d" * 64,
            '{"eligible":true}',
            before_snapshot_json,
            after_snapshot_sha256,
            "2026-08-23T00:00:00Z",
            "2026-08-23T00:00:00Z",
            applied_at,
            cancelled_at,
            reversed_at,
        ),
    )


def test_identity_schema_is_additive_exact_and_foreign_key_clean(tmp_path):
    from src.security_lifecycle_schema import create_profile_schema, verify_profile_connection
    from src.ticker_identity_schema import (
        create_ticker_identity_schema,
        verify_ticker_identity_connection,
    )

    conn = sqlite3.connect(tmp_path / "profile.db")
    try:
        create_profile_schema(conn)
        create_ticker_identity_schema(conn)

        verify_profile_connection(conn)
        verify_ticker_identity_connection(conn)
        assert _component_tables(conn) == IDENTITY_TABLES
        assert _component_indexes(conn) == IDENTITY_INDEXES
        assert _columns(conn, "ticker_identity_transitions") == [
            "transition_id",
            "case_id",
            "assessment_id",
            "proposal_ids_json",
            "transition_dedupe_key",
            "kind",
            "status",
            "source_ticker",
            "successor_ticker",
            "execute_on",
            "priority_resolution",
            "unhide_successor",
            "approved_observation_fingerprint_sha256",
            "approved_assessment_fingerprint_sha256",
            "approved_preview_sha256",
            "approved_preview_json",
            "before_snapshot_json",
            "after_snapshot_sha256",
            "approved_at",
            "updated_at",
            "applied_at",
            "cancelled_at",
            "reversed_at",
        ]
        assert _columns(conn, "ticker_identity_transition_attempts") == [
            "attempt_id",
            "transition_id",
            "trigger",
            "status",
            "block_reasons_json",
            "observed_preview_sha256",
            "attempted_at",
        ]
        assert _columns(conn, "ticker_identity_links") == [
            "link_id",
            "transition_id",
            "source_ticker",
            "successor_ticker",
            "relationship",
            "effective_date",
            "created_at",
            "reversed_at",
        ]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_identity_verifier_rejects_missing_extended_or_changed_schema(tmp_path):
    from src.security_lifecycle_schema import create_profile_schema
    from src.ticker_identity_schema import (
        TickerIdentitySchemaMismatch,
        create_ticker_identity_schema,
        identity_schema_present,
        verify_ticker_identity_connection,
    )

    missing = sqlite3.connect(tmp_path / "missing.db")
    try:
        create_profile_schema(missing)
        assert identity_schema_present(missing) is False
        with pytest.raises(TickerIdentitySchemaMismatch, match="table set"):
            verify_ticker_identity_connection(missing)
        assert identity_schema_present(missing) is False
    finally:
        missing.close()

    extended = sqlite3.connect(tmp_path / "extended.db")
    try:
        create_profile_schema(extended)
        create_ticker_identity_schema(extended)
        extended.execute("CREATE TABLE ticker_identity_shadow (id INTEGER)")
        with pytest.raises(TickerIdentitySchemaMismatch, match="table set"):
            verify_ticker_identity_connection(extended)
    finally:
        extended.close()

    changed = sqlite3.connect(tmp_path / "changed.db")
    try:
        create_profile_schema(changed)
        create_ticker_identity_schema(changed)
        changed.execute("DROP INDEX idx_ticker_identity_transitions_due")
        with pytest.raises(TickerIdentitySchemaMismatch, match="index set"):
            verify_ticker_identity_connection(changed)
    finally:
        changed.close()


def test_identity_schema_enforces_closed_shapes_and_coherent_terminal_states(tmp_path):
    from src.security_lifecycle_schema import create_profile_schema
    from src.ticker_identity_schema import create_ticker_identity_schema

    conn = sqlite3.connect(tmp_path / "profile.db")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        create_profile_schema(conn)
        create_ticker_identity_schema(conn)
        _seed_case_and_assessment(conn)

        _insert_transition(conn)
        _insert_transition(
            conn,
            transition_id="tit_terminal",
            kind="terminal_delisting",
            successor_ticker=None,
        )

        with pytest.raises(sqlite3.IntegrityError):
            _insert_transition(conn, transition_id="tit_unknown", status="queued")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_transition(
                conn,
                transition_id="tit_no_successor",
                kind="symbol_continuation",
                successor_ticker=None,
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_transition(
                conn,
                transition_id="tit_terminal_successor",
                kind="terminal_delisting",
                successor_ticker="NEW",
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_transition(
                conn,
                transition_id="tit_applied_without_snapshot",
                status="applied",
                applied_at="2026-08-24T00:00:00Z",
            )

        conn.execute(
            "INSERT INTO ticker_identity_transition_attempts "
            "(attempt_id,transition_id,trigger,status,block_reasons_json,"
            "observed_preview_sha256,attempted_at) VALUES (?,?,?,?,?,?,?)",
            (
                "tia_1",
                "tit_1",
                "scheduler",
                "blocked",
                '["preview_changed"]',
                "d" * 64,
                "2026-08-24T00:00:00Z",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO ticker_identity_transition_attempts "
                "(attempt_id,transition_id,trigger,status,block_reasons_json,attempted_at) "
                "VALUES (?,?,?,?,?,?)",
                ("tia_bad", "tit_1", "background", "blocked", "[]", "2026-08-24T00:00:00Z"),
            )

        conn.execute(
            "INSERT INTO ticker_identity_links "
            "(link_id,transition_id,source_ticker,successor_ticker,relationship,"
            "effective_date,created_at) VALUES (?,?,?,?,?,?,?)",
            (
                "til_1",
                "tit_1",
                "OLD",
                "NEW",
                "symbol_continuation",
                "2026-08-24",
                "2026-08-24T00:00:00Z",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO ticker_identity_links "
                "(link_id,transition_id,source_ticker,successor_ticker,relationship,"
                "effective_date,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    "til_bad",
                    "tit_terminal",
                    "OLD",
                    "OLD",
                    "renamed",
                    "2026-08-24",
                    "2026-08-24T00:00:00Z",
                ),
            )
    finally:
        conn.close()
