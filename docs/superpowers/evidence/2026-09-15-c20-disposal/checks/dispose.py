"""One-time C20 transaction, not an application migration or startup hook.

The user approved deleting exactly the two old query rows without an archive.
Only schema metadata, sequence metadata and row counts may be read.
"""

import json
from pathlib import Path
import re
import sqlite3
import stat
import sys


PROTECTED = ("research_reports", "agent_memories", "research_threads",
             "research_messages", "research_runs", "research_run_events")
EXPECTED_COLUMNS = (
    ("id", "INTEGER", 0, None, 1), ("question", "TEXT", 1, None, 0),
    ("answer", "TEXT", 0, None, 0), ("provider", "TEXT", 0, None, 0),
    ("model", "TEXT", 0, None, 0), ("tools_used", "TEXT", 0, None, 0),
    ("duration_ms", "INTEGER", 0, None, 0), ("tokens_in", "INTEGER", 0, None, 0),
    ("tokens_out", "INTEGER", 0, None, 0), ("created_at", "TEXT", 1, None, 0),
)


def require(condition, code):
    if not condition:
        raise ValueError(code)


def authorize(action, first, second, db, source):
    if source is not None:
        return sqlite3.SQLITE_DENY
    allowed = False
    if action == sqlite3.SQLITE_SELECT:
        allowed = True
    elif action == sqlite3.SQLITE_FUNCTION:
        allowed = second == "count"
    elif action == sqlite3.SQLITE_TRANSACTION:
        allowed = first in {"BEGIN", "COMMIT", "ROLLBACK"}
    elif action == sqlite3.SQLITE_PRAGMA:
        allowed = first in {"table_info", "foreign_key_list"} and second == "agent_queries"
    elif action == sqlite3.SQLITE_READ and db in {None, "main"}:
        allowed = (first in {"sqlite_master", "sqlite_schema"}
                   or first == "sqlite_sequence" and second in {"name", "seq"}
                   or first in {*PROTECTED, "agent_queries"} and second == "")
    elif db == "main":
        if action == sqlite3.SQLITE_DROP_TABLE:
            allowed = first == "agent_queries"
        elif action == sqlite3.SQLITE_DELETE:
            allowed = first in {"agent_queries", "sqlite_master", "sqlite_sequence"}
        elif action == sqlite3.SQLITE_UPDATE:
            allowed = first == "sqlite_master"
    return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY


def schema(conn):
    return conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name").fetchall()


def counts(conn):
    return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in PROTECTED}


def sequences(conn):
    return conn.execute("SELECT name,seq FROM sqlite_sequence WHERE name<>? ORDER BY name",
                        ("agent_queries",)).fetchall()


def dispose(conn):
    require(not conn.in_transaction, "c20_transaction_already_open")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.set_authorizer(authorize)
    try:
        conn.execute("BEGIN IMMEDIATE")
        before = schema(conn)
        require(sum(row[0:3] == ("table", "agent_queries", "agent_queries") for row in before) == 1,
                "c20_target_table_missing")
        columns = tuple(row[1:] for row in conn.execute("PRAGMA table_info(agent_queries)"))
        require(columns == EXPECTED_COLUMNS, "c20_schema_changed")
        require(not conn.execute("PRAGMA foreign_key_list(agent_queries)").fetchall(), "c20_schema_dependency")
        others = [row for row in before if row[1] != "agent_queries"]
        require(not any(row[2] == "agent_queries" or re.search(r"\bagent_queries\b", row[3] or "", re.I)
                        for row in others), "c20_schema_dependency")
        require(conn.execute("SELECT COUNT(*) FROM agent_queries").fetchone()[0] == 2, "c20_row_count_changed")
        preserved_counts, preserved_sequences = counts(conn), sequences(conn)
        conn.execute("DROP TABLE main.agent_queries")
        require(schema(conn) == others, "c20_unexpected_schema_change")
        require(counts(conn) == preserved_counts, "c20_unexpected_record_change")
        require(sequences(conn) == preserved_sequences, "c20_unexpected_sequence_change")
        conn.commit()
        return {"status": "removed", "table": "agent_queries", "removed_rows": 2,
                "other_schema_unchanged": True, "protected_counts_unchanged": True,
                "other_sequences_unchanged": True, "archive_created": False,
                "row_contents_read": False}
    except BaseException:
        conn.rollback()
        raise
    finally:
        # Reset explicitly; the current Python build does not accept None here.
        conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)


if __name__ == "__main__":
    require(len(sys.argv) == 3 and sys.argv[1] == "--apply", "explicit_apply_path_required")
    path = Path(sys.argv[2]).absolute()
    require(path == Path("/mnt/md0/PycharmProjects/ArkScope/data/profile_state.db"), "c20_profile_not_approved")
    require(path.resolve(strict=True) == path and not path.is_symlink(), "c20_path_unsafe")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "c20_path_unsafe")
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        require(not sidecar.is_symlink(), "c20_sidecar_unsafe")
    with sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=2) as conn:
        result = dispose(conn)
    conn.close()
    after = path.stat()
    require((info.st_dev, info.st_ino) == (after.st_dev, after.st_ino), "c20_identity_changed")
    print(json.dumps({**result, "sqlite_version": sqlite3.sqlite_version}, sort_keys=True))
