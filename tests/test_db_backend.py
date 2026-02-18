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
        """Can query news without ticker filter."""
        df = backend.query_news(days=3650)
        assert not df.empty
        assert set(df.columns) >= {"date", "ticker", "title", "source"}

    def test_query_news_ticker(self, backend):
        """Can filter news by ticker."""
        df = backend.query_news("NVDA", days=3650)
        assert not df.empty
        assert all(df["ticker"] == "NVDA")

    def test_query_news_source_filter(self, backend):
        """Can filter news by source."""
        df = backend.query_news("AAPL", days=3650, source="ibkr")
        if not df.empty:
            assert all(df["source"] == "ibkr")

    def test_query_news_scored_only(self, backend):
        """scored_only=True returns articles with scores."""
        df = backend.query_news("NVDA", days=3650, scored_only=True)
        if not df.empty:
            has_score = df["sentiment_score"].notna() | df["risk_score"].notna()
            assert has_score.all()

    def test_news_schema_via_dal(self, dal):
        """DAL wraps DB news in NewsQueryResult schema."""
        result = dal.get_news("NVDA", days=3650)
        assert result.ticker == "NVDA"
        assert result.count > 0
        article = result.articles[0]
        assert article.ticker == "NVDA"
        assert article.title


# ---------------------------------------------------------------------------
# IV History
# ---------------------------------------------------------------------------

@requires_db
class TestIVHistoryDB:
    def test_query_iv_history(self, backend):
        """Can query IV history."""
        df = backend.query_iv_history("AMD")
        assert not df.empty
        assert "atm_iv" in df.columns

    def test_iv_via_dal(self, dal):
        """DAL wraps DB IV data in IVHistoryPoint schema."""
        points = dal.get_iv_history("AMD")
        assert len(points) > 0
        assert points[0].atm_iv is not None


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

@requires_db
class TestFundamentalsDB:
    def test_query_fundamentals(self, backend):
        """Can query fundamentals."""
        data = backend.query_fundamentals("NVDA")
        assert data
        assert data["ticker"] == "NVDA"
        assert "snapshot" in data

    def test_fundamentals_empty_ticker(self, backend):
        """Unknown ticker returns empty dict."""
        data = backend.query_fundamentals("ZZZZZ")
        assert data == {}

    def test_fundamentals_via_dal(self, dal):
        """DAL wraps DB fundamentals in FundamentalsResult schema."""
        result = dal.get_fundamentals("NVDA")
        assert result.ticker == "NVDA"


# ---------------------------------------------------------------------------
# Available Tickers
# ---------------------------------------------------------------------------

@requires_db
class TestAvailableTickersDB:
    def test_news_tickers(self, backend):
        """Can list available news tickers."""
        tickers = backend.get_available_tickers("news")
        assert len(tickers) > 10
        assert "NVDA" in tickers

    def test_fundamentals_tickers(self, backend):
        """Can list available fundamentals tickers."""
        tickers = backend.get_available_tickers("fundamentals")
        assert len(tickers) > 10


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
        """DAL with db_dsn='auto' reads from .env."""
        dal = DataAccessLayer(db_dsn="auto")
        assert dal.backend_type == "DatabaseBackend"

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