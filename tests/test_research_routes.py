"""C-2b backend: research persistence helpers + GET routes.

Handler-direct (NOT TestClient — see feedback_route_unit_tests): the GET route
fns are called directly with a real temp-file ResearchThreadStore. Covers the 5
acceptance criteria: server-side ticker compose (#2 — raw question persisted),
server-side tool_calls accumulation from tool_start/tool_end (#3), best-effort
persistence (#4 — store errors never propagate), thread_id validation (#5).
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import pytest

from src.api.routes import query as q
from src.api.routes import research as r
from src.research_history import ResearchHistoryStore
from src.research_runs import ResearchRunStore
from src.research_threads import ResearchThreadStore, valid_thread_id


@pytest.fixture()
def store(tmp_path):
    return ResearchThreadStore(tmp_path / "profile_state.db")


@pytest.fixture()
def research_stores(tmp_path):
    db = tmp_path / "profile_state.db"
    thread_store = ResearchThreadStore(db)
    run_store = ResearchRunStore(db)
    return thread_store, run_store, ResearchHistoryStore(db)


def _archive_thread(thread_store, thread_id, archived_at):
    with sqlite3.connect(thread_store.db_path) as conn:
        conn.execute(
            "UPDATE research_threads SET archived_at = ? WHERE id = ?",
            (archived_at, thread_id),
        )


def _add_run(run_store, thread_id, run_id, *, status="queued", created_at=None):
    run_store.create_run(
        id=run_id,
        thread_id=thread_id,
        question=f"question for {thread_id}",
        ticker=None,
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
        auth_mode="api_key",
        credential_id=None,
    )
    if status != "queued" or created_at is not None:
        timestamp = created_at or "2026-07-18T02:00:00+00:00"
        with sqlite3.connect(run_store.db_path) as conn:
            conn.execute(
                "UPDATE research_runs SET status = ?, created_at = ?, updated_at = ? WHERE id = ?",
                (status, timestamp, timestamp, run_id),
            )
    return run_store.get_run(run_id)


def _begin_writer(db_path):
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN IMMEDIATE")
    return conn


def _insert_active_run(conn, thread_id, run_id):
    conn.execute(
        """
        INSERT INTO research_runs
            (id, thread_id, status, question, provider, model, created_at, updated_at)
        VALUES
            (?, ?, 'queued', 'question', 'openai', 'gpt-5.4-mini',
             '2026-07-18T02:00:00+00:00', '2026-07-18T02:00:00+00:00')
        """,
        (run_id, thread_id),
    )


def _capture(call):
    try:
        return None, call()
    except Exception as exc:  # assertions inspect the exact routed failure
        return exc, None


class _WriteSignalingConnection:
    def __init__(self, conn, blocked):
        self._conn = conn
        self._blocked = blocked

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if (
            normalized == "BEGIN IMMEDIATE"
            or normalized.startswith("UPDATE research_threads SET")
            or normalized.startswith("DELETE FROM research_threads")
            or normalized.startswith("INSERT INTO research_messages")
        ):
            self._blocked.set()
        return self._conn.execute(sql, params)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, *args):
        return self._conn.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _install_write_signal(
    monkeypatch,
    thread_store,
    run_store,
    thread_connect,
    run_connect,
):
    blocked = threading.Event()
    monkeypatch.setattr(
        thread_store,
        "_connect",
        lambda: _WriteSignalingConnection(thread_connect(), blocked),
    )
    monkeypatch.setattr(
        run_store,
        "_connect",
        lambda: _WriteSignalingConnection(run_connect(), blocked),
    )
    return blocked


def _finish_after_writer_commit(writer, call, blocked):

    def invoke():
        return _capture(call)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(invoke)
        assert blocked.wait(timeout=1)
        with pytest.raises(FutureTimeoutError):
            future.result(timeout=0.1)
        writer.commit()
        return future.result(timeout=5)


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
        elapsed=2.0, effort="high",
    )
    msgs = store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == "最近焦點？" and msgs[0].tickers == ["NVDA"]  # RAW question, NOT prefixed
    assert msgs[1].tool_calls == [{"name": "get_sa_feed", "input": {"ticker": "NVDA"}, "result_preview": "5"}]
    assert msgs[1].tools_used == ["get_sa_feed"] and msgs[1].elapsed_seconds == 2.0
    assert msgs[1].effort == "high"
    assert msgs[1].is_error is False
    assert store.get_thread("t1").title == "最近焦點？"


def test_persist_error_turn_marks_is_error_and_preserves_partial_trace(store):
    # MUST-FIX 2: a non-`done` terminal (agent error) persists an assistant turn
    # so reload doesn't show a dangling user question with no reply.
    q._persist_user_turn(store, thread_id="t1", question="q", ticker=None, provider="anthropic", model="m", title="q")
    q._persist_error_turn(
        store, thread_id="t1", content="RuntimeError: db down",
        collected=[("tool_start", {"tool": "get_sa_feed", "input": {"x": 1}}), ("tool_end", {"tool": "get_sa_feed", "summary": "r"})],
        provider="anthropic", model="m", effort="max", elapsed=1.5,
    )
    msgs = store.list_messages("t1")
    assert [m.role for m in msgs] == ["user", "assistant"]
    a = msgs[1]
    assert a.is_error is True and a.content == "RuntimeError: db down"
    assert a.effort == "max"
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
def test_list_threads_route_orders_desc(research_stores):
    store, run_store, history_store = research_stores
    store.ensure_thread(id="t1", title="alpha", now="2026-06-14T00:00:00+00:00")
    store.ensure_thread(id="t2", title="beta", now="2026-06-14T00:01:00+00:00")
    res = r.list_research_threads(
        q=None,
        ticker=None,
        updated_from=None,
        updated_before=None,
        run_state="all",
        archived="current",
        limit=50,
        offset=0,
        store=store,
        history_store=history_store,
        run_store=run_store,
    )
    assert [t["id"] for t in res["threads"]] == ["t2", "t1"]  # updated_at desc
    assert res["threads"][0]["title"] == "beta"
    assert res["total"] == 2
    assert res["limit"] == 50 and res["offset"] == 0
    assert res["threads"][0]["archived_at"] is None
    assert res["threads"][0]["latest_run_status"] is None
    assert res["threads"][0]["active_run"] is None


def test_history_route_filters_before_pagination_and_batches_active_runs(
    research_stores, monkeypatch
):
    thread_store, run_store, history_store = research_stores
    thread_specs = [
        ("match-new", "Needle newest", "NVDA", "2026-07-18T03:00:00+00:00", True),
        ("match-old", "Needle older", "nvda", "2026-07-18T02:00:00+00:00", True),
        ("wrong-q", "Unrelated", "NVDA", "2026-07-18T02:30:00+00:00", True),
        ("wrong-ticker", "Needle ticker", "AAPL", "2026-07-18T02:30:00+00:00", True),
        ("outside-window", "Needle old", "NVDA", "2026-07-18T00:30:00+00:00", True),
        ("terminal", "Needle failed", "NVDA", "2026-07-18T02:30:00+00:00", True),
        ("current", "Needle current", "NVDA", "2026-07-18T02:30:00+00:00", False),
    ]
    for thread_id, title, ticker, updated_at, _ in thread_specs:
        thread_store.ensure_thread(
            id=thread_id,
            title=title,
            ticker=ticker,
            provider="openai",
            model="gpt-5.4-mini",
            now=updated_at,
        )
    for thread_id in [
        "match-new",
        "match-old",
        "wrong-q",
        "wrong-ticker",
        "outside-window",
        "current",
    ]:
        _add_run(run_store, thread_id, f"r-{thread_id}")
    _add_run(run_store, "terminal", "r-terminal", status="failed")
    for thread_id, _, _, updated_at, archived in thread_specs:
        if archived:
            _archive_thread(thread_store, thread_id, updated_at)

    history_calls = []
    real_query = history_store.query_threads

    def recording_query(**kwargs):
        history_calls.append(kwargs)
        page = real_query(**kwargs)
        run_store.mark_terminal("r-match-old", "failed", error="interleaved")
        return page

    batch_calls = []
    real_batch = run_store.latest_active_for_threads

    def recording_batch(thread_ids, *, conn=None):
        batch_calls.append((list(thread_ids), conn is not None))
        return real_batch(thread_ids, conn=conn)

    def forbid_single_lookup(*args, **kwargs):
        raise AssertionError("list route must not call latest_active_for_thread")

    monkeypatch.setattr(history_store, "query_threads", recording_query)
    monkeypatch.setattr(run_store, "latest_active_for_threads", recording_batch)
    monkeypatch.setattr(run_store, "latest_active_for_thread", forbid_single_lookup)

    response = r.list_research_threads(
        q="Needle",
        ticker="nvda",
        updated_from="2026-07-18T01:00:00+00:00",
        updated_before="2026-07-18T04:00:00+00:00",
        run_state="active",
        archived="archived",
        limit=1,
        offset=1,
        store=thread_store,
        history_store=history_store,
        run_store=run_store,
    )

    assert history_calls == [
        {
            "q": "Needle",
            "ticker": "nvda",
            "updated_from": "2026-07-18T01:00:00+00:00",
            "updated_before": "2026-07-18T04:00:00+00:00",
            "run_state": "active",
            "archive_mode": "archived",
            "limit": 1,
            "offset": 1,
            "run_store": run_store,
        }
    ]
    assert response["total"] == 2
    assert response["limit"] == 1 and response["offset"] == 1
    assert [thread["id"] for thread in response["threads"]] == ["match-old"]
    thread = response["threads"][0]
    assert thread["latest_run_status"] == "queued"
    assert thread["archived_at"] == "2026-07-18T02:00:00+00:00"
    assert thread["active_run"]["id"] == "r-match-old"
    assert thread["active_run"]["status"] == "queued"
    assert run_store.get_run("r-match-old").status == "failed"
    assert batch_calls == [(["match-old"], True)]
    assert run_store.latest_active_for_threads([]) == {}
    with pytest.raises(ValueError):
        run_store.latest_active_for_threads([f"thread-{i}" for i in range(201)])
    with pytest.raises(TypeError):
        run_store.latest_active_for_threads(iter(["match-old"]))


def test_exact_thread_route_returns_archived_target_outside_history_page(research_stores):
    thread_store, run_store, history_store = research_stores
    thread_store.ensure_thread(
        id="target", title="Archived target", now="2026-07-18T01:00:00+00:00"
    )
    thread_store.ensure_thread(
        id="newer", title="Newer archived", now="2026-07-18T02:00:00+00:00"
    )
    _archive_thread(thread_store, "target", "2026-07-18T01:30:00+00:00")
    _archive_thread(thread_store, "newer", "2026-07-18T02:30:00+00:00")
    page = history_store.query_threads(archive_mode="archived", limit=1)
    assert [thread.id for thread in page.threads] == ["newer"]

    response = r.get_research_thread(
        thread_id="target", store=thread_store, run_store=run_store
    )

    assert response["thread"]["id"] == "target"
    assert response["thread"]["archived_at"] == "2026-07-18T01:30:00+00:00"
    assert response["thread"]["active_run"] is None


def test_patch_thread_renames_and_rejects_invalid_titles_without_mutation(
    research_stores, monkeypatch
):
    from fastapi import HTTPException

    thread_store, run_store, _ = research_stores
    original = thread_store.ensure_thread(
        id="t1", title="Original", now="2026-07-18T01:00:00+00:00"
    )
    thread_store.append_message(thread_id="t1", role="user", content="keep me")

    response = r.patch_research_thread(
        thread_id="t1",
        request=r.ResearchThreadPatch(title="  Renamed  "),
        store=thread_store,
        run_store=run_store,
    )

    assert response["thread"]["title"] == "Renamed"
    assert response["thread"]["created_at"] == original.created_at
    assert response["thread"]["updated_at"] != original.updated_at
    assert [m.content for m in thread_store.list_messages("t1")] == ["keep me"]

    with sqlite3.connect(thread_store.db_path) as conn:
        conn.execute(
            """
            CREATE TRIGGER abort_thread_archive
            BEFORE UPDATE OF archived_at ON research_threads
            WHEN NEW.id = 't1'
            BEGIN
                SELECT RAISE(ABORT, 'archive write failed');
            END
            """
        )
    with pytest.raises(sqlite3.IntegrityError, match="archive write failed"):
        r.patch_research_thread(
            thread_id="t1",
            request=r.ResearchThreadPatch(title="Must roll back", archived=True),
            store=thread_store,
            run_store=run_store,
        )
    rolled_back = thread_store.get_thread("t1")
    assert rolled_back.title == "Renamed"
    assert rolled_back.archived_at is None
    with sqlite3.connect(thread_store.db_path) as conn:
        conn.execute("DROP TRIGGER abort_thread_archive")

    combined = r.patch_research_thread(
        thread_id="t1",
        request=r.ResearchThreadPatch(title="Atomic rename", archived=True),
        store=thread_store,
        run_store=run_store,
    )
    assert combined["thread"]["title"] == "Atomic rename"
    assert combined["thread"]["archived_at"] is not None

    for invalid_title in ("   ", "x" * 61):
        with pytest.raises(HTTPException) as exc_info:
            r.patch_research_thread(
                thread_id="t1",
                request=r.ResearchThreadPatch(title=invalid_title),
                store=thread_store,
                run_store=run_store,
            )
        assert exc_info.value.status_code == 422
        assert thread_store.get_thread("t1").title == "Atomic rename"
    with pytest.raises(HTTPException) as exc_info:
        r.patch_research_thread(
            thread_id="t1",
            request=r.ResearchThreadPatch(),
            store=thread_store,
            run_store=run_store,
        )
    assert exc_info.value.status_code == 422
    assert thread_store.get_thread("t1").title == "Atomic rename"

    thread_store.ensure_thread(id="missing-race", title="Race")
    real_update = thread_store.update_thread_lifecycle

    def delete_before_update(thread_id, **kwargs):
        assert thread_store.delete_thread(thread_id) is True
        return real_update(thread_id, **kwargs)

    monkeypatch.setattr(thread_store, "update_thread_lifecycle", delete_before_update)
    with pytest.raises(HTTPException) as exc_info:
        r.patch_research_thread(
            thread_id="missing-race",
            request=r.ResearchThreadPatch(title="Gone"),
            store=thread_store,
            run_store=run_store,
        )
    assert exc_info.value.status_code == 404


def test_patch_archive_active_thread_returns_409_without_mutation(
    research_stores, monkeypatch
):
    from fastapi import HTTPException

    thread_store, run_store, _ = research_stores
    thread_connect = thread_store._connect
    run_connect = run_store._connect
    thread_store.ensure_thread(id="t1", title="Active")
    thread_store.append_message(thread_id="t1", role="user", content="question")
    _add_run(run_store, "t1", "r1")

    with pytest.raises(HTTPException) as exc_info:
        r.patch_research_thread(
            thread_id="t1",
            request=r.ResearchThreadPatch(archived=True),
            store=thread_store,
            run_store=run_store,
        )

    assert exc_info.value.status_code == 409
    assert thread_store.get_thread("t1").archived_at is None
    assert [m.content for m in thread_store.list_messages("t1")] == ["question"]
    assert run_store.get_run("r1").status == "queued"

    thread_store.ensure_thread(id="run-first-archive", title="Run first")
    blocked = _install_write_signal(
        monkeypatch, thread_store, run_store, thread_connect, run_connect
    )
    writer = _begin_writer(thread_store.db_path)
    try:
        _insert_active_run(writer, "run-first-archive", "r-run-first-archive")
        error, _ = _finish_after_writer_commit(
            writer,
            lambda: r.patch_research_thread(
                thread_id="run-first-archive",
                request=r.ResearchThreadPatch(archived=True),
                store=thread_store,
                run_store=run_store,
            ),
            blocked,
        )
    finally:
        writer.close()
    assert isinstance(error, HTTPException) and error.status_code == 409
    assert thread_store.get_thread("run-first-archive").archived_at is None
    assert run_store.get_run("r-run-first-archive").status == "queued"

    thread_store.ensure_thread(id="archive-first", title="Archive first")
    thread_store.append_message(
        thread_id="archive-first", role="assistant", content="existing"
    )
    monkeypatch.setattr(r, "_resolve_auth_metadata", lambda provider: (None, None))
    monkeypatch.setattr(r, "schedule_research_run", lambda **kwargs: None)
    blocked = _install_write_signal(
        monkeypatch, thread_store, run_store, thread_connect, run_connect
    )
    writer = _begin_writer(thread_store.db_path)
    try:
        writer.execute(
            "UPDATE research_threads SET archived_at = ? WHERE id = ?",
            ("2026-07-18T03:00:00+00:00", "archive-first"),
        )
        request = r.ResearchRunCreate(
            thread_id="archive-first",
            question="must not append",
            provider="openai",
            model="gpt-5.4-mini",
            effort="low",
        )
        error, _ = _finish_after_writer_commit(
            writer,
            lambda: asyncio.run(
                r.create_research_run(
                    request,
                    dal=object(),
                    thread_store=thread_store,
                    run_store=run_store,
                )
            ),
            blocked,
        )
    finally:
        writer.close()
    assert isinstance(error, HTTPException) and error.status_code == 409
    assert thread_store.get_thread("archive-first").archived_at is not None
    assert [m.content for m in thread_store.list_messages("archive-first")] == [
        "existing"
    ]
    assert run_store.latest_active_for_thread("archive-first") is None

    monkeypatch.setattr(thread_store, "_connect", thread_connect)
    monkeypatch.setattr(run_store, "_connect", run_connect)
    scheduled = []

    def record_schedule(**kwargs):
        created_thread = thread_store.get_thread("atomic-create")
        created_run = run_store.get_run(kwargs["run_id"])
        created_messages = thread_store.list_messages("atomic-create")
        assert created_thread is not None
        assert created_run is not None and created_run.status == "queued"
        assert [message.content for message in created_messages] == ["atomic question"]
        scheduled.append(kwargs["run_id"])

    monkeypatch.setattr(r, "schedule_research_run", record_schedule)
    with sqlite3.connect(thread_store.db_path) as conn:
        conn.execute(
            """
            CREATE TRIGGER abort_atomic_create_message
            BEFORE INSERT ON research_messages
            WHEN NEW.thread_id = 'atomic-create'
            BEGIN
                SELECT RAISE(ABORT, 'message insert failed');
            END
            """
        )

    atomic_request = r.ResearchRunCreate(
        thread_id="atomic-create",
        question="atomic question",
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
    )
    with pytest.raises(sqlite3.IntegrityError, match="message insert failed"):
        asyncio.run(
            r.create_research_run(
                atomic_request,
                dal=object(),
                thread_store=thread_store,
                run_store=run_store,
            )
        )

    assert thread_store.get_thread("atomic-create") is None
    assert thread_store.list_messages("atomic-create") == []
    with sqlite3.connect(run_store.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM research_runs WHERE thread_id = ?",
            ("atomic-create",),
        ).fetchone()[0] == 0
        conn.execute("DROP TRIGGER abort_atomic_create_message")
    assert scheduled == []

    response = asyncio.run(
        r.create_research_run(
            atomic_request,
            dal=object(),
            thread_store=thread_store,
            run_store=run_store,
        )
    )
    assert response["run"]["status"] == "queued"
    assert scheduled == [response["run"]["id"]]

    other_thread_store = ResearchThreadStore(f"{thread_store.db_path}.other")
    mismatched_request = r.ResearchRunCreate(
        thread_id="wrong-database",
        question="must stay absent",
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
    )
    with pytest.raises(ValueError, match="same SQLite database"):
        asyncio.run(
            r.create_research_run(
                mismatched_request,
                dal=object(),
                thread_store=other_thread_store,
                run_store=run_store,
            )
        )
    assert other_thread_store.get_thread("wrong-database") is None
    assert scheduled == [response["run"]["id"]]

    thread_store.ensure_thread(id="history-race", title="History race")
    thread_store.append_message(
        thread_id="history-race", role="user", content="prior question"
    )
    _add_run(run_store, "history-race", "r-history-race")
    scheduled_history = {}
    monkeypatch.setattr(
        r,
        "schedule_research_run",
        lambda **kwargs: scheduled_history.update(kwargs),
    )
    blocked = _install_write_signal(
        monkeypatch, thread_store, run_store, thread_connect, run_connect
    )
    writer = _begin_writer(thread_store.db_path)
    try:
        writer.execute(
            """
            INSERT INTO research_messages (thread_id, role, content, created_at)
            VALUES (?, 'assistant', 'just completed', ?)
            """,
            ("history-race", "2026-07-18T04:00:00+00:00"),
        )
        writer.execute(
            "UPDATE research_threads SET updated_at = ? WHERE id = ?",
            ("2026-07-18T04:00:00+00:00", "history-race"),
        )
        writer.execute(
            """
            UPDATE research_runs
            SET status = 'succeeded', completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                "2026-07-18T04:00:01+00:00",
                "2026-07-18T04:00:01+00:00",
                "r-history-race",
            ),
        )
        history_request = r.ResearchRunCreate(
            thread_id="history-race",
            question="follow up",
            provider="openai",
            model="gpt-5.4-mini",
            effort="low",
        )
        error, response = _finish_after_writer_commit(
            writer,
            lambda: asyncio.run(
                r.create_research_run(
                    history_request,
                    dal=object(),
                    thread_store=thread_store,
                    run_store=run_store,
                )
            ),
            blocked,
        )
    finally:
        writer.close()
    assert error is None
    assert response["run"]["status"] == "queued"
    assert scheduled_history["history"] == [
        {"role": "user", "content": "prior question"},
        {"role": "assistant", "content": "just completed"},
    ]
    assert run_store.get_run("r-history-race").status == "succeeded"


def test_patch_archive_and_unarchive_preserve_transcript_and_runs(research_stores):
    thread_store, run_store, history_store = research_stores
    thread_store.ensure_thread(id="t1", title="Lifecycle")
    thread_store.append_message(thread_id="t1", role="user", content="question")
    _add_run(run_store, "t1", "r1", status="succeeded")
    run_store.append_event("r1", "done", {"answer": "answer"})

    archived = r.patch_research_thread(
        thread_id="t1",
        request=r.ResearchThreadPatch(archived=True),
        store=thread_store,
        run_store=run_store,
    )

    assert archived["thread"]["archived_at"] is not None
    assert history_store.query_threads().total == 0
    assert [t.id for t in history_store.query_threads(archive_mode="archived").threads] == ["t1"]

    restored = r.patch_research_thread(
        thread_id="t1",
        request=r.ResearchThreadPatch(archived=False),
        store=thread_store,
        run_store=run_store,
    )

    assert restored["thread"]["archived_at"] is None
    assert [m.content for m in thread_store.list_messages("t1")] == ["question"]
    assert run_store.get_run("r1").status == "succeeded"
    assert [event.type for event in run_store.list_events("r1")] == ["done"]


def test_delete_active_thread_returns_409_without_cascade(
    research_stores, monkeypatch
):
    from fastapi import HTTPException

    thread_store, run_store, _ = research_stores
    thread_connect = thread_store._connect
    run_connect = run_store._connect
    thread_store.ensure_thread(id="t1", title="Active")
    thread_store.append_message(thread_id="t1", role="user", content="question")
    _add_run(run_store, "t1", "r1")
    run_store.append_event("r1", "thinking", {"turn": 1})

    with pytest.raises(HTTPException) as exc_info:
        r.delete_research_thread(
            thread_id="t1", store=thread_store, run_store=run_store
        )

    assert exc_info.value.status_code == 409
    assert thread_store.get_thread("t1") is not None
    assert [m.content for m in thread_store.list_messages("t1")] == ["question"]
    assert run_store.get_run("r1").status == "queued"
    assert [event.type for event in run_store.list_events("r1")] == ["thinking"]

    thread_store.ensure_thread(id="run-first-delete", title="Run first")
    blocked = _install_write_signal(
        monkeypatch, thread_store, run_store, thread_connect, run_connect
    )
    writer = _begin_writer(thread_store.db_path)
    try:
        _insert_active_run(writer, "run-first-delete", "r-run-first-delete")
        error, _ = _finish_after_writer_commit(
            writer,
            lambda: r.delete_research_thread(
                thread_id="run-first-delete",
                store=thread_store,
                run_store=run_store,
            ),
            blocked,
        )
    finally:
        writer.close()
    assert isinstance(error, HTTPException) and error.status_code == 409
    assert thread_store.get_thread("run-first-delete") is not None
    assert run_store.get_run("r-run-first-delete").status == "queued"

    thread_store.ensure_thread(id="delete-first", title="Delete first")
    thread_store.append_message(
        thread_id="delete-first", role="assistant", content="removed with thread"
    )
    monkeypatch.setattr(r, "_resolve_auth_metadata", lambda provider: (None, None))
    monkeypatch.setattr(r, "schedule_research_run", lambda **kwargs: None)
    blocked = _install_write_signal(
        monkeypatch, thread_store, run_store, thread_connect, run_connect
    )
    writer = _begin_writer(thread_store.db_path)
    try:
        writer.execute("DELETE FROM research_threads WHERE id = ?", ("delete-first",))
        request = r.ResearchRunCreate(
            thread_id="delete-first",
            question="must not append",
            provider="openai",
            model="gpt-5.4-mini",
            effort="low",
        )
        error, _ = _finish_after_writer_commit(
            writer,
            lambda: asyncio.run(
                r.create_research_run(
                    request,
                    dal=object(),
                    thread_store=thread_store,
                    run_store=run_store,
                )
            ),
            blocked,
        )
    finally:
        writer.close()
    assert isinstance(error, HTTPException) and error.status_code == 409
    assert thread_store.get_thread("delete-first") is None
    assert thread_store.list_messages("delete-first") == []
    assert run_store.latest_active_for_thread("delete-first") is None

    monkeypatch.setattr(thread_store, "_connect", thread_connect)
    monkeypatch.setattr(run_store, "_connect", run_connect)

    def fail_schedule(**kwargs):
        raise RuntimeError("secret scheduler internals")

    monkeypatch.setattr(r, "schedule_research_run", fail_schedule)
    schedule_request = r.ResearchRunCreate(
        thread_id="schedule-failure",
        question="schedule me",
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            r.create_research_run(
                schedule_request,
                dal=object(),
                thread_store=thread_store,
                run_store=run_store,
            )
        )
    assert exc_info.value.status_code == 503
    assert "secret scheduler internals" not in str(exc_info.value.detail)

    messages = thread_store.list_messages("schedule-failure")
    assert [(message.role, message.content) for message in messages] == [
        ("user", "schedule me"),
        ("assistant", "research run could not be scheduled"),
    ]
    assert messages[-1].is_error is True
    assert messages[-1].run_id is not None
    failed_run = run_store.get_run(messages[-1].run_id)
    assert failed_run.status == "failed"
    assert failed_run.error == "research run could not be scheduled"
    assert run_store.latest_active_for_thread("schedule-failure") is None
    assert [
        (event.type, event.data)
        for event in run_store.list_events(failed_run.id)
    ] == [
        ("error", {"error": "research run could not be scheduled"})
    ]

    retry_schedule = {}
    monkeypatch.setattr(
        r,
        "schedule_research_run",
        lambda **kwargs: retry_schedule.update(kwargs),
    )
    retry_request = r.ResearchRunCreate(
        thread_id="schedule-failure",
        question="retry now",
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
        retry_last_failed=True,
    )
    retry_response = asyncio.run(
        r.create_research_run(
            retry_request,
            dal=object(),
            thread_store=thread_store,
            run_store=run_store,
        )
    )
    assert retry_response["run"]["status"] == "queued"
    assert retry_schedule["history"] == []
    assert [
        (message.role, message.content)
        for message in thread_store.list_messages("schedule-failure")
    ] == [
        ("user", "schedule me"),
        ("assistant", "research run could not be scheduled"),
        ("user", "retry now"),
    ]


def test_list_messages_route_roundtrip(store):
    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="hi", tickers=["NVDA"])
    res = r.list_research_messages(thread_id="t1", store=store)
    assert res["thread_id"] == "t1" and len(res["messages"]) == 1
    assert res["messages"][0]["role"] == "user" and res["messages"][0]["tickers"] == ["NVDA"]
    assert res["messages"][0]["is_error"] is False  # serialized for the client mapper


def test_latest_selection_route_returns_semantic_tuple_without_credentials(
    research_stores,
):
    thread_store, run_store, _ = research_stores
    thread_store.ensure_thread(id="selection", title="Selection")
    run_store.create_run(
        id="successful",
        thread_id="selection",
        question="successful",
        ticker=None,
        provider="anthropic",
        model="claude-sonnet-5",
        effort=None,
        auth_mode="claude_code_oauth",
        credential_id="local:secret",
    )
    run_store.mark_terminal("successful", "succeeded")
    run_store.create_run(
        id="newer-failed",
        thread_id="selection",
        question="failed",
        ticker=None,
        provider="openai",
        model="gpt-5.6-luna",
        effort="high",
        auth_mode="api_key",
        credential_id="local:other-secret",
    )
    run_store.mark_terminal("newer-failed", "failed", error="failed")

    response = r.get_research_thread_selection(
        "selection",
        store=thread_store,
        run_store=run_store,
    )

    assert response == {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "effort": "default",
    }
    assert all("credential" not in key for key in response)


def test_run_and_message_routes_expose_typed_redacted_failure_details(
    research_stores,
):
    thread_store, run_store, _ = research_stores
    secret = "AbCdEf1234567890"
    raw_error = f"failed access_token={secret} " + ("detail " * 100)
    thread_store.ensure_thread(id="typed-error", title="Typed error")
    run_store.create_run(
        id="typed-run",
        thread_id="typed-error",
        question="q",
        ticker=None,
        provider="openai",
        model="gpt-5.4-mini",
        effort="default",
        auth_mode="api_key",
        credential_id="local:compat-only",
    )
    run_store.mark_terminal(
        "typed-run",
        "failed",
        error=raw_error,
        error_code="model_timeout",
    )
    thread_store.append_message(
        thread_id="typed-error",
        run_id="typed-run",
        role="assistant",
        content=raw_error,
        provider="openai",
        model="gpt-5.4-mini",
        effort="default",
        is_error=True,
        error_code="model_timeout",
    )

    run_response = r.get_research_run("typed-run", run_store=run_store)["run"]
    message_response = r.list_research_messages(
        "typed-error", store=thread_store
    )["messages"][-1]

    assert run_response["error_code"] == "model_timeout"
    assert secret not in run_response["error"]
    assert "[REDACTED]" in run_response["error"]
    assert len(run_response["error"]) <= 500
    assert message_response["run_id"] == "typed-run"
    assert message_response["error_code"] == "model_timeout"
    assert message_response["error"] == message_response["content"]
    assert secret not in str(message_response)
    assert len(message_response["error"]) <= 500
    assert all("credential" not in key for key in message_response)


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


def test_query_stream_retry_last_failed_excludes_failed_pair_from_history(store, monkeypatch):
    import asyncio

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="q1")
    store.append_message(thread_id="t1", role="assistant", content="a1")
    store.append_message(thread_id="t1", role="user", content="failed q")
    store.append_message(thread_id="t1", role="assistant", content="RuntimeError: db down", is_error=True)
    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured["question"] = question
        captured["history"] = history
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "retried ok", "tools_used": [], "provider": "openai", "model": model, "token_usage": {}})

    monkeypatch.setattr("src.agents.openai_agent.agent.run_query_stream", fake_stream)

    req = q.QueryRequest(
        question="failed q",
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
        thread_id="t1",
        ticker=None,
        retry_last_failed=True,
    )

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    assert captured["question"] == "failed q"
    assert captured["history"] == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    assert [m.content for m in store.list_messages("t1")][-2:] == ["failed q", "retried ok"]


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


# --- (c) openai api_key → unchanged; the OAuth helper is never consulted ---
def test_openai_api_key_active_still_uses_run_query_stream(store, monkeypatch):
    import asyncio

    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda provider, **k: _apikey_active("openai"))

    def boom_sub(**k):  # pragma: no cover - asserts it's never reached
        raise AssertionError("_openai_subscription_stream must NOT run for api_key")

    monkeypatch.setattr(q, "_openai_subscription_stream", boom_sub)

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


def test_oauth_active_openai_routes_to_chatgpt_oauth_driver(store, monkeypatch):
    import asyncio

    store.ensure_thread(id="t1", title="prev")
    store.append_message(thread_id="t1", role="user", content="prev q")
    store.append_message(thread_id="t1", role="assistant", content="prev a")

    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda provider, **k: _oauth_active("openai", "local:9"))

    captured = {}

    def fake_oauth_stream(*, credential_id, question, model, effort, dal, history):
        captured.update(credential_id=credential_id, question=question, model=model,
                        effort=effort, history=history)
        return _canned_events(provider="openai", model=model)

    monkeypatch.setattr(q, "_openai_subscription_stream", fake_oauth_stream)

    def boom_run_query_stream(**k):  # pragma: no cover - asserts it's never reached
        raise AssertionError("run_query_stream must NOT be called for chatgpt_oauth")

    monkeypatch.setattr("src.agents.openai_agent.agent.run_query_stream", boom_run_query_stream)

    req = q.QueryRequest(question="follow up", provider="openai", model="gpt-5.4-mini",
                         effort="low", thread_id="t1", ticker="AAPL")

    frames = []

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for chunk in resp.body_iterator:
            frames.append(chunk)

    asyncio.run(drive())

    assert captured["credential_id"] == "local:9"
    assert captured["question"] == "針對 AAPL：follow up"
    assert captured["model"] == "gpt-5.4-mini"
    assert captured["effort"] == "low"
    assert captured["history"] == [
        {"role": "user", "content": "prev q"},
        {"role": "assistant", "content": "prev a"},
    ]
    blob = "".join(frames)
    assert '"type": "done"' in blob and "subscription answer" in blob
    assert store.list_messages("t1")[-1].content == "subscription answer"


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
def test_anthropic_subscription_stream_builds_driver_with_registry_dal_and_prompt(monkeypatch, tmp_path):
    """_anthropic_subscription_stream: cred from CredentialStore.get, a registered
    ToolRegistry, build_driver(..., registry, dal, token_store), and an LLMRequest
    whose input_messages = [*history, user] and instructions = the REUSED anthropic
    research system prompt (build_system_prompt)."""
    sentinel_token_store = object()
    sentinel_dal = object()
    sentinel_cred = object()
    sentinel_stream = object()
    db = tmp_path / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))
    from src.research_runtime_config import ResearchRuntimeStore
    ResearchRuntimeStore(db).set(max_tool_calls=72, session_timeout_s=1800, per_tool_timeout_s=60)

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

    def fake_build_driver(
        *,
        provider,
        auth_mode,
        credential,
        token_store,
        registry,
        dal,
        max_turns,
        timeout_s,
        per_tool_timeout_s,
    ):
        captured.update(provider=provider, auth_mode=auth_mode, credential=credential,
                        token_store=token_store, registry=registry, dal=dal,
                        max_turns=max_turns, timeout_s=timeout_s,
                        per_tool_timeout_s=per_tool_timeout_s)
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
    assert captured["max_turns"] == 72  # DB authority; no hidden 8-turn cap
    assert captured["timeout_s"] == 1800.0  # DB authority; no hidden 180s wall-clock cap
    assert captured["per_tool_timeout_s"] == 60.0
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
        effort="max", dal=object(), history=[],
    )

    from src.agents.shared.prompts import build_system_prompt
    req = captured["req"]
    assert req.instructions == build_system_prompt()  # no suffix on single-turn
    assert "[多輪脈絡]" not in req.instructions
    assert req.input_messages == [{"role": "user", "content": "hi"}]
    assert req.reasoning_effort == "max"


def test_openai_subscription_stream_builds_driver_with_research_runtime(monkeypatch, tmp_path):
    sentinel_token_store = object()
    sentinel_dal = object()
    sentinel_cred = object()
    sentinel_stream = object()
    db = tmp_path / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))
    from src.research_runtime_config import ResearchRuntimeStore
    ResearchRuntimeStore(db).set(max_tool_calls=23, session_timeout_s=1200, per_tool_timeout_s=18)

    class FakeStore:
        def __init__(self, *a, **k):
            pass

        def get(self, credential_id):
            assert credential_id == "local:9"
            return sentinel_cred

    class FakeRegistry:
        def register_all(self):
            pass

    class FakeDriver:
        def stream_llm(self, req):
            return sentinel_stream

    captured = {}

    def fake_build_driver(
        *,
        provider,
        auth_mode,
        credential,
        token_store,
        registry,
        dal,
        max_turns,
        timeout_s,
        per_tool_timeout_s,
    ):
        captured.update(
            provider=provider, auth_mode=auth_mode, credential=credential,
            token_store=token_store, registry=registry, dal=dal,
            max_turns=max_turns, timeout_s=timeout_s,
            per_tool_timeout_s=per_tool_timeout_s,
        )
        return FakeDriver()

    monkeypatch.setattr("src.model_credentials.CredentialStore", FakeStore)
    monkeypatch.setattr("src.auth_drivers.token_store.get_token_store", lambda: sentinel_token_store)
    monkeypatch.setattr("src.tools.registry.ToolRegistry", FakeRegistry)
    monkeypatch.setattr("src.auth_drivers.factory.build_driver", fake_build_driver)

    out = q._openai_subscription_stream(
        credential_id="local:9", question="hi", model="gpt-5.4-mini",
        effort="low", dal=sentinel_dal, history=[],
    )

    assert out is sentinel_stream
    assert captured["provider"] == "openai"
    assert captured["auth_mode"] == "chatgpt_oauth"
    assert captured["max_turns"] == 23
    assert captured["timeout_s"] == 1200.0
    assert captured["per_tool_timeout_s"] == 18.0


def test_api_key_stream_receives_research_max_turns(store, monkeypatch, tmp_path):
    import asyncio

    db = tmp_path / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))
    from src.research_runtime_config import ResearchRuntimeStore
    ResearchRuntimeStore(db).set(max_tool_calls=31, session_timeout_s=900, per_tool_timeout_s=45)
    monkeypatch.setattr("src.auth_drivers.live_resolver.resolve_live_auth", lambda provider, **k: _apikey_active("openai"))
    captured = {}

    async def fake_stream(*, question, model, dal, history, max_tool_calls, **kwargs):
        captured["max_tool_calls"] = max_tool_calls
        from src.agents.shared.events import AgentEvent, EventType
        yield AgentEvent(EventType.done, {"answer": "ok", "tools_used": [], "provider": "openai", "model": model, "token_usage": {}})

    monkeypatch.setattr("src.agents.openai_agent.agent.run_query_stream", fake_stream)

    req = q.QueryRequest(question="q", provider="openai", model="gpt-5.4-mini", thread_id=None)

    async def drive():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(drive())
    assert captured["max_tool_calls"] == 31


# ─── Track A: investor profile personalization on /query/stream ──────────────


def _profile_store(tmp_path, monkeypatch, *, enabled):
    from src.investor_profile import InvestorProfileStore

    pstore = InvestorProfileStore(tmp_path / "investor_profile.db")
    if enabled:
        pstore.save(
            {
                "enabled": True,
                "risk_appetite": 8,
                "risk_capacity": 4,
                "behavioral_flags": ["FOMO"],
                "default_stance": "complementary",
            }
        )
    monkeypatch.setattr(
        "src.api.dependencies.get_investor_profile_store", lambda: pstore
    )
    return pstore


def _drive(req, store):
    import asyncio

    frames = []

    async def go():
        resp = await q.query_agent_stream(req, dal=object(), store=store)
        async for chunk in resp.body_iterator:
            frames.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))

    asyncio.run(go())
    return frames


def test_query_stream_profile_off_does_not_pass_personalization_kwarg(
    store, tmp_path, monkeypatch
):
    _profile_store(tmp_path, monkeypatch, enabled=False)
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth", lambda p, **k: _apikey_active()
    )

    async def strict_fake(*, question, model, dal, history, effort=None, max_tool_calls=None):
        # NO **kwargs on purpose: an unexpected personalization kwarg = TypeError.
        from src.agents.shared.events import AgentEvent, EventType

        yield AgentEvent(
            EventType.done,
            {"answer": "ok", "tools_used": [], "provider": "anthropic", "model": model, "token_usage": {}},
        )

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", strict_fake)
    store.ensure_thread(id="tpo", title="x")
    req = q.QueryRequest(question="hi", provider="anthropic", thread_id="tpo")
    frames = _drive(req, store)
    assert any('"done"' in f for f in frames)
    last = store.list_messages("tpo")[-1]
    assert last.personalization is None or last.personalization["profile_active"] is False


def test_query_stream_enabled_profile_passes_context_and_persists_trace(
    store, tmp_path, monkeypatch
):
    _profile_store(tmp_path, monkeypatch, enabled=True)
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth", lambda p, **k: _apikey_active()
    )
    captured = {}

    async def fake_stream(*, question, model, dal, history, **kwargs):
        captured.update(kwargs)
        from src.agents.shared.events import AgentEvent, EventType

        yield AgentEvent(
            EventType.done,
            {"answer": "ok", "tools_used": [], "provider": "anthropic", "model": model, "token_usage": {}},
        )

    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", fake_stream)
    store.ensure_thread(id="tpe", title="x")
    req = q.QueryRequest(question="hi", provider="anthropic", thread_id="tpe")
    frames = _drive(req, store)

    ctx = captured.get("personalization_context", "")
    assert "[Assistant Stance]" in ctx and "complementary" in ctx
    assert "appetite_above_capacity" in ctx
    assert set(captured) == {
        "effort",
        "max_tool_calls",
        "personalization_context",
    }
    # done SSE event carries the trace
    import json as _json

    done_frames = [f for f in frames if '"done"' in f]
    payload = _json.loads(done_frames[-1].split("data: ", 1)[1])
    trace = payload["data"]["personalization"]
    assert trace["assistant_stance"] == "complementary"
    assert trace["profile_active"] is True
    assert trace["context_snapshot"] == ctx
    assert {
        "profile_active",
        "assistant_stance",
        "skill_mode",
        "suggested_skills",
        "applied_skills",
    } <= set(trace) <= {
        "profile_active",
        "assistant_stance",
        "skill_mode",
        "suggested_skills",
        "applied_skills",
        "context_snapshot",
    }
    assert not {
        "credential_id",
        "freeform_notes",
        "risk_appetite",
        "behavioral_flags",
    } & set(trace)
    # persisted assistant message carries the same trace
    last = store.list_messages("tpe")[-1]
    assert last.personalization == trace
    assert last.personalization["suggested_skills"] == []


@pytest.mark.parametrize("provider,helper", [
    ("anthropic", "_anthropic_subscription_stream"),
    ("openai", "_openai_subscription_stream"),
])
def test_query_stream_subscription_branches_receive_personalization_context(
    store, tmp_path, monkeypatch, provider, helper
):
    _profile_store(tmp_path, monkeypatch, enabled=True)
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda p, **k: _oauth_active(provider=p),
    )
    captured = {}

    def fake_sub(*, credential_id, question, model, effort, dal, history, **kwargs):
        captured.update(kwargs)
        return _canned_events(model=model)

    monkeypatch.setattr(q, helper, fake_sub)
    store.ensure_thread(id=f"ts-{provider}", title="x")
    req = q.QueryRequest(question="hi", provider=provider, thread_id=f"ts-{provider}")
    _drive(req, store)
    ctx = captured.get("personalization_context", "")
    assert "[Assistant Stance]" in ctx and "complementary" in ctx


def test_query_stream_subscription_profile_off_does_not_pass_personalization_kwarg(
    store, tmp_path, monkeypatch
):
    _profile_store(tmp_path, monkeypatch, enabled=False)
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth", lambda p, **k: _oauth_active()
    )

    def strict_sub(*, credential_id, question, model, effort, dal, history):
        # NO **kwargs — matches the legacy strict fake shape; off must omit the kwarg.
        return _canned_events(model=model)

    monkeypatch.setattr(q, "_anthropic_subscription_stream", strict_sub)
    store.ensure_thread(id="tso", title="x")
    req = q.QueryRequest(question="hi", provider="anthropic", thread_id="tso")
    frames = _drive(req, store)
    assert any('"done"' in f for f in frames)


def test_query_stream_invalid_assistant_stance_returns_400(store, tmp_path, monkeypatch):
    import asyncio

    from fastapi import HTTPException

    _profile_store(tmp_path, monkeypatch, enabled=True)
    req = q.QueryRequest(question="hi", provider="anthropic", assistant_stance="yolo")

    async def go():
        await q.query_agent_stream(req, dal=object(), store=store)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(go())
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "invalid_assistant_stance", "field": "assistant_stance"}
