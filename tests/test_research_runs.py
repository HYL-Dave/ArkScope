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

    thread_store.ensure_thread(id="t2", title="q")
    run_store.create_run(
        id="r2",
        thread_id="t2",
        question="q",
        ticker=None,
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
        auth_mode="api_key",
        credential_id=None,
    )
    trace = {
        "profile_active": True,
        "assistant_stance": "complementary",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
        "context_snapshot": "exact context",
    }
    run_store.mark_running_with_personalization("r2", trace)

    assert run_store.reconcile_interrupted() == ["r2"]
    assert run_store.list_events("r2")[-1].data["personalization"] == trace

    malformed_traces = {
        "malformed-json": '{"profile_active":',
        "non-dict-json": '["profile_active", true]',
    }
    for run_id in malformed_traces:
        thread_store.ensure_thread(id=run_id, title="q")
        run_store.create_run(
            id=run_id,
            thread_id=run_id,
            question="q",
            ticker=None,
            provider="openai",
            model="gpt-5.4-mini",
            effort="low",
            auth_mode="api_key",
            credential_id=None,
        )
    with sqlite3.connect(run_store.db_path) as conn:
        conn.executemany(
            "UPDATE research_runs SET personalization_json = ? WHERE id = ?",
            [(value, run_id) for run_id, value in malformed_traces.items()],
        )
        raw_before = dict(
            conn.execute(
                "SELECT id, CAST(personalization_json AS BLOB) "
                "FROM research_runs WHERE id IN (?, ?)",
                tuple(malformed_traces),
            ).fetchall()
        )

    for run_id in malformed_traces:
        assert run_store.get_run(run_id).personalization is None
    assert set(run_store.reconcile_interrupted(thread_store=thread_store)) == set(
        malformed_traces
    )
    for run_id in malformed_traces:
        assert run_store.get_run(run_id).status == "interrupted"
        assert "personalization" not in run_store.list_events(run_id)[-1].data
    with sqlite3.connect(run_store.db_path) as conn:
        raw_after = dict(
            conn.execute(
                "SELECT id, CAST(personalization_json AS BLOB) "
                "FROM research_runs WHERE id IN (?, ?)",
                tuple(malformed_traces),
            ).fetchall()
        )
    assert raw_after == raw_before == {
        run_id: value.encode() for run_id, value in malformed_traces.items()
    }


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
    run_store.append_event(
        "r1",
        "done",
        {
            "answer": "ok",
            "personalization": {
                "profile_active": True,
                "assistant_stance": "complementary",
                "skill_mode": "off",
                "suggested_skills": [],
                "applied_skills": [],
                "context_snapshot": "closed context",
                "freeform_notes": "private note",
                "credential_id": "nested-secret",
            },
        },
    )

    res = r.list_research_run_events("r1", after=1, run_store=run_store)

    assert res["run"]["id"] == "r1"
    assert [(e["seq"], e["type"]) for e in res["events"]] == [(2, "done")]
    assert res["events"][0]["data"] == {
        "answer": "ok",
        "personalization": {
            "profile_active": True,
            "assistant_stance": "complementary",
            "skill_mode": "off",
            "suggested_skills": [],
            "applied_skills": [],
            "context_snapshot": "closed context",
        },
    }
    assert "private note" not in str(res["events"])
    assert "nested-secret" not in str(res["events"])


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
        "personalization": {
            "profile_active": False,
            "assistant_stance": "off",
            "skill_mode": "off",
            "suggested_skills": [],
            "applied_skills": [],
            "context_snapshot": "",
        },
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


def test_research_run_persists_prompt_assembly_trace_and_exact_context_before_stream(
    stores, tmp_path, monkeypatch
):
    from src.api import personalization as personalization_api
    from src.investor_profile import build_personalization_context, personalization_trace
    from src.research_run_manager import execute_research_run

    run_store, thread_store = stores
    profile_store = _tracka_profile(tmp_path, monkeypatch, enabled=True)
    profile_store.save(
        {
            "preferred_edge": ["valuation", "earnings revisions"],
            "behavioral_flags": ["FOMO"],
        }
    )
    thread_store.ensure_thread(id="snapshot-active", title="q")
    thread_store.append_message(
        thread_id="snapshot-active", role="user", content="q"
    )
    run_store.create_run(
        id="snapshot-active-run",
        thread_id="snapshot-active",
        question="q",
        ticker=None,
        provider="anthropic",
        model="m",
        effort="high",
        auth_mode="api_key",
        credential_id="local:private",
        assistant_stance="strict_risk_control",
    )
    profile = profile_store.get()
    expected_context = build_personalization_context(
        profile, override="strict_risk_control"
    )
    expected_trace = {
        **personalization_trace(profile, override="strict_risk_control"),
        "context_snapshot": expected_context,
    }
    original_resolve = personalization_api.resolve_personalization
    resolution_statuses = []

    def observing_resolve(assistant_stance):
        resolution_statuses.append(run_store.get_run("snapshot-active-run").status)
        return original_resolve(assistant_stance)

    monkeypatch.setattr(
        personalization_api, "resolve_personalization", observing_resolve
    )
    original_claim = run_store.mark_running_with_personalization
    before_claim = threading.Barrier(2)
    after_claim = threading.Barrier(2)
    claim_results = []
    claim_lock = threading.Lock()

    def coordinated_claim(run_id, personalization):
        before_claim.wait(timeout=5)
        claimed = original_claim(run_id, personalization)
        with claim_lock:
            claim_results.append(claimed)
        after_claim.wait(timeout=5)
        return claimed

    monkeypatch.setattr(
        run_store, "mark_running_with_personalization", coordinated_claim
    )
    provider_calls = []
    provider_lock = threading.Lock()

    async def stream_factory(**kwargs):
        running = run_store.get_run("snapshot-active-run")
        with provider_lock:
            provider_calls.append(
                {
                    "status": running.status,
                    "started_at": running.started_at,
                    "personalization": getattr(running, "personalization", None),
                    "kwargs": kwargs,
                }
            )
        await asyncio.sleep(0.05)
        profile_store.save({"enabled": False})
        yield AgentEvent(
            EventType.done,
            {
                "answer": "a",
                "provider": "anthropic",
                "model": "m",
                "tools_used": [],
                "token_usage": {},
            },
        )

    def execute_worker():
        asyncio.run(
            execute_research_run(
                run_id="snapshot-active-run",
                run_store=run_store,
                thread_store=thread_store,
                dal=object(),
                history=[],
                stream_factory=stream_factory,
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(execute_worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=5)

    run_store.mark_terminal(
        "snapshot-active-run",
        "failed",
        error="late worker must not overwrite terminal state",
        error_code="provider_call_failed",
    )

    assert resolution_statuses == ["queued", "queued"]
    assert claim_results.count(True) == 1
    assert claim_results.count(False) == 1
    assert len(provider_calls) == 1
    provider_call = provider_calls[0]
    assert provider_call["status"] == "running"
    assert provider_call["started_at"] is not None
    assert provider_call["personalization"] == expected_trace
    assert provider_call["kwargs"]["personalization_context"] == expected_context
    persisted = run_store.get_run("snapshot-active-run")
    assert persisted.status == "succeeded"
    assert persisted.error is None
    assert persisted.personalization == expected_trace
    done = [
        event
        for event in run_store.list_events("snapshot-active-run")
        if event.type == "done"
    ][-1]
    assert done.data["personalization"] == expected_trace
    assert [event.type for event in run_store.list_events("snapshot-active-run")] == [
        "done"
    ]
    messages = thread_store.list_messages("snapshot-active")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[-1].personalization == expected_trace
    assert r.get_research_run(
        "snapshot-active-run", run_store=run_store
    )["run"]["personalization"] == expected_trace
    assert set(expected_trace) == {
        "profile_active",
        "assistant_stance",
        "skill_mode",
        "suggested_skills",
        "applied_skills",
        "context_snapshot",
    }


def test_research_run_context_snapshot_distinguishes_legacy_null_from_disabled_empty(
    tmp_path, monkeypatch
):
    from src.research_run_manager import execute_research_run

    db = tmp_path / "legacy_research.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE research_threads (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                ticker TEXT,
                provider TEXT,
                model TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT
            );
            CREATE TABLE research_runs (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL REFERENCES research_threads(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                question TEXT NOT NULL,
                ticker TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                effort TEXT,
                assistant_stance TEXT,
                auth_mode TEXT,
                credential_id TEXT,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                error_code TEXT,
                token_usage_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO research_threads
                (id, title, created_at, updated_at)
            VALUES
                ('legacy-thread', 'Legacy', '2026-07-01T00:00:00+00:00',
                 '2026-07-01T00:00:00+00:00');
            INSERT INTO research_runs
                (id, thread_id, status, question, provider, model,
                 started_at, completed_at, created_at, updated_at)
            VALUES
                ('legacy-run', 'legacy-thread', 'succeeded', 'old q', 'openai', 'old-model',
                 '2026-07-01T00:01:00+00:00', '2026-07-01T00:02:00+00:00',
                 '2026-07-01T00:00:00+00:00', '2026-07-01T00:02:00+00:00');
            """
        )

    run_store = ResearchRunStore(db)
    thread_store = ResearchThreadStore(db)
    legacy = run_store.get_run("legacy-run")
    assert legacy is not None
    assert legacy.personalization is None

    thread_store.ensure_thread(id="queued-thread", title="Queued")
    queued = run_store.create_run(
        id="queued-run",
        thread_id="queued-thread",
        question="queued",
        ticker=None,
        provider="anthropic",
        model="m",
        effort=None,
        auth_mode="api_key",
        credential_id=None,
    )
    assert queued.personalization is None
    assert r.get_research_run("queued-run", run_store=run_store)["run"][
        "personalization"
    ] is None

    _tracka_profile(tmp_path, monkeypatch, enabled=False)
    expected_off = {
        "profile_active": False,
        "assistant_stance": "off",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
        "context_snapshot": "",
    }

    async def execute_off(thread_id, run_id):
        thread_store.ensure_thread(id=thread_id, title=thread_id)
        thread_store.append_message(thread_id=thread_id, role="user", content="q")
        run_store.create_run(
            id=run_id,
            thread_id=thread_id,
            question="q",
            ticker=None,
            provider="anthropic",
            model="m",
            effort=None,
            auth_mode="api_key",
            credential_id=None,
        )
        observed = []

        async def strict_factory(*, provider, question, model, effort, dal, history):
            observed.append(run_store.get_run(run_id).personalization)
            yield AgentEvent(
                EventType.done,
                {
                    "answer": "a",
                    "provider": provider,
                    "model": model,
                    "tools_used": [],
                    "token_usage": {},
                },
            )

        await execute_research_run(
            run_id=run_id,
            run_store=run_store,
            thread_store=thread_store,
            dal=object(),
            history=[],
            stream_factory=strict_factory,
        )
        return observed

    disabled_observed = asyncio.run(execute_off("disabled-thread", "disabled-run"))
    assert disabled_observed == [expected_off]
    assert run_store.get_run("disabled-run").personalization == expected_off
    assert run_store.list_events("disabled-run")[-1].data["personalization"] == expected_off
    assert thread_store.list_messages("disabled-thread")[-1].personalization == expected_off

    monkeypatch.setattr(
        "src.api.personalization.resolve_personalization",
        lambda _stance: (_ for _ in ()).throw(RuntimeError("profile unavailable")),
    )
    fallback_observed = asyncio.run(execute_off("fallback-thread", "fallback-run"))
    assert fallback_observed == [expected_off]
    assert run_store.get_run("fallback-run").personalization == expected_off
    assert run_store.list_events("fallback-run")[-1].data["personalization"] == expected_off
    assert thread_store.list_messages("fallback-thread")[-1].personalization == expected_off
    assert run_store.get_run("legacy-run").personalization is None
    assert run_store.get_run("queued-run").personalization is None

    with sqlite3.connect(db) as conn:
        rows = dict(
            conn.execute(
                "SELECT id, personalization_json FROM research_runs "
                "WHERE id IN ('legacy-run', 'queued-run', 'disabled-run', 'fallback-run')"
            ).fetchall()
        )
    assert rows["legacy-run"] is None
    assert rows["queued-run"] is None
    assert rows["disabled-run"] is not None
    assert rows["fallback-run"] is not None


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
    persisted = run_store.get_run("rc").personalization
    assert persisted["context_snapshot"]
    assert last.personalization == persisted
    assert run_store.list_events("rc")[-1].data["personalization"] == persisted
