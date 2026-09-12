"""Real native producer and governed metadata cancellation regression owners."""

import asyncio
from contextlib import contextmanager
import json
import threading

import httpx2
import pytest

from src.agents.anthropic_agent.agent import _build_anthropic_tools_list as build_tools
from src.agents.shared.events import EventType
from tests.test_research_output_events import anthropic_frames, collect, terminal
from tests.test_sec_research_tool_adapters import NAMES, unwrap, wire
from tests.test_sec_research_tool_service import (
    CIK, doc_tool, document_rig, seed, tool_fixture,
)
from tests.test_task_runtime_binding import isolated


@pytest.mark.parametrize("name", NAMES)
def test_anthropic_actual_stream_returns_exact_sec_result_to_model(
        name, isolated, tool_fixture, document_rig, monkeypatch):
    from anthropic import Anthropic
    from src.agents import config
    from src.agents.anthropic_agent import agent
    from src.auth_drivers import live_resolver
    from src.sec_research.tool_results import serialize_sec_result
    from tests.test_sec_research_document_service import FILING_ID

    settings = config.AgentConfig(web_openai_search=False, web_playwright=False)
    monkeypatch.setattr(agent, "get_agent_config", lambda: settings)
    monkeypatch.setattr(agent, "_build_anthropic_tools_list", build_tools)
    if name == "read_sec_filing":
        service, _ = doc_tool(document_rig)
        document_rig.enqueue(b"<p>Consolidated 391035000000.</p>")
        index = service.invoke(name, dict(filing_id=FILING_ID))
        arguments = dict(filing_id=FILING_ID, freshness="stored",
                         cursor=index["data"]["text_start_cursor"])
    else:
        seed(tool_fixture)
        service = tool_fixture.service
        arguments = dict(issuer=CIK, freshness="stored")
    wire(monkeypatch, service)
    expected = serialize_sec_result(service.invoke(name, arguments), name)
    assert unwrap(expected)["status"] == "ok"
    requests, returned = [], []

    def reply(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert name in {tool["name"] for tool in payload["tools"]}
        if len(requests) == 1:
            blocks = [{"type": "tool_use", "id": "call_sec", "name": name,
                       "input": arguments}]
            stop = "tool_use"
        else:
            assert len(requests) == 2
            results = [block for message in payload["messages"]
                       if isinstance(message["content"], list)
                       for block in message["content"] if block["type"] == "tool_result"]
            assert len(results) == 1
            returned.append(results[0]["content"])
            blocks, stop = [{"type": "text", "text": "Research complete."}], "end_turn"
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
            text=anthropic_frames(payload["model"], blocks, stop=stop))

    with Anthropic(api_key="offline-native-sec-key",
            http_client=httpx2.Client(transport=httpx2.MockTransport(reply))) as client:
        monkeypatch.setattr(live_resolver, "live_anthropic_client", lambda: client)
        events = asyncio.run(collect(agent.run_query_stream(
            "Read the SEC evidence.", model="claude-sonnet-4-6", effort="low", dal=object())))
    assert terminal(events)["answer"] == "Research complete."
    assert returned == [expected], "actual native stream changed or lost the SEC envelope"
    assert [event.data["tool"] for event in events if event.type == EventType.tool_end] == [name]


@pytest.mark.parametrize("issuer", [CIK, "AAPL"], ids=["submissions", "issuer-map"])
@pytest.mark.parametrize("stop_kind", ["timeout", "cancel"])
def test_owned_metadata_worker_never_dispatches_after_governor_stop(
        issuer, stop_kind, tool_fixture, monkeypatch):
    from data_sources.sec_transport import SecTransport
    from src.sec_research.tool_execution import invoke_sec_tool
    from tests.test_sec_transport import _Response

    f = tool_fixture
    entered, stopped, finished = threading.Event(), threading.Event(), threading.Event()
    calls, checks = [], []

    class Governor:
        def reserve_request_start(self, *, check=None):
            checks.append(check)
            entered.set()
            assert stopped.wait(3), "owned worker was not stopped"
            if check is not None:
                check()
            return 0

    class Session:
        def get(self, url, **kwargs):
            calls.append((url, stopped.is_set()))
            return _Response(body=f.transport.responses[url])

        def close(self):
            stopped.set()

    transport = SecTransport(user_agent="ArkScope tests@example.test", session=Session(),
                             governor=Governor(), max_rate_limit_retries=0)

    @contextmanager
    def acquire():
        try:
            yield f.captures, transport, None
        finally:
            transport.close()
            finished.set()

    f.service.acquisition_factory = acquire
    wire(monkeypatch, f.service)

    async def run():
        task = asyncio.create_task(invoke_sec_tool("list_sec_filings", dict(issuer=issuer),
            timeout_s=0.2 if stop_kind == "timeout" else None))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            if stop_kind == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                assert (await task)["gaps"] == [{"code": "sec_result_timeout"}]
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())
    assert finished.is_set(), "tool returned before acquisition was joined"
    assert calls == [], "metadata dispatch occurred after cancellation during governor wait"
    assert len(checks) == 1 and callable(checks[0])
    assert not f.store.snapshots(CIK, "catalog")
    assert not f.store.snapshots(CIK, "facts")
