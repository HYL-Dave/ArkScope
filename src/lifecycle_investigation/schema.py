"""Current investigation journal; initialization never rewrites populated stores."""

import hashlib

from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_schema import _normalize_sql, assert_lifecycle_writes_available, verify_profile_connection


TABLES = {
    "lifecycle_investigation_installation": """CREATE TABLE lifecycle_investigation_installation (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL CHECK(version=2),
        schema_sha256 TEXT NOT NULL, installed_at TEXT NOT NULL)""",
    "lifecycle_investigation_jobs": """CREATE TABLE lifecycle_investigation_jobs (
        run_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE,
        header_json TEXT NOT NULL, header_sha256 TEXT NOT NULL CHECK(length(header_sha256)=64),
        owner TEXT NOT NULL, created_at TEXT NOT NULL, lease_until TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('running','succeeded','incomplete','failed','cancelled','remote_outcome_unknown')),
        phase TEXT NOT NULL, cancel_requested_at TEXT, finished_at TEXT, failure_code TEXT,
        CHECK((status='running' AND finished_at IS NULL) OR (status<>'running' AND finished_at IS NOT NULL)))""",
    "lifecycle_investigation_calls": """CREATE TABLE lifecycle_investigation_calls (
        run_id TEXT NOT NULL REFERENCES lifecycle_investigation_jobs(run_id),
        call_id TEXT NOT NULL, remote_id TEXT, terminal TEXT CHECK(terminal IS NULL OR terminal IN ('completed','failed','cancelled','interrupted')),
        PRIMARY KEY(run_id,call_id), UNIQUE(run_id,remote_id), CHECK(terminal IS NULL OR remote_id IS NOT NULL))""",
    "lifecycle_investigation_steps": """CREATE TABLE lifecycle_investigation_steps (
        run_id TEXT NOT NULL REFERENCES lifecycle_investigation_jobs(run_id), ordinal INTEGER NOT NULL CHECK(ordinal>0),
        kind TEXT NOT NULL, payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(run_id,ordinal))""",
    "lifecycle_investigation_sources": """CREATE TABLE lifecycle_investigation_sources (
        run_id TEXT NOT NULL REFERENCES lifecycle_investigation_jobs(run_id), source_id TEXT NOT NULL,
        payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, PRIMARY KEY(run_id,source_id))""",
    "lifecycle_investigation_results": """CREATE TABLE lifecycle_investigation_results (
        run_id TEXT PRIMARY KEY REFERENCES lifecycle_investigation_jobs(run_id),
        payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, completed_at TEXT NOT NULL)""",
    "lifecycle_investigation_acceptances": """CREATE TABLE lifecycle_investigation_acceptances (
        assessment_id TEXT PRIMARY KEY REFERENCES security_lifecycle_assessments(assessment_id),
        run_id TEXT NOT NULL UNIQUE REFERENCES lifecycle_investigation_results(run_id),
        packet_json TEXT NOT NULL, packet_sha256 TEXT NOT NULL, actor TEXT NOT NULL CHECK(actor='attended_user'),
        confirmed_at TEXT NOT NULL)""",
}
INDEXES = {"idx_lifecycle_investigation_running": """CREATE UNIQUE INDEX idx_lifecycle_investigation_running
    ON lifecycle_investigation_jobs(ticker) WHERE status='running'"""}
TRIGGERS = {
    f"{table}_{op.lower()}_immutable": f"""CREATE TRIGGER {table}_{op.lower()}_immutable BEFORE {op} ON {table}
    BEGIN SELECT RAISE(ABORT,'investigation_immutable'); END"""
    for table in TABLES if table not in {"lifecycle_investigation_jobs", "lifecycle_investigation_calls"}
    for op in ("UPDATE", "DELETE")
}
TRIGGERS["lifecycle_investigation_jobs_identity_immutable"] = """CREATE TRIGGER lifecycle_investigation_jobs_identity_immutable
    BEFORE UPDATE OF run_id,ticker,request_key,header_json,header_sha256,owner,created_at ON lifecycle_investigation_jobs
    BEGIN SELECT RAISE(ABORT,'investigation_immutable'); END"""
TRIGGERS["lifecycle_investigation_jobs_terminal_immutable"] = """CREATE TRIGGER lifecycle_investigation_jobs_terminal_immutable
    BEFORE UPDATE ON lifecycle_investigation_jobs WHEN OLD.status<>'running'
    BEGIN SELECT RAISE(ABORT,'investigation_immutable'); END"""
TRIGGERS["lifecycle_investigation_calls_terminal_immutable"] = """CREATE TRIGGER lifecycle_investigation_calls_terminal_immutable
    BEFORE UPDATE ON lifecycle_investigation_calls
    WHEN OLD.run_id<>NEW.run_id OR OLD.call_id<>NEW.call_id
      OR (OLD.remote_id IS NOT NULL AND (NEW.remote_id IS NULL OR OLD.remote_id<>NEW.remote_id))
      OR (OLD.terminal IS NOT NULL AND (NEW.terminal IS NULL OR OLD.terminal<>NEW.terminal))
    BEGIN SELECT RAISE(ABORT,'investigation_immutable'); END"""
for table in ("lifecycle_investigation_jobs", "lifecycle_investigation_calls"):
    TRIGGERS[f"{table}_delete_immutable"] = f"""CREATE TRIGGER {table}_delete_immutable BEFORE DELETE ON {table}
        BEGIN SELECT RAISE(ABORT,'investigation_immutable'); END"""


def schema_digest():
    return hashlib.sha256("\n".join(f"{key}:{_normalize_sql(sql)}" for key, sql in sorted({**TABLES, **INDEXES, **TRIGGERS}.items())).encode()).hexdigest()


def installed(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name='lifecycle_investigation_installation'").fetchone() is not None


def verify_journal(conn):
    if not installed(conn):
        raise ValueError("investigation_not_installed")
    for expected in (TABLES, INDEXES, TRIGGERS):
        for name, sql in expected.items():
            row = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
            if row is None or _normalize_sql(row[0]) != _normalize_sql(sql):
                raise ValueError("investigation_schema_mismatch")
    row = conn.execute("SELECT version,schema_sha256 FROM lifecycle_investigation_installation WHERE singleton=1").fetchone()
    if row is None or tuple(row) != (2, schema_digest()):
        raise ValueError("investigation_schema_mismatch")


def install_journal(conn, *, at):
    instant(at)
    if conn.in_transaction:
        raise ValueError("investigation_install_transaction_open")
    conn.execute("PRAGMA foreign_keys=ON")
    verify_profile_connection(conn)
    assert_lifecycle_writes_available(conn)
    if installed(conn):
        verify_journal(conn)
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        _install_on_connection(conn, at=at)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _install_on_connection(conn, *, at):
    if not conn.in_transaction:
        raise ValueError("investigation_install_transaction_required")
    for sql in (*TABLES.values(), *INDEXES.values(), *TRIGGERS.values()):
        conn.execute(sql)
    conn.execute("INSERT INTO lifecycle_investigation_installation VALUES(1,2,?,?)", (schema_digest(), at))
    from src.lifecycle_investigation.runtime import install_runtime
    install_runtime(conn)
    verify_journal(conn)
    if conn.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("investigation_install_foreign_key")
