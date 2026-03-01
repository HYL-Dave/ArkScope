"""Tests for Data Freshness Registry."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from src.tools.freshness import (
    FreshnessRegistry,
    SourceHealth,
    check_data_freshness,
    get_registry,
    reset_for_tests,
    _parse_ts,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset singleton before and after each test."""
    reset_for_tests()
    yield
    reset_for_tests()


# ── SourceHealth dataclass ──────────────────────────────────


class TestSourceHealth:
    def test_defaults(self):
        h = SourceHealth(source="news")
        assert h.source == "news"
        assert h.latest_data_at is None
        assert h.record_count_recent == 0
        assert h.expected_frequency == "daily"
        assert h.is_stale is False
        assert h.stale_reason == ""
        assert h.details == {}


# ── FreshnessRegistry scan ──────────────────────────────────


class TestFreshnessRegistryScan:
    def _make_backend(self, stats):
        backend = MagicMock()
        backend.query_health_stats.return_value = stats
        return backend

    def test_scan_fresh_data(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=2)
        stats = {
            "news": {
                "rows": [("finnhub", recent, 42)],
                "error": None,
            },
            "prices": {
                "rows": [(now - timedelta(hours=12),)],
                "error": None,
            },
            "iv_history": {
                "rows": [(now - timedelta(hours=6),)],
                "error": None,
            },
            "financial_cache": {
                "rows": [("sec_edgar", 30, 5)],
                "error": None,
            },
        }
        fr = FreshnessRegistry(db_backend=self._make_backend(stats))
        result = fr.scan(force=True)

        assert "news" in result
        assert "prices" in result
        assert "iv_history" in result
        assert "fundamentals_cache" in result

        # All should be fresh (within thresholds)
        assert result["news"].is_stale is False
        assert result["prices"].is_stale is False
        assert result["iv_history"].is_stale is False
        assert result["fundamentals_cache"].is_stale is False

    def test_scan_stale_news(self):
        old = datetime.now(timezone.utc) - timedelta(hours=30)
        stats = {
            "news": {"rows": [("finnhub", old, 0)], "error": None},
            "prices": {"rows": [], "error": None},
            "iv_history": {"rows": [], "error": None},
            "financial_cache": {"rows": [], "error": None},
        }
        fr = FreshnessRegistry(db_backend=self._make_backend(stats))
        result = fr.scan(force=True)

        assert result["news"].is_stale is True
        assert "30h" in result["news"].stale_reason or "old" in result["news"].stale_reason

    def test_scan_query_error(self):
        stats = {
            "news": {"rows": [], "error": "connection refused"},
            "prices": {"rows": [], "error": None},
            "iv_history": {"rows": [], "error": None},
            "financial_cache": {"rows": [], "error": None},
        }
        fr = FreshnessRegistry(db_backend=self._make_backend(stats))
        result = fr.scan(force=True)

        assert result["news"].is_stale is True
        assert "query failed" in result["news"].stale_reason

    def test_scan_no_data(self):
        stats = {
            "news": {"rows": [], "error": None},
            "prices": {"rows": [], "error": None},
            "iv_history": {"rows": [], "error": None},
            "financial_cache": {"rows": [], "error": None},
        }
        fr = FreshnessRegistry(db_backend=self._make_backend(stats))
        result = fr.scan(force=True)

        assert result["news"].is_stale is True
        assert "no news" in result["news"].stale_reason

    def test_scan_cache_hit(self):
        stats = {
            "news": {"rows": [], "error": None},
            "prices": {"rows": [], "error": None},
            "iv_history": {"rows": [], "error": None},
            "financial_cache": {"rows": [], "error": None},
        }
        backend = self._make_backend(stats)
        fr = FreshnessRegistry(db_backend=backend)

        fr.scan(force=True)
        fr.scan()  # should use cache
        fr.scan()  # should use cache

        assert backend.query_health_stats.call_count == 1

    def test_scan_force_bypass_cache(self):
        stats = {
            "news": {"rows": [], "error": None},
            "prices": {"rows": [], "error": None},
            "iv_history": {"rows": [], "error": None},
            "financial_cache": {"rows": [], "error": None},
        }
        backend = self._make_backend(stats)
        fr = FreshnessRegistry(db_backend=backend)

        fr.scan(force=True)
        fr.scan(force=True)

        assert backend.query_health_stats.call_count == 2

    def test_scan_no_backend(self):
        fr = FreshnessRegistry(db_backend=None)
        result = fr.scan(force=True)
        assert result == {}

    def test_scan_total_failure(self):
        """When query_health_stats() itself raises, all sources marked stale."""
        backend = MagicMock()
        backend.query_health_stats.side_effect = RuntimeError("connection lost")
        fr = FreshnessRegistry(db_backend=backend)
        result = fr.scan(force=True)

        # Should have all 4 sources, all stale
        assert len(result) == 4
        for key in ("news", "prices", "iv_history", "fundamentals_cache"):
            assert key in result
            assert result[key].is_stale is True
            assert "connection lost" in result[key].stale_reason

        # format_detailed should NOT say "No data sources scanned yet"
        detailed = fr.format_detailed()
        assert "No data sources" not in detailed
        assert "STALE" in detailed


# ── Format methods ──────────────────────────────────────────


class TestFreshnessFormat:
    def _make_registry_with_data(self):
        now = datetime.now(timezone.utc)
        backend = MagicMock()
        backend.query_health_stats.return_value = {
            "news": {
                "rows": [("finnhub", now - timedelta(hours=3), 15),
                         ("polygon", now - timedelta(hours=5), 10)],
                "error": None,
            },
            "prices": {
                "rows": [(now - timedelta(hours=12),)],
                "error": None,
            },
            "iv_history": {
                "rows": [(now - timedelta(hours=18),)],
                "error": None,
            },
            "financial_cache": {
                "rows": [("sec_edgar", 25, 3)],
                "error": None,
            },
        }
        fr = FreshnessRegistry(db_backend=backend)
        fr.scan(force=True)
        return fr

    def test_format_summary(self):
        fr = self._make_registry_with_data()
        summary = fr.format_summary()
        assert "News:" in summary
        assert "Prices:" in summary
        assert "IV:" in summary
        assert "Fundamentals:" in summary

    def test_format_summary_empty(self):
        fr = FreshnessRegistry(db_backend=None)
        assert fr.format_summary() == ""

    def test_format_detailed(self):
        fr = self._make_registry_with_data()
        detailed = fr.format_detailed()
        assert "Data Freshness Report" in detailed
        assert "[OK]" in detailed
        assert "news" in detailed

    def test_format_detailed_empty(self):
        fr = FreshnessRegistry(db_backend=None)
        assert "No data sources" in fr.format_detailed()


# ── Singleton management ────────────────────────────────────


class TestSingleton:
    def test_get_registry_creates(self):
        backend = MagicMock()
        fr = get_registry(db_backend=backend)
        assert fr is not None
        assert isinstance(fr, FreshnessRegistry)

    def test_get_registry_reuses(self):
        backend = MagicMock()
        fr1 = get_registry(db_backend=backend)
        fr2 = get_registry(db_backend=backend)
        assert fr1 is fr2

    def test_get_registry_none_returns_current(self):
        backend = MagicMock()
        get_registry(db_backend=backend)
        fr = get_registry()  # No backend → return existing
        assert fr is not None

    def test_get_registry_none_before_init(self):
        fr = get_registry()
        assert fr is None

    def test_reset_for_tests(self):
        backend = MagicMock()
        get_registry(db_backend=backend)
        reset_for_tests()
        fr = get_registry()
        assert fr is None


# ── Tool function ───────────────────────────────────────────


class TestCheckDataFreshness:
    def test_file_backend(self):
        dal = MagicMock()
        dal._backend = MagicMock()  # Not a DatabaseBackend
        result = check_data_freshness(dal)
        assert "file" in result.lower() or "File" in result

    def test_no_backend_attr(self):
        dal = MagicMock(spec=[])
        result = check_data_freshness(dal)
        assert "requires" in result.lower()


# ── Timestamp parsing ───────────────────────────────────────


class TestParseTs:
    def test_none(self):
        assert _parse_ts(None) is None

    def test_datetime_with_tz(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _parse_ts(dt) == dt

    def test_datetime_without_tz(self):
        dt = datetime(2026, 1, 1)
        result = _parse_ts(dt)
        assert result.tzinfo == timezone.utc

    def test_string_date(self):
        result = _parse_ts("2026-01-15")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
