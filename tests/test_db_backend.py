"""
Tests for DatabaseBackend against PostgreSQL.

These tests require:
1. DATABASE_URL configured in config/.env
2. Schema created via sql/001_init_schema.sql
3. Data imported via scripts/migrate_to_supabase.py

Tests are auto-skipped if DB is not available.

Run:
    pytest tests/test_db_backend.py -v
"""

import pytest
from pathlib import Path

import pandas as pd

from src.tools.backends import DataBackend
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.data_access import DataAccessLayer
from src.tools.db_config import load_database_url, load_sslmode

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ENV_PATH = Path("config/.env")
_DSN = load_database_url(_ENV_PATH)
_SSLMODE = load_sslmode(_ENV_PATH, _DSN) if _DSN else "disable"

requires_db = pytest.mark.skipif(
    _DSN is None,
    reason="DATABASE_URL not configured in config/.env"
)


def _poison_dead_domain_pg(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("retired PG domain queried")

    monkeypatch.setattr(DatabaseBackend, "_query_df", fail)
    monkeypatch.setattr(DatabaseBackend, "_get_conn", fail)


def test_retired_pg_domain_methods_do_not_query_dropped_tables(monkeypatch):
    _poison_dead_domain_pg(monkeypatch)
    backend = DatabaseBackend(dsn="postgresql://poisoned/arkscope")

    assert backend.query_news(days=1).empty
    assert backend.query_news_search(query="NVDA").empty
    assert backend.query_news_stats(ticker="NVDA").empty
    assert backend.query_news_scores(123).empty
    assert backend.query_iv_history("NVDA").empty
    assert backend.query_fundamentals("NVDA") == {}
    assert backend.get_financial_cache("k") is None
    assert backend.set_financial_cache("k", "NVDA", {"x": 1}) is False
    assert backend.get_available_tickers("news") == []
    assert backend.get_available_tickers("iv_history") == []
    assert backend.get_available_tickers("fundamentals") == []

    feed = backend.query_news_feed(q="nvda", ticker="NVDA")
    assert feed == {"available": False, "items": [], "total": 0, "sources": {}, "days": {}}


def test_query_prices_is_retired_after_batch3(monkeypatch):
    _poison_dead_domain_pg(monkeypatch)

    out = DatabaseBackend(dsn="postgresql://poisoned/arkscope").query_prices("NVDA")

    assert list(out.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert out.empty


def test_query_health_stats_is_retired_after_batch3(monkeypatch):
    _poison_dead_domain_pg(monkeypatch)

    stats = DatabaseBackend(dsn="postgresql://poisoned/arkscope").query_health_stats()

    for key in ("news", "prices", "iv_history", "financial_cache"):
        assert stats[key] == {"rows": [], "error": None}


@pytest.fixture(scope="module")
def backend():
    """Create a DatabaseBackend connected to PostgreSQL."""
    b = DatabaseBackend(dsn=_DSN, sslmode=_SSLMODE)
    yield b
    b.close()


@pytest.fixture(scope="module")
def dal():
    """Create a DAL with DatabaseBackend."""
    d = DataAccessLayer(db_dsn=_DSN)
    yield d


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------

@requires_db
class TestBackendProtocol:
    def test_db_backend_is_data_backend(self, backend):
        """DatabaseBackend satisfies the DataBackend protocol."""
        assert isinstance(backend, DataBackend)

    def test_backend_type(self, dal):
        """DAL reports correct backend type."""
        assert dal.backend_type == "DatabaseBackend"


# ---------------------------------------------------------------------------
# News Queries
# ---------------------------------------------------------------------------

@requires_db
class TestNewsDB:
    def test_query_news_all(self, backend):
        """PG news table is retired after N9 batch-1."""
        df = backend.query_news(days=3650)
        assert set(df.columns) >= {"date", "ticker", "title", "source"}
        assert df.empty

    def test_query_news_ticker(self, backend):
        """PG news ticker filter is a retired empty surface."""
        df = backend.query_news("NVDA", days=3650)
        assert df.empty

    def test_query_news_source_filter(self, backend):
        """PG news source filter is a retired empty surface."""
        df = backend.query_news("AAPL", days=3650, source="ibkr")
        assert df.empty

    def test_query_news_scored_only(self, backend):
        """PG news_scores is retired; scored PG reads are empty."""
        df = backend.query_news("NVDA", days=3650, scored_only=True)
        assert df.empty

    def test_news_schema_via_dal(self, dal):
        """DAL wraps retired PG news in an empty NewsQueryResult schema."""
        result = dal.get_news("NVDA", days=3650)
        assert result.ticker == "NVDA"
        assert result.count == 0
        assert result.articles == []


# ---------------------------------------------------------------------------
# IV History
# ---------------------------------------------------------------------------

@requires_db
class TestIVHistoryDB:
    def test_query_iv_history(self, backend):
        """PG iv_history is retired after N9 batch-1."""
        df = backend.query_iv_history("AMD")
        assert "atm_iv" in df.columns
        assert df.empty

    def test_iv_via_dal(self, dal):
        """DAL wraps retired PG IV data as an empty sequence."""
        points = dal.get_iv_history("AMD")
        assert points == []


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

@requires_db
class TestFundamentalsDB:
    def test_query_fundamentals(self, backend):
        """PG fundamentals is retired after S-B/N9."""
        data = backend.query_fundamentals("NVDA")
        assert data == {}

    def test_fundamentals_empty_ticker(self, backend):
        """Unknown ticker returns empty dict."""
        data = backend.query_fundamentals("ZZZZZ")
        assert data == {}

    def test_fundamentals_via_dal(self, dal):
        """DAL wraps retired PG fundamentals as not found."""
        result = dal.get_fundamentals("NVDA")
        assert result.ticker == "NVDA"
        assert result.found is False


# ---------------------------------------------------------------------------
# Available Tickers
# ---------------------------------------------------------------------------

@requires_db
class TestAvailableTickersDB:
    def test_news_tickers(self, backend):
        """PG news ticker listing is retired."""
        tickers = backend.get_available_tickers("news")
        assert tickers == []

    def test_fundamentals_tickers(self, backend):
        """PG fundamentals ticker listing is retired."""
        tickers = backend.get_available_tickers("fundamentals")
        assert tickers == []


# ---------------------------------------------------------------------------
# Prices (may be partially imported)
# ---------------------------------------------------------------------------

@requires_db
class TestPricesDB:
    def test_query_prices(self, backend):
        """Can query prices (if imported)."""
        df = backend.query_prices("AAPL", interval="15min", days=3650)
        # Prices may still be importing, so just check structure
        assert set(df.columns) >= {"datetime", "open", "high", "low", "close", "volume"} or df.empty

    def test_available_price_tickers(self, backend):
        """Can list price tickers (may be partial during import)."""
        tickers = backend.get_available_tickers("prices")
        assert isinstance(tickers, list)


# ---------------------------------------------------------------------------
# DAL Backend Switching
# ---------------------------------------------------------------------------

@requires_db
class TestDALBackendSwitch:
    def test_dal_auto_mode(self):
        """DAL with db_dsn='auto' reads from .env → a PG-backed DatabaseBackend.

        Hermetic to local-market routing: when the persisted ``use_local_market``
        toggle is on AND ``market_data.db`` exists, auto mode layers a
        ``LocalMarketDatabaseBackend`` on top — still a ``DatabaseBackend`` subclass
        (and NOT a FileBackend) — so assert the instance type, not the exact name.
        """
        dal = DataAccessLayer(db_dsn="auto")
        assert isinstance(dal._backend, DatabaseBackend)

    def test_dal_default_is_file(self):
        """DAL with no db_dsn uses FileBackend."""
        dal = DataAccessLayer()
        assert dal.backend_type == "FileBackend"

    def test_dal_explicit_dsn(self):
        """DAL with explicit DSN uses DatabaseBackend."""
        dal = DataAccessLayer(db_dsn=_DSN)
        assert dal.backend_type == "DatabaseBackend"

    def test_both_backends_same_schema(self, dal):
        """DB and File backends return same schema structure."""
        file_dal = DataAccessLayer()  # FileBackend

        db_result = dal.get_news("NVDA", days=3650)
        file_result = file_dal.get_news("NVDA", days=3650)

        # Both return NewsQueryResult with same fields
        assert type(db_result) == type(file_result)
        assert db_result.ticker == file_result.ticker

        # Both have articles with same schema
        if db_result.articles and file_result.articles:
            db_fields = set(type(db_result.articles[0]).model_fields.keys())
            file_fields = set(type(file_result.articles[0]).model_fields.keys())
            assert db_fields == file_fields
