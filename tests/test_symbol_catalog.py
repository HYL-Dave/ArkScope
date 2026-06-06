"""Tests for the local symbol catalog + /symbols/search route (no network)."""

from __future__ import annotations

import pytest

from src import symbol_catalog
from src.api.routes.symbols import symbols_search
from src.profile_state import ProfileStateStore

_CATALOG = [
    {"ticker": "AAPL", "name": "Apple Inc."},
    {"ticker": "AABA", "name": "Altaba Inc."},
    {"ticker": "MSFT", "name": "Microsoft Corp"},
    {"ticker": "NVDA", "name": "NVIDIA Corp"},
    {"ticker": "PLTR", "name": "Palantir Technologies"},
]


@pytest.fixture(autouse=True)
def _seed_catalog():
    symbol_catalog.set_catalog_for_tests(_CATALOG)
    yield
    symbol_catalog.reset_for_tests()


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


def test_sec_overlay_enriches_names(monkeypatch):
    symbol_catalog.reset_for_tests()
    monkeypatch.setattr(symbol_catalog, "_local_seed", lambda: {"RKLB": ""})
    monkeypatch.setattr(symbol_catalog, "_load_sec", lambda force: {"RKLB": "Rocket Lab", "TSLA": "Tesla Inc"})
    cat = {e["ticker"]: e["name"] for e in symbol_catalog.load_catalog(force=True)}
    assert cat["RKLB"] == "Rocket Lab"  # SEC name fills the local-seed blank
    assert cat["TSLA"] == "Tesla Inc"   # SEC-only ticker also present


def test_route_flags_tracked(tmp_path):
    store = ProfileStateStore(tmp_path / "p.db")
    store.import_lists([{"name": "Holdings", "kind": "holdings", "tickers": ["NVDA"]}])
    out = symbols_search(q="n", limit=10, store=store)
    by = {r["ticker"]: r for r in out["results"]}
    assert by["NVDA"]["tracked"] is True   # in a list
    assert by["NVDA"]["name"] == "NVIDIA Corp"
    # a catalog hit not in any list is not tracked
    assert by.get("MSFT", {}).get("tracked", False) is False or "MSFT" not in by
