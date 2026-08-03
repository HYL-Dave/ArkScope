"""Storage-free valuation formula contracts."""

from __future__ import annotations

import inspect
from unittest.mock import patch


_DYNAMIC_FIELDS = (
    "market_cap",
    "enterprise_value",
    "price_to_earnings_ratio",
    "price_to_book_ratio",
    "price_to_sales_ratio",
    "enterprise_value_to_ebitda_ratio",
    "enterprise_value_to_revenue_ratio",
    "free_cash_flow_yield",
    "peg_ratio",
)


def _valuation_inputs():
    return {
        "outstanding_shares": 2_000_000.0,
        "cash_and_equivalents": 1_000_000.0,
        "total_debt": 3_000_000.0,
        "revenue": 5_000_000.0,
        "ebitda": 2_500_000.0,
        "free_cash_flow": 500_000.0,
        "shareholders_equity": 4_000_000.0,
        "net_income": 2_000_000.0,
        "earnings_per_share": 1.0,
        "earnings_growth": 0.20,
    }


def _cached_calculator():
    from data_sources.financial_metrics_calculator import FinancialMetricsCalculator

    calc = FinancialMetricsCalculator.__new__(FinancialMetricsCalculator)
    calc.ticker = "TEST"
    calc.years_for_growth = 2
    calc._income_statements = [
        {
            "report_period": "2025-12-31",
            "revenue": 5_000_000.0,
            "gross_profit": 2_000_000.0,
            "operating_income": 1_500_000.0,
            "net_income": 2_000_000.0,
            "earnings_per_share": 1.0,
        },
        {
            "report_period": "2024-12-31",
            "revenue": 4_000_000.0,
            "operating_income": 1_000_000.0,
            "net_income": 1_600_000.0,
            "earnings_per_share": 0.8,
        },
    ]
    calc._balance_sheets = [
        {
            "outstanding_shares": 2_000_000.0,
            "cash_and_equivalents": 1_000_000.0,
            "current_debt": 1_000_000.0,
            "non_current_debt": 2_000_000.0,
            "shareholders_equity": 4_000_000.0,
            "total_assets": 8_000_000.0,
            "total_liabilities": 4_000_000.0,
            "current_assets": 3_000_000.0,
            "current_liabilities": 1_500_000.0,
        },
        {
            "shareholders_equity": 3_500_000.0,
            "total_assets": 7_000_000.0,
        },
    ]
    calc._cash_flow_statements = [
        {
            "free_cash_flow": 500_000.0,
            "depreciation_and_amortization": 1_000_000.0,
        },
        {
            "free_cash_flow": 400_000.0,
            "depreciation_and_amortization": 800_000.0,
        },
    ]
    return calc


def _assert_dynamic_null(mapping):
    assert {field: mapping.get(field) for field in _DYNAMIC_FIELDS} == {
        field: None for field in _DYNAMIC_FIELDS
    }


def test_explicit_price_uses_base_unit_shares_without_million_scaling():
    from data_sources.financial_metrics_calculator import calculate_valuation_metrics

    result = calculate_valuation_metrics(
        price=10.0,
        valuation_inputs=_valuation_inputs(),
    )

    assert result == {
        "market_cap": 20_000_000.0,
        "enterprise_value": 22_000_000.0,
        "price_to_earnings_ratio": 10.0,
        "price_to_book_ratio": 5.0,
        "price_to_sales_ratio": 4.0,
        "enterprise_value_to_ebitda_ratio": 8.8,
        "enterprise_value_to_revenue_ratio": 4.4,
        "free_cash_flow_yield": 0.025,
        "peg_ratio": 0.5,
    }


def test_missing_inputs_null_only_dependent_valuation_fields():
    from data_sources.financial_metrics_calculator import calculate_valuation_metrics

    inputs = _valuation_inputs()
    inputs.update({
        "shareholders_equity": None,
        "ebitda": None,
        "free_cash_flow": None,
        "earnings_growth": None,
    })

    result = calculate_valuation_metrics(price=10.0, valuation_inputs=inputs)

    assert result == {
        "market_cap": 20_000_000.0,
        "enterprise_value": 22_000_000.0,
        "price_to_earnings_ratio": 10.0,
        "price_to_book_ratio": None,
        "price_to_sales_ratio": 4.0,
        "enterprise_value_to_ebitda_ratio": None,
        "enterprise_value_to_revenue_ratio": 4.4,
        "free_cash_flow_yield": None,
        "peg_ratio": None,
    }


def test_no_price_convenience_and_cli_paths_cannot_read_legacy_files():
    import data_sources.financial_metrics_calculator as metrics_module

    calc = _cached_calculator()

    def legacy_path_access(*_args, **_kwargs):
        raise AssertionError("legacy repository path accessed")

    with patch.object(metrics_module, "Path", side_effect=legacy_path_access, create=True):
        _assert_dynamic_null(calc.get_valuation_metrics())
        _assert_dynamic_null(calc.get_all_metrics().to_dict())
        _assert_dynamic_null(calc.get_metrics_dict())
        _assert_dynamic_null(calc.get_snapshot())
        with patch.object(metrics_module, "FinancialMetricsCalculator", return_value=calc):
            _assert_dynamic_null(metrics_module.get_financial_metrics("TEST"))
            _assert_dynamic_null(metrics_module.get_financial_metrics_snapshot("TEST"))

    for method_name in (
        "get_valuation_metrics",
        "get_all_metrics",
        "get_metrics_dict",
        "get_snapshot",
    ):
        parameter = inspect.signature(
            getattr(metrics_module.FinancialMetricsCalculator, method_name)
        ).parameters["price"]
        assert parameter.default is None
    assert not hasattr(metrics_module, "_get_current_price_ibkr")
