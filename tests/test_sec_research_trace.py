"""Call-bound SEC evidence through real producer loops, with offline providers."""

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import httpx
import httpx2
import pytest

from src.agents.shared.events import AgentEvent, EventType
from src.agents.shared.output_boundary import OutputBoundaryError, output_scope
from src.agents.shared.output_events import protect_events
from tests.test_research_output_events import anthropic_frames, collect, terminal
from tests.test_sec_research_citations import evidence, rig
from tests.test_task_runtime_binding import isolated, response_json


CHANNELS = ("openai", "anthropic", "chatgpt", "claude")
SECRET = "trace-private-fixture-value"


def test_sec_tool_end_preserves_whole_citations_by_call_id(evidence):
    from src.api.routes.query import accumulate_tool_calls

    events = [
        ("tool_start", {"tool": "read_sec_filing", "call_id": "first", "input": {"index": 1}}),
        ("tool_start", {"tool": "read_sec_filing", "call_id": "second", "input": {"index": 2}}),
        ("tool_end", {"tool": "read_sec_filing", "call_id": "first", "summary": "first preview",
                      "sec_citations": [evidence.document_ref]}),
        ("tool_end", {"tool": "read_sec_filing", "call_id": "second", "summary": "second preview",
                      "sec_citation_gaps": ["sec_citation_result_invalid"]}),
    ]
    before = deepcopy(events)
    rows = accumulate_tool_calls(events)
    assert rows == [
        {"name": "read_sec_filing", "input": {"index": 1}, "call_id": "first",
         "result_preview": "first preview", "sec_citations": [evidence.document_ref]},
        {"name": "read_sec_filing", "input": {"index": 2}, "call_id": "second",
         "result_preview": "second preview", "sec_citation_gaps": ["sec_citation_result_invalid"]},
    ]
    assert accumulate_tool_calls(events[:2] + list(reversed(events[2:]))) == rows
    assert events == before
    rows[0]["sec_citations"][0]["start_byte"] = -1
    assert events == before


def test_idless_events_never_consume_identified_calls(evidence):
    from src.api.routes.query import accumulate_tool_calls

    events = [
        ("tool_start", {"tool": "legacy", "input": {"legacy": True}}),
        ("tool_start", {"tool": "read_sec_filing", "call_id": "pending", "input": {"index": 0}}),
        ("tool_end", {"tool": "read_sec_filing", "call_id": "end-only", "input": {"index": 1},
                      "summary": "cited", "sec_citations": [evidence.document_ref]}),
        ("tool_end", {"tool": "legacy", "summary": "legacy done"}),
    ]
    assert accumulate_tool_calls(events) == [
        {"name": "legacy", "input": {"legacy": True}, "result_preview": "legacy done"},
        {"name": "read_sec_filing", "call_id": "pending", "input": {"index": 0}, "result_preview": None},
        {"name": "read_sec_filing", "call_id": "end-only", "input": {"index": 1},
         "result_preview": "cited", "sec_citations": [evidence.document_ref]},
    ]


def test_duplicate_identified_events_do_not_duplicate_or_exchange_references(evidence):
    from src.api.routes.query import accumulate_tool_calls

    start = ("tool_start", {"tool": "read_sec_filing", "call_id": "same", "input": {"index": 0}})
    end = ("tool_end", {"tool": "read_sec_filing", "call_id": "same", "input": {"index": 0},
                        "summary": "cited", "sec_citations": [evidence.document_ref]})
    conflict = ("tool_end", {**end[1], "summary": "wrong", "sec_citations": [evidence.fact_ref]})
    expected = [{"name": "read_sec_filing", "call_id": "same", "input": {"index": 0},
                 "result_preview": "cited", "sec_citations": [evidence.document_ref]}]
    assert accumulate_tool_calls([start, start, end, start, end, conflict]) == expected
    assert accumulate_tool_calls([end, start, end]) == expected


@pytest.mark.parametrize("name,want", [
    ("mcp__ark__tool_read_sec_filing", "read_sec_filing"),
    ("tool_read_sec_filing", "read_sec_filing"),
    ("mcp__foreign__read_sec_filing", "mcp__foreign__read_sec_filing"),
    ("prefix_tool_read_sec_filing", "prefix_tool_read_sec_filing"),
    ("tool_tool_read_sec_filing", "tool_read_sec_filing"),
])
def test_trace_normalizes_only_owned_prefixes(name, want):
    from src.api.routes.query import accumulate_tool_calls

    assert accumulate_tool_calls([("tool_end", {"tool": name, "input": {"x": 1}})]) == [
        {"name": want, "input": {"x": 1}, "result_preview": None}]


@pytest.fixture
def trace_stores(tmp_path):
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore

    db = tmp_path / "trace-profile.db"
    runs, threads = ResearchRunStore(db), ResearchThreadStore(db)
    threads.ensure_thread(id="trace-thread", title="Question")
    runs.create_run(id="trace-run", thread_id="trace-thread", question="Question", ticker=None,
        provider="openai", model="gpt-5.4-mini", effort="low", auth_mode="api_key", credential_id=None)
    threads.append_message(thread_id="trace-thread", role="user", content="Question")
    return runs, threads


def test_sec_citations_roundtrip_event_message_and_legacy_rows(evidence, trace_stores):
    from src.api.routes import query, research
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore, build_thread_history

    runs, threads = trace_stores
    events = [
        ("tool_end", {"tool": "read_sec_filing", "call_id": "document", "input": {"part": 1},
                      "summary": "preview", "sec_citations": [evidence.document_ref]}),
        ("tool_end", {"tool": "get_sec_financial_facts", "call_id": "facts", "input": {},
                      "summary": "facts", "sec_citations": [evidence.fact_ref]}),
        ("tool_end", {"tool": "list_sec_filings", "call_id": "filings", "input": {},
                      "summary": "filings", "sec_citations": evidence.filing_refs}),
        ("tool_end", {"tool": "list_sec_filings", "call_id": "gap", "summary": "bad",
                      "sec_citation_gaps": ["sec_citation_result_invalid"]}),
        ("tool_end", {"tool": "legacy", "summary": "old"}),
    ]
    for kind, data in events:
        runs.append_event("trace-run", kind, data)
    reopened = ResearchRunStore(runs.db_path)
    assert [(event.type, event.data) for event in reopened.list_events("trace-run")] == events
    query._persist_assistant_turn(threads, thread_id="trace-thread", run_id="trace-run",
        done_data={"answer": "Answer", "provider": "openai", "model": "gpt-5.4-mini"},
        collected=[(event.type, event.data) for event in reopened.list_events("trace-run")], elapsed=1)
    reopened.mark_terminal("trace-run", "succeeded")
    threads = ResearchThreadStore(threads.db_path)
    message = research.list_research_messages("trace-thread", store=threads)["messages"][-1]
    assert message["tool_calls"][0] == {"name": "read_sec_filing", "call_id": "document",
        "input": {"part": 1}, "result_preview": "preview", "sec_citations": [evidence.document_ref]}
    assert message["tool_calls"][1]["sec_citations"] == [evidence.fact_ref]
    assert message["tool_calls"][2]["sec_citations"] == evidence.filing_refs
    assert message["tool_calls"][3]["sec_citation_gaps"] == ["sec_citation_result_invalid"]
    assert message["tool_calls"][4] == {"name": "legacy", "input": None, "result_preview": "old"}
    assert build_thread_history(threads, "trace-thread") == [
        {"role": "user", "content": "Question"}, {"role": "assistant", "content": "Answer"}]
    threads.set_thread_archived("trace-thread", archived=True)
    assert research.list_research_messages("trace-thread", store=threads)["messages"][-1] == message


@pytest.mark.parametrize("terminal", ["restart", "no-task-cancel"])
def test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls(terminal, evidence, trace_stores):
    from src.api.routes import research
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore

    runs, threads = trace_stores
    # 602 events, with the only citation in the very last completion.
    for index in range(301):
        data = {"tool": "read_sec_filing", "call_id": f"call-{index}", "input": {"index": index}}
        runs.append_event("trace-run", "tool_start", data)
        runs.append_event("trace-run", "tool_end", {**data, "summary": f"preview-{index}",
            **({"sec_citations": [evidence.document_ref]} if index == 300 else {})})
    assert len(runs.list_events("trace-run")) == 500
    runs = ResearchRunStore(runs.db_path)
    if terminal == "restart":
        assert runs.reconcile_interrupted(thread_store=threads) == ["trace-run"]
        assert runs.reconcile_interrupted(thread_store=threads) == []
    else:
        research.cancel_research_run_route("trace-run", run_store=runs, thread_store=threads)
        research.cancel_research_run_route("trace-run", run_store=runs, thread_store=threads)
    messages = ResearchThreadStore(threads.db_path).list_messages("trace-thread")
    assert len(messages) == 2
    assert len(messages[-1].tool_calls) == 301
    assert messages[-1].tool_calls[-1] == {"name": "read_sec_filing", "call_id": "call-300",
        "input": {"index": 300}, "result_preview": "preview-300", "sec_citations": [evidence.document_ref]}
    assert messages[-1].error_code == ("run_interrupted" if terminal == "restart" else "run_cancelled")
    assert len(runs.list_events("trace-run")) == 500
    assert len(runs.list_events("trace-run", after=500)) == 103


@pytest.mark.parametrize("partial", [None, [], [
    {"name": "read_sec_filing", "call_id": "saved", "input": {}, "result_preview": None},
    {"name": "other", "call_id": "caller-only", "input": {"x": 1}, "result_preview": "extra"},
]])
def test_terminalization_reconciles_partial_caller_trace(evidence, trace_stores, partial):
    runs, threads = trace_stores
    runs.append_event("trace-run", "tool_end", {"tool": "read_sec_filing", "call_id": "saved",
        "input": {"retained": True}, "summary": "saved", "sec_citations": [evidence.document_ref]})
    runs.terminalize_error_with_message(thread_store=threads, run_id="trace-run", status="failed",
        error="failure", error_code="provider_call_failed", tool_calls=partial)
    calls = threads.list_messages("trace-thread")[-1].tool_calls
    assert calls[0] == {"name": "read_sec_filing", "call_id": "saved", "input": {"retained": True},
                        "result_preview": "saved", "sec_citations": [evidence.document_ref]}
    if partial:
        assert calls[1:] == [partial[1]]
    else:
        assert len(calls) == 1


def test_terminal_trace_reads_uncommitted_events_and_rolls_back_atomically(evidence, trace_stores):
    runs, threads = trace_stores
    with runs._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        runs._append_event_on_connection(conn, "trace-run", "tool_end", {
            "tool": "read_sec_filing", "call_id": "transaction-only", "summary": "saved",
            "sec_citations": [evidence.document_ref]})
        runs._terminalize_error_on_connection(conn, thread_store=threads, run_id="trace-run",
            status="interrupted", error="restart", error_code="run_interrupted", expected_statuses=("queued",))
        saved = json.loads(conn.execute(
            "SELECT tool_calls_json FROM research_messages WHERE role='assistant'").fetchone()[0])
        assert saved and saved[0]["sec_citations"] == [evidence.document_ref]
        assert saved[0]["call_id"] == "transaction-only"
        assert runs.get_run("trace-run").status == "queued"
        assert len(threads.list_messages("trace-thread")) == 1
        conn.rollback()
    assert runs.get_run("trace-run").status == "queued"
    assert runs.list_events("trace-run") == []
    assert len(threads.list_messages("trace-thread")) == 1


def test_partial_trace_cannot_replace_durable_refs_or_consume_identified_rows(evidence, trace_stores):
    runs, threads = trace_stores
    runs.append_event("trace-run", "tool_end", {"tool": "read_sec_filing", "call_id": "saved",
        "input": {}, "summary": "saved", "sec_citations": [evidence.document_ref]})
    runs.append_event("trace-run", "tool_start", {"tool": "list_sec_filings", "call_id": "pending"})
    partial = [
        {"name": "read_sec_filing", "call_id": "saved", "input": {}, "result_preview": "wrong",
         "sec_citations": [evidence.fact_ref]},
        {"name": "read_sec_filing", "input": {}, "result_preview": "legacy"},
        {"name": "list_sec_filings", "call_id": "pending", "input": {"x": 1}, "result_preview": "bad",
         "sec_citation_gaps": ["sec_citation_result_invalid"]},
    ]
    runs.terminalize_error_with_message(thread_store=threads, run_id="trace-run", status="cancelled",
        error="cancel", error_code="run_cancelled", tool_calls=partial)
    calls = threads.list_messages("trace-thread")[-1].tool_calls
    assert len(calls) == 3
    assert calls[0]["sec_citations"] == [evidence.document_ref]
    assert calls[0]["result_preview"] == "saved"
    assert calls[1] == partial[2]
    assert calls[2] == partial[1]


@pytest.mark.parametrize("terminal", ["success", "error", "cancel"])
def test_executor_retains_citations_and_gaps_through_terminal_and_archive(
    terminal, evidence, trace_stores, monkeypatch,
):
    from src.api.routes import research
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding
    from src.research_run_manager import execute_research_run
    from src.research_threads import ResearchThreadStore

    runs, threads = trace_stores
    monkeypatch.setattr("src.api.personalization.resolve_personalization", lambda _: ("", {
        "profile_active": False, "assistant_stance": "off", "skill_mode": "off",
        "suggested_skills": [], "applied_skills": [], "context_snapshot": ""}))

    async def stream(**kwargs):
        yield AgentEvent(EventType.tool_start, {"tool": "read_sec_filing", "call_id": "saved", "input": {}})
        yield AgentEvent(EventType.tool_end, {"tool": "read_sec_filing", "call_id": "saved", "input": {},
            "summary": "preview", "sec_citations": [evidence.document_ref]})
        yield AgentEvent(EventType.tool_end, {"tool": "list_sec_filings", "call_id": "gap", "input": {},
            "summary": "bad", "sec_citation_gaps": ["sec_citation_result_invalid"]})
        if terminal == "cancel":
            raise asyncio.CancelledError
        if terminal == "error":
            yield AgentEvent(EventType.error, {"error": "provider failed"})
        else:
            yield AgentEvent(EventType.done, {"answer": "Answer", "provider": "openai", "model": "gpt-5.4-mini"})

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
    assert runs.get_run("trace-run").status == {"success": "succeeded", "error": "failed", "cancel": "cancelled"}[terminal]
    threads.set_thread_archived("trace-thread", archived=True)
    messages = research.list_research_messages("trace-thread", store=ResearchThreadStore(threads.db_path))["messages"]
    assert len(messages) == 2
    assert messages[-1]["tool_calls"] == [
        {"name": "read_sec_filing", "call_id": "saved", "input": {}, "result_preview": "preview",
         "sec_citations": [evidence.document_ref]},
        {"name": "list_sec_filings", "call_id": "gap", "input": {}, "result_preview": "bad",
         "sec_citation_gaps": ["sec_citation_result_invalid"]},
    ]


@pytest.fixture
def producer(monkeypatch, isolated):
    from src.agents import config
    from src.agents.anthropic_agent import agent as ant
    from src.agents.openai_agent import agent as oai
    from src.auth_drivers import live_resolver

    settings = config.AgentConfig(web_openai_search=False, web_playwright=False)
    monkeypatch.setattr(ant, "get_agent_config", lambda: settings)
    monkeypatch.setattr(oai, "get_agent_config", lambda: settings)
    clients = []

    def make(channel, name, results, *, is_error=False, text_blocks=True):
        state = SimpleNamespace(requests=[], closed=False, pause=None)
        calls = [{"type": "function_call", "name": name, "call_id": f"call_{i}",
                  "arguments": json.dumps({"index": i})} for i in range(len(results))]

        async def invoke(context, arguments):
            return results[json.loads(arguments)["index"]]

        if channel == "openai":
            from agents import FunctionTool
            from openai import AsyncOpenAI

            tool = FunctionTool(name="tool_" + name, description="Offline evidence",
                params_json_schema={"type": "object", "properties": {"index": {"type": "integer"}},
                                    "required": ["index"], "additionalProperties": False},
                on_invoke_tool=invoke)
            monkeypatch.setattr("src.agents.openai_agent.tools.create_openai_tools", lambda dal: [tool])

            async def reply(request):
                payload = json.loads(request.content)
                state.requests.append(payload)
                response = response_json(payload["model"])
                response["id"] = f"response_{len(state.requests)}"
                if len(state.requests) == 1:
                    response["output"] = [{**call, "name": tool.name, "id": f"fc_{i}",
                                           "status": "completed"} for i, call in enumerate(calls)]
                elif state.pause is not None:
                    state.entered.set()
                    try:
                        await state.pause.wait()
                    finally:
                        state.closed = True
                return httpx.Response(200, json=response)

            client = AsyncOpenAI(api_key=SECRET, max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(reply)))
            clients.append(client)
            monkeypatch.setattr(live_resolver, "live_openai_async_client", lambda: client)
            state.stream = lambda: oai.run_query_stream("Read evidence", model="gpt-5.4-mini",
                                                       reasoning_effort="low", dal=object())
        elif channel == "anthropic":
            from anthropic import Anthropic

            async def execute(tool_name, args, dal):
                return results[args["index"]]

            monkeypatch.setattr("src.agents.anthropic_agent.tools.execute_tool_async", execute)

            def reply(request):
                payload = json.loads(request.content)
                state.requests.append(payload)
                first = len(state.requests) == 1
                blocks = [{"type": "tool_use", "id": call["call_id"], "name": name,
                           "input": json.loads(call["arguments"])} for call in calls] if first else [
                               {"type": "text", "text": "OK"}]
                return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                    text=anthropic_frames(payload["model"], blocks, stop="tool_use" if first else "end_turn"))

            client = Anthropic(api_key=SECRET, max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(reply)))
            clients.append(client)
            monkeypatch.setattr(live_resolver, "live_anthropic_client", lambda: client)
            state.stream = lambda: ant.run_query_stream("Read evidence", model="claude-sonnet-4-6",
                                                       effort="low", dal=object())
        elif channel == "chatgpt":
            from src.auth_drivers import chatgpt_oauth_driver as mod
            from tests.test_chatgpt_oauth_driver import _driver, _ExecClient, _req

            client = _ExecClient([
                [{"type": "response.completed", "response": {"output": calls}}],
                [{"type": "response.completed", "response": response_json("gpt-5.4-mini")}],
            ])
            monkeypatch.setattr(mod, "_execution_client", lambda token: client)
            driver = _driver(token=SECRET)

            async def execute(*, name, args, token):
                return not is_error, results[args["index"]]

            monkeypatch.setattr(driver, "_invoke_tool", execute)
            state.stream = lambda: driver.stream_llm(_req())
        else:
            from claude_agent_sdk import AssistantMessage, ToolUseBlock, ToolResultBlock, UserMessage
            from tests.test_claude_code_sdk_driver import _install_fake_query, _make_driver, _REQ, _result_msg

            messages = [AssistantMessage(model="m", content=[ToolUseBlock(
                id=call["call_id"], name="mcp__ark__" + name,
                input=json.loads(call["arguments"])) for call in calls])]
            # Reverse completions so name-only association cannot pass.
            messages += [UserMessage(content=[ToolResultBlock(tool_use_id=f"call_{i}",
                content=[{"type": "text", "text": results[i]}] if text_blocks else results[i],
                is_error=is_error)])
                for i in reversed(range(len(results)))]
            messages.append(_result_msg(result="OK"))
            _install_fake_query(monkeypatch, messages, {})
            driver = _make_driver(token=SECRET)
            state.stream = lambda: driver.stream_llm(_REQ)
        return state

    yield make
    for client in clients:
        if asyncio.iscoroutinefunction(client.close):
            asyncio.run(client.close())
        else:
            client.close()


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("kind,name", [("facts", "get_sec_financial_facts"),
    ("filings", "list_sec_filings"), ("document", "read_sec_filing")])
def test_four_channels_keep_whole_refs_and_call_inputs(channel, kind, name, evidence, producer):
    envelope = deepcopy(getattr(evidence, kind))
    # Put the source past every preview cap without altering its authority.
    envelope = {"coverage": {**envelope["coverage"], "note": "public " * 1200},
                **{key: value for key, value in envelope.items() if key != "coverage"}}
    raw = json.dumps(envelope, ensure_ascii=False)
    expected = {"facts": [evidence.fact_ref], "filings": evidence.filing_refs,
                "document": [evidence.document_ref]}[kind]
    state = producer(channel, name, [raw, raw])
    events = asyncio.run(collect(state.stream()))
    assert terminal(events)["answer"] == "OK"
    starts = {event.data["call_id"]: event.data for event in events if event.type == EventType.tool_start}
    ends = [event.data for event in events if event.type == EventType.tool_end]
    assert len(starts) == len(ends) == 2
    assert len({end["call_id"] for end in ends}) == 2
    for end in ends:
        assert end["input"] == starts[end["call_id"]]["input"]
        assert end["sec_citations"] == expected
        assert "sec_citation_gaps" not in end
        assert len(end["summary"]) < len(raw)
        assert "source_sha256" not in end["summary"]


@pytest.mark.parametrize("channel", CHANNELS)
def test_malformed_owned_evidence_is_a_gap_in_each_producer(channel, producer):
    events = asyncio.run(collect(producer(channel, "list_sec_filings", ['{"data": "bad"}']).stream()))
    terminal(events)
    ends = [event.data for event in events if event.type == EventType.tool_end]
    assert len(ends) == 1
    assert ends[0]["sec_citation_gaps"] == ["sec_citation_result_invalid"]
    assert "sec_citations" not in ends[0]


@pytest.mark.parametrize("channel,text_blocks", [("chatgpt", False), ("claude", False), ("claude", True)])
def test_error_marked_result_cannot_become_successful_evidence(channel, text_blocks, evidence, producer):
    state = producer(channel, "list_sec_filings", [json.dumps(evidence.filings)],
                     is_error=True, text_blocks=text_blocks)
    events = asyncio.run(collect(state.stream()))
    terminal(events)
    end = next(event.data for event in events if event.type == EventType.tool_end)
    assert end["is_error"] is True
    assert "sec_citations" not in end
    assert end["sec_citation_gaps"] == ["sec_citation_result_invalid"]


@pytest.mark.parametrize("channel", CHANNELS)
def test_same_name_calls_cannot_exchange_distinct_sources(channel, evidence, producer):
    row = evidence.filings["data"][0]
    assert len(row["sources"]) >= 2
    envelopes, expected = [], []
    for source in row["sources"][:2]:
        envelopes.append({**evidence.filings, "data": [{**row, "sources": [source]}]})
        expected.append([{"kind": "filing", "filing_id": row["filing_id"],
                         "snapshot_id": source["snapshot_id"], "source_sha256": source["source"]["sha256"],
                         "source_pointer": source["source"]["pointer"], "source_url": source["source_url"],
                         "observed_at": source["observed_at"]}])
    assert expected[0] != expected[1]
    events = asyncio.run(collect(producer(channel, "list_sec_filings", [json.dumps(e) for e in envelopes]).stream()))
    terminal(events)
    ends = [event.data for event in events if event.type == EventType.tool_end]
    assert len(ends) == 2
    for end in ends:
        index = end["input"]["index"]
        assert end["call_id"].endswith(f"call_{index}")
        assert end["sec_citations"] == expected[index]


@pytest.mark.parametrize("channel", CHANNELS)
def test_non_sec_tool_cannot_claim_sec_result_metadata(channel, evidence, producer):
    events = asyncio.run(collect(producer(channel, "get_news_brief", [json.dumps(evidence.filings)]).stream()))
    terminal(events)
    end = next(event.data for event in events if event.type == EventType.tool_end)
    assert "sec_citations" not in end and "sec_citation_gaps" not in end


@pytest.mark.parametrize("channel", CHANNELS)
def test_full_result_secret_is_rejected_before_citation_projection(channel, producer, monkeypatch):
    from src.sec_research import citations

    seen = []
    original = citations.citation_event_fields

    def record(name, value):
        seen.append(value)
        return original(name, value)

    monkeypatch.setattr(citations, "citation_event_fields", record)
    state = producer(channel, "list_sec_filings", [json.dumps({"padding": "public " * 1200, "tail": SECRET})])
    async def drive():
        events = []
        try:
            async for event in state.stream():
                events.append(event)
        except OutputBoundaryError as error:
            assert error.code == "known_secret"
        assert not any(event.type == EventType.tool_end for event in events)
        assert SECRET not in json.dumps([event.data for event in events])
    asyncio.run(drive())
    assert seen == []


@pytest.mark.parametrize("stop", ["cancel", "close"])
def test_real_openai_sdk_completion_precedes_cancelled_followup(stop, producer, evidence):
    state = producer("openai", "list_sec_filings", [json.dumps(evidence.filings)])

    async def drive():
        state.pause, state.entered = asyncio.Event(), asyncio.Event()
        stream = state.stream()
        try:
            async def completed():
                async for event in stream:
                    if event.type == EventType.tool_end:
                        return event.data
                pytest.fail("missing live completion")
            end = await asyncio.wait_for(completed(), 2)
            assert end["sec_citations"] == evidence.filing_refs
            await asyncio.wait_for(state.entered.wait(), 2)
            if stop == "cancel":
                pending = asyncio.create_task(stream.__anext__())
                await asyncio.sleep(0)
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            else:
                await stream.aclose()
            assert state.closed, "SDK followup was not awaited through HTTP cancellation"
            with pytest.raises(StopAsyncIteration):
                await stream.__anext__()
        finally:
            await stream.aclose()

    asyncio.run(drive())


@pytest.mark.parametrize("repeat_cancel", [False, True])
def test_queued_openai_completions_survive_executor_cancellation(
    repeat_cancel, producer, evidence, trace_stores, monkeypatch,
):
    import sqlite3

    from agents import Runner
    from agents.tool_context import ToolContext
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding
    from src.research_run_manager import execute_research_run
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore
    from src.sec_research.references import iter_research_sec_citations, sec_reference_closure

    runs, threads = trace_stores
    raw = json.dumps(evidence.filings)
    state = producer("openai", "list_sec_filings", [raw])
    monkeypatch.setattr("src.api.personalization.resolve_personalization", lambda _: ("", {
        "profile_active": False, "assistant_stance": "off", "skill_mode": "off",
        "suggested_skills": [], "applied_skills": [], "context_snapshot": ""}))

    async def run(agent, *, hooks, **kwargs):
        try:
            for index in range(2):
                context = ToolContext(context=None, tool_name="tool_list_sec_filings",
                    tool_call_id=f"queued-{index}", tool_arguments=json.dumps({"index": index}))
                await hooks.on_tool_start(context, agent, agent.tools[0])
                await hooks.on_tool_end(context, agent, agent.tools[0], raw)
            # No await between publication and cancel: the consumer cannot drain.
            assert not any(event.type == "tool_end" for event in runs.list_events("trace-run"))
            state.executor.cancel()
            await asyncio.Event().wait()
        finally:
            if repeat_cancel:
                for _ in range(2):
                    state.executor.cancel()
                    await asyncio.sleep(0)
            # Cleanup must neither publish a new result nor admit its secret.
            await hooks.on_tool_end(context, agent, agent.tools[0], SECRET)
            state.closed = True

    monkeypatch.setattr(Runner, "run", run)

    async def execute():
        state.executor = asyncio.create_task(execute_research_run(
            run_id="trace-run", run_store=runs, thread_store=threads, dal=object(), history=[],
            stream_factory=lambda **kwargs: state.stream(),
            auth_binding=RuntimeAuthBinding("openai", "db_api_key", "api_key", None,
                                           _api_key=SECRET)))
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(state.executor, 2)
        assert state.closed

    asyncio.run(execute())
    runs = ResearchRunStore(runs.db_path)
    ends = [event.data for event in runs.list_events("trace-run") if event.type == "tool_end"]
    assert [end["call_id"] for end in ends] == ["openai:0:queued-0", "openai:0:queued-1"]
    assert [end["sec_citations"] for end in ends] == [evidence.filing_refs] * 2
    assert [end["input"] for end in ends] == [{"index": 0}, {"index": 1}]
    assert runs.get_run("trace-run").status == "cancelled"
    message = ResearchThreadStore(threads.db_path).list_messages("trace-thread")[-1]
    assert message.error_code == "run_cancelled"
    assert [call["call_id"] for call in message.tool_calls] == [end["call_id"] for end in ends]
    assert [call["sec_citations"] for call in message.tool_calls] == [evidence.filing_refs] * 2
    with sqlite3.connect(runs.db_path) as conn:
        conn.execute("PRAGMA query_only=ON")
        refs = list(iter_research_sec_citations(conn))
    assert refs == evidence.filing_refs * 4  # Two durable ends and two message calls.
    assert sec_reference_closure(evidence.rig.store, citations=refs)["filing_ids"]


def test_repeated_close_cancellation_awaits_same_openai_worker(producer, evidence, monkeypatch):
    from agents import Runner
    from agents.tool_context import ToolContext

    raw = json.dumps(evidence.filings)
    state = producer("openai", "list_sec_filings", [raw])
    workers = []

    async def run(agent, **kwargs):
        workers.append(asyncio.current_task())
        context = ToolContext(context=None, tool_name="tool_list_sec_filings",
                              tool_call_id="before-close", tool_arguments='{"index":0}')
        try:
            await kwargs["hooks"].on_tool_end(context, agent, agent.tools[0], raw)
            await asyncio.Event().wait()
        finally:
            state.entered.set()
            await state.release.wait()
            # Publication is disabled before cleanup, including invalid late output.
            await kwargs["hooks"].on_tool_end(context, agent, agent.tools[0], SECRET)
            state.closed = True

    monkeypatch.setattr(Runner, "run", run)

    async def drive():
        state.entered, state.release = asyncio.Event(), asyncio.Event()
        stream = state.stream()
        closing = None
        try:
            assert (await stream.__anext__()).type == EventType.thinking
            end = await asyncio.wait_for(stream.__anext__(), 2)
            assert end.data["sec_citations"] == evidence.filing_refs
            closing = asyncio.create_task(stream.aclose())
            await asyncio.wait_for(state.entered.wait(), 2)
            for _ in range(2):
                closing.cancel()
                await asyncio.sleep(0)
                assert not closing.done()
                assert not workers[0].done()
            state.release.set()
            with pytest.raises(asyncio.CancelledError):
                await closing
            assert state.closed and len(workers) == 1 and workers[0].done()
            with pytest.raises(StopAsyncIteration):
                await stream.__anext__()
        finally:
            state.release.set()
            if closing is not None:
                await asyncio.gather(closing, return_exceptions=True)
            await stream.aclose()

    asyncio.run(drive())


async def single_event(data):
    yield AgentEvent(EventType.tool_end, data)


@pytest.mark.parametrize("prefix", ["", "tool_", "mcp__ark__", "mcp__ark__tool_"])
def test_event_boundary_admits_only_typed_owned_citations(prefix, evidence):
    data = {"tool": prefix + "list_sec_filings", "call_id": "owned", "input": {"issuer": "AAPL"},
            "sec_citations": evidence.filing_refs, "sec_citation_gaps": ["sec_citation_missing"]}
    events = asyncio.run(collect(protect_events(single_event(data))))
    assert events[0].data == data


@pytest.mark.parametrize("change", [
    {"tool": "search_news"}, {"tool": "mcp__foreign__list_sec_filings"},
    {"tool": "tool_tool_list_sec_filings"}, {"sec_citations": {}},
    {"sec_citations": [{"kind": "filing"}]}, {"sec_citation_gaps": ["unreviewed"]},
    {"sec_citation_gaps": [{"code": "sec_citation_missing"}]},
    {"sec_citation_gaps": "sec_citation_missing"}, {"unreviewed": []}, {"input": []},
])
def test_event_boundary_rejects_unowned_or_malformed_metadata(change, evidence):
    data = {"tool": "list_sec_filings", "sec_citations": evidence.filing_refs, **change}
    with pytest.raises(OutputBoundaryError, match="^invalid_value$"):
        asyncio.run(collect(protect_events(single_event(data))))


def test_citation_metadata_exact_secret_check_precedes_shape_validation(evidence):
    data = {"tool": "list_sec_filings", "sec_citation_gaps": [SECRET]}
    with output_scope(SECRET), pytest.raises(OutputBoundaryError, match="^known_secret$"):
        asyncio.run(collect(protect_events(single_event(data))))


def test_openai_end_hook_retains_input_without_start_and_ignores_raw_duplicate(producer, evidence, monkeypatch):
    from agents import Runner
    from agents.tool_context import ToolContext

    state = producer("openai", "list_sec_filings", [json.dumps(evidence.filings)])
    async def run(agent, **kwargs):
        context = ToolContext(context=None, tool_name="tool_list_sec_filings",
                              tool_call_id="raw", tool_arguments='{"issuer":"AAPL"}')
        await kwargs["hooks"].on_tool_end(context, agent, agent.tools[0], json.dumps(evidence.filings))
        await kwargs["hooks"].on_tool_end(context, agent, agent.tools[0], json.dumps(evidence.filings))
        return SimpleNamespace(final_output="OK", raw_responses=[SimpleNamespace(output=[
            SimpleNamespace(type="function_call", name="tool_list_sec_filings",
                            call_id="raw", arguments='{"issuer":"AAPL"}'),
            SimpleNamespace(type="function_call_output", call_id="raw", output=json.dumps(evidence.filings)),
        ])])
    monkeypatch.setattr(Runner, "run", run)
    events = asyncio.run(collect(state.stream()))
    terminal(events)
    ends = [event.data for event in events if event.type == EventType.tool_end]
    assert len(ends) == 1
    assert ends[0]["input"] == {"issuer": "AAPL"}
    assert ends[0]["sec_citations"] == evidence.filing_refs
    assert isinstance(ends[0]["call_id"], str)


@pytest.mark.parametrize("stop", ["cancel", "close", "error", "retry"])
def test_completed_openai_sec_tool_survives_later_cancel(stop, producer, evidence, monkeypatch):
    from agents import Runner
    from agents.lifecycle import RunHooksBase
    from agents.tool_context import ToolContext

    raw = json.dumps(evidence.filings)
    state = producer("openai", "list_sec_filings", [raw])
    workers, hooks_seen, finished = [], [], []

    async def run(agent, **kwargs):
        workers.append(asyncio.current_task())
        hooks = kwargs.get("hooks")
        # Old producer never installs hooks: stay pending to expose the timing failure.
        if hooks is None:
            await asyncio.Event().wait()
        assert isinstance(hooks, RunHooksBase)
        hooks_seen.append(hooks)
        context = ToolContext(context=None, tool_name="tool_list_sec_filings",
                              tool_call_id="reused", tool_arguments='{"index":0}')
        try:
            await hooks.on_tool_start(context, agent, agent.tools[0])
            await hooks.on_tool_end(context, agent, agent.tools[0], raw)
            if stop in {"error", "retry"}:
                raise RuntimeError("No tool output found" if stop == "retry" else "offline later failure")
            await asyncio.Event().wait()
        finally:
            # A cancelled worker may attempt to publish during asynchronous cleanup.
            if stop in {"cancel", "close"}:
                await asyncio.sleep(0)
                await hooks.on_tool_end(context, agent, agent.tools[0], raw)
            finished.append(asyncio.current_task())

    monkeypatch.setattr(Runner, "run", run)

    async def drive():
        stream = state.stream()
        events = []
        try:
            async def until_end():
                async for event in stream:
                    events.append(event)
                    if event.type == EventType.tool_end:
                        return
            await asyncio.wait_for(until_end(), timeout=2)
            assert any(event.type == EventType.tool_end for event in events)
            if stop in {"cancel", "close"}:
                assert not workers[0].done()
            if stop == "cancel":
                pending = asyncio.create_task(stream.__anext__())
                await asyncio.sleep(0)
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            elif stop in {"error", "retry"}:
                events.extend(await collect(stream))
            else:
                await stream.aclose()
            assert all(worker.done() for worker in workers)
            assert finished == workers
            assert [event.data["sec_citations"] for event in events if event.type == EventType.tool_end] == [
                evidence.filing_refs] * (2 if stop == "retry" else 1)
            ends = [event.data for event in events if event.type == EventType.tool_end]
            assert len({end["call_id"] for end in ends}) == len(ends)
            assert len(workers) == (2 if stop == "retry" else 1)
            if stop in {"error", "retry"}:
                assert events[-1].type == EventType.error
            with pytest.raises(StopAsyncIteration):
                await stream.__anext__()
        finally:
            await stream.aclose()

    asyncio.run(drive())
