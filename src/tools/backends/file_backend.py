"""
FileBackend — reads existing Parquet/CSV/JSON data files on disk.

This is the first backend implementation, designed to work immediately
with the project's existing data without any database setup.

Data path mapping:
    Scored news (IBKR)  : data/news/ibkr_scored_final.parquet
    Scored news (Polygon): data/news/polygon_scored_final.csv
    15min prices        : data/prices/15min/{TICKER}_15min_*.csv
    Hourly prices       : data/prices/hourly/{TICKER}_hourly_*.csv
    Daily prices        : data/prices/daily/{TICKER}.parquet or .csv
    IV history          : data/options/iv_history/{TICKER}.parquet
    Fundamentals        : data_lake/raw/ibkr_fundamentals/{TICKER}_*.json
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class FileBackend:
    """
    File-based data backend.

    Reads Parquet, CSV, and JSON files from the project's data directories.
    Implements the DataBackend protocol.
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

        # Data paths
        self._news_dir = self._base / "data" / "news"
        self._prices_dir = self._base / "data" / "prices"
        self._iv_dir = self._base / "data" / "options" / "iv_history"
        self._fundamentals_dir = self._base / "data_lake" / "raw" / "ibkr_fundamentals"

        # Caches for scored news (loaded lazily, large files)
        self._ibkr_news: Optional[pd.DataFrame] = None
        self._polygon_news: Optional[pd.DataFrame] = None

    # --------------------------------------------------------
    # News
    # --------------------------------------------------------

    def _load_ibkr_news(self) -> pd.DataFrame:
        """Load and normalize IBKR scored news (lazy, cached)."""
        if self._ibkr_news is not None:
            return self._ibkr_news

        path = self._news_dir / "ibkr_scored_final.parquet"
        if not path.exists():
            self._ibkr_news = pd.DataFrame()
            return self._ibkr_news

        df = pd.read_parquet(path, columns=[
            "ticker", "title", "published_at", "source_api",
            "url", "publisher", "sentiment_haiku", "risk_haiku", "description",
        ])
        # Normalize column names to our standard schema
        df = df.rename(columns={
            "source_api": "source",
            "sentiment_haiku": "sentiment_score",
            "risk_haiku": "risk_score",
        })
        df["source"] = "ibkr"
        df["date"] = pd.to_datetime(df["published_at"], errors="coerce").dt.strftime("%Y-%m-%d")
        self._ibkr_news = df
        logger.debug(f"Loaded IBKR news: {len(df)} rows")
        return self._ibkr_news

    def _load_polygon_news(self) -> pd.DataFrame:
        """Load and normalize Polygon scored news (lazy, cached)."""
        if self._polygon_news is not None:
            return self._polygon_news

        path = self._news_dir / "polygon_scored_final.csv"
        if not path.exists():
            self._polygon_news = pd.DataFrame()
            return self._polygon_news

        df = pd.read_csv(path, usecols=[
            "Stock_symbol", "Article_title", "published_at",
            "url", "publisher", "sentiment_haiku", "risk_haiku", "description",
        ])
        df = df.rename(columns={
            "Stock_symbol": "ticker",
            "Article_title": "title",
            "sentiment_haiku": "sentiment_score",
            "risk_haiku": "risk_score",
        })
        df["source"] = "polygon"
        df["date"] = pd.to_datetime(df["published_at"], errors="coerce").dt.strftime("%Y-%m-%d")
        self._polygon_news = df
        logger.debug(f"Loaded Polygon news: {len(df)} rows")
        return self._polygon_news

    def query_news(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        source: str = "auto",
        scored_only: bool = True,
    ) -> pd.DataFrame:
        """Query news articles from local scored files."""
        frames = []
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        if source in ("ibkr", "auto"):
            df = self._load_ibkr_news()
            if not df.empty:
                frames.append(df)

        if source in ("polygon", "auto"):
            df = self._load_polygon_news()
            if not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame(columns=[
                "date", "ticker", "title", "source", "url",
                "publisher", "sentiment_score", "risk_score", "description",
            ])

        combined = pd.concat(frames, ignore_index=True)

        # Date filter
        combined = combined[combined["date"] >= cutoff]

        # Ticker filter
        if ticker:
            combined = combined[combined["ticker"] == ticker.upper()]

        # Scored-only filter
        if scored_only:
            combined = combined[
                combined["sentiment_score"].notna() | combined["risk_score"].notna()
            ]

        # Select and order output columns
        output_cols = [
            "date", "ticker", "title", "source", "url",
            "publisher", "sentiment_score", "risk_score", "description",
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
        """Query OHLCV price bars from local CSV/Parquet files."""
        ticker = ticker.upper()
        cutoff_dt = datetime.now() - timedelta(days=days)

        if interval == "15min":
            df = self._load_price_files(self._prices_dir / "15min", ticker, "15min")
        elif interval in ("1h", "hourly"):
            df = self._load_price_files(self._prices_dir / "hourly", ticker, "hourly")
        elif interval in ("1d", "daily"):
            df = self._load_daily_prices(ticker)
        else:
            logger.warning(f"Unknown interval {interval}, falling back to 15min")
            df = self._load_price_files(self._prices_dir / "15min", ticker, "15min")

        if df.empty:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])

        # Parse and filter by date
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
        df = df.dropna(subset=["datetime"])
        df = df[df["datetime"] >= pd.Timestamp(cutoff_dt, tz="UTC")]
        df = df.sort_values("datetime").reset_index(drop=True)

        # Format datetime back to ISO string
        df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")

        output_cols = ["datetime", "open", "high", "low", "close", "volume"]
        return df[output_cols]

    def _load_price_files(
        self, directory: Path, ticker: str, pattern_prefix: str
    ) -> pd.DataFrame:
        """Load all matching price CSV files for a ticker."""
        if not directory.exists():
            return pd.DataFrame()

        # Match patterns like NVDA_15min_2024_2026.csv
        matches = sorted(directory.glob(f"{ticker}_{pattern_prefix}_*.csv"))
        if not matches:
            return pd.DataFrame()

        frames = []
        for f in matches:
            try:
                df = pd.read_csv(f, usecols=["datetime", "open", "high", "low", "close", "volume"])
                frames.append(df)
            except Exception as e:
                logger.warning(f"Error reading {f}: {e}")
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _load_daily_prices(self, ticker: str) -> pd.DataFrame:
        """Load daily prices from Parquet or CSV."""
        daily_dir = self._prices_dir / "daily"
        if not daily_dir.exists():
            # Try resampling 15min data
            return self._resample_to_daily(ticker)

        for ext, reader in [(".parquet", pd.read_parquet), (".csv", pd.read_csv)]:
            path = daily_dir / f"{ticker}{ext}"
            if path.exists():
                df = reader(path)
                # Normalize column name (some may have 'date' instead of 'datetime')
                if "date" in df.columns and "datetime" not in df.columns:
                    df = df.rename(columns={"date": "datetime"})
                return df

        # Fall back to resampling
        return self._resample_to_daily(ticker)

    def _resample_to_daily(self, ticker: str) -> pd.DataFrame:
        """Resample 15min data to daily OHLCV."""
        df = self._load_price_files(self._prices_dir / "15min", ticker, "15min")
        if df.empty:
            return pd.DataFrame()

        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
        df = df.dropna(subset=["datetime"])
        df = df.set_index("datetime")

        daily = df.resample("1D").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(subset=["open"])

        daily = daily.reset_index()
        daily["datetime"] = daily["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        return daily

    # --------------------------------------------------------
    # IV History
    # --------------------------------------------------------

    def query_iv_history(self, ticker: str) -> pd.DataFrame:
        """Query IV history for a ticker from local Parquet."""
        ticker = ticker.upper()
        path = self._iv_dir / f"{ticker}.parquet"

        if not path.exists():
            return pd.DataFrame(columns=[
                "date", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes",
            ])

        df = pd.read_parquet(path)
        output_cols = ["date", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes"]
        for col in output_cols:
            if col not in df.columns:
                df[col] = None
        return df[output_cols].sort_values("date").reset_index(drop=True)

    # --------------------------------------------------------
    # Fundamentals
    # --------------------------------------------------------

    def query_fundamentals(self, ticker: str) -> dict:
        """Query fundamental data from local IBKR JSON files."""
        ticker = ticker.upper()
        if not self._fundamentals_dir.exists():
            return {}

        # Find most recent file for this ticker
        matches = sorted(self._fundamentals_dir.glob(f"{ticker}_*.json"), reverse=True)
        if not matches:
            return {}

        try:
            with open(matches[0]) as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Error reading fundamentals for {ticker}: {e}")
            return {}

        # Extract the ReportSnapshot if available
        reports = data.get("reports", {})
        snapshot = reports.get("ReportSnapshot", {})

        return {
            "ticker": ticker,
            "collected_at": data.get("collected_at"),
            "snapshot": snapshot,
            "fin_summary": reports.get("ReportsFinSummary", {}),
            "ownership": reports.get("ReportsOwnership", {}),
        }

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
            ibkr = self._load_ibkr_news()
            if not ibkr.empty and "ticker" in ibkr.columns:
                tickers.update(ibkr["ticker"].dropna().unique())
            polygon = self._load_polygon_news()
            if not polygon.empty and "ticker" in polygon.columns:
                tickers.update(polygon["ticker"].dropna().unique())

        elif data_type == "prices":
            for d in [self._prices_dir / "15min", self._prices_dir / "hourly"]:
                if d.exists():
                    for f in d.glob("*.csv"):
                        # Extract ticker from filenames like NVDA_15min_2024_2026.csv
                        parts = f.stem.split("_")
                        if parts:
                            tickers.add(parts[0])

        elif data_type == "iv_history":
            if self._iv_dir.exists():
                for f in self._iv_dir.glob("*.parquet"):
                    tickers.add(f.stem)

        elif data_type == "fundamentals":
            if self._fundamentals_dir.exists():
                for f in self._fundamentals_dir.glob("*.json"):
                    parts = f.stem.split("_")
                    if parts:
                        tickers.add(parts[0])

        return sorted(tickers)