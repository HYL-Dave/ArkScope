"""
Base classes and data models for unified data source interface.

This module defines the abstract interface that all data sources must implement,
plus common data structures used across all sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Optional, Iterator, Any
from enum import Enum
import hashlib


class DataSourceType(Enum):
    """Supported data source types."""
    TIINGO = "tiingo"
    FINNHUB = "finnhub"
    FINANCIAL_DATASETS = "financial_datasets"
    SEC_EDGAR = "sec_edgar"
    POLYGON = "polygon"
    ALPHA_VANTAGE = "alpha_vantage"
    EODHD = "eodhd"
    YAHOO = "yahoo"
    IBKR = "ibkr"
    # Note: Quiver removed - Enterprise only. Congressional data via Finnhub Fundamental-1


@dataclass
class NewsArticle:
    """Standardized news article structure."""

    # Required fields
    ticker: str
    title: str
    published_date: datetime
    source: str

    # Content fields
    description: str = ""
    content: str = ""
    url: str = ""

    # Metadata
    author: str = ""
    tags: List[str] = field(default_factory=list)
    related_tickers: List[str] = field(default_factory=list)

    # Source tracking
    data_source: str = ""  # Which API this came from
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Original response

    # Processing fields (filled by LLM later)
    sentiment_score: Optional[float] = None  # -1 to 1 or 1-5
    risk_score: Optional[float] = None  # 1-5
    summary: str = ""

    # Deduplication
    article_hash: str = ""

    def __post_init__(self):
        """Generate hash for deduplication."""
        if not self.article_hash:
            hash_input = f"{self.ticker}|{self.title}|{self.published_date.date()}"
            self.article_hash = hashlib.md5(hash_input.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            'Date': self.published_date.strftime('%Y-%m-%d'),
            'Stock_symbol': self.ticker,
            'Article_title': self.title,
            'Article': self.content or self.description,
            'Url': self.url,
            'Publisher': self.source,
            'Author': self.author,
            'data_source': self.data_source,
            'sentiment_score': self.sentiment_score,
            'risk_score': self.risk_score,
            'summary': self.summary,
            'article_hash': self.article_hash,
        }


@dataclass
class StockPrice:
    """Standardized stock price structure."""

    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int

    # Optional fields
    adj_open: Optional[float] = None
    adj_high: Optional[float] = None
    adj_low: Optional[float] = None
    adj_close: Optional[float] = None
    adj_volume: Optional[int] = None
    dividend: Optional[float] = None
    split_factor: Optional[float] = None

    # Source tracking
    data_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            'ticker': self.ticker,
            'date': self.date.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'adj_close': self.adj_close,
            'data_source': self.data_source,
        }


@dataclass
class SECFiling:
    """Standardized SEC filing structure."""

    ticker: str
    filing_type: str  # 10-K, 10-Q, 8-K, etc.
    filing_date: date
    period_end: Optional[date] = None

    # Document info
    accession_number: str = ""
    url: str = ""

    # Content
    title: str = ""
    description: str = ""
    content: str = ""  # Extracted text content

    # Source tracking
    data_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            'ticker': self.ticker,
            'filing_type': self.filing_type,
            'filing_date': self.filing_date.isoformat(),
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'accession_number': self.accession_number,
            'url': self.url,
            'title': self.title,
            'data_source': self.data_source,
        }


class BaseDataSource(ABC):
    """
    Abstract base class for all data sources.

    All data source implementations must inherit from this class and
    implement the required abstract methods.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize data source.

        Args:
            api_key: API key for the service. If None, will try to load from environment.
        """
        self.api_key = api_key
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[datetime] = None

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this data source."""
        pass

    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """Return the type of this data source."""
        pass

    @property
    @abstractmethod
    def supports_news(self) -> bool:
        """Whether this source supports news fetching."""
        pass

    @property
    @abstractmethod
    def supports_prices(self) -> bool:
        """Whether this source supports price fetching."""
        pass

    @property
    @abstractmethod
    def supports_sec_filings(self) -> bool:
        """Whether this source supports SEC filings."""
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validate that the API credentials are working.

        Returns:
            True if credentials are valid, False otherwise.
        """
        pass

    @abstractmethod
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

        Args:
            tickers: List of stock symbols to fetch news for.
            start_date: Start date for news search.
            end_date: End date for news search.
            days_back: If start_date is None, look back this many days from end_date.
            limit: Maximum number of articles to return.

        Returns:
            List of NewsArticle objects.
        """
        pass

    @abstractmethod
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
            tickers: List of stock symbols.
            start_date: Start date for price data.
            end_date: End date (default: today).
            frequency: Data frequency ('daily', 'weekly', 'monthly').

        Returns:
            List of StockPrice objects.
        """
        pass

    def fetch_sec_filings(
        self,
        tickers: List[str],
        filing_types: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SECFiling]:
        """
        Fetch SEC filings for given tickers.

        Default implementation raises NotImplementedError.
        Override in subclasses that support SEC filings.
        """
        raise NotImplementedError(f"{self.source_name} does not support SEC filings")

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.

        Returns:
            Dictionary with rate limit information.
        """
        return {
            'remaining': self._rate_limit_remaining,
            'reset_time': self._rate_limit_reset,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source_name='{self.source_name}'>"