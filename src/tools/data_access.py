"""
DataAccessLayer — unified interface for all data queries.

Wraps a DataBackend (file or database) and adds:
- Config access (user_profile.yaml, tickers_core.json, sectors.yaml)
- Simple in-memory cache with TTL
- Helper methods for watchlists, sectors, strategy weights
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from .backends import DataBackend
from .backends.file_backend import FileBackend
from .backends.db_backend import DatabaseBackend
from .schemas import (
    FundamentalsResult,
    IVAnalysisResult,
    IVHistoryPoint,
    NewsArticle,
    NewsQueryResult,
    PriceBar,
    PriceQueryResult,
    SECFiling,
    WatchlistInfo,
    WatchlistResult,
)

logger = logging.getLogger(__name__)


class DataAccessLayer:
    """
    Unified data access entry point.

    Usage:
        dal = DataAccessLayer()                    # FileBackend auto-detected
        dal = DataAccessLayer(backend=my_backend)  # Custom backend
        dal = DataAccessLayer(db_dsn="postgresql://...")  # Future DB backend

    All data methods delegate to the backend, then wrap results
    in Pydantic schemas for consistent output.
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        backend: Optional[DataBackend] = None,
        db_dsn: Optional[str] = None,
    ):
        """
        Args:
            base_path: Project root. Auto-detected if None.
            backend: Explicit backend instance (takes priority).
            db_dsn: Database DSN. Use "auto" to detect from config/.env.
        """
        # Resolve project root
        if base_path is None:
            p = Path(__file__).resolve()
            for parent in p.parents:
                if (parent / "config").is_dir() and (parent / "data").is_dir():
                    base_path = parent
                    break
        self._base = Path(base_path) if base_path else None

        # Initialize backend
        if backend is not None:
            self._backend = backend
        elif db_dsn == "auto":
            # Auto-detect from config/.env
            env_dsn = self._load_env_db_dsn()
            if env_dsn:
                self._backend = DatabaseBackend(dsn=env_dsn)
                logger.info("Using DatabaseBackend (Supabase) from .env")
            else:
                self._backend = FileBackend(base_path=self._base)
        elif db_dsn:
            self._backend = DatabaseBackend(dsn=db_dsn)
        else:
            self._backend = FileBackend(base_path=self._base)

        # Config cache
        self._config_cache: Dict[str, Any] = {}

        # Simple TTL cache: key -> (data, timestamp)
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl_seconds: int = 3600  # 1 hour default

    @property
    def backend_type(self) -> str:
        """Return the active backend type name."""
        return type(self._backend).__name__

    def _load_env_db_dsn(self) -> Optional[str]:
        """Try to load SUPABASE_DB_URL from config/.env."""
        if self._base is None:
            return None
        env_path = self._base / "config" / ".env"
        if not env_path.exists():
            return None
        try:
            # Simple .env parser (avoid requiring python-dotenv at this level)
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SUPABASE_DB_URL=") and not line.startswith("#"):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val and val.startswith("postgresql"):
                            return val
        except Exception as e:
            logger.debug(f"Could not read .env: {e}")
        return None

    # ============================================================
    # Config Access
    # ============================================================

    def _load_yaml(self, name: str) -> dict:
        """Load and cache a YAML config file."""
        if name in self._config_cache:
            return self._config_cache[name]

        path = self._base / "config" / name
        if not path.exists():
            logger.warning(f"Config file not found: {path}")
            return {}

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        self._config_cache[name] = data
        return data

    def _load_json(self, name: str) -> dict:
        """Load and cache a JSON config file."""
        if name in self._config_cache:
            return self._config_cache[name]

        path = self._base / "config" / name
        if not path.exists():
            logger.warning(f"Config file not found: {path}")
            return {}

        with open(path) as f:
            data = json.load(f)
        self._config_cache[name] = data
        return data

    def get_user_profile(self) -> dict:
        """Get full user profile config."""
        return self._load_yaml("user_profile.yaml")

    def get_watchlist(self, include_sectors: bool = True) -> WatchlistResult:
        """
        Get watchlist tickers from user_profile.yaml.

        Returns tickers from core_holdings, interested, and custom_themes.
        """
        profile = self._load_yaml("user_profile.yaml")
        watchlists = profile.get("watchlists", {})
        details = []
        all_tickers = set()

        # Core holdings
        core = watchlists.get("core_holdings", {})
        for t in core.get("tickers", []):
            details.append(WatchlistInfo(
                ticker=t, group="core_holdings",
                priority=core.get("priority", "high"),
            ))
            all_tickers.add(t)

        # Interested
        interested = watchlists.get("interested", {})
        for t in interested.get("tickers", []):
            details.append(WatchlistInfo(
                ticker=t, group="interested",
                priority=interested.get("priority", "medium"),
            ))
            all_tickers.add(t)

        # Custom themes
        for theme in watchlists.get("custom_themes", []):
            theme_name = theme.get("name", "custom")
            for t in theme.get("tickers", []):
                if t not in all_tickers:
                    details.append(WatchlistInfo(
                        ticker=t, group=f"theme:{theme_name}",
                        priority="medium",
                    ))
                    all_tickers.add(t)

        # Sectors (from sectors.yaml)
        sectors = None
        if include_sectors:
            sector_watch = watchlists.get("sector_watch", {})
            watched_sectors = sector_watch.get("sectors", [])
            if watched_sectors:
                sectors_config = self._load_yaml("sectors.yaml")
                sectors = {}
                for s in watched_sectors:
                    if s in sectors_config:
                        sectors[s] = sectors_config[s]

        return WatchlistResult(
            tickers=sorted(all_tickers),
            details=details,
            sectors=sectors,
        )

    def get_sector_tickers(self, sector: str) -> List[str]:
        """Get tickers for a specific sector from sectors.yaml."""
        sectors = self._load_yaml("sectors.yaml")
        return sectors.get(sector, [])

    def get_all_sectors(self) -> Dict[str, List[str]]:
        """Get all sector definitions."""
        return self._load_yaml("sectors.yaml")

    def get_strategy_weights(self, strategy: Optional[str] = None) -> dict:
        """Get strategy weights from user_profile.yaml."""
        profile = self._load_yaml("user_profile.yaml")
        weights = profile.get("strategy_weights", {})

        if strategy is None:
            strategy = weights.get("default_strategy", "my_custom")

        return weights.get(strategy, {})

    def get_tickers_config(self) -> dict:
        """Get tickers_core.json config."""
        return self._load_json("tickers_core.json")

    def get_tier_tickers(self, tier: str = "tier1_core") -> List[str]:
        """Get all tickers in a given tier."""
        config = self.get_tickers_config()
        tier_data = config.get(tier, {})
        tickers = set()
        for group_key, group_val in tier_data.items():
            if isinstance(group_val, dict) and "tickers" in group_val:
                tickers.update(group_val["tickers"])
        return sorted(tickers)

    # ============================================================
    # Data Access (delegates to backend)
    # ============================================================

    def get_news(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        source: str = "auto",
        scored_only: bool = True,
    ) -> NewsQueryResult:
        """Query news and return structured result."""
        df = self._backend.query_news(
            ticker=ticker, days=days, source=source, scored_only=scored_only,
        )

        articles = []
        for _, row in df.iterrows():
            articles.append(NewsArticle(
                date=str(row.get("date", "")),
                ticker=str(row.get("ticker", "")),
                title=str(row.get("title", "")),
                source=str(row.get("source", "")),
                url=_safe_str(row.get("url")),
                publisher=_safe_str(row.get("publisher")),
                sentiment_score=_safe_float(row.get("sentiment_score")),
                risk_score=_safe_float(row.get("risk_score")),
                description=_safe_str(row.get("description")),
            ))

        # Source breakdown
        source_counts = {}
        if not df.empty and "source" in df.columns:
            source_counts = df["source"].value_counts().to_dict()

        return NewsQueryResult(
            ticker=ticker or "ALL",
            count=len(articles),
            articles=articles,
            source_breakdown=source_counts,
            query_days=days,
        )

    def get_prices(
        self,
        ticker: str,
        interval: str = "15min",
        days: int = 30,
    ) -> PriceQueryResult:
        """Query price bars and return structured result."""
        df = self._backend.query_prices(
            ticker=ticker, interval=interval, days=days,
        )

        bars = []
        for _, row in df.iterrows():
            bars.append(PriceBar(
                datetime=str(row["datetime"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
            ))

        date_range = None
        if bars:
            date_range = f"{bars[0].datetime[:10]} to {bars[-1].datetime[:10]}"

        return PriceQueryResult(
            ticker=ticker.upper(),
            interval=interval,
            count=len(bars),
            bars=bars,
            date_range=date_range,
        )

    def get_iv_history(self, ticker: str) -> List[IVHistoryPoint]:
        """Query IV history and return structured result."""
        df = self._backend.query_iv_history(ticker)

        points = []
        for _, row in df.iterrows():
            points.append(IVHistoryPoint(
                date=str(row["date"]),
                atm_iv=float(row["atm_iv"]),
                hv_30d=_safe_float(row.get("hv_30d")),
                vrp=_safe_float(row.get("vrp")),
                spot_price=_safe_float(row.get("spot_price")),
                num_quotes=_safe_int(row.get("num_quotes")),
            ))
        return points

    def get_iv_history_df(self, ticker: str) -> pd.DataFrame:
        """Query IV history as raw DataFrame (for analysis functions)."""
        return self._backend.query_iv_history(ticker)

    def get_fundamentals(self, ticker: str) -> FundamentalsResult:
        """Query fundamentals and return structured result."""
        raw = self._backend.query_fundamentals(ticker)
        if not raw:
            return FundamentalsResult(ticker=ticker.upper())

        snapshot = raw.get("snapshot", {})

        return FundamentalsResult(
            ticker=ticker.upper(),
            snapshot_date=raw.get("collected_at", "")[:10] if raw.get("collected_at") else None,
            market_cap=_safe_float(snapshot.get("market_cap")),
            pe_ratio=_safe_float(snapshot.get("pe_ratio")),
            forward_pe=_safe_float(snapshot.get("forward_pe")),
            ps_ratio=_safe_float(snapshot.get("price_to_sales")),
            pb_ratio=_safe_float(snapshot.get("price_to_book")),
            roe=_safe_float(snapshot.get("roe")),
            roa=_safe_float(snapshot.get("roa")),
            debt_to_equity=_safe_float(snapshot.get("debt_to_equity")),
            current_ratio=_safe_float(snapshot.get("current_ratio")),
            revenue_growth=_safe_float(snapshot.get("revenue_growth")),
            earnings_growth=_safe_float(snapshot.get("earnings_growth")),
            dividend_yield=_safe_float(snapshot.get("dividend_yield")),
            beta=_safe_float(snapshot.get("beta")),
            snapshot=snapshot if snapshot else None,
        )

    def get_sec_filings(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
    ) -> List[SECFiling]:
        """Query SEC filing metadata."""
        df = self._backend.query_sec_filings(ticker, filing_types)

        filings = []
        for _, row in df.iterrows():
            filings.append(SECFiling(
                ticker=str(row.get("ticker", ticker.upper())),
                filing_type=str(row.get("filing_type", "")),
                filed_date=str(row.get("filed_date", "")),
                period_of_report=row.get("period_of_report"),
                url=row.get("url"),
                accession_number=row.get("accession_number"),
                description=row.get("description"),
            ))
        return filings

    def get_available_tickers(self, data_type: str) -> List[str]:
        """List tickers with available data."""
        return self._backend.get_available_tickers(data_type)

    # ============================================================
    # Prices (raw DataFrame for analysis)
    # ============================================================

    def get_prices_df(
        self,
        ticker: str,
        interval: str = "15min",
        days: int = 30,
    ) -> pd.DataFrame:
        """Query prices as raw DataFrame (for analysis functions)."""
        return self._backend.query_prices(ticker, interval, days)

    # ============================================================
    # Simple Cache
    # ============================================================

    def get_from_cache(self, key: str, max_age_minutes: int = 60) -> Optional[Any]:
        """Retrieve cached data if not expired."""
        if key not in self._cache:
            return None
        data, ts = self._cache[key]
        if time.time() - ts > max_age_minutes * 60:
            del self._cache[key]
            return None
        return data

    def save_to_cache(self, key: str, data: Any) -> None:
        """Store data in cache with current timestamp."""
        self._cache[key] = (data, time.time())

    def clear_cache(self) -> None:
        """Clear all cached data (including config cache)."""
        self._cache.clear()
        self._config_cache.clear()


# ============================================================
# Helpers
# ============================================================

def _safe_str(val) -> Optional[str]:
    """Safely convert to string, return None for NaN/None."""
    if val is None:
        return None
    if isinstance(val, float) and val != val:  # NaN check
        return None
    return str(val)


def _safe_float(val) -> Optional[float]:
    """Safely convert to float, return None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None  # NaN check
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Safely convert to int, return None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN
            return None
        return int(f)
    except (ValueError, TypeError):
        return None