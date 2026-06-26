"""PG-exit 1c-core — PG→local app-records migration (offline; fake PG source, no live PG).

Covers the 5 gates: id-preserving (PG id N → local get_report(N)); dry-run preview separate from
apply; collision guard (empty-only / idempotent skip / same-id-diff-content FAIL); backup before
write; explicit apply. Scope = reports/memories/agent_queries (NOT signals).
"""

from __future__ import annotations

import os

import pytest

from src.app_records_store import AppRecordsLocalStore
from src.app_records_migrate import apply_migration, preview_migration


class _FakePG:
    """Stand-in for the live PG read side — full row dicts, same columns as the local schema."""
    def __init__(self, reports=None, memories=None, queries=None):
        self._r = reports or []
        self._m = memories or []
        self._q = queries or []
    def fetch_reports(self): return self._r
    def fetch_memories(self): return self._m
    def fetch_agent_queries(self): return self._q


def _report(id, title="R", created="2026-06-20T10:00:00", summary="s", file_path=None):
    return {"id": id, "title": title, "tickers": '["AFRM"]', "report_type": "entry_analysis",
            "summary": summary, "conclusion": "BUY", "confidence": 0.8, "provider": "anthropic",
            "model": "claude-opus-4-8", "file_path": file_path, "tools_used": '["get_ticker_news"]',
            "tool_calls": 3, "duration_seconds": 1.0, "tokens_in": 10, "tokens_out": 20,
            "created_at": created}


def _memory(id, title="M", created="2026-06-20T10:00:00", content="body"):
    return {"id": id, "title": title, "content": content, "category": "insight",
            "tickers": '["AFRM"]', "tags": '["earnings"]', "source": "agent_auto",
            "provider": "anthropic", "model": "x", "importance": 8, "file_path": None,
            "expires_at": None, "created_at": created}


def _query(id, q="what is AFRM?", created="2026-06-20T10:00:00"):
    return {"id": id, "question": q, "answer": "fintech", "provider": "openai", "model": "gpt-5.4",
            "tools_used": '["get_ticker_news"]', "duration_ms": 100, "tokens_in": 5,
            "tokens_out": 7, "created_at": created}


@pytest.fixture()
def local(tmp_path):
    return AppRecordsLocalStore(tmp_path / "profile_state.db")


# --- gate #2: id-preserving ---------------------------------------------------------

def test_apply_preserves_pg_ids(local):
    src = _FakePG(reports=[_report(42, title="link-target")], memories=[_memory(7)],
                  queries=[_query(99)])
    res = apply_migration(src, local, backup=False)
    assert res["tables"]["research_reports"]["inserted"] == 1
    # PG report id 42 → local readable at id 42 (so ai_card_runs.saved_report_id=42 still resolves)
    meta = local.get_report_metadata(42)
    assert meta is not None and meta["title"] == "link-target" and meta["id"] == 42
    assert local.count("agent_memories") == 1 and local.count("agent_queries") == 1
    # created_at preserved verbatim
    assert local.query_reports(days=3650).iloc[0]["created_at"] == "2026-06-20T10:00:00"


# --- gate #5: dry-run preview separate from apply -----------------------------------

def test_preview_is_readonly_and_classifies(local, tmp_path):
    src = _FakePG(reports=[_report(1), _report(2, file_path="data/reports/missing.md")])
    prev = preview_migration(src, local)
    assert prev["would_apply"] is True
    t = prev["tables"]["research_reports"]
    assert t["pg_count"] == 2 and t["local_count"] == 0 and t["max_pg_id"] == 2
    assert set(t["to_insert"]) == {1, 2} and t["conflicts"] == []
    assert "data/reports/missing.md" in t["missing_files"]   # gate: surfaces missing files
    assert local.count("research_reports") == 0              # preview wrote nothing


# --- gate #3: collision guard -------------------------------------------------------

def test_idempotent_rerun_skips_same_content(local):
    src = _FakePG(reports=[_report(1)], memories=[_memory(1)], queries=[_query(1)])
    apply_migration(src, local, backup=False)
    res2 = apply_migration(src, local, backup=False)   # re-run → all idempotent skips
    assert res2["tables"]["research_reports"] == {"inserted": 0, "skipped": 1}
    assert local.count("research_reports") == 1        # no duplicate


def test_same_id_different_content_refuses_before_any_write(local):
    apply_migration(_FakePG(reports=[_report(1, title="original", summary="a")]), local, backup=False)
    apply_migration(_FakePG(memories=[_memory(5)]), local, backup=False)  # add a memory too
    # now PG claims id 1 is a DIFFERENT report → must refuse, write nothing new
    bad = _FakePG(reports=[_report(1, title="DIFFERENT", summary="b"), _report(2, title="new")])
    with pytest.raises(RuntimeError, match="conflict"):
        apply_migration(bad, local, backup=False)
    assert local.get_report_metadata(1)["title"] == "original"   # unchanged
    assert local.get_report_metadata(2) is None                  # id 2 NOT written (refused before write)


def test_partial_overlap_inserts_only_new_ids(local):
    apply_migration(_FakePG(reports=[_report(1)]), local, backup=False)
    res = apply_migration(_FakePG(reports=[_report(1), _report(2), _report(3)]), local, backup=False)
    assert res["tables"]["research_reports"] == {"inserted": 2, "skipped": 1}
    assert {int(r) for r in local.query_reports(days=3650)["id"]} == {1, 2, 3}


# --- gate #4: backup before write ---------------------------------------------------

def test_apply_backs_up_before_write(local, tmp_path):
    apply_migration(_FakePG(reports=[_report(1)]), local, backup=False)  # seed so db file exists
    src = _FakePG(reports=[_report(1), _report(2)])
    res = apply_migration(src, local, backup=True, now_stamp="20260626T000000Z")
    assert res["backup"] and os.path.exists(res["backup"])
    # the backup is a real SQLite snapshot taken BEFORE this apply (has only the seeded id 1)
    pre = AppRecordsLocalStore(res["backup"])
    assert pre.count("research_reports") == 1


# --- scope: signals NOT migrated ----------------------------------------------------

def test_migrator_scope_excludes_signals():
    import src.app_records_migrate as mig
    tables = {p[0] for p in mig._PLAN}
    assert tables == {"research_reports", "agent_memories", "agent_queries"}
    assert "signals" not in tables


# --- 1c-core-fix regression tests ---------------------------------------------------

def test_full_field_difference_is_conflict_not_skip(local):
    # fix #1: same id + same title/created/summary/conclusion/file_path but DIFFERENT
    # provider/model/tokens → must be a CONFLICT (the old 5-field hash falsely skipped it).
    apply_migration(_FakePG(reports=[_report(1)]), local, backup=False)
    base = _report(1)  # identical hash-subset fields...
    diff = {**base, "provider": "openai", "model": "gpt-5.4", "tokens_in": 9999, "confidence": 0.1}
    prev = preview_migration(_FakePG(reports=[diff]), local)
    assert prev["tables"]["research_reports"]["conflicts"] == [1]   # caught now
    assert prev["would_apply"] is False
    with pytest.raises(RuntimeError, match="conflict"):
        apply_migration(_FakePG(reports=[diff]), local, backup=False)


def test_apply_raises_on_insert_failure_no_silent_partial(local, monkeypatch):
    # fix #2: an insert that returns None (sqlite error) or a wrong id must ABORT, not count.
    src = _FakePG(reports=[_report(1), _report(2)])
    real_insert = local.insert_report
    calls = {"n": 0}
    def flaky(**k):
        calls["n"] += 1
        return real_insert(**k) if calls["n"] == 1 else None  # 2nd insert "fails"
    monkeypatch.setattr(local, "insert_report", flaky)
    with pytest.raises(RuntimeError, match="write failed"):
        apply_migration(src, local, backup=False)


def test_apply_uses_single_source_snapshot(local):
    # fix #3: a source whose fetch returns different rows each call must not skew apply —
    # apply reads the source ONCE. Track fetch counts.
    class _MutatingPG:
        def __init__(self):
            self.report_fetches = 0
        def fetch_reports(self):
            self.report_fetches += 1
            return [_report(1)] if self.report_fetches == 1 else [_report(1), _report(2)]
        def fetch_memories(self): return []
        def fetch_agent_queries(self): return []
    src = _MutatingPG()
    res = apply_migration(src, local, backup=False)
    assert src.report_fetches == 1                       # snapshot: fetched once, not per-phase
    assert res["tables"]["research_reports"]["inserted"] == 1
    assert local.count("research_reports") == 1          # only the snapshot's single row


# --- 1c-api: PgAppRecordsSource (fake conn) + routes (direct handler) ----------------

class _FakeCursor:
    def __init__(self, rows): self._rows = rows
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql): self._sql = sql
    def fetchall(self): return self._rows

class _FakeConn:
    def __init__(self, rows_by_sql): self._rows_by_sql = rows_by_sql
    def cursor(self, cursor_factory=None):
        # pick rows by which table the SQL hits
        for key, rows in self._rows_by_sql.items():
            if key in self._last_sql_table:
                return _FakeCursor(rows)
        return _FakeCursor([])
    # crude: route by table name in the SELECT
    def cursor(self, cursor_factory=None):  # noqa: F811
        return _TableCursor(self._rows_by_sql)

class _TableCursor:
    def __init__(self, rows_by_table): self._rows_by_table = rows_by_table; self._rows = []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql):
        for tbl, rows in self._rows_by_table.items():
            if f"FROM {tbl}" in sql:
                self._rows = rows; return
        self._rows = []
    def fetchall(self): return self._rows

class _FakePgBackend:
    def __init__(self, rows_by_table): self._rows_by_table = rows_by_table
    def _get_conn(self): return _FakeConn(self._rows_by_table)


def test_pg_source_maps_tables(monkeypatch):
    from src.app_records_migrate import PgAppRecordsSource
    monkeypatch.setitem(__import__("sys").modules, "psycopg2.extras",
                        type("M", (), {"RealDictCursor": object})())
    be = _FakePgBackend({
        "research_reports": [{"id": 1, "title": "r"}],
        "agent_memories": [{"id": 2, "title": "m"}],
        "agent_queries": [{"id": 3, "question": "q"}],
    })
    src = PgAppRecordsSource(be)
    assert src.available is True
    assert src.fetch_reports()[0]["id"] == 1
    assert src.fetch_memories()[0]["id"] == 2
    assert src.fetch_agent_queries()[0]["id"] == 3


def test_pg_source_unavailable_without_get_conn():
    from src.app_records_migrate import PgAppRecordsSource
    assert PgAppRecordsSource(object()).available is False
    assert PgAppRecordsSource(None).available is False


def test_route_preview_and_apply(tmp_path, monkeypatch):
    import src.api.routes.app_records as routes
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)

    class _Dal:
        _base = str(tmp_path)
        _backend = _FakePgBackend({
            "research_reports": [dict(_report(1), tickers=["AFRM"], tools_used=["t"])],
            "agent_memories": [], "agent_queries": [],
        })
    dal = _Dal()
    prev = routes.migration_preview(dal=dal)
    assert prev["would_apply"] is True
    assert prev["tables"]["research_reports"]["pg_count"] == 1
    applied = routes.migration_apply(dal=dal)
    assert applied["tables"]["research_reports"]["inserted"] == 1
    assert AppRecordsLocalStore(tmp_path / "profile_state.db").get_report_metadata(1)["id"] == 1


def test_route_409_without_pg():
    import src.api.routes.app_records as routes
    from fastapi import HTTPException
    class _NoPgDal:
        _base = None
        _backend = object()  # no _get_conn
    with pytest.raises(HTTPException) as e:
        routes.migration_preview(dal=_NoPgDal())
    assert e.value.status_code == 409
