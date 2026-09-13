"""One canonical SEC research schema, installed only by an explicit command."""

from __future__ import annotations

import sqlite3


_TABLES = {
    "sec_research_schedule_batches": """checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('running','succeeded','partial','failed')),
        acquired_at TEXT, payload TEXT NOT NULL CHECK(length(CAST(payload AS BLOB))<=16777216)""",
    "sec_research_objects": "sha256 TEXT PRIMARY KEY, object_key TEXT UNIQUE NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes>=0)",
    "sec_research_reservations": "reservation_id TEXT PRIMARY KEY, size_bytes INTEGER NOT NULL CHECK(size_bytes>=0)",
    "sec_research_orphans": "object_key TEXT PRIMARY KEY, size_bytes INTEGER NOT NULL CHECK(size_bytes>=0)",
    "sec_research_issuer_maps": """observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL CHECK(status IN ('ok','unavailable')),
        object_sha256 TEXT REFERENCES sec_research_objects(sha256),
        observed_at TEXT NOT NULL, source_url TEXT NOT NULL,
        symbols TEXT NOT NULL, gaps TEXT NOT NULL,
        CHECK(status!='ok' OR object_sha256 IS NOT NULL)""",
    "sec_research_snapshots": """snapshot_id TEXT PRIMARY KEY NOT NULL,
        cik TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('catalog','facts')),
        object_sha256 TEXT NOT NULL REFERENCES sec_research_objects(sha256),
        observed_at TEXT NOT NULL, source_url TEXT NOT NULL,
        historical_name TEXT, historical_files_observed INTEGER NOT NULL CHECK(historical_files_observed IN (0,1)),
        historical_files TEXT NOT NULL, row_count INTEGER NOT NULL CHECK(row_count>=0)""",
    "sec_research_filings": """snapshot_id TEXT NOT NULL REFERENCES sec_research_snapshots(snapshot_id),
        ordinal INTEGER NOT NULL, filing_id TEXT NOT NULL, cik TEXT NOT NULL,
        accession TEXT NOT NULL, form TEXT NOT NULL, filed_date TEXT NOT NULL,
        report_date TEXT, accepted_at TEXT, primary_document TEXT, primary_url TEXT,
        source_sha256 TEXT NOT NULL REFERENCES sec_research_objects(sha256),
        source_pointer TEXT NOT NULL, PRIMARY KEY(snapshot_id, ordinal)""",
    "sec_research_facts": """snapshot_id TEXT NOT NULL REFERENCES sec_research_snapshots(snapshot_id),
        ordinal INTEGER NOT NULL, fact_id TEXT NOT NULL, cik TEXT NOT NULL,
        namespace TEXT NOT NULL, concept TEXT NOT NULL, value TEXT NOT NULL,
        unit TEXT NOT NULL, start TEXT, end TEXT NOT NULL, fiscal_year INTEGER,
        fiscal_period TEXT, form TEXT NOT NULL, accession TEXT NOT NULL,
        filed_date TEXT NOT NULL, frame TEXT,
        source_sha256 TEXT NOT NULL REFERENCES sec_research_objects(sha256),
        source_pointer TEXT NOT NULL, PRIMARY KEY(snapshot_id, ordinal)""",
    "sec_research_receipts": """receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scope TEXT NOT NULL DEFAULT 'full' CHECK(scope IN ('full','recent')),
        cik TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('ok','partial','unavailable')),
        completed TEXT NOT NULL, pending TEXT NOT NULL, gaps TEXT NOT NULL,
        observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
        source_snapshots TEXT NOT NULL DEFAULT '{}'""",
    "sec_research_document_directories": """directory_id TEXT PRIMARY KEY NOT NULL,
        filing_id TEXT NOT NULL, receipt_id INTEGER NOT NULL REFERENCES sec_research_receipts(receipt_id),
        object_sha256 TEXT NOT NULL REFERENCES sec_research_objects(sha256),
        observed_at TEXT NOT NULL, metadata TEXT NOT NULL""",
    "sec_research_documents": """capture_id TEXT PRIMARY KEY NOT NULL,
        directory_id TEXT NOT NULL REFERENCES sec_research_document_directories(directory_id),
        filing_id TEXT NOT NULL, document_id TEXT NOT NULL, primary_document TEXT,
        original_sha256 TEXT NOT NULL REFERENCES sec_research_objects(sha256),
        text_sha256 TEXT NOT NULL REFERENCES sec_research_objects(sha256),
        observed_at TEXT NOT NULL, metadata TEXT NOT NULL""",
    "sec_research_document_sources": """capture_id TEXT NOT NULL REFERENCES sec_research_documents(capture_id),
        snapshot_id TEXT NOT NULL REFERENCES sec_research_snapshots(snapshot_id),
        provenance TEXT NOT NULL, PRIMARY KEY(capture_id, snapshot_id)""",
    "sec_research_document_attempts": """attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        filing_id TEXT NOT NULL, document_id TEXT NOT NULL, resolved_document_id TEXT,
        primary_document TEXT,
        capture_id TEXT REFERENCES sec_research_documents(capture_id),
        status TEXT NOT NULL CHECK(status IN ('ok','partial','unavailable')),
        observed_at TEXT NOT NULL, details TEXT NOT NULL""",
}

_DDL = {name: ("table", name, f"CREATE TABLE {name}({columns})")
        for name, columns in _TABLES.items()}
for _table, _columns in (
    ("snapshots", "cik, kind"), ("filings", "cik, accession"),
    ("facts", "cik, fact_id"), ("receipts", "cik, receipt_id DESC"),
    ("document_attempts", "filing_id, attempt_id DESC"),
):
    _name = f"sec_research_{_table}_lookup"
    _owner = f"sec_research_{_table}"
    _DDL[_name] = ("index", _owner, f"CREATE INDEX {_name} ON {_owner}({_columns})")

for _table in ("objects", "issuer_maps", "snapshots", "filings", "facts", "receipts",
               "document_directories", "documents", "document_sources", "document_attempts", "schedule_batches"):
    for _operation in ("UPDATE", "DELETE"):
        _name = f"sec_research_{_table}_no_{_operation.lower()}"
        _owner = f"sec_research_{_table}"
        _DDL[_name] = ("trigger", _owner,
                       f"CREATE TRIGGER {_name} BEFORE {_operation} ON {_owner} "
                       "BEGIN SELECT RAISE(ABORT, 'sec_research_immutable'); END")

# REPLACE's implicit deletion does not fire DELETE triggers by default.
for _table, _conflict in (
    ("schedule_batches", "checkpoint_id=NEW.checkpoint_id"),
    ("objects", "sha256=NEW.sha256 OR object_key=NEW.object_key"),
    ("issuer_maps", "observation_id=NEW.observation_id"),
    ("snapshots", "snapshot_id=NEW.snapshot_id"),
    ("filings", "(snapshot_id=NEW.snapshot_id AND ordinal=NEW.ordinal)"),
    ("facts", "(snapshot_id=NEW.snapshot_id AND ordinal=NEW.ordinal)"),
    ("receipts", "receipt_id=NEW.receipt_id"),
    ("document_directories", "directory_id=NEW.directory_id"),
    ("documents", "capture_id=NEW.capture_id"),
    ("document_sources", "(capture_id=NEW.capture_id AND snapshot_id=NEW.snapshot_id)"),
    ("document_attempts", "attempt_id=NEW.attempt_id"),
):
    _name = f"sec_research_{_table}_no_replace"
    _owner = f"sec_research_{_table}"
    _DDL[_name] = ("trigger", _owner,
                   f"CREATE TRIGGER {_name} BEFORE INSERT ON {_owner} "
                   f"WHEN EXISTS(SELECT 1 FROM {_owner} WHERE {_conflict} OR rowid=NEW.rowid) "
                   "BEGIN SELECT RAISE(ABORT, 'sec_research_immutable'); END")


def _owned(conn: sqlite3.Connection) -> dict:
    # Inspect definitions, not just columns: CHECKs, references and triggers matter.
    return {name: (kind, owner, sql) for kind, name, owner, sql in conn.execute(
        "SELECT type, name, tbl_name, sql FROM main.sqlite_master"
    ) if sql is not None and (
        name.lower().startswith("sec_research_")
        or owner.lower().startswith("sec_research_")
    )}


def verify(conn: sqlite3.Connection) -> None:
    """Validate exact owned definitions without creating or repairing anything."""
    if _owned(conn) != _DDL:
        raise ValueError("sec_research_schema_mismatch")


def install(conn: sqlite3.Connection) -> None:
    """Atomically create a fresh schema or verify a complete canonical schema.

    The caller owns market_write_lock. Partial existing schemas are mismatches,
    not an invitation to repair an unknown installation.
    """
    if conn.in_transaction:
        raise ValueError("sec_research_transaction_active")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if _owned(conn):
            verify(conn)
        else:
            for _, _, ddl in _DDL.values():
                conn.execute(ddl)
            verify(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
