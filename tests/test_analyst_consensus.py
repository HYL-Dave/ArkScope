"""Tests for the analyst-consensus daily cache + derivation (no network)."""

from __future__ import annotations

from src.analyst_consensus import (
    AnalystConsensusCache,
    derive_consensus,
    fetch_recommendation_consensus,
)


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


def test_non_ok_statuses_are_not_cached(tmp_path):
    cache = AnalystConsensusCache(tmp_path / "ac.db")
    from src.analyst_consensus import _empty_summary

    for status in ("no_coverage", "rate_limited", "missing_key", "provider_error"):
        r = cache.get_or_fetch("AAPL", lambda t, s=status: {**_empty_summary(), "status": s})
        assert r["status"] == status and r["rating"] is None
        assert cache.get("AAPL") is None  # not cached → a later working fetch still runs


def test_get_or_fetch_never_raises_on_fetcher_error(tmp_path):
    cache = AnalystConsensusCache(tmp_path / "ac.db")

    def boom(t):
        raise RuntimeError("boom")

    r = cache.get_or_fetch("AAPL", boom)
    assert r["ticker"] == "AAPL" and r["rating"] is None and r["status"] == "provider_error"


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self, resp):
        self.resp = resp

    def get(self, *args, **kwargs):
        return self.resp


def _patch_finnhub(monkeypatch, resp):
    import src.tools.analyst_tools as tools

    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(tools, "_throttle", lambda: None)
    monkeypatch.setattr(tools, "_get_finnhub_session", lambda: (_Session(resp), "test-key"))


def test_fetch_recommendation_consensus_splits_statuses(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert fetch_recommendation_consensus("AAPL")["status"] == "missing_key"

    _patch_finnhub(monkeypatch, _Resp(429, []))
    assert fetch_recommendation_consensus("AAPL")["status"] == "rate_limited"

    _patch_finnhub(monkeypatch, _Resp(200, []))
    assert fetch_recommendation_consensus("AAPL")["status"] == "no_coverage"

    _patch_finnhub(monkeypatch, _Resp(200, {"unexpected": True}))
    assert fetch_recommendation_consensus("AAPL")["status"] == "provider_error"

    _patch_finnhub(monkeypatch, _Resp(200, [_cur(sb=2, b=1, h=1)]))
    ok = fetch_recommendation_consensus("AAPL")
    assert ok["status"] == "ok"
    assert ok["rating"] == "Buy"
    assert ok["total"] == 4
