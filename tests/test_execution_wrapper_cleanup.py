"""Retired execution wrappers must not reappear beside current entrypoints."""

import pytest

from src import daily_update
from src.service import data_scheduler, jobs


MACRO_DELEGATES = (
    "_run_fetch_fred_release_dates",
    "_run_fetch_fred_series",
    "_run_fetch_economic_calendar_recent",
    "_run_fetch_economic_calendar_backfill",
    "_run_fetch_earnings_calendar",
    "_run_fetch_ipo_calendar",
)


@pytest.mark.parametrize("name", MACRO_DELEGATES)
def test_macro_delegate_is_absent(name):
    assert not hasattr(jobs, name)


def test_scheduler_subprocess_wrapper_is_absent():
    assert not hasattr(data_scheduler, "_run_subprocess")


def test_daily_update_command_wrapper_is_absent():
    assert not hasattr(daily_update, "run_command")
