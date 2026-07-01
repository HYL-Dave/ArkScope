"""#3 — SEC fundamentals cache + User-Agent hardening.

The 22 'missing' tickers already resolve via the SEC EDGAR fallback in
get_fundamentals_analysis, but that branch was UNCACHED → it re-hit SEC live every call.
These tests pin: (a) the SEC branch reads/writes the local financial_cache (local-first,
strict/no-PG safe); (b) only successful results are cached, with a short negative-cache
TTL for no-data; (c) the SEC User-Agent reads the canonical ARKSCOPE_SEC_USER_AGENT with
back-compat for the legacy vars.
"""

from __future__ import annotations

import pytest

import src.tools.analysis_tools as at
from src.tools.schemas import FundamentalsResult


class _FakeBackend:
    """Local-first financial_cache double (no PG): cache_key → dict."""
    def __init__(self):
        self.store = {}
        self.set_calls = []
    def get_financial_cache(self, cache_key):
        return self.store.get(cache_key)
    def set_financial_cache(self, cache_key, ticker, data, ttl_days=90, source="sec_edgar"):
        self.set_calls.append((cache_key, ticker, ttl_days, source))
        self.store[cache_key] = data


class _FakeDAL:
    def __init__(self, backend):
        self._backend = backend
    def get_fundamentals(self, ticker):
        return FundamentalsResult(ticker=ticker.upper())  # no IBKR snapshot → SEC branch


def _sec_returns(monkeypatch, income=None, balance=None, cashflow=None):
    """Stub SECEdgarFinancials so no live HTTP — control what the SEC branch 'fetches'."""
    class _FakeSEC:
        def __init__(self, *a, **k): pass
        def get_income_statement(self, t, years=2, period="annual"): return income or []
        def get_balance_sheet(self, t, years=1, period="annual"): return balance or []
        def get_cash_flow_statement(self, t, years=2, period="annual"): return cashflow or []
    import data_sources.sec_edgar_financials as sec_mod
    monkeypatch.setattr(sec_mod, "SECEdgarFinancials", _FakeSEC)
    # neutralize the FD branch + IBKR-snapshot path
    monkeypatch.setattr(at, "_is_fd_enabled", lambda dal: False)


def test_sec_result_is_cached_then_served_from_cache(monkeypatch):
    be = _FakeBackend(); dal = _FakeDAL(be)
    calls = {"sec": 0}
    income = [type("S", (), {"report_period": "2025-12-31"})()]
    class _CountingSEC:
        def __init__(self,*a,**k): pass
        def get_income_statement(self,t,years=2,period="annual"): calls.__setitem__("sec", calls["sec"]+1); return income
        def get_balance_sheet(self,t,years=1,period="annual"): return []
        def get_cash_flow_statement(self,t,years=2,period="annual"): return []
    import data_sources.sec_edgar_financials as sec_mod
    monkeypatch.setattr(sec_mod, "SECEdgarFinancials", _CountingSEC)
    monkeypatch.setattr(at, "_is_fd_enabled", lambda dal: False)
    monkeypatch.setattr(at, "_build_result_from_statements",
                        lambda t, src, i, b, c: FundamentalsResult(ticker=t.upper(), data_source=src, snapshot_date="2025-12-31"))

    r1 = at.get_fundamentals_analysis(dal, "GM")
    assert r1.data_source == "sec_edgar" and calls["sec"] == 1
    assert be.set_calls and be.set_calls[0][0].startswith("fundamentals_analysis:sec_edgar:GM:annual")

    r2 = at.get_fundamentals_analysis(dal, "GM")          # 2nd call → cache hit, no SEC
    assert r2.data_source == "sec_edgar" and calls["sec"] == 1  # SEC NOT hit again


def test_sec_empty_uses_short_negative_cache(monkeypatch):
    be = _FakeBackend(); dal = _FakeDAL(be)
    _sec_returns(monkeypatch, income=[], balance=[])      # no data (non-US / CIK miss)
    monkeypatch.setattr(at, "_is_fd_enabled", lambda dal: False)
    at.get_fundamentals_analysis(dal, "VISN")
    # a negative result is cached with a SHORT ttl so we don't hammer SEC, but not the 90d one
    assert be.set_calls, "negative result should be cached to avoid repeated SEC hits"
    neg = be.set_calls[-1]
    assert neg[2] <= 7  # short negative TTL (days)


def test_sec_cache_miss_then_hit_round_trips_result(monkeypatch):
    be = _FakeBackend(); dal = _FakeDAL(be)
    income = [type("S", (), {"report_period": "2025-12-31"})()]
    _sec_returns(monkeypatch, income=income)
    monkeypatch.setattr(at, "_build_result_from_statements",
                        lambda t, src, i, b, c: FundamentalsResult(ticker=t.upper(), data_source=src, roe=0.21))
    r1 = at.get_fundamentals_analysis(dal, "DELL")
    r2 = at.get_fundamentals_analysis(dal, "DELL")        # served from cache
    assert r1.roe == r2.roe == 0.21 and r2.data_source == "sec_edgar"


def test_sec_cache_hit_with_local_market_backend_does_not_pg_fallback(monkeypatch):
    from src.tools.schemas import FundamentalsResult

    class _Market:
        def __init__(self):
            self.calls = []

        def get_financial_cache(self, cache_key):
            self.calls.append(cache_key)
            return FundamentalsResult(
                ticker="AAPL",
                data_source="sec_edgar",
                snapshot_date="2025-12-31",
                roe=0.33,
            ).model_dump()

    class _LocalMarketLike:
        def __init__(self):
            self._market = _Market()
            self.pg_calls = []

        def get_financial_cache(self, cache_key):
            self.pg_calls.append(cache_key)
            raise AssertionError("PG cache fallback must not be used for fundamentals")

        def set_financial_cache(self, *args, **kwargs):
            raise AssertionError("cache hit must not write")

    class _DAL:
        def __init__(self):
            self._backend = _LocalMarketLike()

        def get_fundamentals(self, ticker):
            return FundamentalsResult(ticker=ticker.upper())

    monkeypatch.setattr(at, "_is_fd_enabled", lambda dal: False)
    dal = _DAL()

    result = at.get_fundamentals_analysis(dal, "AAPL")

    assert result.data_source == "sec_edgar"
    assert result.roe == 0.33
    assert dal._backend._market.calls == [
        "fundamentals_analysis:sec_edgar:AAPL:annual:v1"
    ]
    assert dal._backend.pg_calls == []


def test_sec_cache_miss_writes_with_shared_cache_key(monkeypatch):
    from src.fundamentals.cache import fundamentals_analysis_cache_key
    from src.tools.schemas import FundamentalsResult

    class _Backend:
        def __init__(self):
            self.store = {}
            self.set_calls = []

        def get_financial_cache(self, cache_key):
            return self.store.get(cache_key)

        def set_financial_cache(self, cache_key, ticker, data, ttl_days=90, source="sec_edgar"):
            self.set_calls.append((cache_key, ticker, ttl_days, source, data))
            self.store[cache_key] = data
            return True

    class _DAL:
        def __init__(self):
            self._backend = _Backend()

        def get_fundamentals(self, ticker):
            return FundamentalsResult(ticker=ticker.upper())

    class _FakeSEC:
        def get_income_statement(self, ticker, years=2, period="annual"):
            return [type("Statement", (), {"report_period": "2025-12-31"})()]

        def get_balance_sheet(self, ticker, years=1, period="annual"):
            return []

        def get_cash_flow_statement(self, ticker, years=2, period="annual"):
            return []

    import data_sources.sec_edgar_financials as sec_mod
    monkeypatch.setattr(sec_mod, "SECEdgarFinancials", lambda: _FakeSEC())
    monkeypatch.setattr(at, "_is_fd_enabled", lambda dal: False)
    monkeypatch.setattr(
        at,
        "_build_result_from_statements",
        lambda t, src, i, b, c: FundamentalsResult(
            ticker=t.upper(),
            data_source=src,
            snapshot_date="2025-12-31",
            roe=0.44,
        ),
    )

    dal = _DAL()
    result = at.get_fundamentals_analysis(dal, "AAPL")

    expected_key = fundamentals_analysis_cache_key("AAPL", "annual")
    assert result.data_source == "sec_edgar"
    assert result.roe == 0.44
    assert dal._backend.set_calls
    assert dal._backend.set_calls[0][:4] == (expected_key, "AAPL", 90, "sec_edgar")
    assert dal._backend.store[expected_key]["roe"] == 0.44


# --- SEC User-Agent canonicalization (ARKSCOPE_SEC_USER_AGENT) ----------------------

def test_user_agent_prefers_canonical_arkscope_var(monkeypatch):
    import data_sources.sec_edgar_financials as sec
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "ArkScope ops@arkscope.test")
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "legacy@old.test")
    assert sec._get_sec_user_agent() == "ArkScope ops@arkscope.test"  # canonical wins


def test_user_agent_back_compat_legacy_vars(monkeypatch):
    import data_sources.sec_edgar_financials as sec
    monkeypatch.delenv("ARKSCOPE_SEC_USER_AGENT", raising=False)
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "legacy@old.test")
    assert "legacy@old.test" in sec._get_sec_user_agent()  # legacy still honored
