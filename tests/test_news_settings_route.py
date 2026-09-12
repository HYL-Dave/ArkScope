from __future__ import annotations

import src.api.routes.news as routes
from src.news_normalized.routing import USE_NORMALIZED_NEWS_WRITES_KEY


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
    monkeypatch.delenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", raising=False)

    out = routes.news_status(store=_FakeProfileStore())

    assert out["exists"] is False
    assert out["news"]["row_count"] == 0
    assert out["normalized_writes_setting"] is False
    assert out["normalized_writes_setting_explicit"] is False
    assert out["normalized_writes_env_override"] is False
    assert out["normalized_writes_env_value"] is None
    assert out["write_route"] == "legacy_local"
    assert out["write_route_reason"]
    assert out["sync"] is None
    assert not db.exists()


def test_status_reports_current_normalized_environment_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "absent.db"))
    store = _FakeProfileStore()
    monkeypatch.setenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", "true")

    out = routes.news_status(store=store)

    assert out["normalized_writes_setting"] is False
    assert out["normalized_writes_setting_explicit"] is False
    assert out["normalized_writes_env_override"] is True
    assert out["normalized_writes_env_value"] is True
    assert out["write_route"] == "normalized"


def test_put_normalized_writes_persists_with_permission(monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail: calls.append((action, detail)))
    store = _FakeProfileStore()

    out = routes.set_normalized_news_writes(routes.NormalizedNewsWritesToggle(enabled=True), store=store)

    assert out == {"normalized_writes_setting": True}
    assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) == "true"
    assert calls == [("set_normalized_news_writes", {"enabled": True})]

def test_status_selects_direct_writer_when_normalized_writes_are_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "market_data.db"))
    monkeypatch.delenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", raising=False)
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail: None)
    store = _FakeProfileStore()

    routes.set_normalized_news_writes(
        routes.NormalizedNewsWritesToggle(enabled=False),
        store=store,
    )
    body = routes.news_status(store=store)

    assert body["write_route"] == "legacy_local"
    assert body["normalized_writes_setting"] is False
    assert body["normalized_writes_setting_explicit"] is True
    assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) == "false"


def test_static_status_route_is_declared_before_dynamic_ticker_route():
    paths = [route.path for route in routes.router.routes]
    assert paths.index("/news/status") < paths.index("/news/{ticker}")
    assert paths.index("/news/settings/normalized-writes") < paths.index("/news/{ticker}")
