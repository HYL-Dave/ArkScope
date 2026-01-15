"""
SEC EDGAR Financial Statements Converter.

Converts SEC EDGAR XBRL data to structured financial statements format
matching the Financial Datasets API structure.

Usage:
    from data_sources.sec_edgar_financials import SECEdgarFinancials

    sec_fin = SECEdgarFinancials()

    # Get income statement (same format as Financial Datasets)
    income_stmt = sec_fin.get_income_statement('AAPL', years=5)

    # Get balance sheet
    balance_sheet = sec_fin.get_balance_sheet('AAPL', years=5)

    # Get all financials as DataFrame
    df = sec_fin.get_financials_dataframe('AAPL', statement='income')
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pandas as pd

from .sec_edgar_source import SECEdgarDataSource

logger = logging.getLogger(__name__)


@dataclass
class IncomeStatement:
    """Income statement structure matching Financial Datasets format."""
    ticker: str
    report_period: str  # YYYY-MM-DD
    fiscal_period: str  # e.g., "2025-FY"
    period: str  # "annual" or "quarterly"
    currency: str
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_expense: Optional[float] = None
    selling_general_and_administrative_expenses: Optional[float] = None
    research_and_development: Optional[float] = None
    operating_income: Optional[float] = None
    interest_expense: Optional[float] = None
    ebit: Optional[float] = None
    income_tax_expense: Optional[float] = None
    net_income: Optional[float] = None
    net_income_common_stock: Optional[float] = None
    earnings_per_share: Optional[float] = None
    earnings_per_share_diluted: Optional[float] = None
    dividends_per_common_share: Optional[float] = None
    weighted_average_shares: Optional[float] = None
    weighted_average_shares_diluted: Optional[float] = None


@dataclass
class BalanceSheet:
    """Balance sheet structure matching Financial Datasets format."""
    ticker: str
    report_period: str
    fiscal_period: str
    period: str
    currency: str
    total_assets: Optional[float] = None
    current_assets: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    inventory: Optional[float] = None
    current_investments: Optional[float] = None
    trade_and_non_trade_receivables: Optional[float] = None
    non_current_assets: Optional[float] = None
    property_plant_and_equipment: Optional[float] = None
    goodwill_and_intangible_assets: Optional[float] = None
    investments: Optional[float] = None
    non_current_investments: Optional[float] = None
    total_liabilities: Optional[float] = None
    current_liabilities: Optional[float] = None
    current_debt: Optional[float] = None
    trade_and_non_trade_payables: Optional[float] = None
    deferred_revenue: Optional[float] = None
    non_current_liabilities: Optional[float] = None
    non_current_debt: Optional[float] = None
    shareholders_equity: Optional[float] = None
    retained_earnings: Optional[float] = None
    accumulated_other_comprehensive_income: Optional[float] = None
    outstanding_shares: Optional[float] = None
    total_debt: Optional[float] = None


# SEC EDGAR concept mappings
# Some companies use different concept names, so we try alternatives
INCOME_STATEMENT_MAPPING = {
    'revenue': [
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'Revenues',
        'SalesRevenueNet',
        'SalesRevenueGoodsNet',
    ],
    'cost_of_revenue': [
        'CostOfGoodsAndServicesSold',
        'CostOfRevenue',
        'CostOfGoodsSold',
    ],
    'gross_profit': ['GrossProfit'],
    'operating_expense': ['OperatingExpenses'],
    'selling_general_and_administrative_expenses': [
        'SellingGeneralAndAdministrativeExpense',
        'GeneralAndAdministrativeExpense',
    ],
    'research_and_development': ['ResearchAndDevelopmentExpense'],
    'operating_income': ['OperatingIncomeLoss'],
    'interest_expense': ['InterestExpense', 'InterestExpenseDebt'],
    'ebit': ['OperatingIncomeLoss'],  # EBIT ≈ Operating Income for most companies
    'income_tax_expense': ['IncomeTaxExpenseBenefit'],
    'net_income': ['NetIncomeLoss'],
    'net_income_common_stock': [
        'NetIncomeLossAvailableToCommonStockholdersBasic',
        'NetIncomeLoss',
    ],
    'earnings_per_share': ['EarningsPerShareBasic'],
    'earnings_per_share_diluted': ['EarningsPerShareDiluted'],
    'dividends_per_common_share': ['CommonStockDividendsPerShareDeclared'],
    'weighted_average_shares': [
        'WeightedAverageNumberOfSharesOutstandingBasic',
        'CommonStockSharesOutstanding',
    ],
    'weighted_average_shares_diluted': [
        'WeightedAverageNumberOfDilutedSharesOutstanding',
    ],
}

BALANCE_SHEET_MAPPING = {
    'total_assets': ['Assets'],
    'current_assets': ['AssetsCurrent'],
    'cash_and_equivalents': [
        'CashAndCashEquivalentsAtCarryingValue',
        'CashCashEquivalentsAndShortTermInvestments',
    ],
    'inventory': ['InventoryNet', 'Inventory'],
    'current_investments': [
        'ShortTermInvestments',
        'MarketableSecuritiesCurrent',
    ],
    'trade_and_non_trade_receivables': [
        'AccountsReceivableNetCurrent',
        'ReceivablesNetCurrent',
    ],
    'non_current_assets': ['AssetsNoncurrent'],
    'property_plant_and_equipment': [
        'PropertyPlantAndEquipmentNet',
        'PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization',
    ],
    'goodwill_and_intangible_assets': [
        'Goodwill',
        'IntangibleAssetsNetExcludingGoodwill',
    ],
    'investments': [
        'Investments',
        'LongTermInvestments',
    ],
    'non_current_investments': [
        'MarketableSecuritiesNoncurrent',
        'AvailableForSaleSecuritiesNoncurrent',
    ],
    'total_liabilities': ['Liabilities'],
    'current_liabilities': ['LiabilitiesCurrent'],
    'current_debt': [
        'ShortTermBorrowings',
        'DebtCurrent',
        'LongTermDebtCurrent',
    ],
    'trade_and_non_trade_payables': [
        'AccountsPayableCurrent',
        'AccountsPayableAndAccruedLiabilitiesCurrent',
    ],
    'deferred_revenue': [
        'DeferredRevenueCurrent',
        'ContractWithCustomerLiabilityCurrent',
    ],
    'non_current_liabilities': ['LiabilitiesNoncurrent'],
    'non_current_debt': [
        'LongTermDebtNoncurrent',
        'LongTermDebt',
    ],
    'shareholders_equity': [
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
    ],
    'retained_earnings': ['RetainedEarningsAccumulatedDeficit'],
    'accumulated_other_comprehensive_income': [
        'AccumulatedOtherComprehensiveIncomeLossNetOfTax',
    ],
    'outstanding_shares': [
        'CommonStockSharesOutstanding',
        'CommonStockSharesIssued',
    ],
    'total_debt': ['LongTermDebt', 'DebtAndCapitalLeaseObligations'],
}


class SECEdgarFinancials:
    """
    Converts SEC EDGAR XBRL data to structured financial statements.

    Provides the same format as Financial Datasets API but from official
    SEC data (free, unlimited access).
    """

    def __init__(self):
        self._sec = SECEdgarDataSource()
        self._cache: Dict[str, Any] = {}

    def _get_company_facts(self, ticker: str) -> Optional[Dict]:
        """Get company facts with caching."""
        if ticker not in self._cache:
            self._cache[ticker] = self._sec.fetch_company_facts(ticker)
        return self._cache[ticker]

    def _extract_concept_value(
        self,
        facts: Dict,
        concept_names: List[str],
        fiscal_year: int,
        form: str = '10-K',
        period_type: str = 'FY',
    ) -> Optional[float]:
        """
        Extract a value from SEC EDGAR facts for a specific fiscal year.

        Args:
            facts: Company facts from SEC EDGAR
            concept_names: List of concept names to try (first match wins)
            fiscal_year: Fiscal year to extract
            form: '10-K' for annual, '10-Q' for quarterly
            period_type: 'FY' for full year, 'Q1'/'Q2'/'Q3'/'Q4' for quarters

        Returns:
            The value or None if not found
        """
        if not facts or 'facts' not in facts:
            return None

        gaap = facts['facts'].get('us-gaap', {})

        for concept in concept_names:
            if concept not in gaap:
                continue

            concept_data = gaap[concept]
            if 'units' not in concept_data:
                continue

            # Try different unit types (USD, USD/shares, shares, etc.)
            for unit_type, entries in concept_data['units'].items():
                # Filter for the right form and period
                matching = [
                    e for e in entries
                    if e.get('form') == form and e.get('fp') == period_type and e.get('fy') == fiscal_year
                ]

                if not matching:
                    continue

                # If multiple matches, pick the one with the latest end date
                # (this is the actual fiscal year, not comparison periods)
                best = max(matching, key=lambda x: x.get('end', ''))
                return best.get('val')

        return None

    def _get_fiscal_years(
        self,
        facts: Dict,
        years: int = 5,
        form: str = '10-K',
    ) -> List[int]:
        """Get available fiscal years from SEC filings."""
        if not facts or 'facts' not in facts:
            return []

        gaap = facts['facts'].get('us-gaap', {})

        # Use a common concept to find available years
        for concept in ['Assets', 'Revenues', 'NetIncomeLoss']:
            if concept not in gaap:
                continue
            if 'units' not in gaap[concept]:
                continue

            for entries in gaap[concept]['units'].values():
                fy_set = set()
                for e in entries:
                    if e.get('form') == form and e.get('fp') == 'FY':
                        fy_set.add(e.get('fy'))

                if fy_set:
                    return sorted(fy_set, reverse=True)[:years]

        return []

    def get_income_statement(
        self,
        ticker: str,
        years: int = 5,
        period: str = 'annual',
    ) -> List[IncomeStatement]:
        """
        Get income statements for a ticker.

        Args:
            ticker: Stock symbol
            years: Number of years to fetch
            period: 'annual' or 'quarterly'

        Returns:
            List of IncomeStatement objects (newest first)
        """
        facts = self._get_company_facts(ticker)
        if not facts:
            logger.warning(f"No SEC data found for {ticker}")
            return []

        form = '10-K' if period == 'annual' else '10-Q'
        fp = 'FY' if period == 'annual' else None  # TODO: handle quarters

        fiscal_years = self._get_fiscal_years(facts, years, form)

        statements = []
        for fy in fiscal_years:
            stmt = IncomeStatement(
                ticker=ticker,
                report_period=f"{fy}-12-31",  # Approximate, actual varies by company
                fiscal_period=f"{fy}-FY",
                period=period,
                currency='USD',
            )

            # Extract each field
            for field, concepts in INCOME_STATEMENT_MAPPING.items():
                value = self._extract_concept_value(facts, concepts, fy, form, 'FY')
                setattr(stmt, field, value)

            statements.append(stmt)

        return statements

    def get_balance_sheet(
        self,
        ticker: str,
        years: int = 5,
        period: str = 'annual',
    ) -> List[BalanceSheet]:
        """
        Get balance sheets for a ticker.

        Args:
            ticker: Stock symbol
            years: Number of years to fetch
            period: 'annual' or 'quarterly'

        Returns:
            List of BalanceSheet objects (newest first)
        """
        facts = self._get_company_facts(ticker)
        if not facts:
            logger.warning(f"No SEC data found for {ticker}")
            return []

        form = '10-K' if period == 'annual' else '10-Q'

        fiscal_years = self._get_fiscal_years(facts, years, form)

        sheets = []
        for fy in fiscal_years:
            sheet = BalanceSheet(
                ticker=ticker,
                report_period=f"{fy}-12-31",
                fiscal_period=f"{fy}-FY",
                period=period,
                currency='USD',
            )

            for field, concepts in BALANCE_SHEET_MAPPING.items():
                value = self._extract_concept_value(facts, concepts, fy, form, 'FY')
                setattr(sheet, field, value)

            sheets.append(sheet)

        return sheets

    def get_financials_dataframe(
        self,
        ticker: str,
        statement: str = 'income',
        years: int = 5,
    ) -> pd.DataFrame:
        """
        Get financial statements as a pandas DataFrame.

        Args:
            ticker: Stock symbol
            statement: 'income' or 'balance'
            years: Number of years

        Returns:
            DataFrame with financial data
        """
        if statement == 'income':
            data = self.get_income_statement(ticker, years)
        else:
            data = self.get_balance_sheet(ticker, years)

        if not data:
            return pd.DataFrame()

        return pd.DataFrame([asdict(d) for d in data])

    def compare_with_financial_datasets(
        self,
        ticker: str,
        fd_data: Dict,
    ) -> pd.DataFrame:
        """
        Compare SEC EDGAR data with Financial Datasets API response.

        Args:
            ticker: Stock symbol
            fd_data: Response from Financial Datasets API

        Returns:
            DataFrame showing comparison
        """
        sec_income = self.get_income_statement(ticker, years=1)
        if not sec_income:
            return pd.DataFrame()

        sec = asdict(sec_income[0])

        comparison = []
        for field in sec.keys():
            if field in ['ticker', 'report_period', 'fiscal_period', 'period', 'currency']:
                continue

            sec_val = sec.get(field)
            fd_val = fd_data.get(field)

            match = '✅' if sec_val == fd_val else '❌' if sec_val and fd_val else '⚠️'

            comparison.append({
                'field': field,
                'SEC_EDGAR': sec_val,
                'Financial_Datasets': fd_val,
                'match': match,
            })

        return pd.DataFrame(comparison)


# Convenience functions
def get_income_statement(ticker: str, years: int = 5) -> List[Dict]:
    """Get income statement as list of dicts."""
    sec = SECEdgarFinancials()
    return [asdict(s) for s in sec.get_income_statement(ticker, years)]


def get_balance_sheet(ticker: str, years: int = 5) -> List[Dict]:
    """Get balance sheet as list of dicts."""
    sec = SECEdgarFinancials()
    return [asdict(s) for s in sec.get_balance_sheet(ticker, years)]