"""One selected observation set; local facts never grant paid acquisition authority."""

from copy import deepcopy
import json
import os
from unittest.mock import Mock

import pytest

from src.data_provider_config import DataProviderConfigStore
from src.fundamentals.contracts import FinancialQuery
from src.sa.company_store import save_capture
from tests.financial_read_fixtures import financial_local, sa_payload, save_fd
from tests.test_financial_datasets import (
    MOCK_INCOME_RESPONSE, MOCK_BALANCE_RESPONSE, MOCK_CASHFLOW_RESPONSE, TEST_POLICY,
)


KINDS = ("income_statement", "balance_sheet", "cash_flow_statement")
SA, FD = "seeking_alpha", "financial_datasets"


def route(providers):
    store = DataProviderConfigStore(os.environ["ARKSCOPE_PROFILE_DB"])
    store.set_setting("data_sources.route.fundamentals_analysis", json.dumps(providers))
    return store


def read(dal, **kwargs):
    from src.fundamentals.read_service import read_financials
    return read_financials(dal, FinancialQuery(ticker=kwargs.pop("ticker", "AAPL"), **kwargs))


def codes(result):
    return {g.code for g in result.read_gaps}


def files(root):
    # SQLite mode=ro still coordinates with live WAL writers. Do not use immutable=1 to hide them.
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and not p.name.endswith(("-shm", "-wal"))}


def seed(dal, source, count=3, age_days=1):
    for kind in KINDS[:count]:
        if source == SA:
            save_capture(sa_payload(kind.replace("_", "-")))
        else:
            save_fd(dal, kind, age_days=age_days)


def paid(dal, http, monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "offline-test")
    dal.get_user_profile = lambda: {"data_preferences": {"paid_sources": {"financial_datasets": TEST_POLICY}}}
    responses = {"income-statements": MOCK_INCOME_RESPONSE, "balance-sheets": MOCK_BALANCE_RESPONSE,
                 "cash-flow-statements": MOCK_CASHFLOW_RESPONSE}
    http.side_effect = lambda url, **_: Mock(status_code=200, json=lambda: deepcopy(responses[url.rsplit("/", 1)[-1]]))


@pytest.mark.parametrize("selection,sa_count,fd_count,age,mode,expected,status", [
    (None, 3, 0, 1, "stored", SA, "ok"),
    ([FD], 3, 0, 1, "stored", "none", "unavailable"),
    ([SA, FD], 1, 3, 1, "stored", SA, "partial"),
    ([SA, FD], 0, 3, 1, "auto", FD, "ok"),
    ([SA, FD], 0, 1, 1, "auto", FD, "partial"),
    ([SA, FD], 0, 3, 200, "auto", FD, "ok"),
    ([FD, SA], 3, 3, 1, "stored", FD, "ok"),
])
def test_local_selection_is_coherent_and_never_writes(financial_local, tmp_path, selection, sa_count,
                                                     fd_count, age, mode, expected, status):
    dal, http, sec = financial_local
    if selection is not None:
        route(selection)
    seed(dal, SA, sa_count)
    seed(dal, FD, fd_count, age)
    before = files(tmp_path)
    result = read(dal, freshness=mode)
    assert result.data_source == expected and result.status == status
    rows = [*(result.income_statements or []), *(result.balance_sheet or []), *(result.cash_flow_statements or [])]
    assert {r.provider for r in rows} == ({expected} if rows else set())
    if expected == SA and status == "partial":
        assert result.cash_flow_statements == []
    if mode == "auto" and (fd_count < 3 or age == 200):
        assert "sa_browser_update_required" in codes(result)
    assert files(tmp_path) == before
    http.assert_not_called()
    sec.assert_not_called()


def test_explicit_unselected_sa_does_not_read_or_repair_setting(financial_local, tmp_path, monkeypatch):
    dal, http, _ = financial_local
    route([FD])
    forbidden = Mock(side_effect=AssertionError("unselected source read"))
    monkeypatch.setattr("src.fundamentals.adapters.read_capture", forbidden)
    before = files(tmp_path)
    result = read(dal, source=SA)
    assert "data_source_not_selected" in codes(result) and result.status == "unavailable"
    assert files(tmp_path) == before
    forbidden.assert_not_called()
    http.assert_not_called()


@pytest.mark.parametrize("raw,code", [("[]", "data_source_route_disabled"), ("{", "data_source_policy_invalid"),
                                      ('["sec_edgar"]', "data_source_policy_invalid"),
                                      ('["unknown"]', "data_source_policy_invalid")])
def test_invalid_route_fails_closed(financial_local, tmp_path, raw, code):
    dal, http, sec = financial_local
    seed(dal, SA)
    route([]).set_setting("data_sources.route.fundamentals_analysis", raw)
    before = files(tmp_path)
    result = read(dal, freshness="auto")
    assert result.status == "unavailable" and code in codes(result)
    assert files(tmp_path) == before
    http.assert_not_called()
    sec.assert_not_called()


def test_fd_auto_reuses_income_and_acquires_only_missing_statements(financial_local, monkeypatch):
    dal, http, sec = financial_local
    route([SA, FD])
    entry = save_fd(dal, age_days=1)
    paid(dal, http, monkeypatch)
    result = read(dal, source=FD, freshness="auto")
    assert result.status == "ok" and result.data_source == FD
    assert http.call_count == 2
    assert [call.args[0].rsplit("/", 1)[-1] for call in http.call_args_list] == ["balance-sheets", "cash-flow-statements"]
    income = next(o for o in result.source_observations if o["dataset"] == "income_statement")
    assert income["retrieval"] == "stored" and income["fetched_at"] == entry["fetched_at"]
    sec.assert_not_called()


def test_fd_primary_refusal_stops_remaining_attempts(financial_local, monkeypatch):
    dal, http, sec = financial_local
    route([FD, SA])
    paid(dal, http, monkeypatch)
    http.side_effect = lambda *_a, **_k: Mock(status_code=429)
    result = read(dal, freshness="auto")
    assert result.status == "unavailable" and http.call_count == 1
    assert "financial_datasets_not_attempted_after_refusal" in codes(result)
    sec.assert_not_called()


@pytest.mark.parametrize("source,code", [("auto", "financial_refresh_source_required"), (SA, "sa_browser_update_required")])
def test_refresh_does_not_implicitly_dispatch(financial_local, tmp_path, source, code):
    dal, http, sec = financial_local
    seed(dal, SA)
    before = files(tmp_path)
    result = read(dal, source=source, freshness="refresh")
    assert result.status == "unavailable" and code in codes(result)
    assert files(tmp_path) == before and result.income_statements == []
    if source == SA:
        assert result.update_choices[0]["provider"] == SA
        assert result.update_choices[0]["action"] == "browser_capture"
        assert result.update_choices[0]["status_url"] == "/sa/acquisition-status"
    http.assert_not_called()
    sec.assert_not_called()


def test_refused_fd_refresh_cannot_return_old_cache_or_sa(financial_local, monkeypatch):
    dal, http, sec = financial_local
    route([FD, SA])
    seed(dal, FD)
    seed(dal, SA)
    paid(dal, http, monkeypatch)
    http.side_effect = lambda *_a, **_k: Mock(status_code=429)
    result = read(dal, source=FD, freshness="refresh")
    assert result.status == "unavailable" and result.income_statements == []
    assert result.data_source == "none" and not result.source_observations
    assert http.call_count == 1
    sec.assert_not_called()


@pytest.mark.parametrize("pin", [{"end_month": "2025-12"}, {"observation_id": "a" * 64}, {"read_id": "a" * 64}])
@pytest.mark.parametrize("mode", ["auto", "refresh"])
def test_historical_acquisition_rejected_before_dispatch(financial_local, mode, pin):
    dal, http, sec = financial_local
    result = read(dal, source=FD, freshness=mode, **pin)
    assert "financial_historical_requires_stored" in codes(result)
    http.assert_not_called()
    sec.assert_not_called()


def test_old_sa_observation_reopens_after_new_capture(financial_local):
    dal, _, _ = financial_local
    payload = sa_payload()
    receipt = save_capture(payload)
    payload["rows"][1]["values"][1] = "999.0"
    payload["captured_at"] = "2026-09-24T12:00:00Z"
    save_capture(payload)
    query = dict(source=SA, statement="income_statement", observation_id=receipt["observation_id"])
    result = read(dal, **query)
    assert result.income_statements[0].data["revenue"] == "123400000"
    assert result.period_selection == "retained_observation"
    for change in ({"ticker": "AMD"}, {"statement": "balance_sheet"}, {"currency": "EUR"}):
        wrong = read(dal, **{**query, **change})
        assert wrong.status == "unavailable" and wrong.income_statements == []


@pytest.mark.parametrize("kwargs", [{}, {"source": FD}, {"source": SA}])
def test_observation_pin_requires_explicit_sa_statement(financial_local, kwargs):
    result = read(financial_local[0], observation_id="a" * 64, **kwargs)
    assert "financial_observation_scope_required" in codes(result)


def test_read_id_stable_across_time_and_paging(financial_local):
    dal, _, _ = financial_local
    seed(dal, SA)
    first = read(dal, period_limit=1)
    second = read(dal, read_id=first.read_id, period_offset=1, period_limit=1)
    assert second.read_id == first.read_id and second.income_statements[0].end_month == "2024-12"
    assert second.gross_margin == first.gross_margin
    assert second.metric_basis == first.metric_basis
    assert second.coverage == first.coverage
    assert first.pagination["has_more"] and not second.pagination["has_more"]


def test_unpinned_page_two_fails_closed(financial_local):
    seed(financial_local[0], SA)
    result = read(financial_local[0], period_offset=1)
    assert "financial_read_id_required" in codes(result) and not result.income_statements


def test_replaced_fd_read_cannot_reopen_by_old_id(financial_local):
    dal, _, _ = financial_local
    route([FD])
    seed(dal, FD, age_days=200)
    first = read(dal, end_month="2025-09", max_age_seconds=60)
    assert first.income_statements[0].data["revenue"] == 416161000000
    assert first.source_observations[0]["within_max_age"] is False
    save_fd(dal, change=lambda rows: rows[0].update(revenue=42))
    changed = read(dal, end_month="2025-09", read_id=first.read_id)
    assert changed.status == "unavailable" and changed.income_statements == []
    assert changed.read_gaps[0].code == "financial_read_changed"


def test_historical_fd_growth_uses_retained_previous_period(financial_local):
    dal, _, _ = financial_local
    route([FD])
    def rows(values):
        original = values[0]
        values[:] = [{**original, "report_period": f"{y}-09-27", "fiscal_period": f"{y}-FY", "revenue": v}
                     for y, v in [(2024, 200), (2023, 100)]]
    save_fd(dal, change=rows)
    result = read(dal, end_month="2024-09", statement="income_statement")
    assert result.revenue_growth == 1.0
    assert result.income_statements[0].end_month == "2024-09"
    assert result.metric_basis["revenue_growth"]["previous_report_period"] == "2023-09-27"


def test_fd_currency_mismatch_keeps_raw_but_blocks_metrics(financial_local):
    dal, _, _ = financial_local
    route([FD])
    save_fd(dal, change=lambda rows: rows[0].update(currency="EUR"))
    result = read(dal, statement="income_statement")
    assert result.income_statements[0].currency == "EUR" and result.gross_margin is None
    assert "currency_mismatch" in codes(result)
    assert result.metric_gaps["gross_margin"] == "currency_mismatch"


def test_success_without_retention_discloses_no_reopenability(financial_local, monkeypatch):
    dal, http, _ = financial_local
    route([FD])
    paid(dal, http, monkeypatch)
    monkeypatch.setattr(dal._backend, "set_financial_cache", lambda *_a, **_k: False)
    monkeypatch.setattr("data_sources.financial_datasets_client.FinancialDatasetsClient._write_file_cache", lambda *_a, **_k: False)
    result = read(dal, source=FD, statement="income_statement", freshness="refresh")
    assert result.status == "ok" and "financial_retention_failed" in codes(result)
    assert result.source_observations[0]["persisted"] is False
    assert result.source_observations[0]["history"] == "not_retained"


def test_default_dal_missing_stores_has_no_side_effect(financial_local, tmp_path):
    _, http, sec = financial_local
    before = files(tmp_path)
    result = read(None)
    assert result.status == "unavailable" and files(tmp_path) == before
    http.assert_not_called()
    sec.assert_not_called()
