"""
DataAccessLayer — unified interface for all data queries.

Wraps a DataBackend (file or database) and adds:
- Config access (user_profile.yaml, tickers_core.json, sectors.yaml)
- Simple in-memory cache with TTL
- Helper methods for watchlists, sectors, strategy weights
"""

from __future__ import annotations

import hashlib
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
_SA_MARKET_NEWS_DETAIL_CACHE_HOURS = 24


def _extract_sa_published_year(published_date: Any) -> Optional[int]:
    """Extract a four-digit year from SA article metadata."""
    if hasattr(published_date, "year"):
        try:
            return int(published_date.year)
        except Exception:
            return None
    if isinstance(published_date, str):
        text = published_date.strip()
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
    return None


def _sanitize_sa_comments_count(
    comments_count: Any, published_date: Any
) -> int:
    """Normalize SA comment counts and strip known year-prefix pollution."""
    try:
        count = int(comments_count or 0)
    except Exception:
        return 0
    if count < 0:
        return 0

    year = _extract_sa_published_year(published_date)
    if year is None or count < 10000:
        return count

    count_text = str(count)
    year_text = str(year)
    if not count_text.startswith(year_text) or len(count_text) <= len(year_text):
        return count

    suffix_text = count_text[len(year_text):]
    if not suffix_text.isdigit():
        return count

    suffix = int(suffix_text)
    if 0 <= suffix <= 9999:
        return suffix
    return count


def _normalize_sa_market_news_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize SA market-news metadata before DB persistence."""
    normalized = dict(item)
    url = (normalized.get("url") or "").strip()
    title = (normalized.get("title") or "").strip()
    news_id = str(normalized.get("news_id") or "").strip()
    if not news_id and url:
        # Prefer the numeric /news/{id} segment; fall back to a stable URL hash.
        parts = [p for p in url.split("/") if p]
        if "news" in parts:
            idx = parts.index("news")
            if idx + 1 < len(parts):
                news_id = parts[idx + 1].split("?")[0].split("#")[0]
        if not news_id:
            news_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    if not news_id and title:
        raw = f"{title}:{normalized.get('published_text') or normalized.get('published_at') or ''}"
        news_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    tickers = []
    seen = set()
    for ticker in normalized.get("tickers") or []:
        t = str(ticker or "").strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        tickers.append(t)

    try:
        comments_count = int(normalized.get("comments_count") or 0)
    except Exception:
        comments_count = 0
    if comments_count < 0:
        comments_count = 0

    normalized.update({
        "news_id": news_id,
        "url": url,
        "title": title,
        "tickers": tickers,
        "comments_count": comments_count,
    })
    return normalized


def _sanitize_sa_article_meta(article: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of article metadata with normalized comment counts."""
    normalized = dict(article)
    published_date = normalized.get("published_date") or normalized.get("date")
    raw_count = normalized.get("comments_count", 0)
    clean_count = _sanitize_sa_comments_count(raw_count, published_date)
    if clean_count != raw_count:
        logger.warning(
            "Sanitized SA comments_count for %s: %s -> %s",
            normalized.get("article_id"),
            raw_count,
            clean_count,
        )
    normalized["comments_count"] = clean_count
    return normalized


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
                from src.tools.db_config import load_sslmode
                sslmode = load_sslmode(self._base / "config" / ".env", env_dsn)
                self._backend = DatabaseBackend(dsn=env_dsn, sslmode=sslmode)
                logger.info(f"Using DatabaseBackend (sslmode={sslmode})")
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
        """Try to load DATABASE_URL (or legacy SUPABASE_DB_URL) from config/.env."""
        if self._base is None:
            return None
        from src.tools.db_config import load_database_url
        return load_database_url(self._base / "config" / ".env")

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
        model: Optional[str] = None,
    ) -> NewsQueryResult:
        """Query news and return structured result.

        Args:
            model: Specific scoring model (e.g. 'gpt_5_2'). None = latest/best.
        """
        df = self._backend.query_news(
            ticker=ticker, days=days, source=source,
            scored_only=scored_only, model=model,
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

    def search_news(
        self,
        query: str = "",
        ticker: Optional[str] = None,
        days: int = 30,
        limit: int = 20,
        scored_only: bool = True,
    ) -> NewsQueryResult:
        """Search news with full-text search (DB) or keyword filtering (file fallback).

        Uses PostgreSQL tsvector/GIN for DB backend, falls back to Python-level
        filtering for FileBackend.
        """
        if isinstance(self._backend, DatabaseBackend):
            df = self._backend.query_news_search(
                query=query, ticker=ticker, days=days,
                limit=limit, scored_only=scored_only,
            )
        else:
            # FileBackend fallback: get all, filter in Python
            df = self._backend.query_news(
                ticker=ticker, days=days, scored_only=scored_only,
            )
            if query.strip() and not df.empty:
                q_lower = query.lower()
                mask = (
                    df["title"].str.lower().str.contains(q_lower, na=False)
                    | df.get("description", pd.Series(dtype=str)).str.lower().str.contains(q_lower, na=False)
                )
                df = df[mask].head(limit)

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

    def get_news_stats(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> List[dict]:
        """Get lightweight per-ticker news statistics.

        Returns list of dicts, one per ticker, with article_count,
        scored_count, date_range, avg_sentiment, avg_risk.
        """
        if isinstance(self._backend, DatabaseBackend):
            df = self._backend.query_news_stats(ticker=ticker, days=days)
        else:
            # FileBackend fallback: compute stats from full data
            news_result = self.get_news(ticker=ticker, days=days, scored_only=False)
            if not news_result.articles:
                return []
            # Group by ticker manually
            from collections import defaultdict
            groups: dict = defaultdict(list)
            for a in news_result.articles:
                groups[a.ticker].append(a)
            rows = []
            for t, arts in groups.items():
                sents = [a.sentiment_score for a in arts if a.sentiment_score is not None]
                risks = [a.risk_score for a in arts if a.risk_score is not None]
                rows.append({
                    "ticker": t,
                    "article_count": len(arts),
                    "scored_count": len(sents),
                    "earliest_date": min(a.date for a in arts) if arts else None,
                    "latest_date": max(a.date for a in arts) if arts else None,
                    "avg_sentiment": round(sum(sents) / len(sents), 2) if sents else None,
                    "avg_risk": round(sum(risks) / len(risks), 2) if risks else None,
                    "bullish_count": sum(1 for s in sents if s >= 4),
                    "bearish_count": sum(1 for s in sents if s <= 2),
                })
            return rows

        if df.empty:
            return []
        return df.to_dict("records")

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

    # ================================================================
    # Seeking Alpha Alpha Picks (Phase 11c)
    # ================================================================

    _SA_CACHE_DIR = Path("data/cache/seeking_alpha")

    def get_sa_portfolio(
        self,
        portfolio_status: Optional[str] = None,
        symbol: Optional[str] = None,
        include_stale: bool = False,
    ) -> List[Dict]:
        """Get SA Alpha Picks portfolio data."""
        if isinstance(self._backend, DatabaseBackend):
            return self._backend.query_sa_picks(
                portfolio_status=portfolio_status,
                symbol=symbol,
                include_stale=include_stale,
            )
        return self._load_sa_file_cache(portfolio_status, symbol, include_stale)

    def apply_sa_refresh(
        self,
        scope: str,
        picks: List[Dict],
        attempt_ts,
        snapshot_ts,
    ) -> int:
        """Atomic per-tab refresh: mark_stale + upsert + update_meta.

        Success path: overwrites all meta fields.
        """
        if isinstance(self._backend, DatabaseBackend):
            count = self._backend.apply_sa_refresh(scope, picks, attempt_ts, snapshot_ts)
        else:
            count = len(picks)

        # File cache: always write (dual storage when DB available)
        try:
            old_picks = self._load_sa_file_cache(scope, include_stale=True)
            reconciled = self._reconcile_sa_file_stale(old_picks, picks)
            self._save_sa_file_cache(reconciled, scope)
            self._save_sa_file_meta(
                scope=scope,
                attempt_ts=attempt_ts,
                snapshot_ts=snapshot_ts,
                row_count=count,
                ok=True,
                error=None,
            )
        except Exception as e:
            logger.warning("File cache write failed for SA refresh: %s", e)

        return count

    def record_sa_refresh_failure(
        self, scope: str, attempt_ts, error: str
    ) -> None:
        """Record refresh failure — only update meta, don't touch picks.

        Failure path: only updates last_attempt_at, ok, last_error.
        Preserves: last_success_at, snapshot_ts, row_count.
        """
        if isinstance(self._backend, DatabaseBackend):
            self._backend.record_sa_refresh_failure(scope, attempt_ts, error)

        # File cache meta
        try:
            self._save_sa_file_meta(
                scope=scope,
                attempt_ts=attempt_ts,
                snapshot_ts=None,
                row_count=None,
                ok=False,
                error=error,
            )
        except Exception as e:
            logger.warning("File cache meta write failed: %s", e)

    def get_sa_pick_detail(
        self, symbol: str, picked_date: Optional[str] = None
    ) -> Optional[Dict]:
        """Get detail for a specific SA pick."""
        if isinstance(self._backend, DatabaseBackend):
            result = self._backend.get_sa_pick_detail(symbol, picked_date)
            if result:
                return result

        # File fallback: check file cache
        if picked_date:
            detail = self._load_sa_file_detail(symbol, picked_date)
            # Merge portfolio row metadata (company, return_pct, sector, etc.)
            row = None
            for status in ("current", "closed"):
                picks = self._load_sa_file_cache(
                    status, symbol=symbol, include_stale=True
                )
                for p in (picks or []):
                    if p.get("picked_date") == picked_date:
                        row = p
                        break
                if row:
                    break
            if row and detail:
                return {**row, **detail}
            return detail or row

        # Deterministic fallback for file mode
        picks = self._load_sa_file_cache("current", symbol=symbol, include_stale=False)
        if picks:
            p = sorted(picks, key=lambda x: x.get("picked_date", ""), reverse=True)[0]
            detail = self._load_sa_file_detail(symbol, p.get("picked_date", ""))
            if detail:
                return {**p, **detail}
            return p

        # Check stale
        picks = self._load_sa_file_cache("current", symbol=symbol, include_stale=True)
        if picks:
            p = sorted(picks, key=lambda x: x.get("picked_date", ""), reverse=True)[0]
            return p

        return None

    def save_sa_pick_detail(
        self, symbol: str, picked_date: str, content: str
    ) -> bool:
        """Save detail report for a specific SA pick.

        Returns True if the primary backend write succeeded:
        - DB mode: DB update must succeed (file is best-effort backup)
        - File-only mode: file write must succeed
        """
        db_ok = True  # default for file-only mode
        if isinstance(self._backend, DatabaseBackend):
            try:
                db_ok = self._backend.update_sa_pick_detail(
                    symbol, picked_date, content
                )
                if not db_ok:
                    logger.warning(
                        "No DB row found for %s/%s — detail not saved to DB",
                        symbol, picked_date,
                    )
            except Exception as e:
                logger.error(
                    "DB detail save failed for %s/%s: %s", symbol, picked_date, e
                )
                db_ok = False

        file_ok = False
        try:
            self._save_sa_file_detail(symbol, picked_date, content)
            file_ok = True
        except Exception as e:
            logger.warning("File detail save failed: %s", e)

        # DB mode: DB must succeed; file-only mode: file must succeed
        if isinstance(self._backend, DatabaseBackend):
            return db_ok
        return file_ok

    def get_sa_refresh_meta(self) -> Dict[str, Any]:
        """Get per-tab refresh metadata."""
        if isinstance(self._backend, DatabaseBackend):
            return self._backend.get_sa_refresh_meta()
        return self._load_sa_file_meta() or {}


    # ── SA Market News (SA-R1, DB-only) ──

    def save_sa_market_news(
        self,
        items: List[Dict],
        detail_backfill_limit: int = 0,
    ) -> Dict[str, Any]:
        """Persist recent Seeking Alpha market-news metadata."""
        if not isinstance(self._backend, DatabaseBackend):
            return {"error": "DB required for market news"}
        normalized = [
            _normalize_sa_market_news_item(item)
            for item in items
            if (item.get("url") or item.get("title"))
        ]
        saved = self._backend.upsert_sa_market_news(normalized)
        current_ids = [item["news_id"] for item in normalized if item.get("news_id")]
        need_detail = self._backend.query_sa_market_news_need_detail(
            current_ids,
            detail_cache_hours=_SA_MARKET_NEWS_DETAIL_CACHE_HOURS,
            limit=len(normalized) or 50,
        )
        if detail_backfill_limit:
            backlog = self._backend.query_sa_market_news_need_detail(
                news_ids=None,
                detail_cache_hours=_SA_MARKET_NEWS_DETAIL_CACHE_HOURS,
                limit=detail_backfill_limit,
                exclude_news_ids=current_ids,
            )
            seen = {item.get("news_id") for item in need_detail if item.get("news_id")}
            for item in backlog:
                news_id = item.get("news_id")
                if not news_id or news_id in seen:
                    continue
                seen.add(news_id)
                need_detail.append(item)
        return {"status": "ok", "saved": saved, "need_detail": need_detail}

    def get_sa_market_news(
        self,
        ticker: str = None,
        keyword: str = None,
        limit: int = 20,
    ) -> List[Dict]:
        """Query recent Seeking Alpha market-news metadata."""
        if not isinstance(self._backend, DatabaseBackend):
            return []
        return self._backend.query_sa_market_news(
            ticker=ticker, keyword=keyword, limit=limit
        )

    def get_sa_market_news_recent_ids(self, limit: int = 200) -> List[str]:
        """Return recent market-news IDs for duplicate-aware list scanning."""
        if not isinstance(self._backend, DatabaseBackend):
            return []
        return self._backend.query_sa_market_news_recent_ids(limit=limit)

    def save_sa_market_news_detail(self, news_id: str, body_markdown: str) -> bool:
        """Persist a single market-news body Markdown payload."""
        if not isinstance(self._backend, DatabaseBackend):
            return False
        return self._backend.save_sa_market_news_detail(news_id, body_markdown)

    def invalidate_dirty_sa_market_news_detail(self) -> int:
        """Invalidate cached market-news body content that matches known noisy captures."""
        if not isinstance(self._backend, DatabaseBackend):
            return 0
        return self._backend.invalidate_dirty_sa_market_news_detail()

    # ── SA Articles + Comments (Phase 11c-v3, DB-only) ──

    def save_sa_articles_meta(
        self, articles: List[Dict], mode: str = "quick"
    ) -> Dict[str, Any]:
        """Batch upsert article metadata. Returns need_content + unresolved info.

        DB-only — returns error in file-only mode.
        """
        if not isinstance(self._backend, DatabaseBackend):
            return {"error": "DB required for articles"}

        # Auto-upgrade: check if first run (empty DB)
        try:
            existing = self._backend.query_sa_articles(limit=1)
            if not existing and mode == "quick":
                return {"status": "ok", "auto_upgrade": True, "saved": 0}
        except Exception:
            pass

        # Upsert metadata
        normalized_articles = [_sanitize_sa_article_meta(a) for a in articles]
        saved = self._backend.upsert_sa_articles_meta(normalized_articles)

        try:
            cleaned = self._backend.sanitize_corrupted_sa_comments_counts()
            if cleaned:
                logger.warning("Sanitized %d corrupted SA comments_count rows in DB", cleaned)
        except AttributeError:
            pass
        except Exception as e:
            logger.warning("Failed to sanitize corrupted SA comments_count rows: %s", e)

        # Determine need_content (body IS NULL)
        all_articles = self._backend.query_sa_articles(limit=9999)
        need_content = [
            {"article_id": a["article_id"], "url": a.get("url", "")}
            for a in all_articles
            if not a.get("has_content")
        ]

        # Determine need_comments
        need_comments = []
        need_content_ids = {a["article_id"] for a in need_content}
        if mode in ("full", "backfill"):
            from src.agents.config import get_agent_config
            try:
                config = get_agent_config()
                ttl = getattr(config, "sa_comments_cache_days", 7)
                if mode == "backfill":
                    backfill_limit = max(
                        0,
                        int(getattr(config, "sa_comments_backfill_per_backfill_scan", 50)),
                    )
                else:
                    backfill_limit = max(
                        0,
                        int(getattr(config, "sa_comments_backfill_per_full_scan", 10)),
                    )
            except Exception:
                ttl = 7
                backfill_limit = 50 if mode == "backfill" else 10
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=ttl)
            need_comment_ids = set()
            backfill_candidates = []
            for a in all_articles:
                if a["article_id"] in need_content_ids:
                    continue  # Mutual exclusion: need_content takes priority
                if not a.get("has_content"):
                    continue
                remote_count = _sanitize_sa_comments_count(
                    a.get("comments_count"), a.get("published_date")
                )
                stored_count = int(a.get("stored_comments_count") or 0)
                gap = remote_count - stored_count
                fetched = a.get("comments_fetched_at")
                is_stale = fetched is None
                if fetched:
                    if isinstance(fetched, str):
                        fetched = datetime.fromisoformat(
                            fetched.replace("Z", "+00:00")
                        )
                    is_stale = fetched <= cutoff
                if is_stale:
                    if remote_count <= 0 and stored_count <= 0:
                        continue
                    need_comments.append(
                        {"article_id": a["article_id"], "url": a.get("url", "")}
                    )
                    need_comment_ids.add(a["article_id"])
                    continue
                if gap > 0:
                    published = a.get("published_date")
                    if hasattr(published, "isoformat"):
                        published_key = published.isoformat()
                    elif published is None:
                        published_key = ""
                    else:
                        published_key = str(published)
                    backfill_candidates.append((gap, published_key, a))
            if backfill_limit > 0:
                backfill_candidates.sort(
                    key=lambda item: (item[0], item[1]),
                    reverse=True,
                )
                for _, _, a in backfill_candidates[:backfill_limit]:
                    if a["article_id"] in need_comment_ids:
                        continue
                    need_comments.append(
                        {"article_id": a["article_id"], "url": a.get("url", "")}
                    )
                    need_comment_ids.add(a["article_id"])
        elif mode == "quick":
            scanned_ids = {
                a.get("article_id")
                for a in normalized_articles
                if a.get("article_id")
            }
            for a in all_articles:
                if a["article_id"] not in scanned_ids:
                    continue
                if a["article_id"] in need_content_ids:
                    continue
                if not a.get("has_content"):
                    continue
                remote_count = _sanitize_sa_comments_count(
                    a.get("comments_count"), a.get("published_date")
                )
                stored_count = int(a.get("stored_comments_count") or 0)
                if remote_count > stored_count:
                    need_comments.append(
                        {"article_id": a["article_id"], "url": a.get("url", "")}
                    )

        # Unresolved symbols (current picks only, metadata-only matching)
        unresolved = self._compute_unresolved_symbols()

        return {
            "status": "ok",
            "saved": saved,
            "need_content": need_content,
            "need_comments": need_comments,
            "unresolved_symbols": unresolved,
            "auto_upgrade": False,
        }

    def save_sa_article_with_comments(
        self, article_id: str, body_markdown: str, comments: List[Dict]
    ) -> Dict:
        """Compound atomic write: article body + comments + pick sync."""
        if not isinstance(self._backend, DatabaseBackend):
            return {"error": "DB required"}
        return self._backend.save_article_with_comments(
            article_id, body_markdown, comments
        )

    def save_sa_comments_only(
        self, article_id: str, comments: List[Dict]
    ) -> Dict[str, int]:
        """Update comments only (refresh run). Returns refresh stats."""
        if not isinstance(self._backend, DatabaseBackend):
            return {"prepared_comments": 0, "stored_comments_total": 0, "net_new_comments": 0}
        return self._backend.update_article_comments(article_id, comments)

    def audit_sa_unresolved_symbols(self) -> Dict:
        """Full-text fallback matching for current picks without canonical article."""
        if not isinstance(self._backend, DatabaseBackend):
            return {"unresolved_symbols": [], "resolved_by_fulltext": 0}
        return self._backend.audit_unresolved_symbols()

    def get_sa_articles(
        self,
        ticker: str = None,
        keyword: str = None,
        article_type: str = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Query SA articles with filters."""
        if not isinstance(self._backend, DatabaseBackend):
            return []
        return self._backend.query_sa_articles(
            ticker=ticker, keyword=keyword, article_type=article_type, limit=limit
        )

    def get_sa_article_detail(self, article_id: str) -> Optional[Dict]:
        """Get full article content + comments."""
        if not isinstance(self._backend, DatabaseBackend):
            return None
        return self._backend.get_sa_article_with_comments(article_id)

    def _compute_unresolved_symbols(self) -> List[str]:
        """Current picks truly missing detail, after metadata-level article matching.

        Checks: no canonical, no detail_report, AND no matching article in sa_articles
        (exact/prefix ticker match on analysis/removal type).
        """
        if not isinstance(self._backend, DatabaseBackend):
            return []
        conn = self._backend._get_conn()
        try:
            with conn.cursor() as cur:
                # Get picks without canonical and without detail_report
                cur.execute(
                    "SELECT DISTINCT symbol FROM sa_alpha_picks "
                    "WHERE portfolio_status = 'current' AND is_stale = false "
                    "AND canonical_article_id IS NULL "
                    "AND detail_report IS NULL"
                )
                candidates = [r[0] for r in cur.fetchall()]

                # Filter: only truly unresolved (no matching article exists)
                unresolved = []
                for symbol in candidates:
                    cur.execute(
                        "SELECT 1 FROM sa_articles "
                        "WHERE (ticker = %s OR (ticker LIKE %s AND LENGTH(ticker) <= LENGTH(%s) * 2)) "
                        "AND article_type IN ('analysis', 'removal') "
                        "LIMIT 1",
                        (symbol, symbol + "%", symbol),
                    )
                    if not cur.fetchone():
                        unresolved.append(symbol)
                return unresolved
        except Exception as e:
            logger.warning("_compute_unresolved_symbols failed: %s", e)
            return []

    # ── SA file I/O private methods ──

    def _load_sa_file_cache(
        self,
        portfolio_status: Optional[str] = None,
        symbol: Optional[str] = None,
        include_stale: bool = False,
    ) -> List[Dict]:
        """Read portfolio_{status}.json, filter by is_stale + symbol."""
        results = []
        statuses = (
            [portfolio_status]
            if portfolio_status and portfolio_status != "all"
            else ["current", "closed"]
        )

        for status in statuses:
            path = self._SA_CACHE_DIR / f"portfolio_{status}.json"
            if not path.exists():
                continue
            try:
                import json as _json
                with open(path) as f:
                    rows = _json.load(f)
                for row in rows:
                    if not include_stale and row.get("is_stale", False):
                        continue
                    if symbol and row.get("symbol", "").upper() != symbol.upper():
                        continue
                    results.append(row)
            except Exception as e:
                logger.warning("Failed to read %s: %s", path, e)

        return results

    def _save_sa_file_cache(self, picks: List[Dict], portfolio_status: str) -> None:
        """Write portfolio_{status}.json (includes stale rows)."""
        import json as _json

        self._SA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = self._SA_CACHE_DIR / f"portfolio_{portfolio_status}.json"
        tmp_path = path.with_suffix(".json.tmp")

        # Serialize datetime objects
        serializable = []
        for p in picks:
            row = {}
            for k, v in p.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
                elif isinstance(v, (int, float, str, bool, type(None), list, dict)):
                    row[k] = v
                else:
                    row[k] = str(v)
            serializable.append(row)

        with open(tmp_path, "w") as f:
            _json.dump(serializable, f, indent=2, ensure_ascii=False)
        import os
        os.replace(tmp_path, path)

    def _reconcile_sa_file_stale(
        self, old_picks: List[Dict], new_picks: List[Dict]
    ) -> List[Dict]:
        """Diff by (symbol, picked_date). Missing → is_stale=True. Returns merged list."""
        new_keys = {
            (p.get("symbol", ""), p.get("picked_date", ""))
            for p in new_picks
        }

        stale = []
        for p in old_picks:
            key = (p.get("symbol", ""), p.get("picked_date", ""))
            if key not in new_keys:
                p = {**p, "is_stale": True}
                stale.append(p)

        # New picks (is_stale=False) + stale from old
        result = [{**p, "is_stale": False} for p in new_picks]
        result.extend(stale)
        return result

    def _load_sa_file_detail(
        self, symbol: str, picked_date: str
    ) -> Optional[Dict]:
        """Read detail_{SYMBOL}_{YYYY-MM-DD}.json."""
        import json as _json

        path = self._SA_CACHE_DIR / "details" / f"{symbol.upper()}_{picked_date}.json"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return _json.load(f)
        except Exception:
            return None

    def _save_sa_file_detail(
        self, symbol: str, picked_date: str, content: str
    ) -> None:
        """Write detail_{SYMBOL}_{YYYY-MM-DD}.json."""
        import json as _json
        from datetime import datetime, timezone

        details_dir = self._SA_CACHE_DIR / "details"
        details_dir.mkdir(parents=True, exist_ok=True)

        path = details_dir / f"{symbol.upper()}_{picked_date}.json"
        data = {
            "detail_report": content,
            "detail_fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        with open(path, "w") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_sa_file_meta(self) -> Optional[Dict]:
        """Read meta.json."""
        import json as _json

        path = self._SA_CACHE_DIR / "meta.json"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return _json.load(f)
        except Exception:
            return None

    def _save_sa_file_meta(
        self,
        scope: str,
        attempt_ts,
        snapshot_ts,
        row_count,
        ok: bool,
        error: Optional[str] = None,
    ) -> None:
        """Update meta.json for a scope.

        Success: overwrites all fields for scope.
        Failure (ok=False): only updates last_attempt_at, ok, last_error.
        Preserves: last_success_at, snapshot_ts, row_count on failure.
        """
        import json as _json

        self._SA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        meta_path = self._SA_CACHE_DIR / "meta.json"
        tmp_path = meta_path.with_suffix(".json.tmp")

        # Read existing meta
        meta = {}
        if meta_path.exists():
            try:
                with open(meta_path) as f:
                    meta = _json.load(f)
            except Exception:
                pass

        # Serialize timestamps
        def _ts(v):
            if v is None:
                return None
            return v.isoformat() if hasattr(v, "isoformat") else str(v)

        if ok:
            # Success: overwrite all fields
            meta[scope] = {
                "last_attempt_at": _ts(attempt_ts),
                "last_success_at": _ts(snapshot_ts),
                "snapshot_ts": _ts(snapshot_ts),
                "row_count": row_count,
                "ok": True,
                "last_error": None,
            }
        else:
            # Failure: only update attempt/ok/error, preserve success fields
            existing = meta.get(scope, {})
            existing["last_attempt_at"] = _ts(attempt_ts)
            existing["ok"] = False
            existing["last_error"] = error
            meta[scope] = existing

        with open(tmp_path, "w") as f:
            _json.dump(meta, f, indent=2, ensure_ascii=False)
        import os
        os.replace(tmp_path, meta_path)

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
