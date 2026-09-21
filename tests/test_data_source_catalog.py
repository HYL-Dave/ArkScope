"""The data catalog describes integration, never account access or activation."""

import json
import os
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.dependencies import get_dal, get_data_provider_store
from src.api.routes.providers_config import router
from src.data_provider_config import PROVIDER_FIELDS
from src.data_source_routing import DATASETS, SOURCE_ACCESS


@pytest.fixture
def catalog_client(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(router)
    forbidden = Mock(side_effect=AssertionError("catalog must not initialize services"))
    app.dependency_overrides[get_dal] = forbidden
    app.dependency_overrides[get_data_provider_store] = forbidden
    monkeypatch.setattr("src.api.routes.providers_config.run_connection_test", forbidden)
    monkeypatch.setattr("sqlite3.connect", forbidden)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)
    for name in ("PROFILE", "MARKET", "SA", "MACRO_CALENDAR", "CONSENSUS"):
        monkeypatch.setenv(f"ARKSCOPE_{name}_DB", str(tmp_path / f"{name}.db"))
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "not-for-catalog-disclosure")
    with TestClient(app) as client:
        yield client, forbidden, tmp_path


def catalog(client):
    response = client.get("/providers/data-catalog")
    assert response.status_code == 200
    return response.json()


def by_category(client):
    return {row["id"]: row["sources"] for row in catalog(client)["categories"]}


def test_catalog_inspection_never_opens_stores_or_providers(catalog_client):
    client, forbidden, root = catalog_client
    before_env = dict(os.environ)
    result = catalog(client)
    assert result["scope"] == "current_integrations_and_candidates"
    assert len(result["categories"]) == 12
    assert "earnings_estimates" in {row["id"] for row in result["categories"]}
    assert not list(root.iterdir())
    assert dict(os.environ) == before_env
    forbidden.assert_not_called()
    assert "not-for-catalog-disclosure" not in json.dumps(result)


def test_financial_sources_follow_the_existing_routing_authority(catalog_client):
    rows = by_category(catalog_client[0])["financial_statements"]
    definition = DATASETS["fundamentals_analysis"]
    assert [row["provider"] for row in rows if row["integration"] == "implemented"] == [*definition.providers, "seeking_alpha"]
    assert [row["provider"] for row in rows if row["integration"] == "candidate"] == ["massive"]
    for row in rows:
        if row["integration"] == "implemented":
            assert row["access_requirement"] == SOURCE_ACCESS[row["provider"]]
            assert row["controls"] == (["financial_sources", "sa_extension"] if row["provider"] == "seeking_alpha" else ["financial_sources"])
            assert row["financial_routes"] == (["sa_company_financials"] if row["provider"] == "seeking_alpha" else [
                name for name, route in DATASETS.items() if row["provider"] in route.providers
            ])


@pytest.mark.parametrize("category", ["financial_statements"])
def test_unimplemented_sources_have_no_acquisition_controls(catalog_client, category):
    rows = by_category(catalog_client[0])[category]
    candidates = [row for row in rows if row["integration"] == "candidate"]
    assert candidates
    for row in candidates:
        assert row["controls"] == []
        assert row["schedule_sources"] == []
        assert row["financial_routes"] == []
        assert row["acquisition"] == "not_implemented"


@pytest.mark.parametrize("category", ["news", "recommendations", "research_content"])
def test_sa_existing_capture_is_not_confused_with_financial_pages(catalog_client, category):
    rows = by_category(catalog_client[0])
    sa = next(row for row in rows[category] if row["provider"] == "seeking_alpha")
    assert sa["integration"] == "implemented"
    assert sa["acquisition"] == "browser_extension"
    assert sa["access_requirement"] == "signed_in_browser_subscription"
    assert sa["controls"] == ["sa_extension"]
    assert sa["schedule_sources"] == []
    financial = next(row for row in rows["financial_statements"] if row["provider"] == "seeking_alpha")
    assert financial["acquisition"] == "browser_page_capture"
    assert financial["financial_routes"] == ["sa_company_financials"]
    assert financial["schedule_sources"] == []
    assert rows["valuation_ratings"][0]["integration"] == "implemented"


def test_every_app_schedule_is_accounted_for_without_inventing_sa_jobs(catalog_client):
    from src.service.data_scheduler import SOURCES

    rows = by_category(catalog_client[0])
    referenced = {source for entries in rows.values() for row in entries for source in row["schedule_sources"]}
    assert referenced == set(SOURCES)
    for entries in rows.values():
        for row in entries:
            for source in row["schedule_sources"]:
                expected_control = "macro_schedules" if SOURCES[source].writes_macro_db else "source_schedules"
                assert expected_control in row["controls"]


def test_catalog_is_a_description_not_an_account_probe(catalog_client):
    rows = by_category(catalog_client[0])
    assert len(rows) == 12
    for entries in rows.values():
        assert len({row["provider"] for row in entries}) == len(entries)
        for row in entries:
            assert row["provider"] in PROVIDER_FIELDS
            assert "enabled" not in row
            assert "available" not in row
            assert "entitled" not in row
            assert "fetched_at" not in row
    assert rows["company_events"][0]["access_requirement"] == "endpoint_entitlement_unverified"
    assert rows["current_quotes"][0]["acquisition"] == "gateway_snapshot"
    assert rows["holdings"][0]["acquisition"] == "account_capture"


@pytest.mark.parametrize("category,route", [("valuation_ratings", "sa_company_valuation"),
                                           ("earnings_estimates", "sa_company_estimates")])
def test_research_inputs_have_separate_selection_without_invented_schedules(catalog_client, category, route):
    row, = by_category(catalog_client[0])[category]
    assert row["integration"] == "implemented" and row["acquisition"] == "browser_page_capture"
    assert row["financial_routes"] == [route]
    assert row["schedule_sources"] == []
    assert row["controls"] == ["financial_sources", "sa_extension"]


def test_massive_price_worker_does_not_claim_an_independent_schedule(catalog_client):
    row = next(row for row in by_category(catalog_client[0])["price_history"] if row["provider"] == "massive")
    assert row["integration"] == "implemented"
    assert row["acquisition"] == "price_worker"
    assert row["schedule_sources"] == []
    assert "source_schedules" not in row["controls"]


def test_repeated_catalog_reads_are_deterministic_and_independent(catalog_client):
    client = catalog_client[0]
    expected = catalog(client)
    modified = catalog(client)
    modified["categories"][0]["sources"][0]["controls"].clear()
    assert catalog(client) == expected


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_catalog_is_not_an_activation_endpoint(catalog_client, method):
    client, forbidden, root = catalog_client
    response = getattr(client, method)("/providers/data-catalog")
    assert response.status_code == 405
    assert not list(root.iterdir())
    forbidden.assert_not_called()
