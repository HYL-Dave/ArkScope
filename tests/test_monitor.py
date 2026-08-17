"""Tests for the monitor system (Phase E1 + E2 + E3 + Batch A)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.monitor.notifiers import (
    Alert,
    ConsoleNotifier,
    LogNotifier,
    NotificationRouter,
)
from src.monitor.watchers import (
    NewsVolumeWatcher,
    PriceWatcher,
    SectorWatcher,
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


class TestNewsVolumeWatcher:
    def _dal(self, recent_count: int, baseline_count: int):
        dal = MagicMock()
        dal.get_news_stats.side_effect = [
            [{"ticker": "NVDA", "article_count": recent_count}],
            [{"ticker": "NVDA", "article_count": baseline_count}],
        ]
        return dal

    def test_news_volume_spike_alert(self):
        watcher = NewsVolumeWatcher({
            "news_volume_alerts": {"enabled": True, "spike_multiplier": 3.0}
        })
        alerts = asyncio.run(watcher.check(self._dal(21, 30), ["NVDA"]))

        assert len(alerts) == 1
        assert alerts[0].alert_type == "news_volume"
        assert alerts[0].title == "News volume spike"
        assert alerts[0].ticker == "NVDA"
        assert alerts[0].data == {
            "recent_daily_avg": 3.0,
            "baseline_daily_avg": 1.0,
            "spike_multiple": 3.0,
        }

    def test_no_alert_under_volume_threshold(self):
        watcher = NewsVolumeWatcher({
            "news_volume_alerts": {"enabled": True, "spike_multiplier": 3.0}
        })
        assert asyncio.run(watcher.check(self._dal(14, 30), ["NVDA"])) == []

    def test_no_alert_when_disabled(self):
        dal = MagicMock()
        watcher = NewsVolumeWatcher({"news_volume_alerts": {"enabled": False}})
        assert asyncio.run(watcher.check(dal, ["NVDA"])) == []
        dal.get_news_stats.assert_not_called()


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
        dal.get_news_stats.side_effect = [
            [{"ticker": "NVDA", "article_count": 21}],
            [{"ticker": "NVDA", "article_count": 30}],
        ]
        config = {
            "alerts": {
                "price_alerts": {"enabled": False},
                "news_volume_alerts": {"enabled": True, "spike_multiplier": 3.0},
                "sector_alerts": {"enabled": False},
                "notification_channels": [{"type": "log", "enabled": True}],
            },
            "watchlists": {"core_holdings": {"tickers": ["NVDA"]}},
        }

        engine = MonitorEngine(dal=dal, config=config)
        alerts = asyncio.run(engine.scan_once(notify=False))

        assert len(alerts) >= 1
        assert alerts[0].alert_type == "news_volume"

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
            Alert(alert_type="news_volume", severity="warning", title="News volume spike", message="3x baseline", ticker="NVDA"),
        ]
        summary = engine.format_scan_summary(alerts)
        assert "2 alert(s)" in summary
        assert "Price Alerts" in summary
        assert "News Volume Alerts" in summary

    def test_scan_once_records_watcher_metrics(self):
        dal = MagicMock()
        config = {
            "alerts": {"notification_channels": []},
            "watchlists": {"core_holdings": {"tickers": ["NVDA"]}},
        }
        engine = MonitorEngine(dal=dal, config=config)

        class FakeWatcher:
            async def check(self, dal, tickers):
                del dal, tickers
                return [
                    Alert(
                        alert_type="price",
                        severity="warning",
                        title="Moved",
                        message="NVDA moved",
                        ticker="NVDA",
                    )
                ]

        class ExplodingWatcher:
            async def check(self, dal, tickers):
                del dal, tickers
                raise RuntimeError("boom")

        engine._watchers = [FakeWatcher(), ExplodingWatcher()]

        alerts = asyncio.run(engine.scan_once(notify=False))

        assert len(alerts) == 1
        assert engine.last_scan_metrics["tickers_scanned"] == 1
        assert engine.last_scan_metrics["alerts_before_dedup"] == 1
        assert engine.last_scan_metrics["alerts_after_dedup"] == 1
        assert engine.last_scan_metrics["watchers"][0]["watcher"] == "FakeWatcher"
        assert engine.last_scan_metrics["watchers"][0]["status"] == "ok"
        assert engine.last_scan_metrics["watchers"][1]["watcher"] == "ExplodingWatcher"
        assert engine.last_scan_metrics["watchers"][1]["status"] == "failed"


# ── Tool registration ─────────────────────────────────────────


class TestMonitorToolRegistration:
    def test_scan_alerts_registered(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        tool = registry.get("scan_alerts")
        assert tool is not None
        assert tool.category == "monitor"


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


# ===================================================================
# Batch A: Dedup tests
# ===================================================================


class TestAlertDeduplicator:
    """Test alert deduplication logic."""

    def test_first_alert_always_sent(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alert = Alert(
            alert_type="price", severity="warning",
            title="Price up 5.2%", message="NVDA moved",
            ticker="NVDA", data={"daily_change_pct": 5.2},
        )
        assert dedup.should_send(alert) is True

    def test_same_value_suppressed(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alert = Alert(
            alert_type="price", severity="warning",
            title="Price up 5.2%", message="NVDA moved",
            ticker="NVDA", data={"daily_change_pct": 5.2},
        )
        assert dedup.should_send(alert) is True
        assert dedup.should_send(alert) is False  # Same value → suppressed

    def test_value_change_triggers_resend(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alert1 = Alert(
            alert_type="price", severity="warning",
            title="Price up 8%", message="AMD moved",
            ticker="AMD", data={"daily_change_pct": 8.0},
        )
        alert2 = Alert(
            alert_type="price", severity="critical",
            title="Price up 10%", message="AMD moved",
            ticker="AMD", data={"daily_change_pct": 10.0},
        )
        assert dedup.should_send(alert1) is True
        assert dedup.should_send(alert2) is True  # 2.0 > 1.5 threshold

    def test_small_value_change_suppressed(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alert1 = Alert(
            alert_type="price", severity="warning",
            title="Price up 8%", message="AMD moved",
            ticker="AMD", data={"daily_change_pct": 8.0},
        )
        alert2 = Alert(
            alert_type="price", severity="warning",
            title="Price up 8.5%", message="AMD moved",
            ticker="AMD", data={"daily_change_pct": 8.5},
        )
        assert dedup.should_send(alert1) is True
        assert dedup.should_send(alert2) is False  # 0.5 < 1.5 threshold

    def test_cooldown_expired_resends(self):
        from src.monitor.dedup import AlertDeduplicator, _SentRecord

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alert = Alert(
            alert_type="price", severity="warning",
            title="Price up 5%", message="NVDA",
            ticker="NVDA", data={"daily_change_pct": 5.0},
        )
        # Manually inject an old record
        key = dedup._dedup_key(alert)
        dedup._sent[key] = _SentRecord(
            last_value=5.0,
            last_sent=datetime.now() - timedelta(minutes=31),
        )
        assert dedup.should_send(alert) is True  # Cooldown expired

    def test_different_tickers_independent(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alert_nvda = Alert(
            alert_type="price", severity="warning",
            title="Price up 5%", message="NVDA",
            ticker="NVDA", data={"daily_change_pct": 5.0},
        )
        alert_amd = Alert(
            alert_type="price", severity="warning",
            title="Price up 5%", message="AMD",
            ticker="AMD", data={"daily_change_pct": 5.0},
        )
        assert dedup.should_send(alert_nvda) is True
        assert dedup.should_send(alert_amd) is True  # Different ticker

    def test_different_types_independent(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        price_alert = Alert(
            alert_type="price", severity="warning",
            title="Price up 5%", message="NVDA",
            ticker="NVDA", data={"daily_change_pct": 5.0},
        )
        sentiment_alert = Alert(
            alert_type="sentiment", severity="warning",
            title="Sentiment improved", message="NVDA",
            ticker="NVDA", data={"delta": 1.0},
        )
        assert dedup.should_send(price_alert) is True
        assert dedup.should_send(sentiment_alert) is True  # Different type

    def test_filter_returns_unique_only(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alerts = [
            Alert(
                alert_type="price", severity="warning",
                title="Price up 5%", message="NVDA",
                ticker="NVDA", data={"daily_change_pct": 5.0},
            ),
            Alert(
                alert_type="price", severity="warning",
                title="Price up 5.1%", message="NVDA",
                ticker="NVDA", data={"daily_change_pct": 5.1},
            ),
            Alert(
                alert_type="price", severity="critical",
                title="Price up 15%", message="PYPL",
                ticker="PYPL", data={"daily_change_pct": 15.0},
            ),
        ]
        result = dedup.filter(alerts)
        assert len(result) == 2  # NVDA second suppressed, PYPL passes

    def test_sector_alert_dedup(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator(cooldown_minutes=30, value_threshold=1.5)
        alert1 = Alert(
            alert_type="sector", severity="warning",
            title="Sector sync: 10 stocks bullish", message="...",
            data={"avg_change_pct": 4.4, "count": 10},
        )
        alert2 = Alert(
            alert_type="sector", severity="warning",
            title="Sector sync: 10 stocks bullish", message="...",
            data={"avg_change_pct": 4.5, "count": 10},
        )
        assert dedup.should_send(alert1) is True
        assert dedup.should_send(alert2) is False  # 0.1 < 1.5

    def test_reset(self):
        from src.monitor.dedup import AlertDeduplicator

        dedup = AlertDeduplicator()
        alert = Alert(
            alert_type="price", severity="warning",
            title="Price up", message="...",
            ticker="NVDA", data={"daily_change_pct": 5.0},
        )
        dedup.should_send(alert)
        assert dedup.should_send(alert) is False
        dedup.reset()
        assert dedup.should_send(alert) is True


# ===================================================================
# Batch A: Scheduler thread safety tests
# ===================================================================

class TestSchedulerThreadSafety:
    """Test scheduler's _scan_and_notify pattern."""

    def test_scan_blocking_creates_new_loop(self):
        """_scan_blocking should work in a thread (new event loop)."""
        from src.monitor.scheduler import MonitorScheduler

        mock_engine = MagicMock()
        mock_engine.scan_once = AsyncMock(return_value=[])
        scheduler = MonitorScheduler(engine=mock_engine, interval_minutes=5)
        scheduler._tickers = ["NVDA"]

        # _scan_blocking runs asyncio.run() → should succeed
        result = scheduler._scan_blocking()
        assert result == []
        mock_engine.scan_once.assert_called_once_with(
            tickers=["NVDA"], notify=False,
        )

    def test_scan_and_notify_calls_engine_notify(self):
        """_scan_and_notify should dispatch alerts on main loop."""
        from src.monitor.scheduler import MonitorScheduler

        fake_alert = Alert(
            alert_type="price", severity="warning",
            title="Test", message="Test",
        )
        mock_engine = MagicMock()
        mock_engine.scan_once = AsyncMock(return_value=[fake_alert])
        mock_engine.notify = AsyncMock(return_value=1)

        scheduler = MonitorScheduler(engine=mock_engine, interval_minutes=5)
        scheduler._tickers = ["NVDA"]

        asyncio.run(scheduler._scan_and_notify())
        mock_engine.notify.assert_called_once_with([fake_alert])

    def test_scan_and_notify_no_alerts_skips_notify(self):
        """No alerts → don't call engine.notify()."""
        from src.monitor.scheduler import MonitorScheduler

        mock_engine = MagicMock()
        mock_engine.scan_once = AsyncMock(return_value=[])
        mock_engine.notify = AsyncMock()

        scheduler = MonitorScheduler(engine=mock_engine, interval_minutes=5)
        scheduler._tickers = ["NVDA"]

        asyncio.run(scheduler._scan_and_notify())
        mock_engine.notify.assert_not_called()
