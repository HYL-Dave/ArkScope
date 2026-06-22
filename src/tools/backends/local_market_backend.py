"""
LocalMarketDatabaseBackend — DatabaseBackend that serves the market_data domain
from a local SQLite (3a prices + 3b news + 3c-A iv/fundamentals), with PostgreSQL
fallback.

Why a SUBCLASS of DatabaseBackend rather than a wrapper: the DAL and agents branch
on ``isinstance(backend, DatabaseBackend)`` in ~30 places to decide "is this a
SQL/DB backend" (batch summaries, news, sentiment, freshness, …). A wrapper that
merely forwarded calls would FAIL those isinstance checks → every DB-only path
short-circuits to empty/file behavior → the cockpit shows wrong/empty data. By
subclassing, this IS a DatabaseBackend (isinstance passes, ``_get_conn`` + all ~41
methods inherited and hit PG); we override ONLY the migrated market-domain reads
to go local-first. Everything else — Seeking-Alpha, reports, memories, news
SCORES — is the inherited PG behaviour, unchanged.

Overridden, local-first with PG fallback on empty/miss:
  - ``query_prices`` (3a);
  - ``query_news`` (3b, UNSCORED — scored_only/model requests fall back to PG,
    where news_scores live), ``query_news_search`` (3b, FTS5), and
    ``query_news_stats`` (score-free scout stats; no PG fallback on local empty);
  - ``query_iv_history`` + ``query_fundamentals`` (3c-A);
  - ``get_available_tickers('prices'|'news'|'iv_history'|'fundamentals')``.

financial_cache (3c-C) is LOCAL-PRIMARY, not a mirror:
  - ``set_financial_cache`` writes the LOCAL cache ONLY (never PG);
  - ``get_financial_cache`` is local-first, falls back to PG for legacy rows, and
    READ-THROUGH PROMOTES a valid PG hit into the local cache (free, preserving its
    TTL) so PG cache migrates local over time.
"""

from __future__ import annotations

import logging

import pandas as pd

from . import provenance
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

    def query_news(self, ticker=None, days=30, source="auto", scored_only=True, model=None):
        # Score-free local reads only; scored_only / a specific model → local empty
        # → PG (super) where news_scores live.
        try:
            df = self._market.query_news(
                ticker=ticker, days=days, source=source, scored_only=scored_only, model=model
            )
        except Exception as e:
            logger.warning(f"local query_news failed ({e}); falling back to PG")
            df = None
        if df is not None and not df.empty:
            return df
        return super().query_news(
            ticker=ticker, days=days, source=source, scored_only=scored_only, model=model
        )

    def query_news_search(self, query="", ticker=None, days=30, limit=20, scored_only=True):
        try:
            df = self._market.query_news_search(
                query=query, ticker=ticker, days=days, limit=limit, scored_only=scored_only
            )
        except Exception as e:
            logger.warning(f"local query_news_search failed ({e}); falling back to PG")
            df = None
        if df is not None and not df.empty:
            return df
        return super().query_news_search(
            query=query, ticker=ticker, days=days, limit=limit, scored_only=scored_only
        )

    def query_news_stats(self, ticker=None, days=30):
        # Scout stats must stay local and quick. The local mirror has article counts
        # and date ranges but not news_scores yet, so score fields are NULL/0. Empty
        # local results are honest empty results — do NOT fall back to PG, or a ticker
        # miss can block get_news_brief on the remote score path.
        try:
            return self._market.query_news_stats(ticker=ticker, days=days)
        except Exception as e:
            logger.warning(f"local query_news_stats failed ({e}); falling back to PG")
            return super().query_news_stats(ticker=ticker, days=days)

    def query_news_feed(self, q=None, ticker=None, source=None, days=30,
                        limit=50, offset=0):
        # Local-first feed (新聞·事件): the local DB is authoritative when it has a
        # news table — an empty result there is an honest zero, NOT a fallback
        # trigger. PG only serves pre-3b DBs (available=False).
        try:
            local = self._market.query_news_feed(
                q=q, ticker=ticker, source=source, days=days, limit=limit, offset=offset)
        except Exception as e:
            logger.warning(f"local query_news_feed failed ({e}); falling back to PG")
            local = {"available": False}
        if local.get("available"):
            return local
        return super().query_news_feed(
            q=q, ticker=ticker, source=source, days=days, limit=limit, offset=offset)

    def query_iv_history(self, ticker: str) -> pd.DataFrame:
        try:
            df = self._market.query_iv_history(ticker)
        except Exception as e:
            logger.warning(f"local query_iv_history failed ({e}); falling back to PG")
            df = None
        if df is not None and not df.empty:
            provenance.record("iv", "local")
            return df
        pg = super().query_iv_history(ticker)
        provenance.record("iv", "pg_fallback" if pg is not None and not pg.empty else "none")
        return pg

    def query_fundamentals(self, ticker: str) -> dict:
        try:
            data = self._market.query_fundamentals(ticker)
        except Exception as e:
            logger.warning(f"local query_fundamentals failed ({e}); falling back to PG")
            data = None
        if data:  # non-empty dict → local hit
            provenance.record("fundamentals", "local")
            return data
        pg = super().query_fundamentals(ticker)
        provenance.record("fundamentals", "pg_fallback" if pg else "none")
        return pg

    # --- financial_cache (3c-C): local-primary (set local-only; get local-first +
    #     PG fallback + read-through promotion) -----------------------------------

    def get_financial_cache(self, cache_key: str):
        try:
            local = self._market.get_financial_cache(cache_key)
        except Exception as e:
            logger.warning(f"local get_financial_cache failed ({e}); falling back to PG")
            local = None
        if local is not None:
            return local
        # PG fallback (legacy rows) + read-through promotion into local (free, not a
        # paid call) so old PG cache migrates local over time.
        data = super().get_financial_cache(cache_key)
        if data is not None:
            try:
                row = self._pg_financial_cache_row(cache_key)
                if row:
                    source, ticker, fetched_at, expires_at = row
                    self._market.set_financial_cache(
                        cache_key, ticker, data, source=source,
                        fetched_at=fetched_at, expires_at=expires_at,
                    )
            except Exception as e:
                logger.debug(f"financial_cache promotion skipped for {cache_key}: {e}")
        return data

    def set_financial_cache(self, cache_key, ticker, data, ttl_days=90, source="sec_edgar"):
        # local-PRIMARY: write the LOCAL cache only, never PG.
        try:
            return self._market.set_financial_cache(
                cache_key, ticker, data, ttl_days=ttl_days, source=source
            )
        except Exception as e:
            logger.warning(f"local set_financial_cache failed ({e})")
            return False

    def _pg_financial_cache_row(self, cache_key: str):
        """Full valid PG cache row for read-through promotion:
        ``(source, ticker, fetched_at_iso, expires_at_iso)`` or None. Timestamps are
        formatted to the same UTC ISO-seconds string the local cache stores."""
        from datetime import timezone

        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source, ticker, fetched_at, expires_at FROM financial_data_cache "
                "WHERE cache_key = %s AND expires_at > NOW()",
                (cache_key,),
            )
            row = cur.fetchone()
        if not row:
            return None
        source, ticker, fetched_dt, expires_dt = row

        def _fmt(dt):
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds") if dt else None

        return (source or "financial_datasets", ticker or "", _fmt(fetched_dt), _fmt(expires_dt))

    def get_available_tickers(self, data_type: str):
        if data_type in ("prices", "news", "iv_history", "fundamentals"):  # all local-first now
            try:
                local = self._market.get_available_tickers(data_type)
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
