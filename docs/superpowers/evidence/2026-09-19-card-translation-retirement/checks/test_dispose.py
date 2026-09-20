"""Standalone synthetic disposal checks; no App, network or production access."""

import importlib.util
from pathlib import Path
import sqlite3
import unittest


spec = importlib.util.spec_from_file_location("translation_disposal", Path(__file__).with_name("dispose.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisposalTests(unittest.TestCase):
    def setUp(self):
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
            INSERT INTO ai_card_runs VALUES (1,'{"original":true}','{"retired":true}','original-model');
            INSERT INTO ai_card_runs VALUES (2,'{"another":true}',NULL,'historical-spark');
            INSERT INTO ai_card_execution_receipts VALUES (1,'original-model');
            INSERT INTO research_threads VALUES (1,'original research');
            INSERT INTO ai_card_translation_versions(run_id,lang,card_json) VALUES (1,'zh-Hant','{}');
            INSERT INTO model_route VALUES ('card_translation','openai','old','medium','fixture'),
                ('card_synthesis','anthropic','keep','high','fixture');
            INSERT INTO fixed_task_runtime_config VALUES ('card_translation',500,'fixture'),
                ('card_synthesis',900,'fixture');
        """)

    def snapshot(self):
        return "\n".join(self.conn.iterdump())

    def test_only_translation_records_are_removed_and_repeat_is_noop(self):
        schema = module.schema(self.conn)
        result = module.dispose(self.conn)
        self.assertEqual(result["removed"], {"versions": 1, "embedded_cards": 1})
        self.assertEqual(module.schema(self.conn), schema)
        self.assertEqual(self.conn.execute("SELECT * FROM ai_card_runs ORDER BY id").fetchall(), [
            (1,'{"original":true}',None,'original-model'), (2,'{"another":true}',None,'historical-spark')])
        self.assertEqual(self.conn.execute("SELECT * FROM ai_card_execution_receipts").fetchall(), [(1,'original-model')])
        self.assertEqual(self.conn.execute("SELECT * FROM research_threads").fetchall(), [(1,'original research')])
        self.assertEqual(self.conn.execute("SELECT * FROM model_route ORDER BY task").fetchall(),
                         [('card_synthesis','anthropic','keep','high','fixture'),
                          ('card_translation','openai','old','medium','fixture')])
        self.assertEqual(self.conn.execute("SELECT * FROM fixed_task_runtime_config ORDER BY task").fetchall(),
                         [('card_synthesis',900,'fixture'), ('card_translation',500,'fixture')])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ai_card_translation_versions").fetchone(), (0,))
        after = self.snapshot()
        self.assertEqual(module.dispose(self.conn)["removed"]["versions"], 0)
        self.assertEqual(self.snapshot(), after)

    def test_legacy_embedded_only(self):
        self.conn.execute("DROP TABLE ai_card_translation_versions")
        self.assertEqual(module.dispose(self.conn)["removed"]["embedded_cards"], 1)

    def test_original_write_trigger_is_refused(self):
        self.conn.executescript("""
            CREATE TRIGGER unexpected AFTER UPDATE ON ai_card_runs BEGIN DELETE FROM research_threads; END;
        """)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "trigger_dependency"):
            module.dispose(self.conn)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_owned_index_is_refused(self):
        self.conn.execute("CREATE INDEX unknown ON ai_card_translation_versions(card_json)")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "unknown_owned_object"):
            module.dispose(self.conn)
        self.assertEqual(self.snapshot(), before)

    def test_external_reference_is_refused(self):
        self.conn.execute("CREATE TABLE other(id REFERENCES ai_card_translation_versions(id) ON DELETE CASCADE)")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "foreign_key_dependency"):
            module.dispose(self.conn)
        self.assertEqual(self.snapshot(), before)

    def test_settings_and_their_dependents_are_untouched(self):
        self.conn.executescript("""
            CREATE TABLE other(task TEXT REFERENCES model_route(task) ON DELETE CASCADE, content TEXT);
            INSERT INTO other VALUES ('card_translation','must not cascade');
        """)
        module.dispose(self.conn)
        self.assertEqual(self.conn.execute("SELECT * FROM other").fetchall(),
                         [('card_translation','must not cascade')])

    def test_translation_view_survives_record_cleanup(self):
        self.conn.execute("CREATE VIEW old_translation AS SELECT translations_json FROM ai_card_runs")
        module.dispose(self.conn)
        self.assertEqual(self.conn.execute("SELECT * FROM old_translation").fetchall(), [(None,), (None,)])

    def test_changed_target_schema_is_refused(self):
        self.conn.execute("ALTER TABLE ai_card_translation_versions ADD COLUMN unexpected TEXT")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "version_schema_changed"):
            module.dispose(self.conn)
        self.assertEqual(self.snapshot(), before)

    def test_unrelated_settings_shape_is_untouched(self):
        self.conn.execute("ALTER TABLE model_route ADD COLUMN unreviewed TEXT")
        before = self.conn.execute("SELECT * FROM model_route ORDER BY task").fetchall()
        module.dispose(self.conn)
        self.assertEqual(self.conn.execute("SELECT * FROM model_route ORDER BY task").fetchall(), before)

    def test_new_translation_can_be_saved_without_schema_recreation(self):
        module.dispose(self.conn)
        self.conn.execute("INSERT INTO ai_card_translation_versions(run_id,lang,card_json,model) "
                          "VALUES (1,'zh-Hant','{}','supported-model')")
        self.assertEqual(self.conn.execute("SELECT id,model FROM ai_card_translation_versions").fetchall(),
                         [(2,'supported-model')])

    def test_only_two_translation_data_statements_execute(self):
        statements = []
        self.conn.set_trace_callback(statements.append)
        before = self.conn.total_changes
        module.dispose(self.conn)
        self.assertEqual(self.conn.total_changes - before, 2)
        self.assertEqual([sql for sql in statements if sql.lstrip().upper().startswith(
            ('DELETE', 'UPDATE', 'INSERT', 'REPLACE', 'DROP', 'ALTER', 'CREATE'))], [
                'DELETE FROM main.ai_card_translation_versions',
                'UPDATE main.ai_card_runs SET translations_json=NULL WHERE translations_json IS NOT NULL',
            ])

    def test_failed_commit_rolls_back_every_target(self):
        before = self.snapshot()
        self.conn.set_authorizer(lambda action, first, *rest:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and first == "COMMIT" else sqlite3.SQLITE_OK)
        with self.assertRaises(sqlite3.DatabaseError):
            module.dispose(self.conn)
        self.conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
