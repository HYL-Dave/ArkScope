"""
Monitor system — automated watchlist scanning with configurable alerts.

Provides:
- Alert/Notifier abstractions for multi-channel notifications
- Watchers for price, raw news volume, and sector monitoring
- MonitorEngine to orchestrate scans and dispatch alerts
"""

from .notifiers import Alert, ConsoleNotifier, LogNotifier, NotificationRouter, Notifier
from .watchers import (
    BaseWatcher,
    NewsVolumeWatcher,
    PriceWatcher,
    SectorWatcher,
)
from .engine import MonitorEngine

__all__ = [
    "Alert",
    "ConsoleNotifier",
    "LogNotifier",
    "NotificationRouter",
    "Notifier",
    "BaseWatcher",
    "NewsVolumeWatcher",
    "PriceWatcher",
    "SectorWatcher",
    "MonitorEngine",
]
