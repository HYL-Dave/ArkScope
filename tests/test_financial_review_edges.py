"""Financial review regressions; all application state is disposable."""

from dataclasses import fields

import pytest

from data_sources.financial_statements import BalanceSheet, CashFlowStatement, IncomeStatement
from src.fundamentals import adapters

from src.sa.company_store import save_capture
from tests.financial_read_fixtures import financial_local, sa_payload, save_fd
from tests.test_common_financial_api import client
from tests.test_common_financial_read import FD, SA, read, route


@pytest.mark.parametrize("kind,field,unit", [
    ("income_statement", "weighted_average_shares", "shares"),
    ("income_statement", "weighted_average_shares_diluted", "shares"),
    ("balance_sheet", "outstanding_shares", "shares"),
    ("income_statement", "dividends_per_common_share", "USD/share"),
])
def test_fd_native_units(financial_local, kind, field, unit):
    dal, http, sec = financial_local
    save_fd(dal, kind, change=lambda rows: rows[0].update({field: 12.5}))
    result = read(dal, source=FD, statement=kind)
    rows = result.balance_sheet if kind == "balance_sheet" else result.income_statements
    assert rows[0].data[field] == 12.5
    http.assert_not_called()
    sec.assert_not_called()
    assert rows[0].value_metadata[field].unit == unit


def test_fd_unit_contract_covers_all_retained_statement_fields():
    expected = {item.name for cls in (IncomeStatement, BalanceSheet, CashFlowStatement)
                for item in fields(cls)} - adapters._IDENTITY_FIELDS
    assert set(adapters.FD_FIELD_UNITS) == expected


def test_unpinned_missing_month_remains_a_typed_local_gap(financial_local):
    dal, http, sec = financial_local
    route([SA, FD])
    save_capture(sa_payload())
    save_fd(dal)
    result = read(dal, end_month="2020-01")
    assert result.status == "unavailable"
    assert "financial_period_unavailable" in {gap.code for gap in result.read_gaps}
    http.assert_not_called()
    sec.assert_not_called()


def test_historical_auto_selects_source_with_requested_month(financial_local):
    dal, http, sec = financial_local
    route([SA, FD])
    save_capture(sa_payload())  # SA has December 2025 / December 2024.
    save_fd(dal)  # FD has September 2025.
    explicit = read(dal, source=FD, statement="income_statement", end_month="2025-09")
    assert explicit.status == "ok"
    automatic = read(dal, statement="income_statement", end_month="2025-09")
    http.assert_not_called()
    sec.assert_not_called()
    assert automatic.data_source == FD, automatic.model_dump()
    assert automatic.income_statements == explicit.income_statements


@pytest.mark.parametrize("replacement", ["empty", "other_month"])
def test_pinned_version_loss_is_conflict(client, financial_local, replacement):
    dal, http, sec = financial_local
    route([FD])
    save_fd(dal)
    query = dict(source=FD, statement="income_statement", end_month="2025-09", period_limit=1)
    first = client.get("/fundamentals/AAPL", params=query)
    assert first.status_code == 200 and first.json()["read_id"]

    def overwrite(rows):
        if replacement == "empty":
            rows.clear()
        else:
            rows[0].update(report_period="2026-09-26", fiscal_period="2026-FY")

    save_fd(dal, change=overwrite)
    response = client.get("/fundamentals/AAPL", params={**query, "read_id": first.json()["read_id"]})
    http.assert_not_called()
    sec.assert_not_called()
    assert response.status_code == 409, response.json()
    assert response.json()["detail"]["code"] == "financial_read_changed"
