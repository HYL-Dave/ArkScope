"""Tests for the market_data lifecycle substrate (slice 3a.1): admin core + routes."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

import src.market_data_admin as mda
from src.news_identity import canonical_article_hash
from src.profile_state import ProfileStateStore


def _legacy_bootstrap_market(*args, **kwargs):
    return mda.bootstrap_market(*args, allow_retired_pg_mirror=True, **kwargs)


def _legacy_validate_market(*args, **kwargs):
    return mda.validate_market(*args, allow_retired_pg_mirror=True, **kwargs)


def _legacy_incremental_update(*args, **kwargs):
    return mda.incremental_update(*args, allow_retired_pg_mirror=True, **kwargs)


# --- a minimal fake PG serving BOTH domains (no live DB needed) ---------------

_PRICE_ROWS = [
    ("AAPL", "2026-06-01T09:00:00+0000", "15min", 100.0, 102.0, 99.0, 101.0, 1000),
    ("AAPL", "2026-06-01T09:15:00+0000", "15min", 101.0, 103.0, 100.0, 102.0, 1100),
    ("NVDA", "2026-06-01T09:00:00+0000", "15min", 900.0, 905.0, 899.0, 904.0, 2000),
]
_NEWS_ROWS = [
    (1, "AAPL", "Apple beat estimates", "iPhone demand", "http://a", "Reuters",
     "polygon", "2026-06-01T12:00:00+0000", "h1"),
    (2, "NVDA", "Nvidia new chip", "datacenter", "http://b", "Bloomberg",
     "finnhub", "2026-06-01T12:00:00+0000", "h2"),
]
# 3c-A: iv_history (id, ticker, date, atm_iv, hv_30d, vrp, spot_price, num_quotes)
_IV_ROWS = [
    (1, "AAPL", "2026-06-01", 0.25, 0.20, 0.05, 101.0, 12),
    (2, "AAPL", "2026-06-02", 0.26, 0.21, 0.05, 102.0, 14),
    (3, "NVDA", "2026-06-01", 0.45, 0.40, 0.05, 904.0, 30),
]
# 3c-A: fundamentals (id, ticker, snapshot_date, data::text — ReportSnapshot JSON)
_FUND_ROWS = [
    (1, "AAPL", "2026-06-01",
     '{"reports": {"ReportSnapshot": {"Name": "Apple Inc"}, '
     '"ReportsFinSummary": {"rev": 1}, "ReportsOwnership": {"inst": 0.6}}}'),
    (2, "NVDA", "2026-06-01", '{"reports": {"ReportSnapshot": {"Name": "NVIDIA"}}}'),
]


def _price_checksum(rows):
    out = {}
    for r in rows:
        out[(r[0], r[2])] = out.get((r[0], r[2]), 0) + 1
    return [(t, iv, n) for (t, iv), n in out.items()]


def _news_checksum(rows):
    # mirror PG: SELECT source, ticker, COUNT(*), SUM(id) GROUP BY source, ticker
    out = {}
    for r in rows:
        key = (r[6], r[1])  # (source, ticker)
        cnt, sid = out.get(key, (0, 0))
        out[key] = (cnt + 1, sid + r[0])  # +1 row, +id
    return [(src, tk, c, s) for (src, tk), (c, s) in out.items()]


def _ticker_idsum_checksum(rows):
    # mirror PG for iv/fundamentals: SELECT ticker, COUNT(*), SUM(id) GROUP BY ticker
    # (id is col 0, ticker is col 1 in both row shapes).
    out = {}
    for r in rows:
        cnt, sid = out.get(r[1], (0, 0))
        out[r[1]] = (cnt + 1, sid + r[0])
    return [(tk, c, s) for tk, (c, s) in out.items()]


class _FakeCursor:
    def __init__(self, prices, news, price_total=None, news_total=None,
                 iv=None, fund=None, iv_total=None, fund_total=None):
        self._p, self._n = prices, news
        self._iv = _IV_ROWS if iv is None else iv
        self._f = _FUND_ROWS if fund is None else fund
        self._pt = price_total if price_total is not None else len(prices)
        self._nt = news_total if news_total is not None else len(news)
        self._ivt = iv_total if iv_total is not None else len(self._iv)
        self._ft = fund_total if fund_total is not None else len(self._f)
        self._mode, self._it, self._val = None, None, None

    @staticmethod
    def _domain(s):
        if "FROM iv_history" in s:
            return "iv"
        if "FROM fundamentals" in s:
            return "fundamentals"
        if "FROM news" in s:
            return "news"
        return "prices"

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        dom = self._domain(s)
        rows = {"prices": self._p, "news": self._n, "iv": self._iv, "fundamentals": self._f}[dom]
        if "GROUP BY" in s:  # checked before COUNT(*): checksum SQL contains both
            checksum = {"prices": _price_checksum, "news": _news_checksum,
                        "iv": _ticker_idsum_checksum, "fundamentals": _ticker_idsum_checksum}[dom]
            self._mode, self._val = "all", checksum(rows)
        elif "COUNT(*)" in s:
            total = {"prices": self._pt, "news": self._nt,
                     "iv": self._ivt, "fundamentals": self._ft}[dom]
            self._mode, self._val = "one", (total,)
        else:
            self._mode, self._it = "select", iter(rows)

    def fetchone(self):
        return self._val if self._mode == "one" else None

    def fetchall(self):
        return list(self._val) if self._mode == "all" else []

    def fetchmany(self, n):
        out = []
        for _ in range(n):
            try:
                out.append(next(self._it))
            except StopIteration:
                break
        return out


class _FakePG:
    def __init__(self, prices, news, price_total=None, news_total=None,
                 iv=None, fund=None, iv_total=None, fund_total=None):
        self._c = _FakeCursor(prices, news, price_total, news_total,
                              iv=iv, fund=fund, iv_total=iv_total, fund_total=fund_total)

    def cursor(self):
        return self._c

    def close(self):
        pass


@pytest.fixture()
def fake_pg(monkeypatch):
    """Patch _pg_conn → fake serving prices + news + iv + fundamentals (happy path)."""
    monkeypatch.setattr(mda, "_pg_conn", lambda: _FakePG(_PRICE_ROWS, _NEWS_ROWS))


# --- admin core ---------------------------------------------------------------

def test_local_stats_missing(tmp_path):
    s = mda.local_market_stats(str(tmp_path / "nope.db"))
    assert s["exists"] is False
    assert s["prices"]["row_count"] == 0 and s["news"]["row_count"] == 0


# --- 3c-A: iv_history + fundamentals ------------------------------------------

_NEW_IV = (4, "AAPL", "2026-06-03", 0.27, 0.22, 0.05, 103.0, 16)
_NEW_FUND = (3, "TSLA", "2026-06-02", '{"reports": {"ReportSnapshot": {"Name": "Tesla"}}}')


_NEW_PRICE = ("AAPL", "2026-06-01T09:30:00+0000", "15min", 102.0, 104.0, 101.0, 103.0, 1200)
_NEW_NEWS = (3, "AAPL", "Apple new product launch", "big reveal", "http://d", "Reuters",
             "polygon", "2026-06-02T10:00:00+0000", "h3")


_NEW_TICKER_BAR = ("TSLA", "2026-05-01T09:00:00+0000", "15min", 200.0, 202.0, 199.0, 201.0, 500)


# --- 3c-C: financial_cache (local-primary; carry-over on rebuild) -------------

def test_local_stats_financial_cache_counts(tmp_path, fake_pg):
    from src.tools.backends.sqlite_backend import SqliteBackend
    out = str(tmp_path / "market_data.db")
    _legacy_bootstrap_market(out)
    sb = SqliteBackend(out)
    sb.set_financial_cache("valid", "AAPL", {"x": 1}, expires_at="2099-01-01T00:00:00+00:00")
    sb.set_financial_cache("expired", "AAPL", {"x": 2}, expires_at="2000-01-01T00:00:00+00:00")
    fc = mda.local_market_stats(out)["financial_cache"]
    assert fc["row_count"] == 2 and fc["valid_count"] == 1 and fc["expired_count"] == 1
    assert fc["latest_fetched_at"] is not None


def test_local_ticker_coverage(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    # missing DB → exists False, all domains False
    cov = mda.local_ticker_coverage("AAPL", out)
    assert cov["exists"] is False and not any(cov[d] for d in ("prices", "news", "iv", "fundamentals"))
    _legacy_bootstrap_market(out)  # fake serves AAPL+NVDA across all domains
    cov = mda.local_ticker_coverage("aapl", out)  # case-insensitive
    assert cov["exists"] is True
    assert cov["prices"] and cov["news"] and cov["iv"] and cov["fundamentals"]
    absent = mda.local_ticker_coverage("ZZZZ", out)  # tracked DB, untracked ticker
    assert absent["exists"] is True
    assert not (absent["prices"] or absent["news"] or absent["iv"] or absent["fundamentals"])


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
    assert out["pg_fallback_active"] is False
    assert out["routing_enabled"] is True  # post-PG-exit default local, even before DB creation


def test_fresh_profile_without_market_db_uses_local_backend_not_pg(tmp_path, monkeypatch):
    from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend
    from src.tools.data_access import DataAccessLayer

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / ".env").write_text(
        "DATABASE_URL=postgresql://invalid.invalid/arkscope\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    profile = data_dir / "profile_state.db"
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE profile_settings (key TEXT PRIMARY KEY, value TEXT)")

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MARKET", raising=False)
    monkeypatch.delenv("ARKSCOPE_MARKET_DB", raising=False)

    dal = DataAccessLayer(base_path=tmp_path, db_dsn="auto")

    assert isinstance(dal._backend, LocalMarketDatabaseBackend)
    assert not (data_dir / "market_data.db").exists()
    assert dal.get_prices("NVDA").bars == []


def test_status_news_sync_follows_active_writer_only(store, tmp_path, monkeypatch):
    from src.api.routes.market_data import market_data_status

    db = tmp_path / "market_data.db"
    db.write_bytes(b"")
    mirror = {
        "prices": {"last_success": "p", "last_error": None, "rows_added": 1, "updated_at": "p"},
        "news": {"last_success": "mirror", "last_error": None, "rows_added": 2, "updated_at": "mirror"},
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
    monkeypatch.setattr("src.api.routes.market_data.read_sync_meta", lambda path: mirror)
    monkeypatch.setattr("src.news_sync_status.read_news_sync_status", lambda path: direct)

    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: False)
    off = market_data_status(store=store)
    assert off["fundamentals_mode"] == "local_cache_refetch"
    assert off["sync"]["news"] == mirror["news"]
    assert off["sync"]["prices"]["last_success"] == "p"
    assert off["sync"]["prices"]["retired"] is True

    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: True)
    on = market_data_status(store=store)
    assert on["sync"]["news"] == direct
    assert on["sync"]["prices"]["last_success"] == "p"
    assert on["sync"]["prices"]["retired"] is True


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
    assert out["price_mirror_retired"] is True
    assert out["pg_fallback_active"] is False
    assert out["sync"]["prices"]["retired"] is True
    assert out["sync"]["prices"]["authority"] == "local"


def test_toggle_persists_and_dal_reads_it(store, tmp_path, monkeypatch):
    from src.api.routes.market_data import set_local_market, LocalMarketToggle, market_data_status
    set_local_market(LocalMarketToggle(enabled=True), store=store)
    assert store.get_setting("use_local_market") == "true"
    # status reflects the persisted legacy setting, but routing is local by default
    # even before the DB is created.
    monkeypatch.setattr("src.api.routes.market_data.resolve_market_db_path",
                        lambda: str(tmp_path / "nope.db"))
    monkeypatch.setattr("src.api.routes.market_data.env_routing_enabled", lambda: False)
    out = market_data_status(store=store)
    assert out["use_local_market_setting"] is True and out["routing_enabled"] is True

    # the DAL remains local by default; the setting is provenance, not a PG fallback lever.
    from src.tools.data_access import DataAccessLayer
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MARKET", raising=False)
    dal = DataAccessLayer.__new__(DataAccessLayer)
    dal._base = tmp_path
    assert dal._local_market_enabled() is True


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
    assert out["pg_fallback_active"] is False


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


def test_ensure_news_sentiment_columns_migrates_pre_existing_in_place(tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript(_PRE_SENTIMENT_NEWS)
    conn.execute("INSERT INTO news VALUES (1,'AAPL','t','d','u','p','polygon','2026-06-01T12:00:00+0000','h')")
    conn.commit()

    mda._ensure_news_sentiment_columns(conn)  # the in-place upgrade
    cols = {r[1] for r in conn.execute("PRAGMA table_info(news)").fetchall()}
    assert {"sentiment_score", "sentiment_source", "sentiment_scale"} <= cols  # added
    row = conn.execute("SELECT sentiment_score, ticker FROM news WHERE id=1").fetchone()
    assert row == (None, "AAPL")  # existing row preserved, score born NULL

    mda._ensure_news_sentiment_columns(conn)  # idempotent — second run is a no-op
    assert len({r[1] for r in conn.execute("PRAGMA table_info(news)").fetchall()}) == len(cols)
    conn.close()


def test_ensure_news_sentiment_columns_no_news_table_is_safe(tmp_path):
    conn = sqlite3.connect(tmp_path / "empty.db")
    mda._ensure_news_sentiment_columns(conn)  # no news table → must not raise
    conn.close()


def test_local_news_sentiment_score_is_check_constrained_to_1_5(tmp_path):
    # The scale invariant is ENFORCED, not conventional: a provider polarity (-1/0/+1)
    # CANNOT be written into the 1-5 sentiment_score — the storage rejects it.
    db = tmp_path / "fresh.db"
    conn = sqlite3.connect(db)
    conn.executescript(mda._NEWS_SCHEMA)  # fresh schema carries the CHECK
    base = "INSERT INTO news (id,ticker,title,source,published_at,sentiment_score) VALUES (?,?,?,?,?,?)"
    conn.execute(base, (1, "AAPL", "t", "polygon", "2026-06-01T12:00:00+0000", 4.0))   # 1-5 ok
    conn.execute(base, (2, "AAPL", "t", "polygon", "2026-06-01T12:00:00+0000", None))  # NULL ok
    conn.commit()
    for bad in (-1.0, 0.0, 6.0):  # polarity / out-of-range → rejected
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(base, (99, "AAPL", "t", "polygon", "2026-06-01T12:00:00+0000", bad))
    conn.close()


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
    # PG-exit 2b: external-content news_fts kept in sync by AFTER INSERT/UPDATE/DELETE triggers,
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
