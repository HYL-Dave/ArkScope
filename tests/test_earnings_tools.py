"""Earnings returns use exact, complete exchange-session windows."""

import pytest

from src.tools.earnings_tools import _compute_move, get_earnings_impact


def test_positive_move_with_partial_drift_windows():
    result = _compute_move([100.0, 110.0, 108.0], ["2025-10-01", "2025-10-02", "2025-10-03"], 1)
    assert result["earnings_day_move_pct"] == 10
    assert result["pre_drift_5d_pct"] is None
    assert result["post_drift_5d_pct"] is None


def test_negative_move():
    result = _compute_move([100.0, 95.0], ["2025-10-02", "2025-10-03"], 1)
    assert result["earnings_day_move_pct"] == -5


def test_complete_five_session_windows():
    dates = ["2025-09-24", "2025-09-25", "2025-09-26", "2025-09-29", "2025-09-30", "2025-10-01",
             "2025-10-02", "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09"]
    result = _compute_move([90, 90, 90, 90, 90, 100, 110, 110, 110, 110, 110, 121], dates, 6)
    assert result["earnings_day_move_pct"] == 10
    assert result["pre_drift_5d_pct"] == 11.11
    assert result["post_drift_5d_pct"] == 10
    assert result["window_gaps"] == {}


@pytest.mark.parametrize("closes,dates,idx", [
    ([100], ["2025-10-02"], 0),
    ([100,110], ["2025-10-01","2025-10-03"], 1),
    ([100,110], ["2025-10-03","2025-10-04"], 1),
    ([0,110], ["2025-10-01","2025-10-02"], 1),
    ([100,float("nan")], ["2025-10-01","2025-10-02"], 1),
    ([100,110], ["2025-10-01","not-a-date"], 1),
])
def test_invalid_or_missing_session_cannot_be_substituted(closes, dates, idx):
    assert _compute_move(closes, dates, idx) is None


@pytest.mark.parametrize("quarters", [0,-1,True,1.5,1000])
def test_invalid_quarters_rejected_before_any_storage_access(quarters):
    assert get_earnings_impact(None, "TEST", quarters)["error_code"] == "invalid_quarters"


def test_tool_registered():
    from src.tools.registry import create_default_registry
    tool = create_default_registry().get("get_earnings_impact")
    assert tool is not None and tool.requires_dal and tool.category == "analysis"
