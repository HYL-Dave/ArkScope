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


def test_local_capability_protocol_matches_inventory_method_set():
    import importlib

    module = importlib.import_module("src.tools.backends.local_capabilities")
    protocol = module.LocalDataCapabilities
    public_callables = {
        name
        for name, value in vars(protocol).items()
        if not name.startswith("_") and callable(value)
    }
    assert public_callables == {
        "accept_sa_article_link",
        "apply_sa_refresh",
        "audit_unresolved_symbols",
        "get_available_tickers",
        "get_sa_article_with_comments",
        "get_sa_pick_detail",
        "get_sa_refresh_meta",
        "invalidate_dirty_sa_market_news_detail",
        "query_fundamentals",
        "query_health_stats",
        "query_news",
        "query_news_feed",
        "query_news_search",
        "query_news_stats",
        "query_prices",
        "query_sa_article_review_queue",
        "query_sa_articles",
        "query_sa_market_news",
        "query_sa_market_news_body_presence",
        "query_sa_market_news_missing_detail_interval",
        "query_sa_market_news_need_detail",
        "query_sa_market_news_recent_ids",
        "query_sa_market_news_recovery_rows",
        "query_sa_picks",
        "query_sec_filings",
        "reconcile_sa_articles",
        "record_sa_refresh_failure",
        "reject_sa_article_candidate",
        "resolve_sa_reconciliation_event",
        "sanitize_corrupted_sa_comments_counts",
        "save_article_with_comments",
        "save_sa_market_news_detail",
        "update_article_comments",
        "update_sa_pick_detail",
        "upsert_sa_articles_meta",
        "upsert_sa_market_news",
    }
    assert not getattr(protocol, "_is_runtime_protocol", False)


def test_default_data_access_constructs_current_local_authority(tmp_path):
    import inspect

    assert "db_dsn" not in inspect.signature(DataAccessLayer).parameters
    local = DataAccessLayer(base_path=tmp_path)
    assert type(local._backend).__name__ == "SACaptureBackend"
    assert not hasattr(local, "_db_dsn")


def test_explicit_capability_injection_needs_no_nominal_type_routing(tmp_path):
    class StructuralCapability:
        def __init__(self):
            self.calls = []

        def query_sa_market_news(self, **kwargs):
            self.calls.append(kwargs)
            return [{"news_id": "local-1"}]

    capability = StructuralCapability()
    local = DataAccessLayer(base_path=tmp_path, backend=capability)

    assert local.get_sa_market_news(ticker="NVDA", limit=3) == [
        {"news_id": "local-1"}
    ]
    assert capability.calls == [{"ticker": "NVDA", "keyword": None, "limit": 3}]


def test_runtime_backend_module_graph_matches_current_local_modules(tmp_path):
    import subprocess

    code = f"""
import sys
sys.path.insert(0, {str(project_root)!r})
from src.tools.data_access import DataAccessLayer
local = DataAccessLayer(base_path={str(tmp_path)!r})
required = {{
    'src.tools.backends.local_capabilities',
    'src.tools.backends.local_market_backend',
    'src.tools.backends.sa_capture_backend',
    'src.tools.backends.sqlite_backend',
}}
forbidden = {{
    'src.tools.backends.db_backend',
    'src.tools.backends.db_config',
    'psycopg2',
}}
assert required <= set(sys.modules), sorted(required - set(sys.modules))
assert not (forbidden & set(sys.modules)), sorted(forbidden & set(sys.modules))
assert type(local._backend).__name__ == 'SACaptureBackend'
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


# ============================================================
# Config Access
# ============================================================

class TestConfigAccess:
    def test_get_watchlist(self, dal):
        """get_watchlist() should return tickers from user_profile.yaml."""
        assert not hasattr(dal, "_load_json")
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

# ============================================================
# News
# ============================================================

class TestNews:
    def test_get_news_ticker(self, dal):
        """get_news() should filter by ticker."""
        result = dal.get_news(ticker="NVDA", days=9999)
        assert isinstance(result, NewsQueryResult)
        assert result.ticker == "NVDA"
        for article in result.articles:
            assert article.ticker == "NVDA"

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

    def test_get_prices_df(self, dal):
        """get_prices_df() should return raw DataFrame."""
        df = dal.get_prices_df("NVDA", interval="15min", days=30)
        assert isinstance(df, type(df))  # pandas DataFrame
        assert "close" in df.columns

# ============================================================
# Fundamentals
# ============================================================

class TestFundamentals:
    def test_fundamentals_empty_ticker(self, dal):
        """Non-existent ticker should return empty result."""
        result = dal.get_fundamentals("XXXNOTREAL")
        assert isinstance(result, FundamentalsResult)
        assert result.ticker == "XXXNOTREAL"
        assert result.market_cap is None

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
