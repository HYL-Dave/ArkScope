"""Retained research citations outlive the removed Settings document reader."""

import base64
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store
from tests.test_sec_research_document_service import FILING_ID, rig  # noqa: F401
from tests.test_sec_research_citations import TEXT, evidence  # noqa: F401


@pytest.fixture
def route(tmp_path, monkeypatch):
    import src.api.routes.sec_research as module

    paths = SecResearchPaths.from_market_db(tmp_path / "market.db")
    monkeypatch.setattr(module.SecResearchPaths, "resolve", lambda: paths)
    app = FastAPI()
    app.include_router(module.router)
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append((args, kwargs))
        raise RuntimeError("citation route crossed a forbidden side-effect boundary")

    with TestClient(app) as client:
        request = client.request

        def checked_request(*args, **kwargs):
            try:
                return request(*args, **kwargs)
            finally:
                assert forbidden_calls == [], f"forbidden citation access: {forbidden_calls!r}"

        monkeypatch.setattr(client, "request", checked_request)
        yield SimpleNamespace(module=module, paths=paths, client=client, forbidden=forbidden)


def forbid_get_writes(route, monkeypatch):
    for name in ("get_profile_store", "get_data_provider_store", "SecTransport"):
        monkeypatch.setattr(route.module, name, route.forbidden)
    monkeypatch.setattr(Store, "install", route.forbidden)
    for name in ("put", "preflight", "recover", "status"):
        monkeypatch.setattr(CaptureStore, name, route.forbidden)
    from src.sec_research.document_service import DocumentService
    monkeypatch.setattr(DocumentService, "refresh", route.forbidden)


def snapshot(paths):
    return {str(p.relative_to(paths.market_db_path.parent)): p.read_bytes()
            for p in paths.market_db_path.parent.rglob("*") if p.is_file()}


def test_citation_get_reopens_real_retained_source_before_dynamic_cik_route(route, evidence, monkeypatch):
    forbid_get_writes(route, monkeypatch)
    before = snapshot(route.paths)
    canonical = json.dumps(evidence.document_ref, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    token = base64.urlsafe_b64encode(canonical.encode()).decode().rstrip("=")
    response = route.client.get("/sec-research/citation", params={"ref": token})
    assert response.status_code == 200, response.text
    page = response.json()
    assert set(page) == {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}
    assert page["status"] == "ok"
    assert page["data"]["text"] == TEXT and page["data"]["citation"] == evidence.document_ref
    assert snapshot(route.paths) == before


@pytest.mark.parametrize("params", [{}, {"ref": "PRIVATE"}, {"ref": "a" * 8193},
    {"ref": "e30="}, {"ref": "e30", "path": "/PRIVATE"},
    [("ref", "e30"), ("ref", "e30")]])
def test_citation_query_errors_are_closed_before_store_access(route, monkeypatch, params):
    forbid_get_writes(route, monkeypatch)
    monkeypatch.setattr(route.module.SecResearchPaths, "resolve", route.forbidden)
    response = route.client.get("/sec-research/citation", params=params)
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "sec_citation_query_invalid"}}
    assert not route.paths.market_db_path.exists() and not route.paths.capture_root.exists()


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_settings_reader_endpoints_are_absent_before_credentials_or_storage(route, monkeypatch, method):
    forbid_get_writes(route, monkeypatch)
    monkeypatch.setattr(route.module.SecResearchPaths, "resolve", route.forbidden)
    response = route.client.request(method, f"/sec-research/filings/{FILING_ID}/document",
                                    json={"document_id": "primary"})
    assert response.status_code == 404
