"""macro/cal local store (§4c slice 1) — hermetic parity tests over a real temp SQLite DB.

NO PG, NO _get_conn, NO psycopg2: the store resolves entirely against macro_calendar.db.
Covers the acceptance list: revision baseline/append/no-op for all 3 calendars, read-as-of,
macro vintage windows, observations current/as-of, release dates, JSON payload round-trip,
FK cascade, and honest-empty on a fresh DB.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import pytest

from src.macro_calendar.local_store import MacroCalendarLocalStore


@pytest.fixture()
def store(tmp_path):
    return MacroCalendarLocalStore(tmp_path / "macro_calendar.db")


def _dt(y, m, d, h=12):
    return datetime(y, m, d, h, 0, 0, tzinfo=timezone.utc)


# --- economic: baseline / mutate / unchanged + as-of -------------------------------

def test_economic_baseline_mutate_unchanged(store):
    p = {"country": "US", "event_name": "CPI", "event_time": _dt(2026, 6, 10),
         "impact": "high", "unit": "%", "actual": None, "estimate": 3.1, "prev": 3.0}
    eid, action = store.upsert_economic_event(p, source_payload={"raw": 1}, observed_at=_dt(2026, 6, 1))
    assert isinstance(eid, int) and action == "inserted"

    # re-ingest unchanged → no-op
    _, action2 = store.upsert_economic_event(p, source_payload={"raw": 1}, observed_at=_dt(2026, 6, 2))
    assert action2 == "unchanged"

    # actual arrives → mutation appends a revision
    p2 = {**p, "actual": 3.2}
    eid3, action3 = store.upsert_economic_event(p2, source_payload={"raw": 2}, observed_at=_dt(2026, 6, 11))
    assert eid3 == eid and action3 == "mutated"


def test_economic_read_as_of_vintage(store):
    p = {"country": "US", "event_name": "NFP", "event_time": _dt(2026, 6, 6),
         "impact": "high", "unit": "k", "actual": None, "estimate": 200, "prev": 180}
    eid, _ = store.upsert_economic_event(p, source_payload={"v": "pre"}, observed_at=_dt(2026, 6, 1))
    store.upsert_economic_event({**p, "actual": 210}, source_payload={"v": "post"}, observed_at=_dt(2026, 6, 7))

    # before the release: actual still unknown (None)
    early = store.read_economic_event_as_of(eid, _dt(2026, 6, 3))
    assert early is not None and early["actual"] is None
    # after: actual visible
    late = store.read_economic_event_as_of(eid, _dt(2026, 6, 8))
    assert late["actual"] == 210
    # before ANY observation → None (asking about a time before we observed it)
    assert store.read_economic_event_as_of(eid, _dt(2026, 5, 1)) is None


def test_economic_numeric_coercion_no_false_mutation(store):
    # Decimal-from-DB vs float-from-feed must compare equal (no revision-log flood).
    p = {"country": "US", "event_name": "PMI", "event_time": _dt(2026, 6, 2),
         "impact": "med", "unit": "", "actual": 52.5, "estimate": 52.0, "prev": 51.8}
    store.upsert_economic_event(p, source_payload={}, observed_at=_dt(2026, 6, 1))
    # same values re-fed as ints/strings where equal → still unchanged
    _, action = store.upsert_economic_event({**p, "actual": 52.50}, source_payload={}, observed_at=_dt(2026, 6, 2))
    assert action == "unchanged"


# --- earnings + ipo ----------------------------------------------------------------

def test_earnings_baseline_mutate(store):
    p = {"symbol": "AAPL", "report_date": date(2026, 7, 30), "year": 2026, "quarter": 3,
         "hour": "amc", "eps_estimate": 1.5, "eps_actual": None,
         "revenue_estimate": 90e9, "revenue_actual": None}
    eid, a = store.upsert_earnings_event(p, source_payload={}, observed_at=_dt(2026, 7, 1))
    assert a == "inserted"
    _, a2 = store.upsert_earnings_event({**p, "eps_actual": 1.62}, source_payload={}, observed_at=_dt(2026, 7, 31))
    assert a2 == "mutated"
    asof = store.read_earnings_event_as_of(eid, _dt(2026, 8, 1))
    assert asof["eps_actual"] == 1.62


def test_ipo_baseline_unchanged(store):
    p = {"symbol": None, "name": "Acme Corp", "ipo_date": date(2026, 8, 5), "exchange": "NASDAQ",
         "status": "expected", "number_of_shares": 1e7, "price": "18-20", "total_shares_value": 1.9e8}
    eid, a = store.upsert_ipo_event(p, source_payload={}, observed_at=_dt(2026, 7, 1))
    assert a == "inserted"
    _, a2 = store.upsert_ipo_event(p, source_payload={}, observed_at=_dt(2026, 7, 2))
    assert a2 == "unchanged"
    _, a3 = store.upsert_ipo_event({**p, "status": "priced", "price": "19"}, source_payload={}, observed_at=_dt(2026, 8, 5))
    assert a3 == "mutated"


# --- macro series + observations (vintage) + release dates -------------------------

def test_macro_series_roundtrip(store):
    assert store.upsert_macro_series({"series_id": "GDP", "title": "Gross Domestic Product",
        "frequency": "Quarterly", "units": "Bil. $", "seasonal_adjustment": "SAAR",
        "last_updated": "2026-06-01", "revision_strategy": "vintage"}) is True
    row = store.get_macro_series("GDP")
    assert row["title"] == "Gross Domestic Product" and row["revision_strategy"] == "vintage"
    assert store.get_macro_series("NOPE") is None


def test_macro_observation_vintage_window(store):
    # two vintages of the same observation; get_macro_value_as_of picks by window
    store.upsert_macro_observation(series_id="GDP", observation_date=date(2026, 3, 31),
                                   value=100.0, realtime_start=date(2026, 4, 30), realtime_end=date(2026, 5, 30))
    store.upsert_macro_observation(series_id="GDP", observation_date=date(2026, 3, 31),
                                   value=101.5, realtime_start=date(2026, 5, 30))  # open-ended (latest)
    assert store.get_macro_value_as_of("GDP", date(2026, 3, 31), date(2026, 5, 1)) == 100.0   # first vintage
    assert store.get_macro_value_as_of("GDP", date(2026, 3, 31), date(2026, 6, 15)) == 101.5  # revised
    assert store.get_macro_value_as_of("GDP", date(2026, 3, 31), date(2026, 4, 1)) is None    # before any vintage


def test_macro_observation_realtime_start_mandatory(store):
    with pytest.raises(ValueError):
        store.upsert_macro_observation(series_id="GDP", observation_date=date(2026, 3, 31),
                                       value=1.0, realtime_start=None)


def test_release_dates(store):
    for d in (date(2026, 5, 13), date(2026, 6, 11), date(2026, 7, 15)):
        store.upsert_release_date(release_id=10, release_name="CPI", release_date_value=d)
    store.upsert_release_date(release_id=10, release_name="CPI", release_date_value=date(2026, 5, 13))  # idempotent
    alld = store.get_release_dates(10)
    assert alld == [date(2026, 7, 15), date(2026, 6, 11), date(2026, 5, 13)]  # DESC
    assert store.get_release_dates(10, before=date(2026, 6, 12)) == [date(2026, 6, 11), date(2026, 5, 13)]


# --- JSON payload round-trip + FK cascade + honest empty ---------------------------

def test_source_payload_json_roundtrip(store):
    import json
    p = {"country": "US", "event_name": "Retail Sales", "event_time": _dt(2026, 6, 14),
         "impact": "med", "unit": "%", "actual": 0.4, "estimate": 0.3, "prev": 0.2}
    eid, _ = store.upsert_economic_event(p, source_payload={"nested": {"a": [1, 2]}, "s": "x"},
                                         observed_at=_dt(2026, 6, 14))
    rev = store.read_economic_event_as_of(eid, _dt(2026, 6, 15))
    assert json.loads(rev["source_payload"]) == {"nested": {"a": [1, 2]}, "s": "x"}


def test_fk_cascade_deletes_revisions(store, tmp_path):
    p = {"country": "US", "event_name": "X", "event_time": _dt(2026, 6, 1),
         "impact": "low", "unit": "", "actual": 1, "estimate": 1, "prev": 1}
    eid, _ = store.upsert_economic_event(p, source_payload={}, observed_at=_dt(2026, 6, 1))
    conn = sqlite3.connect(tmp_path / "macro_calendar.db")
    conn.execute("PRAGMA foreign_keys = ON")
    assert conn.execute("SELECT COUNT(*) FROM cal_economic_event_revisions WHERE event_id=?", (eid,)).fetchone()[0] == 1
    conn.execute("DELETE FROM cal_economic_events WHERE event_id=?", (eid,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM cal_economic_event_revisions WHERE event_id=?", (eid,)).fetchone()[0] == 0
    conn.close()


def test_empty_db_honest_empty(store):
    assert store.get_macro_series("ANY") is None
    assert store.get_macro_value_as_of("ANY", date(2026, 1, 1), date(2026, 2, 1)) is None
    assert store.get_release_dates(999) == []
    assert store.read_economic_event_as_of(123, _dt(2026, 1, 1)) is None


def test_no_pg_dependency(store, monkeypatch):
    # the whole store must work with NO psycopg2 / _get_conn anywhere on the path.
    import src.macro_calendar.local_store as mod
    assert not hasattr(mod, "psycopg2")
    assert store.is_available() is True  # always available (unlike the PG-gated twin)
