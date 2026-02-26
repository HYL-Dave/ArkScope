"""
Monitor scheduler — periodic scan execution.

Uses asyncio tasks (no external scheduler dependency).
Coordinates MonitorEngine scans at fixed intervals.

Threading model:
    The watcher scan (DB queries via psycopg2, signal synthesis, etc.)
    is synchronous and can block for 10+ seconds.  Running it directly
    on the Discord event-loop thread causes gateway heartbeat timeouts.

    Solution: ``_scan_and_notify()`` runs the scan in a *background
    thread* via ``asyncio.to_thread``, then dispatches notifications
    back on the main event loop where the Discord bot lives.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .engine import MonitorEngine

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """Run MonitorEngine.scan_once() at fixed intervals."""

    def __init__(
        self,
        engine: MonitorEngine,
        interval_minutes: int = 5,
        tickers: Optional[List[str]] = None,
    ) -> None:
        self._engine = engine
        self._interval = interval_minutes * 60  # seconds
        self._tickers = tickers
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the periodic scan loop."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Scheduler started (interval=%dm, tickers=%s)",
            self._interval // 60,
            self._tickers or "watchlist",
        )

    async def stop(self) -> None:
        """Stop the periodic scan loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def run_once(self) -> None:
        """Run a single scan (useful for /scan command or testing).

        Runs directly on the current event loop — fine for one-off calls
        but NOT suitable for the periodic loop (use _scan_and_notify).
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("Scan triggered at %s", now)
        try:
            alerts = await self._engine.scan_once(
                tickers=self._tickers, notify=True,
            )
            logger.info("Scan complete: %d alert(s)", len(alerts))
        except Exception:
            logger.exception("Scheduled scan failed")

    async def _loop(self) -> None:
        """Internal loop — scan, sleep, repeat."""
        # Run first scan immediately
        await self._scan_and_notify()

        while self._running:
            await asyncio.sleep(self._interval)
            if self._running:
                await self._scan_and_notify()

    # ── Thread-safe scan ──────────────────────────────────────────────

    async def _scan_and_notify(self) -> None:
        """Scan in a background thread, then notify on the main event loop.

        This prevents synchronous DB queries (psycopg2) and signal
        synthesis from blocking the Discord gateway heartbeat.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("Scan triggered at %s", now)
        try:
            # Heavy I/O (psycopg2, HTTP) runs in thread-pool thread.
            alerts = await asyncio.to_thread(self._scan_blocking)
            logger.info("Scan complete: %d alert(s)", len(alerts))
            # Notifications must run on the main event loop because
            # the Discord bot connection is bound to it.
            if alerts:
                await self._engine.notify(alerts)
        except Exception:
            logger.exception("Scheduled scan failed")

    def _scan_blocking(self) -> list:
        """Blocking scan wrapper — executed in a thread-pool thread.

        Creates a fresh event loop in the thread because the watchers
        are declared ``async def`` (even though their I/O is sync).
        ``notify=False`` so we don't try to send Discord messages from
        a non-main event loop.
        """
        return asyncio.run(
            self._engine.scan_once(tickers=self._tickers, notify=False)
        )
