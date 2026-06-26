"""PG-exit 2c — Parquet-free news provider adapters + the use_local_news routing toggle.

The direct-local writer (`news_direct.backfill_news_direct`) wants a provider with
``fetch_news(ticker, since_iso) -> list[raw article dict]``. These adapters wrap the EXISTING
collectors' fetch+parse (``PolygonNewsCollector.fetch_news_range`` / ``FinnhubNewsCollector.fetch_news``
+ ``parse_article``) but DELIBERATELY never call ``StorageManager.save_articles`` — so the direct
path writes only the local SQLite ``news`` table, no Parquet, and is cursored against the local DB
(``backfill_news_direct`` passes the local newest-published_at as ``since_iso``), not the Parquet
``get_latest_timestamp``.

The collector ``NewsArticle`` is mapped to the local news-row contract:
``article_hash = dedup_hash`` (the collector's MD5 identity) and ``description`` falls back to
``content``. Also here: ``use_local_news_enabled()`` — the default-OFF routing toggle, read
standalone (no DAL) so the scheduler can consult it per source-run.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_TRUTHY = ("1", "true", "yes", "on")
_DEFAULT_LOOKBACK_DAYS = 7   # first run (no local cursor for this source/ticker) → look back a week


def _default_profile_db() -> str:
    return str(Path(__file__).resolve().parents[1] / "data" / "profile_state.db")


def use_local_news_enabled() -> bool:
    """Whether news ingest routes to the direct-local writer (2c toggle, default-OFF).

    Env override (``ARKSCOPE_USE_LOCAL_NEWS``) OR the persisted ``profile_settings.use_local_news``
    key, read-only — standalone (the scheduler reads it per source-run without constructing a DAL).
    Mirrors the DAL's ``_profile_setting_truthy`` semantics; default OFF keeps the current
    collector→Parquet→PG sync→local mirror path."""
    if os.environ.get("ARKSCOPE_USE_LOCAL_NEWS", "").strip().lower() in _TRUTHY:
        return True
    db = os.environ.get("ARKSCOPE_PROFILE_DB") or _default_profile_db()
    if not db or not Path(db).exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT value FROM profile_settings WHERE key = 'use_local_news'").fetchone()
        finally:
            conn.close()
        return bool(row) and str(row[0]).strip().lower() in _TRUTHY
    except sqlite3.OperationalError:
        return False


def _article_to_raw(article: Any) -> Dict[str, Any]:
    """Collector ``NewsArticle`` (duck-typed) → the raw dict ``backfill_news_direct`` expects.
    ``article_hash`` = the collector's ``dedup_hash``; ``description`` falls back to ``content``."""
    return {
        "ticker": article.ticker,
        "title": article.title,
        "description": getattr(article, "description", "") or getattr(article, "content", "") or "",
        "url": getattr(article, "url", "") or "",
        "publisher": getattr(article, "publisher", "") or "",
        "published_at": article.published_at,
        "article_hash": article.dedup_hash,
    }


def _since_to_start(since_iso: Optional[str], today: date) -> date:
    """Local cursor (newest stored published_at, exact-inclusive) → fetch start date. The boundary
    day is re-fetched and dropped by article_hash dedup. No cursor → a default lookback window."""
    if since_iso and len(since_iso) >= 10:
        try:
            return date.fromisoformat(since_iso[:10])
        except ValueError:
            pass
    return today - timedelta(days=_DEFAULT_LOOKBACK_DAYS)


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
    tests; otherwise the real collector is built lazily (needs the provider API key in config/.env)."""
    if collector is None:
        if source == "polygon":
            from scripts.collection.collect_polygon_news import (
                CollectionConfig, PolygonNewsCollector, load_env)
            collector = PolygonNewsCollector(load_env(), CollectionConfig())
        elif source == "finnhub":
            from scripts.collection.collect_finnhub_news import (
                FinnhubConfig, FinnhubNewsCollector, load_env)
            collector = FinnhubNewsCollector(load_env(), FinnhubConfig())
        else:
            raise ValueError(f"unknown news source: {source!r}")
    return _CollectorNewsProvider(source, collector)
