"""Configured acquisition scope does not erase or overstate retained FD history."""

from copy import deepcopy
import json

import pytest

from tests.financial_read_fixtures import financial_local, save_fd
from tests.test_common_financial_read import read, route, paid, codes, files, FD
from tests.test_financial_read_settings import KEY, DEFAULTS


def configured(period, values):
    settings = deepcopy(DEFAULTS)
    settings["fd_periods"][period] = values
    route([FD]).set_setting(KEY, json.dumps(settings))


@pytest.mark.parametrize("period", ["annual", "quarterly"])
def test_refresh_applies_each_configured_statement_scope(financial_local, monkeypatch, period):
    dal, http, _ = financial_local
    configured(period, dict(income_statement=6, balance_sheet=3, cash_flow_statement=5))
    paid(dal, http, monkeypatch)
    # Empty is a valid provider response, not a license to ignore the requested scope.
    for_response = http.side_effect
    def response(url, **kwargs):
        value = for_response(url, **kwargs)
        data = value.json()
        for rows in data.values():
            for row in rows:
                row["period"] = period
        value.json = lambda: data
        return value
    http.side_effect = response
    result = read(dal, source=FD, freshness="refresh", period=period)
    assert [c.kwargs["params"]["limit"] for c in http.call_args_list] == [6, 3, 5]
    assert result.source_observations
    assert [o["requested_periods"] for o in result.source_observations] == [6, 3, 5]


@pytest.mark.parametrize("from_file", [False, True])
def test_changed_settings_keep_old_facts_readable_without_claiming_larger_scope(financial_local, tmp_path, from_file):
    dal, http, _ = financial_local
    saved = save_fd(dal, age_days=1, from_file=from_file)
    configured("annual", dict(income_statement=12, balance_sheet=1, cash_flow_statement=2))
    before = files(tmp_path)
    result = read(dal, source=FD, statement="income_statement", freshness="stored")
    assert result.income_statements and result.data_source == FD
    assert "financial_datasets_history_scope_shortfall" in codes(result)
    assert result.source_observations[0]["requested_periods"] == 2
    assert result.source_observations[0]["configured_periods"] == 12
    assert result.source_observations[0]["fetched_at"] == saved["fetched_at"]
    assert files(tmp_path) == before
    http.assert_not_called()


def test_lowering_scope_does_not_hide_previously_acquired_history(financial_local):
    dal, http, _ = financial_local
    def two_rows(rows):
        rows.append({**rows[0], "report_period": "2024-09-28", "fiscal_period": "2024-FY"})
    save_fd(dal, change=two_rows)
    configured("annual", dict(income_statement=1, balance_sheet=1, cash_flow_statement=1))
    result = read(dal, source=FD, statement="income_statement", freshness="stored")
    assert len(result.income_statements) == 2
    assert result.source_observations[0]["requested_periods"] == 2
    assert "financial_datasets_history_scope_shortfall" not in codes(result)
    http.assert_not_called()


def test_auto_cannot_reuse_fresh_but_smaller_requested_scope(financial_local, monkeypatch):
    dal, http, _ = financial_local
    save_fd(dal, age_days=1)
    configured("annual", dict(income_statement=6, balance_sheet=1, cash_flow_statement=2))
    paid(dal, http, monkeypatch)
    first = read(dal, source=FD, statement="income_statement", freshness="auto")
    assert http.call_count == 1
    assert http.call_args.kwargs["params"]["limit"] == 6
    assert first.source_observations[0]["requested_periods"] == 6
    # Fewer actual rows than requested can mean limited provider coverage, not a retry loop.
    second = read(dal, source=FD, statement="income_statement", freshness="auto")
    assert second.source_observations[0]["retrieval"] == "stored"
    assert http.call_count == 1


def test_invalid_period_settings_refuse_acquisition(financial_local, monkeypatch):
    dal, http, _ = financial_local
    route([FD]).set_setting(KEY, "{")
    paid(dal, http, monkeypatch)
    result = read(dal, source=FD, freshness="refresh")
    assert "financial_read_settings_invalid" in codes(result)
    http.assert_not_called()
