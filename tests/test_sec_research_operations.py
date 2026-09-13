"""Operation exclusion and portable bundles over disposable, offline stores."""

import asyncio
import errno
import hashlib
import importlib.util
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from contextvars import copy_context

import pytest

from src.sec_research import capture_lock
from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.queries import StoredQueries
from src.sec_research.service import ResearchService
from src.sec_research.store import Store
from tests.test_sec_research_service import CIK, NOW, Transport
from tests.test_sec_research_citations import evidence, rig, publish_facts
from tests.test_sec_research_trace import trace_stores


def operation(root, **kwargs):
    # Before Task5 the real producer permits maintenance in this gap.
    return getattr(capture_lock, "research_operation", lambda *a, **k: nullcontext())(root, **kwargs)


def admission(root, *, exclusive=True):
    try:
        with operation(root, exclusive=exclusive):
            return "entered"
    except ValueError as exc:
        return str(exc)


def other_owner(root, *, exclusive=True):
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(admission, root, exclusive=exclusive).result(timeout=5)


@pytest.fixture
def store(tmp_path):
    result = Store(SecResearchPaths.from_market_db(tmp_path / "market.db"))
    result.install()
    return result


def test_maintenance_cannot_enter_put_to_publish_gap(store, monkeypatch):
    captures = CaptureStore(store, budget=lambda: 1024**2, free_bytes=lambda _: 1024**3)
    put = captures.put
    admissions = []

    def paused_put(body):
        sha = put(body)
        admissions.append(other_owner(store.paths.capture_root))
        return sha

    monkeypatch.setattr(captures, "put", paused_put)
    receipt = ResearchService(store, captures, Transport(), clock=lambda: NOW).refresh(CIK)
    assert receipt["status"] == "ok"
    assert admissions == ["sec_research_operation_busy"] * 3
    assert other_owner(store.paths.capture_root) == "entered"


def test_stored_reader_lease_does_not_create_capture_root(store, monkeypatch):
    original = store.latest_receipt
    admissions = []

    def paused_receipt(cik):
        result = original(cik)
        admissions.append(other_owner(store.paths.capture_root))
        return result

    monkeypatch.setattr(store, "latest_receipt", paused_receipt)
    assert StoredQueries(store).filings(CIK)["status"] == "unavailable"
    assert admissions == ["sec_research_operation_busy"]
    assert not store.paths.capture_root.exists()


def test_capture_read_retains_lease_through_bytes(store, monkeypatch):
    captures = CaptureStore(store, budget=lambda: 1024**2, free_bytes=lambda _: 1024**3)
    sha = captures.put(b"retained bytes")
    original = capture_lock.CaptureDirectory.read
    admissions = []

    def read(directory, key, size):
        admissions.append(other_owner(store.paths.capture_root))
        return original(directory, key, size)

    monkeypatch.setattr(capture_lock.CaptureDirectory, "read", read)
    assert captures.read(sha) == b"retained bytes"
    assert admissions == ["sec_research_operation_busy"]


def test_operation_reentrancy_is_thread_and_task_owned(tmp_path):
    root = tmp_path / "missing"
    with operation(root, exclusive=True):
        assert admission(root) == "entered"
        context = copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(context.run, admission, root).result(timeout=5) == "sec_research_operation_busy"

    async def scenario():
        with operation(root, exclusive=True):
            assert admission(root, exclusive=False) == "entered"

            async def child():
                return admission(root, exclusive=False)

            assert await asyncio.create_task(child()) == "sec_research_operation_busy"

    asyncio.run(scenario())
    assert other_owner(root) == "entered"
    assert not root.exists()


def test_shared_operations_coexist_but_never_upgrade(tmp_path):
    root = tmp_path / "missing"
    with operation(root):
        assert admission(root, exclusive=False) == "entered"
        assert other_owner(root, exclusive=False) == "entered"
        assert admission(root) == "sec_research_operation_busy"
        assert other_owner(root) == "sec_research_operation_busy"
    assert other_owner(root) == "entered"


def test_operation_exception_releases_and_rejects_unsafe_root(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(RuntimeError):
        with operation(root):
            raise RuntimeError("interrupted")
    assert other_owner(root) == "entered"
    root.symlink_to(tmp_path / "outside", target_is_directory=True)
    assert admission(root) == "capture_path_unsafe"


def test_operation_unsupported_platform_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_lock, "_supported", lambda: False)
    assert admission(tmp_path / "root") == "capture_platform_unsupported"


def test_stale_copied_context_cannot_reuse_released_lease(tmp_path):
    root = tmp_path / "missing"
    with operation(root, exclusive=True):
        stale = copy_context()

    def resumed():
        with operation(root):
            return other_owner(root)

    assert stale.run(resumed) == "sec_research_operation_busy"


@pytest.mark.parametrize("sink", ["message", "event", "terminal"])
def test_direct_reference_publication_holds_operation(evidence, trace_stores, monkeypatch, sink):
    runs, threads = trace_stores
    root = evidence.rig.store.paths.capture_root
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: evidence.rig.store.paths)
    target, method = ((threads, "_append_message_on_connection") if sink != "event" else
                      (runs, "_append_event_on_connection"))
    original = getattr(target, method)
    admissions = []

    def commit(*args, **kwargs):
        admissions.append(other_owner(root))
        return original(*args, **kwargs)

    monkeypatch.setattr(target, method, commit)
    if sink == "message":
        threads.append_message(thread_id="trace-thread", role="assistant", content="answer",
            tool_calls=[{"name": "read_sec_filing", "input": {}, "sec_citations": [evidence.document_ref]}])
    elif sink == "event":
        runs.append_event("trace-run", "tool_end", {"tool": "read_sec_filing", "sec_citations": [evidence.document_ref]})
    else:
        runs.terminalize_error_with_message(thread_store=threads, run_id="trace-run", status="failed",
            error="provider failed", error_code="provider_call_failed",
            tool_calls=[{"name": "read_sec_filing", "input": {}, "sec_citations": [evidence.document_ref]}])
    assert admissions == ["sec_research_operation_busy"]


def test_legacy_stream_keeps_result_lease_until_transcript(evidence, trace_stores, monkeypatch):
    from src.api.routes import query
    from src.agents.shared.events import AgentEvent, EventType
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding

    _, threads = trace_stores
    paths = evidence.rig.store.paths
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    monkeypatch.setattr(query, "capture_runtime_auth", lambda _: RuntimeAuthBinding(
        "openai", "db_api_key", "api_key", None, _api_key="offline-key"))
    monkeypatch.setattr(query, "_resolve_query_task_route", lambda *_: ("gpt-5.4-mini", "low"))
    monkeypatch.setattr(query, "_require_live_model_auth", lambda *_: None)
    monkeypatch.setattr(query, "_require_client_compaction_compatibility", lambda *_: None)
    monkeypatch.setattr(query, "_resolve_personalization", lambda _: ("", {}))
    admissions = []

    async def stream(**kwargs):
        admissions.append(other_owner(paths.capture_root))
        yield AgentEvent(EventType.tool_end, {"tool": "read_sec_filing", "call_id": "saved",
            "input": {}, "summary": "preview", "sec_citations": [evidence.document_ref]})
        admissions.append(other_owner(paths.capture_root))
        yield AgentEvent(EventType.done, {"answer": "Answer", "provider": "openai", "model": "gpt-5.4-mini"})

    monkeypatch.setattr(query, "_research_provider_stream", stream)

    async def execute():
        response = await query.query_agent_stream(query.QueryRequest(question="Question", provider="openai",
            thread_id="trace-thread"), dal=object(), store=threads)
        async for _ in response.body_iterator:
            admissions.append(other_owner(paths.capture_root))

    asyncio.run(execute())
    assert len(admissions) == 4
    assert set(admissions) == {"sec_research_operation_busy"}
    assert threads.list_messages("trace-thread")[-1].tool_calls[0]["sec_citations"] == [evidence.document_ref]
    assert other_owner(paths.capture_root) == "entered"


@pytest.mark.parametrize("terminal", ["success", "error", "cancel"])
def test_research_result_lease_reaches_durable_commit(evidence, trace_stores, monkeypatch, terminal):
    from src.agents.shared.events import AgentEvent, EventType
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding
    from src.research_run_manager import execute_research_run
    from src.sec_research.citations import read_sec_citation

    runs, threads = trace_stores
    paths = evidence.rig.store.paths
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    monkeypatch.setattr("src.api.personalization.resolve_personalization", lambda _: ("", {
        "profile_active": False, "assistant_stance": "off", "skill_mode": "off",
        "suggested_skills": [], "applied_skills": [], "context_snapshot": ""}))
    admissions = []
    original = threads._append_message_on_connection

    def append(*args, **kwargs):
        admissions.append(("message", other_owner(paths.capture_root)))
        return original(*args, **kwargs)

    monkeypatch.setattr(threads, "_append_message_on_connection", append)
    original_event = runs.append_event

    def event(run_id, kind, data):
        if kind == "tool_end":
            admissions.append(("event", other_owner(paths.capture_root)))
        return original_event(run_id, kind, data)

    monkeypatch.setattr(runs, "append_event", event)

    async def stream(**kwargs):
        result = read_sec_citation(evidence.rig.store, evidence.rig.captures, citation=evidence.document_ref)
        assert result["status"] == "ok"
        admissions.append(("result", other_owner(paths.capture_root)))
        yield AgentEvent(EventType.tool_end, {"tool": "read_sec_filing", "call_id": "saved",
            "input": {}, "summary": "preview", "sec_citations": [evidence.document_ref]})
        if terminal == "cancel":
            raise asyncio.CancelledError
        yield (AgentEvent(EventType.error, {"error": "provider failed"}) if terminal == "error" else
               AgentEvent(EventType.done, {"answer": "Answer", "provider": "openai", "model": "gpt-5.4-mini"}))

    async def execute():
        task = execute_research_run(run_id="trace-run", run_store=runs, thread_store=threads,
            dal=object(), history=[], stream_factory=stream,
            auth_binding=RuntimeAuthBinding("openai", "db_api_key", "api_key", None, _api_key="offline-key"))
        if terminal == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task

    asyncio.run(execute())
    assert threads.list_messages("trace-thread")[-1].tool_calls[0]["sec_citations"] == [evidence.document_ref]
    assert admissions == [(phase, "sec_research_operation_busy") for phase in ("result", "event", "message")]
    assert other_owner(paths.capture_root) == "entered"


def bundle_api():
    assert importlib.util.find_spec("src.sec_research.operations") is not None, "portable bundle command absent"
    from src.sec_research import operations
    return operations


def attempt(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except (ValueError, OSError, sqlite3.Error) as exc:
        return {"error": str(exc)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exported(evidence, tmp_path):
    api = bundle_api()
    path = tmp_path / "bundle"
    result = attempt(api.export_bundle, evidence.rig.store.paths, path)
    assert "error" not in result, result
    assert (path / "manifest.json").is_file()
    return api, path, result


def test_export_restore_preserves_wal_and_historical_citations(evidence, tmp_path):
    from src.sec_research.citations import read_sec_citation

    api = bundle_api()
    paths = evidence.rig.store.paths
    with evidence.rig.store.connect() as keeper:
        keeper.execute("PRAGMA journal_mode=WAL")
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("CREATE TABLE retained_market(value TEXT)")
        keeper.execute("INSERT INTO retained_market VALUES('uncheckpointed')")
        keeper.execute("INSERT INTO sec_research_reservations VALUES('interrupted',123)")
        keeper.execute("INSERT INTO sec_research_orphans VALUES('staging/abc',45)")
        before = {suffix: digest(paths.market_db_path.with_name(paths.market_db_path.name + suffix))
                  for suffix in ("", "-wal")}
        _, bundle, manifest = exported(evidence, tmp_path)
        destination = tmp_path / "restored"
        restored = attempt(api.restore_bundle, bundle, destination)
        assert "error" not in restored, restored
        reopened = Store(SecResearchPaths.from_market_db(destination / "market_data.db"))
        captures = CaptureStore(reopened, budget=lambda: 1)
        for ref in [evidence.fact_ref, evidence.document_ref, *evidence.filing_refs]:
            original = read_sec_citation(evidence.rig.store, evidence.rig.captures, citation=ref)
            assert read_sec_citation(reopened, captures, citation=ref) == original
        with reopened.connect(readonly=True) as conn:
            assert conn.execute("SELECT value FROM retained_market").fetchone()[0] == "uncheckpointed"
            assert conn.execute("SELECT COUNT(*) FROM sec_research_reservations").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM sec_research_orphans").fetchone()[0] == 0
        assert manifest["normalization"]["reservations_cleared"] == 1
        assert manifest["normalization"]["orphans_cleared"] == 1
        assert manifest["normalization"]["database_bytes"] == "normalized-backup-not-source"
        assert before == {suffix: digest(paths.market_db_path.with_name(paths.market_db_path.name + suffix))
                          for suffix in ("", "-wal")}


def test_export_uses_backup_inventory_during_concurrent_publish(evidence, tmp_path, monkeypatch):
    api = bundle_api()
    paths = evidence.rig.store.paths
    retained = evidence.rig.captures.put(b"registered but not published")
    orphan = paths.capture_root / "objects" / ("f" * 64)
    orphan.write_bytes(b"unregistered orphan")
    (paths.capture_root / "staging" / "abc").write_bytes(b"staged")
    with evidence.rig.store.connect(readonly=True) as conn:
        expected = {row[0] for row in conn.execute("SELECT sha256 FROM sec_research_objects")}
    original = api.backup_market_db
    admitted = []

    def backup(source, destination, *, overwrite):
        assert source == str(paths.market_db_path) and overwrite is False
        result = original(source, destination, overwrite=overwrite)
        admitted.append(other_owner(paths.capture_root))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(publish_facts, evidence.rig, "777.123").result(timeout=5)
        return result

    monkeypatch.setattr(api, "backup_market_db", backup)
    _, bundle, manifest = exported(evidence, tmp_path)
    assert {obj["sha256"] for obj in manifest["objects"]} == expected
    assert retained in expected and "f" * 64 not in expected
    assert admitted == ["sec_research_operation_busy"]
    assert len(list((bundle / "market_data.db.sec-research" / "objects").iterdir())) == len(expected)


def test_restore_renamed_database_reopens_same_capture(evidence, tmp_path):
    from src.sec_research.citations import read_sec_citation

    api, bundle, _ = exported(evidence, tmp_path)
    destination = tmp_path / "renamed"
    result = attempt(api.restore_bundle, bundle, destination, database_name="relocated.db")
    assert "error" not in result, result
    store = Store(SecResearchPaths.from_market_db(destination / "relocated.db"))
    result = read_sec_citation(store, CaptureStore(store, budget=None), citation=evidence.document_ref)
    assert result["status"] == "ok"
    assert "needle" in result["data"]["text"]
    assert store.paths.capture_root.is_dir()
    assert not (destination / "market_data.db.sec-research").exists()


@pytest.mark.parametrize("damage", ["missing", "corrupt", "db-corrupt", "symlink", "fifo", "extra",
                                  "traversal", "duplicate", "version", "unknown-field"])
def test_bundle_rejects_missing_corrupt_and_unsafe_members(evidence, tmp_path, damage):
    api, bundle, manifest = exported(evidence, tmp_path)
    marker = bundle / "manifest.json"
    obj = bundle / "market_data.db.sec-research" / manifest["objects"][0]["key"]
    if damage == "missing":
        obj.unlink()
    elif damage == "corrupt":
        body = obj.read_bytes()
        obj.write_bytes(bytes([body[0] ^ 1]) + body[1:])
    elif damage == "db-corrupt":
        with (bundle / "market_data.db").open("ab") as handle:
            handle.write(b"unexpected")
    elif damage in {"symlink", "fifo"}:
        obj.unlink()
        if damage == "symlink":
            obj.symlink_to(evidence.rig.store.paths.capture_root / manifest["objects"][0]["key"])
        else:
            os.mkfifo(obj)
    elif damage == "extra":
        (bundle / "undeclared").write_bytes(b"extra")
    elif damage == "duplicate":
        marker.write_text(marker.read_text().replace('"version":1', '"version":1,"version":1'))
    else:
        if damage == "traversal":
            manifest["objects"][0]["key"] = "../outside"
        elif damage == "version":
            manifest["version"] = 2
        else:
            manifest["unexpected"] = True
        marker.write_text(json.dumps(manifest))
    destination = tmp_path / "rejected"
    result = attempt(api.restore_bundle, bundle, destination)
    assert "error" in result, "invalid bundle accepted"
    assert not (destination / "manifest.json").exists()


@pytest.mark.parametrize("operation_name", ["export", "restore"])
@pytest.mark.parametrize("contents", ["empty", "store"])
def test_create_only_publication_never_overwrites_competing_destination(evidence, tmp_path, operation_name, contents):
    api, bundle, _ = exported(evidence, tmp_path)
    destination = tmp_path / "competing"
    destination.mkdir()
    sentinel = destination / "market_data.db"
    if contents == "store":
        sentinel.write_bytes(b"user-owned")
        (destination / "market_data.db-wal").write_bytes(b"user WAL")
    result = (attempt(api.export_bundle, evidence.rig.store.paths, destination) if operation_name == "export" else
              attempt(api.restore_bundle, bundle, destination))
    assert "error" in result, "existing destination accepted"
    if contents == "store":
        assert sentinel.read_bytes() == b"user-owned"
        assert (destination / "market_data.db-wal").read_bytes() == b"user WAL"
    else:
        assert list(destination.iterdir()) == []
    assert not (destination / "manifest.json").exists()


@pytest.mark.parametrize("failure", ["enospc", "fsync", "interrupt"])
def test_incomplete_bundle_has_no_success_marker(evidence, tmp_path, monkeypatch, failure):
    api = bundle_api()
    destination = tmp_path / "incomplete"
    original = api._copy_member

    def copy(*args, **kwargs):
        original(*args, **kwargs)
        if failure == "interrupt":
            raise KeyboardInterrupt
        raise OSError(errno.ENOSPC if failure == "enospc" else errno.EIO, "private failure")

    monkeypatch.setattr(api, "_copy_member", copy)
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            api.export_bundle(evidence.rig.store.paths, destination)
    else:
        result = attempt(api.export_bundle, evidence.rig.store.paths, destination)
        assert "error" in result
        assert "private failure" not in result["error"]
    assert destination.is_dir()
    assert not (destination / "manifest.json").exists()
    assert (destination / ".incomplete").exists()
    assert other_owner(evidence.rig.store.paths.capture_root) == "entered"


def test_bundle_space_preflight_is_independent_of_capture_quota(evidence, tmp_path):
    api = bundle_api()
    destination = tmp_path / "no-space"
    result = attempt(api.export_bundle, evidence.rig.store.paths, destination, free_bytes=lambda _: 0)
    assert result == {"error": "storage_space_insufficient"}
    assert not (destination / "manifest.json").exists()


def test_success_marker_is_atomic_final_publication(evidence, tmp_path, monkeypatch):
    api = bundle_api()
    destination = tmp_path / "atomic"
    original = api.os.fsync
    states = []

    def sync(fd):
        if (destination / "manifest.json").exists():
            states.append({p.name for p in destination.iterdir()})
        return original(fd)

    monkeypatch.setattr(api.os, "fsync", sync)
    result = attempt(api.export_bundle, evidence.rig.store.paths, destination)
    assert "error" not in result, result
    assert states and all(state == {"manifest.json", "market_data.db", "market_data.db.sec-research"} for state in states)


def test_final_marker_fsync_failure_withdraws_success(evidence, tmp_path, monkeypatch):
    api = bundle_api()
    destination = tmp_path / "final-fsync"
    original = api.os.fsync

    def sync(fd):
        if (destination / "manifest.json").exists():
            raise OSError(errno.EIO, "private final fsync")
        return original(fd)

    monkeypatch.setattr(api.os, "fsync", sync)
    result = attempt(api.export_bundle, evidence.rig.store.paths, destination)
    assert result == {"error": "sec_research_bundle_write_failed"}
    assert not (destination / "manifest.json").exists()
    assert (destination / ".incomplete").exists()


def test_create_only_destination_race_after_space_admission(evidence, tmp_path, monkeypatch):
    api = bundle_api()
    destination = tmp_path / "race"

    def free(_):
        destination.mkdir()
        (destination / "sentinel").write_bytes(b"other owner")
        return 1024**4

    result = attempt(api.export_bundle, evidence.rig.store.paths, destination, free_bytes=free)
    assert result == {"error": "sec_research_bundle_destination_exists"}
    assert {p.name for p in destination.iterdir()} == {"sentinel"}
    assert (destination / "sentinel").read_bytes() == b"other owner"


@pytest.mark.parametrize("damage", ["receipt-json", "catalog-source", "directory-json"])
def test_bundle_rejects_dangling_json_and_catalog_sources(evidence, tmp_path, damage):
    from src.sec_research import schema

    api, bundle, manifest = exported(evidence, tmp_path)
    database = bundle / "market_data.db"
    with sqlite3.connect(database) as conn:
        if damage == "catalog-source":
            trigger = "sec_research_document_sources_no_delete"
            conn.execute("DROP TRIGGER " + trigger)
            conn.execute("DELETE FROM sec_research_document_sources WHERE snapshot_id IN "
                         "(SELECT snapshot_id FROM sec_research_snapshots WHERE historical_name IS NOT NULL)")
        elif damage == "directory-json":
            trigger = "sec_research_document_directories_no_update"
            conn.execute("DROP TRIGGER " + trigger)
            conn.execute("UPDATE sec_research_document_directories SET metadata='{}'")
        else:
            trigger = "sec_research_receipts_no_update"
            conn.execute("DROP TRIGGER " + trigger)
            conn.execute("UPDATE sec_research_receipts SET source_snapshots=? WHERE receipt_id=?",
                (json.dumps({"submissions": {"snapshot_id": "secsnapshot_" + "0" * 64, "observed_at": NOW}}),
                 evidence.receipt["receipt_id"]))
        conn.execute(schema._DDL[trigger][2])
    manifest["database"]["sha256"] = digest(database)
    manifest["database"]["size_bytes"] = database.stat().st_size
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    result = attempt(api.restore_bundle, bundle, tmp_path / "bad-reference")
    assert "error" in result, "invalid reference closure accepted"
    assert not (tmp_path / "bad-reference" / "manifest.json").exists()


def test_bundle_rejects_corrupt_unreferenced_registered_object(evidence, tmp_path):
    sha = evidence.rig.captures.put(b"registered history")
    api, bundle, manifest = exported(evidence, tmp_path)
    obj = bundle / "market_data.db.sec-research" / "objects" / sha
    obj.write_bytes(b"Registered history")
    result = attempt(api.restore_bundle, bundle, tmp_path / "bad-hash")
    assert "error" in result, "unreferenced registered object bypassed hash validation"


@pytest.mark.parametrize("name", ["../escape.db", "market.db-wal/other", "manifest.json", "CON", "bad\\name", ""])
def test_restore_invalid_basename_precedes_database_open(tmp_path, monkeypatch, name):
    api = bundle_api()
    monkeypatch.setattr(api.sqlite3, "connect", lambda *a, **k: pytest.fail("invalid operation opened SQLite"))
    result = attempt(api.restore_bundle, tmp_path / "missing", tmp_path / "new", database_name=name)
    assert "error" in result
    assert not (tmp_path / "new").exists()


def test_bundle_cli_uses_same_owners_and_reports_scope(evidence, tmp_path, monkeypatch, capsys):
    bundle_api()
    from src.sec_research.__main__ import main

    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: evidence.rig.store.paths)
    bundle, destination = tmp_path / "cli-bundle", tmp_path / "cli-restore"
    assert main(["export", "--destination", str(bundle)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["scope"] == {"database": "whole-market-database", "captures": "sec-research-only",
        "excluded": ["independent-profile-store", "independent-sa-store", "other-capture-roots"]}
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: pytest.fail("restore resolved ambient source"))
    assert main(["restore", "--bundle", str(bundle), "--destination", str(destination),
                 "--database-name", "renamed.db"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["references"] == first["references"]
    assert "needle" not in json.dumps(second)


def test_export_preserves_nonempty_issuer_map(evidence, tmp_path):
    from src.sec_research.issuer_store import IssuerStore
    from src.sec_research.issuers import TICKER_MAP_URL

    mapping = b'{"0":{"cik_str":320193,"ticker":"AAPL","title":"Apple"}}'
    observation = IssuerStore(evidence.rig.store).refresh(Transport({TICKER_MAP_URL: mapping}),
        evidence.rig.captures, clock=lambda: NOW, check=None)
    assert observation["status"] == "ok"
    api, bundle, _ = exported(evidence, tmp_path)
    result = attempt(api.restore_bundle, bundle, tmp_path / "issuer-restored")
    assert "error" not in result, result
    store = Store(SecResearchPaths.from_market_db(tmp_path / "issuer-restored" / "market_data.db"))
    assert IssuerStore(store).resolve("AAPL")["cik"] == CIK


def test_export_preserves_large_utf8_document(rig, tmp_path):
    from src.sec_research.document_queries import DocumentQueries
    from tests.test_sec_research_document_service import FILING_ID, service

    api = bundle_api()
    text = "\u4e2d" + "x" * 100000
    rig.enqueue(b"<p>" + text.encode("utf-8") + b"</p>")
    observation = service(rig).refresh(FILING_ID)
    assert observation["status"] == "ok"
    bundle = tmp_path / "large"
    result = attempt(api.export_bundle, rig.store.paths, bundle)
    assert "error" not in result, result
    restored = attempt(api.restore_bundle, bundle, tmp_path / "large-restored")
    assert "error" not in restored, restored
    store = Store(SecResearchPaths.from_market_db(tmp_path / "large-restored" / "market_data.db"))
    captures = CaptureStore(store, budget=None)
    from src.sec_research.document_store import DocumentStore
    metadata = DocumentStore(store).capture(observation["capture_id"])["metadata"]
    assert captures.read(metadata["text_sha256"]) == text.encode("utf-8")
    page = DocumentQueries(store, captures).read(FILING_ID,
        capture_id=observation["capture_id"], query="xxx", max_chars=80)
    assert page["status"] == "ok" and page["data"]["passages"], page
    assert page["data"]["passages"][0]["text"].startswith("\u4e2dxxx")


def test_empty_export_never_creates_source_capture_root(store, tmp_path):
    api = bundle_api()
    result = attempt(api.export_bundle, store.paths, tmp_path / "empty-bundle")
    assert "error" not in result, result
    assert result["objects"] == []
    assert not store.paths.capture_root.exists()


def test_publication_platform_failure_precedes_database_open(tmp_path, monkeypatch):
    api = bundle_api()
    monkeypatch.setattr(api, "_renameat2", None)
    monkeypatch.setattr(api.sqlite3, "connect", lambda *a, **k: pytest.fail("unsupported publication opened SQLite"))
    result = attempt(api.export_bundle, SecResearchPaths.from_market_db(tmp_path / "source.db"), tmp_path / "unsupported")
    assert result == {"error": "sec_research_bundle_publication_unsupported"}
    assert not (tmp_path / "unsupported").exists()


def test_restore_rejects_wal_bundle_before_sqlite_open(evidence, tmp_path, monkeypatch):
    api, bundle, manifest = exported(evidence, tmp_path)
    database = bundle / "market_data.db"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.close()
    manifest["database"]["sha256"] = digest(database)
    manifest["database"]["size_bytes"] = database.stat().st_size
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    original = api.sqlite3.connect
    opened = []

    def connect(*args, **kwargs):
        opened.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(api.sqlite3, "connect", connect)
    result = attempt(api.restore_bundle, bundle, tmp_path / "wal-rejected")
    assert "error" in result
    assert not opened, "non-normalized bundle reached SQLite and could create WAL/SHM"
    assert not (bundle / "market_data.db-wal").exists()
    assert not (bundle / "market_data.db-shm").exists()
