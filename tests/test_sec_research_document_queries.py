"""Pinned UTF-8 passages, closed cursors, bounded indexes and literal search."""

import base64
import json
import shutil

import pytest

from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store
from tests.test_sec_research_document_service import (
    FILING_ID, CIK, HISTORY, NOW, bind_catalog, owner, rig, service,
)


def queries(rig):
    return owner("document_queries").DocumentQueries(rig.store, rig.captures)


def test_failed_refresh_does_not_borrow_latest_capture(rig):
    rig.enqueue()
    old = service(rig).refresh(FILING_ID)
    rig.enqueue(status=503)
    failed = service(rig).refresh(FILING_ID)
    assert failed["capture_id"] is None
    assert queries(rig).read(FILING_ID)["status"] == "unavailable"
    assert queries(rig).read(FILING_ID, capture_id=old["capture_id"])["status"] == "ok"


def test_pinned_capture_survives_refresh_restart_and_relocation(rig, tmp_path):
    rig.enqueue(b"<p>needle old observation needle retained</p>")
    old = service(rig).refresh(FILING_ID)
    first = queries(rig).read(FILING_ID, capture_id=old["capture_id"], query="needle", max_chars=80)
    assert first["data"]["passages"]
    rig.enqueue(b"<p>needle new observation</p>")
    service(rig).refresh(FILING_ID)
    bind_catalog(rig.store, rig.captures, primary="changed.htm")
    assert queries(rig).read(FILING_ID, capture_id=old["capture_id"], query="needle", max_chars=80) == first
    moved = Store(SecResearchPaths(tmp_path / "moved.db"))
    shutil.copy2(rig.store.paths.market_db_path, moved.paths.market_db_path)
    shutil.copytree(rig.store.paths.capture_root, moved.paths.capture_root)
    caps = CaptureStore(moved, budget=lambda: 1)
    reopened = owner("document_queries").DocumentQueries(moved, caps)
    assert reopened.read(FILING_ID, capture_id=old["capture_id"], query="needle", max_chars=80) == first
    resolved = reopened.read(FILING_ID, document_id="file:actual.htm", capture_id=old["capture_id"], query="needle", max_chars=80)
    assert resolved["data"]["passages"] == first["data"]["passages"]


def test_passage_offsets_preserve_multibyte_text(rig):
    text = "A\u4e2d\u6587 needle \U0001f642 needle Z"
    rig.enqueue(text.encode(), mime="text/plain")
    captured = service(rig).refresh(FILING_ID)
    read = queries(rig)
    index = read.read(FILING_ID, capture_id=captured["capture_id"], max_chars=3)
    cursor, emitted = index["data"]["text_start_cursor"], []
    assert cursor and index["data"]["passages"] == []
    while cursor:
        page = read.read(FILING_ID, cursor=cursor, max_chars=3)
        for passage in page["data"]["passages"]:
            citation = passage["citation"]
            assert text.encode()[citation["start_byte"]:citation["end_byte"]].decode() == passage["text"]
            assert len(passage["text"]) <= 3
            emitted.append(passage["text"])
        cursor = page["next_cursor"]
    assert "".join(emitted) == text


def test_document_cursor_binds_capture_filter_and_size(rig):
    rig.enqueue(b"needle one needle two needle three", mime="text/plain")
    first = service(rig).refresh(FILING_ID)
    rig.enqueue(b"needle newer", mime="text/plain")
    second = service(rig).refresh(FILING_ID)
    page = queries(rig).read(FILING_ID, capture_id=first["capture_id"], query="needle", max_chars=8)
    cursor = page["next_cursor"]
    assert cursor
    for changed in ({"query": "other"}, {"max_chars": 9}, {"capture_id": second["capture_id"]},
                    {"document_id": "file:actual.htm"}, {"section_id": "item_1"}):
        with pytest.raises(ValueError, match="sec_research_cursor_mismatch"):
            queries(rig).read(FILING_ID, **({"query": "needle", "max_chars": 8, "cursor": cursor} | changed))
    next_page = queries(rig).read(FILING_ID, query="needle", max_chars=8, cursor=cursor)
    assert next_page["data"]["document"]["capture_id"] == first["capture_id"]
    assert next_page["data"]["passages"][0]["citation"]["match_start_byte"] == 11


def edit_cursor(cursor, **changes):
    value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    value.update(changes)
    return base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":")).encode()).decode().rstrip("=")


@pytest.mark.parametrize("offset", [1, 10000, -1, True])
def test_caller_edited_offsets_are_bounded_utf8_boundaries(rig, offset):
    rig.enqueue("\u4e2dneedle".encode(), mime="text/plain")
    service(rig).refresh(FILING_ID)
    cursor = queries(rig).read(FILING_ID)["data"]["text_start_cursor"]
    with pytest.raises(ValueError, match="sec_research_cursor_invalid"):
        queries(rig).read(FILING_ID, cursor=edit_cursor(cursor, offset=offset))


def test_index_continuation_exposes_all_documents_and_sections(rig):
    names = ["actual.htm", *[f"exhibit-{i}.xml" for i in range(650)]]
    rig.enqueue(b"<h1>Item 1. Business</h1><p>needle</p><h1>Item 2. Properties</h1><p>land</p>", names=names)
    service(rig).refresh(FILING_ID)
    read, cursor, entries, sections = queries(rig), None, [], []
    while True:
        page = read.read(FILING_ID, cursor=cursor, max_chars=30)
        assert len(json.dumps(page, ensure_ascii=True).encode()) <= 256 * 1024
        assert page["data"]["text_start_cursor"]
        entries.extend(row["name"] for row in page["data"]["documents"])
        sections.extend(row["section_id"] for row in page["data"]["sections"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert entries == names and sections == ["item_1", "item_2"]


def test_literal_query_obeys_section_and_empty_requires_observation(rig):
    rig.enqueue(b"<h1>Item 1. Business</h1><p>needle.* first</p><h1>Item 2. Properties</h1><p>needle other</p>")
    service(rig).refresh(FILING_ID)
    page = queries(rig).read(FILING_ID, section_id="item_1", query="needle.*")
    assert len(page["data"]["passages"]) == 1
    assert "first" in page["data"]["passages"][0]["text"]
    assert "other" not in page["data"]["passages"][0]["text"]
    empty = queries(rig).read(FILING_ID, section_id="item_2", query="needle.*")
    assert empty["status"] == "empty" and empty["coverage"]["complete"]
    unknown = queries(rig).read(FILING_ID, section_id="item_999", query="needle")
    assert unknown["status"] == "unavailable" and unknown["data"]["text_start_cursor"]
    assert {g["code"] for g in unknown["gaps"]} == {"section_unavailable"}
    whole = queries(rig).read(FILING_ID, cursor=unknown["data"]["text_start_cursor"])
    assert "other" in whole["data"]["passages"][0]["text"]


def test_tiny_page_cannot_emit_partial_search_match_or_stuck_cursor(rig):
    rig.enqueue(b"needle needle", mime="text/plain")
    service(rig).refresh(FILING_ID)
    page = queries(rig).read(FILING_ID, query="needle", max_chars=3)
    assert page["status"] == "unavailable" and not page["coverage"]["complete"]
    assert not page["data"]["passages"] and page["next_cursor"] is None
    assert {g["code"] for g in page["gaps"]} == {"document_page_size_insufficient"}


def test_primary_alias_never_reopens_non_primary_capture(rig):
    rig.enqueue(b"<h1>Item 1. Business</h1><p>needle exhibit</p>")
    result = service(rig).refresh(FILING_ID, "file:exhibit.xml")
    assert result["capture_id"]
    assert queries(rig).read(FILING_ID, capture_id=result["capture_id"])["status"] == "unavailable"
    assert queries(rig).read(FILING_ID, document_id="file:exhibit.xml", capture_id=result["capture_id"])["status"] == "ok"


@pytest.mark.parametrize("changes", [{"max_chars": True}, {"max_chars": 0}, {"max_chars": 20001},
    {"query": ""}, {"query": "\ud800"}, {"document_id": "file:../x"},
    {"document_id": "file:xslF345X06/form4.xml"},
    {"document_id": "https://evil.example/x"}, {"capture_id": "bad"}, {"cursor": "bad"}])
def test_pure_validation_rejects_before_storage(changes):
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail("invalid query touched storage")
    with pytest.raises(ValueError):
        owner("document_queries").DocumentQueries(Forbidden(), Forbidden()).read(FILING_ID, **changes)


def test_unknown_form_keeps_whole_text_and_section_gap(rig):
    bind_catalog(rig.store, rig.captures, form="S-1")
    rig.enqueue(b"whole needle text", mime="text/plain")
    service(rig).refresh(FILING_ID)
    page = queries(rig).read(FILING_ID)
    assert page["status"] == "partial"
    assert page["data"]["text_start_cursor"] and not page["data"]["sections"]
    assert {g["code"] for g in page["gaps"]} == {"section_index_unsupported"}


def test_failed_resolved_primary_refresh_also_blocks_latest_primary_alias(rig):
    rig.enqueue()
    first = service(rig).refresh(FILING_ID)
    rig.enqueue(status=503)
    service(rig).refresh(FILING_ID, "file:actual.htm")
    assert queries(rig).read(FILING_ID)["status"] == "unavailable"
    assert queries(rig).read(FILING_ID, document_id="file:actual.htm")["status"] == "unavailable"
    assert queries(rig).read(FILING_ID, capture_id=first["capture_id"])["status"] == "ok"


def test_successful_resolved_primary_capture_is_visible_through_latest_alias(rig):
    rig.enqueue()
    result = service(rig).refresh(FILING_ID, "file:actual.htm")
    page = queries(rig).read(FILING_ID)
    assert page["data"]["document"]["capture_id"] == result["capture_id"]


def test_edited_search_mode_cannot_bypass_filter_and_section_binding(rig):
    rig.enqueue()
    service(rig).refresh(FILING_ID)
    page = queries(rig).read(FILING_ID, query="needle", max_chars=8)
    assert page["next_cursor"]
    with pytest.raises(ValueError, match="sec_research_cursor_mismatch"):
        queries(rig).read(FILING_ID, query="needle", max_chars=8,
                          cursor=edit_cursor(page["next_cursor"], mode="text"))


def test_nonoverlapping_literal_matches_keep_exact_multibyte_match_ranges(rig):
    text = "\u4e2d\u6587\u4e2d\u6587\u4e2d\u6587 aaa aaa"
    rig.enqueue(text.encode(), mime="text/plain")
    service(rig).refresh(FILING_ID)
    cursor, starts = None, []
    while True:
        page = queries(rig).read(FILING_ID, query="\u4e2d\u6587", cursor=cursor, max_chars=4)
        for passage in page["data"]["passages"]:
            cite = passage["citation"]
            starts.append(cite["match_start_byte"])
            assert text.encode()[cite["match_start_byte"]:cite["match_end_byte"]].decode() == "\u4e2d\u6587"
            assert text.encode()[cite["start_byte"]:cite["end_byte"]].decode() == passage["text"]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert starts == [0, 6, 12]


def test_stored_reads_do_not_write_or_acquire(rig, monkeypatch):
    rig.enqueue()
    captured = service(rig).refresh(FILING_ID)
    def forbidden(*args, **kwargs):
        pytest.fail("stored read acquired or wrote")
    monkeypatch.setattr(rig.captures, "preflight", forbidden)
    monkeypatch.setattr(rig.captures, "put", forbidden)
    monkeypatch.setattr(rig.store, "_write", forbidden)
    rig.before = forbidden
    assert queries(rig).read(FILING_ID, capture_id=captured["capture_id"], query="needle")["data"]["passages"]


@pytest.mark.parametrize("changes", [{"extra": True}, {"v": True}, {"v": 2}, {"mode": []},
    {"mode": "other"}, {"filters_hash": None}, {"capture_id": 10}, {"offset": 128 * 1024**2 + 1}])
def test_document_cursor_closed_shape_rejected_before_io(rig, monkeypatch, changes):
    rig.enqueue()
    service(rig).refresh(FILING_ID)
    cursor = queries(rig).read(FILING_ID)["data"]["text_start_cursor"]
    def forbidden(*args, **kwargs):
        pytest.fail("malformed cursor accessed the store")
    monkeypatch.setattr(rig.store, "connect", forbidden)
    with pytest.raises(ValueError, match="sec_research_cursor_invalid"):
        queries(rig).read(FILING_ID, cursor=edit_cursor(cursor, **changes))


def test_edited_out_of_section_byte_cursor_is_rejected(rig):
    rig.enqueue(b"<h1>Item 1. Business</h1><p>needle first</p><h1>Item 2. Properties</h1><p>needle second</p>")
    service(rig).refresh(FILING_ID)
    page = queries(rig).read(FILING_ID, section_id="item_2", max_chars=2)
    with pytest.raises(ValueError, match="sec_research_cursor_invalid"):
        queries(rig).read(FILING_ID, section_id="item_2", max_chars=2,
                          cursor=edit_cursor(page["next_cursor"], offset=0))


def test_unexpected_stored_error_is_content_free(rig, monkeypatch):
    def failed(*args, **kwargs):
        raise RuntimeError("PRIVATE storage details")
    monkeypatch.setattr(rig.store, "connect", failed)
    page = queries(rig).read(FILING_ID)
    assert page["status"] == "unavailable" and "PRIVATE" not in json.dumps(page)


def test_oversized_index_entry_does_not_hide_following_choices(rig):
    rig.enqueue(names=["actual.htm", "x" * 100000, "after.xml"])
    service(rig).refresh(FILING_ID)
    read = queries(rig)
    first = read.read(FILING_ID, max_chars=20000)
    blocked = read.read(FILING_ID, max_chars=20000, cursor=first["next_cursor"])
    assert blocked["status"] == "unavailable" and not blocked["coverage"]["complete"]
    assert blocked["gaps"] == [{"code": "document_index_entry_too_large"}]
    assert blocked["next_cursor"]
    after = read.read(FILING_ID, max_chars=20000, cursor=blocked["next_cursor"])
    assert [entry["name"] for entry in after["data"]["documents"]] == ["after.xml"]
    assert len(json.dumps(blocked, ensure_ascii=True).encode()) <= 256 * 1024


@pytest.mark.parametrize("requested,other", [
    ("primary", "file:actual.htm"), ("file:actual.htm", "primary"),
])
@pytest.mark.parametrize("failure", ["conflict", "early_cancel"])
def test_pre_resolution_failure_invalidates_both_observed_aliases(rig, requested, other, failure):
    from src.lifecycle_public_sources import SourceReadError

    rig.enqueue()
    captured = service(rig).refresh(FILING_ID)
    read = queries(rig)
    pinned = read.read(FILING_ID, capture_id=captured["capture_id"], query="needle")
    before = len(rig.requests)
    check = None
    if failure == "conflict":
        recent = rig.store.latest_receipt(CIK)["source_snapshots"]["submissions"]
        sid = bind_catalog(rig.store, rig.captures, history=HISTORY, bind=False, primary="other.htm")
        bindings = {"submissions": recent, HISTORY: {"snapshot_id": sid, "observed_at": NOW}}
        rig.store.record_receipt(CIK, status="ok", completed=list(bindings), pending=[], gaps=[],
                                 observed_at=NOW, source_snapshots=bindings)
    else:
        def check():
            raise SourceReadError("source_read_cancelled")
    failed = service(rig).refresh(FILING_ID, requested, check=check)
    assert failed["outcome"] == "no_dispatch" and failed["capture_id"] is None
    assert len(rig.requests) == before
    assert read.read(FILING_ID, document_id=requested)["status"] == "unavailable"
    assert read.read(FILING_ID, document_id=other)["status"] == "unavailable"
    assert failed["invalidation_primary_document"] == "actual.htm"
    assert failed["resolved_document_id"] is None and failed["primary_document"] is None
    assert read.read(FILING_ID, capture_id=captured["capture_id"], query="needle") == pinned
    assert read.read(FILING_ID, document_id="file:actual.htm", capture_id=captured["capture_id"],
                     query="needle")["data"]["passages"] == pinned["data"]["passages"]


@pytest.mark.parametrize("requested,other", [
    ("primary", "file:actual.htm"), ("file:actual.htm", "primary"),
])
def test_first_interruption_marker_invalidates_both_observed_aliases(rig, requested, other):
    rig.enqueue()
    captured = service(rig).refresh(FILING_ID)
    read = queries(rig)
    before = len(rig.requests)
    observed = []
    def interrupt():
        observed.append(read.read(FILING_ID, document_id=other)["status"])
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        service(rig).refresh(FILING_ID, requested, check=interrupt)
    assert observed == ["unavailable"]
    assert len(rig.requests) == before
    documents = owner("document_store").DocumentStore(rig.store)
    requested_attempt = documents.latest_attempt(FILING_ID, requested)
    assert documents.latest_attempt(FILING_ID, other) == requested_attempt
    assert requested_attempt["outcome"] == "interrupted" and requested_attempt["capture_id"] is None
    assert read.read(FILING_ID, document_id=other)["status"] == "unavailable"
    assert read.read(FILING_ID, capture_id=captured["capture_id"])["status"] == "ok"


def test_early_exhibit_failure_does_not_invalidate_primary(rig):
    from src.lifecycle_public_sources import SourceReadError

    rig.enqueue()
    primary = service(rig).refresh(FILING_ID)
    rig.enqueue()
    service(rig).refresh(FILING_ID, "file:exhibit.xml")
    def cancel():
        raise SourceReadError("source_read_cancelled")
    failed = service(rig).refresh(FILING_ID, "file:exhibit.xml", check=cancel)
    assert failed["outcome"] == "no_dispatch"
    assert queries(rig).read(FILING_ID)["data"]["document"]["capture_id"] == primary["capture_id"]
    assert queries(rig).read(FILING_ID, document_id="file:exhibit.xml")["status"] == "unavailable"


def test_old_primary_spelling_cannot_invalidate_newer_primary(rig):
    from src.lifecycle_public_sources import SourceReadError

    rig.enqueue()
    old = service(rig).refresh(FILING_ID)
    bind_catalog(rig.store, rig.captures, primary="new.htm")
    rig.enqueue(names=["new.htm", "actual.htm"])
    new = service(rig).refresh(FILING_ID)
    def cancel():
        raise SourceReadError("source_read_cancelled")
    service(rig).refresh(FILING_ID, "file:actual.htm", check=cancel)
    assert queries(rig).read(FILING_ID)["data"]["document"]["capture_id"] == new["capture_id"]
    assert queries(rig).read(FILING_ID, document_id="file:actual.htm")["status"] == "unavailable"
    assert queries(rig).read(FILING_ID, capture_id=old["capture_id"])["status"] == "ok"
