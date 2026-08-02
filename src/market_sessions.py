"""Shared completed-session rules for US-equity market data."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.tools.data_coverage_tools import _market_day_status


EXCHANGE_TZ = "America/New_York"
RTH_COMPLETE_AFTER_ET = time(16, 30)


def normalize_now_et(now_et: datetime | None) -> datetime:
    """Resolve a supplied clock in New York time."""
    exchange_tz = ZoneInfo(EXCHANGE_TZ)
    if now_et is None:
        return datetime.now(exchange_tz)
    if now_et.tzinfo is None:
        return now_et.replace(tzinfo=exchange_tz)
    return now_et.astimezone(exchange_tz)


def is_session_complete(day: date, now_et: datetime) -> bool:
    """Return whether ``day`` is complete under the existing 16:30 ET rule."""
    today_et = now_et.date()
    if day < today_et:
        return True
    if day == today_et:
        return now_et.timetz().replace(tzinfo=None) >= RTH_COMPLETE_AFTER_ET
    return False


def complete_trading_days(
    start: date,
    end: date,
    now_et: datetime,
) -> list[date]:
    """Return complete US trading days in the inclusive date range."""
    days: list[date] = []
    current = start
    while current <= end:
        if (
            _market_day_status(current)["is_trading_day"]
            and is_session_complete(current, now_et)
        ):
            days.append(current)
        current += timedelta(days=1)
    return days


def latest_completed_market_date(now_et: datetime | None = None) -> date | None:
    """Find the latest completed US trading day within a bounded lookback."""
    normalized = normalize_now_et(now_et)
    for days_back in range(14):
        candidate = normalized.date() - timedelta(days=days_back)
        if (
            _market_day_status(candidate)["is_trading_day"]
            and is_session_complete(candidate, normalized)
        ):
            return candidate
    return None
