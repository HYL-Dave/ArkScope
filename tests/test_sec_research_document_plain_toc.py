"""Plain-label linked tables observed in the 2025 Apple 10-K hand test."""

import pytest

from src.sec_research import document_text as text_owner
from src.sec_research.tool_service import ToolService
from tests.test_sec_research_document_queries import queries
from tests.test_sec_research_document_service import FILING_ID, NOW, owner, rig
from tests.test_sec_research_document_toc import assert_citations, capture, read_section


# Preserve the observed div/span, wrapped-table, and split item/title/page links.
# Company prose is replaced with a small explicit fixture; no live SEC request.
TABLE = (
    b'<table><tr><td><div><span><a href="#part">Part I</a></span></div></td></tr>'
    b'<tr><td><div><span><a href="#one">Item 1.</a></span></div></td>'
    b'<td><div><span><a href="#one">Business</a></span></div></td>'
    b'<td><div><span><a href="#one">1</a></span></div></td></tr>'
    b'<tr><td><div><span><a href="#risks">Item 1A.</a></span></div></td>'
    b'<td><div><span><a href="#risks">Risk Factors</a></span></div></td>'
    b'<td><div><span><a href="#risks">2</a></span></div></td></tr></table>'
)
TITLE = b'<div><span>TABLE OF CONTENTS</span></div>'
BODY = (
    b'<div id="part"></div><div><span>Part I</span></div>'
    b'<div id="one"></div><div><span>Item 1.&#160;&#160;Business</span></div>'
    b'<p>Actual operations.</p><div id="risks"></div>'
    b'<div><span>Item 1A. Risk Factors</span></div><p>Distinctive operating risk.</p>'
)
TEXT = (
    'TABLE OF CONTENTS\nPart I\nItem 1.\nBusiness\n1\nItem 1A.\nRisk Factors\n2\n'
    'Part I\nItem 1. Business\nActual operations.\nItem 1A. Risk Factors\nDistinctive operating risk.'
)


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("title", [TITLE, b'<p><span>TABLE OF CONTENTS</span></p>'])
@pytest.mark.parametrize("wrapped", [False, True])
def test_plain_label_linked_table_preserves_real_body_sections(rig, mime, title, wrapped):
    table = b'<div>' + TABLE + b'</div>' if wrapped else TABLE
    body = title + table + BODY
    record = capture(rig, body, mime)
    assert rig.captures.read(record["original_sha256"]) == body
    assert rig.captures.read(record["text_sha256"]) == TEXT.encode()
    page = read_section(rig, record)
    assert page["status"] == "ok", page
    assert page["data"]["passages"][0]["text"] == 'Item 1. Business\nActual operations.\n'
    assert [section["section_id"] for section in record["metadata"]["sections"]] == [
        "part_i", "item_1", "item_1a"]
    assert record["metadata"]["section_gaps"] == []
    assert_citations(rig, record, page)


@pytest.mark.parametrize("prefix,table", [
    (TITLE + b'<p>Intervening body text.</p>', TABLE),
    (b'<div id="a" id="b"><span>TABLE OF CONTENTS</span></div>', TABLE),
    (b'<div xmlns="urn:foreign"><span>TABLE OF CONTENTS</span></div>', TABLE),
    (TITLE, b'<div id="a" id="b">' + TABLE + b'</div>'),
    (TITLE, b'<div xmlns="urn:foreign">' + TABLE + b'</div>'),
    (TITLE, TABLE.replace(b'href="#risks"', b'href="#one"')),
    (TITLE, TABLE.replace(b'href="#one"', b'href="https://example.invalid/one"')),
    (TITLE, TABLE.removesuffix(b'</table>')),
    (TITLE, TABLE.removesuffix(b'</table>') + BODY + b'</table>'),
])
def test_unverified_plain_label_table_never_excludes_body(rig, prefix, table):
    record = capture(rig, prefix + table + BODY)
    assert record["metadata"]["toc_ranges"] == []
    page = read_section(rig, record)
    assert page["status"] == "unavailable" and page["data"]["passages"] == []
    index = queries(rig).read(FILING_ID, capture_id=record["capture_id"])
    whole = queries(rig).read(FILING_ID, cursor=index["data"]["text_start_cursor"])
    assert 'Actual operations.' in whole["data"]["passages"][0]["text"]
    assert_citations(rig, record, whole)


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("tag", [
    "blockquote", "fieldset", "figure", "form", "header", "main", "pre", "x-label",
])
def test_plain_toc_label_rejects_non_inline_descendants(rig, mime, tag):
    title = f'<div><{tag}><span>TABLE OF CONTENTS</span></{tag}></div>'.encode()
    record = capture(rig, title + TABLE + BODY, mime)
    assert record["metadata"]["toc_ranges"] == []
    assert read_section(rig, record)["status"] == "unavailable"


@pytest.mark.parametrize("tag", [
    "a", "b", "em", "font", "i", "mark", "s", "small", "span", "strong", "sub", "sup", "u",
])
def test_plain_toc_label_retains_explicit_inline_descendants(rig, tag):
    title = f'<div><{tag}>TABLE OF CONTENTS</{tag}></div>'.encode()
    record = capture(rig, title + TABLE + BODY)
    assert record["metadata"]["toc_ranges"]
    assert read_section(rig, record)["status"] == "ok"
    assert rig.captures.read(record["text_sha256"]) == TEXT.encode()


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("tag", [
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
])
def test_plain_toc_label_rejects_void_descendants(rig, mime, tag):
    title = f'<div><span>TABLE OF CONTENTS</span><{tag}/></div>'.encode()
    record = capture(rig, title + TABLE + BODY, mime)
    assert record["metadata"]["toc_ranges"] == []
    assert read_section(rig, record)["status"] == "unavailable"


def test_plain_label_toc_does_not_remove_duplicate_body_veto(rig):
    record = capture(rig, TITLE + b'<div>' + TABLE + b'</div>' + BODY + BODY)
    assert record["metadata"]["toc_ranges"], record["metadata"]
    for section in ("part_i", "item_1", "item_1a"):
        page = read_section(rig, record, section)
        assert page["status"] == "unavailable" and not page["data"]["passages"]


def test_plain_item_link_allows_only_its_terminal_period_outside_anchor(rig):
    table = TABLE.replace(b'>Item 1.</a>', b'>Item 1</a>.')
    record = capture(rig, TITLE + b'<div>' + table + b'</div>' + BODY)
    page = read_section(rig, record)
    assert page["status"] == "ok", page
    assert rig.captures.read(record["text_sha256"]) == TEXT.encode()
    assert_citations(rig, record, page)


def test_plain_item_link_cannot_certify_unlinked_heading_words(rig):
    table = TABLE.replace(b'>Item 1.</a>', b'>Item 1.</a> Actual body heading')
    record = capture(rig, TITLE + b'<div>' + table + b'</div>' + BODY)
    assert record["metadata"]["toc_ranges"] == []
    assert read_section(rig, record)["status"] == "unavailable"


def test_plain_label_toc_reaches_model_read_with_exact_citations(rig):
    record = capture(rig, TITLE + b'<div>' + TABLE + b'</div>' + BODY)

    def forbidden():
        pytest.fail("stored tool read attempted a new acquisition")

    tool = ToolService(rig.store, acquisition_factory=forbidden, clock=lambda: NOW)
    arguments = dict(filing_id=FILING_ID, capture_id=record["capture_id"], freshness="stored")
    page = tool.invoke("read_sec_filing", {**arguments, "section_id": "item_1a"})
    assert page["status"] == "ok", page
    assert page["data"]["passages"][0]["text"] == 'Item 1A. Risk Factors\nDistinctive operating risk.'
    assert_citations(rig, record, page)
    found = tool.invoke("read_sec_filing", {**arguments, "query": "Distinctive operating risk"})
    assert found["data"]["passages"]
    assert_citations(rig, record, found)


def test_new_plain_label_index_never_rewrites_a_retained_capture(rig, monkeypatch):
    body = TITLE + b'<div>' + TABLE + b'</div>' + BODY
    seed = capture(rig, body)
    documents = owner("document_store").DocumentStore(rig.store)
    canonical = rig.captures.read(seed["text_sha256"])
    metadata = {**seed["metadata"], "extraction_version": "sec-document-text-v4",
                "observation_id": "retained-plain-label-v4", "toc_ranges": [], "structure_gaps": []}
    metadata["sections"], metadata["section_gaps"] = text_owner.index_sections(
        canonical.decode(), "10-K", check=lambda: None)
    old_id = documents.publish(directory={**seed["directory"], "observation_id": "retained-plain-label-v4"},
                               metadata=metadata)
    old = documents.capture(old_id)
    pinned = queries(rig).read(FILING_ID, capture_id=old_id, query="Actual")
    fresh = capture(rig, body)
    assert read_section(rig, fresh)["status"] == "ok"
    assert fresh["metadata"]["extraction_version"] == "sec-document-text-v5"
    assert fresh["text_sha256"] == old["text_sha256"]
    assert fresh["original_sha256"] == old["original_sha256"]
    assert documents.capture(old_id) == old

    def forbidden(*args, **kwargs):
        pytest.fail("retained capture was re-extracted or rewritten")

    monkeypatch.setattr(text_owner, "extract_document_text", forbidden)
    monkeypatch.setattr(text_owner, "index_sections", forbidden)
    monkeypatch.setattr(rig.store, "_write", forbidden)
    assert queries(rig).read(FILING_ID, capture_id=old_id, query="Actual") == pinned
    assert read_section(rig, old)["status"] == "unavailable"
    assert_citations(rig, old, pinned)
