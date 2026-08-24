from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
from pathlib import Path
import sqlite3

import pytest


_AT = "2026-08-25T00:00:00Z"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed_v1(path: Path) -> None:
    from src.security_lifecycle_schema import create_v1_profile_schema
    from src.ticker_identity_schema import create_v1_ticker_identity_schema

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute(
            "CREATE TABLE job_runs (job_name TEXT PRIMARY KEY, tick INTEGER NOT NULL)"
        )
        conn.execute("INSERT INTO job_runs VALUES ('scheduler', 1)")
        conn.execute("CREATE INDEX idx_job_runs_tick ON job_runs(tick)")
        conn.execute(
            "CREATE VIEW job_run_projection AS SELECT job_name,tick FROM job_runs"
        )
        create_v1_profile_schema(conn)
        create_v1_ticker_identity_schema(conn)
        for ordinal in range(1, 5):
            case_id = f"slc_{ordinal}"
            assessment_id = f"sla_{ordinal}"
            conn.execute(
                "INSERT INTO security_lifecycle_cases "
                "(case_id,source,source_ref,ticker,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    case_id,
                    "sec_edgar",
                    f"0000000000-26-00000{ordinal}",
                    f"T{ordinal}",
                    _AT,
                    _AT,
                ),
            )
            conn.execute(
                "INSERT INTO security_lifecycle_assessments "
                "(assessment_id,case_id,revision,status,relevance,confidence,author,"
                "conclusion,impact_summary,successor_ticker,effective_date,"
                "observation_fingerprint_sha256,evidence_set_sha256,created_at,accepted_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    assessment_id,
                    case_id,
                    1,
                    "accepted",
                    "direct_tracked_security",
                    "unknown",
                    "legacy_review",
                    f"Legacy conclusion {ordinal}",
                    f"Legacy impact {ordinal}",
                    None,
                    None,
                    _sha(f"observation-{ordinal}"),
                    _sha(""),
                    _AT,
                    _AT,
                ),
            )
            conn.execute(
                "INSERT INTO security_lifecycle_assessment_outcomes "
                "(assessment_id,outcome) VALUES (?,?)",
                (assessment_id, "symbol_or_venue_changed"),
            )
            conn.execute(
                "INSERT INTO security_lifecycle_assessment_evidence "
                "(assessment_id,reference_kind,evidence_id,cited_content_sha256) "
                "VALUES (?,?,NULL,?)",
                (assessment_id, "observation", _sha(f"observation-{ordinal}")),
            )

        conn.execute(
            "INSERT INTO security_lifecycle_investigation_runs "
            "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
            "result_count,fetch_count,usage_json,started_at,finished_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slr_manual",
                "slc_1",
                "attended_user",
                "manual",
                "succeeded",
                "[]",
                0,
                0,
                0,
                "{}",
                _AT,
                _AT,
                _AT,
            ),
        )
        excerpt = "Manual evidence retained verbatim."
        conn.execute(
            "INSERT INTO security_lifecycle_evidence "
            "(evidence_id,case_id,run_id,kind,source_url,title,publisher,domain,"
            "source_published_at,retrieved_at,adapter,excerpt,content_sha256,"
            "mime_type,document_status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sle_manual",
                "slc_1",
                "slr_manual",
                "manual_text",
                None,
                None,
                None,
                None,
                None,
                None,
                "manual",
                excerpt,
                _sha(excerpt),
                "text/plain",
                None,
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_case_acknowledgements "
            "(acknowledgement_id,case_id,reason,note,author,"
            "observation_fingerprint_sha256,evidence_set_sha256,acknowledged_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                "slk_1",
                "slc_4",
                "evidence_insufficient",
                "Legacy acknowledgement",
                "human",
                _sha("observation-4"),
                _sha(""),
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_action_proposals "
            "(proposal_id,case_id,assessment_id,action_type,status,source_ticker,"
            "replacement_ticker,source_snapshot_json,reason,block_reason,"
            "assessment_fingerprint_sha256,proposal_dedupe_key,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "slp_1",
                "slc_1",
                "sla_1",
                "notify",
                "proposed",
                "T1",
                None,
                "[]",
                "Legacy proposal",
                None,
                _sha("assessment-1"),
                "proposal:1",
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_migration_receipts "
            "(migration_key,market_snapshot_sha256,legacy_mapping_sha256,phase,"
            "expected_legacy_rows,expected_observations,expected_kinds,"
            "expected_legacy_assessments,started_at,updated_at,completed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-v1",
                _sha("market"),
                _sha("mapping"),
                "complete",
                4,
                4,
                4,
                4,
                _AT,
                _AT,
                _AT,
            ),
        )
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
                "tit_1",
                "slc_1",
                "sla_1",
                '["slp_1"]',
                "transition:1",
                "symbol_continuation",
                "approved",
                "T1",
                "T1N",
                "2026-08-26",
                None,
                0,
                _sha("observation-1"),
                _sha("assessment-1"),
                _sha("preview-1"),
                '{"eligible":true}',
                None,
                None,
                _AT,
                _AT,
                None,
                None,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_transition_attempts "
            "(attempt_id,transition_id,trigger,status,block_reasons_json,"
            "observed_preview_sha256,attempted_at) VALUES (?,?,?,?,?,?,?)",
            (
                "tia_1",
                "tit_1",
                "attended_user",
                "blocked",
                '["preview_changed"]',
                _sha("preview-1"),
                _AT,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_links "
            "(link_id,transition_id,source_ticker,successor_ticker,relationship,"
            "effective_date,created_at) VALUES (?,?,?,?,?,?,?)",
            (
                "til_1",
                "tit_1",
                "T1",
                "T1N",
                "symbol_continuation",
                "2026-08-26",
                _AT,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _table_rows(path: Path, table: str) -> list[tuple]:
    conn = sqlite3.connect(path)
    try:
        columns = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
        order = ",".join(f'"{column}" COLLATE BINARY' for column in columns)
        return [tuple(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY {order}')]
    finally:
        conn.close()


def _migrate(path: Path):
    from src.security_lifecycle_automation_migration import (
        migrate_automation_profile_schema,
        preflight_automation_migration,
    )

    before = preflight_automation_migration(profile_path=path)
    result = migrate_automation_profile_schema(
        profile_path=path,
        approval_sha256=before.approval_sha256,
    )
    return before, result


def test_public_automation_migration_paths_are_keyword_only_and_have_no_defaults():
    import src.security_lifecycle_automation_migration as migration

    required = {
        migration.preflight_automation_migration: {"profile_path"},
        migration.create_automation_profile_backup: {
            "profile_path",
            "backup_dir",
            "clock",
        },
        migration.restore_automation_profile_backup: {"profile_path", "backup"},
        migration.migrate_automation_profile_schema: {
            "profile_path",
            "approval_sha256",
        },
    }
    for function, required_names in required.items():
        signature = inspect.signature(function)
        assert required_names <= set(signature.parameters)
        for name in required_names:
            parameter = signature.parameters[name]
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
            assert parameter.default is inspect.Parameter.empty


def test_preflight_is_read_only_deterministic_and_hashes_only_owned_components(
    tmp_path,
):
    from src.security_lifecycle_automation_migration import (
        preflight_automation_migration,
    )

    path = tmp_path / "profile.db"
    _seed_v1(path)
    before_bytes = hashlib.sha256(path.read_bytes()).hexdigest()
    before_stat = path.stat()
    first = preflight_automation_migration(profile_path=path)
    second = preflight_automation_migration(profile_path=path)
    assert first == second
    assert first.schema_version == "v1"
    assert first.integrity == "ok"
    assert first.foreign_key_violation_count == 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_bytes
    assert path.stat().st_size == before_stat.st_size

    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE job_runs SET tick=2 WHERE job_name='scheduler'")
    changed_unrelated = preflight_automation_migration(profile_path=path)
    assert changed_unrelated.approval_sha256 == first.approval_sha256
    assert changed_unrelated.owned_schema_sha256 == first.owned_schema_sha256
    assert changed_unrelated.owned_rows_sha256 == first.owned_rows_sha256


def test_preflight_rejects_stored_tavily_or_retired_web_evidence_before_writes(
    tmp_path,
):
    from src.security_lifecycle_automation_migration import (
        AutomationMigrationRejected,
        preflight_automation_migration,
    )

    tavily_run = tmp_path / "tavily-run.db"
    _seed_v1(tavily_run)
    with sqlite3.connect(tavily_run) as conn:
        conn.execute(
            "INSERT INTO security_lifecycle_investigation_runs "
            "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
            "fetch_count,usage_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "slr_tavily",
                "slc_2",
                "attended_user",
                "tavily",
                "queued",
                "[]",
                0,
                0,
                "{}",
                _AT,
            ),
        )
    with pytest.raises(AutomationMigrationRejected, match="stored_tavily_run"):
        preflight_automation_migration(profile_path=tavily_run)

    retired_evidence = tmp_path / "retired-evidence.db"
    _seed_v1(retired_evidence)
    excerpt = "Retired search result"
    with sqlite3.connect(retired_evidence) as conn:
        conn.execute(
            "INSERT INTO security_lifecycle_evidence "
            "(evidence_id,case_id,run_id,kind,source_url,title,publisher,domain,"
            "source_published_at,retrieved_at,adapter,excerpt,content_sha256,"
            "mime_type,document_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sle_tavily",
                "slc_2",
                None,
                "web_search_result",
                "https://example.com/result",
                "Result",
                "Example",
                "example.com",
                None,
                _AT,
                "tavily",
                excerpt,
                _sha(excerpt),
                "text/plain",
                None,
                _AT,
            ),
        )
    with pytest.raises(AutomationMigrationRejected, match="retired_web_evidence"):
        preflight_automation_migration(profile_path=retired_evidence)


def test_mapping_preserves_every_legacy_lifecycle_row_and_four_accepted_assessments(
    tmp_path,
):
    from src.security_lifecycle_schema import verify_profile_connection

    path = tmp_path / "profile.db"
    _seed_v1(path)
    preserved_tables = (
        "security_lifecycle_cases",
        "security_lifecycle_investigation_runs",
        "security_lifecycle_assessment_outcomes",
        "security_lifecycle_assessment_evidence",
        "security_lifecycle_case_acknowledgements",
        "security_lifecycle_action_proposals",
        "security_lifecycle_migration_receipts",
    )
    before_rows = {table: _table_rows(path, table) for table in preserved_tables}
    before, result = _migrate(path)
    assert before.schema_version == "v1"
    assert result.changed is True
    assert result.source_schema_version == "v1"
    assert result.target_schema_version == "v2"
    conn = sqlite3.connect(path)
    try:
        verify_profile_connection(conn)
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_assessments"
        ).fetchone()[0] == 4
    finally:
        conn.close()
    assert {table: _table_rows(path, table) for table in preserved_tables} == before_rows


def test_mapping_assigns_legacy_acceptance_without_inventing_automation_provenance(
    tmp_path,
):
    path = tmp_path / "profile.db"
    _seed_v1(path)
    _migrate(path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT author,status,acceptance_authority,automation_method,"
            "automation_run_id,rule_id,rule_version,decision_provenance_sha256 "
            "FROM security_lifecycle_assessments ORDER BY assessment_id"
        ).fetchall()
        assert rows == [
            ("legacy_review", "accepted", "legacy_migration", None, None, None, None, None),
            ("legacy_review", "accepted", "legacy_migration", None, None, None, None, None),
            ("legacy_review", "accepted", "legacy_migration", None, None, None, None, None),
            ("legacy_review", "accepted", "legacy_migration", None, None, None, None, None),
        ]
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_automation_runs"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_automation_facts"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_mapping_preserves_manual_evidence_and_attended_transition_authority(tmp_path):
    path = tmp_path / "profile.db"
    _seed_v1(path)
    before_excerpt = _table_rows(path, "security_lifecycle_evidence")[0][11:13]
    _migrate(path)
    conn = sqlite3.connect(path)
    try:
        evidence = conn.execute(
            "SELECT source_family,adapter,kind,excerpt,content_sha256,"
            "automation_run_id,source_document_sha256,source_locator_json "
            "FROM security_lifecycle_evidence WHERE evidence_id='sle_manual'"
        ).fetchone()
        assert evidence == (
            "manual",
            "manual",
            "manual_text",
            before_excerpt[0],
            before_excerpt[1],
            None,
            None,
            None,
        )
        transition = conn.execute(
            "SELECT approval_authority,automation_policy_version,rule_id,rule_version,"
            "decision_provenance_sha256,approved_assessment_fingerprint_sha256 "
            "FROM ticker_identity_transitions WHERE transition_id='tit_1'"
        ).fetchone()
        assert transition == (
            "attended_user",
            None,
            None,
            None,
            _sha("assessment-1"),
            _sha("assessment-1"),
        )
    finally:
        conn.close()


def test_migration_rebuilds_exact_owned_components_and_preserves_unrelated_rows(
    tmp_path,
):
    from src.security_lifecycle_schema import verify_profile_connection
    from src.ticker_identity_schema import verify_ticker_identity_connection

    path = tmp_path / "profile.db"
    _seed_v1(path)
    _, first = _migrate(path)
    assert first.changed is True
    conn = sqlite3.connect(path)
    try:
        verify_profile_connection(conn)
        verify_ticker_identity_connection(conn)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT * FROM job_runs").fetchall() == [("scheduler", 1)]
        assert conn.execute("SELECT * FROM job_run_projection").fetchall() == [
            ("scheduler", 1)
        ]
    finally:
        conn.close()
    from src.security_lifecycle_automation_migration import (
        migrate_automation_profile_schema,
    )

    second = migrate_automation_profile_schema(
        profile_path=path,
        approval_sha256=first.postflight_approval_sha256,
    )
    assert second.changed is False
    assert second.source_schema_version == "v2"


def test_migration_revalidates_owned_digest_under_begin_immediate(tmp_path):
    from src.security_lifecycle_automation_migration import (
        AutomationMigrationRejected,
        migrate_automation_profile_schema,
        preflight_automation_migration,
    )

    path = tmp_path / "profile.db"
    _seed_v1(path)
    approved = preflight_automation_migration(profile_path=path)

    def drift_after_begin(phase: str, conn: sqlite3.Connection) -> None:
        if phase == "after_begin":
            conn.execute(
                "UPDATE security_lifecycle_cases SET updated_at=? WHERE case_id='slc_1'",
                ("2026-08-25T00:01:00Z",),
            )

    with pytest.raises(
        AutomationMigrationRejected, match="approval_digest_mismatch_under_lock"
    ):
        migrate_automation_profile_schema(
            profile_path=path,
            approval_sha256=approved.approval_sha256,
            _step_hook=drift_after_begin,
        )
    assert preflight_automation_migration(profile_path=path) == approved


def test_fault_injection_rolls_back_every_ddl_and_row_change(tmp_path):
    from src.security_lifecycle_automation_migration import (
        migrate_automation_profile_schema,
        preflight_automation_migration,
    )
    from src.security_lifecycle_schema import verify_v1_profile_connection
    from src.ticker_identity_schema import verify_v1_ticker_identity_connection

    phases = (
        "after_locked_validation",
        "after_drop",
        "after_create",
        "after_profile_copy",
        "after_identity_copy",
        "before_verify",
        "before_commit",
    )
    for phase in phases:
        path = tmp_path / f"{phase}.db"
        _seed_v1(path)
        approved = preflight_automation_migration(profile_path=path)

        def fail_at(current: str, _conn: sqlite3.Connection, *, wanted=phase) -> None:
            if current == wanted:
                raise RuntimeError(f"fault:{wanted}")

        with pytest.raises(RuntimeError, match=f"fault:{phase}"):
            migrate_automation_profile_schema(
                profile_path=path,
                approval_sha256=approved.approval_sha256,
                _step_hook=fail_at,
            )
        assert preflight_automation_migration(profile_path=path) == approved
        conn = sqlite3.connect(path)
        try:
            verify_v1_profile_connection(conn)
            verify_v1_ticker_identity_connection(conn)
        finally:
            conn.close()


def test_backup_and_restore_are_bound_and_fail_before_target_mutation(
    tmp_path, monkeypatch
):
    import src.security_lifecycle_automation_migration as migration
    from src.security_lifecycle_schema import (
        LifecycleSchemaMismatch,
        verify_profile_connection,
        verify_v1_profile_connection,
    )
    from src.ticker_identity_schema import verify_v1_ticker_identity_connection

    source = tmp_path / "profile.db"
    _seed_v1(source)
    sync_calls: list[tuple[str, Path]] = []
    real_fsync_file = migration._fsync_file
    real_fsync_directory = migration._fsync_directory

    def record_file(path: Path) -> None:
        sync_calls.append(("file", path))
        real_fsync_file(path)

    def record_directory(path: Path) -> None:
        sync_calls.append(("directory", path))
        real_fsync_directory(path)

    monkeypatch.setattr(migration, "_fsync_file", record_file)
    monkeypatch.setattr(migration, "_fsync_directory", record_directory)
    backup = migration.create_automation_profile_backup(
        profile_path=source,
        backup_dir=tmp_path / "backups",
        clock=lambda: "2026-08-25T00:00:00Z",
    )
    assert backup.path.is_file()
    assert ("file", backup.path) in sync_calls
    assert ("directory", backup.path.parent) in sync_calls

    approved = migration.preflight_automation_migration(profile_path=source)
    migration.migrate_automation_profile_schema(
        profile_path=source,
        approval_sha256=approved.approval_sha256,
    )
    with sqlite3.connect(source) as conn:
        verify_profile_connection(conn)

    restored = tmp_path / "restored" / "profile.db"
    restored.parent.mkdir()
    migration.restore_automation_profile_backup(
        profile_path=restored,
        backup=backup,
    )
    with sqlite3.connect(restored) as conn:
        verify_v1_profile_connection(conn)
        verify_v1_ticker_identity_connection(conn)
        with pytest.raises(LifecycleSchemaMismatch):
            verify_profile_connection(conn)

    existing = tmp_path / "existing.db"
    existing.write_bytes(b"do-not-touch")
    with pytest.raises(migration.AutomationRestoreRejected, match="target_must_be_absent"):
        migration.restore_automation_profile_backup(
            profile_path=existing,
            backup=backup,
        )
    assert existing.read_bytes() == b"do-not-touch"

    tampered = replace(backup, path=tmp_path / "tampered.db")
    tampered.path.write_bytes(backup.path.read_bytes() + b"tamper")
    absent = tmp_path / "tampered-target.db"
    with pytest.raises(migration.AutomationRestoreRejected, match="backup_digest_mismatch"):
        migration.restore_automation_profile_backup(
            profile_path=absent,
            backup=tampered,
        )
    assert not absent.exists()
