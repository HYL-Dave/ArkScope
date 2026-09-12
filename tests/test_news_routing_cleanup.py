"""Current routing and ingest authority against disposable persisted state."""
from __future__ import annotations

import inspect
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import src.api.routes.news as routes
import src.news_providers as providers
from src.market_data_admin import _NEWS_SCHEMA, _PRICES_SCHEMA
from src.market_data_direct import _ensure_provider_sync_tables
from src.news_normalized.routing import (
    USE_NORMALIZED_NEWS_WRITES_KEY,
    read_news_write_route,
    resolve_news_write_route,
)
from src.news_sync_status import overlay_news_sync_status, read_news_sync_status
from src.profile_state import ProfileStateStore
from src.service.provider_health import compute_provider_health
from src.tools.backends.sqlite_backend import SqliteBackend


@pytest.fixture(params=[
    pytest.param(("false", None), id="stored-false"),
    pytest.param(("malformed", None), id="stored-malformed"),
    pytest.param(("true", "false"), id="env-false"),
    pytest.param(("true", "malformed"), id="env-malformed"),
    pytest.param(("false", "true"), id="env-true"),
])
def obsolete_profile(request, tmp_path, monkeypatch):
    stored, env = request.param
    path = tmp_path / "profile.db"
    store = ProfileStateStore(path)
    store.set_setting("use_local_news", stored)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "absent.db"))
    monkeypatch.delenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", raising=False)
    if env is None:
        monkeypatch.delenv("ARKSCOPE_USE_LOCAL_NEWS", raising=False)
    else:
        monkeypatch.setenv("ARKSCOPE_USE_LOCAL_NEWS", env)
    yield store
    assert store.get_setting("use_local_news") == stored


@pytest.fixture
def telemetry_db(tmp_path, monkeypatch):
    path = tmp_path / "market.db"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_NEWS_SCHEMA)
        conn.executescript(_PRICES_SCHEMA)
        _ensure_provider_sync_tables(conn)
        conn.executemany(
            "INSERT INTO news (ticker,title,source,published_at,article_hash) "
            "VALUES (?,?,?,?,?)",
            [("AAPL", "Stored article", source, "2026-06-10T11:30:00+0000", source)
             for source in ("polygon", "finnhub")],
        )
        conn.execute(
            "INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) "
            "VALUES ('AAPL','2026-06-10T11:45:00+0000','15min',10,12,9,11,100)"
        )
        conn.executemany(
            "INSERT INTO provider_sync_runs "
            "(provider,domain,interval,started_at,finished_at,tickers_scanned,rows_added,status,error) "
            "VALUES (?,'news','news',?,?,?,?,?,?)",
            [
                ("polygon", "2026-06-10T09:59:00+00:00", "2026-06-10T10:00:00+00:00", 2, 7, "succeeded", None),
                ("polygon", "2026-06-10T10:59:00+00:00", "2026-06-10T11:00:00+00:00", 2, 3, "failed", "upstream unavailable"),
                ("finnhub", "2026-06-10T08:59:00+00:00", "2026-06-10T09:00:00+00:00", 1, 5, "succeeded", None),
            ],
        )
        conn.execute(
            "INSERT INTO provider_sync_meta (provider,ticker,interval,last_error,rows_added,updated_at) "
            "VALUES ('polygon','BAD','news','HTTP 403',0,'2026-06-10T11:00:00+00:00')"
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(path))
    return path


@pytest.mark.parametrize(("normalized", "expected"), [
    ("false", "legacy_local"), ("true", "normalized"),
])
def test_current_writer_ignores_obsolete_profile_and_environment(obsolete_profile, normalized, expected):
    obsolete_profile.set_setting(USE_NORMALIZED_NEWS_WRITES_KEY, normalized)

    route = read_news_write_route()
    status = routes.news_status(store=obsolete_profile)

    assert route.mode.value == expected
    assert status["write_route"] == expected
    assert status["normalized_writes_setting"] is (normalized == "true")


def test_status_has_only_current_routing_fields(obsolete_profile):
    status = routes.news_status(store=obsolete_profile)
    assert set(status) == {
        "market_db", "exists", "news", "normalized_writes_setting",
        "normalized_writes_setting_explicit", "normalized_writes_env_override",
        "normalized_writes_env_value", "write_route", "write_route_reason", "sync",
    }


def _assert_telemetry(sync):
    assert sync is not None
    assert sync.get("status") == "failed"
    assert sync["last_success"] == "2026-06-10T10:00:00+00:00"
    assert sync["last_attempt"] == "2026-06-10T11:00:00+00:00"
    assert sync["rows_added"] == 8
    assert sync["last_error"] == "polygon: upstream unavailable; BAD: HTTP 403"
    assert set(sync["providers"]) == {"polygon", "finnhub"}
    assert sync["providers"]["polygon"]["tickers_scanned"] == 2
    assert sync["providers"]["polygon"]["ticker_errors"] == [{
        "ticker": "BAD", "error": "HTTP 403", "updated_at": "2026-06-10T11:00:00+00:00",
    }]


def test_status_keeps_actual_ingest_telemetry_with_obsolete_settings(obsolete_profile, telemetry_db):
    status = routes.news_status(store=obsolete_profile)
    _assert_telemetry(status["sync"])
    assert status["news"]["row_count"] == 2


def test_overlay_keeps_actual_ingest_telemetry_with_obsolete_settings(obsolete_profile, telemetry_db):
    original = {"news": {"last_success": "obsolete"}, "prices": {"rows_added": 26}, "sa": {"last_error": "capture failed"}}
    overlaid = overlay_news_sync_status(original, telemetry_db)
    _assert_telemetry(overlaid["news"])
    assert overlaid["prices"] == {"rows_added": 26}
    assert overlaid["sa"] == {"last_error": "capture failed"}
    assert original["news"] == {"last_success": "obsolete"}


def test_overlay_clears_stale_news_when_current_store_is_absent(obsolete_profile, tmp_path):
    path = tmp_path / "absent.db"
    original = {"news": {"last_success": "obsolete"}, "prices": {"rows_added": 26}}
    assert overlay_news_sync_status(original, path) == {"news": None, "prices": {"rows_added": 26}}
    assert original["news"] == {"last_success": "obsolete"}
    assert not path.exists()


def test_health_keeps_ingest_success_errors_and_counters_with_obsolete_settings(
    obsolete_profile, telemetry_db, monkeypatch,
):
    monkeypatch.setenv("MASSIVE_API_KEY", "disposable-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "disposable-key")
    monkeypatch.setattr("src.env_keys._loaded_keys", set())
    dal = SimpleNamespace(_backend=SqliteBackend(telemetry_db))
    out = compute_provider_health(dal, now=datetime(2026, 6, 10, 12, tzinfo=timezone.utc))
    by_id = {provider["id"]: provider for provider in out["providers"]}
    massive = by_id["massive"]
    assert massive["status"] == "connected"
    assert massive["last_success_at"] == "2026-06-10T10:00:00+00:00"
    assert massive["last_attempt_at"] == "2026-06-10T11:00:00+00:00"
    assert massive["last_error"] == "upstream unavailable; BAD: HTTP 403"
    assert massive["signals"]["direct_sync"]["rows_added"] == 3
    assert massive["signals"]["news_latest"] == "2026-06-10T11:30:00+00:00"
    assert by_id["finnhub"]["status"] == "connected"
    assert by_id["finnhub"]["last_success_at"] == "2026-06-10T09:00:00+00:00"
    assert by_id["ibkr"]["signals"]["prices_latest"] == "2026-06-10T11:45:00+00:00"
    _assert_telemetry(out["local_market"]["sync"]["news"])


def test_obsolete_helpers_and_resolver_parameters_are_physically_removed():
    for name in ("USE_LOCAL_NEWS_KEY", "ENV_USE_LOCAL_NEWS", "resolve_use_local_news",
                 "use_local_news_enabled", "_default_profile_db"):
        assert not hasattr(providers, name), name
    assert set(inspect.signature(resolve_news_write_route).parameters) == {
        "normalized_required", "normalized_value", "normalized_env",
    }
    assert not hasattr(routes, "LocalNewsToggle")
    assert not hasattr(routes, "set_local_news")


def test_obsolete_put_is_unmounted_and_returns_405_without_writing(tmp_path, monkeypatch):
    store = ProfileStateStore(tmp_path / "profile.db")
    store.set_setting("use_local_news", "malformed")
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_profile_store] = lambda: store
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *args: None)
    with TestClient(app) as client:
        response = client.put("/news/settings", json={"enabled": False})
    assert response.status_code == 405
    assert store.get_setting("use_local_news") == "malformed"
    assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) is None
    assert {(next(iter(route.methods)), route.path) for route in routes.router.routes} == {
        ("GET", "/news/status"), ("PUT", "/news/settings/normalized-writes"),
        ("GET", "/news/feed"), ("GET", "/news/{ticker}"), ("GET", "/news/search/keyword"),
    }


def test_normalized_setter_denies_before_writing_and_preserves_old_key(tmp_path, monkeypatch):
    store = ProfileStateStore(tmp_path / "profile.db")
    store.set_setting("use_local_news", "malformed")

    def deny(action, detail):
        assert action == "set_normalized_news_writes"
        assert detail == {"enabled": True}
        raise HTTPException(status_code=403, detail="denied")

    monkeypatch.setattr(routes, "require_profile_state_write", deny)
    with pytest.raises(HTTPException) as exc:
        routes.set_normalized_news_writes(routes.NormalizedNewsWritesToggle(enabled=True), store=store)
    assert exc.value.status_code == 403
    assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) is None
    assert store.get_setting("use_local_news") == "malformed"


def test_normalized_setter_writes_only_current_key(tmp_path, monkeypatch):
    store = ProfileStateStore(tmp_path / "profile.db")
    store.set_setting("use_local_news", "malformed")
    store.set_setting("unrelated", "retain")
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *args: calls.append(args))
    for enabled in (True, False):
        out = routes.set_normalized_news_writes(routes.NormalizedNewsWritesToggle(enabled=enabled), store=store)
        assert out == {"normalized_writes_setting": enabled}
        assert store.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY) == ("true" if enabled else "false")
        assert store.get_setting("use_local_news") == "malformed"
        assert store.get_setting("unrelated") == "retain"
    assert calls == [
        ("set_normalized_news_writes", {"enabled": True}),
        ("set_normalized_news_writes", {"enabled": False}),
    ]


def test_overlay_propagates_corrupt_telemetry_without_mutation(tmp_path):
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"not a sqlite database")
    original = {"news": {"last_success": "obsolete"}, "prices": {"rows_added": 26}}
    with pytest.raises(sqlite3.DatabaseError):
        overlay_news_sync_status(original, path)
    assert original == {"news": {"last_success": "obsolete"}, "prices": {"rows_added": 26}}
    assert path.read_bytes() == b"not a sqlite database"


@pytest.mark.parametrize(("stored", "env"), [("malformed", None), ("true", "malformed")])
def test_malformed_current_normalized_setting_still_blocks(tmp_path, monkeypatch, stored, env):
    store = ProfileStateStore(tmp_path / "profile.db")
    store.set_setting(USE_NORMALIZED_NEWS_WRITES_KEY, stored)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", store.db_path)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "absent.db"))
    if env is None:
        monkeypatch.delenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", raising=False)
    else:
        monkeypatch.setenv("ARKSCOPE_USE_NORMALIZED_NEWS_WRITES", env)

    route = read_news_write_route()
    status = routes.news_status(store=store)

    assert route.mode.value == "blocked"
    assert status["write_route"] == "blocked"
    assert "normalized-writer setting is malformed" in route.reason.lower()
    assert "normalized-writer setting is malformed" in status["write_route_reason"].lower()
