"""Old partial sessions cannot disappear behind a complete recent week."""

from datetime import date, datetime, timedelta, timezone
import socket

import pytest

from src.market_coverage.models import CalendarDay
from src.market_coverage.repair import preview_price_repair
from src.market_coverage.service import TradingDayCoverageService
from tests.test_trading_day_coverage import _Calendar, _Fixtures, _session, _slots, _create_market_db


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("multiday_coverage_is_local_only")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def test_multiple_old_partial_sessions_remain_visible_when_recent_week_is_complete(tmp_path):
    end = date(2026, 9, 4)
    days = [end - timedelta(days=offset) for offset in range(121)]
    calendar = {day: _session(day) if day.weekday() < 5 else CalendarDay.closed(day) for day in days}
    partial_counts = {date(2026, 6, 5): 6, date(2026, 6, 25): 5, date(2026, 6, 26): 3}
    missing = date(2026, 8, 27)
    rows = []
    for day, session in calendar.items():
        if day.weekday() >= 5 or day == missing:
            continue
        slots = _slots(session)
        rows.extend(("LIVE", at) for at in slots[:partial_counts.get(day, len(slots))])
    path = tmp_path / "market.db"
    _create_market_db(path, rows=tuple(rows))
    service = TradingDayCoverageService(db_path=path, calendar_adapter=_Calendar(calendar), fixtures=_Fixtures(),
        clock=lambda: datetime(2026, 9, 4, 23, tzinfo=timezone.utc))
    recent = service.get_coverage(universe=["LIVE"], lookback_days=5, interval="15min")
    assert recent.history_gaps == []
    assert preview_price_repair(recent)["tickers"] == []

    full = service.get_coverage(universe=["LIVE"], lookback_days=120, interval="15min")
    plan = preview_price_repair(full)
    assert plan["gaps"] == [{"ticker": "LIVE", "missing_dates": [missing.isoformat()],
                             "partial_dates": sorted(day.isoformat() for day in partial_counts)}]
    for day in full.days:
        if date.fromisoformat(day.date) in partial_counts:
            assert day.expected_slot_count == 26
            assert day.complete_ticker_count == 0 and day.partial_ticker_count == 1
    assert plan["lookback_days"] == 120 and plan["fallback_allowed"] is False
