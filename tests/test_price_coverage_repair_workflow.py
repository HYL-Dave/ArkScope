"""Actual writer/reader integration; only the upstream bar source is a fixture."""

from datetime import date, datetime, timezone
import sqlite3

import pytest

from src import market_data_direct, prices_runtime
from src.market_coverage.repair import preview_price_repair
from src.market_coverage.service import TradingDayCoverageService
from tests.test_market_data_direct import _FakeIBKR, _FakePolygon, _bar
from tests.test_trading_day_coverage import _Calendar, _Fixtures, _session, _slots, _create_market_db


def test_real_price_worker_fills_missing_and_partial_sessions_then_coverage_proves_completion(tmp_path, monkeypatch):
    path = tmp_path / "market.db"
    days = (date(2026, 9, 2), date(2026, 9, 3))
    sessions = {day: _session(day) for day in days}
    _create_market_db(path, rows=(("LIVE", _slots(sessions[days[0]])[0]),))
    service = TradingDayCoverageService(
        db_path=path, calendar_adapter=_Calendar(sessions), fixtures=_Fixtures(),
        clock=lambda: datetime(2026, 9, 3, 23, tzinfo=timezone.utc),
    )
    before = service.get_coverage(universe=["LIVE"], lookback_days=1, interval="15min")
    plan = preview_price_repair(before)
    assert plan["gaps"] == [{"ticker": "LIVE", "missing_dates": ["2026-09-03"], "partial_dates": ["2026-09-02"]}]
    source = _FakeIBKR({"LIVE": [_bar(at) for session in sessions.values() for at in _slots(session)]})
    monkeypatch.setattr(market_data_direct, "resolve_market_db_path", lambda: str(path))
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: source)
    monkeypatch.setattr(market_data_direct, "_default_polygon_src", lambda: pytest.fail("unapproved fallback"))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    result = prices_runtime._run_worker(
        tickers="LIVE", lookback_days=plan["lookback_days"], provider="ibkr",
        gateway_lock_held=True, no_provider_fallback=True, as_of_date=date.fromisoformat(plan["as_of_date"]),
    )
    assert result["rows_added"] == 51
    assert len(source.calls) == 1
    after = service.get_coverage(universe=["LIVE"], lookback_days=1, interval="15min")
    assert after.history_gaps == []
    assert all(day.complete_ticker_count == 1 and day.expected_slot_count == 26 for day in after.days)
    assert preview_price_repair(after)["tickers"] == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM prices").fetchone()[0] == 52
        assert conn.execute("SELECT close FROM prices ORDER BY datetime LIMIT 1").fetchone()[0] == 1


@pytest.mark.parametrize("injected", (False, True))
def test_explicit_ibkr_only_repair_never_falls_back_even_after_an_empty_response(tmp_path, monkeypatch, injected):
    path = tmp_path / "market.db"
    _create_market_db(path)
    source, fallback = _FakeIBKR(), _FakePolygon()
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(market_data_direct, "_default_polygon_src", lambda: pytest.fail("fallback construction"))
    result = market_data_direct.backfill_prices_direct(
        tickers_arg="LIVE", lookback_days=1, provider="ibkr", db_path=str(path),
        ibkr_src=source, polygon_src=fallback if injected else None,
        now_et=datetime(2026, 9, 3, 23, tzinfo=timezone.utc),
        allow_provider_fallback=False, acquire_gateway_lock=False,
    )
    assert source.calls and not fallback.calls
    assert result["status"] == "failed"
    assert result["rows_added"] == 0
