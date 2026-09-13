"""Durable citation contracts over real, offline captured SEC source bytes."""

import base64
from copy import deepcopy
import json
import shutil
from types import SimpleNamespace

import pytest

from src.sec_research.captures import CaptureStore
from src.sec_research.document_queries import DocumentQueries
from src.sec_research.facts import parse_companyfacts
from src.sec_research.paths import SecResearchPaths
from src.sec_research.queries import StoredQueries
from src.sec_research.store import Store
from tests.test_sec_research_document_service import (
    CIK, FILING_ID, HISTORY, NOW, bind_catalog, owner, rig, service,
)


ENVELOPE = {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}
FACT_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
TEXT = "A\u4e2d\u6587 needle \U0001f642 retained observation"
LATER = "2026-09-13T12:00:00Z"


def publish_facts(rig, value="1234567890123456789.123", *, observed_at=NOW):
    raw = (b'{"cik":320193,"facts":{"us-gaap":{"Revenues":{"units":{"USD":['
           b'{"val":' + value.encode("ascii") + b',"start":"2025-01-01",'
           b'"end":"2025-12-31","filed":"2026-05-01","form":"10-K",'
           b'"accn":"0000950170-26-000001","fy":2025,"fp":"FY"}]}}}}}')
    parsed = parse_companyfacts(raw, cik=CIK)
    sid = rig.store.publish(parsed, object_sha256=rig.captures.put(raw),
                            observed_at=observed_at, source_url=FACT_URL)
    return sid


def bind_sources(rig, bindings, *, observed_at=NOW):
    return rig.store.record_receipt(CIK, status="ok", completed=list(bindings),
        pending=[], gaps=[], observed_at=observed_at, source_snapshots=bindings)


def fact_ref(row):
    return {"kind": "fact", "cik": row["cik"], "fact_id": row["fact_id"],
            "snapshot_id": row["snapshot_id"], "source_sha256": row["source"]["sha256"],
            "source_pointer": row["source"]["pointer"], "source_url": row["source_url"],
            "observed_at": row["observed_at"]}


def filing_refs(page):
    return [{"kind": "filing", "filing_id": row["filing_id"],
             "snapshot_id": source["snapshot_id"], "source_sha256": source["source"]["sha256"],
             "source_pointer": source["source"]["pointer"], "source_url": source["source_url"],
             "observed_at": source["observed_at"]}
            for row in page["data"] for source in row["sources"]]


@pytest.fixture
def evidence(rig):
    bindings = rig.store.latest_receipt(CIK)["source_snapshots"]
    historical = bind_catalog(rig.store, rig.captures, history=HISTORY, bind=False)
    sid = publish_facts(rig)
    bindings.update({HISTORY: {"snapshot_id": historical, "observed_at": NOW},
                     "companyfacts": {"snapshot_id": sid, "observed_at": NOW}})
    receipt = bind_sources(rig, bindings)
    rig.enqueue(b"<p>" + TEXT.encode("utf-8") + b"</p>", mime="text/html")
    captured = service(rig).refresh(FILING_ID)
    assert captured["capture_id"], captured
    doc = DocumentQueries(rig.store, rig.captures).read(FILING_ID, query="needle", max_chars=80)
    facts = StoredQueries(rig.store).facts(CIK, concepts=["us-gaap:Revenues"])
    filings = StoredQueries(rig.store).filings(CIK)
    return SimpleNamespace(rig=rig, document=doc, facts=facts, filings=filings, receipt=receipt,
        document_ref={"kind": "document", **doc["data"]["passages"][0]["citation"]},
        fact_ref=fact_ref(facts["data"][0]), filing_refs=filing_refs(filings))


def test_whole_query_results_pin_fact_document_and_every_catalog_source(evidence):
    api = owner("citations")
    assert api.sec_citations_from_envelope("read_sec_filing", evidence.document) == [evidence.document_ref]
    assert api.sec_citations_from_envelope("get_sec_financial_facts", evidence.facts) == [evidence.fact_ref]
    refs = api.sec_citations_from_envelope("list_sec_filings", evidence.filings)
    assert sorted(refs, key=lambda r: r["snapshot_id"]) == sorted(evidence.filing_refs, key=lambda r: r["snapshot_id"])
    assert len(refs) == 2 and len({r["snapshot_id"] for r in refs}) == 2
    assert set(evidence.document) == ENVELOPE


def test_conflicting_filing_variants_keep_separate_exact_references(rig):
    bindings = rig.store.latest_receipt(CIK)["source_snapshots"]
    sid = bind_catalog(rig.store, rig.captures, history=HISTORY, bind=False, form="10-Q")
    bindings[HISTORY] = {"snapshot_id": sid, "observed_at": NOW}
    bind_sources(rig, bindings)
    page = StoredQueries(rig.store).filings(CIK)
    api = owner("citations")
    refs = api.sec_citations_from_envelope("list_sec_filings", page)
    assert len(refs) == 2 and len({r["filing_id"] for r in refs}) == 1
    reopened = [api.read_sec_citation(rig.store, rig.captures, citation=ref) for ref in refs]
    assert {r["data"]["observation"]["form"] for r in reopened} == {"10-K", "10-Q"}


@pytest.mark.parametrize("prefix", ["", "tool_", "mcp__ark__", "mcp__ark__tool_"])
@pytest.mark.parametrize("shape", ["dict", "json", "wrapped", "blocks", "mcp", "sdk"])
def test_owned_whole_results_and_actual_mcp_text_blocks(evidence, prefix, shape):
    api = owner("citations")
    raw = json.dumps(evidence.facts)
    wrapped = '<tool_output tool="get_sec_financial_facts">\n' + raw + '\n</tool_output>'
    result = {"dict": evidence.facts, "json": raw, "wrapped": wrapped,
              "blocks": [{"type": "text", "text": wrapped}],
              "mcp": {"content": [{"type": "text", "text": raw}], "is_error": False}}.get(shape)
    if shape == "sdk":
        from mcp.types import CallToolResult, TextContent
        result = CallToolResult(content=[TextContent(type="text", text=raw)], isError=False)
    assert api.sec_citations_from_result(prefix + "get_sec_financial_facts", result) == [evidence.fact_ref]
    assert api.citation_event_fields(prefix + "get_sec_financial_facts", result) == {
        "sec_citations": [evidence.fact_ref]}


@pytest.mark.parametrize("tool", ["other", "provider__list_sec_filings", "mcp__other__read_sec_filing", "tool_tool_list_sec_filings", None])
def test_unknown_tools_never_parse_or_scan_evidence(tool):
    api = owner("citations")
    assert api.sec_citations_from_result(tool, object()) == []
    assert api.citation_event_fields(tool, "PRIVATE malformed evidence") == {}


@pytest.mark.parametrize("change", [
    {"extra": True}, {"kind": "other"}, {"cik": "320193"}, {"fact_id": "bad"},
    {"snapshot_id": "bad"}, {"source_sha256": "A" * 64}, {"source_pointer": "facts/x"},
    {"source_pointer": "/bad~2escape"}, {"source_pointer": "/" + "x" * 10000},
    {"source_url": "file:///PRIVATE"}, {"source_url": "https://evil.example/private"},
    {"observed_at": "yesterday"}, {"observed_at": "2026-09-12T12:00:00"},
])
def test_closed_fact_reference_rejects_malformed_fields(evidence, change):
    api = owner("citations")
    with pytest.raises(api.CitationError) as error:
        api.validate_citation(evidence.fact_ref | change)
    assert error.value.code == "sec_citation_invalid"
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("change", [
    {"document_id": "primary"}, {"accession": "0000950170-26-000002"},
    {"start_byte": True}, {"start_byte": -1}, {"end_byte": 0}, {"end_byte": 128 * 1024**2 + 1},
    {"match_start_byte": None}, {"match_end_byte": 1}, {"extraction_version": ""},
])
def test_closed_document_reference_rejects_invalid_ranges(evidence, change):
    api = owner("citations")
    with pytest.raises(api.CitationError, match="^sec_citation_invalid$"):
        api.validate_citation(evidence.document_ref | change)


@pytest.mark.parametrize("mode", ["prose", "preview", "extra", "bad_row", "bad_source", "wrong_wrapper", "mixed_blocks", "duplicate_json", "nonfinite"])
def test_malformed_owned_evidence_is_a_typed_event_gap(evidence, mode):
    api = owner("citations")
    page = deepcopy(evidence.facts)
    result = page
    if mode == "prose":
        result = "The source says " + json.dumps(page)
    elif mode == "preview":
        result = {"output_preview": json.dumps(page)}
    elif mode == "extra":
        page["extra"] = True
    elif mode == "bad_row":
        page["data"].append({"value": "PRIVATE"})
    elif mode == "bad_source":
        page["data"][0]["source"]["sha256"] = "0" * 64
    elif mode == "wrong_wrapper":
        result = '<tool_output tool="list_sec_filings">\n' + json.dumps(page) + '\n</tool_output>'
    elif mode == "mixed_blocks":
        result = [{"type": "text", "text": json.dumps(page)}, {"type": "image", "data": "PRIVATE"}]
    elif mode == "duplicate_json":
        result = json.dumps(page).replace('"status":', '"status":"ok","status":', 1)
    elif mode == "nonfinite":
        page["coverage"]["bad"] = float("nan")
    with pytest.raises(api.CitationError):
        api.sec_citations_from_result("get_sec_financial_facts", result)
    assert api.citation_event_fields("get_sec_financial_facts", result) == {
        "sec_citation_gaps": ["sec_citation_result_invalid"]}


@pytest.mark.parametrize("tool", ["get_sec_financial_facts", "list_sec_filings", "read_sec_filing"])
@pytest.mark.parametrize("status", ["empty", "unavailable"])
def test_valid_whole_no_reference_envelopes_are_not_citation_gaps(tool, status):
    api = owner("citations")
    page = dict(status=status, data=[], gaps=[{"code": "sec_result_unavailable"}] if status == "unavailable" else [],
                observed_at=None, coverage={}, next_cursor=None)
    assert api.citation_event_fields(tool, page) == {}


def test_document_index_and_empty_search_do_not_invent_passage_citations(evidence):
    api = owner("citations")
    query = DocumentQueries(evidence.rig.store, evidence.rig.captures)
    for params in ({}, {"query": "absent"}, {"section_id": "item_999"}):
        assert api.citation_event_fields("read_sec_filing", query.read(FILING_ID, **params)) == {}


@pytest.mark.parametrize("mode", ["document_type", "document_fields", "document_hash", "coverage", "section", "directory_source"])
def test_malformed_no_passage_document_evidence_is_not_silently_ignored(evidence, mode):
    api, r = owner("citations"), evidence.rig
    page = DocumentQueries(r.store, r.captures).read(FILING_ID)
    assert page["data"]["passages"] == []
    if mode == "document_type":
        page["data"]["document"] = "PRIVATE"
    elif mode == "document_fields":
        del page["data"]["document"]["source_url"]
    elif mode == "document_hash":
        page["data"]["document"]["original_sha256"] = "bad"
    elif mode == "coverage":
        page["coverage"]["capture_id"] = "secdoc_" + "0" * 64
    elif mode == "section":
        page["data"]["sections"] = [{"section_id": "item_1", "label": "Item 1", "start_byte": True, "end_byte": 999999}]
    else:
        page["data"]["documents"][0]["source"]["sha256"] = "0" * 64
    assert api.citation_event_fields("read_sec_filing", page) == {
        "sec_citation_gaps": ["sec_citation_result_invalid"]}


@pytest.mark.parametrize("status", ["empty", "unavailable"])
def test_no_evidence_status_cannot_hide_a_nonempty_document_passage(evidence, status):
    api = owner("citations")
    assert api.citation_event_fields("read_sec_filing", evidence.document | {"status": status}) == {
        "sec_citation_gaps": ["sec_citation_result_invalid"]}


@pytest.mark.parametrize("shape", ["dict", "sdk"])
def test_conflicting_mcp_structured_content_is_a_gap_not_ignored_evidence(evidence, shape):
    api = owner("citations")
    different = deepcopy(evidence.facts)
    different["data"][0]["source"]["pointer"] += "1"
    result = {"content": [{"type": "text", "text": json.dumps(evidence.facts)}],
              "structuredContent": different}
    if shape == "sdk":
        from mcp.types import CallToolResult
        result = CallToolResult.model_validate(result)
    assert api.citation_event_fields("get_sec_financial_facts", result) == {
        "sec_citation_gaps": ["sec_citation_result_invalid"]}


def test_escaped_json_pointer_reopens_the_exact_fact_object(rig):
    api = owner("citations")
    sid = publish_facts(rig)
    body = rig.captures.read(rig.store.snapshot(CIK, sid)["object_sha256"])
    body = body.replace(b'"us-gaap"', b'"custom/~ns"').replace(b'"Revenues"', b'"Revenue/~Net"').replace(b'"USD"', b'"USD/~share"')
    parsed = parse_companyfacts(body, cik=CIK)
    rig.store.publish(parsed, object_sha256=rig.captures.put(body), observed_at=NOW, source_url=FACT_URL)
    page = StoredQueries(rig.store).facts(CIK, fact_ids=[parsed.facts[0].fact_id])
    ref = api.sec_citations_from_envelope("get_sec_financial_facts", page)[0]
    assert ref["source_pointer"] == "/facts/custom~1~0ns/Revenue~1~0Net/units/USD~1~0share/0"
    exact = api.read_sec_citation(rig.store, rig.captures, citation=ref)
    assert exact["status"] == "ok"
    assert exact["data"]["observation"]["value"] == "1234567890123456789.123"
    assert exact["data"]["observation"]["unit"] == "USD/~share"


@pytest.mark.parametrize("kind", ["document", "fact", "filing"])
def test_missing_pins_do_not_substitute_an_existing_observation(evidence, kind):
    api, r = owner("citations"), evidence.rig
    ref = {"document": evidence.document_ref, "fact": evidence.fact_ref, "filing": evidence.filing_refs[0]}[kind]
    key, prefix = ("capture_id", "secdoc_") if kind == "document" else ("snapshot_id", "secsnapshot_")
    page = api.read_sec_citation(r.store, r.captures, citation=ref | {key: prefix + "0" * 64})
    assert page["status"] == "unavailable" and page["data"] is None
    assert page["gaps"] == [{"code": "sec_citation_missing"}]


@pytest.mark.parametrize("kind", ["document", "fact", "filing"])
@pytest.mark.parametrize("mode", ["extra", "missing"])
def test_every_union_member_is_closed_and_validation_precedes_reads(evidence, kind, mode):
    api, r = owner("citations"), evidence.rig
    ref = dict({"document": evidence.document_ref, "fact": evidence.fact_ref, "filing": evidence.filing_refs[0]}[kind])
    if mode == "extra":
        ref["extra"] = "PRIVATE"
    else:
        del ref["source_url"]
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail("invalid reference accessed storage")
    with pytest.raises(api.CitationError, match="^sec_citation_invalid$"):
        api.read_sec_citation(Forbidden(), Forbidden(), citation=ref)


def test_research_citation_reopens_exact_bytes_after_refresh_and_relocation(evidence, tmp_path, monkeypatch):
    api, r = owner("citations"), evidence.rig
    refs = [evidence.document_ref, evidence.fact_ref, *evidence.filing_refs]
    sid = publish_facts(r, "999", observed_at=LATER)
    bind_catalog(r.store, r.captures, primary="new.htm", form="10-Q")
    bindings = r.store.latest_receipt(CIK)["source_snapshots"]
    bindings["companyfacts"] = {"snapshot_id": sid, "observed_at": LATER}
    bind_sources(r, bindings, observed_at=LATER)
    r.enqueue(b"new text only", names=["new.htm"], mime="text/plain")
    assert service(r).refresh(FILING_ID)["capture_id"] != evidence.document_ref["capture_id"]
    moved = Store(SecResearchPaths(tmp_path / "relocated.db"))
    shutil.move(r.store.paths.market_db_path, moved.paths.market_db_path)
    shutil.move(r.store.paths.capture_root, moved.paths.capture_root)
    captures = CaptureStore(moved, budget=None)
    def forbidden(*args, **kwargs):
        pytest.fail("exact citation performed a latest read, write or acquisition")
    for name in ("latest_receipt", "_write", "install"):
        monkeypatch.setattr(moved, name, forbidden)
    for name in ("put", "preflight", "status", "recover"):
        monkeypatch.setattr(captures, name, forbidden)
    r.before = forbidden
    reopened = [api.read_sec_citation(moved, captures, citation=ref) for ref in refs]
    assert all(set(page) == ENVELOPE and page["status"] == "ok" for page in reopened)
    assert [page["data"]["citation"] for page in reopened] == refs
    assert reopened[0]["data"]["text"] == TEXT
    assert reopened[1]["data"]["observation"]["value"] == "1234567890123456789.123"
    assert {page["data"]["observation"]["form"] for page in reopened[2:]} == {"10-K"}


@pytest.mark.parametrize("kind,change", [
    ("fact", {"source_sha256": "0" * 64}), ("fact", {"source_pointer": "/facts/us-gaap/Revenues/units/USD/1"}),
    ("fact", {"observed_at": LATER}), ("fact", {"source_url": "https://data.sec.gov/other.json"}),
    ("filing", {"source_pointer": "/filings/recent/accessionNumber/1"}),
    ("document", {"original_sha256": "0" * 64}), ("document", {"text_sha256": "0" * 64}),
    ("document", {"extraction_version": "sec-document-text-v999"}),
    ("document", {"start_byte": 2}), ("document", {"end_byte": 10_000}),
    ("document", {"match_start_byte": 2}), ("document", {"source_url": "https://www.sec.gov/other.htm"}),
])
def test_bound_hash_pointer_metadata_and_utf8_tampering_is_unavailable(evidence, kind, change):
    api = owner("citations")
    ref = {"fact": evidence.fact_ref, "filing": evidence.filing_refs[0], "document": evidence.document_ref}[kind]
    page = api.read_sec_citation(evidence.rig.store, evidence.rig.captures, citation=ref | change)
    assert set(page) == ENVELOPE and page["status"] == "unavailable"
    assert page["gaps"] == [{"code": "sec_citation_integrity_failed"}]


def test_identical_bytes_reobserved_at_receipt_time_remain_reopenable(evidence):
    api, r = owner("citations"), evidence.rig
    bindings = {key: value | {"observed_at": LATER} for key, value in evidence.receipt["source_snapshots"].items()}
    bind_sources(r, bindings, observed_at=LATER)
    page = StoredQueries(r.store).facts(CIK, concepts=["us-gaap:Revenues"])
    ref = api.sec_citations_from_envelope("get_sec_financial_facts", page)[0]
    assert ref["observed_at"] == LATER
    reopened = api.read_sec_citation(r.store, r.captures, citation=ref)
    assert reopened["status"] == "ok" and reopened["observed_at"] == LATER
    assert reopened["data"]["observation"]["observed_at"] == LATER


def test_canonical_query_roundtrip_is_bounded_and_rejects_other_encodings(evidence):
    api = owner("citations")
    for ref in (evidence.document_ref, evidence.fact_ref, *evidence.filing_refs):
        canonical = json.dumps(ref, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        expected = base64.urlsafe_b64encode(canonical.encode("ascii")).decode("ascii").rstrip("=")
        assert api.encode_citation_query(ref) == expected
        assert api.decode_citation_query(expected) == ref
        for token in (expected + "=", " " + expected, "!", "a" * 8193,
                      base64.urlsafe_b64encode(json.dumps(ref).encode()).decode().rstrip("=")):
            with pytest.raises(api.CitationError, match="^sec_citation_query_invalid$"):
                api.decode_citation_query(token)
