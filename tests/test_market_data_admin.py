"""Tests for the market_data lifecycle substrate (slice 3a.1): admin core + routes."""

from __future__ import annotations

import sqlite3
import time

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


class _FakeCursor:
    def __init__(self, prices, news, price_total=None, news_total=None):
        self._p, self._n = prices, news
        self._pt = price_total if price_total is not None else len(prices)
        self._nt = news_total if news_total is not None else len(news)
        self._mode, self._it, self._val = None, None, None

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        is_news = "FROM news" in s
        rows = self._n if is_news else self._p
        if "GROUP BY" in s:
            self._mode, self._val = "all", (_news_checksum(rows) if is_news else _price_checksum(rows))
        elif "COUNT(*)" in s:
            self._mode, self._val = "one", (self._nt if is_news else self._pt,)
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
    def __init__(self, prices, news, price_total=None, news_total=None):
        self._c = _FakeCursor(prices, news, price_total, news_total)

    def cursor(self):
        return self._c

    def close(self):
        pass


@pytest.fixture()
def fake_pg(monkeypatch):
    """Patch _pg_conn → fake serving prices + news (happy path)."""
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
    for _ in range(50):
        j = mda.get_job(job["id"])
        if j["status"] != "running":
            break
        time.sleep(0.05)
    j = mda.get_job(job["id"])
    assert j["status"] == "done" and j["result"]["match"] is True


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
