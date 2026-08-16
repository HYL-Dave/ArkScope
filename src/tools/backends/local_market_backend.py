"""Current local market, news, fundamentals, and filing capabilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.news_content_availability import ContentFilter, empty_content_counts

from . import provenance
from .file_backend import FileBackend
from .sqlite_backend import (
    SqliteBackend,
    _NEWS_COLS,
    _NEWS_SEARCH_COLS,
    _NEWS_STATS_COLS,
)

logger = logging.getLogger(__name__)


class LocalMarketBackend:
    """Direct composition of the current local market data authorities."""

    def __init__(self, *, market_db: str, base_path: Optional[Path] = None):
        self._market = SqliteBackend(market_db)
        self._market_db = market_db
        self._files = FileBackend(base_path=base_path)

    def query_prices(
        self, ticker: str, interval: str = "15min", days: int = 30
    ) -> pd.DataFrame:
        try:
            return self._market.query_prices(ticker, interval=interval, days=days)
        except Exception as exc:
            logger.warning("local market query_prices failed (%s)", exc)
            return pd.DataFrame()

    def query_news(self, ticker=None, days=30, source="auto"):
        try:
            return self._market.query_news(ticker=ticker, days=days, source=source)
        except Exception as exc:
            logger.warning("local query_news failed (%s)", exc)
            return pd.DataFrame(columns=_NEWS_COLS)

    def query_news_search(self, query="", ticker=None, days=30, limit=20):
        try:
            return self._market.query_news_search(
                query=query, ticker=ticker, days=days, limit=limit
            )
        except Exception as exc:
            logger.warning("local query_news_search failed (%s)", exc)
            return pd.DataFrame(columns=_NEWS_SEARCH_COLS)

    def query_news_stats(self, ticker=None, days=30):
        try:
            return self._market.query_news_stats(ticker=ticker, days=days)
        except Exception as exc:
            logger.warning("local query_news_stats failed (%s)", exc)
            return pd.DataFrame(columns=_NEWS_STATS_COLS)

    def query_news_feed(
        self,
        q=None,
        ticker=None,
        source=None,
        days=30,
        limit=50,
        offset=0,
        content: ContentFilter = "all",
    ):
        try:
            return self._market.query_news_feed(
                q=q,
                ticker=ticker,
                source=source,
                content=content,
                days=days,
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            logger.warning("local query_news_feed failed (%s)", exc)
            return {
                "available": False,
                "items": [],
                "total": 0,
                "sources": {},
                "days": {},
                "content_counts": empty_content_counts(),
            }

    def query_fundamentals(self, ticker: str) -> dict:
        del ticker
        provenance.record("fundamentals", "none")
        return {}

    def get_financial_cache(self, cache_key: str):
        try:
            return self._market.get_financial_cache(cache_key)
        except Exception as exc:
            logger.warning("local get_financial_cache failed (%s)", exc)
            return None

    def set_financial_cache(
        self,
        cache_key: str,
        ticker: str,
        data: dict,
        ttl_days: int = 90,
        source: str = "sec_edgar",
    ):
        try:
            return self._market.set_financial_cache(
                cache_key,
                ticker,
                data,
                ttl_days=ttl_days,
                source=source,
            )
        except Exception as exc:
            logger.warning("local set_financial_cache failed (%s)", exc)
            return False

    def query_health_stats(self):
        try:
            return self._market.query_health_stats()
        except Exception as exc:
            logger.warning("local query_health_stats failed (%s)", exc)
            return {
                key: {"rows": [], "error": str(exc)}
                for key in ("news", "prices", "financial_cache")
            }

    def get_available_tickers(self, data_type: str):
        try:
            return self._market.get_available_tickers(data_type)
        except Exception as exc:
            logger.warning("local get_available_tickers failed (%s)", exc)
            return []

    def query_sec_filings(
        self, ticker: str, filing_types: Optional[List[str]] = None
    ) -> pd.DataFrame:
        return self._files.query_sec_filings(ticker, filing_types)

    def close(self) -> None:
        self._market.close()
