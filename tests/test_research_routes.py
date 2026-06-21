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
    # 7B-6: pin the anthropic credential to a NON-OAuth resolution so the branch
    # deterministically uses run_query_stream (the api-key/env path), regardless of
    # whether the dev machine has a claude_code_oauth credential active. (No-op for
    # the openai parametrization — the openai branch never consults resolve_live_auth.)
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda p, **k: _apikey_active())

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


def test_query_stream_explicit_model_and_effort_passthrough(store, monkeypatch):
    # S3 step 3a: when the request carries an explicit model + effort (the AI 研究
    # picker), use them DIRECTLY — do not consult resolve_research_route.
    import asyncio

    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured["model"] = model
        captured["effort"] = kwargs.get("reasoning_effort")  # openai kwarg
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "ok", "tools_used": [], "provider": "openai", "model": model, "token_usage": {}})

    monkeypatch.setattr("src.agents.openai_agent.agent.run_query_stream", fake_stream)

    def _boom(*a, **k):
        raise AssertionError("resolve_research_route must NOT be called when model is explicit")

    monkeypatch.setattr("src.agents.config.resolve_research_route", _boom)
    req = q.QueryRequest(question="q", provider="openai", model="gpt-5.4-mini", effort="low", thread_id=None, ticker=None)

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    assert captured["model"] == "gpt-5.4-mini" and captured["effort"] == "low"


def test_query_stream_no_thread_id_sends_empty_history(store, monkeypatch):
    """Without a (valid) thread_id, no persistence and history=[] (single-turn)."""
    import asyncio

    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured["history"] = history
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "ok", "tools_used": [], "provider": "anthropic", "model": "m", "token_usage": {}})

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", fake_stream)
    # 7B-6: pin to a NON-OAuth resolution so the anthropic branch uses run_query_stream.
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda p, **k: _apikey_active())
    req = q.QueryRequest(question="hi", provider="anthropic", model=None, thread_id=None, ticker=None)

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    assert captured["history"] == []
    assert store.list_threads() == []  # nothing persisted without a thread_id


def test_anthropic_run_query_stream_raise_becomes_error_event_and_persists(store, monkeypatch):
    """A SubscriptionDriverNotWiredError (or any exception) raised from the anthropic
    run_query_stream must surface as an error EVENT (not a 500 crash) AND persist an
    is_error turn (no dangling user).

    7B-6 NOTE: an OAuth-active credential no longer reaches run_query_stream — it is
    intercepted and routed to the subscription driver BEFORE this call (its
    raise-on-first-step graceful fallback is covered by
    test_oauth_active_driver_raises_persists_error_turn_no_crash). This test pins the
    NON-OAuth (api-key/env) path, where run_query_stream is still used; it could
    still fail-close in that path. The error→event conversion is unchanged."""
    import asyncio
    from src.auth_drivers.live_resolver import SubscriptionDriverNotWiredError

    async def failing_stream(*, question, model, dal, history, **kwargs):
        raise SubscriptionDriverNotWiredError(
            "Claude OAuth is the active Anthropic credential — switch to an API key in Settings, or finish Slice 7."
        )
        yield  # noqa: makes this an async generator (raise fires on first __anext__)

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", failing_stream)
    # 7B-6: pin to a NON-OAuth resolution so the branch uses run_query_stream (the
    # only path that can still raise SubscriptionDriverNotWiredError post-7B-6).
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda p, **k: _apikey_active())
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


# =====================================================================
# 7B-6: AI 研究 on the Claude SUBSCRIPTION (claude_code_oauth-active).
#
# When the ACTIVE anthropic credential is claude_code_oauth, /query/stream's
# anthropic branch must route to the in-process Agent-SDK driver
# (_anthropic_subscription_stream) INSTEAD of run_query_stream (which fail-closes
# for OAuth). The shared `stream` is then consumed by the SAME SSE/persist code,
# so the SSE output + thread persistence behave exactly as for run_query_stream.
#
# Handler-direct, NO live: the credential resolution (resolve_live_auth, patched
# at its source module — the branch imports it lazily) and the driver
# (q._anthropic_subscription_stream / build_driver) are mocked; nothing hits PG or
# the network. The api-key-anthropic and openai paths must stay byte-for-byte
# unchanged in behavior (the subscription path is NOT taken).
# =====================================================================
from src.auth_drivers.live_resolver import LiveAuthResolution  # noqa: E402


def _oauth_active(provider="anthropic", cid="local:7"):
    """A resolution as live_resolver returns for an OAuth-active credential."""
    return LiveAuthResolution(provider, "oauth_driver_unwired", cid, "oauth pending note")


def _apikey_active(provider="anthropic", cid="local:3"):
    return LiveAuthResolution(provider, "db_api_key", cid)


async def _canned_events(provider="anthropic", model="claude-sonnet-4-6"):
    """A canned [tool_start, tool_end, text, done] AgentEvent stream — the SAME
    vocabulary run_query_stream yields, so downstream consumption is identical."""
    from src.agents.shared.events import AgentEvent, EventType

    yield AgentEvent(EventType.tool_start, {"tool": "get_ticker_news", "input": {"ticker": "NVDA"}})
    yield AgentEvent(EventType.tool_end, {"tool": "get_ticker_news", "summary": "3 articles", "chars": 42})
    yield AgentEvent(EventType.text, {"content": "partial..."})
    yield AgentEvent(
        EventType.done,
        {"answer": "subscription answer", "tools_used": ["get_ticker_news"],
         "provider": provider, "model": model, "token_usage": {"total_tokens": 9}},
    )


# --- (a) claude_code_oauth active → routes to the SDK driver; SSE + persist fire ---
def test_oauth_active_anthropic_routes_to_subscription_driver(store, monkeypatch):
    import asyncio

    store.ensure_thread(id="t1", title="prev")
    store.append_message(thread_id="t1", role="user", content="prev q")
    store.append_message(thread_id="t1", role="assistant", content="prev a")

    # Detection: the active anthropic credential is claude_code_oauth. Patched at
    # the source module (the branch imports it lazily — project convention).
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda provider, **k: _oauth_active())

    captured = {}

    def fake_sub_stream(*, credential_id, question, model, effort, dal, history):
        captured.update(credential_id=credential_id, question=question, model=model,
                        effort=effort, history=history)
        return _canned_events(model=model)

    # _anthropic_subscription_stream is a module-level fn in query.py — patch on q.
    monkeypatch.setattr(q, "_anthropic_subscription_stream", fake_sub_stream)

    # run_query_stream MUST NOT be called on the subscription path.
    def boom_run_query_stream(**k):  # pragma: no cover - asserts it's never reached
        raise AssertionError("run_query_stream must NOT be called for claude_code_oauth")

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", boom_run_query_stream)

    req = q.QueryRequest(question="follow up", provider="anthropic", model=None, thread_id="t1", ticker="NVDA")

    frames = []

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for chunk in resp.body_iterator:
            frames.append(chunk)

    asyncio.run(drive())

    # routed to the subscription helper with the resolved model + full history + framed question
    assert captured["credential_id"] == "local:7"
    assert captured["question"] == "針對 NVDA：follow up"
    assert captured["model"]  # resolved from the ai_research route (request.model=None)
    assert captured["history"] == [
        {"role": "user", "content": "prev q"},
        {"role": "assistant", "content": "prev a"},
    ]
    # SSE: the canned events streamed verbatim (same vocab as run_query_stream)
    blob = "".join(frames)
    assert '"type": "tool_start"' in blob and '"type": "tool_end"' in blob
    assert '"type": "done"' in blob and "subscription answer" in blob
    # thread persistence fired exactly as for run_query_stream (assistant turn + trace)
    msgs = store.list_messages("t1")
    assert msgs[-1].role == "assistant" and msgs[-1].content == "subscription answer"
    assert msgs[-1].is_error is False
    assert msgs[-1].tool_calls == [
        {"name": "get_ticker_news", "input": {"ticker": "NVDA"}, "result_preview": "3 articles"}
    ]


# --- (b) API-KEY anthropic active → still run_query_stream (subscription NOT taken) ---
def test_apikey_active_anthropic_still_uses_run_query_stream(store, monkeypatch):
    import asyncio

    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda provider, **k: _apikey_active())

    # The subscription helper MUST NOT be called for an api_key-active credential.
    def boom_sub(**k):  # pragma: no cover - asserts it's never reached
        raise AssertionError("_anthropic_subscription_stream must NOT run for api_key")

    monkeypatch.setattr(q, "_anthropic_subscription_stream", boom_sub)

    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured["question"] = question
        captured["history"] = history
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "apikey answer", "tools_used": [], "provider": "anthropic", "model": "m", "token_usage": {}})

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", fake_stream)

    req = q.QueryRequest(question="hi", provider="anthropic", model=None, thread_id="t1", ticker=None)

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    # run_query_stream was used (existing api-key behavior, unchanged)
    assert captured["question"] == "hi"
    assert store.list_messages("t1")[-1].content == "apikey answer"


# --- (c) openai → unchanged; the subscription path is never consulted ---
def test_openai_unaffected_by_subscription_branch(store, monkeypatch):
    import asyncio

    # If the openai branch ever consults the anthropic OAuth detection or helper,
    # these explode — proving the openai path is behaviorally untouched.
    def boom_resolve(*a, **k):  # pragma: no cover
        raise AssertionError("openai branch must NOT call resolve_live_auth")

    def boom_sub(**k):  # pragma: no cover
        raise AssertionError("openai branch must NOT call _anthropic_subscription_stream")

    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", boom_resolve)
    monkeypatch.setattr(q, "_anthropic_subscription_stream", boom_sub)

    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured["question"] = question
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "openai answer", "tools_used": [], "provider": "openai", "model": "m", "token_usage": {}})

    monkeypatch.setattr("src.agents.openai_agent.agent.run_query_stream", fake_stream)

    req = q.QueryRequest(question="hi", provider="openai", model=None, thread_id="t1", ticker=None)

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    assert captured["question"] == "hi"
    assert store.list_messages("t1")[-1].content == "openai answer"


# --- (d) claude_code_oauth active but the driver raises on first step → error turn ---
def test_oauth_active_driver_raises_persists_error_turn_no_crash(store, monkeypatch):
    import asyncio

    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda provider, **k: _oauth_active())

    async def failing_stream():
        # mirrors the driver raising MissingCredentialError on first __anext__ when
        # the token is missing (claude_code_sdk_driver._stream).
        raise RuntimeError("no Claude setup-token stored for this credential")
        yield  # noqa: makes this an async generator

    def fake_sub_stream(**k):
        return failing_stream()

    monkeypatch.setattr(q, "_anthropic_subscription_stream", fake_sub_stream)

    req = q.QueryRequest(question="q", provider="anthropic", model=None, thread_id="t1", ticker=None)

    frames = []

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for chunk in resp.body_iterator:
            frames.append(chunk)

    asyncio.run(drive())  # must NOT crash the route
    blob = "".join(frames)
    assert '"type": "error"' in blob  # surfaced as an error EVENT
    msgs = store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]  # no dangling user turn
    assert msgs[1].is_error is True
    assert "setup-token" in msgs[1].content


# --- helper unit: builds the SDK driver with registry+dal+token_store + reused prompt ---
def test_anthropic_subscription_stream_builds_driver_with_registry_dal_and_prompt(monkeypatch):
    """_anthropic_subscription_stream: cred from CredentialStore.get, a registered
    ToolRegistry, build_driver(..., registry, dal, token_store), and an LLMRequest
    whose input_messages = [*history, user] and instructions = the REUSED anthropic
    research system prompt (build_system_prompt)."""
    sentinel_token_store = object()
    sentinel_dal = object()
    sentinel_cred = object()
    sentinel_stream = object()

    # CredentialStore() → .get(credential_id) returns our sentinel credential.
    # Patched at SOURCE modules (the helper imports them lazily — project convention).
    class FakeStore:
        def __init__(self, *a, **k):
            pass

        def get(self, credential_id):
            assert credential_id == "local:7"
            return sentinel_cred

    monkeypatch.setattr("src.model_credentials.CredentialStore", FakeStore)
    monkeypatch.setattr("src.auth_drivers.token_store.get_token_store", lambda: sentinel_token_store)

    # ToolRegistry() with register_all() called.
    reg_calls = {"register_all": 0}

    class FakeRegistry:
        def register_all(self):
            reg_calls["register_all"] += 1

    monkeypatch.setattr("src.tools.registry.ToolRegistry", FakeRegistry)

    captured = {}

    class FakeDriver:
        def stream_llm(self, req):
            captured["req"] = req
            return sentinel_stream

    def fake_build_driver(*, provider, auth_mode, credential, token_store, registry, dal):
        captured.update(provider=provider, auth_mode=auth_mode, credential=credential,
                        token_store=token_store, registry=registry, dal=dal)
        return FakeDriver()

    monkeypatch.setattr("src.auth_drivers.factory.build_driver", fake_build_driver)

    history = [{"role": "user", "content": "prev q"}, {"role": "assistant", "content": "prev a"}]
    out = q._anthropic_subscription_stream(
        credential_id="local:7", question="follow up", model="claude-sonnet-4-6",
        effort=None, dal=sentinel_dal, history=history,
    )

    assert out is sentinel_stream  # returns driver.stream_llm(req) unconsumed
    assert reg_calls["register_all"] == 1
    assert captured["provider"] == "anthropic" and captured["auth_mode"] == "claude_code_oauth"
    assert captured["credential"] is sentinel_cred
    assert captured["token_store"] is sentinel_token_store
    assert captured["dal"] is sentinel_dal
    assert isinstance(captured["registry"], FakeRegistry)
    req = captured["req"]
    assert req.model == "claude-sonnet-4-6"
    # full conversation folded: history + this turn's user message
    assert req.input_messages == [
        {"role": "user", "content": "prev q"},
        {"role": "assistant", "content": "prev a"},
        {"role": "user", "content": "follow up"},
    ]
    # system prompt REUSED from the anthropic agent (same constant builder), AND —
    # because history is non-empty — suffixed with the SAME [多輪脈絡] staleness
    # guard the API-key anthropic loop appends (agent.py:235-240), so subscription
    # and API-key Research give the model identical multi-turn guidance.
    from src.agents.shared.prompts import build_system_prompt
    assert req.instructions == build_system_prompt() + (
        "\n\n[多輪脈絡] 以下對話歷史僅供理解使用者意圖與指代；價格、新聞、SA、"
        "基本面等時效性事實一律以工具即時查詢為準，歷史內容可能已過期。"
    )
    assert "[多輪脈絡]" in req.instructions


def test_anthropic_subscription_stream_no_history_uses_bare_prompt(monkeypatch):
    """Parity the other way: with EMPTY history the helper must NOT append the
    [多輪脈絡] guard — instructions == bare build_system_prompt(), matching the
    API-key loop which only appends the guard when history is non-empty
    (src/agents/anthropic_agent/agent.py:235-240)."""
    captured = {}

    class FakeStore:
        def __init__(self, *a, **k):
            pass

        def get(self, credential_id):
            return object()

    class FakeRegistry:
        def register_all(self):
            pass

    class FakeDriver:
        def stream_llm(self, req):
            captured["req"] = req
            return object()

    monkeypatch.setattr("src.model_credentials.CredentialStore", FakeStore)
    monkeypatch.setattr("src.auth_drivers.token_store.get_token_store", lambda: object())
    monkeypatch.setattr("src.tools.registry.ToolRegistry", FakeRegistry)
    monkeypatch.setattr(
        "src.auth_drivers.factory.build_driver",
        lambda **k: FakeDriver(),
    )

    q._anthropic_subscription_stream(
        credential_id="local:7", question="hi", model="claude-sonnet-4-6",
        effort=None, dal=object(), history=[],
    )

    from src.agents.shared.prompts import build_system_prompt
    req = captured["req"]
    assert req.instructions == build_system_prompt()  # no suffix on single-turn
    assert "[多輪脈絡]" not in req.instructions
    assert req.input_messages == [{"role": "user", "content": "hi"}]
