from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.news_normalized.routing import NEWS_PG_EXIT_COMPLETED_KEY
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend
from src.tools.data_access import DataAccessLayer


def seed_profile(base: Path, **settings: str) -> Path:
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db = data_dir / "profile_state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE profile_settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany(
            "INSERT INTO profile_settings (key, value) VALUES (?, ?)",
            sorted(settings.items()),
        )
        conn.commit()
    finally:
        conn.close()
    return db


def seed_market_db(base: Path, *, completed: bool = True) -> Path:
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
            CREATE TABLE news_pg_exit_runs (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL
            );
            """
        )
        if completed:
            conn.execute("INSERT INTO news_pg_exit_runs (status) VALUES ('completed')")
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


def _poison_pg_news(monkeypatch) -> None:
    def boom(self, *args, **kwargs):
        raise AssertionError("PG called")

    for name in (
        "query_news",
        "query_news_search",
        "query_news_stats",
        "query_news_feed",
    ):
        monkeypatch.setattr(DatabaseBackend, name, boom)


def test_no_dsn_completed_news_exit_selects_local_backend_with_market_strict(tmp_path):
    seed_profile(
        tmp_path,
        **{NEWS_PG_EXIT_COMPLETED_KEY: "true", "use_local_market": "false"},
    )
    seed_market_db(tmp_path)

    dal = DataAccessLayer(base_path=tmp_path, db_dsn="auto")

    assert isinstance(dal._backend, LocalMarketDatabaseBackend)
    assert dal._backend._news_strict is True
    assert dal._backend._strict is True
    assert dal._backend._dsn == ""


def test_news_hard_local_no_dsn_never_calls_pg_for_empty_reads(tmp_path, monkeypatch):
    seed_profile(
        tmp_path,
        **{NEWS_PG_EXIT_COMPLETED_KEY: "true", "use_local_market": "false"},
    )
    seed_market_db(tmp_path)
    _poison_pg_news(monkeypatch)

    dal = DataAccessLayer(base_path=tmp_path, db_dsn="auto")

    assert isinstance(dal._backend, LocalMarketDatabaseBackend)
    assert dal.get_news(ticker="AAPL", scored_only=False).count == 0
    assert dal.search_news(query="Apple", ticker="AAPL", scored_only=False).count == 0
    assert dal.get_news_stats(ticker="AAPL") == []
    feed = dal.get_news_feed(q="Apple", ticker="AAPL")
    assert feed["available"] is True
    assert feed["total"] == 0


def test_completed_audit_marker_forces_news_hard_local_without_profile_exit_setting(
    tmp_path,
):
    seed_profile(tmp_path, use_local_market="false")
    seed_market_db(tmp_path, completed=True)

    dal = DataAccessLayer(base_path=tmp_path, db_dsn="auto")

    assert isinstance(dal._backend, LocalMarketDatabaseBackend)
    assert dal._backend._news_strict is True
    assert dal._backend._strict is True


def test_no_dsn_get_conn_fails_before_psycopg(monkeypatch):
    called = []

    def connect_boom(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("psycopg2 called")

    monkeypatch.setattr("src.tools.backends.db_backend.psycopg2.connect", connect_boom)
    backend = DatabaseBackend("")

    with pytest.raises(RuntimeError, match="PostgreSQL is not configured"):
        backend._get_conn()

    assert called == []
