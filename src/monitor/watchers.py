"""
Watcher implementations for the monitor system.

Each watcher checks one aspect (price, sentiment, signal, sector)
against configured thresholds from user_profile.yaml alerts section.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .notifiers import Alert

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer

logger = logging.getLogger(__name__)


def _preload_signal_news_df(
    dal: "DataAccessLayer",
    *,
    days: int,
) -> Optional[Any]:
    """Prepare shared signal news context once per scan.

    Signal synthesis needs a full-news DataFrame for sector/anomaly context.
    Building that dataset for every ticker is extremely expensive during
    monitor scans, so watchers preload it once and pass it through.
    """
    from src.tools.signal_tools import _prepare_news_df_for_signals

    try:
        return _prepare_news_df_for_signals(dal, ticker=None, days=days)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.debug("SignalWatcher preload failed, falling back to per-ticker load: %s", exc)
        return None


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


class SentimentWatcher(BaseWatcher):
    """Detect sentiment score spikes or news volume surges.

    Config keys (alerts.sentiment_alerts):
        sentiment_change_threshold: 1.5
        news_volume_spike_multiplier: 3
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        sa = config.get("sentiment_alerts", {})
        self.enabled = sa.get("enabled", True)
        self.sentiment_threshold = sa.get("sentiment_change_threshold", 1.5)
        self.volume_multiplier = sa.get("news_volume_spike_multiplier", 3)

    async def check(self, dal: DataAccessLayer, tickers: List[str]) -> List[Alert]:
        if not self.enabled:
            return []

        alerts: List[Alert] = []
        for ticker in tickers:
            try:
                # Compare recent (7d) vs baseline (30d) stats
                recent_stats = dal.get_news_stats(ticker=ticker, days=7)
                baseline_stats = dal.get_news_stats(ticker=ticker, days=30)

                recent = recent_stats[0] if recent_stats else {}
                baseline = baseline_stats[0] if baseline_stats else {}

                if not recent or not baseline:
                    continue

                # Sentiment shift: compare 7d avg vs 30d avg
                recent_sent = recent.get("avg_sentiment")
                baseline_sent = baseline.get("avg_sentiment")
                if recent_sent is not None and baseline_sent is not None:
                    delta = abs(recent_sent - baseline_sent)
                    if delta >= self.sentiment_threshold:
                        direction = "improved" if recent_sent > baseline_sent else "deteriorated"
                        alerts.append(Alert(
                            alert_type="sentiment",
                            severity="warning",
                            title=f"Sentiment {direction}",
                            message=(
                                f"{ticker} sentiment shifted by {delta:.1f} "
                                f"(30d avg {baseline_sent:.1f} → 7d avg {recent_sent:.1f})"
                            ),
                            ticker=ticker,
                            data={
                                "recent_avg": round(recent_sent, 2),
                                "baseline_avg": round(baseline_sent, 2),
                                "delta": round(delta, 2),
                            },
                        ))

                # News volume spike: recent 7d count vs 30d daily average
                recent_count = recent.get("article_count", 0)
                baseline_count = baseline.get("article_count", 0)
                baseline_daily_avg = baseline_count / 30 if baseline_count > 0 else 0
                recent_daily_avg = recent_count / 7 if recent_count > 0 else 0

                if baseline_daily_avg > 0 and recent_daily_avg >= baseline_daily_avg * self.volume_multiplier:
                    alerts.append(Alert(
                        alert_type="sentiment",
                        severity="warning",
                        title="News volume spike",
                        message=(
                            f"{ticker} has {recent_daily_avg:.1f} articles/day (7d) "
                            f"vs {baseline_daily_avg:.1f}/day baseline "
                            f"({recent_daily_avg / baseline_daily_avg:.1f}x)"
                        ),
                        ticker=ticker,
                        data={
                            "recent_daily_avg": round(recent_daily_avg, 1),
                            "baseline_daily_avg": round(baseline_daily_avg, 1),
                        },
                    ))

            except Exception as e:
                logger.debug("SentimentWatcher failed for %s: %s", ticker, e)

        return alerts


class SignalWatcher(BaseWatcher):
    """Run signal synthesis and alert on strong buy/sell signals.

    Triggers alert when SignalSynthesizer produces STRONG_BUY or STRONG_SELL,
    or when risk_level >= 4.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.days = 14

    async def check(self, dal: DataAccessLayer, tickers: List[str]) -> List[Alert]:
        from src.tools.signal_tools import synthesize_signal

        alerts: List[Alert] = []
        shared_news_df = _preload_signal_news_df(dal, days=self.days)
        for ticker in tickers:
            try:
                result = synthesize_signal(
                    dal,
                    ticker=ticker,
                    days=self.days,
                    news_df=shared_news_df,
                )
                if not result:
                    continue

                # result is a TradingSignal Pydantic model (src/tools/schemas.py)
                action_str = str(result.action)
                confidence = result.confidence
                risk_level = result.risk_level
                reasoning = result.reasoning

                if action_str in ("STRONG_BUY", "STRONG_SELL"):
                    severity = "critical"
                    alerts.append(Alert(
                        alert_type="signal",
                        severity=severity,
                        title=f"Signal: {action_str}",
                        message=f"{ticker} — {action_str} (confidence {confidence:.0%}, risk {risk_level}/5)\n  {reasoning}",
                        ticker=ticker,
                        data={
                            "action": action_str,
                            "confidence": round(confidence, 3),
                            "risk_level": risk_level,
                        },
                    ))
                elif risk_level >= 4:
                    alerts.append(Alert(
                        alert_type="signal",
                        severity="warning",
                        title=f"High risk level ({risk_level}/5)",
                        message=f"{ticker} — {action_str} (confidence {confidence:.0%})\n  {reasoning}",
                        ticker=ticker,
                        data={
                            "action": action_str,
                            "confidence": round(confidence, 3),
                            "risk_level": risk_level,
                        },
                    ))

            except Exception as e:
                logger.debug("SignalWatcher failed for %s: %s", ticker, e)

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
