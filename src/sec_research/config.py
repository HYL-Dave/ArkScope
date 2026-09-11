"""Typed SEC capture budget over the existing profile settings store."""

from __future__ import annotations

import re

from src.profile_state import ProfileStateStore


CAPTURE_BUDGET_KEY = "sec_research.capture_budget_bytes"
DEFAULT_CAPTURE_BUDGET_BYTES = 100 * 1024**3
MAX_CAPTURE_BUDGET_BYTES = 2**53 - 1
_CANONICAL_POSITIVE_INTEGER = re.compile(r"[1-9][0-9]*")


def _validate_capture_budget_bytes(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_CAPTURE_BUDGET_BYTES:
        raise ValueError(
            f"{CAPTURE_BUDGET_KEY} must be a positive integer no larger than "
            f"{MAX_CAPTURE_BUDGET_BYTES}"
        )
    return value


def get_capture_budget_bytes(store: ProfileStateStore) -> int:
    """Default only an absent key; never mask or repair persisted corruption."""
    snapshot = store.get_settings_snapshot((CAPTURE_BUDGET_KEY,))
    if CAPTURE_BUDGET_KEY not in snapshot:
        return DEFAULT_CAPTURE_BUDGET_BYTES

    value = snapshot[CAPTURE_BUDGET_KEY]
    if (
        not isinstance(value, str)
        or len(value) > len(str(MAX_CAPTURE_BUDGET_BYTES))
        or _CANONICAL_POSITIVE_INTEGER.fullmatch(value) is None
    ):
        raise ValueError(
            f"{CAPTURE_BUDGET_KEY} must contain canonical decimal integer text"
        )
    return _validate_capture_budget_bytes(int(value))


def set_capture_budget_bytes(store: ProfileStateStore, value: int) -> int:
    """Persist only the validated budget; no scheduling or filesystem effects."""
    validated = _validate_capture_budget_bytes(value)
    store.set_setting(CAPTURE_BUDGET_KEY, str(validated))
    return validated
