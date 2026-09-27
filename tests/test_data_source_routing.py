"""Settings source choices must change dispatch, not only presentation."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from unittest.mock import Mock

import pytest

from src.data_provider_config import DataProviderConfigStore
from src.fundamentals.cache import fundamentals_analysis_cache_key
from src.tools.analysis_tools import get_detailed_financials, get_fundamentals_analysis
from src.tools.schemas import FundamentalsResult
from tests.test_financial_local_reuse import local, save_fd


def select(dataset, providers):
    store = DataProviderConfigStore(os.environ["ARKSCOPE_PROFILE_DB"])
    store.set_setting("data_sources.route." + dataset, json.dumps(providers))
    return store


def save_statements(backend):
    for prefix, dataset, limit in (("income", "income_statements", 2),
                                   ("balance", "balance_sheets", 1),
                                   ("cashflow", "cash_flow_statements", 2)):
        save_fd(backend, prefix=prefix, dataset=dataset, limit=limit)


def save_sec(backend):
    fetched = datetime.now(timezone.utc) - timedelta(days=1)
    assert backend.set_financial_cache(
        fundamentals_analysis_cache_key("AAPL", "annual"), "AAPL",
        FundamentalsResult(ticker="AAPL", data_source="sec_edgar", snapshot_date="2025-12-31").model_dump(),
        source="sec_edgar", fetched_at=fetched.isoformat(),
        expires_at=(fetched + timedelta(days=90)).isoformat(),
    )


def test_selected_fd_excludes_even_fresh_sec_cache(local):
    dal, http, sec = local
    save_sec(dal._backend)
    save_statements(dal._backend)
    select("fundamentals_analysis", ["financial_datasets"])
    result = get_fundamentals_analysis(dal, "AAPL")
    assert result.data_source == "financial_datasets"
    assert result.source_routes[0]["selected_source"] == "financial_datasets"
    assert result.source_routes[0]["configured_sources"] == ["financial_datasets"]
    http.assert_not_called()
    sec.assert_not_called()


@pytest.mark.parametrize("providers", [["seeking_alpha", "financial_datasets"], ["financial_datasets", "seeking_alpha"]])
def test_selected_order_breaks_ties_between_complete_local_observations(local, providers):
    from src.sa.company_store import save_capture
    from tests.financial_read_fixtures import sa_payload
    dal, http, sec = local
    for kind in ("income-statement", "balance-sheet", "cash-flow-statement"):
        save_capture(sa_payload(kind))
    save_statements(dal._backend)
    select("fundamentals_analysis", providers)
    result = get_fundamentals_analysis(dal, "AAPL", freshness="stored")
    assert result.data_source == providers[0]
    assert result.source_routes[0]["configured_sources"] == providers
    http.assert_not_called()
    sec.assert_not_called()


def test_refresh_auto_source_never_spends_or_falls_back(local):
    dal, http, sec = local
    select("fundamentals_analysis", ["financial_datasets", "seeking_alpha"])
    result = get_fundamentals_analysis(dal, "AAPL", freshness="refresh")
    assert result.data_source == "none"
    assert result.acquisition_gaps == [{"provider": "financials", "code": "financial_refresh_source_required"}]
    sec.assert_not_called()
    http.assert_not_called()


def test_retired_sec_cache_cannot_supplement_partial_fd_result(local):
    dal, http, sec = local
    select("fundamentals_analysis", ["financial_datasets", "seeking_alpha"])
    save_fd(dal._backend)
    save_sec(dal._backend)
    result = get_fundamentals_analysis(dal, "AAPL", freshness="stored")
    assert result.data_source == "financial_datasets" and result.status == "partial"
    assert result.balance_sheet == [] and result.cash_flow_statements == []
    http.assert_not_called()
    sec.assert_not_called()


def test_partial_selected_fd_reuses_income_and_buys_only_missing_statements(local, monkeypatch):
    from tests.test_financial_datasets import MOCK_BALANCE_RESPONSE, MOCK_CASHFLOW_RESPONSE, TEST_POLICY

    dal, http, sec = local
    select("fundamentals_analysis", ["seeking_alpha", "financial_datasets"])
    fetched = save_fd(dal._backend)
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "offline-test")
    dal.get_user_profile = lambda: {"data_preferences": {"paid_sources": {"financial_datasets": TEST_POLICY}}}

    def response(url, **_kwargs):
        assert url.endswith(("/balance-sheets", "/cash-flow-statements"))
        return Mock(status_code=200, json=lambda:
                    MOCK_BALANCE_RESPONSE if url.endswith("/balance-sheets") else MOCK_CASHFLOW_RESPONSE)

    http.side_effect = response
    result = get_fundamentals_analysis(dal, "AAPL", source="financial_datasets")
    assert result.data_source == "financial_datasets"
    assert len(result.source_observations) == 3
    assert result.source_observations[0]["retrieval"] == "stored"
    assert result.source_observations[0]["fetched_at"] == fetched.isoformat()
    assert not result.acquisition_gaps
    assert http.call_count == 2
    sec.assert_not_called()


def test_retired_sec_selection_does_not_fall_back_or_self_repair(local):
    dal, http, sec = local
    save_statements(dal._backend)
    select("fundamentals_analysis", ["sec_edgar"])
    result = get_fundamentals_analysis(dal, "AAPL")
    assert result.data_source == "none"
    assert not result.source_observations
    assert result.acquisition_gaps == [{"provider": "financials", "code": "data_source_policy_invalid"}]
    sec.assert_not_called()
    http.assert_not_called()


def test_empty_selection_is_disabled_not_default_fallback(local):
    dal, http, sec = local
    save_sec(dal._backend)
    select("fundamentals_analysis", [])
    result = get_fundamentals_analysis(dal, "AAPL")
    assert result.data_source == "none"
    assert result.acquisition_gaps[0]["code"] == "data_source_route_disabled"
    sec.assert_not_called()
    http.assert_not_called()


@pytest.mark.parametrize("raw", ["{", "null", "true", '"sec_edgar"', '["massive"]',
                                  '["sec_edgar", "sec_edgar"]', '[false]'])
def test_malformed_saved_route_cannot_silently_enable_default_sources(local, raw):
    dal, http, sec = local
    store = select("fundamentals_analysis", [])
    store.set_setting("data_sources.route.fundamentals_analysis", raw)
    result = get_fundamentals_analysis(dal, "AAPL")
    assert result.acquisition_gaps[0]["code"] == "data_source_policy_invalid"
    assert result.data_source == "none"
    sec.assert_not_called()
    http.assert_not_called()


def test_route_changes_are_observed_without_rebuilding_dal(local):
    dal, http, sec = local
    save_sec(dal._backend)
    save_statements(dal._backend)
    select("fundamentals_analysis", ["seeking_alpha"])
    assert get_fundamentals_analysis(dal, "AAPL").data_source == "none"
    select("fundamentals_analysis", ["financial_datasets"])
    assert get_fundamentals_analysis(dal, "AAPL").data_source == "financial_datasets"
    sec.assert_not_called()
    http.assert_not_called()


@pytest.mark.parametrize("source,code", [
    ("financial_datasets", "data_source_not_selected"),
    ("massive", "data_source_unsupported"),
    (True, "data_source_unsupported"),
])
def test_explicit_source_is_not_an_authorization_override(local, source, code):
    dal, http, sec = local
    select("fundamentals_analysis", ["seeking_alpha"])
    result = get_fundamentals_analysis(dal, "AAPL", source=source)
    assert result.acquisition_gaps[0]["code"] == code
    sec.assert_not_called()
    http.assert_not_called()


def test_explicit_fd_failure_does_not_switch_to_sec(local):
    dal, http, sec = local
    select("fundamentals_analysis", ["financial_datasets", "seeking_alpha"])
    save_sec(dal._backend)
    result = get_fundamentals_analysis(dal, "AAPL", source="financial_datasets", freshness="refresh")
    assert result.data_source == "none"
    assert {gap["provider"] for gap in result.acquisition_gaps} == {"financial_datasets"}
    sec.assert_not_called()
    http.assert_not_called()


def test_earnings_supplements_can_be_disabled_independently(local, monkeypatch):
    from tests.test_detailed_financials import _StaticCalculatorDouble, _price_basis

    dal, http, _ = local
    select("earnings_supplements", [])
    monkeypatch.setattr("data_sources.financial_metrics_calculator.FinancialMetricsCalculator", _StaticCalculatorDouble)
    monkeypatch.setattr("src.valuation_price.get_valuation_price_basis", lambda _: _price_basis())
    finnhub = Mock(side_effect=AssertionError("disabled earnings must not call Finnhub"))
    monkeypatch.setattr("src.tools.analyst_tools._finnhub_get", finnhub)
    result = get_detailed_financials(dal, "AAPL")
    assert result.gross_margin is None
    assert result.earnings_surprises is None
    assert result.acquisition_gaps[-1]["code"] == "financial_operation_not_ported"
    finnhub.assert_not_called()
    http.assert_not_called()


def test_disabled_detailed_sec_does_not_construct_calculator(local, monkeypatch):
    from tests.test_detailed_financials import _price_basis

    dal, http, sec = local
    select("detailed_financials", [])
    select("earnings_supplements", [])
    calculator = Mock(side_effect=AssertionError("disabled SEC path must not construct calculator"))
    monkeypatch.setattr("data_sources.financial_metrics_calculator.FinancialMetricsCalculator", calculator)
    monkeypatch.setattr("src.valuation_price.get_valuation_price_basis", lambda _: _price_basis())
    result = get_detailed_financials(dal, "AAPL")
    assert result.data_source == "none"
    assert result.gross_margin is None
    calculator.assert_not_called()
    sec.assert_not_called()
    http.assert_not_called()


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_explicit_source_survives_all_four_channels(local, channel):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    dal, http, sec = local
    save_sec(dal._backend)
    save_statements(dal._backend)
    select("fundamentals_analysis", ["seeking_alpha", "financial_datasets"])
    result = unwrap(asyncio.run(invoke(channel, "get_fundamentals_analysis", {
        "ticker": "AAPL", "source": "financial_datasets", "freshness": "stored",
    }, dal)))
    if result.get("error_code") == "financial_read_page_too_large":
        expected = get_fundamentals_analysis(dal, "AAPL", source="financial_datasets", freshness="stored")
        assert result["status"] == "unavailable" and result["read_id"] == expected.read_id
        assert result["required_action"] == "repeat_same_read_with_smaller_page"
        sec.assert_not_called()
        http.assert_not_called()
        return
    assert result["data_source"] == "financial_datasets"
    assert result["source_routes"][0]["requested"] == "financial_datasets"
    assert result["source_routes"][0]["selected_source"] == "financial_datasets"
    assert {item["provider"] for item in result["source_observations"]} == {"financial_datasets"}
    sec.assert_not_called()
    http.assert_not_called()
