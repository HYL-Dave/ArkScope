"""
Monitor system — automated watchlist scanning with configurable alerts.

Provides:
- Alert/Notifier abstractions for multi-channel notifications
- Watchers for price, sentiment, signal, and sector monitoring
- MonitorEngine to orchestrate scans and dispatch alerts
"""

from .notifiers import Alert, ConsoleNotifier, DiscordNotifier, LogNotifier, NotificationRouter, Notifier
from .watchers import (
    BaseWatcher,
    PriceWatcher,
    SectorWatcher,
    SentimentWatcher,
    SignalWatcher,
)
from .engine import MonitorEngine

__all__ = [
    "Alert",
    "ConsoleNotifier",
    "DiscordNotifier",
    "LogNotifier",
    "NotificationRouter",
    "Notifier",
    "BaseWatcher",
    "PriceWatcher",
    "SectorWatcher",
    "SentimentWatcher",
    "SignalWatcher",
    "MonitorEngine",
]