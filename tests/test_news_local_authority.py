from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.tools.backends.local_market_backend import LocalMarketBackend
from src.tools.data_access import DataAccessLayer


def seed_market_db(base: Path) -> Path:
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db = data_dir / "market_data.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE news (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                title TEXT,
                description TEXT,
                url TEXT,
                publisher TEXT,
                source TEXT,
                published_at TEXT,
                article_hash TEXT
            );
            CREATE VIRTUAL TABLE news_fts USING fts5(
                title, description, content='news', content_rowid='id',
                tokenize='porter unicode61'
            );
            CREATE TABLE prices (
                ticker TEXT, datetime TEXT, interval TEXT,
                open REAL, high REAL, low REAL, close REAL, volume INTEGER,
                PRIMARY KEY (ticker, datetime, interval)
            );
            CREATE TABLE iv_history (
                id INTEGER PRIMARY KEY, ticker TEXT, date TEXT,
                atm_iv REAL, hv_30d REAL, vrp REAL, spot_price REAL, num_quotes INTEGER
            );
            CREATE TABLE fundamentals (
                id INTEGER PRIMARY KEY, ticker TEXT, snapshot_date TEXT, data TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for name in (
        "ARKSCOPE_MARKET_DB",
        "ARKSCOPE_PROFILE_DB",
        "ARKSCOPE_SA_DB",
        "ARKSCOPE_USE_LOCAL_MARKET",
        "ARKSCOPE_LOCAL_MARKET_STRICT",
        "ARKSCOPE_USE_LOCAL_SA",
    ):
        monkeypatch.delenv(name, raising=False)


def test_local_news_authority_uses_strict_market_store(tmp_path):
    seed_market_db(tmp_path)

    dal = DataAccessLayer(base_path=tmp_path)

    assert isinstance(dal._backend, LocalMarketBackend)
    assert dal._backend._market_db == str(tmp_path / "data" / "market_data.db")
    assert not hasattr(dal._backend, "_dsn")


def test_local_news_empty_reads_are_honest(tmp_path):
    seed_market_db(tmp_path)
    dal = DataAccessLayer(base_path=tmp_path)

    assert isinstance(dal._backend, LocalMarketBackend)
    assert dal.get_news(ticker="AAPL").count == 0
    assert dal.search_news(query="Apple", ticker="AAPL").count == 0
    assert dal.get_news_stats(ticker="AAPL") == []
    feed = dal.get_news_feed(q="Apple", ticker="AAPL")
    assert feed["available"] is True
    assert feed["total"] == 0
    assert feed["content_counts"] == {
        "full": 0,
        "headline_only": 0,
        "unknown": 0,
    }


def test_local_news_authority_is_default_without_profile_toggle(tmp_path):
    seed_market_db(tmp_path)

    dal = DataAccessLayer(base_path=tmp_path)

    assert isinstance(dal._backend, LocalMarketBackend)
    assert dal._backend._market_db == str(tmp_path / "data" / "market_data.db")


def test_local_news_authority_initializes_with_declared_dependencies(tmp_path):
    seed_market_db(tmp_path)
    dal = DataAccessLayer(base_path=tmp_path)

    assert isinstance(dal._backend, LocalMarketBackend)
    assert dal._backend._market_db == str(tmp_path / "data" / "market_data.db")
