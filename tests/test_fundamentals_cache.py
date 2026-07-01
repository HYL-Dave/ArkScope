from __future__ import annotations

from src.fundamentals.cache import (
    fundamentals_analysis_cache_key,
    read_cached_sec_fundamentals,
)
from src.tools.schemas import FundamentalsResult


class _LocalStore:
    def __init__(self, rows):
        self.rows = dict(rows)
        self.calls = []

    def get_financial_cache(self, cache_key):
        self.calls.append(cache_key)
        return self.rows.get(cache_key)


class _LocalMarketBackend:
    def __init__(self, rows):
        self._market = _LocalStore(rows)
        self.pg_calls = []

    def get_financial_cache(self, cache_key):
        self.pg_calls.append(cache_key)
        raise AssertionError("generic LocalMarketDatabaseBackend cache getter must not run")


def test_fundamentals_analysis_cache_key_is_stable():
    assert (
        fundamentals_analysis_cache_key("aapl", "annual")
        == "fundamentals_analysis:sec_edgar:AAPL:annual:v1"
    )
    assert (
        fundamentals_analysis_cache_key(" nvda ", "quarterly")
        == "fundamentals_analysis:sec_edgar:NVDA:quarterly:v1"
    )


def test_read_cached_sec_fundamentals_uses_local_market_store_without_pg_fallback():
    key = fundamentals_analysis_cache_key("AAPL")
    backend = _LocalMarketBackend({
        key: FundamentalsResult(
            ticker="AAPL",
            data_source="sec_edgar",
            snapshot_date="2025-12-31",
            roe=0.21,
        ).model_dump()
    })

    result, negative = read_cached_sec_fundamentals(backend, "AAPL")

    assert negative is False
    assert result is not None
    assert result.ticker == "AAPL"
    assert result.data_source == "sec_edgar"
    assert result.roe == 0.21
    assert backend._market.calls == [key]
    assert backend.pg_calls == []


def test_read_cached_sec_fundamentals_returns_empty_on_miss():
    result, negative = read_cached_sec_fundamentals(_LocalMarketBackend({}), "MSFT")
    assert result is None
    assert negative is False


def test_read_cached_sec_fundamentals_recognizes_negative_cache():
    key = fundamentals_analysis_cache_key("VISN")
    result, negative = read_cached_sec_fundamentals(
        _LocalMarketBackend({key: {"_negative": True}}),
        "VISN",
    )
    assert result is None
    assert negative is True


def test_read_cached_sec_fundamentals_ignores_incompatible_payload():
    key = fundamentals_analysis_cache_key("BAD")
    result, negative = read_cached_sec_fundamentals(
        _LocalMarketBackend({key: {"ticker": object()}}),
        "BAD",
    )
    assert result is None
    assert negative is False
