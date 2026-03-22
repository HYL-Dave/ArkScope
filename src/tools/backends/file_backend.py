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
import re
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score column detection utilities
# ---------------------------------------------------------------------------

# Pattern: sentiment_haiku, risk_gpt_5_2_xhigh, etc.
_SCORE_COL_PATTERN = re.compile(
    r"^(sentiment|risk)_(.+?)(?:_(none|minimal|low|medium|high|xhigh))?$"
)
_NON_MODEL_SUFFIXES = {"score", "title", "content", "source", "description"}

# Model priority: newest/best first. Used when no specific model is requested.
# Fallback if config/user_profile.yaml doesn't define model_priority
_DEFAULT_MODEL_PRIORITY = ["gpt_5_4", "gpt_5_4_mini", "gpt_5_4_nano", "gpt_5_2", "gpt_5"]


def detect_score_columns(df: pd.DataFrame) -> list[tuple[str, str, str | None, str]]:
    """Auto-detect score columns from a DataFrame.

    Returns list of (score_type, model, reasoning_effort, column_name).
    """
    results = []
    for col in df.columns:
        m = _SCORE_COL_PATTERN.match(col)
        if m:
            model = m.group(2)
            if model in _NON_MODEL_SUFFIXES:
                continue
            results.append((m.group(1), model, m.group(3), col))
    return results


def resolve_score_columns(
    score_cols: list[tuple[str, str, str | None, str]],
    preferred_model: str | None = None,
    model_priority: list[str] | None = None,
) -> tuple[str | None, str | None]:
    """Pick the best sentiment/risk column pair based on model preference or priority.

    Args:
        score_cols: Output of detect_score_columns().
        preferred_model: Model column suffix to prefer (e.g. 'gpt_5_2').
        model_priority: Ordered list of model suffixes (highest priority first).
            Falls back to _DEFAULT_MODEL_PRIORITY if None.

    Returns:
        (sentiment_column_name, risk_column_name) — either may be None.
    """
    sentiment_map = {c[1]: c[3] for c in score_cols if c[0] == "sentiment"}
    risk_map = {c[1]: c[3] for c in score_cols if c[0] == "risk"}

    if preferred_model:
        suffix = preferred_model.replace("-", "_").replace(".", "_")
        return sentiment_map.get(suffix), risk_map.get(suffix)

    # Auto-select by priority
    priority = model_priority or _DEFAULT_MODEL_PRIORITY
    for m in priority:
        if m in sentiment_map:
            return sentiment_map[m], risk_map.get(m)

    # Fallback: first available
    s = next(iter(sentiment_map.values()), None) if sentiment_map else None
    r = next(iter(risk_map.values()), None) if risk_map else None
    return s, r


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

        # Load model priority from config (fallback to default)
        self._model_priority = self._load_model_priority()

        # Caches for raw data (loaded lazily, large files)
        self._ibkr_raw: Optional[pd.DataFrame] = None
        self._polygon_raw: Optional[pd.DataFrame] = None

    def _load_model_priority(self) -> list[str]:
        """Load model_priority from config/user_profile.yaml."""
        cfg_path = self._base / "config" / "user_profile.yaml"
        if not cfg_path.exists():
            return _DEFAULT_MODEL_PRIORITY
        try:
            import yaml
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            priority = cfg.get("llm_preferences", {}).get("model_priority")
            if isinstance(priority, list) and priority:
                return priority
        except Exception:
            pass
        return _DEFAULT_MODEL_PRIORITY

    # --------------------------------------------------------
    # News
    # --------------------------------------------------------

    def _load_ibkr_news(self, model: Optional[str] = None) -> pd.DataFrame:
        """Load and normalize IBKR scored news with flexible model selection.

        Dynamically detects all score columns and picks the best pair
        based on model preference or config model_priority.
        """
        if self._ibkr_raw is None:
            path = self._news_dir / "ibkr_scored_final.parquet"
            if not path.exists():
                self._ibkr_raw = pd.DataFrame()
            else:
                self._ibkr_raw = pd.read_parquet(path)
                logger.debug(f"Loaded IBKR news raw: {len(self._ibkr_raw)} rows")

        if self._ibkr_raw.empty:
            return pd.DataFrame()

        df = self._ibkr_raw.copy()

        # Detect and resolve score columns
        score_cols = detect_score_columns(df)
        sent_col, risk_col = resolve_score_columns(
            score_cols, model, self._model_priority,
        )

        df["sentiment_score"] = df[sent_col] if sent_col and sent_col in df.columns else None
        df["risk_score"] = df[risk_col] if risk_col and risk_col in df.columns else None

        # Normalize other columns
        if "source_api" in df.columns:
            df = df.rename(columns={"source_api": "source"})
        df["source"] = "ibkr"
        df["date"] = pd.to_datetime(df.get("published_at"), errors="coerce").dt.strftime("%Y-%m-%d")

        # Ensure standard column names exist
        for col in ["ticker", "title", "url", "publisher", "description"]:
            if col not in df.columns:
                df[col] = None

        return df

    def _load_polygon_news(self, model: Optional[str] = None) -> pd.DataFrame:
        """Load and normalize Polygon scored news with flexible model selection."""
        if self._polygon_raw is None:
            path = self._news_dir / "polygon_scored_final.csv"
            if not path.exists():
                self._polygon_raw = pd.DataFrame()
            else:
                self._polygon_raw = pd.read_csv(path)
                logger.debug(f"Loaded Polygon news raw: {len(self._polygon_raw)} rows")

        if self._polygon_raw.empty:
            return pd.DataFrame()

        df = self._polygon_raw.copy()

        # Detect and resolve score columns
        score_cols = detect_score_columns(df)
        sent_col, risk_col = resolve_score_columns(
            score_cols, model, self._model_priority,
        )

        df["sentiment_score"] = df[sent_col] if sent_col and sent_col in df.columns else None
        df["risk_score"] = df[risk_col] if risk_col and risk_col in df.columns else None

        # Normalize column names
        if "Stock_symbol" in df.columns:
            df = df.rename(columns={"Stock_symbol": "ticker"})
        if "Article_title" in df.columns:
            df = df.rename(columns={"Article_title": "title"})
        df["source"] = "polygon"
        df["date"] = pd.to_datetime(df.get("published_at"), errors="coerce").dt.strftime("%Y-%m-%d")

        for col in ["url", "publisher", "description"]:
            if col not in df.columns:
                df[col] = None

        return df

    def _load_raw_news(self, days: int = 30) -> pd.DataFrame:
        """Load unscored news from data/news/raw/ parquet files.

        Only loads files from year-months overlapping the requested date
        range to avoid scanning all historical data.  Returns a DataFrame
        with the standard news columns; sentiment/risk scores are NaN.
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

                # Standardise columns to match scored-file output
                df["source"] = source_name
                df["date"] = pd.to_datetime(
                    df.get("published_at"), errors="coerce",
                ).dt.strftime("%Y-%m-%d")
                df["sentiment_score"] = float("nan")
                df["risk_score"] = float("nan")

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
        scored_only: bool = True,
        model: Optional[str] = None,
    ) -> pd.DataFrame:
        """Query news articles from local scored + raw files.

        Scored articles (with sentiment/risk scores) are loaded first.
        Raw articles from data/news/raw/ are merged in to fill gaps
        (e.g. recently collected but not yet scored).  When an article
        exists in both scored and raw, the scored version is kept.

        Args:
            ticker: Filter by ticker symbol.
            days: Number of days to look back.
            source: Data source filter ('ibkr', 'polygon', 'auto').
            scored_only: Only return articles with at least one score.
            model: Specific model to get scores from (e.g. 'gpt-5.2' or 'gpt_5_2').
                   If None, picks the best available by config model_priority.
        """
        frames = []
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        if source in ("ibkr", "auto"):
            df = self._load_ibkr_news(model=model)
            if not df.empty:
                frames.append(df)

        if source in ("polygon", "auto"):
            df = self._load_polygon_news(model=model)
            if not df.empty:
                frames.append(df)

        # Also load raw (unscored) articles to fill gaps
        raw_df = self._load_raw_news(days=days)
        if not raw_df.empty:
            if source not in ("auto",):
                # Filter raw to requested source
                raw_df = raw_df[raw_df["source"] == source]
            if not raw_df.empty:
                frames.append(raw_df)

        if not frames:
            return pd.DataFrame(columns=[
                "date", "ticker", "title", "source", "url",
                "publisher", "sentiment_score", "risk_score", "description",
            ])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            combined = pd.concat(frames, ignore_index=True)

        # Deduplicate: scored articles (loaded first) take priority
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
        if not frames:
            return pd.DataFrame()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            return pd.concat(frames, ignore_index=True)

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
            ibkr = self._load_ibkr_news(model=None)
            if not ibkr.empty and "ticker" in ibkr.columns:
                tickers.update(ibkr["ticker"].dropna().unique())
            polygon = self._load_polygon_news(model=None)
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