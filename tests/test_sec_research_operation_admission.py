"""Closed operation admission failures through actual Research execution owners."""

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
    ("unsupported", "capture_platform_unsupported", "platform"),
    ("unsafe", "capture_path_unsafe", "path"),
    ("invalid", "sec_research_operation_invalid", "configuration"),
    ("space", "storage_space_insufficient", "space"),
    ("lock", "capture_store_write_failed", "protection"),
    ("unknown-value", None, None),
    ("unknown-runtime", None, None),
]


@contextmanager
def admission_fault(paths, monkeypatch, kind):
    import fcntl
    from src import research_run_manager as manager

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
            patch.setattr(manager, "research_operation", invalid)
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
@pytest.mark.parametrize("fault,code,reason", FAILURES, ids=[row[0] for row in FAILURES])
def test_closed_admission_failure_has_truthful_terminal_without_dispatch(
    store, trace_stores, monkeypatch, entry, fault, code, reason,
):
    from src.agents.shared.events import AgentEvent, EventType
    from src.api.routes import query
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding
    from src import research_run_manager as manager

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

    async def events():
        yield AgentEvent(EventType.done, {"answer": "No tools", "provider": "openai", "model": "gpt-5.4-mini"})

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
    assert dispatched == []
    assert other_owner(paths.capture_root) == "entered"
    assert not paths.capture_root.exists()
    messages = threads.list_messages("trace-thread")
    run = runs.get_run("trace-run")
    if code is None:
        assert len(errors) == 1, "unknown programming failure was converted to admission status"
        assert isinstance(errors[0], ValueError if fault == "unknown-value" else RuntimeError)
        assert run.status == "queued" and runs.list_events("trace-run") == []
        assert len(messages) == 1
        assert not any(message.get("more_body") is False for message in sent)
        return
    if entry.startswith("sse-"):
        assert errors == [], errors
        assert sent[0]["status"] == 200
        assert b"text/event-stream" in dict(sent[0]["headers"])[b"content-type"]
        assert sent[-1] == {"type": "http.response.body", "body": b"", "more_body": False}
        body = b"".join(message.get("body", b"") for message in sent).decode()
        frames = [json.loads(frame.removeprefix("data: ")) for frame in body.strip().split("\n\n")]
        assert len(frames) == 1 and frames[0]["type"] == "error"
        assert set(frames[0]["data"]) == {"code", "error"}
        assert frames[0]["data"]["code"] == code
        detail = frames[0]["data"]["error"]
        assert len(messages) == 1  # Legacy admission has not appended a user turn.
    else:
        assert run.status == "failed", (run.status, errors)
        assert errors == []
        assert run.error_code == code and run.started_at is None and run.completed_at is not None
        assert run.personalization is None and run.token_usage is None
        replay = runs.list_events("trace-run")
        assert len(replay) == 1 and replay[0].type == "error"
        assert replay[0].data == {"code": code, "error": run.error}
        assert len(messages) == 2
        assert messages[-1].is_error and messages[-1].error_code == code and messages[-1].run_id == "trace-run"
        assert messages[-1].content == run.error and not messages[-1].tool_calls
        assert messages[-1].personalization is None and messages[-1].token_usage is None
        detail = run.error
    assert "not started" in detail.lower() and reason in detail.lower()
    assert "maintenance" not in detail.lower() and "offline-key" not in detail and "fixture" not in detail

