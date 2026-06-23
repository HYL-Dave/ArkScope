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
    # scored_only / model with NO local sentiment → empty (news_scores RETIRED; honest empty)
    db, _ = market_db
    b = SqliteBackend(db)
    assert b.query_news(ticker="AAPL", scored_only=True).empty
    assert b.query_news(ticker="AAPL", scored_only=False, model="gpt_5").empty


def test_query_news_surfaces_local_sentiment_when_present(tmp_path):
    # news_scores RETIRED → local-first sentiment: when the local news table carries a
    # 1-5 sentiment_score, scored_only=True returns ONLY the scored rows from LOCAL.
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, title TEXT NOT NULL, "
        "description TEXT, url TEXT, publisher TEXT, source TEXT NOT NULL, published_at TEXT NOT NULL, "
        "article_hash TEXT, sentiment_score REAL, sentiment_source TEXT, sentiment_scale TEXT);"
    )
    pub = f"{date.today().isoformat()}T00:00:00+0000"
    conn.execute("INSERT INTO news VALUES (1,'AAPL','scored','d','u','p','polygon',?, 'h1', 4.0, 'llm', '1-5')", (pub,))
    conn.execute("INSERT INTO news VALUES (2,'AAPL','unscored','d','u','p','polygon',?, 'h2', NULL, NULL, NULL)", (pub,))
    conn.commit()
    conn.close()
    b = SqliteBackend(db)

    scored = b.query_news(ticker="AAPL", scored_only=True)
    assert len(scored) == 1 and float(scored.iloc[0]["sentiment_score"]) == 4.0  # only the scored row, from local
    assert b.query_news(ticker="AAPL", scored_only=False).shape[0] == 2          # all rows, score surfaced


def test_query_news_scored_no_pg_fallback(market_db, monkeypatch):
    # news_scores RETIRED: a scored request has NO PG authority → honest local result,
    # never a PG fallback. (Unscored local-miss MAY still fall back until strict mode.)
    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend, "query_news",
        lambda self, ticker=None, days=30, source="auto", scored_only=True, model=None:
            (hit.append("PG"), _PG_SENTINEL)[1],
    )
    b = _make(db)
    assert b.query_news(ticker="AAPL", scored_only=True).empty   # local has no scores → honest empty
    assert hit == []                                             # scored → NEVER hits PG
    b.query_news(ticker="AAPL", scored_only=False, model="gpt_5")
    assert hit == []                                             # specific model also score-dep → no PG
    b.query_news(ticker="ZZZZ", scored_only=False)               # unscored local miss → transition fallback
    assert hit == ["PG"]


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


def test_query_news_stats_unscored_local_counts(market_db):
    db, day = market_db
    df = SqliteBackend(db).query_news_stats(ticker="aapl", days=30)
    assert list(df.columns) == [
        "ticker", "article_count", "scored_count", "earliest_date", "latest_date",
        "avg_sentiment", "avg_risk", "bullish_count", "bearish_count",
    ]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["ticker"] == "AAPL"
    assert int(row["article_count"]) == 2
    assert int(row["scored_count"]) == 0
    assert row["earliest_date"] == day.isoformat()
    assert row["latest_date"] == day.isoformat()
    assert pd.isna(row["avg_sentiment"])
    assert pd.isna(row["avg_risk"])
    assert int(row["bullish_count"]) == 0
    assert int(row["bearish_count"]) == 0


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


def test_set_financial_cache_serialized_by_lock(market_db):
    # set_financial_cache must take _CACHE_WRITE_LOCK so it serializes against a
    # bootstrap's read-old→swap→write-carried section (else a cache write racing a
    # rebuild is dropped). Deterministic proof: hold the lock → the write blocks;
    # release → it completes.
    import threading
    import time as _time
    import src.market_data_admin as mda
    db, _ = market_db
    b = SqliteBackend(db)
    done = threading.Event()

    def writer():
        b.set_financial_cache("LOCKED", "AAPL", {"v": 1})
        done.set()

    with mda._CACHE_WRITE_LOCK:                 # simulate bootstrap holding it
        t = threading.Thread(target=writer, daemon=True)
        t.start()
        assert not done.wait(timeout=0.5)       # blocked while we hold the lock
        assert b.get_financial_cache("LOCKED") is None  # nothing written yet
    assert done.wait(timeout=5)                 # released → completes
    t.join(timeout=5)
    assert b.get_financial_cache("LOCKED") == {"v": 1}


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


def test_provenance_iv_recorded(market_db, monkeypatch):
    # LocalMarketDatabaseBackend records the TRUE per-call origin of the IV read.
    from src.tools.backends import provenance
    db, _ = market_db
    b = _make(db)
    provenance.reset(); b.query_iv_history("AAPL")           # local has AAPL
    assert provenance.read("iv") == "local"
    monkeypatch.setattr(  # local miss → PG returns data → pg_fallback
        DatabaseBackend, "query_iv_history",
        lambda self, t: pd.DataFrame([["2026-01-01", 0.3, 0.2, 0.1, 1.0, 5]], columns=_IV_COLS))
    provenance.reset(); b.query_iv_history("UNKNOWN")
    assert provenance.read("iv") == "pg_fallback"
    monkeypatch.setattr(  # local miss → PG empty → none
        DatabaseBackend, "query_iv_history", lambda self, t: pd.DataFrame(columns=_IV_COLS))
    provenance.reset(); b.query_iv_history("UNKNOWN")
    assert provenance.read("iv") == "none"


def test_provenance_fundamentals_recorded(market_db, monkeypatch):
    from src.tools.backends import provenance
    db, _ = market_db
    b = _make(db)
    provenance.reset(); b.query_fundamentals("AAPL")          # local has AAPL
    assert provenance.read("fundamentals") == "local"
    monkeypatch.setattr(DatabaseBackend, "query_fundamentals",
                        lambda self, t: {"ticker": t, "snapshot": {"x": 1}})
    provenance.reset(); b.query_fundamentals("UNKNOWN")
    assert provenance.read("fundamentals") == "pg_fallback"
    monkeypatch.setattr(DatabaseBackend, "query_fundamentals", lambda self, t: {})
    provenance.reset(); b.query_fundamentals("UNKNOWN")
    assert provenance.read("fundamentals") == "none"


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
    assert type(b).query_news_stats is not DatabaseBackend.query_news_stats  # local scout stats


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
    # scored → news_scores RETIRED → honest local empty, PG NOT hit (no scored authority)
    df = b.query_news(ticker="AAPL", days=30, scored_only=True)
    assert df.empty and hit == []


def test_news_stats_local_when_present_does_not_hit_pg(market_db, monkeypatch):
    db, day = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend,
        "query_news_stats",
        lambda self, ticker=None, days=30: hit.append(ticker) or pd.DataFrame(
            [("PGONLY", 99, 99, "2000-01-01", "2000-01-01", 1.0, 1.0, 1, 1)],
            columns=[
                "ticker", "article_count", "scored_count", "earliest_date", "latest_date",
                "avg_sentiment", "avg_risk", "bullish_count", "bearish_count",
            ],
        ),
    )
    df = _make(db).query_news_stats(ticker="AAPL", days=30)
    assert hit == []
    assert len(df) == 1
    row = df.iloc[0]
    assert row["ticker"] == "AAPL"
    assert int(row["article_count"]) == 2
    assert row["earliest_date"] == day.isoformat()
    assert pd.isna(row["avg_sentiment"])


def test_news_stats_local_empty_does_not_fallback_to_pg(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend,
        "query_news_stats",
        lambda self, ticker=None, days=30: hit.append(ticker) or pd.DataFrame(
            [("PGONLY", 99, 99, "2000-01-01", "2000-01-01", 1.0, 1.0, 1, 1)],
            columns=[
                "ticker", "article_count", "scored_count", "earliest_date", "latest_date",
                "avg_sentiment", "avg_risk", "bullish_count", "bearish_count",
            ],
        ),
    )
    df = _make(db).query_news_stats(ticker="SNEX", days=30)
    assert hit == []
    assert df.empty


# --- 新聞·事件 feed (score-free browse/search + facets) ------------------------

def test_fts_search_is_tokenized_and(market_db):
    # Multi-word queries AND the tokens (parity with PG plainto_tsquery) instead
    # of the old exact-phrase match: "earnings apple" matches "Apple earnings
    # beat estimates" even though the words are not adjacent / ordered.
    db, _ = market_db
    b = SqliteBackend(db)
    df = b.query_news_search(query="earnings apple", days=30, scored_only=False)
    assert len(df) == 1 and df.iloc[0]["ticker"] == "AAPL"
    # operator characters still neutralized per token
    df2 = b.query_news_search(query='apple OR "x AND (', days=30, scored_only=False)
    assert isinstance(df2, pd.DataFrame)  # no OperationalError


def test_news_feed_browse_and_facets(market_db):
    db, day = market_db
    f = SqliteBackend(db).query_news_feed(days=30)
    assert f["available"] is True and f["total"] == 3
    assert f["sources"] == {"polygon": 2, "finnhub": 1}
    assert f["days"] == {day.isoformat(): 3}
    assert len(f["items"]) == 3
    # newest first, FULL timestamps
    assert f["items"][0]["published_at"].endswith("+0000")
    assert "T" in f["items"][0]["published_at"]


def test_news_feed_filters_and_pagination(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    f = b.query_news_feed(ticker="AAPL", days=30)
    assert f["total"] == 2 and {i["ticker"] for i in f["items"]} == {"AAPL"}
    f = b.query_news_feed(source="finnhub", days=30)
    assert f["total"] == 1 and f["items"][0]["source"] == "finnhub"
    page = b.query_news_feed(days=30, limit=2, offset=2)
    assert page["total"] == 3 and len(page["items"]) == 1  # last page


def test_news_feed_search(market_db):
    db, _ = market_db
    f = SqliteBackend(db).query_news_feed(q="nvidia chip", days=30)
    assert f["total"] == 1 and f["items"][0]["ticker"] == "NVDA"
    assert f["sources"] == {"finnhub": 1}  # facets respect the query


def test_news_feed_missing_table_not_available(tmp_path):
    db = tmp_path / "bare.db"
    sqlite3.connect(str(db)).close()
    f = SqliteBackend(str(db)).query_news_feed()
    assert f["available"] is False and f["items"] == []


def test_news_feed_local_authoritative_vs_pre3b_fallback(market_db, monkeypatch):
    # Local DB with a news table is AUTHORITATIVE: zero matches is an honest
    # zero, not a PG-fallback trigger. Only available=False (pre-3b DB) falls back.
    db, _ = market_db
    pg_called = []
    monkeypatch.setattr(
        DatabaseBackend, "query_news_feed",
        lambda self, **k: (pg_called.append(1),
                           {"available": True, "items": [], "total": 99,
                            "sources": {}, "days": {}})[1])
    b = _make(db)
    f = b.query_news_feed(q="zzz_no_match_zzz", days=30)
    assert f["total"] == 0 and pg_called == []   # honest zero, PG not consulted

    b2 = LocalMarketDatabaseBackend("postgresql://fake/db", market_db="/nonexistent/x.db")
    f2 = b2.query_news_feed(days=30)
    assert f2["total"] == 99 and pg_called == [1]  # pre-3b → PG fallback


def test_news_feed_search_relevance_title_weighted(tmp_path):
    # Title hits must outrank passing mentions in descriptions (weighted bm25) —
    # the user's "nvidia earnings" precision complaint: newest-first put
    # description-only mentions on top.
    db = tmp_path / "rank.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE news (
            id INTEGER PRIMARY KEY, ticker TEXT, title TEXT, description TEXT,
            url TEXT, publisher TEXT, source TEXT, published_at TEXT, article_hash TEXT);
        CREATE VIRTUAL TABLE news_fts USING fts5(title, description, content='news',
            content_rowid='id', tokenize='porter unicode61');
    """)
    day = (date.today() - timedelta(days=1)).isoformat()
    conn.executemany("INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?)", [
        # NEWER article: tokens only as a passing mention in the description
        (1, "MU", "Micron upgraded on memory cycle",
         "analysts note nvidia earnings momentum spills over", "http://m",
         "X", "finnhub", f"{day}T18:00:00+0000", "m1"),
        # OLDER article: tokens in the TITLE — must rank first
        (2, "NVDA", "Nvidia earnings preview: data center in focus",
         "what to expect", "http://n", "Y", "polygon", f"{day}T08:00:00+0000", "n1"),
    ])
    conn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")
    conn.commit(); conn.close()

    f = SqliteBackend(str(db)).query_news_feed(q="nvidia earnings", days=30)
    assert f["total"] == 2
    assert f["items"][0]["ticker"] == "NVDA"   # title match first despite being older
    assert f["items"][1]["ticker"] == "MU"


def test_news_feed_description_html_cleaned(tmp_path):
    # IBKR (DJ-N) descriptions are stored as raw HTML fragments — the feed must
    # return a readable plain-text snippet (read-time cleanup, stored data verbatim).
    db = tmp_path / "html.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE news (
            id INTEGER PRIMARY KEY, ticker TEXT, title TEXT, description TEXT,
            url TEXT, publisher TEXT, source TEXT, published_at TEXT, article_hash TEXT);
        CREATE VIRTUAL TABLE news_fts USING fts5(title, description, content='news',
            content_rowid='id', tokenize='porter unicode61');
    """)
    day = (date.today() - timedelta(days=1)).isoformat()
    conn.execute("INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?)",
                 (1, "RIVN", "Rivian starts Model 3 era",
                  "<p>&#10;  By Al Root </p>&#10;<p>&#10;  Rivian has started.</p>",
                  "http://r", "DJ-N", "ibkr", f"{day}T12:00:00+0000", "r1"))
    conn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")
    conn.commit(); conn.close()

    f = SqliteBackend(str(db)).query_news_feed(days=30)
    desc = f["items"][0]["description"]
    assert "<" not in desc and "&#10;" not in desc
    assert desc == "By Al Root Rivian has started."


# --- health_stats local recompute (sub-slice B: PG-exit for provider health) ----

def test_query_health_stats_local_shape(market_db):
    # SqliteBackend recomputes the same {news,prices,iv_history,financial_cache} shape
    # query_health_stats returns, from market_data.db — so provider health stops needing PG.
    db, _ = market_db
    stats = SqliteBackend(db).query_health_stats()
    assert set(stats) == {"news", "prices", "iv_history", "financial_cache"}
    assert all(stats[k]["error"] is None for k in stats)
    assert stats["prices"]["rows"][0][0] is not None              # MAX(datetime)
    assert stats["iv_history"]["rows"][0][0] is not None          # MAX(date)
    news_rows = stats["news"]["rows"]
    assert news_rows and all(len(r) == 3 for r in news_rows)      # (source, latest, recent_count)
    assert stats["financial_cache"]["rows"] == []                 # fixture has no fin cache → honest empty


def test_health_stats_local_first(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(DatabaseBackend, "query_health_stats", lambda self: (hit.append("PG"), {})[1])
    stats = _make(db).query_health_stats()
    assert hit == []                                             # served locally, PG NOT hit
    assert set(stats) == {"news", "prices", "iv_history", "financial_cache"}


# --- review fix: query_news_search + query_news_stats local sentiment (news_scores retired) ---

def _news_db_with_sentiment(tmp_path, rows):
    """A market_data.db with a sentiment-capable news table + FTS5, populated from rows
    (id, ticker, title, desc, source, published_at, sentiment_score)."""
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, title TEXT NOT NULL, "
        "description TEXT, url TEXT, publisher TEXT, source TEXT NOT NULL, published_at TEXT NOT NULL, "
        "article_hash TEXT, sentiment_score REAL, sentiment_source TEXT, sentiment_scale TEXT);"
        "CREATE VIRTUAL TABLE news_fts USING fts5(title, description, content='news', "
        "content_rowid='id', tokenize='porter unicode61');"
    )
    for (nid, tkr, title, desc, src, pub, sent) in rows:
        conn.execute(
            "INSERT INTO news (id,ticker,title,description,url,publisher,source,published_at,"
            "article_hash,sentiment_score,sentiment_source,sentiment_scale) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (nid, tkr, title, desc, "u", "p", src, pub, f"h{nid}", sent,
             "llm" if sent is not None else None, "1-5" if sent is not None else None),
        )
    conn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    return db


def test_query_news_search_scored_no_pg_fallback(market_db, monkeypatch):
    # news_scores RETIRED: scored FTS search has no PG authority → honest empty, never PG.
    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend, "query_news_search",
        lambda self, query="", ticker=None, days=30, limit=20, scored_only=True:
            (hit.append("PG"), _PG_SENTINEL)[1],
    )
    b = _make(db)
    assert b.query_news_search(query="Apple", scored_only=True).empty   # local has no scores
    assert hit == []                                                    # scored search → NEVER PG
    b.query_news_search(query="Apple", scored_only=False)              # unscored local hit
    assert hit == []                                                    # served locally, no PG


def test_query_news_search_surfaces_local_sentiment(tmp_path):
    pub = f"{date.today().isoformat()}T00:00:00+0000"
    db = _news_db_with_sentiment(tmp_path, [
        (1, "AAPL", "Apple soars on earnings", "great quarter", "polygon", pub, 5.0),
        (2, "AAPL", "Apple unscored note", "no score", "polygon", pub, None),
    ])
    b = SqliteBackend(db)
    scored = b.query_news_search(query="Apple", scored_only=True)
    assert len(scored) == 1 and float(scored.iloc[0]["sentiment_score"]) == 5.0  # only the scored hit
    assert b.query_news_search(query="Apple", scored_only=False).shape[0] == 2   # all hits


def test_query_news_stats_aggregates_local_sentiment(tmp_path):
    pub = f"{date.today().isoformat()}T00:00:00+0000"
    db = _news_db_with_sentiment(tmp_path, [
        (1, "AAPL", "bull", "d", "polygon", pub, 5.0),   # bullish (>=4)
        (2, "AAPL", "bear", "d", "polygon", pub, 2.0),   # bearish (<=2)
        (3, "AAPL", "none", "d", "polygon", pub, None),  # unscored
    ])
    row = SqliteBackend(db).query_news_stats(ticker="AAPL").iloc[0]
    assert row["article_count"] == 3 and row["scored_count"] == 2
    assert row["avg_sentiment"] == 3.5
    assert row["bullish_count"] == 1 and row["bearish_count"] == 1


# --- strict (local-only) mode: market reads NEVER dial PG (desktop-app boot-without-PG) ---

_MARKET_PG_METHODS = (
    "query_prices", "query_news", "query_news_search", "query_news_stats", "query_news_feed",
    "query_iv_history", "query_fundamentals", "get_financial_cache", "query_health_stats",
    "get_available_tickers",
)


def _poison_pg(monkeypatch):
    """Make every market read on the PG base RAISE — so any strict-mode fallback is caught."""
    def boom(self, *a, **k):
        raise AssertionError("PG dialed in strict mode")
    for m in _MARKET_PG_METHODS:
        monkeypatch.setattr(DatabaseBackend, m, boom)


def test_strict_market_serves_local_without_pg(market_db, monkeypatch):
    db, _ = market_db
    _poison_pg(monkeypatch)
    b = LocalMarketDatabaseBackend("postgresql://unreachable/db", market_db=db, strict=True)
    # local HITS resolve from SQLite, PG never touched
    assert len(b.query_prices("AAPL", days=30)) == 8
    assert b.get_available_tickers("prices") == ["AAPL"]
    assert not b.query_news(ticker="AAPL", scored_only=False).empty
    assert set(b.query_health_stats()) == {"news", "prices", "iv_history", "financial_cache"}


def test_strict_market_local_miss_is_honest_empty_not_pg(market_db, monkeypatch):
    db, _ = market_db
    _poison_pg(monkeypatch)
    b = LocalMarketDatabaseBackend("postgresql://unreachable/db", market_db=db, strict=True)
    # local MISS → honest empty / unavailable, NOT a PG fallback (no AssertionError raised)
    assert b.query_prices("ZZZZ", days=30).empty
    assert b.query_iv_history("ZZZZ").empty
    assert b.query_fundamentals("ZZZZ") in ({}, None)
    assert b.get_financial_cache("nope:key") is None
    assert b.get_available_tickers("options") == []   # non-local type → strict empty, not PG


def test_non_strict_still_falls_back_to_pg(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(DatabaseBackend, "query_prices",
                        lambda self, ticker, interval="15min", days=30: (hit.append(ticker), _PG_SENTINEL)[1])
    b = LocalMarketDatabaseBackend("postgresql://fake/db", market_db=db, strict=False)  # default
    assert b.query_prices("UNKNOWN").iloc[0]["datetime"] == "PGSENTINEL" and hit == ["UNKNOWN"]


def test_sa_capture_backend_threads_strict(market_db, tmp_path, monkeypatch):
    from src.tools.backends.sa_capture_backend import SACaptureDatabaseBackend
    db, _ = market_db
    _poison_pg(monkeypatch)
    sa_db = tmp_path / "sa.db"  # empty SA db is fine; we exercise the market path
    sqlite3.connect(sa_db).close()
    b = SACaptureDatabaseBackend("postgresql://unreachable/db", sa_db=str(sa_db), market_db=db, strict=True)
    assert len(b.query_prices("AAPL", days=30)) == 8       # market served local
    assert b.query_prices("ZZZZ", days=30).empty           # miss → honest empty, no PG


def test_strict_uses_fast_pg_connect_timeout(market_db):
    # boot-without-PG: a residual non-market PG path (app-records, a deferred slice) must
    # FAIL FAST, not hang ~15s, when PG is unreachable. Strict → short connect_timeout.
    db, _ = market_db
    assert LocalMarketDatabaseBackend("postgresql://x/db", market_db=db, strict=True)._connect_timeout == 3
    assert LocalMarketDatabaseBackend("postgresql://x/db", market_db=db, strict=False)._connect_timeout == 15


def test_strict_news_feed_exception_returns_full_shape_not_thin(market_db, monkeypatch):
    # On a NON-OperationalError local failure, the strict feed fallback must still be the
    # CANONICAL full shape — News.tsx reads feed.total/feed.sources BEFORE the available
    # guard, so a thin {available:false} would crash the News tab.
    db, _ = market_db
    _poison_pg(monkeypatch)  # PG must NOT be dialed in strict
    b = LocalMarketDatabaseBackend("postgresql://unreachable/db", market_db=db, strict=True)

    def _boom(**k):
        raise RuntimeError("corrupt local db")
    monkeypatch.setattr(b._market, "query_news_feed", _boom)

    feed = b.query_news_feed(q="x")
    assert set(feed) >= {"available", "items", "total", "sources", "days"}  # full shape, not thin
    assert feed["available"] is False and feed["total"] == 0 and feed["sources"] == {}


# --- ticker canon resolve-on-read (strict-readiness slice #1) ----------------------

def test_query_resolves_alias_to_canonical(tmp_path):
    # A query for the alias spelling ('BRK.B') must resolve to the canonical rows
    # ('BRK B') across domains — the cross-domain join fix, resolve-on-read.
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL);"
        "CREATE TABLE prices (ticker TEXT, datetime TEXT, interval TEXT, open REAL, high REAL, "
        "low REAL, close REAL, volume INTEGER, PRIMARY KEY(ticker,datetime,interval));"
    )
    conn.execute("INSERT INTO ticker_aliases VALUES ('BRK.B','BRK B')")
    pub = f"{date.today().isoformat()}T13:30:00+0000"
    conn.execute("INSERT INTO prices VALUES ('BRK B',?,?,1,1,1,9,100)", (pub, "15min"))
    conn.commit()
    conn.close()
    b = SqliteBackend(db)
    # querying the ALIAS returns the canonical row's data
    df_alias = b.query_prices("BRK.B", interval="15min", days=5)
    df_canon = b.query_prices("BRK B", interval="15min", days=5)
    assert len(df_alias) == 1 and float(df_alias.iloc[0]["close"]) == 9.0
    assert len(df_canon) == 1  # canonical spelling still works too


def test_canon_resolver_passthrough_when_no_alias_table(market_db):
    # A pre-canon DB (no ticker_aliases table) must not break reads — resolver is a no-op.
    db, _ = market_db
    assert len(SqliteBackend(db).query_prices("AAPL", days=30)) == 8
