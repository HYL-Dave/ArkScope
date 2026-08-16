"""Structurally typed capabilities used by the current local data runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

import pandas as pd

from src.news_content_availability import ContentFilter


class LocalDataCapabilities(Protocol):
    def accept_sa_article_link(self, **kwargs) -> dict: ...

    def apply_sa_refresh(
        self, scope: str, picks: list, attempt_ts: Any, snapshot_ts: Any
    ) -> int: ...

    def audit_unresolved_symbols(self) -> dict: ...

    def get_available_tickers(self, data_type: str) -> List[str]: ...

    def get_sa_article_with_comments(self, article_id: str) -> dict: ...

    def get_sa_pick_detail(
        self, symbol: str, picked_date: Optional[str] = None
    ) -> Optional[dict]: ...

    def get_sa_refresh_meta(self) -> dict: ...

    def invalidate_dirty_sa_market_news_detail(self) -> int: ...

    def query_fundamentals(self, ticker: str) -> dict: ...

    def query_health_stats(self) -> dict: ...

    def query_news(
        self, ticker: Optional[str] = None, days: int = 30, source: str = "auto"
    ) -> pd.DataFrame: ...

    def query_news_feed(
        self,
        q: Optional[str] = None,
        ticker: Optional[str] = None,
        source: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
        offset: int = 0,
        content: ContentFilter = "all",
    ) -> dict: ...

    def query_news_search(
        self,
        query: str = "",
        ticker: Optional[str] = None,
        days: int = 30,
        limit: int = 20,
    ) -> pd.DataFrame: ...

    def query_news_stats(
        self, ticker: Optional[str] = None, days: int = 30
    ) -> pd.DataFrame: ...

    def query_prices(
        self, ticker: str, interval: str = "15min", days: int = 30
    ) -> pd.DataFrame: ...

    def query_sa_article_review_queue(self, limit: int = 50) -> dict: ...

    def query_sa_articles(
        self,
        ticker: Optional[str] = None,
        keyword: Optional[str] = None,
        article_type: Optional[str] = None,
        limit: int = 10,
    ) -> list: ...

    def query_sa_market_news(
        self,
        ticker: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> list: ...

    def query_sa_market_news_body_presence(
        self, news_ids: list[str]
    ) -> dict[str, bool]: ...

    def query_sa_market_news_missing_detail_interval(
        self, start_at: str, end_at: str
    ) -> list[dict]: ...

    def query_sa_market_news_need_detail(
        self,
        news_ids: Optional[list] = None,
        detail_cache_hours: int = 24,
        limit: int = 50,
        exclude_news_ids: Optional[list] = None,
        published_within_hours: Optional[int] = None,
    ) -> list: ...

    def query_sa_market_news_recent_ids(self, limit: int = 200) -> list[str]: ...

    def query_sa_market_news_recovery_rows(
        self, news_ids: list[str]
    ) -> list[dict]: ...

    def query_sa_picks(
        self,
        portfolio_status: Optional[str] = None,
        symbol: Optional[str] = None,
        include_stale: bool = False,
    ) -> list: ...

    def query_sec_filings(
        self, ticker: str, filing_types: Optional[List[str]] = None
    ) -> pd.DataFrame: ...

    def reconcile_sa_articles(
        self,
        *,
        pick_keys: Optional[list] = None,
        article_ids: Optional[list] = None,
        max_events: int = 100,
        enrichment_limit: int = 4,
    ) -> dict: ...

    def record_sa_refresh_failure(
        self, scope: str, attempt_ts: Any, error: str
    ) -> None: ...

    def reject_sa_article_candidate(self, **kwargs) -> dict: ...

    def resolve_sa_reconciliation_event(
        self, *, symbol: str, role: str, event_anchor_date: str
    ) -> dict: ...

    def sanitize_corrupted_sa_comments_counts(self) -> int: ...

    def save_article_with_comments(
        self,
        article_id: str,
        body_markdown: str,
        comments: list,
        *,
        detail_ticker: Optional[str] = None,
        detail_ticker_observed_at: Any = None,
        provider_comments_count: Any = None,
        comment_scan_mode: str = "quick",
        comment_scan_stop_reason: Optional[str] = None,
        comment_scan_stable_bottom_rounds: int = 0,
    ) -> dict: ...

    def save_sa_market_news_detail(
        self, news_id: str, body_markdown: str
    ) -> bool: ...

    def update_article_comments(
        self,
        article_id: str,
        comments: list,
        *,
        provider_comments_count: Any = None,
        comment_scan_mode: str = "quick",
        comment_scan_stop_reason: Optional[str] = None,
        comment_scan_stable_bottom_rounds: int = 0,
    ) -> Dict[str, Any]: ...

    def update_sa_pick_detail(
        self, symbol: str, picked_date: str, content: str
    ) -> bool: ...

    def upsert_sa_articles_meta(self, articles: list) -> int: ...

    def upsert_sa_market_news(self, items: list) -> int: ...
