from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
import socket
import sqlite3

import pytest


IDENTITY_TABLES = {
    "ticker_identity_links",
    "ticker_identity_transition_attempts",
    "ticker_identity_transitions",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile_database(tmp_path: Path) -> Path:
    from src.security_lifecycle_schema import create_profile_schema

    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "profile.db"
    conn = sqlite3.connect(path)
    try:
        create_profile_schema(conn)
        conn.execute(
            "CREATE TABLE unrelated_profile_state "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO unrelated_profile_state(key,value) VALUES (?,?)",
            ("fixture", "preserve-me"),
        )
        conn.execute(
            "INSERT INTO security_lifecycle_cases "
            "(case_id,source,source_ref,ticker,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                "slc_fixture",
                "sec_edgar",
                "0000000000-26-000001",
                "OLD",
                "2026-08-23T00:00:00Z",
                "2026-08-23T00:00:00Z",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _identity_tables(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'ticker_identity_%'"
            )
        }
    finally:
        conn.close()


def test_preflight_is_read_only_deterministic_and_reports_exact_profile_shape(tmp_path):
    from src.ticker_identity_migration import preflight_ticker_identity_migration

    profile_path = _profile_database(tmp_path)
    before_bytes = profile_path.read_bytes()
    before_stat = profile_path.stat()

    first = preflight_ticker_identity_migration(profile_path=profile_path)
    second = preflight_ticker_identity_migration(profile_path=profile_path)

    assert first == second
    assert first.approval_sha256 == second.approval_sha256
    assert len(first.approval_sha256) == 64
    assert len(first.schema_sha256) == 64
    assert len(first.rows_sha256) == 64
    assert first.integrity == "ok"
    assert first.foreign_key_violation_count == 0
    assert first.identity_tables == ()
    assert first.identity_indexes == ()
    assert dict(first.lifecycle_counts)["security_lifecycle_cases"] == 1
    assert dict(first.table_row_sha256)["unrelated_profile_state"]
    assert profile_path.read_bytes() == before_bytes
    assert profile_path.stat().st_size == before_stat.st_size
    assert _identity_tables(profile_path) == set()


def test_migration_is_additive_exact_and_idempotent(tmp_path):
    from src.ticker_identity_migration import (
        migrate_ticker_identity_schema,
        preflight_ticker_identity_migration,
    )
    from src.ticker_identity_schema import verify_ticker_identity_connection

    profile_path = _profile_database(tmp_path)
    before = preflight_ticker_identity_migration(profile_path=profile_path)
    before_rows = dict(before.table_row_sha256)
    before_schema = dict(before.schema_object_sha256)

    result = migrate_ticker_identity_schema(
        profile_path=profile_path,
        approval_sha256=before.approval_sha256,
    )

    assert result.changed is True
    assert set(result.created_tables) == IDENTITY_TABLES
    assert result.preflight_approval_sha256 == before.approval_sha256
    after = preflight_ticker_identity_migration(profile_path=profile_path)
    assert set(after.identity_tables) == IDENTITY_TABLES
    for table, digest in before_rows.items():
        assert dict(after.table_row_sha256)[table] == digest
    for name, digest in before_schema.items():
        assert dict(after.schema_object_sha256)[name] == digest

    conn = sqlite3.connect(profile_path)
    try:
        verify_ticker_identity_connection(conn)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()

    repeated = migrate_ticker_identity_schema(
        profile_path=profile_path,
        approval_sha256=before.approval_sha256,
    )
    assert repeated.changed is False
    assert repeated.created_tables == ()
    assert repeated.created_indexes == ()
    assert preflight_ticker_identity_migration(profile_path=profile_path) == after


def test_migration_rejects_stale_approval_before_any_schema_change(tmp_path):
    from src.ticker_identity_migration import (
        TickerIdentityMigrationRejected,
        migrate_ticker_identity_schema,
        preflight_ticker_identity_migration,
    )

    profile_path = _profile_database(tmp_path)
    approval = preflight_ticker_identity_migration(profile_path=profile_path)
    conn = sqlite3.connect(profile_path)
    try:
        conn.execute(
            "UPDATE unrelated_profile_state SET value='changed-after-approval' WHERE key='fixture'"
        )
        conn.commit()
    finally:
        conn.close()
    before_attempt = profile_path.read_bytes()

    with pytest.raises(TickerIdentityMigrationRejected, match="approval_digest_mismatch"):
        migrate_ticker_identity_schema(
            profile_path=profile_path,
            approval_sha256=approval.approval_sha256,
        )

    assert profile_path.read_bytes() == before_attempt
    assert _identity_tables(profile_path) == set()


def test_migration_does_not_recreate_profile_removed_after_preflight(
    tmp_path,
    monkeypatch,
):
    import src.ticker_identity_migration as migration

    profile_path = _profile_database(tmp_path)
    original_preflight = migration.preflight_ticker_identity_migration
    approval = original_preflight(profile_path=profile_path)

    def remove_after_preflight(*, profile_path):
        result = original_preflight(profile_path=profile_path)
        Path(profile_path).unlink()
        return result

    monkeypatch.setattr(
        migration,
        "preflight_ticker_identity_migration",
        remove_after_preflight,
    )

    with pytest.raises(
        migration.TickerIdentityMigrationRejected,
        match="profile_database_unavailable",
    ):
        migration.migrate_ticker_identity_schema(
            profile_path=profile_path,
            approval_sha256=approval.approval_sha256,
        )

    assert not profile_path.exists()


def test_interrupted_ddl_rolls_back_all_identity_tables(tmp_path, monkeypatch):
    import src.ticker_identity_migration as migration

    profile_path = _profile_database(tmp_path)
    approval = migration.preflight_ticker_identity_migration(profile_path=profile_path)
    malformed = dict(migration.IDENTITY_TABLE_SQL)
    second_name = tuple(malformed)[1]
    malformed[second_name] = "CREATE TABLE ticker_identity_broken ("
    monkeypatch.setattr(migration, "IDENTITY_TABLE_SQL", malformed)

    with pytest.raises(sqlite3.Error):
        migration.migrate_ticker_identity_schema(
            profile_path=profile_path,
            approval_sha256=approval.approval_sha256,
        )

    assert _identity_tables(profile_path) == set()
    conn = sqlite3.connect(profile_path)
    try:
        assert conn.execute(
            "SELECT value FROM unrelated_profile_state WHERE key='fixture'"
        ).fetchone()[0] == "preserve-me"
    finally:
        conn.close()


@pytest.mark.parametrize("shape", ["partial", "extended", "changed"])
def test_malformed_preexisting_identity_component_stops_fail_closed(tmp_path, shape):
    from src.ticker_identity_migration import (
        TickerIdentityMigrationRejected,
        migrate_ticker_identity_schema,
        preflight_ticker_identity_migration,
    )
    from src.ticker_identity_schema import create_ticker_identity_schema

    profile_path = _profile_database(tmp_path)
    conn = sqlite3.connect(profile_path)
    try:
        if shape == "partial":
            conn.execute("CREATE TABLE ticker_identity_transitions (id TEXT PRIMARY KEY)")
        else:
            create_ticker_identity_schema(conn)
            if shape == "extended":
                conn.execute("CREATE TABLE ticker_identity_shadow (id TEXT PRIMARY KEY)")
            else:
                conn.execute("DROP INDEX idx_ticker_identity_transitions_due")
        conn.commit()
    finally:
        conn.close()
    before = profile_path.read_bytes()

    with pytest.raises(TickerIdentityMigrationRejected, match="identity_schema_mismatch"):
        preflight_ticker_identity_migration(profile_path=profile_path)
    with pytest.raises(TickerIdentityMigrationRejected, match="identity_schema_mismatch"):
        migrate_ticker_identity_schema(
            profile_path=profile_path,
            approval_sha256="0" * 64,
        )
    assert profile_path.read_bytes() == before


def test_backup_is_logically_bound_and_restore_fails_before_target_mutation(tmp_path):
    from src.ticker_identity_migration import (
        TickerIdentityRestoreRejected,
        create_profile_backup,
        preflight_ticker_identity_migration,
        restore_profile_backup,
    )

    profile_path = _profile_database(tmp_path / "live")
    original_preflight = preflight_ticker_identity_migration(profile_path=profile_path)
    backup = create_profile_backup(
        profile_path=profile_path,
        backup_dir=tmp_path / "backups",
        clock=lambda: "2026-08-23T10:11:12Z",
    )
    assert backup.path.is_file()
    assert backup.sha256 == _sha(backup.path)
    assert backup.source_approval_sha256 == original_preflight.approval_sha256
    assert preflight_ticker_identity_migration(
        profile_path=backup.path
    ).approval_sha256 == original_preflight.approval_sha256

    profile_path.write_bytes(b"changed-profile")
    corrupted = type(backup)(
        path=backup.path,
        sha256="0" * 64,
        source_approval_sha256=backup.source_approval_sha256,
        created_at=backup.created_at,
    )
    with pytest.raises(TickerIdentityRestoreRejected, match="backup_digest_mismatch"):
        restore_profile_backup(profile_path=profile_path, backup=corrupted)
    assert profile_path.read_bytes() == b"changed-profile"

    with pytest.raises(TickerIdentityRestoreRejected, match="backup_cannot_be_target"):
        restore_profile_backup(profile_path=backup.path, backup=backup)
    assert backup.sha256 == _sha(backup.path)

    with pytest.raises(TickerIdentityRestoreRejected, match="target_must_be_absent"):
        restore_profile_backup(profile_path=profile_path, backup=backup)
    assert profile_path.read_bytes() == b"changed-profile"

    profile_path.unlink()
    restore_profile_backup(profile_path=profile_path, backup=backup)
    assert profile_path.read_bytes() == backup.path.read_bytes()
    assert preflight_ticker_identity_migration(
        profile_path=profile_path
    ).approval_sha256 == original_preflight.approval_sha256


def test_restore_refuses_an_existing_idle_database_without_sidecars(tmp_path):
    from src.ticker_identity_migration import (
        TickerIdentityRestoreRejected,
        create_profile_backup,
        restore_profile_backup,
    )

    profile_path = _profile_database(tmp_path / "live-idle")
    backup = create_profile_backup(
        profile_path=profile_path,
        backup_dir=tmp_path / "backups-idle",
        clock=lambda: "2026-08-23T10:11:12Z",
    )
    idle = sqlite3.connect(profile_path)
    try:
        assert not profile_path.with_name(f"{profile_path.name}-wal").exists()
        assert not profile_path.with_name(f"{profile_path.name}-shm").exists()
        with pytest.raises(
            TickerIdentityRestoreRejected,
            match="target_must_be_absent",
        ):
            restore_profile_backup(profile_path=profile_path, backup=backup)
        assert idle.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        idle.close()


def test_public_migration_paths_are_keyword_only_and_have_no_defaults():
    import src.ticker_identity_migration as migration

    expected = {
        migration.preflight_ticker_identity_migration: {"profile_path"},
        migration.create_profile_backup: {"profile_path", "backup_dir", "clock"},
        migration.migrate_ticker_identity_schema: {"profile_path", "approval_sha256"},
        migration.restore_profile_backup: {"profile_path", "backup"},
    }
    for function, names in expected.items():
        parameters = inspect.signature(function).parameters
        assert set(parameters) == names
        assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values())
        assert all(parameter.default is inspect.Parameter.empty for parameter in parameters.values())


def test_migration_is_profile_path_scoped_and_network_free(tmp_path, monkeypatch):
    from src.ticker_identity_migration import (
        migrate_ticker_identity_schema,
        preflight_ticker_identity_migration,
    )

    profile_path = _profile_database(tmp_path / "profile")
    market_path = tmp_path / "market_data.db"
    sa_path = tmp_path / "sa_capture.db"
    market_path.write_bytes(b"fixture market history and ticker aliases")
    sa_path.write_bytes(b"fixture seeking alpha provider state")
    untouched = {market_path: market_path.read_bytes(), sa_path: sa_path.read_bytes()}
    approval = preflight_ticker_identity_migration(profile_path=profile_path)

    def deny_socket(*_args, **_kwargs):
        raise AssertionError("network access is outside ticker migration")

    monkeypatch.setattr(socket, "socket", deny_socket)
    result = migrate_ticker_identity_schema(
        profile_path=profile_path,
        approval_sha256=approval.approval_sha256,
    )

    assert result.changed is True
    assert {path: path.read_bytes() for path in untouched} == untouched
