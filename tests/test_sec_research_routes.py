"""Explicit SEC writes and genuinely stored-only reads at the application edge."""

import importlib.util
import sqlite3
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest


def test_sec_research_routes_exist():
    assert importlib.util.find_spec("src.api.routes.sec_research") is not None


@pytest.fixture
def route(tmp_path, monkeypatch):
    import src.api.routes.sec_research as module
    from src.sec_research.paths import SecResearchPaths
    paths = SecResearchPaths.from_market_db(tmp_path / "market.db")
    monkeypatch.setattr(module.SecResearchPaths, "resolve", lambda: paths)
    app = FastAPI()
    app.include_router(module.router)
    return module, paths, TestClient(app)


def test_absent_stored_get_creates_nothing_and_never_constructs_transport(route, monkeypatch):
    module, paths, client = route
    monkeypatch.setattr(module, "SecTransport", lambda **kw: pytest.fail("GET constructed transport"))
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("GET opened profile"))
    response = client.get("/sec-research/CIK:320193")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["gaps"] == [{"code": "sec_research_not_installed"}]
    assert not paths.market_db_path.exists()
    assert not paths.capture_root.exists()


def test_existing_unrelated_db_get_does_not_install_schema(route):
    _, paths, client = route
    with sqlite3.connect(paths.market_db_path) as conn:
        conn.execute("CREATE TABLE prices(value TEXT)")
        conn.execute("INSERT INTO prices VALUES('retained')")
    response = client.get("/sec-research/320193")
    assert response.json()["status"] == "unavailable"
    with sqlite3.connect(paths.market_db_path) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("prices",)]
        assert conn.execute("SELECT value FROM prices").fetchone()[0] == "retained"


def test_permission_rejection_precedes_every_store_and_provider_construction(route, monkeypatch):
    module, paths, client = route
    def reject(*args):
        raise HTTPException(403, "denied")
    monkeypatch.setattr(module, "require_db_write", reject)
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("profile constructed before admission"))
    monkeypatch.setattr(module, "get_data_provider_store", lambda: pytest.fail("config constructed before admission"))
    monkeypatch.setattr(module, "SecTransport", lambda **kw: pytest.fail("transport before admission"))
    assert client.post("/sec-research/320193/refresh", json={}).status_code == 403
    assert not paths.market_db_path.exists()


@pytest.mark.parametrize("body", [{"max_sources": 0}, {"max_sources": 17}, {"max_sources": True}, {"resume": "yes"}, {"extra": 1}])
def test_invalid_refresh_options_do_not_open_stores(route, monkeypatch, body):
    module, paths, client = route
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("invalid input opened stores"))
    assert client.post("/sec-research/320193/refresh", json=body).status_code == 422
    assert not paths.market_db_path.exists()


def test_invalid_cik_precedes_permissions_and_stores(route, monkeypatch):
    module, paths, client = route
    monkeypatch.setattr(module, "require_db_write", lambda *a: pytest.fail("invalid identity admitted"))
    assert client.post("/sec-research/NOT_A_CIK/refresh", json={}).status_code == 422
    assert not paths.market_db_path.exists()


def test_refresh_persists_real_sources_and_resume_uses_no_request(route, monkeypatch):
    import json
    from data_sources.sec_transport import SecResponse
    module, paths, client = route
    monkeypatch.setattr(module, "get_profile_store", lambda: SimpleNamespace(get_settings_snapshot=lambda keys: {}))
    monkeypatch.setattr(module, "get_data_provider_store", lambda: SimpleNamespace(
        get_all=lambda: {"sec_edgar": {"user_agent": "research@arkscope.test"}}))
    calls, closed, identities = [], [], []
    class Transport:
        def __init__(self, *, user_agent):
            identities.append(user_agent)

        def get(self, url, **kwargs):
            calls.append(url)
            with sqlite3.connect(paths.market_db_path, timeout=0) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.rollback()
            if "companyfacts" in url:
                data = {"cik": 320193, "facts": {}}
            else:
                data = {"cik": 320193, "filings": {"recent": {
                    "accessionNumber": [], "filingDate": [], "form": []}, "files": []}}
            return SecResponse(200, json.dumps(data).encode())

        def close(self):
            closed.append(True)
    monkeypatch.setattr(module, "SecTransport", Transport)
    response = client.post("/sec-research/320193/refresh", json={})
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "ok", response.json()
    assert len(calls) == 2
    status = client.get("/sec-research/320193").json()
    assert status["status"] == "ok"
    assert status["data"]["snapshots"] == {"catalog": 1, "facts": 1}
    assert status["coverage"]["pending"] == []
    assert client.post("/sec-research/320193/refresh", json={"resume": True}).status_code == 200
    assert len(calls) == 2
    assert len(closed) == 2
    assert identities == ["ArkScope research@arkscope.test"] * 2


def test_missing_managed_sec_identity_never_uses_environment_fallback(route, monkeypatch):
    module, paths, client = route
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "Legacy legacy@arkscope.test")
    monkeypatch.setattr(module, "get_profile_store", lambda: SimpleNamespace(get_settings_snapshot=lambda keys: {}))
    monkeypatch.setattr(module, "get_data_provider_store", lambda: SimpleNamespace(get_all=lambda: {}))
    monkeypatch.setattr(module, "SecTransport", lambda **kw: pytest.fail("unmanaged identity used"))
    response = client.post("/sec-research/320193/refresh", json={})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "sec_identity_unconfigured"
    assert not paths.market_db_path.exists()
