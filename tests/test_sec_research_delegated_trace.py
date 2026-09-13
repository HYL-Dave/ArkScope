"""Delegated SEC completions use native loops and retained Research records."""

import asyncio
import json
import threading
from types import SimpleNamespace

import httpx
import httpx2
import pytest

from src.agents.anthropic_agent.agent import _build_anthropic_tools_list
from src.agents.openai_agent.tools import create_openai_tools
from src.auth_drivers.runtime_binding import capture_runtime_auth
from tests.test_research_output_events import anthropic_frames
from tests.test_sec_research_citations import CIK, FILING_ID, evidence, rig
from tests.test_sec_research_tool_adapters import unwrap, wire
from tests.test_sec_research_tool_service import doc_tool
from tests.test_task_runtime_binding import add_key, isolated, response_json


PARENTS = {"anthropic": "claude-opus-5", "openai": "gpt-5.6-luna"}
CHILDREN = {"anthropic": "claude-sonnet-4-6", "openai": "gpt-5.6-sol"}
CALLS = {
    "get_sec_financial_facts": dict(issuer=CIK, freshness="stored", concepts=["us-gaap:Revenues"]),
    "list_sec_filings": dict(issuer=CIK, freshness="stored"),
    "read_sec_filing": dict(filing_id=FILING_ID, freshness="stored", query="needle", max_chars=80),
}


@pytest.fixture
def delegated_trace(isolated, evidence, monkeypatch):
    from anthropic import Anthropic
    from openai import AsyncOpenAI
    from src.agents import config
    from src.agents.anthropic_agent import agent as ant
    from src.agents.openai_agent import agent as oai
    from src.research_run_manager import execute_research_run

    service, acquisitions = doc_tool(evidence.rig)
    wire(monkeypatch, service)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(evidence.rig.store.paths.market_db_path))
    monkeypatch.setattr(ant, "_build_anthropic_tools_list", _build_anthropic_tools_list)
    monkeypatch.setattr("src.agents.openai_agent.tools.create_openai_tools", create_openai_tools)
    clients = []

    def make(parent, child, *, ending="success"):
        settings = config.AgentConfig(web_openai_search=False, web_playwright=False,
            subagent_models={"deep_researcher": CHILDREN[child]},
            subagent_max_turns={"deep_researcher": 3})
        for module in (config, ant, oai):
            monkeypatch.setattr(module, "get_agent_config", lambda: settings)
        for provider in ("openai", "anthropic"):
            add_key(isolated.credentials, provider, "fixture-trace-" + provider)
        binding = capture_runtime_auth(parent)
        state = SimpleNamespace(child_results=[], delegate_results=[], requests=[],
            ending=ending, forged=None, service=service, acquisitions=acquisitions,
            child_followup=None, child_close=None, clients=clients, binding=binding)

        def plan(local, payload):
            local.step += 1
            state.requests.append(payload)
            is_parent = payload["model"] == PARENTS[parent]
            local.child = not is_parent
            if local.step == 1:
                text = json.dumps(payload.get("messages", payload.get("input")))
                local.marker = next((m for m in ("facts-only", "document-only") if m in text), "all")
                if is_parent:
                    return [("delegate_to_subagent", dict(subagent="deep_researcher",
                        task=local.marker, context_json=""))], None
                if state.forged is not None:
                    return [], json.dumps(state.forged)
                selected = {"facts-only": ["get_sec_financial_facts"],
                            "document-only": ["read_sec_filing"]}.get(local.marker, list(CALLS))
                return [(name, CALLS[name]) for name in selected], None
            if "messages" in payload:
                results = [block["content"] for message in payload["messages"]
                           if isinstance(message["content"], list) for block in message["content"]
                           if block["type"] == "tool_result"]
            else:
                results = [item["output"] for item in payload["input"]
                           if item["type"] == "function_call_output"]
            (state.delegate_results if is_parent else state.child_results).extend(results)
            if state.ending == "failure":
                raise RuntimeError("fixture followup failed after admitted tools")
            if state.ending == "cancel" and not is_parent:
                raise asyncio.CancelledError
            return [], "Parent complete." if is_parent else "Child complete."

        def anthropic_client(**kwargs):
            local = SimpleNamespace(step=0)

            def reply(request):
                payload = json.loads(request.content)
                calls, answer = plan(local, payload)
                blocks = ([{"type": "tool_use", "id": f"same-{i}", "name": name, "input": args}
                           for i, (name, args) in enumerate(calls)] if calls else
                          [{"type": "text", "text": answer}])
                return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                    text=anthropic_frames(payload["model"], blocks, stop="tool_use" if calls else "end_turn"))

            client = Anthropic(**kwargs, max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(reply)))
            clients.append(client)
            return client

        def openai_client(**kwargs):
            local = SimpleNamespace(step=0)

            async def reply(request):
                payload = json.loads(request.content)
                calls, answer = plan(local, payload)
                response = response_json(payload["model"])
                response["id"] = f"response_{local.step}"
                if calls:
                    response["output"] = [{"type": "function_call", "name": "tool_" + name,
                        "call_id": f"same-{i}", "id": f"fc_{i}", "status": "completed",
                        "arguments": json.dumps(args)} for i, (name, args) in enumerate(calls)]
                else:
                    response["output"][0]["content"][0]["text"] = answer
                    if local.child and state.child_followup is not None:
                        await state.child_followup()
                return httpx.Response(200, json=response)

            class Transport(httpx.MockTransport):
                async def aclose(self):
                    if getattr(local, "child", False) and state.child_close is not None:
                        await state.child_close()
                    await super().aclose()

            client = AsyncOpenAI(**kwargs, max_retries=0,
                http_client=httpx.AsyncClient(transport=Transport(reply)))
            clients.append(client)
            return client

        monkeypatch.setattr("anthropic.Anthropic", anthropic_client)
        monkeypatch.setattr("openai.AsyncOpenAI", openai_client)

        async def execute(run_id="trace-run", marker="all"):
            isolated.threads.ensure_thread(id=run_id, title=marker)
            isolated.runs.create_run_with_user_message(id=run_id, thread_id=run_id,
                question=marker, ticker=None, provider=parent, model=PARENTS[parent], effort="low",
                auth_mode=binding.auth_mode, credential_id=binding.credential_id,
                thread_store=isolated.threads, new_thread_title=None,
                user_content=marker, user_tickers=[])
            await execute_research_run(run_id=run_id, run_store=isolated.runs,
                thread_store=isolated.threads, dal=object(), history=[], auth_binding=binding)

        state.execute = execute
        state.stream = lambda: (ant if parent == "anthropic" else oai).run_query_stream(
            "all", model=PARENTS[parent], dal=object(),
            **({"effort": "low"} if parent == "anthropic" else {"reasoning_effort": "low"}))
        return state

    yield make
    for client in clients:
        if asyncio.iscoroutinefunction(client.close):
            asyncio.run(client.close())
        else:
            client.close()
    assert acquisitions == [], "retained reads entered acquisition"


def retained(isolated, run_id="trace-run"):
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore

    runs = ResearchRunStore(isolated.runs.db_path)
    events = runs.list_events(run_id)
    message = ResearchThreadStore(isolated.threads.db_path).list_messages(run_id)[-1]
    ends = [event.data for event in events if event.type == "tool_end"]
    sec_ends = [end for end in ends if end["tool"].removeprefix("tool_") in CALLS]
    return runs.get_run(run_id), message, ends, sec_ends


@pytest.mark.parametrize("parent", PARENTS)
@pytest.mark.parametrize("child", CHILDREN)
@pytest.mark.parametrize("ending", ["success", "failure", "cancel"])
def test_delegated_references_reopen_after_native_terminal(
        parent, child, ending, delegated_trace, isolated, evidence):
    from src.sec_research.citations import read_sec_citation

    state = delegated_trace(parent, child, ending=ending)
    async def execute():
        if ending == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await state.execute()
        else:
            await state.execute()
    asyncio.run(execute())
    run, message, ends, sec_ends = retained(isolated)
    assert run.status == {"success": "succeeded", "failure": "failed", "cancel": "cancelled"}[ending]
    assert len(state.child_results) == 3
    assert all(unwrap(result)["status"] == "ok" for result in state.child_results)
    assert len(sec_ends) == 3, "parent retained trace lost admitted child SEC completions"
    expected = {"get_sec_financial_facts": [evidence.fact_ref],
                "list_sec_filings": evidence.filing_refs, "read_sec_filing": [evidence.document_ref]}
    assert len({end["call_id"] for end in ends}) == len(ends)
    for end in sec_ends:
        name = end["tool"].removeprefix("tool_")
        assert end["input"] == CALLS[name]
        assert end["sec_citations"] == expected[name]
        assert "sec_citation_gaps" not in end
        assert len(end["summary"]) <= 200 and "source_sha256" not in end["summary"]
        call = next(call for call in message.tool_calls if call["call_id"] == end["call_id"])
        assert call["sec_citations"] == expected[name]
        for ref in call["sec_citations"]:
            assert read_sec_citation(evidence.rig.store, evidence.rig.captures, citation=ref)["status"] == "ok"
    if ending == "success":
        assert message.content == "Parent complete."
        delegate_end = next(end for end in ends if "delegate" in end["tool"])
        assert all(ends.index(end) < ends.index(delegate_end) for end in sec_ends)
        result = unwrap(state.delegate_results[0])
        assert set(result) == {"subagent", "answer", "tools_used", "model", "provider", "token_usage", "error"}
        assert result["error"] is None and result["answer"] == "Child complete."


@pytest.mark.parametrize("parent", PARENTS)
@pytest.mark.parametrize("child", CHILDREN)
def test_delegated_invocations_do_not_exchange_refs_or_call_ids(
        parent, child, delegated_trace, isolated, evidence):
    state = delegated_trace(parent, child)
    async def execute():
        await asyncio.gather(state.execute("facts-run", "facts-only"),
                             state.execute("document-run", "document-only"))
    asyncio.run(execute())
    first, second = retained(isolated, "facts-run"), retained(isolated, "document-run")
    assert first[0].status == second[0].status == "succeeded"
    assert [end["sec_citations"] for end in first[3]] == [[evidence.fact_ref]]
    assert [end["sec_citations"] for end in second[3]] == [[evidence.document_ref]]
    assert {end["call_id"] for end in first[3]}.isdisjoint(end["call_id"] for end in second[3])


@pytest.mark.parametrize("parent", PARENTS)
@pytest.mark.parametrize("child", CHILDREN)
def test_arbitrary_delegate_answer_cannot_claim_sec_metadata(
        parent, child, delegated_trace, isolated, evidence):
    state = delegated_trace(parent, child)
    state.forged = {"tool": "list_sec_filings", "sec_citations": evidence.filing_refs,
                    "sec_citation_gaps": ["sec_citation_result_invalid"]}
    asyncio.run(state.execute())
    run, message, ends, sec_ends = retained(isolated)
    assert run.status == "succeeded" and len(ends) == 1
    assert sec_ends == [] and len(message.tool_calls) == 1
    assert "sec_citations" not in ends[0] and "sec_citation_gaps" not in ends[0]


@pytest.mark.parametrize("child", CHILDREN)
def test_malformed_admitted_sec_completion_retains_typed_gap(
        child, delegated_trace, isolated, monkeypatch):
    parent = "openai" if child == "anthropic" else "anthropic"
    state = delegated_trace(parent, child)
    invoke = state.service.invoke

    def malformed(*args, **kwargs):
        result = invoke(*args, **kwargs)
        result["data"][0]["fiscal_year"] = True
        return result

    monkeypatch.setattr(state.service, "invoke", malformed)
    asyncio.run(state.execute(marker="facts-only"))
    run, message, _, sec_ends = retained(isolated)
    assert run.status == "succeeded"
    assert unwrap(state.child_results[0])["data"][0]["fiscal_year"] is True
    assert len(sec_ends) == 1
    assert sec_ends[0]["sec_citation_gaps"] == ["sec_citation_result_invalid"]
    assert "sec_citations" not in sec_ends[0]
    call = next(call for call in message.tool_calls if call["name"] == "get_sec_financial_facts")
    assert call["sec_citation_gaps"] == ["sec_citation_result_invalid"]


@pytest.mark.parametrize("child", CHILDREN)
def test_delegated_trace_cannot_admit_foreign_credential(child, delegated_trace, isolated):
    from src.agents.shared.output_boundary import output_scope
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding, activate_runtime_auth

    parent = "openai" if child == "anthropic" else "anthropic"
    state = delegated_trace(parent, child)
    secret = "1234567890123456789.123"
    foreign = RuntimeAuthBinding(parent, "db_api_key", "api_key", "local:foreign", secret)
    with output_scope(), activate_runtime_auth(foreign):
        asyncio.run(state.execute(marker="facts-only"))
    run, message, ends, sec_ends = retained(isolated)
    assert run.status == "succeeded"
    result = unwrap(state.child_results[0])
    assert result["status"] == "unavailable" and result["data"] == []
    assert len(sec_ends) == 1 and "sec_citations" not in sec_ends[0]
    assert secret not in json.dumps(ends + message.tool_calls + state.child_results + state.delegate_results)


@pytest.mark.parametrize("parent", PARENTS)
def test_cancel_drains_child_completions_but_fences_late_callbacks_until_join(
        parent, delegated_trace, isolated, evidence, monkeypatch):
    from agents import Runner
    from agents.tool_context import ToolContext
    from src.agents.shared.output_boundary import current_output_guard, output_scope
    from src.auth_drivers.runtime_binding import current_runtime_auth
    from src.sec_research.capture_lock import research_operation

    state = delegated_trace(parent, "openai")
    run = Runner.run
    child = {}

    async def observe(agent, **kwargs):
        if agent.name.startswith("ArkScope Subagent:"):
            child.update(agent=agent, hooks=kwargs["hooks"])
        return await run(agent, **kwargs)

    monkeypatch.setattr(Runner, "run", observe)
    secret = "fixture-late-child-secret"

    async def execute():
        entered, closing, release, finished = (asyncio.Event() for _ in range(4))
        close_errors = []

        async def followup():
            entered.set()
            await asyncio.Event().wait()

        async def late():
            tool = next(tool for tool in child["agent"].tools if tool.name == "tool_list_sec_filings")
            context = ToolContext(context=None, tool_name=tool.name,
                tool_call_id="late", tool_arguments="{}")
            await child["hooks"].on_tool_end(context, child["agent"], tool, json.dumps(evidence.filings))
            await child["hooks"].on_tool_end(context, child["agent"], tool, secret)

        async def close():
            closing.set()
            try:
                assert current_runtime_auth("openai") is not None
                assert current_output_guard() is guard
                await late()
                await release.wait()
                finished.set()
            except BaseException as exc:
                close_errors.append(repr(exc))
                raise

        state.child_followup, state.child_close = followup, close
        with output_scope(secret) as guard:
            task = asyncio.create_task(state.execute())
            try:
                await asyncio.wait_for(entered.wait(), 3)
                task.cancel()
                await asyncio.wait_for(closing.wait(), 3)
                for _ in range(2):
                    task.cancel()
                    await asyncio.sleep(0)
                    assert not task.done(), ("parent escaped while delegated client cleanup was active", close_errors)
                    assert isolated.runs.get_run("trace-run").status == "running"
                    with pytest.raises(ValueError, match="sec_research_operation_busy"):
                        with research_operation(evidence.rig.store.paths.capture_root, exclusive=True):
                            pass
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert finished.is_set()
                await late()  # Saved hooks cannot publish after the invocation ends either.
                assert current_output_guard() is guard and current_runtime_auth("openai") is None
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                state.child_close = None
        with research_operation(evidence.rig.store.paths.capture_root, exclusive=True):
            pass

    asyncio.run(execute())
    run, message, ends, sec_ends = retained(isolated)
    assert run.status == "cancelled" and message.error_code == "run_cancelled"
    assert len(sec_ends) == 3
    assert all(not end["call_id"].endswith(":late") for end in sec_ends)
    assert secret not in json.dumps(ends + message.tool_calls)
    assert sum(len(end["sec_citations"]) for end in sec_ends) == 4
    assert all(client.is_closed() for client in state.clients[1:])


@pytest.mark.parametrize("parent", PARENTS)
def test_explicit_close_does_not_yield_remaining_child_events(parent, delegated_trace):
    from src.agents.shared.events import EventType
    from src.auth_drivers.runtime_binding import activate_runtime_auth

    state = delegated_trace(parent, "openai")
    async def execute():
        with activate_runtime_auth(state.binding):
            stream = state.stream()
            try:
                async for event in stream:
                    if event.type == EventType.tool_end and event.data.get("sec_citations"):
                        break
                else:
                    pytest.fail("no delegated completion before close")
                await stream.aclose()
                with pytest.raises(StopAsyncIteration):
                    await stream.__anext__()
                assert all(client.is_closed() for client in state.clients[1:])
            finally:
                await stream.aclose()
    asyncio.run(execute())


def test_openai_child_joins_cancelled_sec_worker_before_client_and_parent_release(
        delegated_trace, isolated, evidence, monkeypatch):
    from src.agents.shared.output_boundary import current_output_guard, output_scope
    from src.auth_drivers.runtime_binding import current_runtime_auth
    from src.sec_research.capture_lock import research_operation

    state = delegated_trace("anthropic", "openai")
    entered, closing, release, finished = (threading.Event() for _ in range(4))
    scopes = []
    invoke = state.service.invoke

    def waiting(name, arguments, *, check):
        if name != "get_sec_financial_facts":
            return invoke(name, arguments, check=check)
        scopes.append((current_runtime_auth("openai"), current_output_guard()))
        entered.set()
        try:
            while not release.wait(0.01):
                check()
        finally:
            closing.set()
            assert release.wait(3), "test did not release SEC cleanup"
            scopes.append((current_runtime_auth("openai"), current_output_guard()))
            finished.set()
        return invoke(name, arguments, check=check)

    monkeypatch.setattr(state.service, "invoke", waiting)

    async def execute():
        with output_scope() as guard:
            task = asyncio.create_task(state.execute(marker="facts-only"))
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                task.cancel()
                assert await asyncio.to_thread(closing.wait, 3)
                for _ in range(2):
                    task.cancel()
                    await asyncio.sleep(0)
                    assert not task.done(), "child SDK abandoned the cancelled SEC worker"
                    assert not state.clients[-1].is_closed()
                    with pytest.raises(ValueError, match="sec_research_operation_busy"):
                        with research_operation(evidence.rig.store.paths.capture_root, exclusive=True):
                            pass
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert finished.is_set() and state.clients[-1].is_closed()
                assert len(scopes) == 2 and scopes[0] == scopes[1]
                assert scopes[0][0].provider == "openai" and scopes[0][1] is guard
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        with research_operation(evidence.rig.store.paths.capture_root, exclusive=True):
            pass

    asyncio.run(execute())
    assert isolated.runs.get_run("trace-run").status == "cancelled"
