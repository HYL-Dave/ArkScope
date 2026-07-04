from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace


def test_evidence_report_fingerprint_is_order_stable():
    from scripts.migration import n9_batch2_cleanup as cli

    first = cli.build_evidence_report(
        pg_snapshot={
            "server_version": "17.8",
            "objects": [
                {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
                {"kind": "table", "name": "job_runs", "status": "present", "row_count": 2},
            ],
            "functions": [
                {"name": "news_search_vector_update()", "status": "present"},
            ],
            "row_fingerprints": {"job_runs": "abc"},
            "dependencies": [],
        },
        grep_summary={"allowed_hits": [{"path": "docs/x", "match": "job_runs"}], "blockers": []},
        local_default_proof={"market": True, "macro": True, "job_runs": True},
    )
    second = cli.build_evidence_report(
        pg_snapshot={
            "objects": [
                {"kind": "table", "name": "job_runs", "status": "present", "row_count": 2},
                {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
            ],
            "server_version": "17.8",
            "row_fingerprints": {"job_runs": "abc"},
            "dependencies": [],
            "functions": [
                {"status": "present", "name": "news_search_vector_update()"},
            ],
        },
        grep_summary={"blockers": [], "allowed_hits": [{"match": "job_runs", "path": "docs/x"}]},
        local_default_proof={"job_runs": True, "macro": True, "market": True},
    )

    assert first == second
    assert len(first["fingerprint"]) == 64


def test_classify_targets_marks_job_runs_function_and_excluded_tables():
    from scripts.migration import n9_batch2_cleanup as cli

    snapshot = cli.classify_catalog_objects(
        {
            "job_runs": "public.job_runs",
            "prices": "public.prices",
            "agent_queries": "public.agent_queries",
            "research_reports": "public.research_reports",
            "agent_memories": "public.agent_memories",
        },
        {"news_search_vector_update()": True},
    )

    objects = {item["name"]: item for item in snapshot["objects"]}
    functions = {item["name"]: item for item in snapshot["functions"]}
    assert objects["job_runs"]["status"] == "present"
    assert functions["news_search_vector_update()"]["status"] == "present"
    assert objects["prices"]["status"] == "excluded_present"
    assert objects["agent_queries"]["status"] == "excluded_present"


def test_grep_classifier_blocks_runtime_pg_job_runs_reader():
    from scripts.migration import n9_batch2_cleanup as cli

    summary = cli.classify_grep_hits([
        ("src/runtime/foo.py", "SELECT * FROM job_runs"),
        ("src/service/job_runs_store.py", "SELECT * FROM job_runs"),
        ("src/service/job_runs_cutover.py", "\"FROM job_runs ORDER BY id\""),
        ("src/tools/backends/db_backend.py", "def query_news_scores(self): return []"),
        ("scripts/migration/n9_batch2_cleanup.py", "FROM job_runs"),
        ("docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md", "job_runs"),
    ])

    assert summary["blockers"] == [
        {
            "path": "src/runtime/foo.py",
            "reason": "runtime_reference_to_batch2_target",
            "match": "SELECT * FROM job_runs",
        }
    ]
    reasons = {hit["path"]: hit["reason"] for hit in summary["allowed_hits"]}
    assert reasons["src/service/job_runs_store.py"] == "local_sqlite_authority"
    assert reasons["src/service/job_runs_cutover.py"] == "migration_cutover_dead_path_pending_batch2_cleanup"
    assert reasons["src/tools/backends/db_backend.py"] == "retired_pg_backend_stub"
    assert reasons["scripts/migration/n9_batch2_cleanup.py"] == "n9_batch2_orchestrator"
    assert reasons["docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md"] == "docs_or_tests"


def test_pg_dump_command_targets_only_job_runs(tmp_path):
    from scripts.migration import n9_batch2_cleanup as cli

    cmd = cli.build_pg_dump_command(
        database_url="postgres://secret@example/db",
        output=tmp_path / "n9_batch2.dump",
        present_tables=["job_runs", "prices"],
    )

    assert "pg_dump" in cmd[0]
    assert "--format=custom" in cmd
    assert "--table=public.job_runs" in cmd
    assert "--table=public.prices" not in cmd
    assert "postgres://secret@example/db" not in cmd


def test_dump_command_writes_archive_manifest(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch2_cleanup as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "server_version": "17.8",
            "objects": [{"kind": "table", "name": "job_runs", "status": "present", "row_count": 0}],
            "functions": [{"name": "news_search_vector_update()", "status": "present"}],
            "row_fingerprints": {"job_runs": "d41d8cd98f00b204e9800998ecf8427e"},
        },
    }
    report = tmp_path / "evidence.json"
    report.write_text(cli._canonical_json(evidence), encoding="utf-8")
    archive_dir = tmp_path / "archive"

    def fake_run(cmd, **kwargs):
        if cmd == ["pg_dump", "--version"]:
            return SimpleNamespace(returncode=0, stdout="pg_dump (PostgreSQL) 17.8\n", stderr="")
        if cmd[0] == "pg_dump":
            output = next(part.split("=", 1)[1] for part in cmd if part.startswith("--file="))
            Path(output).write_bytes(b"dump")
        return SimpleNamespace(returncode=0, stdout="toc\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "connect_pg", lambda _url: _FakeConn())
    monkeypatch.setattr(cli, "read_function_ddl", lambda _conn: "-- function ddl\n")

    code = cli.main([
        "dump",
        "--database-url", "postgres://secret@example/db",
        "--expected-report", str(report),
        "--archive-dir", str(archive_dir),
    ])

    stdout = capsys.readouterr().out
    assert code == 0
    assert "secret" not in stdout
    assert (archive_dir / "n9_batch2.dump").exists()
    assert (archive_dir / "evidence.json").exists()
    assert (archive_dir / "manifest.json").exists()
    assert (archive_dir / "function_ddl.sql").read_text(encoding="utf-8") == "-- function ddl\n"


def test_restore_proof_compares_counts_and_fingerprints():
    from scripts.migration import n9_batch2_cleanup as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [{"kind": "table", "name": "job_runs", "status": "present", "row_count": 1}],
            "row_fingerprints": {"job_runs": "old"},
        },
    }
    restored = {
        "objects": [{"kind": "table", "name": "job_runs", "status": "present", "row_count": 2}],
        "row_fingerprints": {"job_runs": "new"},
    }

    result = cli.compare_restore_to_evidence(restored, evidence)

    assert result["ok"] is False
    assert result["mismatches"] == [
        {"table": "job_runs", "field": "row_count", "expected": 1, "actual": 2},
        {"table": "job_runs", "field": "row_fingerprint", "expected": "old", "actual": "new"},
    ]


def test_drop_refuses_without_required_gate_inputs(tmp_path):
    from scripts.migration import n9_batch2_cleanup as cli

    args = cli.parse_args(["drop", "--database-url", "postgres://x"])
    assert cli.validate_drop_args(args).reason == "missing_reviewed_fingerprint"

    args = cli.parse_args([
        "drop",
        "--database-url", "postgres://x",
        "--reviewed-fingerprint", "abc",
        "--archive-dir", str(tmp_path),
        "--confirm-scheduler-paused",
        "--confirm-native-host-paused",
        "--confirm-destructive-drop",
    ])
    assert cli.validate_drop_args(args).reason == "missing_restore_proof"


def test_drop_sql_is_explicit_and_never_cascade():
    from scripts.migration import n9_batch2_cleanup as cli

    sql = cli.build_drop_sql(
        present_tables=["job_runs"],
        present_functions=["news_search_vector_update()"],
    )

    joined = "\n".join(sql)
    assert "CASCADE" not in joined.upper()
    assert "DROP FUNCTION IF EXISTS public.news_search_vector_update()" in joined
    assert "DROP TABLE IF EXISTS public.job_runs" in joined


def test_drop_uses_fresh_write_connection_after_read_only_evidence(tmp_path, monkeypatch):
    from scripts.migration import n9_batch2_cleanup as cli

    current_snapshot = {
        "server_version": "17.8",
        "objects": [
            {"kind": "table", "name": "job_runs", "status": "present", "row_count": 2},
            {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
            {"kind": "excluded_table", "name": "agent_queries", "status": "excluded_present"},
            {"kind": "excluded_table", "name": "research_reports", "status": "excluded_present"},
            {"kind": "excluded_table", "name": "agent_memories", "status": "excluded_present"},
        ],
        "functions": [{"kind": "function", "name": "news_search_vector_update()", "status": "present"}],
        "row_counts": {"job_runs": 2},
        "row_fingerprints": {"job_runs": "abc"},
        "dependencies": [],
    }
    post_drop_snapshot = {
        **current_snapshot,
        "objects": [
            {"kind": "table", "name": "job_runs", "status": "missing_unexpected"},
            {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
            {"kind": "excluded_table", "name": "agent_queries", "status": "excluded_present"},
            {"kind": "excluded_table", "name": "research_reports", "status": "excluded_present"},
            {"kind": "excluded_table", "name": "agent_memories", "status": "excluded_present"},
        ],
        "functions": [{"kind": "function", "name": "news_search_vector_update()", "status": "missing_unexpected"}],
    }
    grep_summary = {"blockers": [], "allowed_hits": []}
    local_default_proof = {"market_unset_routes_local": True}
    evidence = cli.build_evidence_report(
        pg_snapshot=current_snapshot,
        grep_summary=grep_summary,
        local_default_proof=local_default_proof,
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    dump_path = archive / "n9_batch2.dump"
    dump_path.write_bytes(b"dump")
    (archive / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    (archive / "restore_proof.json").write_text(
        cli._canonical_json({"ok": True, "evidence_fingerprint": evidence["fingerprint"]}),
        encoding="utf-8",
    )
    (archive / "manifest.json").write_text(
        cli._canonical_json({"dump_sha256": cli.file_sha256(dump_path)}),
        encoding="utf-8",
    )

    conns = [_DropConn("precheck"), _DropConn("write")]

    def fake_connect(_url):
        return conns.pop(0)

    collect_calls = []

    def fake_collect(conn, *, read_only=True):
        collect_calls.append((conn.name, read_only, conn.dropped))
        if read_only:
            conn.read_only = True
        return post_drop_snapshot if conn.dropped else current_snapshot

    monkeypatch.setattr(cli, "connect_pg", fake_connect)
    monkeypatch.setattr(cli, "collect_pg_snapshot", fake_collect)
    monkeypatch.setattr(cli, "collect_repo_grep_summary", lambda _root: grep_summary)
    monkeypatch.setattr(cli, "collect_local_default_proof", lambda: local_default_proof)

    code = cli.main([
        "drop",
        "--database-url",
        "postgres://secret@example/db",
        "--archive-dir",
        str(archive),
        "--reviewed-fingerprint",
        evidence["fingerprint"],
        "--confirm-scheduler-paused",
        "--confirm-native-host-paused",
        "--confirm-destructive-drop",
    ])

    assert code == 0
    assert collect_calls == [
        ("precheck", True, False),
        ("write", False, True),
    ]


def test_postcheck_reports_targets_absent_and_excluded_present(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch2_cleanup as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = {"fingerprint": "abc"}
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")

    monkeypatch.setattr(cli, "connect_pg", lambda _url: _PostcheckConn())

    code = cli.main([
        "postcheck",
        "--database-url", "postgres://secret@example/db",
        "--archive-dir", str(archive_dir),
    ])

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert code == 0
    assert payload["ok"] is True
    assert payload["targets_still_present"] == []
    assert payload["excluded_missing"] == []


def test_main_without_explicit_argv_uses_process_argv(monkeypatch):
    from scripts.migration import n9_batch2_cleanup as cli

    calls = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "n9_batch2_cleanup.py",
            "preview",
            "--database-url",
            "postgres://secret@example/db",
            "--repo-root",
            ".",
            "--output",
            "preview.json",
        ],
    )
    monkeypatch.setattr(cli, "_cmd_preview", lambda args: calls.append(args.output) or 7)

    assert cli.main() == 7
    assert calls == ["preview.json"]


class _FakeConn:
    def cursor(self):
        return _FakeCursor()

    def close(self):
        pass


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self._sql = " ".join(sql.split())
        self._params = params

    def fetchone(self):
        if "pg_get_functiondef" in self._sql:
            return ("CREATE FUNCTION news_search_vector_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",)
        return ("17.8",)

    def fetchall(self):
        return []


class _PostcheckConn:
    def cursor(self):
        return _PostcheckCursor()

    def close(self):
        pass


class _PostcheckCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self._sql = " ".join(sql.split())
        self._params = params

    def fetchone(self):
        if self._sql == "SHOW server_version":
            return ("17.8",)
        if "to_regprocedure" in self._sql:
            return (None,)
        return (None,)

    def fetchall(self):
        if "to_regclass" in self._sql:
            return [
                ("job_runs", None),
                ("prices", "public.prices"),
                ("agent_queries", "public.agent_queries"),
                ("research_reports", "public.research_reports"),
                ("agent_memories", "public.agent_memories"),
            ]
        return []


class _DropConn:
    def __init__(self, name):
        self.name = name
        self.read_only = False
        self.dropped = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return _DropCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class _DropCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        statement = " ".join(str(sql).split()).upper()
        if statement.startswith("DROP") and self.conn.read_only:
            raise AssertionError("drop attempted on read-only evidence connection")
        if statement.startswith("DROP"):
            self.conn.dropped = True
