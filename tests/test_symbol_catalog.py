"""Tests for the local symbol catalog + /symbols/search route (no network)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src import sa_capture_store, symbol_catalog
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
    # First load with SEC down → blank names; once stale, a later load picks up
    # SEC names without a process restart (self-heal).
    symbol_catalog.reset_for_tests()
    monkeypatch.setattr(symbol_catalog, "_local_seed", lambda: {"RKLB": ""})
    monkeypatch.setattr(symbol_catalog, "_load_sec", lambda force: {})  # SEC down
    symbol_catalog.load_catalog(force=True)
    assert symbol_catalog.search("RKLB")[0]["name"] == ""  # blank for now
    # SEC recovers; mark the in-memory cache stale → next (force=False) load rebuilds
    monkeypatch.setattr(symbol_catalog, "_load_sec", lambda force: {"RKLB": "Rocket Lab"})
    symbol_catalog._cache_built_at = 0.0
    symbol_catalog.load_catalog()  # not forced, but stale → re-overlay
    assert symbol_catalog.search("RKLB")[0]["name"] == "Rocket Lab"


def test_sec_overlay_enriches_names(monkeypatch):
    symbol_catalog.reset_for_tests()
    monkeypatch.setattr(symbol_catalog, "_local_seed", lambda: {"RKLB": ""})
    monkeypatch.setattr(symbol_catalog, "_load_sec", lambda force: {"RKLB": "Rocket Lab", "TSLA": "Tesla Inc"})
    cat = {e["ticker"]: e["name"] for e in symbol_catalog.load_catalog(force=True)}
    assert cat["RKLB"] == "Rocket Lab"  # SEC name fills the local-seed blank
    assert cat["TSLA"] == "Tesla Inc"   # SEC-only ticker also present


def test_route_flags_tracked(symbol_databases):
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

    nvda = symbols_search(q="NVDA", limit=10, store=store)["results"][0]
    msft = symbols_search(q="MSFT", limit=10, store=store)["results"][0]
    brk = {
        row["ticker"]: row
        for row in symbols_search(q="BRK", limit=10, store=store)["results"]
    }

    assert nvda["tracked"] is True  # active only through Alpha Picks
    assert nvda["name"] == "NVIDIA Corp"
    assert msft["tracked"] is False  # archived list history is not active
    assert brk["BRK.B"]["tracked"] is False
    assert brk["BRK B"]["tracked"] is True


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
