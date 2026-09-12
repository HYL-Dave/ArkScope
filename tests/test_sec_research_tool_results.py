"""SEC results must remain whole envelopes through every result boundary."""

import asyncio
import json

import pytest

from src.agents.shared.compressor.reducers import get_reducer
from tests.test_sec_research_tool_adapters import CHANNELS, NAMES, dispatch, registry, unwrap, wire
from tests.test_sec_research_tool_service import CIK, SUBMISSIONS, tool_fixture, document_rig


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("payload", ['{"broken":', json.dumps(dict(status="ok", data=["x" * 20000],
    gaps=[], observed_at=None, coverage={}, next_cursor=None))], ids=["malformed", "oversized"])
def test_sec_pages_remain_complete_json_through_bridge_reduction(name, payload):
    result, meta = get_reducer(name)(payload, budget=8000)
    envelope = unwrap(result)
    assert set(envelope) == {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}
    assert envelope["status"] == "unavailable"
    assert envelope["gaps"][0]["code"].startswith("sec_result_")
    assert len(result) <= 8000


@pytest.mark.parametrize("channel", CHANNELS)
def test_whole_pages_use_active_layer0_budget_without_changing_filters(
        channel, registry, tool_fixture, monkeypatch):
    from src.agents import config
    configured = config.AgentConfig(compaction_layer_0_budget_chars=3500)
    monkeypatch.setattr(config, "get_agent_config", lambda: configured)
    f = tool_fixture
    catalog = json.loads(f.transport.responses[SUBMISSIONS])
    recent = catalog["filings"]["recent"]
    for key in recent:
        recent[key] *= 12
    recent["accessionNumber"] = [f"0000950170-26-{i:06}" for i in range(24)]
    f.transport.responses[SUBMISSIONS] = json.dumps(catalog).encode()
    wire(monkeypatch, f.service)
    seen, cursor = [], None
    for _ in range(30):
        payload = asyncio.run(dispatch(channel, registry, "list_sec_filings",
            dict(issuer=CIK, limit=20, cursor=cursor)))
        assert len(payload) <= 3500
        page = unwrap(payload)
        assert page["data"], page
        seen.extend(row["filing_id"] for row in page["data"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 24


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
def test_sec_cancel_awaits_worker_and_prevents_later_dispatch(tool_fixture, monkeypatch, mode):
    import contextvars
    import importlib.util
    import threading
    assert importlib.util.find_spec("src.sec_research.tool_execution"), "missing SEC worker owner"
    from src.sec_research.tool_execution import invoke_sec_tool
    f = tool_fixture
    wire(monkeypatch, f.service)
    entered, stopped, finished = threading.Event(), threading.Event(), threading.Event()
    marker = contextvars.ContextVar("sec_test_context", default="lost")
    contexts = []
    original = f.transport.get

    def read(*args, **kwargs):
        contexts.append(marker.get())
        # This owner models an already-dispatched response, not governor wait.
        response = original(*args, **kwargs)
        entered.set()
        assert stopped.wait(3), "cancellation did not ask active transport to stop"
        # Give the caller time to return incorrectly if it omits the owned wait.
        import time
        time.sleep(0.08)
        try:
            return response
        finally:
            finished.set()

    monkeypatch.setattr(f.transport, "get", read)
    monkeypatch.setattr(f.transport, "close", stopped.set, raising=False)

    async def run():
        token = marker.set("copied")
        try:
            task = asyncio.create_task(invoke_sec_tool("list_sec_filings", dict(issuer=CIK),
                timeout_s=0.15 if mode == "timeout" else None))
            while not entered.is_set() and not task.done():
                await asyncio.sleep(0.001)
            assert entered.is_set()
            if mode == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                result = await task
                assert result["status"] == "unavailable"
            assert finished.is_set(), "SEC returned before its owned worker completed"
        finally:
            stopped.set()
            marker.reset(token)

    asyncio.run(run())
    assert contexts == ["copied"]
    assert f.transport.calls == [SUBMISSIONS]
    assert f.closes == [True]


@pytest.mark.parametrize("layer", ["layer0", "layer5"])
@pytest.mark.parametrize("kind", ["complete", "oversized", "malformed"])
def test_sec_layers_select_whole_envelope_reduction(layer, kind, tool_fixture, tmp_path):
    from src.sec_research.tool_results import serialize_sec_result
    from src.agents.shared.compressor.layers import apply_layer_0
    from src.agents.shared.compressor.overflow_store import OverflowStore
    from src.agents.shared.compressor.summary_prompt import render_layer_5_transcript
    from tests.test_sec_research_tool_service import seed
    f = tool_fixture
    seed(f)
    envelope = f.service.invoke("list_sec_filings", dict(issuer=CIK, freshness="stored"))
    if kind == "oversized":
        envelope["data"] *= 20
    payload = "{broken" if kind == "malformed" else serialize_sec_result(envelope, "list_sec_filings")
    if layer == "layer0":
        store = OverflowStore(tmp_path / "overflow", "sec-boundary")
        result, record = apply_layer_0(tool_name="list_sec_filings", args={}, payload=payload,
                                     overflow_store=store, budget_chars=8000)
        if kind != "complete":
            assert record is not None
    else:
        text = render_layer_5_transcript([dict(role="tool_result", tool_name="list_sec_filings", content=payload)])
        result = text.split("]: ", 1)[1]
    if kind == "complete":
        assert result == payload
    else:
        assert unwrap(result)["status"] == "unavailable"
        assert len(result) <= 8000


@pytest.mark.parametrize("mode", ["cancel", "timeout", "repeat_cancel"])
def test_sec_cancel_stops_actual_document_reader_before_next_source(document_rig, monkeypatch, mode):
    import threading
    import time
    from src.sec_research.tool_execution import invoke_sec_tool
    from tests.test_sec_research_tool_service import doc_tool
    from tests.test_sec_research_document_service import FILING_ID
    r = document_rig
    service, _ = doc_tool(r)
    wire(monkeypatch, service)
    r.enqueue()
    entered, finished = threading.Event(), threading.Event()

    def blocked_read(size):
        entered.set()
        deadline = time.monotonic() + 3
        while not r.requests[0].closed and time.monotonic() < deadline:
            time.sleep(0.001)
        assert r.requests[0].closed, "active reader was not stopped"
        time.sleep(0.08)
        finished.set()
        return b""

    monkeypatch.setattr(r.queue[0], "read", blocked_read)

    async def run():
        task = asyncio.create_task(invoke_sec_tool("read_sec_filing", dict(filing_id=FILING_ID),
            timeout_s=0.15 if mode == "timeout" else None))
        while not entered.is_set() and not task.done():
            await asyncio.sleep(0.001)
        assert entered.is_set()
        if mode == "timeout":
            assert (await task)["status"] == "unavailable"
        else:
            task.cancel()
            if mode == "repeat_cancel":
                await asyncio.sleep(0.01)
                task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert finished.is_set(), "returned before document worker completed"

    asyncio.run(run())
    assert len(r.requests) == 1
    from src.sec_research.document_store import DocumentStore
    assert DocumentStore(r.store).latest_attempt(FILING_ID, "primary")["capture_id"] is None


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
@pytest.mark.parametrize("mode", ["text", "search"])
def test_whole_document_size_gap_advances_with_original_max_chars(
        channel, mode, registry, document_rig, monkeypatch):
    from src.agents import config
    from tests.test_sec_research_tool_service import doc_tool
    from tests.test_sec_research_document_service import FILING_ID
    from src.sec_research.document_queries import _decode
    from src.sec_research.queries import _digest
    configured = config.AgentConfig(compaction_layer_0_budget_chars=3500)
    monkeypatch.setattr(config, "get_agent_config", lambda: configured)
    r = document_rig
    service, _ = doc_tool(r)
    wire(monkeypatch, service)
    r.enqueue(("<p>" + "needle " * 3500 + "</p>").encode())
    index = unwrap(asyncio.run(dispatch(channel, registry, "read_sec_filing", dict(filing_id=FILING_ID))))
    arguments = dict(filing_id=FILING_ID, max_chars=6000)
    if mode == "search":
        arguments["query"] = "needle"
    else:
        arguments["cursor"] = index["data"]["text_start_cursor"]
    from src.sec_research.tool_results import serialize_sec_result
    if mode == "search":
        minimum = service.invoke("read_sec_filing", dict(filing_id=FILING_ID, query="needle", max_chars=6))
    else:
        tiny_index = service.invoke("read_sec_filing", dict(filing_id=FILING_ID, max_chars=1))
        minimum = service.invoke("read_sec_filing", dict(filing_id=FILING_ID, max_chars=1,
            cursor=tiny_index["data"]["text_start_cursor"]))
    assert minimum["data"]["passages"]
    configured.compaction_layer_0_budget_chars = len(serialize_sec_result(minimum, "read_sec_filing")) - 40
    payload = asyncio.run(dispatch(channel, registry, "read_sec_filing", arguments))
    gap = unwrap(payload)
    assert len(payload) <= configured.compaction_layer_0_budget_chars and not gap["data"]["passages"]
    assert {g["code"] for g in gap["gaps"]} == {"document_passage_too_large"}
    token = _decode(gap["next_cursor"])
    assert token["offset"] == (6000 if mode == "text" else 6)
    assert token["filters_hash"] == _digest(dict(section_id=None, query=arguments.get("query"), max_chars=6000))
    arguments["cursor"] = gap["next_cursor"]
    second = unwrap(asyncio.run(dispatch(channel, registry, "read_sec_filing", arguments)))
    assert _decode(second["next_cursor"])["offset"] > token["offset"]
    assert len(r.requests) == 2


def test_domain_row_size_gap_advances_and_envelope_alone_fails_closed(tool_fixture):
    from src.sec_research.queries import StoredQueries, _decode
    from tests.test_sec_research_tool_service import seed
    f = tool_fixture
    seed(f)
    queries = StoredQueries(f.store)
    skipped = queries.filings(CIK, limit=20, result_fits=lambda value: not value["data"])
    assert skipped["data"] == [] and skipped["gaps"] == [{"code": "observation_too_large", "count": 1}]
    assert _decode(skipped["next_cursor"])["offset"] == 1
    second = queries.filings(CIK, limit=20, cursor=skipped["next_cursor"], result_fits=lambda value: not value["data"])
    assert second["next_cursor"] is None and second["gaps"] == skipped["gaps"]
    oversized = queries.filings(CIK, result_fits=lambda value: False)
    assert oversized["status"] == "unavailable" and oversized["next_cursor"] is None
    assert oversized["gaps"] == [{"code": "sec_result_too_large"}]


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_exact_facts_page_by_wrapped_budget_with_unchanged_limit(channel, registry, tool_fixture, monkeypatch):
    from src.agents import config
    from tests.test_sec_research_tool_service import FACTS
    configured = config.AgentConfig(compaction_layer_0_budget_chars=3500)
    monkeypatch.setattr(config, "get_agent_config", lambda: configured)
    f = tool_fixture
    fact = ('{"val":1234567890123456789.123,"end":"2025-12-31","form":"10-K",'
            '"accn":"0000320193-26-000001","filed":"2026-01-30"}')
    concepts = ",".join(f'"Value{i}":{{"units":{{"USD":[{fact}]}}}}' for i in range(15))
    f.transport.responses[FACTS] = ('{"cik":320193,"facts":{"us-gaap":{' + concepts + '}}}').encode()
    wire(monkeypatch, f.service)
    ids, cursor = [], None
    for _ in range(16):
        payload = asyncio.run(dispatch(channel, registry, "get_sec_financial_facts",
            dict(issuer=CIK, limit=40, cursor=cursor)))
        assert len(payload) <= 3500
        page = unwrap(payload)
        assert page["data"], page
        for row in page["data"]:
            assert row["value"] == "1234567890123456789.123"
            assert row["source"]["sha256"] == row["object_sha256"]
            ids.append(row["fact_id"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(ids) == len(set(ids)) == 15
    assert len(f.transport.calls) == 2


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_non_ascii_passages_keep_exact_citations_through_transport(channel, registry, document_rig, monkeypatch):
    from tests.test_sec_research_tool_service import doc_tool
    from tests.test_sec_research_document_service import FILING_ID
    r = document_rig
    service, _ = doc_tool(r)
    wire(monkeypatch, service)
    body = "A\u4e2d\u6587 needle \U0001f642 needle Z"
    r.enqueue(body.encode(), mime="text/plain")
    index = unwrap(asyncio.run(dispatch(channel, registry, "read_sec_filing",
        dict(filing_id=FILING_ID, max_chars=3))))
    cursor, emitted = index["data"]["text_start_cursor"], []
    while cursor:
        payload = asyncio.run(dispatch(channel, registry, "read_sec_filing",
            dict(filing_id=FILING_ID, max_chars=3, cursor=cursor)))
        page = unwrap(payload)
        for passage in page["data"]["passages"]:
            citation = passage["citation"]
            assert body.encode()[citation["start_byte"]:citation["end_byte"]].decode() == passage["text"]
            emitted.append(passage["text"])
        cursor = page["next_cursor"]
    assert "".join(emitted) == body
    assert len(r.requests) == 2


def test_document_pager_measures_final_status_with_each_candidate(document_rig):
    from tests.test_sec_research_tool_service import doc_tool
    from tests.test_sec_research_document_service import FILING_ID
    from src.sec_research.document_queries import DocumentQueries
    r = document_rig
    service, _ = doc_tool(r)
    r.enqueue()
    service.invoke("read_sec_filing", dict(filing_id=FILING_ID))
    read = DocumentQueries(r.store, r.captures)
    checked = []
    def fit(value):
        checked.append(json.loads(json.dumps(value)))
        return True
    result = read.read(FILING_ID, result_fits=fit)
    assert checked[-1] == result
    assert all(v["coverage"]["complete"] == (not v["gaps"] and v["next_cursor"] is None)
               for v in checked)


def test_sec_runtime_setup_failure_is_closed(tool_fixture, monkeypatch):
    from src.sec_research import tool_execution
    def fail():
        raise RuntimeError("PRIVATE sk-setup-secret")
    monkeypatch.setattr(tool_execution, "active_budget", fail)
    result = asyncio.run(tool_execution.invoke_sec_tool("list_sec_filings", dict(issuer=CIK)))
    assert result["status"] == "unavailable"
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
@pytest.mark.parametrize("alphabet", ["ordinary SEC passage ", "\u4e2d\u6587"], ids=["ascii", "utf8"])
def test_default_sec_document_budget_returns_usable_text_without_skips(
        channel, alphabet, registry, document_rig, monkeypatch):
    from src.agents import config
    from tests.test_sec_research_tool_service import doc_tool
    from tests.test_sec_research_document_service import FILING_ID
    from src.sec_research.document_queries import _decode, _filters
    monkeypatch.setattr(config, "get_agent_config", lambda: config.AgentConfig())
    r = document_rig
    service, _ = doc_tool(r)
    wire(monkeypatch, service)
    body = (alphabet * 7000)[:14000]
    r.enqueue(body.encode(), mime="text/plain")
    index = unwrap(asyncio.run(dispatch(channel, registry, "read_sec_filing", dict(filing_id=FILING_ID))))
    cursor, emitted, end_byte = index["data"]["text_start_cursor"], [], 0
    while cursor:
        assert _decode(cursor)["filters_hash"] == _filters(None, None, 6000)
        payload = asyncio.run(dispatch(channel, registry, "read_sec_filing", dict(filing_id=FILING_ID, cursor=cursor)))
        assert len(payload) <= 8000
        page = unwrap(payload)
        assert page["data"]["passages"], page
        assert not page["gaps"]
        for passage in page["data"]["passages"]:
            citation = passage["citation"]
            assert citation["start_byte"] == end_byte
            end_byte = citation["end_byte"]
            assert body.encode()[citation["start_byte"]:end_byte].decode() == passage["text"]
            assert len(passage["text"]) <= 6000
            emitted.append(passage["text"])
        cursor = page["next_cursor"]
    assert "".join(emitted) == body and end_byte == len(body.encode())
    assert len(r.requests) == 2


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_default_search_returns_complete_matches_with_bounded_context(channel, registry, document_rig, monkeypatch):
    from src.agents import config
    from tests.test_sec_research_tool_service import doc_tool
    from tests.test_sec_research_document_service import FILING_ID
    r = document_rig
    monkeypatch.setattr(config, "get_agent_config", lambda: config.AgentConfig())
    service, _ = doc_tool(r)
    wire(monkeypatch, service)
    body = "\u4e2d" * 4000 + "needle" + "\u6587" * 4000 + "needle" + "\u4e2d" * 4000
    r.enqueue(body.encode(), mime="text/plain")
    cursor, matches = None, []
    for _ in range(3):
        payload = asyncio.run(dispatch(channel, registry, "read_sec_filing",
            dict(filing_id=FILING_ID, query="needle", cursor=cursor)))
        assert len(payload) <= 8000
        page = unwrap(payload)
        assert page["data"]["passages"] and not page["gaps"]
        citation = page["data"]["passages"][0]["citation"]
        assert body.encode()[citation["match_start_byte"]:citation["match_end_byte"]] == b"needle"
        assert body.encode()[citation["start_byte"]:citation["end_byte"]].decode() == page["data"]["passages"][0]["text"]
        matches.append(citation["match_start_byte"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert matches == [12000, 24006] and len(r.requests) == 2
