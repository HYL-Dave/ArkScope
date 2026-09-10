"""The operator endpoints use the same read-only projection as local callers."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from tests.test_security_lifecycle_current import reader, deny_network
from tests.test_security_lifecycle_review import context, rows
from tests.test_security_lifecycle_provider_authority import NOW


def client(c, monkeypatch):
    from src.api.dependencies import get_security_lifecycle_read_service
    from src.api.routes import security_lifecycle as routes
    app = FastAPI()
    app.include_router(routes.router)
    service = reader(c["market"], c["profile"], c["sources"])
    app.dependency_overrides[get_security_lifecycle_read_service] = lambda: service
    monkeypatch.setattr(routes, "_utc_now", lambda: NOW)
    def denied(*args, **kwargs):
        raise AssertionError("no_write_command_on_read")
    monkeypatch.setattr(routes, "require_db_write", denied)
    monkeypatch.setattr(routes, "require_profile_state_write", denied)
    return TestClient(app), service


def test_current_routes_return_the_shared_projection_without_any_write(tmp_path, monkeypatch):
    c = context(tmp_path)
    browser, service = client(c, monkeypatch)
    before = rows(c)
    response = browser.get("/security-lifecycle/reviews")
    assert response.status_code == 200, response.text
    assert response.json() == service.list_current_reviews(at=NOW)
    assert rows(c) == before


@pytest.mark.parametrize("query", ("view=invalid", "limit=0", "limit=201", "offset=-1"))
def test_current_routes_reject_invalid_filters(tmp_path, monkeypatch, query):
    browser, _ = client(context(tmp_path), monkeypatch)
    assert browser.get("/security-lifecycle/reviews?" + query).status_code == 422


def test_current_route_unavailable_is_not_a_successful_empty_page(tmp_path, monkeypatch):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    c = context(tmp_path)
    browser, service = client(c, monkeypatch)
    def unavailable(**kwargs):
        raise LifecyclePopulationUnavailable("current_snapshot_changed")
    monkeypatch.setattr(service, "list_current_reviews", unavailable)
    response = browser.get("/security-lifecycle/reviews")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "lifecycle_current_unavailable"
    assert "items" not in response.json()


def test_current_route_case_filter_is_not_silently_ignored(tmp_path, monkeypatch):
    c = context(tmp_path)
    browser, _ = client(c, monkeypatch)
    assert browser.get("/security-lifecycle/reviews?case_id=absent").json()["items"] == []
    response = browser.get("/security-lifecycle/reviews", params={"case_id": c["case_id"]})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
