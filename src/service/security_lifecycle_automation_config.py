"""Strict profile controls and durable scheduling for lifecycle automation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


ENABLED_KEY = "security_lifecycle.automation.enabled"
INTERVAL_MINUTES_KEY = "security_lifecycle.automation.interval_minutes"
BATCH_LIMIT_KEY = "security_lifecycle.automation.batch_limit"
APPLY_PROFILE_TRANSITIONS_KEY = (
    "security_lifecycle.automation.apply_profile_transitions"
)
SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS = (
    ENABLED_KEY,
    INTERVAL_MINUTES_KEY,
    BATCH_LIMIT_KEY,
    APPLY_PROFILE_TRANSITIONS_KEY,
)

_CANONICAL_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_RFC3339_OR_LEGACY_OFFSET = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
    r"(?:Z|[+-][0-9]{2}:[0-9]{2}|[+-][0-9]{4})\Z"
)


@dataclass(frozen=True)
class SecurityLifecycleAutomationConfig:
    enabled: bool
    interval_minutes: int
    batch_limit: int
    apply_profile_transitions: bool

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled")
        if (
            type(self.interval_minutes) is not int
            or not 5 <= self.interval_minutes <= 10_080
        ):
            raise ValueError("interval_minutes")
        if type(self.batch_limit) is not int or self.batch_limit not in {1, 2}:
            raise ValueError("batch_limit")
        if type(self.apply_profile_transitions) is not bool:
            raise ValueError("apply_profile_transitions")


DEFAULT_SECURITY_LIFECYCLE_AUTOMATION_CONFIG = SecurityLifecycleAutomationConfig(
    enabled=True,
    interval_minutes=5,
    batch_limit=2,
    apply_profile_transitions=False,
)


@dataclass(frozen=True)
class SecurityLifecycleAutomationConfigState:
    config: SecurityLifecycleAutomationConfig | None
    invalid_keys: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.config is not None and not self.invalid_keys

    @property
    def effective_background_enabled(self) -> bool:
        return bool(self.valid and self.config and self.config.enabled)

    @property
    def effective_apply_profile_transitions(self) -> bool:
        return bool(
            self.valid and self.config and self.config.apply_profile_transitions
        )


@dataclass(frozen=True)
class SecurityLifecycleAutomationSchedule:
    due: bool
    last_attempt_at: datetime | None
    next_scheduled_at: datetime | None
    invalid_reason: str | None = None

    @property
    def valid(self) -> bool:
        return self.invalid_reason is None


def _boolean(value: object) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _bounded_integer(value: object, *, minimum: int, maximum: int) -> int | None:
    if not isinstance(value, str) or _CANONICAL_INTEGER.fullmatch(value) is None:
        return None
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        return None
    return parsed


def parse_security_lifecycle_automation_config(
    stored: Mapping[str, str | None],
) -> SecurityLifecycleAutomationConfigState:
    """Parse one setting snapshot without defaulting malformed present values."""

    defaults = DEFAULT_SECURITY_LIFECYCLE_AUTOMATION_CONFIG
    enabled = defaults.enabled
    interval_minutes = defaults.interval_minutes
    batch_limit = defaults.batch_limit
    apply_profile_transitions = defaults.apply_profile_transitions
    invalid_keys: list[str] = []

    if ENABLED_KEY in stored:
        parsed_enabled = _boolean(stored[ENABLED_KEY])
        if parsed_enabled is None:
            invalid_keys.append(ENABLED_KEY)
        else:
            enabled = parsed_enabled

    if INTERVAL_MINUTES_KEY in stored:
        parsed_interval = _bounded_integer(
            stored[INTERVAL_MINUTES_KEY], minimum=5, maximum=10_080
        )
        if parsed_interval is None:
            invalid_keys.append(INTERVAL_MINUTES_KEY)
        else:
            interval_minutes = parsed_interval

    if BATCH_LIMIT_KEY in stored:
        parsed_batch = _bounded_integer(
            stored[BATCH_LIMIT_KEY], minimum=1, maximum=2
        )
        if parsed_batch is None:
            invalid_keys.append(BATCH_LIMIT_KEY)
        else:
            batch_limit = parsed_batch

    if APPLY_PROFILE_TRANSITIONS_KEY in stored:
        parsed_apply = _boolean(stored[APPLY_PROFILE_TRANSITIONS_KEY])
        if parsed_apply is None:
            invalid_keys.append(APPLY_PROFILE_TRANSITIONS_KEY)
        else:
            apply_profile_transitions = parsed_apply

    if invalid_keys:
        return SecurityLifecycleAutomationConfigState(
            config=None,
            invalid_keys=tuple(sorted(invalid_keys)),
        )
    return SecurityLifecycleAutomationConfigState(
        config=SecurityLifecycleAutomationConfig(
            enabled=enabled,
            interval_minutes=interval_minutes,
            batch_limit=batch_limit,
            apply_profile_transitions=apply_profile_transitions,
        )
    )


def serialize_security_lifecycle_automation_config(
    config: SecurityLifecycleAutomationConfig,
) -> dict[str, str]:
    return {
        ENABLED_KEY: "true" if config.enabled else "false",
        INTERVAL_MINUTES_KEY: str(config.interval_minutes),
        BATCH_LIMIT_KEY: str(config.batch_limit),
        APPLY_PROFILE_TRANSITIONS_KEY: (
            "true" if config.apply_profile_transitions else "false"
        ),
    }


def _parse_last_attempt(value: object) -> datetime:
    if (
        not isinstance(value, str)
        or _RFC3339_OR_LEGACY_OFFSET.fullmatch(value) is None
    ):
        raise ValueError("last_attempt_invalid")
    if value.endswith("Z"):
        normalized = value[:-1] + "+00:00"
    elif value[-5] in "+-" and value[-3] != ":":
        normalized = value[:-2] + ":" + value[-2:]
    else:
        normalized = value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("last_attempt_invalid")
    return parsed.astimezone(timezone.utc)


def calculate_security_lifecycle_automation_schedule(
    *,
    last_attempt: str | None,
    interval_minutes: int,
    now: datetime,
) -> SecurityLifecycleAutomationSchedule:
    """Project due/next from durable state; malformed state never becomes due."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_must_be_timezone_aware")
    if (
        isinstance(interval_minutes, bool)
        or not isinstance(interval_minutes, int)
        or not 5 <= interval_minutes <= 10_080
    ):
        raise ValueError("interval_minutes_invalid")

    current = now.astimezone(timezone.utc)
    if last_attempt is None:
        return SecurityLifecycleAutomationSchedule(
            due=True,
            last_attempt_at=None,
            next_scheduled_at=current,
        )
    try:
        attempted_at = _parse_last_attempt(last_attempt)
    except (TypeError, ValueError):
        return SecurityLifecycleAutomationSchedule(
            due=False,
            last_attempt_at=None,
            next_scheduled_at=None,
            invalid_reason="last_attempt_invalid",
        )

    next_scheduled_at = attempted_at + timedelta(minutes=interval_minutes)
    return SecurityLifecycleAutomationSchedule(
        due=current >= next_scheduled_at,
        last_attempt_at=attempted_at,
        next_scheduled_at=next_scheduled_at,
    )
