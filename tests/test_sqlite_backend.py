"""Tests for the local market-data SqliteBackend + LocalMarketDatabaseBackend
(3a prices + 3b news + 3c-A iv_history/fundamentals)."""

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
    """A market_data.db with 15min bars + news (FTS5) + iv_history + fundamentals."""
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
        CREATE TABLE news (
            id INTEGER PRIMARY KEY, ticker TEXT, title TEXT, description TEXT,
            url TEXT, publisher TEXT, source TEXT, published_at TEXT, article_hash TEXT
        );
        CREATE VIRTUAL TABLE news_fts USING fts5(title, description, content='news', content_rowid='id', tokenize='porter unicode61');
        CREATE TABLE iv_history (
            id INTEGER PRIMARY KEY, ticker TEXT, date TEXT,
            atm_iv REAL, hv_30d REAL, vrp REAL, spot_price REAL, num_quotes INTEGER
        );
        CREATE TABLE fundamentals (
            id INTEGER PRIMARY KEY, ticker TEXT, snapshot_date TEXT, data TEXT
        );
        """
    )
    bars = []
    for i in range(8):
        hour = 9 + i // 4
        minute = (i % 4) * 15
        o = 100 + i
        bars.append(("AAPL", _dt(day, hour, minute), "15min", o, o + 2, o - 1, o + 0.5, 1000 + i))
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)", bars)

    pub = f"{day.isoformat()}T12:00:00+0000"
    news = [
        (1, "AAPL", "Apple earnings beat estimates", "strong iPhone demand", "http://a",
         "Reuters", "polygon", pub, "h1"),
        (2, "NVDA", "Nvidia unveils new AI chip", "datacenter growth", "http://b",
         "Bloomberg", "finnhub", pub, "h2"),
        (3, "AAPL", "Apple services revenue grows", "App Store momentum", "http://c",
         "WSJ", "polygon", pub, "h3"),
    ]
    conn.executemany("INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?)", news)
    conn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")

    # iv_history: two AAPL snapshots (ASC order check) + one NVDA
    iv = [
        (1, "AAPL", "2026-05-01", 0.25, 0.20, 0.05, 101.0, 12),
        (2, "AAPL", "2026-05-02", 0.26, 0.21, 0.05, 102.0, 14),
        (3, "NVDA", "2026-05-01", 0.45, 0.40, 0.05, 904.0, 30),
    ]
    conn.executemany("INSERT INTO iv_history VALUES (?,?,?,?,?,?,?,?)", iv)
    # fundamentals: AAPL has two snapshots — latest (DESC) must win; reports JSON shape
    fund = [
        (1, "AAPL", "2026-05-01", '{"reports": {"ReportSnapshot": {"Name": "STALE"}}}'),
        (2, "AAPL", "2026-05-02",
         '{"reports": {"ReportSnapshot": {"Name": "Apple Inc"}, '
         '"ReportsFinSummary": {"rev": 1}, "ReportsOwnership": {"inst": 0.6}}}'),
        (3, "NVDA", "2026-05-01", '{"reports": {"ReportSnapshot": {"Name": "NVIDIA"}}}'),
    ]
    conn.executemany("INSERT INTO fundamentals VALUES (?,?,?,?)", fund)
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
    b = SqliteBackend(db)
    assert b.get_available_tickers("prices") == ["AAPL"]
    assert b.get_available_tickers("news") == ["AAPL", "NVDA"]          # 3b: news local
    assert b.get_available_tickers("iv_history") == ["AAPL", "NVDA"]    # 3c-A
    assert b.get_available_tickers("fundamentals") == ["AAPL", "NVDA"]  # 3c-A
    assert b.get_available_tickers("options") == []                     # unknown → empty


# --- news (3b): unscored reads + FTS5 search ---------------------------------

_NEWS_COLS = ["date", "ticker", "title", "source", "url", "publisher",
              "sentiment_score", "risk_score", "scored_model", "description"]


def test_query_news_unscored(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    df = b.query_news(ticker="aapl", days=30, scored_only=False)
    assert list(df.columns) == _NEWS_COLS
    assert len(df) == 2  # two AAPL articles
    assert set(df["ticker"]) == {"AAPL"}
    assert df["sentiment_score"].isna().all()  # local has no scores


def test_query_news_scored_returns_empty(market_db):
    # scored_only / model can't be served locally → empty (caller falls back to PG)
    db, _ = market_db
    b = SqliteBackend(db)
    assert b.query_news(ticker="AAPL", scored_only=True).empty
    assert b.query_news(ticker="AAPL", scored_only=False, model="gpt_5").empty


def test_query_news_search_fts5(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    # FTS match (>=3 chars) — "Nvidia" only in the NVDA article
    df = b.query_news_search(query="Nvidia", days=30, scored_only=False)
    assert len(df) == 1 and df.iloc[0]["ticker"] == "NVDA"
    # multi-hit term
    df = b.query_news_search(query="Apple", days=30, scored_only=False)
    assert len(df) == 2 and set(df["ticker"]) == {"AAPL"}
    # scored_only → empty (PG fallback)
    assert b.query_news_search(query="Apple", scored_only=True).empty


def test_query_news_search_like_fallback_short_query(market_db):
    # <3 chars → LIKE fallback (no FTS); "AI" appears in the Nvidia article body/title
    db, _ = market_db
    df = SqliteBackend(db).query_news_search(query="AI", days=30, scored_only=False)
    assert len(df) >= 1 and "NVDA" in set(df["ticker"])


def test_query_news_search_malicious_fts_query_is_safe(market_db):
    # FTS5 operator characters must not raise (phrase-quoted)
    db, _ = market_db
    df = SqliteBackend(db).query_news_search(query='Apple OR "x', days=30, scored_only=False)
    assert isinstance(df, pd.DataFrame)  # no sqlite OperationalError


# --- iv_history + fundamentals (3c-A) ----------------------------------------

_IV_COLS = ["date", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes"]


def test_query_iv_history(market_db):
    db, _ = market_db
    df = SqliteBackend(db).query_iv_history("aapl")  # case-insensitive
    assert list(df.columns) == _IV_COLS
    assert len(df) == 2
    assert list(df["date"]) == ["2026-05-01", "2026-05-02"]  # ASC order
    assert df.iloc[0]["atm_iv"] == 0.25 and df.iloc[-1]["spot_price"] == 102.0


def test_query_iv_history_empty(market_db, tmp_path):
    db, _ = market_db
    assert SqliteBackend(db).query_iv_history("NOPE").empty            # unknown ticker
    assert list(SqliteBackend(db).query_iv_history("NOPE").columns) == _IV_COLS
    assert SqliteBackend(str(tmp_path / "nope.db")).query_iv_history("AAPL").empty  # no DB


def test_query_fundamentals_latest_snapshot(market_db):
    db, _ = market_db
    out = SqliteBackend(db).query_fundamentals("aapl")
    assert out["ticker"] == "AAPL"
    assert out["collected_at"] == "2026-05-02"            # latest snapshot wins (DESC)
    assert out["snapshot"] == {"Name": "Apple Inc"}       # not the STALE one
    assert out["fin_summary"] == {"rev": 1}
    assert out["ownership"] == {"inst": 0.6}


def test_query_fundamentals_partial_and_empty(market_db, tmp_path):
    db, _ = market_db
    # NVDA snapshot has only ReportSnapshot → fin_summary/ownership default to {}
    nvda = SqliteBackend(db).query_fundamentals("NVDA")
    assert nvda["snapshot"] == {"Name": "NVIDIA"}
    assert nvda["fin_summary"] == {} and nvda["ownership"] == {}
    # unknown ticker / missing DB → empty dict (caller falls back to PG)
    assert SqliteBackend(db).query_fundamentals("NOPE") == {}
    assert SqliteBackend(str(tmp_path / "nope.db")).query_fundamentals("AAPL") == {}


def test_query_fundamentals_same_day_tiebreak_by_id(market_db):
    # Two snapshots on the SAME snapshot_date → the higher id wins deterministically
    # (ORDER BY snapshot_date DESC, id DESC), matching the PG path.
    db, _ = market_db
    conn = sqlite3.connect(db)
    conn.executemany("INSERT INTO fundamentals VALUES (?,?,?,?)", [
        (10, "TIE", "2026-05-05", '{"reports": {"ReportSnapshot": {"Name": "older same-day"}}}'),
        (11, "TIE", "2026-05-05", '{"reports": {"ReportSnapshot": {"Name": "newer same-day"}}}'),
    ])
    conn.commit()
    conn.close()
    out = SqliteBackend(db).query_fundamentals("TIE")
    assert out["snapshot"] == {"Name": "newer same-day"}  # higher id wins


# --- financial_cache (3c-C): local-primary read/write -------------------------

def test_financial_cache_roundtrip(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    assert b.get_financial_cache("metrics_AAPL") is None              # miss
    assert b.set_financial_cache("metrics_AAPL", "aapl", {"standard": {"pe": 30}}) is True
    assert b.get_financial_cache("metrics_AAPL") == {"standard": {"pe": 30}}
    # upsert overwrites in place (same cache_key)
    assert b.set_financial_cache("metrics_AAPL", "aapl", {"standard": {"pe": 31}}) is True
    assert b.get_financial_cache("metrics_AAPL") == {"standard": {"pe": 31}}


def test_financial_cache_expiry(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    # explicit past expiry → reads as a miss (caller falls back to PG)
    assert b.set_financial_cache("k", "AAPL", {"x": 1}, expires_at="2000-01-01T00:00:00+00:00") is True
    assert b.get_financial_cache("k") is None


def test_financial_cache_missing_table_is_safe(tmp_path):
    # a pre-3c-C DB without the financial_cache table → get returns None (no raise)
    db = tmp_path / "bare.db"
    sqlite3.connect(str(db)).close()
    assert SqliteBackend(str(db)).get_financial_cache("k") is None


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
    assert b.get_available_tickers("prices") == ["AAPL"]              # local
    assert b.get_available_tickers("news") == ["AAPL", "NVDA"]        # local (3b)
    assert b.get_available_tickers("iv_history") == ["AAPL", "NVDA"]  # local (3c-A)
    assert b.get_available_tickers("fundamentals") == ["AAPL", "NVDA"]  # local (3c-A)
    assert b.get_available_tickers("options") == ["PGONLY"]          # non-local → PG (super)


def test_iv_history_local_then_pg_fallback(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    pg = pd.DataFrame([("2020-01-01", 0.1, 0.1, 0.0, 1.0, 1)], columns=_IV_COLS)
    monkeypatch.setattr(DatabaseBackend, "query_iv_history",
                        lambda self, ticker: (hit.append(ticker), pg)[1])
    b = _make(db)
    df = b.query_iv_history("AAPL")          # local has AAPL → PG not hit
    assert len(df) == 2 and hit == []
    df = b.query_iv_history("UNKNOWN")        # local empty → PG fallback
    assert df.iloc[0]["date"] == "2020-01-01" and hit == ["UNKNOWN"]


def test_fundamentals_local_then_pg_fallback(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(DatabaseBackend, "query_fundamentals",
                        lambda self, ticker: (hit.append(ticker), {"ticker": ticker, "snapshot": "PG"})[1])
    b = _make(db)
    out = b.query_fundamentals("AAPL")        # local hit → PG not hit
    assert out["snapshot"] == {"Name": "Apple Inc"} and hit == []
    out = b.query_fundamentals("UNKNOWN")      # local empty {} → PG fallback
    assert out["snapshot"] == "PG" and hit == ["UNKNOWN"]


def test_financial_cache_set_is_local_only(market_db, monkeypatch):
    # local-PRIMARY: set writes the local cache and must NEVER write PG.
    db, _ = market_db
    pg_set = []
    monkeypatch.setattr(DatabaseBackend, "set_financial_cache",
                        lambda self, *a, **k: pg_set.append(1) or True)
    b = _make(db)
    assert b.set_financial_cache("mk", "AAPL", {"v": 1}, ttl_days=30, source="sec_edgar") is True
    assert pg_set == []                                       # PG never written
    assert b._market.get_financial_cache("mk") == {"v": 1}    # written local


def test_financial_cache_get_local_first(market_db, monkeypatch):
    db, _ = market_db
    pg_get = []
    monkeypatch.setattr(DatabaseBackend, "get_financial_cache",
                        lambda self, k: pg_get.append(k) or {"v": "PG"})
    b = _make(db)
    b._market.set_financial_cache("mk", "AAPL", {"v": "LOCAL"})
    assert b.get_financial_cache("mk") == {"v": "LOCAL"} and pg_get == []  # PG skipped on local hit


def test_financial_cache_pg_fallback_and_promotion(market_db, monkeypatch):
    # local miss → PG fallback → read-through promote into local (preserving PG TTL).
    db, _ = market_db
    monkeypatch.setattr(DatabaseBackend, "get_financial_cache", lambda self, k: {"v": "fromPG"})
    monkeypatch.setattr(
        LocalMarketDatabaseBackend, "_pg_financial_cache_row",
        lambda self, ck: ("sec_edgar", "NVDA", "2026-06-01T00:00:00+00:00", "2099-01-01T00:00:00+00:00"),
    )
    b = _make(db)
    assert b.get_financial_cache("mk_NVDA") == {"v": "fromPG"}        # PG fallback
    # promoted into local with PG's (future) expiry → now a local hit
    assert b._market.get_financial_cache("mk_NVDA") == {"v": "fromPG"}


def test_inherited_vs_overridden_methods(market_db):
    # market-domain reads + the local-primary financial_cache are overridden;
    # everything else (SA/reports/memories/stats) is inherited PG behaviour.
    db, _ = market_db
    b = _make(db)
    assert type(b).query_prices is not DatabaseBackend.query_prices
    assert type(b).query_news is not DatabaseBackend.query_news
    assert type(b).query_news_search is not DatabaseBackend.query_news_search
    assert type(b).query_iv_history is not DatabaseBackend.query_iv_history       # 3c-A
    assert type(b).query_fundamentals is not DatabaseBackend.query_fundamentals   # 3c-A
    assert type(b).get_financial_cache is not DatabaseBackend.get_financial_cache  # 3c-C
    assert type(b).set_financial_cache is not DatabaseBackend.set_financial_cache  # 3c-C
    assert type(b).query_news_stats is DatabaseBackend.query_news_stats  # NOT overridden (needs scores)


def test_news_local_unscored_scored_falls_back(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend, "query_news",
        lambda self, **k: (hit.append(k.get("scored_only")),
                           pd.DataFrame([("PGNEWS",)], columns=["ticker"]))[1],
    )
    b = _make(db)
    # unscored → local (2 AAPL articles), PG not hit
    df = b.query_news(ticker="AAPL", days=30, scored_only=False)
    assert len(df) == 2 and hit == []
    # scored → local empty → PG fallback
    df = b.query_news(ticker="AAPL", days=30, scored_only=True)
    assert df.iloc[0]["ticker"] == "PGNEWS" and hit == [True]
