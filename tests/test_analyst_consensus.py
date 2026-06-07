"""Tests for the analyst-consensus daily cache + derivation (no network)."""

from __future__ import annotations

from src.analyst_consensus import AnalystConsensusCache, derive_consensus


def _cur(sb=0, b=0, h=0, s=0, ss=0):
    return {"strongBuy": sb, "buy": b, "hold": h, "sell": s, "strongSell": ss, "period": "2026-06"}


def test_derive_rating_from_distribution():
    assert derive_consensus(_cur(sb=8, b=10, h=2))["rating"] == "Buy"
    assert derive_consensus(_cur(sb=20))["rating"] == "Strong Buy"
    assert derive_consensus(_cur(h=10))["rating"] == "Hold"
    assert derive_consensus(_cur(ss=10))["rating"] == "Strong Sell"
    d = derive_consensus(_cur(sb=3, b=1))
    assert d["buy_ratio"] == 1.0 and d["total"] == 4 and d["source"] == "finnhub"
    # None / empty current → empty summary (caller decides no-coverage vs transient)
    none = derive_consensus(None)
    assert none["rating"] is None and none["total"] == 0


def _ok_fetcher(t):
    s = derive_consensus(_cur(sb=5, b=10, h=3))
    s["status"] = "ok"
    return s


def test_cache_only_caches_ok_and_hits(tmp_path):
    cache = AnalystConsensusCache(tmp_path / "ac.db")
    calls = {"n": 0}

    def fetcher(t):
        calls["n"] += 1
        return _ok_fetcher(t)

    r1 = cache.get_or_fetch("nvda", fetcher)
    assert r1["ticker"] == "NVDA" and r1["rating"] == "Buy" and r1["status"] == "ok" and r1["cached"] is False
    r2 = cache.get_or_fetch("NVDA", fetcher)  # within TTL → cached, no re-fetch
    assert r2["status"] == "cached" and r2["cached"] is True
    assert calls["n"] == 1


def test_transient_and_no_data_are_not_cached(tmp_path):
    cache = AnalystConsensusCache(tmp_path / "ac.db")
    from src.analyst_consensus import _empty_summary

    # no_data (ambiguous: no coverage OR 429/network) must NOT be cached
    r = cache.get_or_fetch("AAPL", lambda t: {**_empty_summary(), "status": "no_data"})
    assert r["status"] == "no_data" and r["rating"] is None
    assert cache.get("AAPL") is None  # not cached → a later working fetch still runs

    # missing_key likewise uncached
    r2 = cache.get_or_fetch("MSFT", lambda t: {**_empty_summary(), "status": "missing_key"})
    assert r2["status"] == "missing_key"
    assert cache.get("MSFT") is None


def test_get_or_fetch_never_raises_on_fetcher_error(tmp_path):
    cache = AnalystConsensusCache(tmp_path / "ac.db")

    def boom(t):
        raise RuntimeError("boom")

    r = cache.get_or_fetch("AAPL", boom)
    assert r["ticker"] == "AAPL" and r["rating"] is None and r["status"] == "provider_error"
