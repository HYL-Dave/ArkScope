"""
Polygon.io (Massive.com) Data Source Implementation.

Polygon provides:
- Stock Prices: Real-time and historical (tick, minute, daily)
- News API: Financial news with sentiment
- Reference Data: Tickers, exchanges, markets

Free Tier Limits:
- 5 API calls/minute
- 2 years historical minute-level data
- EOD data included
- 15-minute delayed quotes

Documentation: https://polygon.io/docs/stocks
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


class PolygonDataSource(BaseDataSource):
    """
    Polygon.io data source implementation.

    Usage:
        # With explicit API key
        polygon = PolygonDataSource(api_key='your_key')

        # From environment variable POLYGON_API_KEY
        polygon = PolygonDataSource()

        # Fetch news
        news = polygon.fetch_news(['AAPL', 'MSFT'], days_back=7)

        # Fetch daily prices
        prices = polygon.fetch_prices(['AAPL'], start_date=date(2024, 1, 1))

        # Fetch minute-level prices (intraday)
        prices = polygon.fetch_intraday_prices('AAPL', date(2024, 1, 15))
    """

    BASE_URL = "https://api.polygon.io"

    # Rate limiting: 5 calls/minute for free tier
    REQUESTS_PER_MINUTE = 5
    REQUEST_DELAY = 12.0  # 12 seconds between requests for free tier

    def __init__(self, api_key: Optional[str] = None, is_paid: bool = False):
        """
        Initialize Polygon data source.

        Args:
            api_key: Polygon API key. If None, reads from POLYGON_API_KEY env var.
            is_paid: If True, uses faster rate limiting for paid plans.
        """
        super().__init__(api_key)

        if self.api_key is None:
            self.api_key = os.environ.get('POLYGON_API_KEY')

        if not self.api_key:
            logger.warning(
                "No Polygon API key provided. Set POLYGON_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self._session = requests.Session()
        self._last_request_time = 0
        self._request_count = 0
        self._minute_start = time.time()

        # Adjust rate limiting for paid plans
        if is_paid:
            self.REQUEST_DELAY = 0.1  # Much faster for paid plans
            self.REQUESTS_PER_MINUTE = 1000

    @property
    def source_name(self) -> str:
        return "Polygon.io"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.FINANCIAL_DATASETS  # Reuse enum, or add POLYGON

    @property
    def supports_news(self) -> bool:
        return True

    @property
    def supports_prices(self) -> bool:
        return True

    @property
    def supports_sec_filings(self) -> bool:
        return False

    def _rate_limit_wait(self):
        """Wait to respect rate limits (5 calls/minute for free tier)."""
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

        # Add delay between requests
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
            raise ValueError("Polygon API key is required")

        self._rate_limit_wait()

        url = f"{self.BASE_URL}{endpoint}"

        # Add API key to params
        if params is None:
            params = {}
        params['apiKey'] = self.api_key

        try:
            response = self._session.get(url, params=params, timeout=30)

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
                logger.error("Access forbidden - check API key permissions or subscription")
                return None
            elif response.status_code == 404:
                logger.warning(f"Resource not found: {endpoint}")
                return None
            else:
                logger.error(f"API error {response.status_code}: {response.text[:200]}")
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

        # Test with a simple ticker details request
        result = self._make_request("/v3/reference/tickers/AAPL")
        return result is not None and result.get('status') == 'OK'

    def fetch_news(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days_back: int = 7,
        limit: Optional[int] = None,
    ) -> List[NewsArticle]:
        """
        Fetch news articles from Polygon.

        Args:
            tickers: List of stock symbols (e.g., ['AAPL', 'MSFT']).
            start_date: Start date for news search.
            end_date: End date (default: today).
            days_back: Days to look back if start_date not specified.
            limit: Max articles to return (default: 100).

        Returns:
            List of NewsArticle objects.
        """
        if end_date is None:
            end_date = date.today()

        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        all_articles = []
        seen_ids = set()

        # Polygon allows multiple tickers in one request
        ticker_str = ','.join(tickers)

        params = {
            'ticker': ticker_str,
            'published_utc.gte': start_date.isoformat(),
            'published_utc.lte': end_date.isoformat(),
            'limit': limit or 100,
            'sort': 'published_utc',
            'order': 'desc',
        }

        logger.info(f"Fetching news for {ticker_str} from {start_date} to {end_date}")

        response = self._make_request("/v2/reference/news", params)

        if response and response.get('status') == 'OK':
            results = response.get('results', [])
            for item in results:
                article = self._parse_news_item(item)
                if article and article.article_hash not in seen_ids:
                    seen_ids.add(article.article_hash)
                    all_articles.append(article)

            logger.info(f"Fetched {len(all_articles)} articles")
        else:
            logger.warning("No news results returned")

        return all_articles

    def _parse_news_item(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse a single news item from Polygon response."""
        try:
            # Parse published date
            pub_date_str = item.get('published_utc', '')
            if pub_date_str:
                pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
            else:
                pub_date = datetime.now()

            # Get tickers
            tickers = item.get('tickers', [])
            primary_ticker = tickers[0] if tickers else 'UNKNOWN'

            # Get sentiment if available
            insights = item.get('insights', [])
            sentiment_score = None
            if insights:
                for insight in insights:
                    if insight.get('sentiment'):
                        sentiment_map = {'positive': 1, 'neutral': 0, 'negative': -1}
                        sentiment_score = sentiment_map.get(insight.get('sentiment'), 0)
                        break

            return NewsArticle(
                ticker=primary_ticker,
                title=item.get('title', ''),
                published_date=pub_date,
                source=item.get('publisher', {}).get('name', 'Polygon'),
                description=item.get('description', ''),
                content=item.get('description', ''),
                url=item.get('article_url', ''),
                author=item.get('author', ''),
                tags=item.get('keywords', []),
                related_tickers=tickers,
                data_source='polygon',
                sentiment_score=sentiment_score,
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
        Fetch historical stock prices from Polygon.

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

        # Map frequency to Polygon timespan
        timespan_map = {
            'daily': 'day',
            'weekly': 'week',
            'monthly': 'month',
        }
        timespan = timespan_map.get(frequency, 'day')

        for ticker in tickers:
            logger.info(f"Fetching {frequency} prices for {ticker}")

            # Use aggregates endpoint
            endpoint = f"/v2/aggs/ticker/{ticker}/range/1/{timespan}/{start_date.isoformat()}/{end_date.isoformat()}"

            params = {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000,
            }

            response = self._make_request(endpoint, params)

            if response and response.get('status') == 'OK':
                results = response.get('results', [])
                for item in results:
                    price = self._parse_price_item(ticker, item)
                    if price:
                        all_prices.append(price)

                logger.info(f"  Got {len(results)} price records for {ticker}")
            elif response and response.get('resultsCount', 0) == 0:
                logger.warning(f"No price data for {ticker}")

        logger.info(f"Fetched {len(all_prices)} price records total")
        return all_prices

    def _parse_price_item(self, ticker: str, item: Dict[str, Any]) -> Optional[StockPrice]:
        """Parse a single price item from Polygon response."""
        try:
            # Parse timestamp (milliseconds since epoch)
            timestamp = item.get('t', 0) / 1000
            price_date = datetime.fromtimestamp(timestamp).date()

            return StockPrice(
                ticker=ticker,
                date=price_date,
                open=item.get('o', 0),
                high=item.get('h', 0),
                low=item.get('l', 0),
                close=item.get('c', 0),
                volume=int(item.get('v', 0)),
                adj_close=item.get('c'),  # Polygon returns adjusted by default
                data_source='polygon',
            )
        except Exception as e:
            logger.warning(f"Failed to parse price for {ticker}: {e}")
            return None

    def fetch_intraday_prices(
        self,
        ticker: str,
        trade_date: date,
        multiplier: int = 1,
        timespan: str = 'minute',
    ) -> List[Dict[str, Any]]:
        """
        Fetch intraday (minute-level) prices for a single day.

        Args:
            ticker: Stock symbol.
            trade_date: Date to fetch data for.
            multiplier: Size of the timespan multiplier (e.g., 5 for 5-minute bars).
            timespan: 'minute', 'hour', 'second'.

        Returns:
            List of price dictionaries with OHLCV data.
        """
        logger.info(f"Fetching {multiplier}-{timespan} data for {ticker} on {trade_date}")

        endpoint = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{trade_date.isoformat()}/{trade_date.isoformat()}"

        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000,
        }

        response = self._make_request(endpoint, params)

        if response and response.get('status') == 'OK':
            results = response.get('results', [])
            logger.info(f"  Got {len(results)} intraday records")

            # Convert timestamps to readable format
            for item in results:
                item['datetime'] = datetime.fromtimestamp(item['t'] / 1000)

            return results

        return []

    def fetch_ticker_details(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information about a ticker.

        Returns company info, market cap, description, etc.
        """
        response = self._make_request(f"/v3/reference/tickers/{ticker}")

        if response and response.get('status') == 'OK':
            return response.get('results')
        return None

    def fetch_previous_close(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the previous day's OHLCV data.

        Useful for quick checks without historical queries.
        """
        response = self._make_request(f"/v2/aggs/ticker/{ticker}/prev")

        if response and response.get('status') == 'OK':
            results = response.get('results', [])
            return results[0] if results else None
        return None

    def fetch_market_status(self) -> Optional[Dict[str, Any]]:
        """
        Check if the market is currently open.

        Returns market status information.
        """
        return self._make_request("/v1/marketstatus/now")

    def get_available_history(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Check how much historical data is available for a ticker.

        Returns date range information.
        """
        # Fetch ticker details which includes list date
        details = self.fetch_ticker_details(ticker)
        if details:
            return {
                'ticker': ticker,
                'list_date': details.get('list_date'),
                'market': details.get('market'),
                'type': details.get('type'),
            }
        return None

    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, '_session'):
            self._session.close()