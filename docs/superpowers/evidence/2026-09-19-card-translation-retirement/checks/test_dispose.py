"""Standalone synthetic disposal checks; no App, network or production access."""

import importlib.util
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest import mock


spec = importlib.util.spec_from_file_location("translation_disposal", Path(__file__).with_name("dispose.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SPARK = "gpt-5.3-codex-spark"
SPARK_CARD = {"translation": "Spark fixture", "confidence": 0.5}
SUPPORTED_CARD = {"translation": "Supported fixture"}
UNKNOWN_CARD = {"translation": "Unknown provenance"}


class DisposalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.backup_number = 0
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.executescript("""
            CREATE TABLE ai_card_runs (id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_card_json TEXT NOT NULL, translations_json TEXT, model TEXT);
            CREATE TABLE ai_card_execution_receipts (run_id INTEGER PRIMARY KEY REFERENCES ai_card_runs(id), model TEXT);
            CREATE TABLE research_threads (id INTEGER PRIMARY KEY, title TEXT);
            CREATE TABLE ai_card_translation_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES ai_card_runs(id),
                lang TEXT NOT NULL, card_json TEXT NOT NULL,
                provider TEXT, model TEXT, effort TEXT, auth_mode TEXT, created_at TEXT);
            CREATE INDEX idx_card_translation_versions ON ai_card_translation_versions(run_id,lang,id);
            CREATE TABLE model_route (task TEXT PRIMARY KEY, provider TEXT NOT NULL,
                model TEXT NOT NULL, effort TEXT NOT NULL DEFAULT 'default', updated_at TEXT NOT NULL);
            CREATE TABLE fixed_task_runtime_config (task TEXT PRIMARY KEY,
                model_timeout_s REAL NOT NULL, updated_at TEXT NOT NULL);
            INSERT INTO ai_card_runs VALUES (1,'{"original":true}',NULL,'original-model');
            INSERT INTO ai_card_runs VALUES (2,'{"another":true}',NULL,'historical-spark');
            INSERT INTO ai_card_runs VALUES (13,'{"target":true}',NULL,'original-model');
            INSERT INTO ai_card_execution_receipts VALUES (1,'original-model');
            INSERT INTO research_threads VALUES (1,'original research');
            INSERT INTO model_route VALUES ('card_translation','openai','old','medium','fixture'),
                ('card_synthesis','anthropic','keep','high','fixture');
            INSERT INTO fixed_task_runtime_config VALUES ('card_translation',500,'fixture'),
                ('card_synthesis',900,'fixture');
        """)
        self.conn.execute("UPDATE ai_card_runs SET translations_json=? WHERE id=1",
                          (json.dumps({"zh-Hant": SPARK_CARD}),))
        self.conn.execute("UPDATE ai_card_runs SET translations_json=? WHERE id=13",
                          (json.dumps({"zh-Hant": SPARK_CARD, "zh-Hans": SUPPORTED_CARD,
                                       "de": UNKNOWN_CARD}),))
        self.conn.executemany(
            "INSERT INTO ai_card_translation_versions(run_id,lang,card_json,model) VALUES (?,?,?,?)",
            [(13, "zh-Hant", json.dumps(SPARK_CARD), SPARK),
             (13, "zh-Hans", json.dumps(SUPPORTED_CARD), "supported-model"),
             (13, "de", json.dumps(UNKNOWN_CARD), None),
             (1, "zh-Hant", json.dumps(SPARK_CARD), SPARK)],
        )
        self.conn.commit()

    def dispose(self):
        self.backup_number += 1
        return module.dispose(self.conn, backup_path=self.directory / f"backup-{self.backup_number}.db")

    def embedded(self, run_id=13):
        raw = self.conn.execute("SELECT translations_json FROM ai_card_runs WHERE id=?", (run_id,)).fetchone()[0]
        return json.loads(raw) if raw is not None else None

    def snapshot(self):
        return "\n".join(self.conn.iterdump())

    def test_only_spark_versions_and_matched_run_13_language_are_removed(self):
        schema = module.schema(self.conn)
        other_cards = self.conn.execute("SELECT * FROM ai_card_runs WHERE id!=13 ORDER BY id").fetchall()
        kept_versions = self.conn.execute("SELECT * FROM ai_card_translation_versions WHERE id IN (2,3) ORDER BY id").fetchall()
        result = self.dispose()
        self.assertEqual(result["removed"], {"versions": 2, "embedded_cards": 1})
        self.assertEqual(module.schema(self.conn), schema)
        self.assertEqual(self.conn.execute("SELECT * FROM ai_card_runs WHERE id!=13 ORDER BY id").fetchall(), other_cards)
        self.assertEqual(self.embedded(), {"zh-Hans": SUPPORTED_CARD, "de": UNKNOWN_CARD})
        self.assertEqual(self.conn.execute("SELECT result_card_json,model FROM ai_card_runs WHERE id=13").fetchone(),
                         ('{"target":true}', 'original-model'))
        self.assertEqual(self.conn.execute("SELECT * FROM ai_card_execution_receipts").fetchall(), [(1,'original-model')])
        self.assertEqual(self.conn.execute("SELECT * FROM research_threads").fetchall(), [(1,'original research')])
        self.assertEqual(self.conn.execute("SELECT * FROM model_route ORDER BY task").fetchall(),
                         [('card_synthesis','anthropic','keep','high','fixture'),
                          ('card_translation','openai','old','medium','fixture')])
        self.assertEqual(self.conn.execute("SELECT * FROM fixed_task_runtime_config ORDER BY task").fetchall(),
                         [('card_synthesis',900,'fixture'), ('card_translation',500,'fixture')])
        self.assertEqual(self.conn.execute("SELECT * FROM ai_card_translation_versions ORDER BY id").fetchall(), kept_versions)
        after = self.snapshot()
        self.assertEqual(self.dispose()["removed"], {"versions": 0, "embedded_cards": 0})
        self.assertEqual(self.snapshot(), after)

    def test_legacy_without_version_provenance_is_preserved(self):
        self.conn.execute("DROP TABLE ai_card_translation_versions")
        before = self.snapshot()
        self.assertEqual(self.dispose()["removed"]["embedded_cards"], 0)
        self.assertEqual(self.snapshot(), before)

    def test_current_non_spark_and_unknown_cache_values_are_preserved(self):
        for card in (SUPPORTED_CARD, UNKNOWN_CARD):
            with self.subTest(card=card):
                raw = json.dumps({"zh-Hant": card})
                self.conn.execute("UPDATE ai_card_runs SET translations_json=? WHERE id=13", (raw,))
                self.conn.commit()
                self.assertEqual(self.dispose()["removed"]["embedded_cards"], 0)
                self.assertEqual(self.conn.execute("SELECT translations_json FROM ai_card_runs WHERE id=13").fetchone(), (raw,))

    def test_matching_content_on_other_run_or_language_is_not_authority(self):
        for sql in (
            "UPDATE ai_card_translation_versions SET run_id=1 WHERE id=1",
            "UPDATE ai_card_translation_versions SET lang='en' WHERE id=1",
        ):
            with self.subTest(sql=sql):
                self.conn.execute(sql)
                self.conn.commit()
                self.assertEqual(self.dispose()["removed"]["embedded_cards"], 0)
                self.assertEqual(self.embedded()["zh-Hant"], SPARK_CARD)
                self.conn.execute("INSERT INTO ai_card_translation_versions(id,run_id,lang,card_json,model) "
                                  "VALUES (1,13,'zh-Hant',?,?)", (json.dumps(SPARK_CARD), SPARK))
                self.conn.commit()

    def test_ambiguous_same_content_with_non_spark_provenance_is_preserved(self):
        self.conn.execute("INSERT INTO ai_card_translation_versions(run_id,lang,card_json,model) "
                          "VALUES (13,'zh-Hant',?,'supported-model')", (json.dumps(SPARK_CARD),))
        self.conn.commit()
        self.assertEqual(self.dispose()["removed"]["embedded_cards"], 0)
        self.assertEqual(self.embedded()["zh-Hant"], SPARK_CARD)
        self.assertEqual(self.conn.execute("SELECT model FROM ai_card_translation_versions WHERE lang='zh-Hant'").fetchall(),
                         [('supported-model',)])

    def test_match_is_canonical_not_whitespace_or_key_order(self):
        self.conn.execute("UPDATE ai_card_runs SET translations_json=? WHERE id=13",
                          ('{ "zh-Hant": { "confidence": 0.5, "translation": "Spark fixture" } }',))
        self.conn.commit()
        self.assertEqual(self.dispose()["removed"]["embedded_cards"], 1)
        self.assertIsNone(self.embedded())

    def test_model_match_is_exact_and_does_not_delete_unknown_provenance(self):
        models = ("GPT-5.3-Codex-Spark", SPARK + "-fixture", "supported-model", None)
        self.conn.executemany("INSERT INTO ai_card_translation_versions(run_id,lang,card_json,model) "
                              "VALUES (2,'en','{}',?)", [(model,) for model in models])
        self.conn.commit()
        self.dispose()
        self.assertEqual(self.conn.execute("SELECT model FROM ai_card_translation_versions WHERE run_id=2 ORDER BY id").fetchall(),
                         [(model,) for model in models])

    def test_malformed_duplicate_or_lossy_json_refuses_cleanup(self):
        for raw in ('{', '{"zh-Hant":{},"zh-Hant":{}}', '{"zh-Hant":{"n":NaN}}',
                    '{"zh-Hant":{"n":1.0000000000000001}}'):
            with self.subTest(raw=raw):
                self.conn.execute("UPDATE ai_card_runs SET translations_json=? WHERE id=13", (raw,))
                self.conn.commit()
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    self.dispose()
                self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_private_backup_contains_all_original_data_before_cleanup(self):
        before = self.snapshot()
        result = self.dispose()
        self.assertTrue(result["backup_created"])
        backup = Path(result["backup_path"])
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        conn = sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True)
        try:
            self.assertEqual("\n".join(conn.iterdump()), before)
        finally:
            conn.close()

    def test_backup_is_mandatory(self):
        before = self.snapshot()
        with self.assertRaises(TypeError):
            module.dispose(self.conn)
        self.assertEqual(self.snapshot(), before)

    def test_failed_backup_never_deletes_any_record(self):
        before = self.snapshot()
        with mock.patch.object(module, "backup_connection", side_effect=OSError("fixture disk full")):
            with self.assertRaises(OSError):
                self.dispose()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.conn.in_transaction)

    def test_existing_backup_cannot_be_overwritten(self):
        backup = self.directory / "backup.db"
        other = sqlite3.connect(backup)
        other.execute("CREATE TABLE keep(id INTEGER)")
        other.close()
        original = backup.read_bytes()
        before = self.snapshot()
        with self.assertRaises(FileExistsError):
            module.dispose(self.conn, backup_path=backup)
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(self.snapshot(), before)

    def test_incorrect_backup_blocks_cleanup(self):
        real_backup = module.backup_connection

        def incomplete(conn, path):
            real_backup(conn, path)
            other = sqlite3.connect(path)
            try:
                other.execute("DELETE FROM ai_card_translation_versions")
                other.commit()
            finally:
                other.close()

        before = self.snapshot()
        with mock.patch.object(module, "backup_connection", side_effect=incomplete):
            with self.assertRaisesRegex(ValueError, "backup_changed"):
                self.dispose()
        self.assertEqual(self.snapshot(), before)

    def test_wal_backup_and_concurrent_write_detection(self):
        path = self.directory / "profile.db"
        conn = sqlite3.connect(path)
        self.addCleanup(conn.close)
        self.conn.backup(conn)
        self.conn.close()
        self.conn = conn
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("UPDATE research_threads SET title='committed in WAL'")
        self.conn.commit()
        real_backup = module.backup_connection

        def racing(source, backup):
            real_backup(source, backup)
            other = sqlite3.connect(path)
            try:
                other.execute("UPDATE research_threads SET title='another writer'")
                other.commit()
            finally:
                other.close()

        with mock.patch.object(module, "backup_connection", side_effect=racing):
            with self.assertRaisesRegex(ValueError, "source_changed"):
                self.dispose()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ai_card_translation_versions").fetchone(), (4,))
        self.assertEqual(self.embedded()["zh-Hant"], SPARK_CARD)
        backup = sqlite3.connect(self.directory / "backup-1.db")
        try:
            self.assertEqual(backup.execute("SELECT title FROM research_threads").fetchone(), ('committed in WAL',))
        finally:
            backup.close()

    def test_original_write_trigger_is_refused(self):
        self.conn.executescript("""
            CREATE TRIGGER unexpected AFTER UPDATE ON ai_card_runs BEGIN DELETE FROM research_threads; END;
        """)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "trigger_dependency"):
            self.dispose()
        self.assertEqual(self.snapshot(), before)

    def test_unknown_owned_index_is_refused(self):
        self.conn.execute("CREATE INDEX unknown ON ai_card_translation_versions(card_json)")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "unknown_owned_object"):
            self.dispose()
        self.assertEqual(self.snapshot(), before)

    def test_external_reference_is_refused(self):
        self.conn.execute("CREATE TABLE other(id REFERENCES ai_card_translation_versions(id) ON DELETE CASCADE)")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "foreign_key_dependency"):
            self.dispose()
        self.assertEqual(self.snapshot(), before)

    def test_settings_and_their_dependents_are_untouched(self):
        self.conn.executescript("""
            CREATE TABLE other(task TEXT REFERENCES model_route(task) ON DELETE CASCADE, content TEXT);
            INSERT INTO other VALUES ('card_translation','must not cascade');
        """)
        self.dispose()
        self.assertEqual(self.conn.execute("SELECT * FROM other").fetchall(),
                         [('card_translation','must not cascade')])

    def test_translation_view_survives_record_cleanup(self):
        self.conn.execute("CREATE VIEW old_translation AS SELECT translations_json FROM ai_card_runs")
        self.dispose()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM old_translation").fetchone(), (3,))
        self.assertEqual(self.embedded(), {"zh-Hans": SUPPORTED_CARD, "de": UNKNOWN_CARD})

    def test_changed_target_schema_is_refused(self):
        self.conn.execute("ALTER TABLE ai_card_translation_versions ADD COLUMN unexpected TEXT")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "version_schema_changed"):
            self.dispose()
        self.assertEqual(self.snapshot(), before)

    def test_unrelated_settings_shape_is_untouched(self):
        self.conn.execute("ALTER TABLE model_route ADD COLUMN unreviewed TEXT")
        before = self.conn.execute("SELECT * FROM model_route ORDER BY task").fetchall()
        self.dispose()
        self.assertEqual(self.conn.execute("SELECT * FROM model_route ORDER BY task").fetchall(), before)

    def test_new_translation_can_be_saved_without_schema_recreation(self):
        self.dispose()
        self.conn.execute("INSERT INTO ai_card_translation_versions(run_id,lang,card_json,model) "
                          "VALUES (1,'zh-Hant','{}','supported-model')")
        self.assertEqual(self.conn.execute("SELECT id,model FROM ai_card_translation_versions ORDER BY id").fetchall(),
                         [(2,'supported-model'), (3, None), (5,'supported-model')])

    def test_only_two_translation_data_statements_execute(self):
        statements = []
        self.conn.set_trace_callback(statements.append)
        before = self.conn.total_changes
        self.dispose()
        self.assertEqual(self.conn.total_changes - before, 3)
        writes = [sql for sql in statements if sql.lstrip().upper().startswith(
            ('DELETE', 'UPDATE', 'INSERT', 'REPLACE', 'DROP', 'ALTER', 'CREATE'))]
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0], "DELETE FROM main.ai_card_translation_versions WHERE model = 'gpt-5.3-codex-spark'")
        self.assertTrue(writes[1].startswith('UPDATE main.ai_card_runs SET translations_json='))
        self.assertTrue(writes[1].endswith(' WHERE id=13'))

    def test_failed_commit_rolls_back_every_target(self):
        before = self.snapshot()
        changed = False

        def authorize(action, first, *rest):
            nonlocal changed
            if action == sqlite3.SQLITE_DELETE and first == "ai_card_translation_versions":
                changed = True
            if changed and action == sqlite3.SQLITE_TRANSACTION and first == "COMMIT":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.conn.set_authorizer(authorize)
        with self.assertRaises(sqlite3.DatabaseError):
            self.dispose()
        self.conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
