"""Parquet-free news provider adapters and shared toggle parsing.

The direct-local writer (`news_direct.backfill_news_direct`) wants a provider with
``fetch_news(ticker, since_iso) -> list[raw article dict]``. These adapters wrap the EXISTING
clients' fetch+parse (``PolygonNewsCollector.fetch_news_range`` /
``FinnhubNewsCollector.fetch_news`` + ``parse_article``). The writer owns storage
and per-source/ticker SQLite cursors; clients do not write Parquet or keep cursors.

The collector ``NewsArticle`` is mapped to the local news-row contract using the canonical SHA-256
identity used by the local store; ``description`` falls back to ``content``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from src import news_collection_policy
from src.news_identity import canonical_article_hash

_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")


def parse_news_toggle(value: Any) -> Optional[bool]:
    text = str(value).strip().lower() if value is not None else ""
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return None


def _article_to_raw(article: Any) -> Dict[str, Any]:
    """Collector ``NewsArticle`` (duck-typed) → the raw dict ``backfill_news_direct`` expects.
    ``article_hash`` = the shared canonical SHA-256; ``description`` falls back to ``content``."""
    return {
        "ticker": article.ticker,
        "title": article.title,
        "description": getattr(article, "description", "") or getattr(article, "content", "") or "",
        "url": getattr(article, "url", "") or "",
        "publisher": getattr(article, "publisher", "") or "",
        "published_at": article.published_at,
        "article_hash": canonical_article_hash(
            article.ticker, article.title, article.published_at),
    }


def _since_to_start(since_iso: Optional[str], today: date) -> date:
    """Local cursor (newest stored published_at, exact-inclusive) → fetch start date. The boundary
    day is re-fetched and dropped by article_hash dedup. No cursor → a default lookback window."""
    if since_iso and len(since_iso) >= 10:
        try:
            return date.fromisoformat(since_iso[:10])
        except ValueError:
            pass
    return today - news_collection_policy.INITIAL_NEWS_LOOKBACK


class _CollectorNewsProvider:
    """``fetch_news(ticker, since_iso) -> [raw dict]`` via a collector's fetch+parse (no Parquet)."""

    def __init__(self, source: str, collector: Any):
        self.source = source
        self._c = collector

    def fetch_news(self, ticker: str, since_iso: Optional[str] = None) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        start = _since_to_start(since_iso, now.date())
        if self.source == "polygon":
            raw = self._c.fetch_news_range(ticker, start, now.date())
            parsed = (self._c.parse_article(r, now) for r in raw)
        else:  # finnhub — parse_article takes the ticker and may return None (truncated articles)
            raw = self._c.fetch_news(ticker, start, now.date())
            parsed = (self._c.parse_article(r, ticker, now) for r in raw)
        return [_article_to_raw(a) for a in parsed if a is not None]


def make_news_provider(source: str, collector: Any = None) -> _CollectorNewsProvider:
    """Direct-local provider for ``'polygon'`` | ``'finnhub'``. ``collector`` is injectable for
    tests; otherwise the real client is built lazily using its credential authority."""
    if collector is None:
        if source == "polygon":
            from src.news_clients.polygon import (
                CollectionConfig, PolygonNewsCollector, load_env)
            collector = PolygonNewsCollector(load_env(), CollectionConfig())
        elif source == "finnhub":
            from src.news_clients.finnhub import (
                FinnhubConfig, FinnhubNewsCollector, load_env)
            collector = FinnhubNewsCollector(load_env(), FinnhubConfig())
        else:
            raise ValueError(f"unknown news source: {source!r}")
    return _CollectorNewsProvider(source, collector)
