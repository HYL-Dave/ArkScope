"""Service contract owners; real persistence owners are added below."""

from copy import deepcopy
from dataclasses import asdict
import errno
import hashlib
import importlib
import inspect
import json
from types import SimpleNamespace

import pytest

from data_sources.sec_transport import SecResponse, SecTransport, SecTransportFailure


CIK = "0000320193"
HISTORY = "CIK0000320193-submissions-001.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
HISTORY_URL = "https://data.sec.gov/submissions/" + HISTORY
NOW = "2026-09-11T12:00:00Z"
EMPTY_COLUMNS = b'{"accessionNumber":[],"filingDate":[],"form":[]}'
EMPTY_FACTS = b'{"cik":320193,"facts":{}}'
EXACT_FACTS = (
    b'{"cik":320193,"facts":{"us-gaap":{"Assets":{"units":{"USD":['
    b'{"val":9007199254740993.123456789,"end":"2025-12-31","form":"10-K",'
    b'"accn":"0000320193-26-000001","filed":"2026-01-30"}'
    b']}}}}}'
)


def submissions(*, history=True, observed=True):
    files = b',"files":[' + (b'{"name":"' + HISTORY.encode() + b'"}' if history else b'') + b']'
    return b'{"cik":320193,"filings":{"recent":' + EMPTY_COLUMNS + (files if observed else b'') + b'}}'


class MemoryStore:
    """Temporary interface double until the independently owned store lands."""

    def __init__(self, root):
        self.paths = SimpleNamespace(capture_root=root)
        self.receipts = []
        self.published = []

    def install(self):
        raise AssertionError("service must not install schema")

    def publish(self, snapshot, *, object_sha256, observed_at, source_url):
        assert snapshot.sha256 == object_sha256
        self.published.append((snapshot, observed_at, source_url))
        return str(len(self.published))

    def record_receipt(self, cik, *, status, completed, pending, gaps, observed_at, source_snapshots=None, scope="full"):
        self.receipts.append(deepcopy(dict(cik=cik, scope=scope, status=status, completed=completed,
                                          pending=pending, gaps=gaps, observed_at=observed_at,
                                          source_snapshots=source_snapshots or {})))

    def latest_receipt(self, cik, *, scope=None):
        rows = [row for row in self.receipts if row["cik"] == cik and (scope is None or row["scope"] == scope)]
        return deepcopy(rows[-1]) if rows else None

    def snapshots(self, cik, kind):
        return [{**asdict(s), "row_count": len(getattr(s, "filings", getattr(s, "facts", ())))}
                for s, _, _ in self.published if s.cik == cik and
                ((kind == "catalog" and hasattr(s, "filings")) or
                 (kind == "facts" and hasattr(s, "facts")))]

    def catalog(self, cik):
        return [asdict(row) for s, _, _ in self.published if s.cik == cik
                for row in getattr(s, "filings", ())]

    def facts(self, cik):
        return [asdict(row) for s, _, _ in self.published if s.cik == cik
                for row in getattr(s, "facts", ())]


class MemoryCaptures:
    def __init__(self):
        self.bodies = {}
        self.preflights = 0
        self.block = None

    def preflight(self):
        self.preflights += 1
        if self.block:
            raise ValueError(self.block)

    def put(self, body):
        digest = hashlib.sha256(body).hexdigest()
        self.bodies[digest] = body
        return digest

    def read(self, digest):
        return self.bodies[digest]


class Transport:
    def __init__(self, responses=None, before=None):
        self.responses = responses if responses is not None else {
            SUBMISSIONS_URL: submissions(), FACTS_URL: EXACT_FACTS, HISTORY_URL: EMPTY_COLUMNS,
        }
        self.calls = []
        self.before = before

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.before:
            self.before(url)
        result = self.responses[url]
        if isinstance(result, BaseException):
            raise result
        return result if isinstance(result, SecResponse) else SecResponse(200, result)


@pytest.fixture
def service_type():
    # Missing module is an explicit initial RED assertion, not collection failure.
    assert importlib.util.find_spec("src.sec_research.service") is not None, "Task 3 service missing"
    return importlib.import_module("src.sec_research.service").ResearchService


@pytest.fixture
def rig(service_type, tmp_path):
    store, captures, transport = MemoryStore(tmp_path / "captures"), MemoryCaptures(), Transport()
    return service_type(store, captures, transport, clock=lambda: NOW), store, captures, transport


def test_pending_is_durable_before_first_dispatch_and_success_before_next(rig):
    service, store, _, transport = rig
    checkpoints = []
    transport.before = lambda url: checkpoints.append(store.latest_receipt(CIK))
    receipt = service.refresh(" CIK:320193 ")
    assert checkpoints[0]["pending"] == ["submissions", "companyfacts"]
    assert checkpoints[0]["completed"] == []
    assert checkpoints[0]["status"] == "unavailable"
    assert checkpoints[1]["completed"] == ["submissions"]
    assert checkpoints[1]["pending"] == ["companyfacts", HISTORY]
    assert checkpoints[2]["completed"] == ["submissions", "companyfacts"]
    assert receipt == store.latest_receipt(CIK)
    assert receipt["status"] == "ok"
    assert receipt["pending"] == []
    assert receipt["completed"] == ["submissions", "companyfacts", HISTORY]


def test_bounded_resume_only_requests_unfinished_sources(rig):
    service, store, _, transport = rig
    receipt = service.refresh(CIK, max_sources=1)
    assert receipt["status"] == "partial"
    assert receipt["pending"] == ["companyfacts", HISTORY]
    receipt = service.refresh(CIK, max_sources=1, resume=True)
    assert receipt["pending"] == [HISTORY]
    receipt = service.refresh(CIK, resume=True)
    assert receipt["status"] == "ok"
    assert service.refresh(CIK, resume=True) == receipt
    assert [url for url, _ in transport.calls] == [SUBMISSIONS_URL, FACTS_URL, HISTORY_URL]


def test_crash_keeps_success_checkpoint_and_resume_continuation(rig):
    service, store, _, transport = rig
    transport.responses[FACTS_URL] = SystemExit("worker died")
    with pytest.raises(SystemExit):
        service.refresh(CIK)
    assert store.latest_receipt(CIK)["completed"] == ["submissions"]
    assert store.latest_receipt(CIK)["pending"] == ["companyfacts", HISTORY]
    transport.responses[FACTS_URL] = EXACT_FACTS
    assert service.refresh(CIK, resume=True)["status"] == "ok"
    assert [url for url, _ in transport.calls].count(SUBMISSIONS_URL) == 1


def test_fresh_refresh_does_not_borrow_prior_success(rig):
    service, store, _, transport = rig
    service.refresh(CIK)
    transport.responses[SUBMISSIONS_URL] = RuntimeError("PRIVATE provider body")
    receipt = service.refresh(CIK)
    assert receipt["status"] == "partial"
    assert receipt["completed"] == ["companyfacts"]
    assert receipt["pending"] == ["submissions"]
    assert len(store.published) == 4
    assert "PRIVATE" not in json.dumps(receipt)
    assert service.stored(CIK)["status"] == "partial"


def test_unobserved_history_is_explicit_gap_even_after_noop_resume(rig):
    service, _, _, transport = rig
    transport.responses[SUBMISSIONS_URL] = submissions(observed=False)
    receipt = service.refresh(CIK)
    assert receipt["pending"] == []
    assert receipt["status"] == "partial"
    assert {gap["code"] for gap in receipt["gaps"]} == {"historical_files_unobserved"}
    assert service.refresh(CIK, resume=True) == receipt
    assert len(transport.calls) == 2


def test_observed_empty_is_complete_not_unavailable(rig):
    service, _, _, transport = rig
    transport.responses = {SUBMISSIONS_URL: submissions(history=False), FACTS_URL: EMPTY_FACTS}
    receipt = service.refresh(CIK)
    assert receipt["status"] == "ok"
    assert receipt["gaps"] == []
    stored = service.stored(CIK)
    assert stored["status"] == "ok"
    assert stored["catalog_count"] == stored["fact_count"] == 0


def test_declared_history_is_deduplicated_and_no_guessed_requests(rig):
    service, _, _, transport = rig
    body = submissions().replace(b'"files":[', b'"files":[{"name":"' + HISTORY.encode() + b'"},')
    transport.responses[SUBMISSIONS_URL] = body
    assert service.refresh(CIK)["completed"] == ["submissions", "companyfacts", HISTORY]
    assert [url for url, _ in transport.calls] == [SUBMISSIONS_URL, FACTS_URL, HISTORY_URL]


def test_raw_body_precision_survives_service_without_response_json(rig, monkeypatch):
    service, store, captures, _ = rig
    monkeypatch.setattr(SecResponse, "json", lambda self: pytest.fail("lossy response.json used"))
    service.refresh(CIK)
    assert store.facts(CIK)[0]["value"] == "9007199254740993.123456789"
    assert EXACT_FACTS in captures.bodies.values()


def test_malformed_whole_source_is_retained_without_smaller_success(rig):
    service, store, captures, transport = rig
    malformed = EXACT_FACTS.replace(b']}}}}}', b',{"val":"bad"}]}}}}}')
    transport.responses[FACTS_URL] = malformed
    receipt = service.refresh(CIK)
    assert store.facts(CIK) == []
    assert malformed in captures.bodies.values()
    assert receipt["pending"] == ["companyfacts"]
    assert receipt["status"] == "partial"
    assert any(g["source"] == "companyfacts" and g["code"] == "source_invalid" for g in receipt["gaps"])


@pytest.mark.parametrize("failure,code", [
    (RuntimeError("PRIVATE body token URL"), "sec_transport_unavailable"),
    (SecTransportFailure("sec_rate_limited"), "sec_rate_limited"),
    (SecTransportFailure("PRIVATE"), "sec_transport_unavailable"),
    (SecResponse(403, b"PRIVATE"), "sec_http_error"),
])
def test_provider_failure_is_closed_pending_and_retryable(rig, failure, code):
    service, _, _, transport = rig
    transport.responses[FACTS_URL] = failure
    receipt = service.refresh(CIK)
    assert receipt["pending"] == ["companyfacts"]
    assert {g["code"] for g in receipt["gaps"]} == {code}
    assert "PRIVATE" not in json.dumps(receipt)
    transport.responses[FACTS_URL] = EMPTY_FACTS
    receipt = service.refresh(CIK, resume=True)
    assert receipt["status"] == "ok"
    assert receipt["gaps"] == []


@pytest.mark.parametrize("code", ["capture_budget_exceeded", "storage_space_insufficient"])
def test_preflight_blocks_first_and_each_later_request(rig, code):
    service, _, captures, transport = rig
    captures.block = code
    receipt = service.refresh(CIK)
    assert transport.calls == []
    assert receipt["pending"] == ["submissions", "companyfacts"]
    assert receipt["gaps"][0]["code"] == code
    captures.block = None
    transport.before = lambda url: setattr(captures, "block", code)
    receipt = service.refresh(CIK, resume=True)
    assert [url for url, _ in transport.calls] == [SUBMISSIONS_URL]
    assert receipt["completed"] == ["submissions"]
    assert receipt["pending"] == ["companyfacts", HISTORY]
    assert receipt["status"] == "partial"


def test_cancellation_between_requests_keeps_checkpoint_and_redacts(rig):
    service, store, _, transport = rig

    def check():
        if transport.calls:
            raise RuntimeError("PRIVATE cancel reason")

    receipt = service.refresh(CIK, check=check)
    assert len(transport.calls) == 1
    assert receipt["completed"] == ["submissions"]
    assert receipt["pending"] == ["companyfacts", HISTORY]
    assert receipt["status"] == "partial"
    assert receipt["gaps"][0]["code"] == "cancelled"
    assert "PRIVATE" not in json.dumps(receipt)
    assert service.refresh(CIK, resume=True)["status"] == "ok"


@pytest.mark.parametrize("kwargs", [
    {"max_sources": 0}, {"max_sources": 17}, {"max_sources": True},
    {"max_sources": 1.0}, {"max_sources": "4"}, {"resume": 1},
])
def test_invalid_controls_fail_before_side_effects(rig, kwargs):
    service, store, captures, transport = rig
    with pytest.raises(ValueError):
        service.refresh(CIK, **kwargs)
    assert store.receipts == []
    assert captures.preflights == 0
    assert transport.calls == []


@pytest.mark.parametrize("cik", ["https://evil.invalid/source", "AAPL", "0", 320193])
def test_cik_not_arbitrary_url_is_required_before_side_effects(rig, cik):
    service, store, captures, transport = rig
    with pytest.raises(ValueError):
        service.refresh(cik)
    assert store.receipts == []
    assert captures.preflights == 0
    assert transport.calls == []


def test_stored_absence_never_acquires_or_installs(rig):
    service, store, captures, transport = rig
    result = service.stored(CIK)
    assert result["status"] == "unavailable"
    assert result["receipt"] is None
    assert captures.preflights == 0
    assert transport.calls == []
    assert store.receipts == []


@pytest.mark.parametrize("code", [
    "capture_store_busy", "capture_path_unsafe", "capture_platform_unsupported",
    "capture_integrity_failed", "capture_store_write_failed",
])
def test_capture_typed_failures_remain_distinct_and_pending(rig, code):
    service, _, captures, transport = rig
    captures.block = code
    receipt = service.refresh(CIK)
    assert receipt["gaps"] == [{"source": "submissions", "code": code}]
    assert receipt["pending"] == ["submissions", "companyfacts"]
    assert transport.calls == []


def test_enospc_after_preflight_never_publishes_or_loses_pending(rig, monkeypatch):
    service, store, captures, transport = rig

    def full(body):
        raise OSError(errno.ENOSPC, "PRIVATE filesystem")

    monkeypatch.setattr(captures, "put", full)
    receipt = service.refresh(CIK)
    assert receipt["gaps"] == [{"source": "submissions", "code": "storage_space_insufficient"}]
    assert store.published == []
    assert receipt["pending"] == ["submissions", "companyfacts"]
    assert len(transport.calls) == 1


def test_sixteen_source_bound_retains_seventeenth_declared_source(rig):
    service, _, _, transport = rig
    names = [f"CIK{CIK}-submissions-{index:03}.json" for index in range(20)]
    payload = json.loads(submissions(history=False))
    payload["filings"]["files"] = [{"name": name} for name in names]
    transport.responses[SUBMISSIONS_URL] = json.dumps(payload).encode()
    transport.responses.update({"https://data.sec.gov/submissions/" + name: EMPTY_COLUMNS for name in names})
    receipt = service.refresh(CIK, max_sources=16)
    assert len(transport.calls) == 16
    assert receipt["completed"] == ["submissions", "companyfacts", *names[:14]]
    assert receipt["pending"] == names[14:]
    assert receipt["status"] == "partial"


def test_resume_rejects_tampered_source_locator_without_network(rig):
    service, store, _, transport = rig
    store.record_receipt(CIK, status="partial", completed=[],
                         pending=["https://evil.invalid/source"], gaps=[], observed_at=NOW)
    with pytest.raises(ValueError, match="invalid_source_locator"):
        service.refresh(CIK, resume=True)
    assert transport.calls == []


class WireResponse:
    def __init__(self, body, status=200, *, length=None):
        self.status_code = status
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.body = body
        self.encoding = "utf-8"
        self.closed = False

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


class WireSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses[url]


def test_real_sec_transport_body_status_and_default_metadata_bound(service_type, tmp_path, monkeypatch):
    from src.sec_research.captures import CaptureStore
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store

    responses = {
        SUBMISSIONS_URL: WireResponse(submissions(history=False)),
        FACTS_URL: WireResponse(EXACT_FACTS),
    }
    session = WireSession(responses)
    transport = SecTransport(user_agent="ArkScope offline@example.test", session=session,
                             lock_dir=tmp_path / "governor")
    store = Store(SecResearchPaths.from_market_db(tmp_path / "market.db"))
    store.install()
    captures = CaptureStore(store, budget=lambda: 1024**2, free_bytes=lambda path: 1024**3)
    service = service_type(store, captures, transport, clock=lambda: NOW)
    monkeypatch.setattr(SecResponse, "json", lambda self: pytest.fail("lossy response.json used"))
    try:
        assert service.refresh(CIK)["status"] == "ok"
        assert store.facts(CIK)[0]["value"] == "9007199254740993.123456789"
        assert captures.read(hashlib.sha256(EXACT_FACTS).hexdigest()) == EXACT_FACTS
        responses[SUBMISSIONS_URL] = WireResponse(submissions(history=False), length=16 * 1024**2 + 1)
        receipt = service.refresh(CIK, max_sources=1)
        assert receipt["gaps"] == [{"source": "submissions", "code": "sec_response_too_large"}]
        responses[SUBMISSIONS_URL] = WireResponse(b"PRIVATE", status=403)
        receipt = service.refresh(CIK, max_sources=1, resume=True)
        assert receipt["gaps"] == [{"source": "submissions", "code": "sec_http_error"}]
        assert all(response.closed for response in responses.values())
    finally:
        transport.close()


@pytest.fixture
def durable(service_type, tmp_path):
    from src.sec_research.captures import CaptureStore
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store

    paths = SecResearchPaths.from_market_db(tmp_path / "market.db")
    store = Store(paths)
    store.install()
    captures = CaptureStore(store, budget=lambda: 1024**2, free_bytes=lambda path: 1024**3)
    transport = Transport()
    return service_type(store, captures, transport, clock=lambda: NOW), store, captures, transport


def test_real_persistence_reopens_bytes_precision_receipts_and_resume(durable, service_type):
    from src.sec_research.captures import CaptureStore
    from src.sec_research.store import Store

    service, store, captures, transport = durable
    receipt = service.refresh(CIK, max_sources=1)
    reopened = Store(store.paths)
    reopened_captures = CaptureStore(reopened, budget=lambda: 1024**2, free_bytes=lambda path: 1024**3)
    assert reopened.latest_receipt(CIK) == receipt
    second = service_type(reopened, reopened_captures, transport, clock=lambda: NOW)
    assert second.refresh(CIK, resume=True)["status"] == "ok"
    assert reopened.facts(CIK)[0]["value"] == "9007199254740993.123456789"
    for body in (submissions(), EXACT_FACTS, EMPTY_COLUMNS):
        assert reopened_captures.read(hashlib.sha256(body).hexdigest()) == body
    assert [url for url, _ in transport.calls] == [SUBMISSIONS_URL, FACTS_URL, HISTORY_URL]
    count = len(transport.calls)
    assert second.refresh(CIK, resume=True)["status"] == "ok"
    assert len(transport.calls) == count
    assert second.stored(CIK)["fact_count"] == 1


def test_real_provider_and_parser_run_outside_sqlite_market_and_capture_write_locks(durable, monkeypatch):
    from src.market_data_direct import market_write_lock
    from src.sec_research.capture_lock import capture_writer
    import src.sec_research.service as service_module

    service, store, _, transport = durable
    observations = []

    def probe(label):
        with market_write_lock(timeout=0, poll=0):
            with store.connect() as conn:
                conn.execute("PRAGMA busy_timeout=0")
                conn.execute("BEGIN IMMEDIATE")
                conn.rollback()
            with capture_writer(store.paths.capture_root):
                pass
        observations.append(label)

    parse_submissions = service_module.parse_submissions
    parse_companyfacts = service_module.parse_companyfacts

    def parse_catalog(*args, **kwargs):
        probe("catalog")
        return parse_submissions(*args, **kwargs)

    def parse_facts(*args, **kwargs):
        probe("facts")
        return parse_companyfacts(*args, **kwargs)

    transport.before = lambda url: probe("transport")
    monkeypatch.setattr(service_module, "parse_submissions", parse_catalog)
    monkeypatch.setattr(service_module, "parse_companyfacts", parse_facts)
    assert service.refresh(CIK)["status"] == "ok"
    assert observations == ["transport", "catalog", "transport", "facts", "transport", "catalog"]


def test_real_crash_then_reopen_preserves_checkpoint(durable, service_type):
    from src.sec_research.store import Store

    service, store, captures, transport = durable
    transport.responses[FACTS_URL] = SystemExit("crash")
    with pytest.raises(SystemExit):
        service.refresh(CIK)
    reopened = Store(store.paths)
    assert reopened.latest_receipt(CIK)["completed"] == ["submissions"]
    transport.responses[FACTS_URL] = EXACT_FACTS
    assert service_type(reopened, captures, transport, clock=lambda: NOW).refresh(CIK, resume=True)["status"] == "ok"
    assert [url for url, _ in transport.calls].count(SUBMISSIONS_URL) == 1


def test_real_malformed_body_is_retained_without_partial_fact_rows(durable):
    service, store, captures, transport = durable
    malformed = EXACT_FACTS.replace(b']}}}}}', b',{"val":"bad"}]}}}}}')
    transport.responses[FACTS_URL] = malformed
    receipt = service.refresh(CIK)
    assert receipt["status"] == "partial"
    assert store.facts(CIK) == []
    assert captures.read(hashlib.sha256(malformed).hexdigest()) == malformed


@pytest.mark.parametrize("code", [
    "sec_research_snapshot_bytes_exceeded", "sec_research_snapshot_rows_exceeded",
])
def test_store_admission_failures_remain_typed_pending(rig, monkeypatch, code):
    service, store, captures, _ = rig

    def reject(*args, **kwargs):
        raise ValueError(code)

    monkeypatch.setattr(store, "publish", reject)
    receipt = service.refresh(CIK)
    assert receipt["status"] == "unavailable"
    assert receipt["completed"] == []
    assert receipt["pending"] == ["submissions", "companyfacts"]
    assert receipt["gaps"] == [{"source": "submissions", "code": code}]
    assert captures.read(hashlib.sha256(submissions()).hexdigest()) == submissions()


def test_stored_uses_current_receipt_only_and_never_materializes_observations(rig, service_type, monkeypatch):
    service, store, _, transport = rig
    service.refresh(CIK)

    def forbidden(*args):
        pytest.fail("unpaged observations must not be materialized")

    monkeypatch.setattr(store, "facts", forbidden)
    monkeypatch.setattr(store, "catalog", forbidden)
    local = service_type(store, None, None)
    assert local.stored(CIK)["fact_count"] == 1
    assert "facts" not in local.stored(CIK)
    assert "catalog" not in local.stored(CIK)
    store.receipts.clear()
    assert local.stored(CIK)["status"] == "unavailable"
    transport.responses[SUBMISSIONS_URL] = RuntimeError("PRIVATE")
    receipt = service.refresh(CIK, max_sources=1)
    assert receipt["status"] == "unavailable"
    assert local.stored(CIK)["status"] == "unavailable"
    assert local.stored(CIK)["fact_count"] == 1


def test_same_issuer_overlap_is_rejected_without_overwriting_receipt(durable, service_type):
    from src.sec_research.store import Store

    service, store, captures, transport = durable
    competing_transport = Transport()
    competing = service_type(Store(store.paths), captures, competing_transport, clock=lambda: NOW)
    denied = []

    def overlap(url):
        prior = store.latest_receipt(CIK)
        with pytest.raises(ValueError, match="^sec_research_refresh_busy$"):
            competing.refresh(CIK)
        assert store.latest_receipt(CIK) == prior
        denied.append(url)

    transport.before = overlap
    result = service.refresh(CIK)
    assert result["status"] == "ok"
    assert denied == [SUBMISSIONS_URL, FACTS_URL, HISTORY_URL]
    assert competing_transport.calls == []
    assert competing.refresh(CIK, resume=True) == result


def test_different_issuer_refresh_is_allowed_during_provider_wait(durable, service_type):
    service, store, captures, transport = durable
    other_cik = "0000789019"
    other_transport = Transport({
        "https://data.sec.gov/submissions/CIK0000789019.json": submissions(history=False).replace(b"320193", b"789019"),
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json": EMPTY_FACTS.replace(b"320193", b"789019"),
    })
    other = service_type(store, captures, other_transport, clock=lambda: NOW)
    nested = []

    def overlap(url):
        if not nested:
            nested.append(other.refresh(other_cik))

    transport.before = overlap
    result = service.refresh(CIK)
    assert result["cik"] == CIK
    assert result["status"] == "ok"
    assert nested[0]["cik"] == other_cik
    assert nested[0]["status"] == "ok"
    assert len(other_transport.calls) == 2


def test_real_recent_and_historical_rows_and_fresh_failure_keep_old_observations(durable, service_type):
    from src.sec_research.store import Store

    service, store, _, transport = durable
    recent = (b'{"accessionNumber":["0000320193-26-000002"],"filingDate":["2026-02-01"],'
              b'"reportDate":["2025-12-31"],"form":["10-K/A"]}')
    historical = (b'{"accessionNumber":["0000320193-25-000001"],"filingDate":["2025-02-01"],'
                  b'"reportDate":["2024-12-31"],"form":["10-K"]}')
    transport.responses[SUBMISSIONS_URL] = submissions().replace(EMPTY_COLUMNS, recent)
    transport.responses[HISTORY_URL] = historical
    assert service.refresh(CIK)["status"] == "ok"
    reopened = Store(store.paths)
    rows = reopened.catalog(CIK)
    assert [(row["accession"], row["form"], row["report_date"], row["filed_date"]) for row in rows] == [
        ("0000320193-26-000002", "10-K/A", "2025-12-31", "2026-02-01"),
        ("0000320193-25-000001", "10-K", "2024-12-31", "2025-02-01"),
    ]
    transport.responses[SUBMISSIONS_URL] = RuntimeError("PRIVATE")
    transport.responses[FACTS_URL] = EXACT_FACTS.replace(b"9007199254740993.123456789", b"42.5000")
    receipt = service.refresh(CIK)
    assert receipt["status"] == "partial"
    assert receipt["completed"] == ["companyfacts"]
    assert receipt["pending"] == ["submissions"]
    assert reopened.catalog(CIK) == rows
    assert [row["value"] for row in reopened.facts(CIK)] == ["9007199254740993.123456789", "42.5000"]
    local = service_type(reopened, None, None).stored(CIK)
    assert local["status"] == "partial"
    assert local["catalog_count"] == local["fact_count"] == 2


def test_real_stored_only_does_not_create_capture_root_or_change_database(durable, service_type, monkeypatch):
    service, store, _, transport = durable
    before = store.paths.market_db_path.read_bytes()

    def forbidden():
        pytest.fail("read installed schema implicitly")

    monkeypatch.setattr(store, "install", forbidden)
    assert not store.paths.capture_root.exists()
    result = service_type(store, None, None).stored(CIK)
    assert result["status"] == "unavailable"
    assert result["catalog_count"] == result["fact_count"] == 0
    assert not store.paths.capture_root.exists()
    assert store.paths.market_db_path.read_bytes() == before
    assert transport.calls == []


def test_real_receipt_bindings_survive_unchanged_capture_restart_and_resume(durable, service_type):
    from src.sec_research.store import Store

    service, store, captures, transport = durable
    first = service.refresh(CIK)
    assert "source_snapshots" in first, "receipts must bind published snapshots"
    later = "2026-09-12T12:00:00Z"
    reopened = Store(store.paths)
    second_service = service_type(reopened, captures, transport, clock=lambda: later)
    second = second_service.refresh(CIK, max_sources=1)
    assert second["source_snapshots"] == {"submissions": {
        "snapshot_id": first["source_snapshots"]["submissions"]["snapshot_id"],
        "observed_at": later}}
    resumed = second_service.refresh(CIK, resume=True)
    assert set(resumed["source_snapshots"]) == {"submissions", "companyfacts", HISTORY}
    assert resumed["source_snapshots"]["submissions"] == second["source_snapshots"]["submissions"]
    assert all(binding["observed_at"] == later for binding in resumed["source_snapshots"].values())
    assert reopened.snapshots(CIK, "catalog")[0]["observed_at"] == NOW


def test_interrupted_new_refresh_has_no_prior_snapshot_authority(durable):
    service, store, _, transport = durable
    first = service.refresh(CIK)
    transport.responses[SUBMISSIONS_URL] = SystemExit("interrupted")
    with pytest.raises(SystemExit):
        service.refresh(CIK)
    latest = store.latest_receipt(CIK)
    assert latest["receipt_id"] > first["receipt_id"]
    assert latest.get("source_snapshots") == {}, "new intent must be explicitly unbound"
    assert store.snapshots(CIK, "catalog")
    from src.sec_research.queries import StoredQueries
    result = StoredQueries(store).filings(CIK)
    assert result["status"] == "unavailable"
    assert result["data"] == []


@pytest.mark.parametrize("pending", [[], ["companyfacts"]])
def test_resume_explicitly_unbound_receipt_reacquires_instead_of_blessing_it(durable, pending):
    service, store, _, transport = durable
    store.record_receipt(CIK, status="partial" if pending else "ok", completed=["submissions"],
                         pending=pending, gaps=[], observed_at=NOW)
    resumed = service.refresh(CIK, resume=True, max_sources=1)
    assert [url for url, _ in transport.calls] == [SUBMISSIONS_URL]
    assert set(resumed["source_snapshots"]) == {"submissions"}


def test_recent_schedule_preserves_explicit_history_continuation(durable):
    from src.sec_research.queries import StoredQueries

    service, store, captures, transport = durable
    assert "scope" in inspect.signature(service.refresh).parameters, "explicit acquisition scope missing"
    full = service.refresh(CIK, max_sources=2)
    assert full["pending"] == [HISTORY]
    transport.calls.clear()
    recent = service.refresh(CIK, scope="recent")
    assert [url for url, _ in transport.calls] == [SUBMISSIONS_URL, FACTS_URL]
    assert recent["scope"] == "recent"
    assert recent["status"] == "ok"
    assert recent["pending"] == []
    assert store.latest_receipt(CIK) == recent
    assert store.latest_receipt(CIK, scope="full") == full
    assert store.receipt(CIK, full["receipt_id"]) == full
    local = StoredQueries(store).filings(CIK)
    assert local["coverage"]["scope"] == "recent"
    assert local["coverage"]["complete"] is False
    assert {g["code"] for g in local["gaps"]} == {"historical_not_requested"}
    assert StoredQueries(store).facts(CIK)["data"][0]["value"] == "9007199254740993.123456789"
    transport.calls.clear()
    resumed = service.refresh(CIK, resume=True)
    assert [url for url, _ in transport.calls] == [HISTORY_URL]
    assert resumed["scope"] == "full"
    assert resumed["source_snapshots"]["submissions"] == full["source_snapshots"]["submissions"]
    assert captures.read(hashlib.sha256(EXACT_FACTS).hexdigest()) == EXACT_FACTS


@pytest.mark.parametrize("scope", [None, "history", "", True])
def test_invalid_receipt_scope_rejected_before_acquisition(durable, scope):
    service, store, _, transport = durable
    assert "scope" in inspect.signature(service.refresh).parameters, "explicit acquisition scope missing"
    with pytest.raises(ValueError, match="invalid_scope"):
        service.refresh(CIK, scope=scope)
    assert transport.calls == []
    assert store.latest_receipt(CIK) is None
