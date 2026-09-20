"""Backed-up, offline Spark cleanup; all other translations and the feature remain."""

import argparse
from contextlib import closing
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import stat
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from src.sqlite_backup import backup_connection


TARGET = "ai_card_translation_versions"
INDEX = "idx_card_translation_versions"
COLUMN = "translations_json"
MODEL = "gpt-5.3-codex-spark"
RUN_ID = 13
LANG = "zh-Hant"
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


def _inventory(conn):
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
        require(TARGET not in parents, "translation_disposal_foreign_key_dependency")
    for kind, name, table, sql in before:
        if name in {TARGET, "ai_card_runs", INDEX}:
            continue
        require(table != TARGET, "translation_disposal_unknown_owned_object")
        require(not (kind == "trigger" and table in {"ai_card_runs", TARGET}),
                "translation_disposal_trigger_dependency")
    index = next((row for row in before if row[1] == INDEX), None)
    if index:
        require(index[0] == "index" and index[2] == TARGET,
                "translation_disposal_index_owner_changed")
        require([row[2] for row in conn.execute(
            "SELECT * FROM pragma_index_info(?)", (INDEX,),
        )] == ["run_id", "lang", "id"], "translation_disposal_index_changed")
    return {
        "schema": before,
        "card_columns": [row[0] for row in card_columns],
        "cards": conn.execute("SELECT * FROM main.ai_card_runs ORDER BY id").fetchall(),
        "versions": conn.execute(f"SELECT * FROM main.{TARGET} ORDER BY id").fetchall()
                    if TARGET in tables else [],
        "protected_counts": {table: conn.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0]
                             for table in PROTECTED if table in tables},
        "sequences": conn.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name").fetchall()
                     if "sqlite_sequence" in tables else [],
        "settings": {table: conn.execute(f'SELECT * FROM main."{table}" ORDER BY task').fetchall()
                     for table in ("model_route", "fixed_task_runtime_config") if table in tables},
    }


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "translation_disposal_duplicate_json_key")
        value[key] = item
    return value


def _lossless_float(text):
    value = float(text)
    require(Decimal(text) == Decimal(str(value)), "translation_disposal_lossy_json_number")
    return value


def _load_object(raw):
    value = json.loads(raw, object_pairs_hook=_unique_object, parse_float=_lossless_float,
                       parse_constant=lambda _: require(False, "translation_disposal_nonfinite_json"))
    require(isinstance(value, dict), "translation_disposal_json_object_required")
    return value


def _content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _plan(before):
    expected = {**before, "versions": [row for row in before["versions"] if row[5] != MODEL]}
    if COLUMN not in before["card_columns"]:
        return expected, "not_present", None
    id_column = before["card_columns"].index("id")
    column = before["card_columns"].index(COLUMN)
    original = next((row for row in before["cards"] if row[id_column] == RUN_ID), None)
    if original is None or original[column] is None:
        return expected, "not_present", None
    cache = _load_object(original[column])
    if LANG not in cache:
        return expected, "not_present", None
    require(isinstance(cache[LANG], dict), "translation_disposal_json_object_required")
    target = _content_hash(cache[LANG])
    matches = [row for row in before["versions"] if row[1:3] == (RUN_ID, LANG)
               and _content_hash(_load_object(row[3])) == target]
    if not any(row[5] == MODEL for row in matches):
        return expected, "preserved_no_spark_match", None
    if any(row[5] != MODEL for row in matches):
        return expected, "preserved_ambiguous_provenance", None
    del cache[LANG]
    replacement = json.dumps(cache, ensure_ascii=False, allow_nan=False) if cache else None
    changed = tuple(replacement if index == column else value for index, value in enumerate(original))
    expected["cards"] = [changed if row[id_column] == RUN_ID else row for row in before["cards"]]
    return expected, "removed_matched_spark", replacement


def dispose(conn, *, backup_path):
    require(not conn.in_transaction, "translation_disposal_transaction_open")
    backup = Path(backup_path).absolute()
    require(backup.resolve() == backup, "translation_disposal_backup_path_unsafe")
    for _, _, source in conn.execute("PRAGMA database_list"):
        if source:
            require(backup not in {Path(source + suffix).resolve() for suffix in ("", "-wal", "-shm", "-journal")},
                    "translation_disposal_backup_path_unsafe")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        # Pin the WAL-inclusive read snapshot for backup, then refuse any intervening writer.
        conn.execute("BEGIN")
        data_version = conn.execute("PRAGMA data_version").fetchone()
        before = _inventory(conn)
        expected, embedded_status, replacement = _plan(before)
        backup_connection(conn, backup)
        with closing(sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True)) as saved:
            saved.execute("PRAGMA query_only=ON")
            saved.execute("BEGIN")
            require(_inventory(saved) == before, "translation_disposal_backup_changed")
        checksum = hashlib.sha256()
        with backup.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                checksum.update(block)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        require(conn.execute("PRAGMA data_version").fetchone() == data_version,
                "translation_disposal_source_changed")
        require(_inventory(conn) == before, "translation_disposal_source_changed")
        removed = {"versions": 0, "embedded_cards": 0}
        if any(row[0] == "table" and row[1] == TARGET for row in before["schema"]):
            removed["versions"] = conn.execute(
                f"DELETE FROM main.{TARGET} WHERE model = ?", (MODEL,),
            ).rowcount
        if embedded_status == "removed_matched_spark":
            removed["embedded_cards"] = conn.execute(
                "UPDATE main.ai_card_runs SET translations_json=? WHERE id=?", (replacement, RUN_ID),
            ).rowcount
        require(_inventory(conn) == expected, "translation_disposal_preservation_failed")
        conn.commit()
        return {"removed": removed, "embedded_status": embedded_status,
                "protected_counts": before["protected_counts"],
                "integrity_check": "ok", "foreign_key_check": "ok",
                "schema_and_all_settings_unchanged": True, "backup_created": True,
                "backup_path": str(backup), "backup_sha256": checksum.hexdigest()}
    except BaseException:
        conn.rollback()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clear-spark-translations", action="store_true", required=True)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    parser.add_argument("--backup-path", type=Path, required=True)
    args = parser.parse_args()
    path = Path("/mnt/md0/PycharmProjects/ArkScope/data/profile_state.db")
    require(path.resolve(strict=True) == path and not path.is_symlink(), "profile_path_unsafe")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "profile_path_unsafe")
    for suffix in ("-wal", "-shm"):
        require(not Path(str(path) + suffix).is_symlink(), "profile_sidecar_unsafe")
    conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=2)
    try:
        result = dispose(conn, backup_path=args.backup_path)
    finally:
        conn.close()
    require((path.stat().st_dev, path.stat().st_ino) == (info.st_dev, info.st_ino),
            "profile_identity_changed")
    print(json.dumps({**result, "sqlite_version": sqlite3.sqlite_version}, sort_keys=True))
