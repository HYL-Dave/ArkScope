"""Tests for the market_data lifecycle substrate (slice 3a.1): admin core + routes."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

import src.market_data_admin as mda
from src.news_identity import canonical_article_hash
from src.profile_state import ProfileStateStore


def _create_local_market_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(mda._PRICES_SCHEMA)
        conn.executescript(mda._NEWS_SCHEMA)
        conn.executescript(
            "CREATE TABLE fundamentals ("
            "id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, "
            "snapshot_date TEXT NOT NULL, data TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO prices "
            "(ticker, datetime, interval, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("AAPL", "2026-06-01T09:00:00+0000", "15min", 100, 102, 99, 101, 1000),
        )
        conn.execute(
            "INSERT INTO news "
            "(ticker, title, description, url, publisher, source, published_at, article_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("AAPL", "Apple beat estimates", "iPhone demand", "http://a", "Reuters",
             "polygon", "2026-06-01T12:00:00+0000", "h1"),
        )
        conn.execute(
            "INSERT INTO fundamentals (id, ticker, snapshot_date, data) VALUES (?, ?, ?, ?)",
            (1, "AAPL", "2026-06-01", '{"reports": {"ReportSnapshot": {"Name": "Apple"}}}'),
        )
        conn.commit()
    finally:
        conn.close()


# --- admin core ---------------------------------------------------------------

def test_local_stats_missing(tmp_path):
    s = mda.local_market_stats(str(tmp_path / "nope.db"))
    assert s["exists"] is False
    assert s["prices"]["row_count"] == 0 and s["news"]["row_count"] == 0


# --- 3c-C: financial_cache (local-primary; carry-over on rebuild) -------------

def test_local_stats_financial_cache_counts(tmp_path):
    from src.tools.backends.sqlite_backend import SqliteBackend
    out = str(tmp_path / "market_data.db")
    _create_local_market_db(out)
    sb = SqliteBackend(out)
    sb.set_financial_cache("valid", "AAPL", {"x": 1}, expires_at="2099-01-01T00:00:00+00:00")
    sb.set_financial_cache("expired", "AAPL", {"x": 2}, expires_at="2000-01-01T00:00:00+00:00")
    fc = mda.local_market_stats(out)["financial_cache"]
    assert fc["row_count"] == 2 and fc["valid_count"] == 1 and fc["expired_count"] == 1
    assert fc["latest_fetched_at"] is not None


def test_local_ticker_coverage(tmp_path):
    out = str(tmp_path / "market_data.db")
    # missing DB → exists False, all domains False
    cov = mda.local_ticker_coverage("AAPL", out)
    assert set(cov) == {"exists", "prices", "news", "fundamentals"}
    assert cov["exists"] is False and not any(cov[d] for d in ("prices", "news", "fundamentals"))
    _create_local_market_db(out)
    from src.fundamentals.cache import fundamentals_analysis_cache_key
    from src.tools.backends.sqlite_backend import SqliteBackend
    from src.tools.schemas import FundamentalsResult

    SqliteBackend(out).set_financial_cache(
        fundamentals_analysis_cache_key("AAPL"),
        "AAPL",
        FundamentalsResult(
            ticker="AAPL",
            data_source="sec_edgar",
            snapshot_date="2026-05-31",
        ).model_dump(),
        source="sec_edgar",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    cov = mda.local_ticker_coverage("aapl", out)  # case-insensitive
    assert cov["exists"] is True
    assert cov["prices"] and cov["news"] and cov["fundamentals"]
    absent = mda.local_ticker_coverage("ZZZZ", out)  # tracked DB, untracked ticker
    assert absent["exists"] is True
    assert not (absent["prices"] or absent["news"] or absent["fundamentals"])


# --- routes -------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    return ProfileStateStore(tmp_path / "profile_state.db")


def test_status_route_local_only(store, tmp_path, monkeypatch):
    from src.api.routes.market_data import market_data_status
    monkeypatch.setattr("src.api.routes.market_data.resolve_market_db_path",
                        lambda: str(tmp_path / "nope.db"))
    monkeypatch.setattr("src.api.routes.market_data.env_routing_enabled", lambda: False)
    out = market_data_status(store=store)
    assert out["exists"] is False
    assert out["prices"]["row_count"] == 0 and out["news"]["row_count"] == 0
    assert out["fundamentals_mode"] == "local_cache_refetch"
    assert out["use_local_market_setting"] is False
    assert out["prices_authority"] == "local"
    assert out["routing_enabled"] is True


def test_fresh_profile_uses_local_market_backend(tmp_path, monkeypatch):
    from src.tools.backends.local_market_backend import LocalMarketBackend
    from src.tools.data_access import DataAccessLayer

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    profile = data_dir / "profile_state.db"
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE profile_settings (key TEXT PRIMARY KEY, value TEXT)")

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MARKET", raising=False)
    monkeypatch.delenv("ARKSCOPE_MARKET_DB", raising=False)

    dal = DataAccessLayer(base_path=tmp_path)

    assert isinstance(dal._backend, LocalMarketBackend)
    assert not hasattr(dal._backend, "_dsn")
    assert not (data_dir / "market_data.db").exists()
    assert dal.get_prices("NVDA").bars == []


def test_status_news_sync_follows_active_writer_only(store, tmp_path, monkeypatch):
    from src.api.routes.market_data import market_data_status

    db = tmp_path / "market_data.db"
    db.write_bytes(b"")
    stored = {
        "prices": {"last_success": "p", "last_error": None, "rows_added": 1, "updated_at": "p"},
        "news": {"last_success": "stored", "last_error": None, "rows_added": 2, "updated_at": "stored"},
    }
    direct = {
        "status": "partial", "last_success": "direct", "last_attempt": "now",
        "last_error": "polygon: BAD: 403", "rows_added": 3, "updated_at": "now",
        "providers": {},
    }
    monkeypatch.setattr("src.api.routes.market_data.resolve_market_db_path", lambda: str(db))
    monkeypatch.setattr("src.api.routes.market_data.local_market_stats", lambda path: {
        "exists": True, "prices": {}, "news": {}, "iv": {}, "fundamentals": {},
        "financial_cache": {},
    })
    monkeypatch.setattr("src.api.routes.market_data.read_sync_meta", lambda path: stored)
    monkeypatch.setattr("src.news_sync_status.read_news_sync_status", lambda path: direct)

    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: False)
    off = market_data_status(store=store)
    assert off["fundamentals_mode"] == "local_cache_refetch"
    assert off["sync"]["news"] == stored["news"]
    assert off["sync"]["prices"]["last_success"] == "p"
    assert off["sync"]["prices"]["authority"] == "local"

    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: True)
    on = market_data_status(store=store)
    assert on["sync"]["news"] == direct
    assert on["sync"]["prices"]["last_success"] == "p"
    assert on["sync"]["prices"]["authority"] == "local"


def test_p0c_market_status_reports_prices_local_authority(monkeypatch):
    from src.api.routes import market_data as route

    class Store:
        def get_setting(self, key):
            return "true"

    monkeypatch.setattr(route, "resolve_market_db_path", lambda: "/tmp/market_data.db")
    monkeypatch.setattr(route, "env_routing_enabled", lambda: False)
    monkeypatch.setattr(route, "env_strict_enabled", lambda: False)
    monkeypatch.setattr(route, "local_market_stats", lambda _path: {
        "exists": True,
        "prices": {"row_count": 10, "ticker_count": 1, "latest_datetime": "2026-07-02T14:15:00+0000"},
        "news": {},
        "iv": {},
        "fundamentals": {},
        "financial_cache": {},
    })
    monkeypatch.setattr(route, "read_sync_meta", lambda _path: {
        "prices": {"last_success": "old", "last_error": None, "rows_added": 1, "updated_at": "old"}
    })
    monkeypatch.setattr(route, "overlay_news_sync_status", lambda sync, _path: sync)

    out = route.market_data_status(Store())

    assert out["prices_authority"] == "local"
    assert out["sync"]["prices"]["authority"] == "local"


def test_toggle_persists_and_dal_reads_it(store, tmp_path, monkeypatch):
    from src.api.routes.market_data import set_local_market, LocalMarketToggle, market_data_status
    set_local_market(LocalMarketToggle(enabled=True), store=store)
    assert store.get_setting("use_local_market") == "true"
    # Status reports the stored preference while local routing remains active.
    monkeypatch.setattr("src.api.routes.market_data.resolve_market_db_path",
                        lambda: str(tmp_path / "nope.db"))
    monkeypatch.setattr("src.api.routes.market_data.env_routing_enabled", lambda: False)
    out = market_data_status(store=store)
    assert out["use_local_market_setting"] is True and out["routing_enabled"] is True

    # The DAL remains local by default.
    from src.tools.data_access import DataAccessLayer
    from src.tools.backends.local_market_backend import LocalMarketBackend
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "market_data.db"))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MARKET", raising=False)
    dal = DataAccessLayer(base_path=tmp_path)
    assert isinstance(dal._backend, LocalMarketBackend)
    assert dal._backend._market_db == str(tmp_path / "market_data.db")


def test_status_route_reports_strict_local_only_when_enabled(store, tmp_path, monkeypatch):
    from src.api.routes.market_data import market_data_status
    db = tmp_path / "market_data.db"
    db.write_bytes(b"")
    store.set_setting("use_local_market", "true")
    store.set_setting("use_local_market_strict", "true")
    monkeypatch.setattr("src.api.routes.market_data.resolve_market_db_path", lambda: str(db))
    monkeypatch.setattr("src.api.routes.market_data.env_routing_enabled", lambda: False)
    monkeypatch.delenv("ARKSCOPE_LOCAL_MARKET_STRICT", raising=False)

    out = market_data_status(store=store)

    assert out["routing_enabled"] is True
    assert out["local_market_strict_setting"] is True
    assert out["strict_env_override"] is False
    assert out["strict_enabled"] is True


def test_toggle_invalidates_dal_cache(store, monkeypatch):
    # Toggling the setting must drop the lru_cache'd DAL so routing re-evaluates
    # on the next request (no sidecar restart needed).
    from src.api.routes.market_data import set_local_market, LocalMarketToggle
    from src.api import dependencies

    cleared = {"n": 0}
    monkeypatch.setattr(dependencies.get_dal, "cache_clear", lambda: cleared.__setitem__("n", cleared["n"] + 1))
    set_local_market(LocalMarketToggle(enabled=True), store=store)
    assert cleared["n"] == 1


# --- news_scores RETIRED: local sentiment column migration + 1-5 scale enforcement ---

_PRE_SENTIMENT_NEWS = (
    "CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, title TEXT NOT NULL, "
    "description TEXT, url TEXT, publisher TEXT, source TEXT NOT NULL, published_at TEXT NOT NULL, "
    "article_hash TEXT);"  # the OLD 9-column shape, before this slice
)


# --- ticker canonicalization (strict-readiness slice #1): aliases + PK-safe reconcile ---

def test_ensure_ticker_aliases_seeds_brk_idempotent(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mda._ensure_ticker_aliases(conn)
    rows = dict(conn.execute("SELECT alias, canonical FROM ticker_aliases").fetchall())
    assert rows.get("BRK.B") == "BRK B" and rows.get("BRK-B") == "BRK B"  # seeded
    mda._ensure_ticker_aliases(conn)  # idempotent — second run no error, no dup
    assert len(conn.execute("SELECT alias FROM ticker_aliases").fetchall()) == len(rows)
    conn.close()


def test_canonicalize_news_rows_pk_safe_when_both_forms_present(tmp_path):
    # news holds BOTH 'BRK B' and 'BRK.B' (the live state). Reconcile must NOT collide:
    # canonical rows inserted-or-ignored, alias rows deleted only after, no row lost.
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, title TEXT NOT NULL, "
        "source TEXT NOT NULL, published_at TEXT NOT NULL, article_hash TEXT);"
    )
    conn.executemany(
        "INSERT INTO news (id,ticker,title,source,published_at,article_hash) VALUES (?,?,?,?,?,?)",
        [(1, "BRK B", "a", "polygon", "2026-06-01T00:00:00+0000", "h1"),
         (2, "BRK.B", "b", "finnhub", "2026-06-01T00:00:00+0000", "h2"),
         (3, "AAPL", "c", "polygon", "2026-06-01T00:00:00+0000", "h3")],
    )
    conn.commit()
    mda._ensure_ticker_aliases(conn)
    n = mda._canonicalize_table_tickers(conn, "news")
    assert n == 1  # one alias row (BRK.B) reconciled to canonical
    tickers = sorted(r[0] for r in conn.execute("SELECT ticker FROM news").fetchall())
    assert tickers == ["AAPL", "BRK B", "BRK B"]  # both BRK rows now canonical, none lost
    conn.close()


def test_canonicalize_news_updates_ticker_and_hash_together(tmp_path):
    conn = sqlite3.connect(tmp_path / "m.db")
    conn.executescript(mda._NEWS_SCHEMA)
    mda._ensure_news_hash_unique(conn)
    mda._ensure_news_fts_triggers(conn)
    published = "2026-06-18T12:00:00+0000"
    conn.execute(
        "INSERT INTO news (id,ticker,title,source,published_at,article_hash) "
        "VALUES (1,'LC','rename article','ibkr',?,?)",
        (published, canonical_article_hash("LC", "rename article", published)),
    )
    mda._ensure_ticker_aliases(conn)
    conn.commit()

    reconciled = mda._canonicalize_table_tickers(conn, "news")

    row = conn.execute("SELECT id,ticker,article_hash FROM news").fetchone()
    assert reconciled == 1
    assert row == (
        1,
        "HAPN",
        canonical_article_hash("HAPN", "rename article", published),
    )
    conn.close()


def test_canonicalize_news_collision_merges_and_keeps_canonical_id(tmp_path):
    conn = sqlite3.connect(tmp_path / "m.db")
    conn.executescript(mda._NEWS_SCHEMA)
    mda._ensure_news_hash_unique(conn)
    mda._ensure_news_fts_triggers(conn)
    published = "2026-06-18T12:00:00+0000"
    conn.executemany(
        "INSERT INTO news (id,ticker,title,description,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (1, "LC", "same article", "richarchivephrase", "ibkr", published,
             canonical_article_hash("LC", "same article", published)),
            (2, "HAPN", "same article", "", "ibkr", published,
             canonical_article_hash("HAPN", "same article", published)),
        ],
    )
    mda._ensure_ticker_aliases(conn)
    conn.commit()

    reconciled = mda._canonicalize_table_tickers(conn, "news")

    rows = conn.execute("SELECT id,ticker,description FROM news").fetchall()
    assert reconciled == 1
    assert rows == [(2, "HAPN", "richarchivephrase")]
    conn.close()


def test_canonicalize_news_collision_keeps_fts_in_sync(tmp_path):
    conn = sqlite3.connect(tmp_path / "m.db")
    conn.executescript(mda._NEWS_SCHEMA)
    mda._ensure_news_hash_unique(conn)
    mda._ensure_news_fts_triggers(conn)
    published = "2026-06-18T12:00:00+0000"
    conn.executemany(
        "INSERT INTO news (id,ticker,title,description,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (1, "LC", "same article", "richarchivephrase", "ibkr", published,
             canonical_article_hash("LC", "same article", published)),
            (2, "HAPN", "same article", "", "ibkr", published,
             canonical_article_hash("HAPN", "same article", published)),
        ],
    )
    mda._ensure_ticker_aliases(conn)
    conn.commit()

    mda._canonicalize_table_tickers(conn, "news")

    hits = conn.execute(
        "SELECT n.id FROM news_fts f JOIN news n ON n.id=f.rowid "
        "WHERE news_fts MATCH 'richarchivephrase'"
    ).fetchall()
    assert hits == [(2,)]
    assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0] == 1
    conn.close()


def test_canonicalize_prices_pk_safe_on_collision(tmp_path):
    # prices PK = (ticker, datetime, interval). If an alias row would collide with an
    # existing canonical row on rename, the INSERT-OR-IGNORE-then-delete keeps the
    # canonical row and drops the dup — never a PK IntegrityError, never a lost canonical.
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.executescript(mda._PRICES_SCHEMA)
    conn.executemany(
        "INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?,?)",
        [("BRK B", "2026-06-01T13:30:00+0000", "15min", 1, 1, 1, 9, 100),   # canonical (keep its close=9)
         ("BRK.B", "2026-06-01T13:30:00+0000", "15min", 1, 1, 1, 5, 50)],   # alias dup → drop on reconcile
    )
    conn.commit()
    mda._ensure_ticker_aliases(conn)
    mda._canonicalize_table_tickers(conn, "prices")
    rows = conn.execute("SELECT ticker, close FROM prices ORDER BY ticker").fetchall()
    assert rows == [("BRK B", 9.0)]  # canonical row survived, alias dup dropped, no error
    conn.close()


def test_seed_includes_lc_to_hapn_rename(tmp_path):
    # LendingClub → Nasdaq HAPN rename (2026-06-22): registered so reads fold LC→HAPN and
    # the coverage panel shows one HAPN row instead of a perpetual LC missing-gap.
    conn = sqlite3.connect(tmp_path / "m.db")
    mda._ensure_ticker_aliases(conn)
    rows = dict(conn.execute("SELECT alias, canonical FROM ticker_aliases").fetchall())
    assert rows.get("LC") == "HAPN"
    conn.close()


def test_canonicalize_rename_moves_history_when_canonical_absent(tmp_path):
    # A genuine RENAME (LC→HAPN): unlike the BRK spelling-variant, the history lives under the
    # OLD symbol and the canonical (HAPN) has no rows yet → ALL alias rows move to canonical,
    # nothing dropped (no collision). This is the "carry history" stitch.
    conn = sqlite3.connect(tmp_path / "m.db")
    conn.executescript(mda._PRICES_SCHEMA)
    conn.executemany(
        "INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?,?)",
        [("LC", "2026-06-18T19:45:00+0000", "15min", 1, 1, 1, 7, 10),
         ("LC", "2026-06-18T20:00:00+0000", "15min", 1, 1, 1, 8, 20),
         ("AAPL", "2026-06-18T20:00:00+0000", "15min", 1, 1, 1, 9, 30)],
    )
    conn.commit()
    mda._ensure_ticker_aliases(conn)
    n = mda._canonicalize_table_tickers(conn, "prices")
    assert n == 1  # LC reconciled
    tickers = sorted(r[0] for r in conn.execute("SELECT DISTINCT ticker FROM prices").fetchall())
    assert tickers == ["AAPL", "HAPN"]  # all LC history now under HAPN, none lost, no LC left
    assert conn.execute("SELECT COUNT(*) FROM prices WHERE ticker='HAPN'").fetchone()[0] == 2
    conn.close()


def test_news_fts_triggers_keep_index_in_sync(tmp_path):
    # so no writer needs a manual fts insert. Triggers are NOT in _NEWS_SCHEMA (bulk bootstrap
    # uses 'rebuild') — applied via _ensure_news_fts_triggers.
    conn = sqlite3.connect(tmp_path / "m.db")
    conn.executescript(mda._NEWS_SCHEMA)          # news + news_fts (external content), no triggers
    mda._ensure_news_fts_triggers(conn)

    def match(q):
        return [r[0] for r in conn.execute(
            "SELECT n.id FROM news_fts f JOIN news n ON n.id=f.rowid WHERE news_fts MATCH ?", (q,))]

    conn.execute("INSERT INTO news (id,ticker,title,description,source,published_at,article_hash) "
                 "VALUES (1,'AAPL','datacenter momentum','strong demand','polygon','2026-06-01T00:00:00+0000','h1')")
    conn.commit()
    assert match("datacenter") == [1]             # AFTER INSERT populated fts
    conn.execute("UPDATE news SET title='earnings beat' WHERE id=1"); conn.commit()
    assert match("datacenter") == [] and match("earnings") == [1]   # AFTER UPDATE re-synced
    conn.execute("DELETE FROM news WHERE id=1"); conn.commit()
    assert match("earnings") == []                # AFTER DELETE removed the entry
    assert conn.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0] == 0
    mda._ensure_news_fts_triggers(conn)           # idempotent (CREATE TRIGGER IF NOT EXISTS)
    conn.close()


def test_ensure_news_hash_unique_dedups(tmp_path):
    conn = sqlite3.connect(tmp_path / "m.db")
    conn.executescript(mda._NEWS_SCHEMA)
    mda._ensure_news_hash_unique(conn)
    ins = ("INSERT OR IGNORE INTO news (ticker,title,source,published_at,article_hash) "
           "VALUES ('AAPL','t','polygon','2026-06-01T00:00:00+0000','dup')")
    conn.execute(ins); conn.execute(ins); conn.commit()   # same article_hash twice
    assert conn.execute("SELECT COUNT(*) FROM news WHERE article_hash='dup'").fetchone()[0] == 1
    mda._ensure_news_hash_unique(conn)            # idempotent
    conn.close()


def test_local_ticker_coverage_resolves_aliases(tmp_path):
    # coverage is user-facing: querying the alias spelling ('BRK.B') must report the
    # canonical rows ('BRK B') as present, not falsely "missing" after canon.
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.executescript(mda._PRICES_SCHEMA)
    conn.executescript("CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, "
                       "title TEXT NOT NULL, source TEXT NOT NULL, published_at TEXT NOT NULL);")
    mda._ensure_ticker_aliases(conn)
    conn.execute("INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) "
                 "VALUES ('BRK B','2026-06-01T13:30:00+0000','15min',1,1,1,1,1)")
    conn.execute("INSERT INTO news (id,ticker,title,source,published_at) "
                 "VALUES (1,'BRK B','t','polygon','2026-06-01T12:00:00+0000')")
    conn.commit()
    conn.close()
    cov = mda.local_ticker_coverage("BRK.B", out_path=str(db))   # query the ALIAS
    assert cov["exists"] is True
    assert cov["prices"] is True and cov["news"] is True          # resolved to canonical rows
    # canonical spelling still works
    cov2 = mda.local_ticker_coverage("BRK B", out_path=str(db))
    assert cov2["prices"] is True
