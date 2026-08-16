"""
DataAccessLayer — unified interface for all data queries.

Wraps a DataBackend (file or database) and adds:
- Config access (user_profile.yaml and sectors.yaml)
- Simple in-memory cache with TTL
- Helper methods for watchlists, sectors, strategy weights
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from src.news_content_availability import ContentFilter, empty_content_counts

from .backends.local_capabilities import LocalDataCapabilities
from .backends.sa_capture_backend import SACaptureBackend
from .schemas import (
    FundamentalsResult,
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
_SA_MARKET_NEWS_BACKFILL_PUBLISHED_WINDOW_HOURS = 24


def _failed_sa_reconciliation() -> Dict[str, Any]:
    return {
        "status": "failed",
        "error_code": "reconciliation_failed",
        "enrichment": [],
    }


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
    normalized["comments_count_observed_at"] = (
        normalized.get("comments_count_observed_at") or None
    )
    return normalized


class DataAccessLayer:
    """
    Unified data access entry point.

    Usage:
        dal = DataAccessLayer()
        dal = DataAccessLayer(backend=my_local_capability)

    All data methods delegate to the backend, then wrap results
    in Pydantic schemas for consistent output.
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        backend: Optional[LocalDataCapabilities] = None,
    ):
        """
        Args:
            base_path: Project root. Auto-detected if None.
            backend: Explicit structural local capability.
        """
        # Resolve project root
        if base_path is None:
            p = Path(__file__).resolve()
            for parent in p.parents:
                if (parent / "config").is_dir() and (parent / "data").is_dir():
                    base_path = parent
                    break
        self._base = Path(base_path) if base_path else Path(__file__).resolve().parents[2]

        if backend is not None:
            self._backend = backend
        else:
            import os

            market_db = os.environ.get("ARKSCOPE_MARKET_DB") or str(
                self._base / "data" / "market_data.db"
            )
            sa_db = os.environ.get("ARKSCOPE_SA_DB") or str(
                self._base / "data" / "sa_capture.db"
            )
            self._backend = SACaptureBackend(
                sa_db=sa_db,
                market_db=market_db,
                base_path=self._base,
            )

        # Config cache
        self._config_cache: Dict[str, Any] = {}

        # Simple TTL cache: key -> (data, timestamp)
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl_seconds: int = 3600  # 1 hour default

    @property
    def backend_type(self) -> str:
        """Return the active backend type name."""
        return type(self._backend).__name__

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

    # ============================================================
    # Data Access (delegates to backend)
    # ============================================================

    def get_news(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        source: str = "auto",
    ) -> NewsQueryResult:
        """Query raw news and return a structured result."""
        df = self._backend.query_news(
            ticker=ticker, days=days, source=source,
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
    ) -> NewsQueryResult:
        """Search the current local news authority."""
        df = self._backend.query_news_search(
            query=query,
            ticker=ticker,
            days=days,
            limit=limit,
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

        Returns one raw article count and date range per ticker.
        """
        df = self._backend.query_news_stats(ticker=ticker, days=days)

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

    def get_news_feed(
        self,
        q=None,
        ticker=None,
        source=None,
        days=30,
        limit=50,
        offset=0,
        content: ContentFilter = "all",
    ) -> dict:
        """Return the score-free local news feed."""
        return self._backend.query_news_feed(
            q=q,
            ticker=ticker,
            source=source,
            content=content,
            days=days,
            limit=limit,
            offset=offset,
        )

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
        return self._backend.query_sa_picks(
            portfolio_status=portfolio_status,
            symbol=symbol,
            include_stale=include_stale,
        )

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
        count = self._backend.apply_sa_refresh(scope, picks, attempt_ts, snapshot_ts)

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

        Returns True when the current local store update succeeds. The report
        file remains a best-effort secondary representation.
        """
        local_ok = False
        try:
            local_ok = self._backend.update_sa_pick_detail(
                symbol, picked_date, content
            )
            if not local_ok:
                logger.warning("No local row found for %s/%s", symbol, picked_date)
        except Exception as exc:
            logger.error("Local detail save failed for %s/%s: %s", symbol, picked_date, exc)

        try:
            self._save_sa_file_detail(symbol, picked_date, content)
        except Exception as exc:
            logger.warning("File detail save failed: %s", exc)
        return local_ok

    def get_sa_refresh_meta(self) -> Dict[str, Any]:
        """Get per-tab refresh metadata."""
        return self._backend.get_sa_refresh_meta()


    # ── SA Market News ──

    def save_sa_market_news(
        self,
        items: List[Dict],
        detail_current_limit: int | None = None,
        detail_backfill_limit: int = 0,
    ) -> Dict[str, Any]:
        """Persist recent Seeking Alpha market-news metadata."""
        normalized = [
            _normalize_sa_market_news_item(item)
            for item in items
            if (item.get("url") or item.get("title"))
        ]
        saved = self._backend.upsert_sa_market_news(normalized)
        current_ids = [item["news_id"] for item in normalized if item.get("news_id")]
        current_limit = detail_current_limit
        if current_limit is None:
            current_limit = len(normalized) or 50

        need_detail_current = self._backend.query_sa_market_news_need_detail(
            current_ids,
            detail_cache_hours=_SA_MARKET_NEWS_DETAIL_CACHE_HOURS,
            limit=current_limit,
        )
        need_detail_backfill = []
        if detail_backfill_limit:
            need_detail_backfill = self._backend.query_sa_market_news_need_detail(
                news_ids=None,
                detail_cache_hours=_SA_MARKET_NEWS_DETAIL_CACHE_HOURS,
                limit=detail_backfill_limit,
                exclude_news_ids=current_ids,
                published_within_hours=_SA_MARKET_NEWS_BACKFILL_PUBLISHED_WINDOW_HOURS,
            )
        need_detail = []
        seen = set()
        for bucket in (need_detail_current, need_detail_backfill):
            for item in bucket:
                news_id = item.get("news_id")
                if not news_id or news_id in seen:
                    continue
                seen.add(news_id)
                need_detail.append(item)
        return {
            "status": "ok",
            "saved": saved,
            "need_detail": need_detail,
            "need_detail_current": need_detail_current,
            "need_detail_backfill": need_detail_backfill,
        }

    def get_sa_market_news(
        self,
        ticker: str = None,
        keyword: str = None,
        limit: int = 20,
    ) -> List[Dict]:
        """Query recent Seeking Alpha market-news metadata."""
        return self._backend.query_sa_market_news(
            ticker=ticker, keyword=keyword, limit=limit
        )

    def get_sa_market_news_recent_ids(self, limit: int = 200) -> List[str]:
        """Return recent market-news IDs for duplicate-aware list scanning."""
        return self._backend.query_sa_market_news_recent_ids(limit=limit)

    def get_sa_market_news_recovery_rows(self, news_ids: List[str]) -> List[Dict]:
        """Return the exact, privacy-minimal rows used to freeze repair targets."""
        return self._backend.query_sa_market_news_recovery_rows(news_ids)

    def get_sa_market_news_body_presence(self, news_ids: List[str]) -> Dict[str, bool]:
        """Read body presence for frozen repair IDs without an age predicate."""
        return self._backend.query_sa_market_news_body_presence(news_ids)

    def get_sa_market_news_missing_detail_interval(
        self, start_at: str, end_at: str
    ) -> List[Dict]:
        """Return missing-detail rows in an inclusive recovery interval."""
        return self._backend.query_sa_market_news_missing_detail_interval(start_at, end_at)

    def save_sa_market_news_detail(self, news_id: str, body_markdown: str) -> bool:
        """Persist a single market-news body Markdown payload."""
        return self._backend.save_sa_market_news_detail(news_id, body_markdown)

    def invalidate_dirty_sa_market_news_detail(self) -> int:
        """Invalidate cached market-news body content that matches known noisy captures."""
        return self._backend.invalidate_dirty_sa_market_news_detail()

    # ── SA Articles + Comments ──

    def save_sa_articles_meta(
        self, articles: List[Dict], mode: str = "quick"
    ) -> Dict[str, Any]:
        """Batch upsert article metadata. Returns need_content + unresolved info.

        The current local capture store owns this operation.
        """
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

        # Normal capture work is bounded to the rows in this list scan. Historic
        # body-less rows are review/enrichment work, not an implicit backfill.
        all_articles = self._backend.query_sa_articles(limit=9999)
        scanned_article_ids = list(dict.fromkeys(
            a["article_id"]
            for a in normalized_articles
            if a.get("article_id")
        ))
        scanned_ids = set(scanned_article_ids)
        current_count_observations = {
            a["article_id"]: int(a.get("comments_count") or 0)
            for a in normalized_articles
            if a.get("article_id") and a.get("comments_count_observed_at")
        }
        articles_by_id = {
            a["article_id"]: a for a in all_articles if a.get("article_id")
        }

        def comment_work_item(a: Dict[str, Any]) -> Dict[str, Any]:
            item = {"article_id": a["article_id"], "url": a.get("url", "")}
            if a["article_id"] in scanned_ids:
                provider_count = current_count_observations.get(a["article_id"])
            elif a.get("comments_count_observed_at"):
                provider_count = _sanitize_sa_comments_count(
                    a.get("comments_count"), a.get("published_date")
                )
            else:
                provider_count = None
            if provider_count is not None:
                item["provider_comments_count"] = provider_count
            return item

        need_content = []
        for article_id in scanned_article_ids:
            article = articles_by_id.get(article_id)
            if article is not None and not article.get("has_content"):
                need_content.append(comment_work_item(article))

        # Determine need_comments
        need_comments = []
        need_content_ids = {a["article_id"] for a in need_content}
        need_comment_ids = set()

        for article_id in scanned_article_ids:
            article = articles_by_id.get(article_id)
            if (
                article is None
                or article_id in need_content_ids
                or not article.get("has_content")
                or article_id not in current_count_observations
            ):
                continue
            provider_count = current_count_observations[article_id]
            checkpoint = article.get("provider_comments_count_at_last_scan")
            count_changed = checkpoint is not None and provider_count != int(checkpoint)
            first_positive = checkpoint is None and provider_count > 0
            if count_changed or first_positive:
                need_comments.append(comment_work_item(article))
                need_comment_ids.add(article_id)

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
            recovery_candidates = []
            ttl_candidates = []
            for a in all_articles:
                if a["article_id"] in need_content_ids:
                    continue  # Mutual exclusion: need_content takes priority
                if a["article_id"] in need_comment_ids:
                    continue
                if not a.get("has_content"):
                    continue
                published = a.get("published_date")
                if hasattr(published, "isoformat"):
                    published_key = published.isoformat()
                elif published is None:
                    published_key = ""
                else:
                    published_key = str(published)
                order_key = (published_key, str(a["article_id"]))

                state = a.get("comment_recovery_state") or "repaired"
                if state == "pending":
                    if mode == "backfill" or not a.get("comment_recovery_parked_at"):
                        recovery_candidates.append((order_key, a))
                    continue
                if state == "unreachable_terminal":
                    continue

                fetched = a.get("comments_fetched_at")
                is_stale = fetched is None
                if fetched:
                    if isinstance(fetched, str):
                        fetched = datetime.fromisoformat(
                            fetched.replace("Z", "+00:00")
                        )
                    is_stale = fetched <= cutoff
                if is_stale:
                    provider_count = _sanitize_sa_comments_count(
                        a.get("comments_count"), a.get("published_date")
                    )
                    stored_count = int(a.get("stored_comments_count") or 0)
                    if provider_count <= 0 and stored_count <= 0:
                        continue
                    ttl_candidates.append((order_key, a))

            recovery_candidates.sort(key=lambda item: item[0], reverse=True)
            ttl_candidates.sort(key=lambda item: item[0], reverse=True)
            for _, a in (recovery_candidates + ttl_candidates)[:backfill_limit]:
                if a["article_id"] not in need_comment_ids:
                    need_comments.append(comment_work_item(a))
                    need_comment_ids.add(a["article_id"])

        # Unresolved symbols (current picks only, metadata-only matching)
        unresolved = self._compute_unresolved_symbols()

        try:
            reconciliation = self._backend.reconcile_sa_articles(
                article_ids=scanned_article_ids,
                max_events=100,
                enrichment_limit={"quick": 4, "full": 12, "backfill": 20}.get(
                    mode, 4
                ),
            )
        except Exception as exc:
            logger.warning(
                "SA article reconciliation failed after metadata capture: %s", exc
            )
            reconciliation = _failed_sa_reconciliation()

        return {
            "status": "ok",
            "saved": saved,
            "need_content": need_content,
            "need_comments": need_comments,
            "unresolved_symbols": unresolved,
            "auto_upgrade": False,
            "reconciliation": reconciliation,
        }

    def save_sa_article_with_comments(
        self,
        article_id: str,
        body_markdown: str,
        comments: List[Dict],
        *,
        detail_ticker: str | None = None,
        detail_ticker_observed_at=None,
        provider_comments_count=None,
        comment_scan_mode="quick",
        comment_scan_stop_reason=None,
        comment_scan_stable_bottom_rounds=0,
    ) -> Dict:
        """Capture body/comments first, then reconcile in a separate transaction."""
        captured = self._backend.save_article_with_comments(
            article_id,
            body_markdown,
            comments,
            detail_ticker=detail_ticker,
            detail_ticker_observed_at=detail_ticker_observed_at,
            provider_comments_count=provider_comments_count,
            comment_scan_mode=comment_scan_mode,
            comment_scan_stop_reason=comment_scan_stop_reason,
            comment_scan_stable_bottom_rounds=comment_scan_stable_bottom_rounds,
        )
        try:
            reconciliation = self._backend.reconcile_sa_articles(
                article_ids=[article_id],
                max_events=100,
                enrichment_limit=4,
            )
        except Exception as exc:
            logger.warning("SA article reconciliation failed after body capture: %s", exc)
            reconciliation = _failed_sa_reconciliation()
        return {**captured, "reconciliation": reconciliation}

    def save_sa_comments_only(
        self,
        article_id: str,
        comments: List[Dict],
        *,
        provider_comments_count=None,
        comment_scan_mode="quick",
        comment_scan_stop_reason=None,
        comment_scan_stable_bottom_rounds=0,
    ) -> Dict[str, Any]:
        """Update comments only (refresh run). Returns refresh stats."""
        return self._backend.update_article_comments(
            article_id,
            comments,
            provider_comments_count=provider_comments_count,
            comment_scan_mode=comment_scan_mode,
            comment_scan_stop_reason=comment_scan_stop_reason,
            comment_scan_stable_bottom_rounds=comment_scan_stable_bottom_rounds,
        )

    def audit_sa_unresolved_symbols(self) -> Dict:
        """Return the read-only reconciliation queue projection."""
        return self._backend.audit_unresolved_symbols()

    def reconcile_sa_articles(self, **kwargs) -> Dict[str, Any]:
        return self._backend.reconcile_sa_articles(**kwargs)

    def query_sa_article_review_queue(self, limit: int = 50) -> Dict[str, Any]:
        return self._backend.query_sa_article_review_queue(limit=limit)

    def resolve_sa_reconciliation_event(self, **kwargs) -> Dict[str, Any]:
        return self._backend.resolve_sa_reconciliation_event(**kwargs)

    def accept_sa_article_link(self, **kwargs) -> Dict[str, Any]:
        return self._backend.accept_sa_article_link(**kwargs)

    def reject_sa_article_candidate(self, **kwargs) -> Dict[str, Any]:
        return self._backend.reject_sa_article_candidate(**kwargs)

    def get_sa_articles(
        self,
        ticker: str = None,
        keyword: str = None,
        article_type: str = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Query SA articles with filters."""
        return self._backend.query_sa_articles(
            ticker=ticker, keyword=keyword, article_type=article_type, limit=limit
        )

    def get_sa_article_detail(self, article_id: str) -> Optional[Dict]:
        """Get full article content + comments."""
        return self._backend.get_sa_article_with_comments(article_id)

    def _compute_unresolved_symbols(self) -> List[str]:
        """Return symbols admitted by the current local reconciliation owner."""
        result = self._backend.audit_unresolved_symbols()
        return list(result.get("unresolved_symbols") or [])

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
