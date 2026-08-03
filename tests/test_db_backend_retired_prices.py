from pathlib import Path

import pandas as pd

from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.file_backend import FileBackend


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
    assert "iv_history" not in stats
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


def test_file_backend_prices_and_fundamentals_are_empty_without_path_probes(
    tmp_path, monkeypatch,
):
    backend = FileBackend(base_path=tmp_path)

    def _must_not_probe(*_args, **_kwargs):
        raise AssertionError("retired repository data paths must not be probed")

    blocked_roots = (str(backend._prices_dir), str(backend._fundamentals_dir))
    real_exists = Path.exists
    real_glob = Path.glob
    real_rglob = Path.rglob

    def _is_retired_data_path(path):
        text = str(path)
        return any(text == root or text.startswith(f"{root}/") for root in blocked_roots)

    def _guarded_exists(path):
        if _is_retired_data_path(path):
            return _must_not_probe(path)
        return real_exists(path)

    def _guarded_glob(path, pattern):
        if _is_retired_data_path(path):
            return _must_not_probe(path, pattern)
        return real_glob(path, pattern)

    def _guarded_rglob(path, pattern):
        if _is_retired_data_path(path):
            return _must_not_probe(path, pattern)
        return real_rglob(path, pattern)

    monkeypatch.setattr(Path, "exists", _guarded_exists)
    monkeypatch.setattr(Path, "glob", _guarded_glob)
    monkeypatch.setattr(Path, "rglob", _guarded_rglob)
    monkeypatch.setattr(pd, "read_csv", _must_not_probe)
    monkeypatch.setattr(pd, "read_parquet", _must_not_probe)

    prices = backend.query_prices("AAPL", interval="15min", days=7)
    assert list(prices.columns) == [
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert prices.empty
    assert backend.query_fundamentals("AAPL") == {}
    assert backend.get_available_tickers("prices") == []
    assert backend.get_available_tickers("fundamentals") == []
