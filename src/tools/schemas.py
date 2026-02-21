"""
Pydantic I/O models shared across DAL, HTTP API, and Agent layers.

These schemas define the contract between all layers. Tool functions
return these models, the API serializes them, and Agents parse them.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Enums
# ============================================================

class NewsSource(str, Enum):
    """Available news data sources."""
    IBKR = "ibkr"
    POLYGON = "polygon"
    FINNHUB = "finnhub"
    FNSPID = "fnspid"
    AUTO = "auto"  # Pick best available


class PriceInterval(str, Enum):
    """Supported price bar intervals."""
    MIN_15 = "15min"
    HOURLY = "1h"
    DAILY = "1d"


class OptionRight(str, Enum):
    CALL = "C"
    PUT = "P"


# ============================================================
# News
# ============================================================

class NewsArticle(BaseModel):
    """Single news article with scores."""
    date: str = Field(description="Publication date (YYYY-MM-DD)")
    ticker: str
    title: str
    source: str = Field(description="News source (ibkr, polygon, etc.)")
    url: Optional[str] = None
    publisher: Optional[str] = None
    sentiment_score: Optional[float] = Field(None, description="1-5 sentiment score")
    risk_score: Optional[float] = Field(None, description="1-5 risk score")
    description: Optional[str] = None


class NewsQueryResult(BaseModel):
    """Result of a news query."""
    ticker: str
    count: int
    articles: List[NewsArticle]
    source_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of articles per source"
    )
    query_days: int = Field(description="Number of days queried")


# ============================================================
# Prices
# ============================================================

class PriceBar(BaseModel):
    """Single OHLCV price bar."""
    datetime: str = Field(description="Bar timestamp (ISO format)")
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceQueryResult(BaseModel):
    """Result of a price query."""
    ticker: str
    interval: str
    count: int
    bars: List[PriceBar]
    date_range: Optional[str] = Field(
        None, description="e.g. '2026-01-01 to 2026-01-30'"
    )


# ============================================================
# Options / IV
# ============================================================

class IVHistoryPoint(BaseModel):
    """Single day IV record."""
    date: str
    atm_iv: float
    hv_30d: Optional[float] = None
    vrp: Optional[float] = None
    spot_price: Optional[float] = None
    num_quotes: Optional[int] = None


class IVAnalysisResult(BaseModel):
    """Full IV analysis for a ticker."""
    ticker: str
    current_iv: Optional[float] = Field(None, description="Latest ATM IV")
    hv_30d: Optional[float] = Field(None, description="30-day historical vol")
    vrp: Optional[float] = Field(None, description="Volatility risk premium (IV - HV)")
    iv_rank: Optional[float] = Field(None, description="IV rank (0-100)")
    iv_percentile: Optional[float] = Field(None, description="IV percentile (0-100)")
    spot_price: Optional[float] = None
    history_days: int = Field(0, description="Number of IV history records")
    signal: Optional[str] = Field(
        None,
        description="Trading signal: HIGH_IV_SELL, LOW_IV_BUY, NEUTRAL"
    )


class MispricingResult(BaseModel):
    """Option mispricing detection result."""
    underlying: str
    expiry: str
    strike: float
    right: str = Field(description="C or P")
    theoretical_price: float
    market_mid: float
    mispricing_pct: float = Field(description="(theo - market) / market * 100")
    signal: str = Field(description="UNDERPRICED, OVERPRICED, or FAIR")
    confidence: float = Field(description="Signal confidence 0-1")
    model: str = Field(default="american", description="Pricing model used")
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None


# ============================================================
# Trading Signals
# ============================================================

class TradingSignal(BaseModel):
    """Synthesized multi-factor trading signal."""
    ticker: Optional[str] = None
    sector: Optional[str] = None
    action: str = Field(description="BUY, SELL, HOLD, WATCH")
    confidence: float = Field(description="0-1 confidence score")
    composite_score: float = Field(description="Weighted composite score")
    risk_level: int = Field(description="1-5 risk level")
    reasoning: str = Field(description="Human-readable explanation")
    factors: Optional[Dict[str, float]] = Field(
        None, description="Individual factor scores"
    )


# ============================================================
# Fundamentals
# ============================================================

class FinancialStatement(BaseModel):
    """Single period financial statement (income, balance sheet, or cash flow)."""
    report_period: str = Field(description="Period end date YYYY-MM-DD")
    fiscal_period: Optional[str] = Field(None, description="e.g. 2025-Q3")
    period_type: str = Field(description="annual or quarterly")
    data: Dict[str, Optional[float]] = Field(
        description="Metric name → value (e.g. revenue, net_income)"
    )


class FundamentalsResult(BaseModel):
    """Fundamental analysis result for a ticker."""
    ticker: str
    snapshot_date: Optional[str] = None
    data_source: str = Field(default="none", description="ibkr, sec_edgar, or none")
    # Key metrics (derived from IBKR snapshot or SEC)
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    ps_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    # Margins
    gross_margin: Optional[float] = Field(None, description="Gross profit / revenue")
    operating_margin: Optional[float] = Field(None, description="Operating income / revenue")
    net_margin: Optional[float] = Field(None, description="Net income / revenue")
    # Cash
    free_cash_flow: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    total_debt: Optional[float] = None
    # SEC EDGAR structured financial statements
    income_statements: Optional[List[FinancialStatement]] = Field(
        None, description="Recent income statements (newest first)"
    )
    balance_sheet: Optional[List[FinancialStatement]] = Field(
        None, description="Recent balance sheets (newest first)"
    )
    cash_flow_statements: Optional[List[FinancialStatement]] = Field(
        None, description="Recent cash flow statements (newest first)"
    )
    # Raw snapshot for detailed access
    snapshot: Optional[dict] = Field(
        None, description="Full raw snapshot data (IBKR)"
    )


# ============================================================
# SEC Filings
# ============================================================

class SECFiling(BaseModel):
    """SEC filing metadata (not full text)."""
    ticker: str
    filing_type: str = Field(description="10-K, 10-Q, 8-K, etc.")
    filed_date: str
    period_of_report: Optional[str] = None
    url: Optional[str] = None
    accession_number: Optional[str] = None
    description: Optional[str] = None


# ============================================================
# Watchlist / Config
# ============================================================

class WatchlistInfo(BaseModel):
    """Watchlist ticker with metadata."""
    ticker: str
    group: str = Field(description="e.g. core_holdings, interested, theme:AI")
    priority: str = Field(default="medium", description="high, medium, low")


class WatchlistResult(BaseModel):
    """Watchlist query result."""
    tickers: List[str]
    details: List[WatchlistInfo]
    sectors: Optional[Dict[str, List[str]]] = None


# ============================================================
# Agent Query (for POST /query)
# ============================================================

class QueryRequest(BaseModel):
    """Agent query request."""
    question: str
    provider: str = Field(default="openai", description="openai or anthropic")
    model: Optional[str] = Field(None, description="Override default model")


class QueryResponse(BaseModel):
    """Agent query response."""
    answer: str
    tools_used: List[str] = Field(default_factory=list)
    provider: str
    model: str