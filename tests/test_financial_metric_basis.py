"""Financial claims need matching periods and retained input evidence."""

from dataclasses import replace

import pytest

from data_sources.sec_edgar_financials import BalanceSheet, IncomeStatement
from src.tools.analysis_tools import _build_result_from_statements
from src.fundamentals.metric_basis import SEC_STATEMENT_BASIS_VERSION


def income(end="2025-12-31", fiscal="2025-FY", period="annual", **values):
    return IncomeStatement("TEST", end, fiscal, period, "USD", input_basis_version=SEC_STATEMENT_BASIS_VERSION, **values)


def balance(**values):
    return BalanceSheet("TEST", "2025-12-31", "2025-FY", "annual", "USD", input_basis_version=SEC_STATEMENT_BASIS_VERSION, **values)


def analyze(inc=(), bal=(), cash=()):
    return _build_result_from_statements("TEST", "sec_edgar", list(inc), list(bal), list(cash))


@pytest.mark.parametrize("debt,want", [(20, 0.5), (0, 0.0), (None, None)])
def test_debt_is_not_total_liabilities_and_missing_is_not_zero(debt, want):
    result = analyze(bal=[balance(total_debt=debt, total_liabilities=80, shareholders_equity=40)])
    assert result.debt_to_equity == want
    if want is not None:
        assert result.metric_basis["debt_to_equity"]["numerator"] == "total_debt"
    else:
        assert result.metric_gaps["debt_to_equity"] == "debt_unavailable"


@pytest.mark.parametrize("change", [{"report_period": "2016-12-31"}, {"currency": "EUR"}])
def test_roe_cannot_mix_independent_periods_or_currencies(change):
    result = analyze([income(net_income=10)], [replace(balance(shareholders_equity=40, total_assets=100), **change)])
    assert result.roe is None and result.roa is None
    assert result.metric_gaps["roe"] == "statement_basis_mismatch"


def test_quarterly_earnings_are_not_silently_annualized():
    result = analyze([income(period="quarterly", fiscal="2025-Q4", net_income=10)],
                     [replace(balance(shareholders_equity=40), period="quarterly", fiscal_period="2025-Q4")])
    assert result.roe is None
    assert result.metric_gaps["roe"] == "annual_income_required"


def test_annual_return_discloses_period_end_not_average_equity():
    result = analyze([income(net_income=10)], [balance(shareholders_equity=40)])
    assert result.roe == 0.25
    assert result.metric_basis["roe"]["denominator_basis"] == "period_end"


def test_nonconsecutive_years_do_not_claim_year_over_year_growth():
    result = analyze([income(revenue=120), income("2023-12-31", "2023-FY", revenue=100)])
    assert result.revenue_growth is None
    assert result.metric_gaps["revenue_growth"] == "comparable_previous_period_unavailable"


def test_quarter_growth_requires_adjacent_fiscal_quarters_and_names_its_basis():
    latest = income("2025-09-30", "2025-Q3", "quarterly", revenue=120)
    adjacent = income("2025-06-30", "2025-Q2", "quarterly", revenue=100)
    valid = analyze([latest, adjacent])
    assert valid.revenue_growth == 0.2
    assert valid.metric_basis["revenue_growth"]["comparison"] == "quarter_over_quarter"
    invalid = analyze([latest, replace(adjacent, report_period="2025-03-31", fiscal_period="2025-Q1")])
    assert invalid.revenue_growth is None


def test_cached_legacy_fundamentals_are_recomputed_without_mutating_payload():
    from src.fundamentals.cache import validate_positive_annual_sec_payload

    payload = analyze([income(net_income=10)], [balance(total_debt=20, shareholders_equity=40)]).model_dump()
    payload["debt_to_equity"] = 999
    payload["roe"] = 999
    result = validate_positive_annual_sec_payload(payload, ticker="TEST")
    assert result.debt_to_equity == 0.5 and result.roe == 0.25
    assert payload["debt_to_equity"] == 999


def test_cached_legacy_ratio_without_inputs_is_withheld_not_trusted():
    from src.fundamentals.cache import validate_positive_annual_sec_payload

    result = validate_positive_annual_sec_payload({"ticker":"TEST", "data_source":"sec_edgar",
        "snapshot_date":"2025-12-31", "roe":999, "debt_to_equity":999}, ticker="TEST")
    assert result is not None
    assert result.roe is None and result.debt_to_equity is None
    assert result.metric_gaps["roe"] == "income_unavailable"


def test_detailed_calculator_and_basic_tool_use_the_same_debt_definition():
    from dataclasses import asdict
    from data_sources.financial_metrics_calculator import FinancialMetricsCalculator

    bs = balance(total_debt=20, total_liabilities=80, shareholders_equity=40)
    calc = FinancialMetricsCalculator.__new__(FinancialMetricsCalculator)
    calc._balance_sheets = [asdict(bs)]
    calc._income_statements = []
    assert calc.get_leverage_metrics()["debt_to_equity"] == analyze(bal=[bs]).debt_to_equity == 0.5


def test_detailed_cache_without_calculation_contract_cannot_publish_old_ratios():
    from src.fundamentals.cache import validate_detailed_financials_static_payload

    result = validate_detailed_financials_static_payload({"version":2, "ticker":"TEST", "period":"annual",
        "years_for_growth":2, "data_source":"sec_edgar", "report_date":"2025-12-31",
        "static_metrics":{"debt_to_equity":999}, "tech_metrics":{}, "valuation_inputs":{}}, ticker="TEST")
    assert result is not None
    assert result["static_metrics"].get("debt_to_equity") is None
    assert result["static_metrics"]["metric_gaps"]["legacy_calculation"] == "retained_inputs_unavailable"


def calculator(inc, bal, cf=()):
    from dataclasses import asdict
    from data_sources.financial_metrics_calculator import FinancialMetricsCalculator
    calc = FinancialMetricsCalculator.__new__(FinancialMetricsCalculator)
    calc.ticker = "TEST"
    calc.years_for_growth = 2
    calc._income_statements = [asdict(row) for row in inc]
    calc._balance_sheets = [asdict(row) for row in bal]
    calc._cash_flow_statements = [asdict(row) for row in cf]
    return calc


def test_detailed_profitability_rejects_mismatched_balance_but_keeps_margins():
    calc = calculator([income(revenue=100, net_income=10)],
                      [replace(balance(shareholders_equity=40), report_period="2024-12-31")])
    result = calc.get_profitability_metrics()
    assert result["return_on_equity"] is None
    assert result["net_margin"] == 0.1


def test_detailed_growth_does_not_compare_nonadjacent_years():
    calc = calculator([income(revenue=120), income("2023-12-31", "2023-FY", revenue=100)], [])
    assert calc.get_growth_metrics()["revenue_growth"] is None


def test_missing_debt_component_is_not_assumed_zero_in_valuation():
    calc = calculator([income()], [balance(current_debt=10)])
    assert calc.get_valuation_inputs()["total_debt"] is None


def test_detailed_ebitda_does_not_mix_cashflow_years():
    from data_sources.sec_edgar_financials import CashFlowStatement
    cf = CashFlowStatement("TEST", "2024-12-31", "2024-FY", "annual", "USD", depreciation_and_amortization=5,
                           input_basis_version=SEC_STATEMENT_BASIS_VERSION)
    calc = calculator([income(operating_income=20)], [balance()], [cf])
    assert calc.get_valuation_inputs()["ebitda"] is None
    assert calc.get_tech_metrics()["sbc_to_revenue"] is None


def test_roe_and_debt_are_consistent_between_detailed_and_basic_outputs():
    inc = income(net_income=10, revenue=100)
    bs = balance(total_debt=20, shareholders_equity=40)
    calc = calculator([inc], [bs])
    result = calc.get_static_metrics_dict()
    assert result["return_on_equity"] == analyze([inc], [bs]).roe == 0.25
    assert result["debt_to_equity"] == 0.5
    assert result["calculation_version"] == "statement-basis-v1"


def test_detailed_valuation_cannot_mix_balance_and_income_periods():
    calc = calculator([income(net_income=10, revenue=100)],
                      [replace(balance(outstanding_shares=10), report_period="2024-12-31")])
    assert calc.get_valuation_inputs() == {}
    assert calc.get_static_metrics_dict()["metric_gaps"]["valuation"] == "statement_basis_mismatch"


def test_efficiency_does_not_average_nonadjacent_balance_sheets():
    calc = calculator([income(revenue=100)], [balance(total_assets=100),
                      replace(balance(total_assets=50), report_period="2023-12-31", fiscal_period="2023-FY")])
    assert calc.get_efficiency_metrics() == {}


def test_payout_does_not_mix_income_and_cashflow_periods():
    from data_sources.sec_edgar_financials import CashFlowStatement
    cf = CashFlowStatement("TEST", "2024-12-31", "2024-FY", "annual", "USD",
                          dividends_and_other_cash_distributions=10, input_basis_version=SEC_STATEMENT_BASIS_VERSION)
    calc = calculator([income(net_income=20)],
                      [replace(balance(outstanding_shares=10), report_period="2024-12-31")], [cf])
    assert calc.get_per_share_metrics()["payout_ratio"] is None


def test_extreme_numeric_input_cannot_crash_ratio_validation():
    from src.fundamentals.metric_basis import ratio
    assert ratio(10**1000, 1) is None


def test_detailed_cache_retains_valuation_period_basis():
    calc = calculator([income(revenue=100, net_income=10)], [balance(total_debt=20, outstanding_shares=10)])
    result = calc.get_static_metrics_dict()
    assert result["valuation_basis"] == {"report_period":"2025-12-31", "period":"annual", "currency":"USD"}


def test_unverified_latest_input_cannot_silently_select_an_older_year():
    latest = replace(income(revenue=200, net_income=40), input_basis_version=None)
    prior = income("2024-12-31", "2024-FY", revenue=100, net_income=10)
    assert analyze([latest, prior]).net_margin is None
    assert calculator([latest, prior], []).get_profitability_metrics().get("net_margin") is None


@pytest.mark.parametrize("method", ["standard", "fd_style", "all"])
def test_efficiency_missing_assets_does_not_crash_or_substitute_zero(method):
    prior = replace(balance(total_assets=100), report_period="2024-12-31", fiscal_period="2024-FY")
    result = calculator([income(revenue=100)], [balance(), prior]).get_efficiency_metrics(method=method)
    if method == "all":
        assert result["standard"]["asset_turnover"] is None
        assert result["fd_style"]["asset_turnover"] is None
    else:
        assert result["asset_turnover"] is None


def test_efficiency_average_requires_both_observations():
    prior = replace(balance(), report_period="2024-12-31", fiscal_period="2024-FY")
    result = calculator([income(revenue=100)], [balance(trade_and_non_trade_receivables=10), prior]).get_efficiency_metrics()
    assert result["receivables_turnover"] is None
