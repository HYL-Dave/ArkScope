"""Structural exclusions through extraction, immutable capture, and pinned reads."""

import hashlib

import pytest

from src.sec_research import document_text as text_owner
from tests.test_sec_research_document_queries import queries
from tests.test_sec_research_document_service import FILING_ID, owner, rig, service


TOC = (b'<nav role="doc-toc"><h2>Table of Contents</h2>'
       b'<a href="#one">Item 1. Business</a></nav>')
BODY = b'<h2 id="one">Item 1. Business</h2><p>Actual operations.</p>'


def capture(rig, body, mime="text/html"):
    rig.enqueue(body, mime=mime)
    result = service(rig).refresh(FILING_ID)
    assert result["capture_id"], result
    return owner("document_store").DocumentStore(rig.store).capture(result["capture_id"])


def read_section(rig, record, section_id="item_1"):
    return queries(rig).read(FILING_ID, capture_id=record["capture_id"], section_id=section_id)


def assert_citations(rig, record, page):
    canonical = rig.captures.read(record["text_sha256"])
    assert hashlib.sha256(canonical).hexdigest() == record["text_sha256"]
    for passage in page["data"]["passages"]:
        cite = passage["citation"]
        assert canonical[cite["start_byte"]:cite["end_byte"]].decode() == passage["text"]
        assert cite["capture_id"] == record["capture_id"]
        assert cite["text_sha256"] == record["text_sha256"]
        assert cite["original_sha256"] == record["original_sha256"]
        assert cite["extraction_version"] == record["metadata"]["extraction_version"]


@pytest.mark.parametrize("opening", [b'<nav role="doc-toc">',
    b'<nav aria-label="Table of Contents">', b'<nav>'])
def test_semantic_toc_does_not_hide_real_10k_sections(rig, opening):
    record = capture(rig, TOC.replace(b'<nav role="doc-toc">', opening) + BODY)
    page = read_section(rig, record)
    assert page["data"]["passages"], page
    assert page["data"]["passages"][0]["text"] == "Item 1. Business\nActual operations."
    assert_citations(rig, record, page)


def test_linked_table_toc_has_structural_end(rig):
    toc = (b'<table><caption>Table of Contents</caption><tr><td>'
           b'<a href="#one">Item 1. Business</a></td></tr><tr><td>'
           b'<a href="#two">Item 2. Properties</a></td></tr></table>')
    record = capture(rig, toc + BODY + b'<h2 id="two">Item 2. Properties</h2><p>Offices.</p>')
    page = read_section(rig, record)
    assert page["data"]["passages"], page
    assert page["data"]["passages"][0]["text"] == "Item 1. Business\nActual operations.\n"
    assert read_section(rig, record, "item_2")["data"]["passages"][0]["text"] == "Item 2. Properties\nOffices."
    assert_citations(rig, record, page)


def test_unbounded_text_toc_remains_ambiguous(rig):
    record = capture(rig, b'<h2>Table of Contents</h2><p>Item 1. Business</p>' + BODY)
    page = read_section(rig, record)
    assert page["status"] == "unavailable" and page["data"]["passages"] == []
    assert {"code": "section_ambiguous", "section_id": "item_1"} in record["metadata"]["section_gaps"]


def test_body_duplicate_is_still_ambiguous(rig):
    record = capture(rig, TOC + BODY + b'<h2>Item 1. Business</h2><p>Duplicate body.</p>')
    page = read_section(rig, record)
    assert page["status"] == "unavailable" and page["data"]["passages"] == []
    assert {"code": "section_ambiguous", "section_id": "item_1"} in record["metadata"]["section_gaps"]


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
def test_toc_keeps_full_text_and_exact_utf8_ranges(rig, mime):
    body = ('<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Cover \u754c</p>'
            '<NAV ROLE="doc-toc"><H2>Table of Contents</H2><div><a href="#one">'
            'Item 1. Caf\u00e9</a></div></NAV><H2 id="one">Item 1. Caf\u00e9</H2>'
            '<p>Actual \u71df\u904b \u03bb.</p></body></html>').encode()
    expected = 'Cover \u754c\nTable of Contents\nItem 1. Caf\u00e9\nItem 1. Caf\u00e9\nActual \u71df\u904b \u03bb.'
    record = capture(rig, body, mime)
    canonical = rig.captures.read(record["text_sha256"])
    assert canonical == expected.encode()
    assert rig.captures.read(record["original_sha256"]) == body
    assert record["metadata"]["extraction_version"] == "sec-document-text-v5"
    ranges = record["metadata"]["toc_ranges"]
    assert len(ranges) == 1
    start, end = ranges[0]["start_byte"], ranges[0]["end_byte"]
    assert canonical[start:end].decode() == 'Table of Contents\nItem 1. Caf\u00e9'
    assert (start, end) == (len('Cover \u754c\n'.encode()), len('Cover \u754c\nTable of Contents\nItem 1. Caf\u00e9'.encode()))
    index = queries(rig).read(FILING_ID, capture_id=record["capture_id"])
    whole = queries(rig).read(FILING_ID, cursor=index["data"]["text_start_cursor"])
    assert whole["data"]["passages"][0]["text"] == expected
    assert_citations(rig, record, whole)
    section = read_section(rig, record)
    assert section["data"]["passages"][0]["text"] == 'Item 1. Caf\u00e9\nActual \u71df\u904b \u03bb.'
    assert_citations(rig, record, section)


def test_old_capture_unchanged_after_toc_refresh(rig, monkeypatch):
    body = TOC + BODY
    seed = capture(rig, body)
    documents = owner("document_store").DocumentStore(rig.store)
    metadata = dict(seed["metadata"])
    metadata.pop("toc_ranges", None)
    metadata.pop("structure_gaps", None)
    metadata["extraction_version"] = "sec-document-text-v3"
    metadata["observation_id"] = "retained-v3-fixture"
    canonical = rig.captures.read(seed["text_sha256"])
    metadata["sections"], metadata["section_gaps"] = text_owner.index_sections(
        canonical.decode(), "10-K", check=lambda: None)
    directory = {**seed["directory"], "observation_id": "retained-v3-fixture"}
    old_id = documents.publish(directory=directory, metadata=metadata)
    old = documents.capture(old_id)
    pinned = queries(rig).read(FILING_ID, capture_id=old_id, query="Actual")
    assert pinned["data"]["passages"]
    fresh = capture(rig, body)
    assert read_section(rig, fresh)["data"]["passages"], "new structural index unavailable"
    assert fresh["text_sha256"] == old["text_sha256"]
    assert fresh["original_sha256"] == old["original_sha256"]
    assert documents.capture(old_id) == old

    def forbidden(*args, **kwargs):
        pytest.fail("retained capture was re-extracted or rewritten")

    monkeypatch.setattr(text_owner, "extract_document_text", forbidden)
    monkeypatch.setattr(text_owner, "index_sections", forbidden)
    monkeypatch.setattr(rig.store, "_write", forbidden)
    reopened = owner("document_queries").DocumentQueries(rig.store, rig.captures)
    assert reopened.read(FILING_ID, capture_id=old_id, query="Actual") == pinned
    assert read_section(rig, old)["status"] == "unavailable"
    assert_citations(rig, old, pinned)


@pytest.mark.parametrize("toc", [
    b'<body role="doc-toc"><h2>Table of Contents</h2>' + BODY + b'</body>',
    b'<div role="doc-toc"><h2>Table of Contents</h2>' + BODY + b'</div>',
    b'<nav role="doc-toc"><h2>Table of Contents</h2>' + BODY,
    b'<nav role="doc-toc"><h2>Table of Contents</h2><div>Item 1. Business</nav>' + BODY,
    TOC[:-6] + BODY + b'</nav><p>Tail</p>',
    b'<table><caption>Table of Contents</caption><tr><td><a href="#one">Item 1. Business</a></td></tr></table>' + BODY,
    b'<table><caption>Table of Contents</caption><tr><td><a href="https://example.invalid/#one">Item 1. Business</a>'
    b'</td></tr><tr><td><a href="#two">Item 2. Properties</a></td></tr></table>' + BODY,
])
def test_unverified_structure_has_gap_and_keeps_full_text(rig, toc):
    record = capture(rig, toc)
    assert read_section(rig, record)["data"]["passages"] == []
    assert record["metadata"].get("structure_gaps"), record["metadata"]
    assert record["metadata"]["toc_ranges"] == []
    assert b"Actual operations." in rig.captures.read(record["text_sha256"])


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
def test_foreign_namespace_is_not_semantic_html(rig, mime):
    record = capture(rig, TOC.replace(b'<nav ', b'<nav xmlns="urn:foreign" ') + BODY, mime)
    assert read_section(rig, record)["data"]["passages"] == []


@pytest.mark.parametrize("chunk", [1, 7, 65536])
def test_observer_runs_once_after_complete_extraction(chunk, monkeypatch):
    import inspect

    assert "structure_observer" in inspect.signature(text_owner.extract_document_text).parameters
    monkeypatch.setattr(text_owner, "_CHUNK", chunk)
    observed = []
    text, mime = text_owner.extract_document_text(TOC + BODY, "text/html", check=lambda: None,
                                                structure_observer=observed.append)
    assert mime == "text/html" and len(observed) == 1
    assert observed[0] == {"toc_ranges": [{"start_byte": 0, "end_byte": 34}], "structure_gaps": []}
    assert text == "Table of Contents\nItem 1. Business\nItem 1. Business\nActual operations."
    sections, gaps = text_owner.index_sections(text, "10-K", check=lambda: None,
                                               toc_ranges=observed[0]["toc_ranges"])
    assert [s["section_id"] for s in sections] == ["item_1"] and gaps == []
    assert text_owner.index_sections(text, "10-K", check=lambda: None)[0] == []


def test_observer_never_receives_partial_extraction(monkeypatch):
    import inspect
    from src.lifecycle_public_sources import SourceReadError

    assert "structure_observer" in inspect.signature(text_owner.extract_document_text).parameters
    monkeypatch.setattr(text_owner, "_CHUNK", 7)
    observed = []
    with pytest.raises(SourceReadError, match="source_encoding_unsupported"):
        text_owner.extract_document_text(TOC + BODY + b'\xff', "text/html", check=lambda: None,
                                         structure_observer=observed.append)
    assert observed == []


@pytest.mark.parametrize("toc", [
    b'<h2>Table of Contents</h2><table><tr><td><a href="#one">Item 1. Business</a></td></tr>'
    b'<tr><td><a href="#two">Item 2. Properties</a></td></tr></table>',
    b'<nav role="doc-toc"><div><h2>Table of Contents</h2><ul><li>'
    b'<a href="#one"><span>Item 1. Business</span></a></li></ul></div></nav>',
    b'<H:nav xmlns:H="http://www.w3.org/1999/xhtml" role="doc-toc">'
    b'<h2>Table of Contents</h2><a href="#one">Item 1. Business</a></H:nav>',
    b'<nav role="doc-toc"><nav aria-label="Table of Contents">'
    b'<h2>Table of Contents</h2><a href="#one">Item 1. Business</a></nav></nav>',
])
def test_nested_and_adjacent_structural_containers(rig, toc):
    record = capture(rig, toc + BODY, "application/xhtml+xml")
    page = read_section(rig, record)
    assert page["data"]["passages"], page
    assert page["data"]["passages"][0]["text"] == "Item 1. Business\nActual operations."
    assert_citations(rig, record, page)


def test_plain_body_is_not_excluded(rig):
    record = capture(rig, BODY)
    assert record["metadata"]["toc_ranges"] == []
    page = read_section(rig, record)
    assert page["data"]["passages"][0]["text"] == "Item 1. Business\nActual operations."
    assert_citations(rig, record, page)


@pytest.mark.parametrize("failure", ["cancel", "events", "nesting"])
def test_structural_observation_keeps_parser_bounds(monkeypatch, failure):
    from src.lifecycle_public_sources import SourceReadError

    observed = []
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if failure == "cancel" and calls == 30:
            raise SourceReadError("source_read_cancelled")

    body = TOC + BODY
    if failure == "events":
        monkeypatch.setattr(text_owner, "MAX_PARSER_EVENTS", 20)
    elif failure == "nesting":
        body = b'<div>' * 513 + body + b'</div>' * 513
    code = "source_read_cancelled" if failure == "cancel" else "source_document_complexity"
    with pytest.raises(SourceReadError, match=code):
        text_owner.extract_document_text(body, "text/html", check=check, structure_observer=observed.append)
    assert observed == []


def linked_heading(label, href, direction):
    anchor = b'<a href="' + href + b'">'
    if direction == "anchor-heading":
        return anchor + b'<h2>' + label + b'</h2></a>'
    return b'<h2>' + anchor + label + b'</a></h2>'


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("direction", ["anchor-heading", "heading-anchor"])
def test_external_heading_link_keeps_body_duplicate_ambiguous(rig, mime, direction):
    wrapped = linked_heading(b'Item 1. Business', b'https://example.invalid/body', direction)
    body = TOC[:-6] + wrapped + b'<p>Actual operations.</p></nav>' + BODY.replace(
        b'Actual operations.', b'Duplicate body.')
    record = capture(rig, body, mime)
    page = read_section(rig, record)
    assert page["status"] == "unavailable" and not page["data"]["passages"], page
    assert record["metadata"]["toc_ranges"] == []
    assert record["metadata"]["structure_gaps"]
    assert {"code": "section_ambiguous", "section_id": "item_1"} in record["metadata"]["section_gaps"]
    whole = queries(rig).read(FILING_ID, cursor=page["data"]["text_start_cursor"])
    expected = ('Table of Contents\nItem 1. Business\nItem 1. Business\n'
                'Actual operations.\nItem 1. Business\nDuplicate body.')
    assert whole["data"]["passages"][0]["text"] == expected
    assert rig.captures.read(record["original_sha256"]) == body
    assert_citations(rig, record, whole)


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("invalid_link", [
    b'<a href="https://example.invalid/one" href="#one">Item 1. Business</a>',
    b'<a href="#one" href="https://example.invalid/one">Item 1. Business</a>',
    b'<a href="#one"><span id="a" id="b">Item 1. Business</span></a>',
    b'<span id="a" id="b"><a href="#one">Item 1. Business</a></span>',
])
def test_invalid_descendant_attributes_cannot_certify_table(rig, mime, invalid_link):
    toc = (b'<table><caption>Table of Contents</caption><tr><td>' + invalid_link
           + b'</td></tr><tr><td><a href="#two">Item 2. Properties</a></td></tr>'
           b'<tr><td><a href="#three">Item 3. Legal Proceedings</a></td></tr></table>')
    record = capture(rig, toc + BODY, mime)
    assert record["metadata"]["toc_ranges"] == [], record["metadata"]
    assert record["metadata"]["structure_gaps"]
    page = read_section(rig, record)
    assert page["status"] == "unavailable" and not page["data"]["passages"]
    assert {"code": "section_ambiguous", "section_id": "item_1"} in record["metadata"]["section_gaps"]
    whole = queries(rig).read(FILING_ID, cursor=page["data"]["text_start_cursor"])
    assert whole["data"]["passages"][0]["text"] == (
        'Table of Contents\nItem 1. Business\nItem 2. Properties\n'
        'Item 3. Legal Proceedings\nItem 1. Business\nActual operations.')
    assert_citations(rig, record, whole)


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("direction", ["anchor-heading", "heading-anchor"])
@pytest.mark.parametrize("kind", ["Item 1. Business", "Part I"])
def test_valid_local_heading_link_membership(rig, mime, direction, kind):
    toc = (b'<nav role="doc-toc"><h2>Table of Contents</h2>'
           + linked_heading(kind.encode(), b'#target', direction) + b'</nav>')
    body = b'<h2>Part I</h2>' + BODY
    record = capture(rig, toc + body, mime)
    page = read_section(rig, record)
    assert page["data"]["passages"], page
    assert page["data"]["passages"][0]["text"] == 'Item 1. Business\nActual operations.'
    assert record["metadata"]["structure_gaps"] == []
    assert len(record["metadata"]["toc_ranges"]) == 1
    part = read_section(rig, record, "part_i")
    assert part["data"]["passages"][0]["text"] == 'Part I\nItem 1. Business\nActual operations.'
    assert_citations(rig, record, page)
    assert_citations(rig, record, part)


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("item_count", [1, 2])
def test_part_membership_does_not_replace_table_item_threshold(rig, mime, item_count):
    toc = (b'<table><caption>Table of Contents</caption><tr><td>'
           + linked_heading(b'Part I', b'#part', "heading-anchor")
           + b'</td></tr><tr><td><a href="#one">Item 1. Business</a></td></tr>')
    if item_count == 2:
        toc += b'<tr><td><a href="#two">Item 2. Properties</a></td></tr>'
    record = capture(rig, toc + b'</table><h2>Part I</h2>' + BODY, mime)
    page = read_section(rig, record)
    if item_count == 1:
        assert record["metadata"]["toc_ranges"] == []
        assert record["metadata"]["structure_gaps"]
        assert page["status"] == "unavailable" and not page["data"]["passages"]
    else:
        assert page["data"]["passages"], page
        assert page["data"]["passages"][0]["text"] == 'Item 1. Business\nActual operations.'
        assert record["metadata"]["structure_gaps"] == []
        assert_citations(rig, record, page)


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
def test_linked_part_toc_preserves_body_duplicate_veto(rig, mime):
    toc = (b'<nav role="doc-toc"><h2>Table of Contents</h2>'
           b'<h3><a href="#part">Part I</a></h3><div>'
           b'<a href="#one">Item 1. Business</a></div></nav>')
    record = capture(rig, toc + b'<h2>Part I</h2>' + BODY + b'<h2>Part I</h2>' + BODY, mime)
    assert record["metadata"]["toc_ranges"], record["metadata"]
    for section in ("part_i", "item_1"):
        page = read_section(rig, record, section)
        assert page["status"] == "unavailable" and not page["data"]["passages"]
        assert {"code": "section_ambiguous", "section_id": section} in record["metadata"]["section_gaps"]


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
@pytest.mark.parametrize("wrapped", [
    b'<a href="#one"><h2>Item 1. Business</h2><p>Actual operations.</p></a>',
    b'<h2><a href="#one">Item 1.</a> Business</h2><p>Actual operations.</p>',
    b'<a href="#one"><h2>Item 1. Business</h2><h2>Item 1. Business</h2></a>'
    b'<p>Actual operations.</p>',
])
def test_local_link_must_match_complete_single_heading(rig, mime, wrapped):
    record = capture(rig, TOC[:-6] + wrapped + b'</nav>' + BODY.replace(
        b'Actual operations.', b'Duplicate body.'), mime)
    page = read_section(rig, record)
    assert page["status"] == "unavailable" and not page["data"]["passages"], page
    assert record["metadata"]["toc_ranges"] == []
    assert record["metadata"]["structure_gaps"]
    assert {"code": "section_ambiguous", "section_id": "item_1"} in record["metadata"]["section_gaps"]
    whole = queries(rig).read(FILING_ID, cursor=page["data"]["text_start_cursor"])
    assert 'Actual operations.' in whole["data"]["passages"][0]["text"]
    assert 'Duplicate body.' in whole["data"]["passages"][0]["text"]
    assert_citations(rig, record, whole)
