"""
LocalMarketDatabaseBackend — DatabaseBackend that serves the market_data domain
from local SQLite stores.

Why a SUBCLASS of DatabaseBackend rather than a wrapper: the DAL and agents branch
on ``isinstance(backend, DatabaseBackend)`` to decide "is this a SQL/DB backend".
A wrapper that
merely forwarded calls would FAIL those isinstance checks → every DB-only path
short-circuits to empty/file behavior → the cockpit shows wrong/empty data. By
subclassing, this IS a DatabaseBackend (isinstance passes, ``_get_conn`` + all ~41
methods inherited and hit PG); we override ONLY the migrated market-domain reads
to go local-first. App-records, Seeking Alpha, and job-runs now route through
their own local stores; remaining inherited PG methods are archive or tombstone
surfaces that must fail closed rather than revive a runtime fallback.

Overridden market reads:
  - ``query_prices`` (3a) — local-only after P0-C; a miss is an honest empty,
    never a PG fallback;
  - ``query_news`` / search / stats (3b) — raw local news only; an empty local
    result is an honest empty and never revives the PostgreSQL archive;
  - ``get_available_tickers('prices')`` is local-only after P0-C;
    other local domains remain transitional where noted.

The old ``fundamentals`` mirror table is retained for legacy inspection until N9,
but is no longer an authority. Current fundamentals are served through the
SEC/Financial-Datasets analysis path and local ``financial_cache``.

financial_cache (3c-C) is LOCAL-PRIMARY, not a mirror:
  - ``set_financial_cache`` writes the LOCAL cache ONLY (never PG);
  - ``get_financial_cache`` reads the LOCAL cache ONLY. A miss is an honest miss; callers that
    need fresh data must refetch from SEC/Financial Datasets and write the local cache.
"""

from __future__ import annotations

import logging

import pandas as pd

from src.news_content_availability import ContentFilter, empty_content_counts

from . import provenance
from .db_backend import DatabaseBackend
from .sqlite_backend import SqliteBackend, _NEWS_COLS, _NEWS_SEARCH_COLS, _NEWS_STATS_COLS

logger = logging.getLogger(__name__)


class LocalMarketDatabaseBackend(DatabaseBackend):
    def __init__(
        self,
        dsn: str,
        sslmode: str = "prefer",
        *,
        market_db: str,
        strict: bool = False,
        news_strict: bool = False,
    ):
        # strict (local-only): market reads NEVER fall back to PG — a local miss is an
        # honest empty/unavailable, PG is import/archive only. The short connect_timeout
        # makes any residual non-market PG path (app-records, a deferred slice) fail FAST
        # rather than hang the desktop app when PG is unreachable.
        super().__init__(dsn, sslmode, connect_timeout=3 if strict else 15)
        self._market = SqliteBackend(market_db)
        self._market_db = market_db
        self._strict = strict
        self._news_strict = news_strict

    def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
        try:
            return self._market.query_prices(ticker, interval=interval, days=days)
        except Exception as e:  # never let the local path break a read
            logger.warning(f"local market query_prices failed ({e})")
            return pd.DataFrame()

    def query_news(self, ticker=None, days=30, source="auto"):
        try:
            return self._market.query_news(ticker=ticker, days=days, source=source)
        except Exception as e:
            logger.warning(f"local query_news failed ({e})")
            return pd.DataFrame(columns=_NEWS_COLS)

    def query_news_search(self, query="", ticker=None, days=30, limit=20):
        try:
            return self._market.query_news_search(
                query=query, ticker=ticker, days=days, limit=limit
            )
        except Exception as e:
            logger.warning(f"local query_news_search failed ({e})")
            return pd.DataFrame(columns=_NEWS_SEARCH_COLS)

    def query_news_stats(self, ticker=None, days=30):
        # Raw scout stats stay local and quick.
        try:
            return self._market.query_news_stats(ticker=ticker, days=days)
        except Exception as e:
            logger.warning(f"local query_news_stats failed ({e})")
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
        # Local-first feed (新聞·事件): the local DB is authoritative when it has a
        # news table — an empty result there is an honest zero, NOT a fallback
        # trigger. PG only serves pre-3b DBs (available=False).
        try:
            local = self._market.query_news_feed(
                q=q,
                ticker=ticker,
                source=source,
                content=content,
                days=days,
                limit=limit,
                offset=offset,
            )
        except Exception as e:
            logger.warning(f"local query_news_feed failed ({e})")
            # CANONICAL full shape (mirror SqliteBackend.query_news_feed's empty) — never a
            # thin {available:False}: in strict mode this returns directly to the frontend,
            # which reads total/sources before the available guard.
            local = {
                "available": False,
                "items": [],
                "total": 0,
                "sources": {},
                "days": {},
                "content_counts": empty_content_counts(),
            }
        if local.get("available"):
            return local
        if self._strict or self._news_strict:
            return local  # local-only: honest local feed state (no PG), even if empty
        return super().query_news_feed(
            q=q,
            ticker=ticker,
            source=source,
            content=content,
            days=days,
            limit=limit,
            offset=offset,
        )

    def query_fundamentals(self, ticker: str) -> dict:
        """The PG-mirrored fundamentals table is retired as an authority.

        Use get_fundamentals_analysis() for live SEC/Financial-Datasets fallback and
        /fundamentals/{ticker}?stored=true for local financial_cache hits. The old
        fundamentals table remains inspectable through SqliteBackend until N9, but
        LocalMarketDatabaseBackend must not serve or PG-fallback it as current data.
        """
        provenance.record("fundamentals", "none")
        return {}

    # --- financial_cache (3c-C/S-H2): local-primary (set local-only; get local-only) ---

    def get_financial_cache(self, cache_key: str):
        try:
            return self._market.get_financial_cache(cache_key)
        except Exception as e:
            logger.warning(f"local get_financial_cache failed ({e})")
            return None

    def set_financial_cache(self, cache_key, ticker, data, ttl_days=90, source="sec_edgar"):
        # local-PRIMARY: write the LOCAL cache only, never PG.
        try:
            return self._market.set_financial_cache(
                cache_key, ticker, data, ttl_days=ttl_days, source=source
            )
        except Exception as e:
            logger.warning(f"local set_financial_cache failed ({e})")
            return False

    def query_health_stats(self):
        # Provider health / freshness reflect what the app actually SERVES — the local
        # market_data.db — so recompute locally. PG (super) only if the local read itself
        # errors (transition safety); a source with 0 local rows is an honest local state.
        try:
            return self._market.query_health_stats()
        except Exception as e:
            logger.warning(f"local query_health_stats failed ({e})")
            if self._strict:  # local-only: honest empty health, no PG
                return {k: {"rows": [], "error": str(e)}
                        for k in ("news", "prices", "financial_cache")}
            return super().query_health_stats()

    def get_available_tickers(self, data_type: str):
        if data_type in ("prices", "news", "fundamentals"):  # all local-first now
            try:
                local = self._market.get_available_tickers(data_type)
                if data_type in ("prices", "fundamentals"):
                    return local
                if local:
                    return local
            except Exception:
                if data_type in ("prices", "fundamentals"):
                    return []
        if data_type == "news" and self._news_strict:
            return []  # news PG-exit: honest local empty, no PG
        if self._strict:
            return []  # local-only: honest empty (incl. non-local types), no PG
        return super().get_available_tickers(data_type)

    def close(self) -> None:
        try:
            self._market.close()
        except Exception:
            pass
        super().close()
