"""A ticker front door without implicit issuer-map downloads or company writes."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from data_sources.sec_transport import SecResponse
from src.sec_research.issuer_store import IssuerStore
from src.sec_research.captures import CaptureStore
from src.sec_research.issuers import TICKER_MAP_URL
from src.sec_research.store import Store
from tests.test_sec_research_routes import route


def test_missing_map_is_typed_without_any_network_or_database_creation(route, monkeypatch):
    module, paths, client = route
    monkeypatch.setattr(module, "SecTransport", lambda **_: pytest.fail("read must not construct transport"))
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("read must not open writable profile"))
    response = client.get("/sec-research/issuer/resolve", params={"issuer": "aapl"})
    assert response.status_code == 200
    result = response.json()
    assert result["issuer"] == "AAPL" and result["cik"] is None
    assert result["gaps"] == [{"code": "issuer_map_unobserved"}]
    assert not paths.market_db_path.exists() and not paths.capture_root.exists()


def test_stored_ticker_resolution_preserves_map_identity_and_ambiguity(route):
    _, paths, client = route
    store = Store(paths)
    store.install()
    digest = CaptureStore(store, budget=lambda: 10000).put(b"stored test map")
    IssuerStore(store)._record(status="ok", observed_at=datetime.now(timezone.utc).isoformat(), digest=digest,
                             symbols={"AAPL": ["0000320193"], "DUAL": ["0000000001", "0000000002"]})
    before = sha256(paths.market_db_path.read_bytes()).hexdigest()
    result = client.get("/sec-research/issuer/resolve", params={"issuer": "AAPL"}).json()
    assert result["cik"] == "0000320193" and result["status"] == "ok"
    assert result["source"]["url"] == TICKER_MAP_URL
    ambiguous = client.get("/sec-research/issuer/resolve", params={"issuer": "DUAL"}).json()
    assert ambiguous["cik"] is None and ambiguous["gaps"] == [{"code": "issuer_ambiguous"}]
    assert ambiguous["candidates"] == ["0000000001", "0000000002"]
    assert sha256(paths.market_db_path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("issuer", ["", "Apple Inc.", "../AAPL", "0", "A" * 21])
def test_invalid_symbol_rejected_before_write_admission(route, monkeypatch, issuer):
    module, paths, client = route
    monkeypatch.setattr(module, "require_db_write", lambda *_: pytest.fail("invalid query admitted"))
    assert client.get("/sec-research/issuer/resolve", params={"issuer": issuer}).status_code == 422
    assert client.post("/sec-research/issuer/refresh", json={"issuer": issuer}).status_code == 422
    assert not paths.market_db_path.exists()


def test_cik_remains_an_optional_exact_identifier_without_a_map(route):
    _, paths, client = route
    result = client.get("/sec-research/issuer/resolve", params={"issuer": "CIK:320193"}).json()
    assert result["cik"] == "0000320193" and result["status"] == "ok"
    assert result["source"] is None and not paths.market_db_path.exists()


@pytest.mark.parametrize("issuer", ["CIK:320193", "320193"])
def test_directory_update_requires_a_ticker_before_admission(route, monkeypatch, issuer):
    module, paths, client = route
    monkeypatch.setattr(module, "require_db_write", lambda *_: pytest.fail("invalid directory request admitted"))
    response = client.post("/sec-research/issuer/refresh", json={"issuer": issuer})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "sec_issuer_directory_requires_ticker"
    assert not paths.market_db_path.exists()


def test_directory_refresh_is_admitted_before_configuration_or_storage(route, monkeypatch):
    module, paths, client = route
    def reject(*_):
        raise HTTPException(403, "denied")
    monkeypatch.setattr(module, "require_db_write", reject)
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("profile opened before admission"))
    monkeypatch.setattr(module, "SecTransport", lambda **_: pytest.fail("transport before admission"))
    assert client.post("/sec-research/issuer/refresh", json={"issuer": "AAPL"}).status_code == 403
    assert not paths.market_db_path.exists()


def test_explicit_directory_refresh_uses_one_governed_request_and_no_company_acquisition(route, monkeypatch):
    module, paths, client = route
    monkeypatch.setattr(module, "get_profile_store", lambda: SimpleNamespace(get_settings_snapshot=lambda keys: {}))
    monkeypatch.setattr(module, "get_data_provider_store", lambda: SimpleNamespace(
        get_all=lambda: {"sec_edgar": {"user_agent": "research@arkscope.test"}}))
    calls, closes = [], []
    class Transport:
        def __init__(self, *, user_agent, max_rate_limit_retries):
            assert user_agent == "ArkScope research@arkscope.test" and max_rate_limit_retries == 0

        def get(self, url):
            calls.append(url)
            return SecResponse(200, json.dumps({"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}).encode())

        def close(self):
            closes.append(True)

    monkeypatch.setattr(module, "SecTransport", Transport)
    monkeypatch.setattr(module.ResearchService, "refresh", lambda *_a, **_k: pytest.fail("directory command fetched company"))
    result = client.post("/sec-research/issuer/refresh", json={"issuer": "AAPL"}).json()
    assert result["status"] == "ok" and result["cik"] == "0000320193"
    assert calls == [TICKER_MAP_URL] and closes == [True]
    result2 = client.get("/sec-research/issuer/resolve", params={"issuer": "aapl"}).json()
    assert result2 == result
    assert Store(paths).latest_receipt("0000320193", scope="full") is None
