"""SEC admission failures stay local to SEC tools, not the whole research run."""

import asyncio
from contextlib import contextmanager
import errno
import json

import pytest

from src.sec_research import capture_lock
from src.sec_research.paths import SecResearchPaths
from tests.test_sec_research_operations import other_owner, store
from tests.test_sec_research_trace import trace_stores


FAILURES = [
    ("unsupported", "capture_platform_unsupported"),
    ("unsafe", "capture_path_unsafe"),
    ("invalid", "sec_research_operation_invalid"),
    ("space", "storage_space_insufficient"),
    ("lock", "capture_store_write_failed"),
    ("unknown-value", "sec_research_store_unavailable"),
    ("unknown-runtime", "capture_platform_unsupported"),
]


@contextmanager
def admission_fault(paths, monkeypatch, kind):
    import fcntl
    from src.sec_research import tool_service

    root = paths.capture_root
    with monkeypatch.context() as patch:
        if kind == "unsupported":
            patch.setattr(capture_lock, "_supported", lambda: False)
        elif kind == "unsafe":
            root.symlink_to(root.parent, target_is_directory=True)
        elif kind == "invalid":
            original = capture_lock.research_operation

            def invalid(root, **kwargs):
                return original(root, create="invalid")

            patch.setattr(capture_lock, "research_operation", invalid)
            patch.setattr(tool_service, "research_operation", invalid)
        else:
            error = {
                "space": OSError(errno.ENOSPC, "fixture allocation failure"),
                "lock": OSError(errno.ENOLCK, "fixture lock failure"),
                "unknown-value": ValueError("unrecognized admission failure"),
                "unknown-runtime": RuntimeError("capture_platform_unsupported"),
            }[kind]

            def fail(*args, **kwargs):
                raise error

            # Exercise real lease cleanup and OSError-to-closed-code mapping.
            patch.setattr(fcntl, "flock", fail)
        try:
            yield
        finally:
            if kind == "unsafe":
                root.unlink()


@pytest.mark.parametrize("entry", ["direct", "scheduled", "sse-2.3", "sse-2.4"])
@pytest.mark.parametrize("use_sec", [False, True], ids=["no-sec", "sec-tool"])
@pytest.mark.parametrize("fault,code", FAILURES, ids=[row[0] for row in FAILURES])
def test_closed_admission_failure_is_local_to_sec_tool(
    store, trace_stores, monkeypatch, entry, fault, code, use_sec,
):
    from src.agents.shared.events import AgentEvent, EventType
    from src.api.routes import query
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding
    from src import research_run_manager as manager
    from src.sec_research import runtime
    from src.sec_research.citations import citation_event_fields
    from src.sec_research.tool_execution import invoke_sec_tool
    from src.sec_research.tool_service import ToolService

    runs, threads = trace_stores
    paths = store.paths
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    binding = RuntimeAuthBinding("openai", "db_api_key", "api_key", None, _api_key="offline-key")
    monkeypatch.setattr(query, "capture_runtime_auth", lambda _: binding)
    monkeypatch.setattr(query, "_resolve_query_task_route", lambda *_: ("gpt-5.4-mini", "low"))
    monkeypatch.setattr(query, "_require_live_model_auth", lambda *_: None)
    monkeypatch.setattr(query, "_require_client_compaction_compatibility", lambda *_: None)
    monkeypatch.setattr(query, "_resolve_personalization", lambda _: ("", {}))
    dispatched, sent, errors = [], [], []
    results = []

    def unexpected_acquisition():
        pytest.fail("SEC admission failure must not start acquisition")

    service = ToolService(store, acquisition_factory=unexpected_acquisition, clock=lambda: "2026-09-20T00:00:00Z")
    monkeypatch.setattr(runtime, "build_tool_service", lambda: service)

    async def events():
        if use_sec:
            result = await invoke_sec_tool("list_sec_filings", {"issuer": "0000320193"})
            results.append(result)
            fields = citation_event_fields("list_sec_filings", result)
            assert fields == {}
            yield AgentEvent(EventType.tool_end, {"tool": "list_sec_filings", "input": {},
                "summary": json.dumps(result), "is_error": True, **fields})
        yield AgentEvent(EventType.done, {"answer": "Research remains available", "provider": "openai", "model": "gpt-5.4-mini"})

    def stream(**kwargs):
        dispatched.append(True)
        return events()

    monkeypatch.setattr(query, "_research_provider_stream", stream)

    async def send(message):
        sent.append(message)

    async def receive():
        await asyncio.Future()

    async def execute():
        with admission_fault(paths, monkeypatch, fault):
            args = dict(run_id="trace-run", run_store=runs, thread_store=threads,
                dal=object(), history=[], auth_binding=binding)
            if entry.startswith("sse-"):
                response = await query.query_agent_stream(query.QueryRequest(question="Question", provider="openai",
                    thread_id="trace-thread"), dal=object(), store=threads)
                task = asyncio.create_task(response(
                    {"type": "http", "asgi": {"spec_version": entry.removeprefix("sse-")}}, receive, send))
            else:
                task = (manager.schedule_research_run(**args) if entry == "scheduled" else
                        asyncio.create_task(manager.execute_research_run(**args, stream_factory=stream)))
            try:
                await task
            except Exception as exc:
                errors.append(exc)
            await asyncio.sleep(0)
            assert "trace-run" not in manager._TASKS

    asyncio.run(execute())
    assert dispatched == [True]
    assert len(results) == int(use_sec)
    if use_sec:
        assert results[0]["status"] == "unavailable" and results[0]["data"] == []
        assert results[0]["gaps"] == [{"code": code}]
    assert other_owner(paths.capture_root) == "entered"
    assert not paths.capture_root.exists()
    messages = threads.list_messages("trace-thread")
    run = runs.get_run("trace-run")
    assert errors == [], errors
    if entry.startswith("sse-"):
        assert errors == [], errors
        assert sent[0]["status"] == 200
        assert b"text/event-stream" in dict(sent[0]["headers"])[b"content-type"]
        assert sent[-1] == {"type": "http.response.body", "body": b"", "more_body": False}
        body = b"".join(message.get("body", b"") for message in sent).decode()
        frames = [json.loads(frame.removeprefix("data: ")) for frame in body.strip().split("\n\n")]
        assert len(frames) == 1 + int(use_sec) and frames[-1]["type"] == "done"
        assert run.status == "queued"  # The legacy endpoint does not own this fixture run.
        assert len(messages) == 3
    else:
        assert run.status == "succeeded", (run.status, errors)
        assert run.error_code is None and run.started_at is not None and run.completed_at is not None
        replay = runs.list_events("trace-run")
        assert len(replay) == 1 + int(use_sec) and replay[-1].type == "done"
        assert len(messages) == 2
        assert messages[-1].run_id == "trace-run"
    assert not messages[-1].is_error and messages[-1].error_code is None
    assert messages[-1].content == "Research remains available"
    assert len(messages[-1].tool_calls) == int(use_sec)
    assert not runs.has_persistence_failure("trace-run")
