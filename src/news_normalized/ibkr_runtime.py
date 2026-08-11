"""Runtime IBKR gateway adapter for isolated normalized-news workers."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re
from typing import Any, Optional

from .ibkr_adapter import IBKRHeadline


_ARTICLE_ID_RE = re.compile(r"^\[Article ID:\s*([^\]\s]+)\]$")
_BOOTSTRAP_LOOKBACK = timedelta(days=7)


class IBKRNewsCoverageIncomplete(RuntimeError):
    """The provider page could not prove coverage back to the local cursor."""

    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(error_code)


def _iso_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None:
            return f"{parsed.isoformat()}Z"
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value or "")


def _date_from_cursor(since_iso: Optional[str]) -> Optional[date]:
    if not since_iso:
        return None
    value = since_iso.strip()
    parseable = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(parseable).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _datetime_from_value(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(parseable)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def extract_provider_article_id(description: str, provider_code: str) -> str:
    """Extract and validate the IBKR provider article ID from the headline marker."""
    provider = (provider_code or "").strip()
    match = _ARTICLE_ID_RE.match(description or "")
    if not provider or not match:
        raise ValueError("malformed IBKR article ID")
    article_id = match.group(1).strip()
    if not article_id.startswith(f"{provider}$") or len(article_id) <= len(provider) + 1:
        raise ValueError("malformed IBKR article ID")
    return article_id


class IBKRRuntimeGateway:
    """Small adapter around one ``IBKRDataSource`` with deterministic cleanup."""

    def __init__(self, source):
        self.source = source
        self._provider_codes: frozenset[str] | None = None
        self._headline_pages_requested = 0
        self._headline_saturated_tickers = 0
        self._headline_incomplete_tickers = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self) -> None:
        disconnect = getattr(self.source, "disconnect", None)
        if callable(disconnect):
            disconnect()

    def discover_news_provider_codes(self) -> frozenset[str]:
        rows = self.source.get_news_providers_strict()
        self._provider_codes = frozenset(
            code
            for row in rows
            if (code := str(row.get("code", "")).strip().upper())
        )
        return self._provider_codes

    def headline_coverage_counts(self) -> dict[str, int]:
        return {
            "headline_pages_requested": self._headline_pages_requested,
            "headline_saturated_tickers": self._headline_saturated_tickers,
            "headline_incomplete_tickers": self._headline_incomplete_tickers,
        }

    def fetch_headlines(self, ticker: str, since_iso: Optional[str]):
        start_date = _date_from_cursor(since_iso)
        coverage_start: Optional[datetime] = None
        if self._provider_codes == frozenset():
            articles = []
            has_more: bool | None = False
        elif callable(getattr(self.source, "fetch_news_page_strict", None)):
            now = datetime.now(timezone.utc)
            coverage_start = _datetime_from_value(since_iso) or (
                now - _BOOTSTRAP_LOOKBACK
            )
            self._headline_pages_requested += 1
            page = self.source.fetch_news_page_strict(
                ticker,
                start_dt=coverage_start,
                end_dt=now,
                providers=(
                    "+".join(sorted(self._provider_codes))
                    if self._provider_codes is not None
                    else None
                ),
            )
            articles = page.articles
            has_more = page.has_more
            if has_more is True:
                self._headline_saturated_tickers += 1
        else:
            kwargs = {
                "start_date": start_date,
                "end_date": date.today(),
            }
            if self._provider_codes is not None:
                kwargs["providers"] = "+".join(sorted(self._provider_codes))
            articles = self.source.fetch_news([ticker], **kwargs)
            has_more = False
        for article in articles or ():
            provider_code = str(getattr(article, "source", "") or "").strip()
            provider_id = extract_provider_article_id(
                str(getattr(article, "description", "") or ""),
                provider_code,
            )
            observed_ticker = str(getattr(article, "ticker", "") or ticker).strip().upper()
            yield IBKRHeadline(
                article_id=provider_id,
                provider_code=provider_code,
                title=str(getattr(article, "title", "") or ""),
                published_at=_iso_timestamp(getattr(article, "published_date", "")),
                observed_at=datetime.now(timezone.utc).isoformat(),
                ticker=observed_ticker or ticker,
            )

        if has_more is None:
            self._headline_incomplete_tickers += 1
            raise IBKRNewsCoverageIncomplete(
                "ibkr_news_completion_unknown"
            )
        if has_more:
            published = tuple(
                parsed
                for article in articles or ()
                if (parsed := _datetime_from_value(
                    getattr(article, "published_date", None)
                )) is not None
            )
            if (
                coverage_start is None
                or not published
                or min(published) > coverage_start
            ):
                self._headline_incomplete_tickers += 1
                raise IBKRNewsCoverageIncomplete(
                    "ibkr_news_window_incomplete"
                )

    def fetch_news_article_body_strict(
        self, provider_code: str, article_id: str
    ) -> Optional[str]:
        extract_provider_article_id(f"[Article ID: {article_id}]", provider_code)
        return self.source.fetch_news_article_body_strict(provider_code, article_id)
