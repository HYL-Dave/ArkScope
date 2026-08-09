"""
Watcher implementations for the monitor system.

Each watcher checks one aspect (price, raw news volume, sector)
against configured thresholds from user_profile.yaml alerts section.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

from .notifiers import Alert

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer

logger = logging.getLogger(__name__)


class BaseWatcher(ABC):
    """Abstract watcher — checks tickers and returns Alert list."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    async def check(self, dal: DataAccessLayer, tickers: List[str]) -> List[Alert]:
        """Run the check against given tickers. Returns alerts for threshold violations."""


class PriceWatcher(BaseWatcher):
    """Detect price moves exceeding daily/weekly thresholds.

    Config keys (alerts.price_alerts):
        daily_change_threshold_pct: 5
        weekly_change_threshold_pct: 10
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        pa = config.get("price_alerts", {})
        self.enabled = pa.get("enabled", True)
        self.daily_threshold = pa.get("daily_change_threshold_pct", 5)
        self.weekly_threshold = pa.get("weekly_change_threshold_pct", 10)

    async def check(self, dal: DataAccessLayer, tickers: List[str]) -> List[Alert]:
        if not self.enabled:
            return []

        alerts: List[Alert] = []
        for ticker in tickers:
            try:
                result = dal.get_prices(ticker=ticker, interval="daily", days=7)
                if not result.bars or len(result.bars) < 2:
                    continue

                bars = result.bars
                latest = bars[-1].close
                prev_day = bars[-2].close

                # Daily change
                if prev_day > 0:
                    daily_pct = ((latest - prev_day) / prev_day) * 100
                    if abs(daily_pct) >= self.daily_threshold:
                        direction = "up" if daily_pct > 0 else "down"
                        severity = "critical" if abs(daily_pct) >= self.daily_threshold * 2 else "warning"
                        alerts.append(Alert(
                            alert_type="price",
                            severity=severity,
                            title=f"Price {direction} {abs(daily_pct):.1f}%",
                            message=f"{ticker} moved {daily_pct:+.1f}% today (${prev_day:.2f} → ${latest:.2f})",
                            ticker=ticker,
                            data={"daily_change_pct": round(daily_pct, 2), "close": latest},
                        ))

                # Weekly change (first bar vs last)
                if len(bars) >= 5:
                    week_start = bars[0].close
                    if week_start > 0:
                        weekly_pct = ((latest - week_start) / week_start) * 100
                        if abs(weekly_pct) >= self.weekly_threshold:
                            direction = "up" if weekly_pct > 0 else "down"
                            alerts.append(Alert(
                                alert_type="price",
                                severity="critical" if abs(weekly_pct) >= self.weekly_threshold * 2 else "warning",
                                title=f"Weekly {direction} {abs(weekly_pct):.1f}%",
                                message=f"{ticker} moved {weekly_pct:+.1f}% this week (${week_start:.2f} → ${latest:.2f})",
                                ticker=ticker,
                                data={"weekly_change_pct": round(weekly_pct, 2), "close": latest},
                            ))

            except Exception as e:
                logger.debug("PriceWatcher failed for %s: %s", ticker, e)

        return alerts


class NewsVolumeWatcher(BaseWatcher):
    """Detect raw-news volume spikes against a 30-day baseline."""

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        settings = config.get("news_volume_alerts", {})
        self.enabled = settings.get("enabled", True)
        self.spike_multiplier = float(settings.get("spike_multiplier", 3.0))

    async def check(self, dal: DataAccessLayer, tickers: List[str]) -> List[Alert]:
        if not self.enabled:
            return []

        alerts: List[Alert] = []
        for ticker in tickers:
            try:
                recent_rows = dal.get_news_stats(ticker=ticker, days=7)
                baseline_rows = dal.get_news_stats(ticker=ticker, days=30)
                recent = recent_rows[0] if recent_rows else {}
                baseline = baseline_rows[0] if baseline_rows else {}
                recent_daily = float(recent.get("article_count", 0)) / 7
                baseline_daily = float(baseline.get("article_count", 0)) / 30
                if baseline_daily <= 0:
                    continue
                multiple = recent_daily / baseline_daily
                if multiple < self.spike_multiplier:
                    continue
                alerts.append(Alert(
                    alert_type="news_volume",
                    severity="warning",
                    title="News volume spike",
                    message=(
                        f"{ticker} has {recent_daily:.1f} articles/day (7d) vs "
                        f"{baseline_daily:.1f}/day baseline ({multiple:.1f}x)"
                    ),
                    ticker=ticker,
                    data={
                        "recent_daily_avg": round(recent_daily, 1),
                        "baseline_daily_avg": round(baseline_daily, 1),
                        "spike_multiple": round(multiple, 1),
                    },
                ))
            except Exception as exc:
                logger.debug("NewsVolumeWatcher failed for %s: %s", ticker, exc)
        return alerts


class SectorWatcher(BaseWatcher):
    """Detect sector-wide synchronized moves.

    Config keys (alerts.sector_alerts):
        sector_sync_threshold: 3
        sector_avg_change_threshold_pct: 3
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        sa = config.get("sector_alerts", {})
        self.enabled = sa.get("enabled", True)
        self.sync_threshold = sa.get("sector_sync_threshold", 3)
        self.avg_change_threshold = sa.get("sector_avg_change_threshold_pct", 3)

    async def check(self, dal: DataAccessLayer, tickers: List[str]) -> List[Alert]:
        if not self.enabled:
            return []

        # Collect daily changes for all tickers
        changes: Dict[str, float] = {}
        for ticker in tickers:
            try:
                result = dal.get_prices(ticker=ticker, interval="daily", days=3)
                if result.bars and len(result.bars) >= 2:
                    prev = result.bars[-2].close
                    curr = result.bars[-1].close
                    if prev > 0:
                        changes[ticker] = ((curr - prev) / prev) * 100
            except Exception:
                continue

        if len(changes) < 2:
            return []

        alerts: List[Alert] = []

        # Check for synchronized moves (N tickers moving same direction)
        up_tickers = [t for t, c in changes.items() if c > 0]
        down_tickers = [t for t, c in changes.items() if c < 0]

        for direction, group in [("bullish", up_tickers), ("bearish", down_tickers)]:
            if len(group) >= self.sync_threshold:
                avg_change = sum(changes[t] for t in group) / len(group)
                if abs(avg_change) >= self.avg_change_threshold:
                    tickers_str = ", ".join(sorted(group))
                    alerts.append(Alert(
                        alert_type="sector",
                        severity="warning",
                        title=f"Sector sync: {len(group)} stocks {direction}",
                        message=(
                            f"{len(group)} stocks moving {direction} (avg {avg_change:+.1f}%): {tickers_str}"
                        ),
                        data={
                            "direction": direction,
                            "count": len(group),
                            "avg_change_pct": round(avg_change, 2),
                            "tickers": group,
                        },
                    ))

        return alerts
