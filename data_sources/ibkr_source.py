"""
Interactive Brokers (IBKR) Data Source Implementation.

IBKR provides via TWS/IB Gateway:
- Historical OHLCV data (tick, minute, daily)
- Real-time quotes and market data
- Order execution

Requirements:
- TWS (Trader Workstation) or IB Gateway running locally
- API enabled in TWS/Gateway settings
- ib_insync library: pip install ib_insync

Free with IBKR account:
- Historical data included with trading account
- Rate limiting: ~60 requests per 10 minutes (pacing violations)

Documentation: https://ib-insync.readthedocs.io/
"""

import os
import time
import logging
import math
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

try:
    from ib_insync import IB, Stock, Option, util
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False

from .base import (
    BaseDataSource,
    DataSourceType,
    NewsArticle,
    StockPrice,
)

logger = logging.getLogger(__name__)


@dataclass
class IntradayBar:
    """Intraday bar data structure."""
    ticker: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    wap: Optional[float] = None  # Volume-weighted average price
    bar_count: Optional[int] = None  # Number of trades


@dataclass
class OptionChainParams:
    """Option chain parameters from OPRA."""
    underlying: str
    exchange: str
    expirations: List[str]  # Format: YYYYMMDD
    strikes: List[float]
    multiplier: str


@dataclass
class OptionQuote:
    """Option quote data structure."""
    underlying: str
    expiry: str
    strike: float
    right: str  # 'C' or 'P'
    con_id: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    # Greeks (may be None if not available)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    implied_vol: Optional[float] = None


class IBKRDataSource(BaseDataSource):
    """
    Interactive Brokers data source implementation.

    Connects to TWS or IB Gateway for market data and historical prices.

    Usage:
        # Default connection (localhost:7497 for TWS Paper Trading)
        ibkr = IBKRDataSource()

        # Connect to live TWS (port 7496)
        ibkr = IBKRDataSource(port=7496)

        # Connect to IB Gateway (port 4001 for live, 4002 for paper)
        ibkr = IBKRDataSource(port=4002)

        # Fetch daily prices
        prices = ibkr.fetch_prices(['AAPL'], start_date=date(2023, 1, 1))

        # Fetch 15-minute bars
        bars = ibkr.fetch_intraday_prices('AAPL', date(2024, 1, 15), interval='15 mins')

        # Always disconnect when done
        ibkr.disconnect()
    """

    # Supported intervals for historical data
    VALID_INTERVALS = [
        '1 secs', '5 secs', '10 secs', '15 secs', '30 secs',
        '1 min', '2 mins', '3 mins', '5 mins', '10 mins', '15 mins',
        '20 mins', '30 mins',
        '1 hour', '2 hours', '3 hours', '4 hours', '8 hours',
        '1 day', '1 week', '1 month',
    ]

    # Available data types for whatToShow parameter
    # Reference: https://interactivebrokers.github.io/tws-api/historical_bars.html
    WHAT_TO_SHOW_TYPES = [
        'TRADES',              # Trade prices OHLCV
        'MIDPOINT',            # Midpoint prices (bid+ask)/2
        'BID',                 # Bid prices
        'ASK',                 # Ask prices
        'BID_ASK',             # Time-averaged bid/ask spread
        'ADJUSTED_LAST',       # Split/dividend adjusted prices (TWS 967+)
        'HISTORICAL_VOLATILITY',  # Historical volatility
        'OPTION_IMPLIED_VOLATILITY',  # Option IV
        'FEE_RATE',            # Short borrow fee rate
    ]

    # Request pacing rules (from IBKR docs):
    # - No identical requests within 15 seconds
    # - Max 6 requests for same contract/exchange/type in 2 seconds
    # - Max 60 requests in any 10-minute period
    # - Max 50 concurrent requests
    REQUEST_DELAY = 0.5  # Conservative delay between requests
    MAX_REQUESTS_PER_10MIN = 60

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,  # 7497 = TWS paper, 7496 = TWS live, 4002 = GW paper, 4001 = GW live
        client_id: int = 1,
        timeout: int = 60,
        readonly: bool = True,
    ):
        """
        Initialize IBKR data source.

        Args:
            host: TWS/Gateway hostname (default localhost).
            port: TWS/Gateway port:
                  - 7497: TWS Paper Trading
                  - 7496: TWS Live
                  - 4002: IB Gateway Paper
                  - 4001: IB Gateway Live
            client_id: Client ID for connection (must be unique per connection).
            timeout: Connection timeout in seconds.
            readonly: If True, only allows data requests (no orders).
        """
        super().__init__(api_key=None)  # IBKR doesn't use API keys

        if not HAS_IB_INSYNC:
            raise ImportError(
                "ib_insync is required for IBKR data source. "
                "Install with: pip install ib_insync"
            )

        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.readonly = readonly

        self._ib: Optional[IB] = None
        self._connected = False
        self._last_request_time = 0
        self._request_count = 0

    @property
    def source_name(self) -> str:
        return "Interactive Brokers"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.POLYGON  # Reuse enum for now

    @property
    def supports_news(self) -> bool:
        return True  # IBKR news available with subscription (DJ, FLY, Briefing, etc.)

    @property
    def supports_prices(self) -> bool:
        return True

    @property
    def supports_sec_filings(self) -> bool:
        return False

    def connect(self) -> bool:
        """
        Connect to TWS/IB Gateway.

        Returns:
            True if connection successful.
        """
        if self._connected and self._ib and self._ib.isConnected():
            return True

        try:
            self._ib = IB()
            self._ib.connect(
                self.host,
                self.port,
                clientId=self.client_id,
                timeout=self.timeout,
                readonly=self.readonly,
            )
            self._connected = True
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from TWS/IB Gateway."""
        if self._ib:
            try:
                self._ib.disconnect()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._connected = False
                logger.info("Disconnected from IBKR")

    def _ensure_connected(self):
        """Ensure we have an active connection."""
        if not self._connected or not self._ib or not self._ib.isConnected():
            if not self.connect():
                raise ConnectionError("Cannot connect to TWS/IB Gateway")

    def _rate_limit_wait(self):
        """Wait to respect IBKR pacing limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def _create_contract(self, ticker: str) -> Stock:
        """Create a stock contract for the given ticker."""
        return Stock(ticker, "SMART", "USD")

    def _calculate_duration(self, start_date: date, end_date: date) -> str:
        """
        Calculate IBKR duration string.

        IBKR accepts: 'S' (seconds), 'D' (days), 'W' (weeks), 'M' (months), 'Y' (years)
        """
        duration_days = (end_date - start_date).days

        if duration_days <= 0:
            return "1 D"
        elif duration_days <= 365:
            return f"{duration_days} D"
        else:
            years = math.ceil(duration_days / 365)
            return f"{years} Y"

    def validate_credentials(self) -> bool:
        """
        Validate connection by attempting to connect and query.

        Returns:
            True if connection works.
        """
        try:
            self._ensure_connected()
            # Test with a simple contract query
            contract = self._create_contract("AAPL")
            self._ib.qualifyContracts(contract)
            return True
        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            return False

    def get_news_providers(self) -> List[Dict[str, str]]:
        """
        Get list of available news providers for the account.

        Returns:
            List of dicts with 'code' and 'name' keys.
        """
        self._ensure_connected()

        try:
            providers = self._ib.reqNewsProviders()
            return [{'code': p.code, 'name': p.name} for p in providers]
        except Exception as e:
            logger.error(f"Error fetching news providers: {e}")
            return []

    def _fetch_news_single_query(
        self,
        con_id: int,
        providers: str,
        start_dt: datetime,
        end_dt: datetime,
        ticker: str,
    ) -> List[NewsArticle]:
        """
        Single IBKR news query (max 300 results).

        Internal helper - use fetch_news() instead.

        Args:
            start_dt: Start datetime (with time precision)
            end_dt: End datetime (with time precision)
        """
        start_str = start_dt.strftime('%Y%m%d %H:%M:%S')
        end_str = end_dt.strftime('%Y%m%d %H:%M:%S')

        self._rate_limit_wait()

        headlines = self._ib.reqHistoricalNews(
            con_id,
            providers,
            start_str,
            end_str,
            300,  # Always request max to detect if we need to split
        )

        if not headlines:
            return []

        articles = []
        for h in headlines:
            # Parse the headline metadata
            # Format: {A:conId:L:lang:K:sentiment:C:confidence}headline
            headline_text = h.headline
            sentiment = None

            # Extract sentiment if present
            if headline_text.startswith('{'):
                try:
                    end_meta = headline_text.index('}')
                    meta = headline_text[1:end_meta]
                    headline_text = headline_text[end_meta + 1:]

                    # Parse K: (sentiment) value
                    for part in meta.split(':'):
                        if part.startswith('K:'):
                            try:
                                sentiment = float(part[2:])
                            except ValueError:
                                pass
                except (ValueError, IndexError):
                    pass

            # Convert time to datetime
            pub_time = h.time
            if isinstance(pub_time, str):
                try:
                    pub_time = datetime.strptime(pub_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pub_time = datetime.now()

            articles.append(NewsArticle(
                ticker=ticker,
                title=headline_text,
                published_date=pub_time,
                source=h.providerCode,
                description=f"[Article ID: {h.articleId}]",  # Store article_id for later body fetch
                url='',  # IBKR doesn't provide URL in headlines
                data_source='ibkr',
            ))

        return articles

    def fetch_news(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days_back: int = 7,
        limit: Optional[int] = None,
        providers: Optional[str] = None,
    ) -> List[NewsArticle]:
        """
        Fetch news articles from IBKR news providers.

        Requires news subscription (DJ, FLY, Briefing, etc.)

        IMPORTANT API LIMITATION:
            IBKR's reqHistoricalNews API IGNORES the date range parameters!
            It always returns the 300 most recent articles regardless of
            start_date/end_date. See docs/data/IBKR_NEWS_API_LIMITATIONS.md
            for details and workarounds.

        Args:
            tickers: List of stock symbols.
            start_date: Start date (IGNORED by IBKR API - see note above).
            end_date: End date (IGNORED by IBKR API - see note above).
            days_back: Days to look back if start_date not specified (IGNORED).
            limit: Max articles per ticker (max 300 due to API limit).
            providers: Provider codes separated by '+' (e.g., 'DJ-N+FLY').
                      If None, uses all available providers.

        Returns:
            List of NewsArticle objects (max 300 per ticker).
        """
        self._ensure_connected()

        # Get available providers if not specified
        if providers is None:
            available = self.get_news_providers()
            if not available:
                logger.warning("No news providers available for this account")
                return []
            providers = '+'.join([p['code'] for p in available])
            logger.info(f"Using providers: {providers}")

        # Set date range (note: IBKR ignores these, but we still need them for the API call)
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        all_articles = []

        for ticker in tickers:
            logger.info(f"Fetching news for {ticker}")

            try:
                contract = self._create_contract(ticker)
                self._ib.qualifyContracts(contract)

                # Convert dates to datetimes for the query
                # Note: IBKR ignores these - always returns 300 most recent
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())

                ticker_articles = self._fetch_news_single_query(
                    contract.conId, providers, start_dt, end_dt, ticker
                )

                if ticker_articles:
                    all_articles.extend(ticker_articles)
                    logger.info(f"  Got {len(ticker_articles)} headlines for {ticker}")
                else:
                    logger.info(f"  No news for {ticker}")

            except Exception as e:
                logger.error(f"Error fetching news for {ticker}: {e}")

        logger.info(f"Fetched {len(all_articles)} total news articles")
        return all_articles

    def fetch_news_article_body(self, provider_code: str, article_id: str) -> Optional[str]:
        """
        Fetch the full body of a news article.

        Args:
            provider_code: Provider code (e.g., 'DJ-N', 'FLY').
            article_id: Article ID from headline.

        Returns:
            Article body text or None.
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            body = self._ib.reqNewsArticle(provider_code, article_id)
            if body:
                return body.articleText
            return None
        except Exception as e:
            logger.error(f"Error fetching article body: {e}")
            return None

    def fetch_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: Optional[date] = None,
        frequency: str = 'daily',
    ) -> List[StockPrice]:
        """
        Fetch historical stock prices from IBKR.

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

        # Map frequency to IBKR bar size
        bar_size_map = {
            'daily': '1 day',
            'weekly': '1 week',
            'monthly': '1 month',
        }
        bar_size = bar_size_map.get(frequency, '1 day')

        all_prices = []
        self._ensure_connected()

        for ticker in tickers:
            logger.info(f"Fetching {frequency} prices for {ticker}")

            try:
                self._rate_limit_wait()

                contract = self._create_contract(ticker)
                self._ib.qualifyContracts(contract)

                duration = self._calculate_duration(start_date, end_date)
                end_datetime = datetime.combine(end_date, datetime.max.time())

                bars = self._ib.reqHistoricalData(
                    contract,
                    endDateTime=end_datetime,
                    durationStr=duration,
                    barSizeSetting=bar_size,
                    whatToShow='TRADES',
                    useRTH=False,  # Include extended hours
                    formatDate=1,
                )

                if bars:
                    for bar in bars:
                        bar_date = bar.date
                        if isinstance(bar_date, datetime):
                            bar_date = bar_date.date()

                        # Filter by date range
                        if start_date <= bar_date <= end_date:
                            all_prices.append(StockPrice(
                                ticker=ticker,
                                date=bar_date,
                                open=bar.open,
                                high=bar.high,
                                low=bar.low,
                                close=bar.close,
                                volume=int(bar.volume),
                                data_source='ibkr',
                            ))

                    logger.info(f"  Got {len(bars)} price records for {ticker}")
                else:
                    logger.warning(f"  No price data for {ticker}")

            except Exception as e:
                logger.error(f"Error fetching prices for {ticker}: {e}")

        logger.info(f"Fetched {len(all_prices)} price records total")
        return all_prices

    def fetch_intraday_prices(
        self,
        ticker: str,
        trade_date: date,
        interval: str = '15 mins',
        include_extended: bool = False,
    ) -> List[IntradayBar]:
        """
        Fetch intraday (minute-level) prices for a single day.

        Args:
            ticker: Stock symbol.
            trade_date: Date to fetch data for.
            interval: Bar interval:
                      '1 min', '5 mins', '15 mins', '30 mins', '1 hour'
            include_extended: Include pre/post market hours.

        Returns:
            List of IntradayBar objects.
        """
        if interval not in self.VALID_INTERVALS:
            raise ValueError(f"Invalid interval '{interval}'. Valid options: {self.VALID_INTERVALS}")

        logger.info(f"Fetching {interval} data for {ticker} on {trade_date}")

        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            self._ib.qualifyContracts(contract)

            end_datetime = datetime.combine(trade_date, datetime.max.time())

            bars = self._ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting=interval,
                whatToShow='TRADES',
                useRTH=not include_extended,
                formatDate=1,
            )

            result = []
            for bar in bars:
                bar_datetime = bar.date
                if isinstance(bar_datetime, date) and not isinstance(bar_datetime, datetime):
                    bar_datetime = datetime.combine(bar_datetime, datetime.min.time())

                result.append(IntradayBar(
                    ticker=ticker,
                    datetime=bar_datetime,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=int(bar.volume),
                    wap=getattr(bar, 'wap', None),
                    bar_count=getattr(bar, 'barCount', None),
                ))

            logger.info(f"  Got {len(result)} intraday bars")
            return result

        except Exception as e:
            logger.error(f"Error fetching intraday data for {ticker}: {e}")
            return []

    def fetch_historical_intraday(
        self,
        tickers: List[str],
        start_date: date,
        end_date: Optional[date] = None,
        interval: str = '15 mins',
        include_extended: bool = False,
    ) -> Dict[str, List[IntradayBar]]:
        """
        Fetch historical intraday data for multiple days.

        IBKR limits historical intraday data requests. For minute bars:
        - Max ~10 days of 1-min bars per request
        - Max ~30 days of 5-min bars per request
        - Longer history for larger intervals

        This method handles chunking automatically.

        Args:
            tickers: List of stock symbols.
            start_date: Start date.
            end_date: End date (default: today).
            interval: Bar interval ('15 mins' recommended for RL training).
            include_extended: Include pre/post market hours.

        Returns:
            Dictionary mapping ticker to list of IntradayBar objects.
        """
        if end_date is None:
            end_date = date.today()

        # Determine chunk size based on interval
        # IBKR historical data limits vary by bar size
        interval_to_max_days = {
            '1 min': 10,
            '5 mins': 30,
            '15 mins': 60,
            '30 mins': 120,
            '1 hour': 365,
        }
        max_days_per_chunk = interval_to_max_days.get(interval, 60)

        result: Dict[str, List[IntradayBar]] = {}

        self._ensure_connected()

        for ticker in tickers:
            logger.info(f"Fetching historical {interval} data for {ticker}")
            result[ticker] = []

            # Process in chunks
            chunk_start = start_date
            while chunk_start <= end_date:
                chunk_end = min(
                    chunk_start + timedelta(days=max_days_per_chunk),
                    end_date
                )

                logger.info(f"  Chunk: {chunk_start} to {chunk_end}")

                try:
                    self._rate_limit_wait()

                    contract = self._create_contract(ticker)
                    self._ib.qualifyContracts(contract)

                    duration_days = (chunk_end - chunk_start).days + 1
                    end_datetime = datetime.combine(chunk_end, datetime.max.time())

                    bars = self._ib.reqHistoricalData(
                        contract,
                        endDateTime=end_datetime,
                        durationStr=f"{duration_days} D",
                        barSizeSetting=interval,
                        whatToShow='TRADES',
                        useRTH=not include_extended,
                        formatDate=1,
                    )

                    for bar in bars:
                        bar_datetime = bar.date
                        if isinstance(bar_datetime, date) and not isinstance(bar_datetime, datetime):
                            bar_datetime = datetime.combine(bar_datetime, datetime.min.time())

                        # Filter by actual date range
                        if start_date <= bar_datetime.date() <= end_date:
                            result[ticker].append(IntradayBar(
                                ticker=ticker,
                                datetime=bar_datetime,
                                open=bar.open,
                                high=bar.high,
                                low=bar.low,
                                close=bar.close,
                                volume=int(bar.volume),
                                wap=getattr(bar, 'wap', None),
                                bar_count=getattr(bar, 'barCount', None),
                            ))

                    logger.info(f"    Retrieved {len(bars)} bars for chunk")

                except Exception as e:
                    logger.error(f"  Error in chunk {chunk_start}-{chunk_end}: {e}")

                chunk_start = chunk_end + timedelta(days=1)

            logger.info(f"  Total: {len(result[ticker])} bars for {ticker}")

        return result

    def get_contract_details(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get contract details for a ticker.

        Returns info like exchange, trading hours, etc.
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            details = self._ib.reqContractDetails(contract)

            if details:
                d = details[0]
                return {
                    'ticker': ticker,
                    'long_name': d.longName,
                    'industry': d.industry,
                    'category': d.category,
                    'subcategory': d.subcategory,
                    'timezone': d.timeZoneId,
                    'trading_hours': d.tradingHours,
                    'liquid_hours': d.liquidHours,
                    'min_tick': d.minTick,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting contract details for {ticker}: {e}")
            return None

    def get_current_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote for a ticker.

        Note: Requires market data subscription for real-time quotes.
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            self._ib.qualifyContracts(contract)

            # Request snapshot
            ticker_data = self._ib.reqMktData(contract, '', True, False)
            self._ib.sleep(2)  # Wait for data

            return {
                'ticker': ticker,
                'bid': ticker_data.bid,
                'ask': ticker_data.ask,
                'last': ticker_data.last,
                'volume': ticker_data.volume,
                'high': ticker_data.high,
                'low': ticker_data.low,
                'close': ticker_data.close,
            }
        except Exception as e:
            logger.error(f"Error getting quote for {ticker}: {e}")
            return None

    def fetch_historical_volatility(
        self,
        ticker: str,
        start_date: date,
        end_date: Optional[date] = None,
        interval: str = '1 day',
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical volatility data.

        Args:
            ticker: Stock symbol.
            start_date: Start date.
            end_date: End date (default: today).
            interval: Bar interval.

        Returns:
            List of volatility data points.
        """
        if end_date is None:
            end_date = date.today()

        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            self._ib.qualifyContracts(contract)

            duration = self._calculate_duration(start_date, end_date)
            end_datetime = datetime.combine(end_date, datetime.max.time())

            bars = self._ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr=duration,
                barSizeSetting=interval,
                whatToShow='HISTORICAL_VOLATILITY',
                useRTH=True,
                formatDate=1,
            )

            result = []
            for bar in bars:
                bar_date = bar.date
                if isinstance(bar_date, datetime):
                    bar_date = bar_date.date()

                result.append({
                    'ticker': ticker,
                    'date': bar_date,
                    'volatility': bar.close,  # HV is in the close field
                })

            logger.info(f"Fetched {len(result)} volatility records for {ticker}")
            return result

        except Exception as e:
            logger.error(f"Error fetching volatility for {ticker}: {e}")
            return []

    def fetch_fundamental_ratios(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch fundamental ratios (P/E, EPS, etc.) using generic tick 258.

        Returns:
            Dictionary of fundamental ratios or None.
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            self._ib.qualifyContracts(contract)

            # Request fundamental ratios with generic tick 258
            ticker_data = self._ib.reqMktData(contract, '258', False, False)
            self._ib.sleep(3)  # Wait for data

            if ticker_data.fundamentalRatios:
                ratios = ticker_data.fundamentalRatios
                return {
                    'ticker': ticker,
                    'pe_ratio': getattr(ratios, 'PEEXCLXOR', None),
                    'eps': getattr(ratios, 'AEPSNORM', None),
                    'price_to_book': getattr(ratios, 'PRICE2BK', None),
                    'price_to_sales': getattr(ratios, 'PRICE2SAL', None),
                    'dividend_yield': getattr(ratios, 'YIELD', None),
                    'beta': getattr(ratios, 'BETA', None),
                    'market_cap': getattr(ratios, 'MKTCAP', None),
                    'revenue': getattr(ratios, 'TTMREV', None),
                    'gross_margin': getattr(ratios, 'GROSMGN', None),
                    'roe': getattr(ratios, 'TTMROEPCT', None),
                }
            return None

        except Exception as e:
            logger.error(f"Error fetching fundamental ratios for {ticker}: {e}")
            return None
        finally:
            # Cancel market data subscription
            try:
                self._ib.cancelMktData(contract)
            except:
                pass

    def fetch_dividends(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch dividend information using generic tick 456.

        Returns:
            Dictionary with dividend info or None.
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            self._ib.qualifyContracts(contract)

            # Request dividends with generic tick 456
            ticker_data = self._ib.reqMktData(contract, '456', False, False)
            self._ib.sleep(2)

            if ticker_data.dividends:
                # Format: "past12Months,next12Months,nextDate,nextAmount"
                parts = ticker_data.dividends.split(',')
                return {
                    'ticker': ticker,
                    'past_12_months': float(parts[0]) if len(parts) > 0 and parts[0] else None,
                    'next_12_months': float(parts[1]) if len(parts) > 1 and parts[1] else None,
                    'next_date': parts[2] if len(parts) > 2 else None,
                    'next_amount': float(parts[3]) if len(parts) > 3 and parts[3] else None,
                }
            return None

        except Exception as e:
            logger.error(f"Error fetching dividends for {ticker}: {e}")
            return None
        finally:
            try:
                self._ib.cancelMktData(contract)
            except:
                pass

    def fetch_short_borrow_rate(
        self,
        ticker: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical short borrow fee rate.

        Useful for understanding short selling costs.

        Args:
            ticker: Stock symbol.
            start_date: Start date.
            end_date: End date (default: today).

        Returns:
            List of fee rate data points.
        """
        if end_date is None:
            end_date = date.today()

        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            self._ib.qualifyContracts(contract)

            duration = self._calculate_duration(start_date, end_date)
            end_datetime = datetime.combine(end_date, datetime.max.time())

            bars = self._ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr=duration,
                barSizeSetting='1 day',
                whatToShow='FEE_RATE',
                useRTH=True,
                formatDate=1,
            )

            result = []
            for bar in bars:
                bar_date = bar.date
                if isinstance(bar_date, datetime):
                    bar_date = bar_date.date()

                result.append({
                    'ticker': ticker,
                    'date': bar_date,
                    'fee_rate': bar.close,  # Fee rate in the close field
                })

            logger.info(f"Fetched {len(result)} fee rate records for {ticker}")
            return result

        except Exception as e:
            logger.error(f"Error fetching fee rate for {ticker}: {e}")
            return []

    def fetch_adjusted_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: Optional[date] = None,
    ) -> List[StockPrice]:
        """
        Fetch split and dividend adjusted historical prices.

        Uses ADJUSTED_LAST data type (requires TWS 967+).

        Args:
            tickers: List of stock symbols.
            start_date: Start date.
            end_date: End date (default: today).

        Returns:
            List of adjusted StockPrice objects.
        """
        if end_date is None:
            end_date = date.today()

        all_prices = []
        self._ensure_connected()

        for ticker in tickers:
            logger.info(f"Fetching adjusted prices for {ticker}")

            try:
                self._rate_limit_wait()

                contract = self._create_contract(ticker)
                self._ib.qualifyContracts(contract)

                duration = self._calculate_duration(start_date, end_date)
                end_datetime = datetime.combine(end_date, datetime.max.time())

                bars = self._ib.reqHistoricalData(
                    contract,
                    endDateTime=end_datetime,
                    durationStr=duration,
                    barSizeSetting='1 day',
                    whatToShow='ADJUSTED_LAST',
                    useRTH=True,
                    formatDate=1,
                )

                if bars:
                    for bar in bars:
                        bar_date = bar.date
                        if isinstance(bar_date, datetime):
                            bar_date = bar_date.date()

                        if start_date <= bar_date <= end_date:
                            all_prices.append(StockPrice(
                                ticker=ticker,
                                date=bar_date,
                                open=bar.open,
                                high=bar.high,
                                low=bar.low,
                                close=bar.close,
                                volume=int(bar.volume),
                                adj_close=bar.close,  # Already adjusted
                                data_source='ibkr_adjusted',
                            ))

                    logger.info(f"  Got {len(bars)} adjusted prices for {ticker}")

            except Exception as e:
                logger.error(f"Error fetching adjusted prices for {ticker}: {e}")

        return all_prices

    # =========================================================================
    # OPRA - Option Chain and Quote Methods (requires OPRA subscription $1.50/month)
    # =========================================================================

    def get_option_chain_params(
        self,
        ticker: str,
        exchange: str = '',
    ) -> List[OptionChainParams]:
        """
        Get option chain parameters (expirations, strikes) for a stock.

        Requires OPRA subscription ($1.50/month, waived if commissions > $20).

        Args:
            ticker: Underlying stock symbol.
            exchange: Exchange filter ('' for all exchanges).

        Returns:
            List of OptionChainParams for each exchange.

        Example:
            >>> ibkr = IBKRDataSource()
            >>> chains = ibkr.get_option_chain_params('AAPL')
            >>> for c in chains[:3]:
            ...     print(f"{c.exchange}: {len(c.expirations)} expirations, {len(c.strikes)} strikes")
            CBOE: 21 expirations, 113 strikes
            ISE: 21 expirations, 113 strikes
            PHLX: 21 expirations, 113 strikes
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            contract = self._create_contract(ticker)
            self._ib.qualifyContracts(contract)

            chains = self._ib.reqSecDefOptParams(
                contract.symbol,
                exchange,
                contract.secType,
                contract.conId,
            )

            result = []
            for chain in chains:
                result.append(OptionChainParams(
                    underlying=ticker,
                    exchange=chain.exchange,
                    expirations=sorted(list(chain.expirations)),
                    strikes=sorted(list(chain.strikes)),
                    multiplier=chain.multiplier,
                ))

            logger.info(f"Got {len(result)} option chains for {ticker}")
            return result

        except Exception as e:
            logger.error(f"Error getting option chain for {ticker}: {e}")
            return []

    def get_option_expirations(self, ticker: str) -> List[str]:
        """
        Get all available option expiration dates for a stock.

        Args:
            ticker: Underlying stock symbol.

        Returns:
            Sorted list of expiration dates in YYYYMMDD format.
        """
        chains = self.get_option_chain_params(ticker)
        if not chains:
            return []

        # Use SMART exchange if available, otherwise first
        chain = next((c for c in chains if c.exchange == 'SMART'), chains[0])
        return chain.expirations

    def get_option_strikes(
        self,
        ticker: str,
        near_price: Optional[float] = None,
        range_pct: float = 0.1,
    ) -> List[float]:
        """
        Get available option strikes for a stock.

        Args:
            ticker: Underlying stock symbol.
            near_price: Filter strikes near this price (e.g., current stock price).
            range_pct: Range as percentage (default 10% above/below near_price).

        Returns:
            Sorted list of strike prices.
        """
        chains = self.get_option_chain_params(ticker)
        if not chains:
            return []

        chain = next((c for c in chains if c.exchange == 'SMART'), chains[0])
        strikes = chain.strikes

        if near_price is not None:
            low = near_price * (1 - range_pct)
            high = near_price * (1 + range_pct)
            strikes = [s for s in strikes if low <= s <= high]

        return strikes

    def _create_option_contract(
        self,
        ticker: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = 'SMART',
    ) -> Option:
        """
        Create an option contract.

        Args:
            ticker: Underlying stock symbol.
            expiry: Expiration date (YYYYMMDD format).
            strike: Strike price.
            right: 'C' for Call, 'P' for Put.
            exchange: Exchange (default SMART).

        Returns:
            Option contract object.
        """
        return Option(ticker, expiry, strike, right, exchange)

    def get_option_quote(
        self,
        ticker: str,
        expiry: str,
        strike: float,
        right: str,
        delayed: bool = True,
        include_greeks: bool = True,
        timeout: float = 5.0,
    ) -> Optional[OptionQuote]:
        """
        Get option quote (bid, ask, last) and optionally Greeks.

        Requires OPRA subscription ($1.50/month).

        Note on data types:
        - delayed=True: Uses 15-minute delayed data (included with OPRA)
        - delayed=False: Requires additional subscription (underlying stock data)

        Args:
            ticker: Underlying stock symbol.
            expiry: Expiration date (YYYYMMDD format).
            strike: Strike price.
            right: 'C' for Call, 'P' for Put.
            delayed: Use delayed data (True) or real-time (False).
            include_greeks: Request Greeks (requires option pricing model).
            timeout: Seconds to wait for data.

        Returns:
            OptionQuote object or None if contract not found.

        Example:
            >>> ibkr = IBKRDataSource()
            >>> quote = ibkr.get_option_quote('AAPL', '20260123', 230.0, 'C')
            >>> print(f"Bid: {quote.bid}, Ask: {quote.ask}")
            Bid: 15.5, Ask: 17.65
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            # Set market data type (3 = delayed, 1 = real-time)
            self._ib.reqMarketDataType(3 if delayed else 1)

            # Create and qualify option contract
            opt = self._create_option_contract(ticker, expiry, strike, right)
            qualified = self._ib.qualifyContracts(opt)

            if not qualified:
                logger.warning(f"Could not qualify option: {ticker} {expiry} {strike} {right}")
                return None

            # Request market data with optional Greeks (tick 106)
            generic_ticks = '106' if include_greeks else ''
            ticker_data = self._ib.reqMktData(opt, generic_ticks, False, False)
            self._ib.sleep(timeout)

            # Build result
            result = OptionQuote(
                underlying=ticker,
                expiry=expiry,
                strike=strike,
                right=right,
                con_id=opt.conId,
                bid=ticker_data.bid if not math.isnan(ticker_data.bid) else None,
                ask=ticker_data.ask if not math.isnan(ticker_data.ask) else None,
                last=ticker_data.last if not math.isnan(ticker_data.last) else None,
                close=ticker_data.close if not math.isnan(ticker_data.close) else None,
                volume=ticker_data.volume if ticker_data.volume and ticker_data.volume > 0 else None,
            )

            # Extract Greeks if available
            if include_greeks and ticker_data.modelGreeks:
                g = ticker_data.modelGreeks
                result.delta = g.delta
                result.gamma = g.gamma
                result.theta = g.theta
                result.vega = g.vega
                result.implied_vol = g.impliedVol

            # Cancel subscription
            self._ib.cancelMktData(opt)

            return result

        except Exception as e:
            logger.error(f"Error getting option quote: {e}")
            return None

    def get_option_chain_quotes(
        self,
        ticker: str,
        expiry: str,
        strikes: Optional[List[float]] = None,
        right: str = 'C',
        delayed: bool = True,
        max_strikes: int = 10,
    ) -> List[OptionQuote]:
        """
        Get quotes for multiple strikes in an option chain.

        Args:
            ticker: Underlying stock symbol.
            expiry: Expiration date (YYYYMMDD format).
            strikes: List of strikes to quote. If None, uses ATM +/- range.
            right: 'C' for Calls, 'P' for Puts.
            delayed: Use delayed data.
            max_strikes: Maximum number of strikes to quote.

        Returns:
            List of OptionQuote objects.
        """
        if strikes is None:
            # Get current price and find nearby strikes
            quote = self.get_current_quote(ticker)
            if quote and quote.get('last'):
                price = quote['last']
                all_strikes = self.get_option_strikes(ticker, near_price=price)
                strikes = all_strikes[:max_strikes]
            else:
                logger.warning(f"Could not get price for {ticker} to determine strikes")
                return []

        results = []
        for strike in strikes[:max_strikes]:
            quote = self.get_option_quote(ticker, expiry, strike, right, delayed)
            if quote:
                results.append(quote)
            time.sleep(0.2)  # Small delay between requests

        return results

    def get_option_contract_details(
        self,
        ticker: str,
        expiry: str,
        strike: float,
        right: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed contract information for an option.

        Args:
            ticker: Underlying stock symbol.
            expiry: Expiration date (YYYYMMDD format).
            strike: Strike price.
            right: 'C' for Call, 'P' for Put.

        Returns:
            Dictionary with contract details or None.
        """
        self._ensure_connected()
        self._rate_limit_wait()

        try:
            opt = self._create_option_contract(ticker, expiry, strike, right)
            self._ib.qualifyContracts(opt)

            details = self._ib.reqContractDetails(opt)

            if details:
                d = details[0]
                return {
                    'underlying': ticker,
                    'expiry': expiry,
                    'strike': strike,
                    'right': right,
                    'con_id': opt.conId,
                    'local_symbol': opt.localSymbol,
                    'multiplier': opt.multiplier,
                    'trading_class': opt.tradingClass,
                    'long_name': d.longName,
                    'min_tick': d.minTick,
                    'valid_exchanges': d.validExchanges,
                    'market_name': d.marketName,
                }
            return None

        except Exception as e:
            logger.error(f"Error getting option contract details: {e}")
            return None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def __del__(self):
        """Cleanup on deletion."""
        self.disconnect()