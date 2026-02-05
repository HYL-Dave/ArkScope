"""
DatabaseBackend — reads data from Supabase/PostgreSQL.

Implements the DataBackend protocol using psycopg2 with direct SQL queries.
Designed for both Supabase Cloud and self-hosted PostgreSQL.

Connection string format:
    postgresql://postgres:password@host:port/postgres
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class DatabaseBackend:
    """
    PostgreSQL/Supabase data backend.

    Uses psycopg2 for direct SQL queries. Connection pooling is handled
    by creating connections on demand with a simple single-connection cache.
    """

    def __init__(self, dsn: str, sslmode: str = "require"):
        """
        Args:
            dsn: PostgreSQL connection string.
            sslmode: SSL mode (require for Supabase Cloud, prefer for local).
        """
        self._dsn = dsn
        self._sslmode = sslmode
        self._conn: Optional[psycopg2.extensions.connection] = None

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Get or create a database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                self._dsn,
                sslmode=self._sslmode,
                connect_timeout=15,
            )
            self._conn.autocommit = True
        return self._conn

    def _query_df(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """Execute a query and return results as a DataFrame."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(rows)
        except psycopg2.Error as e:
            logger.error(f"Database query error: {e}")
            # Reset connection on error
            self._conn = None
            return pd.DataFrame()

    def close(self):
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    # --------------------------------------------------------
    # News
    # --------------------------------------------------------

    def query_news(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        source: str = "auto",
        scored_only: bool = True,
    ) -> pd.DataFrame:
        """Query news articles from the database."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        conditions = ["published_at >= %s"]
        params: list = [cutoff]

        if ticker:
            conditions.append("ticker = %s")
            params.append(ticker.upper())

        if source != "auto":
            conditions.append("source = %s")
            params.append(source)

        if scored_only:
            conditions.append("(sentiment_score IS NOT NULL OR risk_score IS NOT NULL)")

        where = " AND ".join(conditions)
        sql = f"""
            SELECT
                TO_CHAR(published_at, 'YYYY-MM-DD') AS date,
                ticker, title, source, url, publisher,
                sentiment_score, risk_score, description
            FROM news
            WHERE {where}
            ORDER BY published_at DESC
        """

        df = self._query_df(sql, tuple(params))
        if df.empty:
            return pd.DataFrame(columns=[
                "date", "ticker", "title", "source", "url",
                "publisher", "sentiment_score", "risk_score", "description",
            ])
        return df

    # --------------------------------------------------------
    # Prices
    # --------------------------------------------------------

    def query_prices(
        self,
        ticker: str,
        interval: str = "15min",
        days: int = 30,
    ) -> pd.DataFrame:
        """Query OHLCV price bars from the database."""
        ticker = ticker.upper()

        # Normalize interval names
        interval_map = {"1h": "1h", "hourly": "1h", "1d": "1d", "daily": "1d", "15min": "15min"}
        db_interval = interval_map.get(interval, interval)

        cutoff = (date.today() - timedelta(days=days)).isoformat()

        sql = """
            SELECT
                TO_CHAR(datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
                open, high, low, close, volume
            FROM prices
            WHERE ticker = %s AND interval = %s AND datetime >= %s
            ORDER BY datetime ASC
        """

        df = self._query_df(sql, (ticker, db_interval, cutoff))
        if df.empty:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        return df

    # --------------------------------------------------------
    # IV History
    # --------------------------------------------------------

    def query_iv_history(self, ticker: str) -> pd.DataFrame:
        """Query IV history from the database."""
        ticker = ticker.upper()

        sql = """
            SELECT
                TO_CHAR(date, 'YYYY-MM-DD') AS date,
                atm_iv, hv_30d, vrp, spot_price, num_quotes
            FROM iv_history
            WHERE ticker = %s
            ORDER BY date ASC
        """

        df = self._query_df(sql, (ticker,))
        if df.empty:
            return pd.DataFrame(columns=[
                "date", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes",
            ])
        return df

    # --------------------------------------------------------
    # Fundamentals
    # --------------------------------------------------------

    def query_fundamentals(self, ticker: str) -> dict:
        """Query latest fundamental data from the database."""
        ticker = ticker.upper()

        sql = """
            SELECT data, TO_CHAR(snapshot_date, 'YYYY-MM-DD') AS snapshot_date
            FROM fundamentals
            WHERE ticker = %s
            ORDER BY snapshot_date DESC
            LIMIT 1
        """

        df = self._query_df(sql, (ticker,))
        if df.empty:
            return {}

        row = df.iloc[0]
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)

        # Return in same format as FileBackend
        reports = data.get("reports", data)
        snapshot = reports.get("ReportSnapshot", {}) if isinstance(reports, dict) else {}

        return {
            "ticker": ticker,
            "collected_at": row.get("snapshot_date", ""),
            "snapshot": snapshot,
            "fin_summary": reports.get("ReportsFinSummary", {}) if isinstance(reports, dict) else {},
            "ownership": reports.get("ReportsOwnership", {}) if isinstance(reports, dict) else {},
        }

    # --------------------------------------------------------
    # SEC Filings (same as FileBackend — API-based, not in DB)
    # --------------------------------------------------------

    def query_sec_filings(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        SEC filing metadata.

        SEC filings are fetched via SEC EDGAR API, not stored in DB.
        Returns empty DataFrame (same as FileBackend).
        """
        return pd.DataFrame(columns=[
            "ticker", "filing_type", "filed_date", "url",
            "accession_number", "description", "period_of_report",
        ])

    # --------------------------------------------------------
    # Available tickers
    # --------------------------------------------------------

    def get_available_tickers(self, data_type: str) -> List[str]:
        """List tickers with available data of a given type."""
        table_map = {
            "news": "news",
            "prices": "prices",
            "iv_history": "iv_history",
            "fundamentals": "fundamentals",
        }

        table = table_map.get(data_type)
        if not table:
            return []

        sql = f"SELECT DISTINCT ticker FROM {table} ORDER BY ticker"
        df = self._query_df(sql)

        if df.empty:
            return []
        return df["ticker"].tolist()