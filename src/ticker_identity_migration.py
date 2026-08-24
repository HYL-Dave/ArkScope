"""Explicit, approval-bound migration for ticker identity profile schema."""

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
from typing import Callable

from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    verify_v1_profile_connection as verify_profile_connection,
)
from src.ticker_identity_schema import (
    V1_IDENTITY_INDEX_SQL as IDENTITY_INDEX_SQL,
    V1_IDENTITY_TABLE_SQL as IDENTITY_TABLE_SQL,
    TickerIdentitySchemaMismatch,
    verify_v1_ticker_identity_connection as verify_ticker_identity_connection,
)


class TickerIdentityMigrationRejected(RuntimeError):
    """The profile database cannot receive the approved additive schema."""


class TickerIdentityRestoreRejected(RuntimeError):
    """A profile backup cannot be verified or safely restored."""


@dataclass(frozen=True)
class TickerIdentityMigrationPreflight:
    schema_sha256: str
    rows_sha256: str
    integrity: str
    foreign_key_violation_count: int
    identity_tables: tuple[str, ...]
    identity_indexes: tuple[str, ...]
    lifecycle_counts: tuple[tuple[str, int], ...]
    table_row_sha256: tuple[tuple[str, str], ...]
    schema_object_sha256: tuple[tuple[str, str], ...]
    approval_sha256: str


@dataclass(frozen=True)
class TickerIdentityMigrationResult:
    changed: bool
    created_tables: tuple[str, ...]
    created_indexes: tuple[str, ...]
    preflight_approval_sha256: str
    postflight_approval_sha256: str


@dataclass(frozen=True)
class ProfileBackup:
    path: Path
    sha256: str
    source_approval_sha256: str
    created_at: str


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
    raise TickerIdentityMigrationRejected("unsupported_sqlite_value")


def _user_tables(conn: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    )


def _table_row_digest(conn: sqlite3.Connection, table: str) -> str:
    columns = [
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table)})")
    ]
    digest = hashlib.sha256()
    digest.update(_encode_cell(table))
    for column in columns:
        digest.update(_encode_cell(column))
    if not columns:
        return digest.hexdigest()
    projected = ",".join(_quote_identifier(column) for column in columns)
    ordered = ",".join(
        f"{_quote_identifier(column)} COLLATE BINARY" for column in columns
    )
    try:
        rows = conn.execute(
            f"SELECT {projected} FROM {_quote_identifier(table)} ORDER BY {ordered}"
        )
        for row in rows:
            digest.update(b"r")
            for value in row:
                encoded = _encode_cell(value)
                digest.update(str(len(encoded)).encode("ascii"))
                digest.update(b":")
                digest.update(encoded)
    except sqlite3.Error as exc:
        raise TickerIdentityMigrationRejected(f"table_digest_failed:{table}") from exc
    return digest.hexdigest()


def _schema_objects(conn: sqlite3.Connection) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3] or ""),
        )
        for row in conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        )
    )


def _identity_objects(conn: sqlite3.Connection) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tables = tuple(
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'ticker_identity_%' ORDER BY name"
        )
    )
    indexes = tuple(
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_ticker_identity_%' ORDER BY name"
        )
    )
    return tables, indexes


def _inspect_connection(conn: sqlite3.Connection) -> TickerIdentityMigrationPreflight:
    try:
        verify_profile_connection(conn)
    except LifecycleSchemaMismatch as exc:
        raise TickerIdentityMigrationRejected("profile_schema_mismatch") from exc

    identity_tables, identity_indexes = _identity_objects(conn)
    if identity_tables or identity_indexes:
        try:
            verify_ticker_identity_connection(conn)
        except TickerIdentitySchemaMismatch as exc:
            raise TickerIdentityMigrationRejected("identity_schema_mismatch") from exc

    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.Error as exc:
        raise TickerIdentityMigrationRejected("profile_integrity_unavailable") from exc
    if integrity != "ok":
        raise TickerIdentityMigrationRejected("profile_integrity_failed")
    if foreign_key_violations:
        raise TickerIdentityMigrationRejected("profile_foreign_key_failed")

    tables = _user_tables(conn)
    table_digests = tuple((table, _table_row_digest(conn, table)) for table in tables)
    schema_objects = _schema_objects(conn)
    schema_object_digests = tuple(
        (f"{kind}:{name}", _sha_bytes(_canonical_json([kind, name, table, sql])))
        for kind, name, table, sql in schema_objects
    )
    lifecycle_counts = tuple(
        (table, int(conn.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}").fetchone()[0]))
        for table in tables
        if table.startswith("security_lifecycle_")
    )
    schema_sha256 = _sha_bytes(_canonical_json(schema_objects))
    rows_sha256 = _sha_bytes(_canonical_json(table_digests))
    approval_payload = {
        "foreign_key_violation_count": len(foreign_key_violations),
        "identity_indexes": identity_indexes,
        "identity_tables": identity_tables,
        "integrity": integrity,
        "lifecycle_counts": lifecycle_counts,
        "rows_sha256": rows_sha256,
        "schema_sha256": schema_sha256,
    }
    return TickerIdentityMigrationPreflight(
        schema_sha256=schema_sha256,
        rows_sha256=rows_sha256,
        integrity=integrity,
        foreign_key_violation_count=len(foreign_key_violations),
        identity_tables=identity_tables,
        identity_indexes=identity_indexes,
        lifecycle_counts=lifecycle_counts,
        table_row_sha256=table_digests,
        schema_object_sha256=schema_object_digests,
        approval_sha256=_sha_bytes(_canonical_json(approval_payload)),
    )


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise TickerIdentityMigrationRejected("profile_database_missing")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise TickerIdentityMigrationRejected("profile_database_unavailable") from exc
    return conn


def _open_read_write_existing(path: Path) -> sqlite3.Connection:
    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=rw", uri=True)
    except sqlite3.Error as exc:
        raise TickerIdentityMigrationRejected("profile_database_unavailable") from exc


def preflight_ticker_identity_migration(
    *, profile_path: str | Path
) -> TickerIdentityMigrationPreflight:
    """Inspect one explicit profile database without creating schema or files."""

    conn = _open_read_only(Path(profile_path))
    try:
        return _inspect_connection(conn)
    except sqlite3.Error as exc:
        raise TickerIdentityMigrationRejected("profile_preflight_failed") from exc
    finally:
        conn.close()


def _assert_preserved(
    before: TickerIdentityMigrationPreflight,
    after: TickerIdentityMigrationPreflight,
) -> None:
    after_rows = dict(after.table_row_sha256)
    for table, digest in before.table_row_sha256:
        if after_rows.get(table) != digest:
            raise TickerIdentityMigrationRejected(f"existing_table_changed:{table}")
    after_schema = dict(after.schema_object_sha256)
    for name, digest in before.schema_object_sha256:
        if after_schema.get(name) != digest:
            raise TickerIdentityMigrationRejected(f"existing_schema_changed:{name}")


def migrate_ticker_identity_schema(
    *, profile_path: str | Path, approval_sha256: str
) -> TickerIdentityMigrationResult:
    """Create only the approved identity component in one SQLite transaction."""

    path = Path(profile_path)
    candidate = preflight_ticker_identity_migration(profile_path=path)
    if candidate.identity_tables:
        return TickerIdentityMigrationResult(
            changed=False,
            created_tables=(),
            created_indexes=(),
            preflight_approval_sha256=candidate.approval_sha256,
            postflight_approval_sha256=candidate.approval_sha256,
        )
    if candidate.approval_sha256 != approval_sha256:
        raise TickerIdentityMigrationRejected("approval_digest_mismatch")

    conn = _open_read_write_existing(path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        locked = _inspect_connection(conn)
        if locked.identity_tables:
            conn.rollback()
            return TickerIdentityMigrationResult(
                changed=False,
                created_tables=(),
                created_indexes=(),
                preflight_approval_sha256=locked.approval_sha256,
                postflight_approval_sha256=locked.approval_sha256,
            )
        if locked.approval_sha256 != approval_sha256:
            raise TickerIdentityMigrationRejected("approval_digest_mismatch_under_lock")
        for statement in IDENTITY_TABLE_SQL.values():
            conn.execute(statement)
        for statement in IDENTITY_INDEX_SQL.values():
            conn.execute(statement)
        postflight = _inspect_connection(conn)
        _assert_preserved(locked, postflight)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return TickerIdentityMigrationResult(
        changed=True,
        created_tables=tuple(sorted(IDENTITY_TABLE_SQL)),
        created_indexes=tuple(sorted(IDENTITY_INDEX_SQL)),
        preflight_approval_sha256=approval_sha256,
        postflight_approval_sha256=postflight.approval_sha256,
    )


def _clock_token(value: str) -> str:
    if not value or "\0" in value or len(value) > 100:
        raise TickerIdentityMigrationRejected("backup_clock_invalid")
    token = re.sub(r"[^0-9A-Za-z]+", "", value)
    if not token:
        raise TickerIdentityMigrationRejected("backup_clock_invalid")
    return token


def create_profile_backup(
    *,
    profile_path: str | Path,
    backup_dir: str | Path,
    clock: Callable[[], str],
) -> ProfileBackup:
    """Create and verify a consistent SQLite backup of an explicit profile DB."""

    source_path = Path(profile_path)
    before = preflight_ticker_identity_migration(profile_path=source_path)
    created_at = clock()
    destination_dir = Path(backup_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_path = destination_dir / f"profile_state-{_clock_token(created_at)}.db"
    if backup_path.exists():
        raise TickerIdentityMigrationRejected("backup_already_exists")
    if backup_path.resolve() == source_path.resolve():
        raise TickerIdentityMigrationRejected("backup_matches_source")

    source = _open_read_only(source_path)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
    except Exception:
        destination.close()
        source.close()
        backup_path.unlink(missing_ok=True)
        raise
    else:
        destination.close()
        source.close()

    try:
        copied = preflight_ticker_identity_migration(profile_path=backup_path)
        if copied.approval_sha256 != before.approval_sha256:
            raise TickerIdentityMigrationRejected("backup_logical_digest_mismatch")
        return ProfileBackup(
            path=backup_path,
            sha256=_sha_file(backup_path),
            source_approval_sha256=before.approval_sha256,
            created_at=created_at,
        )
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise


def _sidecars(path: Path) -> tuple[Path, Path]:
    return Path(f"{path}-wal"), Path(f"{path}-shm")


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


def restore_profile_backup(*, profile_path: str | Path, backup: ProfileBackup) -> None:
    """Install a verified backup only at an explicitly absent target path."""

    target = Path(profile_path)
    if target.resolve() == backup.path.resolve():
        raise TickerIdentityRestoreRejected("backup_cannot_be_target")
    if not backup.path.is_file():
        raise TickerIdentityRestoreRejected("backup_missing")
    if _sha_file(backup.path) != backup.sha256:
        raise TickerIdentityRestoreRejected("backup_digest_mismatch")
    try:
        backup_state = preflight_ticker_identity_migration(profile_path=backup.path)
    except TickerIdentityMigrationRejected as exc:
        raise TickerIdentityRestoreRejected("backup_invalid") from exc
    if backup_state.approval_sha256 != backup.source_approval_sha256:
        raise TickerIdentityRestoreRejected("backup_logical_digest_mismatch")
    if target.exists():
        raise TickerIdentityRestoreRejected("target_must_be_absent")
    if any(path.exists() for path in _sidecars(target)):
        raise TickerIdentityRestoreRejected("target_not_quiesced")
    if not target.parent.is_dir():
        raise TickerIdentityRestoreRejected("target_parent_missing")

    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.restore-", dir=target.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(backup.path, temp_path)
        if _sha_file(temp_path) != backup.sha256:
            raise TickerIdentityRestoreRejected("restore_copy_digest_mismatch")
        restored = preflight_ticker_identity_migration(profile_path=temp_path)
        if restored.approval_sha256 != backup.source_approval_sha256:
            raise TickerIdentityRestoreRejected("restore_copy_logical_digest_mismatch")
        try:
            _fsync_file(temp_path)
        except OSError as exc:
            raise TickerIdentityRestoreRejected("restore_sync_failed") from exc
        if target.exists():
            raise TickerIdentityRestoreRejected("target_must_be_absent")
        if any(path.exists() for path in _sidecars(target)):
            raise TickerIdentityRestoreRejected("target_not_quiesced")
        try:
            os.link(temp_path, target)
            _fsync_directory(target.parent)
        except FileExistsError as exc:
            raise TickerIdentityRestoreRejected("target_must_be_absent") from exc
        except OSError as exc:
            raise TickerIdentityRestoreRejected("restore_install_failed") from exc
    finally:
        temp_path.unlink(missing_ok=True)


__all__ = [
    "ProfileBackup",
    "TickerIdentityMigrationPreflight",
    "TickerIdentityMigrationRejected",
    "TickerIdentityMigrationResult",
    "TickerIdentityRestoreRejected",
    "create_profile_backup",
    "migrate_ticker_identity_schema",
    "preflight_ticker_identity_migration",
    "restore_profile_backup",
]
