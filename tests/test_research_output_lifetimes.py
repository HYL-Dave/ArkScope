"""Task 3 RED owners for retained guards and async iterator ownership."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
from dataclasses import replace

import pytest

from src.agents.shared.events import AgentEvent, EventType
from src.agents.shared.output_boundary import (
    OutputBoundaryError, OutputGuard, activate_output_guard, current_output_guard, output_scope,
)
from src.auth_drivers.runtime_binding import (
    RuntimeAuthBinding, activate_runtime_auth, current_runtime_auth,
)
from tests.test_research_output_events import (
    CHANNELS, PUBLIC, SECRET, collect, event_text, make_producer, managed_run, terminal,
)
from tests.test_task_runtime_binding import add_key, isolated


def event_api():
    name = "src.agents.shared.output_events"
    assert importlib.util.find_spec(name) is not None, "missing Task3 ProtectedEventStream / protect_events boundary"
    module = importlib.import_module(name)
    assert isinstance(getattr(module, "ProtectedEventStream", None), type), "missing Task3 trusted iterator type"
    assert callable(getattr(module, "protect_events", None)), "missing Task3 protect_events factory"
    return module


def test_wrapper_activates_only_during_interleaved_upstream_advance_and_close():
    api = event_api()
    seen = []
    first_guard = OutputGuard([SECRET])
    second_guard = OutputGuard(["other-synthetic-key"])

    async def raw(label):
        try:
            seen.append((label, "next", current_output_guard()))
            yield AgentEvent(EventType.thinking, {"turn": 1})
            seen.append((label, "next", current_output_guard()))
            yield AgentEvent(EventType.done, {"answer": "Public"})
        finally:
            seen.append((label, "close", current_output_guard()))

    async def drive():
        with output_scope("consumer-synthetic-key") as consumer:
            first = api.protect_events(raw("first"), guard=first_guard)
            second = api.protect_events(raw("second"), guard=second_guard)
            try:
                await anext(first)
                assert current_output_guard() is consumer
                await anext(second)
                assert current_output_guard() is consumer
                await first.aclose()
                assert current_output_guard() is consumer
                await anext(second)
                assert current_output_guard() is consumer
            finally:
                await first.aclose()
                await second.aclose()
    asyncio.run(drive())
    assert seen == [
        ("first", "next", first_guard), ("second", "next", second_guard),
        ("first", "close", first_guard), ("second", "next", second_guard),
        ("second", "close", second_guard),
    ]
    assert current_output_guard() is None


def test_factory_reuses_only_exact_trusted_type_with_same_guard():
    api = event_api()
    guard = OutputGuard([SECRET])

    async def raw():
        yield AgentEvent(EventType.done, {"answer": SECRET})

    async def drive():
        protected = api.protect_events(raw(), guard=guard)
        try:
            assert type(protected) is api.ProtectedEventStream
            assert api.protect_events(protected, guard=guard) is protected
            with activate_output_guard(guard):
                assert api.protect_events(protected) is protected
            with pytest.raises(OutputBoundaryError, match="^invalid_value$"):
                api.protect_events(protected, guard=OutputGuard([SECRET]))
            with activate_output_guard(OutputGuard([SECRET])):
                with pytest.raises(OutputBoundaryError, match="^invalid_value$"):
                    api.protect_events(protected)
            assert terminal(await collect(protected))["answer"] == "[REDACTED]"
        finally:
            await protected.aclose()
    asyncio.run(drive())


def test_subclass_cannot_claim_already_protected_status():
    api = event_api()
    guard = OutputGuard([SECRET])

    class Forged(api.ProtectedEventStream):
        def __init__(self):
            self.sent = False

        @property
        def guard(self):
            return guard

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.sent:
                raise StopAsyncIteration
            self.sent = True
            return AgentEvent(EventType.done, {"answer": SECRET})

        async def aclose(self):
            pass

    async def drive():
        forged = Forged()
        protected = api.protect_events(forged, guard=guard)
        assert protected is not forged
        assert type(protected) is api.ProtectedEventStream
        assert terminal(await collect(protected))["answer"] == "[REDACTED]"
    asyncio.run(drive())


@pytest.mark.parametrize("flag", ["protected", "output_protected", "_output_guarded"])
def test_payload_boolean_cannot_bypass_closed_event_projection(flag):
    api = event_api()

    async def raw():
        yield AgentEvent(EventType.text, {"content": SECRET, flag: True, "extra": SECRET})

    async def drive():
        with pytest.raises(OutputBoundaryError):
            await collect(api.protect_events(raw(), guard=OutputGuard([SECRET])))
    asyncio.run(drive())


def test_wrapper_preserves_public_tool_metadata_and_typed_counters():
    api = event_api()
    data = [
        (EventType.tool_start, {"tool": "search_news_advanced", "call_id": "call_1234567890123456789",
                               "input": {"query": PUBLIC, "limit": 20}}),
        (EventType.tool_end, {"tool": "search_news_advanced", "call_id": "call_1234567890123456789",
                             "summary": PUBLIC, "chars": len(PUBLIC), "is_error": False}),
        (EventType.done, {"answer": PUBLIC, "provider": "openai", "model": "gpt-5.6-luna",
                         "tools_used": ["search_news_advanced"], "token_usage": {"input_tokens": 8012345678907}}),
    ]

    async def raw():
        for kind, payload in data:
            yield AgentEvent(kind, payload)

    events = asyncio.run(collect(api.protect_events(raw(), guard=OutputGuard([SECRET]))))
    assert [(event.type, event.data) for event in events] == data
    # check() deliberately does not stringify numeric leaves. Admission must
    # also check the canonical JSON spelling before emitting this counter.
    with pytest.raises(OutputBoundaryError, match="^known_secret$"):
        asyncio.run(collect(api.protect_events(raw(), guard=OutputGuard(["8012345678907"]))))


def test_text_and_thinking_have_independent_rolling_state():
    api = event_api()

    async def raw():
        yield AgentEvent(EventType.text, {"content": SECRET[:3]})
        yield AgentEvent(EventType.thinking_content, {"thinking": "Reason|" + SECRET[:2]})
        yield AgentEvent(EventType.text, {"content": SECRET[3:]})
        yield AgentEvent(EventType.thinking_content, {"thinking": SECRET[2:] + "|End"})
        yield AgentEvent(EventType.done, {"answer": "Public"})

    events = asyncio.run(collect(api.protect_events(raw(), guard=OutputGuard([SECRET]))))
    assert event_text(events) == "[REDACTED]"
    assert event_text(events, EventType.thinking_content) == "Reason|[REDACTED]|End"


@pytest.mark.parametrize("ending", ["eof", "done"])
def test_normal_completion_flushes_unmatched_tail_before_terminal(ending):
    api = event_api()
    partial = SECRET[:3]

    async def raw():
        yield AgentEvent(EventType.text, {"content": "Public|" + partial})
        if ending == "done":
            yield AgentEvent(EventType.done, {"answer": "Public|" + partial})

    events = asyncio.run(collect(api.protect_events(raw(), guard=OutputGuard([SECRET]))))
    assert event_text(events) == "Public|" + partial
    if ending == "done":
        assert events[-1].type == EventType.done
        assert terminal(events)["answer"] == "Public|" + partial
    else:
        assert all(event.type == EventType.text for event in events)


@pytest.mark.parametrize("ending", ["error", "exception", "close", "cancel"])
def test_abnormal_exit_drops_pending_tail_and_closes_upstream(ending):
    api = event_api()
    guard = OutputGuard([SECRET])
    closed, events = [], []

    async def drive():
        waiting = asyncio.Event()
        release = asyncio.Event()

        async def raw():
            try:
                yield AgentEvent(EventType.text, {"content": SECRET[:3]})
                yield AgentEvent(EventType.thinking, {"turn": 1})
                if ending == "error":
                    yield AgentEvent(EventType.error, {"error": "upstream failed", "code": "provider_call_failed"})
                elif ending == "exception":
                    raise RuntimeError("synthetic upstream failure")
                elif ending == "cancel":
                    waiting.set()
                    await release.wait()
            finally:
                closed.append(current_output_guard())

        stream = api.protect_events(raw(), guard=guard)
        try:
            events.append(await anext(stream))
            assert events[-1].type == EventType.thinking, "pending raw prefix escaped before abort"
            assert current_output_guard() is None
            if ending == "close":
                await stream.aclose()
            elif ending == "exception":
                with pytest.raises(RuntimeError, match="synthetic upstream failure"):
                    await anext(stream)
            elif ending == "cancel":
                advance = asyncio.create_task(anext(stream))
                try:
                    await asyncio.wait_for(waiting.wait(), timeout=2)
                    advance.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await advance
                finally:
                    release.set()
                    if not advance.done():
                        advance.cancel()
                    await asyncio.gather(advance, return_exceptions=True)
            else:
                events.append(await anext(stream))
                assert events[-1].type == EventType.error
            with pytest.raises(StopAsyncIteration):
                await anext(stream)
        finally:
            await stream.aclose()
    asyncio.run(drive())
    assert closed == [guard]
    assert event_text(events) == ""
    assert current_output_guard() is None


def test_terminal_closes_before_public_yield_and_cannot_repeat():
    api = event_api()
    seen = []

    async def raw():
        try:
            yield AgentEvent(EventType.done, {"answer": "Public"})
            seen.append("advanced-after-terminal")
            yield AgentEvent(EventType.error, {"error": "second terminal"})
        finally:
            seen.append("closed")

    async def drive():
        stream = api.protect_events(raw(), guard=OutputGuard())
        try:
            assert (await anext(stream)).type == EventType.done
            assert seen == ["closed"], "terminal left upstream suspended and owning resources"
            for _ in range(2):
                with pytest.raises(StopAsyncIteration):
                    await anext(stream)
            await stream.aclose()
            await stream.aclose()
        finally:
            await stream.aclose()
    asyncio.run(drive())
    assert seen == ["closed"]


def test_non_reentrant_next_and_close_do_not_steal_inflight_ownership():
    api = event_api()
    closed = []

    async def drive():
        entered, release = asyncio.Event(), asyncio.Event()

        async def raw():
            try:
                entered.set()
                await release.wait()
                yield AgentEvent(EventType.done, {"answer": "Public"})
            finally:
                closed.append(True)

        stream = api.protect_events(raw(), guard=OutputGuard())
        first = asyncio.create_task(anext(stream))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            with pytest.raises(RuntimeError):
                await anext(stream)
            with pytest.raises(RuntimeError):
                await stream.aclose()
            release.set()
            assert (await first).type == EventType.done
        finally:
            release.set()
            await asyncio.gather(first, return_exceptions=True)
            await stream.aclose()
    asyncio.run(drive())
    assert closed == [True]


def test_closing_borrowed_wrapper_does_not_abort_sibling_or_late_registered_secret():
    api = event_api()
    guard = OutputGuard([SECRET])
    sibling = guard.stream()
    assert sibling.feed(SECRET[:3]) == ""

    async def raw():
        yield AgentEvent(EventType.thinking, {"turn": 1})

    async def drive():
        stream = api.protect_events(raw(), guard=guard)
        await anext(stream)
        await stream.aclose()
    asyncio.run(drive())
    assert sibling.feed(SECRET[3:]) + sibling.finish() == "[REDACTED]"
    guard.add_secret("child-synthetic-key")
    with pytest.raises(OutputBoundaryError, match="^known_secret$"):
        guard.check("child-synthetic-key")


@pytest.mark.parametrize("channel", CHANNELS)
def test_actual_producer_reuses_active_guard_and_restores_consumer(make_producer, channel):
    api = event_api()
    producer = make_producer(channel, answer=SECRET)

    async def drive():
        with output_scope() as guard:
            stream = producer.stream()
            assert type(stream) is api.ProtectedEventStream
            assert api.protect_events(stream, guard=guard) is stream
            with output_scope("consumer-only-key") as consumer:
                try:
                    while True:
                        try:
                            await anext(stream)
                        except StopAsyncIteration:
                            break
                        assert current_output_guard() is consumer
                finally:
                    await stream.aclose()
                assert current_output_guard() is consumer
    asyncio.run(drive())


@pytest.mark.parametrize("channel", ["chatgpt", "claude"])
def test_oauth_terminal_releases_client_or_config_before_consumer_resumes(make_producer, channel):
    producer = make_producer(channel, chunks=["Public"], answer="Public")

    async def drive():
        stream = producer.stream()
        try:
            while True:
                event = await anext(stream)
                if event.type in (EventType.done, EventType.error):
                    assert event.type == EventType.done, event.data
                    assert producer.closed, "SDK/client cleanup was deferred past the terminal public yield"
                    if producer.config_dir is not None:
                        assert not producer.config_dir.exists()
                    break
            with pytest.raises(StopAsyncIteration):
                await anext(stream)
        finally:
            await stream.aclose()
    asyncio.run(drive())


@pytest.mark.parametrize("cancellations", [0, 1, 2], ids=["normal-close", "cancel-during-close", "cancel-again-during-close"])
def test_chatgpt_terminal_cleanup_is_owned_until_settled(make_producer, monkeypatch, cancellations):
    from src.auth_drivers import chatgpt_oauth_driver as driver_module

    producer = make_producer("chatgpt", chunks=[SECRET[:3]], answer="Public answer")
    execution_client = driver_module._execution_client
    observed, close_guards = [], []

    async def drive():
        entered, release = asyncio.Event(), asyncio.Event()
        original_closes = []

        def client_factory(token):
            client = execution_client(token)
            close = client.close
            original_closes.append(close)

            async def delayed_close():
                close_guards.append(("start", current_output_guard()))
                entered.set()
                await release.wait()
                await close()
                close_guards.append(("finish", current_output_guard()))

            client.close = delayed_close
            return client

        monkeypatch.setattr(driver_module, "_execution_client", client_factory)
        stream = producer.stream()
        with output_scope("consumer-only-key") as consumer_guard:
            async def consume():
                try:
                    async for event in stream:
                        assert current_output_guard() is consumer_guard
                        observed.append(event)
                finally:
                    assert current_output_guard() is consumer_guard
                    await stream.aclose()
                    assert current_output_guard() is consumer_guard

            consumer = asyncio.create_task(consume())
            try:
                await asyncio.wait_for(entered.wait(), timeout=2)
                assert not producer.closed
                assert current_output_guard() is consumer_guard
                with pytest.raises(RuntimeError, match="^event_stream_busy$"):
                    await anext(stream)
                with pytest.raises(RuntimeError, match="^event_stream_busy$"):
                    await stream.aclose()
                for _ in range(cancellations):
                    consumer.cancel()
                    await asyncio.sleep(0)
                    assert not consumer.done(), "cancellation returned before in-flight cleanup settled"
                    with pytest.raises(RuntimeError, match="^event_stream_busy$"):
                        await stream.aclose()
                release.set()
                outcome = await asyncio.wait_for(asyncio.gather(consumer, return_exceptions=True), timeout=2)
                if cancellations:
                    assert isinstance(outcome[0], asyncio.CancelledError)
                    assert event_text(observed) == "", "cancellation flushed a pending credential prefix"
                    assert not any(event.type in (EventType.done, EventType.error) for event in observed)
                else:
                    assert outcome == [None]
                    assert event_text(observed) == SECRET[:3]
                    assert terminal(observed)["answer"] == "Public answer"
                assert producer.closed
                assert close_guards == [("start", stream.guard), ("finish", stream.guard)]
                assert len(original_closes) == 1
                await stream.aclose()
                with pytest.raises(StopAsyncIteration):
                    await anext(stream)
                assert current_output_guard() is consumer_guard
            finally:
                release.set()
                if not consumer.done():
                    consumer.cancel()
                await asyncio.gather(consumer, return_exceptions=True)
                await stream.aclose()
                if not producer.closed:
                    for close in original_closes:
                        await close()

    asyncio.run(drive())
    assert current_output_guard() is None


@pytest.mark.parametrize("channel", ["chatgpt", "claude"])
def test_actual_oauth_cancel_drops_pending_prefix_and_cleans_up(make_producer, channel):
    observed = []

    async def drive():
        entered, release = asyncio.Event(), asyncio.Event()
        producer = make_producer(channel, chunks=[SECRET[:3]], pause=(entered, release))

        async def consume():
            stream = producer.stream()
            try:
                async for event in stream:
                    observed.append(event)
            finally:
                await stream.aclose()

        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            task.cancel()
            # Preserve each driver's existing cancellation surface: propagated
            # cancellation or a single typed error, never successful completion.
            outcome = await asyncio.gather(task, return_exceptions=True)
            assert outcome[0] is None or isinstance(outcome[0], asyncio.CancelledError)
            assert producer.closed
            if producer.config_dir is not None:
                assert not producer.config_dir.exists()
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(drive())
    assert event_text(observed) == "", "cancellation released an undecidable credential prefix"
    assert not any(event.type == EventType.done for event in observed)
    assert len([event for event in observed if event.type == EventType.error]) <= 1
    assert current_output_guard() is None


def test_actual_producer_and_manager_have_one_rolling_tail(make_producer, managed_run, isolated, monkeypatch):
    from src.research_run_manager import execute_research_run

    bearer = "fixture-bearer." + "j" * (2051 - len("fixture-bearer."))
    text = ("Public answer " * 800)[:10400]
    producer = make_producer("chatgpt", chunks=[text[i:i + 3] for i in range(0, len(text), 3)], answer=text, secret=bearer)
    first_emission = []
    append = isolated.runs.append_event

    def observe(run_id, kind, data):
        if kind == "text" and data.get("content") and not first_emission:
            first_emission.append(producer.input_chars)
        return append(run_id, kind, data)

    monkeypatch.setattr(isolated.runs, "append_event", observe)
    kwargs = {**managed_run, "auth_binding": replace(managed_run["auth_binding"], _api_key=bearer)}
    asyncio.run(execute_research_run(**kwargs, stream_factory=lambda **kw: producer.stream()))
    assert first_emission == [2736], "producer/manager must retain exactly one 2735-character undecided suffix"
    events = isolated.runs.list_events("boundary-run", limit=5000)
    assert "".join(event.data["content"] for event in events if event.type == "text") == text
    assert isolated.runs.get_run("boundary-run").status == "succeeded"
    assert producer.closed


@pytest.mark.parametrize("ending", ["cancel", "exception"])
def test_managed_abort_drops_tail_and_closes_injected_iterator(managed_run, isolated, ending):
    from src.research_run_manager import execute_research_run

    closed = []

    async def drive():
        entered, release = asyncio.Event(), asyncio.Event()

        async def raw(**kwargs):
            try:
                yield AgentEvent(EventType.text, {"content": SECRET[:3]})
                entered.set()
                if ending == "exception":
                    raise RuntimeError("synthetic stream failed")
                await release.wait()
            finally:
                closed.append(current_output_guard())

        task = asyncio.create_task(execute_research_run(**managed_run, stream_factory=raw))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            if ending == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                await task
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(drive())
    events = isolated.runs.list_events("boundary-run")
    assert not any(event.type == "text" and event.data.get("content") for event in events), "abort persisted an undecidable raw prefix"
    assert len(closed) == 1 and closed[0] is not None
    assert len([event for event in events if event.type in ("done", "error")]) == 1
    run = isolated.runs.get_run("boundary-run")
    assert run.status == ("cancelled" if ending == "cancel" else "failed")
    if ending == "cancel":
        assert run.error_code == "run_cancelled"
    assert current_output_guard() is None


@pytest.mark.parametrize("child_provider", ["openai", "anthropic"])
def test_threaded_child_retains_captured_secret_for_late_parent_callback(make_producer, isolated, monkeypatch, child_provider):
    from src.agents import config
    from src.agents.shared import subagent
    from src.agents.openai_agent.tools import _serialize_result

    parent_secret = "parent-synthetic-key"
    child_secret = parent_secret if child_provider == "openai" else SECRET
    make_producer(child_provider, answer="Public child answer", secret=child_secret)
    add_key(isolated.credentials, "anthropic", SECRET)
    model = "gpt-5.4-mini" if child_provider == "openai" else "claude-sonnet-4-6"
    monkeypatch.setattr(config, "get_agent_config", lambda: config.AgentConfig(
        web_openai_search=False, subagent_models={"code_analyst": model},
    ))
    parent = RuntimeAuthBinding("openai", "fixture", "api_key", _api_key=parent_secret)

    async def drive():
        with output_scope(parent_secret) as guard, activate_runtime_auth(parent):
            result = await asyncio.to_thread(subagent.dispatch_subagent, "code_analyst", "Public question", dal=object())
            assert result["error"] is None, result
            assert result["answer"] == "Public child answer"
            assert current_runtime_auth("openai") is parent
            assert current_output_guard() is guard
            with pytest.raises(OutputBoundaryError, match="^known_secret$"):
                guard.check(child_secret)
            with pytest.raises(OutputBoundaryError, match="^known_secret$"):
                _serialize_result({"answer": child_secret}, tool_name="delegate_to_subagent")
        assert current_output_guard() is None
    asyncio.run(drive())


@pytest.mark.parametrize("channel", ["chatgpt", "claude"])
def test_oauth_worker_callback_retains_child_secret_in_parent_guard(isolated, monkeypatch, channel):
    from src.tools import registry as registry_module
    from src.agents.shared.output_boundary import remember_output_secret

    child_secret = "late-child-callback-key"
    seen = []

    def handler(dal, **kwargs):
        seen.append(current_output_guard())
        remember_output_secret(child_secret)
        return {"count": 0}

    registry = registry_module.create_default_registry()
    registry.get("get_news_brief").function = handler

    async def invoke():
        if channel == "chatgpt":
            from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
            return await OpenAIChatGPTOAuthDriver(registry=registry, dal=object())._invoke_tool(
                name="get_news_brief", args={"days": 7}, token=SECRET,
            )
        from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool
        return await _invoke_bridged_tool(name="get_news_brief", args={"days": 7}, token=SECRET,
                                          registry=registry, dal=object(), per_tool_timeout_s=5)

    with output_scope(SECRET) as guard:
        result = asyncio.run(invoke())
        assert seen == [guard], "executor callback lost the execution guard context"
        with pytest.raises(OutputBoundaryError, match="^known_secret$"):
            guard.check(child_secret)
        assert "no_output_scope" not in str(result)
