"""SEC maintenance must exclude SEC work, not unrelated research persistence."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from contextvars import copy_context
import multiprocessing

import pytest

from src.agents.shared.events import AgentEvent, EventType
from src.auth_drivers.runtime_binding import RuntimeAuthBinding
from src.research_run_manager import execute_research_run
from src.sec_research import capture_lock
from src.sec_research.paths import SecResearchPaths
from tests.test_sec_research_operations import other_owner, store
from tests.test_sec_research_trace import trace_stores
from tests.test_sec_research_citations import evidence, rig
from tests.test_sec_research_tool_adapters import CHANNELS, dispatch, registry, tool_fixture, unwrap, wire
from tests.test_sec_research_tool_service import CIK, seed


@pytest.mark.parametrize("terminal", ["success", "error", "cancel"])
@pytest.mark.parametrize("condition", ["maintenance", "unsafe", "unsupported"])
def test_non_sec_research_finishes_without_sec_admission(
    store, trace_stores, monkeypatch, terminal, condition,
):
    runs, threads = trace_stores
    paths = store.paths
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    dispatched = []

    async def stream(**kwargs):
        dispatched.append(True)
        yield AgentEvent(EventType.text, {"content": "No SEC dependency."})
        yield AgentEvent(EventType.tool_end, {"tool": "calculate", "summary": "4"})
        if terminal == "cancel":
            raise asyncio.CancelledError
        yield (AgentEvent(EventType.error, {"error": "offline provider failed"})
               if terminal == "error" else AgentEvent(EventType.done, {
                   "answer": "No SEC dependency.", "provider": "openai", "model": "gpt-5.4-mini",
               }))

    async def execute():
        with (capture_lock.research_operation(paths.capture_root, exclusive=True)
              if condition == "maintenance" else nullcontext()):
            task = asyncio.create_task(execute_research_run(
                run_id="trace-run", run_store=runs, thread_store=threads, dal=object(), history=[],
                stream_factory=stream,
                auth_binding=RuntimeAuthBinding("openai", "db_api_key", "api_key", None,
                                               _api_key="offline-key"),
            ))
            if terminal == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                await task

    if condition == "unsafe":
        paths.capture_root.symlink_to(paths.capture_root.parent, target_is_directory=True)
    elif condition == "unsupported":
        monkeypatch.setattr(capture_lock, "_supported", lambda: False)
    asyncio.run(execute())
    assert dispatched == [True]
    run = runs.get_run("trace-run")
    assert run.status == {"success": "succeeded", "error": "failed", "cancel": "cancelled"}[terminal]
    assert not runs.has_persistence_failure("trace-run")
    saved = threads.list_messages("trace-thread")[-1]
    assert saved.run_id == "trace-run"
    assert saved.tool_calls == [{"name": "calculate", "input": None, "result_preview": "4"}]
    assert runs.list_events("trace-run")[-1].type == ("done" if terminal == "success" else "error")


@pytest.mark.parametrize("sink", ["message", "event", "running-event", "success", "error"])
def test_direct_non_sec_publication_does_not_need_capture_paths(trace_stores, monkeypatch, sink):
    runs, threads = trace_stores
    runs.mark_running("trace-run")

    def unexpected_resolution():
        pytest.fail("a non-SEC write tried to resolve the SEC capture root")

    monkeypatch.setattr(SecResearchPaths, "resolve", unexpected_resolution)
    if sink == "message":
        threads.append_message(thread_id="trace-thread", role="assistant", content="plain answer")
    elif sink in {"event", "running-event"}:
        append = runs.append_event if sink == "event" else runs.append_running_event
        append("trace-run", "text", {"content": "plain answer"})
    elif sink == "success":
        runs.terminalize_success_with_message(thread_store=threads, run_id="trace-run", done_data={
            "answer": "plain answer", "provider": "openai", "model": "gpt-5.4-mini",
        })
    else:
        runs.terminalize_error_with_message(thread_store=threads, run_id="trace-run", status="failed",
                                           error="provider failed", error_code="provider_call_failed")


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("busy", [False, True], ids=["available", "maintenance"])
def test_real_sec_dispatch_retains_protection_or_returns_local_gap(
    tool_fixture, registry, monkeypatch, channel, busy,
):
    fixture = tool_fixture
    seed(fixture)
    wire(monkeypatch, fixture.service)
    root = fixture.store.paths.capture_root

    async def execute():
        with capture_lock.ResearchPublication() as publication, publication.activate():
            assert other_owner(root) == "entered"
            with capture_lock.research_operation(root, exclusive=True) if busy else nullcontext():
                # Real adapters include worker threads and SDK child tasks.
                result = unwrap(await asyncio.create_task(dispatch(
                    channel, registry, "get_sec_financial_facts", {"issuer": CIK, "freshness": "stored"},
                )))
                if busy:
                    assert result["status"] == "unavailable" and result["data"] == []
                    assert result["gaps"] == [{"code": "sec_research_operation_busy"}]
                else:
                    assert result["status"] == "ok" and result["data"]
            assert other_owner(root) == ("entered" if busy else "sec_research_operation_busy")
        assert other_owner(root) == "entered"

    asyncio.run(execute())
    assert fixture.transport.calls == []


def test_publication_retention_is_lazy_independent_and_not_an_upgrade(tmp_path):
    root = tmp_path / "first"
    second = tmp_path / "second"
    with capture_lock.ResearchPublication() as outer, outer.activate():
        assert other_owner(root) == "entered"
        with capture_lock.research_operation(root):
            pass
        assert other_owner(root) == "sec_research_operation_busy"
        with pytest.raises(ValueError, match="^sec_research_operation_busy$"):
            with capture_lock.research_operation(root, exclusive=True):
                pytest.fail("a result lease cannot upgrade to maintenance")
        with capture_lock.ResearchPublication() as inner, inner.activate():
            with capture_lock.research_operation(second):
                pass
            assert other_owner(second) == "sec_research_operation_busy"
        assert other_owner(second) == "entered"
        assert other_owner(root) == "sec_research_operation_busy"
        stale = copy_context()
    assert other_owner(root) == "entered"

    def resume():
        with capture_lock.research_operation(root):
            pytest.fail("a closed publication cannot admit late work")

    with pytest.raises(ValueError, match="^sec_research_operation_invalid$"):
        stale.run(resume)
    assert other_owner(root) == "entered"
    assert not root.exists() and not second.exists()


def test_failed_retention_closes_the_short_operation_descriptor(tmp_path, monkeypatch):
    import errno
    import fcntl

    root = tmp_path / "missing"
    flock = fcntl.flock
    attempts = []

    def fail_retention(fd, operation):
        attempts.append(fd)
        if len(attempts) == 2:
            raise OSError(errno.ENOLCK, "offline retained-lock failure")
        return flock(fd, operation)

    with capture_lock.ResearchPublication() as publication, publication.activate():
        with monkeypatch.context() as patch:
            patch.setattr(fcntl, "flock", fail_retention)
            with pytest.raises(ValueError, match="^capture_store_write_failed$"):
                with capture_lock.research_operation(root):
                    pytest.fail("failed retention cannot admit a source read")
        assert len(attempts) == 2
        assert other_owner(root) == "entered"
        with capture_lock.research_operation(root):
            pass
        assert other_owner(root) == "sec_research_operation_busy"
    assert other_owner(root) == "entered"


def test_one_publication_retains_concurrent_child_workers(tool_fixture, registry, monkeypatch):
    fixture = tool_fixture
    seed(fixture)
    wire(monkeypatch, fixture.service)
    root = fixture.store.paths.capture_root

    async def execute():
        with capture_lock.ResearchPublication() as publication, publication.activate():
            results = await asyncio.gather(*(dispatch(
                channel, registry, "get_sec_financial_facts", {"issuer": CIK, "freshness": "stored"},
            ) for channel in CHANNELS))
            assert all(unwrap(result)["status"] == "ok" for result in results)
            assert other_owner(root) == "sec_research_operation_busy"
        assert other_owner(root) == "entered"

    asyncio.run(execute())
    assert fixture.transport.calls == []


@pytest.mark.parametrize("field,value", [
    ("sec_citations", []), ("sec_citations", None),
    ("sec_citation_gaps", []), ("sec_citation_gaps", ["sec_citation_result_invalid"]),
])
@pytest.mark.parametrize("sink", ["event", "message", "success", "error"])
def test_reference_field_presence_never_bypasses_maintenance(
    store, trace_stores, monkeypatch, field, value, sink,
):
    runs, threads = trace_stores
    runs.mark_running("trace-run")
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: store.paths)
    calls = [{"name": "read_sec_filing", field: value}]

    def write():
        with pytest.raises(ValueError, match="^sec_research_operation_busy$"):
            if sink == "event":
                runs.append_event("trace-run", "tool_end", {"tool": "read_sec_filing", field: value})
            elif sink == "message":
                threads.append_message(thread_id="trace-thread", role="assistant", tool_calls=calls)
            elif sink == "success":
                runs.terminalize_success_with_message(thread_store=threads, run_id="trace-run",
                                                     done_data={"answer": "answer"}, tool_calls=calls)
            else:
                runs.terminalize_error_with_message(thread_store=threads, run_id="trace-run", status="failed",
                    error="failed", error_code="provider_call_failed", tool_calls=calls)

    with capture_lock.research_operation(store.paths.capture_root, exclusive=True):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(write).result(timeout=5)
    assert runs.get_run("trace-run").status == "running"
    assert runs.list_events("trace-run") == []
    assert len(threads.list_messages("trace-thread")) == 1


def test_copy_of_durable_references_can_complete_during_maintenance(evidence, trace_stores, monkeypatch):
    runs, threads = trace_stores
    paths = evidence.rig.store.paths
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    runs.mark_running("trace-run")
    runs.append_running_event("trace-run", "tool_end", {
        "tool": "read_sec_filing", "sec_citations": [evidence.document_ref],
    })
    with capture_lock.research_operation(paths.capture_root, exclusive=True):
        with ThreadPoolExecutor(max_workers=1) as pool:
            saved = pool.submit(runs.terminalize_success_with_message, thread_store=threads,
                                run_id="trace-run", done_data={"answer": "already retained"}).result(timeout=5)
    assert saved.status == "succeeded"
    assert threads.list_messages("trace-thread")[-1].tool_calls[0]["sec_citations"] == [evidence.document_ref]


def _retained_worker(root, ready, stop):
    with capture_lock.ResearchPublication() as publication, publication.activate():
        with capture_lock.research_operation(root):
            pass
        ready.set()
        stop.wait(20)


def test_retained_publication_blocks_other_process_until_owner_dies(tmp_path):
    root = tmp_path / "missing"
    context = multiprocessing.get_context("fork")
    ready, stop = context.Event(), context.Event()
    process = context.Process(target=_retained_worker, args=(root, ready, stop))
    process.start()
    try:
        assert ready.wait(10)
        assert other_owner(root) == "sec_research_operation_busy"
        process.terminate()
        process.join(10)
        assert not process.is_alive()
        assert other_owner(root) == "entered"
    finally:
        if process.is_alive():
            process.terminate()
        process.join(10)
