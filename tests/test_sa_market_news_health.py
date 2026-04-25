"""Tests for SA market-news health telemetry (P0.4).

Coverage:
  - evaluate_health pure logic across the severity ladder
  - market-hours detection (NY tz, DST-naive — relies on zoneinfo)
  - threshold visibility in response
  - DB-unavailable fallback report
  - /sa/market-news/health route (200 default, 503 strict, 503 disabled)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.config import get_agent_config
from src.api.routes.seeking_alpha import market_news_health
from src.service.sa_market_news_health import (
    DEFAULT_THRESHOLDS,
    SEVERITY_CRITICAL,
    SEVERITY_OK,
    SEVERITY_WARNING,
    _is_us_market_hours,
    compute_market_news_health,
    evaluate_health,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# A New York weekday at 10:30 (regular trading hours). Choose a Wednesday in
# March so we sit comfortably inside DST without testing the transition.
WEEKDAY_MARKET_HOURS_UTC = datetime(2026, 3, 11, 14, 30, tzinfo=timezone.utc)
# Same weekday but 02:00 ET — pre-market, not regular hours.
WEEKDAY_OFF_HOURS_UTC = datetime(2026, 3, 11, 6, 0, tzinfo=timezone.utc)
# Saturday noon ET → off-hours.
SATURDAY_UTC = datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc)


def _stats(
    *,
    last_fetched_at=None,
    last_published_at=None,
    rows_24h_fetched=0,
    items_24h_published=0,
    items_7d=0,
    detail_present_7d=0,
):
    return {
        "last_fetched_at": last_fetched_at,
        "last_published_at": last_published_at,
        "rows_24h_fetched": rows_24h_fetched,
        "items_24h_published": items_24h_published,
        "items_7d": items_7d,
        "detail_present_7d": detail_present_7d,
    }


def _healthy_stats(now: datetime):
    """Plausible healthy DB state: fresh fetch, recent publish, lots of detail."""
    return _stats(
        last_fetched_at=now - timedelta(minutes=20),
        last_published_at=now - timedelta(minutes=45),
        rows_24h_fetched=180,
        items_24h_published=170,
        items_7d=900,
        detail_present_7d=820,  # 91.1% completeness
    )


# ---------------------------------------------------------------------------
# Market-hours detection
# ---------------------------------------------------------------------------


class TestMarketHours:
    def test_weekday_during_regular_session_is_market_hours(self):
        assert _is_us_market_hours(WEEKDAY_MARKET_HOURS_UTC) is True

    def test_weekday_premarket_is_not_market_hours(self):
        assert _is_us_market_hours(WEEKDAY_OFF_HOURS_UTC) is False

    def test_weekday_at_close_boundary_is_not_market_hours(self):
        # 16:00 ET == 20:00 UTC during DST (March)
        close = datetime(2026, 3, 11, 20, 0, tzinfo=timezone.utc)
        assert _is_us_market_hours(close) is False

    def test_weekday_at_open_boundary_is_market_hours(self):
        # 09:30 ET == 13:30 UTC during DST
        open_ = datetime(2026, 3, 11, 13, 30, tzinfo=timezone.utc)
        assert _is_us_market_hours(open_) is True

    def test_saturday_during_normal_session_is_not_market_hours(self):
        assert _is_us_market_hours(SATURDAY_UTC) is False

    def test_sunday_during_normal_session_is_not_market_hours(self):
        sun = datetime(2026, 3, 15, 16, 0, tzinfo=timezone.utc)
        assert _is_us_market_hours(sun) is False

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 3, 11, 14, 30)
        assert _is_us_market_hours(naive) is True


# ---------------------------------------------------------------------------
# evaluate_health: severity ladder
# ---------------------------------------------------------------------------


class TestEvaluateHealthSeverity:
    def test_healthy_state_returns_ok(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        report = evaluate_health(_healthy_stats(now), now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["ok"] is True
        assert report["severity"] == SEVERITY_OK
        assert report["reasons"] == []

    def test_stale_fetch_triggers_warning(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["last_fetched_at"] = now - timedelta(hours=8)  # >6h threshold
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        codes = [r["code"] for r in report["reasons"]]
        assert "stale_fetch" in codes

    def test_zero_published_items_market_hours_is_critical(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["items_24h_published"] = 0
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        codes = [r["code"] for r in report["reasons"]]
        assert "no_published_items_market_hours" in codes

    def test_zero_published_items_offhours_is_warning_only(self):
        now = SATURDAY_UTC
        stats = _healthy_stats(now)
        stats["items_24h_published"] = 0
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        codes = [r["code"] for r in report["reasons"]]
        assert "no_published_items_offhours" in codes
        assert "no_published_items_market_hours" not in codes

    def test_completeness_warning_band(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["items_7d"] = 100
        stats["detail_present_7d"] = 70  # 70% < 80
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING
        codes = [r["code"] for r in report["reasons"]]
        assert "detail_completeness_warning" in codes
        assert "detail_completeness_critical" not in codes

    def test_completeness_critical_band(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["items_7d"] = 100
        stats["detail_present_7d"] = 30  # 30% < 50
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        codes = [r["code"] for r in report["reasons"]]
        assert "detail_completeness_critical" in codes

    def test_completeness_at_warning_boundary_is_ok(self):
        """80.0% exactly is the warning threshold — strict less-than."""
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["items_7d"] = 100
        stats["detail_present_7d"] = 80
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_OK

    def test_completeness_just_below_warning_threshold_is_warning(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["items_7d"] = 1000
        stats["detail_present_7d"] = 799  # 79.9%
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_WARNING

    def test_small_sample_skips_completeness_check(self):
        """items_7d below min_rows → completeness inconclusive, not graded."""
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["items_7d"] = 3
        stats["detail_present_7d"] = 0  # 0% but n=3 < min_rows=5
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        # Should NOT be critical from completeness; could still be ok overall.
        codes = [r["code"] for r in report["reasons"]]
        assert "detail_completeness_critical" not in codes
        assert "detail_completeness_warning" not in codes
        assert "detail_sample_too_small" in codes

    def test_empty_db_returns_critical(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        report = evaluate_health(_stats(), now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL
        codes = [r["code"] for r in report["reasons"]]
        assert "no_fetch_history" in codes

    def test_overall_severity_is_max_of_layers(self):
        """A stale fetch + completeness critical → critical (not warning)."""
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["last_fetched_at"] = now - timedelta(hours=8)  # warning
        stats["items_7d"] = 100
        stats["detail_present_7d"] = 30  # critical
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["severity"] == SEVERITY_CRITICAL


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_top_level_keys_present(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        report = evaluate_health(_healthy_stats(now), now=now, thresholds=DEFAULT_THRESHOLDS)
        for key in (
            "ok",
            "severity",
            "reasons",
            "freshness",
            "feed_health",
            "detail_health",
            "thresholds",
            "evaluated_at",
            "is_market_hours",
        ):
            assert key in report, f"missing top-level key: {key}"

    def test_freshness_block_carries_both_ages(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        f = report["freshness"]
        assert isinstance(f["last_fetch_age_seconds"], int)
        assert isinstance(f["latest_published_age_seconds"], int)
        assert f["last_fetch_age_human"] is not None
        assert f["latest_published_age_human"] is not None
        assert f["last_fetch_status"] in (SEVERITY_OK, SEVERITY_WARNING, SEVERITY_CRITICAL)

    def test_thresholds_visible_in_response(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        report = evaluate_health(_healthy_stats(now), now=now, thresholds=DEFAULT_THRESHOLDS)
        for key in (
            "last_fetch_warning_seconds",
            "items_24h_warning_threshold",
            "detail_completeness_warning_pct",
            "detail_completeness_critical_pct",
        ):
            assert key in report["thresholds"]

    def test_reasons_carry_severity_and_code(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["last_fetched_at"] = now - timedelta(hours=8)
        report = evaluate_health(stats, now=now, thresholds=DEFAULT_THRESHOLDS)
        assert all({"severity", "code", "message"} <= r.keys() for r in report["reasons"])

    def test_completeness_pct_is_none_when_items_7d_zero(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        report = evaluate_health(_stats(), now=now, thresholds=DEFAULT_THRESHOLDS)
        assert report["detail_health"]["completeness_7d_pct"] is None


# ---------------------------------------------------------------------------
# Threshold overrides
# ---------------------------------------------------------------------------


class TestThresholdOverrides:
    def test_custom_stale_fetch_threshold(self):
        now = WEEKDAY_MARKET_HOURS_UTC
        stats = _healthy_stats(now)
        stats["last_fetched_at"] = now - timedelta(hours=2)
        # Default 6h → ok. Tightened 30min → warning.
        custom = {**DEFAULT_THRESHOLDS, "last_fetch_warning_seconds": 30 * 60}
        report = evaluate_health(stats, now=now, thresholds=custom)
        assert report["severity"] == SEVERITY_WARNING
        assert report["thresholds"]["last_fetch_warning_seconds"] == 30 * 60


# ---------------------------------------------------------------------------
# Orchestrator + DB unavailability
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def test_db_unavailable_returns_critical_report(self):
        dal = SimpleNamespace()  # no _backend
        report = compute_market_news_health(dal)
        assert report["severity"] == SEVERITY_CRITICAL
        assert any(r["code"] == "db_unavailable" for r in report["reasons"])

    def test_orchestrator_passes_now_to_query_and_evaluation(self, monkeypatch):
        captured = {}

        def fake_run_health_query(backend, *, now):
            captured["now"] = now
            return _healthy_stats(now)

        backend = SimpleNamespace(_get_conn=lambda: None)
        dal = SimpleNamespace(_backend=backend)

        monkeypatch.setattr(
            "src.service.sa_market_news_health._run_health_query",
            fake_run_health_query,
        )
        report = compute_market_news_health(dal, now=WEEKDAY_MARKET_HOURS_UTC)
        assert captured["now"] == WEEKDAY_MARKET_HOURS_UTC
        assert report["ok"] is True


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestHealthRoute:
    @staticmethod
    def _set_sa_enabled(value: bool, monkeypatch):
        cfg = get_agent_config()
        original = cfg.sa_enabled
        cfg.sa_enabled = value
        monkeypatch.setattr(
            "src.api.routes.seeking_alpha.get_agent_config",
            lambda: cfg,
        )
        return original

    def test_route_returns_payload_when_ok(self, monkeypatch):
        original = self._set_sa_enabled(True, monkeypatch)
        try:
            monkeypatch.setattr(
                "src.api.routes.seeking_alpha.compute_market_news_health",
                lambda dal: {
                    "ok": True,
                    "severity": SEVERITY_OK,
                    "reasons": [],
                    "freshness": {},
                    "feed_health": {},
                    "detail_health": {},
                    "thresholds": {},
                    "evaluated_at": "2026-04-25T00:00:00+00:00",
                    "is_market_hours": False,
                },
            )

            class _Resp:
                status_code = 200

            resp = _Resp()
            result = market_news_health(response=resp, strict=False, dal=object())
            assert result["severity"] == SEVERITY_OK
            assert resp.status_code == 200
        finally:
            get_agent_config().sa_enabled = original

    def test_route_strict_warning_returns_503(self, monkeypatch):
        original = self._set_sa_enabled(True, monkeypatch)
        try:
            monkeypatch.setattr(
                "src.api.routes.seeking_alpha.compute_market_news_health",
                lambda dal: {
                    "ok": False,
                    "severity": SEVERITY_WARNING,
                    "reasons": [{"severity": "warning", "code": "stale_fetch", "message": "x"}],
                    "freshness": {},
                    "feed_health": {},
                    "detail_health": {},
                    "thresholds": {},
                    "evaluated_at": "2026-04-25T00:00:00+00:00",
                    "is_market_hours": False,
                },
            )

            class _Resp:
                status_code = 200

            resp = _Resp()
            result = market_news_health(response=resp, strict=True, dal=object())
            assert result["severity"] == SEVERITY_WARNING
            assert resp.status_code == 503
        finally:
            get_agent_config().sa_enabled = original

    def test_route_non_strict_warning_returns_200(self, monkeypatch):
        original = self._set_sa_enabled(True, monkeypatch)
        try:
            monkeypatch.setattr(
                "src.api.routes.seeking_alpha.compute_market_news_health",
                lambda dal: {
                    "ok": False,
                    "severity": SEVERITY_WARNING,
                    "reasons": [],
                    "freshness": {},
                    "feed_health": {},
                    "detail_health": {},
                    "thresholds": {},
                    "evaluated_at": "2026-04-25T00:00:00+00:00",
                    "is_market_hours": False,
                },
            )

            class _Resp:
                status_code = 200

            resp = _Resp()
            result = market_news_health(response=resp, strict=False, dal=object())
            assert result["severity"] == SEVERITY_WARNING
            assert resp.status_code == 200
        finally:
            get_agent_config().sa_enabled = original

    def test_route_returns_503_when_sa_disabled(self, monkeypatch):
        original = self._set_sa_enabled(False, monkeypatch)
        try:

            class _Resp:
                status_code = 200

            with pytest.raises(HTTPException) as exc:
                market_news_health(response=_Resp(), strict=False, dal=object())
            assert exc.value.status_code == 503
        finally:
            get_agent_config().sa_enabled = original