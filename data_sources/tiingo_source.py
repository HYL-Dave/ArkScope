"""
Tiingo Data Source Implementation.

Tiingo provides:
- News API: Financial news with ticker filtering
- Stock Prices: 30+ years of EOD data (free tier)
- IEX Real-time: Real-time prices (paid tier)

Free Tier Limits:
- 500 unique symbols per month
- 50 symbols per hour
- 1000 requests per day (estimated)

Documentation: https://www.tiingo.com/documentation/
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
    SECFiling,
)

logger = logging.getLogger(__name__)


class TiingoDataSource(BaseDataSource):
    """
    Tiingo data source implementation.

    Usage:
        # With explicit API key
        tiingo = TiingoDataSource(api_key='your_key')

        # From environment variable TIINGO_API_KEY
        tiingo = TiingoDataSource()

        # Fetch news
        news = tiingo.fetch_news(['AAPL', 'MSFT'], days_back=7)

        # Fetch prices
        prices = tiingo.fetch_prices(['AAPL'], start_date=date(2024, 1, 1))
    """

    BASE_URL = "https://api.tiingo.com"
    NEWS_ENDPOINT = "/tiingo/news"
    PRICES_ENDPOINT = "/tiingo/daily"
    IEX_ENDPOINT = "/iex"

    # Rate limiting
    REQUESTS_PER_MINUTE = 50  # Conservative estimate
    REQUEST_DELAY = 1.2  # Seconds between requests

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tiingo data source.

        Args:
            api_key: Tiingo API key. If None, reads from TIINGO_API_KEY env var.
        """
        super().__init__(api_key)

        if self.api_key is None:
            self.api_key = os.environ.get('TIINGO_API_KEY')

        if not self.api_key:
            logger.warning(
                "No Tiingo API key provided. Set TIINGO_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self._session = requests.Session()
        self._last_request_time = 0

    @property
    def source_name(self) -> str:
        return "Tiingo"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.TIINGO

    @property
    def supports_news(self) -> bool:
        return True

    @property
    def supports_prices(self) -> bool:
        return True

    @property
    def supports_sec_filings(self) -> bool:
        return False  # Tiingo doesn't provide SEC filings

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.api_key}',
        }

    def _rate_limit_wait(self):
        """Wait to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

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
            raise ValueError("Tiingo API key is required")

        self._rate_limit_wait()

        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self._session.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )

            # Track rate limit headers if available
            if 'X-RateLimit-Remaining' in response.headers:
                self._rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
                return self._make_request(endpoint, params)
            elif response.status_code == 401:
                logger.error("Invalid API key")
                return None
            elif response.status_code == 404:
                logger.warning(f"Resource not found: {endpoint}")
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

        # Test with a simple metadata request
        result = self._make_request(
            f"{self.PRICES_ENDPOINT}/AAPL",
            params={'startDate': date.today().isoformat(), 'endDate': date.today().isoformat()}
        )
        return result is not None

    def fetch_news(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days_back: int = 7,
        limit: Optional[int] = None,
    ) -> List[NewsArticle]:
        """
        Fetch news articles from Tiingo.

        Tiingo News API returns articles that mention the specified tickers.

        Args:
            tickers: List of stock symbols (e.g., ['AAPL', 'MSFT']).
            start_date: Start date for news search.
            end_date: End date (default: today).
            days_back: Days to look back if start_date not specified.
            limit: Max articles to return (default: 100 per ticker).

        Returns:
            List of NewsArticle objects.
        """
        if end_date is None:
            end_date = date.today()

        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        all_articles = []

        # Tiingo allows comma-separated tickers, but we'll batch for safety
        batch_size = 10
        for i in range(0, len(tickers), batch_size):
            batch_tickers = tickers[i:i + batch_size]
            ticker_str = ','.join(batch_tickers)

            params = {
                'tickers': ticker_str,
                'startDate': start_date.isoformat(),
                'endDate': end_date.isoformat(),
                'limit': limit or 100,
                'sortBy': 'publishedDate',
            }

            logger.info(f"Fetching news for {ticker_str} from {start_date} to {end_date}")

            response = self._make_request(self.NEWS_ENDPOINT, params)

            if response:
                for item in response:
                    article = self._parse_news_item(item)
                    if article:
                        all_articles.append(article)

        logger.info(f"Fetched {len(all_articles)} articles total")
        return all_articles

    def _parse_news_item(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse a single news item from Tiingo response."""
        try:
            # Parse published date
            pub_date_str = item.get('publishedDate', '')
            if pub_date_str:
                # Tiingo returns ISO format with timezone
                pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
            else:
                pub_date = datetime.now()

            # Get tickers mentioned
            tickers = item.get('tickers', [])
            primary_ticker = tickers[0] if tickers else 'UNKNOWN'

            return NewsArticle(
                ticker=primary_ticker,
                title=item.get('title', ''),
                published_date=pub_date,
                source=item.get('source', 'Tiingo'),
                description=item.get('description', ''),
                content=item.get('description', ''),  # Tiingo doesn't provide full content
                url=item.get('url', ''),
                tags=item.get('tags', []),
                related_tickers=tickers,
                data_source='tiingo',
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
        Fetch historical stock prices from Tiingo.

        Tiingo provides up to 30+ years of EOD data on the free tier.

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

        # Map frequency to Tiingo's resampleFreq parameter
        freq_map = {
            'daily': 'daily',
            'weekly': 'weekly',
            'monthly': 'monthly',
        }
        tiingo_freq = freq_map.get(frequency, 'daily')

        for ticker in tickers:
            params = {
                'startDate': start_date.isoformat(),
                'endDate': end_date.isoformat(),
                'resampleFreq': tiingo_freq,
            }

            logger.info(f"Fetching {frequency} prices for {ticker}")

            response = self._make_request(
                f"{self.PRICES_ENDPOINT}/{ticker}/prices",
                params,
            )

            if response:
                for item in response:
                    price = self._parse_price_item(ticker, item)
                    if price:
                        all_prices.append(price)

        logger.info(f"Fetched {len(all_prices)} price records total")
        return all_prices

    def _parse_price_item(self, ticker: str, item: Dict[str, Any]) -> Optional[StockPrice]:
        """Parse a single price item from Tiingo response."""
        try:
            # Parse date
            date_str = item.get('date', '')
            if date_str:
                price_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            else:
                return None

            return StockPrice(
                ticker=ticker,
                date=price_date,
                open=item.get('open', 0),
                high=item.get('high', 0),
                low=item.get('low', 0),
                close=item.get('close', 0),
                volume=item.get('volume', 0),
                adj_open=item.get('adjOpen'),
                adj_high=item.get('adjHigh'),
                adj_low=item.get('adjLow'),
                adj_close=item.get('adjClose'),
                adj_volume=item.get('adjVolume'),
                dividend=item.get('divCash'),
                split_factor=item.get('splitFactor'),
                data_source='tiingo',
            )
        except Exception as e:
            logger.warning(f"Failed to parse price item for {ticker}: {e}")
            return None

    def fetch_metadata(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata for a ticker.

        Returns company info like name, exchange, description, etc.
        """
        response = self._make_request(f"{self.PRICES_ENDPOINT}/{ticker}")
        return response

    def get_supported_tickers(self) -> List[str]:
        """
        Get list of all supported tickers.

        Note: This endpoint may be rate-limited or require paid tier.
        """
        # This would need a different endpoint or local cache
        logger.warning("get_supported_tickers not fully implemented for Tiingo")
        return []

    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, '_session'):
            self._session.close()