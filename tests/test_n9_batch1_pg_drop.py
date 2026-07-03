from __future__ import annotations

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
    assert (archive_dir / "function_ddl.sql").read_text(encoding="utf-8") == "-- function ddl\n"


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
