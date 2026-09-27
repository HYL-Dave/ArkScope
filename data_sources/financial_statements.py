"""Provider-neutral day-identified statement types; SA month values use read contracts."""

from dataclasses import dataclass
from typing import Optional


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
    input_basis_version: Optional[str] = None


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
    input_basis_version: Optional[str] = None


@dataclass
class CashFlowStatement:
    """Cash flow statement structure matching Financial Datasets format."""
    ticker: str
    report_period: str  # YYYY-MM-DD
    fiscal_period: str  # e.g., "2025-FY"
    period: str  # "annual" or "quarterly"
    currency: str
    # Operating Activities
    net_income: Optional[float] = None
    depreciation_and_amortization: Optional[float] = None
    share_based_compensation: Optional[float] = None
    net_cash_flow_from_operations: Optional[float] = None
    # Investing Activities
    capital_expenditure: Optional[float] = None
    property_plant_and_equipment: Optional[float] = None
    business_acquisitions_and_disposals: Optional[float] = None
    investment_acquisitions_and_disposals: Optional[float] = None
    net_cash_flow_from_investing: Optional[float] = None
    # Financing Activities
    issuance_or_repayment_of_debt_securities: Optional[float] = None
    issuance_or_purchase_of_equity_shares: Optional[float] = None
    dividends_and_other_cash_distributions: Optional[float] = None
    net_cash_flow_from_financing: Optional[float] = None
    # Cash Changes
    change_in_cash_and_equivalents: Optional[float] = None
    effect_of_exchange_rate_changes: Optional[float] = None
    ending_cash_balance: Optional[float] = None
    # Calculated
    free_cash_flow: Optional[float] = None
    input_basis_version: Optional[str] = None

