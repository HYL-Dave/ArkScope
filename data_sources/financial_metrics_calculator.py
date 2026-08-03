#!/usr/bin/env python3
"""
Financial Metrics Calculator - Complete 39 metrics matching Financial Datasets API.

This module calculates all 39 financial metrics that Financial Datasets API provides,
using free data from SEC EDGAR (via sec_edgar_financials.py).

Usage:
    from data_sources.financial_metrics_calculator import FinancialMetricsCalculator

    calc = FinancialMetricsCalculator('AAPL')
    metrics = calc.get_all_metrics()

    # Or get specific categories
    profitability = calc.get_profitability_metrics()
    valuation = calc.get_valuation_metrics(price=qualified_price)

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
    - Qualified price: supplied explicitly by the caller
"""

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime

from data_sources.sec_edgar_financials import SECEdgarFinancials
from src.fundamentals.cache import CALCULATOR_DYNAMIC_FIELDS

logger = logging.getLogger(__name__)


def _finite_number(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def calculate_valuation_metrics(
    *,
    price: Optional[float],
    valuation_inputs: Mapping[str, Optional[float]],
) -> Dict[str, Optional[float]]:
    """Calculate the nine price-dependent fields from explicit base-unit facts."""
    result = {field: None for field in CALCULATOR_DYNAMIC_FIELDS}
    normalized_price = _finite_number(price)
    shares = _finite_number(valuation_inputs.get("outstanding_shares"))
    if normalized_price is None or normalized_price <= 0 or shares is None or shares <= 0:
        return result

    market_cap = normalized_price * shares
    debt = _finite_number(valuation_inputs.get("total_debt"))
    cash = _finite_number(valuation_inputs.get("cash_and_equivalents"))
    enterprise_value = (
        market_cap + debt - cash
        if debt is not None and cash is not None
        else None
    )
    net_income = _finite_number(valuation_inputs.get("net_income"))
    earnings_per_share = _finite_number(
        valuation_inputs.get("earnings_per_share")
    )
    pe_ratio = _divide(market_cap, net_income)
    if pe_ratio is None:
        pe_ratio = _divide(normalized_price, earnings_per_share)

    equity = _finite_number(valuation_inputs.get("shareholders_equity"))
    revenue = _finite_number(valuation_inputs.get("revenue"))
    ebitda = _finite_number(valuation_inputs.get("ebitda"))
    free_cash_flow = _finite_number(valuation_inputs.get("free_cash_flow"))
    earnings_growth = _finite_number(valuation_inputs.get("earnings_growth"))

    result.update({
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "price_to_earnings_ratio": pe_ratio,
        "price_to_book_ratio": _divide(market_cap, equity),
        "price_to_sales_ratio": _divide(market_cap, revenue),
        "enterprise_value_to_ebitda_ratio": _divide(
            enterprise_value, ebitda
        ),
        "enterprise_value_to_revenue_ratio": _divide(
            enterprise_value, revenue
        ),
        "free_cash_flow_yield": _divide(free_cash_flow, market_cap),
        "peg_ratio": _divide(pe_ratio, earnings_growth * 100)
        if earnings_growth is not None
        else None,
    })
    return result


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
    Calculate all 39 financial metrics from SEC EDGAR and an explicit price.

    This replaces Financial Datasets API endpoints 11-12 (financial-metrics).
    """

    def __init__(
        self,
        ticker: str,
        years_for_growth: int = 2,
    ):
        """
        Initialize calculator.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            years_for_growth: Number of years for growth calculations (default 2 for YoY)
        """
        self.ticker = ticker.upper()
        self.years_for_growth = years_for_growth

        # Initialize SEC EDGAR client
        self.sec = SECEdgarFinancials()

        # Cache for financial data
        self._income_statements: Optional[List] = None
        self._balance_sheets: Optional[List] = None
        self._cash_flow_statements: Optional[List] = None

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
    # Efficiency Metrics (6) - Multiple Calculation Methods
    # =========================================================================

    def get_efficiency_metrics(
        self,
        method: str = 'standard',
    ) -> Dict[str, Optional[float]]:
        """
        Calculate efficiency metrics with selectable calculation method.

        Args:
            method: Calculation method to use
                - 'standard': 標準方法 (COGS/Avg Inventory, Revenue/Avg Receivables)
                - 'fd_style': Financial Datasets 風格 (Revenue/End Inventory, Revenue/Total Receivables)
                - 'all': 返回所有方法的計算結果

        Metrics:
            - asset_turnover: Revenue / Total Assets
            - inventory_turnover: COGS / Average Inventory (standard) or Revenue / End Inventory (fd_style)
            - receivables_turnover: Revenue / Average Receivables (standard) or Revenue / Total Receivables (fd_style)
            - days_sales_outstanding: 365 / Receivables Turnover
            - operating_cycle: Days Inventory + Days Receivables
            - working_capital_turnover: Revenue / Working Capital

        Note on method differences:
            - 'standard': 教科書標準方法，使用 COGS 和平均值
            - 'fd_style': Financial Datasets 似乎使用的方法
              - inventory_turnover: Revenue / End Inventory (非標準但接近 FD 值)
              - receivables_turnover: 使用 Total Receivables (包含 Non-trade)
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

        # Assets
        total_assets = bal.get('total_assets')
        total_assets_prev = bal_prev.get('total_assets')
        avg_assets = (total_assets + total_assets_prev) / 2 if total_assets_prev else total_assets

        # Inventory
        inventory = bal.get('inventory') or 0
        inventory_prev = bal_prev.get('inventory') or 0
        avg_inventory = (inventory + inventory_prev) / 2 if inventory_prev else inventory

        # Receivables - note: trade_and_non_trade_receivables includes Non-trade
        receivables = bal.get('trade_and_non_trade_receivables') or 0
        receivables_prev = bal_prev.get('trade_and_non_trade_receivables') or 0
        avg_receivables = (receivables + receivables_prev) / 2 if receivables_prev else receivables

        # Working Capital
        current_assets = bal.get('current_assets') or 0
        current_liabilities = bal.get('current_liabilities') or 0
        working_capital = current_assets - current_liabilities

        if method == 'all':
            # Return all calculation methods for comparison
            return self._get_all_efficiency_methods(
                revenue, cogs, total_assets, avg_assets,
                inventory, avg_inventory,
                receivables, avg_receivables,
                working_capital
            )

        # Select method
        if method == 'fd_style':
            # FD-style: Revenue/End Inventory, uses Total Receivables
            asset_turnover = self._safe_divide(revenue, avg_assets)  # FD uses ~avg
            inventory_turnover = self._safe_divide(revenue, inventory) if inventory > 0 else None
            receivables_turnover = self._safe_divide(revenue, receivables) if receivables > 0 else None
        else:
            # Standard: COGS/Avg Inventory
            asset_turnover = self._safe_divide(revenue, total_assets)
            inventory_turnover = self._safe_divide(cogs, avg_inventory) if avg_inventory > 0 else None
            receivables_turnover = self._safe_divide(revenue, avg_receivables) if avg_receivables > 0 else None

        # Days calculations
        days_inventory = self._safe_divide(365, inventory_turnover) if inventory_turnover else None
        days_receivables = self._safe_divide(365, receivables_turnover) if receivables_turnover else None
        days_sales_outstanding = days_receivables  # Standard definition

        # Operating cycle = Days Inventory + Days Receivables
        operating_cycle = None
        if days_inventory is not None and days_receivables is not None:
            operating_cycle = days_inventory + days_receivables

        # Working capital turnover
        working_capital_turnover = self._safe_divide(revenue, working_capital) if working_capital != 0 else None

        return {
            'asset_turnover': asset_turnover,
            'inventory_turnover': inventory_turnover,
            'receivables_turnover': receivables_turnover,
            'days_sales_outstanding': days_sales_outstanding,
            'operating_cycle': operating_cycle,
            'working_capital_turnover': working_capital_turnover,
        }

    def _get_all_efficiency_methods(
        self,
        revenue, cogs, total_assets, avg_assets,
        inventory, avg_inventory,
        receivables, avg_receivables,
        working_capital,
    ) -> Dict[str, Any]:
        """
        Calculate efficiency metrics using ALL methods for comparison.

        Returns a nested dict with both 'standard' and 'fd_style' results,
        plus individual method breakdowns.
        """
        # Asset Turnover variants
        at_end = self._safe_divide(revenue, total_assets)
        at_avg = self._safe_divide(revenue, avg_assets)

        # Inventory Turnover variants
        it_cogs_avg = self._safe_divide(cogs, avg_inventory) if avg_inventory > 0 else None
        it_cogs_end = self._safe_divide(cogs, inventory) if inventory > 0 else None
        it_rev_avg = self._safe_divide(revenue, avg_inventory) if avg_inventory > 0 else None
        it_rev_end = self._safe_divide(revenue, inventory) if inventory > 0 else None

        # Receivables Turnover variants
        rt_avg = self._safe_divide(revenue, avg_receivables) if avg_receivables > 0 else None
        rt_end = self._safe_divide(revenue, receivables) if receivables > 0 else None

        # Days calculations (using standard inventory turnover)
        days_inv_std = self._safe_divide(365, it_cogs_avg) if it_cogs_avg else None
        days_recv_std = self._safe_divide(365, rt_avg) if rt_avg else None

        # Working Capital Turnover
        wc_standard = self._safe_divide(revenue, working_capital) if working_capital != 0 else None
        wc_abs = self._safe_divide(revenue, abs(working_capital)) if working_capital != 0 else None

        return {
            # Standard method results
            'standard': {
                'asset_turnover': at_end,
                'inventory_turnover': it_cogs_avg,
                'receivables_turnover': rt_avg,
                'days_sales_outstanding': days_recv_std,
                'operating_cycle': (days_inv_std + days_recv_std) if days_inv_std and days_recv_std else None,
                'working_capital_turnover': wc_standard,
            },
            # FD-style method results
            'fd_style': {
                'asset_turnover': at_avg,
                'inventory_turnover': it_rev_end,  # Revenue / End Inventory
                'receivables_turnover': rt_end,  # Revenue / End Total Receivables
                'days_sales_outstanding': self._safe_divide(365, rt_end) if rt_end else None,
                'operating_cycle': None,  # Not reliable with FD method
                'working_capital_turnover': wc_abs if working_capital < 0 else wc_standard,
            },
            # All individual methods for detailed analysis
            'methods': {
                'asset_turnover': {
                    'revenue_div_end_assets': at_end,
                    'revenue_div_avg_assets': at_avg,
                },
                'inventory_turnover': {
                    'cogs_div_avg_inventory': it_cogs_avg,
                    'cogs_div_end_inventory': it_cogs_end,
                    'revenue_div_avg_inventory': it_rev_avg,
                    'revenue_div_end_inventory': it_rev_end,
                },
                'receivables_turnover': {
                    'revenue_div_avg_receivables': rt_avg,
                    'revenue_div_end_receivables': rt_end,
                },
                'working_capital_turnover': {
                    'revenue_div_wc': wc_standard,
                    'revenue_div_abs_wc': wc_abs,
                    'working_capital_value': working_capital,
                    'is_negative_wc': working_capital < 0,
                },
            },
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
    # Growth Metrics (7) - Multiple Calculation Methods
    # =========================================================================

    def _get_quarterly_values(
        self,
        concept_names: List[str],
        unit: str = 'USD',
        num_quarters: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Get quarterly values from SEC EDGAR for TTM calculation.

        This extracts individual quarter values (not YTD) by:
        1. Identifying unique fiscal years from 10-K data (by end date)
        2. Finding quarterly data by matching fiscal period dates
        3. Calculating Q4 from: FY total - (Q1 + Q2 + Q3) for 10-K filings

        Args:
            concept_names: List of SEC EDGAR concept names to try
            unit: Unit type ('USD', 'USD/shares', etc.)
            num_quarters: Number of quarters to retrieve

        Returns:
            List of dicts with keys: end, val, fp, fy, form
            Sorted by end date descending (newest first)
        """
        facts = self.sec._get_company_facts(self.ticker)
        if not facts or 'facts' not in facts:
            return []

        gaap = facts['facts'].get('us-gaap', {})

        for concept in concept_names:
            if concept not in gaap:
                continue

            concept_data = gaap[concept]
            if 'units' not in concept_data or unit not in concept_data['units']:
                continue

            entries = concept_data['units'][unit]

            from collections import defaultdict

            # Step 1: Get unique fiscal years from 10-K data (by end date, not fy number)
            # SEC EDGAR has duplicate fy assignments, so we use end date as the unique key
            fy_by_end = {}  # {end_date: {val, fy}}
            for e in entries:
                if e.get('form') == '10-K' and e.get('fp') == 'FY' and e.get('val') is not None:
                    end = e.get('end')
                    fy = e.get('fy')
                    # Only keep if the fiscal year matches the end date year
                    # (e.g., FY2025 should end in 2025, not 2024)
                    if end and end[:4] == str(fy):
                        if end not in fy_by_end:
                            fy_by_end[end] = {'end': end, 'val': e['val'], 'fy': fy}

            # Step 2: Get all 10-Q entries grouped by end date
            q_by_end = defaultdict(list)  # {end_date: [entries]}
            for e in entries:
                if e.get('form') == '10-Q' and e.get('val') is not None:
                    end = e.get('end')
                    q_by_end[end].append({
                        'end': end,
                        'val': e['val'],
                        'fp': e.get('fp'),
                        'fy': e.get('fy'),
                        'form': '10-Q',
                    })

            # Step 3: For each quarterly end date, get QTD value (min of duplicates)
            qtd_values = {}  # {end_date: {end, val, fp, fy, form}}
            for end, q_entries in q_by_end.items():
                # Pick the smallest value (QTD vs YTD)
                best = min(q_entries, key=lambda x: x['val'])
                # Only keep Q1, Q2, Q3 entries
                if best['fp'] in ('Q1', 'Q2', 'Q3'):
                    qtd_values[end] = best

            # Step 4: Build fiscal year data with Q4 derived from FY - Q1 - Q2 - Q3
            quarters = []

            for fy_end in sorted(fy_by_end.keys(), reverse=True):
                fy_data = fy_by_end[fy_end]
                fy = fy_data['fy']
                fy_val = fy_data['val']

                # Find Q1, Q2, Q3 for this fiscal year
                # Q3 ends ~3 months before FY end, Q2 ~6 months, Q1 ~9 months
                fy_year = int(fy_end[:4])

                # Find matching quarters by fiscal year number in the entries
                q1_val = q2_val = q3_val = None
                q1_end = q2_end = q3_end = None

                for end, q_data in qtd_values.items():
                    q_fy = q_data['fy']
                    fp = q_data['fp']
                    # Match quarters that belong to this fiscal year
                    if q_fy == fy:
                        if fp == 'Q1':
                            q1_val = q_data['val']
                            q1_end = end
                        elif fp == 'Q2':
                            q2_val = q_data['val']
                            q2_end = end
                        elif fp == 'Q3':
                            q3_val = q_data['val']
                            q3_end = end

                # Calculate Q4 if we have all three quarters
                if q1_val is not None and q2_val is not None and q3_val is not None:
                    q4_val = fy_val - q1_val - q2_val - q3_val
                    quarters.append({
                        'end': fy_end, 'val': q4_val, 'fp': 'Q4', 'fy': fy, 'form': '10-K (derived)'
                    })
                    quarters.append({
                        'end': q3_end, 'val': q3_val, 'fp': 'Q3', 'fy': fy, 'form': '10-Q'
                    })
                    quarters.append({
                        'end': q2_end, 'val': q2_val, 'fp': 'Q2', 'fy': fy, 'form': '10-Q'
                    })
                    quarters.append({
                        'end': q1_end, 'val': q1_val, 'fp': 'Q1', 'fy': fy, 'form': '10-Q'
                    })

            # Sort by end date descending and return
            quarters = sorted(quarters, key=lambda x: x['end'], reverse=True)
            if quarters:
                return quarters[:num_quarters]

        return []

    def _calculate_ttm(self, quarterly_values: List[Dict], start_idx: int = 0) -> Optional[float]:
        """
        Calculate TTM (Trailing Twelve Months) by summing 4 quarters.

        Args:
            quarterly_values: List of quarterly data (newest first)
            start_idx: Starting index (0 = most recent 4 quarters)

        Returns:
            Sum of 4 quarters or None if insufficient data
        """
        if len(quarterly_values) < start_idx + 4:
            return None

        quarters = quarterly_values[start_idx:start_idx + 4]
        total = sum(q['val'] for q in quarters if q['val'] is not None)
        return total if len(quarters) == 4 else None

    def get_growth_metrics(
        self,
        method: str = 'fiscal_year',
    ) -> Dict[str, Optional[float]]:
        """
        Calculate growth metrics with selectable calculation method.

        Args:
            method: Calculation method
                - 'fiscal_year': YoY growth using annual 10-K data (default)
                - 'ttm': TTM (Trailing Twelve Months) growth using quarterly data
                - 'all': Return both methods for comparison

        Metrics:
            - revenue_growth: Revenue growth
            - earnings_growth: Net Income growth
            - book_value_growth: Shareholders' Equity growth
            - earnings_per_share_growth: EPS growth
            - free_cash_flow_growth: FCF growth
            - operating_income_growth: Operating Income growth
            - ebitda_growth: EBITDA growth

        Note on TTM calculation:
            TTM sums the most recent 4 quarters (regardless of fiscal year alignment)
            and compares to the 4 quarters before that. This may differ from
            Financial Datasets' proprietary methodology.
        """
        if method == 'all':
            return {
                'fiscal_year': self._get_fiscal_year_growth(),
                'ttm': self._get_ttm_growth(),
            }
        elif method == 'ttm':
            return self._get_ttm_growth()
        else:
            return self._get_fiscal_year_growth()

    def _get_fiscal_year_growth(self) -> Dict[str, Optional[float]]:
        """Calculate growth metrics using fiscal year (10-K) data."""
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

    def _get_ttm_growth(self) -> Dict[str, Optional[float]]:
        """
        Calculate growth metrics using TTM (Trailing Twelve Months).

        TTM = sum of most recent 4 quarters
        TTM Growth = (TTM_current - TTM_previous) / TTM_previous

        Where:
            - TTM_current = Q0 + Q1 + Q2 + Q3 (most recent 4 quarters)
            - TTM_previous = Q4 + Q5 + Q6 + Q7 (4 quarters before that)
        """
        # Concept mappings for quarterly data
        from data_sources.sec_edgar_financials import (
            INCOME_STATEMENT_MAPPING,
            CASH_FLOW_MAPPING,
        )

        results = {}

        # Revenue TTM
        revenue_q = self._get_quarterly_values(INCOME_STATEMENT_MAPPING.get('revenue', ['Revenues']), 'USD', 8)
        if len(revenue_q) >= 8:
            ttm_curr = self._calculate_ttm(revenue_q, 0)
            ttm_prev = self._calculate_ttm(revenue_q, 4)
            results['revenue_growth'] = self._calculate_growth(ttm_curr, ttm_prev)
        else:
            results['revenue_growth'] = None

        # Net Income TTM
        ni_q = self._get_quarterly_values(INCOME_STATEMENT_MAPPING.get('net_income', ['NetIncomeLoss']), 'USD', 8)
        if len(ni_q) >= 8:
            ttm_curr = self._calculate_ttm(ni_q, 0)
            ttm_prev = self._calculate_ttm(ni_q, 4)
            results['earnings_growth'] = self._calculate_growth(ttm_curr, ttm_prev)
        else:
            results['earnings_growth'] = None

        # Operating Income TTM
        oi_q = self._get_quarterly_values(INCOME_STATEMENT_MAPPING.get('operating_income', ['OperatingIncomeLoss']), 'USD', 8)
        if len(oi_q) >= 8:
            ttm_curr = self._calculate_ttm(oi_q, 0)
            ttm_prev = self._calculate_ttm(oi_q, 4)
            results['operating_income_growth'] = self._calculate_growth(ttm_curr, ttm_prev)
        else:
            results['operating_income_growth'] = None

        # EPS TTM (uses USD/shares unit)
        eps_concepts = INCOME_STATEMENT_MAPPING.get('earnings_per_share', ['EarningsPerShareBasic'])
        eps_q = self._get_quarterly_values(eps_concepts, 'USD/shares', 8)
        if len(eps_q) >= 8:
            ttm_curr = self._calculate_ttm(eps_q, 0)
            ttm_prev = self._calculate_ttm(eps_q, 4)
            results['earnings_per_share_growth'] = self._calculate_growth(ttm_curr, ttm_prev)
        else:
            results['earnings_per_share_growth'] = None

        # Free Cash Flow TTM
        fcf_q = self._get_quarterly_values(CASH_FLOW_MAPPING.get('free_cash_flow', ['FreeCashFlow']), 'USD', 8)
        if len(fcf_q) >= 8:
            ttm_curr = self._calculate_ttm(fcf_q, 0)
            ttm_prev = self._calculate_ttm(fcf_q, 4)
            results['free_cash_flow_growth'] = self._calculate_growth(ttm_curr, ttm_prev)
        else:
            results['free_cash_flow_growth'] = None

        # Book Value Growth - use balance sheet (instant values, not TTM)
        # For balance sheet items, we compare current vs year-ago values
        equity_q = self._get_quarterly_values(['StockholdersEquity'], 'USD', 8)
        if len(equity_q) >= 5:
            # Compare most recent to 4 quarters ago
            results['book_value_growth'] = self._calculate_growth(
                equity_q[0]['val'], equity_q[4]['val']
            )
        else:
            results['book_value_growth'] = None

        # EBITDA TTM = Operating Income TTM + D&A TTM
        da_q = self._get_quarterly_values(CASH_FLOW_MAPPING.get('depreciation_and_amortization', ['DepreciationAndAmortization']), 'USD', 8)
        if len(oi_q) >= 8 and len(da_q) >= 8:
            ebitda_curr = self._calculate_ttm(oi_q, 0) + self._calculate_ttm(da_q, 0)
            ebitda_prev = self._calculate_ttm(oi_q, 4) + self._calculate_ttm(da_q, 4)
            results['ebitda_growth'] = self._calculate_growth(ebitda_curr, ebitda_prev)
        else:
            results['ebitda_growth'] = None

        return results

    def get_all_growth_methods(self) -> Dict[str, Any]:
        """
        Get growth metrics calculated using all available methods.

        Returns a comprehensive comparison dict with:
            - fiscal_year: Growth based on annual 10-K data
            - ttm: Growth based on TTM (sum of 4 quarters)
            - quarterly_data: Raw quarterly values for debugging
        """
        fy_growth = self._get_fiscal_year_growth()
        ttm_growth = self._get_ttm_growth()

        # Get quarterly data for debugging
        from data_sources.sec_edgar_financials import INCOME_STATEMENT_MAPPING
        ni_q = self._get_quarterly_values(INCOME_STATEMENT_MAPPING.get('net_income', ['NetIncomeLoss']), 'USD', 8)

        return {
            'fiscal_year': fy_growth,
            'ttm': ttm_growth,
            'methodology_notes': {
                'fiscal_year': 'YoY growth using annual 10-K data (FY_t vs FY_t-1)',
                'ttm': 'Rolling 4-quarter sum comparison (Q0-Q3 vs Q4-Q7)',
            },
            'quarterly_net_income': [
                {'end': q['end'], 'val': q['val'], 'fp': q['fp'], 'fy': q['fy']}
                for q in ni_q[:8]
            ] if ni_q else [],
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
    # Valuation Inputs and Metrics (9)
    # =========================================================================

    def get_valuation_inputs(self) -> Dict[str, Optional[float]]:
        """Return SEC-derived base-unit inputs used by valuation formulas."""
        income = self._load_income_statements(years=2)
        balance = self._load_balance_sheets(years=1)
        cashflow = self._load_cash_flow_statements(years=2)

        inc = income[0] if income else {}
        bal = balance[0] if balance else {}
        cf = cashflow[0] if cashflow else {}

        total_debt = bal.get("total_debt")
        if total_debt is None:
            current_debt = bal.get("current_debt")
            non_current_debt = bal.get("non_current_debt")
            if current_debt is not None or non_current_debt is not None:
                total_debt = (current_debt or 0) + (non_current_debt or 0)

        operating_income = inc.get("operating_income")
        depreciation = cf.get("depreciation_and_amortization")
        ebitda = None
        if operating_income is not None and depreciation is not None:
            ebitda = operating_income + depreciation

        return {
            "outstanding_shares": bal.get("outstanding_shares"),
            "cash_and_equivalents": bal.get("cash_and_equivalents"),
            "total_debt": total_debt,
            "revenue": inc.get("revenue"),
            "ebitda": ebitda,
            "free_cash_flow": cf.get("free_cash_flow"),
            "shareholders_equity": bal.get("shareholders_equity"),
            "net_income": inc.get("net_income"),
            "earnings_per_share": inc.get("earnings_per_share"),
            "earnings_growth": self.get_growth_metrics().get("earnings_growth"),
        }

    def get_valuation_metrics(
        self,
        *,
        price: Optional[float] = None,
        valuation_inputs: Optional[Mapping[str, Optional[float]]] = None,
    ) -> Dict[str, Optional[float]]:
        """Calculate price-dependent metrics from explicit qualified price input."""
        inputs = valuation_inputs
        if inputs is None:
            inputs = self.get_valuation_inputs()
        return calculate_valuation_metrics(
            price=price,
            valuation_inputs=inputs,
        )

    # =========================================================================
    # Tech-Specific Metrics
    # =========================================================================

    def get_tech_metrics(self) -> Dict[str, Optional[float]]:
        """
        Tech-specific metrics: SBC/Revenue, R&D/Revenue, Rule of 40.

        Data sources:
        - SBC: SEC EDGAR CashFlowStatement.share_based_compensation
        - R&D: SEC EDGAR IncomeStatement.research_and_development
        - Rule of 40: revenue_growth(%) + FCF_margin(%)

        Returns:
            Dict with sbc_to_revenue, rd_to_revenue, rule_of_40,
            sbc_absolute, rd_absolute
        """
        income = self._load_income_statements(years=2)
        cashflow = self._load_cash_flow_statements(years=2)

        result: Dict[str, Optional[float]] = {
            "sbc_to_revenue": None,
            "rd_to_revenue": None,
            "rule_of_40": None,
            "sbc_absolute": None,
            "rd_absolute": None,
        }

        revenue = income[0].get("revenue") if income else None
        sbc = cashflow[0].get("share_based_compensation") if cashflow else None
        rd = income[0].get("research_and_development") if income else None
        fcf = cashflow[0].get("free_cash_flow") if cashflow else None

        if revenue and revenue > 0:
            if sbc is not None:
                result["sbc_absolute"] = sbc
                result["sbc_to_revenue"] = round(abs(sbc) / revenue, 4)
            if rd is not None:
                result["rd_absolute"] = rd
                result["rd_to_revenue"] = round(abs(rd) / revenue, 4)

        # Rule of 40 = revenue_growth(%) + FCF_margin(%)
        growth = self.get_growth_metrics()
        rev_growth = growth.get("revenue_growth")  # decimal, e.g. 0.15

        fcf_margin = None
        if revenue and revenue > 0 and fcf is not None:
            fcf_margin = fcf / revenue

        if rev_growth is not None and fcf_margin is not None:
            result["rule_of_40"] = round((rev_growth + fcf_margin) * 100, 1)

        return result

    # =========================================================================
    # Get All Metrics
    # =========================================================================

    def get_static_metrics_dict(self) -> Dict[str, Any]:
        """Return only SEC-derived, price-independent financial metrics."""
        self._load_income_statements(years=3)
        self._load_balance_sheets(years=3)
        self._load_cash_flow_statements(years=3)

        income = self._income_statements
        static_metrics: Dict[str, Any] = {
            "ticker": self.ticker,
            "report_date": income[0].get("report_period", "") if income else "",
        }
        static_metrics.update(self.get_profitability_metrics())
        static_metrics.update(self.get_efficiency_metrics())
        static_metrics.update(self.get_liquidity_metrics())
        static_metrics.update(self.get_leverage_metrics())
        static_metrics.update(self.get_growth_metrics())
        static_metrics.update(self.get_per_share_metrics())
        return static_metrics

    def get_all_metrics(self, *, price: Optional[float] = None) -> FinancialMetrics:
        """
        Calculate all 39 financial metrics.

        Returns:
            FinancialMetrics dataclass with all metrics populated
        """
        static_metrics = self.get_static_metrics_dict()
        valuation = self.get_valuation_metrics(price=price)
        return FinancialMetrics(
            **static_metrics,
            **valuation,
        )

    def get_metrics_dict(self, *, price: Optional[float] = None) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        return self.get_all_metrics(price=price).to_dict()

    def get_snapshot(self, *, price: Optional[float] = None) -> Dict[str, Any]:
        """Get metrics snapshot matching Financial Datasets API format."""
        return self.get_all_metrics(price=price).get_snapshot()


# =============================================================================
# Convenience Functions
# =============================================================================

def get_financial_metrics(
    ticker: str,
    *,
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Get all financial metrics for a ticker.

    Args:
        ticker: Stock symbol

    Returns:
        Dictionary of all 39 metrics
    """
    calc = FinancialMetricsCalculator(ticker)
    return calc.get_metrics_dict(price=price)


def get_financial_metrics_snapshot(
    ticker: str,
    *,
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Get financial metrics snapshot matching Financial Datasets API format.

    Args:
        ticker: Stock symbol

    Returns:
        Dictionary matching Financial Datasets /financial-metrics/snapshot format
    """
    calc = FinancialMetricsCalculator(ticker)
    return calc.get_snapshot(price=price)


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
        print(f"  {k}: {v}" if v is not None else f"  {k}: N/A")
