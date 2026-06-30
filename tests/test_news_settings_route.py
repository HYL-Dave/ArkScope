from __future__ import annotations

import sqlite3

import pytest
from fastapi import HTTPException

import src.api.routes.news as routes
from src.news_normalized.routing import (
    NEWS_PG_EXIT_COMPLETED_KEY,
    USE_NORMALIZED_NEWS_WRITES_KEY,
)


class _FakeProfileStore:
    def __init__(self, initial=None):
        self.values = dict(initial or {})

    def get_setting(self, key):
        return self.values.get(key)

    def set_setting(self, key, value):
        self.values[key] = value


def test_status_is_read_only_and_reports_default_direct(tmp_path, monkeypatch):
    db = tmp_path / "market_data.db"
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(db))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_NEWS", raising=False)
    monkeypatch.delenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", raising=False)

    out = routes.news_status(store=_FakeProfileStore())

    assert out["exists"] is False
    assert out["news"]["row_count"] == 0
    assert out["use_local_news_setting"] is True
    assert out["setting_explicit"] is False
    assert out["env_override"] is False
    assert out["direct_active"] is True
    assert out["normalized_writes_setting"] is False
    assert out["normalized_writes_setting_explicit"] is False
    assert out["normalized_writes_env_override"] is False
    assert out["normalized_writes_env_value"] is None
    assert out["write_route"] == "legacy_local"
    assert out["write_route_reason"]
    assert out["news_pg_exit_completed"] is False
    assert out["news_hard_local"] is False
    assert out["pg_news_route_available"] is True
    assert out["sync"] is None
    assert not db.exists()


def test_status_reports_explicit_and_env_rollback(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "absent.db"))
    store = _FakeProfileStore({"use_local_news": "true"})
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_NEWS", "false")
    monkeypatch.setenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", "true")

    out = routes.news_status(store=store)

    assert out["use_local_news_setting"] is True
    assert out["setting_explicit"] is True
    assert out["env_override"] is True
    assert out["env_value"] is False
    assert out["direct_active"] is False
    assert out["normalized_writes_setting"] is False
    assert out["normalized_writes_setting_explicit"] is False
    assert out["normalized_writes_env_override"] is True
    assert out["normalized_writes_env_value"] is True
    assert out["write_route"] == "normalized"
    assert out["pg_news_route_available"] is True


def test_put_settings_persists_explicit_rollback(monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail: calls.append((action, detail)))
    store = _FakeProfileStore()

    out = routes.set_local_news(routes.LocalNewsToggle(enabled=False), store=store)

    assert out == {"use_local_news_setting": False}
    assert store.get_setting("use_local_news") == "false"
    assert calls == [("set_use_local_news", {"enabled": False})]


def test_put_normalized_writes_persists_with_permission(monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail: calls.append((action, detail)))
    store = _FakeProfileStore()

    out = routes.set_normalized_news_writes(routes.NormalizedNewsWritesToggle(enabled=True), store=store)

    assert out == {"normalized_writes_setting": True}
    assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) == "true"
    assert calls == [("set_normalized_news_writes", {"enabled": True})]


def test_post_exit_profile_marker_rejects_pg_selecting_toggles(monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail: calls.append((action, detail)))
    store = _FakeProfileStore({NEWS_PG_EXIT_COMPLETED_KEY: "true"})

    with pytest.raises(HTTPException) as local_exc:
        routes.set_local_news(routes.LocalNewsToggle(enabled=False), store=store)
    with pytest.raises(HTTPException) as normalized_exc:
        routes.set_normalized_news_writes(routes.NormalizedNewsWritesToggle(enabled=False), store=store)

    assert local_exc.value.status_code == 409
    assert normalized_exc.value.status_code == 409
    assert store.get_setting("use_local_news") is None
    assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) is None
    assert calls == []


def _write_completed_exit_run(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE news_pg_exit_runs (status TEXT NOT NULL)")
        conn.execute("INSERT INTO news_pg_exit_runs (status) VALUES ('completed')")
        conn.commit()
    finally:
        conn.close()


def test_status_and_http_409_after_completed_audit_marker(tmp_path, monkeypatch):
    db = tmp_path / "market_data.db"
    _write_completed_exit_run(db)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(db))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_NEWS", raising=False)
    monkeypatch.delenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", raising=False)
    store = _FakeProfileStore()

    body = routes.news_status(store=store)

    assert body["write_route"] == "normalized"
    assert body["news_pg_exit_completed"] is True
    assert body["news_hard_local"] is True
    assert body["pg_news_route_available"] is False
    assert body["normalized_writes_setting"] is False
    assert body["normalized_writes_setting_explicit"] is False
    with pytest.raises(HTTPException) as normalized_exc:
        routes.set_normalized_news_writes(routes.NormalizedNewsWritesToggle(enabled=False), store=store)
    with pytest.raises(HTTPException) as local_exc:
        routes.set_local_news(routes.LocalNewsToggle(enabled=False), store=store)
    assert normalized_exc.value.status_code == 409
    assert local_exc.value.status_code == 409

    assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) is None
    assert store.get_setting("use_local_news") is None


def test_static_status_route_is_declared_before_dynamic_ticker_route():
    paths = [route.path for route in routes.router.routes]
    assert paths.index("/news/status") < paths.index("/news/{ticker}")
    assert paths.index("/news/settings") < paths.index("/news/{ticker}")
    assert paths.index("/news/settings/normalized-writes") < paths.index("/news/{ticker}")
