"""Tests for the app-owned per-source data scheduler (slice 3e-D v1)."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

import src.service.data_scheduler as ds
from src.profile_state import ProfileStateStore

_NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    """Fresh profile store per test; reset scheduler runtime state; never touch
    the real DAL / subprocesses / local market DB — and CRITICALLY, stub both
    in-process news adapters so no test can fire a real provider API call."""
    store = ProfileStateStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(ds, "_store", lambda: store)
    monkeypatch.setattr(ds, "_LAST_ATTEMPT", {})
    # default stubs: no real subprocess, no real local refresh, no telemetry
    monkeypatch.setattr(ds, "_run_subprocess", lambda argv: {"returncode": 0})
    monkeypatch.setattr(ds, "_local_refresh", lambda: {"ok": True})
    import scripts.collection.collect_finnhub_news as cfn
    import scripts.collection.collect_polygon_news as cpn
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: {"mode": "up_to_date", "new_articles": 0})
    monkeypatch.setattr(cfn, "run_incremental",
                        lambda *a, **k: {"mode": "up_to_date", "new_articles": 0})

    class _NoStore:
        def create_run(self, *a, **k):
            return None

        def finish_run(self, *a, **k):
            return False

    monkeypatch.setattr("src.service.job_runs_store.JobRunsStore", lambda dal: _NoStore())
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: object())
    yield store


# --- config -------------------------------------------------------------------

def test_defaults_everything_disabled():
    for source in ds.SOURCES:
        cfg = ds.source_config(source)
        assert cfg["enabled"] is False  # nothing fetches until the user opts in
        assert cfg["interval_minutes"] == ds.SOURCES[source].default_interval_min


def test_set_config_roundtrip_and_clamp():
    cfg = ds.set_source_config("polygon_news", enabled=True, interval_minutes=1)
    assert cfg["enabled"] is True
    assert cfg["interval_minutes"] == 5            # clamped to ≥5min
    cfg = ds.set_source_config("polygon_news", interval_minutes=10 ** 9)
    assert cfg["interval_minutes"] == 7 * 24 * 60  # clamped to ≤1 week
    assert ds.source_config("polygon_news")["enabled"] is True  # persisted


def test_set_config_unknown_source():
    with pytest.raises(KeyError):
        ds.set_source_config("nope", enabled=True)


# --- due logic + tick -----------------------------------------------------------

def test_is_due_matrix():
    assert ds._is_due("polygon_news", _NOW) is False           # disabled
    ds.set_source_config("polygon_news", enabled=True, interval_minutes=60)
    assert ds._is_due("polygon_news", _NOW) is True            # never attempted
    ds._LAST_ATTEMPT["polygon_news"] = _NOW - timedelta(minutes=30)
    assert ds._is_due("polygon_news", _NOW) is False           # ran recently
    ds._LAST_ATTEMPT["polygon_news"] = _NOW - timedelta(minutes=61)
    assert ds._is_due("polygon_news", _NOW) is True            # interval elapsed


def test_tick_fires_only_enabled_and_due():
    ds.set_source_config("finnhub_news", enabled=True, interval_minutes=60)
    ds.set_source_config("local_incremental", enabled=True, interval_minutes=15)
    ds._LAST_ATTEMPT["local_incremental"] = _NOW - timedelta(minutes=5)  # not due
    fired = []
    out = ds.tick_once(_NOW, fire=fired.append)
    assert out == fired == ["finnhub_news"]


# --- run_source ------------------------------------------------------------------

def test_run_source_adapter_success_sync_refresh(monkeypatch):
    # polygon_news runs IN-PROCESS via the adapter; only the PG sync is a subprocess.
    import scripts.collection.collect_polygon_news as cpn
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: {"mode": "incremental", "new_articles": 3})
    calls = []
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (calls.append(argv), {"returncode": 0})[1])
    finished = {}

    class _Store:
        def create_run(self, name, **kw):
            finished["name"] = name
            finished["trigger"] = kw.get("trigger_source")
            return 7

        def finish_run(self, run_id, **kw):
            finished["status"] = kw.get("status")
            return True

    monkeypatch.setattr("src.service.job_runs_store.JobRunsStore", lambda dal: _Store())
    res = ds.run_source("polygon_news", trigger_source="api")
    assert res["status"] == "succeeded"
    assert res["collect"] == {"mode": "incremental", "new_articles": 3}  # structured stats
    assert res["local_refresh"] == {"ok": True}
    assert len(calls) == 1 and "--news" in calls[0]         # ONLY the PG sync subprocess
    assert finished == {"name": "collect.polygon_news", "trigger": "api",
                        "status": "succeeded"}


def test_run_source_subprocess_success_collect_sync_refresh(monkeypatch):
    # IBKR sources stay subprocess: collector + PG sync = two child processes.
    calls = []
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (calls.append(argv), {"returncode": 0})[1])
    res = ds.run_source("ibkr_news")
    assert res["status"] == "succeeded"
    assert len(calls) == 2
    assert "collect_ibkr_news.py" in calls[0][1]
    assert "--news" in calls[1]


def test_run_source_adapter_failure_short_circuits(monkeypatch):
    # adapter raising (e.g. missing API key) → failed, PG sync never attempted
    import scripts.collection.collect_finnhub_news as cfn
    monkeypatch.setattr(cfn, "run_incremental",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("FINNHUB_API_KEY not found")))
    calls = []
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (calls.append(argv), {"returncode": 0})[1])
    res = ds.run_source("finnhub_news")
    assert res["status"] == "failed" and "FINNHUB_API_KEY" in res["error"]
    assert calls == []                                      # PG sync never attempted


def test_run_source_collector_failure_short_circuits(monkeypatch):
    calls = []

    def _sub(argv):
        calls.append(argv)
        return {"returncode": 1, "error_tail": "boom"}

    monkeypatch.setattr(ds, "_run_subprocess", _sub)
    res = ds.run_source("ibkr_news")
    assert res["status"] == "failed" and "collector failed" in res["error"]
    assert len(calls) == 1                                  # PG sync never attempted


def test_run_source_skips_when_already_running():
    lock = ds._SOURCE_LOCKS["polygon_news"]
    assert lock.acquire(blocking=False)
    try:
        res = ds.run_source("polygon_news")
        assert res["status"] == "skipped" and "already running" in res["reason"]
    finally:
        lock.release()


def test_ibkr_sources_serialize_behind_gateway_lock(monkeypatch):
    monkeypatch.setattr(ds, "_IBKR_LOCK_TIMEOUT_S", 0.05)
    assert ds._IBKR_LOCK.acquire(blocking=False)            # someone holds the gateway
    try:
        res = ds.run_source("ibkr_news")
        assert res["status"] == "skipped" and "IBKR" in res["reason"]
    finally:
        ds._IBKR_LOCK.release()
    # non-IBKR source is unaffected by the gateway lock
    assert ds.run_source("polygon_news")["status"] == "succeeded"


def test_price_scope_required(monkeypatch):
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: [])
    res = ds.run_source("ibkr_prices")
    assert res["status"] == "failed" and "scope" in res["error"]

    argv_seen = []
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (argv_seen.append(argv), {"returncode": 0})[1])
    res = ds.run_source("ibkr_prices")
    assert res["status"] == "succeeded" and res["ticker_count"] == 2
    assert "--tickers" in argv_seen[0] and "AAPL,NVDA" in argv_seen[0]


def test_local_incremental_has_no_subprocess(monkeypatch):
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(AssertionError("subprocess used")))
    res = ds.run_source("local_incremental")
    assert res["status"] == "succeeded" and res["local_refresh"] == {"ok": True}


def test_run_source_never_raises(monkeypatch):
    monkeypatch.setattr(ds, "_local_refresh",
                        lambda: (_ for _ in ()).throw(RuntimeError("disk gone")))
    res = ds.run_source("local_incremental")
    assert res["status"] == "failed" and "disk gone" in res["error"]


# --- routes ----------------------------------------------------------------------

def test_get_schedule_snapshot_shape():
    from src.api.routes.schedule import get_schedule
    out = get_schedule()["sources"]
    assert set(out.keys()) == set(ds.SOURCES.keys())
    p = out["polygon_news"]
    assert p["enabled"] is False and p["running"] is False
    assert p["provider_fetch"] is True and p["job_name"] == "collect.polygon_news"
    assert out["local_incremental"]["provider_fetch"] is False
    assert out["ibkr_prices"]["ibkr"] is True


def test_put_schedule_validates():
    from fastapi import HTTPException
    from src.api.routes.schedule import ScheduleUpdate, put_schedule
    with pytest.raises(HTTPException) as e:
        put_schedule("nope", ScheduleUpdate(enabled=True))
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        put_schedule("polygon_news", ScheduleUpdate())
    assert e.value.status_code == 400
    out = put_schedule("polygon_news", ScheduleUpdate(enabled=True, interval_minutes=30))
    assert out == {"source": "polygon_news", "enabled": True, "interval_minutes": 30}


def test_run_now_fires_background_and_skips_running(monkeypatch):
    from src.api.routes.schedule import run_now
    started = threading.Event()
    release = threading.Event()

    def _slow_run(source, trigger_source="scheduler"):
        with ds._SOURCE_LOCKS[source]:
            started.set()
            release.wait(timeout=5)
        return {"status": "succeeded"}

    monkeypatch.setattr("src.api.routes.schedule.run_source", _slow_run)
    out = run_now("polygon_news")
    assert out["status"] == "started" and out["job_name"] == "collect.polygon_news"
    assert started.wait(timeout=5)
    out2 = run_now("polygon_news")            # still holding the source lock
    assert out2["status"] == "skipped"
    release.set()


def test_adapter_gets_universe_tickers_and_progress(monkeypatch):
    # News adapters receive the ACTIVE UNIVERSE as the explicit ticker list (the
    # collectors' own default is the legacy tickers_core.json) + a progress_cb
    # that feeds the live progress the UI shows.
    import scripts.collection.collect_polygon_news as cpn
    seen = {}

    def _fake_run(tickers_arg=None, progress_cb=None, **kw):
        seen["tickers_arg"] = tickers_arg
        progress_cb(3, 10, "AAPL")           # simulate mid-run progress
        snap = ds.status_snapshot()["polygon_news"]  # while still inside the run
        seen["live_progress"] = snap["progress"]
        return {"mode": "incremental", "new_articles": 1}

    monkeypatch.setattr(cpn, "run_incremental", _fake_run)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    res = ds.run_source("polygon_news")
    assert res["status"] == "succeeded" and res["ticker_count"] == 2
    assert seen["tickers_arg"] == "AAPL,NVDA"
    assert seen["live_progress"] == {"done": 3, "total": 10, "current": "AAPL"}
    # progress cleared after the run
    assert ds.status_snapshot()["polygon_news"]["progress"] is None


def test_adapter_universe_unavailable_falls_back_to_default(monkeypatch):
    # profile DB unavailable → adapter runs with the collector's default list
    # (no tickers_arg), with a warning — collection must not die.
    import scripts.collection.collect_finnhub_news as cfn
    seen = {}

    def _fake_run(tickers_arg=None, progress_cb=None, **kw):
        seen["tickers_arg"] = tickers_arg
        return {"mode": "up_to_date", "new_articles": 0}

    monkeypatch.setattr(cfn, "run_incremental", _fake_run)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: [])
    res = ds.run_source("finnhub_news")
    assert res["status"] == "succeeded"
    assert seen["tickers_arg"] is None
