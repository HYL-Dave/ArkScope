from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from src.service.security_lifecycle_automation_config import (
    APPLY_PROFILE_TRANSITIONS_KEY,
    BATCH_LIMIT_KEY,
    ENABLED_KEY,
    INTERVAL_MINUTES_KEY,
    SecurityLifecycleAutomationConfig,
    calculate_security_lifecycle_automation_schedule,
    parse_security_lifecycle_automation_config,
    serialize_security_lifecycle_automation_config,
)


NOW = datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("missing_key", "expected_field", "expected_value"),
    [
        (ENABLED_KEY, "enabled", True),
        (INTERVAL_MINUTES_KEY, "interval_minutes", 5),
        (BATCH_LIMIT_KEY, "batch_limit", 2),
        (APPLY_PROFILE_TRANSITIONS_KEY, "apply_profile_transitions", False),
    ],
)
def test_each_missing_setting_uses_only_its_declared_default(
    missing_key, expected_field, expected_value
):
    stored = {
        ENABLED_KEY: "false",
        INTERVAL_MINUTES_KEY: "60",
        BATCH_LIMIT_KEY: "1",
        APPLY_PROFILE_TRANSITIONS_KEY: "true",
    }
    del stored[missing_key]

    state = parse_security_lifecycle_automation_config(stored)

    assert state.valid is True
    assert state.invalid_keys == ()
    assert state.config is not None
    assert getattr(state.config, expected_field) == expected_value


def test_absent_settings_resolve_to_the_complete_safe_default():
    state = parse_security_lifecycle_automation_config({})

    assert state.config == SecurityLifecycleAutomationConfig(
        enabled=True,
        interval_minutes=5,
        batch_limit=2,
        apply_profile_transitions=False,
    )
    assert state.effective_background_enabled is True
    assert state.effective_apply_profile_transitions is False


@pytest.mark.parametrize("key", [ENABLED_KEY, APPLY_PROFILE_TRANSITIONS_KEY])
@pytest.mark.parametrize("value", ["True", "FALSE", "1", "", " true", None])
def test_present_booleans_accept_only_exact_lowercase_literals(key, value):
    state = parse_security_lifecycle_automation_config({key: value})

    assert state.valid is False
    assert state.config is None
    assert state.invalid_keys == (key,)
    assert state.effective_background_enabled is False
    assert state.effective_apply_profile_transitions is False


@pytest.mark.parametrize("value", ["5", "17", "10080"])
def test_interval_accepts_canonical_values_inside_the_closed_bounds(value):
    state = parse_security_lifecycle_automation_config(
        {INTERVAL_MINUTES_KEY: value}
    )

    assert state.valid is True
    assert state.config is not None
    assert state.config.interval_minutes == int(value)


@pytest.mark.parametrize(
    "value",
    ["4", "10081", "05", "+5", "5.0", " 5", "5 ", "-5", "", "５", None],
)
def test_interval_rejects_out_of_bounds_and_noncanonical_forms(value):
    state = parse_security_lifecycle_automation_config(
        {INTERVAL_MINUTES_KEY: value}
    )

    assert state.valid is False
    assert state.invalid_keys == (INTERVAL_MINUTES_KEY,)


@pytest.mark.parametrize(("value", "expected"), [("1", 1), ("2", 2)])
def test_batch_limit_accepts_only_the_two_canonical_values(value, expected):
    state = parse_security_lifecycle_automation_config({BATCH_LIMIT_KEY: value})

    assert state.valid is True
    assert state.config is not None
    assert state.config.batch_limit == expected


@pytest.mark.parametrize(
    "value", ["0", "3", "01", "+1", "1.0", " 1", "1 ", "", None]
)
def test_batch_limit_rejects_every_other_form(value):
    state = parse_security_lifecycle_automation_config({BATCH_LIMIT_KEY: value})

    assert state.valid is False
    assert state.invalid_keys == (BATCH_LIMIT_KEY,)


def test_all_malformed_keys_are_reported_in_stable_sorted_order_and_fail_closed():
    state = parse_security_lifecycle_automation_config(
        {
            ENABLED_KEY: "TRUE",
            INTERVAL_MINUTES_KEY: "4",
            BATCH_LIMIT_KEY: "9",
            APPLY_PROFILE_TRANSITIONS_KEY: "yes",
        }
    )

    assert state.config is None
    assert state.invalid_keys == tuple(
        sorted(
            (
                ENABLED_KEY,
                INTERVAL_MINUTES_KEY,
                BATCH_LIMIT_KEY,
                APPLY_PROFILE_TRANSITIONS_KEY,
            )
        )
    )
    assert state.effective_background_enabled is False
    assert state.effective_apply_profile_transitions is False


def test_valid_disabled_background_does_not_disable_explicit_mutation_authority():
    state = parse_security_lifecycle_automation_config(
        {ENABLED_KEY: "false", APPLY_PROFILE_TRANSITIONS_KEY: "true"}
    )

    assert state.valid is True
    assert state.effective_background_enabled is False
    assert state.effective_apply_profile_transitions is True


def test_config_and_state_are_immutable_and_serialize_canonically():
    config = SecurityLifecycleAutomationConfig(
        enabled=False,
        interval_minutes=60,
        batch_limit=1,
        apply_profile_transitions=True,
    )
    state = parse_security_lifecycle_automation_config(
        serialize_security_lifecycle_automation_config(config)
    )

    assert serialize_security_lifecycle_automation_config(config) == {
        ENABLED_KEY: "false",
        INTERVAL_MINUTES_KEY: "60",
        BATCH_LIMIT_KEY: "1",
        APPLY_PROFILE_TRANSITIONS_KEY: "true",
    }
    assert state.config == config
    with pytest.raises(FrozenInstanceError):
        config.enabled = True
    with pytest.raises(FrozenInstanceError):
        state.invalid_keys = (ENABLED_KEY,)


def test_first_boot_is_due_now():
    schedule = calculate_security_lifecycle_automation_schedule(
        last_attempt=None,
        interval_minutes=5,
        now=NOW,
    )

    assert schedule.valid is True
    assert schedule.due is True
    assert schedule.last_attempt_at is None
    assert schedule.next_scheduled_at == NOW


def test_thirty_seconds_after_attempt_is_not_due_and_projects_five_minutes():
    schedule = calculate_security_lifecycle_automation_schedule(
        last_attempt="2026-08-31T04:00:00Z",
        interval_minutes=5,
        now=NOW + timedelta(seconds=30),
    )

    assert schedule.valid is True
    assert schedule.due is False
    assert schedule.last_attempt_at == NOW
    assert schedule.next_scheduled_at == NOW + timedelta(minutes=5)


def test_exact_five_minute_boundary_is_due():
    schedule = calculate_security_lifecycle_automation_schedule(
        last_attempt="2026-08-31T04:00:00+00:00",
        interval_minutes=5,
        now=NOW + timedelta(minutes=5),
    )

    assert schedule.due is True
    assert schedule.next_scheduled_at == NOW + timedelta(minutes=5)


def test_schedule_is_restart_independent_and_accepts_existing_compact_utc_offset():
    persisted = "2026-08-31T04:00:00+0000"

    before_restart = calculate_security_lifecycle_automation_schedule(
        last_attempt=persisted,
        interval_minutes=5,
        now=NOW + timedelta(minutes=2),
    )
    after_restart = calculate_security_lifecycle_automation_schedule(
        last_attempt=persisted,
        interval_minutes=5,
        now=NOW + timedelta(minutes=2),
    )

    assert before_restart == after_restart
    assert after_restart.due is False
    assert after_restart.next_scheduled_at == NOW + timedelta(minutes=5)


@pytest.mark.parametrize(
    "last_attempt",
    ["", "not-a-time", "2026-08-31 04:00:00Z", "2026-08-31T04:00:00"],
)
def test_malformed_or_naive_last_attempt_fails_closed_explicitly(last_attempt):
    schedule = calculate_security_lifecycle_automation_schedule(
        last_attempt=last_attempt,
        interval_minutes=5,
        now=NOW,
    )

    assert schedule.valid is False
    assert schedule.due is False
    assert schedule.last_attempt_at is None
    assert schedule.next_scheduled_at is None
    assert schedule.invalid_reason == "last_attempt_invalid"


def test_schedule_requires_an_aware_now():
    with pytest.raises(ValueError, match="now_must_be_timezone_aware"):
        calculate_security_lifecycle_automation_schedule(
            last_attempt=None,
            interval_minutes=5,
            now=datetime(2026, 8, 31, 4, 0),
        )
