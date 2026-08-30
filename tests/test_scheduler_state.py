"""Durable per-source scheduling state in ``profile_state.db``.

Attempts, outcomes, errors, continuations, and result summaries survive process
restarts. ``partial`` is a first-class status.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from src.scheduler_state import SchedulerStateStore


@pytest.fixture()
def store(tmp_path):
    return SchedulerStateStore(tmp_path / "profile_state.db")


def _dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_record_attempt_then_outcome(store):
    store.record_attempt("polygon_news", _dt("2026-06-24T10:00:00"))
    row = store.get("polygon_news")
    assert row["last_attempt"] == "2026-06-24T10:00:00+0000"
    assert row["last_status"] == "running"          # attempt → running until outcome
    store.record_outcome("polygon_news", status="succeeded", error=None,
                          result={"rows_added": 5})
    row = store.get("polygon_news")
    assert row["last_status"] == "succeeded" and row["last_error"] is None
    assert row["last_attempt"] == "2026-06-24T10:00:00+0000"   # outcome preserves last_attempt
    assert row["last_result"] == {"rows_added": 5}


def test_outcome_records_and_then_clears_error(store):
    store.record_attempt("ibkr_prices", _dt("2026-06-24T10:00:00"))
    store.record_outcome("ibkr_prices", status="failed", error="gateway down", result=None)
    assert store.get("ibkr_prices")["last_error"] == "gateway down"
    # a later successful run CLEARS the stale error
    store.record_attempt("ibkr_prices", _dt("2026-06-24T11:00:00"))
    store.record_outcome("ibkr_prices", status="succeeded", error=None, result={"ok": True})
    row = store.get("ibkr_prices")
    assert row["last_status"] == "succeeded" and row["last_error"] is None


def test_partial_status_and_continuation_roundtrip(store):
    # partial is a LOCAL-only status; continuation carries the remaining scope (v1.3).
    store.record_attempt("ibkr_news", _dt("2026-06-24T10:00:00"))
    store.record_outcome("ibkr_news", status="partial", error=None,
                         result={"done": 20}, continuation={"deferred": ["NVDA", "TSLA"]})
    row = store.get("ibkr_news")
    assert row["last_status"] == "partial"
    assert row["continuation"] == {"deferred": ["NVDA", "TSLA"]}
    # a clean run clears the continuation
    store.record_outcome("ibkr_news", status="succeeded", error=None, result={}, continuation=None)
    assert store.get("ibkr_news")["continuation"] is None


def test_last_attempts_for_seeding(store):
    store.record_attempt("a", _dt("2026-06-24T10:00:00"))
    store.record_attempt("b", _dt("2026-06-23T09:00:00"))
    la = store.last_attempts()
    assert la["a"] == _dt("2026-06-24T10:00:00") and la["b"] == _dt("2026-06-23T09:00:00")
    assert all(v.tzinfo is not None for v in la.values())   # tz-aware (for interval math)


def test_all_and_missing(store):
    assert store.get("nope") is None
    assert store.all() == {}
    store.record_attempt("x", _dt("2026-06-24T10:00:00"))
    assert set(store.all()) == {"x"}


def test_attempt_does_not_clobber_prior_outcome_fields(store):
    store.record_attempt("s", _dt("2026-06-24T10:00:00"))
    store.record_outcome("s", status="failed", error="boom", result={"e": 1})
    # a NEW attempt sets running + new last_attempt but keeps last_error/last_result until the
    # next outcome (so the UI still shows why the previous run failed while this one runs).
    store.record_attempt("s", _dt("2026-06-24T12:00:00"))
    row = store.get("s")
    assert row["last_attempt"] == "2026-06-24T12:00:00+0000"
    assert row["last_status"] == "running"
    assert row["last_error"] == "boom"          # preserved until the new outcome


def test_reconcile_interrupted_running_marks_terminal(store):
    store.record_attempt("ibkr_news", _dt("2026-06-24T10:00:00"))
    store.record_outcome("polygon_news", status="succeeded", error=None, result={"ok": True})
    store.record_attempt("finnhub_news", _dt("2026-06-24T11:00:00"))

    changed = store.reconcile_interrupted_running(error="sidecar restarted before run finished")

    assert changed == ["finnhub_news", "ibkr_news"]
    ibkr = store.get("ibkr_news")
    assert ibkr["last_status"] == "failed"
    assert ibkr["last_error"] == "sidecar restarted before run finished"
    assert ibkr["last_result"]["status"] == "failed"
    assert "sidecar restarted" in ibkr["last_result"]["error"]
    assert store.get("polygon_news")["last_status"] == "succeeded"


def test_imports_with_declared_local_dependencies():
    import src.scheduler_state as mod
    assert mod.SchedulerStateStore is SchedulerStateStore


def test_existing_connection_schema_helper_is_idempotent():
    from src.scheduler_state import ensure_scheduler_state_schema

    conn = sqlite3.connect(":memory:")
    try:
        ensure_scheduler_state_schema(conn)
        ensure_scheduler_state_schema(conn)
        row = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='scheduler_state'"
        ).fetchone()
        assert row is not None
        assert "last_result" in str(row[0])
    finally:
        conn.close()
