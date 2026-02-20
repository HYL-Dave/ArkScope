"""
Tests for SEC EDGAR financials quarterly + annual extraction.

Uses mock XBRL JSON to avoid real SEC API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from data_sources.sec_edgar_financials import SECEdgarFinancials


# ============================================================
# Mock XBRL data (simulates SEC EDGAR companyfacts JSON)
# ============================================================

def _make_entry(fy, fp, form, end, val):
    """Helper to create a single XBRL entry."""
    return {
        "fy": fy, "fp": fp, "form": form,
        "end": end, "val": val, "filed": end,
    }


def _build_mock_facts():
    """Build mock company facts with annual + quarterly data.

    Simulates a company with fiscal year ending Sep (like Apple):
    - FY2024 10-K (end 2024-09-28)
    - FY2024 Q1-Q3 10-Q
    - FY2023 10-K + Q1-Q3
    """
    revenue_entries = [
        # FY2024 annual (10-K)
        _make_entry(2024, "FY", "10-K", "2024-09-28", 391000000000),
        # FY2024 quarters (10-Q)
        _make_entry(2024, "Q1", "10-Q", "2023-12-30", 119600000000),
        _make_entry(2024, "Q2", "10-Q", "2024-03-30", 90800000000),
        _make_entry(2024, "Q3", "10-Q", "2024-06-29", 85800000000),
        # Q4 only in 10-K (no separate 10-Q filing for Q4)
        # FY2023 annual
        _make_entry(2023, "FY", "10-K", "2023-09-30", 383300000000),
        # FY2023 quarters
        _make_entry(2023, "Q1", "10-Q", "2022-12-31", 117200000000),
        _make_entry(2023, "Q2", "10-Q", "2023-04-01", 94800000000),
        _make_entry(2023, "Q3", "10-Q", "2023-07-01", 81800000000),
    ]

    net_income_entries = [
        _make_entry(2024, "FY", "10-K", "2024-09-28", 93700000000),
        _make_entry(2024, "Q1", "10-Q", "2023-12-30", 33900000000),
        _make_entry(2024, "Q2", "10-Q", "2024-03-30", 23600000000),
        _make_entry(2024, "Q3", "10-Q", "2024-06-29", 21400000000),
        _make_entry(2023, "FY", "10-K", "2023-09-30", 97000000000),
        _make_entry(2023, "Q1", "10-Q", "2022-12-31", 30000000000),
        _make_entry(2023, "Q2", "10-Q", "2023-04-01", 24200000000),
        _make_entry(2023, "Q3", "10-Q", "2023-07-01", 19900000000),
    ]

    assets_entries = [
        _make_entry(2024, "FY", "10-K", "2024-09-28", 364980000000),
        _make_entry(2024, "Q1", "10-Q", "2023-12-30", 353510000000),
        _make_entry(2024, "Q2", "10-Q", "2024-03-30", 337410000000),
        _make_entry(2024, "Q3", "10-Q", "2024-06-29", 331600000000),
        _make_entry(2023, "FY", "10-K", "2023-09-30", 352580000000),
        _make_entry(2023, "Q1", "10-Q", "2022-12-31", 346750000000),
        _make_entry(2023, "Q2", "10-Q", "2023-04-01", 332160000000),
        _make_entry(2023, "Q3", "10-Q", "2023-07-01", 335040000000),
    ]

    return {
        "cik": 320193,
        "entityName": "Test Corp",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "units": {"USD": revenue_entries},
                },
                "NetIncomeLoss": {
                    "label": "Net Income",
                    "units": {"USD": net_income_entries},
                },
                "Assets": {
                    "label": "Total Assets",
                    "units": {"USD": assets_entries},
                },
            }
        },
    }


# ============================================================
# _get_quarterly_periods() tests
# ============================================================

class TestGetQuarterlyPeriods:

    def setup_method(self):
        self.sec = SECEdgarFinancials()
        self.facts = _build_mock_facts()

    def test_finds_quarterly_periods(self):
        """Should return (fy, fp) pairs for quarterly data."""
        periods = self.sec._get_quarterly_periods(self.facts, quarters=8)
        assert len(periods) > 0
        # Each is a (fy, fp) tuple — only Q1-Q3 from 10-Q filings
        for fy, fp in periods:
            assert isinstance(fy, int)
            assert fp in {"Q1", "Q2", "Q3"}

    def test_newest_first(self):
        """Periods should be sorted newest first (by end_date)."""
        periods = self.sec._get_quarterly_periods(self.facts, quarters=8)
        # The first period should be the most recent 10-Q
        # FY2024 Q3 (end 2024-06-29) should be first
        assert periods[0] == (2024, "Q3")

    def test_no_q4_from_10k(self):
        """Q4 should NOT come from 10-K — 10-K FY is annual total, not Q4."""
        periods = self.sec._get_quarterly_periods(self.facts, quarters=8)
        q4_entries = [(fy, fp) for fy, fp in periods if fp == "Q4"]
        # No Q4 because mock data has no separate 10-Q Q4 filing
        assert len(q4_entries) == 0

    def test_respects_quarters_limit(self):
        """Should respect the quarters parameter."""
        periods = self.sec._get_quarterly_periods(self.facts, quarters=4)
        assert len(periods) <= 4

    def test_empty_facts(self):
        """Returns empty for empty/None facts."""
        assert self.sec._get_quarterly_periods(None) == []
        assert self.sec._get_quarterly_periods({}) == []


# ============================================================
# _get_report_end_date() tests
# ============================================================

class TestGetReportEndDate:

    def setup_method(self):
        self.sec = SECEdgarFinancials()
        self.facts = _build_mock_facts()

    def test_finds_annual_end_date(self):
        """Should find the actual end date for annual reports."""
        end = self.sec._get_report_end_date(self.facts, 2024, "10-K", "FY")
        assert end == "2024-09-28"  # Apple-style Sep fiscal year end

    def test_finds_quarterly_end_date(self):
        """Should find end date for quarterly reports."""
        end = self.sec._get_report_end_date(self.facts, 2024, "10-Q", "Q1")
        assert end == "2023-12-30"

    def test_q4_no_10q_returns_none(self):
        """Q4 with no separate 10-Q filing returns None."""
        end = self.sec._get_report_end_date(self.facts, 2024, "10-Q", "Q4")
        # No 10-Q Q4 in mock data — returns None
        assert end is None

    def test_no_match_returns_none(self):
        """Returns None when no matching period found."""
        end = self.sec._get_report_end_date(self.facts, 2099, "10-K", "FY")
        assert end is None


# ============================================================
# Income statement extraction tests
# ============================================================

class TestIncomeStatement:

    def setup_method(self):
        self.sec = SECEdgarFinancials()
        self.sec._cache = {"TEST": _build_mock_facts()}

    def test_annual_still_works(self):
        """Annual extraction should still work (regression test)."""
        stmts = self.sec.get_income_statement("TEST", years=2, period="annual")
        assert len(stmts) == 2
        assert stmts[0].period == "annual"
        assert stmts[0].fiscal_period == "2024-FY"
        # Actual end date, not hardcoded 12-31
        assert stmts[0].report_period == "2024-09-28"

    def test_quarterly_returns_data(self):
        """Quarterly extraction should return quarterly statements."""
        stmts = self.sec.get_income_statement("TEST", years=2, period="quarterly")
        assert len(stmts) > 0
        for stmt in stmts:
            assert stmt.period == "quarterly"

    def test_quarterly_fiscal_period_format(self):
        """Quarterly fiscal_period should be like '2024-Q3'."""
        stmts = self.sec.get_income_statement("TEST", years=2, period="quarterly")
        for stmt in stmts:
            parts = stmt.fiscal_period.split("-")
            assert len(parts) == 2
            assert parts[1] in {"Q1", "Q2", "Q3", "Q4"}

    def test_quarterly_has_revenue(self):
        """Quarterly income statements should have revenue values."""
        stmts = self.sec.get_income_statement("TEST", years=1, period="quarterly")
        # At least some should have revenue (from Revenues concept)
        revenues = [s.revenue for s in stmts if s.revenue is not None]
        assert len(revenues) > 0

    def test_quarterly_report_period_not_dec31(self):
        """Report period should reflect actual end dates, not hardcoded Dec 31."""
        stmts = self.sec.get_income_statement("TEST", years=1, period="quarterly")
        for stmt in stmts:
            # Should not all end on Dec 31
            assert not all(s.report_period.endswith("-12-31") for s in stmts)
            break

    def test_annual_report_period_uses_real_date(self):
        """Annual report_period should use actual end date, not 12-31."""
        stmts = self.sec.get_income_statement("TEST", years=1, period="annual")
        # Our mock company has fiscal year ending Sep 28
        assert stmts[0].report_period == "2024-09-28"


# ============================================================
# Balance sheet extraction tests
# ============================================================

class TestBalanceSheet:

    def setup_method(self):
        self.sec = SECEdgarFinancials()
        self.sec._cache = {"TEST": _build_mock_facts()}

    def test_annual_still_works(self):
        stmts = self.sec.get_balance_sheet("TEST", years=2, period="annual")
        assert len(stmts) == 2
        assert stmts[0].fiscal_period == "2024-FY"

    def test_quarterly_returns_data(self):
        stmts = self.sec.get_balance_sheet("TEST", years=1, period="quarterly")
        assert len(stmts) > 0
        for stmt in stmts:
            assert stmt.period == "quarterly"


# ============================================================
# Cash flow statement extraction tests
# ============================================================

class TestCashFlowStatement:

    def setup_method(self):
        self.sec = SECEdgarFinancials()
        self.sec._cache = {"TEST": _build_mock_facts()}

    def test_annual_still_works(self):
        stmts = self.sec.get_cash_flow_statement("TEST", years=2, period="annual")
        assert len(stmts) == 2
        assert stmts[0].fiscal_period == "2024-FY"

    def test_quarterly_returns_data(self):
        stmts = self.sec.get_cash_flow_statement("TEST", years=1, period="quarterly")
        assert len(stmts) > 0
        for stmt in stmts:
            assert stmt.period == "quarterly"