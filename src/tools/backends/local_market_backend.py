"""
LocalMarketDatabaseBackend — DatabaseBackend that serves the market_data domain
from a local SQLite (slice 3a), with PostgreSQL fallback.

Why a SUBCLASS of DatabaseBackend rather than a wrapper: the DAL and agents branch
on ``isinstance(backend, DatabaseBackend)`` in ~30 places to decide "is this a
SQL/DB backend" (batch summaries, news, sentiment, freshness, …). A wrapper that
merely forwarded calls would FAIL those isinstance checks → every DB-only path
short-circuits to empty/file behavior → the cockpit shows wrong/empty data. By
subclassing, this IS a DatabaseBackend (isinstance passes, ``_get_conn`` + all ~41
methods inherited and hit PG); we override ONLY the market-domain reads to go
local-first. Everything else — Seeking-Alpha, news, reports, memories — is the
inherited PG behaviour, unchanged.

Slice 3a routes PRICES only; ``query_prices`` falls back to PG (``super()``) on a
local miss/empty so a not-yet/partially-migrated DB still reads correctly.
"""

from __future__ import annotations

import logging

import pandas as pd

from .db_backend import DatabaseBackend
from .sqlite_backend import SqliteBackend

logger = logging.getLogger(__name__)


class LocalMarketDatabaseBackend(DatabaseBackend):
    def __init__(self, dsn: str, sslmode: str = "prefer", *, market_db: str):
        super().__init__(dsn, sslmode)  # full PG backend (lazy connect)
        self._market = SqliteBackend(market_db)
        self._market_db = market_db

    def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
        try:
            df = self._market.query_prices(ticker, interval=interval, days=days)
        except Exception as e:  # never let the local path break a read
            logger.warning(f"local market query_prices failed ({e}); falling back to PG")
            df = None
        if df is not None and not df.empty:
            return df
        return super().query_prices(ticker, interval=interval, days=days)  # PG authority/fallback

    def get_available_tickers(self, data_type: str):
        if data_type == "prices":
            try:
                local = self._market.get_available_tickers("prices")
                if local:
                    return local
            except Exception:
                pass
        return super().get_available_tickers(data_type)

    def close(self) -> None:
        try:
            self._market.close()
        except Exception:
            pass
        super().close()
