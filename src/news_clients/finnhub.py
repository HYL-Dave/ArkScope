"""Finnhub transport and article parsing for current news ingestion."""

import os
import json
import time
import hashlib
import logging
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class FinnhubConfig:
    """Finnhub 收集設定"""
    # Request pacing defaults
    request_delay: float = 1.0  # 1 second between requests
    requests_per_minute: int = 60

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 10.0


@dataclass
class NewsArticle:
    """新聞文章資料結構"""
    article_id: str
    ticker: str
    title: str
    published_at: str
    source_api: str = "finnhub"

    description: str = ""
    content: str = ""
    url: str = ""

    publisher: str = ""
    author: str = ""

    related_tickers: str = ""
    tags: str = ""
    category: str = ""

    source_sentiment: Optional[float] = None
    source_sentiment_label: str = ""

    collected_at: str = ""
    content_length: int = 0
    dedup_hash: str = ""


class FinnhubRateLimiter:
    """Configured request spacing and per-minute budget."""

    def __init__(self, config: FinnhubConfig):
        self.config = config
        self._last_request_time = 0
        self._request_count = 0
        self._minute_start = time.time()

    def wait(self):
        """Wait to respect rate limits."""
        current_time = time.time()

        # Reset counter every minute
        if current_time - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = current_time

        # If we've hit the limit, wait
        if self._request_count >= self.config.requests_per_minute:
            wait_time = 60 - (current_time - self._minute_start)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                self._request_count = 0
                self._minute_start = time.time()

        # Minimum delay between requests
        elapsed = current_time - self._last_request_time
        if elapsed < self.config.request_delay:
            time.sleep(self.config.request_delay - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1


class FinnhubNewsCollector:
    """Finnhub 新聞收集器"""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str, config: FinnhubConfig):
        self.api_key = api_key
        self.config = config
        self.session = requests.Session()
        self.rate_limiter = FinnhubRateLimiter(config)

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_requests': 0,
            'errors': 0,
            'by_source': {},
        }

    def fetch_news(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> List[dict]:
        """Fetch news for a ticker."""
        self.rate_limiter.wait()
        self.stats['total_requests'] += 1

        params = {
            'symbol': ticker,
            'from': start_date.isoformat(),
            'to': end_date.isoformat(),
            'token': self.api_key,
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/company-news",
                params=params,
                timeout=30
            )

            if response.status_code == 429:
                logger.warning("Rate limit hit (429), waiting 60s...")
                time.sleep(60)
                return self.fetch_news(ticker, start_date, end_date)

            if response.status_code != 200:
                logger.error(f"API error {response.status_code}: {response.text[:200]}")
                self.stats['errors'] += 1
                return []

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            self.stats['errors'] += 1
            return []

    def parse_article(self, raw: dict, ticker: str, collected_at: datetime) -> Optional[NewsArticle]:
        """Parse raw API response to NewsArticle.

        Returns None for Yahoo summaries matching the retained truncation filter.
        """

        # Parse timestamp (Finnhub uses Unix timestamp)
        timestamp = raw.get('datetime', 0)
        if timestamp:
            pub_dt = datetime.fromtimestamp(timestamp, timezone.utc)
            published_at = pub_dt.isoformat().replace('+00:00', 'Z')
        else:
            published_at = ''

        # Get content
        headline = raw.get('headline', '')
        summary = raw.get('summary', '')
        content = summary
        content_length = len(content)

        # Publisher (source field)
        publisher = raw.get('source', '')

        # Preserve the existing provider-summary truncation filter.
        if publisher == 'Yahoo' and content_length in [100, 500]:
            self.stats['skipped_truncated'] = self.stats.get('skipped_truncated', 0) + 1
            return None

        # Track by source (only for kept articles)
        if publisher:
            self.stats['by_source'][publisher] = self.stats['by_source'].get(publisher, 0) + 1

        # Generate dedup hash
        pub_date = published_at[:10] if published_at else ''
        hash_input = f"{ticker.upper()}|{headline.strip().lower()}|{pub_date}"
        dedup_hash = hashlib.md5(hash_input.encode()).hexdigest()

        # Article ID
        article_id = str(raw.get('id', dedup_hash))

        return NewsArticle(
            article_id=article_id,
            ticker=ticker,
            title=headline,
            published_at=published_at,
            source_api="finnhub",
            description=summary,
            content=content,
            url=raw.get('url', ''),
            publisher=publisher,
            author='',
            related_tickers=json.dumps(raw.get('related', []) or [ticker]),
            tags=json.dumps(raw.get('category', '').split(',') if raw.get('category') else []),
            category=raw.get('category', ''),
            source_sentiment=None,  # Finnhub doesn't provide sentiment
            source_sentiment_label='',
            collected_at=collected_at.isoformat(),
            content_length=content_length,
            dedup_hash=dedup_hash,
        )


def load_env() -> str:
    """Resolve the Finnhub API key, os.environ FIRST.

    The sidecar's apply_env() injects DB-managed provider values into os.environ
    (precedence real env > app-DB > config/.env), so os.environ is the resolved
    source and reading it first keeps news collection consistent with the Settings
    "test connection" button (which uses os.getenv). Falls back to reading
    config/.env directly for standalone runs that never went through the env bridge.
    A placeholder ('your_'-prefixed) or empty value is rejected at each layer so a
    stub never shadows a real key."""
    env_val = os.environ.get('FINNHUB_API_KEY', '').strip()
    if env_val and not env_val.startswith('your_'):
        return env_val

    env_paths = [
        Path("config/.env"),
        Path(".env"),
    ]
    for path in env_paths:
        if path.exists():
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        # unquote: strip quotes first, then whitespace (mirrors src.env_keys.unquote_env_value)
                        value = value.strip()
                        while len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                            value = value[1:-1].strip()
                        if key == 'FINNHUB_API_KEY' and value and not value.startswith('your_'):
                            return value
    return ''
