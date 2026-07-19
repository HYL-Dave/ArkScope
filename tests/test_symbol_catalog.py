"""Tests for the local symbol catalog + /symbols/search route (no network)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src import active_universe, sa_capture_store, symbol_catalog
from src.api.routes import symbols as symbol_routes
from src.api.routes.symbols import symbols_search
from src.portfolio_state import PortfolioStore
from src.profile_state import ProfileStateStore

_CATALOG = [
    {"ticker": "AAPL", "name": "Apple Inc."},
    {"ticker": "AABA", "name": "Altaba Inc."},
    {"ticker": "MSFT", "name": "Microsoft Corp"},
    {"ticker": "NVDA", "name": "NVIDIA Corp"},
    {"ticker": "PLTR", "name": "Palantir Technologies"},
    {"ticker": "BRK.B", "name": "Berkshire Hathaway Class B"},
    {"ticker": "BRK B", "name": "Berkshire Hathaway Class B Space"},
]

NOW_TEXT = "2026-07-19T12:00:00+00:00"


def _insert_sa_pick(path: Path, symbol: str) -> None:
    symbol_key = symbol.strip().upper()
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sa_pick_lineages "
            "(symbol_key, picked_date, created_at) VALUES (?, '2026-07-01', ?)",
            (symbol_key, NOW_TEXT),
        )
        lineage_id = conn.execute(
            "SELECT lineage_id FROM sa_pick_lineages "
            "WHERE symbol_key=? AND picked_date='2026-07-01'",
            (symbol_key,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO sa_alpha_picks "
            "(lineage_id, symbol, company, picked_date, portfolio_status, is_stale) "
            "VALUES (?, ?, ?, '2026-07-01', 'current', 0)",
            (lineage_id, symbol, f"{symbol_key} Inc"),
        )


def _set_sa_current_refresh(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sa_refresh_meta "
            "(scope, last_attempt_at, last_success_at, ok, updated_at) "
            "VALUES ('current', ?, ?, 1, ?)",
            (NOW_TEXT, NOW_TEXT, NOW_TEXT),
        )


@pytest.fixture(autouse=True)
def _seed_catalog():
    symbol_catalog.set_catalog_for_tests(_CATALOG)
    yield
    symbol_catalog.reset_for_tests()


@pytest.fixture()
def symbol_databases(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile_state.db"
    sa_path = tmp_path / "sa_capture.db"
    profile = ProfileStateStore(profile_path)
    portfolio = PortfolioStore(profile_path)
    conn = sa_capture_store.connect(str(sa_path))
    conn.close()
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(sa_path))
    return SimpleNamespace(
        profile_path=profile_path,
        sa_path=sa_path,
        profile=profile,
        portfolio=portfolio,
    )


def test_search_ranks_exact_then_prefix_then_name():
    # exact ticker first, then prefix
    res = symbol_catalog.search("AA")
    tickers = [r["ticker"] for r in res]
    assert tickers[:2] == ["AABA", "AAPL"]  # both prefix "AA", sorted

    res = symbol_catalog.search("AAPL")
    assert res[0]["ticker"] == "AAPL"  # exact wins

    # name substring match (no ticker match)
    res = symbol_catalog.search("micro")
    assert [r["ticker"] for r in res] == ["MSFT"]

    # nonsense → empty (typo-catch: caller shows "no match")
    assert symbol_catalog.search("ZZZZQ") == []
    assert symbol_catalog.search("") == []


def test_search_respects_limit():
    assert len(symbol_catalog.search("A", limit=2)) == 2


def test_local_seed_uses_accepted_snapshot_without_legacy_reference(
    symbol_databases, monkeypatch
):
    symbol_databases.profile.import_lists(
        [{"name": "Accepted", "kind": "custom", "tickers": ["ACCEPTED"]}]
    )
    symbol_catalog.reset_for_tests()
    monkeypatch.setattr(symbol_catalog, "_load_sec", lambda force: {})

    catalog = symbol_catalog.load_catalog(force=True)

    assert catalog == [{"ticker": "ACCEPTED", "name": ""}]

    symbol_databases.profile.import_lists(
        [{"name": "Accepted", "kind": "custom", "tickers": ["SECOND"]}]
    )
    assert symbol_catalog.load_catalog() == [
        {"ticker": "ACCEPTED", "name": ""},
        {"ticker": "SECOND", "name": ""},
    ]


def test_local_seed_unavailable_keeps_sec_catalog_without_fake_active_seed(
    symbol_databases, monkeypatch, caplog
):
    hostile_path = symbol_databases.sa_path.parent / "password=do-not-log.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(hostile_path))
    symbol_catalog.reset_for_tests()
    monkeypatch.setattr(
        symbol_catalog,
        "_load_sec",
        lambda force: {"SECONLY": "SEC Reference Corp"},
    )

    with caplog.at_level(logging.WARNING, logger="src.symbol_catalog"):
        catalog = symbol_catalog.load_catalog(force=True)

    assert catalog == [{"ticker": "SECONLY", "name": "SEC Reference Corp"}]
    assert "active_universe_unavailable" in caplog.text
    assert "do-not-log" not in caplog.text
    assert str(hostile_path) not in caplog.text


def test_local_seed_works_when_sec_unavailable(monkeypatch):
    # SEC blocked/offline (403 → {}), but local universe still makes RKLB/MXL findable.
    symbol_catalog.reset_for_tests()
    monkeypatch.setattr(symbol_catalog, "_local_seed", lambda: {"RKLB": "", "MXL": "", "NVDA": ""})
    monkeypatch.setattr(symbol_catalog, "_load_sec", lambda force: {})
    cat = symbol_catalog.load_catalog(force=True)
    tickers = {e["ticker"] for e in cat}
    assert {"RKLB", "MXL", "NVDA"} <= tickers
    assert symbol_catalog.search("RKLB")[0]["ticker"] == "RKLB"
    assert symbol_catalog.search("MXL")[0]["ticker"] == "MXL"


def test_cache_reoverlays_sec_names_when_stale(monkeypatch):
    # Active-seed churn rebuilds immediately without touching the independent SEC
    # success TTL. Once that TTL expires, SEC names refresh normally.
    symbol_catalog.reset_for_tests()
    success_calls = []

    def load_success(force):
        success_calls.append(force)
        name = "Rocket Lab" if len(success_calls) == 1 else "Rocket Lab Refreshed"
        return {"RKLB": name}

    monkeypatch.setattr(symbol_catalog, "_load_sec", load_success)
    initial = symbol_catalog.load_catalog(force=True, active_tickers=("RKLB",))
    initial_sec_checked_at = symbol_catalog._sec_checked_at
    assert initial == [{"ticker": "RKLB", "name": "Rocket Lab"}]
    assert success_calls == [True]

    changed = symbol_catalog.load_catalog(active_tickers=("MXL", "RKLB"))
    assert {row["ticker"] for row in changed} == {"MXL", "RKLB"}
    assert symbol_catalog._cache_seed_key == ("MXL", "RKLB")
    assert success_calls == [True]
    assert symbol_catalog._sec_checked_at == initial_sec_checked_at

    symbol_catalog._sec_checked_at = (
        symbol_catalog.time.time() - symbol_catalog._TTL_SECONDS
    )
    refreshed = symbol_catalog.load_catalog(active_tickers=("MXL", "RKLB"))
    assert success_calls == [True, False]
    assert next(row for row in refreshed if row["ticker"] == "RKLB")["name"] == (
        "Rocket Lab Refreshed"
    )

    # The failed-SEC retry clock is independent too: seed churn cannot postpone
    # the backoff retry that lets a long-running process self-heal.
    symbol_catalog.reset_for_tests()
    failure_calls = []

    def load_after_failure(force):
        failure_calls.append(force)
        return {} if len(failure_calls) == 1 else {"RKLB": "Rocket Lab Recovered"}

    monkeypatch.setattr(symbol_catalog, "_load_sec", load_after_failure)
    failed = symbol_catalog.load_catalog(force=True, active_tickers=("RKLB",))
    failed_sec_checked_at = symbol_catalog._sec_checked_at
    assert failed == [{"ticker": "RKLB", "name": ""}]

    changed_after_failure = symbol_catalog.load_catalog(
        active_tickers=("MXL", "RKLB")
    )
    assert {row["ticker"] for row in changed_after_failure} == {"MXL", "RKLB"}
    assert failure_calls == [True]
    assert symbol_catalog._sec_checked_at == failed_sec_checked_at

    symbol_catalog._sec_checked_at = (
        symbol_catalog.time.time() - symbol_catalog._RETRY_AFTER_SEC_FAIL
    )
    recovered = symbol_catalog.load_catalog(active_tickers=("MXL", "RKLB"))
    assert failure_calls == [True, False]
    assert next(row for row in recovered if row["ticker"] == "RKLB")["name"] == (
        "Rocket Lab Recovered"
    )


def test_sec_overlay_enriches_names(monkeypatch):
    symbol_catalog.reset_for_tests()
    monkeypatch.setattr(symbol_catalog, "_local_seed", lambda: {"RKLB": ""})
    monkeypatch.setattr(symbol_catalog, "_load_sec", lambda force: {"RKLB": "Rocket Lab", "TSLA": "Tesla Inc"})
    cat = {e["ticker"]: e["name"] for e in symbol_catalog.load_catalog(force=True)}
    assert cat["RKLB"] == "Rocket Lab"  # SEC name fills the local-seed blank
    assert cat["TSLA"] == "Tesla Inc"   # SEC-only ticker also present


def test_route_flags_tracked(symbol_databases, monkeypatch):
    store = symbol_databases.profile
    store.import_lists(
        [
            {"name": "Active", "kind": "custom", "tickers": ["BRK.B", "BRK B"]},
            {"name": "History", "kind": "custom", "tickers": ["MSFT"]},
        ]
    )
    store.archive_ticker("MSFT")
    store.set_universe_hidden("BRK.B", True)
    _insert_sa_pick(symbol_databases.sa_path, "NVDA")
    _set_sa_current_refresh(symbol_databases.sa_path)

    symbol_catalog.reset_for_tests()
    sec_calls = []

    def load_sec(force):
        sec_calls.append(force)
        return {
            "NVDA": "NVIDIA Match",
            "MSFT": "Microsoft Match",
            "BRK.B": "Berkshire Hidden Match",
            "BRK B": "Berkshire Active Match",
        }

    snapshot_calls = []

    def build_route_snapshot(*, profile_db):
        snapshot_calls.append(profile_db)
        return active_universe.build_active_universe_snapshot(
            profile_db=profile_db,
            sa_db=symbol_databases.sa_path,
        )

    def reject_duplicate_snapshot(**kwargs):
        raise AssertionError("symbol catalog opened a duplicate active snapshot")

    monkeypatch.setattr(symbol_catalog, "_load_sec", load_sec)
    monkeypatch.setattr(
        symbol_catalog, "build_active_universe_snapshot", reject_duplicate_snapshot
    )
    monkeypatch.setattr(
        symbol_routes, "build_active_universe_snapshot", build_route_snapshot
    )

    response = symbols_search(q="match", limit=10, store=store)
    by_ticker = {row["ticker"]: row for row in response["results"]}

    assert snapshot_calls == [store.db_path]
    assert sec_calls == [False]
    assert symbol_catalog._cache_seed_key == ("BRK B", "NVDA")
    assert by_ticker["NVDA"]["tracked"] is True  # Alpha Picks only
    assert by_ticker["MSFT"]["tracked"] is False  # archived list history only
    assert by_ticker["BRK.B"]["tracked"] is False
    assert by_ticker["BRK B"]["tracked"] is True


def test_symbol_search_unavailable_returns_sanitized_503(
    symbol_databases, monkeypatch
):
    hostile_path = symbol_databases.sa_path.parent / "password=do-not-leak.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(hostile_path))

    with pytest.raises(HTTPException) as caught:
        symbols_search(q="NVDA", limit=10, store=symbol_databases.profile)

    assert caught.value.status_code == 503
    assert caught.value.detail == {
        "code": "active_universe_unavailable",
        "status": "unavailable",
        "unavailable_sources": ["sa_alpha_picks_current"],
        "source_reasons": {"sa_alpha_picks_current": "source_db_missing"},
    }
    rendered = repr(caught.value.detail)
    assert "do-not-leak" not in rendered
    assert str(hostile_path) not in rendered
