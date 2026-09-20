"""Explicit, offline translation-record cleanup; the feature and schema remain."""

import json
from pathlib import Path
import sqlite3
import stat
import sys


TARGET = "ai_card_translation_versions"
INDEX = "idx_card_translation_versions"
COLUMN = "translations_json"
PROTECTED = (
    "ai_card_runs", "ai_card_execution_receipts", "research_reports",
    "agent_memories", "research_threads", "research_messages", "research_runs",
    "research_run_events",
)
VERSION_COLUMNS = (
    ("id", "INTEGER", 0, None, 1, 0),
    ("run_id", "INTEGER", 1, None, 0, 0),
    ("lang", "TEXT", 1, None, 0, 0),
    ("card_json", "TEXT", 1, None, 0, 0),
    *((name, "TEXT", 0, None, 0, 0)
      for name in ("provider", "model", "effort", "auth_mode", "created_at")),
)


def require(condition, code):
    if not condition:
        raise ValueError(code)


def schema(conn):
    return conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
    ).fetchall()


def columns(conn, table):
    return tuple(tuple(row[1:]) for row in conn.execute(
        "SELECT * FROM pragma_table_xinfo(?)", (table,),
    ))


def dispose(conn):
    require(not conn.in_transaction, "translation_disposal_transaction_open")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        require(conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)],
                "translation_disposal_integrity_failed")
        require(not conn.execute("PRAGMA foreign_key_check").fetchall(),
                "translation_disposal_foreign_keys_failed")
        before = schema(conn)
        tables = {row[1] for row in before if row[0] == "table"}
        require("ai_card_runs" in tables, "translation_disposal_cards_missing")
        card_columns = columns(conn, "ai_card_runs")
        embedded = next((row for row in card_columns if row[0] == COLUMN), None)
        if embedded:
            require(embedded == (COLUMN, "TEXT", 0, None, 0, 0),
                    "translation_disposal_column_changed")
        if TARGET in tables:
            require(columns(conn, TARGET) == VERSION_COLUMNS,
                    "translation_disposal_version_schema_changed")
        for table in tables:
            parents = {row[0].casefold() for row in conn.execute(
                'SELECT "table" FROM pragma_foreign_key_list(?)', (table,),
            )}
            require(TARGET not in parents,
                    "translation_disposal_foreign_key_dependency")
        for kind, name, table, sql in before:
            if name == TARGET or name == "ai_card_runs" or name == INDEX:
                continue
            require(table != TARGET, "translation_disposal_unknown_owned_object")
            require(not (kind == "trigger" and table in {
                "ai_card_runs", TARGET,
            }), "translation_disposal_trigger_dependency")
        index = next((row for row in before if row[1] == INDEX), None)
        if index:
            require(index[0] == "index" and index[2] == TARGET,
                    "translation_disposal_index_owner_changed")
            require([row[2] for row in conn.execute(
                "SELECT * FROM pragma_index_info(?)", (INDEX,),
            )] == ["run_id", "lang", "id"], "translation_disposal_index_changed")

        counts = lambda: {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                          for table in PROTECTED if table in tables}
        protected = counts()
        original_columns = ",".join('"' + row[0].replace('"', '""') + '"'
                                    for row in card_columns if row[0] != COLUMN)
        originals = lambda: conn.execute(
            f"SELECT {original_columns} FROM ai_card_runs ORDER BY id"
        ).fetchall()
        preserved_originals = originals()
        sequences = lambda: conn.execute(
            "SELECT name,seq FROM sqlite_sequence ORDER BY name",
        ).fetchall() if "sqlite_sequence" in tables else []
        preserved_sequences = sequences()
        settings = {}
        for table in ("model_route", "fixed_task_runtime_config"):
            if table in tables:
                settings[table] = conn.execute(
                    f'SELECT * FROM "{table}" ORDER BY task',
                ).fetchall()
        removed = {"versions": 0, "embedded_cards": 0}
        if TARGET in tables:
            removed["versions"] = conn.execute(f"DELETE FROM main.{TARGET}").rowcount
        if embedded:
            removed["embedded_cards"] = conn.execute(
                "UPDATE main.ai_card_runs SET translations_json=NULL "
                "WHERE translations_json IS NOT NULL"
            ).rowcount
        for table, rows in settings.items():
            require(conn.execute(f'SELECT * FROM "{table}" ORDER BY task').fetchall() == rows,
                    "translation_disposal_settings_changed")
        require(schema(conn) == before, "translation_disposal_schema_changed")
        require(originals() == preserved_originals, "translation_disposal_originals_changed")
        require(counts() == protected, "translation_disposal_protected_counts_changed")
        require(sequences() == preserved_sequences, "translation_disposal_other_sequences_changed")
        require(conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)],
                "translation_disposal_integrity_failed")
        require(not conn.execute("PRAGMA foreign_key_check").fetchall(),
                "translation_disposal_foreign_keys_failed")
        conn.commit()
        return {"removed": removed, "protected_counts": protected,
                "integrity_check": "ok", "foreign_key_check": "ok",
                "schema_and_all_settings_unchanged": True, "archive_created": False}
    except BaseException:
        conn.rollback()
        raise


if __name__ == "__main__":
    require(sys.argv[1:] == ["--clear-all-translations", "--writers-stopped"],
            "explicit_stopped_writer_record_cleanup_required")
    path = Path("/mnt/md0/PycharmProjects/ArkScope/data/profile_state.db")
    require(path.resolve(strict=True) == path and not path.is_symlink(), "profile_path_unsafe")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "profile_path_unsafe")
    for suffix in ("-wal", "-shm"):
        require(not Path(str(path) + suffix).is_symlink(), "profile_sidecar_unsafe")
    conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=2)
    try:
        result = dispose(conn)
    finally:
        conn.close()
    require((path.stat().st_dev, path.stat().st_ino) == (info.st_dev, info.st_ino),
            "profile_identity_changed")
    print(json.dumps({**result, "sqlite_version": sqlite3.sqlite_version}, sort_keys=True))
