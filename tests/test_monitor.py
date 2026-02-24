"""Tests for the monitor system (Phase E1 + E2)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.monitor.notifiers import (
    Alert,
    ConsoleNotifier,
    LogNotifier,
    NotificationRouter,
)
from src.monitor.watchers import (
    PriceWatcher,
    SectorWatcher,
    SentimentWatcher,
    SignalWatcher,
)
from src.monitor.engine import MonitorEngine, _extract_tickers


# ── Alert model ───────────────────────────────────────────────


class TestAlert:
    def test_default_timestamp(self):
        a = Alert(alert_type="price", severity="warning", title="Test", message="msg")
        assert isinstance(a.timestamp, datetime)

    def test_severity_icon(self):
        assert Alert(alert_type="p", severity="info", title="", message="").severity_icon == "[i]"
        assert Alert(alert_type="p", severity="warning", title="", message="").severity_icon == "[!]"
        assert Alert(alert_type="p", severity="critical", title="", message="").severity_icon == "[!!]"

    def test_format_console_with_ticker(self):
        a = Alert(
            alert_type="price", severity="warning", title="Up 6%",
            message="NVDA moved +6%", ticker="NVDA",
        )
        text = a.format_console()
        assert "[NVDA]" in text
        assert "Up 6%" in text

    def test_format_console_without_ticker(self):
        a = Alert(
            alert_type="sector", severity="info", title="Sync",
            message="3 stocks up",
        )
        text = a.format_console()
        assert "[" not in text.split("]")[0] or "Sync" in text


# ── Notifiers ─────────────────────────────────────────────────


class TestConsoleNotifier:
    def test_send_returns_true(self):
        notifier = ConsoleNotifier()
        alert = Alert(alert_type="price", severity="info", title="T", message="M")
        result = asyncio.run(notifier.send(alert))
        assert result is True


class TestLogNotifier:
    def test_send_returns_true(self):
        notifier = LogNotifier()
        alert = Alert(alert_type="price", severity="warning", title="T", message="M")
        result = asyncio.run(notifier.send(alert))
        assert result is True


class TestNotificationRouter:
    def test_loads_enabled_channels(self):
        channels = [
            {"type": "console", "enabled": True},
            {"type": "log", "enabled": True},
            {"type": "telegram", "enabled": False},
        ]
        router = NotificationRouter(channels)
        assert router.active_channels == 2

    def test_empty_channels(self):
        router = NotificationRouter([])
        assert router.active_channels == 0

    def test_dispatch_sends_to_all(self):
        channels = [
            {"type": "console", "enabled": True},
            {"type": "log", "enabled": True},
        ]
        router = NotificationRouter(channels)
        alert = Alert(alert_type="price", severity="info", title="T", message="M")
        sent = asyncio.run(router.dispatch(alert))
        assert sent == 2

    def test_dispatch_many(self):
        channels = [{"type": "log", "enabled": True}]
        router = NotificationRouter(channels)
        alerts = [
            Alert(alert_type="price", severity="info", title="T1", message="M1"),
            Alert(alert_type="price", severity="info", title="T2", message="M2"),
        ]
        total = asyncio.run(router.dispatch_many(alerts))
        assert total == 2


# ── PriceWatcher ──────────────────────────────────────────────


class TestPriceWatcher:
    def _make_dal(self, bars):
        """Create a mock DAL with price bars."""
        dal = MagicMock()
        result = MagicMock()
        result.bars = bars
        dal.get_prices.return_value = result
        return dal

    def _make_bar(self, close):
        bar = MagicMock()
        bar.close = close
        return bar

    def test_daily_alert_triggered(self):
        config = {"price_alerts": {"enabled": True, "daily_change_threshold_pct": 5, "weekly_change_threshold_pct": 10}}
        watcher = PriceWatcher(config)
        bars = [self._make_bar(100), self._make_bar(106)]  # +6%
        dal = self._make_dal(bars)

        alerts = asyncio.run(watcher.check(dal, ["NVDA"]))
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "price"
        assert "6.0%" in alerts[0].title

    def test_no_alert_under_threshold(self):
        config = {"price_alerts": {"enabled": True, "daily_change_threshold_pct": 5, "weekly_change_threshold_pct": 10}}
        watcher = PriceWatcher(config)
        bars = [self._make_bar(100), self._make_bar(102)]  # +2%
        dal = self._make_dal(bars)

        alerts = asyncio.run(watcher.check(dal, ["NVDA"]))
        assert len(alerts) == 0

    def test_disabled_watcher(self):
        config = {"price_alerts": {"enabled": False}}
        watcher = PriceWatcher(config)
        alerts = asyncio.run(watcher.check(MagicMock(), ["NVDA"]))
        assert len(alerts) == 0

    def test_weekly_alert(self):
        config = {"price_alerts": {"enabled": True, "daily_change_threshold_pct": 20, "weekly_change_threshold_pct": 10}}
        watcher = PriceWatcher(config)
        # 5 bars: start at 100, end at 115 (+15% weekly)
        bars = [self._make_bar(100), self._make_bar(103), self._make_bar(106),
                self._make_bar(110), self._make_bar(113), self._make_bar(115)]
        dal = self._make_dal(bars)

        alerts = asyncio.run(watcher.check(dal, ["NVDA"]))
        # Daily: 115 vs 113 = ~1.8% (under 20%), Weekly: 115 vs 100 = 15% (over 10%)
        weekly_alerts = [a for a in alerts if "Weekly" in a.title]
        assert len(weekly_alerts) == 1


# ── SentimentWatcher ──────────────────────────────────────────


class TestSentimentWatcher:
    def test_sentiment_shift_alert(self):
        config = {"sentiment_alerts": {"enabled": True, "sentiment_change_threshold": 1.0, "news_volume_spike_multiplier": 3}}
        watcher = SentimentWatcher(config)

        dal = MagicMock()
        # 7d stats: avg_sentiment 4.2, baseline 30d: avg_sentiment 2.8 → delta 1.4 >= 1.0
        dal.get_news_stats.side_effect = [
            [{"avg_sentiment": 4.2, "article_count": 10}],  # 7d
            [{"avg_sentiment": 2.8, "article_count": 30}],  # 30d
        ]

        alerts = asyncio.run(watcher.check(dal, ["NVDA"]))
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "sentiment"
        assert "improved" in alerts[0].title

    def test_no_alert_when_disabled(self):
        config = {"sentiment_alerts": {"enabled": False}}
        watcher = SentimentWatcher(config)
        alerts = asyncio.run(watcher.check(MagicMock(), ["NVDA"]))
        assert len(alerts) == 0


# ── SignalWatcher ─────────────────────────────────────────────


class TestSignalWatcher:
    def test_strong_buy_alert(self):
        watcher = SignalWatcher({})
        dal = MagicMock()

        mock_signal = MagicMock()
        mock_signal.action = "STRONG_BUY"
        mock_signal.confidence = 0.85
        mock_signal.risk_level = 2
        mock_signal.reasoning = "High momentum"

        with patch("src.tools.signal_tools.synthesize_signal", return_value=mock_signal):
            alerts = asyncio.run(watcher.check(dal, ["NVDA"]))

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert "STRONG_BUY" in alerts[0].title

    def test_high_risk_alert(self):
        watcher = SignalWatcher({})
        dal = MagicMock()

        mock_signal = MagicMock()
        mock_signal.action = "BUY"
        mock_signal.confidence = 0.6
        mock_signal.risk_level = 4
        mock_signal.reasoning = "Risky"

        with patch("src.tools.signal_tools.synthesize_signal", return_value=mock_signal):
            alerts = asyncio.run(watcher.check(dal, ["NVDA"]))

        assert len(alerts) == 1
        assert "risk" in alerts[0].title.lower()

    def test_hold_no_alert(self):
        watcher = SignalWatcher({})
        dal = MagicMock()

        mock_signal = MagicMock()
        mock_signal.action = "HOLD"
        mock_signal.confidence = 0.5
        mock_signal.risk_level = 2
        mock_signal.reasoning = "Neutral"

        with patch("src.tools.signal_tools.synthesize_signal", return_value=mock_signal):
            alerts = asyncio.run(watcher.check(dal, ["NVDA"]))

        assert len(alerts) == 0


# ── SectorWatcher ─────────────────────────────────────────────


class TestSectorWatcher:
    def _make_dal_with_changes(self, changes: dict):
        """Create a mock DAL that returns price bars per ticker."""
        dal = MagicMock()

        def get_prices(ticker, interval, days):
            pct = changes.get(ticker, 0)
            base = 100
            result = MagicMock()
            bar1, bar2 = MagicMock(), MagicMock()
            bar1.close = base
            bar2.close = base * (1 + pct / 100)
            result.bars = [bar1, bar2]
            return result

        dal.get_prices.side_effect = get_prices
        return dal

    def test_bullish_sync_alert(self):
        config = {"sector_alerts": {"enabled": True, "sector_sync_threshold": 3, "sector_avg_change_threshold_pct": 3}}
        watcher = SectorWatcher(config)

        # 4 stocks all up 4%+
        changes = {"NVDA": 5, "AMD": 4, "SMCI": 6, "DELL": 3.5}
        dal = self._make_dal_with_changes(changes)

        alerts = asyncio.run(watcher.check(dal, list(changes.keys())))
        assert len(alerts) >= 1
        assert "bullish" in alerts[0].title

    def test_no_alert_below_threshold(self):
        config = {"sector_alerts": {"enabled": True, "sector_sync_threshold": 3, "sector_avg_change_threshold_pct": 3}}
        watcher = SectorWatcher(config)

        # Only 2 stocks up (below sync_threshold of 3)
        changes = {"NVDA": 5, "AMD": 4}
        dal = self._make_dal_with_changes(changes)

        alerts = asyncio.run(watcher.check(dal, list(changes.keys())))
        assert len(alerts) == 0


# ── MonitorEngine ─────────────────────────────────────────────


class TestExtractTickers:
    def test_extracts_from_watchlists(self):
        config = {
            "watchlists": {
                "core_holdings": {"tickers": ["NVDA", "AMD"]},
                "interested": {"tickers": ["PLTR", "COIN"]},
                "custom_themes": [
                    {"tickers": ["NVDA", "IONQ"]},  # NVDA is duplicate
                ],
            }
        }
        tickers = _extract_tickers(config)
        assert "NVDA" in tickers
        assert "AMD" in tickers
        assert "PLTR" in tickers
        assert "IONQ" in tickers
        # No duplicates
        assert len(tickers) == len(set(tickers))

    def test_empty_config(self):
        assert _extract_tickers({}) == []


class TestMonitorEngine:
    def test_scan_once_returns_alerts(self):
        dal = MagicMock()
        config = {
            "alerts": {
                "price_alerts": {"enabled": False},
                "sentiment_alerts": {"enabled": False},
                "sector_alerts": {"enabled": False},
                "notification_channels": [{"type": "log", "enabled": True}],
            },
            "watchlists": {"core_holdings": {"tickers": ["NVDA"]}},
        }

        engine = MonitorEngine(dal=dal, config=config)

        # Only SignalWatcher is not disabled — mock it
        mock_signal = MagicMock()
        mock_signal.action = "STRONG_BUY"
        mock_signal.confidence = 0.9
        mock_signal.risk_level = 2
        mock_signal.reasoning = "Test"

        with patch("src.tools.signal_tools.synthesize_signal", return_value=mock_signal):
            alerts = asyncio.run(engine.scan_once(notify=False))

        assert len(alerts) >= 1

    def test_format_empty_summary(self):
        dal = MagicMock()
        config = {
            "alerts": {"notification_channels": []},
            "watchlists": {"core_holdings": {"tickers": []}},
        }
        engine = MonitorEngine(dal=dal, config=config)
        assert engine.format_scan_summary([]) == "No alerts triggered."

    def test_format_summary_with_alerts(self):
        dal = MagicMock()
        config = {
            "alerts": {"notification_channels": []},
            "watchlists": {},
        }
        engine = MonitorEngine(dal=dal, config=config)
        alerts = [
            Alert(alert_type="price", severity="warning", title="Up 6%", message="NVDA +6%", ticker="NVDA"),
            Alert(alert_type="signal", severity="critical", title="STRONG_BUY", message="High momentum", ticker="NVDA"),
        ]
        summary = engine.format_scan_summary(alerts)
        assert "2 alert(s)" in summary
        assert "Price Alerts" in summary
        assert "Signal Alerts" in summary


# ── Tool registration ─────────────────────────────────────────


class TestMonitorToolRegistration:
    def test_scan_alerts_registered(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        tool = registry.get("scan_alerts")
        assert tool is not None
        assert tool.category == "monitor"


# ── Discord Bot (Phase 2) ────────────────────────────────────


class TestAlertToEmbed:
    def test_embed_from_alert(self):
        from src.monitor.discord_bot import alert_to_embed
        alert = Alert(
            alert_type="price", severity="critical",
            title="Price up 8%", message="NVDA moved +8%",
            ticker="NVDA", data={"daily_change_pct": 8.0},
        )
        embed = alert_to_embed(alert)
        assert "Price up 8%" in embed.title
        assert embed.color.value == 0xe74c3c  # discord.Color.red()
        assert embed.author.name == "NVDA"

    def test_embed_info_severity(self):
        from src.monitor.discord_bot import alert_to_embed
        alert = Alert(
            alert_type="sector", severity="info",
            title="Sector sync", message="3 stocks up",
        )
        embed = alert_to_embed(alert)
        assert embed.color.value == 0x3498db  # discord.Color.blue()

    def test_embed_no_ticker(self):
        from src.monitor.discord_bot import alert_to_embed
        alert = Alert(
            alert_type="signal", severity="warning",
            title="Signal BUY", message="Test",
        )
        embed = alert_to_embed(alert)
        assert embed.author is None or embed.author.name is None


class TestDiscordNotifier:
    def test_discord_notifier_no_bot(self):
        from src.monitor.notifiers import DiscordNotifier
        notifier = DiscordNotifier()
        alert = Alert(alert_type="price", severity="info", title="T", message="M")
        # No bot set → should return False gracefully
        result = asyncio.run(notifier.send(alert))
        assert result is False

    def test_discord_notifier_with_bot(self):
        from src.monitor.notifiers import DiscordNotifier
        notifier = DiscordNotifier()
        mock_bot = MagicMock()
        mock_bot.send_alert = AsyncMock(return_value=True)
        notifier.set_bot(mock_bot)

        alert = Alert(alert_type="price", severity="info", title="T", message="M")
        result = asyncio.run(notifier.send(alert))
        assert result is True
        mock_bot.send_alert.assert_called_once_with(alert)


class TestNotificationRouterDiscord:
    def test_discord_channel_registered(self):
        channels = [
            {"type": "console", "enabled": True},
            {"type": "discord", "enabled": True},
        ]
        router = NotificationRouter(channels)
        assert router.active_channels == 2
        assert router._discord_notifier is not None

    def test_set_discord_bot(self):
        channels = [{"type": "discord", "enabled": True}]
        router = NotificationRouter(channels)
        mock_bot = MagicMock()
        router.set_discord_bot(mock_bot)
        assert router._discord_notifier._bot is mock_bot


# ── Scheduler (Phase 2) ──────────────────────────────────────


class TestMonitorScheduler:
    def test_scheduler_run_once(self):
        from src.monitor.scheduler import MonitorScheduler

        engine = MagicMock()
        engine.scan_once = AsyncMock(return_value=[])

        scheduler = MonitorScheduler(engine=engine, interval_minutes=1)
        asyncio.run(scheduler.run_once())
        engine.scan_once.assert_called_once()

    def test_scheduler_start_stop(self):
        from src.monitor.scheduler import MonitorScheduler

        engine = MagicMock()
        engine.scan_once = AsyncMock(return_value=[])

        scheduler = MonitorScheduler(engine=engine, interval_minutes=1)

        async def _test():
            await scheduler.start()
            assert scheduler.is_running
            # Let it do one scan
            await asyncio.sleep(0.1)
            await scheduler.stop()
            assert not scheduler.is_running

        asyncio.run(_test())