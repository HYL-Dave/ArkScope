"""C-2b backend: research persistence helpers + GET routes.

Handler-direct (NOT TestClient — see feedback_route_unit_tests): the GET route
fns are called directly with a real temp-file ResearchThreadStore. Covers the 5
acceptance criteria: server-side ticker compose (#2 — raw question persisted),
server-side tool_calls accumulation from tool_start/tool_end (#3), best-effort
persistence (#4 — store errors never propagate), thread_id validation (#5).
"""

from __future__ import annotations

import pytest

from src.api.routes import query as q
from src.api.routes import research as r
from src.research_threads import ResearchThreadStore, valid_thread_id


@pytest.fixture()
def store(tmp_path):
    return ResearchThreadStore(tmp_path / "profile_state.db")


# --- #2: server composes the agent prompt; the RAW question is what's stored ---
def test_compose_agent_question_with_ticker():
    assert q._compose_agent_question("最近焦點？", "NVDA") == "針對 NVDA：最近焦點？"


def test_compose_agent_question_without_ticker():
    assert q._compose_agent_question("hi", None) == "hi"
    assert q._compose_agent_question("hi", "") == "hi"
    assert q._compose_agent_question("hi", "   ") == "hi"


# --- #5: thread_id validation (non-empty, length cap) ---
def test_valid_thread_id():
    assert valid_thread_id("abc-123") is True
    assert valid_thread_id("") is False
    assert valid_thread_id("   ") is False
    assert valid_thread_id(None) is False
    assert valid_thread_id("x" * 201) is False
    assert valid_thread_id("x" * 200) is True


# --- #3: tool_calls accumulated server-side from tool_start/tool_end events ---
def test_accumulate_anthropic_pairs():
    events = [
        ("tool_start", {"tool": "get_sa_feed", "input": {"ticker": "NVDA"}}),
        ("tool_end", {"tool": "get_sa_feed", "summary": "5 articles", "chars": 100}),
    ]
    assert q.accumulate_tool_calls(events) == [
        {"name": "get_sa_feed", "input": {"ticker": "NVDA"}, "result_preview": "5 articles"}
    ]


def test_accumulate_openai_name_only_no_tool_start():
    events = [("tool_end", {"tool": "get_sa_feed"}), ("tool_end", {"tool": "get_sa_comment_focus"})]
    assert q.accumulate_tool_calls(events) == [
        {"name": "get_sa_feed", "input": None, "result_preview": None},
        {"name": "get_sa_comment_focus", "input": None, "result_preview": None},
    ]


def test_accumulate_duplicate_tool_two_distinct_rows():
    events = [
        ("tool_start", {"tool": "f", "input": {"a": 1}}), ("tool_end", {"tool": "f", "summary": "r1"}),
        ("tool_start", {"tool": "f", "input": {"a": 2}}), ("tool_end", {"tool": "f", "summary": "r2"}),
    ]
    out = q.accumulate_tool_calls(events)
    assert [c["input"] for c in out] == [{"a": 1}, {"a": 2}]
    assert [c["result_preview"] for c in out] == ["r1", "r2"]


# --- persistence helpers (raw question; best-effort) ---
# tool_calls are accumulated INSIDE the helper from the raw (type, data) events
# (`collected`), so the accumulation runs under the best-effort guard (SF1).
def test_persist_user_then_assistant_roundtrip(store):
    q._persist_user_turn(store, thread_id="t1", question="最近焦點？", ticker="NVDA", provider="anthropic", model="m", title="最近焦點？")
    q._persist_assistant_turn(
        store, thread_id="t1",
        done_data={"answer": "ans", "provider": "anthropic", "model": "m", "tools_used": ["get_sa_feed"], "token_usage": {"total_tokens": 5, "turn_count": 1}},
        collected=[("tool_start", {"tool": "get_sa_feed", "input": {"ticker": "NVDA"}}), ("tool_end", {"tool": "get_sa_feed", "summary": "5"})],
        elapsed=2.0,
    )
    msgs = store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == "最近焦點？" and msgs[0].tickers == ["NVDA"]  # RAW question, NOT prefixed
    assert msgs[1].tool_calls == [{"name": "get_sa_feed", "input": {"ticker": "NVDA"}, "result_preview": "5"}]
    assert msgs[1].tools_used == ["get_sa_feed"] and msgs[1].elapsed_seconds == 2.0
    assert msgs[1].is_error is False
    assert store.get_thread("t1").title == "最近焦點？"


def test_persist_error_turn_marks_is_error_and_preserves_partial_trace(store):
    # MUST-FIX 2: a non-`done` terminal (agent error) persists an assistant turn
    # so reload doesn't show a dangling user question with no reply.
    q._persist_user_turn(store, thread_id="t1", question="q", ticker=None, provider="anthropic", model="m", title="q")
    q._persist_error_turn(
        store, thread_id="t1", content="RuntimeError: db down",
        collected=[("tool_start", {"tool": "get_sa_feed", "input": {"x": 1}}), ("tool_end", {"tool": "get_sa_feed", "summary": "r"})],
        provider="anthropic", model="m", elapsed=1.5,
    )
    msgs = store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]
    a = msgs[1]
    assert a.is_error is True and a.content == "RuntimeError: db down"
    assert a.tool_calls == [{"name": "get_sa_feed", "input": {"x": 1}, "result_preview": "r"}]  # partial trace kept


def test_persist_is_best_effort_swallows_store_errors():
    class Broken:
        def ensure_thread(self, **k):
            raise RuntimeError("db down")

        def append_message(self, **k):
            raise RuntimeError("db down")

    # Must NOT raise — a persistence failure can never break the SSE answer (#4).
    q._persist_user_turn(Broken(), thread_id="t1", question="q", ticker=None, provider="a", model="m", title="q")
    q._persist_assistant_turn(Broken(), thread_id="t1", done_data={"answer": "a"}, collected=[], elapsed=1.0)
    q._persist_error_turn(Broken(), thread_id="t1", content="boom", collected=[], provider="a", model="m", elapsed=1.0)


# --- GET routes (handler-direct) ---
def test_list_threads_route_orders_desc(store):
    store.ensure_thread(id="t1", title="alpha", now="2026-06-14T00:00:00+00:00")
    store.ensure_thread(id="t2", title="beta", now="2026-06-14T00:01:00+00:00")
    res = r.list_research_threads(limit=50, store=store)
    assert [t["id"] for t in res["threads"]] == ["t2", "t1"]  # updated_at desc
    assert res["threads"][0]["title"] == "beta"


def test_list_messages_route_roundtrip(store):
    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="hi", tickers=["NVDA"])
    res = r.list_research_messages(thread_id="t1", store=store)
    assert res["thread_id"] == "t1" and len(res["messages"]) == 1
    assert res["messages"][0]["role"] == "user" and res["messages"][0]["tickers"] == ["NVDA"]
    assert res["messages"][0]["is_error"] is False  # serialized for the client mapper


def test_list_messages_404_for_missing(store):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        r.list_research_messages(thread_id="nope", store=store)
    assert ei.value.status_code == 404


def test_list_messages_422_for_blank_thread_id(store):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        r.list_research_messages(thread_id="   ", store=store)
    assert ei.value.status_code == 422


def test_delete_thread_route_removes_thread_and_messages(store):
    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="hi")

    res = r.delete_research_thread(thread_id="t1", store=store)

    assert res == {"thread_id": "t1", "deleted": True}
    assert store.get_thread("t1") is None
    assert store.list_messages("t1") == []


def test_delete_thread_route_is_idempotent_for_missing(store):
    res = r.delete_research_thread(thread_id="nope", store=store)
    assert res == {"thread_id": "nope", "deleted": False}


def test_delete_thread_route_422_for_blank_thread_id(store):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        r.delete_research_thread(thread_id="   ", store=store)
    assert ei.value.status_code == 422


@pytest.mark.parametrize("provider,module", [
    ("anthropic", "src.agents.anthropic_agent.agent"),
    ("openai", "src.agents.openai_agent.agent"),
])
def test_query_stream_threads_history_into_provider(store, monkeypatch, provider, module):
    """C-2c: /query/stream must fetch prior thread turns and pass them as
    `history` to the provider's run_query_stream — fetched BEFORE persisting this
    turn's user message (so the current turn is not duplicated). Mocks the
    provider (cheap; no real agent)."""
    import asyncio

    store.ensure_thread(id="t1", title="prev")
    store.append_message(thread_id="t1", role="user", content="prev q")
    store.append_message(thread_id="t1", role="assistant", content="prev a")

    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured["question"] = question
        captured["history"] = history
        captured["model"] = model  # B1: resolved from the ai_research route when request.model is None
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "ok", "tools_used": [], "provider": provider, "model": "m", "token_usage": {}})

    monkeypatch.setattr(f"{module}.run_query_stream", fake_stream)

    req = q.QueryRequest(question="follow up", provider=provider, model=None, thread_id="t1", ticker="NVDA")

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    # history = ONLY the 2 prior turns ({role,content}), NOT the current "follow up"
    assert captured["history"] == [
        {"role": "user", "content": "prev q"},
        {"role": "assistant", "content": "prev a"},
    ]
    # agent receives the ticker-framed question; the store keeps the raw one
    assert captured["question"] == "針對 NVDA：follow up"
    assert captured["model"]  # B1: request.model=None → resolved to the provider's research model (not None)
    assert store.list_messages("t1")[-1].content == "ok"  # assistant turn persisted after


def test_query_stream_no_thread_id_sends_empty_history(store, monkeypatch):
    """Without a (valid) thread_id, no persistence and history=[] (single-turn)."""
    import asyncio

    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured["history"] = history
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "ok", "tools_used": [], "provider": "anthropic", "model": "m", "token_usage": {}})

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", fake_stream)
    req = q.QueryRequest(question="hi", provider="anthropic", model=None, thread_id=None, ticker=None)

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    assert captured["history"] == []
    assert store.list_threads() == []  # nothing persisted without a thread_id


def test_anthropic_oauth_failclosed_becomes_error_event_and_persists(store, monkeypatch):
    """7A-0: a SubscriptionDriverNotWiredError raised from the anthropic stream
    (OAuth active, subscription driver not wired) must surface as an error EVENT
    (not a 500 crash) AND persist an is_error turn (no dangling user). This is the
    integration of live_anthropic_client's fail-closed raise with query.py."""
    import asyncio
    from src.auth_drivers.live_resolver import SubscriptionDriverNotWiredError

    async def failing_stream(*, question, model, dal, history, **kwargs):
        raise SubscriptionDriverNotWiredError(
            "Claude OAuth is the active Anthropic credential — switch to an API key in Settings, or finish Slice 7."
        )
        yield  # noqa: makes this an async generator (raise fires on first __anext__)

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", failing_stream)
    req = q.QueryRequest(question="q", provider="anthropic", model=None, thread_id="t1", ticker=None)

    frames = []
    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for chunk in resp.body_iterator:
            frames.append(chunk)

    asyncio.run(drive())
    blob = "".join(frames)
    assert '"type": "error"' in blob  # converted to an error EVENT, not a crash
    msgs = store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]  # no dangling user turn
    assert msgs[1].is_error is True
    assert "API key" in msgs[1].content and "Settings" in msgs[1].content  # actionable message persisted


def test_unknown_provider_persists_error_turn_not_a_dangling_user(store):
    """An unknown provider returns early without ever calling the agent — but the
    user turn was persisted eagerly, so the error terminal must persist an
    is_error assistant turn too (same invariant as MUST-FIX 2; no dangling turn)."""
    import asyncio

    req = q.QueryRequest(question="q", provider="bad", model=None, thread_id="t1", ticker=None)

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)  # dal unused on this path
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    msgs = store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].is_error is True and "Unknown provider" in msgs[1].content
