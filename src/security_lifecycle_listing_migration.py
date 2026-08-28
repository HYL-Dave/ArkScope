"""Explicit, reversible V2-to-V3 lifecycle listing-authority migration."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    PROFILE_INDEX_SQL,
    PROFILE_TABLE_SQL,
    V2_PROFILE_INDEX_SQL,
    V2_PROFILE_TABLE_SQL,
    verify_profile_connection,
    verify_v2_profile_connection,
)
from src.ticker_identity_schema import (
    IDENTITY_INDEX_SQL,
    IDENTITY_TABLE_SQL,
    TickerIdentitySchemaMismatch,
    verify_ticker_identity_connection,
)


class ListingMigrationRejected(RuntimeError):
    """The explicit profile database is not eligible for this migration."""


class ListingRestoreRejected(RuntimeError):
    """A listing-authority backup cannot be restored safely."""


@dataclass(frozen=True)
class ListingMigrationPreflight:
    schema_version: str
    owned_schema_sha256: str
    owned_rows_sha256: str
    approval_sha256: str
    integrity: str
    foreign_key_violation_count: int
    owned_table_counts: tuple[tuple[str, int], ...]
    owned_table_row_sha256: tuple[tuple[str, str], ...]
    owned_table_rowid_sha256: tuple[tuple[str, str], ...]
    owned_schema_object_sha256: tuple[tuple[str, str], ...]
    lifecycle_sequences: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ListingProfileBackup:
    path: Path
    sha256: str
    source_approval_sha256: str
    source_schema_version: str


@dataclass(frozen=True)
class ListingMigrationResult:
    changed: bool
    source_schema_version: str
    target_schema_version: str
    preflight_approval_sha256: str
    postflight_approval_sha256: str
    backup_sha256: str
    mapped_table_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ListingRestoreResult:
    path: Path
    sha256: str
    schema_version: str
    approval_sha256: str


@dataclass(frozen=True)
class _TableSnapshot:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]


_IDENTITY_TABLES = frozenset(IDENTITY_TABLE_SQL)
_IDENTITY_INDEXES = frozenset(IDENTITY_INDEX_SQL)
_V2_LIFECYCLE_TABLES = frozenset(V2_PROFILE_TABLE_SQL)
_V2_LIFECYCLE_INDEXES = frozenset(V2_PROFILE_INDEX_SQL)
_V3_LIFECYCLE_TABLES = frozenset(PROFILE_TABLE_SQL)
_V3_LIFECYCLE_INDEXES = frozenset(PROFILE_INDEX_SQL)

_DROP_ORDER = (
    "security_lifecycle_assessment_evidence",
    "security_lifecycle_evidence_translations",
    "security_lifecycle_automation_facts",
    "security_lifecycle_assessment_outcomes",
    "security_lifecycle_action_proposals",
    "security_lifecycle_case_acknowledgements",
    "security_lifecycle_automation_run_blockers",
    "security_lifecycle_assessments",
    "security_lifecycle_evidence",
    "security_lifecycle_migration_receipts",
    "security_lifecycle_investigation_runs",
    "security_lifecycle_automation_runs",
    "security_lifecycle_cases",
)

_INSERT_ORDER = tuple(reversed(_DROP_ORDER))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _encode_cell(value: object) -> bytes:
    if value is None:
        return b"n"
    if isinstance(value, bytes):
        return b"b" + str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, str):
        encoded = value.encode("utf-8", errors="surrogatepass")
        return b"s" + str(len(encoded)).encode("ascii") + b":" + encoded
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii") + b";"
    if isinstance(value, float):
        return b"f" + value.hex().encode("ascii") + b";"
    raise ListingMigrationRejected("unsupported_sqlite_value")


def _rows_digest(
    table: str,
    columns: tuple[str, ...],
    rows: tuple[tuple[object, ...], ...],
) -> str:
    digest = hashlib.sha256()
    digest.update(_encode_cell(table))
    for column in columns:
        digest.update(_encode_cell(column))
    for row in rows:
        digest.update(b"r")
        for value in row:
            encoded = _encode_cell(value)
            digest.update(str(len(encoded)).encode("ascii"))
            digest.update(b":")
            digest.update(encoded)
    return digest.hexdigest()


def _table_snapshot(conn: sqlite3.Connection, table: str) -> _TableSnapshot:
    columns = tuple(
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table)})")
    )
    projection = ",".join(_quote_identifier(column) for column in columns)
    try:
        rows = tuple(
            tuple(row)
            for row in conn.execute(
                f"SELECT rowid,{projection} FROM {_quote_identifier(table)} "
                "ORDER BY rowid"
            )
        )
    except sqlite3.Error as exc:
        raise ListingMigrationRejected(f"table_snapshot_failed:{table}") from exc
    return _TableSnapshot(columns=columns, rows=rows)


def _table_digests(
    conn: sqlite3.Connection,
    tables: frozenset[str],
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    cell_digests: list[tuple[str, str]] = []
    rowid_digests: list[tuple[str, str]] = []
    for table in sorted(tables):
        snapshot = _table_snapshot(conn, table)
        cell_rows = tuple(row[1:] for row in snapshot.rows)
        cell_digests.append(
            (table, _rows_digest(table, snapshot.columns, cell_rows))
        )
        rowid_digests.append(
            (
                table,
                _rows_digest(table, ("rowid", *snapshot.columns), snapshot.rows),
            )
        )
    return tuple(cell_digests), tuple(rowid_digests)


def _schema_objects(
    conn: sqlite3.Connection,
    *,
    tables: frozenset[str],
    indexes: frozenset[str],
) -> tuple[tuple[str, str, str, str], ...]:
    names = tuple(sorted(tables | indexes))
    table_names = tuple(sorted(tables))
    name_placeholders = ",".join("?" for _ in names)
    table_placeholders = ",".join("?" for _ in table_names)
    return tuple(
        (str(kind), str(name), str(table), str(sql or ""))
        for kind, name, table, sql in conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            f"WHERE name IN ({name_placeholders}) "
            f"OR tbl_name IN ({table_placeholders}) ORDER BY type,name",
            (*names, *table_names),
        )
    )


def _schema_digests(
    objects: tuple[tuple[str, str, str, str], ...],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            f"{kind}:{name}",
            _sha_bytes(_canonical_json([kind, name, table, sql])),
        )
        for kind, name, table, sql in objects
    )


def _lifecycle_sequences(
    conn: sqlite3.Connection, tables: frozenset[str]
) -> tuple[tuple[str, int], ...]:
    has_sequence = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
    ).fetchone()
    if has_sequence is None:
        return ()
    names = tuple(sorted(tables))
    placeholders = ",".join("?" for _ in names)
    return tuple(
        (str(name), int(sequence))
        for name, sequence in conn.execute(
            f"SELECT name,seq FROM sqlite_sequence WHERE name IN ({placeholders}) "
            "ORDER BY name",
            names,
        )
    )


def _detect_schema_version(conn: sqlite3.Connection) -> str:
    for version, verifier in (
        ("v3", verify_profile_connection),
        ("v2", verify_v2_profile_connection),
    ):
        try:
            verifier(conn)
            verify_ticker_identity_connection(conn)
            return version
        except (LifecycleSchemaMismatch, TickerIdentitySchemaMismatch):
            continue
    raise ListingMigrationRejected("owned_schema_mismatch")


def _authority_for(
    version: str,
) -> tuple[frozenset[str], frozenset[str]]:
    if version == "v2":
        return _V2_LIFECYCLE_TABLES, _V2_LIFECYCLE_INDEXES
    if version == "v3":
        return _V3_LIFECYCLE_TABLES, _V3_LIFECYCLE_INDEXES
    raise ListingMigrationRejected("unknown_schema_version")


def _assert_no_unowned_dependents(
    conn: sqlite3.Connection,
    *,
    lifecycle_tables: frozenset[str],
    lifecycle_indexes: frozenset[str],
) -> None:
    owned_names = lifecycle_tables | lifecycle_indexes | _IDENTITY_TABLES | _IDENTITY_INDEXES
    for kind, name, table_name, sql in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%'"
    ):
        object_name = str(name)
        if object_name in owned_names:
            continue
        if str(table_name) in lifecycle_tables:
            raise ListingMigrationRejected(f"unowned_owned_dependency:{object_name}")
        normalized_sql = str(sql or "").casefold()
        for table in lifecycle_tables:
            if re.search(rf"(?<![a-z0-9_]){re.escape(table.casefold())}(?![a-z0-9_])", normalized_sql):
                raise ListingMigrationRejected(
                    f"unowned_owned_dependency:{object_name}"
                )


def _inspect_connection(conn: sqlite3.Connection) -> ListingMigrationPreflight:
    version = _detect_schema_version(conn)
    lifecycle_tables, lifecycle_indexes = _authority_for(version)
    _assert_no_unowned_dependents(
        conn,
        lifecycle_tables=lifecycle_tables,
        lifecycle_indexes=lifecycle_indexes,
    )
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.Error as exc:
        raise ListingMigrationRejected("profile_integrity_unavailable") from exc
    if integrity != "ok":
        raise ListingMigrationRejected("profile_integrity_failed")
    if foreign_key_violations:
        raise ListingMigrationRejected("profile_foreign_key_failed")

    owned_tables = lifecycle_tables | _IDENTITY_TABLES
    owned_indexes = lifecycle_indexes | _IDENTITY_INDEXES
    cell_digests, rowid_digests = _table_digests(conn, owned_tables)
    schema_objects = _schema_objects(
        conn,
        tables=owned_tables,
        indexes=owned_indexes,
    )
    schema_object_digests = _schema_digests(schema_objects)
    table_counts = tuple(
        (
            table,
            int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
                ).fetchone()[0]
            ),
        )
        for table in sorted(owned_tables)
    )
    sequences = _lifecycle_sequences(conn, lifecycle_tables)
    schema_sha256 = _sha_bytes(_canonical_json(schema_objects))
    rows_sha256 = _sha_bytes(
        _canonical_json(
            {
                "cells": cell_digests,
                "rowids": rowid_digests,
                "sequences": sequences,
            }
        )
    )
    approval_payload = {
        "foreign_key_violation_count": len(foreign_key_violations),
        "integrity": integrity,
        "owned_rows_sha256": rows_sha256,
        "owned_schema_sha256": schema_sha256,
        "schema_version": version,
    }
    return ListingMigrationPreflight(
        schema_version=version,
        owned_schema_sha256=schema_sha256,
        owned_rows_sha256=rows_sha256,
        approval_sha256=_sha_bytes(_canonical_json(approval_payload)),
        integrity=integrity,
        foreign_key_violation_count=len(foreign_key_violations),
        owned_table_counts=table_counts,
        owned_table_row_sha256=cell_digests,
        owned_table_rowid_sha256=rowid_digests,
        owned_schema_object_sha256=schema_object_digests,
        lifecycle_sequences=sequences,
    )


def _open_read_only(path: Path, *, restore: bool = False) -> sqlite3.Connection:
    error = ListingRestoreRejected if restore else ListingMigrationRejected
    if not path.is_file():
        raise error("profile_database_missing")
    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise error("profile_database_unavailable") from exc


def _open_read_write_existing(path: Path) -> sqlite3.Connection:
    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=rw", uri=True)
    except sqlite3.Error as exc:
        raise ListingMigrationRejected("profile_database_unavailable") from exc


def preflight_listing_authority_migration(
    path: str | Path,
) -> ListingMigrationPreflight:
    """Inspect one explicit profile database without changing it."""

    conn = _open_read_only(Path(path))
    try:
        conn.execute("BEGIN")
        try:
            return _inspect_connection(conn)
        finally:
            conn.rollback()
    except sqlite3.Error as exc:
        raise ListingMigrationRejected("profile_preflight_failed") from exc
    finally:
        conn.close()


def _sqlite_backup(source_path: Path, destination: Path) -> None:
    source = _open_read_only(source_path)
    target: sqlite3.Connection | None = None
    try:
        old_umask = os.umask(0o177)
        try:
            target = sqlite3.connect(destination)
        finally:
            os.umask(old_umask)
        source.backup(target)
    finally:
        if target is not None:
            target.close()
        source.close()
    os.chmod(destination, 0o600)


def _expected_backup_sha256(source_path: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="arkscope-listing-backup-") as directory:
        scratch = Path(directory) / "profile.db"
        _sqlite_backup(source_path, scratch)
        return _sha_file(scratch)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_listing_authority_backup(
    path: str | Path,
    destination: str | Path,
    *,
    approval_sha256: str,
) -> ListingProfileBackup:
    """Create an owner-only, logically verified SQLite backup of exact V2."""

    source_path = Path(path)
    destination_path = Path(destination)
    before = preflight_listing_authority_migration(source_path)
    if before.schema_version != "v2":
        raise ListingMigrationRejected("backup_source_not_v2")
    if before.approval_sha256 != approval_sha256:
        raise ListingMigrationRejected("approval_digest_mismatch")
    if destination_path.resolve() == source_path.resolve():
        raise ListingMigrationRejected("backup_matches_source")
    if destination_path.exists():
        raise ListingMigrationRejected("backup_already_exists")

    destination_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if stat_mode(destination_path.parent) != 0o700:
        raise ListingMigrationRejected("backup_directory_permissions")
    try:
        _sqlite_backup(source_path, destination_path)
        copied = preflight_listing_authority_migration(destination_path)
        after = preflight_listing_authority_migration(source_path)
        if copied != before or after != before:
            raise ListingMigrationRejected("backup_logical_digest_mismatch")
        _fsync_file(destination_path)
        _fsync_directory(destination_path.parent)
        return ListingProfileBackup(
            path=destination_path,
            sha256=_sha_file(destination_path),
            source_approval_sha256=before.approval_sha256,
            source_schema_version=before.schema_version,
        )
    except Exception:
        destination_path.unlink(missing_ok=True)
        raise


def stat_mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777


def _snapshot_tables(
    conn: sqlite3.Connection, tables: frozenset[str]
) -> dict[str, _TableSnapshot]:
    return {table: _table_snapshot(conn, table) for table in sorted(tables)}


def _state_for_tables(
    conn: sqlite3.Connection,
    *,
    tables: frozenset[str],
    indexes: frozenset[str],
) -> tuple[
    tuple[tuple[str, str, str, str], ...],
    dict[str, _TableSnapshot],
]:
    return (
        _schema_objects(conn, tables=tables, indexes=indexes),
        _snapshot_tables(conn, tables),
    )


def _unowned_state(
    conn: sqlite3.Connection,
    *,
    lifecycle_tables: frozenset[str],
    lifecycle_indexes: frozenset[str],
) -> tuple[
    tuple[tuple[str, str, str, str], ...],
    dict[str, _TableSnapshot],
]:
    owned_tables = lifecycle_tables | _IDENTITY_TABLES
    owned_names = lifecycle_indexes | _IDENTITY_INDEXES
    objects: list[tuple[str, str, str, str]] = []
    tables: set[str] = set()
    for kind, name, table, sql in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
    ):
        if str(name) in owned_names or str(table) in owned_tables:
            continue
        objects.append((str(kind), str(name), str(table), str(sql or "")))
        if str(kind) == "table":
            tables.add(str(name))
    return tuple(objects), _snapshot_tables(conn, frozenset(tables))


def _insert_snapshot(
    conn: sqlite3.Connection, table: str, snapshot: _TableSnapshot
) -> None:
    if not snapshot.rows:
        return
    columns = ("rowid", *snapshot.columns)
    projection = ",".join(_quote_identifier(column) for column in columns)
    placeholders = ",".join("?" for _ in columns)
    conn.executemany(
        f"INSERT INTO {_quote_identifier(table)} ({projection}) "
        f"VALUES ({placeholders})",
        snapshot.rows,
    )


def _restore_sequences(
    conn: sqlite3.Connection,
    tables: frozenset[str],
    sequences: tuple[tuple[str, int], ...],
) -> None:
    names = tuple(sorted(tables))
    placeholders = ",".join("?" for _ in names)
    conn.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", names
    )
    conn.executemany("INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", sequences)


def migrate_listing_authority_schema(
    path: str | Path,
    *,
    approval_sha256: str,
    backup_sha256: str,
) -> ListingMigrationResult:
    """Rebuild exact V2 lifecycle tables as exact V3 in one transaction."""

    source_path = Path(path)
    candidate = preflight_listing_authority_migration(source_path)
    if candidate.schema_version == "v3":
        return ListingMigrationResult(
            changed=False,
            source_schema_version="v3",
            target_schema_version="v3",
            preflight_approval_sha256=candidate.approval_sha256,
            postflight_approval_sha256=candidate.approval_sha256,
            backup_sha256=backup_sha256,
            mapped_table_counts=candidate.owned_table_counts,
        )
    if candidate.approval_sha256 != approval_sha256:
        raise ListingMigrationRejected("approval_digest_mismatch")
    if _expected_backup_sha256(source_path) != backup_sha256:
        raise ListingMigrationRejected("backup_digest_mismatch")

    conn = _open_read_write_existing(source_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        locked = _inspect_connection(conn)
        if locked.schema_version != "v2":
            raise ListingMigrationRejected("source_schema_changed_under_lock")
        if locked.approval_sha256 != approval_sha256:
            raise ListingMigrationRejected("approval_digest_mismatch_under_lock")

        snapshots = _snapshot_tables(conn, _V2_LIFECYCLE_TABLES)
        sequences = _lifecycle_sequences(conn, _V2_LIFECYCLE_TABLES)
        identity_before = _state_for_tables(
            conn,
            tables=_IDENTITY_TABLES,
            indexes=_IDENTITY_INDEXES,
        )
        unowned_before = _unowned_state(
            conn,
            lifecycle_tables=_V2_LIFECYCLE_TABLES,
            lifecycle_indexes=_V2_LIFECYCLE_INDEXES,
        )

        for table in _DROP_ORDER:
            conn.execute(f"DROP TABLE {_quote_identifier(table)}")
        for statement in PROFILE_TABLE_SQL.values():
            conn.execute(statement)
        for statement in PROFILE_INDEX_SQL.values():
            conn.execute(statement)
        for table in _INSERT_ORDER:
            _insert_snapshot(conn, table, snapshots[table])
        _restore_sequences(conn, _V3_LIFECYCLE_TABLES, sequences)

        verify_profile_connection(conn)
        verify_ticker_identity_connection(conn)
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ListingMigrationRejected("postflight_foreign_key_failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise ListingMigrationRejected("postflight_integrity_failed")
        if _snapshot_tables(conn, _V3_LIFECYCLE_TABLES) != snapshots:
            raise ListingMigrationRejected("lifecycle_rows_changed")
        if _lifecycle_sequences(conn, _V3_LIFECYCLE_TABLES) != sequences:
            raise ListingMigrationRejected("lifecycle_sequences_changed")
        identity_after = _state_for_tables(
            conn,
            tables=_IDENTITY_TABLES,
            indexes=_IDENTITY_INDEXES,
        )
        if identity_after != identity_before:
            raise ListingMigrationRejected("ticker_identity_changed")
        unowned_after = _unowned_state(
            conn,
            lifecycle_tables=_V3_LIFECYCLE_TABLES,
            lifecycle_indexes=_V3_LIFECYCLE_INDEXES,
        )
        if unowned_after != unowned_before:
            raise ListingMigrationRejected("unowned_state_changed")
        postflight = _inspect_connection(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return ListingMigrationResult(
        changed=True,
        source_schema_version="v2",
        target_schema_version="v3",
        preflight_approval_sha256=approval_sha256,
        postflight_approval_sha256=postflight.approval_sha256,
        backup_sha256=backup_sha256,
        mapped_table_counts=postflight.owned_table_counts,
    )


def _sidecars(path: Path) -> tuple[Path, Path]:
    return Path(f"{path}-wal"), Path(f"{path}-shm")


def restore_listing_authority_backup(
    path: str | Path,
    backup: str | Path,
    *,
    backup_sha256: str,
) -> ListingRestoreResult:
    """Install one verified exact-V2 backup at an explicitly absent path."""

    target = Path(path)
    backup_path = Path(backup)
    if target.resolve() == backup_path.resolve():
        raise ListingRestoreRejected("backup_cannot_be_target")
    if not backup_path.is_file():
        raise ListingRestoreRejected("backup_missing")
    if _sha_file(backup_path) != backup_sha256:
        raise ListingRestoreRejected("backup_digest_mismatch")
    try:
        backup_state = preflight_listing_authority_migration(backup_path)
    except ListingMigrationRejected as exc:
        raise ListingRestoreRejected("backup_invalid") from exc
    if backup_state.schema_version != "v2":
        raise ListingRestoreRejected("backup_not_v2")
    if target.exists():
        raise ListingRestoreRejected("target_must_be_absent")
    if any(sidecar.exists() for sidecar in _sidecars(target)):
        raise ListingRestoreRejected("target_not_quiesced")
    if not target.parent.is_dir():
        raise ListingRestoreRejected("target_parent_missing")

    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.restore-", dir=target.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(backup_path, temp_path)
        os.chmod(temp_path, 0o600)
        if _sha_file(temp_path) != backup_sha256:
            raise ListingRestoreRejected("restore_copy_digest_mismatch")
        try:
            restored = preflight_listing_authority_migration(temp_path)
        except ListingMigrationRejected as exc:
            raise ListingRestoreRejected("restore_copy_invalid") from exc
        if restored != backup_state:
            raise ListingRestoreRejected("restore_copy_logical_digest_mismatch")
        _fsync_file(temp_path)
        try:
            os.link(temp_path, target)
            _fsync_directory(target.parent)
        except FileExistsError as exc:
            raise ListingRestoreRejected("target_must_be_absent") from exc
        except OSError as exc:
            raise ListingRestoreRejected("restore_install_failed") from exc
        installed = preflight_listing_authority_migration(target)
        if installed != backup_state or _sha_file(target) != backup_sha256:
            target.unlink(missing_ok=True)
            raise ListingRestoreRejected("restore_postflight_mismatch")
    finally:
        temp_path.unlink(missing_ok=True)

    return ListingRestoreResult(
        path=target,
        sha256=backup_sha256,
        schema_version=installed.schema_version,
        approval_sha256=installed.approval_sha256,
    )


__all__ = [
    "ListingMigrationPreflight",
    "ListingMigrationRejected",
    "ListingMigrationResult",
    "ListingProfileBackup",
    "ListingRestoreRejected",
    "ListingRestoreResult",
    "create_listing_authority_backup",
    "migrate_listing_authority_schema",
    "preflight_listing_authority_migration",
    "restore_listing_authority_backup",
]
