from __future__ import annotations

import sqlite3

from src.tools.data_coverage_tools import get_ticker_data_coverage


def _make_market_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE prices (
            ticker TEXT, datetime TEXT, interval TEXT,
            open REAL, high REAL, low REAL, close REAL, volume INTEGER
        );
        CREATE TABLE news (
            id INTEGER PRIMARY KEY, ticker TEXT, title TEXT, description TEXT,
            url TEXT, publisher TEXT, source TEXT, published_at TEXT, article_hash TEXT
        );
        CREATE TABLE iv_history (
            id INTEGER PRIMARY KEY, ticker TEXT, date TEXT,
            atm_iv REAL, hv_30d REAL, vrp REAL, spot_price REAL, num_quotes INTEGER
        );
        CREATE TABLE fundamentals (
            id INTEGER PRIMARY KEY, ticker TEXT, snapshot_date TEXT, data TEXT
        );
        CREATE TABLE market_sync_meta (
            domain TEXT PRIMARY KEY, last_success TEXT, last_error TEXT,
            rows_added INTEGER, updated_at TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)",
        [
            ("CLS", "2026-06-18T13:30:00+0000", "15min", 10, 11, 9, 10.5, 100),
            ("CLS", "2026-06-18T20:00:00+0000", "15min", 10.5, 12, 10, 11.5, 200),
        ],
    )
    conn.execute(
        "INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?)",
        (1, "CLS", "headline", None, None, None, "ibkr", "2026-06-18T15:00:00+0000", "h"),
    )
    conn.execute("INSERT INTO iv_history VALUES (?,?,?,?,?,?,?,?)", (1, "CLS", "2026-06-18", 0.3, 0.2, 0.1, 11.5, 5))
    conn.execute("INSERT INTO fundamentals VALUES (?,?,?,?)", (1, "CLS", "2026-06-01", "{}"))
    conn.execute(
        "INSERT INTO market_sync_meta VALUES (?,?,?,?,?)",
        ("prices", "2026-06-22T12:00:00+00:00", None, 2, "2026-06-22T12:00:01+00:00"),
    )
    conn.commit()
    conn.close()


def test_ticker_data_coverage_explains_weekend_price_gap(tmp_path, monkeypatch):
    db = tmp_path / "market_data.db"
    _make_market_db(db)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(db))

    out = get_ticker_data_coverage(ticker="cls", target_date="2026-06-20")

    assert out["ticker"] == "CLS"
    assert out["market_db"]["exists"] is True
    assert out["prices"]["intervals"]["15min"]["latest_date"] == "2026-06-18"
    assert out["prices"]["target_date"]["status"] == "non_trading_day"
    assert out["prices"]["target_date"]["reason"] == "weekend"
    assert out["news"]["latest_published_date"] == "2026-06-18"
    assert out["iv"]["latest_date"] == "2026-06-18"
    assert out["fundamentals"]["latest_date"] == "2026-06-01"


def test_ticker_data_coverage_explains_market_holiday(tmp_path, monkeypatch):
    db = tmp_path / "market_data.db"
    _make_market_db(db)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(db))

    out = get_ticker_data_coverage(ticker="CLS", target_date="2026-06-19")

    assert out["prices"]["target_date"]["status"] == "non_trading_day"
    assert out["prices"]["target_date"]["reason"] == "us_market_holiday"
    assert out["prices"]["target_date"]["holiday"] == "Juneteenth National Independence Day"


def test_ticker_data_coverage_reports_local_missing_on_trading_day(tmp_path, monkeypatch):
    db = tmp_path / "market_data.db"
    _make_market_db(db)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(db))

    out = get_ticker_data_coverage(ticker="CLS", target_date="2026-06-22")

    assert out["prices"]["target_date"]["status"] == "missing_local_data"
    assert out["prices"]["target_date"]["reason"] == "trading_day_without_local_bars"


def test_ticker_data_coverage_rejects_invalid_target_date_without_raising(tmp_path, monkeypatch):
    db = tmp_path / "market_data.db"
    _make_market_db(db)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(db))

    out = get_ticker_data_coverage(ticker="CLS", target_date="June 20")

    assert out["prices"]["target_date"]["status"] == "invalid_target_date"
    assert out["prices"]["target_date"]["reason"] == "target_date must be YYYY-MM-DD"
