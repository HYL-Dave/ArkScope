"""Tests for the market_data lifecycle substrate (slice 3a.1): admin core + routes."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

import src.market_data_admin as mda
from src.profile_state import ProfileStateStore

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


def test_bootstrap_builds_prices_and_news(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    res = mda.bootstrap_market(out)
    assert res["match"] is True
    assert res["prices"]["rows"] == 3 and res["news"]["rows"] == 2
    assert not (tmp_path / "market_data.db.building").exists()  # swapped in
    stats = mda.local_market_stats(out)
    assert stats["exists"] is True
    assert stats["prices"]["row_count"] == 3 and stats["prices"]["ticker_count"] == 2
    assert stats["news"]["row_count"] == 2 and stats["news"]["source_count"] == 2
    # FTS5 was rebuilt → news is searchable
    conn = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    try:
        n = conn.execute("SELECT COUNT(*) FROM news_fts WHERE news_fts MATCH 'Nvidia'").fetchone()[0]
    finally:
        conn.close()
    assert n == 1


def test_bootstrap_mismatch_keeps_existing_db(tmp_path, monkeypatch):
    out = str(tmp_path / "market_data.db")
    # pre-existing good DB with a sentinel price row
    conn = sqlite3.connect(out)
    conn.executescript(mda._PRICES_SCHEMA)
    conn.executescript(mda._NEWS_SCHEMA)
    conn.execute("INSERT INTO prices VALUES ('OLD','2020-01-01T00:00:00+0000','15min',1,1,1,1,1)")
    conn.commit(); conn.close()
    # PG claims more price rows than it yields → validation mismatch
    monkeypatch.setattr(mda, "_pg_conn",
                        lambda: _FakePG(_PRICE_ROWS, _NEWS_ROWS, price_total=len(_PRICE_ROWS) + 99))
    res = mda.bootstrap_market(out)
    assert res["match"] is False and res["prices"]["match"] is False
    assert not (tmp_path / "market_data.db.building").exists()  # discarded
    assert mda.local_market_stats(out)["prices"]["row_count"] == 1  # existing untouched


def test_validate_market(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    r = mda.validate_market(out)
    assert r["match"] is True
    assert r["prices"]["local_rows"] == 3 and r["news"]["local_rows"] == 2


def test_news_checksum_catches_id_drift(tmp_path, fake_pg):
    # Hardening: same per-(source,ticker) COUNT but a different id set must be
    # caught via SUM(id) — the old per-source count alone would have passed.
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    conn = sqlite3.connect(out)
    conn.execute("UPDATE news SET id = 999 WHERE id = 1")  # same counts, different SUM(id)
    conn.commit(); conn.close()
    r = mda.validate_market(out)
    assert r["news"]["match"] is False and r["match"] is False
    assert r["news"]["local_rows"] == r["news"]["pg_rows"]  # counts still equal → only SUM(id) caught it


# --- 3c-A: iv_history + fundamentals ------------------------------------------

def test_bootstrap_builds_iv_and_fundamentals(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    res = mda.bootstrap_market(out)
    assert res["match"] is True
    assert res["iv"]["rows"] == 3 and res["iv"]["match"] is True
    assert res["fundamentals"]["rows"] == 2 and res["fundamentals"]["match"] is True
    stats = mda.local_market_stats(out)
    assert stats["iv"]["row_count"] == 3 and stats["iv"]["ticker_count"] == 2
    assert stats["iv"]["latest_date"] == "2026-06-02"
    assert stats["fundamentals"]["row_count"] == 2 and stats["fundamentals"]["ticker_count"] == 2


def test_validate_iv_and_fundamentals(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    r = mda.validate_market(out)
    assert r["match"] is True
    assert r["iv"]["local_rows"] == 3 and r["iv"]["match"] is True
    assert r["fundamentals"]["local_rows"] == 2 and r["fundamentals"]["match"] is True


def test_iv_checksum_catches_id_drift(tmp_path, fake_pg):
    # Same per-ticker COUNT but a different id set must be caught via SUM(id).
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    conn = sqlite3.connect(out)
    conn.execute("UPDATE iv_history SET id = 99 WHERE id = 1")  # same count, different SUM(id)
    conn.commit(); conn.close()
    r = mda.validate_market(out)
    assert r["iv"]["match"] is False and r["match"] is False
    assert r["iv"]["local_rows"] == r["iv"]["pg_rows"]  # counts equal → only SUM(id) caught it


def test_fundamentals_checksum_catches_id_drift(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    conn = sqlite3.connect(out)
    conn.execute("UPDATE fundamentals SET id = 99 WHERE id = 1")
    conn.commit(); conn.close()
    r = mda.validate_market(out)
    assert r["fundamentals"]["match"] is False and r["match"] is False
    assert r["fundamentals"]["local_rows"] == r["fundamentals"]["pg_rows"]


_NEW_IV = (4, "AAPL", "2026-06-03", 0.27, 0.22, 0.05, 103.0, 16)
_NEW_FUND = (3, "TSLA", "2026-06-02", '{"reports": {"ReportSnapshot": {"Name": "Tesla"}}}')


def test_incremental_iv_and_fundamentals_add_new_rows(tmp_path, fake_pg, monkeypatch):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)  # 3 iv, 2 fundamentals
    # PG now has one extra iv snapshot + one extra fundamentals row (id-based delta;
    # INSERT OR IGNORE dedups the existing ids the fake re-serves).
    monkeypatch.setattr(mda, "_pg_conn", lambda: _FakePG(
        _PRICE_ROWS, _NEWS_ROWS, iv=_IV_ROWS + [_NEW_IV], fund=_FUND_ROWS + [_NEW_FUND]))
    res = mda.incremental_update(out)
    assert res["ok"] is True
    assert res["iv"]["rows_added"] == 1 and res["fundamentals"]["rows_added"] == 1
    stats = mda.local_market_stats(out)
    assert stats["iv"]["row_count"] == 4 and stats["fundamentals"]["row_count"] == 3
    meta = mda.read_sync_meta(out)
    assert meta["iv"]["rows_added"] == 1 and meta["iv"]["last_success"]
    assert meta["fundamentals"]["rows_added"] == 1 and meta["fundamentals"]["last_error"] is None


_NEW_PRICE = ("AAPL", "2026-06-01T09:30:00+0000", "15min", 102.0, 104.0, 101.0, 103.0, 1200)
_NEW_NEWS = (3, "AAPL", "Apple new product launch", "big reveal", "http://d", "Reuters",
             "polygon", "2026-06-02T10:00:00+0000", "h3")


def test_incremental_update_adds_new_rows(tmp_path, fake_pg, monkeypatch):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)  # 3 prices, 2 news
    # PG now has one extra bar + one extra article (INSERT OR IGNORE dedups the rest)
    monkeypatch.setattr(mda, "_pg_conn",
                        lambda: _FakePG(_PRICE_ROWS + [_NEW_PRICE], _NEWS_ROWS + [_NEW_NEWS]))
    res = mda.incremental_update(out)
    assert res["ok"] is True
    assert res["prices"]["rows_added"] == 1 and res["news"]["rows_added"] == 1
    stats = mda.local_market_stats(out)
    assert stats["prices"]["row_count"] == 4 and stats["news"]["row_count"] == 3
    # FTS kept in sync → the new article is searchable
    conn = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    try:
        n = conn.execute("SELECT COUNT(*) FROM news_fts WHERE news_fts MATCH 'product'").fetchone()[0]
    finally:
        conn.close()
    assert n == 1
    meta = mda.read_sync_meta(out)
    assert meta["prices"]["rows_added"] == 1 and meta["prices"]["last_success"]
    assert meta["news"]["rows_added"] == 1 and meta["news"]["last_error"] is None


_NEW_TICKER_BAR = ("TSLA", "2026-05-01T09:00:00+0000", "15min", 200.0, 202.0, 199.0, 201.0, 500)


def test_incremental_prices_query_is_group_aware(tmp_path, fake_pg, monkeypatch):
    # The prices delta must be per-(ticker,interval), NOT a single global datetime>max.
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    captured = {}

    class _CapCursor(_FakeCursor):
        def execute(self, sql, params=None):
            s = " ".join(sql.split())
            if "FROM prices p" in s:  # the PG delta query
                captured["sql"], captured["params"] = s, params
            super().execute(sql, params)

    class _CapPG(_FakePG):
        def __init__(self):
            self._c = _CapCursor(_PRICE_ROWS, _NEWS_ROWS)

    monkeypatch.setattr(mda, "_pg_conn", lambda: _CapPG())
    mda.incremental_update(out)
    assert "LEFT JOIN (VALUES" in captured["sql"]
    assert "v.maxdt IS NULL OR p.datetime > v.maxdt" in captured["sql"]
    assert len(captured["params"]) == 2 * 3  # one (ticker,interval,max) triple per local group


def test_incremental_prices_catches_new_ticker(tmp_path, fake_pg, monkeypatch):
    # A NEW ticker whose bars are OLDER than the global max — the old global
    # datetime>max would skip it; per-group catches it (v.maxdt IS NULL → all rows).
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    monkeypatch.setattr(mda, "_pg_conn",
                        lambda: _FakePG(_PRICE_ROWS + [_NEW_TICKER_BAR], _NEWS_ROWS))
    res = mda.incremental_update(out)
    assert res["prices"]["rows_added"] == 1
    conn = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    try:
        n = conn.execute("SELECT COUNT(*) FROM prices WHERE ticker = 'TSLA'").fetchone()[0]
    finally:
        conn.close()
    assert n == 1


def test_incremental_update_idempotent(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    res = mda.incremental_update(out)  # nothing newer → 0 added each
    assert res["prices"]["rows_added"] == 0 and res["news"]["rows_added"] == 0


def test_incremental_update_missing_db(tmp_path):
    res = mda.incremental_update(str(tmp_path / "nope.db"))
    assert res["ok"] is False and "bootstrap" in res["error"]


def test_incremental_provider_failure_not_fatal(tmp_path, fake_pg, monkeypatch):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)

    def _boom():
        raise RuntimeError("PG down")

    monkeypatch.setattr(mda, "_pg_conn", _boom)
    res = mda.incremental_update(out)  # must NOT raise
    assert res["ok"] is False
    assert res["prices"]["ok"] is False and "PG down" in res["prices"]["error"]
    assert res["news"]["ok"] is False  # other domain also recorded, not crashed
    meta = mda.read_sync_meta(out)
    assert meta["prices"]["last_error"] and "PG down" in meta["prices"]["last_error"]
    # existing data untouched
    assert mda.local_market_stats(out)["prices"]["row_count"] == 3


def test_bootstrap_job_runs_to_done(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    job = mda.start_bootstrap_job(out)
    assert job["status"] in ("running", "done")
    # Wait on a wall-clock DEADLINE, not a fixed iteration count: the daemon job's
    # work (4 domains → copy + commit + validate + atomic swap + WAL reopen) is real
    # disk I/O, so under contention it can take a few seconds. A generous deadline
    # stays reliable while still failing fast if the job genuinely hangs.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        j = mda.get_job(job["id"])
        if j["status"] != "running":
            break
        time.sleep(0.05)
    j = mda.get_job(job["id"])
    assert j["status"] == "done" and j["result"]["match"] is True


def _drain_update_job(out, monkeypatch, fake_result):
    """Run start_update_job with incremental_update stubbed to fake_result; poll to done."""
    mda._JOBS.clear()  # hermetic: don't attach to a prior test's running update job
    monkeypatch.setattr(mda, "incremental_update", lambda path, batch=20000: fake_result)
    job = mda.start_update_job(out)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        j = mda.get_job(job["id"])
        if j["status"] != "running":
            break
        time.sleep(0.05)
    return mda.get_job(job["id"])


def test_update_job_surfaces_iv_or_fundamentals_failure(tmp_path, monkeypatch):
    # start_update_job must weigh ALL 4 domains: prices/news ok but iv failed → still
    # "done" (best-effort), and the iv error is surfaced in job["error"] (the old
    # 2-domain predicate ignored iv/fundamentals entirely).
    j = _drain_update_job(str(tmp_path / "m.db"), monkeypatch, {
        "ok": False,
        "prices": {"ok": True, "rows_added": 5, "error": None},
        "news": {"ok": True, "rows_added": 2, "error": None},
        "iv": {"ok": False, "rows_added": 0, "error": "IV provider down"},
        "fundamentals": {"ok": True, "rows_added": 1, "error": None},
    })
    assert j["status"] == "done"
    assert j["error"] and "IV provider down" in j["error"]


def test_update_job_all_domains_fail_is_error(tmp_path, monkeypatch):
    j = _drain_update_job(str(tmp_path / "m.db"), monkeypatch, {
        "ok": False,
        "prices": {"ok": False, "rows_added": 0, "error": "PG down"},
        "news": {"ok": False, "rows_added": 0, "error": "PG down"},
        "iv": {"ok": False, "rows_added": 0, "error": "PG down"},
        "fundamentals": {"ok": False, "rows_added": 0, "error": "PG down"},
    })
    assert j["status"] == "error" and "PG down" in j["error"]


# --- 3c-C: financial_cache (local-primary; carry-over on rebuild) -------------

def test_bootstrap_creates_empty_financial_cache(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    res = mda.bootstrap_market(out)
    assert res["match"] is True
    assert res["financial_cache"]["carried_over"] == 0  # first build → nothing to carry
    assert mda.local_market_stats(out)["financial_cache"]["row_count"] == 0


def test_bootstrap_carries_over_financial_cache(tmp_path, fake_pg):
    # financial_cache is local-primary (NOT mirrored from PG); a full rebuild must
    # preserve its rows across the atomic swap rather than dropping them.
    from src.tools.backends.sqlite_backend import SqliteBackend
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)  # build once → empty financial_cache table exists
    sb = SqliteBackend(out)
    sb.set_financial_cache("metrics_AAPL", "AAPL", {"pe": 30}, expires_at="2099-01-01T00:00:00+00:00")
    sb.set_financial_cache("metrics_NVDA", "NVDA", {"pe": 60}, expires_at="2099-01-01T00:00:00+00:00")
    res = mda.bootstrap_market(out)  # rebuild → rows must survive
    assert res["match"] is True and res["financial_cache"]["carried_over"] == 2
    assert sb.get_financial_cache("metrics_AAPL") == {"pe": 30}
    assert sb.get_financial_cache("metrics_NVDA") == {"pe": 60}


def test_local_stats_financial_cache_counts(tmp_path, fake_pg):
    from src.tools.backends.sqlite_backend import SqliteBackend
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    sb = SqliteBackend(out)
    sb.set_financial_cache("valid", "AAPL", {"x": 1}, expires_at="2099-01-01T00:00:00+00:00")
    sb.set_financial_cache("expired", "AAPL", {"x": 2}, expires_at="2000-01-01T00:00:00+00:00")
    fc = mda.local_market_stats(out)["financial_cache"]
    assert fc["row_count"] == 2 and fc["valid_count"] == 1 and fc["expired_count"] == 1
    assert fc["latest_fetched_at"] is not None


def test_bootstrap_clean_state_after_rebuild_with_stale_sidecars(tmp_path, fake_pg):
    # 3c-C made set_financial_cache a live WAL writer, so a stale `market_data.db-wal`
    # can exist at swap time. os.replace swaps only the main file by inode, but SQLite
    # keys -wal/-shm by FILENAME → a stale WAL could be replayed onto the freshly-built
    # NEW inode (silent stale-data corruption escaping the pre-swap validation), which
    # is why bootstrap unlinks the old sidecars as part of the swap.
    # NOTE: this is an INVARIANT guard, not a fix-discriminating test — the full
    # replay corruption needs a salt-matched valid WAL injected at the exact mid-swap
    # instant (not craftable black-box; verified manually). Here we assert the
    # post-rebuild invariant: a rebuild over a DB with pre-existing sidecars yields a
    # validated DB, no leftover sidecars, and intact carry-over.
    from src.tools.backends.sqlite_backend import SqliteBackend
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    SqliteBackend(out).set_financial_cache("CARRIED", "AAPL", {"v": 1},
                                           expires_at="2099-01-01T00:00:00+00:00")
    Path(out + "-wal").write_bytes(b"stale-wal-bytes")  # sidecars present at rebuild
    Path(out + "-shm").write_bytes(b"stale-shm-bytes")
    res = mda.bootstrap_market(out)
    assert res["match"] is True
    assert not Path(out + "-wal").exists() and not Path(out + "-shm").exists()
    assert res["financial_cache"]["carried_over"] == 1
    assert SqliteBackend(out).get_financial_cache("CARRIED") == {"v": 1}


def test_local_ticker_coverage(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    # missing DB → exists False, all domains False
    cov = mda.local_ticker_coverage("AAPL", out)
    assert cov["exists"] is False and not any(cov[d] for d in ("prices", "news", "iv", "fundamentals"))
    mda.bootstrap_market(out)  # fake serves AAPL+NVDA across all domains
    cov = mda.local_ticker_coverage("aapl", out)  # case-insensitive
    assert cov["exists"] is True
    assert cov["prices"] and cov["news"] and cov["iv"] and cov["fundamentals"]
    absent = mda.local_ticker_coverage("ZZZZ", out)  # tracked DB, untracked ticker
    assert absent["exists"] is True
    assert not (absent["prices"] or absent["news"] or absent["iv"] or absent["fundamentals"])


def test_incremental_update_leaves_financial_cache_intact(tmp_path, fake_pg):
    # contract: the incremental updater does NOT touch financial_cache.
    from src.tools.backends.sqlite_backend import SqliteBackend
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_market(out)
    sb = SqliteBackend(out)
    sb.set_financial_cache("k", "AAPL", {"v": 1}, expires_at="2099-01-01T00:00:00+00:00")
    res = mda.incremental_update(out)
    assert res["ok"] is True
    assert sb.get_financial_cache("k") == {"v": 1}  # untouched
    assert mda.local_market_stats(out)["financial_cache"]["row_count"] == 1


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
    assert out["use_local_market_setting"] is False
    assert out["routing_enabled"] is False  # no DB + setting off


def test_toggle_persists_and_dal_reads_it(store, tmp_path, monkeypatch):
    from src.api.routes.market_data import set_local_market, LocalMarketToggle, market_data_status
    set_local_market(LocalMarketToggle(enabled=True), store=store)
    assert store.get_setting("use_local_market") == "true"
    # status reflects the setting even with no DB (routing still gated on DB existence)
    monkeypatch.setattr("src.api.routes.market_data.resolve_market_db_path",
                        lambda: str(tmp_path / "nope.db"))
    monkeypatch.setattr("src.api.routes.market_data.env_routing_enabled", lambda: False)
    out = market_data_status(store=store)
    assert out["use_local_market_setting"] is True and out["routing_enabled"] is False

    # the DAL reads the same persisted setting (read-only) — enabled, but no DB → stays PG
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


def test_job_not_found_404():
    from fastapi import HTTPException
    from src.api.routes.market_data import market_data_job
    with pytest.raises(HTTPException) as exc:
        market_data_job("nonexistent")
    assert exc.value.status_code == 404


def test_toggle_invalidates_dal_cache(store, monkeypatch):
    # Toggling the setting must drop the lru_cache'd DAL so routing re-evaluates
    # on the next request (no sidecar restart needed).
    from src.api.routes.market_data import set_local_market, LocalMarketToggle
    from src.api import dependencies

    cleared = {"n": 0}
    monkeypatch.setattr(dependencies.get_dal, "cache_clear", lambda: cleared.__setitem__("n", cleared["n"] + 1))
    set_local_market(LocalMarketToggle(enabled=True), store=store)
    assert cleared["n"] == 1


def test_bootstrap_done_poll_invalidates_dal_cache(monkeypatch):
    # A completed bootstrap poll drops the DAL cache (covers enable-before-build).
    import src.market_data_admin as _mda
    from src.api.routes import market_data as md
    from src.api import dependencies

    monkeypatch.setattr(_mda, "get_job", lambda jid: {
        "id": jid, "kind": "bootstrap_market", "status": "done",
        "progress": {"written": 1, "total": 1}, "result": {"match": True}, "error": None})
    monkeypatch.setattr(md, "get_job", _mda.get_job)
    cleared = {"n": 0}
    monkeypatch.setattr(dependencies.get_dal, "cache_clear", lambda: cleared.__setitem__("n", cleared["n"] + 1))
    md.market_data_job("abc")
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
