"""PG-exit Slice 1a — local app-records store (reports / memories / agent_queries).

These are the PG-only, user/agent-authored, NOT-regenerable records. This store is the local
twin of db_backend's app-record surface, over profile_state.db, returning the SAME shapes
(DataFrames with list-typed tickers/tags; created_at as 'YYYY-MM-DDTHH:MM:SS' to match the PG
TO_CHAR). Hermetic — temp SQLite, no PG, no psycopg2. Slice 1a is the store only: no DAL
wiring, no migration (those are 1b / 1c).
"""

from __future__ import annotations

import pytest

from src.app_records_store import AppRecordsLocalStore

# column parity with db_backend (the contract report_tools / memory tools consume)
_REPORT_COLS = ["id", "title", "tickers", "report_type", "summary", "conclusion",
                "confidence", "model", "file_path", "tool_calls", "duration_seconds", "created_at"]
_MEM_COLS = ["id", "title", "content", "category", "tickers", "tags", "importance", "source", "created_at"]
_MEM_META_COLS = ["id", "title", "category", "tickers", "tags", "importance", "created_at"]


@pytest.fixture()
def store(tmp_path):
    return AppRecordsLocalStore(tmp_path / "profile_state.db")


# --- reports -----------------------------------------------------------------------

def test_report_insert_query_roundtrip(store):
    rid = store.insert_report(
        title="AFRM entry", tickers=["AFRM", "NVDA"], report_type="entry_analysis",
        summary="buy the dip", conclusion="BUY", confidence=0.8, provider="anthropic",
        model="claude-opus-4-8", file_path="data/reports/x.md", tools_used=["get_ticker_news"],
        tool_calls=3, duration_seconds=12.5, tokens_in=100, tokens_out=200,
        created_at="2026-06-20T10:00:00")
    assert isinstance(rid, int)
    df = store.query_reports()
    assert list(df.columns) == _REPORT_COLS
    row = df.iloc[0]
    assert row["title"] == "AFRM entry" and row["conclusion"] == "BUY"
    assert row["tickers"] == ["AFRM", "NVDA"]           # JSON text → list parity
    assert row["created_at"] == "2026-06-20T10:00:00"   # TO_CHAR format preserved


def test_report_filters_ticker_type_days_limit(store):
    store.insert_report(title="a", tickers=["AAPL"], report_type="entry_analysis",
                        summary="", created_at="2026-06-20T10:00:00")
    store.insert_report(title="b", tickers=["NVDA"], report_type="sector_review",
                        summary="", created_at="2026-06-19T10:00:00")
    store.insert_report(title="old", tickers=["AAPL"], report_type="entry_analysis",
                        summary="", created_at="2026-01-01T10:00:00")
    assert [r for r in store.query_reports(ticker="AAPL", days=3650)["title"]] == ["a", "old"]
    assert list(store.query_reports(report_type="sector_review", days=3650)["title"]) == ["b"]
    # days window excludes the Jan report relative to the newest
    titles_30 = list(store.query_reports(ticker="AAPL", days=30, today="2026-06-21")["title"])
    assert titles_30 == ["a"]
    assert len(store.query_reports(days=3650, limit=1)) == 1


def test_report_query_empty_has_parity_columns(store):
    df = store.query_reports()
    assert df.empty and list(df.columns) == _REPORT_COLS


def test_report_metadata_full_dict(store):
    rid = store.insert_report(title="t", tickers=["AFRM"], report_type="x", summary="s",
                              tools_used=["a", "b"], tokens_in=5, tokens_out=7,
                              created_at="2026-06-20T10:00:00")
    meta = store.get_report_metadata(rid)
    assert meta["tickers"] == ["AFRM"] and meta["tools_used"] == ["a", "b"]
    assert meta["tokens_in"] == 5 and meta["tokens_out"] == 7
    assert store.get_report_metadata(999999) is None


# --- memories ----------------------------------------------------------------------

def test_memory_insert_query_roundtrip(store):
    mid = store.insert_memory(title="AFRM thesis", content="affirm grows", category="insight",
                              tickers=["AFRM"], tags=["earnings", "entry"], importance=8,
                              source="agent_auto", created_at="2026-06-20T10:00:00")
    assert isinstance(mid, int)
    df = store.query_memories()
    assert list(df.columns) == _MEM_COLS
    row = df.iloc[0]
    assert row["tickers"] == ["AFRM"] and row["tags"] == ["earnings", "entry"]
    assert row["content"] == "affirm grows"


def test_memory_search_category_importance_order(store):
    store.insert_memory(title="alpha", content="affirm whipsaw", category="insight",
                        importance=3, created_at="2026-06-20T10:00:00")
    store.insert_memory(title="beta", content="affirm trend strong", category="insight",
                        importance=9, created_at="2026-06-20T09:00:00")
    store.insert_memory(title="gamma", content="unrelated", category="note",
                        importance=5, created_at="2026-06-20T08:00:00")
    # substring search over title+content (local FTS simplification)
    hits = list(store.query_memories(query="affirm")["title"])
    assert set(hits) == {"alpha", "beta"} and "gamma" not in hits
    # no query → importance DESC then date
    ordered = list(store.query_memories(category="insight")["title"])
    assert ordered == ["beta", "alpha"]


def test_memory_ticker_and_tag_overlap_filter(store):
    store.insert_memory(title="a", content="x", category="note", tickers=["AAPL"],
                        tags=["t1"], created_at="2026-06-20T10:00:00")
    store.insert_memory(title="b", content="y", category="note", tickers=["NVDA"],
                        tags=["t2"], created_at="2026-06-20T10:00:00")
    assert list(store.query_memories(tickers=["AAPL"])["title"]) == ["a"]
    assert list(store.query_memories(tags=["t2"])["title"]) == ["b"]


def test_memory_meta_excludes_content_and_delete(store):
    mid = store.insert_memory(title="m", content="body", category="note",
                              file_path="data/agent_memory/m.md", created_at="2026-06-20T10:00:00")
    meta = store.list_memories_meta()
    assert list(meta.columns) == _MEM_META_COLS and "content" not in meta.columns
    assert store.delete_memory(mid) == "data/agent_memory/m.md"
    assert store.query_memories().empty


# --- agent_queries (write-only log, mirrors db_backend) -----------------------------

def test_agent_query_insert(store):
    qid = store.insert_agent_query(question="what is AFRM?", answer="a fintech",
                                   provider="openai", model="gpt-5.4", tools_used=["get_ticker_news"],
                                   duration_ms=1200, tokens_in=50, tokens_out=80,
                                   created_at="2026-06-20T10:00:00")
    assert isinstance(qid, int)
    assert store.count_agent_queries() == 1


# --- hermetic / no-PG --------------------------------------------------------------

def test_no_pg_dependency():
    import src.app_records_store as mod
    assert not hasattr(mod, "psycopg2")


def test_absent_db_query_is_empty_not_crash(tmp_path):
    # a store pointed at a path whose parent exists but file doesn't → schema created on init;
    # queries return empty parity frames, never raise.
    s = AppRecordsLocalStore(tmp_path / "fresh.db")
    assert s.query_reports().empty and s.query_memories().empty
    assert s.get_report_metadata(1) is None
