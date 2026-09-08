"""Explicit installation of the independent, model-authored Web journal."""

import hashlib
import sqlite3

from src.security_lifecycle_schema import _normalize_sql, assert_lifecycle_writes_available, verify_profile_connection


class WebJournalError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


RUNNING = ("queued", "searching", "reading_sources", "analyzing")
TERMINAL = ("succeeded", "failed", "cancelled", "remote_outcome_unknown")

INVENTORY_FIELDS = {
    "runs": ("run_id", "case_id", "header_sha256", "created_at", "lease_until", "status", "cancel_requested_at", "finished_at", "failure_code"),
    "calls": ("run_id", "call_id", "terminal"),
    "actions": ("run_id", "call_id", "item_id", "kind"),
    "pages": ("run_id", "source_id", "page_sha256"),
    "results": ("run_id", "result_sha256", "completed_at"),
    "acceptances": ("assessment_id", "run_id", "packet_sha256", "actor", "confirmed_at"),
}


TABLES = {
    "lifecycle_web_installation": """CREATE TABLE lifecycle_web_installation (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL CHECK(version=1),
        schema_sha256 TEXT NOT NULL, installed_at TEXT NOT NULL)""",
    "lifecycle_web_runs": """CREATE TABLE lifecycle_web_runs (
        run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES security_lifecycle_cases(case_id),
        request_key TEXT NOT NULL UNIQUE, header_json TEXT NOT NULL, header_sha256 TEXT NOT NULL CHECK(length(header_sha256)=64),
        owner TEXT NOT NULL, created_at TEXT NOT NULL, lease_until TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('queued','searching','reading_sources','analyzing','succeeded','failed','cancelled','remote_outcome_unknown')),
        cancel_requested_at TEXT, finished_at TEXT, failure_code TEXT,
        CHECK((status IN ('queued','searching','reading_sources','analyzing') AND finished_at IS NULL AND failure_code IS NULL)
           OR (status='succeeded' AND finished_at IS NOT NULL AND failure_code IS NULL)
           OR (status IN ('failed','cancelled','remote_outcome_unknown') AND finished_at IS NOT NULL AND failure_code IS NOT NULL)))""",
    "lifecycle_web_calls": """CREATE TABLE lifecycle_web_calls (
        run_id TEXT NOT NULL REFERENCES lifecycle_web_runs(run_id), call_id TEXT NOT NULL CHECK(call_id IN ('search-1','analysis-1')),
        remote_id TEXT, terminal TEXT CHECK(terminal IS NULL OR terminal IN ('completed','failed','cancelled','interrupted')),
        PRIMARY KEY(run_id,call_id), UNIQUE(run_id,remote_id), CHECK(terminal IS NULL OR remote_id IS NOT NULL))""",
    "lifecycle_web_actions": """CREATE TABLE lifecycle_web_actions (
        run_id TEXT NOT NULL, call_id TEXT NOT NULL, item_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('search','open_page','find_in_page')), PRIMARY KEY(run_id,call_id,item_id),
        FOREIGN KEY(run_id,call_id) REFERENCES lifecycle_web_calls(run_id,call_id))""",
    "lifecycle_web_pages": """CREATE TABLE lifecycle_web_pages (
        run_id TEXT NOT NULL REFERENCES lifecycle_web_runs(run_id), source_id TEXT NOT NULL,
        page_json TEXT NOT NULL, page_sha256 TEXT NOT NULL CHECK(length(page_sha256)=64), PRIMARY KEY(run_id,source_id))""",
    "lifecycle_web_results": """CREATE TABLE lifecycle_web_results (
        run_id TEXT PRIMARY KEY REFERENCES lifecycle_web_runs(run_id), payload_json TEXT NOT NULL,
        result_sha256 TEXT NOT NULL CHECK(length(result_sha256)=64), completed_at TEXT NOT NULL)""",
    "lifecycle_web_acceptances": """CREATE TABLE lifecycle_web_acceptances (
        assessment_id TEXT PRIMARY KEY REFERENCES security_lifecycle_assessments(assessment_id),
        run_id TEXT NOT NULL UNIQUE REFERENCES lifecycle_web_results(run_id),
        packet_json TEXT NOT NULL, packet_sha256 TEXT NOT NULL CHECK(length(packet_sha256)=64),
        actor TEXT NOT NULL CHECK(actor='attended_user'), confirmed_at TEXT NOT NULL)""",
}
INDEXES = {"idx_lifecycle_web_active_case": """CREATE UNIQUE INDEX idx_lifecycle_web_active_case
    ON lifecycle_web_runs(case_id) WHERE status IN ('queued','searching','reading_sources','analyzing')"""}
TRIGGERS = {
    f"{name}_{operation.lower()}_immutable": f"""CREATE TRIGGER {name}_{operation.lower()}_immutable BEFORE {operation} ON {name}
    BEGIN SELECT RAISE(ABORT,'web_immutable_record'); END"""
    for name in ("lifecycle_web_installation", "lifecycle_web_pages", "lifecycle_web_results", "lifecycle_web_acceptances", "lifecycle_web_actions")
    for operation in ("UPDATE", "DELETE")
}
TRIGGERS["lifecycle_web_runs_identity_immutable"] = """CREATE TRIGGER lifecycle_web_runs_identity_immutable
    BEFORE UPDATE OF run_id,case_id,request_key,header_json,header_sha256,owner,created_at ON lifecycle_web_runs
    BEGIN SELECT RAISE(ABORT,'web_immutable_record'); END"""
TRIGGERS["lifecycle_web_runs_delete_immutable"] = """CREATE TRIGGER lifecycle_web_runs_delete_immutable BEFORE DELETE ON lifecycle_web_runs
    BEGIN SELECT RAISE(ABORT,'web_immutable_record'); END"""
TRIGGERS["lifecycle_web_calls_terminal_immutable"] = """CREATE TRIGGER lifecycle_web_calls_terminal_immutable BEFORE UPDATE ON lifecycle_web_calls
    WHEN OLD.run_id<>NEW.run_id OR OLD.call_id<>NEW.call_id
      OR (OLD.remote_id IS NOT NULL AND (NEW.remote_id IS NULL OR OLD.remote_id<>NEW.remote_id))
      OR (OLD.terminal IS NOT NULL AND (NEW.terminal IS NULL OR OLD.terminal<>NEW.terminal))
    BEGIN SELECT RAISE(ABORT,'web_immutable_record'); END"""
TRIGGERS["lifecycle_web_calls_delete_immutable"] = """CREATE TRIGGER lifecycle_web_calls_delete_immutable BEFORE DELETE ON lifecycle_web_calls
    BEGIN SELECT RAISE(ABORT,'web_immutable_record'); END"""


def schema_digest():
    return hashlib.sha256("\n".join(f"{name}:{_normalize_sql(sql)}" for name, sql in sorted({**TABLES, **INDEXES, **TRIGGERS}.items())).encode()).hexdigest()


def verify_web_journal(conn):
    for kind, expected, pattern in (("table", TABLES, "lifecycle_web_%"), ("index", INDEXES, "idx_lifecycle_web_%"),
                                     ("trigger", TRIGGERS, "lifecycle_web_%")):
        actual = dict(conn.execute("SELECT name,sql FROM sqlite_master WHERE type=? AND name LIKE ? AND sql IS NOT NULL", (kind, pattern)))
        if kind == "table" and not actual:
            raise WebJournalError("web_journal_not_installed")
        if {name: _normalize_sql(sql) for name, sql in actual.items()} != {name: _normalize_sql(sql) for name, sql in expected.items()}:
            raise WebJournalError("web_journal_schema_mismatch")
    row = conn.execute("SELECT version,schema_sha256 FROM lifecycle_web_installation WHERE singleton=1").fetchone()
    if row is None or tuple(row) != (1, schema_digest()):
        raise WebJournalError("web_journal_schema_mismatch")


def read_web_inventory(conn):
    """Internal retention metadata; no full pages, model prose or credentials."""
    installed = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE 'lifecycle_web_%'").fetchone())
    result = {"installed": installed, **{key: [] for key in INVENTORY_FIELDS}}
    if installed:
        verify_web_journal(conn)
        for key, fields in INVENTORY_FIELDS.items():
            result[key] = [dict(zip(fields, row)) for row in conn.execute(
                f"SELECT {','.join(fields)} FROM lifecycle_web_{key} ORDER BY rowid")]
    return result


def install_web_journal(conn, *, at):
    from src.security_lifecycle_provider_snapshot import instant
    instant(at)
    if conn.in_transaction:
        raise WebJournalError("web_installation_transaction_open")
    conn.execute("PRAGMA foreign_keys=ON")
    verify_profile_connection(conn)
    assert_lifecycle_writes_available(conn)
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE 'lifecycle_web_%'").fetchone():
        verify_web_journal(conn)
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        _install_on_connection(conn, at=at)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _install_on_connection(conn, *, at):
    from src.security_lifecycle_provider_snapshot import instant
    instant(at)
    if not conn.in_transaction:
        raise WebJournalError("web_installation_transaction_required")
    verify_profile_connection(conn)
    assert_lifecycle_writes_available(conn)
    for statement in (*TABLES.values(), *INDEXES.values(), *TRIGGERS.values()):
        conn.execute(statement)
    conn.execute("INSERT INTO lifecycle_web_installation VALUES (1,1,?,?)", (schema_digest(), at))
    verify_web_journal(conn)
    verify_profile_connection(conn)
