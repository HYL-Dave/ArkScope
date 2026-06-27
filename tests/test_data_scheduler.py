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
    # S3.2 defaults news direct-local ON. Most legacy scheduler tests below exercise
    # the mirror path, so pin the rollback explicitly; the default-direct test clears it.
    store.set_setting("use_local_news", "false")
    monkeypatch.setattr(ds, "_store", lambda: store)
    monkeypatch.setattr(ds, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(ds, "_LAST_RESULT", {})
    # v1.2: isolate the durable scheduler-state store to a per-test DB (never the real
    # profile_state.db). Set ARKSCOPE_PROFILE_DB so BOTH the write store (_state_store) and the
    # v1.4a no-create read (resolve_profile_state_db_path) resolve to this tmp path.
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    from src.scheduler_state import SchedulerStateStore
    monkeypatch.setattr(ds, "_SCHED_STATE", SchedulerStateStore(tmp_path / "profile_state.db"))
    # cross-process file locks go to a per-test dir — NEVER the repo data/locks/
    # (a live sidecar's flocks would make these tests skip spuriously, and vice versa)
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    # default stubs: no real subprocess, no real local refresh, no telemetry
    monkeypatch.setattr(ds, "_run_subprocess", lambda argv: {"returncode": 0})
    monkeypatch.setattr(ds, "_local_refresh", lambda: {"ok": True})
    # active-universe scope: stub a non-empty default so price/universe sources are
    # hermetic (no real profile DB). Tests asserting the empty-scope path override this.
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
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
    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: False)
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


def test_run_source_news_direct_when_use_local_news_on(monkeypatch, hermetic):
    # S3.2 default ON: polygon_news routes to the DIRECT-LOCAL writer — NO run_incremental (Parquet),
    # NO --news PG sync subprocess, NO local mirror. (OFF path = the test above, unchanged.)
    import scripts.collection.collect_polygon_news as cpn
    hermetic.set_setting("use_local_news", None)  # unset resolves to the production default ON
    calls = {"run_incremental": 0, "sync": 0, "refresh": 0, "direct": 0, "provider": None}
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: calls.__setitem__("run_incremental", calls["run_incremental"] + 1))

    def _subproc(argv):
        if "--news" in argv:
            calls["sync"] += 1
        return {"returncode": 0}
    monkeypatch.setattr(ds, "_run_subprocess", _subproc)
    monkeypatch.setattr(ds, "_local_refresh",
                        lambda: (calls.__setitem__("refresh", calls["refresh"] + 1), {"ok": True})[1])
    monkeypatch.setattr("src.news_providers.make_news_provider",
                        lambda source, **k: (calls.__setitem__("provider", source), object())[1])

    def _direct(tickers, *, source, provider, progress_cb=None, **k):
        calls["direct"] += 1
        return {"source": source, "tickers_scanned": len(tickers), "articles_added": 0, "errors": {}}
    monkeypatch.setattr("src.news_direct.backfill_news_direct", _direct)

    res = ds.run_source("polygon_news", trigger_source="api")
    assert res["status"] == "succeeded"
    assert calls["direct"] == 1 and calls["provider"] == "polygon"   # direct writer + provider used
    assert calls["run_incremental"] == 0                             # NOT the Parquet adapter
    assert calls["sync"] == 0                                        # NO --news PG sync
    assert calls["refresh"] == 0                                     # NO local mirror
    assert "skipped" in res["local_refresh"]                         # mirror explicitly skipped
    assert res["collect"]["source"] == "polygon" and res["ticker_count"] == 2


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


# --- cross-process locks (CLI ⟷ sidecar) -----------------------------------------

def _hold_flock(tmp_path, name):
    """Simulate ANOTHER PROCESS holding a lock: flock(2) conflicts between separate
    open-file-descriptions even within one process, so a second raw fd stands in
    for the CLI. Caller closes the handle to release."""
    import fcntl
    path = tmp_path / "locks" / f"{name}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fh


def test_run_source_skips_when_running_in_another_process(tmp_path):
    # threading.Lock can't see across processes — the file-lock twin must.
    fh = _hold_flock(tmp_path, "source_polygon_news")
    try:
        res = ds.run_source("polygon_news")
        assert res["status"] == "skipped" and "another process" in res["reason"]
        assert not ds._SOURCE_LOCKS["polygon_news"].locked()  # in-process lock released
    finally:
        fh.close()
    assert ds.run_source("polygon_news")["status"] == "succeeded"  # released → runs


def test_ibkr_gateway_serializes_across_processes(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "_IBKR_LOCK_TIMEOUT_S", 0.05)
    fh = _hold_flock(tmp_path, "ibkr_gateway")
    try:
        res = ds.run_source("ibkr_news")
        assert res["status"] == "skipped" and "another process" in res["reason"]
        assert not ds._IBKR_LOCK.locked()                      # in-process twin released
        # non-IBKR source unaffected by the gateway lock
        assert ds.run_source("polygon_news")["status"] == "succeeded"
    finally:
        fh.close()


def test_run_source_releases_file_locks(tmp_path):
    # after a normal run the flock must be free for the next process
    assert ds.run_source("polygon_news")["status"] == "succeeded"
    fh = _hold_flock(tmp_path, "source_polygon_news")  # would raise if still held
    fh.close()


# --- collect-only semantics (skip_sync) -------------------------------------------

def test_skip_sync_is_true_collect_only(monkeypatch):
    # CLI without --sync-db: Parquet only — NO PG sync subprocess AND no local
    # mirror refresh (PG unchanged → nothing to mirror).
    sync_calls = []
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (sync_calls.append(argv), {"returncode": 0})[1])
    monkeypatch.setattr(ds, "_local_refresh",
                        lambda: (_ for _ in ()).throw(AssertionError("refresh must not run")))
    res = ds.run_source("polygon_news", trigger_source="cli", skip_sync=True)
    assert res["status"] == "succeeded"
    assert sync_calls == []                                   # no PG sync
    assert "skipped" in res["local_refresh"]                  # no local refresh
    # default (scheduler/API) path still refreshes
    monkeypatch.setattr(ds, "_local_refresh", lambda: {"ok": True})
    res = ds.run_source("polygon_news")
    assert res["local_refresh"] == {"ok": True}


# --- startup seed must not depend on PG -------------------------------------------

def test_seed_skipped_fast_when_pg_unreachable(monkeypatch):
    import time as _time
    monkeypatch.setattr(ds, "_pg_reachable", lambda timeout=3.0: False)
    constructed = []
    monkeypatch.setattr("src.service.job_runs_store.JobRunsStore",
                        lambda dal: constructed.append(1))
    t0 = _time.monotonic()
    ds._seed_last_attempts()                                  # must return, not hang
    assert _time.monotonic() - t0 < 1.0
    assert constructed == []                                  # PG never touched


def test_pg_reachable_probe_is_bounded(monkeypatch):
    # closed local port → refused immediately → False (never the ~2min TCP hang)
    import time as _time
    monkeypatch.setattr("src.tools.db_config.load_database_url",
                        lambda p: "postgresql://u:p@127.0.0.1:9/db")
    t0 = _time.monotonic()
    assert ds._pg_reachable(timeout=1.0) is False
    assert _time.monotonic() - t0 < 5.0


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


def test_adapter_universe_unavailable_fails_loud(monkeypatch):
    # 3e-E: the collectors' legacy tickers_core default is retired — no scope
    # means the run FAILS (fail loud), never silently-collect-something-else.
    import scripts.collection.collect_finnhub_news as cfn
    monkeypatch.setattr(cfn, "run_incremental",
                        lambda **kw: (_ for _ in ()).throw(
                            AssertionError("adapter must not run without scope")))
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: [])
    res = ds.run_source("finnhub_news")
    assert res["status"] == "failed"
    assert "scope" in res["error"]


def test_run_source_explicit_tickers_and_skip_sync(monkeypatch):
    # The daily_update thin wrapper passes an explicit ticker list (--tickers)
    # and collect-only mode (no --sync-db → skip_sync) through run_source.
    import scripts.collection.collect_polygon_news as cpn
    seen = {}

    def _fake_run(tickers_arg=None, progress_cb=None, **kw):
        seen["tickers_arg"] = tickers_arg
        return {"mode": "incremental", "new_articles": 1}

    monkeypatch.setattr(cpn, "run_incremental", _fake_run)
    monkeypatch.setattr(ds, "_resolve_price_scope",
                        lambda: (_ for _ in ()).throw(AssertionError("must not resolve")))
    calls = []
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (calls.append(argv), {"returncode": 0})[1])
    res = ds.run_source("polygon_news", trigger_source="cli",
                        tickers=["AAPL", "NVDA"], skip_sync=True)
    assert res["status"] == "succeeded" and res["ticker_count"] == 2
    assert seen["tickers_arg"] == "AAPL,NVDA"
    assert calls == []          # skip_sync: NO PG sync subprocess


def test_run_now_choke_point_covers_all_sources(monkeypatch):
    # finding-4 regression: local_incremental writes market_data.db, so Run now
    # must pass require_db_write for EVERY source — not just provider fetches.
    from src.api.routes import schedule as sr
    gated = []
    monkeypatch.setattr(sr, "require_db_write", lambda action, ctx: gated.append(ctx["source"]))
    monkeypatch.setattr(sr, "run_source", lambda *a, **k: {"status": "succeeded"})
    for source in ("local_incremental", "polygon_news"):
        out = sr.run_now(source)
        assert out["status"] == "started"
    assert gated == ["local_incremental", "polygon_news"]


def test_last_result_surfaces_skips_in_snapshot(tmp_path):
    # finding-1 regression: Run now is fire-and-return, and a skip writes NO
    # job_runs row — last_result in the snapshot is the UI's only trace of it.
    monkey_fh = _hold_flock(tmp_path, "source_polygon_news")  # "CLI" holds the lock
    try:
        res = ds.run_source("polygon_news")
        assert res["status"] == "skipped"
    finally:
        monkey_fh.close()
    snap = ds.status_snapshot()["polygon_news"]
    assert snap["last_result"]["status"] == "skipped"
    assert "another process" in snap["last_result"]["reason"]
    assert snap["last_result"]["at"]                      # timestamped
    # a subsequent successful run overwrites the skip
    assert ds.run_source("polygon_news")["status"] == "succeeded"
    snap = ds.status_snapshot()["polygon_news"]
    assert snap["last_result"]["status"] == "succeeded"


# --- price_backfill: direct local writer source (2b·3) -----------------------------

def test_price_backfill_source_registered():
    d = ds.SOURCES["price_backfill"]
    assert d.adapter == ("src.market_data_direct", "backfill_prices_direct")
    assert d.ibkr is True and d.universe_tickers is True and d.sync_flag is None
    assert ds.source_config("price_backfill")["enabled"] is False  # default-off


def test_price_backfill_uses_planner_scope_no_pg_no_mirror(monkeypatch):
    # v1.3: price_backfill is gap-planned → it runs the PLANNER for scope (NOT the full universe)
    # and passes the planned tickers + lookback_days to the executor; still no PG sync / mirror.
    import src.market_data_direct as mdd
    from src.scheduler_planner import BackfillPlan
    seen = {}

    def _fake_backfill(tickers_arg=None, lookback_days=None, progress_cb=None, **kw):
        seen["tickers_arg"] = tickers_arg
        seen["lookback_days"] = lookback_days
        if progress_cb:
            progress_cb(1, 1, "AAPL")
        return {"provider": "ibkr", "tickers_scanned": 1, "rows_added": 5, "errors": {}}

    monkeypatch.setattr(mdd, "backfill_prices_direct", _fake_backfill)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    # planner picks AAPL with a 3-day window (NVDA had no gaps)
    monkeypatch.setattr(ds, "_plan_price_backfill_scope",
                        lambda scope: BackfillPlan(tickers=["AAPL"], lookback_days=3,
                                                   candidate_count=1))
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(AssertionError("no PG sync for direct writer")))
    monkeypatch.setattr(ds, "_local_refresh",
                        lambda: (_ for _ in ()).throw(AssertionError("no _local_refresh for direct writer")))
    res = ds.run_source("price_backfill")
    assert res["status"] == "succeeded"
    assert seen["tickers_arg"] == "AAPL"          # PLANNED scope, not the full universe
    assert seen["lookback_days"] == 3             # planned window
    assert res["plan"]["tickers"] == ["AAPL"]
    assert res["local_refresh"]["skipped"] == "direct local writer (no PG mirror)"


def test_local_incremental_still_runs_local_refresh(monkeypatch):
    # regression for the guard: local_incremental (adapter=None, sync_flag=None) IS the
    # mirror — it must STILL call _local_refresh (the guard only skips DIRECT adapters).
    ran = {"refresh": False}
    monkeypatch.setattr(ds, "_local_refresh", lambda: ran.__setitem__("refresh", True) or {"ok": True})
    res = ds.run_source("local_incremental")
    assert res["status"] == "succeeded" and ran["refresh"] is True
    assert res["local_refresh"] == {"ok": True}


def test_price_backfill_serializes_behind_ibkr_lock(monkeypatch):
    import src.market_data_direct as mdd
    monkeypatch.setattr(mdd, "backfill_prices_direct",
                        lambda **kw: {"tickers_scanned": 0, "rows_added": 0, "errors": {}})
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])
    monkeypatch.setattr(ds, "_IBKR_LOCK_TIMEOUT_S", 0.05)  # fast timeout → skip, not 30min block
    assert ds._IBKR_LOCK.acquire(blocking=False)           # someone holds the gateway
    try:
        res = ds.run_source("price_backfill")              # IBKR busy → must SKIP, not block
        assert res["status"] == "skipped" and "IBKR" in res["reason"]
    finally:
        ds._IBKR_LOCK.release()


def test_price_backfill_empty_scope_fails_loud(monkeypatch):
    import src.market_data_direct as mdd
    monkeypatch.setattr(mdd, "backfill_prices_direct",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("must not run without scope")))
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: [])
    res = ds.run_source("price_backfill")
    assert res["status"] == "failed" and "scope" in res["error"]


# --- v1.2: durable scheduler_state persistence ------------------------------------

def test_run_source_persists_attempt_and_outcome_to_local_state(monkeypatch):
    # a real run_source records last_attempt + the succeeded outcome in the LOCAL state store
    # (recoverable + visible-failure), independently of PG telemetry.
    import scripts.collection.collect_polygon_news as cpn
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: {"mode": "up_to_date", "new_articles": 0})
    ds.run_source("polygon_news", trigger_source="api")
    row = ds._state_store().get("polygon_news")
    assert row is not None
    assert row["last_status"] == "succeeded" and row["last_error"] is None
    assert row["last_attempt"] is not None
    assert row["last_result"]["status"] == "succeeded"


def test_run_source_failure_persists_error_locally(monkeypatch):
    import scripts.collection.collect_polygon_news as cpn
    def _boom(*a, **k):
        raise RuntimeError("provider exploded")
    monkeypatch.setattr(cpn, "run_incremental", _boom)
    res = ds.run_source("polygon_news", trigger_source="api")
    assert res["status"] == "failed"
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "failed" and "provider exploded" in row["last_error"]


def test_skip_does_not_overwrite_durable_outcome(monkeypatch):
    # a real failure is recorded; a later in-process SKIP (per-source lock busy) must NOT clobber
    # the durable last_error (skips aren't persisted to the state store).
    import scripts.collection.collect_polygon_news as cpn
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("real failure")))
    ds.run_source("polygon_news")
    assert ds._state_store().get("polygon_news")["last_error"] == "real failure"[:200] or \
        "real failure" in ds._state_store().get("polygon_news")["last_error"]
    # now force a skip: hold the per-source lock so run_source returns 'already running'
    ds._SOURCE_LOCKS["polygon_news"].acquire()
    try:
        skip = ds.run_source("polygon_news")
        assert skip["status"] == "skipped"
    finally:
        ds._SOURCE_LOCKS["polygon_news"].release()
    # durable failure still visible (skip not persisted)
    assert "real failure" in ds._state_store().get("polygon_news")["last_error"]


def test_seed_last_attempts_from_local_state(monkeypatch):
    # seed continuity from the LOCAL store (no PG): a recorded attempt seeds _LAST_ATTEMPT.
    from datetime import datetime, timezone
    when = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)
    ds._state_store().record_attempt("polygon_news", when)
    monkeypatch.setattr(ds, "_pg_reachable", lambda timeout=3.0: False)  # PG down → local only
    monkeypatch.setattr(ds, "_LAST_ATTEMPT", {})
    ds._seed_last_attempts()
    assert ds._LAST_ATTEMPT.get("polygon_news") == when


def test_ibkr_lock_skip_does_not_leave_durable_running(monkeypatch):
    # v1.2a HIGH fix: record_attempt is AFTER the IBKR-lock gate. A prior failure is durable;
    # then an IBKR-busy skip must NOT overwrite it with 'running' (skips don't touch durable state).
    # Seed a prior failed outcome on an IBKR source (price_backfill).
    ds._state_store().record_attempt("price_backfill",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome("price_backfill", status="failed",
                                     error="earlier gateway failure", result={"e": 1})
    # hold the shared IBKR lock so run_source skips at the gate (before record_attempt).
    assert ds._IBKR_LOCK.acquire(timeout=2)
    monkeypatch.setattr(ds, "_IBKR_LOCK_TIMEOUT_S", 0.05)   # fast skip, no 1800s wait
    try:
        res = ds.run_source("price_backfill")
        assert res["status"] == "skipped" and "IBKR gateway busy" in res["reason"]
    finally:
        ds._IBKR_LOCK.release()
    row = ds._state_store().get("price_backfill")
    assert row["last_status"] == "failed"            # NOT 'running' — skip didn't clobber it
    assert row["last_error"] == "earlier gateway failure"


# --- v1.3: gap-aware price_backfill (planner + partial/continuation + attended + 2 gates) ----

def _seed_market_coverage(tmp_path, *, missing_days_by_ticker, provider_errors=None):
    """Build a synthetic market_data.db so the REAL _plan_price_backfill_scope (coverage→plan)
    can run end-to-end — exercises GATE 1 (coverage window == planner max_days) for real."""
    import sqlite3
    from src.market_data_admin import _PRICES_SCHEMA
    from src.market_data_direct import _ensure_provider_sync_tables
    db = tmp_path / "market_data.db"
    c = sqlite3.connect(db); c.executescript(_PRICES_SCHEMA); _ensure_provider_sync_tables(c)
    # full 26-bar days for any (ticker, day) NOT in its missing set, across the recent window
    from datetime import date, timedelta
    universe = set(missing_days_by_ticker)
    today = date(2026, 6, 24)
    for t in universe:
        miss = set(missing_days_by_ticker[t])
        for back in range(0, 8):   # include today (a complete session at now_et 17:00 ET)
            d = today - timedelta(days=back)
            if d.weekday() >= 5 or d.isoformat() in miss:
                continue   # weekend or an intentional gap → no bars
            for i in range(26):
                dt = f"{d.isoformat()}T{13+i//4:02d}:{(i%4)*15:02d}:00+0000"
                c.execute("INSERT OR IGNORE INTO prices VALUES(?,?,'15min',1,1,1,1,1)", (t, dt))
    for tk, err in (provider_errors or {}).items():
        c.execute("INSERT INTO provider_sync_meta(provider,ticker,interval,last_success,"
                  "last_bar_datetime,last_error,rows_added,updated_at) VALUES('ibkr',?,'15min',"
                  "NULL,NULL,?,0,'2026-06-24T16:00:00+0000')", (tk, err))
    c.commit(); c.close()
    return db


def test_v13_gate1_coverage_window_matches_planner_max_days(monkeypatch, tmp_path):
    # GATE 1: the helper queries coverage with lookback == _BACKFILL_MAX_DAYS, so a selected gap
    # is within reach of the executor's lookback_days. Assert the planned lookback ≤ max_days AND
    # reaches the gap.
    import src.market_data_direct as mdd
    db = _seed_market_coverage(tmp_path, missing_days_by_ticker={"AAPL": ["2026-06-22"], "NVDA": []})
    monkeypatch.setattr(mdd, "resolve_market_db_path", lambda: str(db))
    monkeypatch.setattr(ds, "_BACKFILL_MAX_DAYS", 5)   # match the 7-day seed window (deterministic)
    # freeze "today" so the coverage window aligns with the 6/24-relative seed (deterministic)
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    _et = datetime(2026, 6, 24, 17, 0, tzinfo=ZoneInfo("America/New_York"))
    plan = ds._plan_price_backfill_scope(["AAPL", "NVDA"], today=date(2026, 6, 24), now_et=_et)
    assert plan.tickers == ["AAPL"]                         # only AAPL has a complete-day gap
    assert 0 < plan.lookback_days <= 5                      # within max_days, reaches the 6/22 gap


def test_v13_gate2_provider_errors_exclude_unresolvable(monkeypatch, tmp_path):
    # GATE 2: an LC-style provider_sync_meta.last_error feeds exclude_tickers → LC never planned.
    import src.market_data_direct as mdd
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    db = _seed_market_coverage(tmp_path,
                               missing_days_by_ticker={"AAPL": ["2026-06-22"], "LC": ["2026-06-22"]},
                               provider_errors={"LC": "contract not found"})
    monkeypatch.setattr(mdd, "resolve_market_db_path", lambda: str(db))
    monkeypatch.setattr(ds, "_BACKFILL_MAX_DAYS", 5)   # match the seed window (deterministic)
    _et = datetime(2026, 6, 24, 17, 0, tzinfo=ZoneInfo("America/New_York"))
    plan = ds._plan_price_backfill_scope(["AAPL", "LC"], today=date(2026, 6, 24), now_et=_et)
    assert "LC" not in plan.tickers                         # excluded, not scheduled
    assert any(e["ticker"] == "LC" for e in plan.excluded)
    assert plan.tickers == ["AAPL"]


def test_v13_partial_when_deferred_and_writes_continuation(monkeypatch):
    import src.market_data_direct as mdd
    from src.scheduler_planner import BackfillPlan
    monkeypatch.setattr(mdd, "backfill_prices_direct",
                        lambda **kw: {"tickers_scanned": 1, "rows_added": 3, "errors": {}})
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA", "TSLA"])
    monkeypatch.setattr(ds, "_plan_price_backfill_scope",
                        lambda scope: BackfillPlan(tickers=["AAPL"], lookback_days=5,
                                                   deferred=["NVDA", "TSLA"], candidate_count=3))
    res = ds.run_source("price_backfill", trigger_source="api")
    assert res["status"] == "partial"
    row = ds._state_store().get("price_backfill")
    assert row["last_status"] == "partial"
    assert row["continuation"]["deferred"] == ["NVDA", "TSLA"]


def test_v13_attended_scheduler_skips_pending_continuation(monkeypatch):
    import src.market_data_direct as mdd
    # a prior partial left a continuation
    ds._state_store().record_attempt("price_backfill",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome("price_backfill", status="partial", error=None,
                                     result={}, continuation={"deferred": ["NVDA"]})
    ran = {"n": 0}
    monkeypatch.setattr(mdd, "backfill_prices_direct",
                        lambda **kw: ran.__setitem__("n", ran["n"] + 1) or {"rows_added": 0, "errors": {}})
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["NVDA"])
    # SCHEDULER trigger → must SKIP (attended; no auto-resume), executor not called
    sched = ds.run_source("price_backfill", trigger_source="scheduler")
    assert sched["status"] == "skipped" and "manual continue" in sched["reason"]
    assert ran["n"] == 0
    # durable partial untouched by the skip
    assert ds._state_store().get("price_backfill")["last_status"] == "partial"


def test_v13a_manual_continue_consumes_saved_deferred_not_fresh_plan(monkeypatch):
    # v1.3a HIGH fix: a manual continue must execute the SAVED deferred scope, NOT a fresh
    # re-plan. Saved continuation = ['NVDA'], but the fresh planner would return ['AAPL'] —
    # the executor must receive NVDA (proving the saved remainder is what's serviced).
    import src.market_data_direct as mdd
    from src.scheduler_planner import BackfillPlan
    ds._state_store().record_attempt("price_backfill",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome("price_backfill", status="partial", error=None,
                                     result={}, continuation={"deferred": ["NVDA"], "lookback_days": 7})
    seen = {}
    monkeypatch.setattr(mdd, "backfill_prices_direct",
                        lambda **kw: seen.update(kw) or {"rows_added": 2, "errors": {}})
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    # the fresh planner would pick AAPL — but the manual continue must IGNORE it for the backlog
    monkeypatch.setattr(ds, "_plan_price_backfill_scope",
                        lambda scope, **k: BackfillPlan(tickers=["AAPL"], lookback_days=3, candidate_count=1))
    res = ds.run_source("price_backfill", trigger_source="api")
    assert res.get("resumed_continuation") is True
    assert seen["tickers_arg"] == "NVDA"          # SAVED deferred, not the fresh-plan AAPL
    assert seen["lookback_days"] == 7             # saved continuation's window
    assert res["status"] == "succeeded"           # remainder exhausted → partial cleared
    assert ds._state_store().get("price_backfill")["continuation"] is None


def test_v13a_manual_continue_carries_remainder_when_over_budget(monkeypatch):
    # saved deferred larger than max_tickers → batch this run, carry the rest forward (still partial).
    import src.market_data_direct as mdd
    ds._state_store().record_attempt("price_backfill",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome("price_backfill", status="partial", error=None, result={},
                                     continuation={"deferred": ["A", "B", "C", "D"], "lookback_days": 5})
    monkeypatch.setattr(ds, "_BACKFILL_MAX_TICKERS", 2)
    seen = {}
    monkeypatch.setattr(mdd, "backfill_prices_direct",
                        lambda **kw: seen.update(kw) or {"rows_added": 1, "errors": {}})
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["A", "B", "C", "D"])
    res = ds.run_source("price_backfill", trigger_source="api")
    assert seen["tickers_arg"] == "A,B"           # batch of max_tickers from the saved deferred
    assert res["status"] == "partial"
    cont = ds._state_store().get("price_backfill")["continuation"]
    assert cont["deferred"] == ["C", "D"]         # remainder carried forward


def test_v13_no_gaps_is_noop_success(monkeypatch):
    import src.market_data_direct as mdd
    from src.scheduler_planner import BackfillPlan
    called = {"n": 0}
    monkeypatch.setattr(mdd, "backfill_prices_direct",
                        lambda **kw: called.__setitem__("n", called["n"] + 1) or {"rows_added": 0, "errors": {}})
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])
    monkeypatch.setattr(ds, "_plan_price_backfill_scope",
                        lambda scope: BackfillPlan(tickers=[], lookback_days=0))
    res = ds.run_source("price_backfill", trigger_source="scheduler")
    assert res["status"] == "succeeded" and called["n"] == 0   # no fillable gaps → executor not called
    assert res["collect"]["planned"] == 0


def test_v14_status_snapshot_exposes_durable_state_and_gap_planned(monkeypatch):
    # v1.4: GET /schedule data must surface the durable scheduler_state (partial + continuation +
    # error) + the gap_planned flag, so the UI can show partial→補抓 and last failure across restarts.
    ds._state_store().record_attempt("price_backfill",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome("price_backfill", status="partial", error=None,
                                     result={"rows_added": 3},
                                     continuation={"deferred": ["NVDA", "TSLA"], "lookback_days": 5})
    snap = ds.status_snapshot()
    pb = snap["price_backfill"]
    assert pb["gap_planned"] is True
    assert pb["durable_state"]["last_status"] == "partial"
    assert pb["durable_state"]["continuation"]["deferred"] == ["NVDA", "TSLA"]
    # a non-gap-planned source: flag false, durable_state present-or-None (no crash)
    assert snap["polygon_news"]["gap_planned"] is False


def test_v14a_status_snapshot_no_create_on_fresh_db(tmp_path, monkeypatch):
    # v1.4a MED fix: a pure status read must NOT materialize profile_state.db / scheduler_state.
    # Point at a FRESH (absent) profile DB, reset the cached store, call status_snapshot → the
    # DB/table must NOT be created, and durable_state is None for every source.
    import os
    fresh = tmp_path / "fresh_profile.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(fresh))
    monkeypatch.setattr(ds, "_SCHED_STATE", None)   # force resolution against the fresh path
    snap = ds.status_snapshot()
    assert not fresh.exists(), "status read must not create profile_state.db"
    assert all(s["durable_state"] is None for s in snap.values())
    # and a no-create read of an absent DB returns {} (helper-level)
    from src.scheduler_state import read_all_if_exists
    assert read_all_if_exists(str(fresh)) == {} and not fresh.exists()
