"""Stored-only HTTP reads and explicit acquisition through the real document owners."""

import hashlib
import json
import sqlite3
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.sec_research.captures import CaptureStore
from src.sec_research.document_store import DocumentStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store
from tests.test_lifecycle_public_sources import Response
from tests.test_sec_research_document_service import FILING_ID, ROOT_URL, rig  # noqa: F401


URL = f"/sec-research/filings/{FILING_ID}/document"
ENVELOPE = {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}


class ForbiddenAccess(RuntimeError):
    """Ordinary request-worker exception; the test-side call ledger is authoritative."""


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
        raise ForbiddenAccess("document route crossed a forbidden side-effect boundary")

    with TestClient(app) as client:
        request = client.request

        def checked_request(*args, **kwargs):
            try:
                return request(*args, **kwargs)
            finally:
                # Check outside the worker even when the route swallowed the sentinel.
                assert forbidden_calls == [], f"forbidden document access: {forbidden_calls!r}"

        monkeypatch.setattr(client, "request", checked_request)
        yield SimpleNamespace(module=module, paths=paths, client=client, app=app, forbidden=forbidden)


@pytest.fixture
def configured(route, monkeypatch):
    monkeypatch.setattr(route.module, "get_profile_store", lambda: SimpleNamespace(
        get_settings_snapshot=lambda keys: {}))
    monkeypatch.setattr(route.module, "get_data_provider_store", lambda: SimpleNamespace(
        get_all=lambda: {"sec_edgar": {"user_agent": "Task3 fixture task3@example.com"}}))
    return route


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


def setup_store(route, mode):
    if mode == "installed":
        Store(route.paths).install()
    elif mode in {"unrelated", "old"}:
        with sqlite3.connect(route.paths.market_db_path) as conn:
            conn.execute("CREATE TABLE prices(value TEXT)")
            conn.execute("INSERT INTO prices VALUES('retained')")
            if mode == "old":
                conn.execute("CREATE TABLE sec_research_documents(secret TEXT)")
    elif mode == "corrupt":
        route.paths.market_db_path.write_bytes(b"PRIVATE broken sqlite")


@pytest.mark.parametrize("mode", ["absent", "unrelated", "old", "corrupt", "installed"])
def test_valid_missing_document_is_unavailable_and_get_never_writes(route, monkeypatch, mode):
    setup_store(route, mode)
    before = snapshot(route.paths)
    forbid_get_writes(route, monkeypatch)
    response = route.client.get(URL)
    assert response.status_code == 200
    result = response.json()
    assert set(result) == ENVELOPE and result["status"] == "unavailable"
    assert result["data"] == dict(document=None, documents=[], sections=[], passages=[], text_start_cursor=None)
    assert result["coverage"] == {"capture_id": None, "complete": False}
    assert result["next_cursor"] is None and result["gaps"]
    assert "PRIVATE" not in response.text
    assert snapshot(route.paths) == before


@pytest.mark.parametrize("mode", ["absent", "corrupt"])
@pytest.mark.parametrize("params,code", [
    ({"document_id": "https://private.invalid/body"}, "sec_research_query_invalid"),
    ({"document_id": "file:.."}, "sec_research_query_invalid"),
    ({"capture_id": "PRIVATE"}, "sec_research_query_invalid"),
    ({"section_id": "Item 1"}, "sec_research_query_invalid"),
    ({"query": ""}, "sec_research_query_invalid"),
    ({"cursor": "PRIVATE!"}, "sec_research_cursor_invalid"),
    ({"cursor": ""}, "sec_research_cursor_invalid"),
    ({"cursor": "x" * 4097}, "sec_research_cursor_invalid"),
    *[({"max_chars": v}, "sec_research_query_invalid")
      for v in ("0", "20001", "1.0", "true", "-1", "01", "", "PRIVATE")],
])
def test_invalid_get_operands_precede_store_access(route, monkeypatch, mode, params, code):
    setup_store(route, mode)
    monkeypatch.setattr(route.module.SecResearchPaths, "resolve", route.forbidden)
    response = route.client.get(URL, params=params)
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": code}}


@pytest.mark.parametrize("method", ["get", "post"])
def test_invalid_filing_precedes_permissions_and_paths(route, monkeypatch, method):
    monkeypatch.setattr(route.module, "require_db_write", route.forbidden)
    monkeypatch.setattr(route.module.SecResearchPaths, "resolve", route.forbidden)
    url = "/sec-research/filings/PRIVATE/document"
    response = (route.client.get(url) if method == "get" else
                route.client.post(url, json={"document_id": "primary"}))
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "sec_research_query_invalid"}}


@pytest.mark.parametrize("body", [{}, {"document_id": "file:actual.htm"},
    {"document_id": None}, {"document_id": True}, {"document_id": 1},
    {"document_id": "primary", "PRIVATE": "PRIVATE"}, {"document_id": "PRIVATE"}, []])
def test_post_requires_exact_primary_body_before_mutation(route, monkeypatch, body):
    monkeypatch.setattr(route.module, "require_db_write", route.forbidden)
    monkeypatch.setattr(route.module.SecResearchPaths, "resolve", route.forbidden)
    response = route.client.post(URL, json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "sec_research_query_invalid"}}


@pytest.mark.parametrize("body", [b"", b'{"document_id": PRIVATE}'])
def test_post_body_parse_errors_are_content_free(route, monkeypatch, body):
    monkeypatch.setattr(route.module, "require_db_write", route.forbidden)
    response = route.client.post(URL, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "sec_research_query_invalid"}}


def test_shared_permission_denial_precedes_all_post_owners(route, monkeypatch):
    from src.api import permissions

    def reject(permission, action, detail):
        assert permission == permissions.PermissionClass.db_write
        assert action == "sec_research_document_acquire"
        assert detail == {"filing_id": FILING_ID, "document_id": "primary"}
        raise HTTPException(403, detail={"code": "denied"})

    monkeypatch.setattr(permissions, "require_permission", reject)
    for name in ("get_profile_store", "get_data_provider_store", "Store", "CaptureStore"):
        monkeypatch.setattr(route.module, name, route.forbidden)
    response = route.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 403 and response.json() == {"detail": {"code": "denied"}}
    assert not route.paths.market_db_path.exists()


@pytest.mark.parametrize("identity", ["", "PRIVATE", None, 42])
def test_bad_managed_identity_never_installs_or_uses_environment(configured, monkeypatch, identity):
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "Legacy legacy@example.com")
    monkeypatch.setattr(configured.module, "get_data_provider_store", lambda: SimpleNamespace(
        get_all=lambda: {"sec_edgar": {"user_agent": identity}}))
    monkeypatch.setattr(Store, "install", configured.forbidden)
    response = configured.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sec_identity_unconfigured"}}
    assert not configured.paths.market_db_path.exists()


def test_corrupt_budget_precedes_installation(configured, monkeypatch):
    monkeypatch.setattr(configured.module, "get_profile_store", lambda: SimpleNamespace(
        get_settings_snapshot=lambda keys: {"sec_research.capture_budget_bytes": "PRIVATE"}))
    monkeypatch.setattr(Store, "install", configured.forbidden)
    response = configured.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sec_research_document_unavailable"}}


@pytest.mark.parametrize("mode", ["old", "corrupt"])
def test_post_cannot_repair_existing_store_shapes(configured, mode):
    setup_store(configured, mode)
    before = snapshot(configured.paths)
    response = configured.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 503 and "PRIVATE" not in response.text
    assert snapshot(configured.paths) == before


def test_explicit_post_installs_fresh_schema_without_inventing_catalog(configured):
    response = configured.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 200
    attempt = response.json()
    assert attempt["status"] == "unavailable" and attempt["capture_id"] is None
    assert attempt["outcome"] == "no_dispatch" and attempt["requests"] == []
    assert isinstance(attempt["attempt_id"], int)
    assert DocumentStore(Store(configured.paths)).latest_attempt(FILING_ID, "primary") == attempt


@pytest.fixture
def live_route(configured, rig, monkeypatch):
    # Keep service, reader, policy, parser and storage real; only the wire and governor are offline.
    from src import lifecycle_web_sec_sources as sec

    monkeypatch.setattr(configured.module.SecResearchPaths, "resolve", lambda: rig.store.paths)
    configured.paths = rig.store.paths
    checks = []

    class Governor:
        def reserve_request_start(self, *, check):
            check()
            checks.append(True)

    monkeypatch.setattr(sec, "SecRequestGovernor", Governor)
    monkeypatch.setattr(sec, "get_sec_user_agent", configured.forbidden)
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "Wrong wrong@example.com")
    configured.rig, configured.policy_checks = rig, checks
    return configured


def acquire(route, **kwargs):
    route.rig.enqueue(**kwargs)
    response = route.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 200, response.text
    return response.json()


def test_real_post_get_search_and_pinned_reread_keep_exact_bytes(live_route, monkeypatch, tmp_path):
    route = live_route
    body = b"<h1>Item 1. Business</h1><p>needle caf\xc3\xa9 needle</p>"
    attempt = acquire(route, body=body, compressed=True)
    assert attempt["status"] == "ok" and attempt["outcome"] == "complete"
    assert attempt["document_id"] == "primary" and attempt["resolved_document_id"] == "file:actual.htm"
    assert attempt["invalidation_primary_document"] is None
    assert [r["request_count"] for r in attempt["requests"]] == [1, 1]
    assert [r["dispatch_state"] for r in attempt["requests"]] == ["dispatched", "dispatched"]
    assert route.policy_checks == [True, True]
    assert [c.requests[0][2]["User-Agent"] for c in route.rig.requests] == [
        "Task3 fixture task3@example.com"] * 2
    assert all(c.closed for c in route.rig.requests)
    assert [r["url"] for r in attempt["requests"]] == [ROOT_URL + "index.json", ROOT_URL + "actual.htm"]
    before = snapshot(route.paths)
    forbid_get_writes(route, monkeypatch)
    params = {"capture_id": attempt["capture_id"], "max_chars": 80}
    index_response = route.client.get(URL, params=params)
    index = index_response.json()
    assert index_response.status_code == 200 and set(index) == ENVELOPE
    assert index["status"] == "ok" and index["coverage"]["complete"] is True
    assert index["data"]["document"]["original_sha256"] == hashlib.sha256(body).hexdigest()
    assert index["data"]["sections"][0]["section_id"] == "item_1"
    text_params = {**params, "cursor": index["data"]["text_start_cursor"]}
    text = route.client.get(URL, params=text_params).json()
    passage = text["data"]["passages"][0]
    assert passage["text"] == "Item 1. Business\nneedle caf\u00e9 needle"
    citation = passage["citation"]
    assert (citation["start_byte"], citation["end_byte"]) == (0, 36)
    assert citation["capture_id"] == attempt["capture_id"]
    assert citation["text_sha256"] == hashlib.sha256(passage["text"].encode()).hexdigest()
    assert route.client.get(URL, params=text_params).json() == text
    search_params = {**params, "section_id": "item_1", "query": "needle"}
    search = route.client.get(URL, params=search_params).json()
    match = search["data"]["passages"][0]["citation"]
    assert (match["match_start_byte"], match["match_end_byte"]) == (17, 23)
    assert search["next_cursor"]
    second = route.client.get(URL, params={**search_params, "cursor": search["next_cursor"]}).json()
    assert second["data"]["passages"][0]["citation"]["match_start_byte"] == 30
    assert second["next_cursor"] is None
    assert route.client.get(URL, params={**params, "query": "NEEDLE"}).json()["status"] == "empty"
    resolved = route.client.get(URL, params={**params, "document_id": "file:actual.htm"}).json()
    assert resolved["data"]["document"] == index["data"]["document"]
    missing = route.client.get(URL, params={**params, "section_id": "missing"}).json()
    assert missing["status"] == "unavailable" and missing["data"]["text_start_cursor"]
    assert snapshot(route.paths) == before
    examples = [
        {"method": "POST", "path": URL, "body": {"document_id": "primary"}, "response": attempt},
        *[{"method": "GET", "path": URL, "params": operands, "response": result}
          for operands, result in ((params, index), (text_params, text), (search_params, search),
              ({**search_params, "cursor": search["next_cursor"]}, second),
              ({**params, "section_id": "missing"}, missing))],
    ]
    (tmp_path / "interface-examples.json").write_text(json.dumps(examples, indent=2) + "\n")


def test_cursor_binding_rejected_before_absent_store(live_route, monkeypatch):
    attempt = acquire(live_route)
    params = {"capture_id": attempt["capture_id"], "max_chars": 80}
    cursor = live_route.client.get(URL, params=params).json()["data"]["text_start_cursor"]
    monkeypatch.setattr(live_route.module.SecResearchPaths, "resolve", live_route.forbidden)
    for changed in ({"query": "needle"}, {"max_chars": 81}, {"document_id": "file:actual.htm"},
                    {"capture_id": "secdoc_" + "0" * 64}, {"section_id": "item_1"}):
        response = live_route.client.get(URL, params={**params, "cursor": cursor, **changed})
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "sec_research_cursor_mismatch"}}


def test_failed_refresh_does_not_replace_pinned_text_with_latest(live_route):
    first = acquire(live_route)
    params = {"capture_id": first["capture_id"], "section_id": "item_1"}
    original = live_route.client.get(URL, params=params).json()
    failed = acquire(live_route, status=600)
    assert failed["status"] == "unavailable" and failed["outcome"] == "failed"
    assert failed["capture_id"] is None
    request = failed["requests"][-1]
    assert request["request_count"] == 1 and request["dispatch_state"] == "dispatched"
    assert request["report"] is None and request["gaps"] == [{"code": "source_read_report_invalid"}]
    assert live_route.client.get(URL).json()["status"] == "unavailable"
    assert live_route.client.get(URL, params=params).json() == original


def test_timeout_after_dispatch_is_an_attempt_and_get_can_reread(live_route):
    first = acquire(live_route)
    live_route.rig.enqueue()

    class TimedOut(Response):
        def read(self, size):
            raise TimeoutError("PRIVATE timeout body")

    live_route.rig.queue[-1] = TimedOut(headers={"Content-Type": "text/html"})
    response = live_route.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 200
    attempt = response.json()
    assert attempt["status"] == "unavailable" and attempt["outcome"] == "failed"
    assert attempt["capture_id"] is None and "PRIVATE" not in response.text
    assert attempt["requests"][-1]["request_count"] == 1
    assert attempt["requests"][-1]["dispatch_state"] == "dispatched"
    assert {"code": "source_read_timeout"} in attempt["gaps"]
    assert DocumentStore(live_route.rig.store).latest_attempt(FILING_ID, "primary") == attempt
    assert live_route.client.get(URL).json()["status"] == "unavailable"
    assert live_route.client.get(URL, params={"capture_id": first["capture_id"]}).json()["status"] == "ok"


def test_document_http_operands_are_exactly_query_owner_operands(route):
    operation = route.app.openapi()["paths"]["/sec-research/filings/{filing_id}/document"]["get"]
    assert {p["name"] for p in operation["parameters"]} == {
        "filing_id", "document_id", "capture_id", "section_id", "query", "cursor", "max_chars"}


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("error", [ValueError, RuntimeError, sqlite3.OperationalError, OSError, TimeoutError])
def test_unexpected_owner_errors_never_expose_content(configured, monkeypatch, method, error):
    def broken():
        raise error("PRIVATE /profile/path original body")

    monkeypatch.setattr(configured.module.SecResearchPaths, "resolve", broken)
    response = (configured.client.get(URL) if method == "get" else
                configured.client.post(URL, json={"document_id": "primary"}))
    assert response.status_code == (200 if method == "get" else 503)
    assert "PRIVATE" not in response.text and "/profile/path" not in response.text
    if method == "get":
        assert set(response.json()) == ENVELOPE and response.json()["status"] == "unavailable"
    else:
        assert response.json() == {"detail": {"code": "sec_research_document_unavailable"}}
    assert not configured.paths.market_db_path.exists()


def test_corrupt_budget_does_not_block_existing_stored_document(live_route, monkeypatch):
    from src.profile_state import ProfileStateStore

    attempt = acquire(live_route)
    profile = ProfileStateStore(live_route.paths.market_db_path.parent / "profile.db")
    profile.set_setting("sec_research.capture_budget_bytes", "PRIVATE broken")
    monkeypatch.setattr(live_route.module, "get_profile_store", lambda: profile)
    before = snapshot(live_route.paths)
    response = live_route.client.get(URL, params={"capture_id": attempt["capture_id"], "section_id": "item_1"})
    assert response.status_code == 200 and response.json()["status"] == "ok"
    assert response.json()["data"]["passages"][0]["text"] == "Item 1. Business\nneedle one needle two"
    assert snapshot(live_route.paths) == before


@pytest.mark.parametrize("max_chars", [None, 1, 20000])
def test_get_character_budget_controls_real_text_pages(live_route, max_chars):
    acquire(live_route, body=b"<h1>Item 1. Business</h1><p>" + b"a" * 20010 + b"</p>")
    params = {"section_id": "item_1"}
    if max_chars is not None:
        params["max_chars"] = max_chars
    response = live_route.client.get(URL, params=params)
    assert response.status_code == 200
    page = response.json()
    assert len(page["data"]["passages"][0]["text"]) == (6000 if max_chars is None else max_chars)
    assert page["next_cursor"] and len(response.content) <= 256 * 1024


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_get_missing_or_corrupt_captured_object_is_not_empty(live_route, monkeypatch, failure):
    attempt = acquire(live_route)
    record = DocumentStore(live_route.rig.store).capture(attempt["capture_id"])
    path = live_route.paths.capture_root / "objects" / record["text_sha256"]
    if failure == "missing":
        path.unlink()
    else:
        path.write_bytes(b"PRIVATE broken capture")
    before = snapshot(live_route.paths)
    forbid_get_writes(live_route, monkeypatch)
    response = live_route.client.get(URL, params={"capture_id": attempt["capture_id"]})
    assert response.status_code == 200 and response.json()["status"] == "unavailable"
    assert response.json()["data"]["passages"] == [] and response.json()["gaps"]
    assert "PRIVATE" not in response.text and snapshot(live_route.paths) == before


def test_email_only_profile_identity_is_normalized_on_both_actual_requests(live_route, monkeypatch):
    monkeypatch.setattr(live_route.module, "get_data_provider_store", lambda: SimpleNamespace(
        get_all=lambda: {"sec_edgar": {"user_agent": "task3@example.com"}}))
    assert acquire(live_route)["capture_id"]
    assert [c.requests[0][2]["User-Agent"] for c in live_route.rig.requests] == [
        "ArkScope task3@example.com"] * 2


def test_busy_root_returns_service_attempt_without_dispatch(live_route):
    from src.sec_research.capture_lock import document_acquisition

    with document_acquisition(live_route.paths.capture_root):
        response = live_route.client.post(URL, json={"document_id": "primary"})
    assert response.status_code == 200
    attempt = response.json()
    assert attempt["status"] == "unavailable" and attempt["attempt_id"] is None
    assert attempt["capture_id"] is None and attempt["outcome"] == "no_dispatch"
    assert attempt["gaps"] == [{"code": "document_acquisition_busy"}]
    assert attempt["requests"] == [] and live_route.rig.requests == []
