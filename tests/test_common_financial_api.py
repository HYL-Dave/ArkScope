"""HTTP reads cannot spend; acquisitions require an explicit source and write gate."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.api.dependencies import get_dal
from src.api.routes import fundamentals as module
from src.sa.company_store import save_capture
from tests.financial_read_fixtures import financial_local, sa_payload
from tests.test_common_financial_read import files, read


@pytest.fixture
def client(financial_local):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_dal] = lambda: financial_local[0]
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("alias", ["", "?stored=true", "?stored=false"])
def test_default_and_stored_alias_are_same_local_read(client, financial_local, tmp_path, alias):
    dal, http, sec = financial_local
    save_capture(sa_payload())
    before = files(tmp_path)
    response = client.get("/fundamentals/AAPL" + alias)
    assert response.status_code == 200
    result = response.json()
    expected = read(dal)
    assert result["coverage"] == expected.coverage.model_dump() and result["read_id"] == expected.read_id
    assert result["snapshot_date"] is None and result["income_statements"][0]["period_precision"] == "month"
    assert files(tmp_path) == before
    http.assert_not_called()
    sec.assert_not_called()


def test_coverage_route_does_not_get_parsed_as_ticker(client):
    save_capture(sa_payload())
    result = client.get("/fundamentals/coverage").json()
    assert result["candidate_count"] == 1 and result["items"][0]["ticker"] == "AAPL"


@pytest.mark.parametrize("query", ["period=monthly", "source=sec_edgar", "end_month=2025-99", "period_limit=0",
    "period_offset=-1", "observation_id=invalid", "read_id=invalid", "currency=usd", "freshness=refresh"])
def test_invalid_read_query_is_422(client, query):
    assert client.get("/fundamentals/AAPL?" + query).status_code == 422


def test_month_selection_and_changed_read_identity(client):
    save_capture(sa_payload())
    query = "source=seeking_alpha&end_month=2025-12"
    first = client.get("/fundamentals/AAPL?" + query).json()
    assert first["period_selection"] == "explicit_month"
    response = client.get("/fundamentals/AAPL?" + query + "&read_id=" + "a" * 64)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "financial_read_changed"
    assert client.get("/fundamentals/NONE").json()["status"] == "unavailable"


@pytest.mark.parametrize("body", [{}, {"source": "auto"}, {"source": "sec_edgar"},
    {"source": "financial_datasets", "period_limit": 8}, {"source": "seeking_alpha", "currency": "eur"}])
def test_invalid_refresh_is_422_before_write_gate(client, monkeypatch, body):
    def forbidden(*_a, **_k):
        raise AssertionError("invalid refresh reached write gate")
    monkeypatch.setattr(module, "require_db_write", forbidden)
    assert client.post("/fundamentals/AAPL/refresh", json=body).status_code == 422


def test_explicit_refresh_endpoint_enforces_provider_and_write_gate(client, financial_local, monkeypatch):
    calls = []
    def denied(action, detail):
        calls.append((action, detail))
        raise HTTPException(403, detail="denied")
    monkeypatch.setattr(module, "require_db_write", denied)
    response = client.post("/fundamentals/AAPL/refresh", json={"source": "financial_datasets"})
    assert response.status_code == 403
    assert calls == [("financial_refresh", {"ticker": "AAPL", "source": "financial_datasets"})]
    monkeypatch.setattr(module, "require_db_write", lambda *_: None)
    for source, code in [("seeking_alpha", "sa_browser_update_required"),
                         ("financial_datasets", "financial_datasets_api_key_missing")]:
        result = client.post("/fundamentals/AAPL/refresh", json={"source": source}).json()
        assert result["status"] == "unavailable" and code in {g["code"] for g in result["read_gaps"]}
    financial_local[1].assert_not_called()
