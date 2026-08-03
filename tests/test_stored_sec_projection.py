from __future__ import annotations

import asyncio
import json
import sqlite3
from types import SimpleNamespace

import fastapi.routing
import httpx
import pytest
from fastapi import FastAPI

from src import market_data_admin as mda
from src.api.dependencies import get_dal, get_registry
from src.api.routes import fundamentals as fundamentals_routes
from src.api.routes import health as health_routes
from src.fundamentals.cache import fundamentals_analysis_cache_key
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend
from src.tools.backends.sqlite_backend import SqliteBackend
from src.tools.data_access import DataAccessLayer
from src.tools.data_coverage_tools import get_ticker_data_coverage
from src.tools.schemas import FundamentalsResult


_PRICE_SYNC = {
    "last_success": "price-success",
    "last_error": None,
    "rows_added": 11,
    "updated_at": "price-updated",
}
_NEWS_SYNC = {
    "last_success": "news-success",
    "last_error": None,
    "rows_added": 7,
    "updated_at": "news-updated",
}


def _positive_payload(ticker: str, snapshot_date: str | None) -> dict:
    return FundamentalsResult(
        ticker=ticker,
        data_source="sec_edgar",
        snapshot_date=snapshot_date,
        roe=0.23,
    ).model_dump()


@pytest.fixture()
def stored_sec_db(tmp_path):
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE prices (
            ticker TEXT, datetime TEXT, interval TEXT,
            open REAL, high REAL, low REAL, close REAL, volume INTEGER
        );
        CREATE TABLE news (
            id INTEGER PRIMARY KEY, ticker TEXT, title TEXT, description TEXT,
            url TEXT, publisher TEXT, source TEXT, published_at TEXT,
            article_hash TEXT
        );
        CREATE TABLE fundamentals (
            id INTEGER PRIMARY KEY, ticker TEXT, snapshot_date TEXT, data TEXT
        );
        CREATE TABLE market_sync_meta (
            domain TEXT PRIMARY KEY, last_success TEXT, last_error TEXT,
            rows_added INTEGER, updated_at TEXT
        );
        """
    )
    conn.executescript(mda._FIN_CACHE_SCHEMA)
    conn.execute(
        "INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)",
        ("AAPL", "2026-07-31T19:45:00+0000", "15min", 100, 102, 99, 101, 1000),
    )
    conn.execute(
        "INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?)",
        (1, "AAPL", "headline", None, None, None, "ibkr", "2026-07-31T20:00:00+0000", "h"),
    )
    conn.execute(
        "INSERT INTO fundamentals VALUES (?,?,?,?)",
        (1, "LEGACY", "2099-12-31", '{"reports": {}}'),
    )
    conn.executemany(
        "INSERT INTO market_sync_meta VALUES (?,?,?,?,?)",
        [
            ("prices", *_PRICE_SYNC.values()),
            ("news", *_NEWS_SYNC.values()),
            ("fundamentals", "legacy-success", None, 130, "legacy-updated"),
        ],
    )

    rows = [
        (
            fundamentals_analysis_cache_key("AAPL"),
            "sec_edgar",
            "AAPL",
            json.dumps(_positive_payload("AAPL", "2025-12-31")),
            "2026-07-01T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            fundamentals_analysis_cache_key("NEG"),
            "sec_edgar",
            "NEG",
            json.dumps({"_negative": True}),
            "2026-07-02T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            fundamentals_analysis_cache_key("EXP"),
            "sec_edgar",
            "EXP",
            json.dumps(_positive_payload("EXP", "2025-12-30")),
            "1999-01-01T00:00:00+00:00",
            "2000-01-01T00:00:00+00:00",
        ),
        (
            fundamentals_analysis_cache_key("BAD"),
            "sec_edgar",
            "BAD",
            "{not-json",
            "2026-07-03T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            fundamentals_analysis_cache_key("QTR", "quarterly"),
            "sec_edgar",
            "QTR",
            json.dumps(_positive_payload("QTR", "2025-09-30")),
            "2026-07-04T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            "financial_datasets:metrics:FD",
            "financial_datasets",
            "FD",
            json.dumps(_positive_payload("FD", "2025-12-29")),
            "2026-07-05T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            "metrics_OLD_annual_y2",
            "sec_edgar",
            "OLD",
            json.dumps(_positive_payload("OLD", "2025-12-28")),
            "2026-07-06T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            "detailed_financials:v2:sec_edgar:V2:annual:y2",
            "sec_edgar",
            "V2",
            json.dumps({"version": 2, "ticker": "V2"}),
            "2026-07-07T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            fundamentals_analysis_cache_key("NOSNAP"),
            "sec_edgar",
            "NOSNAP",
            json.dumps(_positive_payload("NOSNAP", None)),
            "2026-07-08T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
        (
            fundamentals_analysis_cache_key("MISMATCH"),
            "sec_edgar",
            "MISMATCH",
            json.dumps(_positive_payload("OTHER", "2025-12-27")),
            "2026-07-09T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
    ]
    conn.executemany(
        "INSERT INTO financial_cache "
        "(cache_key, source, ticker, data, fetched_at, expires_at) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def _api_get(app: FastAPI, path: str):
    async def _request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get(path)

    try:
        return asyncio.run(_request())
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_legacy_fundamentals_row_does_not_project_as_stored(
    stored_sec_db, monkeypatch,
):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(stored_sec_db))

    assert mda.local_ticker_coverage("LEGACY", str(stored_sec_db))["fundamentals"] is False
    assert get_ticker_data_coverage("LEGACY")["fundamentals"] == {
        "available": False,
        "row_count": 0,
        "earliest_date": None,
        "latest_date": None,
    }


def test_positive_annual_sec_cache_is_the_shared_projection_authority(
    stored_sec_db, monkeypatch,
):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(stored_sec_db))
    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: False)
    monkeypatch.setattr(
        DatabaseBackend,
        "get_available_tickers",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("fundamentals projection must not fall back to PG")
        ),
    )

    sqlite_backend = SqliteBackend(stored_sec_db)
    local_backend = LocalMarketDatabaseBackend(
        "postgresql://unused/db",
        market_db=str(stored_sec_db),
    )
    dal = DataAccessLayer(base_path=stored_sec_db.parent, backend=local_backend)

    stats = mda.local_market_stats(str(stored_sec_db))
    assert stats["fundamentals"] == {
        "row_count": 1,
        "ticker_count": 1,
        "latest_date": "2025-12-31",
    }
    assert stats["financial_cache"]["row_count"] == 10
    assert mda.local_ticker_coverage("AAPL", str(stored_sec_db))["fundamentals"] is True
    assert sqlite_backend.get_available_tickers("fundamentals") == ["AAPL"]
    assert local_backend.get_available_tickers("fundamentals") == ["AAPL"]

    coverage = get_ticker_data_coverage("AAPL")
    assert coverage["fundamentals"] == {
        "available": True,
        "row_count": 1,
        "earliest_date": "2025-12-31",
        "latest_date": "2025-12-31",
    }

    class _Registry:
        def list_all(self):
            return []

        def list_by_category(self, _category):
            return []

    app = FastAPI()
    app.include_router(health_routes.router)
    app.include_router(fundamentals_routes.router)
    app.dependency_overrides[get_dal] = lambda: dal
    app.dependency_overrides[get_registry] = _Registry

    async def _run_sync_inline(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", _run_sync_inline)
    monkeypatch.setattr(
        "src.provider_config_runtime.provider_config_setup_state",
        lambda: SimpleNamespace(as_dict=lambda: {}),
    )

    status_response = _api_get(app, "/status")
    assert status_response.status_code == 200
    assert status_response.json()["data_sources"]["fundamentals_tickers"] == 1

    stored_response = _api_get(app, "/fundamentals/AAPL?stored=true")
    assert stored_response.status_code == 200
    assert stored_response.json()["source_path"] == "local_cache"
    assert stored_response.json()["snapshot_date"] == "2025-12-31"


def test_nonpositive_and_nonannual_cache_rows_do_not_project_as_stored(stored_sec_db):
    assert SqliteBackend(stored_sec_db).get_available_tickers("fundamentals") == ["AAPL"]
    assert mda.local_market_stats(str(stored_sec_db))["fundamentals"] == {
        "row_count": 1,
        "ticker_count": 1,
        "latest_date": "2025-12-31",
    }


def test_fundamentals_sync_is_null_while_price_and_news_remain_unchanged(
    stored_sec_db, monkeypatch,
):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(stored_sec_db))
    monkeypatch.setattr("src.news_providers.use_local_news_enabled", lambda: False)

    admin_sync = mda.read_sync_meta(str(stored_sec_db))
    assert admin_sync == {
        "prices": _PRICE_SYNC,
        "news": _NEWS_SYNC,
        "fundamentals": None,
    }

    coverage_sync = get_ticker_data_coverage("AAPL")["sync"]
    assert coverage_sync == {
        "prices": _PRICE_SYNC,
        "news": _NEWS_SYNC,
        "fundamentals": None,
    }
