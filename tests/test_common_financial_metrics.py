"""Ratios require qualified same-source inputs, not merely numeric cells."""

import pytest

from src.fundamentals.adapters import read_sa_statements
from src.fundamentals.contracts import FinancialQuery
from src.sa.company_store import save_capture
from src.tools.schemas import FinancialStatement
from tests.financial_read_fixtures import financial_local, sa_payload


def sa_rows(dal, *, revenue="100", gross="25"):
    save_capture(sa_payload(values={"Total Revenues": revenue, "Gross Profit": gross,
                                    "Operating Income": "10", "Net Income": "5", "Basic EPS": "2.5"}))
    save_capture(sa_payload("balance-sheet"))
    return read_sa_statements(dal, FinancialQuery(ticker="AAPL")).statements


def calculate(rows, source="seeking_alpha"):
    from src.fundamentals.common_metrics import derive_common_metrics
    return derive_common_metrics(rows.get("income_statement", []), rows.get("balance_sheet", []),
                                 rows.get("cash_flow_statement", []), source=source)


def fd_row(*, end="2025-09-27", fiscal="2025-FY", period="annual", currency="USD", **data):
    return FinancialStatement(report_period=end, end_month=end[:7], fiscal_period=fiscal,
        period_type=period, currency=currency, period_precision="day", provider="financial_datasets",
        observation_id="a" * 64, data=data)


def test_sa_same_column_ratios(financial_local):
    rows = sa_rows(financial_local[0])
    metrics = calculate(rows)
    assert tuple(metrics[k] for k in ("gross_margin", "operating_margin", "net_margin", "current_ratio")) == (0.25, 0.1, 0.05, 2.5)
    basis = metrics["metric_basis"]["gross_margin"]
    assert basis["provider"] == "seeking_alpha" and basis["precision"] == "provider_display_rounded"
    assert basis["column_index"] == 1 and basis["end_month"] == "2025-12"
    assert basis["report_period"] is None
    assert basis["observation_id"] == rows["income_statement"][0].observation_id
    assert metrics["calculation_version"] == "common-statements-v1"


@pytest.mark.parametrize("change,reason", [
    (lambda row: setattr(row, "column_index", None), "same_column_required"),
    (lambda row: setattr(row, "observation_id", None), "same_column_required"),
    (lambda row: setattr(row, "currency", None), "currency_unknown"),
    (lambda row: setattr(row.value_metadata["gross_profit"], "currency", "EUR"), "currency_mismatch"),
    (lambda row: row.data.update(gross_profit="99"), "same_column_required"),
])
def test_no_cross_column_or_currency_arithmetic(financial_local, change, reason):
    rows = sa_rows(financial_local[0])
    change(rows["income_statement"][0])
    metrics = calculate(rows)
    assert metrics["gross_margin"] is None
    assert metrics["metric_gaps"]["gross_margin"] == reason


@pytest.mark.parametrize("revenue,gross,expected,reason", [
    ("100", "0", 0, None), ("100", "(25)", -0.25, None),
    ("0", "25", None, "positive_denominator_required"),
    ("(100)", "25", None, "positive_denominator_required"),
    ("100", "N/M", None, "not_meaningful"), ("100", "-", None, "not_available"),
    ("9007199254740993", "3002399751580331", 0.3333, None),
])
def test_sa_decimal_and_missing_values(financial_local, revenue, gross, expected, reason):
    rows = sa_rows(financial_local[0], revenue=revenue, gross=gross)
    metrics = calculate(rows)
    assert metrics["gross_margin"] == expected
    assert metrics["metric_gaps"].get("gross_margin") == reason


def test_sa_unmapped_inputs_are_not_inferred_from_liabilities(financial_local):
    metrics = calculate(sa_rows(financial_local[0]))
    for field in ("total_debt", "debt_to_equity", "cash_and_equivalents", "free_cash_flow"):
        assert metrics[field] is None and metrics["metric_gaps"][field] == "mapping_not_reviewed"
    for field in ("revenue_growth", "earnings_growth", "roa"):
        assert metrics[field] is None and metrics["metric_gaps"][field] == "exact_period_identity_unavailable"
    gap = next(g for g in metrics["input_gaps"] if g.metric == "roe")
    assert "shareholders_equity" in gap.required_inputs and "exact_period_identity" in gap.required_inputs
    assert metrics["pe_ratio"] is None and "pe_ratio" in metrics["metric_gaps"]


@pytest.mark.parametrize("noncurrent,expected", [(7, 10), (None, None)])
def test_fd_preserves_correct_debt_components(noncurrent, expected):
    rows = {"income_statement": [fd_row(revenue=100, gross_profit=25, net_income=10)],
            "balance_sheet": [fd_row(current_debt=3, non_current_debt=noncurrent, total_liabilities=900,
                                      shareholders_equity=20, current_assets=50, current_liabilities=20)]}
    metrics = calculate(rows, "financial_datasets")
    assert metrics["total_debt"] == expected
    assert metrics["debt_to_equity"] == (0.5 if expected is not None else None)
    assert metrics["gross_margin"] == 0.25 and metrics["roe"] == 0.5
    assert metrics["metric_basis"]["gross_margin"]["observation_id"] == "a" * 64


@pytest.mark.parametrize("change", [{"end": "2025-08-31"}, {"currency": "EUR"}])
def test_fd_return_ratios_require_same_date_and_currency(change):
    rows = {"income_statement": [fd_row(revenue=100, net_income=10)],
            "balance_sheet": [fd_row(**change, total_assets=100, shareholders_equity=20)]}
    metrics = calculate(rows, "financial_datasets")
    assert metrics["roe"] is None and metrics["roa"] is None


@pytest.mark.parametrize("previous,expected", [
    ([fd_row(end="2024-09-28", fiscal="2024-FY", revenue=100, net_income=10)], 1),
    ([], None),
    ([fd_row(end="2023-09-30", fiscal="2023-FY", revenue=100)], None),
    ([fd_row(end="2024-09-28", fiscal=None, revenue=100)], None),
    ([fd_row(end="2024-09-28", fiscal="2024-FY", revenue=100)] * 2, None),
])
def test_fd_growth_requires_one_adjacent_fiscal_period(previous, expected):
    metrics = calculate({"income_statement": [fd_row(revenue=200, net_income=20)] + previous}, "financial_datasets")
    assert metrics["revenue_growth"] == expected


def test_fd_missing_currency_prevents_even_same_column_arithmetic():
    metrics = calculate({"income_statement": [fd_row(currency=None, revenue=100, gross_profit=25)]}, "financial_datasets")
    assert metrics["gross_margin"] is None and metrics["metric_gaps"]["gross_margin"] == "currency_unknown"
