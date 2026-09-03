"""Pure normalization for subscription-plan facts."""

from __future__ import annotations

import re
from typing import Any


_PLAN_TYPE_RE = re.compile(r"[a-z][a-z0-9._-]{0,79}")


def normalize_subscription_plan(value: Any) -> str | None:
    """Return a bounded provider plan identifier, or ``None`` when unknown."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if _PLAN_TYPE_RE.fullmatch(normalized) is None:
        return None
    return normalized
