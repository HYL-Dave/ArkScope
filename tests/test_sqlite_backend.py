"""Tests for the local market-data SqliteBackend + LocalMarketDatabaseBackend routing (slice 3a)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.sqlite_backend import SqliteBackend
from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend

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


# --- LocalMarketDatabaseBackend routing (a DatabaseBackend SUBCLASS) ----------

_PG_SENTINEL = pd.DataFrame([("PGSENTINEL", 1, 1, 1, 1, 1)], columns=_COLS)


def _make(db):
    # Constructing does NOT connect to PG (DatabaseBackend connects lazily).
    return LocalMarketDatabaseBackend("postgresql://fake/db", market_db=db)


def test_is_databasebackend_subclass(market_db):
    # REGRESSION (the "enable local market → all data wrong" bug): the DAL/agents
    # branch on isinstance(backend, DatabaseBackend) in ~30 places to gate every
    # DB-only path (batch summaries / news / sentiment / freshness). The
    # local-market backend MUST satisfy isinstance or those paths silently fall to
    # empty/file behaviour and the cockpit shows wrong/empty data.
    db, _ = market_db
    assert isinstance(_make(db), DatabaseBackend) is True


def test_prices_local_when_present(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend, "query_prices",
        lambda self, ticker, interval="15min", days=30: (hit.append(ticker), _PG_SENTINEL)[1],
    )
    df = _make(db).query_prices("AAPL", interval="15min", days=30)
    assert len(df) == 8 and "PGSENTINEL" not in df["datetime"].values
    assert hit == []  # PG (super) never hit when local has data


def test_prices_fallback_to_pg(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend, "query_prices",
        lambda self, ticker, interval="15min", days=30: (hit.append(ticker), _PG_SENTINEL)[1],
    )
    df = _make(db).query_prices("UNKNOWN", days=30)  # not in local → PG fallback
    assert df.iloc[0]["datetime"] == "PGSENTINEL" and hit == ["UNKNOWN"]


def test_available_tickers_routing(market_db, monkeypatch):
    db, _ = market_db
    monkeypatch.setattr(DatabaseBackend, "get_available_tickers", lambda self, data_type: ["PGONLY"])
    b = _make(db)
    assert b.get_available_tickers("prices") == ["AAPL"]   # local
    assert b.get_available_tickers("news") == ["PGONLY"]   # → PG (super)


def test_non_market_methods_are_inherited_pg(market_db):
    # Non-overridden methods ARE DatabaseBackend's (inheritance, not forwarding) —
    # so SA/news/reports/etc. run exactly as on plain PG.
    db, _ = market_db
    b = _make(db)
    assert type(b).query_news is DatabaseBackend.query_news
    assert type(b).query_prices is not DatabaseBackend.query_prices  # overridden
