"""
SqliteBackend — local-first market-data backend (slice 3a: PRICES only).

Part of the PostgreSQL → local SQLite migration (see
``docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md`` §3/§4). This backend
serves the *market_data* domain from a local ``market_data.db`` (SQLite, WAL).
It is NOT a full ``DataBackend`` — only the methods routed to it by
:class:`CompositeBackend` are implemented (slice 3a = ``query_prices`` +
``get_available_tickers('prices')``). Everything else stays on PostgreSQL.

Reads open the DB **read-only** (``mode=ro``); writes are done only by the
migration script, never here. The on-disk ``datetime`` is stored as the same
UTC string PostgreSQL emits (``YYYY-MM-DDTHH:MM:SS+0000``) so 15min rows pass
through unchanged and 1h/1d roll up by string-prefix grouping in pandas — the
SQLite analogue of the PG ``date_trunc`` aggregation (no ``date_trunc`` in
SQLite), matching the FileBackend resample contract.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

_PRICE_COLS = ["datetime", "open", "high", "low", "close", "volume"]
_INTERVAL_MAP = {"1h": "1h", "hourly": "1h", "1d": "1d", "daily": "1d", "15min": "15min"}


class SqliteBackend:
    """Local market-data backend over ``market_data.db`` (prices, slice 3a)."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        # Read-only: the backend never writes (migration owns writes).
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
        """OHLCV bars for ``ticker`` over the last ``days`` at ``interval``.

        Returns native rows at the requested interval; for 1d/1h with no native
        rows, rolls up from stored 15min bars (first-open / max-high / min-low /
        last-close / sum-volume) — same definition as the PG path. Empty frame on
        any miss (the CompositeBackend then falls back to PG).
        """
        ticker = ticker.upper()
        db_interval = _INTERVAL_MAP.get(interval, interval)
        # cutoff is a date string; ISO datetime strings sort lexicographically, so
        # `datetime >= 'YYYY-MM-DD'` correctly includes all of that day onward.
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        empty = pd.DataFrame(columns=_PRICE_COLS)

        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return empty  # db missing/unreadable → caller falls back to PG
        try:
            native = conn.execute(
                "SELECT datetime, open, high, low, close, volume FROM prices "
                "WHERE ticker = ? AND interval = ? AND datetime >= ? ORDER BY datetime ASC",
                (ticker, db_interval, cutoff),
            ).fetchall()
            if native:
                return pd.DataFrame([tuple(r) for r in native], columns=_PRICE_COLS)

            if db_interval in ("1d", "1h"):
                raw = conn.execute(
                    "SELECT datetime, open, high, low, close, volume FROM prices "
                    "WHERE ticker = ? AND interval = '15min' AND datetime >= ? ORDER BY datetime ASC",
                    (ticker, cutoff),
                ).fetchall()
                if raw:
                    return self._rollup(
                        pd.DataFrame([tuple(r) for r in raw], columns=_PRICE_COLS), db_interval
                    )
        except sqlite3.OperationalError as e:
            logger.warning(f"SqliteBackend.query_prices({ticker}): {e}")
            return empty
        finally:
            conn.close()
        return empty

    @staticmethod
    def _rollup(df: pd.DataFrame, db_interval: str) -> pd.DataFrame:
        """Aggregate 15min bars up to 1d/1h by UTC-string prefix (SQLite analogue
        of PG ``date_trunc``). datetime strings are ``YYYY-MM-DDTHH:MM:SS+0000``."""
        if df.empty:
            return df
        prefix = 10 if db_interval == "1d" else 13  # 'YYYY-MM-DD' | 'YYYY-MM-DDTHH'
        suffix = "T00:00:00+0000" if db_interval == "1d" else ":00:00+0000"
        df = df.sort_values("datetime")
        bucket = df["datetime"].str.slice(0, prefix)
        agg = df.groupby(bucket, sort=True).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        agg.index = [k + suffix for k in agg.index]
        out = agg.reset_index().rename(columns={"index": "datetime"})
        return out[_PRICE_COLS]

    def get_available_tickers(self, data_type: str) -> List[str]:
        """Distinct tickers with price data (slice 3a serves only ``prices``)."""
        if data_type != "prices":
            return []
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return []
        try:
            rows = conn.execute("SELECT DISTINCT ticker FROM prices ORDER BY ticker").fetchall()
            return [r[0] for r in rows]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def close(self) -> None:  # symmetry with DatabaseBackend; nothing persistent to close
        pass
