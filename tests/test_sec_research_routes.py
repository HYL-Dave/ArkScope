"""Explicit SEC writes and genuinely stored-only reads at the application edge."""

import importlib.util
import json
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


CIK = "0000320193"
WHEN = "2026-09-11T12:00:00Z"
BUDGET_KEY = "sec_research.capture_budget_bytes"


@pytest.fixture
def profile(route, tmp_path, monkeypatch):
    from src.profile_state import ProfileStateStore
    result = ProfileStateStore(tmp_path / "profile" / "state.db")
    monkeypatch.setattr(route[0], "get_profile_store", lambda: result)
    return result


@pytest.fixture
def stored(route):
    from src.sec_research.store import Store
    store = Store(route[1])
    store.install()
    return store


def forbid_acquisition(module, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("stored/config route attempted acquisition or installation")
    monkeypatch.setattr(module, "SecTransport", forbidden)
    monkeypatch.setattr(module, "get_data_provider_store", forbidden)
    monkeypatch.setattr(module.Store, "install", forbidden)
    for name in ("recover", "preflight", "put"):
        monkeypatch.setattr(module.CaptureStore, name, forbidden)
    monkeypatch.setattr(module.ResearchService, "refresh", forbidden)


def publish_catalog(store, rows=(), *, pending=False):
    from src.sec_research.catalog import parse_submissions
    from src.sec_research.captures import CaptureStore
    columns = {"accessionNumber": [], "filingDate": [], "form": []}
    for number, filed, form in rows:
        columns["accessionNumber"].append(f"0000320193-26-{number:06d}")
        columns["filingDate"].append(filed)
        columns["form"].append(form)
    history = "CIK0000320193-submissions-001.json"
    raw = json.dumps({"cik": 320193, "filings": {"recent": columns,
                     "files": [{"name": history}] if pending else []}}).encode()
    captures = CaptureStore(store, budget=lambda: 107374182400, free_bytes=lambda _: 10**12)
    sha = captures.put(raw)
    sid = store.publish(parse_submissions(raw, cik=CIK), object_sha256=sha,
                        observed_at=WHEN, source_url=f"https://data.sec.gov/submissions/CIK{CIK}.json")
    return store.record_receipt(CIK, status="partial" if pending else "ok",
        completed=["submissions"], pending=[history] if pending else [], gaps=[], observed_at=WHEN,
        source_snapshots={"submissions": {"snapshot_id": sid, "observed_at": WHEN}})


def publish_facts(store):
    from src.sec_research.captures import CaptureStore
    from src.sec_research.facts import parse_companyfacts
    raw = b'''{"cik":320193,"facts":{"us-gaap":{
      "Assets":{"units":{"EUR":[
        {"val":1234567890123456789.123,"end":"2025-12-31","filed":"2026-02-01",
         "form":"10-K","accn":"0000320193-26-000001"},
        {"val":9,"end":"2025-12-31","filed":"2026-03-01",
         "form":"10-K/A","accn":"0000320193-26-000002"}]}},
      "Liabilities":{"units":{"EUR":[
        {"val":4,"end":"2025-12-31","filed":"2026-02-01",
         "form":"10-K","accn":"0000320193-26-000001"}]}}
    }}}'''
    captures = CaptureStore(store, budget=lambda: 107374182400, free_bytes=lambda _: 10**12)
    sha = captures.put(raw)
    snapshot = parse_companyfacts(raw, cik=CIK)
    sid = store.publish(snapshot, object_sha256=sha, observed_at=WHEN,
        source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json")
    store.record_receipt(CIK, status="ok", completed=["companyfacts"], pending=[], gaps=[],
        observed_at=WHEN, source_snapshots={"companyfacts": {"snapshot_id": sid, "observed_at": WHEN}})
    return snapshot


def test_static_config_default_does_not_install_or_acquire(route, profile, monkeypatch):
    module, paths, client = route
    forbid_acquisition(module, monkeypatch)
    response = client.get("/sec-research/config")
    assert response.status_code == 200
    assert response.json() == {"capture_budget_bytes": 107374182400, "capacity": None}
    assert profile.get_settings_snapshot([BUDGET_KEY]) == {}
    assert not paths.market_db_path.exists()
    assert not paths.capture_root.exists()


@pytest.mark.parametrize("value", [1, 9007199254740989, 9007199254740991])
def test_config_save_persists_exact_integer_without_acquisition(route, profile, monkeypatch, value):
    module, paths, client = route
    forbid_acquisition(module, monkeypatch)
    admissions = []
    monkeypatch.setattr(module, "require_db_write", lambda *args: admissions.append(args))
    response = client.put("/sec-research/config", json={"capture_budget_bytes": value})
    assert response.status_code == 200
    assert response.json() == {"capture_budget_bytes": value}
    assert admissions == [("sec_research_config", {"capture_budget_bytes": value})]
    assert profile.get_settings_snapshot([BUDGET_KEY]) == {BUDGET_KEY: str(value)}
    assert client.get("/sec-research/config").json()["capture_budget_bytes"] == value
    assert not paths.market_db_path.exists()
    assert not paths.capture_root.exists()


@pytest.mark.parametrize("value", [True, False, "1", 1.0, 0, -1, None, 9007199254740992])
def test_invalid_config_rejected_before_owners(route, monkeypatch, value):
    module, _, client = route
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("invalid input opened profile"))
    response = client.put("/sec-research/config", json={"capture_budget_bytes": value})
    assert response.status_code == 422


@pytest.mark.parametrize("body", [{}, {"capture_budget_bytes": 1, "extra": 2}])
def test_config_requires_only_budget_field(route, body):
    assert route[2].put("/sec-research/config", json=body).status_code == 422


def test_config_permission_denial_precedes_mutation_owners(route, monkeypatch):
    module, paths, client = route
    def reject(*args):
        raise HTTPException(403, "denied")
    def forbidden(*args, **kwargs):
        pytest.fail("config constructed owner before write permission")
    monkeypatch.setattr(module, "require_db_write", reject)
    for name in ("get_profile_store", "Store", "CaptureStore", "SecTransport"):
        monkeypatch.setattr(module, name, forbidden)
    assert client.put("/sec-research/config", json={"capture_budget_bytes": 1}).status_code == 403
    assert not paths.market_db_path.exists()


def test_config_reduction_retains_objects_reservations_orphans_and_other_settings(
    route, profile, stored, monkeypatch,
):
    module, paths, client = route
    publish_catalog(stored)
    with stored.connect() as conn:
        conn.execute("INSERT INTO sec_research_orphans VALUES('orphan',7)")
        conn.execute("INSERT INTO sec_research_reservations VALUES('reserved',11)")
        size = conn.execute("SELECT SUM(size_bytes) FROM sec_research_objects").fetchone()[0]
    profile.set_setting("security_lifecycle.automation.enabled", "false")
    before = paths.market_db_path.read_bytes()
    files = {p: p.read_bytes() for p in paths.capture_root.rglob("*") if p.is_file()}
    forbid_acquisition(module, monkeypatch)
    monkeypatch.setattr(module, "require_db_write", lambda *args: None)
    assert client.put("/sec-research/config", json={"capture_budget_bytes": 1}).json() == {
        "capture_budget_bytes": 1}
    assert client.get("/sec-research/config").json() == {"capture_budget_bytes": 1, "capacity": {
        "persisted_bytes": size, "orphan_bytes": 7, "reserved_bytes": 11,
        "charged_bytes": size + 18, "budget_bytes": 1, "remaining_bytes": 0, "over_budget": True}}
    assert paths.market_db_path.read_bytes() == before
    assert {p: p.read_bytes() for p in paths.capture_root.rglob("*") if p.is_file()} == files
    assert profile.get_settings_snapshot(["security_lifecycle.automation.enabled"]) == {
        "security_lifecycle.automation.enabled": "false"}


@pytest.mark.parametrize("value", ["broken/private/path", "0", "01", None])
def test_config_corrupt_persisted_budget_is_explicit_503_not_default(route, profile, value):
    profile.set_setting(BUDGET_KEY, value)
    response = route[2].get("/sec-research/config")
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sec_research_config_invalid"}}
    assert profile.get_settings_snapshot([BUDGET_KEY]) == {BUDGET_KEY: value}


@pytest.mark.parametrize("mode", ["unrelated", "mismatch", "partial-uppercase", "corrupt"])
def test_config_capacity_absent_is_null_but_broken_store_is_explicit(route, profile, mode):
    _, paths, client = route
    with sqlite3.connect(paths.market_db_path) as conn:
        conn.execute("CREATE TABLE prices(value TEXT)")
        if mode == "mismatch":
            conn.execute("CREATE TABLE sec_research_snapshots(secret TEXT)")
        if mode == "partial-uppercase":
            conn.execute("CREATE TABLE SEC_RESEARCH_OBJECTS(secret TEXT)")
    if mode == "corrupt":
        paths.market_db_path.write_bytes(b"not sqlite /private/path")
    before = paths.market_db_path.read_bytes()
    response = client.get("/sec-research/config")
    if mode == "unrelated":
        assert response.status_code == 200
        assert response.json()["capacity"] is None
    else:
        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "sec_research_store_unavailable"}}
    assert paths.market_db_path.read_bytes() == before


@pytest.mark.parametrize("method", ["get", "put"])
def test_config_profile_failure_is_closed_503(route, monkeypatch, method):
    module, _, client = route
    def unavailable():
        raise sqlite3.OperationalError("private /profile/path details")
    monkeypatch.setattr(module, "get_profile_store", unavailable)
    monkeypatch.setattr(module, "require_db_write", lambda *args: None)
    response = (client.get("/sec-research/config") if method == "get" else
                client.put("/sec-research/config", json={"capture_budget_bytes": 1}))
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sec_research_config_unavailable"}}


def test_config_accounting_failure_does_not_become_zero_capacity(route, profile, stored):
    with stored.connect() as conn:
        conn.execute("INSERT INTO sec_research_reservations VALUES('first',9223372036854775807)")
        conn.execute("INSERT INTO sec_research_reservations VALUES('second',1)")
    response = route[2].get("/sec-research/config")
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sec_research_store_unavailable"}}


@pytest.mark.parametrize("suffix", ["", "/filings", "/facts"])
def test_stored_routes_do_not_construct_acquisition_profile_or_capture_owners(route, monkeypatch, suffix):
    module, paths, client = route
    forbid_acquisition(module, monkeypatch)
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("query opened profile"))
    monkeypatch.setattr(module, "CaptureStore", lambda *a, **kw: pytest.fail("query opened captures"))
    response = client.get("/sec-research/320193" + suffix)
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["gaps"] == [{"code": "sec_research_not_installed"}]
    assert not paths.market_db_path.exists()
    assert not paths.capture_root.exists()


@pytest.mark.parametrize("suffix", ["", "/filings", "/facts"])
def test_stored_routes_verify_canonical_schema_without_repair(route, stored, suffix):
    with stored.connect() as conn:
        conn.execute("ALTER TABLE sec_research_facts ADD COLUMN private_column TEXT")
    before = route[1].market_db_path.read_bytes()
    response = route[2].get("/sec-research/320193" + suffix)
    assert response.status_code == 200
    assert response.json() == {"status": "unavailable", "data": None,
        "gaps": [{"code": "sec_research_store_unavailable"}], "observed_at": None,
        "coverage": {}, "next_cursor": None}
    assert route[1].market_db_path.read_bytes() == before


@pytest.mark.parametrize("suffix,params", [
    ("filings", {"limit": "1.0"}), ("filings", {"limit": "0"}),
    ("filings", {"limit": "101"}), ("filings", {"limit": "true"}),
    ("filings", {"include_amendments": "yes"}), ("filings", {"include_amendments": "1"}),
    ("filings", {"filed_from": "2026-02-30"}), ("filings", {"filed_to": "20260101"}),
    ("filings", {"filed_from": "2026-02-01", "filed_to": "2026-01-01"}),
    ("filings", {"forms": ""}), ("facts", {"limit": "1.0"}),
    ("facts", {"limit": "0"}), ("facts", {"limit": "101"}),
    ("facts", {"as_of": "2026-02-30"}), ("facts", {"start": "20260101"}),
    ("facts", {"end": "yesterday"}),
])
def test_query_http_scalar_inputs_are_strict(route, stored, suffix, params):
    assert route[2].get("/sec-research/320193/" + suffix, params=params).status_code == 422


def test_catalog_http_filters_before_pages_and_pins_receipt(route, stored, monkeypatch):
    module, paths, client = route
    receipt = publish_catalog(stored, [(1, "2026-06-01", "8-K"), (2, "2026-05-01", "10-K/A"),
        (3, "2026-04-01", "10-K"), (4, "2026-03-01", "10-Q"), (5, "2026-02-01", "10-K")])
    params = [("forms", "10-K"), ("forms", "10-Q"), ("include_amendments", "false"),
              ("filed_from", "2026-03-01"), ("filed_to", "2026-05-31"), ("limit", "1")]
    response = client.get("/sec-research/CIK:320193/filings", params=params)
    assert response.status_code == 200
    first = response.json()
    assert first["status"] == "ok"
    assert first["data"][0]["accession"] == "0000320193-26-000003"
    assert first["coverage"]["receipt_id"] == receipt["receipt_id"]
    assert first["next_cursor"]
    publish_catalog(stored, [(6, "2026-05-01", "10-K")])
    before = paths.market_db_path.read_bytes()
    forbid_acquisition(module, monkeypatch)
    monkeypatch.setattr(module, "get_profile_store", lambda: pytest.fail("query opened profile"))
    second = client.get("/sec-research/320193/filings", params=params + [("cursor", first["next_cursor"])]).json()
    assert second["data"][0]["accession"] == "0000320193-26-000004"
    assert second["coverage"]["receipt_id"] == first["coverage"]["receipt_id"]
    assert second["next_cursor"] is None
    assert set(second["data"][0]["sources"][0]["source"]) == {"sha256", "pointer"}
    assert paths.market_db_path.read_bytes() == before


@pytest.mark.parametrize("cursor", ["", "!", "e30", "a" * 4097])
def test_catalog_bad_cursor_is_422_not_internal_503(route, stored, cursor):
    response = route[2].get("/sec-research/320193/filings", params={"cursor": cursor})
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "sec_research_cursor_invalid"}}


def test_catalog_cursor_filter_mismatch_is_422(route, stored):
    publish_catalog(stored, [(1, "2026-02-01", "10-K"), (2, "2026-01-01", "10-K")])
    client = route[2]
    first = client.get("/sec-research/320193/filings", params={"limit": 1}).json()
    response = client.get("/sec-research/320193/filings", params={"limit": 2, "cursor": first["next_cursor"]})
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "sec_research_cursor_mismatch"}}


@pytest.mark.parametrize("pending,status", [(False, "empty"), (True, "partial")])
def test_catalog_http_distinguishes_observed_empty_from_partial(route, stored, pending, status):
    publish_catalog(stored, pending=pending)
    response = route[2].get("/sec-research/320193/filings")
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}
    assert result["status"] == status
    assert result["data"] == []
    assert bool(result["gaps"]) is pending


def test_facts_real_service_http_exact_decimal_as_of_and_repeatable_concepts(route, stored, monkeypatch):
    from src.sec_research.queries import StoredQueries
    assert callable(getattr(StoredQueries, "facts", None)), "Task 2 real facts service is not ready"
    snapshot = publish_facts(stored)
    before = route[1].market_db_path.read_bytes()
    forbid_acquisition(route[0], monkeypatch)
    params = [("concepts", "us-gaap:Assets"), ("concepts", "us-gaap:Liabilities"),
              ("as_of", "2026-02-01"), ("period", "instant"), ("end", "2025-12-31"),
              ("revisions", "all"), ("accession", "0000320193-26-000001"), ("limit", "1")]
    first = route[2].get("/sec-research/320193/facts", params=params)
    assert first.status_code == 200
    first = first.json()
    assert first["next_cursor"]
    second = route[2].get("/sec-research/320193/facts", params=params + [("cursor", first["next_cursor"])]).json()
    rows = first["data"] + second["data"]
    assert {row["concept"] for row in rows} == {"Assets", "Liabilities"}
    assets = next(row for row in rows if row["concept"] == "Assets")
    assert assets["value"] == "1234567890123456789.123"
    assert assets["unit"] == "EUR"
    assert assets["source"] == {"sha256": snapshot.sha256, "pointer": "/facts/us-gaap/Assets/units/EUR/0"}
    assert second["next_cursor"] is None
    assert route[1].market_db_path.read_bytes() == before


def test_facts_real_service_http_repeatable_metrics_and_immutable_fact_ids(route, stored):
    from src.sec_research.queries import StoredQueries
    assert callable(getattr(StoredQueries, "facts", None)), "Task 2 real facts service is not ready"
    snapshot = publish_facts(stored)
    response = route[2].get("/sec-research/320193/facts", params=[("metrics", "assets"), ("metrics", "liabilities")])
    assert response.status_code == 200
    assert {row["value"] for row in response.json()["data"]} == {"9", "4"}
    ids = [snapshot.facts[0].fact_id, snapshot.facts[2].fact_id]
    response = route[2].get("/sec-research/320193/facts", params=[("fact_ids", fid) for fid in ids])
    assert response.status_code == 200
    assert {row["fact_id"] for row in response.json()["data"]} == set(ids)
    assert {row["value"] for row in response.json()["data"]} == {"1234567890123456789.123", "4"}


@pytest.mark.parametrize("params", [{"metrics": "unknown"}, {"concepts": "Assets"},
    {"period": "unknown"}, {"revisions": "unknown"}, {"fact_ids": "bad"},
    {"cursor": "!"}, {"accession": "bad"}, {"start": "2026-01-02", "end": "2026-01-01"}])
def test_facts_real_service_http_domain_validation_is_422(route, stored, params):
    from src.sec_research.queries import StoredQueries
    assert callable(getattr(StoredQueries, "facts", None)), "Task 2 real facts service is not ready"
    response = route[2].get("/sec-research/320193/facts", params=params)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] in {"sec_research_query_invalid", "sec_research_cursor_invalid"}


@pytest.mark.parametrize("storage", ["absent", "corrupt", "installed"])
@pytest.mark.parametrize("kind,params,code", [
    ("filings", {}, None),
    ("facts", {}, None),
    ("facts", {"fact_ids": "secfact_" + "0" * 64}, None),
    ("filings", {"forms": ""}, "sec_research_query_invalid"),
    ("filings", [("forms", "10-K"), ("forms", " ")], "sec_research_query_invalid"),
    ("filings", {"filed_from": "2026-02-01", "filed_to": "2026-01-01"}, "sec_research_query_invalid"),
    ("filings", {"limit": "1.0"}, "sec_research_query_invalid"),
    ("facts", {"metrics": "unknown"}, "sec_research_query_invalid"),
    ("facts", {"concepts": "Assets"}, "sec_research_query_invalid"),
    ("facts", {"fact_ids": "bad"}, "sec_research_query_invalid"),
    ("facts", {"fact_ids": "secfact_" + "0" * 64, "metrics": "assets"}, "sec_research_query_invalid"),
    ("facts", {"period": "unknown"}, "sec_research_query_invalid"),
    ("facts", {"revisions": "unknown"}, "sec_research_query_invalid"),
    ("facts", {"start": "2026-02-01", "end": "2026-01-01"}, "sec_research_query_invalid"),
    ("facts", {"accession": "bad"}, "sec_research_query_invalid"),
    ("filings", {"cursor": "!"}, "sec_research_cursor_invalid"),
    ("facts", {"cursor": "!"}, "sec_research_cursor_invalid"),
    ("filings", {"cursor": "e30"}, "sec_research_cursor_invalid"),
    ("facts", {"cursor": "e30"}, "sec_research_cursor_invalid"),
    ("facts", {"fact_ids": "secfact_" + "0" * 64, "cursor": "!"}, "sec_research_cursor_invalid"),
])
def test_query_validation_precedes_storage_availability(route, monkeypatch, storage, kind, params, code):
    module, paths, client = route
    if storage == "corrupt":
        paths.market_db_path.write_bytes(b"not sqlite /private/path")
    elif storage == "installed":
        module.Store(paths).install()
    before = paths.market_db_path.read_bytes() if paths.market_db_path.exists() else None
    forbid_acquisition(module, monkeypatch)

    def forbidden(*args, **kwargs):
        pytest.fail("stored query constructed a forbidden owner")

    monkeypatch.setattr(module, "get_profile_store", forbidden)
    monkeypatch.setattr(module, "CaptureStore", forbidden)
    if code:
        monkeypatch.setattr(module.SecResearchPaths, "resolve", forbidden)
    response = client.get("/sec-research/320193/" + kind, params=params)
    assert response.status_code == (422 if code else 200)
    if code:
        assert response.json() == {"detail": {"code": code}}
    else:
        assert response.json()["status"] == "unavailable"
        if storage != "installed":
            expected = "sec_research_not_installed" if storage == "absent" else "sec_research_store_unavailable"
            assert response.json()["gaps"] == [{"code": expected}]
    assert (paths.market_db_path.read_bytes() if paths.market_db_path.exists() else None) == before
    assert not paths.capture_root.exists()


@pytest.mark.parametrize("storage", ["absent", "corrupt"])
@pytest.mark.parametrize("kind", ["filings", "facts", "fact_ids"])
@pytest.mark.parametrize("changed", [False, True], ids=["bound-request", "changed-limit"])
def test_query_cursor_request_validation_before_unavailable_store(
    route, tmp_path, monkeypatch, storage, kind, changed,
):
    from src.sec_research.queries import StoredQueries
    module, paths, client = route
    seed = module.Store(module.SecResearchPaths.from_market_db(tmp_path / "seed" / "market.db"))
    seed.install()
    params = {"limit": 1}
    endpoint = "facts" if kind == "fact_ids" else kind
    if kind == "filings":
        publish_catalog(seed, [(1, "2026-02-01", "10-K"), (2, "2026-01-01", "10-K")])
    else:
        snapshot = publish_facts(seed)
        if kind == "fact_ids":
            params["fact_ids"] = [row.fact_id for row in snapshot.facts]
    cursor = getattr(StoredQueries(seed), endpoint)(CIK, **params)["next_cursor"]
    assert cursor
    if storage == "corrupt":
        paths.market_db_path.write_bytes(b"not sqlite /private/path")
    before = paths.market_db_path.read_bytes() if paths.market_db_path.exists() else None
    forbid_acquisition(module, monkeypatch)
    response = client.get("/sec-research/320193/" + endpoint,
                          params={**params, "cursor": cursor, "limit": 2 if changed else 1})
    if changed:
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "sec_research_cursor_mismatch"}}
    else:
        assert response.status_code == 200
        assert response.json()["status"] == "unavailable"
        expected = "sec_research_not_installed" if storage == "absent" else "sec_research_store_unavailable"
        assert response.json()["gaps"] == [{"code": expected}]
    assert (paths.market_db_path.read_bytes() if paths.market_db_path.exists() else None) == before
    assert not paths.capture_root.exists()
