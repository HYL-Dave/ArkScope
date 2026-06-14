"""C-2b: ResearchThreadStore — local persistence for AI 研究 threads/messages.

Mirrors the shipped CardRunStore (src/card_runs.py): same local profile_state.db
family, NEVER the remote PG. Thread ids are CLIENT-OWNED (stable unique strings
generated at 新對話), so the client (reducer) and server agree on identity with
no mapping/rekey — ensure_thread is idempotent (the per-turn stream hook calls
it every turn). Column names match the C-2a in-memory DTO (spec §6a) so
persistence is a pure write-through. Tested directly, no FastAPI/TestClient.
"""

from __future__ import annotations

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
        provider="anthropic", model="claude-opus-4-8",
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
    assert a.provider == "anthropic" and a.model == "claude-opus-4-8"
    assert a.tools_used == ["get_sa_feed"]
    assert a.tool_calls == [{"name": "get_sa_feed", "input": {"ticker": "NVDA"}, "result_preview": "5 articles"}]
    assert a.token_usage == {"total_tokens": 1500, "turn_count": 2}
    assert a.tickers == ["NVDA"] and a.elapsed_seconds == 3.0


def test_append_minimal_assistant_tolerates_none_json_fields(store):
    store.ensure_thread(id="th-x", title="q")
    m = store.append_message(thread_id="th-x", role="assistant", content="direct answer")
    assert m.tools_used == [] and m.tool_calls == []
    assert m.token_usage is None and m.tickers is None and m.elapsed_seconds is None


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


def test_local_only_no_pg(store):
    assert store.db_path.endswith(".db")
    assert not hasattr(store, "_pg_conn") and not hasattr(store, "_get_conn")
