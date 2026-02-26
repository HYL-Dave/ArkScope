"""
Alert deduplication — suppress repeated alerts whose values haven't changed.

Design:
    Same (alert_type, ticker) within the cooldown window is considered a
    duplicate **unless** the key numeric value changed by more than
    *value_threshold*.  This prevents spamming "PYPL +15.5%" every 5 min
    while still allowing "PYPL +15.5% → PYPL +17.2%".

    In-memory only — state resets on service restart (acceptable).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .notifiers import Alert

logger = logging.getLogger(__name__)

# ── Value extraction mapping ─────────────────────────────────────────────

# Keys tried in order for each alert_type.  First match wins.
_VALUE_KEYS: Dict[str, List[str]] = {
    "price": ["daily_change_pct", "weekly_change_pct"],
    "sentiment": ["delta"],
    "signal": ["confidence"],
    "sector": ["avg_change_pct"],
}


def _extract_value(alert: Alert) -> Optional[float]:
    """Extract the key numeric value from an alert for change-detection."""
    keys = _VALUE_KEYS.get(alert.alert_type, [])
    for key in keys:
        val = alert.data.get(key)
        if val is not None:
            try:
                v = float(val)
                # signal confidence is 0-1, scale to percentage for threshold
                if alert.alert_type == "signal" and key == "confidence":
                    v *= 100.0
                return v
            except (TypeError, ValueError):
                continue
    return None


# ── Internal record ──────────────────────────────────────────────────────

@dataclass
class _SentRecord:
    last_value: Optional[float]
    last_sent: datetime


# ── Deduplicator ─────────────────────────────────────────────────────────

class AlertDeduplicator:
    """In-memory alert dedup with value-change threshold.

    Parameters:
        cooldown_minutes:  Minimum time before an identical alert is re-sent
                           even if the value hasn't changed.  Default 30 min.
        value_threshold:   Minimum absolute change in the key value to treat
                           as a new alert within the cooldown window.
                           Default 1.5 (percentage points for price/sector,
                           scale-adjusted for signal confidence).
    """

    def __init__(
        self,
        cooldown_minutes: int = 30,
        value_threshold: float = 1.5,
    ) -> None:
        self._sent: Dict[str, _SentRecord] = {}
        self._cooldown = timedelta(minutes=cooldown_minutes)
        self._value_threshold = value_threshold

    # ── Public API ────────────────────────────────────────────────────

    def should_send(self, alert: Alert) -> bool:
        """Return True if the alert should be dispatched."""
        key = self._dedup_key(alert)
        value = _extract_value(alert)
        now = datetime.now()

        record = self._sent.get(key)
        if record is None:
            # First time seeing this (type, ticker) — always send.
            self._sent[key] = _SentRecord(value, now)
            return True

        # Cooldown expired → send regardless of value.
        if (now - record.last_sent) >= self._cooldown:
            self._sent[key] = _SentRecord(value, now)
            return True

        # Value changed significantly → send.
        if self._value_changed(record.last_value, value):
            self._sent[key] = _SentRecord(value, now)
            return True

        # Duplicate — suppress.
        logger.debug("Dedup suppressed: %s (key=%s)", alert.title, key)
        return False

    def filter(self, alerts: List[Alert]) -> List[Alert]:
        """Return only alerts that pass the dedup check."""
        result = [a for a in alerts if self.should_send(a)]
        suppressed = len(alerts) - len(result)
        if suppressed:
            logger.info("Dedup: suppressed %d duplicate alert(s)", suppressed)
        return result

    def reset(self) -> None:
        """Clear all dedup state (useful for testing)."""
        self._sent.clear()

    # ── Internals ─────────────────────────────────────────────────────

    @staticmethod
    def _dedup_key(alert: Alert) -> str:
        """Group by (alert_type, ticker)."""
        return f"{alert.alert_type}|{alert.ticker or '_'}"

    def _value_changed(
        self, old: Optional[float], new: Optional[float],
    ) -> bool:
        """True if the numeric value changed more than the threshold."""
        if old is None or new is None:
            # Can't compare — treat as unchanged (suppress).
            return False
        return abs(new - old) >= self._value_threshold
