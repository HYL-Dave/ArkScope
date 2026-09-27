"""Source-neutral contracts retain precision instead of manufacturing facts."""

from dataclasses import asdict, fields

import pytest
from pydantic import ValidationError

from src.tools.schemas import FinancialStatement


def test_dataclasses_have_one_neutral_owner():
    from data_sources import financial_statements as neutral, sec_edgar_financials as old
    for name in ("IncomeStatement", "BalanceSheet", "CashFlowStatement"):
        cls = getattr(neutral, name)
        assert getattr(old, name) is cls
        obj = cls("AAPL", "2025-12-31", "2025-Q4", "quarterly", "USD")
        assert [f.name for f in fields(obj)][:5] == [
            "ticker", "report_period", "fiscal_period", "period", "currency",
        ]
        assert asdict(obj)["currency"] == "USD"


def test_month_statement_does_not_fabricate_a_day():
    result = FinancialStatement(report_period=None, end_month="2025-12", period_precision="month",
                                period_type="annual", data={"revenue": "123400000"})
    assert result.report_period is None and result.fiscal_period is None
    assert result.end_month == "2025-12"
    assert result.data["revenue"] == "123400000"
    assert result.value_metadata == {} and result.provider is None


def test_old_day_payload_still_validates_without_new_provenance():
    result = FinancialStatement(report_period="2025-12-31", period_type="annual", data={"revenue": 123.0})
    assert result.report_period == "2025-12-31" and result.data["revenue"] == 123.0
    assert result.period_precision == "unknown" and result.observation_id is None


@pytest.mark.parametrize("extra", [
    {"end_month": "2025-00"}, {"end_month": "2025-13"}, {"end_month": "0000-01"},
    {"end_month": "2025-1"}, {"period_offset": True}, {"period_limit": 9}, {"period_limit": 0},
    {"max_age_seconds": True}, {"max_age_seconds": -1}, {"period_offset": -1},
    {"source": "sec_edgar"}, {"source": "typo"}, {"currency": "usd"},
    {"read_id": "a" * 63}, {"observation_id": "G" * 64}, {"extra": "ignored?"},
])
def test_invalid_query_rejected_before_read(extra):
    from src.fundamentals.contracts import FinancialQuery
    with pytest.raises(ValidationError):
        FinancialQuery(ticker="AAPL", **extra)


def test_query_keeps_explicit_history_and_defaults_to_stored():
    from src.fundamentals.contracts import FinancialQuery
    result = FinancialQuery(ticker="AAPL", source="seeking_alpha", end_month="2025-12")
    assert result.freshness == "stored" and result.period == "annual"
    assert result.end_month == "2025-12" and result.period_limit == 4


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -float("inf")])
def test_value_metadata_rejects_non_numeric_numbers(value):
    from src.fundamentals.contracts import FinancialValue
    with pytest.raises(ValidationError):
        FinancialValue(status="ok", raw=value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "abc"])
def test_normalized_value_must_be_a_finite_decimal(value):
    from src.fundamentals.contracts import FinancialValue
    with pytest.raises(ValidationError):
        FinancialValue(status="ok", normalized_value=value)


def test_result_defaults_do_not_invent_coverage():
    from src.tools.schemas import FundamentalsResult
    result = FundamentalsResult(ticker="AAPL")
    assert result.status == "unavailable" and result.coverage is None
    assert result.read_id is None and result.read_gaps == [] and result.update_choices == []
