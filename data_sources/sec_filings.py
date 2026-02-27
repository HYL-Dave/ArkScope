"""
SEC Filings 整合模組

整合 SEC EDGAR API 和 edgartools，提供統一介面：
- 結構化財務數據 (XBRL)
- 10-K/10-Q 章節內容解析
- 財務報表 DataFrame

使用範例：
    from data_sources.sec_filings import SECFilingsClient

    client = SECFilingsClient('AAPL')

    # 結構化財務數據
    revenue = client.get_metric('RevenueFromContractWithCustomerExcludingAssessedTax')
    net_income = client.get_metric('NetIncomeLoss')

    # 10-K 章節內容
    business = client.get_10k_section('business')
    risk_factors = client.get_10k_section('risk_factors')

    # 財務報表
    balance_sheet = client.get_balance_sheet()
    income_stmt = client.get_income_statement()
"""

import logging
import os
from datetime import date
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import pandas as pd

# edgartools
from edgar import set_identity, Company

# 我們現有的 SEC EDGAR 實作
from .sec_edgar_source import SECEdgarDataSource, SECFiling

logger = logging.getLogger(__name__)

_DEFAULT_SEC_CONTACT = 'MindfulRL-Intraday research@example.com'


def _get_sec_user_agent() -> str:
    """Build SEC User-Agent from env var or default (with warning).

    Reads at call time (not import time) so config/.env can be loaded first.
    """
    contact = os.environ.get('SEC_CONTACT_EMAIL', '').strip()
    if contact:
        return f'MindfulRL-Intraday {contact}'
    legacy = os.environ.get('SEC_USER_AGENT', '').strip()
    if legacy:
        return legacy
    logger.warning(
        "SEC_CONTACT_EMAIL not set — using placeholder User-Agent. "
        "SEC may rate-limit or reject requests. Set SEC_CONTACT_EMAIL in config/.env"
    )
    return _DEFAULT_SEC_CONTACT


@dataclass
class FinancialMetric:
    """財務指標數據結構"""
    name: str
    value: float
    unit: str
    end_date: str
    form: str  # 10-K, 10-Q
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None  # FY, Q1, Q2, Q3, Q4


@dataclass
class FilingSection:
    """財報章節內容"""
    item_number: str  # e.g., "1", "1A", "7"
    title: str
    content: str
    filing_date: str
    form: str  # 10-K, 10-Q


class SECFilingsClient:
    """
    SEC 財報整合客戶端

    整合兩個數據來源：
    1. SEC EDGAR API (sec_edgar_source.py) - 結構化 XBRL 數據
    2. edgartools - 10-K/10-Q 章節內容解析

    Usage:
        client = SECFilingsClient('AAPL')

        # 取得財務指標
        metrics = client.get_metrics(['NetIncomeLoss', 'Assets'])

        # 取得 10-K 章節
        business = client.get_10k_section('business')

        # 取得財務報表 DataFrame
        balance_sheet = client.get_balance_sheet()
    """

    # 常用財務指標對照表
    COMMON_METRICS = {
        # 收入相關
        'revenue': 'RevenueFromContractWithCustomerExcludingAssessedTax',
        'total_revenue': 'Revenues',
        'cost_of_revenue': 'CostOfGoodsAndServicesSold',
        'gross_profit': 'GrossProfit',

        # 獲利相關
        'operating_income': 'OperatingIncomeLoss',
        'net_income': 'NetIncomeLoss',
        'eps_basic': 'EarningsPerShareBasic',
        'eps_diluted': 'EarningsPerShareDiluted',

        # 資產負債表
        'total_assets': 'Assets',
        'total_liabilities': 'Liabilities',
        'stockholders_equity': 'StockholdersEquity',
        'cash': 'CashAndCashEquivalentsAtCarryingValue',
        'long_term_debt': 'LongTermDebt',

        # 股票相關
        'shares_outstanding': 'CommonStockSharesOutstanding',
    }

    # 10-K 章節對照
    SECTION_MAP = {
        'business': ('1', 'business'),
        'risk_factors': ('1A', 'risk_factors'),
        'properties': ('2', None),
        'legal_proceedings': ('3', None),
        'mda': ('7', 'management_discussion'),
        'management_discussion': ('7', 'management_discussion'),
        'financial_statements': ('8', 'financials'),
        'controls_procedures': ('9A', None),
    }

    def __init__(
        self,
        ticker: str,
        user_agent: Optional[str] = None,
    ):
        """
        初始化 SEC 財報客戶端

        Args:
            ticker: 股票代號 (e.g., 'AAPL')
            user_agent: SEC 要求的身份識別 (e.g., 'your.name@example.com')
        """
        self.ticker = ticker.upper()
        self.user_agent = user_agent or _get_sec_user_agent()

        # 初始化 SEC EDGAR API (我們的實作)
        self._sec_api = SECEdgarDataSource(user_agent=self.user_agent)

        # 初始化 edgartools
        set_identity(self.user_agent)
        self._company = Company(self.ticker)

        # 快取
        self._facts_cache: Optional[Dict] = None
        self._filings_cache: Dict[str, Any] = {}

    @property
    def company_name(self) -> str:
        """公司名稱"""
        return self._company.name

    @property
    def cik(self) -> str:
        """CIK 編號"""
        return str(self._company.cik)

    # ==================== 結構化財務數據 (XBRL) ====================

    def get_company_facts(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        取得公司所有 XBRL 財務指標

        Returns:
            包含所有財務指標的字典
        """
        if self._facts_cache is None or force_refresh:
            self._facts_cache = self._sec_api.fetch_company_facts(self.ticker)
        return self._facts_cache

    def get_metric(
        self,
        metric_name: str,
        form_filter: Optional[List[str]] = None,
        periods: int = 5,
    ) -> List[FinancialMetric]:
        """
        取得特定財務指標的歷史數據

        Args:
            metric_name: 指標名稱，可以是簡稱 (e.g., 'revenue') 或完整名稱
            form_filter: 篩選表格類型 ['10-K', '10-Q']，預設只取 10-K
            periods: 返回的期數

        Returns:
            FinancialMetric 列表，按日期降序排列
        """
        # 轉換簡稱
        if metric_name.lower() in self.COMMON_METRICS:
            metric_name = self.COMMON_METRICS[metric_name.lower()]

        if form_filter is None:
            form_filter = ['10-K']

        facts = self.get_company_facts()
        if not facts:
            return []

        # 在 us-gaap 中尋找
        us_gaap = facts.get('facts', {}).get('us-gaap', {})
        metric_data = us_gaap.get(metric_name)

        if not metric_data:
            logger.warning(f"Metric '{metric_name}' not found for {self.ticker}")
            return []

        results = []
        units = metric_data.get('units', {})

        for unit_type, values in units.items():
            for v in values:
                form = v.get('form', '')
                if form not in form_filter:
                    continue

                results.append(FinancialMetric(
                    name=metric_name,
                    value=v.get('val'),
                    unit=unit_type,
                    end_date=v.get('end', ''),
                    form=form,
                    fiscal_year=v.get('fy'),
                    fiscal_period=v.get('fp'),
                ))

        # 按日期排序
        results.sort(key=lambda x: x.end_date, reverse=True)
        return results[:periods]

    def get_metrics(
        self,
        metric_names: List[str],
        form_filter: Optional[List[str]] = None,
    ) -> Dict[str, List[FinancialMetric]]:
        """
        批量取得多個財務指標

        Args:
            metric_names: 指標名稱列表
            form_filter: 篩選表格類型

        Returns:
            {metric_name: [FinancialMetric, ...]}
        """
        return {
            name: self.get_metric(name, form_filter)
            for name in metric_names
        }

    def get_latest_metrics(
        self,
        metric_names: Optional[List[str]] = None,
    ) -> Dict[str, FinancialMetric]:
        """
        取得最新一期的財務指標

        Args:
            metric_names: 指標名稱列表，預設為常用指標

        Returns:
            {metric_name: FinancialMetric}
        """
        if metric_names is None:
            metric_names = list(self.COMMON_METRICS.keys())

        result = {}
        for name in metric_names:
            metrics = self.get_metric(name, periods=1)
            if metrics:
                result[name] = metrics[0]

        return result

    def list_available_metrics(self) -> List[str]:
        """列出所有可用的財務指標名稱"""
        facts = self.get_company_facts()
        if not facts:
            return []

        us_gaap = facts.get('facts', {}).get('us-gaap', {})
        return list(us_gaap.keys())

    # ==================== 10-K/10-Q 章節內容 ====================

    def get_filing(
        self,
        form: str = '10-K',
        index: int = 0,
    ) -> Optional[Any]:
        """
        取得特定財報的 edgartools 物件

        Args:
            form: 表格類型 ('10-K', '10-Q', '8-K')
            index: 第幾份 (0 = 最新)

        Returns:
            edgartools filing 物件
        """
        cache_key = f"{form}_{index}"
        if cache_key not in self._filings_cache:
            filings = self._company.get_filings(form=form)
            if filings and len(filings) > index:
                self._filings_cache[cache_key] = filings[index].obj()
            else:
                return None

        return self._filings_cache[cache_key]

    def get_10k_section(
        self,
        section: str,
        year_index: int = 0,
        max_length: Optional[int] = None,
    ) -> Optional[FilingSection]:
        """
        取得 10-K 特定章節的內容

        Args:
            section: 章節名稱，支援:
                - 'business' (Item 1)
                - 'risk_factors' (Item 1A)
                - 'mda' 或 'management_discussion' (Item 7)
                - 'financial_statements' (Item 8)
            year_index: 第幾年的 10-K (0 = 最新)
            max_length: 最大字元數，None = 不限制

        Returns:
            FilingSection 物件
        """
        section_lower = section.lower()
        if section_lower not in self.SECTION_MAP:
            logger.warning(f"Unknown section: {section}")
            return None

        item_number, attr_name = self.SECTION_MAP[section_lower]

        ten_k = self.get_filing('10-K', year_index)
        if not ten_k:
            return None

        content = None
        if attr_name and hasattr(ten_k, attr_name):
            content = getattr(ten_k, attr_name)

        if content is None:
            logger.warning(f"Section '{section}' not available")
            return None

        content_str = str(content)
        if max_length and len(content_str) > max_length:
            content_str = content_str[:max_length] + "\n... [truncated]"

        return FilingSection(
            item_number=item_number,
            title=section,
            content=content_str,
            filing_date=str(ten_k.filing_date) if hasattr(ten_k, 'filing_date') else '',
            form='10-K',
        )

    def get_all_10k_sections(
        self,
        year_index: int = 0,
        max_length: int = 10000,
    ) -> Dict[str, FilingSection]:
        """
        取得 10-K 所有主要章節

        Args:
            year_index: 第幾年的 10-K
            max_length: 每個章節的最大字元數

        Returns:
            {section_name: FilingSection}
        """
        sections = ['business', 'risk_factors', 'mda']
        result = {}

        for section in sections:
            content = self.get_10k_section(section, year_index, max_length)
            if content:
                result[section] = content

        return result

    # ==================== 財務報表 DataFrame ====================

    def get_balance_sheet(
        self,
        form: str = '10-K',
        index: int = 0,
    ) -> Optional[pd.DataFrame]:
        """
        取得資產負債表 DataFrame

        Args:
            form: '10-K' 或 '10-Q'
            index: 第幾份

        Returns:
            pandas DataFrame
        """
        filing = self.get_filing(form, index)
        if not filing:
            return None

        try:
            if hasattr(filing, 'balance_sheet'):
                bs = filing.balance_sheet
                if hasattr(bs, 'to_dataframe'):
                    return bs.to_dataframe()
                elif callable(bs):
                    result = bs()
                    if hasattr(result, 'to_dataframe'):
                        return result.to_dataframe()
        except Exception as e:
            logger.warning(f"Failed to get balance sheet: {e}")

        return None

    def get_income_statement(
        self,
        form: str = '10-K',
        index: int = 0,
    ) -> Optional[pd.DataFrame]:
        """
        取得損益表 DataFrame

        Args:
            form: '10-K' 或 '10-Q'
            index: 第幾份

        Returns:
            pandas DataFrame
        """
        filing = self.get_filing(form, index)
        if not filing:
            return None

        try:
            if hasattr(filing, 'income_statement'):
                stmt = filing.income_statement
                if hasattr(stmt, 'to_dataframe'):
                    return stmt.to_dataframe()
                elif callable(stmt):
                    result = stmt()
                    if hasattr(result, 'to_dataframe'):
                        return result.to_dataframe()
        except Exception as e:
            logger.warning(f"Failed to get income statement: {e}")

        return None

    def get_cash_flow_statement(
        self,
        form: str = '10-K',
        index: int = 0,
    ) -> Optional[pd.DataFrame]:
        """
        取得現金流量表 DataFrame

        Args:
            form: '10-K' 或 '10-Q'
            index: 第幾份

        Returns:
            pandas DataFrame
        """
        filing = self.get_filing(form, index)
        if not filing:
            return None

        try:
            if hasattr(filing, 'cash_flow_statement'):
                stmt = filing.cash_flow_statement
                if hasattr(stmt, 'to_dataframe'):
                    return stmt.to_dataframe()
                elif callable(stmt):
                    result = stmt()
                    if hasattr(result, 'to_dataframe'):
                        return result.to_dataframe()
        except Exception as e:
            logger.warning(f"Failed to get cash flow statement: {e}")

        return None

    # ==================== 財報列表 ====================

    def get_filings_list(
        self,
        form_types: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SECFiling]:
        """
        取得財報列表

        Args:
            form_types: 表格類型列表，預設 ['10-K', '10-Q', '8-K']
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            SECFiling 列表
        """
        if form_types is None:
            form_types = ['10-K', '10-Q', '8-K']

        return self._sec_api.fetch_sec_filings(
            tickers=[self.ticker],
            filing_types=form_types,
            start_date=start_date,
            end_date=end_date,
        )

    # ==================== 便捷方法 ====================

    def summary(self) -> Dict[str, Any]:
        """
        取得公司財務摘要

        Returns:
            包含關鍵財務指標的字典
        """
        latest = self.get_latest_metrics([
            'revenue', 'net_income', 'total_assets',
            'stockholders_equity', 'eps_diluted', 'cash'
        ])

        return {
            'ticker': self.ticker,
            'company_name': self.company_name,
            'cik': self.cik,
            'latest_metrics': {
                k: {
                    'value': v.value,
                    'unit': v.unit,
                    'end_date': v.end_date,
                    'form': v.form,
                }
                for k, v in latest.items()
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """匯出為字典格式"""
        return {
            'ticker': self.ticker,
            'company_name': self.company_name,
            'cik': self.cik,
            'available_metrics': len(self.list_available_metrics()),
        }