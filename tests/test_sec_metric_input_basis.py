"""Raw CompanyFacts must survive period/debt selection before ratios are allowed."""

from dataclasses import asdict

import pytest

from data_sources.financial_metrics_calculator import FinancialMetricsCalculator
from data_sources.sec_edgar_financials import SECEdgarFinancials
from src.fundamentals.cache import validate_positive_annual_sec_payload
from src.tools.analysis_tools import _build_result_from_statements


def entry(value, *, end="2025-12-31", start=None, fy=2025, fp="FY", form="10-K"):
    return {"val":value, "end":end, "fy":fy, "fp":fp, "form":form, "filed":end,
            **({"start":start} if start else {})}


def extractor(concepts):
    sec = SECEdgarFinancials()
    sec._cache = {"TEST":{"facts":{"us-gaap": {key:{"units":{"USD": rows}}
                                                  for key, rows in concepts.items()}}}}
    return sec


def results(sec, period="annual"):
    income = sec.get_income_statement("TEST", years=2, period=period)
    balance = sec.get_balance_sheet("TEST", years=2, period=period)
    cash = sec.get_cash_flow_statement("TEST", years=2, period=period)
    cold = _build_result_from_statements("TEST", "sec_edgar", income, balance, cash)
    warm = validate_positive_annual_sec_payload(cold.model_dump(), ticker="TEST")
    calc = FinancialMetricsCalculator.__new__(FinancialMetricsCalculator)
    calc.ticker, calc.years_for_growth = "TEST", 2
    calc._income_statements, calc._balance_sheets, calc._cash_flow_statements = (
        [asdict(row) for row in rows] for rows in (income,balance,cash))
    return cold, warm, calc


@pytest.mark.parametrize("long_term", [True, False])
def test_overlapping_debt_concepts_never_become_total_debt(long_term):
    concepts = {"Assets":[entry(200)], "StockholdersEquity":[entry(100)],
        "DebtCurrent":[entry(30)], "ShortTermBorrowings":[entry(20)],
        "LongTermDebtCurrent":[entry(10)], "LongTermDebtNoncurrent":[entry(70)]}
    if long_term:
        concepts["LongTermDebt"] = [entry(80)]
    cold, warm, calc = results(extractor(concepts))
    assert cold.debt_to_equity == warm.debt_to_equity == 1
    assert calc.get_leverage_metrics()["debt_to_equity"] == 1


def test_partial_current_debt_components_are_not_a_complete_total():
    cold, warm, calc = results(extractor({"Assets":[entry(200)], "StockholdersEquity":[entry(100)],
        "CommercialPaper":[entry(20)], "LongTermDebtNoncurrent":[entry(70)]}))
    assert cold.debt_to_equity is None and warm.debt_to_equity is None
    assert calc.get_leverage_metrics()["debt_to_equity"] is None


def test_cumulative_only_quarters_are_not_quarter_over_quarter_growth():
    revenue = [entry(100*i, start="2025-01-01", end=end, fp=f"Q{i}", form="10-Q")
               for i,end in enumerate(["2025-03-31","2025-06-30","2025-09-30"],1)]
    assets = [entry(200, end=row["end"], fp=row["fp"], form="10-Q") for row in revenue]
    cold, warm, _ = results(extractor({"Assets":assets,"Revenues":revenue}), "quarterly")
    assert cold.income_statements[0].data.get("revenue") is None
    assert cold.revenue_growth is None and warm.revenue_growth is None


def test_comparative_income_cannot_be_relabeled_with_current_balance_year():
    cold, warm, calc = results(extractor({
        "NetIncomeLoss":[entry(10, start="2024-01-01", end="2024-12-31", fy=2025)],
        "Assets":[entry(200)], "StockholdersEquity":[entry(100)]}))
    assert cold.roe is None and warm.roe is None
    assert calc.get_profitability_metrics().get("return_on_equity") is None


def test_valid_current_fact_period_remains_usable_and_survives_cache():
    cold, warm, calc = results(extractor({"Revenues":[entry(100,start="2025-01-01")],
        "NetIncomeLoss":[entry(10,start="2025-01-01")], "Assets":[entry(200)], "StockholdersEquity":[entry(100)]}))
    assert cold.roe == warm.roe == calc.get_profitability_metrics()["return_on_equity"] == 0.1


def test_unversioned_warm_sec_statements_do_not_bypass_input_guards():
    cold, _, _ = results(extractor({"Assets":[entry(200)], "StockholdersEquity":[entry(100)],
        "NetIncomeLoss":[entry(10,start="2025-01-01")]}))
    payload = cold.model_dump()
    for name in ("income_statements","balance_sheet","cash_flow_statements"):
        for row in payload[name] or []:
            row.pop("input_basis_version", None)
    warm = validate_positive_annual_sec_payload(payload, ticker="TEST")
    assert warm.roe is None
    assert warm.metric_gaps["roe"] == "sec_statement_basis_unverified"


def test_cashflow_without_capex_is_not_free_cashflow():
    cold, warm, _ = results(extractor({"Assets":[entry(200)],
        "NetCashProvidedByUsedInOperatingActivities":[entry(30,start="2025-01-01")]}))
    assert cold.free_cash_flow is None and warm.free_cash_flow is None


@pytest.mark.parametrize("start", [None, "2025-12-31", "2026-01-01", "2024-01-01"])
def test_annual_income_requires_a_valid_annual_duration(start):
    cold, warm, _ = results(extractor({"Assets":[entry(200)], "StockholdersEquity":[entry(100)],
        "NetIncomeLoss":[entry(10,start=start)]}))
    assert cold.roe is None and warm.roe is None


def test_unknown_currency_is_not_read_as_usd_and_share_units_are_preserved():
    sec = extractor({"Assets":[entry(200)], "StockholdersEquity":[entry(100)]})
    concepts = sec._cache["TEST"]["facts"]["us-gaap"]
    concepts["NetIncomeLoss"] = {"units":{"EUR":[entry(10,start="2025-01-01")]}}
    concepts["EarningsPerShareBasic"] = {"units":{"USD/shares":[entry(2,start="2025-01-01")]}}
    concepts["CommonStockSharesOutstanding"] = {"units":{"shares":[entry(50)]}}
    cold, warm, _ = results(sec)
    assert cold.roe is None and warm.roe is None
    assert cold.income_statements[0].data["earnings_per_share"] == 2
    assert cold.balance_sheet[0].data["outstanding_shares"] == 50


@pytest.mark.parametrize("period,fp,form,end,start,later", [
    ("annual", "FY", "10-K", "2025-12-31", "2025-01-01", "2026-02-10"),
    ("quarterly", "Q2", "10-Q", "2025-06-30", "2025-04-01", "2025-08-10"),
])
def test_later_instant_disclosure_cannot_date_any_statement(period, fp, form, end, start, later):
    basis = dict(fp=fp, form=form, end=end)
    sec = extractor({"Assets": [entry(200, **basis)],
                     "Revenues": [entry(100, start=start, **basis)],
                     "NetCashProvidedByUsedInOperatingActivities": [entry(30, start=start, **basis)]})
    concepts = sec._cache["TEST"]["facts"]["us-gaap"]
    concepts["CommonStockSharesOutstanding"] = {"units": {"shares": [entry(50, end=later, fp=fp, form=form)]}}
    concepts["Assets"]["units"]["EUR"] = [entry(900, end=later, fp=fp, form=form)]
    income = sec.get_income_statement("TEST", years=1, period=period)[0]
    balance = sec.get_balance_sheet("TEST", years=1, period=period)[0]
    cash = sec.get_cash_flow_statement("TEST", years=1, period=period)[0]
    assert income.report_period == balance.report_period == cash.report_period == end
    assert income.revenue == 100 and balance.total_assets == 200
    assert cash.net_cash_flow_from_operations == 30
    assert balance.outstanding_shares is None


def test_arbitrary_instant_disclosure_is_not_a_statement_period_anchor():
    sec = extractor({"CommonStockSharesOutstanding": [entry(50)]})
    assert sec._get_report_end_date(sec._cache["TEST"], 2025, "10-K", "FY") is None
