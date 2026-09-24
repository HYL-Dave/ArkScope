"""Acquisition intent is not a claim of provider-wide comment completeness."""

import json
from datetime import datetime, timedelta


def _require(condition):
    if not condition:
        raise ValueError("comment_scan_policy_invalid")


def validate_policy(value):
    if value is None:
        return None  # Old captures have no recorded scope; do not invent one.
    try:
        _require(type(value) is dict)
        _require(value["scope"] in {"recent", "history"})
        _require(value["coverage"] == "unverified")
        _require(value["date_basis"] == "displayed_date_browser_local_if_unzoned")
        reference = datetime.fromisoformat(value["reference_at"].replace("Z", "+00:00"))
        _require(reference.tzinfo is not None)
        if value["scope"] == "recent":
            _require(type(value["window_days"]) is int and value["window_days"] == 30)
            cutoff = datetime.fromisoformat(value["cutoff_at"].replace("Z", "+00:00"))
            _require(cutoff.tzinfo is not None and reference - cutoff == timedelta(days=30))
        else:
            _require(value["window_days"] is None and value["cutoff_at"] is None)
        counts = ("recent_count", "older_count", "unknown_date_count", "context_count", "deferred_historical_controls")
        _require(all(type(value[k]) is int and 0 <= value[k] <= 1_000_000 for k in counts))
        _require(value["context_count"] <= value["older_count"])
        return {k: value[k] for k in ("scope", "window_days", "reference_at", "cutoff_at", "date_basis", "coverage", *counts)}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("comment_scan_policy_invalid") from exc


def read_policy(raw):
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
        result = validate_policy(value)
        if result is not None:
            result["traversal_terminal"] = value.get("traversal_terminal") is True
            count = value.get("provider_count")
            result["provider_count"] = count if type(count) is int and count >= 0 else None
        return result
    except (ValueError, TypeError):
        return None
