"""The Settings policy is strict, provider-free and used by real tool calls."""

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.dependencies import get_dal, get_data_provider_store
from src.api.routes.providers_config import router
from src.data_provider_config import DataProviderConfigStore
from src.data_source_routing import FD_POLICY_KEY, ROUTE_PREFIX, DataSourcePolicyFailure, load_route, read_setting
from src.tools.analysis_tools import get_fundamentals_analysis
from tests.test_data_source_routing import save_statements
from tests.test_financial_local_reuse import local


@pytest.fixture
def settings_client(local):
    dal, _, _ = local
    store = DataProviderConfigStore(os.environ["ARKSCOPE_PROFILE_DB"])
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_data_provider_store] = lambda: store
    app.dependency_overrides[get_dal] = lambda: dal
    with TestClient(app) as client:
        yield client, store


def test_get_is_provider_free_and_does_not_persist_defaults(settings_client, local):
    client, store = settings_client
    _, http, sec = local
    path = Path(os.environ["ARKSCOPE_PROFILE_DB"])
    before = sha256(path.read_bytes()).hexdigest()
    response = client.get("/providers/data-routes")
    assert response.status_code == 200
    result = response.json()
    assert {row["dataset"] for row in result["routes"]} == {
        "fundamentals_analysis", "detailed_financials", "earnings_supplements", "sa_company_financials",
        "sa_company_valuation", "sa_company_estimates",
    }
    assert all(row["setting_source"] == "default" for row in result["routes"])
    assert result["financial_datasets_budget"]["state"] == "unconfigured"
    assert sha256(path.read_bytes()).hexdigest() == before
    assert store.get_setting(ROUTE_PREFIX + "fundamentals_analysis") is None
    http.assert_not_called()
    sec.assert_not_called()


def test_settings_save_changes_real_dispatch_without_dal_restart(settings_client, local):
    client, _ = settings_client
    dal, http, sec = local
    save_statements(dal._backend)
    response = client.put("/providers/data-routes/fundamentals_analysis", json={"providers": ["financial_datasets"]})
    assert response.status_code == 200
    assert response.json()["providers"] == ["financial_datasets"]
    assert get_fundamentals_analysis(dal, "AAPL").data_source == "financial_datasets"
    response = client.put("/providers/data-routes/fundamentals_analysis", json={"providers": []})
    assert response.status_code == 200
    assert get_fundamentals_analysis(dal, "AAPL").data_source == "none"
    http.assert_not_called()
    sec.assert_not_called()


@pytest.mark.parametrize("body", [
    {"providers": ["massive"]}, {"providers": ["seeking_alpha"]},
    {"providers": ["sec_edgar", "sec_edgar"]}, {"providers": [True]},
    {"providers": "sec_edgar"}, {"providers": None},
    {"providers": [], "override_permissions": True},
])
def test_invalid_selection_is_rejected_atomically(settings_client, body):
    client, store = settings_client
    key = ROUTE_PREFIX + "fundamentals_analysis"
    store.set_setting(key, '["financial_datasets"]')
    response = client.put("/providers/data-routes/fundamentals_analysis", json=body)
    assert response.status_code == 422
    assert store.get_setting(key) == '["financial_datasets"]'


def test_unknown_dataset_and_unimplemented_detailed_fd_are_not_admitted(settings_client):
    client, _ = settings_client
    assert client.put("/providers/data-routes/news", json={"providers": []}).status_code == 404
    assert client.put("/providers/data-routes/detailed_financials",
                      json={"providers": ["financial_datasets"]}).status_code == 422


def test_invalid_saved_selection_is_visible_and_can_be_replaced(settings_client):
    client, store = settings_client
    store.set_setting(ROUTE_PREFIX + "fundamentals_analysis", '"sec_edgar"')
    row = client.get("/providers/data-routes").json()["routes"][0]
    assert row["providers"] is None
    assert row["error_code"] == "data_source_policy_invalid"
    response = client.put("/providers/data-routes/fundamentals_analysis", json={"providers": []})
    assert response.json()["error_code"] is None


def test_paid_enablement_requires_confirmation_and_positive_limits(settings_client):
    client, store = settings_client
    body = {"enabled": True, "daily_request_limit": 3, "requests_per_minute": 1}
    response = client.put("/providers/request-budgets/financial_datasets", json=body)
    assert response.status_code == 409
    assert store.get_setting(FD_POLICY_KEY) is None
    response = client.put("/providers/request-budgets/financial_datasets", json={**body, "confirm_paid": True})
    assert response.status_code == 200
    assert response.json()["state"] == "enabled"
    assert json.loads(store.get_setting(FD_POLICY_KEY)) == body


@pytest.mark.parametrize("limit", [None, 0, -1, True, "03", "3.0", "1e2", " 3", 1.5, 2**63, str(2**63)])
def test_invalid_paid_budget_never_overwrites_a_disabled_policy(settings_client, limit):
    client, store = settings_client
    raw = '{"enabled":false,"daily_request_limit":null,"requests_per_minute":null}'
    store.set_setting(FD_POLICY_KEY, raw)
    response = client.put("/providers/request-budgets/financial_datasets", json={
        "enabled": True, "daily_request_limit": limit, "requests_per_minute": 1, "confirm_paid": True,
    })
    assert response.status_code == 422
    assert store.get_setting(FD_POLICY_KEY) == raw


def test_browser_round_trip_preserves_int64_request_limits(settings_client):
    client, store = settings_client
    maximum = 2**63 - 1
    response = client.put("/providers/request-budgets/financial_datasets", json={
        "enabled": True, "daily_request_limit": str(maximum), "requests_per_minute": "3",
        "confirm_paid": True,
    })
    assert response.status_code == 200
    assert response.json()["daily_request_limit"] == str(maximum)
    assert response.json()["requests_per_minute"] == "3"
    assert json.loads(store.get_setting(FD_POLICY_KEY))["daily_request_limit"] == maximum
    assert client.get("/providers/data-routes").json()["financial_datasets_budget"] == response.json()


def test_disabling_paid_requests_overrides_yaml_but_keeps_local_reads(settings_client, local, monkeypatch):
    from tests.test_financial_datasets import TEST_POLICY

    client, _ = settings_client
    dal, http, sec = local
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "offline-test")
    dal.get_user_profile = lambda: {"data_preferences": {"paid_sources": {"financial_datasets": TEST_POLICY}}}
    client.put("/providers/data-routes/fundamentals_analysis", json={"providers": ["financial_datasets"]})
    response = client.put("/providers/request-budgets/financial_datasets", json={
        "enabled": False, "daily_request_limit": None, "requests_per_minute": None,
    })
    assert response.status_code == 200
    result = get_fundamentals_analysis(dal, "AAPL", freshness="refresh")
    assert result.acquisition_gaps[0]["code"] == "financial_datasets_paid_requests_disabled"
    save_statements(dal._backend)
    assert get_fundamentals_analysis(dal, "AAPL").data_source == "financial_datasets"
    http.assert_not_called()
    sec.assert_not_called()


@pytest.mark.parametrize("raw", ["{", "null", "true", '{"enabled":true}',
                                 '{"enabled":true,"daily_request_limit":0,"requests_per_minute":1}'])
def test_invalid_saved_budget_never_falls_back_to_enabled_yaml(settings_client, local, monkeypatch, raw):
    from tests.test_financial_datasets import TEST_POLICY

    client, store = settings_client
    dal, http, sec = local
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "offline-test")
    dal.get_user_profile = lambda: {"data_preferences": {"paid_sources": {"financial_datasets": TEST_POLICY}}}
    client.put("/providers/data-routes/fundamentals_analysis", json={"providers": ["financial_datasets"]})
    store.set_setting(FD_POLICY_KEY, raw)
    assert client.get("/providers/data-routes").json()["financial_datasets_budget"]["state"] == "invalid"
    result = get_fundamentals_analysis(dal, "AAPL", freshness="refresh")
    assert result.acquisition_gaps[0]["code"] == "financial_datasets_policy_invalid"
    save_statements(dal._backend)
    assert get_fundamentals_analysis(dal, "AAPL").data_source == "financial_datasets"
    http.assert_not_called()
    sec.assert_not_called()


def test_saved_budget_governs_the_actual_metered_request(settings_client, local, monkeypatch):
    from tests.test_financial_datasets import MOCK_INCOME_RESPONSE

    client, _ = settings_client
    dal, http, sec = local
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "offline-test")
    client.put("/providers/data-routes/fundamentals_analysis", json={"providers": ["financial_datasets"]})
    response = client.put("/providers/request-budgets/financial_datasets", json={
        "enabled": True, "daily_request_limit": 1, "requests_per_minute": 1, "confirm_paid": True,
    })
    assert response.status_code == 200
    http.side_effect = None
    http.return_value = Mock(status_code=200, json=lambda: MOCK_INCOME_RESPONSE)
    result = get_fundamentals_analysis(dal, "AAPL", freshness="refresh")
    assert result.data_source == "financial_datasets"
    assert http.call_count == 1
    assert result.acquisition_gaps[0]["code"] == "financial_datasets_budget_exhausted"
    get_fundamentals_analysis(dal, "AAPL", freshness="refresh")
    assert http.call_count == 1
    sec.assert_not_called()


def test_missing_profile_read_does_not_create_files():
    path = Path(os.environ["ARKSCOPE_PROFILE_DB"])
    assert not path.exists()
    assert load_route("fundamentals_analysis").providers == ("sec_edgar", "financial_datasets")
    assert not path.exists()


@pytest.mark.parametrize("contents", [b"not a SQLite database", None])
def test_invalid_profile_cannot_silently_enable_default_sources(contents):
    path = Path(os.environ["ARKSCOPE_PROFILE_DB"])
    if contents is None:
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE unrelated (id)")
    else:
        path.write_bytes(contents)
    with pytest.raises(DataSourcePolicyFailure, match="data_source_settings_unavailable"):
        read_setting(ROUTE_PREFIX + "fundamentals_analysis")
