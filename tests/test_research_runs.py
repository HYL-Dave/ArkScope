from __future__ import annotations

import asyncio

import pytest

from src.api.routes import research as r
from src.auth_drivers.live_resolver import LiveAuthResolution
from src.agents.shared.events import AgentEvent, EventType
from src.research_runs import ResearchRunStore
from src.research_threads import ResearchThreadStore


@pytest.fixture()
def stores(tmp_path):
    db = tmp_path / "profile_state.db"
    return ResearchRunStore(db), ResearchThreadStore(db)


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

    res = r.cancel_research_run_route("r1", run_store=run_store)

    assert res["run"]["status"] == "cancelled"
    assert run_store.get_run("r1").status == "cancelled"
    assert run_store.list_events("r1")[-1].type == "error"


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
