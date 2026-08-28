"""Explicit V1-to-V2 lifecycle automation profile migration."""

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
    V1_PROFILE_INDEX_SQL,
    V1_PROFILE_TABLE_SQL,
    V2_PROFILE_INDEX_SQL,
    V2_PROFILE_TABLE_SQL,
    verify_v1_profile_connection,
    verify_v2_profile_connection,
)
from src.ticker_identity_schema import (
    IDENTITY_INDEX_SQL,
    IDENTITY_TABLE_SQL,
    TickerIdentitySchemaMismatch,
    V1_IDENTITY_INDEX_SQL,
    V1_IDENTITY_TABLE_SQL,
    verify_ticker_identity_connection,
    verify_v1_ticker_identity_connection,
)


class AutomationMigrationRejected(RuntimeError):
    """The explicit profile database is not eligible for this migration."""


class AutomationRestoreRejected(RuntimeError):
    """A bound profile backup cannot be restored safely."""


@dataclass(frozen=True)
class AutomationMigrationPreflight:
    schema_version: str
    owned_schema_sha256: str
    owned_rows_sha256: str
    approval_sha256: str
    integrity: str
    foreign_key_violation_count: int
    owned_table_counts: tuple[tuple[str, int], ...]
    owned_table_row_sha256: tuple[tuple[str, str], ...]
    owned_schema_object_sha256: tuple[tuple[str, str], ...]
    tavily_run_count: int
    retired_web_evidence_count: int


@dataclass(frozen=True)
class AutomationMigrationResult:
    changed: bool
    source_schema_version: str
    target_schema_version: str
    preflight_approval_sha256: str
    postflight_approval_sha256: str
    mapped_table_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AutomationProfileBackup:
    path: Path
    sha256: str
    source_approval_sha256: str
    source_schema_version: str
    created_at: str


_V1_PROFILE_TABLES = frozenset(V1_PROFILE_TABLE_SQL)
_V1_IDENTITY_TABLES = frozenset(V1_IDENTITY_TABLE_SQL)
_V2_PROFILE_TABLES = frozenset(V2_PROFILE_TABLE_SQL)
_V2_IDENTITY_TABLES = frozenset(IDENTITY_TABLE_SQL)


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
    raise AutomationMigrationRejected("unsupported_sqlite_value")


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
    projection = ",".join(_quote_identifier(column) for column in columns)
    ordering = ",".join(
        f"{_quote_identifier(column)} COLLATE BINARY" for column in columns
    )
    try:
        rows = conn.execute(
            f"SELECT {projection} FROM {_quote_identifier(table)} "
            f"ORDER BY {ordering}"
        )
        for row in rows:
            digest.update(b"r")
            for value in row:
                encoded = _encode_cell(value)
                digest.update(str(len(encoded)).encode("ascii"))
                digest.update(b":")
                digest.update(encoded)
    except sqlite3.Error as exc:
        raise AutomationMigrationRejected(f"table_digest_failed:{table}") from exc
    return digest.hexdigest()


def _detect_schema_version(conn: sqlite3.Connection) -> str:
    try:
        verify_v2_profile_connection(conn)
        verify_ticker_identity_connection(conn)
        return "v2"
    except (LifecycleSchemaMismatch, TickerIdentitySchemaMismatch):
        pass
    try:
        verify_v1_profile_connection(conn)
        verify_v1_ticker_identity_connection(conn)
        return "v1"
    except (LifecycleSchemaMismatch, TickerIdentitySchemaMismatch) as exc:
        raise AutomationMigrationRejected("owned_schema_mismatch") from exc


def _authority_for(
    version: str,
) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    if version == "v1":
        tables = _V1_PROFILE_TABLES | _V1_IDENTITY_TABLES
        indexes = frozenset(V1_PROFILE_INDEX_SQL) | frozenset(V1_IDENTITY_INDEX_SQL)
    elif version == "v2":
        tables = _V2_PROFILE_TABLES | _V2_IDENTITY_TABLES
        indexes = frozenset(V2_PROFILE_INDEX_SQL) | frozenset(IDENTITY_INDEX_SQL)
    else:
        raise AutomationMigrationRejected("unknown_schema_version")
    return tables, indexes, tables | indexes


def _owned_schema_objects(
    conn: sqlite3.Connection,
    *,
    tables: frozenset[str],
    indexes: frozenset[str],
) -> tuple[tuple[str, str, str, str], ...]:
    names = tuple(sorted(tables | indexes))
    placeholders = ",".join("?" for _ in names)
    rows = conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        f"WHERE name IN ({placeholders}) ORDER BY type,name",
        names,
    ).fetchall()
    return tuple(
        (str(kind), str(name), str(table), str(sql or ""))
        for kind, name, table, sql in rows
    )


def _assert_no_unowned_dependents(
    conn: sqlite3.Connection,
    *,
    tables: frozenset[str],
    approved_indexes: frozenset[str],
) -> None:
    for kind, name, table_name, sql in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%'"
    ):
        object_name = str(name)
        table = str(table_name)
        if str(kind) == "index" and table in tables:
            if object_name not in approved_indexes:
                raise AutomationMigrationRejected(
                    f"unowned_owned_dependency:{object_name}"
                )
        elif str(kind) == "trigger" and table in tables:
            raise AutomationMigrationRejected(f"unowned_owned_dependency:{object_name}")
        elif str(kind) == "view":
            normalized = str(sql or "")
            if any(
                re.search(
                    rf"(?<![0-9A-Za-z_]){re.escape(owned)}(?![0-9A-Za-z_])",
                    normalized,
                    flags=re.IGNORECASE,
                )
                for owned in tables
            ):
                raise AutomationMigrationRejected(
                    f"unowned_owned_dependency:{object_name}"
                )


def _inspect_connection(conn: sqlite3.Connection) -> AutomationMigrationPreflight:
    version = _detect_schema_version(conn)
    tables, indexes, _objects = _authority_for(version)
    _assert_no_unowned_dependents(
        conn,
        tables=tables,
        approved_indexes=indexes,
    )
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.Error as exc:
        raise AutomationMigrationRejected("profile_integrity_unavailable") from exc
    if integrity != "ok":
        raise AutomationMigrationRejected("profile_integrity_failed")
    if foreign_key_violations:
        raise AutomationMigrationRejected("profile_foreign_key_failed")

    tavily_run_count = 0
    retired_web_evidence_count = 0
    if version == "v1":
        tavily_run_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_investigation_runs "
                "WHERE adapter='tavily'"
            ).fetchone()[0]
        )
        retired_web_evidence_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_evidence "
                "WHERE adapter='tavily' OR kind IN "
                "('web_search_result','web_page_excerpt')"
            ).fetchone()[0]
        )
        if tavily_run_count:
            raise AutomationMigrationRejected("stored_tavily_run")
        if retired_web_evidence_count:
            raise AutomationMigrationRejected("retired_web_evidence")

    table_counts = tuple(
        (
            table,
            int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
                ).fetchone()[0]
            ),
        )
        for table in sorted(tables)
    )
    table_digests = tuple(
        (table, _table_row_digest(conn, table)) for table in sorted(tables)
    )
    schema_objects = _owned_schema_objects(conn, tables=tables, indexes=indexes)
    schema_object_digests = tuple(
        (
            f"{kind}:{name}",
            _sha_bytes(_canonical_json([kind, name, table, sql])),
        )
        for kind, name, table, sql in schema_objects
    )
    schema_sha256 = _sha_bytes(_canonical_json(schema_objects))
    rows_sha256 = _sha_bytes(_canonical_json(table_digests))
    approval_payload = {
        "foreign_key_violation_count": len(foreign_key_violations),
        "integrity": integrity,
        "owned_rows_sha256": rows_sha256,
        "owned_schema_sha256": schema_sha256,
        "schema_version": version,
    }
    return AutomationMigrationPreflight(
        schema_version=version,
        owned_schema_sha256=schema_sha256,
        owned_rows_sha256=rows_sha256,
        approval_sha256=_sha_bytes(_canonical_json(approval_payload)),
        integrity=integrity,
        foreign_key_violation_count=len(foreign_key_violations),
        owned_table_counts=table_counts,
        owned_table_row_sha256=table_digests,
        owned_schema_object_sha256=schema_object_digests,
        tavily_run_count=tavily_run_count,
        retired_web_evidence_count=retired_web_evidence_count,
    )


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise AutomationMigrationRejected("profile_database_missing")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise AutomationMigrationRejected("profile_database_unavailable") from exc
    conn.row_factory = sqlite3.Row
    return conn


def _open_read_write_existing(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise AutomationMigrationRejected("profile_database_missing")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=rw", uri=True)
    except sqlite3.Error as exc:
        raise AutomationMigrationRejected("profile_database_unavailable") from exc
    conn.row_factory = sqlite3.Row
    return conn


def preflight_automation_migration(
    *, profile_path: str | Path
) -> AutomationMigrationPreflight:
    """Inspect one explicit profile database in a read transaction."""

    conn = _open_read_only(Path(profile_path))
    try:
        conn.execute("BEGIN")
        inspected = _inspect_connection(conn)
        conn.rollback()
        return inspected
    except sqlite3.Error as exc:
        conn.rollback()
        raise AutomationMigrationRejected("profile_preflight_failed") from exc
    finally:
        conn.close()


def _snapshot_rows(
    conn: sqlite3.Connection,
    tables: frozenset[str],
) -> dict[str, list[dict[str, object]]]:
    snapshots: dict[str, list[dict[str, object]]] = {}
    for table in sorted(tables):
        cursor = conn.execute(f"SELECT * FROM {_quote_identifier(table)}")
        names = [str(column[0]) for column in cursor.description or ()]
        snapshots[table] = [
            {name: row[index] for index, name in enumerate(names)} for row in cursor
        ]
    return snapshots


def _unowned_state(
    conn: sqlite3.Connection,
    owned_tables: frozenset[str],
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    tables = tuple(
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        if str(row[0]) not in owned_tables
    )
    row_digests = tuple((table, _table_row_digest(conn, table)) for table in tables)
    schema_digests: list[tuple[str, str]] = []
    for kind, name, table, sql in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
    ):
        if str(name) in owned_tables or str(table) in owned_tables:
            continue
        schema_digests.append(
            (
                f"{kind}:{name}",
                _sha_bytes(_canonical_json([kind, name, table, sql or ""])),
            )
        )
    return row_digests, tuple(schema_digests)


def _drop_v1_owned_tables(conn: sqlite3.Connection) -> None:
    order = (
        "ticker_identity_links",
        "ticker_identity_transition_attempts",
        "ticker_identity_transitions",
        "security_lifecycle_assessment_evidence",
        "security_lifecycle_assessment_outcomes",
        "security_lifecycle_action_proposals",
        "security_lifecycle_case_acknowledgements",
        "security_lifecycle_evidence",
        "security_lifecycle_assessments",
        "security_lifecycle_investigation_runs",
        "security_lifecycle_migration_receipts",
        "security_lifecycle_cases",
    )
    for table in order:
        conn.execute(f"DROP TABLE {_quote_identifier(table)}")


def _create_v2_owned_tables(conn: sqlite3.Connection) -> None:
    for statement in V2_PROFILE_TABLE_SQL.values():
        conn.execute(statement)
    for statement in V2_PROFILE_INDEX_SQL.values():
        conn.execute(statement)
    for statement in IDENTITY_TABLE_SQL.values():
        conn.execute(statement)
    for statement in IDENTITY_INDEX_SQL.values():
        conn.execute(statement)


def _insert_rows(
    conn: sqlite3.Connection,
    table: str,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        return
    columns = tuple(rows[0])
    projection = ",".join(_quote_identifier(column) for column in columns)
    placeholders = ",".join("?" for _ in columns)
    conn.executemany(
        f"INSERT INTO {_quote_identifier(table)} ({projection}) "
        f"VALUES ({placeholders})",
        [tuple(row[column] for column in columns) for row in rows],
    )


def _copy_profile_rows(
    conn: sqlite3.Connection,
    snapshots: dict[str, list[dict[str, object]]],
) -> None:
    _insert_rows(conn, "security_lifecycle_cases", snapshots["security_lifecycle_cases"])
    _insert_rows(
        conn,
        "security_lifecycle_investigation_runs",
        snapshots["security_lifecycle_investigation_runs"],
    )
    evidence_rows: list[dict[str, object]] = []
    for source in snapshots["security_lifecycle_evidence"]:
        row = dict(source)
        row.update(
            {
                "automation_run_id": None,
                "source_family": "manual",
                "source_document_sha256": None,
                "source_locator_json": None,
                "evidence_dedupe_key": f"legacy-evidence:{source['evidence_id']}",
            }
        )
        evidence_rows.append(row)
    _insert_rows(conn, "security_lifecycle_evidence", evidence_rows)

    assessment_rows: list[dict[str, object]] = []
    for source in snapshots["security_lifecycle_assessments"]:
        row = dict(source)
        if source["status"] == "draft":
            authority = None
        elif source["author"] == "legacy_review":
            authority = "legacy_migration"
        else:
            authority = "human"
        row.update(
            {
                "automation_method": None,
                "acceptance_authority": authority,
                "automation_run_id": None,
                "rule_id": None,
                "rule_version": None,
                "decision_provenance_sha256": None,
            }
        )
        assessment_rows.append(row)
    _insert_rows(conn, "security_lifecycle_assessments", assessment_rows)

    for table in (
        "security_lifecycle_assessment_outcomes",
        "security_lifecycle_assessment_evidence",
        "security_lifecycle_case_acknowledgements",
        "security_lifecycle_action_proposals",
        "security_lifecycle_migration_receipts",
    ):
        _insert_rows(conn, table, snapshots[table])


def _copy_identity_rows(
    conn: sqlite3.Connection,
    snapshots: dict[str, list[dict[str, object]]],
) -> None:
    transitions: list[dict[str, object]] = []
    for source in snapshots["ticker_identity_transitions"]:
        row = dict(source)
        row.update(
            {
                "approval_authority": "attended_user",
                "automation_policy_version": None,
                "rule_id": None,
                "rule_version": None,
                "decision_provenance_sha256": source[
                    "approved_assessment_fingerprint_sha256"
                ],
            }
        )
        transitions.append(row)
    _insert_rows(conn, "ticker_identity_transitions", transitions)
    _insert_rows(
        conn,
        "ticker_identity_transition_attempts",
        snapshots["ticker_identity_transition_attempts"],
    )
    _insert_rows(conn, "ticker_identity_links", snapshots["ticker_identity_links"])


def migrate_automation_profile_schema(
    *,
    profile_path: str | Path,
    approval_sha256: str,
    _step_hook: Callable[[str, sqlite3.Connection], None] | None = None,
) -> AutomationMigrationResult:
    """Rebuild the approved V1 owned component as exact V2 in one transaction."""

    path = Path(profile_path)
    candidate = preflight_automation_migration(profile_path=path)
    if candidate.schema_version == "v2":
        return AutomationMigrationResult(
            changed=False,
            source_schema_version="v2",
            target_schema_version="v2",
            preflight_approval_sha256=candidate.approval_sha256,
            postflight_approval_sha256=candidate.approval_sha256,
            mapped_table_counts=candidate.owned_table_counts,
        )
    if candidate.approval_sha256 != approval_sha256:
        raise AutomationMigrationRejected("approval_digest_mismatch")

    conn = _open_read_write_existing(path)
    hook = _step_hook or (lambda _phase, _conn: None)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")
        hook("after_begin", conn)
        locked = _inspect_connection(conn)
        if locked.schema_version != "v1":
            raise AutomationMigrationRejected("source_schema_changed_under_lock")
        if locked.approval_sha256 != approval_sha256:
            raise AutomationMigrationRejected("approval_digest_mismatch_under_lock")
        hook("after_locked_validation", conn)

        source_tables = _V1_PROFILE_TABLES | _V1_IDENTITY_TABLES
        snapshots = _snapshot_rows(conn, source_tables)
        unowned_before = _unowned_state(conn, source_tables)
        _drop_v1_owned_tables(conn)
        hook("after_drop", conn)
        _create_v2_owned_tables(conn)
        hook("after_create", conn)
        _copy_profile_rows(conn, snapshots)
        hook("after_profile_copy", conn)
        _copy_identity_rows(conn, snapshots)
        hook("after_identity_copy", conn)
        hook("before_verify", conn)

        verify_v2_profile_connection(conn)
        verify_ticker_identity_connection(conn)
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise AutomationMigrationRejected("postflight_foreign_key_failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise AutomationMigrationRejected("postflight_integrity_failed")
        unowned_after = _unowned_state(
            conn,
            _V2_PROFILE_TABLES | _V2_IDENTITY_TABLES,
        )
        if unowned_after != unowned_before:
            raise AutomationMigrationRejected("unowned_state_changed")
        postflight = _inspect_connection(conn)
        hook("before_commit", conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()

    return AutomationMigrationResult(
        changed=True,
        source_schema_version="v1",
        target_schema_version="v2",
        preflight_approval_sha256=approval_sha256,
        postflight_approval_sha256=postflight.approval_sha256,
        mapped_table_counts=postflight.owned_table_counts,
    )


def _clock_token(value: str) -> str:
    if not value or "\0" in value or len(value) > 100:
        raise AutomationMigrationRejected("backup_clock_invalid")
    token = re.sub(r"[^0-9A-Za-z]+", "", value)
    if not token:
        raise AutomationMigrationRejected("backup_clock_invalid")
    return token


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


def create_automation_profile_backup(
    *,
    profile_path: str | Path,
    backup_dir: str | Path,
    clock: Callable[[], str],
) -> AutomationProfileBackup:
    """Create, sync, and logically bind a backup of an explicit profile DB."""

    source_path = Path(profile_path)
    before = preflight_automation_migration(profile_path=source_path)
    created_at = clock()
    destination_dir = Path(backup_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_path = destination_dir / f"profile_state-{_clock_token(created_at)}.db"
    if backup_path.exists():
        raise AutomationMigrationRejected("backup_already_exists")
    if backup_path.resolve() == source_path.resolve():
        raise AutomationMigrationRejected("backup_matches_source")

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
        copied = preflight_automation_migration(profile_path=backup_path)
        if copied.approval_sha256 != before.approval_sha256:
            raise AutomationMigrationRejected("backup_logical_digest_mismatch")
        _fsync_file(backup_path)
        _fsync_directory(destination_dir)
        return AutomationProfileBackup(
            path=backup_path,
            sha256=_sha_file(backup_path),
            source_approval_sha256=before.approval_sha256,
            source_schema_version=before.schema_version,
            created_at=created_at,
        )
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise


def restore_automation_profile_backup(
    *,
    profile_path: str | Path,
    backup: AutomationProfileBackup,
) -> None:
    """Install a verified bound backup only at an explicitly absent path."""

    target = Path(profile_path)
    if target.resolve() == backup.path.resolve():
        raise AutomationRestoreRejected("backup_cannot_be_target")
    if target.exists():
        raise AutomationRestoreRejected("target_must_be_absent")
    if any(sidecar.exists() for sidecar in _sidecars(target)):
        raise AutomationRestoreRejected("target_not_quiesced")
    if not target.parent.is_dir():
        raise AutomationRestoreRejected("target_parent_missing")
    if not backup.path.is_file():
        raise AutomationRestoreRejected("backup_missing")
    if _sha_file(backup.path) != backup.sha256:
        raise AutomationRestoreRejected("backup_digest_mismatch")
    try:
        backup_state = preflight_automation_migration(profile_path=backup.path)
    except AutomationMigrationRejected as exc:
        raise AutomationRestoreRejected("backup_invalid") from exc
    if (
        backup_state.approval_sha256 != backup.source_approval_sha256
        or backup_state.schema_version != backup.source_schema_version
    ):
        raise AutomationRestoreRejected("backup_logical_digest_mismatch")

    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.restore-", dir=target.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    installed = False
    try:
        shutil.copy2(backup.path, temp_path)
        if _sha_file(temp_path) != backup.sha256:
            raise AutomationRestoreRejected("restore_copy_digest_mismatch")
        restored = preflight_automation_migration(profile_path=temp_path)
        if (
            restored.approval_sha256 != backup.source_approval_sha256
            or restored.schema_version != backup.source_schema_version
        ):
            raise AutomationRestoreRejected("restore_copy_logical_digest_mismatch")
        _fsync_file(temp_path)
        if target.exists():
            raise AutomationRestoreRejected("target_must_be_absent")
        if any(sidecar.exists() for sidecar in _sidecars(target)):
            raise AutomationRestoreRejected("target_not_quiesced")
        try:
            os.link(temp_path, target)
            installed = True
            _fsync_directory(target.parent)
        except FileExistsError as exc:
            raise AutomationRestoreRejected("target_must_be_absent") from exc
        except OSError as exc:
            raise AutomationRestoreRejected("restore_install_failed") from exc
        installed_state = preflight_automation_migration(profile_path=target)
        if (
            _sha_file(target) != backup.sha256
            or installed_state.approval_sha256 != backup.source_approval_sha256
            or installed_state.schema_version != backup.source_schema_version
        ):
            raise AutomationRestoreRejected("restore_postflight_mismatch")
    except Exception:
        if installed:
            target.unlink(missing_ok=True)
            _fsync_directory(target.parent)
        raise
    finally:
        temp_path.unlink(missing_ok=True)


__all__ = [
    "AutomationMigrationPreflight",
    "AutomationMigrationRejected",
    "AutomationMigrationResult",
    "AutomationProfileBackup",
    "AutomationRestoreRejected",
    "create_automation_profile_backup",
    "migrate_automation_profile_schema",
    "preflight_automation_migration",
    "restore_automation_profile_backup",
]
