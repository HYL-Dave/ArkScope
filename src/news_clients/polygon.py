"""Massive transport and article parsing for current news ingestion."""

import os
import json
import time
import hashlib
import logging
from datetime import datetime, date
from typing import List, Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class CollectionConfig:
    """收集設定"""
    # Request pacing defaults
    request_delay: float = 12.0  # 12 seconds between requests
    requests_per_minute: int = 5

    # Pagination
    articles_per_request: int = 1000  # Maximum allowed by Massive

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 30.0


@dataclass
class NewsArticle:
    """新聞文章資料結構"""
    article_id: str
    ticker: str
    title: str
    published_at: str  # ISO format
    source_api: str = "polygon"

    description: str = ""
    content: str = ""
    url: str = ""

    publisher: str = ""
    author: str = ""

    related_tickers: str = ""  # JSON string list
    tags: str = ""  # JSON string list
    category: str = ""

    source_sentiment: Optional[float] = None
    source_sentiment_label: str = ""

    collected_at: str = ""
    content_length: int = 0
    dedup_hash: str = ""


class RateLimiter:
    """Configured request spacing and per-minute budget."""

    def __init__(self, config: CollectionConfig):
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

        # Ensure minimum delay between requests
        elapsed = current_time - self._last_request_time
        if elapsed < self.config.request_delay:
            sleep_time = self.config.request_delay - elapsed
            time.sleep(sleep_time)

        self._last_request_time = time.time()
        self._request_count += 1


class PolygonNewsCollector:
    """Massive API client with the durable polygon source identity."""

    BASE_URL = "https://api.massive.com"

    def __init__(self, api_key: str, config: CollectionConfig):
        self.api_key = api_key
        self.config = config
        self.session = requests.Session()
        self.rate_limiter = RateLimiter(config)

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_requests': 0,
            'errors': 0,
            'duplicates': 0,
        }

    def fetch_news_range(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        start_timestamp: Optional[datetime] = None,
    ) -> List[dict]:
        """
        Fetch all news for a ticker in a date range.
        Handles pagination automatically.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for the range
            end_date: End date for the range
            start_timestamp: Optional precise start timestamp (for incremental updates)
        """
        all_articles = []

        # Use precise timestamp if provided, otherwise use date
        if start_timestamp:
            # Format: 2024-01-15T14:30:00Z (ISO 8601)
            start_str = start_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            start_str = start_date.isoformat()

        params = {
            'ticker': ticker,
            'published_utc.gte': start_str,
            'published_utc.lte': f"{end_date.isoformat()}T23:59:59Z",
            'limit': self.config.articles_per_request,
            'sort': 'published_utc',
            'order': 'asc',
            'apiKey': self.api_key,
        }

        url = f"{self.BASE_URL}/v2/reference/news"

        while True:
            self.rate_limiter.wait()
            self.stats['total_requests'] += 1

            try:
                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 429:
                    logger.warning("Rate limit hit (429), waiting 60s...")
                    time.sleep(60)
                    continue

                if response.status_code != 200:
                    logger.error(f"API error {response.status_code}: {response.text[:200]}")
                    self.stats['errors'] += 1
                    break

                data = response.json()
                results = data.get('results', [])
                all_articles.extend(results)

                logger.debug(f"  Fetched {len(results)} articles (total: {len(all_articles)})")

                # Check for pagination
                next_url = data.get('next_url')
                if not next_url:
                    break

                # Use next_url directly (it includes cursor)
                url = next_url
                params = {'apiKey': self.api_key}

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                self.stats['errors'] += 1

                # Retry logic
                for retry in range(self.config.max_retries):
                    logger.info(f"Retrying in {self.config.retry_delay}s... ({retry + 1}/{self.config.max_retries})")
                    time.sleep(self.config.retry_delay)
                    try:
                        response = self.session.get(url, params=params, timeout=30)
                        if response.status_code == 200:
                            break
                    except:
                        pass
                else:
                    logger.error("Max retries exceeded, skipping...")
                    break

        return all_articles

    def parse_article(self, raw: dict, collected_at: datetime) -> NewsArticle:
        """Parse raw API response to NewsArticle."""

        # Parse published date
        pub_str = raw.get('published_utc', '')

        # Get tickers
        tickers = raw.get('tickers', [])
        primary_ticker = tickers[0] if tickers else 'UNKNOWN'

        # Get sentiment from insights
        sentiment_score = None
        sentiment_label = ""
        insights = raw.get('insights', [])
        if insights:
            for insight in insights:
                if insight.get('sentiment'):
                    sentiment_label = insight.get('sentiment', '')
                    sentiment_map = {'positive': 1.0, 'neutral': 0.0, 'negative': -1.0}
                    sentiment_score = sentiment_map.get(sentiment_label, 0.0)
                    break

        # Calculate content length
        content = raw.get('description', '') or ''
        content_length = len(content)

        # Generate dedup hash
        title = raw.get('title', '')
        pub_date = pub_str[:10] if pub_str else ''
        hash_input = f"{primary_ticker.upper()}|{title.strip().lower()}|{pub_date}"
        dedup_hash = hashlib.md5(hash_input.encode()).hexdigest()

        # Generate article_id
        article_id = raw.get('id', dedup_hash)

        return NewsArticle(
            article_id=str(article_id),
            ticker=primary_ticker,
            title=title,
            published_at=pub_str,
            source_api="polygon",
            description=content,
            content=content,
            url=raw.get('article_url', ''),
            publisher=raw.get('publisher', {}).get('name', ''),
            author=raw.get('author', ''),
            related_tickers=json.dumps(tickers),
            tags=json.dumps(raw.get('keywords', [])),
            category='',
            source_sentiment=sentiment_score,
            source_sentiment_label=sentiment_label,
            collected_at=collected_at.isoformat(),
            content_length=content_length,
            dedup_hash=dedup_hash,
        )


def load_env() -> str:
    """Resolve only the profile-backed Massive process bridge.

    The sidecar injects the profile value into ``MASSIVE_API_KEY``. Standalone
    operators may set that same process variable explicitly. Retired credential
    aliases and dotenv files are not runtime authorities.
    """
    value = os.environ.get("MASSIVE_API_KEY", "").strip()
    return "" if not value or value.startswith("your_") else value
