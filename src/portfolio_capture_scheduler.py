"""Cheap async coordinator for Portfolio capture cadence."""

from __future__ import annotations

import asyncio
import logging

from src.portfolio_capture import PortfolioCaptureService


logger = logging.getLogger(__name__)


async def portfolio_capture_scheduler_loop(
    service: PortfolioCaptureService,
    *,
    poll_seconds: float = 15.0,
) -> None:
    first = True
    while True:
        try:
            service.scheduler_tick(startup=first)
        except Exception:
            logger.exception("portfolio capture scheduler tick failed")
        first = False
        await asyncio.sleep(poll_seconds)
