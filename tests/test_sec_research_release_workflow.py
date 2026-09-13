"""Offline release workflows through one real SEC adapter and generated stores."""

import asyncio
from contextlib import closing, contextmanager
from datetime import datetime
import errno
import hashlib
import json
import os
import socket
import sqlite3
from types import SimpleNamespace

import pytest

from src import lifecycle_public_sources as public
from src.api.routes import query, research
from src.lifecycle_web_sec_sources import SecSourcePolicy
from src.research_runs import ResearchRunStore
from src.research_threads import ResearchThreadStore
from src.sec_research.captures import CaptureStore
from src.sec_research.citations import citation_event_fields, read_sec_citation
from src.sec_research.issuer_store import IssuerStore
from src.sec_research.maintenance import apply_cleanup, preview_cleanup
from src.sec_research.operations import export_bundle, restore_bundle
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store
from src.sec_research.tool_service import ToolService
from tests.test_lifecycle_public_sources import Connection, PUBLIC_IP, Response
from tests.test_sec_research_document_service import directory_body
from tests.test_sec_research_issuers import MAP_URL, Transport, map_body
from tests.test_sec_research_tool_adapters import dispatch, unwrap, wire
from tests.test_sec_research_tool_service import CIK, FACTS, NOW, SUBMISSIONS, catalog


TEXT = "A\u4e2d\u6587 needle \U0001f642 retained observation"
HTML = b"<p>" + TEXT.encode("utf-8") + b"</p>"
SECTION_GAP = [{"code": "section_index_unavailable", "section_id": None}]
CALL_IDS = ["catalog", "facts", "document-index", "document-passage"]


def facts_body(value="1234567890123456789.123"):
    return (b'{"cik":320193,"facts":{"us-gaap":{"Revenues":{"units":{"USD":['
            b'{"val":' + value.encode("ascii") + b',"start":"2025-01-01",'
            b'"end":"2025-12-31","filed":"2026-05-01","form":"10-K",'
            b'"accn":"0000950170-26-000001","fy":2025,"fp":"FY"}]}}}}}')


@pytest.fixture
def release_fixture(tmp_path, monkeypatch):
    store = Store(SecResearchPaths(tmp_path / "market.db"))
    profile = tmp_path / "research-profile.db"
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(store.paths.market_db_path))
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    store.install()
    captures = CaptureStore(store, budget=lambda: 1024**3, free_bytes=lambda _: 1024**4)
    transport = Transport({MAP_URL: map_body(("AAPL", 320193)),
                           SUBMISSIONS: catalog(), FACTS: facts_body()})
    f = SimpleNamespace(store=store, captures=captures, transport=transport,
                        profile=profile, now=NOW, responses=[], connections=[])

    def connect(host, address, *, timeout):
        assert host == "www.sec.gov" and address[1][0] == PUBLIC_IP
        assert 0 < timeout <= 60
        assert f.responses, "unexpected document acquisition"
        connection = Connection(f.responses.pop(0))
        f.connections.append(connection)
        return connection

    monkeypatch.setattr(public, "_PinnedHTTPSConnection", connect)
    monkeypatch.setattr(public.socket, "getaddrinfo", lambda host, port, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IP, port))])

    def enqueue(body):
        for raw, mime in ((directory_body(), "application/json"), (body, "text/html")):
            f.responses.append(Response(raw, headers={"Content-Type": mime,
                                                      "Content-Length": str(len(raw))}))

    def reader_factory(limits, *, document_observer, text_extractor):
        return public.PublicSourceReader(limits,
            now=lambda: datetime.fromisoformat(f.now.replace("Z", "+00:00")),
            sec_policy=SecSourcePolicy(user_agent="ArkScope offline fixture tests@example.com"),
            document_observer=document_observer, text_extractor=text_extractor)

    @contextmanager
    def acquire():
        yield captures, transport, reader_factory

    service = ToolService(store, acquisition_factory=acquire, clock=lambda: f.now)
    wire(monkeypatch, service)

    def invoke(name, **arguments):
        return asyncio.run(dispatch("anthropic", None, name, arguments))

    f.invoke, f.enqueue = invoke, enqueue
    runs, threads = ResearchRunStore(profile), ResearchThreadStore(profile)
    threads.ensure_thread(id="release-thread", title="Retained SEC evidence")
    runs.create_run(id="release-run", thread_id="release-thread", question="Retained SEC evidence",
        ticker="AAPL", provider="anthropic", model="offline-fixture", effort="low",
        auth_mode="api_key", credential_id=None)
    threads.append_message(thread_id="release-thread", role="user", content="Retained SEC evidence")
    events, expected_calls = [], []

    def observe(call_id, name, **arguments):
        start = {"tool": name, "call_id": call_id, "input": arguments}
        runs.append_event("release-run", "tool_start", start)
        events.append(("tool_start", start))
        raw = invoke(name, **arguments)
        page = unwrap(raw)
        # Paragraph-only filings have complete text but no section index.
        assert page["status"] == ("partial" if call_id == "document-index" else "ok"), page
        assert page["gaps"] == (SECTION_GAP if call_id == "document-index" else [])
        fields = citation_event_fields(name, raw)
        assert "sec_citation_gaps" not in fields, fields
        end = {**start, "summary": raw[:160], **fields}
        runs.append_event("release-run", "tool_end", end)
        events.append(("tool_end", end))
        expected_calls.append({"name": name, "call_id": call_id, "input": arguments,
                               "result_preview": raw[:160], **fields})
        return page

    f.filings = observe("catalog", "list_sec_filings", issuer="AAPL")
    f.facts = observe("facts", "get_sec_financial_facts", issuer="AAPL", concepts=["us-gaap:Revenues"])
    f.filing_id = next(row["filing_id"] for row in f.filings["data"] if row["form"] == "10-K")
    enqueue(HTML)
    index = observe("document-index", "read_sec_filing", filing_id=f.filing_id)
    f.passage = observe("document-passage", "read_sec_filing", filing_id=f.filing_id,
                        cursor=index["data"]["text_start_cursor"])

    runs = ResearchRunStore(profile)
    collected = [(event.type, event.data) for event in runs.list_events("release-run")]
    assert collected == events
    query._persist_assistant_turn(threads, thread_id="release-thread", run_id="release-run",
        done_data={"answer": "Retained SEC evidence", "provider": "anthropic", "model": "offline-fixture"},
        collected=collected, elapsed=1)
    runs.mark_terminal("release-run", "succeeded")
    messages = research.list_research_messages("release-thread", store=ResearchThreadStore(profile))["messages"]
    assert len(messages) == 2 and messages[-1]["role"] == "assistant"
    assert messages[-1]["tool_calls"] == expected_calls
    assert ResearchRunStore(profile).get_run("release-run").status == "succeeded"
    assert transport.calls == [MAP_URL, SUBMISSIONS, FACTS]
    yield f
    assert not f.responses
    assert all(connection.closed for connection in f.connections)


def reopen_saved(profile, market_db):
    messages = research.list_research_messages("release-thread", store=ResearchThreadStore(profile))["messages"]
    calls = messages[-1]["tool_calls"]
    assert [call["call_id"] for call in calls] == CALL_IDS
    store = Store(SecResearchPaths(market_db))
    captures = CaptureStore(store, budget=None)
    reopened = {}
    for call in calls:
        rows = [read_sec_citation(store, captures, citation=ref) for ref in call.get("sec_citations", [])]
        assert all(row["status"] == "ok" and not row["gaps"] for row in rows), rows
        reopened[call["call_id"]] = rows
    assert [len(reopened[call_id]) for call_id in CALL_IDS] == [2, 1, 0, 1]
    fact = reopened["facts"][0]["data"]
    passage = reopened["document-passage"][0]["data"]
    return {"value": fact["observation"]["value"], "text": passage["text"],
            "text_sha256": passage["document"]["text_sha256"],
            "capture_id": passage["document"]["capture_id"], "reopened": reopened}


def test_research_catalog_fact_document_reload_export_restore(release_fixture, tmp_path):
    f = release_fixture
    before = reopen_saved(f.profile, f.store.paths.market_db_path)
    assert before["value"] == f.facts["data"][0]["value"] == "1234567890123456789.123"
    assert before["text"] == f.passage["data"]["passages"][0]["text"] == TEXT
    assert before["text_sha256"] == hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
    assert before["capture_id"] == f.passage["data"]["document"]["capture_id"]
    fact_ref = before["reopened"]["facts"][0]["data"]["citation"]
    document_ref = before["reopened"]["document-passage"][0]["data"]["citation"]
    assert f.captures.read(fact_ref["source_sha256"]) == facts_body()
    assert f.captures.read(document_ref["original_sha256"]) == HTML
    assert document_ref["end_byte"] == len(TEXT.encode("utf-8")) > len(TEXT)
    assert {row["cik"] for row in f.filings["data"]} == {CIK}
    assert IssuerStore(f.store).resolve("AAPL")["cik"] == CIK

    # New observations must not retarget the citations saved in the earlier turn.
    f.now = "2026-09-13T12:00:00Z"
    f.transport.responses[FACTS] = facts_body("777.123")
    latest_fact = unwrap(f.invoke("get_sec_financial_facts", issuer=CIK, freshness="refresh"))
    assert latest_fact["status"] == "ok" and latest_fact["data"][0]["value"] == "777.123"
    f.enqueue(b"<p>Latest replacement passage.</p>")
    latest_document = unwrap(f.invoke("read_sec_filing", filing_id=f.filing_id, freshness="refresh"))
    assert latest_document["status"] == "partial" and latest_document["gaps"] == SECTION_GAP
    assert latest_document["data"]["document"]["capture_id"] != before["capture_id"]
    assert reopen_saved(f.profile, f.store.paths.market_db_path) == before

    with f.store.connect() as conn:
        conn.execute("CREATE TABLE release_market(value TEXT)")
        conn.execute("INSERT INTO release_market VALUES('retained non-SEC market row')")
    source_objects = {path.name: path.read_bytes() for path in (f.store.paths.capture_root / "objects").iterdir()}
    profile_bytes = f.profile.read_bytes()
    bundle, destination = tmp_path / "bundle", tmp_path / "restored"
    manifest = export_bundle(f.store.paths, bundle)
    assert json.loads((bundle / "manifest.json").read_text()) == manifest
    restored = restore_bundle(bundle, destination, database_name="relocated.db")
    assert restored["database"]["name"] == "relocated.db"
    assert not (bundle / f.profile.name).exists()
    assert not (destination / f.profile.name).exists()

    # Bundles carry the market DB and SEC objects; retain the separate Research profile.
    after = reopen_saved(f.profile, destination / "relocated.db")
    assert after["value"] == before["value"]
    assert after["text"] == before["text"]
    assert after["text_sha256"] == before["text_sha256"]
    assert after["capture_id"] == before["capture_id"]
    assert after["reopened"] == before["reopened"]
    restored_store = Store(SecResearchPaths(destination / "relocated.db"))
    assert IssuerStore(restored_store).resolve("AAPL")["cik"] == CIK
    with restored_store.connect(readonly=True) as conn:
        assert conn.execute("SELECT value FROM release_market").fetchone()[0] == "retained non-SEC market row"
    assert f.profile.read_bytes() == profile_bytes
    assert {path.name: path.read_bytes() for path in (f.store.paths.capture_root / "objects").iterdir()} == source_objects
    assert reopen_saved(f.profile, f.store.paths.market_db_path) == before


def test_interrupted_refresh_keeps_stored_references_out_of_cleanup(release_fixture, tmp_path, monkeypatch):
    f = release_fixture
    before = reopen_saved(f.profile, f.store.paths.market_db_path)
    unrelated = b"unreferenced release cleanup control"
    orphan = f.captures.put(unrelated)
    changed = facts_body("999.456")
    changed_sha = hashlib.sha256(changed).hexdigest()
    f.transport.responses[FACTS] = changed
    f.now = "2026-09-13T12:00:00Z"
    real_link = os.link

    def interrupt_publication(source, destination, **kwargs):
        if destination == changed_sha:
            raise OSError(errno.ENOSPC, "fixture interrupted capture publication")
        return real_link(source, destination, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", interrupt_publication)
        failed = unwrap(f.invoke("get_sec_financial_facts", issuer=CIK, freshness="refresh"))
    assert failed["status"] == "unavailable" and failed["data"] == [], failed
    receipt = f.store.latest_receipt(CIK)
    assert receipt["completed"] == ["submissions"] and receipt["pending"] == ["companyfacts"]
    assert receipt["gaps"] == [{"source": "companyfacts", "code": "storage_space_insufficient"}]
    assert set(receipt["source_snapshots"]) == {"submissions"}
    staged, = (f.store.paths.capture_root / "staging").iterdir()
    assert staged.read_bytes() == changed
    assert not (f.store.paths.capture_root / "objects" / changed_sha).exists()
    assert f.captures.status()["reserved_bytes"] == len(changed)

    requests = list(f.transport.calls)
    assert reopen_saved(f.profile, f.store.paths.market_db_path) == before
    stored = unwrap(f.invoke("get_sec_financial_facts", issuer=CIK, freshness="stored"))
    assert stored["status"] == "unavailable" and stored["data"] == [], stored
    assert f.transport.calls == requests
    recovered = f.captures.recover()
    assert recovered["reserved_bytes"] == 0 and recovered["orphan_bytes"] == len(changed)

    with closing(sqlite3.connect(f"{f.profile.as_uri()}?mode=ro", uri=True)) as profile:
        profile.execute("PRAGMA query_only=ON")
        preview = preview_cleanup(f.store.paths, profile_connection=profile)
        assert preview["status"] == "ready" and preview["reference_status"] == "verified", preview
        assert preview["references"]["research_citations"] > 0
        assert {item["key"] for item in preview["candidates"]} == {
            "objects/" + orphan, "staging/" + staged.name}
        pinned_objects = {ref[field]
            for rows in before["reopened"].values() for row in rows
            for ref in [row["data"]["citation"]]
            for field in ("source_sha256", "original_sha256", "text_sha256") if field in ref}
        assert pinned_objects.isdisjoint(item["sha256"] for item in preview["candidates"])
        assert staged.read_bytes() == changed and f.captures.read(orphan) == unrelated
        receipt_path = tmp_path / "cleanup-receipt.json"
        result = apply_cleanup(f.store.paths, preview, approval_sha256=preview["approval_sha256"],
                               receipt_path=receipt_path, profile_connection=profile)
    assert result["status"] == "ok", result
    assert result["freed_bytes"] == len(unrelated) + len(changed)
    assert json.loads(receipt_path.read_text()) == result
    assert not staged.exists() and not (f.store.paths.capture_root / "objects" / orphan).exists()
    assert f.captures.status()["charged_bytes"] == recovered["charged_bytes"] - result["freed_bytes"]
    assert reopen_saved(f.profile, f.store.paths.market_db_path) == before
    assert f.transport.calls == requests
