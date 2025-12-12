"""
Data Source Factory Module.

Provides factory functions to create and manage data sources.
"""

from typing import Dict, List, Optional, Type
import os
import logging

from .base import BaseDataSource, DataSourceType
from .tiingo_source import TiingoDataSource
from .finnhub_source import FinnhubDataSource
from .sec_edgar_source import SECEdgarDataSource
from .polygon_source import PolygonDataSource
from .alpha_vantage_source import AlphaVantageDataSource

logger = logging.getLogger(__name__)

# Registry of available data sources
_SOURCE_REGISTRY: Dict[str, Type[BaseDataSource]] = {
    'tiingo': TiingoDataSource,
    'finnhub': FinnhubDataSource,
    'sec_edgar': SECEdgarDataSource,
    'polygon': PolygonDataSource,
    'alpha_vantage': AlphaVantageDataSource,
    # Future sources can be added here:
    # 'financial_datasets': FinancialDatasetsSource,
}


def get_data_source(
    source_name: str,
    api_key: Optional[str] = None,
    **kwargs,
) -> BaseDataSource:
    """
    Factory function to create a data source instance.

    Args:
        source_name: Name of the data source ('tiingo', 'finnhub', etc.)
        api_key: Optional API key (will use env var if not provided)
        **kwargs: Additional arguments to pass to the source constructor

    Returns:
        An instance of the requested data source.

    Raises:
        ValueError: If the source name is not recognized.

    Example:
        >>> source = get_data_source('tiingo')
        >>> news = source.fetch_news(['AAPL'], days_back=7)
    """
    source_name_lower = source_name.lower()

    if source_name_lower not in _SOURCE_REGISTRY:
        available = ', '.join(_SOURCE_REGISTRY.keys())
        raise ValueError(
            f"Unknown data source: '{source_name}'. "
            f"Available sources: {available}"
        )

    source_class = _SOURCE_REGISTRY[source_name_lower]

    # SEC EDGAR doesn't need API key
    if source_name_lower == 'sec_edgar':
        return source_class(**kwargs)

    # Try to get API key from environment if not provided
    if api_key is None:
        env_key_names = {
            'tiingo': 'TIINGO_API_KEY',
            'finnhub': 'FINNHUB_API_KEY',
            'polygon': 'POLYGON_API_KEY',
            'alpha_vantage': 'ALPHA_VANTAGE_API_KEY',
            'financial_datasets': 'FINANCIAL_DATASETS_API_KEY',
        }
        env_key = env_key_names.get(source_name_lower)
        if env_key:
            api_key = os.environ.get(env_key)

    return source_class(api_key=api_key, **kwargs)


def list_available_sources() -> List[str]:
    """
    List all available data source names.

    Returns:
        List of source names that can be used with get_data_source().
    """
    return list(_SOURCE_REGISTRY.keys())


def register_source(name: str, source_class: Type[BaseDataSource]) -> None:
    """
    Register a new data source class.

    This allows extending the factory with custom data sources.

    Args:
        name: Name to register the source under.
        source_class: The data source class (must inherit from BaseDataSource).
    """
    if not issubclass(source_class, BaseDataSource):
        raise TypeError(
            f"source_class must inherit from BaseDataSource, "
            f"got {source_class.__name__}"
        )
    _SOURCE_REGISTRY[name.lower()] = source_class
    logger.info(f"Registered data source: {name}")


def get_multi_source_news(
    tickers: List[str],
    sources: Optional[List[str]] = None,
    days_back: int = 7,
    deduplicate: bool = True,
) -> List:
    """
    Fetch news from multiple sources and optionally deduplicate.

    Args:
        tickers: List of stock symbols.
        sources: List of source names to use. If None, uses all available.
        days_back: Number of days to look back.
        deduplicate: Whether to remove duplicate articles.

    Returns:
        Combined list of NewsArticle objects from all sources.
    """
    if sources is None:
        sources = list_available_sources()

    all_articles = []
    seen_hashes = set()

    for source_name in sources:
        try:
            source = get_data_source(source_name)
            if source.supports_news:
                articles = source.fetch_news(tickers, days_back=days_back)
                for article in articles:
                    if deduplicate:
                        if article.article_hash not in seen_hashes:
                            seen_hashes.add(article.article_hash)
                            all_articles.append(article)
                    else:
                        all_articles.append(article)
                logger.info(f"Fetched {len(articles)} articles from {source_name}")
        except Exception as e:
            logger.warning(f"Failed to fetch from {source_name}: {e}")

    return all_articles