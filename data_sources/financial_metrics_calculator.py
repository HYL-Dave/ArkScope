#!/usr/bin/env python3
"""
Financial Metrics Calculator - Complete 39 metrics matching Financial Datasets API.

This module calculates all 39 financial metrics that Financial Datasets API provides,
using free data from SEC EDGAR (via sec_edgar_financials.py) and IBKR fundamentals.

Usage:
    from data_sources.financial_metrics_calculator import FinancialMetricsCalculator

    calc = FinancialMetricsCalculator('AAPL')
    metrics = calc.get_all_metrics()

    # Or get specific categories
    profitability = calc.get_profitability_metrics()
    valuation = calc.get_valuation_metrics()

Metrics Categories (39 total):
    - Valuation (9): market_cap, enterprise_value, P/E, P/B, P/S, EV/EBITDA, etc.
    - Profitability (6): gross_margin, operating_margin, net_margin, ROE, ROA, ROIC
    - Efficiency (6): asset_turnover, inventory_turnover, receivables_turnover, etc.
    - Liquidity (4): current_ratio, quick_ratio, cash_ratio, operating_cash_flow_ratio
    - Leverage (3): debt_to_equity, debt_to_assets, interest_coverage
    - Growth (7): revenue_growth, earnings_growth, eps_growth, fcf_growth, etc.
    - Per-share (4): EPS, book_value_per_share, fcf_per_share, payout_ratio

Data Sources:
    - SEC EDGAR: Financial statements (Income, Balance Sheet, Cash Flow)
    - IBKR Fundamentals: Market price, shares outstanding, market cap, EV
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from data_sources.sec_edgar_financials import SECEdgarFinancials

logger = logging.getLogger(__name__)


def _get_current_price_ibkr(ticker: str) -> Optional[float]:
    """
    Get current stock price from IBKR price data in data/prices/.

    Looks for price data in order of preference:
    1. data/prices/15min/{ticker}_15min_*.csv (most recent)
    2. data/prices/hourly/{ticker}_hourly_*.csv (fallback)

    Returns the latest close price from the most recent file.
    """
    project_root = Path(__file__).parent.parent
    price_dirs = [
        project_root / "data" / "prices" / "15min",
        project_root / "data" / "prices" / "hourly",
    ]

    for price_dir in price_dirs:
        if not price_dir.exists():
            continue

        # Find all files for this ticker
        patterns = [f"{ticker}_15min_*.csv", f"{ticker}_hourly_*.csv"]
        files = []
        for pattern in patterns:
            files.extend(sorted(price_dir.glob(pattern), reverse=True))

        if files:
            # Read the most recent file
            latest_file = files[0]
            try:
                import pandas as pd
                # Read CSV - try with header first, fallback to no header
                try:
                    df = pd.read_csv(latest_file)
                    if 'close' in df.columns:
                        latest_price = float(df['close'].iloc[-1])
                    else:
                        # No header, use positional index
                        df = pd.read_csv(latest_file, header=None)
                        latest_price = float(df.iloc[-1, 4])  # close is column 4
                except:
                    # Fallback: no header
                    df = pd.read_csv(latest_file, header=None)
                    latest_price = float(df.iloc[-1, 4])

                if latest_price > 0:
                    logger.info(f"Got price ${latest_price:.2f} for {ticker} from {latest_file.name}")
                    return latest_price
            except Exception as e:
                logger.warning(f"Error reading price file {latest_file}: {e}")
                continue

    logger.warning(f"No IBKR price data found for {ticker} in data/prices/")
    return None


@dataclass
class FinancialMetrics:
    """Complete financial metrics matching Financial Datasets API format."""

    ticker: str
    report_date: str  # Date of the most recent fiscal year end

    # === Valuation Metrics (9) ===
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    price_to_earnings_ratio: Optional[float] = None
    price_to_book_ratio: Optional[float] = None
    price_to_sales_ratio: Optional[float] = None
    enterprise_value_to_ebitda_ratio: Optional[float] = None
    enterprise_value_to_revenue_ratio: Optional[float] = None
    free_cash_flow_yield: Optional[float] = None
    peg_ratio: Optional[float] = None

    # === Profitability Metrics (6) ===
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None
    return_on_invested_capital: Optional[float] = None

    # === Efficiency Metrics (6) ===
    asset_turnover: Optional[float] = None
    inventory_turnover: Optional[float] = None
    receivables_turnover: Optional[float] = None
    days_sales_outstanding: Optional[float] = None
    operating_cycle: Optional[float] = None
    working_capital_turnover: Optional[float] = None

    # === Liquidity Metrics (4) ===
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    cash_ratio: Optional[float] = None
    operating_cash_flow_ratio: Optional[float] = None

    # === Leverage Metrics (3) ===
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
    interest_coverage: Optional[float] = None

    # === Growth Metrics (7) ===
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    book_value_growth: Optional[float] = None
    earnings_per_share_growth: Optional[float] = None
    free_cash_flow_growth: Optional[float] = None
    operating_income_growth: Optional[float] = None
    ebitda_growth: Optional[float] = None

    # === Per-Share Metrics (4) ===
    earnings_per_share: Optional[float] = None
    book_value_per_share: Optional[float] = None
    free_cash_flow_per_share: Optional[float] = None
    payout_ratio: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get snapshot format matching Financial Datasets API."""
        d = self.to_dict()
        # Remove metadata fields for snapshot
        d.pop('report_date', None)
        return d


class FinancialMetricsCalculator:
    """
    Calculate all 39 financial metrics from SEC EDGAR + IBKR data.

    This replaces Financial Datasets API endpoints 11-12 (financial-metrics).
    """

    def __init__(
        self,
        ticker: str,
        ibkr_data_path: Optional[Path] = None,
        years_for_growth: int = 2,
    ):
        """
        Initialize calculator.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            ibkr_data_path: Path to IBKR fundamentals directory
            years_for_growth: Number of years for growth calculations (default 2 for YoY)
        """
        self.ticker = ticker.upper()
        self.years_for_growth = years_for_growth

        # Set default IBKR data path
        if ibkr_data_path is None:
            project_root = Path(__file__).parent.parent
            self.ibkr_data_path = project_root / "data_lake" / "raw" / "ibkr_fundamentals"
        else:
            self.ibkr_data_path = Path(ibkr_data_path)

        # Initialize SEC EDGAR client
        self.sec = SECEdgarFinancials()

        # Cache for financial data
        self._income_statements: Optional[List] = None
        self._balance_sheets: Optional[List] = None
        self._cash_flow_statements: Optional[List] = None
        self._ibkr_data: Optional[Dict] = None

    # =========================================================================
    # Data Loading
    # =========================================================================

    def _load_income_statements(self, years: int = 3) -> List[Dict]:
        """Load income statements from SEC EDGAR."""
        if self._income_statements is None:
            statements = self.sec.get_income_statement(self.ticker, years=years)
            self._income_statements = [asdict(s) for s in statements]
        return self._income_statements

    def _load_balance_sheets(self, years: int = 3) -> List[Dict]:
        """Load balance sheets from SEC EDGAR."""
        if self._balance_sheets is None:
            statements = self.sec.get_balance_sheet(self.ticker, years=years)
            self._balance_sheets = [asdict(s) for s in statements]
        return self._balance_sheets

    def _load_cash_flow_statements(self, years: int = 3) -> List[Dict]:
        """Load cash flow statements from SEC EDGAR."""
        if self._cash_flow_statements is None:
            statements = self.sec.get_cash_flow_statement(self.ticker, years=years)
            self._cash_flow_statements = [asdict(s) for s in statements]
        return self._cash_flow_statements

    def _load_ibkr_data(self) -> Optional[Dict]:
        """Load IBKR fundamentals data."""
        if self._ibkr_data is None:
            # Find the most recent IBKR file for this ticker
            pattern = f"{self.ticker}_*.json"
            files = sorted(self.ibkr_data_path.glob(pattern), reverse=True)

            if files:
                with open(files[0]) as f:
                    self._ibkr_data = json.load(f)
                logger.info(f"Loaded IBKR data from {files[0]}")
            else:
                logger.warning(f"No IBKR data found for {self.ticker}")
                self._ibkr_data = {}

        return self._ibkr_data

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _safe_divide(self, numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        """Safely divide two numbers, returning None if invalid."""
        if numerator is None or denominator is None or denominator == 0:
            return None
        return numerator / denominator

    def _calculate_growth(self, current: Optional[float], previous: Optional[float]) -> Optional[float]:
        """Calculate YoY growth rate."""
        if current is None or previous is None or previous == 0:
            return None
        return (current - previous) / abs(previous)

    def _get_latest_and_previous(self, statements: List[Dict], field: str) -> tuple:
        """Get current and previous year values for a field."""
        if len(statements) < 2:
            return (statements[0].get(field) if statements else None, None)
        return statements[0].get(field), statements[1].get(field)

    # =========================================================================
    # Profitability Metrics (6)
    # =========================================================================

    def get_profitability_metrics(self) -> Dict[str, Optional[float]]:
        """
        Calculate profitability metrics.

        Metrics:
            - gross_margin: Gross Profit / Revenue
            - operating_margin: Operating Income / Revenue
            - net_margin: Net Income / Revenue
            - return_on_equity: Net Income / Shareholders' Equity
            - return_on_assets: Net Income / Total Assets
            - return_on_invested_capital: NOPAT / Invested Capital
        """
        income = self._load_income_statements(years=1)
        balance = self._load_balance_sheets(years=1)

        if not income or not balance:
            return {}

        inc = income[0]
        bal = balance[0]

        revenue = inc.get('revenue')
        gross_profit = inc.get('gross_profit')
        operating_income = inc.get('operating_income')
        net_income = inc.get('net_income')

        total_assets = bal.get('total_assets')
        total_equity = bal.get('shareholders_equity')
        total_liabilities = bal.get('total_liabilities')
        current_debt = bal.get('current_debt') or 0
        non_current_debt = bal.get('non_current_debt') or 0
        total_debt = current_debt + non_current_debt

        # ROIC calculation: NOPAT / Invested Capital
        # NOPAT = Operating Income * (1 - Tax Rate)
        # Invested Capital = Total Equity + Total Debt - Cash
        cash = bal.get('cash_and_equivalents') or 0
        tax_rate = 0.21  # Approximate corporate tax rate
        nopat = operating_income * (1 - tax_rate) if operating_income else None
        invested_capital = (total_equity or 0) + total_debt - cash
        roic = self._safe_divide(nopat, invested_capital) if invested_capital > 0 else None

        return {
            'gross_margin': self._safe_divide(gross_profit, revenue),
            'operating_margin': self._safe_divide(operating_income, revenue),
            'net_margin': self._safe_divide(net_income, revenue),
            'return_on_equity': self._safe_divide(net_income, total_equity),
            'return_on_assets': self._safe_divide(net_income, total_assets),
            'return_on_invested_capital': roic,
        }

    # =========================================================================
    # Efficiency Metrics (6)
    # =========================================================================

    def get_efficiency_metrics(self) -> Dict[str, Optional[float]]:
        """
        Calculate efficiency metrics.

        Metrics:
            - asset_turnover: Revenue / Total Assets
            - inventory_turnover: COGS / Average Inventory
            - receivables_turnover: Revenue / Average Receivables
            - days_sales_outstanding: 365 / Receivables Turnover
            - operating_cycle: Days Inventory + Days Receivables
            - working_capital_turnover: Revenue / Working Capital
        """
        income = self._load_income_statements(years=2)
        balance = self._load_balance_sheets(years=2)

        if not income or not balance:
            return {}

        inc = income[0]
        bal = balance[0]
        bal_prev = balance[1] if len(balance) > 1 else balance[0]

        revenue = inc.get('revenue')
        cogs = inc.get('cost_of_revenue')

        total_assets = bal.get('total_assets')
        inventory = bal.get('inventory') or 0
        inventory_prev = bal_prev.get('inventory') or 0
        avg_inventory = (inventory + inventory_prev) / 2 if inventory_prev else inventory

        receivables = bal.get('trade_and_non_trade_receivables') or 0
        receivables_prev = bal_prev.get('trade_and_non_trade_receivables') or 0
        avg_receivables = (receivables + receivables_prev) / 2 if receivables_prev else receivables

        current_assets = bal.get('current_assets') or 0
        current_liabilities = bal.get('current_liabilities') or 0
        working_capital = current_assets - current_liabilities

        # Calculate turnover ratios
        asset_turnover = self._safe_divide(revenue, total_assets)
        inventory_turnover = self._safe_divide(cogs, avg_inventory) if avg_inventory > 0 else None
        receivables_turnover = self._safe_divide(revenue, avg_receivables) if avg_receivables > 0 else None

        # Days calculations
        days_inventory = self._safe_divide(365, inventory_turnover) if inventory_turnover else None
        days_receivables = self._safe_divide(365, receivables_turnover) if receivables_turnover else None

        # Note: Financial Datasets uses a different formula for days_sales_outstanding
        # They use: Receivables / (Revenue / 365) which equals 365 / receivables_turnover
        # But their actual value (0.144) suggests they may use a different calculation
        days_sales_outstanding = self._safe_divide(avg_receivables, self._safe_divide(revenue, 365))

        # Operating cycle = Days Inventory + Days Receivables
        operating_cycle = None
        if days_inventory is not None and days_receivables is not None:
            operating_cycle = days_inventory + days_receivables

        working_capital_turnover = self._safe_divide(revenue, working_capital) if working_capital != 0 else None

        return {
            'asset_turnover': asset_turnover,
            'inventory_turnover': inventory_turnover,
            'receivables_turnover': receivables_turnover,
            'days_sales_outstanding': days_sales_outstanding,
            'operating_cycle': operating_cycle,
            'working_capital_turnover': working_capital_turnover,
        }

    # =========================================================================
    # Liquidity Metrics (4)
    # =========================================================================

    def get_liquidity_metrics(self) -> Dict[str, Optional[float]]:
        """
        Calculate liquidity metrics.

        Metrics:
            - current_ratio: Current Assets / Current Liabilities
            - quick_ratio: (Current Assets - Inventory) / Current Liabilities
            - cash_ratio: Cash / Current Liabilities
            - operating_cash_flow_ratio: Operating Cash Flow / Current Liabilities
        """
        balance = self._load_balance_sheets(years=1)
        cashflow = self._load_cash_flow_statements(years=1)

        if not balance:
            return {}

        bal = balance[0]
        cf = cashflow[0] if cashflow else {}

        current_assets = bal.get('current_assets')
        current_liabilities = bal.get('current_liabilities')
        inventory = bal.get('inventory') or 0
        cash = bal.get('cash_and_equivalents')
        operating_cash_flow = cf.get('net_cash_flow_from_operations')

        return {
            'current_ratio': self._safe_divide(current_assets, current_liabilities),
            'quick_ratio': self._safe_divide(
                (current_assets - inventory) if current_assets else None,
                current_liabilities
            ),
            'cash_ratio': self._safe_divide(cash, current_liabilities),
            'operating_cash_flow_ratio': self._safe_divide(operating_cash_flow, current_liabilities),
        }

    # =========================================================================
    # Leverage Metrics (3)
    # =========================================================================

    def get_leverage_metrics(self) -> Dict[str, Optional[float]]:
        """
        Calculate leverage metrics.

        Metrics:
            - debt_to_equity: Total Debt / Shareholders' Equity
            - debt_to_assets: Total Debt / Total Assets
            - interest_coverage: Operating Income / Interest Expense
        """
        balance = self._load_balance_sheets(years=1)
        income = self._load_income_statements(years=1)

        if not balance:
            return {}

        bal = balance[0]
        inc = income[0] if income else {}

        current_debt = bal.get('current_debt') or 0
        non_current_debt = bal.get('non_current_debt') or 0
        total_debt = current_debt + non_current_debt

        total_equity = bal.get('shareholders_equity')
        total_assets = bal.get('total_assets')

        operating_income = inc.get('operating_income')
        interest_expense = inc.get('interest_expense')

        return {
            'debt_to_equity': self._safe_divide(total_debt, total_equity),
            'debt_to_assets': self._safe_divide(total_debt, total_assets),
            'interest_coverage': self._safe_divide(operating_income, interest_expense) if interest_expense else None,
        }

    # =========================================================================
    # Growth Metrics (7)
    # =========================================================================

    def get_growth_metrics(self) -> Dict[str, Optional[float]]:
        """
        Calculate growth metrics (YoY).

        Metrics:
            - revenue_growth: (Revenue_t - Revenue_t-1) / Revenue_t-1
            - earnings_growth: (Net Income_t - Net Income_t-1) / Net Income_t-1
            - book_value_growth: (Equity_t - Equity_t-1) / Equity_t-1
            - earnings_per_share_growth: (EPS_t - EPS_t-1) / EPS_t-1
            - free_cash_flow_growth: (FCF_t - FCF_t-1) / FCF_t-1
            - operating_income_growth: (Op Income_t - Op Income_t-1) / Op Income_t-1
            - ebitda_growth: (EBITDA_t - EBITDA_t-1) / EBITDA_t-1
        """
        income = self._load_income_statements(years=self.years_for_growth)
        balance = self._load_balance_sheets(years=self.years_for_growth)
        cashflow = self._load_cash_flow_statements(years=self.years_for_growth)

        if len(income) < 2:
            return {}

        # Income statement metrics
        revenue_curr, revenue_prev = self._get_latest_and_previous(income, 'revenue')
        net_income_curr, net_income_prev = self._get_latest_and_previous(income, 'net_income')
        operating_income_curr, operating_income_prev = self._get_latest_and_previous(income, 'operating_income')
        eps_curr, eps_prev = self._get_latest_and_previous(income, 'earnings_per_share')

        # Balance sheet metrics
        equity_curr, equity_prev = self._get_latest_and_previous(balance, 'shareholders_equity')

        # Cash flow metrics
        fcf_curr, fcf_prev = self._get_latest_and_previous(cashflow, 'free_cash_flow')

        # EBITDA calculation: Operating Income + D&A
        da_curr = cashflow[0].get('depreciation_and_amortization') if cashflow else None
        da_prev = cashflow[1].get('depreciation_and_amortization') if len(cashflow) > 1 else None

        ebitda_curr = (operating_income_curr + da_curr) if operating_income_curr and da_curr else None
        ebitda_prev = (operating_income_prev + da_prev) if operating_income_prev and da_prev else None

        return {
            'revenue_growth': self._calculate_growth(revenue_curr, revenue_prev),
            'earnings_growth': self._calculate_growth(net_income_curr, net_income_prev),
            'book_value_growth': self._calculate_growth(equity_curr, equity_prev),
            'earnings_per_share_growth': self._calculate_growth(eps_curr, eps_prev),
            'free_cash_flow_growth': self._calculate_growth(fcf_curr, fcf_prev),
            'operating_income_growth': self._calculate_growth(operating_income_curr, operating_income_prev),
            'ebitda_growth': self._calculate_growth(ebitda_curr, ebitda_prev),
        }

    # =========================================================================
    # Per-Share Metrics (4)
    # =========================================================================

    def get_per_share_metrics(self) -> Dict[str, Optional[float]]:
        """
        Calculate per-share metrics.

        Metrics:
            - earnings_per_share: Net Income / Shares Outstanding
            - book_value_per_share: Shareholders' Equity / Shares Outstanding
            - free_cash_flow_per_share: Free Cash Flow / Shares Outstanding
            - payout_ratio: Dividends / Net Income
        """
        income = self._load_income_statements(years=1)
        balance = self._load_balance_sheets(years=1)
        cashflow = self._load_cash_flow_statements(years=1)

        if not income or not balance:
            return {}

        inc = income[0]
        bal = balance[0]
        cf = cashflow[0] if cashflow else {}

        net_income = inc.get('net_income')
        shares_outstanding = bal.get('outstanding_shares')
        shareholders_equity = bal.get('shareholders_equity')
        free_cash_flow = cf.get('free_cash_flow')
        dividends = cf.get('dividends_and_other_cash_distributions')

        # Dividends are reported as negative in cash flow, convert to positive
        if dividends is not None:
            dividends = abs(dividends)

        return {
            'earnings_per_share': self._safe_divide(net_income, shares_outstanding),
            'book_value_per_share': self._safe_divide(shareholders_equity, shares_outstanding),
            'free_cash_flow_per_share': self._safe_divide(free_cash_flow, shares_outstanding),
            'payout_ratio': self._safe_divide(dividends, net_income),
        }

    # =========================================================================
    # Valuation Metrics (9) - Requires IBKR data for market price
    # =========================================================================

    def get_valuation_metrics(self) -> Dict[str, Optional[float]]:
        """
        Calculate valuation metrics.

        Note: These metrics require current market price from IBKR.

        Metrics:
            - market_cap: Share Price * Shares Outstanding
            - enterprise_value: Market Cap + Total Debt - Cash
            - price_to_earnings_ratio: Market Cap / Net Income
            - price_to_book_ratio: Market Cap / Book Value
            - price_to_sales_ratio: Market Cap / Revenue
            - enterprise_value_to_ebitda_ratio: EV / EBITDA
            - enterprise_value_to_revenue_ratio: EV / Revenue
            - free_cash_flow_yield: Free Cash Flow / Market Cap
            - peg_ratio: P/E Ratio / Earnings Growth Rate
        """
        ibkr = self._load_ibkr_data()
        income = self._load_income_statements(years=2)
        balance = self._load_balance_sheets(years=1)
        cashflow = self._load_cash_flow_statements(years=2)

        if not income or not balance:
            return {}

        inc = income[0]
        bal = balance[0]
        cf = cashflow[0] if cashflow else {}

        # Get market data from IBKR
        market_cap = None
        enterprise_value = None

        if ibkr:
            # IBKR provides MKTCAP in millions, convert to actual value
            mktcap_raw = ibkr.get('MKTCAP')
            if mktcap_raw and mktcap_raw != '':
                try:
                    market_cap = float(mktcap_raw) * 1e6  # Convert from millions
                except (ValueError, TypeError):
                    pass

            # IBKR provides EV
            ev_raw = ibkr.get('EV')
            if ev_raw and ev_raw != '':
                try:
                    enterprise_value = float(ev_raw) * 1e6
                except (ValueError, TypeError):
                    pass

        # If no IBKR fundamentals data, calculate from IBKR price data + shares outstanding
        if market_cap is None:
            shares = bal.get('outstanding_shares')
            if shares:
                current_price = _get_current_price_ibkr(self.ticker)
                if current_price:
                    market_cap = current_price * shares
                    logger.info(f"Calculated market cap from IBKR prices: ${market_cap/1e9:.2f}B")

        # Calculate EV if not from IBKR
        if enterprise_value is None and market_cap is not None:
            current_debt = bal.get('current_debt') or 0
            non_current_debt = bal.get('non_current_debt') or 0
            total_debt = current_debt + non_current_debt
            cash = bal.get('cash_and_equivalents') or 0
            enterprise_value = market_cap + total_debt - cash

        # Financial data
        net_income = inc.get('net_income')
        revenue = inc.get('revenue')
        shareholders_equity = bal.get('shareholders_equity')
        free_cash_flow = cf.get('free_cash_flow')
        operating_income = inc.get('operating_income')

        # EBITDA
        da = cf.get('depreciation_and_amortization') or 0
        ebitda = (operating_income + da) if operating_income else None

        # Growth for PEG
        growth_metrics = self.get_growth_metrics()
        earnings_growth = growth_metrics.get('earnings_growth')

        # Calculate valuation ratios
        pe_ratio = self._safe_divide(market_cap, net_income)

        return {
            'market_cap': market_cap,
            'enterprise_value': enterprise_value,
            'price_to_earnings_ratio': pe_ratio,
            'price_to_book_ratio': self._safe_divide(market_cap, shareholders_equity),
            'price_to_sales_ratio': self._safe_divide(market_cap, revenue),
            'enterprise_value_to_ebitda_ratio': self._safe_divide(enterprise_value, ebitda),
            'enterprise_value_to_revenue_ratio': self._safe_divide(enterprise_value, revenue),
            'free_cash_flow_yield': self._safe_divide(free_cash_flow, market_cap),
            'peg_ratio': self._safe_divide(pe_ratio, earnings_growth * 100) if earnings_growth else None,
        }

    # =========================================================================
    # Get All Metrics
    # =========================================================================

    def get_all_metrics(self) -> FinancialMetrics:
        """
        Calculate all 39 financial metrics.

        Returns:
            FinancialMetrics dataclass with all metrics populated
        """
        # Pre-load data with enough years for growth calculations
        # (This ensures cache has sufficient data before individual methods run)
        self._load_income_statements(years=3)
        self._load_balance_sheets(years=3)
        self._load_cash_flow_statements(years=3)

        # Get report date from latest income statement
        income = self._income_statements
        report_date = income[0].get('report_period', '') if income else ''

        # Calculate all metric categories
        profitability = self.get_profitability_metrics()
        efficiency = self.get_efficiency_metrics()
        liquidity = self.get_liquidity_metrics()
        leverage = self.get_leverage_metrics()
        growth = self.get_growth_metrics()
        per_share = self.get_per_share_metrics()
        valuation = self.get_valuation_metrics()

        # Combine all metrics
        return FinancialMetrics(
            ticker=self.ticker,
            report_date=report_date,
            # Valuation
            **valuation,
            # Profitability
            **profitability,
            # Efficiency
            **efficiency,
            # Liquidity
            **liquidity,
            # Leverage
            **leverage,
            # Growth
            **growth,
            # Per-share
            **per_share,
        )

    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        return self.get_all_metrics().to_dict()

    def get_snapshot(self) -> Dict[str, Any]:
        """Get metrics snapshot matching Financial Datasets API format."""
        return self.get_all_metrics().get_snapshot()


# =============================================================================
# Convenience Functions
# =============================================================================

def get_financial_metrics(ticker: str) -> Dict[str, Any]:
    """
    Get all financial metrics for a ticker.

    Args:
        ticker: Stock symbol

    Returns:
        Dictionary of all 39 metrics
    """
    calc = FinancialMetricsCalculator(ticker)
    return calc.get_metrics_dict()


def get_financial_metrics_snapshot(ticker: str) -> Dict[str, Any]:
    """
    Get financial metrics snapshot matching Financial Datasets API format.

    Args:
        ticker: Stock symbol

    Returns:
        Dictionary matching Financial Datasets /financial-metrics/snapshot format
    """
    calc = FinancialMetricsCalculator(ticker)
    return calc.get_snapshot()


def compare_with_financial_datasets(
    ticker: str,
    fd_metrics: Dict[str, Any],
    tolerance_pct: float = 0.1,
) -> Dict[str, Any]:
    """
    Compare calculated metrics with Financial Datasets API response.

    Args:
        ticker: Stock symbol
        fd_metrics: Financial Datasets API snapshot response
        tolerance_pct: Tolerance percentage for exact match (default 0.1%)

    Returns:
        Comparison report with match status for each metric

    Match Status:
        - 'exact': Difference < tolerance_pct (default 0.1%)
        - 'close': Difference between tolerance_pct and 1%
        - 'near': Difference between 1% and 5%
        - 'mismatch': Difference > 5%
        - 'both_null': Both values are None
        - 'fd_null': Only Financial Datasets value is None
        - 'our_null': Only our value is None
        - 'error': Comparison error
    """
    calc = FinancialMetricsCalculator(ticker)
    our_metrics = calc.get_snapshot()

    comparison = {}

    for key in fd_metrics.keys():
        if key == 'ticker':
            continue

        fd_val = fd_metrics.get(key)
        our_val = our_metrics.get(key)

        if fd_val is None and our_val is None:
            status = 'both_null'
            diff_pct = None
        elif fd_val is None:
            status = 'fd_null'
            diff_pct = None
        elif our_val is None:
            status = 'our_null'
            diff_pct = None
        else:
            try:
                diff_pct = abs(our_val - fd_val) / abs(fd_val) * 100 if fd_val != 0 else 0
                # Strict tolerance levels
                if diff_pct < tolerance_pct:
                    status = 'exact'
                elif diff_pct < 1.0:
                    status = 'close'  # Needs investigation
                elif diff_pct < 5.0:
                    status = 'near'  # Significant difference
                else:
                    status = 'mismatch'  # Major difference
            except (TypeError, ZeroDivisionError):
                status = 'error'
                diff_pct = None

        comparison[key] = {
            'our_value': our_val,
            'fd_value': fd_val,
            'diff_pct': diff_pct,
            'status': status,
        }

    # Summary with detailed breakdown
    total = len([k for k in comparison.keys()])
    exact = len([k for k, v in comparison.items() if v['status'] == 'exact'])
    close = len([k for k, v in comparison.items() if v['status'] == 'close'])
    near = len([k for k, v in comparison.items() if v['status'] == 'near'])
    mismatch = len([k for k, v in comparison.items() if v['status'] == 'mismatch'])
    our_null = len([k for k, v in comparison.items() if v['status'] == 'our_null'])

    return {
        'ticker': ticker,
        'total_metrics': total,
        'exact_match': exact,
        'close_match': close,
        'near_match': near,
        'mismatch': mismatch,
        'our_null': our_null,
        'match_summary': f"Exact: {exact}, Close: {close}, Near: {near}, Mismatch: {mismatch}, Missing: {our_null}",
        'details': comparison,
    }


if __name__ == '__main__':
    # Quick test
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else 'AAPL'

    print(f"\n=== Financial Metrics for {ticker} ===\n")

    calc = FinancialMetricsCalculator(ticker)
    metrics = calc.get_all_metrics()

    # Print by category
    print("Profitability:")
    for k, v in calc.get_profitability_metrics().items():
        print(f"  {k}: {v:.4f}" if v else f"  {k}: N/A")

    print("\nEfficiency:")
    for k, v in calc.get_efficiency_metrics().items():
        print(f"  {k}: {v:.4f}" if v else f"  {k}: N/A")

    print("\nLiquidity:")
    for k, v in calc.get_liquidity_metrics().items():
        print(f"  {k}: {v:.4f}" if v else f"  {k}: N/A")

    print("\nLeverage:")
    for k, v in calc.get_leverage_metrics().items():
        print(f"  {k}: {v:.4f}" if v else f"  {k}: N/A")

    print("\nGrowth:")
    for k, v in calc.get_growth_metrics().items():
        print(f"  {k}: {v:.4f}" if v else f"  {k}: N/A")

    print("\nPer-Share:")
    for k, v in calc.get_per_share_metrics().items():
        print(f"  {k}: {v:.4f}" if v else f"  {k}: N/A")

    print("\nValuation:")
    for k, v in calc.get_valuation_metrics().items():
        if v and abs(v) > 1e6:
            print(f"  {k}: ${v/1e9:.2f}B")
        elif v:
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: N/A")