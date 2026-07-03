from __future__ import annotations

from pathlib import Path


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
