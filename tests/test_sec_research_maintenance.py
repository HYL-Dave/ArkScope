"""Explicit cleanup over disposable stores, including interrupted durability."""

from contextlib import closing, contextmanager
from concurrent.futures import ThreadPoolExecutor
import importlib
import importlib.util
import json
import os
import sqlite3
from types import SimpleNamespace

import pytest

from src.sec_research import schema
from src.sec_research.capture_lock import CaptureDirectory, research_operation
from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store
from tests.test_sec_research_citations import evidence, publish_facts, rig
from tests.test_sec_research_references import profile


def api(name="maintenance"):
    module = "src.sec_research." + name
    assert importlib.util.find_spec(module), "missing explicit SEC " + name + " owner"
    return importlib.import_module(module)


@pytest.fixture
def admin(tmp_path):
    paths = SecResearchPaths(tmp_path / "market.db")
    store = Store(paths)
    store.install()
    CaptureDirectory(paths.capture_root, create=True).close()
    captures = CaptureStore(store, budget=lambda: 10**8)
    profile_path = tmp_path / "profile.db"
    with sqlite3.connect(profile_path) as conn:
        conn.execute("CREATE TABLE profile_settings(key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO profile_settings VALUES('fixture', 'retained')")
    with closing(sqlite3.connect(profile_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        yield SimpleNamespace(paths=paths, store=store, captures=captures,
                              profile=conn, profile_path=profile_path, tmp=tmp_path)


def preview(a):
    return api().preview_cleanup(a.paths, profile_connection=a.profile)


def apply(a, p, name="receipt.json", **kwargs):
    return api().apply_cleanup(a.paths, p, approval_sha256=p["approval_sha256"],
        receipt_path=a.tmp / name, profile_connection=a.profile, **kwargs)


def snapshot(a):
    with a.store.connect(readonly=True) as conn:
        rows = list(conn.iterdump())
    files = {str(p.relative_to(a.paths.capture_root)): p.read_bytes()
             for p in a.paths.capture_root.rglob("*") if p.is_file()}
    return rows, files


def assert_profile_writable(a):
    error = None
    try:
        with sqlite3.connect(a.profile_path, timeout=0) as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            conn.execute("UPDATE profile_settings SET value='ordinary profile write' WHERE key='fixture'")
    except sqlite3.Error as exc:
        error = type(exc).__name__
    assert error is None, ("operator output broke the profile writer", error)
    assert a.profile.execute("SELECT value FROM profile_settings WHERE key='fixture'").fetchone()[0] == "ordinary profile write"


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_cleanup_receipt_rejects_profile_sqlite_namespace(admin, suffix):
    a = admin
    a.captures.put(b"retained")
    before, p = snapshot(a), preview(a)
    destination = a.profile_path.with_name(a.profile_path.name + suffix)
    result = apply(a, p, str(destination))
    created = bool(suffix) and destination.exists()
    assert_profile_writable(a)
    assert not created, result
    assert result["status"] == "blocked" and result["phase"] == "not_started", result
    assert snapshot(a) == before


@pytest.fixture
def market_writer(admin, monkeypatch):
    from src.market_data_direct import market_write_lock

    a = admin
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(a.tmp / "ordinary-locks"))
    with a.store.connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE news(value TEXT)")

    def write(locked):
        try:
            if locked:
                with market_write_lock(timeout=0):
                    return write(False)
            with sqlite3.connect(a.paths.market_db_path, timeout=0) as conn:
                conn.execute("INSERT INTO news VALUES('ongoing ingest')")
            return "written"
        except TimeoutError:
            return "market_locked"
        except sqlite3.OperationalError:
            return "database_locked"

    with ThreadPoolExecutor(max_workers=1) as pool:
        yield lambda locked=True: pool.submit(write, locked).result(timeout=5)


@pytest.fixture
def failure_audit_barrier(admin, market_writer, monkeypatch):
    a = admin

    def observe(module):
        events, audits = [], []
        operation = module.research_operation
        write = api("operations").OperationReceipt.write

        @contextmanager
        def lease(*args, **kwargs):
            with operation(*args, **kwargs):
                events.append("entered")
                try:
                    yield
                finally:
                    events.append("exiting")

        def enter_sec():
            try:
                with research_operation(a.paths.capture_root):
                    return "admitted"
            except ValueError as exc:
                return str(exc)

        def audit(self, result):
            if result["status"] == "blocked" and result["code"] is not None:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    sec = pool.submit(enter_sec).result(timeout=5)
                market = market_writer()
                audits.append((result["phase"], sec, market))
                assert events == ["entered"], ("original SEC lease exited before failure audit", events)
                assert sec == "sec_research_operation_busy", audits
                assert market == "written", audits
            return write(self, result)

        monkeypatch.setattr(module, "research_operation", lease)
        monkeypatch.setattr(api("operations").OperationReceipt, "write", audit)
        return events, audits

    return observe


@pytest.mark.parametrize("stage,phase", [("unlink", "charged"), ("transaction", "prepared")])
def test_cleanup_failure_audit_keeps_original_exclusive_lease(admin, failure_audit_barrier, monkeypatch, stage, phase):
    a, module = admin, api()
    sha = a.captures.put(b"retained")
    p = preview(a)
    events, audits = failure_audit_barrier(module)
    delete = module._delete_registered

    def fail(*args):
        if stage == "transaction":
            delete(*args)
        raise OSError("fixture failed cleanup stage")

    if stage == "unlink":
        monkeypatch.setattr(CaptureDirectory, "remove_owned", fail)
    else:
        monkeypatch.setattr(module, "_delete_registered", fail)
    result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == phase, result
    assert audits == [(phase, "sec_research_operation_busy", "written")]
    assert events == ["entered", "exiting"]
    assert json.loads((a.tmp / "receipt.json").read_text())["phase"] == phase
    assert (a.paths.capture_root / "objects" / sha).read_bytes() == b"retained"
    assert a.captures.status()["charged_bytes"] == 8


@pytest.mark.parametrize("operation", ["cleanup", "schema"])
def test_admin_admission_failure_has_no_lease_or_audit(admin, failure_audit_barrier, operation):
    a = admin
    module = api() if operation == "cleanup" else api("schema_admin")
    p = preview(a) if operation == "cleanup" else module.preview_schema_reset(a.paths, mode="reset", profile_connection=a.profile)
    events, audits = failure_audit_barrier(module)
    p["approval_sha256"] = "0" * 64
    if operation == "cleanup":
        result = apply(a, p)
    else:
        result = module.apply_schema_reset(a.paths, p, approval_sha256=p["approval_sha256"],
            receipt_path=a.tmp / "receipt.json", backup_path=a.tmp / "backup", profile_connection=a.profile)
    assert result["status"] == "blocked" and result["phase"] == result["receipt_phase"] == "not_started"
    assert events == audits == []
    assert not (a.tmp / "receipt.json").exists() and not (a.tmp / "backup").exists()


@pytest.mark.parametrize("stage", ["capture", "unlink", "receipt"])
def test_cleanup_expensive_io_allows_ordinary_market_writer(admin, market_writer, monkeypatch, stage):
    a = admin
    a.captures.put(b"orphan")
    p = preview(a)
    target, name = ((api("operations").OperationReceipt, "write") if stage == "receipt" else
                    (CaptureDirectory, "inspect_owned" if stage == "capture" else "remove_owned"))
    original = getattr(target, name)
    writes = []

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


def test_cleanup_database_mutation_excludes_ordinary_writer(admin, market_writer, monkeypatch):
    a, module = admin, api()
    a.captures.put(b"orphan")
    p, original = preview(a), module._delete_registered
    observed = []

    def barrier(*args):
        observed.append((market_writer(), market_writer(False)))
        return original(*args)

    monkeypatch.setattr(module, "_delete_registered", barrier)
    assert apply(a, p)["status"] == "ok"
    assert observed == [("market_locked", "database_locked")]


def test_cleanup_preserves_every_retained_reference_class(evidence, profile, tmp_path):
    r = evidence.rig
    runs, threads = profile
    threads.append_message(thread_id="roots", role="assistant", content="historical",
        tool_calls=[{"name": "get_sec_financial_facts", "sec_citations": [evidence.fact_ref]}])
    runs.append_event("roots-run", "tool_end", {"tool": "read_sec_filing",
        "sec_citations": [evidence.document_ref]})
    runs.mark_terminal("roots-run", "interrupted", error_code="run_interrupted")
    threads.set_thread_archived("roots", archived=True)
    publish_facts(r, "88")
    raw = b'{"0":{"cik_str":320193,"ticker":"AAPL","title":"Fixture"}}'
    sha = r.captures.put(raw)
    with r.store.connect() as conn:
        conn.execute("INSERT INTO sec_research_issuer_maps(status,object_sha256,observed_at,source_url,symbols,gaps) "
            "VALUES('ok',?,'2026-09-12T12:00:00Z','https://www.sec.gov/files/company_tickers.json',?, '[]')",
            (sha, json.dumps({"AAPL": ["0000320193"]})))
    orphan = r.captures.put(b"registered but never published")
    with closing(sqlite3.connect(runs.db_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        a = SimpleNamespace(paths=r.store.paths, store=r.store, profile=conn, tmp=tmp_path)
        before = snapshot(a)
        p = preview(a)
        assert p["status"] == "ready", p
        assert [c["key"] for c in p["candidates"]] == ["objects/" + orphan]
        result = apply(a, p)
        assert result["status"] == "ok", result
        after = snapshot(a)
        assert after[1] == {k: v for k, v in before[1].items() if k != "objects/" + orphan}
        with r.store.connect(readonly=True) as check:
            for table in schema._TABLES:
                if table not in {"sec_research_objects", "sec_research_orphans", "sec_research_reservations"}:
                    assert [s for s in before[0] if s.startswith('INSERT INTO "' + table + '"')] == [
                        s for s in after[0] if s.startswith('INSERT INTO "' + table + '"')]
            schema.verify(check)


def test_new_reference_invalidates_cleanup_preview(evidence, profile, tmp_path):
    runs, _ = profile
    r = evidence.rig
    sha = r.captures.put(b"unpublished")
    with closing(sqlite3.connect(runs.db_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        a = SimpleNamespace(paths=r.store.paths, store=r.store, profile=conn, tmp=tmp_path)
        p = preview(a)
        assert p["status"] == "ready", p
        runs.append_event("roots-run", "tool_end", {"tool": "read_sec_filing",
            "sec_citations": [evidence.document_ref]})
        result = apply(a, p)
        assert result["status"] == "blocked", result
        assert result["code"] == "sec_research_preview_stale"
        assert r.captures.read(sha) == b"unpublished"


def test_stale_caller_read_transaction_is_not_a_fresh_recheck(evidence, profile, tmp_path):
    runs, _ = profile
    r = evidence.rig
    sha = r.captures.put(b"unpublished")
    with closing(sqlite3.connect(runs.db_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        a = SimpleNamespace(paths=r.store.paths, store=r.store, profile=conn, tmp=tmp_path)
        p = preview(a)
        conn.execute("BEGIN")
        assert conn.execute("SELECT COUNT(*) FROM research_run_events").fetchone()[0] == 0
        runs.append_event("roots-run", "tool_end", {"tool": "read_sec_filing",
            "sec_citations": [evidence.document_ref]})
        result = apply(a, p)
        assert result["status"] == "blocked", result
        assert conn.in_transaction, "maintenance must not end the caller's transaction"
        assert r.captures.read(sha) == b"unpublished"


def test_unfinished_autocommit_cursor_is_not_a_fresh_profile_snapshot(evidence, profile, tmp_path):
    runs, _ = profile
    r = evidence.rig
    sha = r.captures.put(b"unpublished")
    for _ in range(3):
        runs.append_event("roots-run", "thinking", {"text": "legacy"})
    with closing(sqlite3.connect(runs.db_path, isolation_level=None)) as conn:
        conn.execute("PRAGMA query_only=ON")
        a = SimpleNamespace(paths=r.store.paths, store=r.store, profile=conn, tmp=tmp_path)
        p = preview(a)
        cursor = conn.execute("SELECT data_json FROM research_run_events")
        assert cursor.fetchone() and not conn.in_transaction
        runs.append_event("roots-run", "tool_end", {"tool": "read_sec_filing",
            "sec_citations": [evidence.document_ref]})
        result = apply(a, p)
        assert result["status"] == "blocked", json.dumps(result)
        assert r.captures.read(sha) == b"unpublished"
        assert cursor.fetchone(), "caller-owned cursor remains usable"
        cursor.close()


def test_registered_orphan_unlink_failure_remains_charged(admin, monkeypatch):
    a = admin
    sha = a.captures.put(b"failed unlink")
    p = preview(a)
    unlink = os.unlink

    def fail(name, *args, **kwargs):
        if name == sha:
            with a.store.connect(readonly=True) as conn:
                assert conn.execute("SELECT COUNT(*) FROM sec_research_objects").fetchone()[0] == 0
                charge = conn.execute("SELECT size_bytes FROM sec_research_orphans").fetchone()
                assert charge is not None and charge[0] == 13
            raise PermissionError("fixture unlink failure")
        return unlink(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "unlink", fail)
        result = apply(a, p)
    assert result["status"] == "blocked", result
    assert result["phase"] == "charged"
    assert result["freed_bytes"] == 0 and result["remaining"] == ["objects/" + sha]
    assert a.captures.recover()["charged_bytes"] == 13
    retry = apply(a, preview(a), "retry.json")
    assert retry["status"] == "ok" and retry["freed_bytes"] == 13
    assert a.captures.status()["charged_bytes"] == 0


def test_failed_directory_durability_charge_survives_ordinary_recovery(admin, monkeypatch):
    a = admin
    sha = a.captures.put(b"pending durability")
    path = a.paths.capture_root / "objects" / sha
    parent_inode = path.parent.stat().st_ino
    p = preview(a)
    fsync = os.fsync

    def fail(fd):
        if os.fstat(fd).st_ino == parent_inode and not path.exists():
            raise OSError("fixture directory fsync failure")
        return fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail)
        result = apply(a, p)
        assert result["status"] == "blocked" and result["freed_bytes"] == 0, result
        assert result["phase"] == "charged"
        try:
            a.captures.recover()
        except ValueError:
            pass
        assert a.captures.status()["charged_bytes"] == 18
    assert a.captures.recover()["charged_bytes"] == 0


def test_recovery_cannot_clear_absent_charge_without_directory_sync(admin, monkeypatch):
    a = admin
    with a.store.connect() as conn:
        conn.execute("INSERT INTO sec_research_orphans VALUES(?,18)", ("objects/" + "a" * 64,))
    inode = (a.paths.capture_root / "objects").stat().st_ino
    fsync = os.fsync

    def fail(fd):
        if os.fstat(fd).st_ino == inode:
            raise OSError("fixture unresolved directory durability")
        return fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail)
        try:
            a.captures.recover()
        except ValueError:
            pass
        assert a.captures.status()["charged_bytes"] == 18
    assert a.captures.recover()["charged_bytes"] == 0


def test_cleanup_restores_immutability_after_rollback(admin, monkeypatch):
    a = admin
    sha = a.captures.put(b"rollback")
    p = preview(a)
    module = api()
    delete = module._delete_registered

    def fail(*args):
        delete(*args)
        raise sqlite3.IntegrityError("fixture after delete")

    with monkeypatch.context() as patch:
        patch.setattr(module, "_delete_registered", fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "prepared", result
    assert a.captures.read(sha) == b"rollback"
    with a.store.connect() as conn:
        schema.verify(conn)
        with pytest.raises(sqlite3.IntegrityError, match="sec_research_immutable"):
            conn.execute("DELETE FROM sec_research_objects")
    assert apply(a, preview(a), "retry.json")["status"] == "ok"


def test_maintenance_preview_is_observational(admin, monkeypatch):
    a = admin
    a.captures.put(b"unpublished")
    (a.paths.capture_root / "staging" / ("a" * 32)).write_bytes(b"staged")
    before = snapshot(a)
    monkeypatch.setattr(CaptureStore, "recover", lambda *_: pytest.fail("preview recovered"))
    monkeypatch.setattr(CaptureStore, "_recover", lambda *_: pytest.fail("preview recovered"))
    result = preview(a)
    assert result["status"] == "ready", result
    assert {c["kind"] for c in result["candidates"]} == {"registered", "staging"}
    assert snapshot(a) == before
    assert not list(a.tmp.glob("*receipt*")) and not a.profile.in_transaction
    assert a.profile.execute("SELECT name FROM sqlite_master WHERE name LIKE 'research_%'").fetchall() == []


@pytest.mark.parametrize("damage", ["missing_root", "missing_child", "unknown_root", "symlink", "hardlink", "unknown_key"])
def test_cleanup_blocks_unsafe_or_ambiguous_file_inventory(admin, damage):
    a = admin
    root = a.paths.capture_root
    if damage == "missing_root":
        (root / "objects").rmdir()
        (root / "staging").rmdir()
        root.rmdir()
    elif damage == "missing_child":
        (root / "staging").rmdir()
    elif damage == "unknown_root":
        (root / "unknown").write_bytes(b"retained")
    elif damage == "symlink":
        (root / "objects" / ("a" * 64)).symlink_to(a.profile_path)
    elif damage == "hardlink":
        sha = a.captures.put(b"linked")
        os.link(root / "objects" / sha, root / "staging" / ("a" * 32))
    else:
        (root / "objects" / "a").write_bytes(b"unknown")
    assert preview(a)["status"] == "blocked"
    if damage == "missing_root":
        assert not root.exists()


@pytest.mark.parametrize("damage", ["partial", "corrupt_json", "not_query_only"])
def test_profile_roots_fail_closed(admin, damage):
    a = admin
    if damage == "not_query_only":
        a.profile.execute("PRAGMA query_only=OFF")
    else:
        with sqlite3.connect(a.profile_path) as conn:
            conn.execute("CREATE TABLE research_messages(id INTEGER, tool_calls_json TEXT)")
            if damage == "corrupt_json":
                conn.execute("CREATE TABLE research_run_events(run_id TEXT, seq INTEGER, data_json TEXT)")
                conn.execute("INSERT INTO research_messages VALUES(1, '{')")
    assert preview(a)["status"] == "blocked"


def test_unrelated_market_rows_do_not_invalidate_approval(admin):
    a = admin
    sha = a.captures.put(b"selected")
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE news(id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT)")
    p = preview(a)
    assert p["status"] == "ready", json.dumps(p)
    with a.store.connect() as conn:
        conn.execute("INSERT INTO news(body) VALUES('independent arrival')")
    result = apply(a, p)
    assert result["status"] == "ok", json.dumps(result)
    assert result["removed"] == ["objects/" + sha]
    with a.store.connect(readonly=True) as conn:
        assert conn.execute("SELECT body FROM news").fetchone()[0] == "independent arrival"


@pytest.mark.parametrize("target", ["sec_research_objects", "SeC_ReSeArCh_ObJeCtS"])
def test_cleanup_external_cascade_cannot_delete_unrelated_rows(admin, target):
    a = admin
    sha = a.captures.put(b"external reference")
    with a.store.connect() as conn:
        conn.execute(f'CREATE TABLE unrelated(sha TEXT REFERENCES "{target}"(sha256) ON DELETE CASCADE)')
        conn.execute("INSERT INTO unrelated VALUES(?)", (sha,))
    p = preview(a)
    assert p["status"] == "blocked", p
    with a.store.connect(readonly=True) as conn:
        assert conn.execute("SELECT sha FROM unrelated").fetchone()[0] == sha
    assert a.captures.read(sha) == b"external reference"


def test_cleanup_requires_fresh_exclusive_lease(admin):
    a = admin
    sha = a.captures.put(b"reader protected")
    p = preview(a)
    with research_operation(a.paths.capture_root):
        result = apply(a, p)
    assert result["status"] == "blocked" and result["code"] == "sec_research_operation_busy", result
    assert a.captures.read(sha) == b"reader protected"


@pytest.mark.parametrize("damage", ["digest", "extra_field", "existing_receipt"])
def test_cleanup_approval_and_receipt_are_create_only(admin, damage):
    a = admin
    sha = a.captures.put(b"not approved")
    p = preview(a)
    if damage == "digest":
        p["approval_sha256"] = "0" * 64
    elif damage == "extra_field":
        p["auto_confirm"] = True
    else:
        (a.tmp / "receipt.json").write_bytes(b"retain receipt")
    assert apply(a, p)["status"] == "blocked"
    assert a.captures.read(sha) == b"not approved"
    if damage == "existing_receipt":
        assert (a.tmp / "receipt.json").read_bytes() == b"retain receipt"


def test_cleanup_colocated_empty_research_roots_use_query_only_snapshot(admin):
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore

    a = admin
    a.captures.put(b"colocated")
    ResearchThreadStore(a.paths.market_db_path)
    ResearchRunStore(a.paths.market_db_path)
    with closing(sqlite3.connect(a.paths.market_db_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        a.profile = conn
        p = preview(a)
        assert p["status"] == "ready", json.dumps(p)
        result = apply(a, p)
        assert result["status"] == "ok", json.dumps(result)
        assert conn.execute("SELECT COUNT(*) FROM research_messages").fetchone()[0] == 0


@pytest.mark.parametrize("value", [None, [], "unknown", {"auto_confirm": True}])
def test_malformed_apply_input_blocks_without_io(admin, value):
    a = admin
    before = snapshot(a)
    try:
        result = api().apply_cleanup(a.paths, value, approval_sha256="0" * 64,
                                    receipt_path=a.tmp / "receipt.json", profile_connection=a.profile)
    except AttributeError:
        result = {"status": "escaped_exception"}
    assert result["status"] == "blocked"
    assert snapshot(a) == before and not (a.tmp / "receipt.json").exists()


def test_receipt_cannot_occupy_sqlite_journal(admin):
    a = admin
    a.captures.put(b"journal protected")
    p = preview(a)
    result = apply(a, p, a.paths.market_db_path.name + "-journal")
    assert result["status"] == "blocked" and result["phase"] == "not_started", json.dumps(result)
    assert a.captures.status()["persisted_bytes"] == 17


@pytest.mark.parametrize("phase,receipt_phase,exists", [
    ("charged", "prepared", True), ("files_removed", "charged", False),
])
def test_cleanup_receipt_failure_reports_last_durable_resource_phase(admin, monkeypatch, phase, receipt_phase, exists):
    a = admin
    sha = a.captures.put(b"receipt interruption")
    p = preview(a)
    operations = api("operations")
    write = operations.OperationReceipt.write

    def fail(self, result):
        if result["phase"] == phase:
            raise OSError("fixture receipt write failure")
        return write(self, result)

    with monkeypatch.context() as patch:
        patch.setattr(operations.OperationReceipt, "write", fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == phase, result
    assert result["receipt_phase"] == receipt_phase
    assert json.loads((a.tmp / "receipt.json").read_text())["phase"] == receipt_phase
    assert (a.paths.capture_root / "objects" / sha).exists() is exists
    assert a.captures.status()["charged_bytes"] == 20
    assert a.captures.recover()["charged_bytes"] == (20 if exists else 0)
    assert apply(a, preview(a), "retry.json")["status"] == "ok"


def test_cleanup_cancellation_after_charge_is_explicitly_resumable(admin, monkeypatch):
    a = admin
    a.captures.put(b"cancel")
    p = preview(a)

    def cancel(*_):
        raise KeyboardInterrupt()

    with monkeypatch.context() as patch:
        patch.setattr(CaptureDirectory, "remove_owned", cancel)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "charged", result
    assert result["code"] == "sec_research_admin_interrupted"
    assert a.captures.recover()["charged_bytes"] == 6
    assert apply(a, preview(a), "retry.json")["status"] == "ok"


@pytest.mark.parametrize("damage", ["receipt", "object", "profile_json"])
def test_corrupt_retained_reference_never_becomes_empty(evidence, profile, tmp_path, damage):
    from tests.test_sec_research_references import corrupt_row

    runs, _ = profile
    r = evidence.rig
    r.captures.put(b"must not sweep")
    if damage == "receipt":
        corrupt_row(r.store, "receipts", "UPDATE sec_research_receipts SET source_snapshots=?", ("{}",))
    elif damage == "object":
        (r.store.paths.capture_root / "objects" / evidence.fact_ref["source_sha256"]).write_bytes(b"damaged")
    else:
        runs.append_event("roots-run", "tool_end", {"tool": "read_sec_filing", "sec_citations": [evidence.document_ref]})
        with sqlite3.connect(runs.db_path) as conn:
            conn.execute("UPDATE research_run_events SET data_json='{' ")
    with closing(sqlite3.connect(runs.db_path)) as conn:
        conn.execute("PRAGMA query_only=ON")
        a = SimpleNamespace(paths=r.store.paths, store=r.store, profile=conn, tmp=tmp_path)
        p = preview(a)
        assert p["status"] == "blocked", json.dumps(p)
        assert apply(a, p)["status"] == "blocked"


def test_changed_capture_identity_invalidates_approval(admin):
    a = admin
    sha = a.captures.put(b"same contents")
    p = preview(a)
    original = a.paths.capture_root / "objects" / sha
    temporary = a.tmp / "replacement"
    temporary.write_bytes(original.read_bytes())
    temporary.replace(original)
    result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "not_started", result
    assert a.captures.read(sha) == b"same contents"


def test_explicit_cleanup_retry_resolves_absent_charge_only_after_directory_sync(admin, monkeypatch):
    a = admin
    key = "objects/" + "a" * 64
    with a.store.connect() as conn:
        conn.execute("INSERT INTO sec_research_orphans VALUES(?,18)", (key,))
    p = preview(a)
    assert [(c["key"], c["kind"]) for c in p["candidates"]] == [(key, "absent_charge")]
    inode = (a.paths.capture_root / "objects").stat().st_ino
    fsync = os.fsync

    def fail(fd):
        if os.fstat(fd).st_ino == inode:
            raise OSError("fixture directory sync")
        return fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail)
        result = apply(a, p)
    assert result["status"] == "blocked" and result["remaining"] == [key]
    assert a.captures.status()["charged_bytes"] == 18
    result = apply(a, preview(a), "retry.json")
    assert result["status"] == "ok" and result["freed_bytes"] == 0
    assert result["resolved_charges"] == [key] and result["removed"] == []
    assert a.captures.status()["charged_bytes"] == 0


def test_cleanup_final_receipt_failure_does_not_claim_durable_completion(admin, monkeypatch):
    a = admin
    a.captures.put(b"final receipt")
    p = preview(a)
    operations = api("operations")
    write = operations.OperationReceipt.write

    def fail(self, result):
        if result["phase"] == "complete":
            raise OSError("fixture final receipt")
        return write(self, result)

    monkeypatch.setattr(operations.OperationReceipt, "write", fail)
    result = apply(a, p)
    assert result["status"] == "blocked" and result["phase"] == "files_removed", result
    assert result["recovery"] != "none"
    assert result["freed_bytes"] == 13 and a.captures.status()["charged_bytes"] == 0


@pytest.mark.parametrize("operation", ["cleanup", "schema"])
def test_first_receipt_failure_never_claims_a_durable_prepared_phase(admin, monkeypatch, operation):
    a = admin
    a.captures.put(b"unmodified")
    module = api("schema_admin") if operation == "schema" else api()
    p = module.preview_schema_reset(a.paths, mode="reset", profile_connection=a.profile) if operation == "schema" else preview(a)
    before = snapshot(a)

    def fail(*_):
        raise OSError("fixture first audit write")

    monkeypatch.setattr(api("operations").OperationReceipt, "write", fail)
    kwargs = dict(approval_sha256=p["approval_sha256"], receipt_path=a.tmp / "receipt.json", profile_connection=a.profile)
    result = module.apply_schema_reset(a.paths, p, backup_path=a.tmp / "backup", **kwargs) if operation == "schema" else module.apply_cleanup(a.paths, p, **kwargs)
    assert result["status"] == "blocked" and result["phase"] == "not_started", result
    assert result["receipt_phase"] == "not_started"
    assert snapshot(a) == before and not (a.tmp / "backup").exists()


def test_invalid_preview_headers_are_not_echoed_in_receipts(admin):
    a = admin
    p = {"operation": {"url": "PRIVATE"}, "mode": "PRIVATE", "approval_sha256": "PRIVATE"}
    result = api().apply_cleanup(a.paths, p, approval_sha256="0" * 64,
        receipt_path=a.tmp / "receipt.json", profile_connection=a.profile)
    assert result["status"] == "blocked"
    assert "PRIVATE" not in json.dumps(result)
