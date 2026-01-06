"""
EODHD (EOD Historical Data) Data Source

Features (Free Tier):
- 20 API calls/day
- News API costs 5 calls each (= 4 news queries/day!)
- 1 year EOD history
- Demo tickers (AAPL.US, MSFT.US, GOOGL.US) unlimited

Paid Tiers:
- EOD ($19.99/month): 100k calls/day, 1972+ EOD history
- Intraday ($29.99/month): +1-minute data
- Fundamentals ($59.99/month): +20 years fundamentals
- All-In-One ($99.99/month): Everything

Coverage: 150,000+ tickers, 60+ exchanges worldwide

Docs: https://eodhd.com/financial-apis/
"""

import os
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any

import requests

from .base import BaseDataSource, DataSourceType, NewsArticle, StockPrice


class EODHDDataSource(BaseDataSource):
    """EODHD API client with rate limiting."""

    BASE_URL = "https://eodhd.com/api"

    # Free tier: 20 calls/day total, news costs 5 calls each!
    CALLS_PER_DAY = 20
    NEWS_CALL_COST = 5  # Each news request costs 5 API calls!
    REQUEST_DELAY = 0.5  # No per-minute limit documented

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('EODHD_API_KEY', '').strip()
        self._last_request_time = 0
        self._daily_calls = 0
        self._daily_reset = datetime.now().date()

    # -------------------------------------------------------------------------
    # BaseDataSource abstract properties
    # -------------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        return "eodhd"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.EODHD

    @property
    def supports_news(self) -> bool:
        return True

    @property
    def supports_prices(self) -> bool:
        return True

    @property
    def supports_sec_filings(self) -> bool:
        return False

    def validate_credentials(self) -> bool:
        """Validate API credentials by making a test request."""
        return self.test_connection()

    # -------------------------------------------------------------------------
    # Rate limiting
    # -------------------------------------------------------------------------

    def _reset_daily_if_needed(self):
        """Reset daily counter if new day."""
        today = datetime.now().date()
        if today > self._daily_reset:
            self._daily_calls = 0
            self._daily_reset = today

    def _rate_limit(self, call_cost: int = 1):
        """Enforce rate limiting."""
        self._reset_daily_if_needed()

        # Check daily limit
        if self._daily_calls + call_cost > self.CALLS_PER_DAY:
            raise Exception(
                f"Daily API limit would be exceeded. "
                f"Used: {self._daily_calls}/{self.CALLS_PER_DAY}, "
                f"Requested: {call_cost} calls. Reset tomorrow."
            )

        # Small delay between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)

        self._last_request_time = time.time()
        self._daily_calls += call_cost

    def _request(self, endpoint: str, params: Dict[str, Any], call_cost: int = 1) -> Any:
        """Make API request with rate limiting."""
        self._rate_limit(call_cost)

        params['api_token'] = self.api_key
        params['fmt'] = 'json'

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, params=params, timeout=30)

        # Check for API errors
        if response.status_code == 401:
            raise Exception("Invalid API key")
        if response.status_code == 402:
            raise Exception("API limit exceeded - upgrade required")
        if response.status_code == 429:
            raise Exception("Rate limit exceeded")

        response.raise_for_status()

        data = response.json()

        # Check for error responses
        if isinstance(data, dict):
            if 'error' in data:
                raise Exception(f"API Error: {data['error']}")
            if data.get('code') == 'NOT_FOUND':
                return None

        return data

    def test_connection(self) -> bool:
        """Test API connection with a demo ticker."""
        try:
            # Use demo ticker (unlimited for free tier)
            params = {'s': 'AAPL.US'}
            data = self._request('real-time/AAPL.US', params, call_cost=1)
            return data is not None and 'code' in data
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # BaseDataSource abstract methods
    # -------------------------------------------------------------------------

    def fetch_news(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days_back: int = 7,
        limit: Optional[int] = None,
    ) -> List[NewsArticle]:
        """
        Fetch news articles for given tickers.

        WARNING: Each news call costs 5 API calls! Free tier = only 4 news queries/day!

        Args:
            tickers: Stock symbols (e.g., ['AAPL', 'MSFT'])
            start_date: Start date for news
            end_date: End date for news
            days_back: Days to look back if start_date is None
            limit: Max articles per ticker

        Returns:
            List of NewsArticle objects
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        all_articles = []

        for ticker in tickers:
            try:
                # Normalize ticker format (EODHD uses SYMBOL.EXCHANGE)
                eodhd_ticker = self._normalize_ticker(ticker)

                params = {
                    's': eodhd_ticker,
                    'from': start_date.strftime('%Y-%m-%d'),
                    'to': end_date.strftime('%Y-%m-%d'),
                    'limit': limit or 50,
                }

                # WARNING: News costs 5 API calls!
                data = self._request('news', params, call_cost=self.NEWS_CALL_COST)

                if not data or not isinstance(data, list):
                    continue

                for item in data:
                    # Parse published date
                    pub_date_str = item.get('date', '')
                    try:
                        pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        try:
                            pub_date = datetime.strptime(pub_date_str[:19], '%Y-%m-%d %H:%M:%S')
                        except:
                            pub_date = datetime.now()

                    # Extract related tickers
                    related = []
                    symbols = item.get('symbols', [])
                    if isinstance(symbols, list):
                        related = symbols
                    elif isinstance(symbols, str):
                        related = [symbols]

                    # Extract sentiment if available
                    sentiment = item.get('sentiment', {})
                    sentiment_score = None
                    if sentiment:
                        # EODHD provides polarity (-1 to 1) and neg/neu/pos scores
                        polarity = sentiment.get('polarity')
                        if polarity is not None:
                            sentiment_score = float(polarity)

                    article = NewsArticle(
                        ticker=ticker,
                        title=item.get('title', ''),
                        published_date=pub_date,
                        source=item.get('source', 'EODHD'),
                        description=item.get('content', ''),
                        url=item.get('link', ''),
                        author='',
                        data_source='eodhd',
                        sentiment_score=sentiment_score,
                        related_tickers=related,
                        raw_data=item
                    )
                    all_articles.append(article)

            except Exception as e:
                print(f"Error fetching news for {ticker}: {e}")

        return all_articles

    def fetch_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: Optional[date] = None,
        frequency: str = 'daily',
    ) -> List[StockPrice]:
        """
        Fetch stock prices for given tickers.

        Args:
            tickers: Stock symbols
            start_date: Start date for price data
            end_date: End date (default: today)
            frequency: Data frequency ('daily' only for EOD)

        Returns:
            List of StockPrice objects
        """
        if end_date is None:
            end_date = date.today()

        all_prices = []

        for ticker in tickers:
            try:
                eodhd_ticker = self._normalize_ticker(ticker)

                params = {
                    'from': start_date.strftime('%Y-%m-%d'),
                    'to': end_date.strftime('%Y-%m-%d'),
                }

                # EOD data endpoint
                data = self._request(f'eod/{eodhd_ticker}', params, call_cost=1)

                if not data or not isinstance(data, list):
                    continue

                for item in data:
                    try:
                        price_date = datetime.strptime(item['date'], '%Y-%m-%d').date()
                    except (ValueError, KeyError):
                        continue

                    price = StockPrice(
                        ticker=ticker,
                        date=price_date,
                        open=float(item.get('open', 0)),
                        high=float(item.get('high', 0)),
                        low=float(item.get('low', 0)),
                        close=float(item.get('close', 0)),
                        volume=int(item.get('volume', 0)),
                        adj_close=float(item.get('adjusted_close', item.get('close', 0))),
                        data_source='eodhd'
                    )
                    all_prices.append(price)

            except Exception as e:
                print(f"Error fetching prices for {ticker}: {e}")

        return sorted(all_prices, key=lambda x: (x.ticker, x.date))

    # -------------------------------------------------------------------------
    # EODHD specific methods
    # -------------------------------------------------------------------------

    def _normalize_ticker(self, ticker: str) -> str:
        """
        Normalize ticker to EODHD format (SYMBOL.EXCHANGE).

        Args:
            ticker: Stock symbol (e.g., 'AAPL' or 'AAPL.US')

        Returns:
            EODHD format ticker (e.g., 'AAPL.US')
        """
        if '.' in ticker:
            return ticker
        # Default to US exchange
        return f"{ticker}.US"

    def fetch_news_raw(
        self,
        tickers: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Fetch news in raw dict format.

        WARNING: Each call costs 5 API calls!

        Args:
            tickers: Stock symbols
            start_date: Start date for news
            end_date: End date for news
            limit: Max articles

        Returns:
            List of raw news articles
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        params = {
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'limit': limit,
        }

        if tickers:
            params['s'] = ','.join([self._normalize_ticker(t) for t in tickers])

        return self._request('news', params, call_cost=self.NEWS_CALL_COST) or []

    def fetch_quote(self, ticker: str) -> Dict:
        """
        Fetch real-time quote for a single stock.

        Args:
            ticker: Stock symbol

        Returns:
            Current quote data
        """
        eodhd_ticker = self._normalize_ticker(ticker)

        data = self._request(f'real-time/{eodhd_ticker}', {}, call_cost=1)

        if not data:
            return {}

        return {
            'ticker': ticker,
            'code': data.get('code'),
            'timestamp': data.get('timestamp'),
            'gmtoffset': data.get('gmtoffset'),
            'open': data.get('open'),
            'high': data.get('high'),
            'low': data.get('low'),
            'close': data.get('close'),
            'previous_close': data.get('previousClose'),
            'change': data.get('change'),
            'change_percent': data.get('change_p'),
            'volume': data.get('volume'),
        }

    def fetch_fundamentals(self, ticker: str) -> Dict:
        """
        Fetch company fundamentals.

        Args:
            ticker: Stock symbol

        Returns:
            Company fundamentals data
        """
        eodhd_ticker = self._normalize_ticker(ticker)

        return self._request(f'fundamentals/{eodhd_ticker}', {}, call_cost=1) or {}

    def get_remaining_calls(self) -> Dict:
        """Get remaining API calls for today."""
        self._reset_daily_if_needed()

        return {
            'daily_limit': self.CALLS_PER_DAY,
            'used_today': self._daily_calls,
            'remaining': self.CALLS_PER_DAY - self._daily_calls,
            'reset_date': str(self._daily_reset + timedelta(days=1)),
            'note': f'News requests cost {self.NEWS_CALL_COST} calls each!'
        }

    def get_exchanges(self) -> List[Dict]:
        """Get list of supported exchanges."""
        return self._request('exchanges-list', {}, call_cost=1) or []