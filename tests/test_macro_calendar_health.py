"""Tests for macro_calendar health telemetry (P1.2 commit 5).

Coverage:
  - evaluate_health pure logic across the severity ladder for both
    job and table layers (fake-clock stats fixtures, no DB)
  - market-hours upgrade for fetch_economic_calendar_recent
  - never_run / failed-but-no-success / one-shot backfill paths
  - empty / null fetched_at / stale tables
  - DB-unavailable fallback report shape
  - /macro/health route: 200 default, 503 strict, 503 disabled
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.config import get_agent_config
from src.api.routes.macro_calendar import macro_calendar_health
from src.service.macro_calendar_health import (
    DEFAULT_THRESHOLDS,
    SEVERITY_CRITICAL,
    SEVERITY_OK,
    SEVERITY_WARNING,
    STATUS_EMPTY,
    STATUS_NEVER_RUN,
    _is_us_market_hours,
    compute_macro_calendar_health,
    evaluate_health,
)


# ---------------------------------------------------------------------------
# Fake-clock fixtures
# ---------------------------------------------------------------------------

# Wednesday 2026-03-11 14:30 UTC = 10:30 ET → regular trading hours
WEEKDAY_MARKET_HOURS_UTC = datetime(2026, 3, 11, 14, 30, tzinfo=timezone.utc)
# Same Wednesday 02:00 ET (06:00 UTC + DST = 06:00) → off-hours pre-market
WEEKDAY_OFF_HOURS_UTC = datetime(2026, 3, 11, 6, 0, tzinfo=timezone.utc)
# Saturday → off-hours
SATURDAY_UTC = datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc)


_ALL_JOBS = (
    "fetch_economic_calendar_recent",
    "fetch_economic_calendar_backfill",
    "fetch_earnings_calendar",
    "fetch_ipo_calendar",
    "fetch_fred_series",
    "fetch_fred_release_dates",
)

_ALL_TABLES = (
    "cal_economic_events",
    "cal_earnings_events",
    "cal_ipo_events",
    "macro_series",
    "macro_observations",
    "macro_release_dates",
)


def _all_healthy_stats(now: datetime) -> dict:
    """Build a stats dict where every job is fresh + every table populated."""
    return {
        "jobs": {
            name: {
                "last_success_at": now - timedelta(seconds=60),
                "last_any_at": now - timedelta(seconds=60),
            }
            for name in _ALL_JOBS
        },
        "tables": {
            name: {
                "last_fetched_at": now - timedelta(seconds=60),
                "row_count": 100,
            }
            for name in _ALL_TABLES
        },
    }


# ---------------------------------------------------------------------------
# Market-hours detection
# ---------------------------------------------------------------------------


class TestMarketHoursDetection:
    def test_weekday_market_hours_is_true(self):
        assert _is_us_market_hours(WEEKDAY_MARKET_HOURS_UTC) is True

    def test_weekday_off_hours_is_false(self):
        assert _is_us_market_hours(WEEKDAY_OFF_HOURS_UTC) is False

    def test_saturday_is_false(self):
        assert _is_us_market_hours(SATURDAY_UTC) is False

    def test_naive_input_treated_as_utc(self):
        naive = WEEKDAY_MARKET_HOURS_UTC.replace(tzinfo=None)
        assert _is_us_market_hours(naive) is True


# ---------------------------------------------------------------------------
# evaluate_health — happy path
# ---------------------------------------------------------------------------


class TestEvaluateHappyPath:
    def test_all_fresh_returns_ok(self):
        now = WEEKDAY_OFF_HOURS_UTC
        report = evaluate_health(
            _all_healthy_stats(now),
            now=now,
            thresholds=DEFAULT_THRESHOLDS,
        )
        assert report["ok"] is True
        assert report["severity"] == SEVERITY_OK
        assert report["reasons"] == []
        # All 6 jobs and 6 tables present.
        assert len(report["jobs"]) == 6
        assert len(report["tables"]) == 6
        # Every per-row status is "ok".
        for job in report["jobs"]:
            assert job["status"] == SEVERITY_OK
        for table in report["tables"]:
            assert table["status"] == SEVERITY_OK

    def test_thresholds_visible_in_response(self):
        now = WEEKDAY_OFF_HOURS_UTC
        report = evaluate_health(
            _all_healthy_stats(now),
            now=now,
            thresholds={**DEFAULT_THRESHOLDS, "warning_cadence_multiplier": 2.0},
        )
        assert report["thresholds"]["warning_cadence_multiplier"] == 2.0
        assert report["thresholds"]["critical_cadence_multiplier"] == 3.0

    def test_evaluated_at_carries_utc(self):
        now = WEEKDAY_OFF_HOURS_UTC
        report = evaluate_health(
            _all_healthy_stats(now), now=now, thresholds=DEFAULT_THRESHOLDS,
        )
        assert report["evaluated_at"].endswith("+00:00")


# ---------------------------------------------------------------------------
# evaluate_health — job staleness
# ---------------------------------------------------------------------------


class TestJobStaleness:
    def test_recent_job_within_cadence_ok(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        # 30 minutes ago — within hourly cadence.
        stats["jobs"]["fetch_economic_calendar_recent"]["last_success_at"] = (
            now - timedelta(minutes=30)
        )
        stats["jobs"]["fetch_economic_calendar_recent"]["last_any_at"] = (
            now - timedelta(minutes=30)
        )
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_OK

    def test_job_stale_warning_offhours(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        # 2 hours ago: > 1h × 1.5 warning threshold but < 1h × 3 critical.
        stale = now - timedelta(hours=2)
        stats["jobs"]["fetch_economic_calendar_recent"]["last_success_at"] = stale
        stats["jobs"]["fetch_economic_calendar_recent"]["last_any_at"] = stale
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        assert any(r["code"] == "job_stale_warning" for r in report["reasons"])

    def test_job_stale_critical_threshold(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        # 5 hours ago: > 1h × 3 critical threshold.
        stale = now - timedelta(hours=5)
        stats["jobs"]["fetch_economic_calendar_recent"]["last_success_at"] = stale
        stats["jobs"]["fetch_economic_calendar_recent"]["last_any_at"] = stale
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        assert any(r["code"] == "job_stale_critical" for r in report["reasons"])

    def test_recent_job_market_hours_upgrades_warning_to_critical(self):
        """During US market hours, fetch_economic_calendar_recent's
        warning threshold is upgraded to critical because economic events
        fire on a tight schedule (e.g. CPI 08:30 ET, FOMC 14:00 ET)."""
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _all_healthy_stats(now)
        # 2h stale — would be warning off-hours, must be critical here.
        stale = now - timedelta(hours=2)
        stats["jobs"]["fetch_economic_calendar_recent"]["last_success_at"] = stale
        stats["jobs"]["fetch_economic_calendar_recent"]["last_any_at"] = stale
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        assert any(
            r["code"] == "job_stale_market_hours" for r in report["reasons"]
        )

    def test_other_jobs_no_market_hours_upgrade(self):
        """The market-hours upgrade is scoped to recent economic only —
        earnings 4h cadence isn't time-of-day sensitive."""
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _all_healthy_stats(now)
        # Earnings 8h stale: > 4h × 1.5 warning, < 4h × 3 critical.
        stale = now - timedelta(hours=8)
        stats["jobs"]["fetch_earnings_calendar"]["last_success_at"] = stale
        stats["jobs"]["fetch_earnings_calendar"]["last_any_at"] = stale
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        # Should be warning, not critical.
        assert report["severity"] == SEVERITY_WARNING
        codes = {r["code"] for r in report["reasons"]}
        assert "job_stale_warning" in codes
        assert "job_stale_market_hours" not in codes


class TestJobNeverRun:
    def test_periodic_job_never_run_warns(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        stats["jobs"]["fetch_earnings_calendar"] = {
            "last_success_at": None,
            "last_any_at": None,
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        # never_run ranks like warning → overall severity warning.
        assert report["severity"] == SEVERITY_WARNING
        statuses = {j["name"]: j["status"] for j in report["jobs"]}
        assert statuses["fetch_earnings_calendar"] == STATUS_NEVER_RUN
        assert any(r["code"] == "job_never_run" for r in report["reasons"])

    def test_backfill_never_run_is_warning_not_critical(self):
        """One-shot backfill is expected to be never_run on a clean install
        and shouldn't be flagged as actively-broken (critical). Default
        severity is warning — strict-mode callers will still see 503 for
        it; ops who want to mute the signal can override the threshold to
        SEVERITY_OK."""
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        stats["jobs"]["fetch_economic_calendar_backfill"] = {
            "last_success_at": None,
            "last_any_at": None,
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING

    def test_backfill_never_run_can_be_muted_to_ok(self):
        """Threshold override SEVERITY_OK suppresses the never_run reason
        entirely so /macro/health?strict=true returns 200 on a clean
        install where backfill is intentionally never invoked."""
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        stats["jobs"]["fetch_economic_calendar_backfill"] = {
            "last_success_at": None,
            "last_any_at": None,
        }
        thresholds = {**DEFAULT_THRESHOLDS, "backfill_never_run_severity": SEVERITY_OK}
        report = evaluate_health(stats, now=now, thresholds=thresholds)
        assert report["severity"] == SEVERITY_OK
        assert all(r["code"] != "job_never_run" for r in report["reasons"])

    def test_failed_but_never_succeeded_is_critical(self):
        """A job that has runs but no successful one is critical: the
        ingestion path is broken."""
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        stats["jobs"]["fetch_fred_series"] = {
            "last_success_at": None,
            "last_any_at": now - timedelta(hours=1),
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        assert any(
            r["code"] == "job_no_successful_run" for r in report["reasons"]
        )


class TestPeriodicRecentFailure:
    """Independent of cadence freshness: a periodic job whose most recent
    run failed (last_any_at > last_success_at) must surface a warning
    reason. Pre-fix the periodic path went straight from cadence checks to
    return ok and ignored the failure entirely."""

    def test_fresh_success_with_recent_failure_warns(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        # Last success 30m ago (within hourly cadence) but a failed run
        # happened 5m ago.
        stats["jobs"]["fetch_economic_calendar_recent"] = {
            "last_success_at": now - timedelta(minutes=30),
            "last_any_at": now - timedelta(minutes=5),
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        codes = {r["code"] for r in report["reasons"]}
        assert "job_recent_failure" in codes
        # Cadence is fine, so no stale reason should fire.
        assert "job_stale_warning" not in codes
        assert "job_stale_critical" not in codes

    def test_stale_critical_with_recent_failure_keeps_critical(self):
        """A job that's both stale-critical AND recently-failed reports
        critical (the worse signal) and includes both reasons additively."""
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        # 5 hours ago success (>1h × 3 critical) + recent failure 5m ago.
        stats["jobs"]["fetch_economic_calendar_recent"] = {
            "last_success_at": now - timedelta(hours=5),
            "last_any_at": now - timedelta(minutes=5),
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        codes = {r["code"] for r in report["reasons"]}
        # Both signals surface — caller can see what's degraded.
        assert "job_stale_critical" in codes
        assert "job_recent_failure" in codes

    def test_periodic_success_only_no_failure_is_ok(self):
        """Sanity: when last_any_at == last_success_at (most recent run
        was the success), no failure reason fires."""
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        same = now - timedelta(minutes=10)
        stats["jobs"]["fetch_earnings_calendar"] = {
            "last_success_at": same,
            "last_any_at": same,
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_OK


class TestBackfillOneShot:
    def test_old_backfill_with_recent_failure_warns(self):
        """Backfill succeeded long ago; subsequent run failed. Surface the
        recent failure as a warning but don't escalate to critical because
        backfill is one-shot."""
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        stats["jobs"]["fetch_economic_calendar_backfill"] = {
            "last_success_at": now - timedelta(days=180),
            "last_any_at": now - timedelta(hours=1),
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        assert any(
            r["code"] == "job_recent_failure" for r in report["reasons"]
        )

    def test_old_backfill_clean_history_is_ok(self):
        """Backfill last ran 6 months ago, succeeded, no later runs.
        No cadence → ok."""
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        old_success = now - timedelta(days=180)
        stats["jobs"]["fetch_economic_calendar_backfill"] = {
            "last_success_at": old_success,
            "last_any_at": old_success,
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        # All 6 jobs and 6 tables fresh otherwise → ok.
        assert report["severity"] == SEVERITY_OK


# ---------------------------------------------------------------------------
# evaluate_health — table coverage
# ---------------------------------------------------------------------------


class TestTableCoverage:
    def test_empty_table_is_warning(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        stats["tables"]["cal_ipo_events"] = {
            "last_fetched_at": None,
            "row_count": 0,
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        statuses = {t["name"]: t["status"] for t in report["tables"]}
        assert statuses["cal_ipo_events"] == STATUS_EMPTY
        assert any(r["code"] == "table_empty" for r in report["reasons"])

    def test_null_fetched_at_with_rows_is_critical(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        stats["tables"]["macro_observations"] = {
            "last_fetched_at": None,
            "row_count": 999,
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        assert any(
            r["code"] == "table_null_fetched_at" for r in report["reasons"]
        )

    def test_stale_table_warning(self):
        now = WEEKDAY_OFF_HOURS_UTC
        stats = _all_healthy_stats(now)
        # 30 days ago: > default 14d threshold.
        stats["tables"]["macro_release_dates"] = {
            "last_fetched_at": now - timedelta(days=30),
            "row_count": 50,
        }
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        assert any(r["code"] == "table_stale" for r in report["reasons"])


# ---------------------------------------------------------------------------
# DB-unavailable fallback
# ---------------------------------------------------------------------------


class TestDbUnavailable:
    def test_no_backend_returns_critical_with_full_shape(self):
        dal = SimpleNamespace(_backend=object())  # no _get_conn
        report = compute_macro_calendar_health(dal, now=WEEKDAY_OFF_HOURS_UTC)
        assert report["ok"] is False
        assert report["severity"] == SEVERITY_CRITICAL
        assert any(r["code"] == "db_unavailable" for r in report["reasons"])
        # Shape contract: jobs + tables blocks still present (even if all
        # critical) so callers can render the same UI without branching.
        assert len(report["jobs"]) == 6
        assert len(report["tables"]) == 6
        for job in report["jobs"]:
            assert job["status"] == SEVERITY_CRITICAL
        for table in report["tables"]:
            assert table["status"] == SEVERITY_CRITICAL

    def test_backend_query_failure_degrades_gracefully(self, monkeypatch):
        """If _run_health_queries raises, the orchestrator returns the
        unavailable report rather than propagating."""
        from src.service import macro_calendar_health as mod

        backend = SimpleNamespace(_get_conn=MagicMock())
        dal = SimpleNamespace(_backend=backend)
        monkeypatch.setattr(
            mod, "_run_health_queries",
            lambda b: (_ for _ in ()).throw(RuntimeError("connection lost")),
        )
        report = compute_macro_calendar_health(dal, now=WEEKDAY_OFF_HOURS_UTC)
        assert report["severity"] == SEVERITY_CRITICAL
        assert any(
            "connection lost" in r["message"] for r in report["reasons"]
        )


# ---------------------------------------------------------------------------
# /macro/health route
# ---------------------------------------------------------------------------


class TestMacroCalendarHealthRoute:
    def test_default_returns_200_with_payload(self, monkeypatch):
        cfg = get_agent_config()
        original = cfg.macro_calendar_enabled
        cfg.macro_calendar_enabled = True
        try:
            monkeypatch.setattr(
                "src.api.routes.macro_calendar.compute_macro_calendar_health",
                lambda dal: {"ok": True, "severity": SEVERITY_OK},
            )
            response = SimpleNamespace(status_code=200)
            result = macro_calendar_health(
                response=response, strict=False, dal=object(),
            )
            assert result["severity"] == SEVERITY_OK
            assert response.status_code == 200
        finally:
            cfg.macro_calendar_enabled = original

    def test_strict_with_warning_returns_503(self, monkeypatch):
        cfg = get_agent_config()
        original = cfg.macro_calendar_enabled
        cfg.macro_calendar_enabled = True
        try:
            monkeypatch.setattr(
                "src.api.routes.macro_calendar.compute_macro_calendar_health",
                lambda dal: {"ok": False, "severity": SEVERITY_WARNING},
            )
            response = SimpleNamespace(status_code=200)
            result = macro_calendar_health(
                response=response, strict=True, dal=object(),
            )
            assert result["severity"] == SEVERITY_WARNING
            assert response.status_code == 503
        finally:
            cfg.macro_calendar_enabled = original

    def test_strict_with_ok_stays_200(self, monkeypatch):
        cfg = get_agent_config()
        original = cfg.macro_calendar_enabled
        cfg.macro_calendar_enabled = True
        try:
            monkeypatch.setattr(
                "src.api.routes.macro_calendar.compute_macro_calendar_health",
                lambda dal: {"ok": True, "severity": SEVERITY_OK},
            )
            response = SimpleNamespace(status_code=200)
            macro_calendar_health(
                response=response, strict=True, dal=object(),
            )
            assert response.status_code == 200
        finally:
            cfg.macro_calendar_enabled = original

    def test_disabled_macro_calendar_returns_503(self):
        cfg = get_agent_config()
        original = cfg.macro_calendar_enabled
        cfg.macro_calendar_enabled = False
        try:
            with pytest.raises(HTTPException) as exc_info:
                macro_calendar_health(
                    response=SimpleNamespace(status_code=200),
                    strict=False,
                    dal=object(),
                )
            assert exc_info.value.status_code == 503
            assert "macro_calendar" in exc_info.value.detail
        finally:
            cfg.macro_calendar_enabled = original