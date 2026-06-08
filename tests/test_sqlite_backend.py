"""Tests for the local market-data SqliteBackend + CompositeBackend routing (slice 3a)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.tools.backends.sqlite_backend import SqliteBackend
from src.tools.backends.composite_backend import CompositeBackend

_COLS = ["datetime", "open", "high", "low", "close", "volume"]


def _dt(day: date, hour: int, minute: int) -> str:
    return f"{day.isoformat()}T{hour:02d}:{minute:02d}:00+0000"


@pytest.fixture()
def market_db(tmp_path):
    """A market_data.db with 15min bars for AAPL across 2 hours of one recent day."""
    day = date.today() - timedelta(days=2)  # safely inside a 30-day window
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE prices (
            ticker TEXT, datetime TEXT, interval TEXT,
            open REAL, high REAL, low REAL, close REAL, volume INTEGER,
            PRIMARY KEY (ticker, datetime, interval)
        );
        """
    )
    # 8 × 15min bars: 09:00..10:45. open ramps 100,101,...; highs/lows spread.
    bars = []
    for i in range(8):
        hour = 9 + i // 4
        minute = (i % 4) * 15
        o = 100 + i
        bars.append(("AAPL", _dt(day, hour, minute), "15min", o, o + 2, o - 1, o + 0.5, 1000 + i))
    conn.executemany(
        "INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)", bars
    )
    conn.commit()
    conn.close()
    return str(db), day


def test_native_15min_passthrough(market_db):
    db, _ = market_db
    df = SqliteBackend(db).query_prices("aapl", interval="15min", days=30)
    assert list(df.columns) == _COLS
    assert len(df) == 8
    assert df.iloc[0]["open"] == 100 and df.iloc[-1]["open"] == 107
    # ordered ascending
    assert list(df["datetime"]) == sorted(df["datetime"])


def test_rollup_1h(market_db):
    db, day = market_db
    df = SqliteBackend(db).query_prices("AAPL", interval="1h", days=30)
    # 8 × 15min over 09:xx and 10:xx → 2 hourly bars
    assert len(df) == 2
    h1 = df.iloc[0]
    assert h1["datetime"] == _dt(day, 9, 0).replace(":00:00", ":00:00")  # 'YYYY-..T09:00:00+0000'
    assert h1["open"] == 100          # first open of the hour
    assert h1["close"] == 103.5       # last close of the hour (103 + 0.5)
    assert h1["high"] == 105          # max high (103+2)
    assert h1["low"] == 99            # min low (100-1)
    assert h1["volume"] == 1000 + 1001 + 1002 + 1003


def test_rollup_1d(market_db):
    db, day = market_db
    df = SqliteBackend(db).query_prices("AAPL", interval="1d", days=30)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["datetime"] == f"{day.isoformat()}T00:00:00+0000"
    assert row["open"] == 100 and row["close"] == 107.5
    assert row["high"] == 109 and row["low"] == 99   # max(107+2)=109, min(100-1)=99
    assert row["volume"] == sum(1000 + i for i in range(8))


def test_empty_and_missing(market_db, tmp_path):
    db, _ = market_db
    # unknown ticker → empty frame (caller falls back to PG)
    assert SqliteBackend(db).query_prices("NOPE", days=30).empty
    # out-of-window (days=0 → cutoff today, bars are 2 days old) → empty
    assert SqliteBackend(db).query_prices("AAPL", days=0).empty
    # missing DB file → empty (no raise)
    assert SqliteBackend(str(tmp_path / "nope.db")).query_prices("AAPL").empty


def test_get_available_tickers(market_db):
    db, _ = market_db
    assert SqliteBackend(db).get_available_tickers("prices") == ["AAPL"]
    assert SqliteBackend(db).get_available_tickers("news") == []  # slice 3a = prices only


# --- CompositeBackend routing -------------------------------------------------


class _FakePG:
    """Stand-in primary (PG) recording which methods were hit."""

    def __init__(self):
        self.calls = []

    def query_prices(self, ticker, interval="15min", days=30):
        self.calls.append(("query_prices", ticker))
        return pd.DataFrame([("PGSENTINEL", 1, 1, 1, 1, 1)], columns=_COLS)

    def get_available_tickers(self, data_type):
        self.calls.append(("get_available_tickers", data_type))
        return ["PGONLY"]

    def query_sa_picks(self, *a, **k):
        self.calls.append(("query_sa_picks", a))
        return ["sa-result"]

    def close(self):
        self.calls.append(("close", None))


def test_composite_prices_local_when_present(market_db):
    db, _ = market_db
    pg = _FakePG()
    comp = CompositeBackend(primary=pg, market=SqliteBackend(db))
    df = comp.query_prices("AAPL", interval="15min", days=30)
    assert len(df) == 8 and "PGSENTINEL" not in df["datetime"].values
    assert pg.calls == []  # PG never touched when local has data


def test_composite_prices_fallback_to_pg(market_db):
    db, _ = market_db
    pg = _FakePG()
    comp = CompositeBackend(primary=pg, market=SqliteBackend(db))
    df = comp.query_prices("UNKNOWN", days=30)  # not in local → PG fallback
    assert df.iloc[0]["datetime"] == "PGSENTINEL"
    assert ("query_prices", "UNKNOWN") in pg.calls


def test_composite_forwards_non_market_methods(market_db):
    db, _ = market_db
    pg = _FakePG()
    comp = CompositeBackend(primary=pg, market=SqliteBackend(db))
    # SA (and any non-market method) → primary via __getattr__
    assert comp.query_sa_picks("x") == ["sa-result"]
    assert ("query_sa_picks", ("x",)) in pg.calls


def test_composite_available_tickers_routing(market_db):
    db, _ = market_db
    pg = _FakePG()
    comp = CompositeBackend(primary=pg, market=SqliteBackend(db))
    assert comp.get_available_tickers("prices") == ["AAPL"]   # local
    assert comp.get_available_tickers("news") == ["PGONLY"]   # → PG
