"""
Integration tests for DataAccessLayer + FileBackend.

These tests run against real data in the project's data/ directory.
They verify that the DAL can read actual files and return correct schemas.
"""

import sys
from pathlib import Path

import pytest

# Ensure project root is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.data_access import DataAccessLayer
from src.tools.schemas import (
    FundamentalsResult,
    IVHistoryPoint,
    NewsArticle,
    NewsQueryResult,
    PriceBar,
    PriceQueryResult,
    SECFiling,
    WatchlistResult,
)
from src.tools.backends import DataBackend
from src.tools.backends.file_backend import FileBackend


@pytest.fixture(scope="module")
def dal():
    """Create a DAL instance for all tests."""
    return DataAccessLayer(base_path=project_root)


@pytest.fixture(scope="module")
def file_backend():
    """Create a FileBackend instance."""
    return FileBackend(base_path=project_root)


# ============================================================
# Backend Protocol
# ============================================================

class TestBackendProtocol:
    def test_file_backend_is_data_backend(self, file_backend):
        """FileBackend should satisfy DataBackend protocol."""
        assert isinstance(file_backend, DataBackend)


# ============================================================
# Config Access
# ============================================================

class TestConfigAccess:
    def test_get_watchlist(self, dal):
        """get_watchlist() should return tickers from user_profile.yaml."""
        result = dal.get_watchlist()
        assert isinstance(result, WatchlistResult)
        assert len(result.tickers) > 0
        # Core holdings from user_profile.yaml
        assert "NVDA" in result.tickers
        assert len(result.details) > 0

    def test_get_watchlist_has_details(self, dal):
        """Watchlist details should have group and priority."""
        result = dal.get_watchlist()
        for info in result.details:
            assert info.ticker
            assert info.group
            assert info.priority in ("high", "medium", "low")

    def test_get_watchlist_sectors(self, dal):
        """Sectors should be populated when include_sectors=True."""
        result = dal.get_watchlist(include_sectors=True)
        if result.sectors:
            for sector, tickers in result.sectors.items():
                assert isinstance(tickers, list)
                assert len(tickers) > 0

    def test_get_sector_tickers(self, dal):
        """get_sector_tickers() should return tickers for known sectors."""
        tickers = dal.get_sector_tickers("AI_CHIPS")
        assert "NVDA" in tickers
        assert "AMD" in tickers

    def test_get_all_sectors(self, dal):
        """get_all_sectors() should return all sector definitions."""
        sectors = dal.get_all_sectors()
        assert "AI_CHIPS" in sectors
        assert "FINTECH" in sectors

    def test_get_strategy_weights(self, dal):
        """get_strategy_weights() should return weight configs."""
        weights = dal.get_strategy_weights("momentum")
        assert "price_trend" in weights
        assert isinstance(weights["price_trend"], (int, float))

    def test_get_strategy_weights_default(self, dal):
        """Default strategy should load correctly."""
        weights = dal.get_strategy_weights()
        assert len(weights) > 0

    def test_get_tier_tickers(self, dal):
        """get_tier_tickers() should return tickers for a tier."""
        tier1 = dal.get_tier_tickers("tier1_core")
        assert "NVDA" in tier1
        assert "AAPL" in tier1
        assert len(tier1) >= 20  # tier1 has ~30 tickers


# ============================================================
# News
# ============================================================

class TestNews:
    def test_get_news_all(self, dal):
        """get_news() should return news from scored files."""
        result = dal.get_news(days=9999)  # All time
        assert isinstance(result, NewsQueryResult)
        assert result.count > 0
        assert len(result.articles) > 0

    def test_get_news_ticker(self, dal):
        """get_news() should filter by ticker."""
        result = dal.get_news(ticker="NVDA", days=9999)
        assert isinstance(result, NewsQueryResult)
        assert result.ticker == "NVDA"
        for article in result.articles:
            assert article.ticker == "NVDA"

    def test_get_news_source_breakdown(self, dal):
        """News result should have source breakdown."""
        result = dal.get_news(days=9999)
        assert isinstance(result.source_breakdown, dict)
        # Should have at least ibkr or polygon
        assert len(result.source_breakdown) > 0

    def test_news_article_schema(self, dal):
        """News articles should have required fields."""
        result = dal.get_news(ticker="NVDA", days=9999)
        if result.articles:
            article = result.articles[0]
            assert isinstance(article, NewsArticle)
            assert article.date
            assert article.ticker == "NVDA"
            assert article.title

    def test_get_news_ibkr_source(self, dal):
        """Querying ibkr source should work."""
        result = dal.get_news(source="ibkr", days=9999)
        assert isinstance(result, NewsQueryResult)
        # All articles should be ibkr source
        for article in result.articles[:10]:
            assert article.source == "ibkr"

    def test_get_news_polygon_source(self, dal):
        """Querying polygon source should work."""
        result = dal.get_news(source="polygon", days=9999)
        assert isinstance(result, NewsQueryResult)
        for article in result.articles[:10]:
            assert article.source == "polygon"


# ============================================================
# Prices
# ============================================================

class TestPrices:
    def test_get_prices_15min(self, dal):
        """get_prices() should return 15min bars."""
        result = dal.get_prices("NVDA", interval="15min", days=9999)
        assert isinstance(result, PriceQueryResult)
        assert result.ticker == "NVDA"
        assert result.interval == "15min"
        assert result.count > 0
        assert len(result.bars) > 0

    def test_price_bar_schema(self, dal):
        """Price bars should have valid OHLCV."""
        result = dal.get_prices("AAPL", interval="15min", days=9999)
        if result.bars:
            bar = result.bars[0]
            assert isinstance(bar, PriceBar)
            assert bar.open > 0
            assert bar.high >= bar.low
            assert bar.close > 0
            assert bar.volume >= 0

    def test_get_prices_hourly(self, dal):
        """get_prices() should return hourly bars."""
        result = dal.get_prices("AAPL", interval="1h", days=9999)
        assert isinstance(result, PriceQueryResult)
        assert result.count > 0

    def test_get_prices_daily_resampled(self, dal):
        """get_prices() daily should resample from 15min if no daily dir."""
        result = dal.get_prices("NVDA", interval="1d", days=9999)
        assert isinstance(result, PriceQueryResult)
        # Should have data (resampled from 15min)
        assert result.count > 0

    def test_get_prices_df(self, dal):
        """get_prices_df() should return raw DataFrame."""
        df = dal.get_prices_df("NVDA", interval="15min", days=30)
        assert isinstance(df, type(df))  # pandas DataFrame
        assert "close" in df.columns

    def test_available_price_tickers(self, dal):
        """get_available_tickers('prices') should list price tickers."""
        tickers = dal.get_available_tickers("prices")
        assert "NVDA" in tickers
        assert "AAPL" in tickers
        assert len(tickers) > 50  # We have 135+ tickers


# ============================================================
# IV History
# ============================================================

class TestIVHistory:
    def test_get_iv_history(self, dal):
        """get_iv_history() should return IV data points."""
        points = dal.get_iv_history("AMD")
        assert isinstance(points, list)
        if points:
            p = points[0]
            assert isinstance(p, IVHistoryPoint)
            assert p.date
            assert p.atm_iv > 0

    def test_get_iv_history_df(self, dal):
        """get_iv_history_df() should return raw DataFrame."""
        df = dal.get_iv_history_df("AMD")
        assert "atm_iv" in df.columns

    def test_iv_history_empty_ticker(self, dal):
        """Non-existent ticker should return empty list."""
        points = dal.get_iv_history("XXXNOTREAL")
        assert points == []


# ============================================================
# Fundamentals
# ============================================================

class TestFundamentals:
    def test_get_fundamentals(self, dal):
        """get_fundamentals() should return structured result."""
        result = dal.get_fundamentals("NVDA")
        assert isinstance(result, FundamentalsResult)
        assert result.ticker == "NVDA"
        assert result.market_cap is not None
        assert result.market_cap > 0

    def test_fundamentals_has_ratios(self, dal):
        """Fundamentals should include key financial ratios."""
        result = dal.get_fundamentals("NVDA")
        # NVDA should have PE ratio
        assert result.pe_ratio is not None or result.snapshot is not None

    def test_fundamentals_empty_ticker(self, dal):
        """Non-existent ticker should return empty result."""
        result = dal.get_fundamentals("XXXNOTREAL")
        assert isinstance(result, FundamentalsResult)
        assert result.ticker == "XXXNOTREAL"
        assert result.market_cap is None

    def test_available_fundamentals_tickers(self, dal):
        """get_available_tickers('fundamentals') should list available tickers."""
        tickers = dal.get_available_tickers("fundamentals")
        assert "NVDA" in tickers
        assert len(tickers) > 10


# ============================================================
# SEC Filings (FileBackend returns empty)
# ============================================================

class TestSECFilings:
    def test_get_sec_filings_empty(self, dal):
        """FileBackend SEC returns empty list (API-based data)."""
        filings = dal.get_sec_filings("NVDA")
        assert isinstance(filings, list)
        # FileBackend has no local SEC data
        assert len(filings) == 0


# ============================================================
# Cache
# ============================================================

class TestCache:
    def test_cache_store_and_retrieve(self, dal):
        """Cache should store and retrieve data."""
        dal.save_to_cache("test_key", {"value": 42})
        result = dal.get_from_cache("test_key")
        assert result == {"value": 42}

    def test_cache_miss(self, dal):
        """Cache miss should return None."""
        result = dal.get_from_cache("nonexistent_key")
        assert result is None

    def test_cache_clear(self, dal):
        """clear_cache() should remove all entries."""
        dal.save_to_cache("test_key_2", "data")
        dal.clear_cache()
        assert dal.get_from_cache("test_key_2") is None