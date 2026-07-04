"""Slice 2 — macro/cal local-first wiring: use_local_macro toggle + store factory +
health local-first. Default OFF (PG store) until the toggle flips. Hermetic, no PG."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.macro_calendar import get_macro_calendar_store
from src.macro_calendar.local_store import MacroCalendarLocalStore
from src.service.macro_calendar_health import compute_macro_calendar_health


class _FakeDal:
    def __init__(self, local: bool, backend=None):
        self._backend = backend
        self._local = local

    def _local_macro_enabled(self) -> bool:
        return self._local


def _econ(dt_day=10):
    return {"country": "US", "event_name": "CPI", "event_time": datetime(2026, 6, dt_day, 12, tzinfo=timezone.utc),
            "impact": "high", "unit": "%", "actual": 1.0, "estimate": 1.0, "prev": 1.0}


def test_factory_returns_local_store_when_toggle_on(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(tmp_path / "macro_calendar.db"))
    assert isinstance(get_macro_calendar_store(_FakeDal(local=True)), MacroCalendarLocalStore)


def test_factory_returns_local_store_when_toggle_off_after_n9(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(tmp_path / "macro_calendar.db"))
    # post-N9 explicit/off legacy state no longer routes back to PG.
    assert isinstance(get_macro_calendar_store(_FakeDal(local=False)), MacroCalendarLocalStore)


def test_dal_local_macro_toggle_default_off_and_env(monkeypatch, tmp_path):
    from src.tools.data_access import DataAccessLayer
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MACRO", raising=False)
    # Hermetic: point at an EMPTY tmp profile DB — deleting the var would fall back
    # to the real data/profile_state.db, whose use_local_macro=true breaks the
    # default-OFF assertion on a configured host.
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir(exist_ok=True)
    dal = DataAccessLayer(base_path=tmp_path)     # FileBackend, no PG
    assert dal._local_macro_enabled() is True     # post-N9 default local
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_MACRO", "1")
    assert dal._local_macro_enabled() is True      # env override


def test_local_store_table_stats(tmp_path):
    s = MacroCalendarLocalStore(tmp_path / "macro_calendar.db")
    s.upsert_economic_event(_econ(), source_payload={})
    stats = s.table_stats()
    assert set(stats) == {"cal_economic_events", "cal_earnings_events", "cal_ipo_events",
                          "macro_series", "macro_observations", "macro_release_dates"}
    assert stats["cal_economic_events"]["row_count"] == 1
    assert stats["cal_economic_events"]["last_fetched_at"] is not None
    assert stats["macro_series"]["row_count"] == 0


def test_health_local_first_without_pg(tmp_path, monkeypatch):
    # local toggle ON + a seeded macro_calendar.db + NO PG backend → health computes table
    # coverage from the local DB (does not fall to the db-unavailable report).
    db = tmp_path / "macro_calendar.db"
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(db))
    MacroCalendarLocalStore(db).upsert_economic_event(_econ(), source_payload={})
    report = compute_macro_calendar_health(_FakeDal(local=True, backend=None))
    assert isinstance(report.get("tables"), list)
    econ = next(b for b in report["tables"] if b["name"] == "cal_economic_events")
    assert econ["row_count"] == 1                 # local data reflected without any PG
    assert econ["status"] != "empty"              # has a fresh fetched_at → evaluated, not empty
