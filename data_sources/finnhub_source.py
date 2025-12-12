"""
Finnhub Data Source Implementation.

Finnhub provides:
- News API: Company news with ticker filtering (FREE)
- Stock Prices: Real-time and historical prices
- Company Fundamentals: Financial data, earnings, etc.

Free Tier Limits:
- 60 API calls/minute
- Access to most endpoints including news

Documentation: https://finnhub.io/docs/api
"""

import os
import time
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
import requests

from .base import (
    BaseDataSource,
    DataSourceType,
    NewsArticle,
    StockPrice,
)

logger = logging.getLogger(__name__)


class FinnhubDataSource(BaseDataSource):
    """
    Finnhub data source implementation.

    Usage:
        # With explicit API key
        finnhub = FinnhubDataSource(api_key='your_key')

        # From environment variable FINNHUB_API_KEY
        finnhub = FinnhubDataSource()

        # Fetch news
        news = finnhub.fetch_news(['AAPL', 'MSFT'], days_back=7)

        # Fetch prices
        prices = finnhub.fetch_prices(['AAPL'], start_date=date(2024, 1, 1))
    """

    BASE_URL = "https://finnhub.io/api/v1"

    # Rate limiting: 60 calls/minute for free tier
    REQUESTS_PER_MINUTE = 60
    REQUEST_DELAY = 1.0  # 1 second between requests to be safe

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Finnhub data source.

        Args:
            api_key: Finnhub API key. If None, reads from FINNHUB_API_KEY env var.
        """
        super().__init__(api_key)

        if self.api_key is None:
            self.api_key = os.environ.get('FINNHUB_API_KEY')

        if not self.api_key:
            logger.warning(
                "No Finnhub API key provided. Set FINNHUB_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self._session = requests.Session()
        self._last_request_time = 0
        self._request_count = 0
        self._minute_start = time.time()

    @property
    def source_name(self) -> str:
        return "Finnhub"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.FINNHUB

    @property
    def supports_news(self) -> bool:
        return True

    @property
    def supports_prices(self) -> bool:
        return True

    @property
    def supports_sec_filings(self) -> bool:
        return True  # Finnhub has SEC filings endpoint

    def _rate_limit_wait(self):
        """Wait to respect rate limits (60 calls/minute)."""
        current_time = time.time()

        # Reset counter every minute
        if current_time - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = current_time

        # If we've hit the limit, wait until the minute resets
        if self._request_count >= self.REQUESTS_PER_MINUTE:
            wait_time = 60 - (current_time - self._minute_start)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                self._request_count = 0
                self._minute_start = time.time()

        # Also add small delay between requests
        elapsed = current_time - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Make an API request with rate limiting and error handling.

        Args:
            endpoint: API endpoint path.
            params: Query parameters.

        Returns:
            JSON response or None on error.
        """
        if not self.api_key:
            raise ValueError("Finnhub API key is required")

        self._rate_limit_wait()

        url = f"{self.BASE_URL}{endpoint}"

        # Add API key to params
        if params is None:
            params = {}
        params['token'] = self.api_key

        try:
            response = self._session.get(url, params=params, timeout=30)

            # Track rate limit headers
            if 'X-Ratelimit-Remaining' in response.headers:
                self._rate_limit_remaining = int(response.headers['X-Ratelimit-Remaining'])
            if 'X-Ratelimit-Reset' in response.headers:
                reset_ts = int(response.headers['X-Ratelimit-Reset'])
                self._rate_limit_reset = datetime.fromtimestamp(reset_ts)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
                self._request_count = 0
                return self._make_request(endpoint, params)
            elif response.status_code == 401:
                logger.error("Invalid API key")
                return None
            elif response.status_code == 403:
                logger.error("Access forbidden - check API key permissions")
                return None
            else:
                logger.error(f"API error {response.status_code}: {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def validate_credentials(self) -> bool:
        """
        Validate API credentials by making a test request.

        Returns:
            True if credentials are valid.
        """
        if not self.api_key:
            return False

        # Test with a simple quote request
        result = self._make_request("/quote", params={'symbol': 'AAPL'})
        return result is not None and 'c' in result  # 'c' is current price

    def fetch_news(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days_back: int = 7,
        limit: Optional[int] = None,
    ) -> List[NewsArticle]:
        """
        Fetch news articles from Finnhub.

        Finnhub's company news endpoint returns articles for a specific company.

        Args:
            tickers: List of stock symbols (e.g., ['AAPL', 'MSFT']).
            start_date: Start date for news search.
            end_date: End date (default: today).
            days_back: Days to look back if start_date not specified.
            limit: Max articles per ticker (default: 50).

        Returns:
            List of NewsArticle objects.
        """
        if end_date is None:
            end_date = date.today()

        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        all_articles = []
        seen_hashes = set()  # For deduplication

        for ticker in tickers:
            params = {
                'symbol': ticker,
                'from': start_date.isoformat(),
                'to': end_date.isoformat(),
            }

            logger.info(f"Fetching news for {ticker} from {start_date} to {end_date}")

            response = self._make_request("/company-news", params)

            if response:
                articles_for_ticker = []
                for item in response:
                    article = self._parse_news_item(ticker, item)
                    if article and article.article_hash not in seen_hashes:
                        seen_hashes.add(article.article_hash)
                        articles_for_ticker.append(article)

                # Apply limit per ticker
                if limit:
                    articles_for_ticker = articles_for_ticker[:limit]

                all_articles.extend(articles_for_ticker)
                logger.info(f"  Got {len(articles_for_ticker)} articles for {ticker}")

        logger.info(f"Fetched {len(all_articles)} unique articles total")
        return all_articles

    def _parse_news_item(self, ticker: str, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse a single news item from Finnhub response."""
        try:
            # Parse published date (Finnhub uses Unix timestamp)
            timestamp = item.get('datetime', 0)
            if timestamp:
                pub_date = datetime.fromtimestamp(timestamp)
            else:
                pub_date = datetime.now()

            return NewsArticle(
                ticker=ticker,
                title=item.get('headline', ''),
                published_date=pub_date,
                source=item.get('source', 'Finnhub'),
                description=item.get('summary', ''),
                content=item.get('summary', ''),
                url=item.get('url', ''),
                tags=item.get('category', '').split(',') if item.get('category') else [],
                related_tickers=[ticker] + item.get('related', '').split(',') if item.get('related') else [ticker],
                data_source='finnhub',
                raw_data=item,
            )
        except Exception as e:
            logger.warning(f"Failed to parse news item: {e}")
            return None

    def fetch_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: Optional[date] = None,
        frequency: str = 'daily',
    ) -> List[StockPrice]:
        """
        Fetch historical stock prices from Finnhub.

        Uses the stock candles endpoint for historical OHLCV data.

        Args:
            tickers: List of stock symbols.
            start_date: Start date for price data.
            end_date: End date (default: today).
            frequency: 'daily', 'weekly', or 'monthly'.

        Returns:
            List of StockPrice objects.
        """
        if end_date is None:
            end_date = date.today()

        all_prices = []

        # Map frequency to Finnhub resolution
        resolution_map = {
            'daily': 'D',
            'weekly': 'W',
            'monthly': 'M',
        }
        resolution = resolution_map.get(frequency, 'D')

        for ticker in tickers:
            # Convert dates to Unix timestamps
            start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
            end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())

            params = {
                'symbol': ticker,
                'resolution': resolution,
                'from': start_ts,
                'to': end_ts,
            }

            logger.info(f"Fetching {frequency} prices for {ticker}")

            response = self._make_request("/stock/candle", params)

            if response and response.get('s') == 'ok':
                prices = self._parse_candle_response(ticker, response)
                all_prices.extend(prices)
                logger.info(f"  Got {len(prices)} price records for {ticker}")
            elif response and response.get('s') == 'no_data':
                logger.warning(f"No price data available for {ticker}")

        logger.info(f"Fetched {len(all_prices)} price records total")
        return all_prices

    def _parse_candle_response(self, ticker: str, response: Dict[str, Any]) -> List[StockPrice]:
        """Parse candle response from Finnhub."""
        prices = []

        timestamps = response.get('t', [])
        opens = response.get('o', [])
        highs = response.get('h', [])
        lows = response.get('l', [])
        closes = response.get('c', [])
        volumes = response.get('v', [])

        for i in range(len(timestamps)):
            try:
                price_date = datetime.fromtimestamp(timestamps[i]).date()

                prices.append(StockPrice(
                    ticker=ticker,
                    date=price_date,
                    open=opens[i],
                    high=highs[i],
                    low=lows[i],
                    close=closes[i],
                    volume=int(volumes[i]),
                    data_source='finnhub',
                ))
            except Exception as e:
                logger.warning(f"Failed to parse price for {ticker} at index {i}: {e}")

        return prices

    def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch real-time quote for a ticker.

        Returns:
            Dictionary with current price info:
            - c: Current price
            - h: High price of the day
            - l: Low price of the day
            - o: Open price of the day
            - pc: Previous close price
            - t: Timestamp
        """
        response = self._make_request("/quote", params={'symbol': ticker})
        return response

    def fetch_company_profile(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company profile/metadata.

        Returns company info like name, industry, market cap, etc.
        """
        response = self._make_request("/stock/profile2", params={'symbol': ticker})
        return response

    def fetch_market_news(self, category: str = 'general') -> List[NewsArticle]:
        """
        Fetch general market news (not ticker-specific).

        Args:
            category: News category ('general', 'forex', 'crypto', 'merger')

        Returns:
            List of NewsArticle objects.
        """
        response = self._make_request("/news", params={'category': category})

        if not response:
            return []

        articles = []
        for item in response:
            try:
                timestamp = item.get('datetime', 0)
                pub_date = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()

                articles.append(NewsArticle(
                    ticker='MARKET',
                    title=item.get('headline', ''),
                    published_date=pub_date,
                    source=item.get('source', 'Finnhub'),
                    description=item.get('summary', ''),
                    content=item.get('summary', ''),
                    url=item.get('url', ''),
                    tags=[item.get('category', '')],
                    data_source='finnhub',
                    raw_data=item,
                ))
            except Exception as e:
                logger.warning(f"Failed to parse market news item: {e}")

        return articles

    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, '_session'):
            self._session.close()