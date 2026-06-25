"""Slice A — read-only trading-day / price-coverage diagnostics (no PG, no provider, no write).

Per-day universe transpose of the per-ticker coverage: for each calendar day in the window,
classify weekend/holiday/trading-day, session-complete, and count universe tickers full /
partial / missing — plus a provider_sync_meta error summary (the LC-style contract-unresolved
signal). Full/partial is measured against the per-day max bar count (self-calibrating for
half-days), so no brittle hardcoded session length.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src.market_data_admin import _PRICES_SCHEMA
from src.market_data_direct import _ensure_provider_sync_tables, summarize_trading_day_coverage

_ET = ZoneInfo("America/New_York")


def _bars(conn, ticker, day, n, interval="15min"):
    for i in range(n):
        dt = f"{day}T{13 + i // 4:02d}:{(i % 4) * 15:02d}:00+0000"
        conn.execute(
            "INSERT OR IGNORE INTO prices(ticker,datetime,interval,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?,?)", (ticker, dt, interval, 1, 1, 1, 1, 1))


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA)
    _ensure_provider_sync_tables(conn)
    conn.execute("CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL)")
    conn.execute("INSERT INTO ticker_aliases VALUES ('BRK.B', 'BRK B')")
    # 6/17 Wed (complete trading): AAPL 26 full, BRK B 26 full, LC 0 missing
    _bars(conn, "AAPL", "2026-06-17", 26); _bars(conn, "BRK B", "2026-06-17", 26)
    # 6/18 Thu (complete): AAPL 26 full, BRK B 3 partial, LC 0 missing
    _bars(conn, "AAPL", "2026-06-18", 26); _bars(conn, "BRK B", "2026-06-18", 3)
    # 6/19 Fri = Juneteenth holiday · 6/20-21 weekend  → no bars
    # 6/22 Mon (complete): AAPL 26, BRK B 26, LC 0
    _bars(conn, "AAPL", "2026-06-22", 26); _bars(conn, "BRK B", "2026-06-22", 26)
    # 6/23 Tue (IN-PROGRESS): AAPL 10, BRK B 10  → session not complete
    _bars(conn, "AAPL", "2026-06-23", 10); _bars(conn, "BRK B", "2026-06-23", 10)
    # provider error for LC (recent IBKR contract unresolved)
    conn.execute(
        "INSERT INTO provider_sync_meta(provider,ticker,interval,last_success,last_bar_datetime,"
        "last_error,rows_added,updated_at) VALUES('ibkr','LC','15min',NULL,NULL,?,0,?)",
        ("contract not found (error 200)", "2026-06-23T16:00:00+0000"))
    conn.commit()
    conn.close()
    return str(path)


_UNIVERSE = ["AAPL", "BRK.B", "LC"]   # BRK.B alias → BRK B; LC has no bars


def _summary(db):
    # now_et 6/23 11:45 ET → 6/23 session in-progress (< 16:30); 6/17/18/22 complete.
    return summarize_trading_day_coverage(
        _UNIVERSE, interval="15min", lookback_days=6, db_path=db,
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 11, 45, tzinfo=_ET))


def _day(summary, d):
    return next(x for x in summary["days"] if x["date"] == d)


def test_universe_count_dedupes_aliases(db):
    # BRK.B canonicalises to BRK B → 3 distinct tickers, not 4.
    assert _summary(db)["universe_count"] == 3


def test_days_newest_first_and_window(db):
    days = [d["date"] for d in _summary(db)["days"]]
    assert days == ["2026-06-23", "2026-06-22", "2026-06-21", "2026-06-20",
                    "2026-06-19", "2026-06-18", "2026-06-17"]


def test_weekend_and_holiday_marked_non_trading(db):
    s = _summary(db)
    assert _day(s, "2026-06-20")["is_trading_day"] is False
    assert _day(s, "2026-06-20")["reason"] == "weekend"
    jun = _day(s, "2026-06-19")
    assert jun["is_trading_day"] is False and jun["reason"] == "us_market_holiday"
    assert jun["holiday"] == "Juneteenth National Independence Day"


def test_complete_trading_day_full_missing_counts(db):
    d = _day(_summary(db), "2026-06-22")
    assert d["is_trading_day"] and d["session_complete"] is True
    assert d["full_bar_count"] == 26          # per-day max across the universe
    assert d["full"] == 2 and d["partial"] == 0 and d["missing"] == 1
    assert d["missing_tickers"] == ["LC"]     # 0 bars on a complete trading day


def test_partial_day_lists_thin_ticker(db):
    d = _day(_summary(db), "2026-06-18")
    assert d["full"] == 1 and d["missing"] == 1
    assert d["partial"] == 1
    assert d["partial_tickers"] == [{"ticker": "BRK B", "bars": 3}]


def test_in_progress_today_flagged_incomplete(db):
    d = _day(_summary(db), "2026-06-23")
    assert d["is_trading_day"] is True
    assert d["session_complete"] is False     # before 16:30 ET → in-progress, not a gap


def test_provider_errors_surface_lc(db):
    errs = _summary(db)["provider_errors"]
    lc = next(e for e in errs if e["ticker"] == "LC")
    assert "contract not found" in lc["last_error"] and lc["interval"] == "15min"


def test_route_wires_universe_and_db(db, monkeypatch):
    # the route resolves the active universe + market DB path and returns the summary shape.
    import src.api.routes.market_data as mroutes
    import src.universe_scope as us
    monkeypatch.setattr(us, "resolve_active_universe", lambda: list(_UNIVERSE))
    monkeypatch.setattr(mroutes, "resolve_market_db_path", lambda: db)
    out = mroutes.market_data_trading_days(lookback_days=6, interval="15min")
    assert out["universe_count"] == 3 and out["interval"] == "15min"
    assert any(d["date"] == "2026-06-22" for d in out["days"])
    assert any(e["ticker"] == "LC" for e in out["provider_errors"])


def test_route_registered():
    import src.api.routes.market_data as mroutes
    assert "/market-data/trading-days" in {r.path for r in mroutes.router.routes}


def test_read_only_absent_db_is_honest(tmp_path):
    out = summarize_trading_day_coverage(
        _UNIVERSE, db_path=str(tmp_path / "nope.db"), lookback_days=3,
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    assert out["universe_count"] == 3
    # absent DB → trading days show all-missing, non-trading days still marked
    tradeday = next(d for d in out["days"] if d["is_trading_day"] and d["session_complete"])
    assert tradeday["missing"] == 3 and tradeday["full"] == 0
    assert out["provider_errors"] == []
