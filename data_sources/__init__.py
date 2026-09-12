"""
Data types and current provider sources for ArkScope.

Use source-specific constructors directly. Finnhub news/calendar and EODHD
lifecycle status use their dedicated collector/client/transport modules.
"""

from .base import BaseDataSource, NewsArticle, StockPrice, SECFiling
from .sec_edgar_source import SECEdgarDataSource
from .polygon_source import PolygonDataSource

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
    'SECEdgarDataSource',
    'PolygonDataSource',
    'IBKRDataSource',
    'IntradayBar',
    'OptionChainParams',
    'OptionQuote',
    'OptionFilter',
    'OptionHistoricalBar',
    'ScannerResult',
]

__version__ = '1.2.0'  # Added ScannerResult, market scanner methods
