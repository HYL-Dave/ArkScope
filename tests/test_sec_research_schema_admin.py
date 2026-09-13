"""Audited reset and uninstall, never a startup migration or prefix DROP."""

from contextlib import closing
import json
import sqlite3

import pytest

from src.sec_research import schema
from src.sec_research.capture_lock import research_operation
from tests.test_sec_research_maintenance import admin, api, snapshot, market_writer
from tests.test_sec_research_citations import evidence, rig
from tests.test_sec_research_references import profile


def preview(a, mode="reset"):
    return api("schema_admin").preview_schema_reset(a.paths, mode=mode, profile_connection=a.profile)


def apply(a, p, name="receipt.json", backup="backup"):
    return api("schema_admin").apply_schema_reset(a.paths, p, approval_sha256=p["approval_sha256"],
        backup_path=None if backup is None else a.tmp / backup,
        receipt_path=a.tmp / name, profile_connection=a.profile)


def test_schema_reset_requires_backup_and_exclusive_lease(admin):
    a = admin
    a.captures.put(b"retained capture")
    p = preview(a)
    assert p["status"] == "ready", p
    before = snapshot(a)
    assert apply(a, p, backup=None)["status"] == "blocked"
    with research_operation(a.paths.capture_root):
        result = apply(a, p)
    assert result["status"] == "blocked" and result["code"] == "sec_research_operation_busy", result
    assert snapshot(a) == before and not (a.tmp / "backup").exists()
    result = apply(a, p)
    assert result["status"] == "ok", result
    assert (a.tmp / "backup" / "market_data.db").is_file()
    assert result["backup"]["format"] == "arkscope-sec-research-raw-backup"


def test_schema_reset_refuses_research_references(evidence, profile, tmp_path):
    r = evidence.rig
    runs, _ = profile
    runs.append_event("roots-run", "tool_end", {"tool": "read_sec_filing", "sec_citations": [evidence.document_ref]})
    with closing(sqlite3.connect(runs.db_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        result = api("schema_admin").preview_schema_reset(r.store.paths, mode="reset", profile_connection=conn)
    assert result["status"] == "blocked", result
    assert result["code"] == "sec_research_reset_references_present"
    assert result["references"]["research_citations"] == 1
    assert r.captures.read(evidence.document_ref["original_sha256"])


def test_schema_reset_refuses_colocated_research_references(evidence, admin):
    from src.research_threads import ResearchThreadStore

    a = admin
    threads = ResearchThreadStore(a.paths.market_db_path)
    threads.ensure_thread(id="retained", title="Retained")
    threads.append_message(thread_id="retained", role="assistant", content="historical",
        tool_calls=[{"name": "read_sec_filing", "sec_citations": [evidence.document_ref]}])
    p = preview(a)
    assert p["status"] == "blocked" and p["code"] == "sec_research_reset_references_present", json.dumps(p)
    assert p["references"]["research_citations"] == 1


@pytest.mark.parametrize("mode", ["reset", "uninstall"])
@pytest.mark.parametrize("mismatch", [False, True])
def test_schema_reset_preserves_unrelated_rows_and_sqlite_sequence(admin, mode, mismatch):
    a = admin
    sha = a.captures.put(b"retained capture")
    stage = a.paths.capture_root / "staging" / ("a" * 32)
    stage.write_bytes(b"staged")
    with a.store.connect() as conn:
        for table in ("news", "prices", "financial_cache"):
            conn.execute(f"CREATE TABLE {table}(id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)")
            conn.execute(f"INSERT INTO {table} VALUES(77, 'retained')")
        if mismatch:
            conn.execute("DROP TRIGGER sec_research_objects_no_update")
            conn.execute("CREATE TRIGGER sec_research_objects_no_update BEFORE UPDATE ON sec_research_objects "
                         "BEGIN SELECT RAISE(ABORT, 'mismatch fixture'); END")
    before = snapshot(a)[1]
    p = preview(a, mode)
    assert p["status"] == "ready", p
    result = apply(a, p)
    assert result["status"] == "ok" and result["phase"] == "complete", result
    assert snapshot(a)[1] == before
    with a.store.connect(readonly=True) as conn:
        for table in ("news", "prices", "financial_cache"):
            assert tuple(conn.execute(f"SELECT * FROM {table}").fetchone()) == (77, "retained")
        assert [tuple(r) for r in conn.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name")] == [
            ("financial_cache", 77), ("news", 77), ("prices", 77)]
        if mode == "reset":
            schema.verify(conn)
            assert a.captures.status()["charged_bytes"] == 22
        else:
            assert schema._owned(conn) == {}
            assert result["retained_bytes"] == 22 and result["accounting"] == "schema_absent"
    manifest = json.loads((a.tmp / "backup" / "raw-backup.json").read_text())
    assert manifest["format"] == "arkscope-sec-research-raw-backup"
    assert not (a.tmp / "backup" / "manifest.json").exists()
    assert (a.tmp / "backup" / "market_data.db.sec-research" / "objects" / sha).read_bytes() == b"retained capture"
    assert (a.tmp / "backup" / "market_data.db.sec-research" / "staging" / stage.name).read_bytes() == b"staged"
    with sqlite3.connect(a.tmp / "backup" / "market_data.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM sec_research_objects").fetchone()[0] == 1


def test_unknown_owned_objects_are_not_prefix_drop_targets(admin):
    a = admin
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE SeC_ReSeArCh_unreviewed(value TEXT)")
        conn.execute("INSERT INTO SeC_ReSeArCh_unreviewed VALUES('retain')")
    before = snapshot(a)
    p = preview(a)
    result = apply(a, p)
    assert snapshot(a) == before
    assert p["status"] == "blocked" and p["code"] == "sec_research_unknown_owned_objects", p
    assert p["recovery"] == "inspect_raw_backup"
    assert result["status"] == "blocked"
    assert result["phase"] == result["receipt_phase"] == "backed_up", result


@pytest.mark.parametrize("mode", ["reset", "uninstall"])
def test_unknown_schema_discloses_backup_only_and_preserves_source(admin, mode):
    a = admin
    sha = a.captures.put(b"registered source")
    stage = a.paths.capture_root / "staging" / ("d" * 32)
    stage.write_bytes(b"staged source")
    unregistered = a.paths.capture_root / "objects" / ("e" * 64)
    unregistered.write_bytes(b"unregistered source")
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE sec_research_unknown(value TEXT)")
        conn.execute("INSERT INTO sec_research_unknown VALUES('retained')")
        conn.execute("CREATE TABLE news(id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)")
        conn.execute("INSERT INTO news VALUES(77,'unrelated')")
    before = snapshot(a)
    source_bytes = a.paths.market_db_path.read_bytes(), a.profile_path.read_bytes()
    p = preview(a, mode)
    assert p.get("apply_effect") == "raw_backup_only", json.dumps(p)
    assert p["reference_status"] == "roots_observed_closure_unverified"
    result = apply(a, p)
    assert result["status"] == "blocked" and result["code"] == "sec_research_unknown_owned_objects", result
    assert result["phase"] == result["receipt_phase"] == "backed_up"
    assert result["backup"].get("path") == str(a.tmp / "backup"), result
    assert result["recovery"] == "inspect_raw_backup" and result["accounting"] == "unchanged"
    assert result["removed"] == [] and result["freed_bytes"] == 0
    assert result["blocked"] == result["remaining"] == result["selected"]
    assert snapshot(a) == before
    assert (a.paths.market_db_path.read_bytes(), a.profile_path.read_bytes()) == source_bytes
    assert json.loads((a.tmp / "receipt.json").read_text()) == result
    raw = a.tmp / "backup"
    manifest = json.loads((raw / "raw-backup.json").read_text())
    assert manifest["scope"] == {"database": "whole-market-database", "captures": "sec-research-only",
        "excluded": ["independent-profile-store", "independent-sa-store", "other-capture-roots"]}
    assert manifest["database_bytes"] == "sqlite-backup-unnormalized"
    assert not (raw / "manifest.json").exists() and not (raw / ".incomplete").exists()
    for key, content in before[1].items():
        assert (raw / "market_data.db.sec-research" / key).read_bytes() == content
    with sqlite3.connect(raw / "market_data.db") as conn:
        assert list(conn.iterdump()) == before[0]
    with pytest.raises(ValueError):
        api("operations").restore_bundle(raw, a.tmp / "canonical-restore")


def test_unknown_schema_backup_keeps_reference_findings_visible(admin, evidence, profile):
    a = admin
    runs, _ = profile
    runs.append_event("roots-run", "tool_end", {"tool": "read_sec_filing", "sec_citations": [evidence.document_ref]})
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE sec_research_unknown(value TEXT)")
    with closing(sqlite3.connect(runs.db_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        a.profile = conn
        p = preview(a)
        result = apply(a, p)
    assert result["phase"] == "backed_up", result
    assert p["references"] == result["references"] == {"research_citations": 1}
    assert result["reference_status"] == "roots_observed_closure_unverified"
    assert result["status"] == "blocked" and result["removed"] == []


@pytest.mark.parametrize("fault", ["missing_backup", "existing_backup", "unsafe_backup", "unsafe_capture",
    "missing_root", "stale", "digest", "partial_profile", "missing_profile", "caller_transaction", "lease"])
def test_unknown_schema_missing_unsafe_or_stale_inputs_never_back_up(admin, fault):
    a = admin
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE sec_research_unknown(value TEXT)")
    p = preview(a)
    backup = "backup"
    if fault == "missing_backup":
        backup = None
    elif fault == "existing_backup":
        (a.tmp / "backup").mkdir()
    elif fault == "unsafe_backup":
        (a.tmp / "backup").symlink_to(a.paths.capture_root, target_is_directory=True)
    elif fault == "unsafe_capture":
        (a.paths.capture_root / "objects" / ("a" * 64)).symlink_to(a.profile_path)
    elif fault == "missing_root":
        a.paths.capture_root.rename(a.tmp / "retained-root")
    elif fault == "stale":
        with a.store.connect() as conn:
            conn.execute("INSERT INTO sec_research_unknown VALUES('new state')")
    elif fault == "digest":
        p["approval_sha256"] = "0" * 64
    elif fault == "partial_profile":
        with sqlite3.connect(a.profile_path) as conn:
            conn.execute("CREATE TABLE research_messages(value TEXT)")
    elif fault == "missing_profile":
        a.profile_path.rename(a.tmp / "retained-profile.db")
    elif fault == "caller_transaction":
        a.profile.execute("BEGIN")
        a.profile.execute("SELECT * FROM profile_settings").fetchall()
    if fault == "lease":
        with research_operation(a.paths.capture_root):
            result = apply(a, p, backup=backup)
    else:
        result = apply(a, p, backup=backup)
    assert result["status"] == "blocked" and result["phase"] == "not_started", result
    assert not (a.tmp / "receipt.json").exists()
    assert not (a.tmp / "backup" / "raw-backup.json").exists()
    assert not (a.tmp / "backup" / "market_data.db").exists()
    if fault == "caller_transaction":
        assert a.profile.in_transaction
    if fault == "missing_root":
        assert not a.paths.capture_root.exists()
    if fault == "missing_profile":
        assert not a.profile_path.exists()


@pytest.mark.parametrize("fault", ["database", "capture", "marker"])
def test_unknown_schema_backup_failure_leaves_no_success_marker(admin, monkeypatch, fault):
    a = admin
    a.captures.put(b"retained")
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE sec_research_unknown(value TEXT)")
    p, before = preview(a), snapshot(a)
    operations = api("operations")

    def fail(*args, **kwargs):
        raise OSError("fixture raw backup failure")

    target = {"database": "backup_market_db", "capture": "_copy_member", "marker": "_rename_new"}[fault]
    with monkeypatch.context() as patch:
        patch.setattr(operations, target, fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "prepared", result
    assert (a.tmp / "backup" / ".incomplete").exists()
    assert not (a.tmp / "backup" / "raw-backup.json").exists()
    assert snapshot(a) == before
    assert apply(a, preview(a), "retry.json", "retry-backup")["phase"] == "backed_up"


def test_unknown_schema_backup_rechecks_before_success_marker(admin, monkeypatch):
    a = admin
    a.captures.put(b"retained")
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE sec_research_unknown(value TEXT)")
    p = preview(a)
    operations = api("operations")
    copy = operations._copy_member

    def change(*args):
        copy(*args)
        with a.store.connect() as conn:
            conn.execute("INSERT INTO sec_research_unknown VALUES('changed during backup')")

    monkeypatch.setattr(operations, "_copy_member", change)
    result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "prepared", result
    assert result["code"] == "sec_research_preview_stale"
    assert (a.tmp / "backup" / ".incomplete").exists()
    assert not (a.tmp / "backup" / "raw-backup.json").exists()
    with a.store.connect(readonly=True) as conn:
        assert conn.execute("SELECT value FROM sec_research_unknown").fetchone()[0] == "changed during backup"
        assert conn.execute("SELECT COUNT(*) FROM sec_research_objects").fetchone()[0] == 1


@pytest.mark.parametrize("dependency", ["mixed_fk", "view", "trigger"])
def test_schema_reset_blocks_external_dependencies(admin, dependency):
    a = admin
    sha = a.captures.put(b"external")
    with a.store.connect() as conn:
        if dependency == "mixed_fk":
            conn.execute('CREATE TABLE external(sha TEXT REFERENCES "SeC_ReSeArCh_ObJeCtS"(sha256) ON DELETE CASCADE)')
            conn.execute("INSERT INTO external VALUES(?)", (sha,))
        elif dependency == "view":
            conn.execute('CREATE VIEW external AS SELECT * FROM "SeC_ReSeArCh_ObJeCtS"')
        else:
            conn.execute("CREATE TABLE external(sha TEXT)")
            conn.execute('CREATE TRIGGER external_update AFTER INSERT ON external BEGIN '
                         'DELETE FROM "SeC_ReSeArCh_ObJeCtS" WHERE sha256=NEW.sha; END')
    before = snapshot(a)
    assert preview(a)["status"] == "blocked"
    assert snapshot(a) == before


def test_backup_failure_precedes_any_drop_and_can_retry(admin, monkeypatch):
    a = admin
    a.captures.put(b"backup source")
    p = preview(a)
    operations = api("operations")
    before = snapshot(a)

    def fail(*args, **kwargs):
        raise OSError("fixture backup failure")

    with monkeypatch.context() as patch:
        patch.setattr(operations, "backup_market_db", fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "prepared", result
    assert snapshot(a) == before
    assert not (a.tmp / "backup" / "raw-backup.json").exists()
    assert apply(a, preview(a), "retry.json", "retry-backup")["status"] == "ok"


def test_schema_rechecks_after_backup(admin, monkeypatch):
    a = admin
    a.captures.put(b"source")
    p = preview(a)
    module = api("schema_admin")
    backup = module.raw_backup

    def change(*args, **kwargs):
        result = backup(*args, **kwargs)
        with a.store.connect() as conn:
            conn.execute("INSERT INTO sec_research_reservations VALUES('changed',1)")
        return result

    monkeypatch.setattr(module, "raw_backup", change)
    result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "backed_up", result
    with a.store.connect(readonly=True) as conn:
        schema.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM sec_research_objects").fetchone()[0] == 1


def test_schema_transaction_failure_restores_original_and_audit_survives(admin, monkeypatch):
    a = admin
    a.captures.put(b"source")
    p = preview(a)
    module = api("schema_admin")
    drop = module._drop_owned
    before = snapshot(a)

    def fail(*args):
        drop(*args)
        raise sqlite3.OperationalError("fixture failure after DROP")

    with monkeypatch.context() as patch:
        patch.setattr(module, "_drop_owned", fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "backed_up", result
    assert snapshot(a) == before
    assert json.loads((a.tmp / "receipt.json").read_text())["status"] == "blocked"
    assert (a.tmp / "backup" / "raw-backup.json").exists()
    assert apply(a, preview(a), "retry.json", "retry-backup")["status"] == "ok"


def test_schema_receipt_failure_after_commit_keeps_backup_and_charges(admin, monkeypatch):
    a = admin
    a.captures.put(b"retained")
    p = preview(a)
    operations = api("operations")
    write = operations.OperationReceipt.write

    def fail(self, result):
        if result["phase"] == "schema_committed":
            raise OSError("fixture receipt failure after commit")
        return write(self, result)

    with monkeypatch.context() as patch:
        patch.setattr(operations.OperationReceipt, "write", fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "schema_committed", result
    assert result["receipt_phase"] == "backed_up"
    with a.store.connect(readonly=True) as conn:
        schema.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM sec_research_objects").fetchone()[0] == 0
    assert a.captures.status()["charged_bytes"] == 8
    assert (a.tmp / "backup" / "raw-backup.json").exists()
    assert preview(a)["status"] == "ready"


def test_schema_reset_cannot_erase_unresolved_absent_file_charge(admin, monkeypatch):
    import os

    a = admin
    with a.store.connect() as conn:
        conn.execute("INSERT INTO sec_research_orphans VALUES(?,18)", ("objects/" + "a" * 64,))
    p = preview(a)
    inode = (a.paths.capture_root / "objects").stat().st_ino
    fsync = os.fsync

    def fail(fd):
        if os.fstat(fd).st_ino == inode:
            raise OSError("fixture unresolved directory fsync")
        return fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "backed_up", result
    assert a.captures.status()["charged_bytes"] == 18
    assert apply(a, preview(a), "retry.json", "retry-backup")["status"] == "ok"


@pytest.mark.parametrize("mode", ["reset", "uninstall"])
def test_schema_reset_accepts_known_definition_mismatch_not_a_legacy_lane(admin, mode):
    a = admin
    a.captures.put(b"retained")
    with a.store.connect() as conn:
        conn.execute("ALTER TABLE sec_research_facts ADD COLUMN fixture_unknown TEXT")
    p = preview(a, mode)
    assert p["status"] == "ready" and p["schema_status"] == "mismatch", json.dumps(p)
    assert apply(a, p)["status"] == "ok"


def test_schema_final_receipt_failure_reports_committed_schema_not_completion(admin, monkeypatch):
    a = admin
    a.captures.put(b"retained")
    p = preview(a)
    operations = api("operations")
    write = operations.OperationReceipt.write

    def fail(self, result):
        if result["phase"] == "complete":
            raise OSError("fixture final receipt")
        return write(self, result)

    monkeypatch.setattr(operations.OperationReceipt, "write", fail)
    result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "schema_committed", result
    assert result["recovery"] != "none"
    assert a.captures.status()["charged_bytes"] == 8


@pytest.mark.parametrize("stage", ["capture", "receipt", "backup"])
def test_schema_expensive_io_allows_ordinary_market_writer(admin, market_writer, monkeypatch, stage):
    a = admin
    a.captures.put(b"retained")
    p = preview(a)
    operations = api("operations")
    target, name = {"capture": (api("capture_lock").CaptureDirectory, "inspect_owned"),
                    "receipt": (operations.OperationReceipt, "write"),
                    "backup": (operations, "backup_market_db")}[stage]
    original, writes = getattr(target, name), []

    def barrier(*args, **kwargs):
        writes.append(market_writer())
        assert writes[-1] == "written", (stage, writes)
        return original(*args, **kwargs)

    monkeypatch.setattr(target, name, barrier)
    result = apply(a, p)
    assert result["status"] == "ok", result
    assert writes and all(value == "written" for value in writes)
    with a.store.connect(readonly=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == len(writes)


def test_schema_database_mutation_excludes_ordinary_writer(admin, market_writer, monkeypatch):
    a, module = admin, api("schema_admin")
    a.captures.put(b"retained")
    p, original = preview(a), module._drop_owned
    observed = []

    def barrier(*args):
        observed.append((market_writer(), market_writer(False)))
        return original(*args)

    monkeypatch.setattr(module, "_drop_owned", barrier)
    assert apply(a, p)["status"] == "ok"
    assert observed == [("market_locked", "database_locked")]
