"""
CompositeBackend — domain-routing DataBackend (PG + local market_data).

Implements the PostgreSQL → local-SQLite migration's intermediate state
(``docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md`` §3d): the
*market_data* domain reads from a local :class:`SqliteBackend`, while every
other domain — Seeking-Alpha capture, news, reports, memories, agent_queries,
… — stays on the primary :class:`DatabaseBackend` (PostgreSQL).

Slice 3a routes ONLY ``query_prices`` (+ ``get_available_tickers('prices')``)
to the local backend, with **PG fallback**: if the local market DB has no rows
for the request (not migrated yet / partial / unknown ticker), the call
transparently falls back to the primary backend. Everything not explicitly
overridden here is forwarded to the primary via ``__getattr__``, so the
composite satisfies the full ``DataBackend`` surface without hand-delegating
all ~40 methods. The protected SA native-host path therefore keeps writing to
PG unchanged.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class CompositeBackend:
    def __init__(self, primary, market):
        """``primary`` = PG DatabaseBackend (authority + fallback); ``market`` =
        local SqliteBackend serving the migrated market domain."""
        self._primary = primary
        self._market = market

    # --- market domain (local-first, PG fallback) -----------------------

    def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
        try:
            df = self._market.query_prices(ticker, interval=interval, days=days)
        except Exception as e:  # never let the local path break a read
            logger.warning(f"local market query_prices failed ({e}); falling back to PG")
            df = None
        if df is not None and not df.empty:
            return df
        # Empty/missing locally → authoritative PG (migration not run / no local rows).
        return self._primary.query_prices(ticker, interval=interval, days=days)

    def get_available_tickers(self, data_type: str):
        if data_type == "prices":
            try:
                local = self._market.get_available_tickers("prices")
                if local:
                    return local
            except Exception:
                pass
        return self._primary.get_available_tickers(data_type)

    def close(self) -> None:
        for backend in (self._market, self._primary):
            try:
                backend.close()
            except Exception:
                pass

    # --- everything else → primary (PG): SA, news, reports, memories, … --

    def __getattr__(self, name):
        # Only reached for attributes not defined above (and not _primary/_market,
        # which are set in __init__ and resolve normally).
        return getattr(self._primary, name)
