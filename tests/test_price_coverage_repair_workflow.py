"""Actual writer/reader integration; only the upstream bar source is a fixture."""

from datetime import date, datetime, timezone
import socket
import sqlite3

import pytest

from src import market_data_direct, prices_runtime
from src.market_coverage.repair import preview_price_repair, validate_price_repair
from src.market_coverage.service import TradingDayCoverageService
from tests.test_market_data_direct import _FakeIBKR, _FakePolygon, _bar
from tests.test_trading_day_coverage import _Calendar, _Fixtures, _session, _slots, _create_market_db


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("price_repair_workflow_must_not_use_network")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    normalize = market_data_direct._norm_now_et
    monkeypatch.setattr(market_data_direct, "_norm_now_et", lambda value=None: normalize(
        value if value is not None else datetime(2026, 9, 3, 23, tzinfo=timezone.utc)))


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


def test_successful_worker_with_partial_bars_keeps_a_gap_and_requires_new_preview(tmp_path, monkeypatch):
    path = tmp_path / "market.db"
    day = date(2026, 9, 3)
    session = _session(day)
    previous_day = date(2026, 9, 2)
    previous_session = _session(previous_day)
    _create_market_db(path, rows=tuple(("LIVE", at) for at in _slots(previous_session)))
    service = TradingDayCoverageService(db_path=path, calendar_adapter=_Calendar({previous_day: previous_session, day: session}), fixtures=_Fixtures(),
        clock=lambda: datetime(2026, 9, 3, 23, tzinfo=timezone.utc))
    before = service.get_coverage(universe=["LIVE"], lookback_days=1, interval="15min")
    plan = preview_price_repair(before)
    source = _FakeIBKR({"LIVE": [_bar(_slots(session)[0])]})
    monkeypatch.setattr(market_data_direct, "resolve_market_db_path", lambda: str(path))
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: source)
    monkeypatch.setattr(market_data_direct, "_default_polygon_src", lambda: pytest.fail("unapproved fallback"))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    result = prices_runtime._run_worker(tickers="LIVE", lookback_days=1, provider="ibkr", gateway_lock_held=True,
        no_provider_fallback=True, as_of_date=day)
    # Collector success is day-presence, not session-slot coverage.
    assert result["status"] == "succeeded"
    assert result["rows_added"] == 1
    partial = service.get_coverage(universe=["LIVE"], lookback_days=1, interval="15min")
    assert partial.history_gaps[0].partial_dates == [day.isoformat()]
    assert partial.days[0].complete_ticker_count == 0
    with pytest.raises(ValueError, match="price_repair_preview_changed"):
        validate_price_repair(partial, plan["preview_sha256"])
    assert len(source.calls) == 1
    fresh = preview_price_repair(partial)
    validate_price_repair(partial, fresh["preview_sha256"])
    complete = _FakeIBKR({"LIVE": [_bar(at) for at in _slots(session)]})
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: complete)
    result = prices_runtime._run_worker(tickers=",".join(fresh["tickers"]), lookback_days=1, provider="ibkr", gateway_lock_held=True,
        no_provider_fallback=True, as_of_date=day)
    assert result["rows_added"] == 25
    assert len(complete.calls) == 1
    after = service.get_coverage(universe=["LIVE"], lookback_days=1, interval="15min")
    assert after.days[0].complete_ticker_count == 1
    assert after.history_gaps == []


def test_repair_after_interrupted_write_resumes_only_remaining_ticker(tmp_path, monkeypatch):
    path = tmp_path / "market.db"
    days = (date(2026, 9, 2), date(2026, 9, 3))
    sessions = {day: _session(day) for day in days}
    _create_market_db(path)
    service = TradingDayCoverageService(db_path=path, calendar_adapter=_Calendar(sessions), fixtures=_Fixtures(),
        clock=lambda: datetime(2026, 9, 3, 23, tzinfo=timezone.utc))
    bars = [_bar(at) for session in sessions.values() for at in _slots(session)]
    source = _FakeIBKR({"FIRST": bars, "SECOND": bars})
    monkeypatch.setattr(market_data_direct, "resolve_market_db_path", lambda: str(path))
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: source)
    monkeypatch.setattr(market_data_direct, "_default_polygon_src", lambda: pytest.fail("unapproved fallback"))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    before = service.get_coverage(universe=["FIRST", "SECOND"], lookback_days=1, interval="15min")
    plan = preview_price_repair(before)
    insert = market_data_direct._insert_rows
    class Interrupted(BaseException):
        pass
    def interrupted(conn, rows):
        if rows and rows[0][0] == "SECOND":
            raise Interrupted()
        return insert(conn, rows)
    with monkeypatch.context() as fault:
        fault.setattr(market_data_direct, "_insert_rows", interrupted)
        with pytest.raises(Interrupted):
            prices_runtime._run_worker(tickers=",".join(plan["tickers"]), lookback_days=1, provider="ibkr", gateway_lock_held=True,
                no_provider_fallback=True, as_of_date=days[-1])
    with sqlite3.connect(path) as conn:
        first_rows = conn.execute("SELECT * FROM prices ORDER BY datetime").fetchall()
        assert len(first_rows) == 52 and all(row[0] == "FIRST" for row in first_rows)
        assert conn.execute("SELECT status FROM provider_sync_runs").fetchone()[0] == "running"
    partial = service.get_coverage(universe=["FIRST", "SECOND"], lookback_days=1, interval="15min")
    with pytest.raises(ValueError, match="price_repair_preview_changed"):
        validate_price_repair(partial, plan["preview_sha256"])
    fresh = preview_price_repair(partial)
    assert fresh["tickers"] == ["SECOND"]
    assert len(source.calls) == 2
    resumed = _FakeIBKR({"SECOND": bars})
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: resumed)
    result = prices_runtime._run_worker(tickers=",".join(fresh["tickers"]), lookback_days=1, provider="ibkr", gateway_lock_held=True,
        no_provider_fallback=True, as_of_date=days[-1])
    assert result["rows_added"] == 52
    assert len(resumed.calls) == 1
    after = service.get_coverage(universe=["FIRST", "SECOND"], lookback_days=1, interval="15min")
    assert after.history_gaps == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT * FROM prices WHERE ticker='FIRST' ORDER BY datetime").fetchall() == first_rows
        assert conn.execute("SELECT count(*) FROM prices").fetchone()[0] == 104


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
