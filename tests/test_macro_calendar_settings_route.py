"""Slice §4c — expose use_local_macro in Settings (explicit toggle, default-off).

Backend route mirrors the use_local_market precedent (/market-data/status + /settings):
GET /macro/status reports the toggle + local-DB coverage (READ-ONLY — must not create the
DB), PUT /macro/settings persists the toggle. Route-unit-test convention: call the handler
directly with a fake ProfileStateStore (NOT TestClient — AnyIO/lifespan hangs without PG).
"""

from __future__ import annotations

import os

import pytest

import src.api.routes.macro_calendar as routes
from src.macro_calendar import USE_LOCAL_MACRO_KEY
from src.macro_calendar.local_store import MacroCalendarLocalStore


class _FakeProfileStore:
    def __init__(self, initial=None):
        self._s = dict(initial or {})
    def get_setting(self, key):
        return self._s.get(key)
    def set_setting(self, key, value):
        self._s[key] = value


@pytest.fixture(autouse=True)
def _no_perm_gate(monkeypatch):
    # the permission gate isn't under test here; persistence is.
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)


def test_status_db_absent_is_honest_and_does_not_create(tmp_path, monkeypatch):
    db = tmp_path / "macro_calendar.db"
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(db))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MACRO", raising=False)
    out = routes.macro_status(store=_FakeProfileStore())
    assert out["exists"] is False and out["tables"] == {}
    assert out["use_local_macro_setting"] is False  # default off
    assert out["local_first_active"] is False
    assert not db.exists(), "status read must not create macro_calendar.db"


def test_status_reflects_setting_and_env_and_coverage(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    db = tmp_path / "macro_calendar.db"
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(db))
    MacroCalendarLocalStore(db).upsert_economic_event(
        {"country": "US", "event_name": "CPI", "event_time": datetime(2026, 6, 10, 12, tzinfo=timezone.utc),
         "impact": "high", "unit": "%", "actual": 1.0, "estimate": 1.0, "prev": 1.0}, source_payload={})
    # setting persisted on → reflected; env override also reflected
    out = routes.macro_status(store=_FakeProfileStore({USE_LOCAL_MACRO_KEY: "true"}))
    assert out["exists"] is True
    assert out["use_local_macro_setting"] is True
    assert out["tables"]["cal_economic_events"]["row_count"] == 1
    assert out["local_first_active"] is True   # setting on AND db exists

    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_MACRO", "1")
    out2 = routes.macro_status(store=_FakeProfileStore())   # setting off, env on
    assert out2["use_local_macro_setting"] is False and out2["env_override"] is True
    assert out2["local_first_active"] is True   # env override + db exists


def test_local_first_active_when_toggle_on_even_if_db_absent(tmp_path, monkeypatch):
    # Bug fix: the factory routes LOCAL the moment use_local_macro is on — it creates the DB
    # on first use and there is NO PG fallback in the local path. So local_first_active must
    # reflect routing (setting OR env), NOT file existence. Previously it was (on AND exists),
    # which lied: status said "PG" while the runtime already served (empty) local.
    db = tmp_path / "macro_calendar.db"
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(db))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MACRO", raising=False)
    out = routes.macro_status(store=_FakeProfileStore({USE_LOCAL_MACRO_KEY: "true"}))
    assert out["exists"] is False              # DB not built yet
    assert out["local_first_active"] is True   # but routing IS local (factory ignores existence)
    assert not db.exists()                     # status itself still must not create it

    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_MACRO", "1")   # env-only path
    out2 = routes.macro_status(store=_FakeProfileStore())
    assert out2["local_first_active"] is True
    # off → PG (unchanged)
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MACRO", raising=False)
    assert routes.macro_status(store=_FakeProfileStore())["local_first_active"] is False


def test_put_settings_persists_toggle(monkeypatch):
    store = _FakeProfileStore()
    res = routes.set_local_macro(routes.LocalMacroToggle(enabled=True), store=store)
    assert res == {"use_local_macro_setting": True}
    assert store.get_setting(USE_LOCAL_MACRO_KEY) == "true"

    res2 = routes.set_local_macro(routes.LocalMacroToggle(enabled=False), store=store)
    assert res2 == {"use_local_macro_setting": False}
    assert store.get_setting(USE_LOCAL_MACRO_KEY) == "false"


def test_status_settings_not_gated_by_macro_calendar_enabled(monkeypatch):
    # config endpoints must work even when the macro FEATURE flag is off (you need them to
    # configure it) — mirrors market-data status/settings having no feature gate.
    from src.agents.config import get_agent_config
    cfg = get_agent_config()
    orig = cfg.macro_calendar_enabled
    cfg.macro_calendar_enabled = False
    try:
        routes.macro_status(store=_FakeProfileStore())          # no 503
        routes.set_local_macro(routes.LocalMacroToggle(enabled=False), store=_FakeProfileStore())
    finally:
        cfg.macro_calendar_enabled = orig
