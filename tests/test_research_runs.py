from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import pytest

from src.api.routes import query as q
from src.api.routes import research as r
from src.auth_drivers.live_resolver import LiveAuthResolution
from src.agents.shared.events import AgentEvent, EventType
from src.research_runs import ResearchRunStore
from src.research_threads import ResearchThreadStore


@pytest.fixture()
def stores(tmp_path):
    db = tmp_path / "profile_state.db"
    return ResearchRunStore(db), ResearchThreadStore(db)


def _seed_run(
    run_store,
    thread_store,
    *,
    thread_id,
    run_id,
    provider="openai",
    model="gpt-5.4-mini",
    effort="low",
):
    thread_store.ensure_thread(id=thread_id, title=f"Question {thread_id}")
    run = run_store.create_run(
        id=run_id,
        thread_id=thread_id,
        question=f"question {thread_id}",
        ticker=None,
        provider=provider,
        model=model,
        effort=effort,
        auth_mode="api_key",
        credential_id="local:test",
    )
    thread_store.append_message(
        thread_id=thread_id,
        run_id=run_id,
        role="user",
        content=f"question {thread_id}",
    )
    return run


def _pause_terminal_message(monkeypatch, thread_store, *, error_code):
    paused = threading.Event()
    release = threading.Event()
    original = thread_store._append_message_on_connection

    def pausing_append(conn, **kwargs):
        if kwargs.get("error_code") == error_code:
            paused.set()
            assert release.wait(timeout=5), "terminal message pause was not released"
        return original(conn, **kwargs)

    monkeypatch.setattr(thread_store, "_append_message_on_connection", pausing_append)
    return paused, release


def test_run_store_create_events_and_active_summary(stores):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q", provider="openai", model="gpt-5.4-mini")

    run = run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="openai", model="gpt-5.4-mini", effort="low",
        auth_mode="api_key", credential_id="local:3",
    )
    assert run.status == "queued"
    assert run_store.latest_active_for_thread("t1").id == "r1"
    assert list(run_store.get_runs(["r1", "missing", "r1"])) == ["r1"]
    with pytest.raises(ValueError, match="cannot exceed"):
        run_store.get_runs([f"run-{index}" for index in range(201)])

    e1 = run_store.append_event("r1", "thinking", {"turn": 1})
    e2 = run_store.append_event("r1", "done", {"answer": "ok"})
    assert (e1.seq, e2.seq) == (1, 2)
    assert [e.seq for e in run_store.list_events("r1", after=1)] == [2]

    run_store.mark_terminal("r1", "succeeded", token_usage={"total_tokens": 3})
    assert run_store.get_run("r1").status == "succeeded"
    assert run_store.latest_active_for_thread("t1") is None


def test_reconcile_interrupted_marks_orphaned_runs_terminal(stores):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q")
    run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="anthropic", model="claude-sonnet-4-6", effort=None,
        auth_mode="claude_code_oauth", credential_id="local:7",
    )

    changed = run_store.reconcile_interrupted(thread_store=thread_store)

    assert changed == ["r1"]
    got = run_store.get_run("r1")
    assert got.status == "interrupted"
    assert "interrupted" in (got.error or "")
    msgs = thread_store.list_messages("t1")
    assert msgs[-1].is_error is True
    assert "interrupted" in msgs[-1].content


def test_execute_run_records_events_and_persists_assistant(stores):
    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q")
    thread_store.append_message(thread_id="t1", role="user", content="q")
    run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="anthropic", model="claude-sonnet-4-6", effort="high",
        auth_mode="api_key", credential_id="local:2",
    )

    async def stream_factory(**kwargs):
        yield AgentEvent(EventType.tool_start, {"tool": "get_sa_feed", "input": {"ticker": "AAPL"}})
        yield AgentEvent(EventType.tool_end, {"tool": "get_sa_feed", "summary": "2 articles", "chars": 20})
        yield AgentEvent(EventType.done, {
            "answer": "answer", "provider": "anthropic", "model": "claude-sonnet-4-6",
            "tools_used": ["get_sa_feed"], "token_usage": {"total_tokens": 9},
        })

    asyncio.run(execute_research_run(
        run_id="r1", run_store=run_store, thread_store=thread_store,
        dal=object(), history=[], stream_factory=stream_factory,
    ))

    assert run_store.get_run("r1").status == "succeeded"
    assert [e.type for e in run_store.list_events("r1")] == ["tool_start", "tool_end", "done"]
    msgs = thread_store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[-1].content == "answer"
    assert msgs[-1].effort == "high"
    assert msgs[-1].tool_calls == [{"name": "get_sa_feed", "input": {"ticker": "AAPL"}, "result_preview": "2 articles"}]


def test_execute_run_error_event_persists_error_assistant(stores):
    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q")
    thread_store.append_message(thread_id="t1", role="user", content="q")
    run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="openai", model="gpt-5.4-mini", effort="low",
        auth_mode="chatgpt_oauth", credential_id="local:9",
    )

    async def stream_factory(**kwargs):
        yield AgentEvent(EventType.error, {"error": "backend timeout", "provider": "openai", "model": "gpt-5.4-mini"})

    asyncio.run(execute_research_run(
        run_id="r1", run_store=run_store, thread_store=thread_store,
        dal=object(), history=[], stream_factory=stream_factory,
    ))

    assert run_store.get_run("r1").status == "failed"
    msgs = thread_store.list_messages("t1")
    assert msgs[-1].is_error is True
    assert msgs[-1].content == "backend timeout"
    assert msgs[-1].effort == "low"


def test_create_run_route_persists_user_and_schedules_with_prior_history(stores, monkeypatch):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="prev")
    thread_store.append_message(thread_id="t1", role="user", content="prev q")
    thread_store.append_message(thread_id="t1", role="assistant", content="prev a")
    scheduled = {}

    def fake_schedule_research_run(**kwargs):
        scheduled.update(kwargs)

    monkeypatch.setattr(r, "schedule_research_run", fake_schedule_research_run)
    monkeypatch.setattr(r, "resolve_research_route", lambda provider: ("gpt-5.4-mini", "low"))
    monkeypatch.setattr(
        r,
        "resolve_live_auth",
        lambda provider: LiveAuthResolution(provider, "db_api_key", "local:3"),
    )

    req = r.ResearchRunCreate(
        thread_id="t1", question="follow up", ticker="AAPL",
        provider="openai", model=None, effort=None,
    )
    res = asyncio.run(r.create_research_run(
        req, dal=object(), thread_store=thread_store, run_store=run_store,
    ))

    run = res["run"]
    assert run["thread_id"] == "t1"
    assert run["status"] == "queued"
    assert run["model"] == "gpt-5.4-mini"
    assert run["effort"] == "low"
    assert run["auth_mode"] == "api_key"
    assert run["credential_id"] == "local:3"
    assert scheduled["run_id"] == run["id"]
    assert scheduled["history"] == [
        {"role": "user", "content": "prev q"},
        {"role": "assistant", "content": "prev a"},
    ]
    assert [m.content for m in thread_store.list_messages("t1")] == ["prev q", "prev a", "follow up"]


def test_threads_route_includes_active_run_summary(stores):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q")
    run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="anthropic", model="claude-sonnet-4-6", effort=None,
        auth_mode="claude_code_oauth", credential_id="local:7",
    )

    res = r.list_research_threads(limit=50, store=thread_store, run_store=run_store)

    assert res["threads"][0]["active_run"]["id"] == "r1"
    assert res["threads"][0]["active_run"]["status"] == "queued"


def test_run_events_route_replays_after_seq(stores):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q")
    run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="openai", model="gpt-5.4-mini", effort="low",
        auth_mode="api_key", credential_id="local:3",
    )
    run_store.append_event("r1", "text", {"content": "a"})
    run_store.append_event("r1", "done", {"answer": "ok"})

    res = r.list_research_run_events("r1", after=1, run_store=run_store)

    assert res["run"]["id"] == "r1"
    assert [(e["seq"], e["type"]) for e in res["events"]] == [(2, "done")]


def test_run_events_route_reports_more_events_before_terminal_page(stores):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q")
    run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="openai", model="gpt-5.5", effort="xhigh",
        auth_mode="api_key", credential_id="local:3",
    )
    for i in range(500):
        run_store.append_event("r1", "text", {"content": str(i)})
    run_store.append_event("r1", "done", {"answer": "ok"})
    run_store.mark_terminal("r1", "succeeded")

    first = r.list_research_run_events("r1", after=0, run_store=run_store)
    second = r.list_research_run_events("r1", after=500, run_store=run_store)

    assert first["run"]["status"] == "succeeded"
    assert len(first["events"]) == 500
    assert first["events"][-1]["seq"] == 500
    assert first["has_more"] is True
    assert [(e["seq"], e["type"]) for e in second["events"]] == [(501, "done")]
    assert second["has_more"] is False


def test_cancel_run_route_terminalizes_when_no_in_memory_task(stores, monkeypatch):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="t1", title="q")
    run_store.create_run(
        id="r1", thread_id="t1", question="q", ticker=None,
        provider="openai", model="gpt-5.4-mini", effort="low",
        auth_mode="api_key", credential_id="local:3",
    )
    monkeypatch.setattr(r, "cancel_research_run", lambda run_id: False)

    res = r.cancel_research_run_route(
        "r1", run_store=run_store, thread_store=thread_store
    )

    assert res["run"]["status"] == "cancelled"
    assert run_store.get_run("r1").status == "cancelled"
    assert run_store.list_events("r1")[-1].type == "error"


# ─── P2.8 Slice 3: semantic selection + typed terminal outcomes ─────────────


def test_latest_successful_selection_ignores_non_success_and_maps_default(stores):
    run_store, thread_store = stores
    _seed_run(
        run_store,
        thread_store,
        thread_id="selection",
        run_id="success",
        provider="anthropic",
        model="claude-sonnet-5",
        effort=None,
    )
    run_store.mark_terminal("success", "succeeded")
    run_store.create_run(
        id="failed",
        thread_id="selection",
        question="failed",
        ticker=None,
        provider="openai",
        model="gpt-5.6-luna",
        effort="high",
        auth_mode="api_key",
        credential_id=None,
    )
    run_store.mark_terminal("failed", "failed", error="failed")
    run_store.create_run(
        id="active",
        thread_id="selection",
        question="active",
        ticker=None,
        provider="openai",
        model="gpt-5.6-sol",
        effort="xhigh",
        auth_mode="api_key",
        credential_id=None,
    )

    selection = run_store.latest_successful_for_thread("selection")

    assert selection is not None
    assert (selection.provider, selection.model, selection.effort) == (
        "anthropic",
        "claude-sonnet-5",
        "default",
    )


def test_latest_successful_selection_orders_by_completion_then_id(stores):
    run_store, thread_store = stores
    thread_store.ensure_thread(id="selection-order", title="selection")
    for run_id, model in (("a-run", "gpt-5.4-mini"), ("z-run", "gpt-5.6-sol")):
        run_store.create_run(
            id=run_id,
            thread_id="selection-order",
            question=run_id,
            ticker=None,
            provider="openai",
            model=model,
            effort="high",
            auth_mode="api_key",
            credential_id=None,
        )
        run_store.mark_terminal(run_id, "succeeded")
    with sqlite3.connect(run_store.db_path) as conn:
        conn.execute(
            "UPDATE research_runs SET completed_at = ? WHERE id IN (?, ?)",
            ("2026-07-18T06:00:00+00:00", "a-run", "z-run"),
        )

    selection = run_store.latest_successful_for_thread("selection-order")

    assert selection is not None
    assert selection.model == "gpt-5.6-sol"


def test_openai_semantic_default_persists_but_wire_receives_none(stores, monkeypatch):
    run_store, thread_store = stores
    scheduled = {}
    monkeypatch.setattr(r, "schedule_research_run", lambda **kwargs: scheduled.update(kwargs))
    monkeypatch.setattr(r, "_resolve_auth_metadata", lambda provider: ("api_key", "local:test"))

    response = asyncio.run(
        r.create_research_run(
            r.ResearchRunCreate(
                question="default effort",
                provider="openai",
                model="gpt-5.4-mini",
                effort=None,
            ),
            dal=object(),
            thread_store=thread_store,
            run_store=run_store,
        )
    )
    run = run_store.get_run(response["run"]["id"])
    assert run is not None and run.effort == "default"

    captured = {}
    sentinel = object()

    def fake_openai_stream(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(provider, "db_api_key", "local:test"),
    )
    monkeypatch.setattr("src.agents.openai_agent.agent.run_query_stream", fake_openai_stream)
    result = q._research_provider_stream(
        provider="openai",
        question="q",
        model=run.model,
        effort=run.effort,
        dal=object(),
        history=[],
    )

    assert result is sentinel
    assert captured["reasoning_effort"] is None

    subscription_captured = {}
    subscription_sentinel = object()

    def fake_openai_subscription_stream(**kwargs):
        subscription_captured.update(kwargs)
        return subscription_sentinel

    monkeypatch.setattr(q, "_openai_subscription_stream", fake_openai_subscription_stream)
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(
            provider, "oauth_driver_unwired", "local:subscription"
        ),
    )
    subscription_result = q._research_provider_stream(
        provider="openai",
        question="q",
        model=run.model,
        effort=run.effort,
        dal=object(),
        history=[],
    )

    assert subscription_result is subscription_sentinel
    assert subscription_captured["effort"] is None


def test_anthropic_semantic_default_persists_but_wire_receives_none(stores, monkeypatch):
    run_store, thread_store = stores
    monkeypatch.setattr(r, "schedule_research_run", lambda **kwargs: None)
    monkeypatch.setattr(r, "_resolve_auth_metadata", lambda provider: ("api_key", "local:test"))

    response = asyncio.run(
        r.create_research_run(
            r.ResearchRunCreate(
                question="default effort",
                provider="anthropic",
                model="claude-sonnet-5",
                effort=None,
            ),
            dal=object(),
            thread_store=thread_store,
            run_store=run_store,
        )
    )
    run = run_store.get_run(response["run"]["id"])
    assert run is not None and run.effort == "default"

    captured = {}
    sentinel = object()

    def fake_anthropic_stream(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(provider, "db_api_key", "local:test"),
    )
    monkeypatch.setattr(
        "src.agents.anthropic_agent.agent.run_query_stream", fake_anthropic_stream
    )
    result = q._research_provider_stream(
        provider="anthropic",
        question="q",
        model=run.model,
        effort=run.effort,
        dal=object(),
        history=[],
    )

    assert result is sentinel
    assert captured["effort"] is None

    subscription_captured = {}
    subscription_sentinel = object()

    def fake_anthropic_subscription_stream(**kwargs):
        subscription_captured.update(kwargs)
        return subscription_sentinel

    monkeypatch.setattr(
        q,
        "_anthropic_subscription_stream",
        fake_anthropic_subscription_stream,
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(
            provider, "oauth_driver_unwired", "local:subscription"
        ),
    )
    subscription_result = q._research_provider_stream(
        provider="anthropic",
        question="q",
        model=run.model,
        effort=run.effort,
        dal=object(),
        history=[],
    )

    assert subscription_result is subscription_sentinel
    assert subscription_captured["effort"] is None


def test_explicit_error_code_survives_event_run_and_linked_message(stores):
    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    _seed_run(run_store, thread_store, thread_id="explicit", run_id="explicit-run")

    async def stream_factory(**kwargs):
        yield AgentEvent(
            EventType.error,
            {"error": "model declined", "code": "model_refusal"},
        )

    asyncio.run(
        execute_research_run(
            run_id="explicit-run",
            run_store=run_store,
            thread_store=thread_store,
            dal=object(),
            history=[],
            stream_factory=stream_factory,
        )
    )

    run = run_store.get_run("explicit-run")
    terminal = run_store.list_events("explicit-run")[-1]
    message = thread_store.list_messages("explicit")[-1]
    assert run is not None and run.error_code == "model_refusal"
    assert terminal.data["code"] == "model_refusal"
    assert (message.run_id, message.error_code) == ("explicit-run", "model_refusal")


def test_unknown_exception_is_typed_redacted_and_bounded(stores):
    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    _seed_run(run_store, thread_store, thread_id="unknown", run_id="unknown-run")
    secret = "AbCdEf1234567890"
    raw = f"provider exploded access_token={secret} " + ("detail " * 120)

    async def stream_factory(**kwargs):
        raise RuntimeError(raw)
        yield  # pragma: no cover - async-generator shape

    asyncio.run(
        execute_research_run(
            run_id="unknown-run",
            run_store=run_store,
            thread_store=thread_store,
            dal=object(),
            history=[],
            stream_factory=stream_factory,
        )
    )

    run = run_store.get_run("unknown-run")
    terminal = run_store.list_events("unknown-run")[-1]
    message = thread_store.list_messages("unknown")[-1]
    assert run is not None and run.error_code == "provider_call_failed"
    assert secret not in (run.error or "") and "[REDACTED]" in (run.error or "")
    assert len(run.error or "") <= 500
    assert terminal.data == {
        "error": run.error,
        "code": "provider_call_failed",
    }
    assert message.content == run.error
    assert message.error_code == "provider_call_failed"


def test_timeout_causes_and_owned_event_shapes_are_model_timeout(stores):
    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    cases = [
        ("api-openai", "APITimeoutError: request deadline exceeded", "model_timeout"),
        ("api-anthropic", "TimeoutError: request deadline exceeded", "model_timeout"),
        ("chatgpt", "ChatGPT OAuth driver timed out after 45s", "model_timeout"),
        ("claude-sdk", "claude agent-sdk timed out after 45s", "model_timeout"),
        ("claude-cli", "claude -p timed out after 45s", "model_timeout"),
        (
            "api-openai-near-miss",
            "wrapped APITimeoutError: request deadline exceeded",
            "provider_call_failed",
        ),
        (
            "api-anthropic-near-miss",
            "wrapped TimeoutError: request deadline exceeded",
            "provider_call_failed",
        ),
        (
            "chatgpt-near-miss",
            "ChatGPT OAuth driver timed out after 45s trailing",
            "provider_call_failed",
        ),
        (
            "claude-sdk-near-miss",
            "claude agent-sdk timed out after 45s trailing",
            "provider_call_failed",
        ),
        (
            "claude-cli-near-miss",
            "claude -p timed out after 45s trailing",
            "provider_call_failed",
        ),
    ]
    for suffix, detail, expected_code in cases:
        thread_id = f"timeout-{suffix}"
        run_id = f"run-{suffix}"
        _seed_run(run_store, thread_store, thread_id=thread_id, run_id=run_id)

        async def event_stream(_detail=detail, **kwargs):
            yield AgentEvent(EventType.error, {"error": _detail})

        asyncio.run(
            execute_research_run(
                run_id=run_id,
                run_store=run_store,
                thread_store=thread_store,
                dal=object(),
                history=[],
                stream_factory=event_stream,
            )
        )
        assert run_store.get_run(run_id).error_code == expected_code

    _seed_run(run_store, thread_store, thread_id="timeout-cause", run_id="run-cause")

    async def caused_timeout(**kwargs):
        try:
            raise asyncio.TimeoutError("provider deadline")
        except asyncio.TimeoutError as cause:
            raise RuntimeError("outer provider failure") from cause
        yield  # pragma: no cover - async-generator shape

    asyncio.run(
        execute_research_run(
            run_id="run-cause",
            run_store=run_store,
            thread_store=thread_store,
            dal=object(),
            history=[],
            stream_factory=caused_timeout,
        )
    )
    assert run_store.get_run("run-cause").error_code == "model_timeout"

    provider_timeout_cases = [
        ("openai", "openai._exceptions", "model_timeout"),
        ("anthropic", "anthropic._exceptions", "model_timeout"),
        ("unrelated", "unrelated._exceptions", "provider_call_failed"),
    ]
    for suffix, module, expected_code in provider_timeout_cases:
        timeout_type = type(
            "APITimeoutError",
            (Exception,),
            {"__module__": module},
        )
        thread_id = f"timeout-cause-{suffix}"
        run_id = f"run-cause-{suffix}"
        _seed_run(run_store, thread_store, thread_id=thread_id, run_id=run_id)

        async def caused_provider_timeout(_timeout_type=timeout_type, **kwargs):
            try:
                raise _timeout_type("provider deadline")
            except Exception as cause:
                raise RuntimeError("outer provider failure") from cause
            yield  # pragma: no cover - async-generator shape

        asyncio.run(
            execute_research_run(
                run_id=run_id,
                run_store=run_store,
                thread_store=thread_store,
                dal=object(),
                history=[],
                stream_factory=caused_provider_timeout,
            )
        )
        assert run_store.get_run(run_id).error_code == expected_code


def test_max_turn_shapes_are_typed_without_fuzzy_near_misses(stores):
    from src.research_run_manager import execute_research_run
    from src.research_threads import MAX_TOOL_CALLS_SENTINEL

    run_store, thread_store = stores
    cases = [
        (
            "anthropic",
            EventType.done,
            {"answer": MAX_TOOL_CALLS_SENTINEL, "token_usage": {"total_tokens": 17}},
            "tool_limit_reached",
        ),
        (
            "openai",
            EventType.error,
            {"error": "MaxTurnsExceeded: maximum turns (8) exceeded", "token_usage": {"total_tokens": 18}},
            "tool_limit_reached",
        ),
        (
            "chatgpt",
            EventType.error,
            {"error": "Reached maximum number of turns (8)", "token_usage": {"total_tokens": 19}},
            "tool_limit_reached",
        ),
        (
            "anthropic-near-miss",
            EventType.done,
            {
                "answer": f"{MAX_TOOL_CALLS_SENTINEL} trailing",
                "token_usage": {"total_tokens": 20},
            },
            None,
        ),
        (
            "openai-near-miss",
            EventType.error,
            {
                "error": "wrapped MaxTurnsExceeded: maximum turns (8) exceeded",
                "token_usage": {"total_tokens": 21},
            },
            "provider_call_failed",
        ),
        (
            "tool-timeout-near-miss",
            EventType.error,
            {"error": "tool 'x' timed out after 8s", "token_usage": {"total_tokens": 22}},
            "provider_call_failed",
        ),
        (
            "chatgpt-near-miss",
            EventType.error,
            {"error": "Reached maximum number of turns (8) trailing", "token_usage": {"total_tokens": 23}},
            "provider_call_failed",
        ),
    ]
    for suffix, terminal_type, terminal_data, expected_code in cases:
        thread_id = f"limit-{suffix}"
        run_id = f"limit-run-{suffix}"
        _seed_run(run_store, thread_store, thread_id=thread_id, run_id=run_id)

        async def stream_factory(
            _terminal_type=terminal_type,
            _terminal_data=terminal_data,
            **kwargs,
        ):
            yield AgentEvent(
                EventType.tool_start,
                {"tool": "get_news", "input": {"ticker": "MU"}},
            )
            yield AgentEvent(
                EventType.tool_end,
                {"tool": "get_news", "summary": "partial", "chars": 7},
            )
            yield AgentEvent(_terminal_type, dict(_terminal_data))

        asyncio.run(
            execute_research_run(
                run_id=run_id,
                run_store=run_store,
                thread_store=thread_store,
                dal=object(),
                history=[],
                stream_factory=stream_factory,
            )
        )

        run = run_store.get_run(run_id)
        terminal = run_store.list_events(run_id)[-1]
        message = thread_store.list_messages(thread_id)[-1]
        if expected_code is None:
            assert run.status == "succeeded"
            assert run.error_code is None
            assert terminal.type == "done"
            assert terminal.data["answer"] == terminal_data["answer"]
            assert "code" not in terminal.data
            assert message.is_error is False
            assert (message.run_id, message.error_code) == (run_id, None)
            assert message.content == terminal_data["answer"]
            assert message.tool_calls == [
                {
                    "name": "get_news",
                    "input": {"ticker": "MU"},
                    "result_preview": "partial",
                }
            ]
            assert message.token_usage == terminal_data["token_usage"]
            assert run.token_usage == terminal_data["token_usage"]
            continue
        assert run.status == "failed"
        assert run.error_code == expected_code
        assert terminal.type == "error"
        assert terminal.data["code"] == expected_code
        assert message.is_error is True
        assert (message.run_id, message.error_code) == (run_id, expected_code)
        assert message.tool_calls == [
            {"name": "get_news", "input": {"ticker": "MU"}, "result_preview": "partial"}
        ]
        assert message.token_usage == terminal_data["token_usage"]
        assert run.token_usage == terminal_data["token_usage"]


def test_cancel_fallback_atomically_persists_typed_terminal_before_next_run(
    stores, monkeypatch
):
    run_store, thread_store = stores
    _seed_run(run_store, thread_store, thread_id="cancel-race", run_id="cancel-old")
    second_run_store = ResearchRunStore(run_store.db_path)
    second_thread_store = ResearchThreadStore(thread_store.db_path)
    paused, release = _pause_terminal_message(
        monkeypatch, thread_store, error_code="run_cancelled"
    )
    scheduled = {}
    monkeypatch.setattr(r, "cancel_research_run", lambda run_id: False)
    monkeypatch.setattr(r, "_resolve_auth_metadata", lambda provider: ("api_key", None))
    monkeypatch.setattr(r, "schedule_research_run", lambda **kwargs: scheduled.update(kwargs))
    request = r.ResearchRunCreate(
        thread_id="cancel-race",
        question="new question",
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        cancel_future = executor.submit(
            r.cancel_research_run_route,
            "cancel-old",
            run_store=run_store,
            thread_store=thread_store,
        )
        assert paused.wait(timeout=2)
        create_future = executor.submit(
            lambda: asyncio.run(
                r.create_research_run(
                    request,
                    dal=object(),
                    thread_store=second_thread_store,
                    run_store=second_run_store,
                )
            )
        )
        try:
            with pytest.raises(FutureTimeoutError):
                create_future.result(timeout=0.1)
        finally:
            release.set()
        cancelled = cancel_future.result(timeout=5)
        created = create_future.result(timeout=5)

    assert cancelled["run"]["error_code"] == "run_cancelled"
    assert created["run"]["status"] == "queued"
    assert scheduled["history"] == [
        {"role": "user", "content": "question cancel-race"},
    ]
    messages = second_thread_store.list_messages("cancel-race")
    assert [message.content for message in messages] == [
        "question cancel-race",
        "research run cancelled",
        "new question",
    ]
    assert (messages[1].run_id, messages[1].error_code) == (
        "cancel-old",
        "run_cancelled",
    )


def test_restart_reconciliation_atomically_persists_typed_terminal_before_next_run(
    stores, monkeypatch
):
    run_store, thread_store = stores
    _seed_run(run_store, thread_store, thread_id="restart-race", run_id="restart-old")
    second_run_store = ResearchRunStore(run_store.db_path)
    second_thread_store = ResearchThreadStore(thread_store.db_path)
    paused, release = _pause_terminal_message(
        monkeypatch, thread_store, error_code="run_interrupted"
    )
    scheduled = {}
    monkeypatch.setattr(r, "_resolve_auth_metadata", lambda provider: ("api_key", None))
    monkeypatch.setattr(r, "schedule_research_run", lambda **kwargs: scheduled.update(kwargs))
    request = r.ResearchRunCreate(
        thread_id="restart-race",
        question="new question",
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        reconcile_future = executor.submit(
            run_store.reconcile_interrupted,
            thread_store=thread_store,
        )
        assert paused.wait(timeout=2)
        create_future = executor.submit(
            lambda: asyncio.run(
                r.create_research_run(
                    request,
                    dal=object(),
                    thread_store=second_thread_store,
                    run_store=second_run_store,
                )
            )
        )
        try:
            with pytest.raises(FutureTimeoutError):
                create_future.result(timeout=0.1)
        finally:
            release.set()
        changed = reconcile_future.result(timeout=5)
        created = create_future.result(timeout=5)

    assert changed == ["restart-old"]
    assert created["run"]["status"] == "queued"
    assert scheduled["history"] == [
        {"role": "user", "content": "question restart-race"},
    ]
    messages = second_thread_store.list_messages("restart-race")
    assert [message.content for message in messages] == [
        "question restart-race",
        "research run interrupted by sidecar restart",
        "new question",
    ]
    assert (messages[1].run_id, messages[1].error_code) == (
        "restart-old",
        "run_interrupted",
    )


# ─── Track A: personalization on server-owned runs ───────────────────────────


def _tracka_profile(tmp_path, monkeypatch, *, enabled):
    from src.investor_profile import InvestorProfileStore

    pstore = InvestorProfileStore(tmp_path / "investor_profile.db")
    if enabled:
        pstore.save({"enabled": True, "risk_appetite": 9, "risk_capacity": 3,
                     "default_stance": "complementary"})
    monkeypatch.setattr("src.api.dependencies.get_investor_profile_store", lambda: pstore)
    return pstore


def test_create_run_stores_stance_and_rejects_invalid(stores, tmp_path, monkeypatch):
    import asyncio

    from fastapi import HTTPException

    run_store, thread_store = stores
    _tracka_profile(tmp_path, monkeypatch, enabled=True)
    monkeypatch.setattr(r, "schedule_research_run", lambda **k: None)
    monkeypatch.setattr(r, "resolve_research_route", lambda provider: ("gpt-5.4-mini", "low"))
    monkeypatch.setattr(r, "_resolve_auth_metadata", lambda provider: ("api_key", None))

    body = r.ResearchRunCreate(
        question="q", provider="openai", assistant_stance="strict_risk_control"
    )
    out = asyncio.run(
        r.create_research_run(body, dal=object(), thread_store=thread_store, run_store=run_store)
    )
    assert out["run"]["assistant_stance"] == "strict_risk_control"
    assert run_store.get_run(out["run"]["id"]).assistant_stance == "strict_risk_control"

    bad = r.ResearchRunCreate(question="q", provider="openai", assistant_stance="yolo")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            r.create_research_run(bad, dal=object(), thread_store=thread_store, run_store=run_store)
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "invalid_assistant_stance", "field": "assistant_stance"}


def test_execute_run_injects_context_and_persists_trace(stores, tmp_path, monkeypatch):
    import asyncio

    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    _tracka_profile(tmp_path, monkeypatch, enabled=True)
    thread_store.ensure_thread(id="t1", title="q")
    thread_store.append_message(thread_id="t1", role="user", content="q")
    run_store.create_run(
        id="rp", thread_id="t1", question="q", ticker=None,
        provider="anthropic", model="m", effort=None,
        auth_mode="api_key", credential_id=None,
        assistant_stance="strict_risk_control",
    )
    captured = {}

    async def stream_factory(**kwargs):
        captured.update(kwargs)
        yield AgentEvent(EventType.done, {
            "answer": "a", "provider": "anthropic", "model": "m",
            "tools_used": [], "token_usage": {},
        })

    asyncio.run(execute_research_run(
        run_id="rp", run_store=run_store, thread_store=thread_store,
        dal=object(), history=[], stream_factory=stream_factory,
    ))
    ctx = captured.get("personalization_context", "")
    assert "[Assistant Stance]" in ctx and "strict_risk_control" in ctx
    done = [e for e in run_store.list_events("rp") if e.type == "done"][-1]
    assert done.data["personalization"]["assistant_stance"] == "strict_risk_control"
    last = thread_store.list_messages("t1")[-1]
    assert last.personalization["assistant_stance"] == "strict_risk_control"
    assert last.personalization["profile_active"] is True


def test_execute_run_off_omits_personalization_kwarg(stores, tmp_path, monkeypatch):
    import asyncio

    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    _tracka_profile(tmp_path, monkeypatch, enabled=False)
    thread_store.ensure_thread(id="t1", title="q")
    thread_store.append_message(thread_id="t1", role="user", content="q")
    run_store.create_run(
        id="ro", thread_id="t1", question="q", ticker=None,
        provider="anthropic", model="m", effort=None,
        auth_mode="api_key", credential_id=None,
    )

    async def strict_factory(*, provider, question, model, effort, dal, history):
        # NO **kwargs: an unexpected personalization kwarg = TypeError.
        yield AgentEvent(EventType.done, {
            "answer": "a", "provider": provider, "model": model,
            "tools_used": [], "token_usage": {},
        })

    asyncio.run(execute_research_run(
        run_id="ro", run_store=run_store, thread_store=thread_store,
        dal=object(), history=[], stream_factory=strict_factory,
    ))
    assert run_store.get_run("ro").status == "succeeded"
    last = thread_store.list_messages("t1")[-1]
    assert last.personalization is None or last.personalization["profile_active"] is False


def test_cancelled_run_persists_personalization_trace(stores, tmp_path, monkeypatch):
    import asyncio

    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    _tracka_profile(tmp_path, monkeypatch, enabled=True)
    thread_store.ensure_thread(id="t1", title="q")
    thread_store.append_message(thread_id="t1", role="user", content="q")
    run_store.create_run(
        id="rc", thread_id="t1", question="q", ticker=None,
        provider="anthropic", model="m", effort=None,
        auth_mode="api_key", credential_id=None,
        assistant_stance="complementary",
    )

    async def cancelling_factory(**kwargs):
        raise asyncio.CancelledError()
        yield  # pragma: no cover — makes this an async generator

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(execute_research_run(
            run_id="rc", run_store=run_store, thread_store=thread_store,
            dal=object(), history=[], stream_factory=cancelling_factory,
        ))
    last = thread_store.list_messages("t1")[-1]
    assert last.is_error is True
    assert last.personalization["assistant_stance"] == "complementary"
    assert last.personalization["profile_active"] is True
