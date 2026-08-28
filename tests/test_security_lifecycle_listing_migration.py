from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import threading

import pytest


_AT = "2026-08-28T00:00:00Z"
_HEX_A = "a" * 64
_HEX_B = "b" * 64
_HEX_C = "c" * 64
_HEX_D = "d" * 64


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seeded_v2_profile(tmp_path: Path, name: str = "profile.db") -> Path:
    from src.security_lifecycle_schema import create_v2_profile_schema
    from src.ticker_identity_schema import create_ticker_identity_schema

    path = tmp_path / name
    conn = sqlite3.connect(path)
    try:
        create_v2_profile_schema(conn)
        create_ticker_identity_schema(conn)
        conn.executescript(
            """
            CREATE TABLE job_runs (job_name TEXT PRIMARY KEY, tick INTEGER NOT NULL);
            CREATE INDEX idx_job_runs_tick ON job_runs(tick);
            CREATE VIEW job_run_projection AS SELECT job_name,tick FROM job_runs;
            CREATE TABLE job_audit (job_name TEXT NOT NULL, old_tick INTEGER NOT NULL);
            CREATE TRIGGER trg_job_runs_update AFTER UPDATE ON job_runs
            BEGIN
                INSERT INTO job_audit VALUES (OLD.job_name, OLD.tick);
            END;
            INSERT INTO job_runs VALUES ('scheduler', 1);
            """
        )
        conn.execute(
            "INSERT INTO security_lifecycle_cases VALUES (?,?,?,?,?,?)",
            ("slc_1", "sec_edgar", "filing-1", "OLD", _AT, _AT),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_investigation_runs "
            "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
            "result_count,fetch_count,usage_json,failure_code,started_at,finished_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slr_1",
                "slc_1",
                "attended_user",
                "manual",
                "succeeded",
                "[]",
                0,
                0,
                0,
                "{}",
                None,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_automation_runs "
            "(run_id,case_id,mode,observation_fingerprint_sha256,policy_version,"
            "run_key,status,decision_tier,action_readiness,query_context_json,"
            "diagnostics_json,retry_at,failure_code,started_at,finished_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slar_success",
                "slc_1",
                "historical",
                _HEX_A,
                "policy-v3",
                "run:success",
                "succeeded",
                "verified_automatic",
                "not_applicable",
                "{}",
                "{}",
                None,
                None,
                _AT,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_automation_runs "
            "(run_id,case_id,mode,observation_fingerprint_sha256,policy_version,"
            "run_key,status,decision_tier,action_readiness,query_context_json,"
            "diagnostics_json,retry_at,failure_code,started_at,finished_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slar_blocked",
                "slc_1",
                "live",
                _HEX_B,
                "policy-v3",
                "run:blocked",
                "blocked",
                None,
                None,
                "{}",
                "{}",
                _AT,
                None,
                _AT,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_automation_run_blockers VALUES (?,?,?,?,?)",
            ("slar_blocked", "sec_rate_limited", 1, "{}", _AT),
        )
        excerpt = "Publisher evidence retained verbatim."
        content_sha = _sha(excerpt)
        conn.execute(
            "INSERT INTO security_lifecycle_evidence "
            "(evidence_id,case_id,run_id,automation_run_id,source_family,kind,"
            "source_url,title,publisher,domain,source_published_at,retrieved_at,adapter,"
            "excerpt,content_sha256,source_document_sha256,source_locator_json,"
            "evidence_dedupe_key,mime_type,document_status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sle_publisher",
                "slc_1",
                None,
                "slar_success",
                "publisher",
                "publisher_excerpt",
                "https://example.com/article",
                "Legacy article",
                "Example",
                "example.com",
                "2026-08-27",
                _AT,
                "internal_news",
                excerpt,
                content_sha,
                None,
                None,
                "evidence:publisher",
                "text/plain",
                None,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_evidence_translations VALUES (?,?,?,?,?,?,?,?)",
            (
                "sle_publisher",
                content_sha,
                "zh-TW",
                "Translated publisher evidence.",
                "openai",
                "model-1",
                "harness-1",
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_automation_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slf_1",
                "slar_success",
                "slc_1",
                "sle_publisher",
                "source_ticker",
                '"OLD"',
                0,
                9,
                _HEX_C,
                "publisher-rule",
                "1",
                "fact:source-ticker",
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_assessments "
            "(assessment_id,case_id,revision,status,relevance,confidence,author,"
            "conclusion,impact_summary,counterparty_name,counterparty_ticker,"
            "counterparty_cik,successor_ticker,destination_venue,effective_date,"
            "consideration_currency,cash_per_security_decimal,exchange_ratio_decimal,"
            "observation_fingerprint_sha256,evidence_set_sha256,created_at,accepted_at,"
            "superseded_at,automation_method,acceptance_authority,automation_run_id,"
            "rule_id,rule_version,decision_provenance_sha256) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sla_1",
                "slc_1",
                1,
                "accepted",
                "direct_tracked_security",
                "high",
                "automation",
                "Legacy conclusion",
                "Legacy impact",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                _HEX_A,
                _HEX_D,
                _AT,
                _AT,
                None,
                "deterministic_rule",
                "automation_policy",
                "slar_success",
                "policy-rule",
                "3",
                _HEX_D,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_assessment_outcomes VALUES (?,?)",
            ("sla_1", "no_tracked_security_change"),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_assessment_evidence "
            "(id,assessment_id,reference_kind,evidence_id,cited_content_sha256) "
            "VALUES (?,?,?,?,?)",
            (17, "sla_1", "evidence", "sle_publisher", content_sha),
        )
        conn.execute(
            "UPDATE sqlite_sequence SET seq=41 "
            "WHERE name='security_lifecycle_assessment_evidence'"
        )
        conn.execute(
            "INSERT INTO security_lifecycle_case_acknowledgements VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "slk_1",
                "slc_1",
                "evidence_insufficient",
                "Legacy acknowledgement",
                "human",
                _HEX_A,
                _HEX_D,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_action_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slp_1",
                "slc_1",
                "sla_1",
                "notify",
                "proposed",
                "OLD",
                None,
                "[]",
                "Legacy proposal",
                None,
                _HEX_D,
                "proposal:1",
                _AT,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_migration_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-v1",
                _HEX_A,
                _HEX_B,
                "complete",
                1,
                1,
                1,
                1,
                _AT,
                _AT,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_transitions VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "tit_1",
                "slc_1",
                "sla_1",
                '["slp_1"]',
                "transition:1",
                "symbol_continuation",
                "approved",
                "OLD",
                "NEW",
                "2026-08-28",
                None,
                0,
                _HEX_A,
                _HEX_D,
                _HEX_C,
                '{"eligible":true}',
                None,
                None,
                _AT,
                _AT,
                None,
                None,
                None,
                "attended_user",
                None,
                None,
                None,
                _HEX_D,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_transition_attempts VALUES (?,?,?,?,?,?,?)",
            ("tia_1", "tit_1", "attended_user", "blocked", "[]", _HEX_C, _AT),
        )
        conn.execute(
            "INSERT INTO ticker_identity_links VALUES (?,?,?,?,?,?,?,?)",
            ("til_1", "tit_1", "OLD", "NEW", "symbol_continuation", "2026-08-28", _AT, None),
        )
        conn.execute(
            "INSERT INTO ticker_identity_transition_activity VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "tiact_1",
                "tit_1",
                "applied",
                "OLD",
                "NEW",
                "2026-08-28",
                "[]",
                "[]",
                _HEX_A,
                None,
                None,
                _HEX_D,
                _AT,
                None,
                _AT,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _rows(path: Path, tables: tuple[str, ...], *, include_rowid: bool) -> dict[str, tuple[tuple, ...]]:
    conn = sqlite3.connect(path)
    try:
        projection = "rowid,*" if include_rowid else "*"
        return {
            table: tuple(
                tuple(row)
                for row in conn.execute(
                    f'SELECT {projection} FROM "{table}" ORDER BY rowid'
                )
            )
            for table in tables
        }
    finally:
        conn.close()


def _lifecycle_tables() -> tuple[str, ...]:
    from src.security_lifecycle_schema import V2_PROFILE_TABLE_SQL

    return tuple(sorted(V2_PROFILE_TABLE_SQL))


def _identity_state(path: Path) -> tuple[tuple[tuple, ...], dict[str, tuple[tuple, ...]]]:
    from src.ticker_identity_schema import IDENTITY_TABLE_SQL

    conn = sqlite3.connect(path)
    try:
        schema = tuple(
            tuple(row)
            for row in conn.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master "
                "WHERE tbl_name LIKE 'ticker_identity_%' ORDER BY type,name"
            )
        )
    finally:
        conn.close()
    return schema, _rows(path, tuple(sorted(IDENTITY_TABLE_SQL)), include_rowid=True)


def _lifecycle_sequences(path: Path) -> tuple[tuple[str, int], ...]:
    conn = sqlite3.connect(path)
    try:
        names = _lifecycle_tables()
        placeholders = ",".join("?" for _ in names)
        return tuple(
            (str(row[0]), int(row[1]))
            for row in conn.execute(
                f"SELECT name,seq FROM sqlite_sequence WHERE name IN ({placeholders}) "
                "ORDER BY name",
                names,
            )
        )
    finally:
        conn.close()


def _unowned_state(path: Path) -> tuple[tuple[tuple, ...], dict[str, tuple[tuple, ...]]]:
    conn = sqlite3.connect(path)
    try:
        schema = tuple(
            tuple(row)
            for row in conn.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' "
                "AND name NOT LIKE 'security_lifecycle_%' "
                "AND name NOT LIKE 'idx_security_lifecycle_%' "
                "AND tbl_name NOT LIKE 'security_lifecycle_%' "
                "AND name NOT LIKE 'ticker_identity_%' "
                "AND name NOT LIKE 'idx_ticker_identity_%' "
                "AND tbl_name NOT LIKE 'ticker_identity_%' "
                "ORDER BY type,name"
            )
        )
    finally:
        conn.close()
    return schema, _rows(path, ("job_audit", "job_runs"), include_rowid=True)


def _count_listing_evidence(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_evidence "
                "WHERE source_family='listing_authority'"
            ).fetchone()[0]
        )
    finally:
        conn.close()


def test_v2_to_v3_preserves_every_existing_cell_and_adds_no_listing_rows(tmp_path):
    from src.security_lifecycle_listing_migration import (
        create_listing_authority_backup,
        migrate_listing_authority_schema,
        preflight_listing_authority_migration,
    )
    from src.security_lifecycle_schema import verify_profile_schema

    source = _seeded_v2_profile(tmp_path)
    lifecycle_tables = _lifecycle_tables()
    before_cells = _rows(source, lifecycle_tables, include_rowid=False)
    before_rowids = _rows(source, lifecycle_tables, include_rowid=True)
    before_sequences = _lifecycle_sequences(source)
    before_identity = _identity_state(source)
    before_unowned = _unowned_state(source)

    preflight = preflight_listing_authority_migration(source)
    assert preflight.schema_version == "v2"
    backup = create_listing_authority_backup(
        source,
        tmp_path / "backups" / "profile-v2.db",
        approval_sha256=preflight.approval_sha256,
    )
    result = migrate_listing_authority_schema(
        source,
        approval_sha256=preflight.approval_sha256,
        backup_sha256=backup.sha256,
    )

    assert result.changed is True
    assert result.source_schema_version == "v2"
    assert result.target_schema_version == "v3"
    assert _rows(source, lifecycle_tables, include_rowid=False) == before_cells
    assert _rows(source, lifecycle_tables, include_rowid=True) == before_rowids
    assert _lifecycle_sequences(source) == before_sequences
    assert _identity_state(source) == before_identity
    assert _unowned_state(source) == before_unowned
    assert _count_listing_evidence(source) == 0
    assert stat.S_IMODE(os.stat(backup.path.parent).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(backup.path).st_mode) == 0o600
    verify_profile_schema(source)


def test_preflight_is_read_only_and_exact_v3_migration_is_an_idempotent_noop(tmp_path):
    from src.security_lifecycle_listing_migration import (
        create_listing_authority_backup,
        migrate_listing_authority_schema,
        preflight_listing_authority_migration,
    )

    source = _seeded_v2_profile(tmp_path)
    before_bytes = source.read_bytes()
    first = preflight_listing_authority_migration(source)
    assert preflight_listing_authority_migration(source) == first
    assert source.read_bytes() == before_bytes
    backup = create_listing_authority_backup(
        source,
        tmp_path / "backups" / "profile-v2.db",
        approval_sha256=first.approval_sha256,
    )
    migrate_listing_authority_schema(
        source,
        approval_sha256=first.approval_sha256,
        backup_sha256=backup.sha256,
    )
    v3 = preflight_listing_authority_migration(source)
    migrated_bytes = source.read_bytes()
    result = migrate_listing_authority_schema(
        source,
        approval_sha256=v3.approval_sha256,
        backup_sha256=backup.sha256,
    )
    assert result.changed is False
    assert result.source_schema_version == "v3"
    assert result.target_schema_version == "v3"
    assert source.read_bytes() == migrated_bytes


def test_preflight_uses_one_read_snapshot_during_concurrent_writer_commit(
    tmp_path, monkeypatch
):
    import src.security_lifecycle_listing_migration as migration

    source = _seeded_v2_profile(tmp_path)
    with sqlite3.connect(source) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        conn.execute("PRAGMA wal_autocheckpoint=0")

    before = migration.preflight_listing_authority_migration(source)
    digest_started = threading.Event()
    writer_committed = threading.Event()
    writer_errors: list[BaseException] = []

    def writer() -> None:
        try:
            if not digest_started.wait(timeout=5):
                raise AssertionError("preflight did not reach table digests")
            with sqlite3.connect(source, timeout=5) as conn:
                conn.execute(
                    "UPDATE security_lifecycle_cases SET updated_at=? "
                    "WHERE case_id='slc_1'",
                    ("2026-08-28T00:01:00Z",),
                )
            writer_committed.set()
        except BaseException as exc:  # pragma: no cover - surfaced below
            writer_errors.append(exc)
            writer_committed.set()

    real_table_digests = migration._table_digests

    def pause_before_table_digests(conn, tables):
        digest_started.set()
        assert writer_committed.wait(timeout=5)
        return real_table_digests(conn, tables)

    monkeypatch.setattr(migration, "_table_digests", pause_before_table_digests)
    thread = threading.Thread(target=writer)
    thread.start()
    during = migration.preflight_listing_authority_migration(source)
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert writer_errors == []

    monkeypatch.setattr(migration, "_table_digests", real_table_digests)
    after = migration.preflight_listing_authority_migration(source)
    assert during == before
    assert after != before


def test_preflight_rolls_back_read_transaction_on_success_and_error(
    tmp_path, monkeypatch
):
    import src.security_lifecycle_listing_migration as migration

    source = _seeded_v2_profile(tmp_path)
    real_open = migration._open_read_only
    opened: list[TrackingConnection] = []

    class TrackingConnection:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection
            self.statements: list[str] = []
            self.rollback_calls = 0
            self.close_calls = 0

        @property
        def in_transaction(self) -> bool:
            return self.connection.in_transaction

        def execute(self, statement, parameters=()):
            self.statements.append(str(statement))
            return self.connection.execute(statement, parameters)

        def rollback(self) -> None:
            self.rollback_calls += 1
            self.connection.rollback()

        def close(self) -> None:
            self.close_calls += 1
            self.connection.close()

    def tracking_open(path: Path, *, restore: bool = False):
        tracked = TrackingConnection(real_open(path, restore=restore))
        opened.append(tracked)
        return tracked

    monkeypatch.setattr(migration, "_open_read_only", tracking_open)
    migration.preflight_listing_authority_migration(source)
    assert any(statement.strip().casefold() == "begin" for statement in opened[0].statements)
    assert opened[0].rollback_calls == 1
    assert opened[0].close_calls == 1

    def fail_inspection(conn) -> None:
        assert conn.in_transaction
        raise migration.ListingMigrationRejected("forced_inspection_failure")

    monkeypatch.setattr(migration, "_inspect_connection", fail_inspection)
    with pytest.raises(
        migration.ListingMigrationRejected, match="forced_inspection_failure"
    ):
        migration.preflight_listing_authority_migration(source)
    assert opened[1].rollback_calls == 1
    assert opened[1].close_calls == 1


def test_migration_rejects_stale_approval_and_wrong_backup_digest(tmp_path):
    from src.security_lifecycle_listing_migration import (
        ListingMigrationRejected,
        create_listing_authority_backup,
        migrate_listing_authority_schema,
        preflight_listing_authority_migration,
    )

    source = _seeded_v2_profile(tmp_path)
    approved = preflight_listing_authority_migration(source)
    backup = create_listing_authority_backup(
        source,
        tmp_path / "backups" / "profile-v2.db",
        approval_sha256=approved.approval_sha256,
    )
    with pytest.raises(ListingMigrationRejected, match="backup_digest_mismatch"):
        migrate_listing_authority_schema(
            source,
            approval_sha256=approved.approval_sha256,
            backup_sha256="0" * 64,
        )

    with sqlite3.connect(source) as conn:
        conn.execute(
            "UPDATE security_lifecycle_cases SET updated_at=? WHERE case_id='slc_1'",
            ("2026-08-28T00:01:00Z",),
        )
    with pytest.raises(ListingMigrationRejected, match="approval_digest_mismatch"):
        migrate_listing_authority_schema(
            source,
            approval_sha256=approved.approval_sha256,
            backup_sha256=backup.sha256,
        )


def test_preflight_rejects_foreign_key_failure_and_partial_or_mixed_authority(tmp_path):
    from src.security_lifecycle_listing_migration import (
        ListingMigrationRejected,
        preflight_listing_authority_migration,
    )
    from src.security_lifecycle_schema import (
        V2_PROFILE_TABLE_SQL,
        create_profile_schema,
    )
    from src.ticker_identity_schema import create_ticker_identity_schema

    broken_fk = _seeded_v2_profile(tmp_path, "broken-fk.db")
    with sqlite3.connect(broken_fk) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "UPDATE security_lifecycle_evidence SET case_id='missing' "
            "WHERE evidence_id='sle_publisher'"
        )
    with pytest.raises(ListingMigrationRejected, match="owned_schema_mismatch"):
        preflight_listing_authority_migration(broken_fk)

    partial = tmp_path / "partial.db"
    with sqlite3.connect(partial) as conn:
        conn.execute("CREATE TABLE security_lifecycle_cases (case_id TEXT PRIMARY KEY)")
    with pytest.raises(ListingMigrationRejected, match="owned_schema_mismatch"):
        preflight_listing_authority_migration(partial)

    mixed = tmp_path / "mixed.db"
    with sqlite3.connect(mixed) as conn:
        create_profile_schema(conn)
        create_ticker_identity_schema(conn)
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP TABLE security_lifecycle_evidence")
        conn.execute(V2_PROFILE_TABLE_SQL["security_lifecycle_evidence"])
    with pytest.raises(ListingMigrationRejected, match="owned_schema_mismatch"):
        preflight_listing_authority_migration(mixed)


def test_restore_rejects_digest_mismatch_and_installs_byte_identical_v2(tmp_path):
    from src.security_lifecycle_listing_migration import (
        ListingRestoreRejected,
        create_listing_authority_backup,
        preflight_listing_authority_migration,
        restore_listing_authority_backup,
    )
    from src.security_lifecycle_schema import verify_v2_profile_connection

    source = _seeded_v2_profile(tmp_path)
    approved = preflight_listing_authority_migration(source)
    backup = create_listing_authority_backup(
        source,
        tmp_path / "backups" / "profile-v2.db",
        approval_sha256=approved.approval_sha256,
    )
    rejected = tmp_path / "restore-digest-mismatch.db"
    with pytest.raises(ListingRestoreRejected, match="backup_digest_mismatch"):
        restore_listing_authority_backup(
            rejected,
            backup.path,
            backup_sha256="0" * 64,
        )
    assert not rejected.exists()

    restored = tmp_path / "restored.db"
    result = restore_listing_authority_backup(
        restored,
        backup.path,
        backup_sha256=backup.sha256,
    )
    assert result.schema_version == "v2"
    assert result.sha256 == backup.sha256
    assert restored.read_bytes() == backup.path.read_bytes()
    with sqlite3.connect(restored) as conn:
        verify_v2_profile_connection(conn)


def test_restore_refuses_existing_target_without_mutating_it(tmp_path):
    from src.security_lifecycle_listing_migration import (
        ListingRestoreRejected,
        create_listing_authority_backup,
        preflight_listing_authority_migration,
        restore_listing_authority_backup,
    )

    source = _seeded_v2_profile(tmp_path)
    approved = preflight_listing_authority_migration(source)
    backup = create_listing_authority_backup(
        source,
        tmp_path / "backups" / "profile-v2.db",
        approval_sha256=approved.approval_sha256,
    )
    target = tmp_path / "existing.db"
    target.write_bytes(b"do-not-touch")
    with pytest.raises(ListingRestoreRejected, match="target_must_be_absent"):
        restore_listing_authority_backup(
            target,
            backup.path,
            backup_sha256=backup.sha256,
        )
    assert target.read_bytes() == b"do-not-touch"
