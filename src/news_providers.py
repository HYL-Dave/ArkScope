"""PG-exit 2c — Parquet-free news provider adapters + the use_local_news routing toggle.

The direct-local writer (`news_direct.backfill_news_direct`) wants a provider with
``fetch_news(ticker, since_iso) -> list[raw article dict]``. These adapters wrap the EXISTING
collectors' fetch+parse (``PolygonNewsCollector.fetch_news_range`` / ``FinnhubNewsCollector.fetch_news``
+ ``parse_article``) but DELIBERATELY never call ``StorageManager.save_articles`` — so the direct
path writes only the local SQLite ``news`` table, no Parquet, and is cursored against the local DB
(``backfill_news_direct`` passes the local newest-published_at as ``since_iso``), not the Parquet
``get_latest_timestamp``.

The collector ``NewsArticle`` is mapped to the local news-row contract using the canonical SHA-256
identity shared with the PG/mirror migration; ``description`` falls back to ``content``. Also here:
``use_local_news_enabled()`` — the default-ON routing toggle with explicit env/profile rollback,
read standalone (no DAL) so the scheduler can consult it per source-run.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.news_identity import canonical_article_hash

USE_LOCAL_NEWS_KEY = "use_local_news"
ENV_USE_LOCAL_NEWS = "ARKSCOPE_USE_LOCAL_NEWS"

_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")
_DEFAULT_LOOKBACK_DAYS = 7   # first run (no local cursor for this source/ticker) → look back a week


def _default_profile_db() -> str:
    return str(Path(__file__).resolve().parents[1] / "data" / "profile_state.db")


def parse_news_toggle(value: Any) -> Optional[bool]:
    text = str(value).strip().lower() if value is not None else ""
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return None


def resolve_use_local_news(profile_value: Any, env_value: Any = None) -> bool:
    """Resolve routing as explicit env > explicit profile > default ON."""
    env = parse_news_toggle(env_value)
    if env is not None:
        return env
    profile = parse_news_toggle(profile_value)
    return profile if profile is not None else True


def use_local_news_enabled() -> bool:
    """Whether Polygon/Finnhub news ingest routes to the direct-local writer.

    Both true and false are explicit overrides. Unset defaults ON; setting either
    ``ARKSCOPE_USE_LOCAL_NEWS=false`` or profile ``use_local_news=false`` restores
    the collector -> PG sync -> local mirror path.
    """
    env_value = os.environ.get(ENV_USE_LOCAL_NEWS)
    if parse_news_toggle(env_value) is not None:
        return resolve_use_local_news(None, env_value)
    db = os.environ.get("ARKSCOPE_PROFILE_DB") or _default_profile_db()
    if not db or not Path(db).exists():
        return True
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT value FROM profile_settings WHERE key = ?", (USE_LOCAL_NEWS_KEY,)
            ).fetchone()
        finally:
            conn.close()
        return resolve_use_local_news(row[0] if row else None)
    except sqlite3.OperationalError:
        return True


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
