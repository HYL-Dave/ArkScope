"""Explicit schema-v2 lifecycle for the Investor Profile calibration journal."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CALIBRATION_SCHEMA_VERSION = 2

_MARKER_TABLE = "investor_profile_calibration_schema"
_SESSIONS_TABLE = "investor_profile_calibration_sessions"
_MESSAGES_TABLE = "investor_profile_calibration_messages"
_TURNS_TABLE = "investor_profile_calibration_turns"
_PROPOSALS_TABLE = "investor_profile_calibration_proposals"


class CalibrationSchemaMismatch(RuntimeError):
    """The calibration component is absent, partial, or not the reviewed version."""


_SESSIONS_V1_SQL = """
CREATE TABLE investor_profile_calibration_sessions (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    closed_at   TEXT
)
"""

_SESSIONS_V2_SQL = """
CREATE TABLE investor_profile_calibration_sessions (
    id                          TEXT PRIMARY KEY,
    status                      TEXT NOT NULL,
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL,
    closed_at                   TEXT,
    interview_version           INTEGER,
    covered_topics_json         TEXT NOT NULL DEFAULT '[]',
    current_topic_id            TEXT,
    current_question_message_id TEXT,
    superseded_reason           TEXT
)
"""

_MESSAGES_V1_SQL = """
CREATE TABLE investor_profile_calibration_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
)
"""

_MESSAGES_V2_SQL = """
CREATE TABLE investor_profile_calibration_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    turn_id     TEXT,
    topic_id    TEXT,
    prompt_id   TEXT
)
"""

_PROPOSALS_V1_SQL = """
CREATE TABLE investor_profile_calibration_proposals (
    id                     TEXT PRIMARY KEY,
    session_id             TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    status                 TEXT NOT NULL,
    profile_patch_json     TEXT NOT NULL,
    raw_profile_patch_json TEXT NOT NULL,
    rationales_json        TEXT NOT NULL,
    changed_fields_json    TEXT NOT NULL DEFAULT '[]',
    created_at             TEXT NOT NULL,
    approved_at            TEXT,
    rejected_at            TEXT
)
"""

_PROPOSALS_V2_SQL = """
CREATE TABLE investor_profile_calibration_proposals (
    id                     TEXT PRIMARY KEY,
    session_id             TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    status                 TEXT NOT NULL,
    profile_patch_json     TEXT NOT NULL,
    raw_profile_patch_json TEXT NOT NULL,
    rationales_json        TEXT NOT NULL,
    changed_fields_json    TEXT NOT NULL DEFAULT '[]',
    created_at             TEXT NOT NULL,
    approved_at            TEXT,
    rejected_at            TEXT,
    covered_topics_json    TEXT NOT NULL DEFAULT '[]',
    base_values_json       TEXT NOT NULL DEFAULT '{}',
    rejected_fields_json   TEXT NOT NULL DEFAULT '[]',
    conflicted_at          TEXT,
    conflict_fields_json   TEXT NOT NULL DEFAULT '[]',
    superseded_at          TEXT,
    superseded_reason      TEXT
)
"""

_TURNS_SQL = """
CREATE TABLE investor_profile_calibration_turns (
    id                   TEXT PRIMARY KEY,
    session_id           TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    kind                 TEXT NOT NULL CHECK (kind IN ('answer','proposal_request')),
    status               TEXT NOT NULL CHECK (status IN ('pending','completed','failed','interrupted')),
    question_message_id  TEXT,
    addressed_topic_id   TEXT,
    request_proposal     INTEGER NOT NULL DEFAULT 0,
    provider             TEXT,
    model                TEXT,
    user_message_id      TEXT,
    assistant_message_id TEXT,
    next_topic_id        TEXT,
    error_code           TEXT,
    diagnostic           TEXT,
    attempt_count        INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    completed_at         TEXT
)
"""

_MARKER_SQL = """
CREATE TABLE investor_profile_calibration_schema (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    version     INTEGER NOT NULL,
    applied_at  TEXT NOT NULL
)
"""

_ACTIVE_INDEX_SQL = """
CREATE UNIQUE INDEX idx_calibration_one_active
ON investor_profile_calibration_sessions(status)
WHERE status = 'active'
"""

_MESSAGES_INDEX_SQL = """
CREATE INDEX idx_calibration_messages_session
ON investor_profile_calibration_messages(session_id, created_at ASC)
"""

_PROPOSALS_INDEX_SQL = """
CREATE INDEX idx_calibration_proposals_session
ON investor_profile_calibration_proposals(session_id, created_at DESC)
"""

_MESSAGE_TURN_INDEX_SQL = """
CREATE UNIQUE INDEX idx_calibration_message_turn_role
ON investor_profile_calibration_messages(session_id, turn_id, role)
WHERE turn_id IS NOT NULL
"""

_PENDING_TURN_INDEX_SQL = """
CREATE UNIQUE INDEX idx_calibration_one_pending_turn
ON investor_profile_calibration_turns(session_id)
WHERE status = 'pending'
"""

_V1_TABLE_SQL = {
    _SESSIONS_TABLE: _SESSIONS_V1_SQL,
    _MESSAGES_TABLE: _MESSAGES_V1_SQL,
    _PROPOSALS_TABLE: _PROPOSALS_V1_SQL,
}

_V2_TABLE_SQL = {
    _MARKER_TABLE: _MARKER_SQL,
    _SESSIONS_TABLE: _SESSIONS_V2_SQL,
    _MESSAGES_TABLE: _MESSAGES_V2_SQL,
    _TURNS_TABLE: _TURNS_SQL,
    _PROPOSALS_TABLE: _PROPOSALS_V2_SQL,
}

_V1_INDEX_SQL = {
    "idx_calibration_one_active": _ACTIVE_INDEX_SQL,
    "idx_calibration_messages_session": _MESSAGES_INDEX_SQL,
    "idx_calibration_proposals_session": _PROPOSALS_INDEX_SQL,
}

_V2_INDEX_SQL = {
    **_V1_INDEX_SQL,
    "idx_calibration_message_turn_role": _MESSAGE_TURN_INDEX_SQL,
    "idx_calibration_one_pending_turn": _PENDING_TURN_INDEX_SQL,
}


def _normalize_sql(sql: str) -> str:
    without_optional_clause = re.sub(
        r"\bIF\s+NOT\s+EXISTS\b", "", sql, flags=re.IGNORECASE
    )
    return "".join(without_optional_clause.split()).rstrip(";").lower()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _component_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name GLOB 'investor_profile_calibration_*'"
        )
    }


def _component_has_non_table_artifacts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('index', 'trigger', 'view') AND "
        "(name GLOB 'investor_profile_calibration_*' "
        "OR name GLOB 'idx_calibration_*' "
        "OR tbl_name GLOB 'investor_profile_calibration_*') LIMIT 1"
    ).fetchone()
    return row is not None


def _schema_sql(conn: sqlite3.Connection, object_type: str, name: str) -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type=? AND name=?", (object_type, name)
    ).fetchone()
    return None if row is None else row[0]


def _verify_table_sql(
    conn: sqlite3.Connection,
    expected: dict[str, str],
) -> bool:
    for table, expected_sql in expected.items():
        actual_sql = _schema_sql(conn, "table", table)
        if actual_sql is None or _normalize_sql(actual_sql) != _normalize_sql(expected_sql):
            return False
    return True


def _verify_index_sql(
    conn: sqlite3.Connection,
    tables: set[str],
    expected: dict[str, str],
) -> bool:
    actual_rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL "
        f"AND tbl_name IN ({','.join('?' for _ in tables)})",
        tuple(sorted(tables)),
    ).fetchall()
    actual = {str(row[0]): str(row[1]) for row in actual_rows}
    if set(actual) != set(expected):
        return False
    return all(
        _normalize_sql(actual[name]) == _normalize_sql(expected_sql)
        for name, expected_sql in expected.items()
    )


def _has_component_triggers(conn: sqlite3.Connection, tables: set[str]) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' "
        f"AND tbl_name IN ({','.join('?' for _ in tables)}) LIMIT 1",
        tuple(sorted(tables)),
    ).fetchone()
    return row is not None


def _marker_is_exact(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        f"SELECT id, version, applied_at FROM {_MARKER_TABLE} ORDER BY id"
    ).fetchall()
    return (
        len(rows) == 1
        and rows[0][0] == 1
        and rows[0][1] == CALIBRATION_SCHEMA_VERSION
        and isinstance(rows[0][2], str)
        and bool(rows[0][2])
    )


def _matches_schema(
    conn: sqlite3.Connection,
    *,
    expected_tables: dict[str, str],
    expected_indexes: dict[str, str],
    require_marker: bool,
) -> bool:
    tables = set(expected_tables)
    if _component_tables(conn) != tables:
        return False
    if not _verify_table_sql(conn, expected_tables):
        return False
    if not _verify_index_sql(conn, tables, expected_indexes):
        return False
    if _has_component_triggers(conn, tables):
        return False
    return not require_marker or _marker_is_exact(conn)


def _classify(conn: sqlite3.Connection) -> str:
    tables = _component_tables(conn)
    if not tables:
        if _component_has_non_table_artifacts(conn):
            raise CalibrationSchemaMismatch("calibration schema has partial artifacts")
        return "fresh"
    if tables == set(_V1_TABLE_SQL) and _matches_schema(
        conn,
        expected_tables=_V1_TABLE_SQL,
        expected_indexes=_V1_INDEX_SQL,
        require_marker=False,
    ):
        return "v1"
    if tables == set(_V2_TABLE_SQL) and _matches_schema(
        conn,
        expected_tables=_V2_TABLE_SQL,
        expected_indexes=_V2_INDEX_SQL,
        require_marker=True,
    ):
        return "v2"
    raise CalibrationSchemaMismatch("calibration schema fingerprint mismatch")


def _fresh_statements(now: str) -> tuple[tuple[str, Any], ...]:
    return (
        (_SESSIONS_V2_SQL, ()),
        (_ACTIVE_INDEX_SQL, ()),
        (_MESSAGES_V2_SQL, ()),
        (_MESSAGES_INDEX_SQL, ()),
        (_MESSAGE_TURN_INDEX_SQL, ()),
        (_TURNS_SQL, ()),
        (_PENDING_TURN_INDEX_SQL, ()),
        (_PROPOSALS_V2_SQL, ()),
        (_PROPOSALS_INDEX_SQL, ()),
        (_MARKER_SQL, ()),
        (
            "INSERT INTO investor_profile_calibration_schema (id, version, applied_at) "
            "VALUES (1, 2, :now)",
            {"now": now},
        ),
    )


def _v1_migration_statements(now: str) -> tuple[tuple[str, Any], ...]:
    return (
        (
            "ALTER TABLE investor_profile_calibration_sessions "
            "ADD COLUMN interview_version INTEGER",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_sessions "
            "ADD COLUMN covered_topics_json TEXT NOT NULL DEFAULT '[]'",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_sessions "
            "ADD COLUMN current_topic_id TEXT",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_sessions "
            "ADD COLUMN current_question_message_id TEXT",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_sessions "
            "ADD COLUMN superseded_reason TEXT",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_messages ADD COLUMN turn_id TEXT",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_messages ADD COLUMN topic_id TEXT",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_messages ADD COLUMN prompt_id TEXT",
            (),
        ),
        (_MESSAGE_TURN_INDEX_SQL, ()),
        (_TURNS_SQL, ()),
        (_PENDING_TURN_INDEX_SQL, ()),
        (
            "ALTER TABLE investor_profile_calibration_proposals "
            "ADD COLUMN covered_topics_json TEXT NOT NULL DEFAULT '[]'",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_proposals "
            "ADD COLUMN base_values_json TEXT NOT NULL DEFAULT '{}'",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_proposals "
            "ADD COLUMN rejected_fields_json TEXT NOT NULL DEFAULT '[]'",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_proposals ADD COLUMN conflicted_at TEXT",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_proposals "
            "ADD COLUMN conflict_fields_json TEXT NOT NULL DEFAULT '[]'",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_proposals ADD COLUMN superseded_at TEXT",
            (),
        ),
        (
            "ALTER TABLE investor_profile_calibration_proposals ADD COLUMN superseded_reason TEXT",
            (),
        ),
        (
            "UPDATE investor_profile_calibration_sessions "
            "SET status='superseded', updated_at=:now, closed_at=COALESCE(closed_at,:now), "
            "superseded_reason='legacy_guided_protocol_unavailable' "
            "WHERE status='active'",
            {"now": now},
        ),
        (
            "UPDATE investor_profile_calibration_proposals "
            "SET status='superseded', superseded_at=:now, "
            "superseded_reason='legacy_proposal_missing_coverage_proof' "
            "WHERE status='draft'",
            {"now": now},
        ),
        (_MARKER_SQL, ()),
        (
            "INSERT INTO investor_profile_calibration_schema (id, version, applied_at) "
            "VALUES (1, 2, :now)",
            {"now": now},
        ),
    )


def _connect_writable(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise CalibrationSchemaMismatch("calibration database does not exist")
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    except sqlite3.Error as exc:
        raise CalibrationSchemaMismatch("calibration database is not readable") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def assert_calibration_schema_v2(db_path: str | Path) -> None:
    """Assert the exact marked v2 fingerprint without creating or writing."""
    path = Path(db_path)
    conn = _connect_read_only(path)
    try:
        if _classify(conn) != "v2":
            raise CalibrationSchemaMismatch("calibration schema is not version 2")
    except CalibrationSchemaMismatch:
        raise
    except sqlite3.Error as exc:
        raise CalibrationSchemaMismatch("calibration schema fingerprint mismatch") from exc
    finally:
        conn.close()


def migrate_calibration_schema(db_path: str | Path) -> None:
    """Create or migrate the exact calibration schema under one write lock."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect_writable(path)
    try:
        try:
            initial_state = _classify(conn)
        except sqlite3.Error as exc:
            raise CalibrationSchemaMismatch("calibration schema fingerprint mismatch") from exc
        if initial_state == "v2":
            return

        conn.execute("BEGIN IMMEDIATE")
        try:
            locked_state = _classify(conn)
            if locked_state == "v2":
                conn.rollback()
                return
            if locked_state != initial_state:
                raise CalibrationSchemaMismatch("calibration schema changed during migration")

            now = _now()
            statements = (
                _fresh_statements(now)
                if locked_state == "fresh"
                else _v1_migration_statements(now)
            )
            for sql, parameters in statements:
                conn.execute(sql, parameters)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.close()

    assert_calibration_schema_v2(path)
