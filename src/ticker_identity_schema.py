"""Additive profile-side schema for approved ticker identity transitions."""

from __future__ import annotations

import re
import sqlite3


TRANSITION_KINDS = frozenset({"symbol_continuation", "terminal_delisting"})
TRANSITION_STATUSES = frozenset(
    {"approved", "needs_review", "applied", "cancelled", "reversed"}
)
ATTEMPT_TRIGGERS = frozenset({"attended_user", "scheduler"})
ATTEMPT_STATUSES = frozenset({"blocked", "applied", "already_applied", "reversed"})
PRIORITY_RESOLUTIONS = frozenset({"source", "successor"})


class TickerIdentitySchemaMismatch(RuntimeError):
    """The ticker identity component is missing, extended, or drifted."""


def _quoted(values: frozenset[str]) -> str:
    return ", ".join(f"'{value}'" for value in sorted(values))


IDENTITY_TABLE_SQL = {
    "ticker_identity_transitions": f"""
        CREATE TABLE ticker_identity_transitions (
            transition_id TEXT PRIMARY KEY CHECK (length(transition_id) BETWEEN 1 AND 120),
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            assessment_id TEXT NOT NULL REFERENCES security_lifecycle_assessments(assessment_id) ON DELETE RESTRICT,
            proposal_ids_json TEXT NOT NULL CHECK (length(proposal_ids_json) BETWEEN 2 AND 8192),
            transition_dedupe_key TEXT NOT NULL UNIQUE CHECK (length(transition_dedupe_key) BETWEEN 1 AND 500 AND instr(transition_dedupe_key, char(0)) = 0),
            kind TEXT NOT NULL CHECK (kind IN ({_quoted(TRANSITION_KINDS)})),
            status TEXT NOT NULL CHECK (status IN ({_quoted(TRANSITION_STATUSES)})),
            source_ticker TEXT NOT NULL CHECK (length(source_ticker) BETWEEN 1 AND 20 AND instr(source_ticker, char(0)) = 0),
            successor_ticker TEXT CHECK (successor_ticker IS NULL OR (length(successor_ticker) BETWEEN 1 AND 20 AND instr(successor_ticker, char(0)) = 0)),
            execute_on TEXT NOT NULL CHECK (length(execute_on) = 10),
            priority_resolution TEXT CHECK (priority_resolution IS NULL OR priority_resolution IN ({_quoted(PRIORITY_RESOLUTIONS)})),
            unhide_successor INTEGER NOT NULL CHECK (unhide_successor IN (0, 1)),
            approved_observation_fingerprint_sha256 TEXT NOT NULL CHECK (length(approved_observation_fingerprint_sha256) = 64),
            approved_assessment_fingerprint_sha256 TEXT NOT NULL CHECK (length(approved_assessment_fingerprint_sha256) = 64),
            approved_preview_sha256 TEXT NOT NULL CHECK (length(approved_preview_sha256) = 64),
            approved_preview_json TEXT NOT NULL CHECK (length(approved_preview_json) BETWEEN 2 AND 65536),
            before_snapshot_json TEXT CHECK (before_snapshot_json IS NULL OR length(before_snapshot_json) BETWEEN 2 AND 65536),
            after_snapshot_sha256 TEXT CHECK (after_snapshot_sha256 IS NULL OR length(after_snapshot_sha256) = 64),
            approved_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            applied_at TEXT,
            cancelled_at TEXT,
            reversed_at TEXT,
            CHECK (
                (kind = 'symbol_continuation' AND successor_ticker IS NOT NULL AND successor_ticker <> source_ticker)
                OR (kind = 'terminal_delisting' AND successor_ticker IS NULL)
            ),
            CHECK (
                kind = 'symbol_continuation'
                OR (priority_resolution IS NULL AND unhide_successor = 0)
            ),
            CHECK (
                (status IN ('approved', 'needs_review')
                    AND before_snapshot_json IS NULL
                    AND after_snapshot_sha256 IS NULL
                    AND applied_at IS NULL
                    AND cancelled_at IS NULL
                    AND reversed_at IS NULL)
                OR (status = 'applied'
                    AND before_snapshot_json IS NOT NULL
                    AND after_snapshot_sha256 IS NOT NULL
                    AND applied_at IS NOT NULL
                    AND cancelled_at IS NULL
                    AND reversed_at IS NULL)
                OR (status = 'cancelled'
                    AND before_snapshot_json IS NULL
                    AND after_snapshot_sha256 IS NULL
                    AND applied_at IS NULL
                    AND cancelled_at IS NOT NULL
                    AND reversed_at IS NULL)
                OR (status = 'reversed'
                    AND before_snapshot_json IS NOT NULL
                    AND after_snapshot_sha256 IS NOT NULL
                    AND applied_at IS NOT NULL
                    AND cancelled_at IS NULL
                    AND reversed_at IS NOT NULL)
            )
        )
    """,
    "ticker_identity_transition_attempts": f"""
        CREATE TABLE ticker_identity_transition_attempts (
            attempt_id TEXT PRIMARY KEY CHECK (length(attempt_id) BETWEEN 1 AND 120),
            transition_id TEXT NOT NULL REFERENCES ticker_identity_transitions(transition_id) ON DELETE CASCADE,
            trigger TEXT NOT NULL CHECK (trigger IN ({_quoted(ATTEMPT_TRIGGERS)})),
            status TEXT NOT NULL CHECK (status IN ({_quoted(ATTEMPT_STATUSES)})),
            block_reasons_json TEXT NOT NULL CHECK (length(block_reasons_json) BETWEEN 2 AND 8192),
            observed_preview_sha256 TEXT CHECK (observed_preview_sha256 IS NULL OR length(observed_preview_sha256) = 64),
            attempted_at TEXT NOT NULL
        )
    """,
    "ticker_identity_links": """
        CREATE TABLE ticker_identity_links (
            link_id TEXT PRIMARY KEY CHECK (length(link_id) BETWEEN 1 AND 120),
            transition_id TEXT NOT NULL UNIQUE REFERENCES ticker_identity_transitions(transition_id) ON DELETE CASCADE,
            source_ticker TEXT NOT NULL CHECK (length(source_ticker) BETWEEN 1 AND 20 AND instr(source_ticker, char(0)) = 0),
            successor_ticker TEXT NOT NULL CHECK (length(successor_ticker) BETWEEN 1 AND 20 AND instr(successor_ticker, char(0)) = 0),
            relationship TEXT NOT NULL CHECK (relationship = 'symbol_continuation'),
            effective_date TEXT NOT NULL CHECK (length(effective_date) = 10),
            created_at TEXT NOT NULL,
            reversed_at TEXT,
            CHECK (successor_ticker <> source_ticker)
        )
    """,
}


IDENTITY_INDEX_SQL = {
    "idx_ticker_identity_transitions_due": """
        CREATE INDEX idx_ticker_identity_transitions_due
        ON ticker_identity_transitions(status, execute_on)
    """,
    "idx_ticker_identity_attempts_transition": """
        CREATE INDEX idx_ticker_identity_attempts_transition
        ON ticker_identity_transition_attempts(transition_id, attempted_at)
    """,
    "idx_ticker_identity_links_source": """
        CREATE INDEX idx_ticker_identity_links_source
        ON ticker_identity_links(source_ticker, reversed_at)
    """,
    "idx_ticker_identity_links_successor": """
        CREATE INDEX idx_ticker_identity_links_successor
        ON ticker_identity_links(successor_ticker, reversed_at)
    """,
}


# V1 is the exact additive ticker-identity authority used by the first live
# cutover. Keep it reproducible for rollback and the next migration.
V1_IDENTITY_TABLE_SQL = dict(IDENTITY_TABLE_SQL)
V1_IDENTITY_INDEX_SQL = dict(IDENTITY_INDEX_SQL)

TRANSITION_APPROVAL_AUTHORITIES = frozenset({"attended_user", "automation_policy"})
TRANSITION_ACTIVITY_TYPES = frozenset({"applied", "reversed"})


IDENTITY_TABLE_SQL = {
    **V1_IDENTITY_TABLE_SQL,
    "ticker_identity_transitions": f"""
        CREATE TABLE ticker_identity_transitions (
            transition_id TEXT PRIMARY KEY CHECK (length(transition_id) BETWEEN 1 AND 120),
            case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id) ON DELETE CASCADE,
            assessment_id TEXT NOT NULL REFERENCES security_lifecycle_assessments(assessment_id) ON DELETE RESTRICT,
            proposal_ids_json TEXT NOT NULL CHECK (length(proposal_ids_json) BETWEEN 2 AND 8192),
            transition_dedupe_key TEXT NOT NULL UNIQUE CHECK (length(transition_dedupe_key) BETWEEN 1 AND 500 AND instr(transition_dedupe_key, char(0)) = 0),
            kind TEXT NOT NULL CHECK (kind IN ({_quoted(TRANSITION_KINDS)})),
            status TEXT NOT NULL CHECK (status IN ({_quoted(TRANSITION_STATUSES)})),
            source_ticker TEXT NOT NULL CHECK (length(source_ticker) BETWEEN 1 AND 20 AND instr(source_ticker, char(0)) = 0),
            successor_ticker TEXT CHECK (successor_ticker IS NULL OR (length(successor_ticker) BETWEEN 1 AND 20 AND instr(successor_ticker, char(0)) = 0)),
            execute_on TEXT NOT NULL CHECK (length(execute_on) = 10),
            priority_resolution TEXT CHECK (priority_resolution IS NULL OR priority_resolution IN ({_quoted(PRIORITY_RESOLUTIONS)})),
            unhide_successor INTEGER NOT NULL CHECK (unhide_successor IN (0, 1)),
            approved_observation_fingerprint_sha256 TEXT NOT NULL CHECK (length(approved_observation_fingerprint_sha256) = 64 AND approved_observation_fingerprint_sha256 NOT GLOB '*[^0-9a-f]*'),
            approved_assessment_fingerprint_sha256 TEXT NOT NULL CHECK (length(approved_assessment_fingerprint_sha256) = 64 AND approved_assessment_fingerprint_sha256 NOT GLOB '*[^0-9a-f]*'),
            approved_preview_sha256 TEXT NOT NULL CHECK (length(approved_preview_sha256) = 64 AND approved_preview_sha256 NOT GLOB '*[^0-9a-f]*'),
            approved_preview_json TEXT NOT NULL CHECK (length(approved_preview_json) BETWEEN 2 AND 65536),
            before_snapshot_json TEXT CHECK (before_snapshot_json IS NULL OR length(before_snapshot_json) BETWEEN 2 AND 65536),
            after_snapshot_sha256 TEXT CHECK (after_snapshot_sha256 IS NULL OR (length(after_snapshot_sha256) = 64 AND after_snapshot_sha256 NOT GLOB '*[^0-9a-f]*')),
            approved_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            applied_at TEXT,
            cancelled_at TEXT,
            reversed_at TEXT,
            approval_authority TEXT NOT NULL CHECK (approval_authority IN ({_quoted(TRANSITION_APPROVAL_AUTHORITIES)})),
            automation_policy_version TEXT CHECK (automation_policy_version IS NULL OR (length(automation_policy_version) BETWEEN 1 AND 120 AND instr(automation_policy_version, char(0)) = 0)),
            rule_id TEXT CHECK (rule_id IS NULL OR (length(rule_id) BETWEEN 1 AND 160 AND instr(rule_id, char(0)) = 0)),
            rule_version TEXT CHECK (rule_version IS NULL OR (length(rule_version) BETWEEN 1 AND 120 AND instr(rule_version, char(0)) = 0)),
            decision_provenance_sha256 TEXT NOT NULL CHECK (length(decision_provenance_sha256) = 64 AND decision_provenance_sha256 NOT GLOB '*[^0-9a-f]*'),
            CHECK (
                (kind = 'symbol_continuation' AND successor_ticker IS NOT NULL AND successor_ticker <> source_ticker)
                OR (kind = 'terminal_delisting' AND successor_ticker IS NULL)
            ),
            CHECK (
                kind = 'symbol_continuation'
                OR (priority_resolution IS NULL AND unhide_successor = 0)
            ),
            CHECK (
                (status IN ('approved', 'needs_review')
                    AND before_snapshot_json IS NULL
                    AND after_snapshot_sha256 IS NULL
                    AND applied_at IS NULL
                    AND cancelled_at IS NULL
                    AND reversed_at IS NULL)
                OR (status = 'applied'
                    AND before_snapshot_json IS NOT NULL
                    AND after_snapshot_sha256 IS NOT NULL
                    AND applied_at IS NOT NULL
                    AND cancelled_at IS NULL
                    AND reversed_at IS NULL)
                OR (status = 'cancelled'
                    AND before_snapshot_json IS NULL
                    AND after_snapshot_sha256 IS NULL
                    AND applied_at IS NULL
                    AND cancelled_at IS NOT NULL
                    AND reversed_at IS NULL)
                OR (status = 'reversed'
                    AND before_snapshot_json IS NOT NULL
                    AND after_snapshot_sha256 IS NOT NULL
                    AND applied_at IS NOT NULL
                    AND cancelled_at IS NULL
                    AND reversed_at IS NOT NULL)
            ),
            CHECK (
                (approval_authority = 'attended_user' AND automation_policy_version IS NULL AND rule_id IS NULL AND rule_version IS NULL)
                OR (approval_authority = 'automation_policy' AND automation_policy_version IS NOT NULL AND rule_id IS NOT NULL AND rule_version IS NOT NULL)
            )
        )
    """,
    "ticker_identity_transition_activity": f"""
        CREATE TABLE ticker_identity_transition_activity (
            activity_id TEXT PRIMARY KEY CHECK (length(activity_id) BETWEEN 1 AND 120),
            transition_id TEXT NOT NULL REFERENCES ticker_identity_transitions(transition_id) ON DELETE CASCADE,
            activity_type TEXT NOT NULL CHECK (activity_type IN ({_quoted(TRANSITION_ACTIVITY_TYPES)})),
            source_ticker TEXT NOT NULL CHECK (length(source_ticker) BETWEEN 1 AND 20 AND instr(source_ticker, char(0)) = 0),
            successor_ticker TEXT CHECK (successor_ticker IS NULL OR (length(successor_ticker) BETWEEN 1 AND 20 AND instr(successor_ticker, char(0)) = 0)),
            effective_date TEXT NOT NULL CHECK (length(effective_date) = 10),
            user_owned_changes_json TEXT NOT NULL CHECK (length(user_owned_changes_json) BETWEEN 2 AND 32768),
            provider_owned_retained_json TEXT NOT NULL CHECK (length(provider_owned_retained_json) BETWEEN 2 AND 32768),
            state_sha256 TEXT NOT NULL CHECK (length(state_sha256) = 64 AND state_sha256 NOT GLOB '*[^0-9a-f]*'),
            rule_id TEXT CHECK (rule_id IS NULL OR (length(rule_id) BETWEEN 1 AND 160 AND instr(rule_id, char(0)) = 0)),
            rule_version TEXT CHECK (rule_version IS NULL OR (length(rule_version) BETWEEN 1 AND 120 AND instr(rule_version, char(0)) = 0)),
            decision_provenance_sha256 TEXT NOT NULL CHECK (length(decision_provenance_sha256) = 64 AND decision_provenance_sha256 NOT GLOB '*[^0-9a-f]*'),
            occurred_at TEXT NOT NULL,
            acknowledged_at TEXT,
            created_at TEXT NOT NULL,
            CHECK ((rule_id IS NULL AND rule_version IS NULL) OR (rule_id IS NOT NULL AND rule_version IS NOT NULL))
        )
    """,
}


IDENTITY_INDEX_SQL = {
    **V1_IDENTITY_INDEX_SQL,
    "idx_ticker_identity_activity_transition": """
        CREATE INDEX idx_ticker_identity_activity_transition
        ON ticker_identity_transition_activity(transition_id, occurred_at)
    """,
    "idx_ticker_identity_activity_unacknowledged": """
        CREATE INDEX idx_ticker_identity_activity_unacknowledged
        ON ticker_identity_transition_activity(acknowledged_at, occurred_at)
    """,
}


def create_ticker_identity_schema(conn: sqlite3.Connection) -> None:
    """Create the component in a caller-owned profile connection."""

    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        for statement in IDENTITY_TABLE_SQL.values():
            conn.execute(statement)
        for statement in IDENTITY_INDEX_SQL.values():
            conn.execute(statement)


def create_v1_ticker_identity_schema(conn: sqlite3.Connection) -> None:
    """Create the exact first-cutover component in a caller-owned connection."""

    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        for statement in V1_IDENTITY_TABLE_SQL.values():
            conn.execute(statement)
        for statement in V1_IDENTITY_INDEX_SQL.values():
            conn.execute(statement)


def identity_schema_present(conn: sqlite3.Connection) -> bool:
    """Return whether any ticker identity table exists without creating one."""

    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name LIKE 'ticker_identity_%' LIMIT 1"
    ).fetchone()
    return row is not None


def _normalize_sql(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    normalized = normalized.replace("create table if not exists", "create table")
    normalized = normalized.replace("create index if not exists", "create index")
    normalized = normalized.replace("create unique index if not exists", "create unique index")
    return normalized


def _verify_ticker_identity_connection(
    conn: sqlite3.Connection,
    tables: dict[str, str],
    indexes: dict[str, str],
) -> None:
    expected_tables = set(tables)
    actual_tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'ticker_identity_%'"
        )
    }
    if actual_tables != expected_tables:
        raise TickerIdentitySchemaMismatch("ticker identity table set mismatch")

    actual_indexes = {
        str(row[0]): str(row[1])
        for row in conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_ticker_identity_%' AND sql IS NOT NULL"
        )
    }
    if set(actual_indexes) != set(indexes):
        raise TickerIdentitySchemaMismatch("ticker identity index set mismatch")

    expected_objects = expected_tables | set(indexes)
    placeholders = ",".join("?" for _ in expected_tables)
    owned_object_names: dict[str, set[str]] = {}
    for catalog in ("sqlite_master", "sqlite_temp_master"):
        names: set[str] = set()
        for object_type, name, _table_name, sql in conn.execute(
            f"SELECT type,name,tbl_name,sql FROM {catalog} WHERE "
            "name LIKE 'ticker_identity_%' OR "
            "name LIKE 'idx_ticker_identity_%' OR "
            f"tbl_name IN ({placeholders})",
            tuple(sorted(expected_tables)),
        ):
            if (
                catalog == "sqlite_master"
                and str(object_type) == "index"
                and str(name).startswith("sqlite_autoindex_")
                and sql is None
            ):
                continue
            names.add(str(name))
        owned_object_names[catalog] = names
    if (
        owned_object_names["sqlite_master"] != expected_objects
        or owned_object_names["sqlite_temp_master"]
    ):
        raise TickerIdentitySchemaMismatch("ticker identity object set mismatch")

    for name, expected_sql in tables.items():
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        if row is None or _normalize_sql(row[0]) != _normalize_sql(expected_sql):
            raise TickerIdentitySchemaMismatch(f"ticker identity table mismatch: {name}")

    for name, expected_sql in indexes.items():
        if _normalize_sql(actual_indexes[name]) != _normalize_sql(expected_sql):
            raise TickerIdentitySchemaMismatch(f"ticker identity index mismatch: {name}")

    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise TickerIdentitySchemaMismatch("ticker identity foreign key mismatch")


def verify_ticker_identity_connection(conn: sqlite3.Connection) -> None:
    """Fail closed unless the caller-owned connection has the current component."""

    _verify_ticker_identity_connection(conn, IDENTITY_TABLE_SQL, IDENTITY_INDEX_SQL)


def verify_v1_ticker_identity_connection(conn: sqlite3.Connection) -> None:
    """Fail closed unless the connection has the exact first-cutover component."""

    _verify_ticker_identity_connection(
        conn,
        V1_IDENTITY_TABLE_SQL,
        V1_IDENTITY_INDEX_SQL,
    )


__all__ = [
    "ATTEMPT_STATUSES",
    "ATTEMPT_TRIGGERS",
    "PRIORITY_RESOLUTIONS",
    "TRANSITION_KINDS",
    "TRANSITION_APPROVAL_AUTHORITIES",
    "TRANSITION_ACTIVITY_TYPES",
    "TRANSITION_STATUSES",
    "TickerIdentitySchemaMismatch",
    "create_ticker_identity_schema",
    "create_v1_ticker_identity_schema",
    "identity_schema_present",
    "verify_ticker_identity_connection",
    "verify_v1_ticker_identity_connection",
]
