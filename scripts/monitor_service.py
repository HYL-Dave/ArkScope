#!/usr/bin/env python3
"""
Monitor service — standalone entry point for scheduled monitoring.

Usage:
    python scripts/monitor_service.py                    # console + log only
    python scripts/monitor_service.py --discord           # + Discord notifications
    python scripts/monitor_service.py --interval 10       # scan every 10 minutes
    python scripts/monitor_service.py --tickers NVDA,TSLA # specific tickers only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(Path("config/.env"))

from src.monitor.engine import MonitorEngine
from src.monitor.scheduler import MonitorScheduler

logger = logging.getLogger("monitor_service")


async def run_service(
    interval_minutes: int = 5,
    discord: bool = False,
    tickers: list[str] | None = None,
) -> None:
    """Run the monitor service with optional Discord integration."""
    from src.tools.data_access import DataAccessLayer

    dal = DataAccessLayer(db_dsn="auto")
    engine = MonitorEngine(dal=dal)

    # Override tickers if specified
    scan_tickers = tickers or engine.default_tickers
    logger.info("Monitoring %d tickers: %s", len(scan_tickers), ", ".join(scan_tickers))

    bot = None
    if discord:
        from src.monitor.discord_bot import (
            MindfulDiscordBot, _load_channel_id,
            _load_alert_channel_id, _load_agent_channel_id,
        )

        bot = MindfulDiscordBot(
            channel_id=_load_channel_id(),
            alert_channel_id=_load_alert_channel_id(),
            agent_channel_id=_load_agent_channel_id(),
            dal=dal,
        )

        # Inject bot into notification router
        engine._router.set_discord_bot(bot)
        logger.info("Discord notifications enabled (with slash commands + free chat)")

    scheduler = MonitorScheduler(
        engine=engine,
        interval_minutes=interval_minutes,
        tickers=scan_tickers,
    )

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        if bot:
            # Start bot and scheduler concurrently
            bot_task = asyncio.create_task(bot.start_bot())

            # Wait for bot to connect
            ready = await bot.wait_until_ready_custom(timeout=30)
            if ready:
                logger.info("Discord bot ready")
            else:
                logger.warning("Discord bot not fully ready, continuing without Discord")

        await scheduler.start()

        logger.info(
            "Monitor service running (interval=%dm, discord=%s). Press Ctrl+C to stop.",
            interval_minutes, discord,
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

    finally:
        await scheduler.stop()
        if bot:
            await bot.close()
        logger.info("Monitor service stopped")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MindfulRL Monitor Service — automated watchlist scanning",
    )
    parser.add_argument(
        "--interval", type=int, default=5,
        help="Scan interval in minutes (default: 5)",
    )
    parser.add_argument(
        "--discord", action="store_true",
        help="Enable Discord bot notifications",
    )
    parser.add_argument(
        "--tickers", type=str, default="",
        help="Comma-separated tickers to monitor (default: watchlist from config)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] or None

    asyncio.run(run_service(
        interval_minutes=args.interval,
        discord=args.discord,
        tickers=tickers,
    ))


if __name__ == "__main__":
    main()