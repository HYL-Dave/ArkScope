"""Rolling page-attempt capacity, not an estimate of SA HTTP traffic."""

import importlib

import pytest


POLICY = dict(hour_limit=4, day_limit=8, hour_reserve=2, day_reserve=2)
UNCAPPED = dict(hour_limit=None, day_limit=None, hour_reserve=0, day_reserve=0)


def eligibility(attempts, priority, now, policy=None):
    return importlib.import_module("src.sa.acquisition_policy").navigation_eligibility(
        attempts, policy or POLICY, priority, now
    )


def test_financial_work_leaves_unused_routine_reserve():
    attempts = [(100., "background"), (101., "background")]
    assert eligibility(attempts, "background", 102) == {"allowed": False, "retry_at": 3700.}
    assert eligibility(attempts, "routine", 102)["allowed"] is True
    assert eligibility(attempts, "background", 3700)["allowed"] is True


def test_reserve_expiration_does_not_necessarily_free_background_capacity():
    attempts = [(100., "routine"), (101., "routine"), (102., "background"), (103., "background")]
    assert eligibility(attempts, "background", 104)["retry_at"] == 3702.
    assert eligibility(attempts, "routine", 104)["retry_at"] == 3700.


def test_both_windows_must_allow_an_attempt():
    policy = dict(hour_limit=4, day_limit=4, hour_reserve=0, day_reserve=1)
    attempts = [(1., "background"), (2., "background"), (3., "background")]
    assert eligibility(attempts, "background", 4000, policy)["retry_at"] == 86401.
    assert eligibility(attempts, "routine", 4000, policy)["allowed"] is True


def test_fully_reserved_policy_has_no_background_retry_time():
    policy = dict(hour_limit=2, day_limit=4, hour_reserve=2, day_reserve=4)
    assert eligibility([], "background", 100, policy) == {"allowed": False, "retry_at": None}


@pytest.mark.parametrize("change", [dict(hour_limit=True), dict(day_limit=0), dict(hour_reserve=5),
                                   dict(day_reserve=-1), dict(hour_limit=1.5), dict(extra=1)])
def test_invalid_policy_is_rejected(change):
    with pytest.raises(ValueError):
        eligibility([], "routine", 100, {**POLICY, **change})


@pytest.mark.parametrize("now", [True, float("nan"), float("inf"), -1])
def test_invalid_clock_is_rejected(now):
    with pytest.raises(ValueError):
        eligibility([], "routine", now)


def test_future_or_unknown_attempt_is_not_silently_ignored():
    with pytest.raises(ValueError):
        eligibility([(101, "routine")], "routine", 100)
    with pytest.raises(ValueError):
        eligibility([(10, "other")], "routine", 100)


@pytest.mark.parametrize("priority", ["routine", "background"])
def test_explicit_uncapped_policy_does_not_stop_at_an_arbitrary_count(priority):
    attempts = [(float(i), "routine" if i % 2 else "background") for i in range(10000)]
    assert eligibility(attempts, priority, 10000, UNCAPPED) == {"allowed": True, "retry_at": None}


@pytest.mark.parametrize("change", [dict(hour_reserve=1), dict(day_reserve=True),
                                   dict(hour_limit=5), dict(day_limit=5)])
def test_uncapped_policy_rejects_unused_reserves_and_partial_modes(change):
    with pytest.raises(ValueError):
        eligibility([], "routine", 100, {**UNCAPPED, **change})


def test_uncapped_policy_still_validates_navigation_history():
    assert eligibility([], "routine", 100, UNCAPPED)["allowed"] is True
    for attempts in ([(101, "routine")], [(10, "other")]):
        with pytest.raises(ValueError):
            eligibility(attempts, "routine", 100, UNCAPPED)
