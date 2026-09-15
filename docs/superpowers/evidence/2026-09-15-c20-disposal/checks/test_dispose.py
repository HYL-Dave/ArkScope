"""Disposable-only tests for the one-time, explicitly approved C20 operation."""

import importlib.util
from pathlib import Path
import sqlite3
import unittest


spec = importlib.util.spec_from_file_location("c20_dispose", Path(__file__).with_name("dispose.py"))
operation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operation)

OLD_SCHEMA = """CREATE TABLE agent_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer TEXT,
    provider TEXT, model TEXT, tools_used TEXT, duration_ms INTEGER,
    tokens_in INTEGER, tokens_out INTEGER, created_at TEXT NOT NULL
)"""


def fixture():
    conn = sqlite3.connect(":memory:")
    conn.execute(OLD_SCHEMA)
    conn.executemany("INSERT INTO agent_queries(question,answer,created_at) VALUES (?,?,?)",
                     [("fixture question", "fixture answer", "2026-01-01")] * 2)
    for table in operation.PROTECTED:
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT)")
        conn.execute(f"INSERT INTO {table}(content) VALUES ('preserved fixture')")
    conn.commit()
    return conn


class DisposalTests(unittest.TestCase):
    def test_only_target_removed(self):
        with fixture() as conn:
            result = operation.dispose(conn)
            self.assertEqual(result["removed_rows"], 2)
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_schema WHERE name='agent_queries'").fetchone())
            for table in operation.PROTECTED:
                self.assertEqual(conn.execute(f"SELECT content FROM {table}").fetchall(), [("preserved fixture",)])
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_changed_count_refused(self):
        with fixture() as conn:
            conn.execute("DELETE FROM agent_queries WHERE id=2")
            conn.commit()
            with self.assertRaisesRegex(ValueError, "c20_row_count_changed"):
                operation.dispose(conn)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_queries").fetchone()[0], 1)

    def test_changed_shape_refused(self):
        with fixture() as conn:
            conn.execute("ALTER TABLE agent_queries ADD COLUMN extra TEXT")
            with self.assertRaisesRegex(ValueError, "c20_schema_changed"):
                operation.dispose(conn)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_queries").fetchone()[0], 2)

    def test_dependencies_refused(self):
        for sql in (
            "CREATE VIEW query_view AS SELECT id FROM agent_queries",
            "CREATE TABLE dependent (ref INTEGER REFERENCES agent_queries(id))",
            "CREATE INDEX query_index ON agent_queries(model)",
        ):
            with self.subTest(sql=sql), fixture() as conn:
                conn.execute(sql)
                with self.assertRaisesRegex(ValueError, "c20_schema_dependency"):
                    operation.dispose(conn)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_queries").fetchone()[0], 2)

    def test_unexpected_write_and_content_read_denied(self):
        with fixture() as conn:
            conn.set_authorizer(operation.authorize)
            for sql in ("SELECT question FROM agent_queries", "SELECT answer FROM agent_queries",
                        "SELECT content FROM research_messages", "DELETE FROM research_messages",
                        "DROP TABLE research_messages", "INSERT INTO agent_queries(question) VALUES ('x')"):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(sql)
            conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)

    def test_failure_after_drop_rolls_back(self):
        with fixture() as conn:
            normal = operation.authorize
            dropped = False

            def deny_commit(action, first, second, db, source):
                nonlocal dropped
                if action == sqlite3.SQLITE_DROP_TABLE:
                    dropped = True
                if action == sqlite3.SQLITE_TRANSACTION and first == "COMMIT":
                    return sqlite3.SQLITE_DENY
                return normal(action, first, second, db, source)

            operation.authorize = deny_commit
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    operation.dispose(conn)
            finally:
                operation.authorize = normal
            self.assertTrue(dropped)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_queries").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
