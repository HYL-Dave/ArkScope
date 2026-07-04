import pandas as pd

from src.tools.backends.db_backend import DatabaseBackend


class NoPgDatabaseBackend(DatabaseBackend):
    def __init__(self):
        super().__init__("postgresql://unused")

    def _query_df(self, sql, params=()):
        raise AssertionError(f"PG query must not run: {sql}")

    def _get_conn(self):
        raise AssertionError("PG connection must not be opened")


def test_query_prices_is_retired_stub_after_batch3():
    backend = NoPgDatabaseBackend()

    out = backend.query_prices("NVDA", interval="15min", days=7)

    assert isinstance(out, pd.DataFrame)
    assert list(out.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert out.empty


def test_query_health_stats_no_longer_queries_prices_after_batch3():
    backend = NoPgDatabaseBackend()

    stats = backend.query_health_stats()

    assert stats["prices"] == {"rows": [], "error": None}
    assert stats["news"] == {"rows": [], "error": None}
    assert stats["iv_history"] == {"rows": [], "error": None}
    assert stats["financial_cache"] == {"rows": [], "error": None}


def test_price_ticker_listing_is_retired_stub_after_batch3():
    backend = NoPgDatabaseBackend()

    assert backend.get_available_tickers("prices") == []


def test_app_record_archive_methods_are_not_removed_by_batch3():
    backend = NoPgDatabaseBackend()

    assert hasattr(backend, "insert_report")
    assert hasattr(backend, "query_reports")
    assert hasattr(backend, "get_report_metadata")
    assert hasattr(backend, "insert_memory")
    assert hasattr(backend, "query_memories")
    assert hasattr(backend, "list_memories_meta")
    assert hasattr(backend, "delete_memory")
    assert hasattr(backend, "insert_agent_query")
