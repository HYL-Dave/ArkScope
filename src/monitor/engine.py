"""
MonitorEngine — orchestrates watchers and notifications.

Reads alerts config and watchlists from user_profile.yaml,
runs all enabled watchers, and dispatches alerts via NotificationRouter.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

from .dedup import AlertDeduplicator
from .notifiers import Alert, NotificationRouter
from .watchers import (
    BaseWatcher,
    PriceWatcher,
    SectorWatcher,
    SentimentWatcher,
    SignalWatcher,
)

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path("config/user_profile.yaml")
_LOCAL_CONFIG_PATH = Path("config/user_profile.local.yaml")


def _load_config() -> dict:
    """Load user_profile.yaml (with optional local override)."""
    config = {}
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
    if _LOCAL_CONFIG_PATH.exists():
        with open(_LOCAL_CONFIG_PATH) as f:
            local = yaml.safe_load(f) or {}
        # shallow merge for alerts and watchlists
        for key in ("alerts", "watchlists", "notification_channels"):
            if key in local:
                config[key] = local[key]
    return config


def _extract_tickers(config: dict) -> List[str]:
    """Extract unique tickers from watchlists config."""
    watchlists = config.get("watchlists", {})
    tickers = set()

    # core_holdings
    for t in watchlists.get("core_holdings", {}).get("tickers", []):
        tickers.add(t.upper())

    # interested
    for t in watchlists.get("interested", {}).get("tickers", []):
        tickers.add(t.upper())

    # custom_themes
    for theme in watchlists.get("custom_themes", []):
        for t in theme.get("tickers", []):
            tickers.add(t.upper())

    return sorted(tickers)


class MonitorEngine:
    """Orchestrates watcher scans and alert dispatch."""

    def __init__(
        self,
        dal: DataAccessLayer,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._dal = dal
        self._config = config or _load_config()

        alerts_cfg = self._config.get("alerts", {})
        channels_cfg = alerts_cfg.get("notification_channels", [
            {"type": "console", "enabled": True},
            {"type": "log", "enabled": True},
        ])

        self._router = NotificationRouter(channels_cfg)
        self._watchers: List[BaseWatcher] = [
            PriceWatcher(alerts_cfg),
            SentimentWatcher(alerts_cfg),
            SignalWatcher(alerts_cfg),
            SectorWatcher(alerts_cfg),
        ]

        # Deduplicator: suppress repeated alerts within 30 min
        # unless the key value changed by ≥ 1.5 percentage points.
        self._dedup = AlertDeduplicator(
            cooldown_minutes=30,
            value_threshold=1.5,
        )

        # Default tickers from config
        self._default_tickers = _extract_tickers(self._config)

    @property
    def default_tickers(self) -> List[str]:
        return self._default_tickers

    async def scan_once(
        self,
        tickers: Optional[List[str]] = None,
        notify: bool = True,
    ) -> List[Alert]:
        """Run all watchers once and return collected alerts.

        Args:
            tickers: Tickers to scan (None = use watchlist from config).
            notify: Whether to dispatch alerts to notification channels.

        Returns:
            List of Alert objects from all watchers.
        """
        scan_tickers = tickers or self._default_tickers
        if not scan_tickers:
            logger.warning("No tickers to scan")
            return []

        logger.info("Scanning %d tickers: %s", len(scan_tickers), ", ".join(scan_tickers))

        all_alerts: List[Alert] = []
        for watcher in self._watchers:
            watcher_name = type(watcher).__name__
            try:
                watcher_alerts = await watcher.check(self._dal, scan_tickers)
                if watcher_alerts:
                    logger.info(
                        "%s found %d alert(s)", watcher_name, len(watcher_alerts)
                    )
                    all_alerts.extend(watcher_alerts)
            except Exception:
                logger.exception("Watcher %s failed", watcher_name)

        # Sort by severity (critical first)
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_alerts.sort(key=lambda a: severity_order.get(a.severity, 9))

        # Dedup: suppress alerts whose value hasn't changed significantly
        all_alerts = self._dedup.filter(all_alerts)

        if notify and all_alerts:
            await self._router.dispatch_many(all_alerts)

        logger.info(
            "Scan complete: %d alert(s) across %d tickers",
            len(all_alerts),
            len(scan_tickers),
        )
        return all_alerts

    async def notify(self, alerts: List[Alert]) -> int:
        """Dispatch alerts via notification channels.

        Separated from scan_once() so the scheduler can run the scan in a
        background thread (to avoid blocking Discord heartbeat) and then
        dispatch notifications on the main event loop where the Discord
        bot lives.
        """
        return await self._router.dispatch_many(alerts)

    async def run_loop(
        self,
        tickers: Optional[List[str]] = None,
        interval_sec: int = 300,
    ) -> None:
        """Continuously scan at fixed intervals (for service mode).

        Args:
            tickers: Tickers to scan (None = use watchlist from config).
            interval_sec: Seconds between scans.
        """
        logger.info("Starting monitor loop (interval=%ds)", interval_sec)
        while True:
            try:
                await self.scan_once(tickers=tickers, notify=True)
            except Exception:
                logger.exception("Monitor loop scan failed")
            await asyncio.sleep(interval_sec)

    def format_scan_summary(self, alerts: List[Alert]) -> str:
        """Format alerts as a human-readable summary string."""
        if not alerts:
            return "No alerts triggered."

        lines = [f"== Monitor Scan: {len(alerts)} alert(s) ==\n"]

        by_type: Dict[str, List[Alert]] = {}
        for a in alerts:
            by_type.setdefault(a.alert_type, []).append(a)

        type_labels = {
            "price": "Price Alerts",
            "sentiment": "Sentiment Alerts",
            "signal": "Signal Alerts",
            "sector": "Sector Alerts",
        }

        for alert_type, type_alerts in by_type.items():
            label = type_labels.get(alert_type, alert_type.title())
            lines.append(f"\n--- {label} ({len(type_alerts)}) ---")
            for a in type_alerts:
                lines.append(a.format_console())

        return "\n".join(lines)