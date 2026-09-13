"""Operation exclusion and portable bundles over disposable, offline stores."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from contextvars import copy_context

import pytest

from src.sec_research import capture_lock
from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.queries import StoredQueries
from src.sec_research.service import ResearchService
from src.sec_research.store import Store
from tests.test_sec_research_service import CIK, NOW, Transport
from tests.test_sec_research_citations import evidence, rig
from tests.test_sec_research_trace import trace_stores


def operation(root, **kwargs):
    # Before Task5 the real producer permits maintenance in this gap.
    return getattr(capture_lock, "research_operation", lambda *a, **k: nullcontext())(root, **kwargs)


def admission(root, *, exclusive=True):
    try:
        with operation(root, exclusive=exclusive):
            return "entered"
    except ValueError as exc:
        return str(exc)


def other_owner(root, *, exclusive=True):
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(admission, root, exclusive=exclusive).result(timeout=5)


@pytest.fixture
def store(tmp_path):
    result = Store(SecResearchPaths.from_market_db(tmp_path / "market.db"))
    result.install()
    return result


def test_maintenance_cannot_enter_put_to_publish_gap(store, monkeypatch):
    captures = CaptureStore(store, budget=lambda: 1024**2, free_bytes=lambda _: 1024**3)
    put = captures.put
    admissions = []

    def paused_put(body):
        sha = put(body)
        admissions.append(other_owner(store.paths.capture_root))
        return sha

    monkeypatch.setattr(captures, "put", paused_put)
    receipt = ResearchService(store, captures, Transport(), clock=lambda: NOW).refresh(CIK)
    assert receipt["status"] == "ok"
    assert admissions == ["sec_research_operation_busy"] * 3
    assert other_owner(store.paths.capture_root) == "entered"


def test_stored_reader_lease_does_not_create_capture_root(store, monkeypatch):
    original = store.latest_receipt
    admissions = []

    def paused_receipt(cik):
        result = original(cik)
        admissions.append(other_owner(store.paths.capture_root))
        return result

    monkeypatch.setattr(store, "latest_receipt", paused_receipt)
    assert StoredQueries(store).filings(CIK)["status"] == "unavailable"
    assert admissions == ["sec_research_operation_busy"]
    assert not store.paths.capture_root.exists()


def test_capture_read_retains_lease_through_bytes(store, monkeypatch):
    captures = CaptureStore(store, budget=lambda: 1024**2, free_bytes=lambda _: 1024**3)
    sha = captures.put(b"retained bytes")
    original = capture_lock.CaptureDirectory.read
    admissions = []

    def read(directory, key, size):
        admissions.append(other_owner(store.paths.capture_root))
        return original(directory, key, size)

    monkeypatch.setattr(capture_lock.CaptureDirectory, "read", read)
    assert captures.read(sha) == b"retained bytes"
    assert admissions == ["sec_research_operation_busy"]


def test_operation_reentrancy_is_thread_and_task_owned(tmp_path):
    root = tmp_path / "missing"
    with operation(root, exclusive=True):
        assert admission(root) == "entered"
        context = copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(context.run, admission, root).result(timeout=5) == "sec_research_operation_busy"

    async def scenario():
        with operation(root, exclusive=True):
            assert admission(root, exclusive=False) == "entered"

            async def child():
                return admission(root, exclusive=False)

            assert await asyncio.create_task(child()) == "sec_research_operation_busy"

    asyncio.run(scenario())
    assert other_owner(root) == "entered"
    assert not root.exists()


def test_shared_operations_coexist_but_never_upgrade(tmp_path):
    root = tmp_path / "missing"
    with operation(root):
        assert admission(root, exclusive=False) == "entered"
        assert other_owner(root, exclusive=False) == "entered"
        assert admission(root) == "sec_research_operation_busy"
        assert other_owner(root) == "sec_research_operation_busy"
    assert other_owner(root) == "entered"


def test_operation_exception_releases_and_rejects_unsafe_root(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(RuntimeError):
        with operation(root):
            raise RuntimeError("interrupted")
    assert other_owner(root) == "entered"
    root.symlink_to(tmp_path / "outside", target_is_directory=True)
    assert admission(root) == "capture_path_unsafe"


def test_operation_unsupported_platform_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_lock, "_supported", lambda: False)
    assert admission(tmp_path / "root") == "capture_platform_unsupported"


def test_stale_copied_context_cannot_reuse_released_lease(tmp_path):
    root = tmp_path / "missing"
    with operation(root, exclusive=True):
        stale = copy_context()

    def resumed():
        with operation(root):
            return other_owner(root)

    assert stale.run(resumed) == "sec_research_operation_busy"


@pytest.mark.parametrize("sink", ["message", "event", "terminal"])
def test_direct_reference_publication_holds_operation(evidence, trace_stores, monkeypatch, sink):
    runs, threads = trace_stores
    root = evidence.rig.store.paths.capture_root
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: evidence.rig.store.paths)
    target, method = ((threads, "_append_message_on_connection") if sink != "event" else
                      (runs, "_append_event_on_connection"))
    original = getattr(target, method)
    admissions = []

    def commit(*args, **kwargs):
        admissions.append(other_owner(root))
        return original(*args, **kwargs)

    monkeypatch.setattr(target, method, commit)
    if sink == "message":
        threads.append_message(thread_id="trace-thread", role="assistant", content="answer",
            tool_calls=[{"name": "read_sec_filing", "input": {}, "sec_citations": [evidence.document_ref]}])
    elif sink == "event":
        runs.append_event("trace-run", "tool_end", {"tool": "read_sec_filing", "sec_citations": [evidence.document_ref]})
    else:
        runs.terminalize_error_with_message(thread_store=threads, run_id="trace-run", status="failed",
            error="provider failed", error_code="provider_call_failed",
            tool_calls=[{"name": "read_sec_filing", "input": {}, "sec_citations": [evidence.document_ref]}])
    assert admissions == ["sec_research_operation_busy"]


def test_legacy_stream_keeps_result_lease_until_transcript(evidence, trace_stores, monkeypatch):
    from src.api.routes import query
    from src.agents.shared.events import AgentEvent, EventType
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding

    _, threads = trace_stores
    paths = evidence.rig.store.paths
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    monkeypatch.setattr(query, "capture_runtime_auth", lambda _: RuntimeAuthBinding(
        "openai", "db_api_key", "api_key", None, _api_key="offline-key"))
    monkeypatch.setattr(query, "_resolve_query_task_route", lambda *_: ("gpt-5.4-mini", "low"))
    monkeypatch.setattr(query, "_require_live_model_auth", lambda *_: None)
    monkeypatch.setattr(query, "_require_client_compaction_compatibility", lambda *_: None)
    monkeypatch.setattr(query, "_resolve_personalization", lambda _: ("", {}))
    admissions = []

    async def stream(**kwargs):
        admissions.append(other_owner(paths.capture_root))
        yield AgentEvent(EventType.tool_end, {"tool": "read_sec_filing", "call_id": "saved",
            "input": {}, "summary": "preview", "sec_citations": [evidence.document_ref]})
        admissions.append(other_owner(paths.capture_root))
        yield AgentEvent(EventType.done, {"answer": "Answer", "provider": "openai", "model": "gpt-5.4-mini"})

    monkeypatch.setattr(query, "_research_provider_stream", stream)

    async def execute():
        response = await query.query_agent_stream(query.QueryRequest(question="Question", provider="openai",
            thread_id="trace-thread"), dal=object(), store=threads)
        async for _ in response.body_iterator:
            admissions.append(other_owner(paths.capture_root))

    asyncio.run(execute())
    assert len(admissions) == 4
    assert set(admissions) == {"sec_research_operation_busy"}
    assert threads.list_messages("trace-thread")[-1].tool_calls[0]["sec_citations"] == [evidence.document_ref]
    assert other_owner(paths.capture_root) == "entered"


@pytest.mark.parametrize("terminal", ["success", "error", "cancel"])
def test_research_result_lease_reaches_durable_commit(evidence, trace_stores, monkeypatch, terminal):
    from src.agents.shared.events import AgentEvent, EventType
    from src.auth_drivers.runtime_binding import RuntimeAuthBinding
    from src.research_run_manager import execute_research_run
    from src.sec_research.citations import read_sec_citation

    runs, threads = trace_stores
    paths = evidence.rig.store.paths
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    monkeypatch.setattr("src.api.personalization.resolve_personalization", lambda _: ("", {
        "profile_active": False, "assistant_stance": "off", "skill_mode": "off",
        "suggested_skills": [], "applied_skills": [], "context_snapshot": ""}))
    admissions = []
    original = threads._append_message_on_connection

    def append(*args, **kwargs):
        admissions.append(("message", other_owner(paths.capture_root)))
        return original(*args, **kwargs)

    monkeypatch.setattr(threads, "_append_message_on_connection", append)
    original_event = runs.append_event

    def event(run_id, kind, data):
        if kind == "tool_end":
            admissions.append(("event", other_owner(paths.capture_root)))
        return original_event(run_id, kind, data)

    monkeypatch.setattr(runs, "append_event", event)

    async def stream(**kwargs):
        result = read_sec_citation(evidence.rig.store, evidence.rig.captures, citation=evidence.document_ref)
        assert result["status"] == "ok"
        admissions.append(("result", other_owner(paths.capture_root)))
        yield AgentEvent(EventType.tool_end, {"tool": "read_sec_filing", "call_id": "saved",
            "input": {}, "summary": "preview", "sec_citations": [evidence.document_ref]})
        if terminal == "cancel":
            raise asyncio.CancelledError
        yield (AgentEvent(EventType.error, {"error": "provider failed"}) if terminal == "error" else
               AgentEvent(EventType.done, {"answer": "Answer", "provider": "openai", "model": "gpt-5.4-mini"}))

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
    assert threads.list_messages("trace-thread")[-1].tool_calls[0]["sec_citations"] == [evidence.document_ref]
    assert admissions == [(phase, "sec_research_operation_busy") for phase in ("result", "event", "message")]
    assert other_owner(paths.capture_root) == "entered"
