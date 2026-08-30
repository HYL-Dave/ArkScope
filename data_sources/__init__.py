"""
Unified Data Sources Module for ArkScope

This module provides a unified interface for fetching financial data from
multiple sources (Finnhub, SEC EDGAR, Massive, etc.)

Usage:
    from data_sources import FinnhubDataSource, get_data_source

    # Direct usage
    finnhub = FinnhubDataSource()
    news = finnhub.fetch_news(['AAPL', 'MSFT'], days_back=7)

    # Factory pattern
    source = get_data_source('finnhub')
    news = source.fetch_news(['AAPL'], days_back=7)
"""

from .base import BaseDataSource, NewsArticle, StockPrice, SECFiling
from .finnhub_source import FinnhubDataSource
from .sec_edgar_source import SECEdgarDataSource
from .polygon_source import PolygonDataSource
from .alpha_vantage_source import AlphaVantageDataSource
from .eodhd_source import EODHDDataSource
from .source_factory import get_data_source, list_available_sources

# IBKR requires ib_insync, import conditionally
try:
    from .ibkr_source import (
        IBKRDataSource,
        IntradayBar,
        OptionChainParams,
        OptionQuote,
        OptionFilter,
        OptionHistoricalBar,
        ScannerResult,
    )
    _HAS_IBKR = True
except (ImportError, RuntimeError):
    _HAS_IBKR = False
    IBKRDataSource = None
    IntradayBar = None
    OptionChainParams = None
    OptionQuote = None
    OptionFilter = None
    OptionHistoricalBar = None
    ScannerResult = None

__all__ = [
    'BaseDataSource',
    'NewsArticle',
    'StockPrice',
    'SECFiling',
    'FinnhubDataSource',
    'SECEdgarDataSource',
    'PolygonDataSource',
    'AlphaVantageDataSource',
    'EODHDDataSource',
    'IBKRDataSource',
    'IntradayBar',
    'OptionChainParams',
    'OptionQuote',
    'OptionFilter',
    'OptionHistoricalBar',
    'ScannerResult',
    'get_data_source',
    'list_available_sources',
]

__version__ = '1.2.0'  # Added ScannerResult, market scanner methods
