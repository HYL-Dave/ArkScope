from __future__ import annotations

import json
from pathlib import Path
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
