"""Tests for macro_calendar read API + agent tools (P1.2 commit 6).

Coverage:
  - /macro/economic-calendar / earnings / ipo / series routes
  - 503 when macro_calendar.enabled = false
  - 400 on malformed iso-date params, to_date < from_date
  - 404 on unknown series_id
  - get_economic_calendar tool: disabled / formatted output / no-rows path
  - get_macro_value tool: disabled / unknown series / no-obs / found
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.config import get_agent_config
from src.api.routes.macro_calendar import (
    earnings_calendar,
    economic_calendar,
    ipo_calendar,
    macro_series,
)
from src.tools.macro_calendar_tools import (
    get_economic_calendar,
    get_macro_value,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_macro(monkeypatch_or_cfg=None):
    """Toggle macro_calendar.enabled=True; return undo callable."""
    cfg = get_agent_config()
    original = cfg.macro_calendar_enabled
    cfg.macro_calendar_enabled = True

    def undo():
        cfg.macro_calendar_enabled = original

    return undo


def _disable_macro():
    cfg = get_agent_config()
    original = cfg.macro_calendar_enabled
    cfg.macro_calendar_enabled = False

    def undo():
        cfg.macro_calendar_enabled = original

    return undo


# ---------------------------------------------------------------------------
# /macro/economic-calendar route
# ---------------------------------------------------------------------------


class TestEconomicCalendarRoute:
    def test_disabled_returns_503(self):
        undo = _disable_macro()
        try:
            with pytest.raises(HTTPException) as exc:
                economic_calendar(
                    country=None, impact=None,
                    from_date=None, to_date=None, as_of=None,
                    limit=100, dal=object(),
                )
            assert exc.value.status_code == 503
        finally:
            undo()

    def test_default_window_reaches_store(self, monkeypatch):
        undo = _enable_macro()
        try:
            captured = {}

            def fake_list(self, **kw):
                captured.update(kw)
                return [
                    {
                        "event_id": 1,
                        "country": "US",
                        "event_name": "CPI m/m",
                        "event_time": datetime(2026, 4, 12, 12, 30, tzinfo=timezone.utc),
                        "impact": "high",
                        "unit": "%",
                        "actual": 0.3,
                        "estimate": 0.2,
                        "prev": 0.1,
                    }
                ]

            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.list_economic_events",
                fake_list,
                raising=True,
            )
            result = economic_calendar(
                country="US,CN", impact="high",
                from_date=None, to_date=None, as_of=None,
                limit=100, dal=object(),
            )
            assert result["count"] == 1
            assert captured["countries"] == ["US", "CN"]
            assert captured["impacts"] == ["high"]
        finally:
            undo()

    def test_to_before_from_returns_400(self):
        undo = _enable_macro()
        try:
            with pytest.raises(HTTPException) as exc:
                economic_calendar(
                    country=None, impact=None,
                    from_date="2026-04-30", to_date="2026-04-01",
                    as_of=None, limit=100, dal=object(),
                )
            assert exc.value.status_code == 400
        finally:
            undo()

    def test_invalid_iso_date_returns_400(self):
        undo = _enable_macro()
        try:
            with pytest.raises(HTTPException) as exc:
                economic_calendar(
                    country=None, impact=None,
                    from_date="not-a-date", to_date=None,
                    as_of=None, limit=100, dal=object(),
                )
            assert exc.value.status_code == 400
        finally:
            undo()

    def test_as_of_threaded_through(self, monkeypatch):
        undo = _enable_macro()
        try:
            captured = {}

            def fake_list(self, **kw):
                captured.update(kw)
                return []

            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.list_economic_events",
                fake_list,
                raising=True,
            )
            economic_calendar(
                country=None, impact=None,
                from_date=None, to_date=None,
                as_of="2024-12-18T18:00:00Z",
                limit=100, dal=object(),
            )
            assert captured["as_of"] == datetime(2024, 12, 18, 18, 0, tzinfo=timezone.utc)
        finally:
            undo()

    def test_as_of_date_only_maps_to_eod_utc(self, monkeypatch):
        """Spec §6.1: date-only as_of must cover the full UTC day so callers
        who pass YYYY-MM-DD don't silently miss revisions observed that day."""
        undo = _enable_macro()
        try:
            captured = {}

            def fake_list(self, **kw):
                captured.update(kw)
                return []

            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.list_economic_events",
                fake_list,
                raising=True,
            )
            economic_calendar(
                country=None, impact=None,
                from_date=None, to_date=None,
                as_of="2024-12-18",
                limit=100, dal=object(),
            )
            assert captured["as_of"] == datetime(
                2024, 12, 18, 23, 59, 59, 999999, tzinfo=timezone.utc
            )
        finally:
            undo()

    def test_same_day_window_covers_full_day(self, monkeypatch):
        """Regression: ``from_date=to_date=D`` must hit the FULL UTC day,
        not a one-microsecond slice. ``from_date`` is SOD, ``to_date`` is
        EOD; if either side is wrong the route excludes most of the day."""
        undo = _enable_macro()
        try:
            captured = {}

            def fake_list(self, **kw):
                captured.update(kw)
                return []

            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.list_economic_events",
                fake_list,
                raising=True,
            )
            economic_calendar(
                country=None, impact=None,
                from_date="2024-12-18", to_date="2024-12-18",
                as_of=None, limit=100, dal=object(),
            )
            assert captured["date_from"] == datetime(
                2024, 12, 18, 0, 0, 0, 0, tzinfo=timezone.utc
            )
            assert captured["date_to"] == datetime(
                2024, 12, 18, 23, 59, 59, 999999, tzinfo=timezone.utc
            )
        finally:
            undo()


# ---------------------------------------------------------------------------
# /macro/earnings-calendar + /macro/ipo-calendar routes
# ---------------------------------------------------------------------------


class TestEarningsAndIpoRoutes:
    def test_earnings_threads_symbols_csv(self, monkeypatch):
        undo = _enable_macro()
        try:
            captured = {}

            def fake_list(self, **kw):
                captured.update(kw)
                return []

            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.list_earnings_events",
                fake_list,
                raising=True,
            )
            earnings_calendar(
                symbol="AAPL,NVDA",
                from_date=None, to_date=None, as_of=None,
                limit=100, dal=object(),
            )
            assert captured["symbols"] == ["AAPL", "NVDA"]
        finally:
            undo()

    def test_ipo_threads_status_csv(self, monkeypatch):
        undo = _enable_macro()
        try:
            captured = {}

            def fake_list(self, **kw):
                captured.update(kw)
                return []

            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.list_ipo_events",
                fake_list,
                raising=True,
            )
            ipo_calendar(
                status="priced,filed",
                from_date=None, to_date=None, as_of=None,
                limit=100, dal=object(),
            )
            assert captured["statuses"] == ["priced", "filed"]
        finally:
            undo()


# ---------------------------------------------------------------------------
# /macro/series/{series_id} route
# ---------------------------------------------------------------------------


class TestMacroSeriesRoute:
    def test_unknown_series_returns_404(self, monkeypatch):
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.get_macro_observations",
                lambda self, *a, **kw: None,
                raising=True,
            )
            with pytest.raises(HTTPException) as exc:
                macro_series(
                    "UNKNOWN",
                    from_date=None, to_date=None, as_of=None,
                    limit=1000, dal=object(),
                )
            assert exc.value.status_code == 404
        finally:
            undo()

    def test_returns_metadata_plus_observations(self, monkeypatch):
        undo = _enable_macro()
        try:
            payload = {
                "series_id": "CPIAUCNS",
                "title": "CPI",
                "frequency": "m",
                "units": "Index",
                "observations": [
                    {"observation_date": date(2024, 3, 1), "value": 312.332},
                ],
            }
            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.get_macro_observations",
                lambda self, *a, **kw: payload,
                raising=True,
            )
            result = macro_series(
                "cpiaucns",
                from_date=None, to_date=None, as_of=None,
                limit=1000, dal=object(),
            )
            assert result["title"] == "CPI"
            assert len(result["observations"]) == 1
        finally:
            undo()

    def test_series_id_uppercased(self, monkeypatch):
        undo = _enable_macro()
        try:
            captured = {}

            def fake(self, sid, **kw):
                captured["series_id"] = sid
                return {"series_id": sid, "title": "x", "frequency": "m",
                        "units": "x", "observations": []}

            monkeypatch.setattr(
                "src.macro_calendar.store.MacroCalendarStore.get_macro_observations",
                fake,
                raising=True,
            )
            macro_series(
                "cpiaucns",
                from_date=None, to_date=None, as_of=None,
                limit=1000, dal=object(),
            )
            assert captured["series_id"] == "CPIAUCNS"
        finally:
            undo()


# ---------------------------------------------------------------------------
# get_economic_calendar tool
# ---------------------------------------------------------------------------


class TestGetEconomicCalendarTool:
    def test_disabled_returns_helpful_string(self):
        undo = _disable_macro()
        try:
            out = get_economic_calendar(dal=object())
            assert "disabled" in out.lower()
        finally:
            undo()

    def test_unavailable_dal_returns_helpful_string(self):
        undo = _enable_macro()
        try:
            dal = SimpleNamespace(_backend=object())  # no _get_conn
            out = get_economic_calendar(dal=dal)
            assert "PostgreSQL" in out or "_get_conn" in out
        finally:
            undo()

    def test_no_rows_message(self, monkeypatch):
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: MagicMock(
                    is_available=MagicMock(return_value=True),
                    list_economic_events=MagicMock(return_value=[]),
                ),
            )
            out = get_economic_calendar(dal=object(), country="US")
            assert "No economic events" in out
            assert "country=US" in out
        finally:
            undo()

    def test_formats_event_rows(self, monkeypatch):
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: MagicMock(
                    is_available=MagicMock(return_value=True),
                    list_economic_events=MagicMock(return_value=[
                        {
                            "event_time": datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc),
                            "country": "US",
                            "event_name": "Fed Interest Rate Decision",
                            "impact": "high",
                            "unit": "%",
                            "actual": 4.25,
                            "estimate": 4.5,
                            "prev": 4.75,
                        }
                    ]),
                ),
            )
            out = get_economic_calendar(dal=object())
            assert "Fed Interest Rate Decision" in out
            assert "[HIGH]" in out
            assert "actual=4.25 %" in out
            assert "est=4.5 %" in out
            assert "prev=4.75 %" in out
        finally:
            undo()

    def test_invalid_as_of_returns_error(self, monkeypatch):
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: MagicMock(is_available=MagicMock(return_value=True)),
            )
            out = get_economic_calendar(dal=object(), as_of="not-a-date")
            assert "Invalid as_of" in out
        finally:
            undo()

    def test_date_only_as_of_passes_eod_to_store(self, monkeypatch):
        """Tool layer must apply the same date-only → EOD UTC contract as
        the API. Otherwise an agent passing a date string would silently miss
        same-day revisions."""
        undo = _enable_macro()
        try:
            captured = {}
            store_mock = MagicMock(
                is_available=MagicMock(return_value=True),
                list_economic_events=MagicMock(
                    side_effect=lambda **kw: (captured.update(kw) or [])
                ),
            )
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: store_mock,
            )
            get_economic_calendar(dal=object(), as_of="2024-12-18")
            assert captured["as_of"] == datetime(
                2024, 12, 18, 23, 59, 59, 999999, tzinfo=timezone.utc
            )
        finally:
            undo()


# ---------------------------------------------------------------------------
# get_macro_value tool
# ---------------------------------------------------------------------------


class TestGetMacroValueTool:
    def test_disabled_returns_helpful_string(self):
        undo = _disable_macro()
        try:
            out = get_macro_value(
                dal=object(),
                series_id="CPIAUCNS",
                observation_date="2024-03-01",
            )
            assert "disabled" in out.lower()
        finally:
            undo()

    def test_invalid_observation_date(self, monkeypatch):
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: MagicMock(is_available=MagicMock(return_value=True)),
            )
            out = get_macro_value(
                dal=object(), series_id="CPIAUCNS", observation_date="bad-date",
            )
            assert "ISO YYYY-MM-DD" in out
        finally:
            undo()

    def test_unknown_series(self, monkeypatch):
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: MagicMock(
                    is_available=MagicMock(return_value=True),
                    get_macro_observations=MagicMock(return_value=None),
                ),
            )
            out = get_macro_value(
                dal=object(),
                series_id="DOES_NOT_EXIST",
                observation_date="2024-03-01",
            )
            assert "Unknown macro series" in out
        finally:
            undo()

    def test_no_observation_with_as_of_explains_unknown(self, monkeypatch):
        """Critical lookahead-safe path: as_of < first publication → empty
        observation list. The tool must explain WHY, not return blank."""
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: MagicMock(
                    is_available=MagicMock(return_value=True),
                    get_macro_observations=MagicMock(return_value={
                        "series_id": "CPIAUCNS",
                        "title": "CPI",
                        "units": "Index",
                        "observations": [],
                    }),
                ),
            )
            out = get_macro_value(
                dal=object(),
                series_id="CPIAUCNS",
                observation_date="2024-03-01",
                as_of="2024-04-01",
            )
            assert "as of 2024-04-01" in out
            assert "unknown" in out.lower()
        finally:
            undo()

    def test_found_value_formatted(self, monkeypatch):
        undo = _enable_macro()
        try:
            monkeypatch.setattr(
                "src.tools.macro_calendar_tools.MacroCalendarStore",
                lambda dal: MagicMock(
                    is_available=MagicMock(return_value=True),
                    get_macro_observations=MagicMock(return_value={
                        "series_id": "CPIAUCNS",
                        "title": "Consumer Price Index",
                        "units": "Index 1982-1984=100",
                        "observations": [{
                            "observation_date": date(2024, 3, 1),
                            "value": 312.332,
                            "realtime_start": date(2024, 4, 10),
                            "realtime_end": date(9999, 12, 31),
                        }],
                    }),
                ),
            )
            out = get_macro_value(
                dal=object(),
                series_id="cpiaucns",  # lowercased input → uppercased
                observation_date="2024-03-01",
            )
            assert "CPIAUCNS" in out
            assert "312.332" in out
            assert "Index 1982-1984=100" in out

        finally:
            undo()