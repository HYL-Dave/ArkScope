"""Actual scheduler/runtime/API contracts over temporary universe and SEC stores."""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from tests.test_active_universe import databases
from tests.test_data_scheduler import hermetic
from tests.test_sec_research_schedule import schedule_fixture, sources, owner
from tests.test_sec_research_service import WireSession, WireResponse
from tests.test_sec_research_issuers import MAP_URL, map_body


@pytest.fixture
def runtime(schedule_fixture, databases, monkeypatch, tmp_path):
    from data_sources.sec_transport import SecTransport
    from src.sec_research.paths import SecResearchPaths
    from src.service.job_runs_store import JobRunsLocalStore
    from tests.test_data_scheduler import _REAL_JOB_RUNS_LOCAL_STORE
    from src.api.routes import sec_research, schedule

    f = schedule_fixture
    f.profile = databases.profile
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(databases.profile_path))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(databases.sa_path))
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: f.store.paths)
    monkeypatch.setattr("src.api.dependencies.get_profile_store", lambda: f.profile)
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: SimpleNamespace(
        get_all=lambda: {"sec_edgar": {"user_agent": "ArkScope offline@example.test"}}))
    sources(f, 1, 2)
    f.transport.responses[MAP_URL] = map_body(("ONE", 1), ("TWO", 2))
    session = WireSession({url: WireResponse(body) for url, body in f.transport.responses.items()})
    f.wire = session
    f.constructed = []
    def transport(**kwargs):
        assert kwargs["max_rate_limit_retries"] == 0
        f.constructed.append(kwargs)
        return SecTransport(**kwargs, session=session, lock_dir=tmp_path / "governor")
    monkeypatch.setattr("data_sources.sec_transport.SecTransport", transport)
    import src.service.data_scheduler as ds
    monkeypatch.setattr(ds, "_store", lambda: f.profile)
    monkeypatch.setattr("src.service.job_runs_store.JobRunsLocalStore", _REAL_JOB_RUNS_LOCAL_STORE)
    f.jobs = _REAL_JOB_RUNS_LOCAL_STORE(databases.profile_path)
    f.ds = ds
    app = FastAPI()
    app.include_router(sec_research.router)
    app.include_router(schedule.router)
    f.client = TestClient(app)
    f.add = lambda: f.profile.import_lists([{"name": "Fixture", "tickers": ["ONE", "TWO"]}])
    return f


def test_runtime_empty_universe_needs_no_credentials_or_transport(runtime, monkeypatch):
    f = runtime
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: pytest.fail("empty universe opened credentials"))
    assert hasattr(owner(), "run_incremental"), "runtime adapter missing"
    result = owner().run_incremental()
    assert result["status"] == "succeeded" and result["request_count"] == 0
    assert f.constructed == [] and f.status()["last_acquisition_at"] is None


def test_actual_space_symbol_membership_keeps_other_issuer_and_stored_status(runtime):
    from src.universe_scope import resolve_active_universe

    f = runtime
    f.profile.import_lists([{"name": "Fixture", "tickers": ["ONE", "BRK B", "BRK.B"]}])
    f.profile.set_universe_hidden("BRK.B", True)
    assert resolve_active_universe() == ["BRK B", "ONE"]
    result = owner().run_incremental()
    assert result["status"] == "partial"
    assert result["universe_status"] == "available"
    assert result["universe_tickers"] == ["BRK B", "ONE"]
    assert result["confirmed_ciks"] == ["0000000001"]
    assert result["unresolved"] == [{"ticker": "BRK B", "candidates": [], "code": "sec_issuer_invalid"}]
    calls = list(f.wire.calls)
    before = f.store.paths.market_db_path.read_bytes()
    response = f.client.get("/sec-research/schedule-status")
    assert response.status_code == 200 and response.json()["status"] == "partial"
    assert response.json()["data"] == f.status()
    assert response.json()["data"]["last_attempt"] == result
    assert f.store.paths.market_db_path.read_bytes() == before
    assert f.wire.calls == calls and len(calls) == 3


def test_only_sec_invalid_symbol_needs_no_credentials_or_transport(runtime, monkeypatch):
    f = runtime
    f.profile.import_lists([{"name": "Fixture", "tickers": ["BRK B"]}])
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: pytest.fail("invalid symbol opened credentials"))
    result = owner().run_incremental()
    assert result["universe_status"] == "available" and result["status"] == "failed"
    assert result["unresolved"] == [{"ticker": "BRK B", "candidates": [], "code": "sec_issuer_invalid"}]
    assert result["request_count"] == 0 and result["gaps"] == []
    assert f.constructed == [] and f.wire.calls == []
    assert f.status()["last_attempt"] == result


@pytest.mark.parametrize("failure,expected", [(None, "succeeded"), ("facts", "partial"), ("all", "failed")])
def test_actual_sec_scheduler_adapter_maps_outcomes_and_audit(runtime, failure, expected):
    f = runtime
    f.add()
    if failure:
        for url, response in f.wire.responses.items():
            if failure == "all" or "/companyfacts/" in url:
                response.status_code = 503
    assert hasattr(owner(), "run_incremental"), "runtime adapter missing"
    result = f.ds.run_source("sec_research_filings", "manual")
    assert result["status"] == expected, result
    assert result["collect"]["status"] == expected
    assert f.ds._state_store().all()["sec_research_filings"]["last_status"] == expected
    rows = f.jobs.list_runs(limit=10)
    assert len(rows) == 1
    assert rows[0]["status"] == ("succeeded" if expected == "succeeded" else "failed")
    if expected == "partial":
        assert rows[0]["error"] == "sec_schedule_partial"
    assert len(f.wire.calls) == (1 if failure == "all" else 5)


@pytest.mark.parametrize("payload", [None, {}, {"status": "unavailable"}, {"status": "succeeded"}, {"status": "failed"}])
def test_malformed_sec_adapter_result_never_becomes_success(runtime, monkeypatch, payload):
    f = runtime
    monkeypatch.setattr(owner(), "run_incremental", lambda **_: payload, raising=False)
    result = f.ds.run_source("sec_research_filings", "manual")
    assert result["status"] == "failed"
    assert result["error"] == "sec_schedule_result_invalid"


def test_schedule_status_is_stored_only_and_precedes_dynamic_cik(runtime, monkeypatch):
    f = runtime
    monkeypatch.setattr("src.api.routes.sec_research.get_profile_store", lambda: pytest.fail("status opened config"))
    response = f.client.get("/sec-research/schedule-status")
    assert response.status_code == 200, "stored schedule-status route missing"
    assert response.json()["data"]["last_attempt"] is None
    assert f.constructed == [] and f.wire.calls == []
    f.run()
    before = f.store.paths.market_db_path.read_bytes()
    result = f.client.get("/sec-research/schedule-status").json()
    assert result["data"] == f.status()
    assert f.store.paths.market_db_path.read_bytes() == before


def test_budget_edit_never_enables_schedule(runtime, monkeypatch):
    f = runtime
    monkeypatch.setattr("src.api.routes.sec_research.get_profile_store", lambda: f.profile)
    before = f.ds.source_config("sec_research_filings")
    response = f.client.put("/sec-research/config", json={"capture_budget_bytes": 2048})
    assert response.status_code == 200
    assert f.ds.source_config("sec_research_filings") == before
    assert f.wire.calls == [] and f.status()["last_attempt"] is None


def test_schedule_commands_keep_actual_permission_gate(runtime, monkeypatch):
    f = runtime
    def deny(*args, **kwargs):
        raise HTTPException(403, "fixture denied")
    monkeypatch.setattr("src.api.routes.schedule.require_db_write", deny)
    monkeypatch.setattr("src.api.routes.schedule.require_profile_state_write", deny)
    assert f.client.put("/schedule/sec_research_filings", json={"enabled": True}).status_code == 403
    assert f.client.post("/schedule/run/sec_research_filings").status_code == 403
    assert f.wire.calls == []


def test_missing_managed_identity_has_typed_failed_batch_without_old_key(runtime, monkeypatch):
    f = runtime
    f.add()
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "Old old@example.test")
    monkeypatch.setattr("src.api.dependencies.get_data_provider_store", lambda: SimpleNamespace(get_all=lambda: {}))
    result = owner().run_incremental()
    assert result["status"] == "failed"
    assert {row["code"] for row in result["unresolved"]} == {"sec_identity_unconfigured"}
    assert result["request_count"] == 0 and f.constructed == [] and f.wire.calls == []


def test_schedule_keeps_per_response_bound_without_twelve_mib_batch_ceiling(runtime):
    f = runtime
    f.add()
    for response in f.wire.responses.values():
        response.body += b" " * (4 * 1024**2)
    result = owner().run_incremental()
    assert result["status"] == "succeeded"
    assert result["request_count"] == len(f.wire.calls) == 5
    assert sum(len(response.body) for response in f.wire.responses.values()) > 12 * 1024**2
    assert result["filing_count"] == result["fact_count"] == 8


def test_schedule_sixteen_mib_response_rejection_and_no_rate_limit_retry(runtime):
    f = runtime
    f.add()
    submissions = "https://data.sec.gov/submissions/CIK0000000001.json"
    facts = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
    f.wire.responses[submissions].headers["Content-Length"] = str(16 * 1024**2 + 1)
    f.wire.responses[facts].status_code = 429
    result = owner().run_incremental()
    assert result["status"] == "partial"
    assert result["confirmed_ciks"] == ["0000000002"]
    assert result["failed_ciks"] == ["0000000001"]
    assert result["request_count"] == len(f.wire.calls) == 5
    assert {gap["code"] for gap in result["gaps"]} == {"sec_response_too_large", "sec_rate_limited"}
    assert f.wire.responses[submissions].closed and f.wire.responses[facts].closed


@pytest.mark.parametrize("invalid", [False, True])
def test_absent_or_invalid_schedule_status_does_not_install(runtime, monkeypatch, tmp_path, invalid):
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store
    paths = SecResearchPaths.from_market_db(tmp_path / "read-only-status.db")
    monkeypatch.setattr(SecResearchPaths, "resolve", lambda: paths)
    monkeypatch.setattr(Store, "install", lambda _: pytest.fail("status installed schema"))
    if invalid:
        paths.market_db_path.write_bytes(b"invalid fixture database")
    before = set(tmp_path.rglob("*"))
    database_bytes = {path: path.read_bytes() for path in before if path.suffix == ".db"}
    result = runtime.client.get("/sec-research/schedule-status")
    assert result.status_code == 200 and result.json()["status"] == "unavailable"
    assert result.json()["gaps"] == [{"code": "sec_schedule_store_unavailable" if invalid else "sec_schedule_unobserved"}]
    assert result.json()["data"] is None if invalid else result.json()["data"]["last_attempt"] is None
    created = set(tmp_path.rglob("*")) - before
    assert len(created) == 1
    lock = created.pop()
    assert lock.parent == tmp_path / "locks" and lock.name.startswith("sec-research-") and lock.name.endswith(".operation.lock")
    assert database_bytes == {path: path.read_bytes() for path in tmp_path.rglob("*.db")}
    assert not paths.capture_root.exists()
    assert runtime.constructed == [] and runtime.wire.calls == []
