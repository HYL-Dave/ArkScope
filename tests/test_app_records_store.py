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


# --- 1b: factory routing (default-off) + DAL toggle ---------------------------------

from src.app_records_store import (
    USE_LOCAL_RECORDS_KEY, ENV_USE_LOCAL_RECORDS,
    get_app_records_store, resolve_profile_state_db_path,
)


class _FakeBackend:
    """Stand-in for dal._backend (PG/File) — distinct from the local store."""
    def insert_report(self, **k): return -1   # sentinel: came from PG path
    def query_reports(self, **k):
        import pandas as pd
        return pd.DataFrame()


class _FakeDal:
    def __init__(self, local: bool, backend=None, base=None):
        self._local = local
        self._backend = backend
        self._base = base
    def _local_records_enabled(self): return self._local


def test_factory_explicit_false_still_returns_local_store(tmp_path, monkeypatch):
    # PG-exit closeout: explicit false is provenance only — records never route back
    # to the PG backend (the three PG app-record tables are archive-only).
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    store = get_app_records_store(_FakeDal(local=False, backend=_FakeBackend()))
    assert isinstance(store, AppRecordsLocalStore)


def test_factory_on_returns_local_store(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    store = get_app_records_store(_FakeDal(local=True, backend=_FakeBackend()))
    assert isinstance(store, AppRecordsLocalStore)


def test_create_store_makes_missing_parent_dirs(tmp_path):
    # Fresh-profile safety (PG-exit closeout): default-create store must mkdir absent
    # parents — a brand-new base without data/ must not OperationalError at construction.
    path = tmp_path / "fresh" / "data" / "profile_state.db"
    store = AppRecordsLocalStore(path)
    mid = store.insert_memory(title="t", content="c", category="note",
                              tickers=None, tags=None, importance=5, source="test")
    assert isinstance(mid, int)
    assert path.exists()


def test_factory_toggleless_dal_routes_local(tmp_path, monkeypatch):
    # A dal lacking the legacy toggle (older/test double) also gets the local store —
    # fresh/reset profiles must never strand on the retired PG app-record path.
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    class _Bare:  # no _local_records_enabled (older/test double)
        _backend = _FakeBackend()
    assert isinstance(get_app_records_store(_Bare()), AppRecordsLocalStore)


def test_resolver_no_api_import_and_env_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", "/x/custom.db")
    assert resolve_profile_state_db_path(None) == "/x/custom.db"
    monkeypatch.delenv("ARKSCOPE_PROFILE_DB", raising=False)
    assert resolve_profile_state_db_path(_FakeDal(local=True, base=str(tmp_path))) == \
        str(tmp_path / "data" / "profile_state.db")
    # gate #3: the store module must not import the API layer
    import src.app_records_store as mod, inspect
    assert "src.api" not in inspect.getsource(mod)


def test_dal_local_records_default_is_local(tmp_path, monkeypatch):
    # PG-exit closeout: unset AND explicit false both resolve local — matches the
    # batch-2 collapse semantics of use_local_market / use_local_macro / use_local_job_runs.
    from src.tools.data_access import DataAccessLayer
    monkeypatch.delenv(ENV_USE_LOCAL_RECORDS, raising=False)
    # hermetic: empty tmp profile DB so the host's persisted use_local_records=true
    # cannot leak in — "unset" must mean truly unset (macro-toggle a5b0496 lesson)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "empty_profile_state.db"))
    dal = DataAccessLayer()
    assert dal._local_records_enabled() is True
    monkeypatch.setenv(ENV_USE_LOCAL_RECORDS, "false")
    assert dal._local_records_enabled() is True


def test_end_to_end_save_report_routes_local_when_on(tmp_path, monkeypatch):
    # toggle on → save_report's insert lands in the LOCAL store, readable via list_reports.
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setenv(ENV_USE_LOCAL_RECORDS, "1")
    from src.tools.data_access import DataAccessLayer
    from src.tools import report_tools
    dal = DataAccessLayer(base_path=str(tmp_path))
    rid = AppRecordsLocalStore(tmp_path / "profile_state.db")  # ensure schema exists
    # route an insert through the tool layer
    out = report_tools.save_report(dal, title="T", content="# body", tickers=["AFRM"],
                                   report_type="entry_analysis", summary="s")
    # the report id should come from the LOCAL store (not the -1 PG sentinel / not None)
    listed = report_tools.list_reports(dal, days=3650)
    assert any(r["title"] == "T" for r in listed), "local-routed report not found via list_reports"


def test_gate4_on_empty_local_is_honest_no_crash(tmp_path, monkeypatch):
    # gate #4: toggle ON + empty local store → reads are honest-empty, never crash, and the
    # tools' existing markdown fallback still runs (no markdown files here → []).
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setenv(ENV_USE_LOCAL_RECORDS, "1")
    from src.tools.data_access import DataAccessLayer
    from src.tools import report_tools, memory_tools
    dal = DataAccessLayer(base_path=str(tmp_path))
    assert report_tools.list_reports(dal, days=30) == []          # honest empty, no crash
    assert isinstance(memory_tools.recall_memories(dal, query="x"), (list, str))
    got = report_tools.get_report(dal, report_id=999999)          # absent id, pre-migration
    assert got is None or isinstance(got, (dict, str))            # honest, not a crash


# --- 1c-api-fix: no-create read semantics -------------------------------------------

def test_create_false_does_not_materialize_db(tmp_path):
    # fix #1: a create=False store over an ABSENT path must NOT create the file, and reads
    # return empty — so /migration/preview never materializes profile_state.db.
    path = tmp_path / "absent.db"
    s = AppRecordsLocalStore(path, create=False)
    assert s.count("research_reports") == 0 and s.raw_rows("agent_memories") == []
    assert not path.exists(), "preview/no-create store must not create the DB file"
