"""
MonitorEngine — orchestrates watchers and notifications.

Reads alerts config and watchlists from user_profile.yaml,
runs all enabled watchers, and dispatches alerts via NotificationRouter.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from time import perf_counter
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
        self._last_scan_metrics: Dict[str, Any] = {
            "tickers_scanned": 0,
            "watchers": [],
            "alerts_before_dedup": 0,
            "alerts_after_dedup": 0,
            "notified": False,
            "notifications_sent": 0,
            "total_elapsed_seconds": 0.0,
        }

    @property
    def default_tickers(self) -> List[str]:
        return self._default_tickers

    @property
    def last_scan_metrics(self) -> Dict[str, Any]:
        """Metrics from the most recent scan_once() execution."""
        return self._last_scan_metrics

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
            self._last_scan_metrics = {
                "tickers_scanned": 0,
                "watchers": [],
                "alerts_before_dedup": 0,
                "alerts_after_dedup": 0,
                "notified": notify,
                "notifications_sent": 0,
                "total_elapsed_seconds": 0.0,
            }
            logger.warning("No tickers to scan")
            return []

        logger.info("Scanning %d tickers: %s", len(scan_tickers), ", ".join(scan_tickers))

        total_started = perf_counter()
        all_alerts: List[Alert] = []
        watcher_metrics: List[Dict[str, Any]] = []
        for watcher in self._watchers:
            watcher_name = type(watcher).__name__
            watcher_started = perf_counter()
            try:
                watcher_alerts = await watcher.check(self._dal, scan_tickers)
                elapsed = round(perf_counter() - watcher_started, 3)
                watcher_metrics.append({
                    "watcher": watcher_name,
                    "status": "ok",
                    "elapsed_seconds": elapsed,
                    "alert_count": len(watcher_alerts),
                })
                logger.info(
                    "%s completed in %.3fs (%d alert(s))",
                    watcher_name,
                    elapsed,
                    len(watcher_alerts),
                )
                if watcher_alerts:
                    logger.info(
                        "%s found %d alert(s)", watcher_name, len(watcher_alerts)
                    )
                    all_alerts.extend(watcher_alerts)
            except Exception as exc:
                elapsed = round(perf_counter() - watcher_started, 3)
                watcher_metrics.append({
                    "watcher": watcher_name,
                    "status": "failed",
                    "elapsed_seconds": elapsed,
                    "alert_count": 0,
                    "error": str(exc),
                })
                logger.exception("Watcher %s failed after %.3fs", watcher_name, elapsed)

        # Sort by severity (critical first)
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_alerts.sort(key=lambda a: severity_order.get(a.severity, 9))

        # Dedup: suppress alerts whose value hasn't changed significantly
        alerts_before_dedup = len(all_alerts)
        all_alerts = self._dedup.filter(all_alerts)

        notifications_sent = 0
        if notify and all_alerts:
            notifications_sent = await self._router.dispatch_many(all_alerts)

        total_elapsed = round(perf_counter() - total_started, 3)
        self._last_scan_metrics = {
            "tickers_scanned": len(scan_tickers),
            "watchers": watcher_metrics,
            "alerts_before_dedup": alerts_before_dedup,
            "alerts_after_dedup": len(all_alerts),
            "notified": notify,
            "notifications_sent": notifications_sent,
            "total_elapsed_seconds": total_elapsed,
        }

        logger.info(
            "Scan complete: %d alert(s) across %d tickers in %.3fs",
            len(all_alerts),
            len(scan_tickers),
            total_elapsed,
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
