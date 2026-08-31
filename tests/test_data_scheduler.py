"""Tests for the app-owned per-source data scheduler (slice 3e-D v1)."""

from __future__ import annotations

import threading
import sqlite3
import sys
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import prices_runtime
import src.service.data_scheduler as ds
from src.active_universe import ActiveUniverseUnavailable
from src.profile_state import ProfileStateStore
from src.service.job_runs_store import JobRunsLocalStore as _REAL_JOB_RUNS_LOCAL_STORE
from src.service.security_lifecycle_automation_config import ENABLED_KEY

_NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
_REAL_RESOLVE_PRICE_SCOPE = ds._resolve_price_scope
ACTIVE_SOURCE_IDS = {
    "polygon_news",
    "finnhub_news",
    "ibkr_news",
    "ibkr_prices",
    "sec_corporate_actions",
    "fred_series",
    "fred_release_dates",
    "finnhub_economic_calendar",
    "finnhub_earnings_calendar",
    "finnhub_ipo_calendar",
}
MACRO_SOURCE_IDS = {
    "fred_series",
    "fred_release_dates",
    "finnhub_economic_calendar",
    "finnhub_earnings_calendar",
    "finnhub_ipo_calendar",
}
RETIRED_SOURCE_IDS = {"price_backfill", "local_incremental", "iv_history"}


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    """Fresh profile store per test; reset scheduler runtime state; never touch
    the real DAL / subprocesses / local market DB — and CRITICALLY, stub both
    in-process news adapters so no test can fire a real provider API call."""
    store = ProfileStateStore(tmp_path / "profile_state.db")
    # writer route unless a test explicitly patches the route.
    store.set_setting("use_local_news", None)
    monkeypatch.setattr(ds, "_store", lambda: store)
    monkeypatch.setattr(ds, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(ds, "_LAST_RESULT", {})
    automation_result = {
        "result_version": 2,
        "case_outcomes": {},
        "status": "succeeded",
        "reason": None,
        "selected": 0,
        "processed": 0,
        "accepted": 0,
        "drafted": 0,
        "blocked": 0,
        "failed": 0,
        "skipped_current": 0,
        "case_ids": [],
    }
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda *, limit, now, transition_mutation_allowed: automation_result,
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "record_security_lifecycle_automation_result",
        lambda result, *, now: True,
        raising=False,
    )
    # v1.2: isolate the durable scheduler-state store to a per-test DB (never the real
    # profile_state.db). Set ARKSCOPE_PROFILE_DB so BOTH the write store (_state_store) and the
    # v1.4a no-create read (resolve_profile_state_db_path) resolve to this tmp path.
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    # N8a cutover writes a durable audit marker to the real market DB. Scheduler tests are
    # hermetic and must not let that live marker change legacy-route expectations.
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "market_data.db"))
    # S-J strict provider preflight reads process env after apply_env. Seed dummy
    # managed keys so existing scheduler tests keep exercising their mocked
    # writers; explicit not_configured tests delenv what they need.
    monkeypatch.setenv("MASSIVE_API_KEY", "pk_test")
    monkeypatch.setenv("FINNHUB_API_KEY", "fk_test")
    monkeypatch.setenv("IBKR_HOST", "127.0.0.1")
    monkeypatch.setenv("IBKR_PORT", "4001")
    monkeypatch.setenv("IBKR_CLIENT_ID", "1")
    from src.scheduler_state import SchedulerStateStore
    monkeypatch.setattr(ds, "_SCHED_STATE", SchedulerStateStore(tmp_path / "profile_state.db"))
    # cross-process file locks go to a per-test dir — NEVER the repo data/locks/
    # (a live sidecar's flocks would make these tests skip spuriously, and vice versa)
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    # default stubs: no real subprocess or telemetry
    monkeypatch.setattr(ds, "_run_subprocess", lambda argv: {"returncode": 0})
    # active-universe scope: stub a non-empty default so price/universe sources are
    # hermetic (no real profile DB). Tests asserting the empty-scope path override this.
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    import src.collectors.finnhub_news as cfn
    import src.collectors.polygon_news as cpn
    import src.collectors.sec_corporate_actions as sca
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: {"mode": "up_to_date", "new_articles": 0})
    monkeypatch.setattr(cfn, "run_incremental",
                        lambda *a, **k: {"mode": "up_to_date", "new_articles": 0})
    monkeypatch.setattr(
        sca,
        "run_incremental",
        lambda *a, **k: {
            "status": "succeeded",
            "tickers_scanned": 2,
            "observations_observed": 0,
            "kinds_observed": 0,
            "errors": {},
        },
    )
    monkeypatch.setattr("src.news_providers.make_news_provider",
                        lambda source, **k: object())
    monkeypatch.setattr(
        "src.news_direct.backfill_news_direct",
        lambda tickers, *, source, provider, progress_cb=None, **k: {
            "source": source,
            "tickers_scanned": len(tickers),
            "articles_added": 0,
            "errors": {},
        },
    )

    class _NoStore:
        def create_run(self, *a, **k):
            return None

        def finish_run(self, *a, **k):
            return False

    monkeypatch.setattr("src.service.job_runs_store.JobRunsLocalStore", lambda profile_db: _NoStore())
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: object())
    yield store


# --- config -------------------------------------------------------------------

def test_defaults_everything_disabled():
    assert set(ds.SOURCES) == ACTIVE_SOURCE_IDS
    for source in ds.SOURCES:
        cfg = ds.source_config(source)
        assert cfg["enabled"] is False  # nothing fetches until the user opts in
        assert cfg["interval_minutes"] == ds.SOURCES[source].default_interval_min


def test_no_active_runtime_source_uses_migrate_to_supabase_sync():
    source = Path(ds.__file__).read_text(encoding="utf-8")

    assert set(ds.SOURCES) == ACTIVE_SOURCE_IDS
    assert all(not hasattr(source_def, "sync_flag") for source_def in ds.SOURCES.values())
    assert "migrate_to_supabase.py" not in source
    assert "_local_refresh(" not in source


def test_scheduler_runtime_no_longer_references_migrate_to_supabase_script():
    assert "migrate_to_supabase.py" not in Path(ds.__file__).read_text(encoding="utf-8")


def test_scheduler_source_defs_have_no_legacy_collector_plumbing():
    from dataclasses import fields

    field_names = {field.name for field in fields(ds.SourceDef)}

    assert set(ds.SOURCES) == ACTIVE_SOURCE_IDS
    assert {"collector", "sync_flag", "coverage_repair_disabled"}.isdisjoint(field_names)
    for source_def in ds.SOURCES.values():
        assert not hasattr(source_def, "collector")
        assert not hasattr(source_def, "sync_flag")
        assert not hasattr(source_def, "coverage_repair_disabled")


def test_status_snapshot_provider_fetch_tracks_live_fetch_paths():
    snap = ds.status_snapshot()

    assert set(snap) == ACTIVE_SOURCE_IDS
    for source in ACTIVE_SOURCE_IDS:
        assert snap[source]["provider_fetch"] is True
        assert "control_mode" not in snap[source]
        assert "retired" not in snap[source]


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
    ds._LAST_ATTEMPT["ibkr_prices"] = _NOW - timedelta(minutes=5)  # not due
    fired = []
    out = ds.tick_once(_NOW, fire=fired.append)
    assert out == fired == ["finnhub_news"]


def test_empty_profile_settings_snapshot_never_makes_lifecycle_automation_due():
    assert ds._store().get_settings_snapshot(
        ds.SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS
    ) == {}
    state = ds._security_lifecycle_automation_config_state()

    assert state.valid is True
    assert state.config is not None
    for now in (
        datetime(1970, 1, 1, tzinfo=timezone.utc),
        datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc),
    ):
        assert ds._security_lifecycle_automation_is_due(state, now=now) is False


def test_tick_uses_the_lock_owned_lifecycle_run_and_record_boundary(monkeypatch):
    ds._store().set_setting(ENABLED_KEY, "true")
    events = []
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda *, limit, now, transition_mutation_allowed: events.append(
            ("owned", limit, now)
        )
        or {
            "result_version": 2,
            "case_outcomes": {},
            "status": "succeeded",
            "reason": None,
            "selected": 0,
            "processed": 0,
            "accepted": 0,
            "drafted": 0,
            "blocked": 0,
            "failed": 0,
            "skipped_current": 0,
            "case_ids": [],
        },
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "run_security_lifecycle_automation",
        lambda **_kwargs: pytest.fail("unrecorded lifecycle runner reached"),
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "record_security_lifecycle_automation_result",
        lambda *_args, **_kwargs: pytest.fail("separate lifecycle recorder reached"),
    )

    assert ds.tick_once(_NOW, fire=lambda _source: None) == []
    assert events == [("owned", 2, _NOW)]


def test_tick_runs_due_ticker_transitions_before_provider_dispatch(monkeypatch):
    ds._store().set_setting(ENABLED_KEY, "true")
    events = []
    ds.set_source_config("finnhub_news", enabled=True, interval_minutes=60)
    automation_result = {
        "status": "succeeded",
        "reason": None,
        "selected": 0,
        "processed": 0,
        "accepted": 0,
        "drafted": 0,
        "blocked": 0,
        "failed": 0,
        "skipped_current": 0,
        "case_ids": [],
    }
    transition_result = {
        "status": "succeeded",
        "reason": None,
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
    }
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda *, limit, now, transition_mutation_allowed: events.append(
            ("automation", limit, now)
        )
        or automation_result,
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda *, now, allow_automation_approved, transition_mutation_allowed: events.append(
            ("transitions", now)
        )
        or transition_result,
    )
    monkeypatch.setattr(
        ds,
        "record_ticker_identity_scheduler_result",
        lambda result, *, now: events.append(("transition-result", result, now)),
        raising=False,
    )

    fired = ds.tick_once(
        _NOW,
        fire=lambda source: events.append(("provider", source)),
    )

    assert fired == ["finnhub_news"]
    assert events == [
        ("automation", 2, _NOW),
        ("transitions", _NOW),
        ("transition-result", transition_result, _NOW),
        ("provider", "finnhub_news"),
    ]


def test_tick_runs_lifecycle_automation_before_transitions_and_provider_dispatch(
    monkeypatch,
):
    ds._store().set_setting(ENABLED_KEY, "true")
    events = []
    ds.set_source_config("finnhub_news", enabled=True, interval_minutes=60)
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda *, limit, now, transition_mutation_allowed: events.append(
            ("automation", limit, now)
        )
        or {
            "status": "succeeded",
            "reason": None,
            "selected": 0,
            "processed": 0,
            "accepted": 0,
            "drafted": 0,
            "blocked": 0,
            "failed": 0,
            "skipped_current": 0,
            "case_ids": [],
        },
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda *, now, allow_automation_approved, transition_mutation_allowed: events.append(
            ("transitions", now)
        )
        or {
            "status": "succeeded",
            "reason": None,
            "due": 0,
            "applied": 0,
            "needs_review": 0,
            "already_applied": 0,
            "transition_ids": [],
            "failed_transition_ids": [],
        },
    )
    monkeypatch.setattr(
        ds,
        "record_ticker_identity_scheduler_result",
        lambda result, *, now: events.append(("transition-result", now)),
    )

    fired = ds.tick_once(
        _NOW,
        fire=lambda source: events.append(("provider", source)),
    )

    assert fired == ["finnhub_news"]
    assert events == [
        ("automation", 2, _NOW),
        ("transitions", _NOW),
        ("transition-result", _NOW),
        ("provider", "finnhub_news"),
    ]


def test_lifecycle_automation_uses_durable_five_minute_clock_and_batch_limit(
    monkeypatch,
):
    ds._store().set_setting(ENABLED_KEY, "true")
    calls = []
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda *, limit, now, transition_mutation_allowed: calls.append(
            (limit, now, transition_mutation_allowed())
        )
        or {},
    )
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda **_kwargs: {
            "status": "succeeded",
            "reason": None,
            "due": 0,
            "applied": 0,
            "needs_review": 0,
            "already_applied": 0,
            "transition_ids": [],
            "failed_transition_ids": [],
        },
    )

    ds.tick_once(_NOW, fire=lambda _source: None)
    ds._state_store().record_attempt("security_lifecycle.automation", _NOW)
    ds.tick_once(_NOW + timedelta(seconds=30), fire=lambda _source: None)
    ds.tick_once(_NOW + timedelta(minutes=5), fire=lambda _source: None)

    assert calls == [
        (2, _NOW, False),
        (2, _NOW + timedelta(minutes=5), False),
    ]


def test_lifecycle_analysis_and_profile_mutation_are_independent_controls(
    monkeypatch,
):
    from src.service.security_lifecycle_automation_config import (
        SecurityLifecycleAutomationConfig,
        serialize_security_lifecycle_automation_config,
    )

    ds._store().update_settings(
        serialize_security_lifecycle_automation_config(
            SecurityLifecycleAutomationConfig(
                enabled=False,
                interval_minutes=5,
                batch_limit=1,
                apply_profile_transitions=True,
            )
        )
    )
    automation_calls = []
    transition_calls = []
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda **kwargs: automation_calls.append(kwargs),
    )
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda **kwargs: transition_calls.append(kwargs)
        or {
            "status": "succeeded",
            "reason": None,
            "due": 0,
            "applied": 0,
            "needs_review": 0,
            "already_applied": 0,
            "transition_ids": [],
            "failed_transition_ids": [],
        },
    )

    ds.tick_once(_NOW, fire=lambda _source: None)

    assert automation_calls == []
    mutation_allowed = transition_calls[0].pop("transition_mutation_allowed")
    assert mutation_allowed() is True
    assert transition_calls == [{"now": _NOW, "allow_automation_approved": True}]


def test_malformed_lifecycle_config_disables_analysis_and_mutation(monkeypatch):
    ds._store().set_setting(
        "security_lifecycle.automation.interval_minutes",
        "05",
    )
    automation_calls = []
    transition_calls = []
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda **kwargs: automation_calls.append(kwargs),
    )
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda **kwargs: transition_calls.append(kwargs)
        or {
            "status": "succeeded",
            "reason": None,
            "due": 0,
            "applied": 0,
            "needs_review": 0,
            "already_applied": 0,
            "transition_ids": [],
            "failed_transition_ids": [],
        },
    )

    ds.tick_once(_NOW, fire=lambda _source: None)

    assert automation_calls == []
    mutation_allowed = transition_calls[0].pop("transition_mutation_allowed")
    assert mutation_allowed() is False
    assert transition_calls == [{"now": _NOW, "allow_automation_approved": False}]


def test_tick_rereads_mutation_authority_after_lifecycle_analysis(monkeypatch):
    from src.service.security_lifecycle_automation_config import (
        APPLY_PROFILE_TRANSITIONS_KEY,
    )

    ds._store().update_settings(
        {
            ENABLED_KEY: "true",
            APPLY_PROFILE_TRANSITIONS_KEY: "true",
        }
    )
    boundary_reads = []
    transition_calls = []

    def run_analysis(*, limit, now, transition_mutation_allowed):
        del limit, now
        boundary_reads.append(transition_mutation_allowed())
        ds._store().set_setting(APPLY_PROFILE_TRANSITIONS_KEY, "false")
        boundary_reads.append(transition_mutation_allowed())
        return {}

    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        run_analysis,
    )
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda **kwargs: transition_calls.append(kwargs)
        or {
            "status": "succeeded",
            "reason": None,
            "due": 0,
            "applied": 0,
            "needs_review": 0,
            "already_applied": 0,
            "transition_ids": [],
            "failed_transition_ids": [],
        },
    )

    ds.tick_once(_NOW, fire=lambda _source: None)

    assert boundary_reads == [True, False]
    mutation_allowed = transition_calls[0].pop("transition_mutation_allowed")
    assert mutation_allowed() is False
    assert transition_calls == [{"now": _NOW, "allow_automation_approved": False}]


def test_tick_records_lifecycle_automation_failure_and_continues(monkeypatch):
    ds._store().set_setting(ENABLED_KEY, "true")
    events = []
    ds.set_source_config("finnhub_news", enabled=True, interval_minutes=60)
    failure = {
        "status": "unavailable",
        "reason": "automation_scheduler_failed",
        "selected": 0,
        "processed": 0,
        "accepted": 0,
        "drafted": 0,
        "blocked": 0,
        "failed": 0,
        "skipped_current": 0,
        "case_ids": [],
    }
    monkeypatch.setattr(
        ds,
        "run_and_record_security_lifecycle_automation",
        lambda *, limit, now, transition_mutation_allowed: (_ for _ in ()).throw(
            RuntimeError("private scheduler detail")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "security_lifecycle_automation_failure",
        lambda reason: events.append(("automation-failure", reason)) or failure,
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "record_security_lifecycle_automation_result",
        lambda result, *, now: events.append(("automation-result", result, now)),
        raising=False,
    )
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda *, now, allow_automation_approved, transition_mutation_allowed: events.append(
            ("transitions", now)
        )
        or {
            "status": "succeeded",
            "reason": None,
            "due": 0,
            "applied": 0,
            "needs_review": 0,
            "already_applied": 0,
            "transition_ids": [],
            "failed_transition_ids": [],
        },
    )
    monkeypatch.setattr(
        ds,
        "record_ticker_identity_scheduler_result",
        lambda result, *, now: events.append(("transition-result", now)),
    )

    fired = ds.tick_once(
        _NOW,
        fire=lambda source: events.append(("provider", source)),
    )

    assert fired == ["finnhub_news"]
    assert events == [
        ("automation-failure", "automation_scheduler_failed"),
        ("automation-result", failure, _NOW),
        ("transitions", _NOW),
        ("transition-result", _NOW),
        ("provider", "finnhub_news"),
    ]


def test_tick_deduplicates_ticker_transition_failure_and_records_recovery(
    tmp_path,
    monkeypatch,
):
    profile_path = tmp_path / "profile_state.db"
    telemetry = _REAL_JOB_RUNS_LOCAL_STORE(profile_path)
    failure = {
        "status": "partial",
        "reason": "transition_execution_failed",
        "due": 2,
        "applied": 1,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": ["slt_ok", "slt_failed"],
        "failed_transition_ids": ["slt_failed"],
    }
    recovered = {
        "status": "succeeded",
        "reason": None,
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
    }
    results = iter((failure, failure, recovered, recovered))
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda *, now, allow_automation_approved, transition_mutation_allowed: next(results),
    )

    for offset in range(4):
        ds.tick_once(_NOW + timedelta(seconds=offset), fire=lambda _source: None)

    runs = telemetry.list_runs(job_name="ticker_identity.transitions", limit=10)
    assert [(row["status"], row["error"]) for row in runs] == [
        ("succeeded", None),
        ("failed", "transition_execution_failed"),
    ]
    assert runs[1]["result"] == failure
    assert runs[0]["result"] == recovered


def test_tick_records_sanitized_unexpected_ticker_runner_failure_and_continues(
    tmp_path,
    monkeypatch,
):
    profile_path = tmp_path / "profile_state.db"
    telemetry = _REAL_JOB_RUNS_LOCAL_STORE(profile_path)
    ds.set_source_config("finnhub_news", enabled=True, interval_minutes=60)
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda *, now, allow_automation_approved, transition_mutation_allowed: (_ for _ in ()).throw(
            RuntimeError("private detail")
        ),
    )
    fired = []

    result = ds.tick_once(_NOW, fire=fired.append)

    assert result == fired == ["finnhub_news"]
    runs = telemetry.list_runs(job_name="ticker_identity.transitions", limit=10)
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert runs[0]["error"] == "ticker_identity_scheduler_failed"
    assert runs[0]["result"] == {
        "status": "unavailable",
        "reason": "ticker_identity_scheduler_failed",
        "due": 0,
        "applied": 0,
        "needs_review": 0,
        "already_applied": 0,
        "transition_ids": [],
        "failed_transition_ids": [],
    }
    assert "private detail" not in json.dumps(runs[0], sort_keys=True)


@pytest.mark.parametrize(
    "runner_result",
    [
        None,
        SimpleNamespace(
            get={
                "status": "succeeded",
                "reason": None,
                "due": 0,
                "applied": 0,
                "needs_review": 0,
                "already_applied": 0,
                "transition_ids": [],
                "failed_transition_ids": [],
            }.get
        ),
    ],
)
def test_tick_records_non_mapping_ticker_runner_result_as_failed_witness(
    tmp_path,
    monkeypatch,
    runner_result,
):
    profile_path = tmp_path / "profile_state.db"
    telemetry = _REAL_JOB_RUNS_LOCAL_STORE(profile_path)
    ds.set_source_config("finnhub_news", enabled=True, interval_minutes=60)
    monkeypatch.setattr(
        ds,
        "run_due_ticker_identity_transitions",
        lambda *, now, allow_automation_approved, transition_mutation_allowed: runner_result,
    )
    fired = []

    result = ds.tick_once(_NOW, fire=fired.append)

    assert result == fired == ["finnhub_news"]
    runs = telemetry.list_runs(job_name="ticker_identity.transitions", limit=10)
    assert [(row["status"], row["error"]) for row in runs] == [
        ("failed", "ticker_identity_scheduler_failed")
    ]


def test_tick_once_defers_extra_market_writers(monkeypatch):
    now = datetime(2026, 7, 4, tzinfo=timezone.utc)
    fired = []
    skipped = []

    monkeypatch.setattr(
        ds,
        "source_config",
        lambda source: {
            "enabled": source in {"ibkr_prices", "polygon_news"},
            "interval_minutes": 1,
        },
    )
    monkeypatch.setattr(
        ds,
        "_is_due",
        lambda source, current: source in {"ibkr_prices", "polygon_news"},
    )
    monkeypatch.setattr(ds, "_record_result", lambda result: skipped.append(result) or result)

    out = ds.tick_once(now, fire=fired.append)

    assert out == ["polygon_news"]
    assert fired == ["polygon_news"]
    assert skipped == [{
        "source": "ibkr_prices",
        "status": "skipped",
        "reason": "market_data.db writer already scheduled this tick",
        "skip_kind": "market_writer_backpressure",
    }]


def test_startup_burst_defers_all_extra_market_writers(monkeypatch):
    import src.service.data_scheduler as ds
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)
    due_sources = {
        "polygon_news",
        "finnhub_news",
        "ibkr_news",
        "ibkr_prices",
    }
    fired = []
    skipped = []

    monkeypatch.setattr(
        ds,
        "source_config",
        lambda source: {"enabled": source in due_sources, "interval_minutes": 1},
    )
    monkeypatch.setattr(ds, "_is_due", lambda source, current: source in due_sources)
    monkeypatch.setattr(ds, "_record_result", lambda result: skipped.append(result) or result)

    out = ds.tick_once(now, fire=fired.append)

    assert out == fired
    actual_writers = due_sources
    assert len(set(fired) & actual_writers) == 1
    deferred = [row for row in skipped if row.get("skip_kind") == "market_writer_backpressure"]
    assert {row["source"] for row in deferred} == actual_writers - set(fired)
    assert all(row["status"] == "skipped" for row in deferred)


def test_market_writer_backpressure_is_not_failed(monkeypatch):
    import src.service.data_scheduler as ds
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)

    monkeypatch.setattr(
        ds,
        "source_config",
        lambda source: {
            "enabled": source in {"polygon_news", "finnhub_news"},
            "interval_minutes": 1,
        },
    )
    monkeypatch.setattr(
        ds,
        "_is_due",
        lambda source, current: source in {"polygon_news", "finnhub_news"},
    )

    ds.tick_once(now, fire=lambda source: None)

    row = ds._state_store().get("finnhub_news")
    if row is not None:
        assert row["last_status"] != "failed"


# --- run_source ------------------------------------------------------------------

def test_run_source_provider_config_missing_returns_not_configured(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.news_direct.backfill_news_direct",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("provider must not run")),
    )

    res = ds.run_source("polygon_news", trigger_source="api")

    assert res == {
        "source": "polygon_news",
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": "massive",
        "field": "api_key",
    }
    assert ds._LAST_RESULT["polygon_news"]["status"] == "not_configured"


def test_polygon_news_keeps_its_source_id_but_uses_massive_config_authority():
    assert ds._SOURCE_PROVIDER_CONFIG["polygon_news"] == "massive"
    assert ds.SOURCES["polygon_news"].name == "polygon_news"
    assert ds.SOURCES["polygon_news"].news_direct_source == "polygon"


def test_normalized_massive_provider_missing_key_names_only_canonical_bridge(
    monkeypatch,
):
    monkeypatch.setattr("src.collectors.polygon_news.load_env", lambda: "")

    with pytest.raises(RuntimeError) as captured:
        ds._make_normalized_news_provider("polygon")

    message = str(captured.value)
    assert "MASSIVE_API_KEY" in message
    assert "POLYGON_API_KEY" not in message


def test_run_source_news_direct_when_use_local_news_on(monkeypatch, hermetic):
    # S3.2 default ON: polygon_news routes to the DIRECT-LOCAL writer — NO run_incremental (Parquet),
    import src.collectors.polygon_news as cpn
    hermetic.set_setting("use_local_news", None)  # unset resolves to the production default ON
    calls = {"run_incremental": 0, "sync": 0, "direct": 0, "provider": None}
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: calls.__setitem__("run_incremental", calls["run_incremental"] + 1))

    def _subproc(argv):
        if "--news" in argv:
            calls["sync"] += 1
        return {"returncode": 0}
    monkeypatch.setattr(ds, "_run_subprocess", _subproc)
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
    assert calls["sync"] == 0
    assert "local_refresh" not in res
    assert res["collect"]["source"] == "polygon" and res["ticker_count"] == 2


def _patch_news_write_route(monkeypatch, mode, reason="test route"):
    import src.news_normalized.routing as routing

    calls = []

    def _read_route(*args, **kwargs):
        calls.append((args, kwargs))
        return routing.NewsWriteRoute(mode, reason)

    monkeypatch.setattr(routing, "read_news_write_route", _read_route)
    return calls


def test_news_write_mode_classifier_is_exhaustive_for_current_modes():
    import src.news_normalized.routing as routing

    assert {
        mode: ds._classify_news_write_mode(mode)
        for mode in routing.NewsWriteMode
    } == {
        routing.NewsWriteMode.NORMALIZED: "direct_local",
        routing.NewsWriteMode.LEGACY_LOCAL: "direct_local",
        routing.NewsWriteMode.BLOCKED: "reject",
    }


def test_unknown_news_write_mode_fails_before_provider_adapter_worker_and_telemetry(
    monkeypatch,
):
    calls = {
        "provider_setup": 0,
        "provider_config": 0,
        "source_lock": 0,
        "source_flock": 0,
        "adapter": 0,
        "provider": 0,
        "writer": 0,
        "json_worker": 0,
        "prices_worker": 0,
        "subprocess": 0,
        "telemetry": 0,
    }

    class _CountingLock:
        def __init__(self, name):
            self.name = name

        def acquire(self, *args, **kwargs):
            calls[self.name] += 1
            return True

        def release(self):
            return None

        def locked(self):
            return False

    class _Telemetry:
        def create_run(self, *args, **kwargs):
            calls["telemetry"] += 1
            return 1

        def finish_run(self, *args, **kwargs):
            calls["telemetry"] += 1
            return True

    def _provider_setup():
        calls["provider_setup"] += 1
        return SimpleNamespace(required=False, reason=None, code=None)

    def _provider_config(source):
        calls["provider_config"] += 1
        return None

    def _called(name, result):
        def _inner(*args, **kwargs):
            calls[name] += 1
            return result
        return _inner

    monkeypatch.setattr(
        ds,
        "_read_news_write_route_for_scheduler",
        lambda source: SimpleNamespace(mode=object(), reason="future unreviewed mode"),
    )
    monkeypatch.setattr(
        "src.provider_config_runtime.provider_config_setup_state",
        _provider_setup,
    )
    monkeypatch.setattr(ds, "_provider_config_missing_for_source", _provider_config)
    monkeypatch.setitem(ds._SOURCE_LOCKS, "polygon_news", _CountingLock("source_lock"))
    monkeypatch.setitem(ds._SOURCE_FLOCKS, "polygon_news", _CountingLock("source_flock"))
    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store",
        lambda dal: _Telemetry(),
    )
    monkeypatch.setattr(
        "src.collectors.polygon_news.run_incremental",
        _called("adapter", {"mode": "up_to_date", "new_articles": 0}),
    )
    monkeypatch.setattr(
        "src.news_providers.make_news_provider",
        _called("provider", object()),
    )
    monkeypatch.setattr(
        "src.news_direct.backfill_news_direct",
        _called("writer", {"source": "polygon", "tickers_scanned": 0}),
    )
    monkeypatch.setattr(
        ds,
        "_run_sanitized_json_subprocess",
        _called("json_worker", {"returncode": 0, "payload": {}}),
    )
    monkeypatch.setattr(
        ds,
        "_run_sanitized_prices_worker_subprocess",
        _called("prices_worker", {"returncode": 0, "payload": {}}),
    )
    monkeypatch.setattr(
        ds,
        "_run_subprocess",
        _called("subprocess", {"returncode": 0}),
    )

    result = ds.run_source("polygon_news", trigger_source="manual")

    assert result == {
        "source": "polygon_news",
        "status": "failed",
        "code": "unsupported_news_write_mode",
        "reason_code": "unsupported_news_write_mode",
    }
    assert "ok" not in result
    assert calls == {name: 0 for name in calls}
    assert ds._state_store().get("polygon_news") is None


@pytest.mark.parametrize(
    ("source", "direct_source", "collector_module", "config_name", "collector_name",
     "provider_name"),
    [
        ("polygon_news", "polygon", "src.collectors.polygon_news",
         "CollectionConfig", "PolygonNewsCollector", "PolygonNormalizedProvider"),
        ("finnhub_news", "finnhub", "src.collectors.finnhub_news",
         "FinnhubConfig", "FinnhubNewsCollector", "FinnhubNormalizedProvider"),
    ],
)
def test_normalized_news_route_calls_writer_under_market_lock(
    monkeypatch, source, direct_source, collector_module, config_name, collector_name,
    provider_name,
):
    # NORMALIZED routes Polygon/Finnhub straight into the normalized writer with legacy projection.
    import importlib
    import sqlite3

    import src.market_data_admin as mda
    import src.market_data_direct as mdd
    import src.news_normalized.provider_adapters as adapters
    import src.news_normalized.routing as routing
    import src.news_normalized.store as store_module
    import src.news_normalized.writer as writer_module
    from src.news_normalized.models import WriterBudget, WriterResult

    route_calls = _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED,
                                          "normalized test route")
    legacy_module = importlib.import_module(collector_module)
    monkeypatch.setattr(legacy_module, "run_incremental",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("legacy run_incremental must not run")))
    monkeypatch.setattr("src.news_direct.backfill_news_direct",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("legacy direct writer must not run")))
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(
                            AssertionError("unexpected synchronization subprocess")))
    monkeypatch.setattr(mda, "resolve_market_db_path", lambda: "/tmp/test-market-data.db")

    events = []

    class FakeConn:
        def close(self):
            events.append("close")

    fake_conn = FakeConn()
    real_connect = sqlite3.connect

    def _connect(path, timeout=0, **kwargs):
        if str(path) != "/tmp/test-market-data.db":
            return real_connect(path, timeout=timeout, **kwargs)
        events.append(("connect", path, timeout))
        return fake_conn

    monkeypatch.setattr(sqlite3, "connect", _connect)

    class FakeStore:
        def __init__(self, conn):
            events.append(("store", conn))
            self.conn = conn

    monkeypatch.setattr(store_module, "NormalizedNewsStore", FakeStore)

    class RecordingLock:
        def __enter__(self):
            events.append("lock_enter")

        def __exit__(self, exc_type, exc, tb):
            events.append("lock_exit")

    monkeypatch.setattr(mdd, "market_write_lock", lambda: RecordingLock())

    seen = {}

    class FakeConfig:
        pass

    class FakeCollector:
        def __init__(self, api_key, config):
            seen["collector"] = (api_key, config)

    class FakeProvider:
        source = direct_source

        def __init__(self, collector):
            seen["provider"] = (direct_source, collector)

        def operation(self):
            return nullcontext()

    monkeypatch.setattr(legacy_module, "load_env", lambda: f"{direct_source}-key")
    monkeypatch.setattr(legacy_module, config_name, FakeConfig)
    monkeypatch.setattr(legacy_module, collector_name, FakeCollector)
    monkeypatch.setattr(adapters, provider_name, FakeProvider)

    def _write_news_batch(store, provider, scope, budget, *, project_legacy=False,
                          progress_cb=None, **kwargs):
        events.append("write")
        seen["writer"] = {
            "store": store,
            "provider": provider,
            "scope": list(scope),
            "budget": budget,
            "project_legacy": project_legacy,
            "progress_cb": progress_cb,
        }
        return WriterResult(
            status="succeeded",
            articles_seen=2,
            articles_inserted=1,
            bodies_fetched=1,
            errors={},
            continuation=None,
            legacy_rows_inserted=1,
        )

    monkeypatch.setattr(writer_module, "write_news_batch", _write_news_batch)

    res = ds.run_source(source, trigger_source="api")

    assert res["status"] == "succeeded"
    assert route_calls and len(route_calls) == 1
    assert seen["collector"][0] == f"{direct_source}-key"
    assert isinstance(seen["collector"][1], FakeConfig)
    assert seen["provider"][0] == direct_source
    assert seen["writer"]["scope"] == ["AAPL", "NVDA"]
    assert isinstance(seen["writer"]["budget"], WriterBudget)
    assert seen["writer"]["project_legacy"] is True
    assert callable(seen["writer"]["progress_cb"])
    assert res["collect"]["articles_seen"] == 2
    assert res["collect"]["legacy_rows_inserted"] == 1
    assert res["ticker_count"] == 2
    assert "local_refresh" not in res
    assert events == [
        ("connect", "/tmp/test-market-data.db", 10.0),
        ("store", fake_conn),
        "write",
        "close",
    ]


def test_normalized_news_route_preserves_writer_partial_continuation(monkeypatch):
    import sqlite3

    import src.market_data_admin as mda
    import src.market_data_direct as mdd
    import src.news_normalized.routing as routing
    import src.news_normalized.store as store_module
    import src.news_normalized.writer as writer_module
    from src.news_normalized.models import WriterContinuation, WriterResult

    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED,
                            "normalized test route")
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(
                            AssertionError("unexpected synchronization subprocess")))
    monkeypatch.setattr(mda, "resolve_market_db_path", lambda: "/tmp/test-market-data.db")

    class FakeConn:
        def close(self):
            pass

    fake_conn = FakeConn()
    real_connect = sqlite3.connect

    def _connect(path, timeout=0, **kwargs):
        if str(path) != "/tmp/test-market-data.db":
            return real_connect(path, timeout=timeout, **kwargs)
        return fake_conn

    monkeypatch.setattr(sqlite3, "connect", _connect)

    class FakeStore:
        def __init__(self, conn):
            self.conn = conn

    class FakeProvider:
        source = "polygon"

    monkeypatch.setattr(store_module, "NormalizedNewsStore", FakeStore)
    monkeypatch.setattr(mdd, "market_write_lock", lambda: nullcontext())
    monkeypatch.setattr(ds, "_make_normalized_news_provider", lambda source: FakeProvider())

    writer_continuation = WriterContinuation(
        deferred_tickers=("MSFT", "TSLA"),
        deferred_body_ids=("polygon-body-1",),
        cursor="cursor-1",
    )

    def _write_news_batch(*args, **kwargs):
        return WriterResult(
            status="partial",
            articles_seen=10,
            articles_inserted=7,
            bodies_fetched=3,
            errors={},
            continuation=writer_continuation,
        )

    monkeypatch.setattr(writer_module, "write_news_batch", _write_news_batch)

    res = ds.run_source("polygon_news", trigger_source="api")

    expected_continuation = {
        "deferred_tickers": ["MSFT", "TSLA"],
        "deferred_body_ids": ["polygon-body-1"],
        "cursor": "cursor-1",
    }
    assert res["status"] == "partial"
    assert res["continuation"] == expected_continuation
    assert res["collect"]["status"] == "partial"
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "partial"
    assert row["continuation"] == expected_continuation
    assert row["last_result"]["status"] == "partial"
    assert row["last_result"]["continuation"] == expected_continuation
    assert ds.status_snapshot()["polygon_news"]["durable_state"]["continuation"] == (
        expected_continuation
    )


def test_normalized_news_scheduler_skips_pending_continuation(monkeypatch):
    import src.news_normalized.routing as routing

    continuation = {
        "deferred_tickers": ["MSFT", "TSLA"],
        "deferred_body_ids": ["polygon-body-1"],
        "cursor": "cursor-1",
    }
    ds._state_store().record_attempt("polygon_news",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome(
        "polygon_news",
        status="partial",
        error=None,
        result={"status": "partial", "continuation": continuation},
        continuation=continuation,
    )
    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED,
                            "normalized test route")
    monkeypatch.setattr(ds, "_run_normalized_news_writer",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("normalized writer must not run")))

    res = ds.run_source("polygon_news", trigger_source="scheduler")

    assert res["status"] == "skipped"
    assert "partial pending manual continue" in res["reason"]
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "partial"
    assert row["continuation"] == continuation
    assert row["last_result"]["continuation"] == continuation


def test_legacy_local_news_route_runs_despite_stale_normalized_continuation(monkeypatch):
    import src.news_normalized.routing as routing

    continuation = {
        "deferred_tickers": ["MSFT"],
        "deferred_body_ids": ["polygon-body-1"],
        "cursor": "cursor-1",
    }
    ds._state_store().record_attempt("polygon_news",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome(
        "polygon_news",
        status="partial",
        error=None,
        result={"status": "partial", "continuation": continuation},
        continuation=continuation,
    )
    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.LEGACY_LOCAL,
                            "legacy local rollback route")
    monkeypatch.setattr(ds, "_run_normalized_news_writer",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("normalized writer must not run")))
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(
                            AssertionError("unexpected synchronization subprocess")))
    monkeypatch.setattr("src.news_providers.make_news_provider", lambda source, **k: object())
    direct_calls = []

    def _direct(tickers, *, source, provider, progress_cb=None, **kwargs):
        direct_calls.append((source, list(tickers)))
        return {"source": source, "tickers_scanned": len(tickers), "articles_added": 0,
                "errors": {}}

    monkeypatch.setattr("src.news_direct.backfill_news_direct", _direct)

    res = ds.run_source("polygon_news", trigger_source="scheduler")

    assert res["status"] == "succeeded"
    assert direct_calls == [("polygon", ["AAPL", "NVDA"])]
    assert res["collect"]["source"] == "polygon"
    assert "local_refresh" not in res


def test_blocked_news_route_fails_despite_stale_normalized_continuation(monkeypatch):
    import src.collectors.polygon_news as cpn
    import src.news_normalized.routing as routing

    continuation = {
        "deferred_tickers": ["MSFT"],
        "deferred_body_ids": ["polygon-body-1"],
        "cursor": "cursor-1",
    }
    ds._state_store().record_attempt("polygon_news",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome(
        "polygon_news",
        status="partial",
        error=None,
        result={"status": "partial", "continuation": continuation},
        continuation=continuation,
    )
    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.BLOCKED,
                            "blocked rollback route")
    calls = {"normalized": 0, "adapter": 0, "direct": 0, "sync": 0}
    monkeypatch.setattr(ds, "_run_normalized_news_writer",
                        lambda *a, **k: calls.__setitem__(
                            "normalized", calls["normalized"] + 1))
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: calls.__setitem__(
                            "adapter", calls["adapter"] + 1))
    monkeypatch.setattr("src.news_direct.backfill_news_direct",
                        lambda *a, **k: calls.__setitem__(
                            "direct", calls["direct"] + 1))
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (calls.__setitem__(
                            "sync", calls["sync"] + 1), {"returncode": 0})[1])

    res = ds.run_source("polygon_news", trigger_source="scheduler")

    assert res["status"] == "failed"
    assert "blocked rollback route" in res["error"]
    assert calls == {"normalized": 0, "adapter": 0, "direct": 0, "sync": 0}


def test_normalized_news_manual_trigger_passes_pending_continuation_and_clears_it(
    monkeypatch,
):
    import src.news_normalized.routing as routing

    from src.news_normalized.models import WriterContinuation

    continuation = {
        "deferred_tickers": ["MSFT", "TSLA"],
        "deferred_body_ids": ["polygon-body-1"],
        "cursor": "cursor-1",
    }
    ds._state_store().record_attempt("polygon_news",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome(
        "polygon_news",
        status="partial",
        error=None,
        result={"status": "partial", "continuation": continuation},
        continuation=continuation,
    )
    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED,
                            "normalized test route")
    seen = {}

    def _normalized_writer(source, scope, *, continuation=None, progress_cb=None):
        seen["source"] = source
        seen["scope"] = list(scope)
        seen["continuation"] = continuation
        return {
            "status": "succeeded",
            "articles_seen": 0,
            "articles_inserted": 0,
            "bodies_fetched": 0,
            "errors": {},
            "continuation": None,
        }

    monkeypatch.setattr(ds, "_run_normalized_news_writer", _normalized_writer)

    res = ds.run_source("polygon_news", trigger_source="api")

    assert res["status"] == "succeeded"
    assert seen["source"] == "polygon"
    assert seen["scope"] == ["MSFT", "TSLA"]
    assert isinstance(seen["continuation"], WriterContinuation)
    assert seen["continuation"].deferred_tickers == ("MSFT", "TSLA")
    assert seen["continuation"].deferred_body_ids == ("polygon-body-1",)
    assert seen["continuation"].cursor == "cursor-1"
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "succeeded"
    assert row["continuation"] is None


def test_manual_normalized_body_continuation_does_not_require_active_scope(monkeypatch):
    import src.news_normalized.routing as routing
    from src.news_normalized.models import WriterContinuation

    continuation = {
        "deferred_tickers": [],
        "deferred_body_ids": ["polygon-body-1", "polygon-body-2"],
        "cursor": "cursor-1",
    }
    ds._state_store().record_attempt("polygon_news",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome(
        "polygon_news",
        status="partial",
        error=None,
        result={"status": "partial", "continuation": continuation},
        continuation=continuation,
    )
    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED,
                            "normalized test route")
    monkeypatch.setattr(ds, "_resolve_price_scope",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("active scope must not be required")))
    seen = {}

    def _normalized_writer(source, scope, *, continuation=None, progress_cb=None):
        seen["source"] = source
        seen["scope"] = list(scope)
        seen["continuation"] = continuation
        return {
            "status": "succeeded",
            "articles_seen": 0,
            "articles_inserted": 0,
            "bodies_fetched": 2,
            "errors": {},
            "continuation": None,
        }

    monkeypatch.setattr(ds, "_run_normalized_news_writer", _normalized_writer)

    res = ds.run_source("polygon_news", trigger_source="api")

    assert res["status"] == "succeeded"
    assert seen["source"] == "polygon"
    assert seen["scope"] == []
    assert isinstance(seen["continuation"], WriterContinuation)
    assert seen["continuation"].deferred_tickers == ()
    assert seen["continuation"].deferred_body_ids == ("polygon-body-1", "polygon-body-2")
    assert seen["continuation"].cursor == "cursor-1"
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "succeeded"
    assert row["continuation"] is None


def test_failed_manual_normalized_continuation_preserves_pending(monkeypatch):
    import src.news_normalized.routing as routing
    from src.news_normalized.models import WriterContinuation

    continuation = {
        "deferred_tickers": ["MSFT", "TSLA"],
        "deferred_body_ids": ["polygon-body-1"],
        "cursor": "cursor-1",
    }
    ds._state_store().record_attempt("polygon_news",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome(
        "polygon_news",
        status="partial",
        error=None,
        result={"status": "partial", "continuation": continuation},
        continuation=continuation,
    )
    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED,
                            "normalized test route")
    seen = {}

    def _normalized_writer(source, scope, *, continuation=None, progress_cb=None):
        seen["continuation"] = continuation
        raise RuntimeError("writer boom")

    monkeypatch.setattr(ds, "_run_normalized_news_writer", _normalized_writer)

    res = ds.run_source("polygon_news", trigger_source="api")

    assert res["status"] == "failed"
    assert "writer boom" in res["error"]
    assert isinstance(seen["continuation"], WriterContinuation)
    assert seen["continuation"].deferred_tickers == ("MSFT", "TSLA")
    assert seen["continuation"].deferred_body_ids == ("polygon-body-1",)
    assert seen["continuation"].cursor == "cursor-1"
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "failed"
    assert row["continuation"] == continuation
    assert ds._pending_continuation("polygon_news") == continuation


def test_normalized_news_partial_without_continuation_stays_partial(monkeypatch):
    import sqlite3

    import src.market_data_admin as mda
    import src.market_data_direct as mdd
    import src.news_normalized.routing as routing
    import src.news_normalized.store as store_module
    import src.news_normalized.writer as writer_module
    from src.news_normalized.models import WriterResult

    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED,
                            "normalized test route")
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(
                            AssertionError("unexpected synchronization subprocess")))
    monkeypatch.setattr(mda, "resolve_market_db_path", lambda: "/tmp/test-market-data.db")

    class FakeConn:
        def close(self):
            pass

    fake_conn = FakeConn()
    real_connect = sqlite3.connect

    def _connect(path, timeout=0, **kwargs):
        if str(path) != "/tmp/test-market-data.db":
            return real_connect(path, timeout=timeout, **kwargs)
        return fake_conn

    monkeypatch.setattr(sqlite3, "connect", _connect)

    class FakeStore:
        def __init__(self, conn):
            self.conn = conn

    class FakeProvider:
        source = "polygon"

    monkeypatch.setattr(store_module, "NormalizedNewsStore", FakeStore)
    monkeypatch.setattr(mdd, "market_write_lock", lambda: nullcontext())
    monkeypatch.setattr(ds, "_make_normalized_news_provider", lambda source: FakeProvider())
    monkeypatch.setattr(
        writer_module,
        "write_news_batch",
        lambda *a, **k: WriterResult(
            status="partial",
            articles_seen=1,
            articles_inserted=0,
            bodies_fetched=0,
            errors={"AAPL": "provider err"},
            continuation=None,
        ),
    )

    res = ds.run_source("polygon_news", trigger_source="api")

    assert res["status"] == "partial"
    assert "continuation" not in res
    assert res["collect"]["status"] == "partial"
    assert res["collect"]["errors"] == {"AAPL": "provider err"}
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "partial"
    assert row["continuation"] is None
    assert row["last_result"]["collect"]["errors"] == {"AAPL": "provider err"}


def test_local_news_route_keeps_single_direct_writer(monkeypatch):
    import src.collectors.polygon_news as cpn
    import src.news_normalized.routing as routing

    route_calls = _patch_news_write_route(monkeypatch, routing.NewsWriteMode.LEGACY_LOCAL,
                                          "legacy local test route")
    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: False)
    calls = {"run_incremental": 0, "sync": 0, "direct": 0, "provider": None}
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: calls.__setitem__("run_incremental",
                                                          calls["run_incremental"] + 1))

    def _subproc(argv):
        if "--news" in argv:
            calls["sync"] += 1
        return {"returncode": 0}

    monkeypatch.setattr(ds, "_run_subprocess", _subproc)
    monkeypatch.setattr("src.news_providers.make_news_provider",
                        lambda source, **k: (calls.__setitem__("provider", source), object())[1])

    def _direct(tickers, *, source, provider, progress_cb=None, **k):
        calls["direct"] += 1
        return {"source": source, "tickers_scanned": len(tickers), "articles_added": 0,
                "errors": {}}

    monkeypatch.setattr("src.news_direct.backfill_news_direct", _direct)

    res = ds.run_source("polygon_news", trigger_source="api")

    assert res["status"] == "succeeded"
    assert len(route_calls) == 1
    assert calls == {"run_incremental": 0, "sync": 0, "direct": 1,
                     "provider": "polygon"}
    assert res["collect"]["source"] == "polygon"
    assert "local_refresh" not in res


def test_normalized_ibkr_news_route_launches_isolated_worker(
    tmp_path,
    monkeypatch,
):
    import src.news_normalized.routing as routing
    import src.market_data_admin as mda

    route_calls = _patch_news_write_route(
        monkeypatch, routing.NewsWriteMode.NORMALIZED, "normalized ibkr test route"
    )
    monkeypatch.setattr(mda, "resolve_market_db_path", lambda: str(tmp_path / "pre_exit.db"))
    calls = []

    def _subprocess(argv, cwd=None, capture_output=False, text=False, timeout=None):
        calls.append(argv)
        assert timeout == ds._IBKR_NEWS_WORKER_TIMEOUT_S
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "succeeded",
                    "articles_seen": 0,
                    "articles_inserted": 0,
                    "bodies_fetched": 0,
                    "legacy_rows_inserted": 0,
                    "legacy_rows_updated": 0,
                    "projection_skipped_no_ticker": 0,
                    "error_count": 0,
                    "error_classes": [],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(ds.subprocess, "run", _subprocess)
    res = ds.run_source("ibkr_news", trigger_source="api")

    assert res["status"] == "succeeded"
    assert len(route_calls) == 1
    assert len(calls) == 1
    argv = calls[0]
    assert argv[:3] == [
        ds.sys.executable,
        "-m",
        "src.news_normalized.ibkr_cli",
    ]
    assert not any(str(part).endswith("collect_ibkr_news_normalized.py") for part in argv)
    assert "--tickers" in argv
    assert argv[argv.index("--tickers") + 1] == "AAPL,NVDA"
    assert "--gateway-lock-held" in argv
    assert "--retry-body-ids" not in argv
    assert "sync" not in res
    assert "local_refresh" not in res


def test_current_news_route_launches_normalized_worker(
    tmp_path,
    monkeypatch,
):
    calls = []

    def _subprocess(argv, cwd=None, capture_output=False, text=False, timeout=None):
        calls.append(argv)
        assert timeout == ds._IBKR_NEWS_WORKER_TIMEOUT_S
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "succeeded",
                    "articles_seen": 0,
                    "articles_inserted": 0,
                    "bodies_fetched": 0,
                    "legacy_rows_inserted": 0,
                    "legacy_rows_updated": 0,
                    "projection_skipped_no_ticker": 0,
                    "error_count": 0,
                    "error_classes": [],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(ds.subprocess, "run", _subprocess)
    res = ds.run_source("ibkr_news", trigger_source="api")

    assert res["status"] == "succeeded"
    rendered_calls = json.dumps(calls)
    assert "src.news_normalized.ibkr_cli" in rendered_calls
    assert "collect_ibkr_news_normalized.py" not in rendered_calls
    assert "collect_ibkr_news.py" not in rendered_calls
    assert "migrate_to_supabase.py" not in rendered_calls
    assert "--news" not in rendered_calls
    assert "local_refresh" not in res


def test_post_exit_ibkr_audit_routes_to_normalized_when_profile_store_unavailable(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(ds, "_store", lambda: (_ for _ in ()).throw(RuntimeError("profile down")))
    calls = []

    def _subprocess(argv, cwd=None, capture_output=False, text=False, timeout=None):
        calls.append(argv)
        assert timeout == ds._IBKR_NEWS_WORKER_TIMEOUT_S
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "succeeded",
                    "articles_seen": 0,
                    "articles_inserted": 0,
                    "bodies_fetched": 0,
                    "legacy_rows_inserted": 0,
                    "legacy_rows_updated": 0,
                    "projection_skipped_no_ticker": 0,
                    "error_count": 0,
                    "error_classes": [],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(ds.subprocess, "run", _subprocess)
    res = ds.run_source("ibkr_news", trigger_source="api")

    assert res["status"] == "succeeded"
    rendered_calls = json.dumps(calls)
    assert "src.news_normalized.ibkr_cli" in rendered_calls
    assert "collect_ibkr_news_normalized.py" not in rendered_calls
    assert "collect_ibkr_news.py" not in rendered_calls


def test_ibkr_news_fails_closed_when_local_route_state_cannot_be_read(
    tmp_path,
    monkeypatch,
):
    profile_db = tmp_path / "profile_state.db"
    profile_db.write_text("not sqlite", encoding="utf-8")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_db))
    calls = []
    monkeypatch.setattr(
        ds,
        "_run_subprocess",
        lambda argv: (calls.append(argv), {"returncode": 0})[1],
    )
    monkeypatch.setattr(
        ds.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("normalized worker should not run with unreadable route state")
        ),
    )
    res = ds.run_source("ibkr_news", trigger_source="api")

    assert res["status"] == "failed"
    assert "profile settings could not be read" in res["error"].lower()
    assert calls == []


def test_normalized_ibkr_worker_partial_stdout_marks_scheduler_partial(
    monkeypatch,
):
    import src.news_normalized.routing as routing

    _patch_news_write_route(
        monkeypatch, routing.NewsWriteMode.NORMALIZED, "normalized ibkr test route"
    )
    raw_id = "DJ-N$raw-secret-id"
    payload = {
        "status": "partial",
        "articles_seen": 5,
        "articles_inserted": 3,
        "bodies_fetched": 1,
        "legacy_rows_inserted": 3,
        "legacy_rows_updated": 0,
        "projection_skipped_no_ticker": 0,
        "error_count": 0,
        "error_classes": [],
        "continuation": {
            "deferred_ticker_count": 0,
            "deferred_body_count": 1,
            "has_cursor": False,
        },
    }
    subprocess_calls = []

    def _run(argv, cwd=None, capture_output=False, text=False, timeout=None):
        subprocess_calls.append(argv)
        assert timeout == ds._IBKR_NEWS_WORKER_TIMEOUT_S
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(ds.subprocess, "run", _run)
    res = ds.run_source("ibkr_news", trigger_source="api")

    assert len(subprocess_calls) == 1
    assert res["status"] == "partial"
    assert res["collect"]["status"] == "partial"
    assert res["collect"]["continuation"] == payload["continuation"]
    assert "sync" not in res
    assert "local_refresh" not in res
    row = ds._state_store().get("ibkr_news")
    assert row["last_status"] == "partial"
    assert row["continuation"] is None
    assert row["last_result"]["collect"]["status"] == "partial"
    snap = ds.status_snapshot()["ibkr_news"]["durable_state"]
    assert snap["last_status"] == "partial"
    assert snap["continuation"] is None
    assert raw_id not in json.dumps(row, sort_keys=True)


def test_normalized_ibkr_worker_failure_hides_raw_child_stderr(
    monkeypatch,
):
    import src.news_normalized.routing as routing

    _patch_news_write_route(
        monkeypatch, routing.NewsWriteMode.NORMALIZED, "normalized ibkr test route"
    )
    secret = "licensed provider payload DJ-N$raw-secret-id raw body text"
    payload = {
        "status": "failed",
        "articles_seen": 0,
        "articles_inserted": 0,
        "bodies_fetched": 0,
        "legacy_rows_inserted": 0,
        "legacy_rows_updated": 0,
        "projection_skipped_no_ticker": 0,
        "error_count": 1,
        "error_classes": ["ProviderError"],
    }

    def _run(argv, cwd=None, capture_output=False, text=False, timeout=None):
        assert timeout == ds._IBKR_NEWS_WORKER_TIMEOUT_S
        return SimpleNamespace(
            returncode=1,
            stdout=json.dumps(payload),
            stderr=f"provider log leaked: {secret}",
        )

    monkeypatch.setattr(ds.subprocess, "run", _run)
    res = ds.run_source("ibkr_news", trigger_source="api")

    rendered = json.dumps(res, sort_keys=True)
    row = ds._state_store().get("ibkr_news")
    assert res["status"] == "failed"
    assert "normalized IBKR worker failed" in res["error"]
    assert res["collect"]["status"] == "failed"
    assert secret not in rendered
    assert secret not in json.dumps(row, sort_keys=True)
    assert row["last_status"] == "failed"
    assert secret not in row["last_error"]


def test_normalized_ibkr_worker_invalid_stdout_is_generic_failure(monkeypatch):
    import src.news_normalized.routing as routing

    _patch_news_write_route(
        monkeypatch, routing.NewsWriteMode.NORMALIZED, "normalized ibkr test route"
    )
    secret = "DJ-N$raw-secret-id raw provider stdout"

    def _run(argv, cwd=None, capture_output=False, text=False, timeout=None):
        assert timeout == ds._IBKR_NEWS_WORKER_TIMEOUT_S
        return SimpleNamespace(
            returncode=0,
            stdout=f"not-json {secret}",
            stderr=f"raw stderr {secret}",
        )

    monkeypatch.setattr(ds.subprocess, "run", _run)

    res = ds.run_source("ibkr_news", trigger_source="api")

    row = ds._state_store().get("ibkr_news")
    rendered = json.dumps(res, sort_keys=True)
    assert res["status"] == "failed"
    assert res["error"] == "normalized IBKR worker failed"
    assert secret not in rendered
    assert row["last_status"] == "failed"
    assert secret not in json.dumps(row, sort_keys=True)


def test_ibkr_legacy_local_route_is_retired_before_collector_sync_and_mirror(
    monkeypatch,
):
    import src.news_normalized.routing as routing

    route_calls = _patch_news_write_route(
        monkeypatch, routing.NewsWriteMode.LEGACY_LOCAL, "ibkr legacy-local rollback"
    )
    calls = []
    monkeypatch.setattr(
        ds, "_run_subprocess", lambda argv: (calls.append(argv), {"returncode": 0})[1]
    )
    res = ds.run_source("ibkr_news", trigger_source="api")

    assert res["status"] == "failed"
    assert len(route_calls) == 1
    assert calls == []
    assert res["error"] == "IBKR news requires the normalized writer policy"


def test_post_exit_blocked_news_route_fails_closed_and_records_failure(monkeypatch):
    # BLOCKED must fail closed before any provider, subprocess, or mirror work starts.
    import src.collectors.polygon_news as cpn
    import src.news_normalized.routing as routing

    route_calls = _patch_news_write_route(monkeypatch, routing.NewsWriteMode.BLOCKED,
                                          "blocked test route")
    provider_calls = {"adapter": 0, "direct": 0, "sync": 0}
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: provider_calls.__setitem__(
                            "adapter", provider_calls["adapter"] + 1))
    monkeypatch.setattr("src.news_direct.backfill_news_direct",
                        lambda *a, **k: provider_calls.__setitem__(
                            "direct", provider_calls["direct"] + 1))
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (provider_calls.__setitem__(
                            "sync", provider_calls["sync"] + 1), {"returncode": 0})[1])
    res = ds.run_source("polygon_news", trigger_source="api")

    assert res["status"] == "failed"
    assert len(route_calls) == 1
    assert "blocked test route" in res["error"]
    assert provider_calls == {"adapter": 0, "direct": 0, "sync": 0}
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "failed"
    assert "blocked test route" in row["last_error"]


def test_run_source_adapter_failure_short_circuits(monkeypatch):
    monkeypatch.setattr(
        "src.news_direct.backfill_news_direct",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("FINNHUB_API_KEY not found")),
    )
    calls = []
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (calls.append(argv), {"returncode": 0})[1])
    res = ds.run_source("finnhub_news")
    assert res["status"] == "failed" and "FINNHUB_API_KEY" in res["error"]
    assert calls == []


def test_default_ibkr_legacy_news_route_does_not_launch_collector(monkeypatch):
    calls = []

    def _sub(argv, **kwargs):
        del kwargs
        calls.append(argv)
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(ds.subprocess, "run", _sub)
    res = ds.run_source("ibkr_news")
    assert res["status"] == "failed"
    assert res["error"] == "normalized IBKR worker failed"
    assert len(calls) == 1


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


def _scheduled_price_payload(
    *, status="succeeded", scanned=2, errors=0, unresolved=0,
):
    unresolved_tickers = ["LCID"][:unresolved]
    error_order = ["LCID", "BAD"] if unresolved else ["BAD", "LCID"]
    error_tickers = sorted(error_order[:errors])
    return {
        "status": status,
        "provider": "ibkr",
        "tickers_scanned": scanned,
        "succeeded_ticker_count": scanned - errors,
        "gaps_found": unresolved,
        "rows_added": 26 if status == "succeeded" else 1,
        "error_count": errors,
        "error_tickers": error_tickers,
        "unresolved_after_fetch_count": unresolved,
        "unresolved_after_fetch_tickers": unresolved_tickers,
        "error_class": "",
        "error": "",
        "retryable": False,
    }


class _RecordingJobStore:
    def __init__(self):
        self.created = []
        self.finished = []

    def create_run(self, name, **kwargs):
        self.created.append((name, kwargs))
        return len(self.created)

    def finish_run(self, run_id, **kwargs):
        self.finished.append((run_id, kwargs))
        return True


def _install_recording_job_store(monkeypatch):
    store = _RecordingJobStore()
    monkeypatch.setattr(
        "src.service.job_runs_store.JobRunsLocalStore",
        lambda profile_db: store,
    )
    return store


def test_price_scope_required(monkeypatch):
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: [])
    res = ds.run_source("ibkr_prices")
    assert res["status"] == "failed" and "scope" in res["error"]

    seen = {}
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(AssertionError("prices subprocess retired")))
    monkeypatch.setattr(
        ds,
        "_run_sanitized_prices_worker_subprocess",
        lambda argv: seen.update({"argv": argv}) or {
            "returncode": 0,
            "payload": _scheduled_price_payload(),
        },
    )
    res = ds.run_source("ibkr_prices")
    assert res["status"] == "succeeded" and res["ticker_count"] == 2
    assert "--tickers" in seen["argv"] and "AAPL,NVDA" in seen["argv"]
    assert "--gateway-lock-held" in seen["argv"]


def test_run_source_never_raises(monkeypatch):
    monkeypatch.setattr(
        "src.news_direct.backfill_news_direct",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("disk gone")),
    )
    res = ds.run_source("polygon_news")
    assert res["status"] == "failed"
    assert res["error"] == "disk gone"


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



def test_missing_scheduler_state_uses_local_job_history_without_early_fire(
    tmp_path,
    monkeypatch,
):
    from types import MappingProxyType

    from src.scheduler_state import SchedulerStateStore
    from src.service import job_runs_store as job_runs_module

    profile_db = tmp_path / "continuity.db"
    state_store = SchedulerStateStore(profile_db)
    history_store = _REAL_JOB_RUNS_LOCAL_STORE(profile_db)
    completed_at = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)
    completed_iso = completed_at.isoformat(timespec="seconds")
    monkeypatch.setattr(job_runs_module, "_now_iso", lambda: completed_iso)
    run_id = history_store.create_run(
        ds.job_name("polygon_news"),
        trigger_source="scheduler",
    )
    assert history_store.finish_run(run_id, status="succeeded", result={})

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_db))
    monkeypatch.setattr(ds, "_SCHED_STATE", state_store)
    monkeypatch.setattr(ds, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(
        ds,
        "SOURCES",
        MappingProxyType({"polygon_news": ds.SOURCES["polygon_news"]}),
    )
    monkeypatch.setattr(job_runs_module, "JobRunsLocalStore", _REAL_JOB_RUNS_LOCAL_STORE)
    monkeypatch.setattr(
        ds,
        "source_config",
        lambda source: {"enabled": source == "polygon_news", "interval_minutes": 60},
    )

    ds._seed_last_attempts()

    assert ds._LAST_ATTEMPT == {"polygon_news": completed_at}
    assert ds._is_due("polygon_news", completed_at + timedelta(minutes=30)) is False


# --- routes ----------------------------------------------------------------------

def test_get_schedule_snapshot_shape():
    from src.api.routes.schedule import get_schedule
    out = get_schedule()["sources"]
    assert set(out) == ACTIVE_SOURCE_IDS
    p = out["polygon_news"]
    assert p["enabled"] is False and p["running"] is False
    assert p["provider_fetch"] is True and p["job_name"] == "collect.polygon_news"
    for name in ("polygon_news", "finnhub_news", "ibkr_news"):
        assert "normalized local records" in out[name]["description"]
        assert "compatibility projection" in out[name]["description"]
    assert out["ibkr_prices"]["ibkr"] is True
    assert out["sec_corporate_actions"]["job_name"] == (
        "collect.sec_corporate_actions"
    )
    assert out["sec_corporate_actions"]["provider_fetch"] is True
    for source in MACRO_SOURCE_IDS:
        assert out[source]["provider_fetch"] is True
        assert out[source]["job_name"] == ds.SOURCES[source].backend_job_name
        assert out[source]["write_target"] == "macro_calendar.db"
    for source in out.values():
        assert "control_mode" not in source
        assert "retired" not in source
        assert "retired_reason" not in source


def test_schedule_status_exposes_current_news_route_metadata():
    snap = ds.status_snapshot()

    assert set(snap) == ACTIVE_SOURCE_IDS

    prices = snap["ibkr_prices"]
    assert prices["source_mode"] == "direct_local"
    assert prices["write_target"] == "market_data.db"
    assert prices["source_badges"] == ["IBKR", "直寫本地"]

    assert snap["polygon_news"]["source_badges"] == ["Massive", "直寫本地"]
    assert snap["finnhub_news"]["source_badges"] == ["Finnhub", "直寫本地"]
    assert snap["ibkr_news"]["source_badges"] == ["IBKR", "直寫本地"]
    assert snap["sec_corporate_actions"]["source_badges"] == ["SEC", "官方申報"]
    for source in MACRO_SOURCE_IDS:
        assert snap[source]["source_mode"] == "provider_fetch"
        assert snap[source]["write_target"] == "macro_calendar.db"
        provider = "FRED" if source.startswith("fred_") else "Finnhub"
        assert snap[source]["source_badges"] == [provider, "macro_calendar.db"]
    assert all("control_mode" not in source for source in snap.values())
    assert all("retired" not in source for source in snap.values())
    assert all("retired_reason" not in source for source in snap.values())


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
    # Direct-local news writers receive the ACTIVE UNIVERSE as the explicit ticker
    # list + a progress_cb that feeds the live progress the UI shows.
    seen = {}

    def _fake_direct(tickers, *, source, provider, progress_cb=None, **kw):
        seen["tickers"] = list(tickers)
        seen["source"] = source
        progress_cb(3, 10, "AAPL")           # simulate mid-run progress
        snap = ds.status_snapshot()["polygon_news"]  # while still inside the run
        seen["live_progress"] = snap["progress"]
        return {"source": source, "tickers_scanned": len(tickers), "articles_added": 1, "errors": {}}

    monkeypatch.setattr("src.news_direct.backfill_news_direct", _fake_direct)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    res = ds.run_source("polygon_news")
    assert res["status"] == "succeeded" and res["ticker_count"] == 2
    assert seen["tickers"] == ["AAPL", "NVDA"]
    assert seen["source"] == "polygon"
    assert seen["live_progress"] == {"done": 3, "total": 10, "current": "AAPL"}
    # progress cleared after the run
    assert ds.status_snapshot()["polygon_news"]["progress"] is None


def test_adapter_universe_unavailable_fails_loud(monkeypatch):
    # A typed source-read failure reaches run_source's generic failure boundary:
    # it never becomes an empty scope and never reaches provider work.
    import src.collectors.finnhub_news as cfn
    import src.universe_scope as universe_scope

    calls = {
        "scope": 0,
        "adapter": 0,
        "provider": 0,
        "writer": 0,
        "json_worker": 0,
        "prices_worker": 0,
        "subprocess_run": 0,
    }

    def _called(name):
        def _fail(*args, **kwargs):
            calls[name] += 1
            raise AssertionError(f"{name} must not run without a complete universe")
        return _fail

    unavailable = ActiveUniverseUnavailable({
        "manual_lists": "source_db_unreadable",
        "sa_alpha_picks_current": "source_db_missing",
    })

    def _unavailable_scope():
        calls["scope"] += 1
        raise unavailable

    monkeypatch.setattr(universe_scope, "resolve_active_universe", _unavailable_scope)
    monkeypatch.setattr(ds, "_resolve_price_scope", _REAL_RESOLVE_PRICE_SCOPE)
    monkeypatch.setattr(cfn, "run_incremental", _called("adapter"))
    monkeypatch.setattr("src.news_providers.make_news_provider", _called("provider"))
    monkeypatch.setattr("src.news_direct.backfill_news_direct", _called("writer"))
    monkeypatch.setattr(ds, "_run_sanitized_json_subprocess", _called("json_worker"))
    monkeypatch.setattr(
        ds,
        "_run_sanitized_prices_worker_subprocess",
        _called("prices_worker"),
    )
    monkeypatch.setattr(ds.subprocess, "run", _called("subprocess_run"))

    res = ds.run_source("finnhub_news")

    safe_error = "active_universe_unavailable: manual_lists,sa_alpha_picks_current"
    assert res["status"] == "failed"
    assert res["error"] == safe_error
    assert calls == {
        "scope": 1,
        "adapter": 0,
        "provider": 0,
        "writer": 0,
        "json_worker": 0,
        "prices_worker": 0,
        "subprocess_run": 0,
    }

    durable = ds._state_store().get("finnhub_news")
    assert durable["last_status"] == "failed"
    assert durable["last_error"] == safe_error
    assert durable["last_result"]["error"] == safe_error
    assert "source_db_unreadable" not in json.dumps(durable, sort_keys=True)
    assert "source_db_missing" not in json.dumps(durable, sort_keys=True)


def test_run_source_explicit_tickers_reaches_active_adapter_without_mirror_controls(
    monkeypatch,
):
    # The daily_update thin wrapper passes an explicit ticker list through the
    seen = {}

    def _fake_direct(tickers, *, source, provider, progress_cb=None, **kw):
        seen["tickers"] = list(tickers)
        return {"source": source, "tickers_scanned": len(tickers), "articles_added": 1, "errors": {}}

    monkeypatch.setattr("src.news_direct.backfill_news_direct", _fake_direct)
    monkeypatch.setattr(ds, "_resolve_price_scope",
                        lambda: (_ for _ in ()).throw(AssertionError("must not resolve")))
    res = ds.run_source("polygon_news", trigger_source="cli",
                        tickers=["AAPL", "NVDA"])
    assert res["status"] == "succeeded" and res["ticker_count"] == 2
    assert seen["tickers"] == ["AAPL", "NVDA"]
    assert "sync_flag" not in res
    assert "skip_sync" not in res


def test_schedule_routes_reject_removed_source_ids_before_writes_or_provider_work(
    monkeypatch,
):
    # Active sources pass the write choke point. Removed IDs are ordinary
    # unknown sources and are rejected before writes or provider work.
    from fastapi import HTTPException
    from src.api.routes import schedule as sr
    gated = []
    monkeypatch.setattr(sr, "require_db_write", lambda action, ctx: gated.append(ctx["source"]))
    monkeypatch.setattr(sr, "run_source", lambda *a, **k: {"status": "succeeded"})
    for source in RETIRED_SOURCE_IDS:
        with pytest.raises(HTTPException) as exc:
            sr.run_now(source)
        assert exc.value.status_code == 404
        assert gated == []

    out = sr.run_now("polygon_news")
    assert out["status"] == "started"
    assert gated == ["polygon_news"]


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


def test_p0c1_ibkr_prices_runs_prices_worker_subprocess(monkeypatch):
    captured = []

    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])

    def fake_worker(argv):
        captured[:] = argv
        parsed = prices_runtime.parse_args(argv[3:])
        assert parsed.provider == "ibkr"
        assert parsed.tickers == "AAPL,NVDA"
        assert "--source" not in argv
        return {
            "returncode": 0,
            "payload": {
                **_scheduled_price_payload(),
                "rows_added": 3,
            },
        }

    monkeypatch.setattr(ds, "_run_sanitized_prices_worker_subprocess", fake_worker)

    res = ds.run_source("ibkr_prices")

    assert res["status"] == "succeeded"
    argv = captured
    assert argv[:3] == [sys.executable, "-m", "src.prices_runtime"]
    assert "--tickers" in argv and "AAPL,NVDA" in argv
    assert "--gateway-lock-held" in argv
    assert "collect_ibkr_prices.py" not in " ".join(argv)
    assert "local_refresh" not in res


def test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation(
    monkeypatch,
):
    store = _install_recording_job_store(monkeypatch)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "LCID"])
    monkeypatch.setattr(
        ds, "_run_sanitized_prices_worker_subprocess",
        lambda argv: {
            "returncode": 0,
            "payload": _scheduled_price_payload(
                status="partial", errors=1, unresolved=1,
            ),
        },
    )
    result = ds.run_source("ibkr_prices", trigger_source="api")
    assert result["status"] == "partial"
    assert result["collect"]["succeeded_ticker_count"] == 1
    assert result["collect"]["unresolved_after_fetch_tickers"] == ["LCID"]
    durable = ds._state_store().get("ibkr_prices")
    assert durable["last_status"] == "partial"
    assert durable["last_error"] is None
    assert durable["continuation"] is None
    _, finished = store.finished[-1]
    assert finished["status"] == "failed"
    assert finished["error"] == "price_collection_partial"
    assert finished["message"] == "price_collection_partial"
    assert finished["result"]["status"] == "partial"


def test_prices_failed_payload_persists_failed_without_partial(monkeypatch):
    store = _install_recording_job_store(monkeypatch)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["BAD", "LCID"])
    monkeypatch.setattr(
        ds, "_run_sanitized_prices_worker_subprocess",
        lambda argv: {
            "returncode": 1,
            "payload": _scheduled_price_payload(
                status="failed", errors=2, unresolved=1,
            ),
        },
    )
    result = ds.run_source("ibkr_prices", trigger_source="api")
    assert result["status"] == "failed"
    assert result["collect"]["status"] == "failed"
    durable = ds._state_store().get("ibkr_prices")
    assert durable["last_status"] == "failed"
    assert durable["continuation"] is None
    _, finished = store.finished[-1]
    assert finished["status"] == "failed"
    assert finished["error"] == "price_collection_failed"


def test_prices_gateway_failure_persists_typed_diagnostic(monkeypatch):
    store = _install_recording_job_store(monkeypatch)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])
    payload = ds._parse_sanitized_prices_worker_stdout(json.dumps({
        "status": "failed",
        "error_class": "PriceCollectionUnavailable",
        "error": "",
        "error_code": "ibkr_gateway_unavailable",
        "retryable": False,
    }))
    assert payload is not None
    monkeypatch.setattr(
        ds,
        "_run_sanitized_prices_worker_subprocess",
        lambda argv: {"returncode": 1, "payload": payload},
    )

    result = ds.run_source("ibkr_prices", trigger_source="api")

    assert result["status"] == "failed"
    assert ds._state_store().get("ibkr_prices")["last_error"] == (
        "ibkr_gateway_unavailable"
    )
    _, finished = store.finished[-1]
    assert finished["error"] == "ibkr_gateway_unavailable"


def test_prices_success_clears_prior_partial_and_preserves_audit_history(monkeypatch):
    store = _install_recording_job_store(monkeypatch)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "LCID"])
    steps = iter([
        {
            "returncode": 0,
            "payload": _scheduled_price_payload(
                status="partial", errors=1, unresolved=1,
            ),
        },
        {
            "returncode": 0,
            "payload": _scheduled_price_payload(status="succeeded"),
        },
    ])
    monkeypatch.setattr(
        ds, "_run_sanitized_prices_worker_subprocess", lambda argv: next(steps),
    )
    assert ds.run_source("ibkr_prices")["status"] == "partial"
    assert ds.run_source("ibkr_prices")["status"] == "succeeded"
    durable = ds._state_store().get("ibkr_prices")
    assert durable["last_status"] == "succeeded"
    assert durable["last_error"] is None
    assert durable["continuation"] is None
    assert [kwargs["status"] for _, kwargs in store.finished] == [
        "failed", "succeeded",
    ]
    assert store.finished[0][1]["error"] == "price_collection_partial"
    assert store.finished[1][1]["error"] is None


def test_price_partial_projection_does_not_change_normalized_news_audit_status(
    monkeypatch,
):
    import src.news_normalized.routing as routing

    store = _install_recording_job_store(monkeypatch)
    _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED)
    monkeypatch.setattr(
        ds, "_run_normalized_news_writer",
        lambda *args, **kwargs: {"status": "partial", "continuation": None},
    )
    result = ds.run_source("polygon_news", trigger_source="api")
    assert result["status"] == "partial"
    assert ds._state_store().get("polygon_news")["continuation"] is None
    _, finished = store.finished[-1]
    assert finished["status"] == "succeeded"
    assert finished["error"] is None


# --- v1.2: durable scheduler_state persistence ------------------------------------

def test_run_source_persists_attempt_and_outcome_to_local_state(monkeypatch):
    # a real run_source records last_attempt + the succeeded outcome in the LOCAL state store
    import src.collectors.polygon_news as cpn
    monkeypatch.setattr(cpn, "run_incremental",
                        lambda *a, **k: {"mode": "up_to_date", "new_articles": 0})
    ds.run_source("polygon_news", trigger_source="api")
    row = ds._state_store().get("polygon_news")
    assert row is not None
    assert row["last_status"] == "succeeded" and row["last_error"] is None
    assert row["last_attempt"] is not None
    assert row["last_result"]["status"] == "succeeded"


def test_run_source_failure_persists_error_locally(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("provider exploded")
    monkeypatch.setattr("src.news_direct.backfill_news_direct", _boom)
    res = ds.run_source("polygon_news", trigger_source="api")
    assert res["status"] == "failed"
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "failed" and "provider exploded" in row["last_error"]


def test_skip_does_not_overwrite_durable_outcome(monkeypatch):
    # a real failure is recorded; a later in-process SKIP (per-source lock busy) must NOT clobber
    # the durable last_error (skips aren't persisted to the state store).
    monkeypatch.setattr(
        "src.news_direct.backfill_news_direct",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("real failure")),
    )
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


def test_prices_worker_retryable_lock_busy_is_skip_not_failure(monkeypatch):
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])
    monkeypatch.setattr(
        ds,
        "_run_sanitized_prices_worker_subprocess",
        lambda argv: {
            "returncode": 1,
            "payload": {
                "status": "failed",
                "error_class": "TimeoutError",
                "error": "market_data.db write lock busy (timeout)",
                "retryable": True,
            },
        },
    )

    res = ds.run_source("ibkr_prices")

    assert res["status"] == "skipped"
    assert res["skip_kind"] == "skipped_lock_busy"
    assert "write lock busy" in res["reason"]
    row = ds._state_store().get("ibkr_prices")
    assert row["last_status"] == "skipped"
    assert row["last_error"] is None
    assert row["last_result"]["skip_kind"] == "skipped_lock_busy"


def test_seed_last_attempts_from_local_state(monkeypatch):
    # A durable scheduler-state attempt remains the first restart authority.
    from datetime import datetime, timezone
    when = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)
    ds._state_store().record_attempt("polygon_news", when)
    monkeypatch.setattr(ds, "_LAST_ATTEMPT", {})
    ds._seed_last_attempts()
    assert ds._LAST_ATTEMPT.get("polygon_news") == when


def test_ibkr_lock_skip_does_not_leave_durable_running(monkeypatch):
    # v1.2a HIGH fix: record_attempt is AFTER the IBKR-lock gate. A prior failure is durable;
    # then an IBKR-busy skip must NOT overwrite it with 'running' (skips don't touch durable state).
    # Seed a prior failed outcome on an active IBKR provider source.
    ds._state_store().record_attempt("ibkr_prices",
                                     datetime(2026, 6, 24, 9, 0, tzinfo=timezone.utc))
    ds._state_store().record_outcome("ibkr_prices", status="failed",
                                     error="earlier gateway failure", result={"e": 1})
    # hold the shared IBKR lock so run_source skips at the gate (before record_attempt).
    assert ds._IBKR_LOCK.acquire(timeout=2)
    monkeypatch.setattr(ds, "_IBKR_LOCK_TIMEOUT_S", 0.05)   # fast skip, no 1800s wait
    try:
        res = ds.run_source("ibkr_prices")
        assert res["status"] == "skipped" and "IBKR gateway busy" in res["reason"]
    finally:
        ds._IBKR_LOCK.release()
    row = ds._state_store().get("ibkr_prices")
    assert row["last_status"] == "failed"            # NOT 'running' — skip didn't clobber it
    assert row["last_error"] == "earlier gateway failure"


def test_status_snapshot_marks_stale_running_durable_state(monkeypatch):
    ds._state_store().record_attempt(
        "ibkr_news", datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc)
    )

    snap = ds.status_snapshot()["ibkr_news"]["durable_state"]

    assert snap["last_status"] == "running"
    assert snap["running_stale"] is True
    assert snap["running_for_seconds"] > 0
    assert "running longer than" in snap["running_stale_reason"]


def test_reconcile_interrupted_runtime_state_marks_local_running_rows(tmp_path, monkeypatch):
    market_db = tmp_path / "market_data.db"
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_db))
    ds._state_store().record_attempt(
        "ibkr_news", datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)
    )
    ds._state_store().record_attempt(
        "security_lifecycle.automation",
        datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc),
    )
    lifecycle_calls = []
    monkeypatch.setattr(
        ds,
        "reconcile_interrupted_security_lifecycle_automation",
        lambda *, now: lifecycle_calls.append(now)
        or {"status": "reconciled", "run_ids": ["slar_orphan"]},
        raising=False,
    )

    import src.market_data_direct as mdd

    conn = sqlite3.connect(market_db)
    mdd._ensure_provider_sync_tables(conn)
    stale_id = mdd._start_provider_run(conn, provider="ibkr", interval="news", domain="news")
    fresh_id = mdd._start_provider_run(conn, provider="polygon", interval="news", domain="news")
    conn.execute(
        "UPDATE provider_sync_runs SET started_at=? WHERE id=?",
        ("2026-06-24T09:30:00+00:00", stale_id),
    )
    conn.execute(
        "UPDATE provider_sync_runs SET started_at=? WHERE id=?",
        ("2026-06-24T11:30:00+00:00", fresh_id),
    )
    conn.commit()
    conn.close()

    result = ds.reconcile_interrupted_runtime_state(
        now=datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    )

    assert result["scheduler_sources"] == ["ibkr_news"]
    assert result["provider_run_ids"] == [stale_id]
    assert result["lifecycle_automation"] == {
        "status": "reconciled",
        "run_ids": ["slar_orphan"],
    }
    assert lifecycle_calls == [
        datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    ]
    assert ds._state_store().get("ibkr_news")["last_status"] == "failed"
    assert (
        ds._state_store()
        .get("security_lifecycle.automation")["last_status"]
        == "running"
    )
    conn = sqlite3.connect(market_db)
    assert conn.execute(
        "SELECT status FROM provider_sync_runs WHERE id=?", (stale_id,)
    ).fetchone()[0] == "failed"
    assert conn.execute(
        "SELECT status FROM provider_sync_runs WHERE id=?", (fresh_id,)
    ).fetchone()[0] == "running"
    conn.close()


def test_lifecycle_startup_reconciliation_failure_replaces_running_telemetry(
    tmp_path,
    monkeypatch,
):
    from src.service.security_lifecycle_automation_scheduler import (
        read_security_lifecycle_automation_durable_status,
    )

    profile_db = tmp_path / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_db))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "missing-market.db"))
    monkeypatch.setattr(ds, "_SCHED_STATE", None)
    ds._state_store().record_attempt(
        "security_lifecycle.automation",
        datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc),
    )

    def unavailable(*, now):
        raise RuntimeError("private reconciliation detail")

    monkeypatch.setattr(
        ds,
        "reconcile_interrupted_security_lifecycle_automation",
        unavailable,
    )

    result = ds.reconcile_interrupted_runtime_state(
        now=datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    )

    assert result["lifecycle_automation"] == {
        "status": "unavailable",
        "reason": "automation_scheduler_failed",
    }
    durable = read_security_lifecycle_automation_durable_status(profile_db)
    assert durable["last_status"] == "failed"
    assert durable["telemetry_status"] == "valid"
    assert durable["active_incident"] == {
        "case_failures": {},
        "scheduler_failure": {"reason": "automation_scheduler_failed"},
    }


def test_lifecycle_startup_reconciliation_uses_terminal_fallback_when_typed_write_fails(
    tmp_path,
    monkeypatch,
):
    profile_db = tmp_path / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_db))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "missing-market.db"))
    monkeypatch.setattr(ds, "_SCHED_STATE", None)
    ds._state_store().record_attempt(
        "security_lifecycle.automation",
        datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        ds,
        "reconcile_interrupted_security_lifecycle_automation",
        lambda *, now: (_ for _ in ()).throw(RuntimeError("private repair")),
    )
    monkeypatch.setattr(
        ds,
        "record_security_lifecycle_automation_reconciliation_failure",
        lambda *, now: (_ for _ in ()).throw(RuntimeError("private telemetry")),
    )

    ds.reconcile_interrupted_runtime_state(
        now=datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    )

    assert (
        ds._state_store()
        .get("security_lifecycle.automation")["last_status"]
        == "failed"
    )


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


def test_sanitized_ibkr_news_worker_timeout_returns_failed_payload(monkeypatch):
    import subprocess as _subprocess

    def _timeout(argv, **kwargs):
        raise _subprocess.TimeoutExpired(cmd=argv, timeout=1)

    monkeypatch.setattr(ds.subprocess, "run", _timeout)
    monkeypatch.setattr(ds, "_IBKR_NEWS_WORKER_TIMEOUT_S", 1)

    step = ds._run_sanitized_json_subprocess(["python", "-m", "worker"])

    assert step["returncode"] == 1
    assert step["payload"]["status"] == "failed"
    assert step["payload"]["error_classes"] == ["TimeoutExpired"]


def test_sanitized_ibkr_news_worker_parser_preserves_gateway_unavailable_code():
    from src.news_normalized.ibkr_cli import sanitize_worker_error

    payload = ds._parse_sanitized_worker_stdout(json.dumps(
        sanitize_worker_error(ConnectionError("PRIVATE_PROVIDER_TEXT"))
    ))

    assert payload is not None
    assert payload["error_code"] == "ibkr_gateway_unavailable"
    assert ds._sanitized_worker_failure_message(payload) == (
        "ibkr_gateway_unavailable"
    )


def test_run_source_refuses_provider_work_when_provider_config_setup_required(monkeypatch):
    import src.provider_config_runtime as runtime
    import src.service.data_scheduler as ds

    runtime.mark_provider_config_setup_required("profile DB unavailable")
    try:
        monkeypatch.setattr(
            ds,
            "_run_subprocess",
            lambda argv: (_ for _ in ()).throw(AssertionError("subprocess used")),
        )
        res = ds.run_source("polygon_news", trigger_source="api")
        assert res["status"] == "failed"
        assert res["code"] == "provider_config_setup_required"
    finally:
        runtime.clear_provider_config_setup_required()


def test_prices_worker_stdout_parse_preserves_retryable_and_counts():
    """Regression: the news-worker allowlist stripped the prices worker's fields,
    making skipped_lock_busy classification dead code and zeroing telemetry."""
    import json as _json

    from src.prices_runtime import sanitize_error

    failure = _json.dumps(sanitize_error(TimeoutError("market_data.db write lock busy (timeout)")))
    payload = ds._parse_sanitized_prices_worker_stdout(failure)
    assert payload["retryable"] is True
    assert payload["error_class"] == "TimeoutError"
    assert "write lock busy" in payload["error"]
    assert ds._prices_worker_retryable_skip_reason(payload) is not None

    success_payload = _scheduled_price_payload(
        status="succeeded", scanned=3, errors=0, unresolved=0,
    )
    success_payload["gaps_found"] = 2
    success_payload["rows_added"] = 55
    success = _json.dumps(success_payload)
    ok = ds._parse_sanitized_prices_worker_stdout(success)
    assert ok["status"] == "succeeded" and ok["rows_added"] == 55
    assert ok["tickers_scanned"] == 3 and ok["gaps_found"] == 2
    assert ok["succeeded_ticker_count"] == 3
    assert ok["error_count"] == 0 and ok["error_tickers"] == []
    assert ok["unresolved_after_fetch_count"] == 0
    assert ok["unresolved_after_fetch_tickers"] == []
    assert ok["provider"] == "ibkr"


def test_prices_worker_stdout_parser_preserves_allowlisted_gateway_code():
    payload = ds._parse_sanitized_prices_worker_stdout(json.dumps({
        "status": "failed",
        "error_class": "PriceCollectionUnavailable",
        "error": "",
        "error_code": "ibkr_gateway_unavailable",
        "retryable": False,
    }))

    assert payload is not None
    assert payload["error_code"] == "ibkr_gateway_unavailable"
    assert ds._sanitized_prices_worker_failure_message(payload) == (
        "ibkr_gateway_unavailable"
    )


def test_prices_worker_stdout_parser_preserves_partial_truth_and_bounded_tickers():
    raw = _scheduled_price_payload(
        status="partial", scanned=30, errors=1, unresolved=1,
    )
    raw["succeeded_ticker_count"] = 29
    raw["error_tickers"] = ["LCID"]
    raw["unresolved_after_fetch_tickers"] = ["LCID"]
    parsed = ds._parse_sanitized_prices_worker_stdout(json.dumps(raw))
    assert parsed == raw


def test_prices_worker_stdout_parser_rejects_malformed_partial_payloads():
    valid = _scheduled_price_payload(status="partial", errors=1, unresolved=1)
    invalid = [
        {**valid, "status": "complete"},
        {**valid, "provider": "PRIVATE_PROVIDER"},
        {**valid, "rows_added": -1},
        {**valid, "error_count": True},
        {**valid, "succeeded_ticker_count": 2},
        {**valid, "unresolved_after_fetch_count": 2},
        {**valid, "error_tickers": "LCID"},
        {**valid, "error_tickers": ["LCID"] * 26},
        {**valid, "error_tickers": [123]},
        {**valid, "unresolved_after_fetch_tickers": ["LCID\nPRIVATE"]},
        {**valid, "error_tickers": ["AAPL"]},
    ]
    for payload in invalid:
        assert ds._parse_sanitized_prices_worker_stdout(json.dumps(payload)) is None


def test_normalized_news_lock_busy_is_retryable_skip(monkeypatch):
    import src.service.data_scheduler as ds
    import src.news_normalized.routing as routing

    monkeypatch.setattr(
        ds,
        "_read_news_write_route_for_scheduler",
        lambda source: routing.NewsWriteRoute(
            mode=routing.NewsWriteMode.NORMALIZED,
            reason="normalized",
        ),
    )
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])

    def fake_writer(*args, **kwargs):
        raise TimeoutError("market_data.db write lock busy (timeout)")

    monkeypatch.setattr(ds, "_run_normalized_news_writer", fake_writer)

    res = ds.run_source("polygon_news", trigger_source="scheduler")

    assert res["status"] == "skipped"
    assert res["skip_kind"] == "skipped_lock_busy"
    assert "write lock busy" in res["reason"]
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "skipped"
    assert row["last_error"] is None
    assert row["last_result"]["skip_kind"] == "skipped_lock_busy"


def test_scheduler_passes_market_lock_factory_to_normalized_news_writer(monkeypatch, tmp_path):
    import src.service.data_scheduler as ds
    import src.news_normalized.routing as routing

    captured = {}

    class _Provider:
        source = "polygon"

    class _Store:
        def __init__(self, conn):
            self.conn = conn

    class _Budget:
        def __init__(self, max_articles, max_body_fetches):
            self.max_articles = max_articles
            self.max_body_fetches = max_body_fetches

    def fake_write_news_batch(store, provider, scope, budget, **kwargs):
        captured.update(kwargs)
        return {
            "status": "succeeded",
            "articles_seen": 0,
            "articles_inserted": 0,
            "bodies_fetched": 0,
            "errors": {},
            "continuation": None,
        }

    monkeypatch.setattr(ds, "_make_normalized_news_provider", lambda source: _Provider())
    monkeypatch.setattr(
        "src.market_data_admin.resolve_market_db_path",
        lambda: str(tmp_path / "market_data.db"),
    )
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", _Store)
    monkeypatch.setattr("src.news_normalized.models.WriterBudget", _Budget)
    monkeypatch.setattr("src.news_normalized.writer.write_news_batch", fake_write_news_batch)

    out = ds._run_normalized_news_writer("polygon", ["AAPL"])

    assert out["status"] == "succeeded"
    assert captured["write_lock_factory"] is not None
    assert captured["project_legacy"] is True


def test_ibkr_news_worker_stdout_parse_preserves_retryable_lock_busy():
    import json as _json
    import src.service.data_scheduler as ds
    from src.news_normalized.ibkr_cli import sanitize_worker_error

    failure = _json.dumps(
        sanitize_worker_error(
            TimeoutError("market_data.db write lock busy (timeout)")
        )
    )
    payload = ds._parse_sanitized_worker_stdout(failure)

    assert payload["retryable"] is True
    assert "write lock busy" in payload["error"]
    assert payload["error_classes"] == ["TimeoutError"]
    assert ds._normalized_worker_retryable_skip_reason(payload) is not None

    provider_failure = _json.dumps(
        sanitize_worker_error(TimeoutError("provider request timed out"))
    )
    provider_payload = ds._parse_sanitized_worker_stdout(provider_failure)
    assert provider_payload["retryable"] is False
    assert provider_payload["error"] == ""
    assert ds._normalized_worker_retryable_skip_reason(provider_payload) is None


def test_ibkr_news_worker_lock_busy_payload_is_skip_not_failure(monkeypatch):
    import src.service.data_scheduler as ds
    import src.news_normalized.routing as routing

    class _Lock:
        def acquire(self, *args, **kwargs):
            return True

        def release(self):
            pass

    monkeypatch.setattr(
        ds,
        "_read_news_write_route_for_scheduler",
        lambda source: routing.NewsWriteRoute(
            mode=routing.NewsWriteMode.NORMALIZED,
            reason="normalized",
        ),
    )
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])
    monkeypatch.setattr(ds, "_IBKR_LOCK", _Lock())
    monkeypatch.setattr(ds, "_IBKR_FLOCK", _Lock())
    monkeypatch.setattr(
        ds,
        "_run_sanitized_json_subprocess",
        lambda argv: {
            "returncode": 1,
            "payload": {
                "status": "failed",
                "articles_seen": 0,
                "articles_inserted": 0,
                "bodies_fetched": 0,
                "error_count": 1,
                "error_classes": ["TimeoutError"],
                "error": "market_data.db write lock busy (timeout)",
                "retryable": True,
            },
        },
    )

    res = ds.run_source("ibkr_news", trigger_source="scheduler")

    assert res["status"] == "skipped"
    assert res["skip_kind"] == "skipped_lock_busy"
    assert "write lock busy" in res["reason"]
    row = ds._state_store().get("ibkr_news")
    assert row["last_status"] == "skipped"
    assert row["last_error"] is None


def test_worker_stdout_parse_preserves_retry_legs_and_body_backlog():
    payload = ds._parse_sanitized_worker_stdout(
        json.dumps(
            {
                "status": "succeeded",
                "retry_bodies_attempted": 2,
                "retry_bodies_fetched": 1,
                "tickers_scanned": 3,
                "headline_pages_requested": 3,
                "headline_saturated_tickers": 2,
                "headline_incomplete_tickers": 1,
                "error_count": 0,
                "error_classes": [],
                "legs": {"retry": "succeeded", "fresh": "succeeded"},
                "body_backlog": {
                    "status": "ok",
                    "due_now": 0,
                    "scheduled_later": 2,
                    "never_attempted": 0,
                    "earliest_next_retry_at": "2026-07-15T12:00:00Z",
                },
            }
        )
    )

    assert payload is not None
    assert payload["retry_bodies_attempted"] == 2
    assert payload["retry_bodies_fetched"] == 1
    assert payload["tickers_scanned"] == 3
    assert payload["headline_pages_requested"] == 3
    assert payload["headline_saturated_tickers"] == 2
    assert payload["headline_incomplete_tickers"] == 1
    assert payload["legs"] == {"retry": "succeeded", "fresh": "succeeded"}
    assert payload["body_backlog"] == {
        "status": "ok",
        "due_now": 0,
        "scheduled_later": 2,
        "never_attempted": 0,
        "earliest_next_retry_at": "2026-07-15T12:00:00Z",
    }


def test_worker_stdout_parser_rejects_malformed_body_backlog_values():
    for invalid in (-1, 1.5, "1", float("inf")):
        payload = ds._parse_sanitized_worker_stdout(
            json.dumps(
                {
                    "status": "partial",
                    "body_backlog": {
                        "status": "ok",
                        "due_now": invalid,
                        "scheduled_later": 0,
                        "never_attempted": 0,
                    },
                }
            )
        )
        assert payload is not None
        assert payload["body_backlog"] == {"status": "unavailable"}

    invalid_timestamp = ds._parse_sanitized_worker_stdout(
        json.dumps(
            {
                "status": "partial",
                "body_backlog": {
                    "status": "ok",
                    "due_now": 0,
                    "scheduled_later": 1,
                    "never_attempted": 0,
                    "earliest_next_retry_at": "not-a-time",
                },
            }
        )
    )
    assert invalid_timestamp is not None
    assert invalid_timestamp["body_backlog"] == {"status": "unavailable"}

    forged_unavailable = ds._parse_sanitized_worker_stdout(
        json.dumps(
            {
                "status": "partial",
                "body_backlog": {"status": "unavailable", "due_now": 99},
            }
        )
    )
    assert forged_unavailable is not None
    assert forged_unavailable["body_backlog"] == {"status": "unavailable"}

    unknown_leg = ds._parse_sanitized_worker_stdout(
        json.dumps(
            {
                "status": "partial",
                "legs": {"retry": "waiting", "fresh": "succeeded"},
            }
        )
    )
    assert unknown_leg is not None
    assert "legs" not in unknown_leg


def test_worker_stdout_parse_preserves_entitlement_block_count():
    payload = ds._parse_sanitized_worker_stdout(
        json.dumps(
            {
                "status": "succeeded",
                "body_backlog": {
                    "status": "ok",
                    "due_now": 0,
                    "scheduled_later": 0,
                    "never_attempted": 0,
                    "earliest_next_retry_at": None,
                    "provider_not_entitled": 78,
                },
            }
        )
    )

    assert payload is not None
    assert payload["body_backlog"]["provider_not_entitled"] == 78


def test_worker_stdout_parser_rejects_malformed_entitlement_block_count():
    for value in (-1, 1.5, True, "78"):
        payload = ds._parse_sanitized_worker_stdout(
            json.dumps(
                {
                    "status": "partial",
                    "body_backlog": {
                        "status": "ok",
                        "due_now": 0,
                        "scheduled_later": 0,
                        "never_attempted": 0,
                        "provider_not_entitled": value,
                    },
                }
            )
        )
        assert payload is not None
        assert payload["body_backlog"] == {"status": "unavailable"}


def _run_ibkr_worker_payload(monkeypatch, payload):
    import src.news_normalized.routing as routing

    _patch_news_write_route(
        monkeypatch, routing.NewsWriteMode.NORMALIZED, "normalized ibkr test route"
    )
    seen = {}

    def fake_worker(argv):
        seen["argv"] = argv
        parsed = ds._parse_sanitized_worker_stdout(json.dumps(payload))
        assert parsed is not None
        return {"returncode": 0, "payload": parsed}

    monkeypatch.setattr(ds, "_run_sanitized_json_subprocess", fake_worker)
    result = ds.run_source("ibkr_news", trigger_source="api")
    return result, seen["argv"]


def test_ibkr_success_persists_scheduled_backlog_without_partial(monkeypatch):
    payload = {
        "status": "succeeded",
        "retry_bodies_attempted": 0,
        "retry_bodies_fetched": 0,
        "tickers_scanned": 2,
        "error_count": 0,
        "error_classes": [],
        "legs": {"retry": "succeeded", "fresh": "succeeded"},
        "body_backlog": {
            "status": "ok",
            "due_now": 0,
            "scheduled_later": 2,
            "never_attempted": 0,
            "earliest_next_retry_at": "2026-07-15T18:00:00Z",
        },
    }

    result, argv = _run_ibkr_worker_payload(monkeypatch, payload)

    assert result["status"] == "succeeded"
    assert result["collect"]["body_backlog"]["scheduled_later"] == 2
    assert "--retry-body-ids" not in argv
    row = ds._state_store().get("ibkr_news")
    assert row["last_status"] == "succeeded"
    assert row["continuation"] is None
    assert row["last_result"]["collect"]["body_backlog"] == payload["body_backlog"]
    assert ds.status_snapshot()["ibkr_news"]["durable_state"]["last_status"] == (
        "succeeded"
    )


def test_ibkr_retry_failure_persists_partial_without_manual_continuation(
    monkeypatch,
):
    payload = {
        "status": "partial",
        "error_count": 1,
        "error_classes": ["ProviderError"],
        "legs": {"retry": "partial", "fresh": "succeeded"},
        "body_backlog": {
            "status": "ok",
            "due_now": 0,
            "scheduled_later": 1,
            "never_attempted": 0,
            "earliest_next_retry_at": "2026-07-15T18:00:00Z",
        },
    }

    result, _ = _run_ibkr_worker_payload(monkeypatch, payload)

    assert result["status"] == "partial"
    assert result["collect"]["legs"] == payload["legs"]
    assert "continuation" not in result
    row = ds._state_store().get("ibkr_news")
    assert row["last_status"] == "partial"
    assert row["continuation"] is None
    assert ds._pending_continuation("ibkr_news") is None


def test_ibkr_backlog_unavailable_is_partial_without_fake_zero(monkeypatch):
    payload = {
        "status": "partial",
        "error_count": 1,
        "error_classes": ["RetryBacklogError"],
        "legs": {"retry": "failed", "fresh": "succeeded"},
        "body_backlog": {"status": "unavailable"},
    }

    result, _ = _run_ibkr_worker_payload(monkeypatch, payload)

    assert result["status"] == "partial"
    assert result["collect"]["body_backlog"] == {"status": "unavailable"}
    assert "due_now" not in result["collect"]["body_backlog"]
    row = ds._state_store().get("ibkr_news")
    assert row["last_status"] == "partial"
    assert row["continuation"] is None
