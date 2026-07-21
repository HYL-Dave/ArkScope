"""Exact schema-v2 and legacy calibration migration contract."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest


V1_SCHEMA = """
CREATE TABLE IF NOT EXISTS investor_profile_calibration_sessions (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    closed_at   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_calibration_one_active
ON investor_profile_calibration_sessions(status)
WHERE status = 'active';

CREATE TABLE IF NOT EXISTS investor_profile_calibration_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calibration_messages_session
ON investor_profile_calibration_messages(session_id, created_at ASC);

CREATE TABLE IF NOT EXISTS investor_profile_calibration_proposals (
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
);
CREATE INDEX IF NOT EXISTS idx_calibration_proposals_session
ON investor_profile_calibration_proposals(session_id, created_at DESC);
"""

EXPECTED_COLUMNS = {
    "investor_profile_calibration_schema": (
        ("id", "INTEGER", 0, None, 1),
        ("version", "INTEGER", 1, None, 0),
        ("applied_at", "TEXT", 1, None, 0),
    ),
    "investor_profile_calibration_sessions": (
        ("id", "TEXT", 0, None, 1),
        ("status", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
        ("updated_at", "TEXT", 1, None, 0),
        ("closed_at", "TEXT", 0, None, 0),
        ("interview_version", "INTEGER", 0, None, 0),
        ("covered_topics_json", "TEXT", 1, "'[]'", 0),
        ("current_topic_id", "TEXT", 0, None, 0),
        ("current_question_message_id", "TEXT", 0, None, 0),
        ("superseded_reason", "TEXT", 0, None, 0),
    ),
    "investor_profile_calibration_messages": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("role", "TEXT", 1, None, 0),
        ("content", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
        ("turn_id", "TEXT", 0, None, 0),
        ("topic_id", "TEXT", 0, None, 0),
        ("prompt_id", "TEXT", 0, None, 0),
    ),
    "investor_profile_calibration_turns": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("kind", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("question_message_id", "TEXT", 0, None, 0),
        ("addressed_topic_id", "TEXT", 0, None, 0),
        ("request_proposal", "INTEGER", 1, "0", 0),
        ("provider", "TEXT", 0, None, 0),
        ("model", "TEXT", 0, None, 0),
        ("user_message_id", "TEXT", 0, None, 0),
        ("assistant_message_id", "TEXT", 0, None, 0),
        ("next_topic_id", "TEXT", 0, None, 0),
        ("error_code", "TEXT", 0, None, 0),
        ("diagnostic", "TEXT", 0, None, 0),
        ("attempt_count", "INTEGER", 1, "1", 0),
        ("created_at", "TEXT", 1, None, 0),
        ("updated_at", "TEXT", 1, None, 0),
        ("completed_at", "TEXT", 0, None, 0),
    ),
    "investor_profile_calibration_proposals": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("profile_patch_json", "TEXT", 1, None, 0),
        ("raw_profile_patch_json", "TEXT", 1, None, 0),
        ("rationales_json", "TEXT", 1, None, 0),
        ("changed_fields_json", "TEXT", 1, "'[]'", 0),
        ("created_at", "TEXT", 1, None, 0),
        ("approved_at", "TEXT", 0, None, 0),
        ("rejected_at", "TEXT", 0, None, 0),
        ("covered_topics_json", "TEXT", 1, "'[]'", 0),
        ("base_values_json", "TEXT", 1, "'{}'", 0),
        ("rejected_fields_json", "TEXT", 1, "'[]'", 0),
        ("conflicted_at", "TEXT", 0, None, 0),
        ("conflict_fields_json", "TEXT", 1, "'[]'", 0),
        ("superseded_at", "TEXT", 0, None, 0),
        ("superseded_reason", "TEXT", 0, None, 0),
    ),
}

EXPECTED_INDEXES = {
    "idx_calibration_one_active",
    "idx_calibration_messages_session",
    "idx_calibration_proposals_session",
    "idx_calibration_message_turn_role",
    "idx_calibration_one_pending_turn",
}


def _schema_module():
    import src.investor_profile_calibration_schema as schema

    return schema


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_v1(path: Path, *, populated: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(V1_SCHEMA)
        conn.execute("PRAGMA user_version = 41")
        if not populated:
            return
        conn.executemany(
            "INSERT INTO investor_profile_calibration_sessions "
            "(id, status, created_at, updated_at, closed_at) VALUES (?, ?, ?, ?, ?)",
            (
                ("session-active", "active", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00", None),
                ("session-closed", "closed", "2026-02-01T00:00:00+00:00", "2026-02-02T00:00:00+00:00", "2026-02-02T00:00:00+00:00"),
                ("session-old-superseded", "superseded", "2026-03-01T00:00:00+00:00", "2026-03-02T00:00:00+00:00", "2026-03-02T00:00:00+00:00"),
            ),
        )
        conn.executemany(
            "INSERT INTO investor_profile_calibration_messages "
            "(id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                ("message-user", "session-active", "user", "Line one.\n投資者原文 stays exact.", "2026-01-03T00:00:00+00:00"),
                ("message-assistant", "session-active", "assistant", "Keep  spaces  and punctuation!", "2026-01-03T00:00:01+00:00"),
            ),
        )
        conn.executemany(
            "INSERT INTO investor_profile_calibration_proposals "
            "(id, session_id, status, profile_patch_json, raw_profile_patch_json, "
            "rationales_json, changed_fields_json, created_at, approved_at, rejected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    "proposal-draft",
                    "session-active",
                    "draft",
                    '{"risk_appetite": 8}',
                    '{ "risk_appetite" : "8" }',
                    '{"risk_appetite":"source wording"}',
                    "[]",
                    "2026-01-04T00:00:00+00:00",
                    None,
                    None,
                ),
                (
                    "proposal-approved",
                    "session-closed",
                    "approved",
                    '{"default_stance":"neutral"}',
                    '{"default_stance":"neutral"}',
                    '{"default_stance":"exact rationale"}',
                    '["default_stance"]',
                    "2026-02-01T00:00:00+00:00",
                    "2026-02-02T00:00:00+00:00",
                    None,
                ),
                (
                    "proposal-rejected",
                    "session-old-superseded",
                    "rejected",
                    '{"holding_horizon":"multi_year"}',
                    '{"holding_horizon":"multi_year"}',
                    "{}",
                    "[]",
                    "2026-03-01T00:00:00+00:00",
                    None,
                    "2026-03-02T00:00:00+00:00",
                ),
            ),
        )


def _column_fingerprint(conn: sqlite3.Connection, table: str) -> tuple[tuple, ...]:
    return tuple(
        (row["name"], row["type"], row["notnull"], row["dflt_value"], row["pk"])
        for row in conn.execute(f'PRAGMA table_info("{table}")')
    )


def _assert_exact_v2(path: Path) -> None:
    with _connect(path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'investor_profile_calibration_%'"
            )
        }
        assert tables == set(EXPECTED_COLUMNS)
        for table, expected in EXPECTED_COLUMNS.items():
            assert _column_fingerprint(conn, table) == expected

        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL "
                "AND tbl_name LIKE 'investor_profile_calibration_%'"
            )
        }
        assert indexes == EXPECTED_INDEXES

        marker_rows = conn.execute(
            "SELECT id, version, applied_at FROM investor_profile_calibration_schema"
        ).fetchall()
        assert len(marker_rows) == 1
        assert tuple(marker_rows[0])[:2] == (1, 2)
        assert marker_rows[0]["applied_at"]

        turns_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='investor_profile_calibration_turns'"
        ).fetchone()[0]
        assert "'answer','proposal_request'" in turns_sql.replace(" ", "")
        assert "'pending','completed','failed','interrupted'" in turns_sql.replace(" ", "")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def _legacy_digest(conn: sqlite3.Connection) -> str:
    payload = {
        "messages": [
            tuple(row)
            for row in conn.execute(
                "SELECT id, session_id, role, content, created_at "
                "FROM investor_profile_calibration_messages ORDER BY id"
            )
        ],
        "terminal_proposals": [
            tuple(row)
            for row in conn.execute(
                "SELECT id, session_id, status, profile_patch_json, raw_profile_patch_json, "
                "rationales_json, changed_fields_json, created_at, approved_at, rejected_at "
                "FROM investor_profile_calibration_proposals "
                "WHERE status IN ('approved', 'rejected') ORDER BY id"
            )
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _logical_snapshot(path: Path) -> tuple:
    with _connect(path) as conn:
        schema_rows = tuple(
            tuple(row)
            for row in conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_autoindex_%' ORDER BY type, name"
            )
        )
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'investor_profile_calibration_%' ORDER BY name"
            )
        ]
        data = tuple(
            (table, tuple(tuple(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid')))
            for table in tables
        )
        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    return schema_rows, data, user_version


def test_fresh_migration_creates_exact_v2_schema_and_marker(tmp_path):
    schema = _schema_module()

    for name, create_unrelated_db, expected_user_version in (
        ("absent.db", False, 0),
        ("unrelated.db", True, 73),
    ):
        path = tmp_path / name
        if create_unrelated_db:
            with _connect(path) as conn:
                conn.execute("CREATE TABLE unrelated_state (id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO unrelated_state(value) VALUES ('preserve me')")
                conn.execute("PRAGMA user_version = 73")

        schema.migrate_calibration_schema(path)

        _assert_exact_v2(path)
        schema.assert_calibration_schema_v2(path)
        with _connect(path) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == expected_user_version
            if create_unrelated_db:
                assert conn.execute("SELECT value FROM unrelated_state").fetchone()[0] == "preserve me"


def test_v1_migration_preserves_message_and_terminal_proposal_bytes(tmp_path):
    schema = _schema_module()
    path = tmp_path / "legacy.db"
    _create_v1(path)
    with _connect(path) as conn:
        before = _legacy_digest(conn)

    schema.migrate_calibration_schema(path)

    with _connect(path) as conn:
        assert _legacy_digest(conn) == before
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 41
        for proposal_id in ("proposal-approved", "proposal-rejected"):
            row = conn.execute(
                "SELECT covered_topics_json, base_values_json, rejected_fields_json, "
                "conflicted_at, conflict_fields_json, superseded_at, superseded_reason "
                "FROM investor_profile_calibration_proposals WHERE id=?",
                (proposal_id,),
            ).fetchone()
            assert tuple(row) == ("[]", "{}", "[]", None, "[]", None, None)


def test_v1_migration_supersedes_active_session_and_draft_only(tmp_path):
    schema = _schema_module()
    path = tmp_path / "legacy.db"
    _create_v1(path)
    with _connect(path) as conn:
        untouched_sessions = {
            row["id"]: tuple(row)
            for row in conn.execute(
                "SELECT id, status, created_at, updated_at, closed_at "
                "FROM investor_profile_calibration_sessions WHERE status != 'active'"
            )
        }

    schema.migrate_calibration_schema(path)

    with _connect(path) as conn:
        active = conn.execute(
            "SELECT status, updated_at, closed_at, interview_version, covered_topics_json, "
            "current_topic_id, current_question_message_id, superseded_reason "
            "FROM investor_profile_calibration_sessions WHERE id='session-active'"
        ).fetchone()
        assert active["status"] == "superseded"
        assert active["updated_at"] == active["closed_at"]
        assert active["interview_version"] is None
        assert active["covered_topics_json"] == "[]"
        assert active["current_topic_id"] is None
        assert active["current_question_message_id"] is None
        assert active["superseded_reason"] == "legacy_guided_protocol_unavailable"

        for session_id, before in untouched_sessions.items():
            after = conn.execute(
                "SELECT id, status, created_at, updated_at, closed_at "
                "FROM investor_profile_calibration_sessions WHERE id=?",
                (session_id,),
            ).fetchone()
            assert tuple(after) == before
            assert conn.execute(
                "SELECT superseded_reason FROM investor_profile_calibration_sessions WHERE id=?",
                (session_id,),
            ).fetchone()[0] is None

        draft = conn.execute(
            "SELECT status, superseded_at, superseded_reason, covered_topics_json, base_values_json "
            "FROM investor_profile_calibration_proposals WHERE id='proposal-draft'"
        ).fetchone()
        assert draft["status"] == "superseded"
        assert draft["superseded_at"]
        assert draft["superseded_reason"] == "legacy_proposal_missing_coverage_proof"
        assert draft["covered_topics_json"] == "[]"
        assert draft["base_values_json"] == "{}"
        assert {
            row["id"]: row["status"]
            for row in conn.execute(
                "SELECT id, status FROM investor_profile_calibration_proposals "
                "WHERE id != 'proposal-draft'"
            )
        } == {"proposal-approved": "approved", "proposal-rejected": "rejected"}


def test_v2_migration_is_idempotent(tmp_path):
    schema = _schema_module()
    path = tmp_path / "current.db"
    schema.migrate_calibration_schema(path)
    with _connect(path) as conn:
        conn.execute(
            "CREATE TABLE unrelated_literal_default ("
            "id INTEGER PRIMARY KEY, note TEXT DEFAULT "
            "'investor_profile_calibration_sessions')"
        )
        conn.execute(
            'CREATE TABLE unrelated_column_name ('
            '"investor_profile_calibration_sessions" TEXT)'
        )
        conn.execute(
            "CREATE VIEW unrelated_comment_view AS "
            "SELECT id /* investor_profile_calibration_sessions */ "
            "FROM unrelated_literal_default"
        )
        conn.execute(
            "CREATE VIEW unrelated_insert_view AS "
            "SELECT id, note FROM unrelated_literal_default"
        )
        conn.execute(
            "CREATE TRIGGER unrelated_insert_view_insert "
            "INSTEAD OF INSERT ON unrelated_insert_view BEGIN "
            "INSERT INTO unrelated_literal_default(note) VALUES (NEW.note); END"
        )
        stored_sql = "\n".join(
            str(row[0])
            for row in conn.execute(
                "SELECT sql FROM sqlite_master WHERE name LIKE 'unrelated_%' "
                "ORDER BY name"
            )
        )
    assert stored_sql.count("investor_profile_calibration_sessions") == 3

    first_bytes = path.read_bytes()
    first_snapshot = _logical_snapshot(path)

    for _attempt in range(3):
        schema.migrate_calibration_schema(path)
        schema.assert_calibration_schema_v2(path)

    assert path.read_bytes() == first_bytes
    assert _logical_snapshot(path) == first_snapshot


def test_marker_schema_mismatch_fails_closed_without_writes(tmp_path):
    schema = _schema_module()

    for case in (
        "wrong_marker",
        "unknown_column",
        "unknown_index",
        "altered_quoted_literal",
        "extra_namespaced_view",
        "namespaced_index_on_unrelated_table",
        "uppercase_component_table",
        "view_tied_to_component_table",
        "schema_qualified_single_quoted_view",
        "unrelated_trigger_writes_component",
        "ordinary_trigger_masks_component_access",
        "unrelated_table_references_component",
    ):
        path = tmp_path / f"{case}.db"
        schema.migrate_calibration_schema(path)
        with _connect(path) as conn:
            if case == "wrong_marker":
                conn.execute("UPDATE investor_profile_calibration_schema SET version=99 WHERE id=1")
            elif case == "unknown_column":
                conn.execute(
                    "ALTER TABLE investor_profile_calibration_sessions ADD COLUMN unreviewed TEXT"
                )
            else:
                if case == "unknown_index":
                    conn.execute(
                        "CREATE INDEX idx_unreviewed_calibration_status "
                        "ON investor_profile_calibration_sessions(status, updated_at)"
                    )
                elif case == "altered_quoted_literal":
                    conn.execute("DROP INDEX idx_calibration_one_pending_turn")
                    conn.execute(
                        "CREATE UNIQUE INDEX idx_calibration_one_pending_turn "
                        "ON investor_profile_calibration_turns(session_id) "
                        "WHERE status = ' pending '"
                    )
                elif case == "extra_namespaced_view":
                    conn.execute(
                        "CREATE VIEW investor_profile_calibration_unreviewed AS "
                        "SELECT id FROM investor_profile_calibration_sessions"
                    )
                elif case == "namespaced_index_on_unrelated_table":
                    conn.execute("CREATE TABLE unrelated_index_state (value TEXT)")
                    conn.execute(
                        "CREATE INDEX idx_calibration_unrelated_state "
                        "ON unrelated_index_state(value)"
                    )
                elif case == "uppercase_component_table":
                    conn.execute(
                        "CREATE TABLE INVESTOR_PROFILE_CALIBRATION_UNREVIEWED "
                        "(id INTEGER PRIMARY KEY)"
                    )
                elif case == "view_tied_to_component_table":
                    conn.execute(
                        "CREATE VIEW unrelated_calibration_projection AS "
                        "SELECT id FROM 'investor_profile_calibration_sessions'"
                    )
                elif case == "schema_qualified_single_quoted_view":
                    conn.execute(
                        "CREATE VIEW qualified_calibration_projection AS "
                        "SELECT id FROM main.'investor_profile_calibration_sessions'"
                    )
                elif case == "unrelated_trigger_writes_component":
                    conn.execute("CREATE TABLE unrelated_trigger_source (id TEXT)")
                    conn.execute(
                        "CREATE TRIGGER inject_calibration_session "
                        "AFTER INSERT ON unrelated_trigger_source BEGIN "
                        "INSERT INTO investor_profile_calibration_sessions "
                        "(id, status, created_at, updated_at) "
                        "VALUES ('injected-by-trigger', 'closed', 'now', 'now'); END"
                    )
                elif case == "ordinary_trigger_masks_component_access":
                    conn.execute("CREATE TABLE unrelated_masking_owner (id TEXT)")
                    conn.execute(
                        "CREATE TRIGGER unrelated_masking_trigger "
                        "AFTER INSERT ON unrelated_masking_owner BEGIN "
                        "INSERT INTO missing_unrelated_target(id) VALUES (NEW.id); "
                        "INSERT INTO investor_profile_calibration_sessions "
                        "(id, status, created_at, updated_at) "
                        "VALUES ('masked-target', 'closed', 'now', 'now'); END"
                    )
                elif case == "unrelated_table_references_component":
                    conn.execute(
                        "CREATE TABLE unrelated_session_links ("
                        "id TEXT PRIMARY KEY, session_id TEXT REFERENCES "
                        "investor_profile_calibration_sessions(id))"
                    )
        before = _logical_snapshot(path)
        before_bytes = path.read_bytes()

        with pytest.raises(schema.CalibrationSchemaMismatch):
            schema.migrate_calibration_schema(path)
        with pytest.raises(schema.CalibrationSchemaMismatch):
            schema.assert_calibration_schema_v2(path)

        assert _logical_snapshot(path) == before
        assert path.read_bytes() == before_bytes
        if case == "unrelated_trigger_writes_component":
            with _connect(path) as conn:
                assert conn.execute(
                    "SELECT COUNT(*) FROM investor_profile_calibration_sessions "
                    "WHERE id='injected-by-trigger'"
                ).fetchone()[0] == 0


def test_unmarked_v2_artifacts_fail_closed_without_rebuild(tmp_path):
    schema = _schema_module()

    paths = []
    full_v2 = tmp_path / "unmarked-v2.db"
    schema.migrate_calibration_schema(full_v2)
    with _connect(full_v2) as conn:
        conn.execute("DROP TABLE investor_profile_calibration_schema")
    paths.append(full_v2)

    partial_v2 = tmp_path / "partial-v2.db"
    _create_v1(partial_v2, populated=False)
    with _connect(partial_v2) as conn:
        conn.execute(
            "ALTER TABLE investor_profile_calibration_sessions ADD COLUMN interview_version INTEGER"
        )
    paths.append(partial_v2)

    unknown_v1 = tmp_path / "unknown-v1.db"
    _create_v1(unknown_v1, populated=False)
    with _connect(unknown_v1) as conn:
        conn.execute(
            "CREATE INDEX idx_unknown_v1_role ON investor_profile_calibration_messages(role)"
        )
    paths.append(unknown_v1)

    dangling_view = tmp_path / "fresh-dangling-view.db"
    with _connect(dangling_view) as conn:
        conn.execute(
            "CREATE VIEW dangling_calibration_projection AS "
            "SELECT id FROM investor_profile_calibration_sessions"
        )
    paths.append(dangling_view)

    comma_literal_view = tmp_path / "fresh-comma-literal-view.db"
    with _connect(comma_literal_view) as conn:
        conn.execute("CREATE TABLE unrelated_view_source (id TEXT)")
        conn.execute(
            "CREATE VIEW comma_literal_calibration_projection AS "
            "SELECT unrelated_view_source.id FROM unrelated_view_source, "
            "'investor_profile_calibration_sessions'"
        )
    paths.append(comma_literal_view)

    missing_trigger_target = tmp_path / "fresh-missing-trigger-target.db"
    with _connect(missing_trigger_target) as conn:
        conn.execute("CREATE TABLE unrelated_trigger_owner (id TEXT)")
        conn.execute(
            "CREATE TRIGGER unrelated_missing_target_trigger "
            "AFTER INSERT ON unrelated_trigger_owner BEGIN "
            "INSERT INTO investor_profile_calibration_sessions "
            "(id, status, created_at, updated_at) "
            "VALUES ('missing-target', 'closed', 'now', 'now'); END"
        )
    paths.append(missing_trigger_target)

    for path in paths:
        before = _logical_snapshot(path)
        before_bytes = path.read_bytes()
        with pytest.raises(schema.CalibrationSchemaMismatch):
            schema.migrate_calibration_schema(path)
        assert _logical_snapshot(path) == before
        assert path.read_bytes() == before_bytes


def test_statement_failure_rolls_back_to_exact_v1(tmp_path, monkeypatch):
    schema = _schema_module()
    path = tmp_path / "legacy.db"
    _create_v1(path)
    before = _logical_snapshot(path)
    real_connect = sqlite3.connect

    def connect_with_failing_index(*args, **kwargs):
        conn = real_connect(*args, **kwargs)

        def authorizer(action, arg1, _arg2, _database, _source):
            if action == sqlite3.SQLITE_CREATE_INDEX and arg1 == "idx_calibration_message_turn_role":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        conn.set_authorizer(authorizer)
        return conn

    monkeypatch.setattr(schema.sqlite3, "connect", connect_with_failing_index)

    with pytest.raises(sqlite3.DatabaseError):
        schema.migrate_calibration_schema(path)

    assert _logical_snapshot(path) == before


def test_store_construction_and_status_read_never_create_or_migrate(tmp_path, monkeypatch):
    schema = _schema_module()
    import src.investor_profile_calibration as calibration_module
    from src.investor_profile_calibration import CalibrationStore

    missing = tmp_path / "missing-parent" / "missing.db"
    with pytest.raises(schema.CalibrationSchemaMismatch):
        CalibrationStore(missing)
    assert not missing.exists()
    assert not missing.parent.exists()

    legacy = tmp_path / "legacy.db"
    _create_v1(legacy, populated=False)
    legacy_before = _logical_snapshot(legacy)
    with pytest.raises(schema.CalibrationSchemaMismatch):
        CalibrationStore(legacy)
    assert _logical_snapshot(legacy) == legacy_before

    current = tmp_path / "current.db"
    schema.migrate_calibration_schema(current)
    current_before = current.read_bytes()
    store = CalibrationStore(current)

    real_connect = sqlite3.connect
    opened = []

    def recording_connect(database, *args, **kwargs):
        opened.append((str(database), dict(kwargs)))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(calibration_module.sqlite3, "connect", recording_connect)

    assert store.get_active_session() is None
    assert store.get_session("missing-session") is None
    assert store.list_sessions() == []
    assert store.list_messages("missing-session") == []
    assert store.get_proposal("missing-proposal") is None
    assert store.latest_proposal("missing-session") is None
    assert len(opened) == 6
    assert all(database.endswith("?mode=ro") for database, _kwargs in opened)
    assert all(kwargs.get("uri") is True for _database, kwargs in opened)

    with store._connect_read_only() as read_conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            read_conn.execute(
                "INSERT INTO investor_profile_calibration_sessions "
                "(id, status, created_at, updated_at) "
                "VALUES ('read-path-write', 'closed', 'now', 'now')"
            )
    assert current.read_bytes() == current_before

    current.unlink()
    with pytest.raises(sqlite3.OperationalError):
        store.get_active_session()
    assert not current.exists()
