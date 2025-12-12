"""
Alpha Vantage Data Source

Features (Free Tier):
- 25 API calls/day (very limited!)
- 5 calls/minute
- News with AI sentiment analysis
- 20+ years EOD stock prices
- 50+ technical indicators
- Earnings call transcripts (15+ years)

Docs: https://www.alphavantage.co/documentation/
"""

import os
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any

import requests

from .base import BaseDataSource, DataSourceType, NewsArticle, StockPrice


class AlphaVantageDataSource(BaseDataSource):
    """Alpha Vantage API client with rate limiting."""

    BASE_URL = "https://www.alphavantage.co/query"

    # Free tier: 25 calls/day, 5 calls/minute
    CALLS_PER_DAY = 25
    CALLS_PER_MINUTE = 5
    REQUEST_DELAY = 12.0  # seconds between requests (safe for 5/min)

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY', '')
        self._last_request_time = 0
        self._daily_calls = 0
        self._daily_reset = datetime.now().date()

    # -------------------------------------------------------------------------
    # BaseDataSource abstract properties
    # -------------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        return "alpha_vantage"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.ALPHA_VANTAGE

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

    def _rate_limit(self):
        """Enforce rate limiting."""
        # Reset daily counter if new day
        today = datetime.now().date()
        if today > self._daily_reset:
            self._daily_calls = 0
            self._daily_reset = today

        # Check daily limit
        if self._daily_calls >= self.CALLS_PER_DAY:
            raise Exception(f"Daily API limit reached ({self.CALLS_PER_DAY} calls). Reset tomorrow.")

        # Enforce per-minute rate limit
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()
        self._daily_calls += 1

    def _request(self, params: Dict[str, Any]) -> Dict:
        """Make API request with rate limiting."""
        self._rate_limit()

        params['apikey'] = self.api_key
        response = requests.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Check for API errors
        if 'Error Message' in data:
            raise Exception(f"API Error: {data['Error Message']}")
        if 'Note' in data:
            # Rate limit warning
            raise Exception(f"Rate limit: {data['Note']}")
        if 'Information' in data:
            # Premium feature or other info
            raise Exception(f"API Info: {data['Information']}")

        return data

    def test_connection(self) -> bool:
        """Test API connection."""
        try:
            # Use a simple quote request to test
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': 'IBM'
            }
            data = self._request(params)
            return 'Global Quote' in data
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
        Fetch news with sentiment analysis (BaseDataSource interface).

        Args:
            tickers: Stock symbols (e.g., ['AAPL', 'MSFT'])
            start_date: Start date for news
            end_date: End date for news
            days_back: Days to look back if start_date is None
            limit: Max articles (default 50, max 1000)

        Returns:
            List of NewsArticle objects
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        params = {
            'function': 'NEWS_SENTIMENT',
            'limit': min(limit or 50, 1000),
            'sort': 'LATEST',
            'tickers': ','.join(tickers),
            'time_from': start_date.strftime('%Y%m%dT0000'),
            'time_to': end_date.strftime('%Y%m%dT2359')
        }

        data = self._request(params)

        articles = []
        for item in data.get('feed', []):
            # Parse published date
            time_published = item.get('time_published', '')
            try:
                pub_date = datetime.strptime(time_published[:8], '%Y%m%d')
            except (ValueError, TypeError):
                pub_date = datetime.now()

            # Get primary ticker from ticker_sentiment
            ticker_sentiments = item.get('ticker_sentiment', [])
            primary_ticker = tickers[0] if tickers else ''
            sentiment_score = None

            # Find sentiment for requested tickers
            for ts in ticker_sentiments:
                if ts.get('ticker') in tickers:
                    primary_ticker = ts.get('ticker')
                    try:
                        sentiment_score = float(ts.get('ticker_sentiment_score', 0))
                    except (ValueError, TypeError):
                        pass
                    break

            # Use overall sentiment if no ticker-specific one
            if sentiment_score is None:
                try:
                    sentiment_score = float(item.get('overall_sentiment_score', 0))
                except (ValueError, TypeError):
                    sentiment_score = 0

            article = NewsArticle(
                ticker=primary_ticker,
                title=item.get('title', ''),
                published_date=pub_date,
                source=item.get('source', 'Alpha Vantage'),
                description=item.get('summary', ''),
                url=item.get('url', ''),
                author=', '.join(item.get('authors', [])),
                data_source='alpha_vantage',
                sentiment_score=sentiment_score,
                related_tickers=[ts.get('ticker') for ts in ticker_sentiments],
                raw_data=item
            )
            articles.append(article)

        return articles

    def fetch_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: Optional[date] = None,
        frequency: str = 'daily',
    ) -> List[StockPrice]:
        """
        Fetch stock prices (BaseDataSource interface).

        Args:
            tickers: Stock symbols
            start_date: Start date for price data
            end_date: End date (default: today)
            frequency: Data frequency ('daily', 'weekly', 'monthly')

        Returns:
            List of StockPrice objects
        """
        if end_date is None:
            end_date = date.today()

        all_prices = []

        for ticker in tickers:
            # Determine if we need full or compact output
            days_needed = (end_date - start_date).days
            outputsize = 'full' if days_needed > 100 else 'compact'

            params = {
                'function': 'TIME_SERIES_DAILY_ADJUSTED',
                'symbol': ticker,
                'outputsize': outputsize
            }

            try:
                data = self._request(params)
                time_series = data.get('Time Series (Daily)', {})

                for date_str, values in time_series.items():
                    try:
                        price_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        continue

                    # Filter by date range
                    if start_date <= price_date <= end_date:
                        price = StockPrice(
                            ticker=ticker,
                            date=price_date,
                            open=float(values['1. open']),
                            high=float(values['2. high']),
                            low=float(values['3. low']),
                            close=float(values['4. close']),
                            volume=int(values['6. volume']),
                            adj_close=float(values['5. adjusted close']),
                            dividend=float(values.get('7. dividend amount', 0)),
                            split_factor=float(values.get('8. split coefficient', 1)),
                            data_source='alpha_vantage'
                        )
                        all_prices.append(price)
            except Exception as e:
                print(f"Error fetching prices for {ticker}: {e}")

        return sorted(all_prices, key=lambda x: (x.ticker, x.date))

    # -------------------------------------------------------------------------
    # Alpha Vantage specific methods
    # -------------------------------------------------------------------------

    def fetch_news_raw(
        self,
        tickers: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        sort: str = 'LATEST'
    ) -> List[Dict]:
        """
        Fetch news with sentiment analysis (raw dict format).

        Args:
            tickers: Stock symbols (e.g., ['AAPL', 'MSFT'])
            topics: Topics filter (e.g., ['technology', 'earnings'])
            start_date: Start date for news
            end_date: End date for news
            limit: Max articles (default 50, max 1000)
            sort: 'LATEST', 'EARLIEST', or 'RELEVANCE'

        Returns:
            List of news articles with sentiment scores
        """
        params = {
            'function': 'NEWS_SENTIMENT',
            'limit': min(limit, 1000),
            'sort': sort
        }

        if tickers:
            params['tickers'] = ','.join(tickers)
        if topics:
            params['topics'] = ','.join(topics)
        if start_date:
            params['time_from'] = start_date.strftime('%Y%m%dT0000')
        if end_date:
            params['time_to'] = end_date.strftime('%Y%m%dT2359')

        data = self._request(params)

        articles = []
        for item in data.get('feed', []):
            article = {
                'title': item.get('title'),
                'url': item.get('url'),
                'published': item.get('time_published'),
                'summary': item.get('summary'),
                'source': item.get('source'),
                'authors': item.get('authors', []),
                'overall_sentiment_score': item.get('overall_sentiment_score'),
                'overall_sentiment_label': item.get('overall_sentiment_label'),
                'ticker_sentiments': []
            }

            # Extract per-ticker sentiment
            for ticker_sentiment in item.get('ticker_sentiment', []):
                article['ticker_sentiments'].append({
                    'ticker': ticker_sentiment.get('ticker'),
                    'relevance_score': ticker_sentiment.get('relevance_score'),
                    'sentiment_score': ticker_sentiment.get('ticker_sentiment_score'),
                    'sentiment_label': ticker_sentiment.get('ticker_sentiment_label')
                })

            articles.append(article)

        return articles

    def fetch_quote(self, ticker: str) -> Dict:
        """
        Fetch real-time quote for a single stock.

        Args:
            ticker: Stock symbol

        Returns:
            Current quote data
        """
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': ticker
        }

        data = self._request(params)
        quote = data.get('Global Quote', {})

        return {
            'ticker': quote.get('01. symbol'),
            'open': float(quote.get('02. open', 0)),
            'high': float(quote.get('03. high', 0)),
            'low': float(quote.get('04. low', 0)),
            'price': float(quote.get('05. price', 0)),
            'volume': int(quote.get('06. volume', 0)),
            'latest_trading_day': quote.get('07. latest trading day'),
            'previous_close': float(quote.get('08. previous close', 0)),
            'change': float(quote.get('09. change', 0)),
            'change_percent': quote.get('10. change percent', '0%')
        }

    def fetch_earnings_calendar(
        self,
        horizon: str = '3month'
    ) -> List[Dict]:
        """
        Fetch upcoming earnings announcements.

        Args:
            horizon: '3month', '6month', or '12month'

        Returns:
            List of upcoming earnings dates
        """
        params = {
            'function': 'EARNINGS_CALENDAR',
            'horizon': horizon
        }

        # This endpoint returns CSV, not JSON
        self._rate_limit()
        params['apikey'] = self.api_key

        response = requests.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        # Parse CSV
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            return []

        headers = lines[0].split(',')
        earnings = []

        for line in lines[1:]:
            values = line.split(',')
            if len(values) == len(headers):
                earnings.append(dict(zip(headers, values)))

        return earnings

    def fetch_company_overview(self, ticker: str) -> Dict:
        """
        Fetch company fundamentals and overview.

        Args:
            ticker: Stock symbol

        Returns:
            Company overview data
        """
        params = {
            'function': 'OVERVIEW',
            'symbol': ticker
        }

        return self._request(params)

    def get_remaining_calls(self) -> Dict:
        """Get remaining API calls for today."""
        today = datetime.now().date()
        if today > self._daily_reset:
            self._daily_calls = 0
            self._daily_reset = today

        return {
            'daily_limit': self.CALLS_PER_DAY,
            'used_today': self._daily_calls,
            'remaining': self.CALLS_PER_DAY - self._daily_calls,
            'reset_date': str(self._daily_reset + timedelta(days=1))
        }