"""
Backend abstraction for data access.

Defines the DataBackend Protocol that both FileBackend and DatabaseBackend implement.
This allows the DataAccessLayer to be backend-agnostic.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DataBackend(Protocol):
    """
    Protocol defining the data access contract.

    Any backend (file-based, database, etc.) must implement these methods.
    All methods return pandas DataFrames or dicts with consistent column names.
    """

    def query_news(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        source: str = "auto",
        scored_only: bool = True,
    ) -> pd.DataFrame:
        """
        Query news articles.

        Args:
            ticker: Filter by ticker (None = all tickers)
            days: Lookback period in days
            source: Data source (ibkr, polygon, auto)
            scored_only: Only return articles with sentiment/risk scores

        Returns:
            DataFrame with columns:
                date, ticker, title, source, url, publisher,
                sentiment_score, risk_score, description
        """
        ...

    def query_prices(
        self,
        ticker: str,
        interval: str = "15min",
        days: int = 30,
    ) -> pd.DataFrame:
        """
        Query OHLCV price bars.

        Args:
            ticker: Stock ticker
            interval: Bar interval (15min, 1h, 1d)
            days: Lookback period in days

        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume
        """
        ...

    def query_iv_history(self, ticker: str) -> pd.DataFrame:
        """
        Query IV history for a ticker.

        Returns:
            DataFrame with columns:
                date, atm_iv, hv_30d, vrp, spot_price, num_quotes
        """
        ...

    def query_fundamentals(self, ticker: str) -> dict:
        """
        Query fundamental data for a ticker.

        Returns:
            Dict with raw fundamental data (snapshot).
            Keys depend on data source (IBKR, SEC, etc.)
        """
        ...

    def query_sec_filings(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Query SEC filing metadata.

        Args:
            ticker: Company ticker
            filing_types: Filter by type (10-K, 10-Q, 8-K, etc.)

        Returns:
            DataFrame with columns:
                ticker, filing_type, filed_date, url,
                accession_number, description, period_of_report
        """
        ...

    def get_available_tickers(self, data_type: str) -> List[str]:
        """
        List tickers with available data of a given type.

        Args:
            data_type: One of 'news', 'prices', 'iv_history', 'fundamentals'

        Returns:
            Sorted list of ticker symbols
        """
        ...


__all__ = ["DataBackend"]