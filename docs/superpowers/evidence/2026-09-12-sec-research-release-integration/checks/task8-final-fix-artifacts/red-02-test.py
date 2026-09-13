"""Delegation keeps real producer, child, adapter and SEC ownership boundaries."""

import asyncio
from contextlib import contextmanager
import json
import threading
from types import SimpleNamespace

import httpx2
import pytest

from src.agents.anthropic_agent.agent import _build_anthropic_tools_list
from src.agents.openai_agent.tools import create_openai_tools
from src.agents.shared.output_boundary import current_output_guard, output_scope
from src.auth_drivers.runtime_binding import (
    activate_runtime_auth, capture_runtime_auth, current_runtime_auth,
)
from tests.test_research_output_events import anthropic_frames, collect, terminal
from tests.test_sec_research_tool_adapters import NAMES, unwrap, wire
from tests.test_sec_research_tool_service import (
    CIK, doc_tool, document_rig, seed, tool_fixture,
)
from tests.test_task_runtime_binding import add_key, isolated


PARENT_MODEL = "claude-opus-4-7"
CHILD_MODEL = "claude-sonnet-4-6"
KEY = "fixture-delegated-selected-key"
DELEGATE = dict(subagent="deep_researcher", task="Read retained SEC evidence.", context_json="")


@pytest.fixture
def delegated(isolated, monkeypatch):
    from anthropic import Anthropic
    from src.agents import config
    from src.agents.anthropic_agent import agent

    settings = config.AgentConfig(web_openai_search=False, web_playwright=False,
        subagent_models={"deep_researcher": CHILD_MODEL}, subagent_max_turns={"deep_researcher": 3})
    monkeypatch.setattr(config, "get_agent_config", lambda: settings)
    monkeypatch.setattr(agent, "get_agent_config", lambda: settings)
    monkeypatch.setattr(agent, "_build_anthropic_tools_list", _build_anthropic_tools_list)
    monkeypatch.setattr("src.agents.openai_agent.tools.create_openai_tools", create_openai_tools)
    add_key(isolated.credentials, "anthropic", KEY)
    binding = capture_runtime_auth("anthropic")
    add_key(isolated.credentials, "anthropic", "fixture-delegated-replacement-key")
    state = SimpleNamespace(binding=binding, requests=[], child_results=[], parent_results=[],
        clients=[], closed=[], name=None, arguments=None, settings=settings)

    def reply(request):
        payload = json.loads(request.content)
        state.requests.append((payload, request.headers["x-api-key"],
                               current_runtime_auth("anthropic"), current_output_guard()))
        results = [block for message in payload["messages"]
                   if isinstance(message["content"], list)
                   for block in message["content"] if block["type"] == "tool_result"]
        parent = payload["model"] == PARENT_MODEL
        if results:
            (state.parent_results if parent else state.child_results).extend(results)
            blocks = [{"type": "text", "text": "Parent complete." if parent else "Child complete."}]
            stop = "end_turn"
        else:
            blocks = [{"type": "tool_use", "id": "delegate" if parent else "sec-child",
                       "name": "delegate_to_subagent" if parent else state.name,
                       "input": DELEGATE if parent else state.arguments}]
            stop = "tool_use"
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
            text=anthropic_frames(payload["model"], blocks, stop=stop))

    class Transport(httpx2.MockTransport):
        def close(self):
            state.closed.append((current_runtime_auth("anthropic"), current_output_guard()))
            super().close()

    def construct(**kwargs):
        client = Anthropic(**kwargs, http_client=httpx2.Client(transport=Transport(reply)))
        state.clients.append(client)
        return client

    monkeypatch.setattr("anthropic.Anthropic", construct)

    async def parent():
        return await collect(agent.run_query_stream("Read the SEC evidence.",
            model=PARENT_MODEL, effort="low", dal=object()))

    state.parent = parent
    yield state
    for client in state.clients:
        client.close()


@pytest.mark.parametrize("entrypoint", ["parent", "sync-dispatch", "sync-tool", "openai-tool"])
@pytest.mark.parametrize("name", NAMES)
def test_delegated_sec_envelope_reaches_child_next_turn(
        name, entrypoint, delegated, tool_fixture, document_rig, monkeypatch):
    from src.agents.anthropic_agent.tools import execute_tool
    from src.agents.shared.subagent import dispatch_subagent
    from src.sec_research.tool_results import serialize_sec_result
    from tests.test_sec_research_document_service import FILING_ID

    d, f = delegated, tool_fixture
    if name == "read_sec_filing":
        service, acquisitions = doc_tool(document_rig)
        document_rig.enqueue(b"<p>Retained document 391035000000.</p>")
        index = service.invoke(name, dict(filing_id=FILING_ID))
        arguments = dict(filing_id=FILING_ID, freshness="stored",
                         cursor=index["data"]["text_start_cursor"])
        calls = document_rig.requests
    else:
        seed(f)
        service, acquisitions, calls = f.service, f.acquisitions, f.transport.calls
        first = service.invoke(name, dict(issuer=CIK, freshness="stored", limit=1))
        if name == "list_sec_filings":
            arguments = dict(issuer=CIK, limit=1, cursor=first["next_cursor"])
        else:
            arguments = dict(issuer=CIK, fact_ids=[first["data"][0]["fact_id"]])
    wire(monkeypatch, service)
    expected = serialize_sec_result(service.invoke(name, arguments), name)
    page = unwrap(expected)
    assert page["status"] == "ok" and page["gaps"] == []
    if name == "get_sec_financial_facts":
        assert page["data"][0]["value"] == "1234567890123456789.123"
    elif name == "list_sec_filings":
        assert page["data"][0]["cik"] == CIK
        assert page["data"][0]["filing_id"] != first["data"][0]["filing_id"]
        assert page["next_cursor"] is None
    else:
        assert page["data"]["document"] == index["data"]["document"]
        assert page["data"]["passages"][0]["text"] == "Retained document 391035000000."
    counts = len(acquisitions), len(calls)
    d.name, d.arguments = name, arguments

    async def openai_tool():
        from agents.tool_context import ToolContext
        tool = next(t for t in create_openai_tools(None) if t.name == "tool_delegate_to_subagent")
        payload = json.dumps(DELEGATE)
        context = ToolContext(context=None, tool_name=tool.name,
            tool_call_id="delegate", tool_arguments=payload)
        return unwrap(await tool.on_invoke_tool(context, payload))

    with output_scope() as guard, activate_runtime_auth(d.binding):
        if entrypoint == "parent":
            assert terminal(asyncio.run(d.parent()))["answer"] == "Parent complete."
            result = unwrap(d.parent_results[0]["content"])
        elif entrypoint == "sync-dispatch":
            result = dispatch_subagent("deep_researcher", DELEGATE["task"], dal=object())
        elif entrypoint == "sync-tool":
            result = unwrap(execute_tool("delegate_to_subagent", DELEGATE, object()))
        else:
            result = asyncio.run(openai_tool())
        assert [item["content"] for item in d.child_results] == [expected], (
            "delegated SEC dispatch must deliver the complete successful envelope to the child")
        assert result["error"] is None and result["answer"] == "Child complete."
        assert (result["provider"], result["model"], result["tools_used"]) == ("anthropic", CHILD_MODEL, [name])
        assert current_runtime_auth("anthropic") is d.binding
        assert current_output_guard() is guard
        assert all(key == KEY and binding is d.binding and scope is guard
                   for _, key, binding, scope in d.requests)
        child_requests = [payload for payload, *_ in d.requests if payload["model"] == CHILD_MODEL]
        assert len(child_requests) == 2
        for payload in child_requests:
            names = {tool["name"] for tool in payload["tools"]}
            assert set(NAMES) <= names and "delegate_to_subagent" not in names
            assert "web_browse" not in names
        assert d.clients[-1].is_closed(), "child client must close before dispatch returns"
        assert d.closed == [(d.binding, guard)]
    assert (len(acquisitions), len(calls)) == counts
    assert current_output_guard() is None and current_runtime_auth("anthropic") is None


def test_parent_cancel_joins_delegated_sec_before_releasing_protection(
        delegated, isolated, tool_fixture, monkeypatch):
    from data_sources.sec_transport import SecTransport
    from src.research_run_manager import execute_research_run
    from src.sec_research.capture_lock import research_operation

    d, f = delegated, tool_fixture
    d.name, d.arguments = "list_sec_filings", dict(issuer=CIK)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(f.store.paths.market_db_path))
    entered, stopped, closing, release, finished = (threading.Event() for _ in range(5))
    observed, calls = [], []

    class Governor:
        def reserve_request_start(self, *, check=None):
            entered.set()
            assert stopped.wait(3), "cancellation never reached the SEC transport"
            check()
            return 0

    class Session:
        def get(self, *args, **kwargs):
            calls.append(args)
            pytest.fail("cancelled delegated work dispatched SEC transport")

        def close(self):
            stopped.set()

    transport = SecTransport(user_agent="ArkScope tests@example.test", session=Session(),
        governor=Governor(), max_rate_limit_retries=0)

    @contextmanager
    def acquire():
        observed.append((current_runtime_auth("anthropic"), current_output_guard()))
        try:
            yield f.captures, transport, None
        finally:
            closing.set()
            assert release.wait(3), "test did not release SEC cleanup"
            observed.append((current_runtime_auth("anthropic"), current_output_guard()))
            finished.set()

    f.service.acquisition_factory = acquire
    wire(monkeypatch, f.service)
    isolated.threads.ensure_thread(id="delegated-thread", title="Delegated cancellation")
    isolated.runs.create_run(id="delegated-run", thread_id="delegated-thread", question="Read SEC.",
        ticker=None, provider="anthropic", model=PARENT_MODEL, effort="low",
        auth_mode=d.binding.auth_mode, credential_id=d.binding.credential_id)

    async def run():
        with output_scope("fixture-foreign-scope-key") as guard:
            task = asyncio.create_task(execute_research_run(run_id="delegated-run",
                run_store=isolated.runs, thread_store=isolated.threads, dal=object(),
                history=[], auth_binding=d.binding))
            try:
                assert await asyncio.to_thread(entered.wait, 3), "parent never awaited real delegated SEC work"
                task.cancel()
                assert await asyncio.to_thread(closing.wait, 3), "SEC work was not stopped"
                for _ in range(2):
                    task.cancel()
                    await asyncio.sleep(0)
                    assert not task.done(), "parent escaped before delegated SEC cleanup joined"
                    assert isolated.runs.get_run("delegated-run").status == "running"
                    assert d.closed == [], "child client closed while SEC still owned resources"
                    with pytest.raises(ValueError, match="sec_research_operation_busy"):
                        with research_operation(f.store.paths.capture_root, exclusive=True):
                            pass
                release.set()
                await task
                assert finished.is_set()
                assert observed == [(d.binding, guard), (d.binding, guard)]
                assert d.closed == [(d.binding, guard)]
                assert d.clients[-1].is_closed()
                assert current_output_guard() is guard
                assert current_runtime_auth("anthropic") is None
            finally:
                stopped.set()
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        with research_operation(f.store.paths.capture_root, exclusive=True):
            pass

    asyncio.run(run())
    assert isolated.runs.get_run("delegated-run").status == "cancelled"
    assert not calls and not d.child_results and not d.parent_results
    assert len(d.requests) == 2
    assert not f.store.snapshots(CIK, "catalog") and not f.store.snapshots(CIK, "facts")
    assert current_output_guard() is None


def test_delegated_sec_rejects_credential_inherited_from_foreign_provider(
        delegated, tool_fixture, monkeypatch):
    from src.agents.shared.output_boundary import OutputBoundaryError
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding

    d, f = delegated, tool_fixture
    seed(f)
    wire(monkeypatch, f.service)
    d.name, d.arguments = "get_sec_financial_facts", dict(issuer=CIK, freshness="stored")
    secret = "1234567890123456789.123"
    foreign = RuntimeAuthBinding("openai", "db_api_key", "api_key", "local:foreign", secret)
    with output_scope() as guard:
        with activate_runtime_auth(foreign):
            pass
        with activate_runtime_auth(d.binding):
            assert terminal(asyncio.run(d.parent()))["answer"] == "Parent complete."
            assert len(d.child_results) == 1
            rejected = unwrap(d.child_results[0]["content"])
            assert rejected.get("status") == "unavailable" and rejected["data"] == []
            assert rejected["gaps"] == [{"code": "sec_result_invalid"}]
            assert secret not in json.dumps(d.child_results + d.parent_results)
            assert all(scope is guard and binding is d.binding for _, _, binding, scope in d.requests)
            with pytest.raises(OutputBoundaryError):
                guard.check(secret)
        assert current_runtime_auth("anthropic") is None
    assert f.acquisitions == [] and f.transport.calls == []
