"""User-visible reuse, not merely accepting a freshness parameter."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from data_sources import financial_datasets_client as fd_module
from src.fundamentals.cache import fundamentals_analysis_cache_key
from src.tools.analysis_tools import get_detailed_financials, get_fundamentals_analysis
from src.tools.backends.local_market_backend import LocalMarketBackend
from src.tools.schemas import FundamentalsResult
from tests.test_financial_datasets import MOCK_INCOME_RESPONSE, TEST_POLICY


@pytest.fixture
def local(tmp_path, monkeypatch):
    backend = LocalMarketBackend(market_db=str(tmp_path / "market.db"))
    monkeypatch.setattr(fd_module, "_FILE_CACHE_DIR", tmp_path / "fd")
    http = Mock(side_effect=AssertionError("this test must not access a provider"))
    monkeypatch.setattr(fd_module.requests, "get", http)
    sec = Mock(side_effect=AssertionError("local reuse must not acquire SEC data"))
    monkeypatch.setattr("data_sources.sec_edgar_financials.SECEdgarFinancials", sec)
    dal = SimpleNamespace(_backend=backend, get_user_profile=lambda: {})
    return dal, http, sec


def save_fd(backend, *, age_days=2, prefix="income", dataset="income_statements", limit=2):
    fetched = datetime.now(timezone.utc) - timedelta(days=age_days)
    item = dict(MOCK_INCOME_RESPONSE["income_statements"][0])
    envelope = fd_module.FinancialDatasetsClient._envelope({dataset: [item]}, "AAPL", "annual", limit)
    assert backend.set_financial_cache(
        f"fd_v1_{prefix}_AAPL_annual_{limit}", "AAPL", envelope,
        source="financial_datasets", fetched_at=fetched.isoformat(),
        expires_at=(fetched + timedelta(days=180)).isoformat(),
    )
    return fetched


def test_fd_default_reuses_saved_response_without_paid_authority(local):
    dal, http, _ = local
    fetched = save_fd(dal._backend)
    client = fd_module.FinancialDatasetsClient(cache_backend=dal._backend)
    client.api_key = None
    assert client.get_income_statements("AAPL", period="annual", limit=2)
    observation = client.observations[-1]
    assert observation["freshness_mode"] == "auto"
    assert observation["max_age_seconds"] == 7 * 86400
    assert observation["fetched_at"] == fetched.isoformat()
    assert "latest_period_verified" not in observation
    http.assert_not_called()


def test_two_default_fd_reads_buy_once(local):
    dal, http, _ = local
    http.side_effect = None
    http.return_value = Mock(status_code=200, json=lambda: MOCK_INCOME_RESPONSE)
    client = fd_module.FinancialDatasetsClient(
        api_key="offline-test", cache_backend=dal._backend, request_policy=TEST_POLICY,
    )
    first = client.get_income_statements("AAPL", period="annual", limit=2)
    second = client.get_income_statements("AAPL", period="annual", limit=2)
    assert first == second
    assert http.call_count == 1
    assert [o["retrieval"] for o in client.observations] == ["refreshed", "stored"]


def test_default_tool_reuses_fd_before_trying_sec_or_checking_paid_access(local):
    dal, http, sec = local
    for prefix, dataset, limit in (("income", "income_statements", 2),
                                   ("balance", "balance_sheets", 1),
                                   ("cashflow", "cash_flow_statements", 2)):
        save_fd(dal._backend, prefix=prefix, dataset=dataset, limit=limit)
    result = get_fundamentals_analysis(dal, "AAPL")
    assert result.data_source == "financial_datasets"
    assert len(result.source_observations) == 3
    assert not result.acquisition_gaps
    http.assert_not_called()
    sec.assert_not_called()


def test_retired_sec_snapshot_never_reenters_default_financial_reader(local):
    dal, http, sec = local
    fetched = datetime.now(timezone.utc) - timedelta(days=2)
    assert dal._backend.set_financial_cache(
        fundamentals_analysis_cache_key("AAPL", "annual"), "AAPL",
        FundamentalsResult(ticker="AAPL", data_source="sec_edgar", snapshot_date="2025-12-31").model_dump(),
        source="sec_edgar", fetched_at=fetched.isoformat(),
        expires_at=(fetched + timedelta(days=90)).isoformat(),
    )
    result = get_fundamentals_analysis(dal, "AAPL")
    assert result.status == "unavailable" and result.source_observations == []
    assert result.data_source == "none"
    http.assert_not_called()
    sec.assert_not_called()


def test_stored_financials_miss_has_no_network_or_cache_write(local, tmp_path):
    dal, http, sec = local
    before = list(tmp_path.rglob("*"))
    result = get_fundamentals_analysis(dal, "AAPL", freshness="stored")
    assert result.acquisition_gaps
    assert list(tmp_path.rglob("*")) == before
    http.assert_not_called()
    sec.assert_not_called()


def test_detailed_stored_miss_never_queries_finnhub_or_sec(local, monkeypatch):
    from src.tools.schemas import ValuationPriceBasis

    dal, http, sec = local
    calc = Mock(side_effect=AssertionError("stored must not build financials"))
    finnhub = Mock(side_effect=AssertionError("stored must not query earnings"))
    monkeypatch.setattr("data_sources.financial_metrics_calculator.FinancialMetricsCalculator", calc)
    monkeypatch.setattr("src.tools.analyst_tools._finnhub_get", finnhub)
    monkeypatch.setattr("src.valuation_price.get_valuation_price_basis", lambda _: ValuationPriceBasis())
    result = get_detailed_financials(dal, "AAPL", freshness="stored")
    assert result.acquisition_gaps
    calc.assert_not_called()
    finnhub.assert_not_called()
    http.assert_not_called()
    sec.assert_not_called()


@pytest.mark.parametrize("refresh_days,override,expected_source", [(1, None, "financial_datasets"), (30, None, "financial_datasets"), (1, 3 * 86400, "financial_datasets")])
def test_auto_uses_operator_policy_then_explicit_override(local, refresh_days, override, expected_source):
    dal, http, _ = local
    for prefix, dataset, limit in (("income", "income_statements", 2),
                                   ("balance", "balance_sheets", 1),
                                   ("cashflow", "cash_flow_statements", 2)):
        save_fd(dal._backend, prefix=prefix, dataset=dataset, limit=limit)
    dal.get_user_profile = lambda: {"data_preferences": {"fundamentals_sources": {"refresh_days": refresh_days}}}
    result = get_fundamentals_analysis(dal, "AAPL", max_age_seconds=override)
    assert result.data_source == expected_source
    if expected_source == "financial_datasets":
        assert all(item["max_age_seconds"] == (override or refresh_days * 86400) for item in result.source_observations)
        if refresh_days == 1 and override is None:
            assert all(item["within_max_age"] is False for item in result.source_observations)
            assert any(g["code"] == "sa_browser_update_required" for g in result.acquisition_gaps)
    else:
        assert result.acquisition_gaps
    http.assert_not_called()


@pytest.mark.parametrize("value", [True, "7", -1, None])
def test_bad_config_does_not_silently_enable_acquisition(local, value):
    dal, http, sec = local
    dal.get_user_profile = lambda: {"data_preferences": {"fundamentals_sources": {"refresh_days": value}}}
    result = get_fundamentals_analysis(dal, "AAPL")
    assert result.acquisition_gaps == [{"provider": "financials", "code": "financial_reuse_policy_invalid"}]
    http.assert_not_called()
    sec.assert_not_called()


@pytest.mark.parametrize("freshness", ["stored", "auto", "refresh"])
def test_unported_detailed_analysis_does_not_query_earnings(local, monkeypatch, freshness):
    dal, http, sec = local
    finnhub = Mock(side_effect=AssertionError("unported detailed operation must not query Finnhub"))
    monkeypatch.setattr("src.tools.analyst_tools._finnhub_get", finnhub)
    result = get_detailed_financials(dal, "AAPL", freshness=freshness)
    assert result.status == "unavailable" and result.error_code == "financial_operation_not_ported"
    assert result.gross_margin is None and result.source_observations == []
    finnhub.assert_not_called()
    http.assert_not_called()
    sec.assert_not_called()


def test_refresh_failure_never_falls_back_to_a_stored_sec_result(local):
    dal, http, sec = local
    assert dal._backend.set_financial_cache(fundamentals_analysis_cache_key("AAPL", "annual"), "AAPL",
        FundamentalsResult(ticker="AAPL", data_source="sec_edgar", snapshot_date="2025-12-31", roe=0.4).model_dump())
    result = get_fundamentals_analysis(dal, "AAPL", freshness="refresh")
    assert result.roe is None
    assert not result.source_observations
    assert any(item["code"] == "financial_refresh_source_required" for item in result.acquisition_gaps)
    sec.assert_not_called()
    http.assert_not_called()


@pytest.mark.parametrize("report_date", [None, "", "not-a-period"])
def test_legacy_empty_detailed_cache_is_not_a_successful_observation(local, monkeypatch, report_date):
    from src.fundamentals.cache import detailed_financials_cache_key
    from src.tools.schemas import ValuationPriceBasis
    from tests.test_detailed_financials import _static_cache_payload

    dal, http, sec = local
    data = _static_cache_payload("AAPL")
    data.update(report_date=report_date, static_metrics={}, tech_metrics={}, valuation_inputs={})
    assert dal._backend.set_financial_cache(detailed_financials_cache_key("AAPL"), "AAPL", data)
    monkeypatch.setattr("src.valuation_price.get_valuation_price_basis", lambda _: ValuationPriceBasis())
    result = get_detailed_financials(dal, "AAPL", freshness="stored")
    assert not result.source_observations
    assert {"provider": "financials", "code": "financial_operation_not_ported"} in result.acquisition_gaps
    http.assert_not_called()
    sec.assert_not_called()
