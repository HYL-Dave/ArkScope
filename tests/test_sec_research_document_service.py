"""Offline durable acquisition contracts using the real bounded public reader."""

from datetime import datetime, timezone
import gzip
import importlib
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from src.sec_research.catalog import parse_submissions
from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store
from tests.test_lifecycle_public_sources import Connection, Response, PUBLIC_IP


CIK = "0000320193"
ACCESSION = "0000950170-26-000001"
FILING_ID = CIK + ":" + ACCESSION
ROOT_URL = "https://www.sec.gov/Archives/edgar/data/320193/000095017026000001/"
NOW = "2026-09-12T12:00:00Z"
HISTORY = "CIK0000320193-submissions-001.json"


def owner(name):
    path = Path(__file__).resolve().parents[1] / "src/sec_research" / (name + ".py")
    assert path.is_file(), f"missing durable document behavior: {name}"
    return importlib.import_module("src.sec_research." + name)


def bind_catalog(store, captures, *, primary="actual.htm", form="10-K", history=None,
                 pending=False, bind=True):
    columns = {"accessionNumber": [ACCESSION], "filingDate": ["2026-05-01"],
               "form": [form], "primaryDocument": [primary]}
    payload = columns if history else {"cik": 320193, "filings": {
        "recent": columns, "files": [{"name": HISTORY}] if pending else []}}
    body = json.dumps(payload).encode()
    snapshot = parse_submissions(body, cik=CIK, historical_name=history)
    sid = store.publish(snapshot, object_sha256=captures.put(body), observed_at=NOW,
                        source_url="https://data.sec.gov/submissions/" + (history or "CIK" + CIK + ".json"))
    if bind:
        bindings = {history or "submissions": {"snapshot_id": sid, "observed_at": NOW}}
        store.record_receipt(CIK, status="partial" if pending else "ok", completed=list(bindings),
                             pending=[HISTORY] if pending else [], gaps=[], observed_at=NOW,
                             source_snapshots=bindings)
    return sid


def directory_body(names=("actual.htm", "exhibit.xml")):
    return json.dumps({"directory": {"name": ROOT_URL.removeprefix("https://www.sec.gov").rstrip("/"),
        "item": [{"name": name, "type": "file", "size": "1"} for name in names]}}).encode()


@pytest.fixture
def rig(tmp_path, monkeypatch):
    from src import lifecycle_public_sources as public
    from src.lifecycle_web_sec_sources import SecSourcePolicy

    store = Store(SecResearchPaths(tmp_path / "market.db"))
    store.install()
    state = SimpleNamespace(store=store, queue=[], requests=[], readers=[], before=None,
                            budget=1024**3, free=1024**4)
    state.captures = CaptureStore(store, budget=lambda: state.budget, free_bytes=lambda _: state.free)
    bind_catalog(store, state.captures)

    class Governor:
        def reserve_request_start(self, *, check):
            check()

    def connect(host, address, *, timeout):
        assert host == "www.sec.gov" and address[1][0] == PUBLIC_IP and 0 < timeout <= 60
        if state.before:
            state.before()
        assert state.queue, "unexpected acquisition"
        connection = Connection(state.queue.pop(0))
        state.requests.append(connection)
        return connection

    monkeypatch.setattr(public, "_PinnedHTTPSConnection", connect)
    monkeypatch.setattr(public.socket, "getaddrinfo", lambda host, port, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IP, port))])

    def factory(limits, *, document_observer, text_extractor):
        reader = public.PublicSourceReader(limits, now=lambda: datetime(2026, 9, 12, 12, tzinfo=timezone.utc),
            sec_policy=SecSourcePolicy(user_agent="ArkScope offline fixture tests@example.com", governor=Governor()),
            document_observer=document_observer, text_extractor=text_extractor)
        state.readers.append(reader)
        return reader

    state.factory = factory

    def enqueue(body=b"<h1>Item 1. Business</h1><p>needle one needle two</p>", *, names=None,
                mime="text/html", compressed=False, status=200, length=None):
        raw = directory_body() if names is None else directory_body(names)
        state.queue.append(Response(raw, headers={"Content-Type": "application/json", "Content-Length": str(len(raw))}))
        wire = gzip.compress(body) if compressed else body
        state.queue.append(Response(wire, status=status, headers={"Content-Type": mime,
            "Content-Length": str(len(wire) if length is None else length),
            **({"Content-Encoding": "gzip"} if compressed else {})}))
        return raw, wire

    state.enqueue = enqueue
    return state


def service(rig):
    return owner("document_service").DocumentService(rig.store, rig.captures,
        reader_factory=rig.factory, clock=lambda: NOW)


def test_document_original_is_decoded_and_observations_are_real(rig):
    body = b"<p>needle complete</p>"
    _, wire = rig.enqueue(body, compressed=True)
    result = service(rig).refresh(FILING_ID)
    assert result["status"] == "ok" and result["capture_id"]
    doc = owner("document_store").DocumentStore(rig.store).capture(result["capture_id"])
    assert rig.captures.read(doc["original_sha256"]) == body
    assert rig.captures.read(doc["text_sha256"]) == b"needle complete"
    report = result["requests"][1]["report"]
    assert report["requests"] == 1
    assert report["observations"][0]["received_body_bytes"] == len(wire)
    assert report["observations"][0]["decoded_body_bytes"] == len(body)
    assert report["observations"][0]["result_code"] == "complete"
    assert [(r.limits.max_requests, r.limits.max_redirects, r.limits.max_response_bytes,
             r.limits.decoded_byte_limit) for r in rig.readers] == [
        (1, 0, 16 * 1024**2, 16 * 1024**2), (1, 0, 32 * 1024**2, 128 * 1024**2)]


def test_document_primary_must_be_in_bound_directory(rig):
    rig.enqueue(names=["other.htm"])
    result = service(rig).refresh(FILING_ID)
    assert result["status"] == "unavailable" and result["capture_id"] is None
    assert {g["code"] for g in result["gaps"]} == {"document_not_in_directory"}
    assert len(rig.requests) == 1


@pytest.mark.parametrize("field", ["primary", "form"])
def test_conflicting_catalog_primary_never_dispatches(rig, field):
    recent = rig.store.latest_receipt(CIK)["source_snapshots"]["submissions"]
    sid = bind_catalog(rig.store, rig.captures, history=HISTORY, bind=False,
                       **{field: "other.htm" if field == "primary" else "10-Q"})
    bindings = {"submissions": recent, HISTORY: {"snapshot_id": sid, "observed_at": NOW}}
    rig.store.record_receipt(CIK, status="ok", completed=list(bindings), pending=[], gaps=[],
                             observed_at=NOW, source_snapshots=bindings)
    result = service(rig).refresh(FILING_ID)
    assert result["status"] == "unavailable"
    assert "filing_metadata_conflict" in {g["code"] for g in result["gaps"]}
    assert rig.requests == []


def test_only_receipt_bound_catalog_is_authority(rig):
    bind_catalog(rig.store, rig.captures, primary="unbound.htm", bind=False)
    rig.enqueue()
    result = service(rig).refresh(FILING_ID)
    assert result["status"] == "ok"
    assert rig.requests[1].requests[0][1].endswith("/actual.htm")


def test_pending_unrelated_history_preserves_gap_but_allows_observed_filing(rig):
    bind_catalog(rig.store, rig.captures, pending=True)
    rig.enqueue()
    result = service(rig).refresh(FILING_ID)
    assert result["capture_id"] and result["status"] == "partial"
    assert "catalog_sources_pending" in {g["code"] for g in result["gaps"]}


def test_authority_budget_cannot_hide_bound_conflict(rig, monkeypatch):
    from src.sec_research import queries
    monkeypatch.setattr(queries, "MAX_QUERY_ROWS", 0)
    result = service(rig).refresh(FILING_ID)
    assert result["capture_id"] is None and rig.requests == []
    assert "query_budget_exceeded" in {g["code"] for g in result["gaps"]}


@pytest.mark.parametrize("stage", ["directory", "document"])
@pytest.mark.parametrize("block", ["budget", "space"])
def test_capture_budget_blocks_document_request(rig, stage, block):
    def exhaust():
        if block == "budget":
            rig.budget = rig.captures.status()["charged_bytes"]
        else:
            rig.free = 0
    if stage == "directory":
        exhaust()
    else:
        rig.enqueue()
        rig.before = exhaust
    result = service(rig).refresh(FILING_ID)
    assert result["status"] == "unavailable" and result["capture_id"] is None
    assert len(rig.requests) == (0 if stage == "directory" else 1)
    assert ("capture_budget_exceeded" if block == "budget" else "storage_space_insufficient") in {
        g["code"] for g in result["gaps"]}


def test_provider_and_parser_do_not_hold_writer_locks(rig):
    from src.sec_research.capture_lock import capture_writer
    def probe():
        with capture_writer(rig.store.paths.capture_root), rig.store._write():
            pass
    rig.before = probe
    rig.enqueue()
    assert service(rig).refresh(FILING_ID, check=probe)["capture_id"]


def test_document_lease_is_root_wide_but_distinct_from_writer(rig):
    acquisition = service(rig)
    nested = []
    def probe():
        nested.append(acquisition.refresh(FILING_ID, "file:exhibit.xml"))
    rig.before = probe
    rig.enqueue()
    assert acquisition.refresh(FILING_ID)["capture_id"]
    assert len(nested) == 2
    assert all(r["status"] == "unavailable" and r["gaps"] == [
        {"code": "document_acquisition_busy"}] for r in nested)


@pytest.mark.parametrize("kind", ["truncated", "redirect", "unsupported", "invalid_directory"])
def test_incomplete_or_unsupported_capture_is_never_published(rig, kind):
    rig.enqueue(length=10000 if kind == "truncated" else None,
                status=302 if kind == "redirect" else 200,
                mime="application/pdf" if kind == "unsupported" else "text/html")
    if kind == "invalid_directory":
        rig.queue[0] = Response(b'{"directory":{}}', headers={"Content-Type": "application/json"})
    result = service(rig).refresh(FILING_ID)
    assert result["status"] == "unavailable" and result["capture_id"] is None
    assert result["requests"][-1]["report"]["observations"][0]["result_code"] != "complete"
    with rig.store.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM sec_research_documents").fetchone()[0] == 0


def test_interruption_before_publication_leaves_no_complete_capture(rig):
    from src.lifecycle_public_sources import SourceReadError
    rig.enqueue()
    def cancel():
        if len(rig.requests) == 2:
            raise SourceReadError("source_read_cancelled")
    result = service(rig).refresh(FILING_ID, check=cancel)
    assert result["status"] == "unavailable" and result["capture_id"] is None
    assert "source_read_cancelled" in {g["code"] for g in result["gaps"]}
    assert owner("document_store").DocumentStore(rig.store).latest_attempt(FILING_ID, "primary")["capture_id"] is None


def test_process_interruption_marks_latest_unavailable(rig, monkeypatch):
    rig.enqueue()
    acquisition = service(rig)
    assert acquisition.refresh(FILING_ID)["capture_id"]
    rig.enqueue()
    def interrupt(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(rig.captures, "put", interrupt)
    with pytest.raises(KeyboardInterrupt):
        acquisition.refresh(FILING_ID)
    latest = owner("document_store").DocumentStore(rig.store).latest_attempt(FILING_ID, "primary")
    assert latest["capture_id"] is None
    assert latest["outcome"] == "interrupted"


def test_explicit_safe_directory_id_not_extension_grants_acquisition(rig):
    rig.enqueue(b"plain needle", names=["NOEXT"], mime="text/plain")
    result = service(rig).refresh(FILING_ID, "file:NOEXT")
    assert result["capture_id"]
    assert rig.requests[1].requests[0][1].endswith("/NOEXT")


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError])
def test_unexpected_errors_are_content_free(rig, monkeypatch, error_type):
    def failure():
        raise error_type("PRIVATE body or /secret/path")
    monkeypatch.setattr(rig.captures, "preflight", failure)
    result = service(rig).refresh(FILING_ID)
    assert "PRIVATE" not in json.dumps(result) and "/secret" not in json.dumps(result)
    assert result["status"] == "unavailable"


def test_known_directory_cost_blocks_document_dispatch(rig):
    rig.budget = rig.captures.status()["charged_bytes"] + 1
    rig.enqueue()
    result = service(rig).refresh(FILING_ID)
    assert result["capture_id"] is None
    assert len(rig.requests) == 1
    assert {g["code"] for g in result["gaps"]} == {"capture_budget_exceeded"}


def test_all_bound_catalog_sources_and_selected_row_provenance_are_retained(rig):
    recent = rig.store.latest_receipt(CIK)["source_snapshots"]["submissions"]
    sid = bind_catalog(rig.store, rig.captures, history=HISTORY, bind=False)
    bindings = {"submissions": recent, HISTORY: {"snapshot_id": sid, "observed_at": NOW}}
    receipt = rig.store.record_receipt(CIK, status="ok", completed=list(bindings), pending=[], gaps=[],
                                      observed_at=NOW, source_snapshots=bindings)
    rig.enqueue()
    result = service(rig).refresh(FILING_ID)
    metadata = owner("document_store").DocumentStore(rig.store).capture(result["capture_id"])["metadata"]
    assert metadata["receipt_id"] == receipt["receipt_id"]
    assert {s["snapshot_id"] for s in metadata["catalog_sources"]} == {recent["snapshot_id"], sid}
    assert len(metadata["sources"]) == 2
    assert {s["source"]["pointer"] for s in metadata["sources"]} == {
        "/filings/recent/accessionNumber/0", "/accessionNumber/0"}


def test_newly_failed_primary_directory_refresh_blocks_resolved_latest(rig):
    rig.enqueue()
    first = service(rig).refresh(FILING_ID)
    rig.enqueue()
    rig.queue[0] = Response(b"failed", status=503)
    second = service(rig).refresh(FILING_ID)
    assert second["capture_id"] is None
    documents = owner("document_store").DocumentStore(rig.store)
    assert documents.latest_attempt(FILING_ID, "file:actual.htm")["capture_id"] is None
    assert documents.capture(first["capture_id"])


def test_document_lease_excludes_other_process_and_releases_after_exit(rig):
    import os
    from src.sec_research.capture_lock import document_acquisition

    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(read_fd)
        try:
            with document_acquisition(rig.store.paths.capture_root):
                os.write(write_fd, b"ready")
                # Parent terminates the owner while its lease is held.
                import signal
                signal.pause()
        finally:
            os._exit(0)
    os.close(write_fd)
    try:
        import select
        import signal
        assert select.select([read_fd], [], [], 5)[0]
        assert os.read(read_fd, 5) == b"ready"
        result = service(rig).refresh(FILING_ID)
        assert result["gaps"] == [{"code": "document_acquisition_busy"}] and not rig.requests
    finally:
        os.close(read_fd)
        os.kill(child, signal.SIGTERM)
        os.waitpid(child, 0)
    rig.enqueue()
    assert service(rig).refresh(FILING_ID)["capture_id"]


def test_observed_long_safe_filename_uses_reader_url_limit(rig):
    name = "x" * 810 + ".htm"
    rig.enqueue(b"<h1>Item 1. Business</h1><p>needle</p>", names=[name])
    result = service(rig).refresh(FILING_ID, "file:" + name)
    assert result["capture_id"]
    page = owner("document_queries").DocumentQueries(rig.store, rig.captures).read(
        FILING_ID, document_id="file:" + name, capture_id=result["capture_id"])
    assert page["status"] == "ok" and len(page["data"]["text_start_cursor"]) <= 4096
