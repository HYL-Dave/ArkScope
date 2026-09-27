"""Every FD cursor page stays in scope and consumes real request admission."""

import json
import sqlite3
from unittest.mock import Mock

import pytest

from data_sources.financial_datasets_governance import FinancialDatasetsFailure
from tests.test_financial_datasets_governance import client_fixture, clock, POLICY


BASE = "https://api.financialdatasets.ai/financials/income-statements"


def page(start, stop, next_url=None, **changes):
    rows = [{"ticker": "TEST", "period": "annual", "report_period": f"{2025 - i}-12-31",
             "fiscal_period": f"{2025-i}-FY", "currency": "USD", "revenue": 1000-i, **changes}
            for i in range(start, stop)]
    data = {"income_statements": rows}
    if next_url is not None:
        data["next_page_url"] = next_url
    return Mock(status_code=200, json=lambda: data)


def test_cursor_pages_are_billed_individually_and_stored_as_one_complete_scope(client_fixture):
    client, governor, http = client_fixture
    pages = [page(0, 10, BASE + "?cursor=first"), page(10, 20, BASE + "?cursor=second"), page(20, 25)]
    http.side_effect = pages
    rows = client.get_income_statements("TEST", "annual", 25, freshness="refresh")
    assert len(rows) == 25
    assert http.call_count == 3
    assert http.call_args_list[0].kwargs["params"] == dict(ticker="TEST", period="annual", limit=25)
    assert [call.args[0] for call in http.call_args_list[1:]] == [BASE + "?cursor=first", BASE + "?cursor=second"]
    assert all(call.kwargs.get("params") is None for call in http.call_args_list[1:])
    assert all(call.kwargs["allow_redirects"] is False for call in http.call_args_list)
    assert all(response.close.call_count == 1 for response in pages)
    assert client.get_income_statements("TEST", "annual", 25, freshness="stored") == rows
    assert http.call_count == 3
    with sqlite3.connect(governor.path) as conn:
        assert conn.execute("SELECT attempts FROM fd_request_accounts").fetchone() == (3,)
    from data_sources.financial_datasets_client import _FILE_CACHE_DIR
    retained = json.loads(next(_FILE_CACHE_DIR.glob("*.json")).read_text())
    assert "next_page_url" not in retained["data"]["payload"]


def test_later_page_denial_does_not_replace_the_prior_complete_response(client_fixture):
    client, governor, http = client_fixture
    http.side_effect = [page(0, 1), page(0, 10, BASE + "?cursor=first")]
    client.get_income_statements("TEST", "annual", 25, freshness="refresh")
    client._request_policy = {**POLICY, "daily_request_limit": 2}
    with pytest.raises(FinancialDatasetsFailure, match="budget_exhausted"):
        client.get_income_statements("TEST", "annual", 25, freshness="refresh")
    assert http.call_count == 2
    assert len(client.get_income_statements("TEST", "annual", 25, freshness="stored")) == 1


@pytest.mark.parametrize("next_url", [
    "https://other.example/financials/income-statements?cursor=x",
    BASE.replace("https:", "http:") + "?cursor=x", BASE.replace("api.", "user@api.") + "?cursor=x",
    BASE.replace("income-statements", "balance-sheets") + "?cursor=x", BASE + "?ticker=OTHER",
    BASE + "?cursor=one&cursor=two", BASE + "?cursor=x#fragment", BASE + "?cursor=",
    "\n" + BASE + "?cursor=x", 123,
])
def test_untrusted_page_link_never_receives_api_key(client_fixture, next_url):
    client, _, http = client_fixture
    http.return_value = page(0, 1, next_url)
    with pytest.raises(FinancialDatasetsFailure, match="pagination_invalid"):
        client.get_income_statements("TEST", "annual", 25, freshness="refresh")
    assert http.call_count == 1


@pytest.mark.parametrize("second", [
    page(0, 1), page(1, 2, BASE + "?cursor=first"), page(1, 2, ticker="OTHER"),
    page(1, 2, period="quarterly"), page(0, 0, BASE + "?cursor=second"),
])
def test_repeated_or_wrong_scope_pages_are_not_cached_as_complete(client_fixture, second):
    client, _, http = client_fixture
    http.side_effect = [page(0, 1, BASE + "?cursor=first"), second]
    with pytest.raises(FinancialDatasetsFailure, match="(pagination|response)_invalid"):
        client.get_income_statements("TEST", "annual", 25, freshness="refresh")
    assert http.call_count == 2
    with pytest.raises(FinancialDatasetsFailure, match="cache_miss"):
        client.get_income_statements("TEST", "annual", 25, freshness="stored")


def test_requested_count_stops_pagination_without_an_arbitrary_lower_cap(client_fixture):
    client, _, http = client_fixture
    http.side_effect = [page(0, 10, BASE + "?cursor=first"), page(10, 20, BASE + "?cursor=unused")]
    assert len(client.get_income_statements("TEST", "annual", 12, freshness="refresh")) == 12
    assert http.call_count == 2
