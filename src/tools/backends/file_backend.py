"""
FileBackend — reads retained raw-news files on disk.

Price and fundamentals methods are retired empty compatibility surfaces. Current
price and stored SEC authorities live in ``market_data.db``.

Raw news lives under ``data/news/raw``. Prices and fundamentals are retired
empty surfaces; their current authorities live in ``market_data.db``.
"""

from __future__ import annotations

import logging
import warnings
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

class FileBackend:
    """
    File-based data backend.

    Reads retained raw-news files and implements the DataBackend protocol.
    Retired price and fundamentals methods remain as empty compatibility calls.
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Args:
            base_path: Project root directory. Auto-detected if None.
        """
        if base_path is None:
            # Walk up from this file to find project root (has config/ dir)
            p = Path(__file__).resolve()
            for parent in p.parents:
                if (parent / "config").is_dir() and (parent / "data").is_dir():
                    base_path = parent
                    break
            if base_path is None:
                raise FileNotFoundError(
                    "Cannot auto-detect project root. Pass base_path explicitly."
                )
        self._base = Path(base_path)

        # Retained data path
        self._news_dir = self._base / "data" / "news"

    # --------------------------------------------------------
    # News
    # --------------------------------------------------------

    def _load_raw_news(self, days: int = 30) -> pd.DataFrame:
        """Load raw news from data/news/raw/ parquet files.

        Only loads files from year-months overlapping the requested date
        range to avoid scanning all historical data.  Returns a DataFrame
        with the standard raw-news columns.
        """
        raw_dir = self._news_dir / "raw"
        if not raw_dir.exists():
            return pd.DataFrame()

        cutoff_date = date.today() - timedelta(days=days)

        # Build set of YYYY-MM strings we need (cutoff month through today)
        target_months: set[str] = set()
        d = cutoff_date.replace(day=1)
        while d <= date.today():
            target_months.add(d.strftime("%Y-%m"))
            # Advance to next month
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)

        frames: list[pd.DataFrame] = []
        for source_dir in sorted(raw_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            source_name = source_dir.name  # 'polygon', 'finnhub', 'ibkr'

            for pq in source_dir.rglob("*.parquet"):
                # Only load files whose name contains a target year-month
                # e.g. stem = "2026-02" or "finnhub_news_2026-02"
                if not any(m in pq.stem for m in target_months):
                    continue

                try:
                    df = pd.read_parquet(pq)
                except Exception as e:
                    logger.warning(f"Could not read {pq}: {e}")
                    continue

                if df.empty:
                    continue

                # Standardise columns to the raw-news output.
                df["source"] = source_name
                df["date"] = pd.to_datetime(
                    df.get("published_at"), errors="coerce",
                ).dt.strftime("%Y-%m-%d")
                for col in ["ticker", "title", "url", "publisher", "description"]:
                    if col not in df.columns:
                        df[col] = None

                frames.append(df)

        if not frames:
            return pd.DataFrame()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            combined = pd.concat(frames, ignore_index=True)
        logger.debug(
            f"Loaded {len(combined)} raw news rows from "
            f"{len(frames)} files (months: {sorted(target_months)})"
        )
        return combined

    def query_news(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        source: str = "auto",
    ) -> pd.DataFrame:
        """Query raw news articles from local files.

        Args:
            ticker: Filter by ticker symbol.
            days: Number of days to look back.
            source: Data source filter (IBKR, Massive, auto; Massive uses legacy ID 'polygon').
        """
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        combined = self._load_raw_news(days=days)
        if combined.empty:
            return pd.DataFrame(columns=[
                "date", "ticker", "title", "source", "url",
                "publisher", "description",
            ])
        if source != "auto":
            combined = combined[combined["source"] == source]
        if "dedup_hash" in combined.columns:
            combined = combined.drop_duplicates(subset="dedup_hash", keep="first")
        else:
            combined = combined.drop_duplicates(
                subset=["ticker", "date", "title"], keep="first",
            )

        # Date filter
        combined = combined[combined["date"] >= cutoff]

        # Ticker filter
        if ticker:
            combined = combined[combined["ticker"] == ticker.upper()]

        # Select and order output columns
        output_cols = [
            "date", "ticker", "title", "source", "url",
            "publisher", "description",
        ]
        for col in output_cols:
            if col not in combined.columns:
                combined[col] = None

        result = combined[output_cols].sort_values("date", ascending=False).reset_index(drop=True)
        return result

    # --------------------------------------------------------
    # Prices
    # --------------------------------------------------------

    def query_prices(
        self,
        ticker: str,
        interval: str = "15min",
        days: int = 30,
    ) -> pd.DataFrame:
        """Retired file authority: prices are available only from SQLite."""
        del ticker, interval, days
        return pd.DataFrame(
            columns=["datetime", "open", "high", "low", "close", "volume"]
        )

    # --------------------------------------------------------
    # Fundamentals
    # --------------------------------------------------------

    def query_fundamentals(self, ticker: str) -> dict:
        """Retired file authority: fundamentals are available from stored SEC."""
        del ticker
        return {}

    # --------------------------------------------------------
    # SEC Filings (limited — no local file store)
    # --------------------------------------------------------

    def query_sec_filings(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        SEC filing metadata.

        FileBackend returns an empty DataFrame since SEC filings are API-based.
        The DataAccessLayer may supplement this via SECEdgarDataSource.
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
        tickers = set()

        if data_type == "news":
            news = self._load_raw_news(days=3650)
            if not news.empty and "ticker" in news.columns:
                tickers.update(news["ticker"].dropna().unique())

        elif data_type in ("prices", "fundamentals"):
            return []

        return sorted(tickers)
