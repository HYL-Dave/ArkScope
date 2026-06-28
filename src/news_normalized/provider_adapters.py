"""Parquet-free Polygon and Finnhub adapters for the normalized writer."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
import json
import re
from typing import Any, Callable, Iterable, Optional

from .models import ArticleCandidate, BodyCandidate, BodyStatus


_DEFAULT_LOOKBACK_DAYS = 7
_HTML_TAG = re.compile(r"<\s*[A-Za-z][^>]*>")


def _related_tickers(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return ()
    if not isinstance(value, (list, tuple, set)):
        return ()
    normalized = (
        str(item).strip().upper() for item in value if str(item).strip()
    )
    return tuple(dict.fromkeys(normalized))


def _raw_format(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return "html" if _HTML_TAG.search(raw) else "text"


def collector_article_to_candidate(source: str, article: Any) -> ArticleCandidate:
    """Map the existing collector dataclass without treating REST summaries as full text."""
    source = source.strip().casefold()
    if source not in {"polygon", "finnhub"}:
        raise ValueError(f"unsupported normalized REST news source: {source!r}")
    content = str(getattr(article, "content", "") or "")
    description = str(getattr(article, "description", "") or "")
    raw = content if content.strip() else (description if description.strip() else None)
    observed_at = (getattr(article, "collected_at", "") or "").strip() or None
    url = (getattr(article, "url", "") or "").strip()
    provider_id = str(getattr(article, "article_id", "") or "").strip() or None
    body = BodyCandidate(
        status=BodyStatus.FETCHED if raw else BodyStatus.EMPTY,
        raw_body=raw,
        raw_format=_raw_format(raw),
        retrieval_method="provider_payload",
        retrieval_source=source,
        source_url=url or None,
        fetched_at=observed_at if raw else None,
    )
    return ArticleCandidate(
        source=source,
        provider_article_id=provider_id,
        title=str(getattr(article, "title", "") or ""),
        publisher=str(getattr(article, "publisher", "") or ""),
        url=url,
        published_at=str(getattr(article, "published_at", "") or ""),
        primary_ticker=str(getattr(article, "ticker", "") or "").strip().upper()
        or None,
        related_tickers=_related_tickers(
            getattr(article, "related_tickers", ())
        ),
        observed_at=observed_at,
        content_kind="summary" if raw else "headline_only",
        body=body,
    )


def _cursor_bounds(
    since_iso: Optional[str], today: date
) -> tuple[date, Optional[datetime]]:
    if since_iso:
        value = since_iso.strip()
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.date(), parsed
        except ValueError:
            try:
                return date.fromisoformat(value[:10]), None
            except ValueError:
                pass
    return today - timedelta(days=_DEFAULT_LOOKBACK_DAYS), None


class _NormalizedRestProvider:
    source: str

    def __init__(
        self,
        collector: Any,
        *,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.collector = collector
        self._now_fn = now_fn

    def operation(self):
        return nullcontext()

    def fetch_body(self, candidate: ArticleCandidate) -> BodyCandidate:
        if candidate.body.status is BodyStatus.FETCHED:
            return candidate.body
        return BodyCandidate(
            status=BodyStatus.EMPTY,
            retrieval_method="provider_payload",
            retrieval_source=self.source,
            source_url=candidate.url or None,
        )


class PolygonNormalizedProvider(_NormalizedRestProvider):
    source = "polygon"

    def fetch_articles(
        self, ticker: str, since_iso: Optional[str]
    ) -> Iterable[ArticleCandidate]:
        now = self._now_fn()
        start, start_timestamp = _cursor_bounds(since_iso, now.date())
        raw_rows = self.collector.fetch_news_range(
            ticker,
            start,
            now.date(),
            start_timestamp=start_timestamp,
        )
        for raw in raw_rows or ():
            parsed = self.collector.parse_article(raw, now)
            if parsed is not None:
                yield collector_article_to_candidate(self.source, parsed)


class FinnhubNormalizedProvider(_NormalizedRestProvider):
    source = "finnhub"

    def fetch_articles(
        self, ticker: str, since_iso: Optional[str]
    ) -> Iterable[ArticleCandidate]:
        now = self._now_fn()
        start, _ = _cursor_bounds(since_iso, now.date())
        raw_rows = self.collector.fetch_news(ticker, start, now.date())
        for raw in raw_rows or ():
            parsed = self.collector.parse_article(raw, ticker, now)
            if parsed is not None:
                yield collector_article_to_candidate(self.source, parsed)
