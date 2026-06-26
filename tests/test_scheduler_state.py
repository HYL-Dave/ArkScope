"""Scheduler-hardening v1.2 — local scheduler_state store (profile_state.db; no PG).

Durable per-source scheduler state (last_attempt / last_status / last_error / continuation /
last_result) so restart continuity + the failure surface no longer depend on PG job_runs.
`partial` is a first-class LOCAL status (decision: do NOT force it into PG job_runs' enum).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.scheduler_state import SchedulerStateStore


@pytest.fixture()
def store(tmp_path):
    return SchedulerStateStore(tmp_path / "profile_state.db")


def _dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_record_attempt_then_outcome(store):
    store.record_attempt("price_backfill", _dt("2026-06-24T10:00:00"))
    row = store.get("price_backfill")
    assert row["last_attempt"] == "2026-06-24T10:00:00+0000"
    assert row["last_status"] == "running"          # attempt → running until outcome
    store.record_outcome("price_backfill", status="succeeded", error=None,
                          result={"rows_added": 5})
    row = store.get("price_backfill")
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
    store.record_attempt("price_backfill", _dt("2026-06-24T10:00:00"))
    store.record_outcome("price_backfill", status="partial", error=None,
                         result={"done": 20}, continuation={"deferred": ["NVDA", "TSLA"]})
    row = store.get("price_backfill")
    assert row["last_status"] == "partial"
    assert row["continuation"] == {"deferred": ["NVDA", "TSLA"]}
    # a clean run clears the continuation
    store.record_outcome("price_backfill", status="succeeded", error=None, result={}, continuation=None)
    assert store.get("price_backfill")["continuation"] is None


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


def test_no_pg_dependency():
    import src.scheduler_state as mod
    assert not hasattr(mod, "psycopg2")
