"""Tests for SqliteBackend and the current local market composition."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.tools.backends.sqlite_backend import SqliteBackend
from src.tools.backends.local_market_backend import LocalMarketBackend
from src.news_normalized.schema import ensure_news_normalized_schema

_COLS = ["datetime", "open", "high", "low", "close", "volume"]


def _dt(day: date, hour: int, minute: int) -> str:
    return f"{day.isoformat()}T{hour:02d}:{minute:02d}:00+0000"


@pytest.fixture()
def market_db(tmp_path):
    """A market_data.db with 15min bars, news (FTS5), and fundamentals."""
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
    # Unknown ticker returns an honest empty frame.
    assert SqliteBackend(db).query_prices("NOPE", days=30).empty
    # out-of-window (days=0 → cutoff today, bars are 2 days old) → empty
    assert SqliteBackend(db).query_prices("AAPL", days=0).empty
    # missing DB file → empty (no raise)
    assert SqliteBackend(str(tmp_path / "nope.db")).query_prices("AAPL").empty


def test_get_available_tickers(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    _store_positive_sec_fundamentals(b, "AAPL", "NVDA")
    assert b.get_available_tickers("prices") == ["AAPL"]
    assert b.get_available_tickers("news") == ["AAPL", "NVDA"]          # 3b: news local
    assert b.get_available_tickers("fundamentals") == ["AAPL", "NVDA"]  # 3c-A
    assert b.get_available_tickers("options") == []                     # unknown → empty


# --- news (3b): unscored reads + FTS5 search ---------------------------------

_NEWS_COLS = ["date", "ticker", "title", "source", "url", "publisher", "description"]


def test_query_news_unscored(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    df = b.query_news(ticker="aapl", days=30)
    assert list(df.columns) == _NEWS_COLS
    assert len(df) == 2  # two AAPL articles
    assert set(df["ticker"]) == {"AAPL"}


def test_query_news_search_fts5(market_db):
    db, _ = market_db
    b = SqliteBackend(db)
    # FTS match (>=3 chars) — "Nvidia" only in the NVDA article
    df = b.query_news_search(query="Nvidia", days=30)
    assert len(df) == 1 and df.iloc[0]["ticker"] == "NVDA"
    # multi-hit term
    df = b.query_news_search(query="Apple", days=30)
    assert len(df) == 2 and set(df["ticker"]) == {"AAPL"}


def test_query_news_search_like_fallback_short_query(market_db):
    # <3 chars → LIKE fallback (no FTS); "AI" appears in the Nvidia article body/title
    db, _ = market_db
    df = SqliteBackend(db).query_news_search(query="AI", days=30)
    assert len(df) >= 1 and "NVDA" in set(df["ticker"])


def test_query_news_search_malicious_fts_query_is_safe(market_db):
    # FTS5 operator characters must not raise (phrase-quoted)
    db, _ = market_db
    df = SqliteBackend(db).query_news_search(query='Apple OR "x', days=30)
    assert isinstance(df, pd.DataFrame)  # no sqlite OperationalError


def test_query_news_stats_unscored_local_counts(market_db):
    db, day = market_db
    df = SqliteBackend(db).query_news_stats(ticker="aapl", days=30)
    assert list(df.columns) == ["ticker", "article_count", "earliest_date", "latest_date"]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["ticker"] == "AAPL"
    assert int(row["article_count"]) == 2
    assert row["earliest_date"] == day.isoformat()
    assert row["latest_date"] == day.isoformat()


# --- fundamentals (3c-A) ----------------------------------------------------


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
    # Unknown ticker or missing storage returns an honest empty dict.
    assert SqliteBackend(db).query_fundamentals("NOPE") == {}
    assert SqliteBackend(str(tmp_path / "nope.db")).query_fundamentals("AAPL") == {}


def test_query_fundamentals_same_day_tiebreak_by_id(market_db):
    # Two snapshots on the SAME snapshot_date → the higher id wins deterministically
    # (ORDER BY snapshot_date DESC, id DESC).
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
    # Explicit past expiry reads as a miss.
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


# --- LocalMarketBackend composition ------------------------------------------


def _make(db):
    return LocalMarketBackend(market_db=db)


def _store_positive_sec_fundamentals(backend, *tickers):
    from src.fundamentals.cache import fundamentals_analysis_cache_key
    from src.tools.schemas import FundamentalsResult

    writer = getattr(backend, "_market", backend)
    for ticker in tickers:
        assert writer.set_financial_cache(
            fundamentals_analysis_cache_key(ticker),
            ticker,
            FundamentalsResult(
                ticker=ticker,
                data_source="sec_edgar",
                snapshot_date="2026-05-02",
            ).model_dump(),
            source="sec_edgar",
            expires_at="2099-01-01T00:00:00+00:00",
        )




def test_prices_local_when_present(market_db):
    db, _ = market_db
    df = _make(db).query_prices("AAPL", interval="15min", days=30)
    assert len(df) == 8


def test_prices_miss_is_honest_empty(market_db):
    db, _ = market_db
    df = _make(db).query_prices("UNKNOWN", days=30)
    assert df.empty


def test_available_tickers_routing(market_db):
    db, _ = market_db
    b = _make(db)
    _store_positive_sec_fundamentals(b, "AAPL", "NVDA")
    assert b.get_available_tickers("prices") == ["AAPL"]              # local
    assert b.get_available_tickers("news") == ["AAPL", "NVDA"]        # local (3b)
    assert b.get_available_tickers("fundamentals") == ["AAPL", "NVDA"]  # local (3c-A)
    assert b.get_available_tickers("options") == []


def test_available_price_tickers_empty_is_honest_empty(tmp_path):
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE prices (ticker TEXT, datetime TEXT, interval TEXT, "
        "open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
    )
    conn.close()
    assert _make(str(db)).get_available_tickers("prices") == []


def test_fundamentals_query_is_honest_empty_without_a_current_snapshot(market_db):
    db, _ = market_db
    b = _make(db)

    assert b.query_fundamentals("AAPL") == {}
    assert b.query_fundamentals("UNKNOWN") == {}


def test_financial_cache_set_is_local_only(market_db):
    db, _ = market_db
    b = _make(db)
    assert b.set_financial_cache("mk", "AAPL", {"v": 1}, ttl_days=30, source="sec_edgar") is True
    assert b._market.get_financial_cache("mk") == {"v": 1}


def test_financial_cache_get_local_first(market_db):
    db, _ = market_db
    b = _make(db)
    b._market.set_financial_cache("mk", "AAPL", {"v": "LOCAL"})
    assert b.get_financial_cache("mk") == {"v": "LOCAL"}


def test_financial_cache_miss_is_honest_empty(market_db):
    db, _ = market_db
    b = _make(db)

    assert b.get_financial_cache("mk_NVDA") is None
    assert b._market.get_financial_cache("mk_NVDA") is None


def test_provenance_fundamentals_records_none_after_mirror_retirement(
    market_db,
):
    from src.tools.backends import provenance

    db, _ = market_db
    b = _make(db)

    provenance.reset()
    assert b.query_fundamentals("AAPL") == {}
    assert provenance.read("fundamentals") == "none"
    provenance.reset(); b.query_fundamentals("UNKNOWN")
    assert b.query_fundamentals("UNKNOWN") == {}
    assert provenance.read("fundamentals") == "none"


def test_inherited_vs_overridden_methods(market_db):
    db, _ = market_db
    b = _make(db)
    assert type(b) is LocalMarketBackend
    assert not hasattr(b, "_dsn")
    assert not hasattr(b, "_get_conn")
    assert callable(b.query_prices)
    assert callable(b.query_news)
    assert callable(b.query_news_search)
    assert callable(b.query_fundamentals)
    assert callable(b.get_financial_cache)
    assert callable(b.set_financial_cache)
    assert callable(b.query_news_stats)


def test_news_stats_reads_local_rows_when_present(market_db):
    db, day = market_db
    df = _make(db).query_news_stats(ticker="AAPL", days=30)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["ticker"] == "AAPL"
    assert int(row["article_count"]) == 2
    assert row["earliest_date"] == day.isoformat()


def test_news_stats_local_empty_is_honest_empty(market_db):
    db, _ = market_db
    df = _make(db).query_news_stats(ticker="SNEX", days=30)
    assert df.empty


# --- 新聞·事件 feed (score-free browse/search + facets) ------------------------

def test_fts_search_is_tokenized_and(market_db):
    # Multi-word queries AND the tokens instead of exact-phrase matching:
    # "earnings apple" matches "Apple earnings
    # beat estimates" even though the words are not adjacent / ordered.
    db, _ = market_db
    b = SqliteBackend(db)
    df = b.query_news_search(query="earnings apple", days=30)
    assert len(df) == 1 and df.iloc[0]["ticker"] == "AAPL"
    # operator characters still neutralized per token
    df2 = b.query_news_search(query='apple OR "x AND (', days=30)
    assert isinstance(df2, pd.DataFrame)  # no OperationalError


def test_news_feed_browse_and_facets(market_db):
    db, day = market_db
    f = SqliteBackend(db).query_news_feed(days=30)
    assert f["available"] is True and f["total"] == 3
    assert f["sources"] == {"polygon": 2, "finnhub": 1}
    assert f["days"] == {day.isoformat(): 3}
    assert f["content_counts"] == {
        "full": 0,
        "headline_only": 0,
        "unknown": 3,
    }
    assert len(f["items"]) == 3
    assert {
        (item["content_availability"], item["content_recovery"])
        for item in f["items"]
    } == {("unknown", None)}
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
    assert f["content_counts"] == {
        "full": 0,
        "headline_only": 0,
        "unknown": 0,
    }


def test_news_feed_local_authoritative_vs_pre3b_fallback(market_db):
    # A readable local table is authoritative; zero matches is an honest zero.
    db, _ = market_db
    b = _make(db)
    f = b.query_news_feed(q="zzz_no_match_zzz", days=30)
    assert f["total"] == 0

    b2 = LocalMarketBackend(market_db="/nonexistent/x.db")
    f2 = b2.query_news_feed(days=30)
    assert f2["available"] is False
    assert f2["total"] == 0


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


# --- health_stats local recompute --------------------------------------------

def test_query_health_stats_local_shape(market_db):
    # SqliteBackend recomputes the current health shape
    # query_health_stats returns directly from market_data.db.
    db, _ = market_db
    stats = SqliteBackend(db).query_health_stats()
    assert set(stats) == {"news", "prices", "financial_cache"}
    assert all(stats[k]["error"] is None for k in stats)
    assert stats["prices"]["rows"][0][0] is not None              # MAX(datetime)
    news_rows = stats["news"]["rows"]
    assert news_rows and all(len(r) == 3 for r in news_rows)      # (source, latest, recent_count)
    assert stats["financial_cache"]["rows"] == []                 # fixture has no fin cache → honest empty


def test_health_stats_local_first(market_db):
    db, _ = market_db
    stats = _make(db).query_health_stats()
    assert set(stats) == {"news", "prices", "financial_cache"}


# --- local-only composition --------------------------------------------------


def test_local_market_serves_local_rows(market_db):
    db, _ = market_db
    b = LocalMarketBackend(market_db=db)
    assert len(b.query_prices("AAPL", days=30)) == 8
    assert b.get_available_tickers("prices") == ["AAPL"]
    assert not b.query_news(ticker="AAPL").empty
    assert set(b.query_health_stats()) == {"news", "prices", "financial_cache"}


def test_local_market_miss_is_honest_empty(market_db):
    db, _ = market_db
    b = LocalMarketBackend(market_db=db)
    assert b.query_prices("ZZZZ", days=30).empty
    assert b.query_fundamentals("ZZZZ") in ({}, None)
    assert b.get_financial_cache("nope:key") is None
    assert b.get_available_tickers("options") == []


def test_price_reads_are_local_regardless_of_provenance_toggle(market_db):
    db, _ = market_db
    b = LocalMarketBackend(market_db=db)
    assert b.query_prices("UNKNOWN").empty


def test_news_hard_local_does_not_make_market_strict(market_db):
    db, _ = market_db
    b = LocalMarketBackend(market_db=db)
    assert b.query_news(ticker="ZZZZ").empty
    assert b.query_news_search(query="notpresent").empty
    assert b.query_news_feed(q="notpresent")["total"] == 0
    assert b.query_news_stats(ticker="ZZZZ").empty

    assert b.query_prices("UNKNOWN").empty
    assert b.query_fundamentals("UNKNOWN") == {}


def test_news_available_tickers_empty_is_honest_empty(tmp_path):
    db = tmp_path / "empty_news.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT, title TEXT, "
        "description TEXT, url TEXT, publisher TEXT, source TEXT, published_at TEXT, "
        "article_hash TEXT)"
    )
    conn.commit()
    conn.close()

    b = LocalMarketBackend(market_db=str(db))

    assert b.get_available_tickers("news") == []


def test_news_feed_local_exception_returns_typed_unavailable(market_db, monkeypatch):
    db, _ = market_db
    b = LocalMarketBackend(market_db=db)
    monkeypatch.setattr(
        b._market,
        "query_news_feed",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("local feed failed")),
    )

    feed = b.query_news_feed(q="Apple")

    assert feed == {
        "available": False,
        "items": [],
        "total": 0,
        "sources": {},
        "days": {},
        "content_counts": {"full": 0, "headline_only": 0, "unknown": 0},
    }


def test_sa_capture_backend_threads_strict(market_db, tmp_path, monkeypatch):
    from src.tools.backends.sa_capture_backend import SACaptureBackend
    db, _ = market_db
    sa_db = tmp_path / "sa.db"  # empty SA db is fine; we exercise the market path
    sqlite3.connect(sa_db).close()
    b = SACaptureBackend(sa_db=str(sa_db), market_db=db, base_path=tmp_path)
    assert len(b.query_prices("AAPL", days=30)) == 8
    assert b.query_prices("ZZZZ", days=30).empty




def test_strict_news_feed_exception_returns_full_shape_not_thin(market_db, monkeypatch):
    # On a NON-OperationalError local failure, the strict feed fallback must still be the
    # CANONICAL full shape — News.tsx reads feed.total/feed.sources BEFORE the available
    # guard, so a thin {available:false} would crash the News tab.
    db, _ = market_db
    b = LocalMarketBackend(market_db=db)

    def _boom(**k):
        raise RuntimeError("corrupt local db")
    monkeypatch.setattr(b._market, "query_news_feed", _boom)

    feed = b.query_news_feed(q="x")
    assert set(feed) >= {
        "available",
        "items",
        "total",
        "sources",
        "days",
        "content_counts",
    }  # full shape, not thin
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
