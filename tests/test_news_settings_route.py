from __future__ import annotations

import os

import src.api.routes.news as routes


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

    out = routes.news_status(store=_FakeProfileStore())

    assert out["exists"] is False
    assert out["news"]["row_count"] == 0
    assert out["use_local_news_setting"] is True
    assert out["setting_explicit"] is False
    assert out["env_override"] is False
    assert out["direct_active"] is True
    assert out["sync"] is None
    assert not db.exists()


def test_status_reports_explicit_and_env_rollback(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "absent.db"))
    store = _FakeProfileStore({"use_local_news": "true"})
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_NEWS", "false")

    out = routes.news_status(store=store)

    assert out["use_local_news_setting"] is True
    assert out["setting_explicit"] is True
    assert out["env_override"] is True
    assert out["env_value"] is False
    assert out["direct_active"] is False


def test_put_settings_persists_explicit_rollback(monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail: calls.append((action, detail)))
    store = _FakeProfileStore()

    out = routes.set_local_news(routes.LocalNewsToggle(enabled=False), store=store)

    assert out == {"use_local_news_setting": False}
    assert store.get_setting("use_local_news") == "false"
    assert calls == [("set_use_local_news", {"enabled": False})]


def test_static_status_route_is_declared_before_dynamic_ticker_route():
    paths = [route.path for route in routes.router.routes]
    assert paths.index("/news/status") < paths.index("/news/{ticker}")
    assert paths.index("/news/settings") < paths.index("/news/{ticker}")
