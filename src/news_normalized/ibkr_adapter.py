"""IBKR headline/body adapter for the bounded normalized-news writer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Iterable, Optional, Protocol

from src.ibkr_gateway_lock import ibkr_gateway_lock

from .models import ArticleCandidate, BodyCandidate, BodyStatus


_HTML_TAG = re.compile(r"<\s*[A-Za-z][^>]*>")


@dataclass(frozen=True)
class IBKRHeadline:
    article_id: str
    provider_code: str
    title: str
    published_at: str
    observed_at: Optional[str] = None
    ticker: Optional[str] = None


class IBKRNewsGateway(Protocol):
    def fetch_headlines(
        self, ticker: str, since_iso: Optional[str]
    ) -> Iterable[IBKRHeadline]: ...

    def fetch_news_article_body_strict(
        self, provider_code: str, article_id: str
    ) -> Optional[str]: ...


class IBKRNormalizedProvider:
    source = "ibkr"

    def __init__(self, gateway: IBKRNewsGateway):
        self.gateway = gateway
        self._body_cache: dict[tuple[str, str], BodyCandidate] = {}

    def operation(self):
        return ibkr_gateway_lock()

    def fetch_articles(
        self, ticker: str, since_iso: Optional[str]
    ) -> Iterable[ArticleCandidate]:
        for headline in self.gateway.fetch_headlines(ticker, since_iso):
            observed_ticker = (headline.ticker or ticker).strip().upper()
            yield ArticleCandidate(
                source=self.source,
                provider_article_id=headline.article_id,
                title=headline.title,
                publisher=headline.provider_code,
                published_at=headline.published_at,
                primary_ticker=None,
                related_tickers=(observed_ticker,) if observed_ticker else (),
                observed_at=headline.observed_at,
                content_kind="headline_only",
                body=BodyCandidate(status=BodyStatus.PENDING),
            )

    def fetch_body(self, candidate: ArticleCandidate) -> BodyCandidate:
        article_id = (candidate.provider_article_id or "").strip()
        if not article_id:
            return BodyCandidate(
                status=BodyStatus.FAILED,
                error="IBKR body fetch requires provider article ID",
                retrieval_method="provider_api",
                retrieval_source=self.source,
            )
        provider_code = (candidate.publisher or "").strip()
        if not provider_code and "$" in article_id:
            provider_code = article_id.split("$", 1)[0]
        if not provider_code:
            return BodyCandidate(
                status=BodyStatus.FAILED,
                error="IBKR body fetch requires provider code",
                retrieval_method="provider_api",
                retrieval_source=self.source,
            )
        key = (provider_code, article_id)
        cached = self._body_cache.get(key)
        if cached is not None:
            return cached
        try:
            raw = self.gateway.fetch_news_article_body_strict(
                provider_code, article_id
            )
        except Exception as exc:
            return BodyCandidate(
                status=BodyStatus.FAILED,
                error=str(exc),
                retrieval_method="provider_api",
                retrieval_source=self.source,
            )

        text = str(raw) if raw is not None else ""
        if text.strip():
            body = BodyCandidate(
                status=BodyStatus.FETCHED,
                raw_body=text,
                raw_format="html" if _HTML_TAG.search(text) else "text",
                retrieval_method="provider_api",
                retrieval_source=self.source,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            body = BodyCandidate(
                status=BodyStatus.EMPTY,
                retrieval_method="provider_api",
                retrieval_source=self.source,
            )
        self._body_cache[key] = body
        return body
