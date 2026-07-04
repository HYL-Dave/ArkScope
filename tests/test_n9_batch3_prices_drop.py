from argparse import Namespace


def test_target_and_protected_tables_are_batch3_specific():
    from scripts.migration import n9_batch3_prices_drop as cli

    assert cli.TARGET_TABLES == ("prices",)
    assert "prices" not in cli.PROTECTED_TABLES
    assert set(cli.PROTECTED_TABLES) == {
        "agent_queries",
        "research_reports",
        "agent_memories",
    }


def test_archive_manifest_declares_pre_cutover_mirror_semantics():
    from scripts.migration import n9_batch3_prices_drop as cli

    manifest = cli.build_manifest(
        evidence={"fingerprint": "abc", "pg_snapshot": {"row_counts": {"prices": 1}}},
        dump_sha256="sha",
        dump_file="n9_batch3_prices.dump",
    )

    note = manifest["archive_semantics"]
    assert "pre-cutover" in note
    assert "not a backup of current local" in note
    assert manifest["scope"] == "pg_exit_n9_batch3_prices"


def test_evidence_fingerprint_is_order_stable():
    from scripts.migration import n9_batch3_prices_drop as cli

    a = cli.build_evidence_report(
        pg_snapshot={"row_counts": {"prices": 2}, "objects": [{"name": "prices", "status": "present"}]},
        local_snapshot={"row_count": 3, "ticker_count": 1},
        grep_summary={"allowed_hits": [{"path": "b"}, {"path": "a"}], "blockers": []},
        e2e_summary={"ok": True, "pg_attempts": []},
    )
    b = cli.build_evidence_report(
        pg_snapshot={"objects": [{"status": "present", "name": "prices"}], "row_counts": {"prices": 2}},
        local_snapshot={"ticker_count": 1, "row_count": 3},
        grep_summary={"blockers": [], "allowed_hits": [{"path": "a"}, {"path": "b"}]},
        e2e_summary={"pg_attempts": [], "ok": True},
    )

    assert a["fingerprint"] == b["fingerprint"]


def test_e2e_summary_fingerprint_ignores_report_path_and_timestamps():
    from scripts.migration import n9_batch3_prices_drop as cli

    base = {
        "pg_snapshot": {"row_counts": {"prices": 2}, "objects": [{"name": "prices", "status": "present"}]},
        "local_snapshot": {"row_count": 3, "ticker_count": 1},
        "grep_summary": {"allowed_hits": [], "blockers": []},
    }

    a = cli.build_evidence_report(
        **base,
        e2e_summary={
            "ok": True,
            "pg_attempts": [],
            "checks": [{"name": "healthz", "ok": True}],
            "output": "scratchpad/run-1.json",
            "started_at": "2026-07-05T01:00:00Z",
        },
    )
    b = cli.build_evidence_report(
        **base,
        e2e_summary={
            "ok": True,
            "pg_attempts": [],
            "checks": [{"ok": True, "name": "healthz"}],
            "output": "scratchpad/run-2.json",
            "started_at": "2026-07-05T01:05:00Z",
        },
    )

    assert a["e2e_summary"] == b["e2e_summary"]
    assert a["fingerprint"] == b["fingerprint"]


def test_dump_command_targets_prices_only_and_keeps_dsn_out_of_argv(tmp_path):
    from scripts.migration import n9_batch3_prices_drop as cli

    cmd = cli.build_pg_dump_command(
        database_url="postgresql://u:secret@host/db",
        output=tmp_path / "prices.dump",
        present_tables=["prices"],
    )

    joined = " ".join(cmd)
    assert "--table=public.prices" in cmd
    assert "agent_queries" not in joined
    assert "secret" not in joined


def test_drop_sql_has_no_cascade():
    from scripts.migration import n9_batch3_prices_drop as cli

    sql = cli.build_drop_sql(present_tables=["prices"])

    assert sql == ["DROP TABLE IF EXISTS public.prices"]
    assert "CASCADE" not in " ".join(sql).upper()


def test_validate_drop_args_requires_restore_proof_and_e2e(tmp_path):
    from scripts.migration import n9_batch3_prices_drop as cli

    args = Namespace(
        archive_dir=str(tmp_path),
        reviewed_fingerprint="abc",
        confirm_scheduler_paused=True,
        confirm_native_host_paused=True,
        confirm_destructive_drop=True,
    )

    result = cli.validate_drop_args(args)

    assert result.ok is False
    assert result.reason == "missing_restore_proof"


def test_postcheck_requires_prices_absent_and_app_records_present():
    from scripts.migration import n9_batch3_prices_drop as cli

    ok = cli.verify_post_drop_snapshot({
        "objects": [
            {"kind": "table", "name": "prices", "status": "missing_expected"},
            {"kind": "protected_table", "name": "agent_queries", "status": "protected_present"},
            {"kind": "protected_table", "name": "research_reports", "status": "protected_present"},
            {"kind": "protected_table", "name": "agent_memories", "status": "protected_present"},
        ],
    })

    assert ok["ok"] is True


def test_grep_classifier_allows_retired_market_admin_price_sql():
    from scripts.migration import n9_batch3_prices_drop as cli

    out = cli.classify_grep_hits([
        ("src/market_data_admin.py", '_PG_PRICES_SELECT = "SELECT * FROM prices"'),
    ])

    assert out["blockers"] == []
    assert out["allowed_hits"][0]["reason"] == "retired_pg_mirror_guarded"


def test_grep_classifier_allows_health_stats_interface_consumers():
    from scripts.migration import n9_batch3_prices_drop as cli

    out = cli.classify_grep_hits([
        ("src/service/provider_health.py", "stats = backend.query_health_stats() or {}"),
        ("src/tools/freshness.py", "stats = self._backend.query_health_stats()"),
    ])

    assert out["blockers"] == []
    assert {item["reason"] for item in out["allowed_hits"]} == {"health_stats_interface_consumer"}


def test_drop_repreview_uses_current_local_snapshot(monkeypatch, tmp_path):
    from scripts.migration import n9_batch3_prices_drop as cli

    archive = tmp_path / "archive"
    archive.mkdir()
    evidence = cli.build_evidence_report(
        pg_snapshot={"row_counts": {"prices": 1}, "objects": [{"kind": "table", "name": "prices", "status": "present"}]},
        local_snapshot={"path": str(tmp_path / "market_data.db"), "row_count": 1},
        grep_summary={"allowed_hits": [], "blockers": []},
        e2e_summary={"ok": True, "pg_attempts": []},
    )
    (archive / "evidence.json").write_text(__import__("json").dumps(evidence), encoding="utf-8")
    (archive / "manifest.json").write_text(
        __import__("json").dumps({
            "scope": cli.SCOPE,
            "archive_semantics": cli.ARCHIVE_SEMANTIC_NOTE,
            "dump_sha256": "sha",
        }),
        encoding="utf-8",
    )
    (archive / "restore_proof.json").write_text(
        __import__("json").dumps({"ok": True, "evidence_fingerprint": evidence["fingerprint"]}),
        encoding="utf-8",
    )
    dump = archive / "n9_batch3_prices.dump"
    dump.write_bytes(b"dump")
    monkeypatch.setattr(cli, "file_sha256", lambda path: "sha")
    monkeypatch.setattr(cli, "validate_drop_args", lambda args: cli.ValidationResult(True))
    class Conn:
        def close(self):
            pass

    monkeypatch.setattr(cli, "connect_pg", lambda _url: Conn())
    monkeypatch.setattr(cli, "collect_pg_snapshot", lambda _conn: evidence["pg_snapshot"])
    monkeypatch.setattr(cli, "collect_repo_grep_summary", lambda _root: evidence["grep_summary"])

    called = {}

    def fake_current_local(path):
        called["path"] = path
        return {"path": str(path), "row_count": 2}

    monkeypatch.setattr(cli, "collect_local_price_snapshot", fake_current_local)

    args = Namespace(
        database_url="postgresql://unused/db",
        archive_dir=str(archive),
        reviewed_fingerprint=evidence["fingerprint"],
        repo_root=str(tmp_path),
    )

    try:
        cli._cmd_drop(args)
    except SystemExit as exc:
        assert "current evidence fingerprint differs" in str(exc)
    else:
        raise AssertionError("drop should stop when current local snapshot drifts")
    assert called["path"] == str(tmp_path / "market_data.db")
