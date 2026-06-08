"""Tests for the market_data lifecycle substrate (slice 3a.1): admin core + routes."""

from __future__ import annotations

import sqlite3
import time

import pytest

import src.market_data_admin as mda
from src.profile_state import ProfileStateStore

# --- a minimal fake PG (no live DB needed) -----------------------------------

_ROWS = [
    ("AAPL", "2026-06-01T09:00:00+0000", "15min", 100.0, 102.0, 99.0, 101.0, 1000),
    ("AAPL", "2026-06-01T09:15:00+0000", "15min", 101.0, 103.0, 100.0, 102.0, 1100),
    ("NVDA", "2026-06-01T09:00:00+0000", "15min", 900.0, 905.0, 899.0, 904.0, 2000),
]


def _checksum(rows):
    out = {}
    for r in rows:
        out[(r[0], r[2])] = out.get((r[0], r[2]), 0) + 1
    return [(t, iv, n) for (t, iv), n in out.items()]


class _FakeCursor:
    def __init__(self, rows, total):
        self._rows, self._total, self._mode, self._it = rows, total, None, None

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "COUNT(*) FROM prices" in s and "GROUP BY" not in s:
            self._mode = "count"
        elif "GROUP BY ticker, interval" in s:
            self._mode = "checksum"
        else:
            self._mode, self._it = "select", iter(self._rows)

    def fetchone(self):
        return (self._total,) if self._mode == "count" else None

    def fetchall(self):
        return _checksum(self._rows) if self._mode == "checksum" else []

    def fetchmany(self, n):
        out = []
        for _ in range(n):
            try:
                out.append(next(self._it))
            except StopIteration:
                break
        return out


class _FakePG:
    def __init__(self, rows, total):
        self._c = _FakeCursor(rows, total)

    def cursor(self):
        return self._c

    def close(self):
        pass


@pytest.fixture()
def fake_pg(monkeypatch):
    """Patch _pg_conn → fake serving _ROWS with a matching total (happy path)."""
    monkeypatch.setattr(mda, "_pg_conn", lambda: _FakePG(_ROWS, len(_ROWS)))


# --- admin core ---------------------------------------------------------------

def test_local_stats_missing(tmp_path):
    s = mda.local_prices_stats(str(tmp_path / "nope.db"))
    assert s == {"exists": False, "row_count": 0, "ticker_count": 0, "latest_datetime": None}


def test_bootstrap_builds_and_validates(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    res = mda.bootstrap_prices(out)
    assert res["match"] is True and res["rows"] == 3 and res["groups"] == 2
    # tmp swapped in; no leftover .building
    assert not (tmp_path / "market_data.db.building").exists()
    stats = mda.local_prices_stats(out)
    assert stats == {"exists": True, "row_count": 3, "ticker_count": 2,
                     "latest_datetime": "2026-06-01T09:15:00+0000"}


def test_bootstrap_mismatch_keeps_existing_db(tmp_path, monkeypatch):
    out = str(tmp_path / "market_data.db")
    # pre-existing good DB with a sentinel row
    conn = sqlite3.connect(out)
    conn.executescript(mda._SCHEMA)
    conn.execute("INSERT INTO prices VALUES ('OLD','2020-01-01T00:00:00+0000','15min',1,1,1,1,1)")
    conn.commit(); conn.close()
    # PG claims more rows than it yields → validation mismatch
    monkeypatch.setattr(mda, "_pg_conn", lambda: _FakePG(_ROWS, len(_ROWS) + 99))
    res = mda.bootstrap_prices(out)
    assert res["match"] is False
    assert not (tmp_path / "market_data.db.building").exists()  # discarded
    # existing DB untouched — still the sentinel row only
    assert mda.local_prices_stats(out)["row_count"] == 1


def test_validate_prices(tmp_path, fake_pg):
    out = str(tmp_path / "market_data.db")
    mda.bootstrap_prices(out)
    r = mda.validate_prices(out)
    assert r["match"] is True and r["local_rows"] == 3 and r["pg_rows"] == 3


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
    assert out["prices"]["exists"] is False
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
