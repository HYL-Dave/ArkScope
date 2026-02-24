"""
Monitor tool functions (1 tool).

31. scan_alerts — Scan watchlist or specific tickers for alerts
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

logger = logging.getLogger(__name__)


def scan_alerts(
    dal: DataAccessLayer,
    tickers: str = "",
) -> str:
    """
    Scan tickers for price, sentiment, signal, and sector alerts.

    Runs all enabled watchers from config/user_profile.yaml against the
    specified tickers (or the default watchlist if none specified).

    Args:
        dal: DataAccessLayer instance
        tickers: Comma-separated ticker symbols (empty = scan full watchlist)

    Returns:
        Human-readable summary of all triggered alerts.
    """
    from src.monitor.engine import MonitorEngine

    engine = MonitorEngine(dal=dal)

    ticker_list = None
    if tickers.strip():
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    # Run async scan in sync context
    alerts = asyncio.run(engine.scan_once(tickers=ticker_list, notify=False))
    return engine.format_scan_summary(alerts)