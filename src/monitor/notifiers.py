"""
Alert model and notification channel implementations.

Reads notification_channels from user_profile.yaml (alerts section)
and dispatches Alert objects to all enabled channels.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """A single monitoring alert."""

    alert_type: str  # "price" | "sentiment" | "signal" | "sector"
    severity: str  # "info" | "warning" | "critical"
    title: str
    message: str
    ticker: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def severity_icon(self) -> str:
        return {"info": "[i]", "warning": "[!]", "critical": "[!!]"}.get(
            self.severity, "[?]"
        )

    def format_console(self) -> str:
        """Format for console output with severity indicator."""
        ticker_str = f" [{self.ticker}]" if self.ticker else ""
        return f"{self.severity_icon}{ticker_str} {self.title}\n  {self.message}"


class Notifier(ABC):
    """Abstract base for notification channels."""

    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """Send an alert. Returns True on success."""


class ConsoleNotifier(Notifier):
    """Print alerts to console with formatting."""

    # ANSI colors for severity
    _COLORS = {
        "info": "\033[36m",  # cyan
        "warning": "\033[33m",  # yellow
        "critical": "\033[31m",  # red
    }
    _RESET = "\033[0m"

    async def send(self, alert: Alert) -> bool:
        color = self._COLORS.get(alert.severity, "")
        print(f"{color}{alert.format_console()}{self._RESET}")
        return True


class LogNotifier(Notifier):
    """Write alerts to the logging system."""

    _LOG_LEVELS = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "critical": logging.ERROR,
    }

    async def send(self, alert: Alert) -> bool:
        level = self._LOG_LEVELS.get(alert.severity, logging.INFO)
        logger.log(level, "ALERT: %s — %s", alert.title, alert.message)
        return True


class NotificationRouter:
    """Load notification channels from config and dispatch alerts."""

    def __init__(self, channels_config: List[Dict[str, Any]]) -> None:
        self._notifiers: List[Notifier] = []

        for ch in channels_config:
            if not ch.get("enabled", False):
                continue
            ch_type = ch.get("type", "")
            if ch_type == "console":
                self._notifiers.append(ConsoleNotifier())
            elif ch_type == "log":
                self._notifiers.append(LogNotifier())
            else:
                logger.debug("Skipping unimplemented channel type: %s", ch_type)

    @property
    def active_channels(self) -> int:
        return len(self._notifiers)

    async def dispatch(self, alert: Alert) -> int:
        """Send alert to all enabled channels. Returns number of successful sends."""
        sent = 0
        for notifier in self._notifiers:
            try:
                if await notifier.send(alert):
                    sent += 1
            except Exception:
                logger.exception("Notifier %s failed", type(notifier).__name__)
        return sent

    async def dispatch_many(self, alerts: List[Alert]) -> int:
        """Dispatch multiple alerts. Returns total successful sends."""
        total = 0
        for alert in alerts:
            total += await self.dispatch(alert)
        return total
