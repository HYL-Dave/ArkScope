"""C-2b: ResearchThreadStore — local persistence for AI 研究 threads/messages.

Mirrors the shipped CardRunStore (src/card_runs.py): same local profile_state.db
family, NEVER the remote PG. Thread ids are CLIENT-OWNED (stable unique strings
generated at 新對話), so the client (reducer) and server agree on identity with
no mapping/rekey — ensure_thread is idempotent (the per-turn stream hook calls
it every turn). Column names match the C-2a in-memory DTO (spec §6a) so
persistence is a pure write-through. Tested directly, no FastAPI/TestClient.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.research_threads import ResearchThreadStore


@pytest.fixture()
def store(tmp_path):
    return ResearchThreadStore(tmp_path / "profile_state.db")


def test_ensure_thread_roundtrips_fields(store):
    t = store.ensure_thread(id="th-abc", title="最近 SA 對 SMCI 的焦點？", ticker="SMCI", provider="anthropic", model="claude-opus-4-8", now="2026-06-14T00:00:00+00:00")
    assert t.id == "th-abc"  # client-supplied string id
    assert t.title == "最近 SA 對 SMCI 的焦點？"
    assert t.ticker == "SMCI" and t.provider == "anthropic" and t.model == "claude-opus-4-8"
    assert t.created_at == "2026-06-14T00:00:00+00:00" and t.updated_at == t.created_at
    assert t.archived_at is None
    assert store.get_thread("th-abc") == t


def test_ensure_thread_is_idempotent_keeps_original(store):
    store.ensure_thread(id="th-1", title="original title", now="2026-06-14T00:00:00+00:00")
    # second turn in the same thread: the stream hook calls ensure_thread again —
    # must NOT create a duplicate or overwrite the original title/created_at.
    again = store.ensure_thread(id="th-1", title="DIFFERENT", now="2026-06-14T05:00:00+00:00")
    assert again.title == "original title"
    assert again.created_at == "2026-06-14T00:00:00+00:00"
    assert len(store.list_threads()) == 1


def test_get_thread_none_for_missing(store):
    assert store.get_thread("nope") is None
    assert store.list_messages("nope") == []


def test_append_user_then_assistant_roundtrips_and_orders(store):
    store.ensure_thread(id="th-nvda", title="q", ticker="NVDA", provider="anthropic", model="m")
    store.append_message(thread_id="th-nvda", role="user", content="NVDA 最新 SA 動態？", tickers=["NVDA"])
    store.append_message(
        thread_id="th-nvda", role="assistant", content="NVDA: 3 看多 2 看空。",
        provider="anthropic", model="claude-opus-4-8", effort="high",
        tools_used=["get_sa_feed"],
        tool_calls=[{"name": "get_sa_feed", "input": {"ticker": "NVDA"}, "result_preview": "5 articles"}],
        token_usage={"total_tokens": 1500, "turn_count": 2},
        tickers=["NVDA"], elapsed_seconds=3.0,
    )
    msgs = store.list_messages("th-nvda")
    assert [m.role for m in msgs] == ["user", "assistant"]
    u, a = msgs
    assert u.content == "NVDA 最新 SA 動態？" and u.tickers == ["NVDA"]
    assert u.tools_used == [] and u.tool_calls == [] and u.token_usage is None
    assert a.provider == "anthropic" and a.model == "claude-opus-4-8" and a.effort == "high"
    assert a.tools_used == ["get_sa_feed"]
    assert a.tool_calls == [{"name": "get_sa_feed", "input": {"ticker": "NVDA"}, "result_preview": "5 articles"}]
    assert a.token_usage == {"total_tokens": 1500, "turn_count": 2}
    assert a.tickers == ["NVDA"] and a.elapsed_seconds == 3.0


def test_append_minimal_assistant_tolerates_none_json_fields(store):
    store.ensure_thread(id="th-x", title="q")
    m = store.append_message(thread_id="th-x", role="assistant", content="direct answer")
    assert m.tools_used == [] and m.tool_calls == []
    assert m.token_usage is None and m.tickers is None and m.elapsed_seconds is None and m.effort is None
    assert m.is_error is False  # default


def test_append_message_is_error_roundtrips(store):
    store.ensure_thread(id="t1", title="q")
    err = store.append_message(thread_id="t1", role="assistant", content="RuntimeError: boom", is_error=True)
    assert err.is_error is True
    ok = store.append_message(thread_id="t1", role="user", content="hi")
    assert ok.is_error is False
    # survives a fresh read (column persisted, not just on the returned object)
    assert [m.is_error for m in store.list_messages("t1")] == [True, False]


def test_append_bumps_thread_updated_at(store):
    store.ensure_thread(id="th-1", title="q", now="2026-06-14T00:00:00+00:00")
    store.append_message(thread_id="th-1", role="user", content="hi", now="2026-06-14T01:00:00+00:00")
    got = store.get_thread("th-1")
    assert got.created_at == "2026-06-14T00:00:00+00:00"
    assert got.updated_at == "2026-06-14T01:00:00+00:00"


def test_list_threads_orders_by_updated_at_desc(store):
    store.ensure_thread(id="th-a", title="first", now="2026-06-14T00:00:00+00:00")
    store.ensure_thread(id="th-b", title="second", now="2026-06-14T00:00:10+00:00")
    store.append_message(thread_id="th-a", role="user", content="later", now="2026-06-14T02:00:00+00:00")
    assert [t.title for t in store.list_threads()] == ["first", "second"]  # 'first' bumped to top


def test_list_threads_respects_limit(store):
    for i in range(5):
        store.ensure_thread(id=f"th-{i}", title=f"t{i}", now=f"2026-06-14T00:00:0{i}+00:00")
    assert len(store.list_threads(limit=3)) == 3


def test_delete_thread_removes_messages_and_history_without_touching_other_threads(store):
    from src.research_threads import build_thread_history

    store.ensure_thread(id="t1", title="first")
    store.append_message(thread_id="t1", role="user", content="q1")
    store.append_message(thread_id="t1", role="assistant", content="a1")
    store.ensure_thread(id="t2", title="second")
    store.append_message(thread_id="t2", role="user", content="q2")

    assert store.delete_thread("t1") is True

    assert store.get_thread("t1") is None
    assert store.list_messages("t1") == []
    assert build_thread_history(store, "t1") == []
    assert store.get_thread("t2").title == "second"
    assert [m.content for m in store.list_messages("t2")] == ["q2"]


def test_delete_thread_missing_is_false(store):
    assert store.delete_thread("missing") is False


def test_local_only_no_pg(store):
    assert store.db_path.endswith(".db")
    assert not hasattr(store, "_pg_conn") and not hasattr(store, "_get_conn")


def test_rename_thread_updates_title_and_timestamp_without_changing_transcript(store):
    store.ensure_thread(
        id="t1", title="Original", now="2026-07-18T01:00:00+00:00"
    )
    store.append_message(
        thread_id="t1",
        role="user",
        content="keep me",
        now="2026-07-18T01:01:00+00:00",
    )

    renamed = store.rename_thread(
        "t1", "Renamed", now="2026-07-18T02:00:00+00:00"
    )

    assert renamed is not None
    assert renamed.title == "Renamed"
    assert renamed.created_at == "2026-07-18T01:00:00+00:00"
    assert renamed.updated_at == "2026-07-18T02:00:00+00:00"
    assert [m.content for m in store.list_messages("t1")] == ["keep me"]
    assert store.ensure_thread(id="t1", title="Legacy overwrite").title == "Renamed"


def test_archive_hides_default_list_but_exact_lookup_survives(store):
    store.ensure_thread(id="t1", title="Keep", now="2026-07-18T01:00:00+00:00")

    archived = store.set_thread_archived(
        "t1", True, now="2026-07-18T02:00:00+00:00"
    )

    assert archived is not None
    assert archived.archived_at == "2026-07-18T02:00:00+00:00"
    assert store.list_threads() == []
    assert store.get_thread("t1") == archived
    assert [t.id for t in store.list_threads(include_archived=True)] == ["t1"]


def test_unarchive_restores_same_thread_and_transcript(store):
    store.ensure_thread(id="t1", title="Keep", now="2026-07-18T01:00:00+00:00")
    store.append_message(thread_id="t1", role="user", content="question")
    store.set_thread_archived("t1", True, now="2026-07-18T02:00:00+00:00")

    restored = store.set_thread_archived(
        "t1", False, now="2026-07-18T03:00:00+00:00"
    )

    assert restored is not None
    assert restored.id == "t1"
    assert restored.created_at == "2026-07-18T01:00:00+00:00"
    assert restored.archived_at is None
    assert [t.id for t in store.list_threads()] == ["t1"]
    assert [m.content for m in store.list_messages("t1")] == ["question"]


def test_archive_never_deletes_runs_or_messages(store):
    from src.research_runs import ResearchRunStore

    run_store = ResearchRunStore(store.db_path)
    store.ensure_thread(id="t1", title="Keep")
    store.append_message(thread_id="t1", role="user", content="question")
    run_store.create_run(
        id="r1",
        thread_id="t1",
        question="question",
        ticker=None,
        provider="openai",
        model="gpt-5.4-mini",
        effort="low",
        auth_mode="api_key",
        credential_id=None,
    )
    run_store.mark_terminal("r1", "succeeded")

    archived = store.set_thread_archived("t1", True)

    assert archived is not None and archived.archived_at is not None
    assert run_store.get_run("r1") is not None
    assert [m.content for m in store.list_messages("t1")] == ["question"]


def test_missing_thread_lifecycle_updates_return_none_and_create_nothing(store):
    assert store.rename_thread("missing", "No row") is None
    assert store.set_thread_archived("missing", True) is None
    assert store.set_thread_archived("missing", False) is None
    assert store.get_thread("missing") is None
    assert store.list_threads(include_archived=True) == []


def test_message_run_linkage_is_fresh_and_tolerantly_migrated(tmp_path):
    legacy_db = tmp_path / "legacy.db"
    with sqlite3.connect(legacy_db) as conn:
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
            CREATE TABLE research_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL REFERENCES research_threads(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                provider TEXT,
                model TEXT,
                effort TEXT,
                tools_used_json TEXT,
                tool_calls_json TEXT,
                token_usage_json TEXT,
                tickers_json TEXT,
                elapsed_seconds REAL,
                is_error INTEGER NOT NULL DEFAULT 0,
                personalization_json TEXT,
                created_at TEXT NOT NULL
            );
            INSERT INTO research_threads
                (id, title, created_at, updated_at)
            VALUES
                ('legacy', 'Legacy', '2026-07-18T01:00:00+00:00', '2026-07-18T01:00:00+00:00');
            INSERT INTO research_messages
                (id, thread_id, role, content, created_at)
            VALUES
                (7, 'legacy', 'assistant', 'old answer', '2026-07-18T01:01:00+00:00');
            """
        )
        before = conn.execute(
            "SELECT id, thread_id, role, content, created_at FROM research_messages"
        ).fetchall()

    migrated = ResearchThreadStore(legacy_db)

    with sqlite3.connect(legacy_db) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(research_messages)")}
        foreign_keys = conn.execute("PRAGMA foreign_key_list(research_messages)").fetchall()
        after = conn.execute(
            "SELECT id, thread_id, role, content, created_at FROM research_messages"
        ).fetchall()
    assert before == after
    assert {"run_id", "error_code"} <= columns
    assert any(
        row[2] == "research_runs"
        and row[3] == "run_id"
        and row[6].upper() == "SET NULL"
        for row in foreign_keys
    )
    legacy_message = migrated.list_messages("legacy")[0]
    assert legacy_message.run_id is None
    assert legacy_message.error_code is None

    from src.research_runs import ResearchRunStore

    fresh_db = tmp_path / "fresh.db"
    fresh = ResearchThreadStore(fresh_db)
    runs = ResearchRunStore(fresh_db)
    fresh.ensure_thread(id="fresh", title="Fresh")
    runs.create_run(
        id="run-fresh",
        thread_id="fresh",
        question="question",
        ticker=None,
        provider="anthropic",
        model="claude-sonnet-4-6",
        effort="high",
        auth_mode="api_key",
        credential_id=None,
    )
    linked = fresh.append_message(
        thread_id="fresh",
        role="assistant",
        content="timed out",
        run_id="run-fresh",
        error_code="model_timeout",
        is_error=True,
    )
    assert linked.run_id == "run-fresh"
    assert linked.error_code == "model_timeout"

    with sqlite3.connect(fresh_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM research_runs WHERE id = 'run-fresh'")
    surviving = fresh.list_messages("fresh")
    assert len(surviving) == 1
    assert surviving[0].run_id is None
    assert surviving[0].error_code == "model_timeout"


# --- C-2c: build_thread_history — provider-neutral prompt-context builder ----
# Policy plan (AI_RESEARCH_CONTEXT_MEMORY_PLAN.md §4/§5): full_thread default,
# no silent truncation, completed non-error turns only, {role,content} only.
def test_build_thread_history_full_thread_roundtrips_role_content_in_order(store):
    from src.research_threads import build_thread_history

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="最近 SA 對 SMCI 的焦點？", tickers=["SMCI"])
    store.append_message(thread_id="t1", role="assistant", content="SMCI: 3 看多 2 看空。", tool_calls=[{"name": "get_sa_feed"}], token_usage={"total_tokens": 9})
    hist = build_thread_history(store, "t1")  # default policy = full_thread
    # {role, content} ONLY — no tool_calls/token_usage/tickers/metadata leak into context
    assert hist == [
        {"role": "user", "content": "最近 SA 對 SMCI 的焦點？"},
        {"role": "assistant", "content": "SMCI: 3 看多 2 看空。"},
    ]


def test_build_thread_history_skips_error_turns(store):
    from src.research_threads import build_thread_history

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="q1")
    store.append_message(thread_id="t1", role="assistant", content="RuntimeError: db down", is_error=True)
    store.append_message(thread_id="t1", role="user", content="q2")
    store.append_message(thread_id="t1", role="assistant", content="real answer")
    hist = build_thread_history(store, "t1")
    assert hist == [
        {"role": "user", "content": "q1"},      # the error assistant is skipped
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "real answer"},
    ]


def test_build_thread_history_retry_excludes_last_failed_pair_only(store):
    from src.research_threads import build_thread_history

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="q1")
    store.append_message(thread_id="t1", role="assistant", content="a1")
    store.append_message(thread_id="t1", role="user", content="failed q")
    store.append_message(thread_id="t1", role="assistant", content="RuntimeError: db down", is_error=True)

    hist = build_thread_history(store, "t1", exclude_last_failed_pair=True)

    assert hist == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]


def test_build_thread_history_retry_excludes_last_max_turns_pair(store):
    from src.research_threads import MAX_TOOL_CALLS_SENTINEL, build_thread_history

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="q1")
    store.append_message(thread_id="t1", role="assistant", content="a1")
    store.append_message(thread_id="t1", role="user", content="too broad")
    store.append_message(thread_id="t1", role="assistant", content=MAX_TOOL_CALLS_SENTINEL)

    hist = build_thread_history(store, "t1", exclude_last_failed_pair=True)

    assert hist == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]


def test_build_thread_history_retry_does_not_exclude_successful_tail(store):
    from src.research_threads import build_thread_history

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="q1")
    store.append_message(thread_id="t1", role="assistant", content="a1")

    assert build_thread_history(store, "t1", exclude_last_failed_pair=True) == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]


def test_build_thread_history_skips_empty_content(store):
    from src.research_threads import build_thread_history

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="q1")
    store.append_message(thread_id="t1", role="assistant", content="")  # empty answer → not useful context
    assert build_thread_history(store, "t1") == [{"role": "user", "content": "q1"}]


def test_build_thread_history_no_history_policy_and_empty_thread(store):
    from src.research_threads import build_thread_history

    store.ensure_thread(id="t1", title="q")
    store.append_message(thread_id="t1", role="user", content="q1")
    assert build_thread_history(store, "t1", policy="no_history") == []  # explicit opt-out
    assert build_thread_history(store, "nope") == []  # missing thread → empty, no error


def test_build_thread_history_rejects_unimplemented_policy(store):
    from src.research_threads import build_thread_history

    # recent_messages / summary_plus_recent are reserved keys (plan §5) but must
    # NOT be silently honored as a cap in this cut — raise so it can't ship implicitly.
    with pytest.raises(ValueError):
        build_thread_history(store, "t1", policy="recent_messages")


def test_message_personalization_round_trip(tmp_path):
    store = ResearchThreadStore(tmp_path / "threads.db")
    store.ensure_thread(id="tp", title="t")
    trace = {
        "profile_active": True,
        "assistant_stance": "complementary",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
    }
    store.append_message(thread_id="tp", role="assistant", content="a", personalization=trace)
    store.append_message(thread_id="tp", role="assistant", content="b")  # old-style write
    msgs = store.list_messages("tp")
    assert msgs[0].personalization == trace
    assert msgs[1].personalization is None
