"""Daily SEC acquisition against real disposable stores and injected source bytes."""

import importlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.active_universe import ActiveUniverseUnavailable
from src.sec_research.captures import CaptureStore
from src.sec_research.issuer_store import IssuerStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.service import ResearchService
from src.sec_research.store import Store
from tests.test_sec_research_service import Transport, NOW
from tests.test_sec_research_issuers import MAP_URL, map_body


def owner(name="scheduled"):
    assert importlib.util.find_spec("src.sec_research." + name), "SEC schedule owner missing"
    return importlib.import_module("src.sec_research." + name)


@pytest.fixture
def schedule_fixture(tmp_path):
    store = Store(SecResearchPaths.from_market_db(tmp_path / "market.db"))
    store.install()
    captures = CaptureStore(store, budget=lambda: 1024**3, free_bytes=lambda _: 1024**4)
    transport = Transport()
    f = SimpleNamespace(store=store, captures=captures, transport=transport,
                        members=[], time=0.0, now=NOW)
    f.service = ResearchService(store, captures, transport, clock=lambda: f.now)

    def run(**limits):
        def universe():
            if isinstance(f.members, BaseException):
                raise f.members
            return list(f.members)
        return owner().run_current_universe(universe_reader=universe,
            issuer_resolver=IssuerStore(store), service=f.service,
            limits=owner().Limits(**limits), clock=lambda: f.time)
    f.run = run
    f.status = lambda: owner("schedule_store").ScheduleStore(Store(store.paths)).status()
    return f


def test_empty_universe_success_is_not_acquisition(schedule_fixture):
    f = schedule_fixture
    result = f.run()
    assert result["status"] == "succeeded"
    assert result["request_count"] == 0
    assert result["attempted_ciks"] == result["confirmed_ciks"] == []
    state = f.status()
    assert state["last_attempt"]["batch_id"] == result["batch_id"]
    assert state["last_acquisition_at"] is None
    assert state["last_completed_batch"]["batch_id"] == result["batch_id"]
    assert f.transport.calls == []


def test_unavailable_universe_never_dispatches(schedule_fixture):
    f = schedule_fixture
    f.members = ActiveUniverseUnavailable("fixture unavailable")
    result = f.run()
    assert result["status"] == "failed"
    assert result["gaps"] == [{"code": "active_universe_unavailable"}]
    assert f.status()["last_attempt"] == result
    assert f.status()["last_acquisition_at"] is None
    assert f.transport.calls == []


@pytest.mark.parametrize("overrides", [dict(max_issuers=501), dict(max_requests=1002),
    dict(wall_seconds=901), dict(max_issuers=True), dict(max_requests=0), dict(wall_seconds=float("nan"))])
def test_limits_are_closed_application_safety_bounds(overrides):
    assert vars(owner().Limits()) == dict(max_issuers=500, max_requests=1001, wall_seconds=900)
    with pytest.raises(ValueError, match="sec_schedule_limits_invalid"):
        owner().Limits(**overrides)


def test_deadline_during_real_transport_body_unwinds_without_claiming_http_success(schedule_fixture, tmp_path):
    from data_sources.sec_transport import SecTransport
    from tests.test_sec_research_service import WireSession, WireResponse
    f = schedule_fixture
    f.members = ["CIK:1", "CIK:2"]
    sources(f, 1, 2)

    class ExpiringBody(WireResponse):
        def iter_content(self, chunk_size):
            f.time = 15
            yield self.body

    session = WireSession({url: ExpiringBody(body) for url, body in f.transport.responses.items()})
    transport = SecTransport(user_agent="ArkScope offline@example.test", session=session,
                             max_rate_limit_retries=0, lock_dir=tmp_path / "governor")
    f.service.transport = transport
    try:
        result = f.run(wall_seconds=15)
    finally:
        transport.close()
    assert result["status"] == "failed" and result["stop_reason"] == "deadline"
    assert result["request_count"] == len(session.calls) == 1
    assert result["confirmed_ciks"] == [] and result["deferred_ciks"] == ["0000000002"]
    assert result["outcomes"][0]["completed_sources"] == 0
    assert result["gaps"][0]["code"] == "sec_request_cancelled"
    assert session.responses[session.calls[0][0]].closed


def sources(f, *ciks):
    for cik in ciks:
        cik = str(cik).zfill(10)
        forms = ["10-K", "10-Q/A", "20-F", "40-F/A", "8-K"]
        f.transport.responses[f"https://data.sec.gov/submissions/CIK{cik}.json"] = json.dumps({
            "cik": int(cik), "filings": {"recent": {
                "accessionNumber": [f"{cik}-26-{n:06}" for n in range(1, 6)],
                "filingDate": ["2026-01-01"] * 5, "form": forms},
                "files": [{"name": f"CIK{cik}-submissions-001.json"}]}}).encode()
        f.transport.responses[f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"] = json.dumps({
            "cik": int(cik), "facts": {"us-gaap": {"Assets": {"units": {"USD": [
                {"val": n, "end": "2025-12-31", "form": form,
                 "accn": f"{cik}-26-{n:06}", "filed": "2026-01-01"}
                for n, form in enumerate(forms, 1)]}}}}}).encode()


def test_schedule_deduplicates_cik_and_exposes_unresolved_symbols(schedule_fixture):
    f = schedule_fixture
    f.members = ["ONE", "ALIAS", "MISSING", "AMBIG", "CIK:1"]
    f.transport.responses[MAP_URL] = map_body(("ONE", 1), ("ALIAS", 1), ("AMBIG", 2), ("AMBIG", 3))
    sources(f, 1)
    f.transport.responses["https://data.sec.gov/submissions/CIK0000000001-submissions-001.json"] = json.dumps({
        "accessionNumber": ["0000000001-25-000001"], "filingDate": ["2025-01-01"], "form": ["10-K"]}).encode()
    result = f.run()
    assert [url for url, _ in f.transport.calls] == [MAP_URL,
        "https://data.sec.gov/submissions/CIK0000000001.json",
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"]
    assert result["status"] == "partial"
    assert result["attempted_ciks"] == result["confirmed_ciks"] == ["0000000001"]
    assert [(r["ticker"], r["code"]) for r in result["unresolved"]] == [
        ("AMBIG", "issuer_ambiguous"), ("MISSING", "issuer_not_found")]
    assert result["request_count"] == len(f.transport.calls) == 3
    assert result["filing_count"] == result["fact_count"] == 4
    assert result["issuer_map_observation_id"] == IssuerStore(f.store).latest()["observation_id"]
    assert f.status()["last_acquisition_at"] == NOW
    assert f.status()["last_completed_batch"] is None
    assert all("submissions-001" not in url for url, _ in f.transport.calls)


def test_space_symbol_is_unresolved_without_rejecting_observed_membership(schedule_fixture):
    from src.sec_research.common import SourceError
    from src.sec_research.issuers import parse_issuer
    from src.sec_research.operations import _verify_database

    f = schedule_fixture
    f.members = ["ONE", "BRK B"]
    f.transport.responses[MAP_URL] = map_body(("ONE", 1), ("TWO", 2), ("BRK.B", 3))
    sources(f, 1, 2, 3)
    first = f.run(max_issuers=1)
    assert first["universe_status"] == "available"
    assert first["universe_tickers"] == ["BRK B", "ONE"]
    assert first["status"] == "partial"
    assert first["confirmed_ciks"] == first["attempted_ciks"] == ["0000000001"]
    assert first["unresolved"] == [{"ticker": "BRK B", "candidates": [], "code": "sec_issuer_invalid"}]
    assert first["rotation"] == [{"cik": "0000000001", "tickers": ["ONE"]}]
    assert f.status()["last_attempt"] == first
    assert f.status()["last_acquisition_at"] == NOW
    assert _verify_database(f.store)["schedule_batches"] > 0
    with pytest.raises(SourceError, match="sec_issuer_invalid"):
        parse_issuer("BRK B")
    f.members = ["BRK B", "TWO"]
    second = f.run(max_issuers=1)
    assert second["confirmed_ciks"] == ["0000000002"]
    assert second["rotation"] == [{"cik": "0000000002", "tickers": ["TWO"]}]
    assert second["unresolved"] == first["unresolved"]
    assert f.status()["last_attempt"] == second
    assert [url for url, _ in f.transport.calls] == [url for cik in (1, 2) for url in (
        MAP_URL, f"https://data.sec.gov/submissions/CIK{cik:010}.json",
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010}.json")]


@pytest.mark.parametrize("member", [None, "", "ONE\nTWO", "X" * 257])
def test_malformed_observed_member_stops_whole_batch_without_dispatch(schedule_fixture, member):
    f = schedule_fixture
    f.members = ["ONE", member]
    result = f.run()
    assert result["status"] == "failed" and result["universe_status"] == "unavailable"
    assert result["gaps"] == [{"code": "active_universe_unavailable"}]
    assert result["universe_tickers"] == [] and result["attempted_ciks"] == []
    assert f.status()["last_attempt"] == result
    assert f.transport.calls == []


def test_batch_bounds_defer_without_starving_current_members(schedule_fixture):
    f = schedule_fixture
    f.members = ["CIK:1", "CIK:2", "CIK:3"]
    sources(f, 1, 2, 3, 4)
    first = f.run(max_issuers=1)
    assert first["status"] == "partial"
    assert first["deferred_ciks"] == ["0000000002", "0000000003"]
    f.members = ["CIK:1", "CIK:3", "CIK:4"]
    second = f.run(max_issuers=1)
    third = f.run(max_issuers=1)
    fourth = f.run(max_issuers=1)
    assert [r["attempted_ciks"] for r in (first, second, third, fourth)] == [
        ["0000000001"], ["0000000003"], ["0000000001"], ["0000000004"]]
    assert all("0000000002" not in url for url, _ in f.transport.calls)
    assert all(r["request_count"] == 2 for r in (first, second, third, fourth))


def test_sec_partial_failure_retains_previous_success(schedule_fixture):
    f = schedule_fixture
    sources(f, 1, 2)
    f.members = ["CIK:1"]
    first = f.run()
    assert first["status"] == "succeeded"
    f.now = "2026-09-12T12:00:00Z"
    f.members = ["CIK:2"]
    f.transport.responses["https://data.sec.gov/api/xbrl/companyfacts/CIK0000000002.json"] = RuntimeError("PRIVATE")
    second = f.run()
    assert second["status"] == "partial"
    assert second["confirmed_ciks"] == []
    assert second["failed_ciks"] == ["0000000002"]
    assert second["filing_count"] == 4 and second["fact_count"] == 0
    assert f.status()["last_acquisition_at"] == NOW
    assert f.status()["last_completed_batch"] == first
    f.transport.responses["https://data.sec.gov/submissions/CIK0000000002.json"] = RuntimeError("PRIVATE")
    third = f.run()
    assert third["status"] == "failed"
    assert f.status()["last_acquisition_at"] == NOW
    assert len(f.store.catalog("1")) == 5
    assert "PRIVATE" not in json.dumps(f.status())


def test_deadline_and_request_budget_checked_before_each_source(schedule_fixture):
    f = schedule_fixture
    sources(f, 1)
    f.members = ["CIK:1"]
    first = f.run(max_requests=1)
    assert first["status"] == "partial"
    assert first["request_count"] == 1
    assert first["stop_reason"] == "request_limit"
    assert first["outcomes"][0]["receipt_id"] == f.store.latest_receipt("1")["receipt_id"]
    f.transport.calls.clear()
    f.transport.before = lambda _: setattr(f, "time", 2.0)
    second = f.run(wall_seconds=1)
    assert second["request_count"] == len(f.transport.calls) == 1
    assert second["stop_reason"] == "deadline"
    assert second["status"] == "partial"


def test_unavailable_membership_preserves_rotation_and_empty_clears_without_acquisition(schedule_fixture):
    f = schedule_fixture
    sources(f, 1, 2)
    f.members = ["CIK:1", "CIK:2"]
    prior = f.run(max_issuers=1)
    assert prior["deferred_ciks"] == ["0000000002"]
    f.members = ActiveUniverseUnavailable("offline")
    failed = f.run()
    assert failed["rotation"] == prior["rotation"]
    f.members = []
    f.now = "2026-09-12T12:00:00Z"
    empty = f.run()
    assert empty["status"] == "succeeded" and empty["rotation"] == []
    assert f.status()["last_acquisition_at"] == NOW


def test_interrupted_batch_persists_intent_and_rotates_failed_member(schedule_fixture):
    f = schedule_fixture
    sources(f, 1, 2)
    f.members = ["CIK:1", "CIK:2"]
    f.transport.responses["https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"] = SystemExit("fixture crash")
    with pytest.raises(SystemExit):
        f.run(max_issuers=1)
    interrupted = f.status()["last_attempt"]
    assert interrupted["status"] == "running"
    assert interrupted["attempted_ciks"] == ["0000000001"]
    assert interrupted["request_count"] == 2
    second = f.run(max_issuers=1)
    assert second["attempted_ciks"] == ["0000000002"]


@pytest.mark.parametrize("mutation", ["receipt", "cik", "scope", "count", "map", "rotation", "extra", "status",
    "map_overflow", "unreported_attempt", "unknown_success"])
def test_batch_shape_and_hidden_receipt_references_are_validated(schedule_fixture, mutation):
    from src.sec_research.operations import _verify_database

    f = schedule_fixture
    sources(f, 1)
    f.members = ["CIK:1"]
    batch = deepcopy(f.run())
    if mutation == "receipt":
        batch["outcomes"][0]["receipt_id"] = 999999
    elif mutation == "cik":
        batch["outcomes"][0]["cik"] = "0000000002"
    elif mutation == "scope":
        batch["scope"] = "full"
    elif mutation == "count":
        batch["fact_count"] = 900
    elif mutation == "map":
        batch["issuer_map_observation_id"] = 999999
    elif mutation == "map_overflow":
        batch["issuer_map_observation_id"] = 2**100
    elif mutation == "unreported_attempt":
        batch.update(outcomes=[], confirmed_ciks=[], acquired_at=None, filing_count=0, fact_count=0)
    elif mutation == "unknown_success":
        batch["universe_status"] = "unknown"
    elif mutation == "rotation":
        batch["rotation"][0]["tickers"] = ["REMOVED"]
    elif mutation == "status":
        batch["status"] = "failed"
    else:
        batch["extra"] = "PRIVATE"
    with f.store._write() as conn:
        conn.execute("""INSERT INTO sec_research_schedule_batches
            (batch_id,status,acquired_at,payload) VALUES (?,?,?,?)""",
            (batch["batch_id"], batch["status"], batch["acquired_at"], json.dumps(batch)))
    with pytest.raises(ValueError, match="sec_schedule_batch_invalid"):
        f.status()
    with pytest.raises(ValueError, match="sec_schedule_batch_invalid"):
        _verify_database(f.store)


def test_schedule_export_and_admin_verify_all_checkpoints(schedule_fixture, tmp_path):
    from src.sec_research.operations import _verify_database, export_bundle, restore_bundle

    f = schedule_fixture
    sources(f, 1, 2)
    f.members = ["CIK:1", "CIK:2"]
    f.run(max_issuers=1)
    counts = _verify_database(f.store)
    assert counts.get("schedule_batches", 0) >= 5, "batch checkpoints omitted from export/admin verification"
    bundle = tmp_path / "bundle"
    manifest = export_bundle(f.store.paths, bundle)
    assert manifest["references"] == counts
    destination = tmp_path / "restored"
    restore_bundle(bundle, destination)
    restored = Store(SecResearchPaths.from_market_db(destination / "market_data.db"))
    assert owner("schedule_store").ScheduleStore(restored).status() == f.status()
    assert _verify_database(restored) == counts


def test_changed_ticker_membership_intersects_before_map_checkpoint(schedule_fixture):
    f = schedule_fixture
    sources(f, 1, 2, 3)
    f.transport.responses[MAP_URL] = map_body(("ONE", 1), ("TWO", 2), ("THREE", 3))
    f.members = ["ONE", "TWO"]
    f.run(max_issuers=1)
    f.members = ["THREE"]
    f.transport.calls.clear()
    try:
        result = f.run()
    except ValueError:
        result = None
    assert result is not None, "removed membership invalidated the next map checkpoint"
    assert result["confirmed_ciks"] == ["0000000003"]
    assert len(f.transport.calls) == 3


def test_busy_issuer_is_failed_without_abandoning_other_issuers(schedule_fixture):
    from src.sec_research.capture_lock import issuer_refresh

    f = schedule_fixture
    sources(f, 1, 2)
    f.members = ["CIK:1", "CIK:2"]
    with issuer_refresh(f.store.paths.capture_root, "1"):
        result = f.run()
    assert result["confirmed_ciks"] == ["0000000002"]
    assert result["failed_ciks"] == ["0000000001"]
    assert result["status"] == "partial"
    assert result["outcomes"][0]["receipt_id"] is None
    assert {gap["code"] for gap in result["gaps"]} == {"sec_research_refresh_busy"}


def test_failed_map_preserves_rotation_without_dispatching_stale_resolution(schedule_fixture):
    f = schedule_fixture
    sources(f, 1, 2)
    f.transport.responses[MAP_URL] = map_body(("ONE", 1), ("TWO", 2))
    f.members = ["ONE", "TWO"]
    first = f.run(max_issuers=1)
    f.transport.responses[MAP_URL] = RuntimeError("offline")
    failed = f.run(max_issuers=1)
    assert failed["request_count"] == 1 and failed["attempted_ciks"] == []
    assert failed["rotation"] == first["rotation"]
    f.transport.responses[MAP_URL] = map_body(("ONE", 1), ("TWO", 2))
    assert f.run(max_issuers=1)["attempted_ciks"] == ["0000000002"]


def test_status_rejects_inconsistent_batch_column_timestamp(schedule_fixture):
    f = schedule_fixture
    result = f.run()
    with f.store._write() as conn:
        conn.execute("""INSERT INTO sec_research_schedule_batches
            (batch_id,status,acquired_at,payload) VALUES (?,?,?,?)""",
            (result["batch_id"], result["status"], "2026-09-20T00:00:00Z", json.dumps(result)))
    with pytest.raises(ValueError, match="sec_schedule_batch_invalid"):
        f.status()
