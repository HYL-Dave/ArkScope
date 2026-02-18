"""
Unified Data Sources Module for MindfulRL-Intraday

This module provides a unified interface for fetching financial data from
multiple sources (Tiingo, Finnhub, Financial Datasets, etc.)

Usage:
    from data_sources import TiingoDataSource, get_data_source

    # Direct usage
    tiingo = TiingoDataSource()
    news = tiingo.fetch_news(['AAPL', 'MSFT'], days_back=7)

    # Factory pattern
    source = get_data_source('tiingo')
    news = source.fetch_news(['AAPL'], days_back=7)
"""

from .base import BaseDataSource, NewsArticle, StockPrice, SECFiling
from .tiingo_source import TiingoDataSource
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
    'TiingoDataSource',
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