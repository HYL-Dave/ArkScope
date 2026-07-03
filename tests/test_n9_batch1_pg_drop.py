from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def test_evidence_report_fingerprint_is_order_stable():
    from scripts.migration import n9_batch1_pg_drop as cli

    first = cli.build_evidence_report(
        pg_snapshot={
            "server_version": "17.5",
            "objects": [
                {"kind": "table", "name": "news_scores", "status": "present", "row_count": 2},
                {"kind": "table", "name": "news", "status": "present", "row_count": 1},
            ],
            "dependencies": [],
            "row_fingerprints": {"news": "a", "news_scores": "b"},
        },
        grep_summary={"blockers": [], "allowed_hits": ["docs only"]},
    )
    second = cli.build_evidence_report(
        pg_snapshot={
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 1},
                {"kind": "table", "name": "news_scores", "status": "present", "row_count": 2},
            ],
            "server_version": "17.5",
            "dependencies": [],
            "row_fingerprints": {"news_scores": "b", "news": "a"},
        },
        grep_summary={"allowed_hits": ["docs only"], "blockers": []},
    )

    assert first == second
    assert len(first["fingerprint"]) == 64


def test_classify_targets_marks_optional_signals_missing_without_blocking():
    from scripts.migration import n9_batch1_pg_drop as cli

    objects = cli.classify_target_objects({
        "news": "public.news",
        "signals": None,
        "prices": "public.prices",
    })

    assert objects["news"]["status"] == "present"
    assert objects["signals"]["status"] == "missing_expected_optional"
    assert objects["prices"]["status"] == "excluded_present"


def test_grep_classifier_blocks_runtime_pg_reader_for_target_table():
    from scripts.migration import n9_batch1_pg_drop as cli

    summary = cli.classify_grep_hits([
        ("src/tools/backends/local_market_backend.py", "return super().query_iv_history(ticker)"),
        ("docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md", "iv_history"),
    ])

    assert summary["blockers"] == [
        {
            "path": "src/tools/backends/local_market_backend.py",
            "reason": "runtime_reference_to_drop_target",
            "match": "return super().query_iv_history(ticker)",
        }
    ]
    assert summary["allowed_hits"][0]["reason"] == "docs_or_tests"


def test_grep_classifier_allows_local_authority_and_retired_scripts():
    from scripts.migration import n9_batch1_pg_drop as cli

    summary = cli.classify_grep_hits([
        ("src/tools/sa_tools.py", "FROM sa_comment_signals s"),
        ("src/sa_capture_store.py", "INSERT INTO sa_comment_signals"),
        ("src/service/sa_market_news_health.py", "FROM sa_market_news"),
        ("src/service/jobs.py", "\"Extract rule-based signals from sa_article_comments into \""),
        ("src/macro_calendar/local_store.py", "FROM cal_economic_events"),
        ("src/market_data_admin.py", "_IV_INSERT = (\"INSERT OR IGNORE INTO iv_history \""),
        ("src/news_normalized/score_cutover.py", "\"FROM news_scores ORDER BY news_id\""),
        ("scripts/collection/daily_update.py", "python daily_update.py --scores"),
        ("scripts/migrate_sa_to_sqlite.py", "FROM sa_alpha_picks ORDER BY id"),
    ])

    assert summary["blockers"] == []
    reasons = {hit["path"]: hit["reason"] for hit in summary["allowed_hits"]}
    assert reasons["src/tools/sa_tools.py"] == "local_sqlite_authority"
    assert reasons["src/sa_capture_store.py"] == "local_sqlite_authority"
    assert reasons["src/service/sa_market_news_health.py"] == "local_sqlite_authority"
    assert reasons["src/service/jobs.py"] == "local_sqlite_authority"
    assert reasons["src/macro_calendar/local_store.py"] == "local_sqlite_authority"
    assert reasons["src/market_data_admin.py"] == "invalidated_rollback_lever_pending_n9_cleanup"
    assert reasons["src/news_normalized/score_cutover.py"] == "migration_cutover_dead_path_pending_n9_cleanup"
    assert reasons["scripts/collection/daily_update.py"] == "retired_cli_or_script"
    assert reasons["scripts/migrate_sa_to_sqlite.py"] == "retired_cli_or_script"


def test_preview_output_is_sanitized_and_written(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch1_pg_drop as cli

    output = tmp_path / "preview.json"
    monkeypatch.setattr(
        cli,
        "connect_pg",
        lambda _url: _FakeConn(),
    )
    monkeypatch.setattr(
        cli,
        "collect_repo_grep_summary",
        lambda _root: {"blockers": [], "allowed_hits": []},
    )

    code = cli.main([
        "preview",
        "--database-url",
        "postgres://secret@example/db",
        "--repo-root",
        str(tmp_path),
        "--output",
        str(output),
    ])

    stdout = capsys.readouterr().out
    assert code == 0
    assert output.exists()
    assert "secret" not in stdout
    assert '"status": "previewed"' in stdout


def test_pg_dump_command_targets_only_batch1_objects(tmp_path):
    from scripts.migration import n9_batch1_pg_drop as cli

    cmd = cli.build_pg_dump_command(
        database_url="postgres://redacted",
        output=tmp_path / "n9.dump",
        present_tables=["news", "news_scores"],
        present_views=["news_latest_scores"],
    )

    assert "pg_dump" in cmd[0]
    assert "--format=custom" in cmd
    assert "--no-owner" in cmd
    assert "--no-privileges" in cmd
    assert "--table=public.news" in cmd
    assert "--table=public.news_scores" in cmd
    assert "--table=public.news_latest_scores" in cmd
    assert "--table=public.prices" not in cmd
    assert "postgres://redacted" not in cmd


def test_restore_proof_requires_matching_row_fingerprints():
    from scripts.migration import n9_batch1_pg_drop as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "row_fingerprints": {"news": "old"},
            "objects": [{"kind": "table", "name": "news", "status": "present", "row_count": 1}],
        },
    }
    restored = {
        "row_fingerprints": {"news": "different"},
        "objects": [{"kind": "table", "name": "news", "status": "present", "row_count": 1}],
    }

    result = cli.compare_restore_to_evidence(restored, evidence)

    assert result["ok"] is False
    assert result["mismatches"] == [
        {"table": "news", "field": "row_fingerprint", "expected": "old", "actual": "different"}
    ]


def test_restore_proof_accepts_matching_counts_and_fingerprints():
    from scripts.migration import n9_batch1_pg_drop as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "row_fingerprints": {"news": "same"},
            "objects": [{"kind": "table", "name": "news", "status": "present", "row_count": 1}],
        },
    }
    restored = {
        "row_fingerprints": {"news": "same"},
        "objects": [{"kind": "table", "name": "news", "status": "present", "row_count": 1}],
    }

    result = cli.compare_restore_to_evidence(restored, evidence)

    assert result == {"ok": True, "mismatches": []}


def test_dump_command_writes_archive_manifest(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch1_pg_drop as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 0},
                {"kind": "view", "name": "news_latest_scores", "status": "present"},
            ],
            "row_fingerprints": {"news": "d41d8cd98f00b204e9800998ecf8427e"},
        },
    }
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(cli._canonical_json(evidence), encoding="utf-8")
    archive_dir = tmp_path / "archive"

    def fake_run(cmd, **kwargs):
        if cmd[0] == "pg_dump":
            output = next(part.split("=", 1)[1] for part in cmd if part.startswith("--file="))
            Path(output).write_bytes(b"dump")
        return SimpleNamespace(returncode=0, stdout="toc\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "read_function_ddl", lambda _conn: "-- function ddl\n")
    monkeypatch.setattr(cli, "connect_pg", lambda _url: _FakeConn())

    code = cli.main([
        "dump",
        "--database-url",
        "postgres://secret@example/db",
        "--expected-report",
        str(evidence_path),
        "--archive-dir",
        str(archive_dir),
    ])

    stdout = capsys.readouterr().out
    assert code == 0
    assert "secret" not in stdout
    assert (archive_dir / "n9_batch1.dump").exists()
    assert (archive_dir / "evidence.json").exists()
    assert (archive_dir / "manifest.json").exists()
    assert (archive_dir / "function_ddl.sql").read_text(encoding="utf-8") == (
        "SET check_function_bodies = off;\n\n-- function ddl\n\n"
    )


def test_verify_dump_writes_restore_proof(tmp_path, monkeypatch):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 0},
            ],
            "row_fingerprints": {"news": "d41d8cd98f00b204e9800998ecf8427e"},
        },
    }
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    (archive_dir / "n9_batch1.dump").write_bytes(b"dump")
    (archive_dir / "manifest.json").write_text(
        cli._canonical_json({"dump_sha256": cli.file_sha256(archive_dir / "n9_batch1.dump")}),
        encoding="utf-8",
    )
    (archive_dir / "function_ddl.sql").write_text("", encoding="utf-8")

    calls = []
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda cmd, **kwargs: calls.append(cmd[0]) or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(cli, "connect_pg", lambda _url: _FakeConn())

    code = cli.main([
        "verify-dump",
        "--database-url",
        "postgres://secret@example/db",
        "--archive-dir",
        str(archive_dir),
        "--restore-db",
        "arkscope_restore_test",
        "--confirm-create-drop-restore-db",
    ])

    proof = cli._load_json(archive_dir / "restore_proof.json")
    assert code == 0
    assert proof["ok"] is True
    assert calls == ["createdb", "pg_restore", "dropdb"]


def test_drop_refuses_without_reviewed_fingerprint(tmp_path):
    from scripts.migration import n9_batch1_pg_drop as cli

    args = cli.parse_args(["drop", "--database-url", "postgres://x"])

    result = cli.validate_drop_args(args)

    assert result.ok is False
    assert result.reason == "missing_reviewed_fingerprint"


def test_drop_refuses_without_restore_proof(tmp_path):
    from scripts.migration import n9_batch1_pg_drop as cli

    args = cli.parse_args([
        "drop",
        "--database-url",
        "postgres://x",
        "--reviewed-fingerprint",
        "abc",
        "--archive-dir",
        str(tmp_path),
        "--confirm-scheduler-paused",
        "--confirm-native-host-paused",
        "--confirm-destructive-drop",
    ])

    result = cli.validate_drop_args(args)

    assert result.ok is False
    assert result.reason == "missing_restore_proof"


def test_drop_sql_is_explicit_and_never_cascade():
    from scripts.migration import n9_batch1_pg_drop as cli

    sql = cli.build_drop_sql(
        present_tables=["news_scores", "news"],
        present_views=["news_latest_scores"],
        present_functions=["news_sentiment_summary(character varying, integer, character varying)"],
    )

    joined = "\n".join(sql)
    assert "CASCADE" not in joined.upper()
    assert "DROP VIEW IF EXISTS public.news_latest_scores" in joined
    assert (
        "DROP FUNCTION IF EXISTS public.news_sentiment_summary"
        "(character varying, integer, character varying)" in joined
    )
    assert "DROP TABLE IF EXISTS public.news_scores, public.news" in joined


def test_drop_rechecks_current_evidence_and_postconditions(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = cli.build_evidence_report(
        pg_snapshot={
            "server_version": "17.5",
            "objects": [
                {"kind": "table", "name": "news", "status": "present"},
                {"kind": "view", "name": "news_latest_scores", "status": "present"},
                {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
            ],
            "row_counts": {"news": 1},
            "row_fingerprints": {"news": "abc"},
            "dependencies": [],
        },
        grep_summary={"blockers": [], "allowed_hits": []},
    )
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    (archive_dir / "restore_proof.json").write_text(
        cli._canonical_json({"ok": True, "evidence_fingerprint": evidence["fingerprint"]}),
        encoding="utf-8",
    )
    (archive_dir / "n9_batch1.dump").write_bytes(b"dump")
    (archive_dir / "manifest.json").write_text(
        cli._canonical_json({"dump_sha256": cli.file_sha256(archive_dir / "n9_batch1.dump")}),
        encoding="utf-8",
    )

    write_conn = _DropConn()
    monkeypatch.setattr(cli, "connect_pg", lambda _url: write_conn)
    monkeypatch.setattr(cli, "collect_pg_snapshot", lambda _conn: evidence["pg_snapshot"])
    monkeypatch.setattr(cli, "collect_repo_grep_summary", lambda _root: evidence["grep_summary"])

    code = cli.main([
        "drop",
        "--database-url",
        "postgres://secret@example/db",
        "--archive-dir",
        str(archive_dir),
        "--reviewed-fingerprint",
        evidence["fingerprint"],
        "--confirm-scheduler-paused",
        "--confirm-native-host-paused",
        "--confirm-destructive-drop",
    ])

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert code == 0
    assert "secret" not in stdout
    assert payload["dropped_tables"] == 1
    assert write_conn.committed is True
    assert write_conn.rolled_back is False
    assert any("DROP TABLE IF EXISTS public.news" in sql for sql in write_conn.sql)
    assert any("to_regclass" in sql for sql in write_conn.sql)


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
        if self._sql == "SHOW server_version":
            return ("17.5",)
        if "COUNT(*)" in self._sql:
            return (0,)
        if "row_fingerprint" in self._sql:
            return ("d41d8cd98f00b204e9800998ecf8427e",)
        return (None,)

    def fetchall(self):
        if "to_regclass" in self._sql:
            return [(name, f"public.{name}") for name in self._params[0]]
        if "pg_depend" in self._sql:
            return []
        return []


class _DropConn:
    def __init__(self):
        self.cursor_obj = _DropCursor()
        self.sql = self.cursor_obj.sql
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class _DropCursor:
    def __init__(self):
        self.sql = []
        self._params = None
        self._last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        assert "CASCADE" not in compact.upper()
        self.sql.append(compact)
        self._last_sql = compact
        self._params = params

    def fetchall(self):
        if "to_regclass" not in self._last_sql:
            return []
        return [
            ("news", None),
            ("news_latest_scores", None),
            ("prices", "public.prices"),
        ]


# --- review fixups: client env propagation / version guard / postcheck ---------------


def test_pg_client_env_builds_libpq_vars_without_url_leak():
    from scripts.migration import n9_batch1_pg_drop as cli

    env = cli.pg_client_env("postgres://user:p%40ss@192.168.0.185:15432/mindfulrl")

    assert env == {
        "PGHOST": "192.168.0.185",
        "PGPORT": "15432",
        "PGUSER": "user",
        "PGPASSWORD": "p@ss",
        "PGDATABASE": "mindfulrl",
    }


def test_pg_client_env_omits_missing_parts_and_overrides_dbname():
    from scripts.migration import n9_batch1_pg_drop as cli

    env = cli.pg_client_env("postgresql://onlyhost/db", dbname="restore_db")

    assert env["PGHOST"] == "onlyhost"
    assert env["PGDATABASE"] == "restore_db"
    assert "PGPORT" not in env
    assert "PGUSER" not in env
    assert "PGPASSWORD" not in env


def test_run_checked_injects_pg_env_not_url(monkeypatch):
    from scripts.migration import n9_batch1_pg_drop as cli

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli._run_checked(["createdb", "x"], database_url="postgres://u:pw@h:5/d")

    env = captured["env"]
    assert env["PGHOST"] == "h"
    assert env["PGPORT"] == "5"
    assert env["PGDATABASE"] == "d"
    assert env["PGPASSWORD"] == "pw"
    assert all("postgres://" not in str(v) for v in env.values())


def test_verify_dump_passes_connection_to_every_client(tmp_path, monkeypatch):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 0},
            ],
            "row_fingerprints": {"news": "d41d8cd98f00b204e9800998ecf8427e"},
        },
    }
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    (archive_dir / "n9_batch1.dump").write_bytes(b"dump")
    (archive_dir / "manifest.json").write_text(
        cli._canonical_json({"dump_sha256": cli.file_sha256(archive_dir / "n9_batch1.dump")}),
        encoding="utf-8",
    )
    (archive_dir / "function_ddl.sql").write_text("-- ddl\n", encoding="utf-8")

    calls = []

    def fake_run_checked(cmd, *, database_url=None, dbname=None):
        calls.append((cmd[0], database_url, dbname))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli, "_run_checked", fake_run_checked)
    monkeypatch.setattr(cli, "connect_pg", lambda _url: _FakeConn())

    code = cli.main([
        "verify-dump",
        "--database-url", "postgres://secret@example/db",
        "--archive-dir", str(archive_dir),
        "--restore-db", "r_db",
        "--confirm-create-drop-restore-db",
    ])

    assert code == 0
    by_tool = {name: (url, dbname) for name, url, dbname in calls}
    assert by_tool["createdb"][0] == "postgres://secret@example/db"
    assert by_tool["pg_restore"] == ("postgres://secret@example/db", "r_db")
    assert by_tool["psql"] == ("postgres://secret@example/db", "r_db")
    assert by_tool["dropdb"][0] == "postgres://secret@example/db"


def test_parse_pg_major_handles_client_and_server_strings():
    from scripts.migration import n9_batch1_pg_drop as cli

    assert cli.parse_pg_major("pg_dump (PostgreSQL) 17.5 (Ubuntu 17.5-1)") == 17
    assert cli.parse_pg_major("16.4") == 16


def test_dump_refuses_when_pg_dump_client_older_than_server(tmp_path, monkeypatch):
    import pytest
    from scripts.migration import n9_batch1_pg_drop as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "server_version": "17.5",
            "objects": [],
            "row_fingerprints": {},
        },
    }
    report = tmp_path / "evidence.json"
    report.write_text(cli._canonical_json(evidence), encoding="utf-8")

    monkeypatch.setattr(
        cli, "_pg_dump_client_version_text", lambda: "pg_dump (PostgreSQL) 16.4"
    )

    with pytest.raises(SystemExit) as exc:
        cli.main([
            "dump",
            "--database-url", "postgres://secret@example/db",
            "--expected-report", str(report),
            "--archive-dir", str(tmp_path / "archive"),
        ])

    assert "older than server" in str(exc.value)


class _PostcheckConn:
    def __init__(self, regclass_by_name, regprocedure_by_signature=None):
        self._map = regclass_by_name
        self._procedures = regprocedure_by_signature or {}

    def cursor(self):
        conn = self

        class _Cur:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, sql, params=None):
                self._sql = " ".join(sql.split())
                self._params = params

            def fetchall(self):
                if "to_regprocedure" in self._sql:
                    return [(signature, conn._procedures.get(signature)) for signature in self._params[0]]
                return [(name, conn._map.get(name)) for name in self._params[0]]

        return _Cur()

    def close(self):
        pass


def test_postcheck_ok_when_targets_gone_and_excluded_present(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 1},
                {"kind": "view", "name": "news_latest_scores", "status": "present"},
                {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
            ],
            "row_fingerprints": {},
        },
    }
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    monkeypatch.setattr(
        cli, "connect_pg",
        lambda _url: _PostcheckConn({"news": None, "news_latest_scores": None, "prices": "public.prices"}),
    )

    code = cli.main([
        "postcheck",
        "--database-url", "postgres://secret@example/db",
        "--archive-dir", str(archive_dir),
    ])

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["targets_still_present"] == []
    assert payload["functions_still_present"] == []
    assert payload["excluded_missing"] == []
    assert "secret" not in out


def test_postcheck_fails_when_target_still_present(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 1},
                {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
            ],
            "row_fingerprints": {},
        },
    }
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    monkeypatch.setattr(
        cli, "connect_pg",
        lambda _url: _PostcheckConn({"news": "public.news", "prices": "public.prices"}),
    )

    code = cli.main([
        "postcheck",
        "--database-url", "postgres://secret@example/db",
        "--archive-dir", str(archive_dir),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["targets_still_present"] == ["news"]


def test_postcheck_fails_when_target_function_still_present(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = cli.build_evidence_report(
        pg_snapshot={
            "server_version": "17.5",
            "objects": [
                {"kind": "excluded_table", "name": "prices", "status": "excluded_present"},
            ],
            "row_fingerprints": {},
        },
        grep_summary={"blockers": [], "allowed_hits": []},
    )
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "connect_pg",
        lambda _url: _PostcheckConn(
            {"prices": "public.prices"},
            {
                "news_sentiment_summary(character varying, integer, character varying)": (
                    "public.news_sentiment_summary(character varying, integer, character varying)"
                )
            },
        ),
    )

    code = cli.main([
        "postcheck",
        "--database-url", "postgres://secret@example/db",
        "--archive-dir", str(archive_dir),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["functions_still_present"] == [
        "news_sentiment_summary(character varying, integer, character varying)"
    ]


def test_extension_statements_skip_builtin_and_quote_names():
    from scripts.migration import n9_batch1_pg_drop as cli

    stmts = cli.build_extension_statements(["vector", "pg_trgm", "plpgsql"])

    assert stmts == [
        'CREATE EXTENSION IF NOT EXISTS "pg_trgm"',
        'CREATE EXTENSION IF NOT EXISTS "vector"',
    ]


def test_dump_manifest_records_required_extensions(tmp_path, monkeypatch, capsys):
    from scripts.migration import n9_batch1_pg_drop as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 0},
            ],
            "row_fingerprints": {"news": "d41d8cd98f00b204e9800998ecf8427e"},
        },
    }
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(cli._canonical_json(evidence), encoding="utf-8")
    archive_dir = tmp_path / "archive"

    def fake_run(cmd, **kwargs):
        if cmd[0] == "pg_dump":
            output = next(part.split("=", 1)[1] for part in cmd if part.startswith("--file="))
            Path(output).write_bytes(b"dump")
        return SimpleNamespace(returncode=0, stdout="toc\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "read_function_ddl", lambda _conn: "")
    monkeypatch.setattr(cli, "collect_required_extensions", lambda _conn: ["pg_trgm", "vector"])
    monkeypatch.setattr(cli, "connect_pg", lambda _url: _FakeConn())

    code = cli.main([
        "dump",
        "--database-url", "postgres://secret@example/db",
        "--expected-report", str(evidence_path),
        "--archive-dir", str(archive_dir),
    ])

    assert code == 0
    manifest = cli._load_json(archive_dir / "manifest.json")
    assert manifest["required_extensions"] == ["pg_trgm", "vector"]


def test_verify_dump_creates_extensions_before_restore(tmp_path, monkeypatch):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 0},
            ],
            "row_fingerprints": {"news": "d41d8cd98f00b204e9800998ecf8427e"},
        },
    }
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    (archive_dir / "n9_batch1.dump").write_bytes(b"dump")
    (archive_dir / "manifest.json").write_text(
        cli._canonical_json({
            "dump_sha256": cli.file_sha256(archive_dir / "n9_batch1.dump"),
            "required_extensions": ["pg_trgm", "vector"],
        }),
        encoding="utf-8",
    )
    (archive_dir / "function_ddl.sql").write_text("", encoding="utf-8")

    calls = []

    def fake_run_checked(cmd, *, database_url=None, dbname=None):
        calls.append((cmd[0], tuple(cmd[1:]), dbname))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli, "_run_checked", fake_run_checked)
    monkeypatch.setattr(cli, "connect_pg", lambda _url: _FakeConn())

    code = cli.main([
        "verify-dump",
        "--database-url", "postgres://secret@example/db",
        "--archive-dir", str(archive_dir),
        "--restore-db", "r_db",
        "--confirm-create-drop-restore-db",
    ])

    assert code == 0
    tools = [name for name, _args, _db in calls]
    assert tools == ["createdb", "psql", "psql", "pg_restore", "dropdb"]
    ext_cmds = [args for name, args, db in calls if name == "psql" and db == "r_db"]
    joined = " ".join(" ".join(args) for args in ext_cmds)
    assert 'CREATE EXTENSION IF NOT EXISTS "pg_trgm"' in joined
    assert 'CREATE EXTENSION IF NOT EXISTS "vector"' in joined


def test_trigger_function_ddl_collected_for_target_tables():
    from scripts.migration import n9_batch1_pg_drop as cli

    class _TrigConn:
        def cursor(self):
            class _Cur:
                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

                def execute(self, sql, params=None):
                    assert "pg_trigger" in sql and "tgisinternal" in sql

                def fetchall(self):
                    return [("CREATE OR REPLACE FUNCTION public.news_search_vector_update() ...",)]

            return _Cur()

    ddl = cli.collect_trigger_function_ddl(_TrigConn(), ["news"])

    assert "news_search_vector_update" in ddl
    assert ddl.rstrip().endswith(";")


def test_verify_dump_applies_function_ddl_before_restore(tmp_path, monkeypatch):
    from scripts.migration import n9_batch1_pg_drop as cli

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "objects": [
                {"kind": "table", "name": "news", "status": "present", "row_count": 0},
            ],
            "row_fingerprints": {"news": "d41d8cd98f00b204e9800998ecf8427e"},
        },
    }
    (archive_dir / "evidence.json").write_text(cli._canonical_json(evidence), encoding="utf-8")
    (archive_dir / "n9_batch1.dump").write_bytes(b"dump")
    (archive_dir / "manifest.json").write_text(
        cli._canonical_json({
            "dump_sha256": cli.file_sha256(archive_dir / "n9_batch1.dump"),
            "required_extensions": ["vector"],
        }),
        encoding="utf-8",
    )
    (archive_dir / "function_ddl.sql").write_text(
        "SET check_function_bodies = off;\nCREATE FUNCTION ...;", encoding="utf-8"
    )

    order = []

    def fake_run_checked(cmd, *, database_url=None, dbname=None):
        tag = cmd[0]
        if tag == "psql" and any("function_ddl" in str(part) for part in cmd):
            assert "ON_ERROR_STOP=1" in cmd
            tag = "psql-function-ddl"
        elif tag == "psql":
            tag = "psql-extension"
        order.append(tag)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli, "_run_checked", fake_run_checked)
    monkeypatch.setattr(cli, "connect_pg", lambda _url: _FakeConn())

    code = cli.main([
        "verify-dump",
        "--database-url", "postgres://secret@example/db",
        "--archive-dir", str(archive_dir),
        "--restore-db", "r_db",
        "--confirm-create-drop-restore-db",
    ])

    assert code == 0
    assert order == ["createdb", "psql-extension", "psql-function-ddl", "pg_restore", "dropdb"]


def test_dead_pg_helper_get_recent_news_is_a_drop_target():
    from scripts.migration import n9_batch1_pg_drop as cli

    # Live drop attempt 1 (2026-07-03) was correctly blocked because this day-one
    # PG helper depends on the news rowtype and was outside the reviewed targets.
    assert "get_recent_news(character varying, integer, integer)" in cli.TARGET_FUNCTION_SIGNATURES
