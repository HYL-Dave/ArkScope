"""Tool orchestration contracts using real stores, queries and acquisition owners."""

from contextlib import contextmanager
import importlib
import inspect
import json
from types import SimpleNamespace

import pytest

from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.service import ResearchService
from src.sec_research.store import Store
from tests.test_sec_research_issuers import MAP_URL, Transport, map_body, owner
from tests.test_sec_research_document_service import rig as document_rig, FILING_ID, bind_catalog


CIK = "0000320193"
NOW = "2026-09-12T12:00:00Z"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK0000320193.json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
EXACT = b'{"cik":320193,"facts":{"us-gaap":{"Assets":{"units":{"USD":[{"val":1234567890123456789.123,"end":"2025-12-31","form":"10-K","accn":"0000320193-26-000001","filed":"2026-01-30"}]}}}}}'


def catalog(history=0):
    return json.dumps({"cik": 320193, "filings": {"recent": {
        "accessionNumber": ["0000950170-26-000001", "0000950170-26-000002"],
        "filingDate": ["2026-05-01", "2026-05-02"], "form": ["10-K", "10-Q"],
        "primaryDocument": ["actual.htm", "actual.htm"]}, "files": [
            {"name": f"CIK{CIK}-submissions-{i:03}.json"} for i in range(history)]}}).encode()


@pytest.fixture
def tool_fixture(tmp_path):
    service_type = owner("tool_service").ToolService
    store = Store(SecResearchPaths(tmp_path / "market.db"))
    store.install()
    captures = CaptureStore(store, budget=lambda: 1024**3, free_bytes=lambda _: 1024**4)
    transport = Transport({MAP_URL: map_body(("AAPL", 320193)), SUBMISSIONS: catalog(), FACTS: EXACT})
    f = SimpleNamespace(store=store, captures=captures, transport=transport, acquisitions=[],
                        closes=[], now=NOW)
    @contextmanager
    def acquire():
        f.acquisitions.append(True)
        try:
            yield captures, transport, None
        finally:
            f.closes.append(True)
    f.service = service_type(store, acquisition_factory=acquire, clock=lambda: f.now)
    return f


def seed(f):
    ResearchService(f.store, f.captures, f.transport, clock=lambda: NOW).refresh(CIK)
    f.transport.calls.clear()


def test_stored_and_pinned_calls_never_open_acquisition(tmp_path):
    f = tool_fixture.__wrapped__(tmp_path)
    seed(f)
    f.now = "2026-09-15T12:00:00Z"
    result = f.service.invoke("get_sec_financial_facts", dict(issuer=CIK, freshness="stored"))
    assert result["data"][0]["value"] == "1234567890123456789.123"
    pinned = f.service.invoke("get_sec_financial_facts", dict(issuer=CIK, fact_ids=[result["data"][0]["fact_id"]]))
    assert pinned["data"][0]["value"] == "1234567890123456789.123"
    assert f.acquisitions == [] and f.transport.calls == []


@pytest.mark.parametrize("args", [dict(issuer="AAPL", limit=True), dict(issuer="AAPL", cursor="!"),
    dict(issuer="AAPL", filed_from="bad"), dict(issuer="AAPL", freshness="typo"),
    dict(issuer="AAPL", unknown=True), dict(issuer="AAPL", forms=12)])
def test_invalid_query_rejected_before_resolution(tool_fixture, monkeypatch, args):
    f = tool_fixture
    def forbidden(*args, **kwargs):
        pytest.fail("invalid query reached resolution or storage")
    monkeypatch.setattr(owner("issuer_store").IssuerStore, "resolve", forbidden)
    monkeypatch.setattr(f.store, "connect", forbidden)
    result = f.service.invoke("list_sec_filings", args)
    assert result["status"] == "unavailable"
    assert result["gaps"][0]["code"] in {"sec_research_query_invalid", "sec_research_cursor_invalid"}
    assert f.acquisitions == []


def test_cursor_survives_ticker_map_change(tool_fixture):
    f = tool_fixture
    first = f.service.invoke("list_sec_filings", dict(issuer="AAPL", limit=1))
    assert first["next_cursor"]
    f.transport.responses[MAP_URL] = map_body(("AAPL", 1))
    owner("issuer_store").IssuerStore(f.store).refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    f.transport.calls.clear()
    f.acquisitions.clear()
    second = f.service.invoke("list_sec_filings", dict(issuer="AAPL", limit=1, cursor=first["next_cursor"]))
    assert second["data"][0]["cik"] == CIK
    assert second["data"][0]["filing_id"] != first["data"][0]["filing_id"]
    assert f.acquisitions == [] and f.transport.calls == []


def test_failed_refresh_does_not_borrow_old_success(tool_fixture):
    f = tool_fixture
    seed(f)
    f.transport.responses[FACTS] = RuntimeError("PRIVATE provider secret")
    result = f.service.invoke("get_sec_financial_facts", dict(issuer=CIK, freshness="refresh"))
    assert result["status"] == "unavailable" and result["data"] == []
    assert len(f.transport.calls) == 2 and "PRIVATE" not in json.dumps(result)


def test_one_map_plus_bounded_metadata_requests(tool_fixture):
    f = tool_fixture
    f.transport.responses[SUBMISSIONS] = catalog(history=8)
    for i in range(8):
        f.transport.responses[f"https://data.sec.gov/submissions/CIK{CIK}-submissions-{i:03}.json"] = b'{"accessionNumber":[],"filingDate":[],"form":[]}'
    result = f.service.invoke("list_sec_filings", dict(issuer="AAPL"))
    assert result["status"] == "partial" and len(result["data"]) == 2
    assert f.transport.calls[0] == MAP_URL and len(f.transport.calls) == 5
    assert len(f.store.latest_receipt(CIK)["pending"]) == 6
    assert f.acquisitions == f.closes == [True]


def test_auto_resumes_partial_without_retrying_in_same_call(tool_fixture):
    f = tool_fixture
    f.transport.responses[FACTS] = RuntimeError("fixture failure")
    first = f.service.invoke("get_sec_financial_facts", dict(issuer=CIK))
    assert first["status"] == "unavailable" and f.transport.calls == [SUBMISSIONS, FACTS]
    f.transport.responses[FACTS] = EXACT
    second = f.service.invoke("get_sec_financial_facts", dict(issuer=CIK))
    assert second["data"][0]["value"] == "1234567890123456789.123"
    assert f.transport.calls == [SUBMISSIONS, FACTS, FACTS]


def test_document_pin_rejects_refresh_before_io(tool_fixture, monkeypatch):
    f = tool_fixture
    def forbidden(*args, **kwargs):
        pytest.fail("pin refresh reached storage")
    monkeypatch.setattr(f.store, "connect", forbidden)
    result = f.service.invoke("read_sec_filing", dict(filing_id=FILING_ID,
        capture_id="secdoc_" + "a" * 64, freshness="refresh"))
    assert result["status"] == "unavailable"
    assert result["gaps"] == [{"code": "sec_research_query_invalid"}]
    assert f.acquisitions == []


def test_cancel_stops_before_next_source(tool_fixture):
    f = tool_fixture
    def check():
        if f.transport.calls:
            raise RuntimeError("PRIVATE cancellation")
    result = f.service.invoke("get_sec_financial_facts", dict(issuer=CIK), check=check)
    assert f.transport.calls == [SUBMISSIONS]
    assert result["status"] == "unavailable"
    assert f.store.latest_receipt(CIK)["gaps"] == [{"source": "companyfacts", "code": "cancelled"}]
    assert f.closes == [True]


def test_recent_observation_reused_and_24h_boundary_revalidates(tool_fixture):
    f = tool_fixture
    seed(f)
    f.now = "2026-09-13T11:59:59Z"
    assert f.service.invoke("list_sec_filings", dict(issuer=CIK))["status"] == "ok"
    assert f.acquisitions == []
    f.now = "2026-09-13T12:00:00Z"
    assert f.service.invoke("list_sec_filings", dict(issuer=CIK))["status"] == "ok"
    assert f.transport.calls == [SUBMISSIONS, FACTS]


def test_missing_contact_never_installs_or_dispatches(tmp_path, monkeypatch):
    runtime = owner("runtime")
    from src.api import dependencies
    from src.profile_state import ProfileStateStore
    profile = ProfileStateStore(tmp_path / "profile" / "state.db")
    store = Store(SecResearchPaths(tmp_path / "absent" / "market.db"))
    monkeypatch.setattr(runtime.SecResearchPaths, "resolve", lambda: store.paths)
    monkeypatch.setattr(dependencies, "get_profile_store", lambda: profile)
    monkeypatch.setattr(dependencies, "get_data_provider_store", lambda: SimpleNamespace(get_all=lambda: {"sec_edgar": {"user_agent": ""}}))
    result = runtime.build_tool_service().invoke("list_sec_filings", dict(issuer=CIK))
    assert result["gaps"] == [{"code": "sec_identity_unconfigured"}]
    assert not store.paths.market_db_path.parent.exists()


def doc_tool(rig):
    acquisitions = []
    @contextmanager
    def acquire():
        acquisitions.append(True)
        yield rig.captures, Transport({SUBMISSIONS: catalog(), FACTS: EXACT}), rig.factory
    service = owner("tool_service").ToolService(rig.store, acquisition_factory=acquire, clock=lambda: NOW)
    return service, acquisitions


def test_document_auto_reuses_capture_and_secondary_uses_observed_file_id(document_rig):
    r = document_rig
    service, acquisitions = doc_tool(r)
    r.enqueue()
    first = service.invoke("read_sec_filing", dict(filing_id=FILING_ID))
    assert first["data"]["document"]["capture_id"]
    first_id = first["data"]["document"]["capture_id"]
    assert service.invoke("read_sec_filing", dict(filing_id=FILING_ID))["data"]["document"]["capture_id"] == first_id
    assert len(acquisitions) == 1 and len(r.requests) == 2
    r.enqueue(b"<p>secondary</p>")
    secondary = service.invoke("read_sec_filing", dict(filing_id=FILING_ID, document_id="file:exhibit.xml"))
    assert secondary["data"]["document"]["document_id"] == "file:exhibit.xml"
    assert r.requests[-1].requests[0][1].endswith("/exhibit.xml")
    pinned = service.invoke("read_sec_filing", dict(filing_id=FILING_ID, capture_id=first_id))
    assert pinned["data"]["document"]["capture_id"] == first_id and len(acquisitions) == 2


def test_document_refresh_failure_blocks_old_capture_but_pin_reopens(document_rig):
    r = document_rig
    service, acquisitions = doc_tool(r)
    r.enqueue()
    first = service.invoke("read_sec_filing", dict(filing_id=FILING_ID))
    from tests.test_lifecycle_public_sources import Response
    r.queue.append(Response(b"failed", status=503))
    failed = service.invoke("read_sec_filing", dict(filing_id=FILING_ID, freshness="refresh"))
    assert failed["status"] == "unavailable" and failed["data"]["document"] is None
    pinned = service.invoke("read_sec_filing", dict(filing_id=FILING_ID, capture_id=first["data"]["document"]["capture_id"]))
    assert pinned["data"]["document"] == first["data"]["document"] and len(acquisitions) == 2


def test_handwritten_tools_have_typed_exact_signatures_and_delegate(tool_fixture, monkeypatch):
    assert importlib.util.find_spec("src.tools.sec_research_tools"), "missing three SEC tool adapters"
    module = importlib.import_module("src.tools.sec_research_tools")
    monkeypatch.setattr(module, "build_tool_service", lambda: tool_fixture.service)
    for name, params in {
        "list_sec_filings": "issuer forms filed_from filed_to include_amendments cursor limit freshness",
        "get_sec_financial_facts": "issuer metrics concepts fact_ids accession as_of period start end revisions cursor limit freshness",
        "read_sec_filing": "filing_id document_id section_id query capture_id cursor max_chars freshness",
    }.items():
        fn = getattr(module, name)
        signature = inspect.signature(fn)
        assert list(signature.parameters) == params.split()
        assert all(p.annotation is not inspect.Parameter.empty for p in signature.parameters.values())
        assert signature.return_annotation in (dict, "dict") and fn.__doc__
    assert module.get_sec_financial_facts(CIK)["data"][0]["value"] == "1234567890123456789.123"


@pytest.mark.parametrize("name,args", [
    ("get_sec_financial_facts", dict(issuer="AAPL", period="bad")),
    ("get_sec_financial_facts", dict(issuer="AAPL", concepts=["bad"])),
    ("get_sec_financial_facts", dict(issuer=CIK, fact_ids=["bad"])),
    ("read_sec_filing", dict(filing_id=FILING_ID, query="")),
    ("read_sec_filing", dict(filing_id=FILING_ID, query="\ud800")),
    ("read_sec_filing", dict(filing_id=FILING_ID, cursor="!")),
    ("read_sec_filing", dict(filing_id=FILING_ID, document_id="https://www.sec.gov")),
])
def test_all_tool_syntax_is_validated_before_storage(tool_fixture, monkeypatch, name, args):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid operands reached storage")
    monkeypatch.setattr(tool_fixture.store, "connect", forbidden)
    result = tool_fixture.service.invoke(name, args)
    assert result["status"] == "unavailable"
    assert result["gaps"][0]["code"] in {"sec_research_query_invalid", "sec_research_cursor_invalid"}
    assert tool_fixture.acquisitions == []


def test_structured_pins_reject_refresh_before_io(tool_fixture, monkeypatch):
    f = tool_fixture
    seed(f)
    fact = f.service.invoke("get_sec_financial_facts", dict(issuer=CIK, freshness="stored"))["data"][0]
    cursor = f.service.invoke("list_sec_filings", dict(issuer=CIK, limit=1, freshness="stored"))["next_cursor"]
    def forbidden(*args, **kwargs):
        pytest.fail("refresh pin reached storage")
    monkeypatch.setattr(f.store, "connect", forbidden)
    for name, args in [("get_sec_financial_facts", dict(fact_ids=[fact["fact_id"]])),
                       ("list_sec_filings", dict(cursor=cursor, limit=1))]:
        result = f.service.invoke(name, dict(issuer=CIK, freshness="refresh", **args))
        assert result["gaps"] == [{"code": "sec_research_query_invalid"}]
    assert f.acquisitions == []


def test_stored_runtime_never_opens_configuration_or_installs(tmp_path, monkeypatch):
    runtime = owner("runtime")
    from src.api import dependencies, permissions
    paths = SecResearchPaths(tmp_path / "absent" / "market.db")
    monkeypatch.setattr(runtime.SecResearchPaths, "resolve", lambda: paths)
    def forbidden(*args, **kwargs):
        pytest.fail("stored read opened acquisition authority")
    monkeypatch.setattr(dependencies, "get_profile_store", forbidden)
    monkeypatch.setattr(dependencies, "get_data_provider_store", forbidden)
    monkeypatch.setattr(permissions, "require_db_write", forbidden)
    for name, args in [("list_sec_filings", dict(issuer="AAPL")),
                       ("get_sec_financial_facts", dict(issuer=CIK)),
                       ("read_sec_filing", dict(filing_id=FILING_ID))]:
        result = runtime.build_tool_service().invoke(name, dict(freshness="stored", **args))
        assert result["gaps"] == [{"code": "sec_research_not_installed"}]
    assert list(tmp_path.iterdir()) == []


def test_permission_rejection_precedes_acquisition(tool_fixture, monkeypatch):
    from src.api import permissions
    def reject(*args, **kwargs):
        raise RuntimeError("PRIVATE denial")
    monkeypatch.setattr(permissions, "require_db_write", reject)
    result = tool_fixture.service.invoke("list_sec_filings", dict(issuer=CIK))
    assert result["status"] == "unavailable" and "PRIVATE" not in json.dumps(result)
    assert tool_fixture.acquisitions == [] and tool_fixture.transport.calls == []


def test_schema_mismatch_is_explicit_and_never_repaired(tool_fixture):
    f = tool_fixture
    with f.store.connect() as conn:
        conn.execute("CREATE TABLE sec_research_unknown(value TEXT)")
    result = f.service.invoke("list_sec_filings", dict(issuer=CIK))
    assert result["gaps"] == [{"code": "sec_research_schema_mismatch"}]
    assert f.acquisitions == []
    with f.store.connect() as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='sec_research_unknown'").fetchone()


def test_document_first_read_obtains_catalog_once(document_rig):
    r = document_rig
    r.store.record_receipt(CIK, status="unavailable", completed=[], pending=["submissions", "companyfacts"],
        gaps=[], observed_at="2026-09-10T00:00:00Z")
    transport = Transport({SUBMISSIONS: catalog(), FACTS: EXACT})
    @contextmanager
    def acquire():
        yield r.captures, transport, r.factory
    service = owner("tool_service").ToolService(r.store, acquisition_factory=acquire, clock=lambda: NOW)
    r.enqueue()
    result = service.invoke("read_sec_filing", dict(filing_id=FILING_ID))
    assert result["data"]["document"]["document_id"] == "file:actual.htm"
    assert transport.calls == [SUBMISSIONS, FACTS] and len(r.requests) == 2


def test_runtime_map_429_has_one_real_dispatch_and_closes(tmp_path, monkeypatch):
    from data_sources import sec_transport
    from src.api import dependencies
    from src.profile_state import ProfileStateStore
    from tests.test_sec_transport import _Clock, _Response, _Session
    runtime = owner("runtime")
    profile = ProfileStateStore(tmp_path / "profile" / "state.db")
    paths = SecResearchPaths(tmp_path / "market.db")
    monkeypatch.setattr(runtime.SecResearchPaths, "resolve", lambda: paths)
    monkeypatch.setattr(dependencies, "get_profile_store", lambda: profile)
    monkeypatch.setattr(dependencies, "get_data_provider_store", lambda: SimpleNamespace(
        get_all=lambda: {"sec_edgar": {"user_agent": "tests@example.test"}}))
    clock = _Clock()
    closed = []
    response = _Response(429, headers={"Retry-After": "3"})
    session = _Session([response, _Response()])
    session.close = lambda: closed.append(True)
    monkeypatch.setattr(sec_transport.requests, "Session", lambda: session)
    governor = sec_transport.SecRequestGovernor(lock_dir=tmp_path / "governor", clock=clock.time, sleep=clock.sleep)
    monkeypatch.setattr(sec_transport, "SecRequestGovernor", lambda **kwargs: governor)
    result = runtime.build_tool_service().invoke("list_sec_filings", dict(issuer="AAPL"))
    assert result["gaps"] == [{"code": "sec_rate_limited"}]
    assert len(session.calls) == 1 and session.calls[0]["url"] == MAP_URL
    assert clock.sleeps == [] and closed == [True] and response.closed


def test_stale_map_revalidates_before_issuer_metadata(tool_fixture):
    f = tool_fixture
    issuers = owner("issuer_store").IssuerStore(f.store)
    issuers.refresh(f.transport, f.captures, clock=lambda: "2026-09-10T00:00:00Z", check=None)
    f.transport.calls.clear()
    result = f.service.invoke("list_sec_filings", dict(issuer="AAPL"))
    assert result["status"] == "ok" and f.transport.calls == [MAP_URL, SUBMISSIONS, FACTS]


def test_failed_map_refresh_stops_before_metadata_and_never_borrows_old_mapping(tool_fixture):
    f = tool_fixture
    assert f.service.invoke("list_sec_filings", dict(issuer="AAPL"))["status"] == "ok"
    f.transport.calls.clear()
    f.transport.responses[MAP_URL] = RuntimeError("PRIVATE map response")
    result = f.service.invoke("list_sec_filings", dict(issuer="AAPL", freshness="refresh"))
    assert result["status"] == "unavailable" and result["coverage"]["issuer"]["cik"] is None
    assert f.transport.calls == [MAP_URL] and "PRIVATE" not in json.dumps(result)


def test_auto_retries_failed_map_in_next_invocation_not_same_call(tool_fixture):
    f = tool_fixture
    f.transport.responses[MAP_URL] = RuntimeError("fixture unavailable")
    first = f.service.invoke("list_sec_filings", dict(issuer="AAPL"))
    assert first["status"] == "unavailable" and f.transport.calls == [MAP_URL]
    f.transport.responses[MAP_URL] = map_body(("AAPL", 320193))
    second = f.service.invoke("list_sec_filings", dict(issuer="AAPL"))
    assert second["status"] == "ok"
    assert f.transport.calls == [MAP_URL, MAP_URL, SUBMISSIONS, FACTS]


def test_recent_schedule_never_satisfies_tool_history_resume_or_changes_cursor(tool_fixture):
    f = tool_fixture
    f.transport.responses[SUBMISSIONS] = catalog(history=1)
    history_url = f"https://data.sec.gov/submissions/CIK{CIK}-submissions-000.json"
    f.transport.responses[history_url] = b'{"accessionNumber":[],"filingDate":[],"form":[]}'
    research = ResearchService(f.store, f.captures, f.transport, clock=lambda: NOW)
    full = research.refresh(CIK, max_sources=2)
    page = f.service.invoke("list_sec_filings", dict(issuer=CIK, freshness="stored", limit=1))
    assert page["next_cursor"]
    research.refresh(CIK, scope="recent")
    f.transport.calls.clear()
    pinned = f.service.invoke("list_sec_filings", dict(issuer=CIK, cursor=page["next_cursor"], limit=1))
    assert pinned["coverage"]["receipt_id"] == full["receipt_id"]
    assert f.transport.calls == []
    result = f.service.invoke("list_sec_filings", dict(issuer=CIK))
    assert f.transport.calls == [history_url], "recent receipt hid full-history continuation"
    assert result["status"] == "ok"
