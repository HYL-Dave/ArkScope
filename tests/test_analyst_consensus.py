"""Tests for the analyst-consensus daily cache + derivation (no network)."""

from __future__ import annotations

from src.analyst_consensus import AnalystConsensusCache, derive_consensus


def _raw(sb=0, b=0, h=0, s=0, ss=0, pt=None):
    return {
        "recommendations": {"current": {
            "strongBuy": sb, "buy": b, "hold": h, "sell": s, "strongSell": ss, "period": "2026-06",
        }},
        "price_target": pt,
    }


def test_derive_rating_from_distribution():
    assert derive_consensus(_raw(sb=8, b=10, h=2))["rating"] == "Buy"
    assert derive_consensus(_raw(sb=20))["rating"] == "Strong Buy"
    assert derive_consensus(_raw(h=10))["rating"] == "Hold"
    assert derive_consensus(_raw(ss=10))["rating"] == "Strong Sell"
    d = derive_consensus(_raw(sb=3, b=1, h=0, s=0, ss=0))
    assert d["buy_ratio"] == 1.0 and d["total"] == 4 and d["source"] == "finnhub"
    # no coverage → null rating, not a crash
    none = derive_consensus(_raw())
    assert none["rating"] is None and none["total"] == 0


def test_cache_get_or_fetch_then_hit(tmp_path):
    cache = AnalystConsensusCache(tmp_path / "ac.db")
    calls = {"n": 0}

    def fetcher(t):
        calls["n"] += 1
        return _raw(sb=5, b=10, h=3)

    r1 = cache.get_or_fetch("nvda", fetcher)
    assert r1["ticker"] == "NVDA" and r1["rating"] == "Buy" and r1["cached"] is False
    r2 = cache.get_or_fetch("NVDA", fetcher)  # within TTL → cached, no re-fetch
    assert r2["cached"] is True
    assert calls["n"] == 1


def test_fetch_failure_yields_empty_summary(tmp_path):
    cache = AnalystConsensusCache(tmp_path / "ac.db")

    def boom(t):
        raise RuntimeError("no FINNHUB_API_KEY")

    r = cache.get_or_fetch("AAPL", boom)
    assert r["ticker"] == "AAPL" and r["rating"] is None and "error" in r
    # failure is not cached → a later (working) fetch still runs
    assert cache.get("AAPL") is None
