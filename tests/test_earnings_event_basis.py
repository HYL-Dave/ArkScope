"""Observed release sessions, not fiscal period ends or nearest available bars."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.macro_calendar.local_store import MacroCalendarLocalStore
from src.tools import earnings_tools as tools


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    path = tmp_path / "calendar.db"
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(path))
    store = MacroCalendarLocalStore(path)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2025, 10, 25, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(tools, "datetime", Clock)
    # The obsolete endpoint supplies only fiscal period ends. No remote call is allowed.
    monkeypatch.setattr("src.tools.analyst_tools.get_analyst_consensus", lambda *_: {
        "earnings":{"history":[{"period":"2025-09-30", "actual":2, "estimate":1}], "upcoming":None}})
    dates = ["2025-09-23", "2025-09-24", "2025-09-25", "2025-09-26", "2025-09-29", "2025-09-30",
             "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09"]
    bars = [SimpleNamespace(datetime=day, close=110 if day >= "2025-10-02" else 100) for day in dates]
    dal = Mock()
    dal.get_prices.return_value = SimpleNamespace(bars=bars, interval="1d", ticker="TEST")
    def release(hour="amc", actual=2, day="2025-10-01"):
        return store.upsert_earnings_event({"symbol":"TEST", "report_date":day, "year":2025, "quarter":3,
            "hour":hour, "eps_actual":actual, "eps_estimate":1}, source_payload={"date":day},
            observed_at=datetime(2025, 10, 2, 22, tzinfo=timezone.utc))
    return dal, release, path


def test_after_close_release_maps_to_next_session_not_fiscal_end(scenario):
    dal, release, path = scenario
    release()
    before = path.read_bytes()
    result = tools.get_earnings_impact(dal, "TEST")
    move = result["historical_moves"][0]
    assert move["release_date"] == "2025-10-01"
    assert move["reaction_session"] == "2025-10-02"
    assert move["earnings_day_move_pct"] == 10
    assert path.read_bytes() == before
    assert "surprise_predictive" not in result["surprise_analysis"]
    assert "expected_move" not in result
    assert result["summary"]["sample_size"] == 1


@pytest.mark.parametrize("hour,actual,code", [("",2,"release_timing_unknown"),
                                             ("amc",None,"actual_release_unconfirmed")])
def test_ambiguous_or_scheduled_only_events_are_explicit_gaps(scenario, hour, actual, code):
    dal, release, _ = scenario
    release(hour, actual)
    result = tools.get_earnings_impact(dal, "TEST")
    assert result["quarters_analyzed"] == 0
    assert result["event_gaps"][0]["code"] == code


def test_missing_reaction_bar_cannot_use_nearest_available_day(scenario):
    dal, release, _ = scenario
    release()
    dal.get_prices.return_value.bars = [bar for bar in dal.get_prices.return_value.bars if bar.datetime != "2025-10-02"]
    result = tools.get_earnings_impact(dal, "TEST")
    assert result["quarters_analyzed"] == 0
    assert result["event_gaps"][0]["code"] == "reaction_session_price_missing"


def test_incomplete_five_session_window_is_not_shortened(scenario):
    dal, release, _ = scenario
    release()
    dal.get_prices.return_value.bars = dal.get_prices.return_value.bars[5:9]
    result = tools.get_earnings_impact(dal, "TEST")
    move = result["historical_moves"][0]
    assert move["pre_drift_5d_pct"] is None and move["post_drift_5d_pct"] is None
    assert move["window_gaps"] == {"pre":"five_session_window_incomplete", "post":"five_session_window_incomplete"}


def test_duplicate_daily_bar_does_not_select_an_arbitrary_close(scenario):
    dal, release, _ = scenario
    release()
    dal.get_prices.return_value.bars.append(SimpleNamespace(datetime="2025-10-02", close=120))
    result = tools.get_earnings_impact(dal, "TEST")
    assert result["quarters_analyzed"] == 0
    assert result["event_gaps"][0]["code"] == "reaction_session_price_missing"


def test_missing_calendar_does_not_install_a_database(tmp_path, monkeypatch):
    path = tmp_path / "absent" / "calendar.db"
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(path))
    monkeypatch.setattr("src.tools.analyst_tools.get_analyst_consensus", lambda *_: {"earnings":{}})
    result = tools.get_earnings_impact(Mock(), "TEST")
    assert result["error_code"] == "earnings_calendar_unavailable"
    assert not path.parent.exists()


def test_five_session_calculation_crosses_holiday_without_inventing_a_bar():
    dates = ["2025-07-01", "2025-07-02", "2025-07-03", "2025-07-07", "2025-07-08", "2025-07-09", "2025-07-10"]
    result = tools._compute_move([100,100,100,100,100,100,110], dates, 6)
    assert result["pre_drift_5d_pct"] == 0
    assert result["post_drift_5d_pct"] is None


def test_before_open_release_uses_same_session_and_zero_actual_is_observed(scenario, monkeypatch):
    dal, release, _ = scenario
    release(hour="bmo", actual=0, day="2025-10-02")
    def forbidden(*args, **kwargs):
        raise AssertionError("a local observation must not request analyst/provider data")
    monkeypatch.setattr("src.tools.analyst_tools.get_analyst_consensus", forbidden)
    result = tools.get_earnings_impact(dal, "TEST")
    move = result["historical_moves"][0]
    assert move["reaction_session"] == "2025-10-02"
    assert move["beat_miss"] == "miss"
    assert result["surprise_analysis"]["miss_down_ratio"] == 0


def test_unclosed_reaction_session_is_not_an_observed_daily_close(scenario, monkeypatch):
    dal, release, _ = scenario
    release(hour="bmo", day="2025-10-02")
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2025, 10, 2, 19, tzinfo=timezone.utc)
    monkeypatch.setattr(tools, "datetime", Clock)
    # Make the provider observation available before the close.
    with MacroCalendarLocalStore(scenario[2])._connect() as connection:
        connection.execute("UPDATE cal_earnings_event_revisions SET observed_at='2025-10-02T18:00:00Z'")
    result = tools.get_earnings_impact(dal, "TEST")
    assert result["quarters_analyzed"] == 0
    assert result["event_gaps"][0]["code"] == "reaction_session_incomplete"


def test_early_close_is_complete_at_calendar_close_not_fixed_utc_hour():
    result = tools._compute_move([100,110], ["2025-07-02","2025-07-03"], 1,
                                now=datetime(2025,7,3,17,tzinfo=timezone.utc))
    assert result["earnings_day_move_pct"] == 10


def test_empty_ticker_cannot_query_the_entire_calendar(scenario):
    dal, release, _ = scenario
    release()
    result = tools.get_earnings_impact(dal, "  ")
    assert result["error_code"] == "invalid_ticker"
    dal.get_prices.assert_not_called()
