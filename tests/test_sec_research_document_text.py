"""Pure bounded extraction and unambiguous byte-addressed sections."""

from dataclasses import asdict
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from src import lifecycle_public_sources as public
from src.sec_research import document_text as mod
from tests.test_lifecycle_public_sources import NOW, Response, _reader


def extract(body, mime="text/html", check=lambda: None):
    return mod.extract_document_text(body, mime, check=check)


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
def test_sec_text_keeps_visible_ixbrl_and_hides_ix_hidden(mime):
    body = (b'<!DOCTYPE html><html><head><title>discard</title></head><body>'
            b'<ix:header><ix:resources>context data</ix:resources></ix:header>'
            b'<ix:hidden><ix:nonNumeric>secret</ix:nonNumeric></ix:hidden>'
            b'<h1>ITEM 1. BUSINESS</h1><p>Revenue <ix:nonFraction>123</ix:nonFraction>'
            b' and <ix:nonNumeric>visible</ix:nonNumeric>.</p><div hidden>hidden</div>'
            b'<script>bad()</script><p>Tail &amp; end.</p></body></html>')
    assert extract(body, mime) == ("ITEM 1. BUSINESS\nRevenue 123 and visible.\nTail & end.", mime)


@pytest.mark.parametrize("kind", ["html-nesting", "xml-nesting", "html-markup", "xml-markup", "events"])
def test_sec_parser_limits_fail_without_truncation(kind, monkeypatch):
    mime = "text/html"
    if kind.endswith("nesting"):
        body = b"<x>" * 513 + b"visible" + b"</x>" * 513
    elif kind.endswith("markup"):
        body = b'<x title="' + b"a" * (1024 * 1024) + b'">visible</x>'
    else:
        monkeypatch.setattr(mod, "MAX_PARSER_EVENTS", 20)
        body = b"visible" + b"<!-- event -->" * 21
    if kind.startswith("xml"):
        mime = "application/xml"
    with pytest.raises(public.SourceReadError, match="^source_document_complexity$"):
        extract(body, mime)


@pytest.mark.parametrize("mime,body", [
    ("text/html", b"<x>" * 512 + b"ok" + b"</x>" * 512),
    ("application/xml", b"<x>" * 512 + b"ok" + b"</x>" * 512),
    ("text/html", b"<p>" + b"abc " * 20000 + b"tail</p>"),
])
def test_admitted_documents_are_complete_at_nesting_limit(mime, body):
    text, actual_mime = extract(body, mime)
    assert actual_mime == mime
    assert ("ok" in text) if b"ok" in body else text.endswith("tail")


@pytest.mark.parametrize("mime", ["text/plain", "text/html", "application/xml"])
def test_canonical_utf8_limit_never_returns_truncated_success(mime, monkeypatch):
    monkeypatch.setattr(mod, "MAX_TEXT_BYTES", 64)
    body = ("\u00e9" * 33).encode("latin-1")
    if mime != "text/plain":
        body = b"<x>" + body + b"</x>"
    with pytest.raises(public.SourceReadError, match="^source_text_too_large$"):
        extract(body, mime + "; charset=iso-8859-1")


def test_plaintext_decoding_and_normalization_cross_chunk_boundaries():
    value = "Cafe\u0301\r\n" + "\u754c" * 22000 + "\t tail  \r\n end"
    assert extract(value.encode(), "text/plain") == (
        "Cafe\u0301\n" + "\u754c" * 22000 + " tail\nend", "text/plain")


def test_xml_keeps_namespaces_mixed_content_and_record_boundaries():
    body = (b'<root xmlns="urn:sec:test"><security id="a">Before <child>not</child> delisted.</security>'
            b'<security id="b">Active &amp; listed</security></root>')
    text, mime = extract(body, "application/xml")
    assert mime == "application/xml" and text.startswith("<root")
    root = ET.fromstring(text)
    assert [(row.attrib["id"], "".join(row.itertext())) for row in root] == [
        ("a", "Before not delisted."), ("b", "Active & listed")]


@pytest.mark.parametrize("body", [
    b'<!DOCTYPE x [<!ENTITY a "expanded">]><x>&a;</x>',
    b'<!DOCTYPE x SYSTEM "https://example.invalid/dtd"><x>text</x>',
    b'<x><unclosed></x>',
])
def test_xml_rejects_dtd_entities_and_malformed_document(body):
    with pytest.raises(public.SourceReadError, match="^source_document_invalid$"):
        extract(body, "application/xml")


@pytest.mark.parametrize("body,mime,code", [
    (b"%PDF-1.4", "application/pdf", "source_format_unsupported"),
    (b"unknown", "application/octet-stream", "source_format_unsupported"),
    (b"\xff", "text/plain", "source_encoding_unsupported"),
    (b"x", "text/plain; charset=not-a-codec", "source_encoding_unsupported"),
    (b" ", "text/plain", "source_text_empty"),
    (b"<ix:hidden>secret</ix:hidden>", "text/html", "source_text_empty"),
])
def test_unusable_formats_return_typed_content_free_errors(body, mime, code):
    with pytest.raises(public.SourceReadError, match=f"^{code}$"):
        extract(body, mime)


@pytest.mark.parametrize("charset,body", [
    ("base64_codec", b"dGV4dA=="), ("rot_13", b"text"),
    ("unicode_escape", b"\\ud800"),
])
@pytest.mark.parametrize("mime", ["text/plain", "text/html"])
def test_nontext_codecs_and_surrogates_return_typed_encoding_gap(charset, body, mime):
    with pytest.raises(public.SourceReadError, match="^source_encoding_unsupported$"):
        extract(body, mime + "; charset=" + charset)


@pytest.mark.parametrize("mime", ["text/html", "application/xml"])
def test_ignored_comments_still_consume_event_budget(mime, monkeypatch):
    monkeypatch.setattr(mod, "MAX_PARSER_EVENTS", 50)
    with pytest.raises(public.SourceReadError, match="^source_document_complexity$"):
        extract(b"<x>visible" + b"<!-- ignored -->" * 51 + b"</x>", mime)


def test_original_decoded_body_limit_applies_before_extraction(monkeypatch):
    monkeypatch.setattr(mod, "MAX_DOCUMENT_BYTES", 32)
    with pytest.raises(public.SourceReadError, match="^source_decoded_body_too_large$"):
        extract(b" " * 33, "text/plain")


def test_reader_callback_failure_never_publishes_observer_bytes(monkeypatch):
    reader, connections, _, _ = _reader(monkeypatch, [Response(b"document")])
    observations = []

    def extractor(body, mime, *, check):
        reader.request_stop()
        check()
        pytest.fail("cancelled extraction completed")

    reader.text_extractor = extractor
    reader.document_observer = lambda *args: observations.append(args)
    with pytest.raises(public.SourceReadError, match="^source_read_cancelled$"):
        reader.read("https://ir.example.com/document")
    assert observations == []
    assert reader.observations[-1].result_code == "source_read_cancelled"
    assert connections[0].closed


@pytest.mark.parametrize("operation", ["text/plain", "text/html", "application/xml", "index"])
def test_parsing_and_indexing_propagate_cancellation(operation):
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if calls == 5:
            raise public.SourceReadError("source_read_cancelled")

    with pytest.raises(public.SourceReadError, match="^source_read_cancelled$"):
        if operation == "index":
            mod.index_sections("ITEM 1. BUSINESS\n" + "line\n" * 10000, "10-K", check=check)
        else:
            extract(b"<x>" + b"content " * 30000 + b"</x>", operation, check)
    assert calls == 5


def test_ambiguous_toc_heading_does_not_fabricate_section():
    text = "TABLE OF CONTENTS\nITEM 1. BUSINESS\nITEM 1A. RISK FACTORS\nITEM 1. BUSINESS\nActual business.\nITEM 2. PROPERTIES\nOffices"
    sections, gaps = mod.index_sections(text, "10-K", check=lambda: None)
    assert {"code": "section_ambiguous", "section_id": "item_1"} in gaps
    assert "item_1" not in [row["section_id"] for row in sections]
    assert "item_1a" not in [row["section_id"] for row in sections]
    assert any(row["section_id"] == "item_2" for row in sections)


def test_section_offsets_are_exact_utf8():
    text = "Cover \u754c\nITEM 1. BUSINESS\nCaf\u00e9\nITEM 1A. RISK FACTORS\nRisks \u03bb"
    sections, gaps = mod.index_sections(text, "10-K", check=lambda: None)
    assert [row["section_id"] for row in sections] == ["item_1", "item_1a"]
    first, second = sections
    assert first == {"section_id": "item_1", "label": "ITEM 1. BUSINESS", "start_byte": 10, "end_byte": 33}
    assert text.encode()[first["start_byte"]:first["end_byte"]].decode() == "ITEM 1. BUSINESS\nCaf\u00e9\n"
    assert text.encode()[second["start_byte"]:second["end_byte"]].decode() == "ITEM 1A. RISK FACTORS\nRisks \u03bb"


@pytest.mark.parametrize("form", ["10-Q", "10-Q/A"])
def test_quarterly_items_are_scoped_to_unambiguous_parts(form):
    text = "PART I. FINANCIAL INFORMATION\nItem 1. Financial Statements\nOne\nPART II. OTHER INFORMATION\nItem 1. Legal Proceedings\nTwo"
    sections, gaps = mod.index_sections(text, form, check=lambda: None)
    assert [row["section_id"] for row in sections] == ["part_i", "part_i_item_1", "part_ii", "part_ii_item_1"]
    assert not any(row["code"] == "section_ambiguous" for row in gaps)
    first = sections[1]
    assert text.encode()[first["start_byte"]:first["end_byte"]].decode() == "Item 1. Financial Statements\nOne\n"


def test_quarterly_item_without_part_is_a_gap():
    sections, gaps = mod.index_sections("Item 1. Unknown part\nBody", "10-Q", check=lambda: None)
    assert sections == []
    assert {"code": "section_ambiguous", "section_id": "item_1"} in gaps


def test_current_report_numbered_headings_do_not_match_prose():
    text = "See Item 1.01 for context.\nItem 1.01 Entry into a Material Definitive Agreement\nTerms\nItem 9.01 Financial Statements and Exhibits\nExhibits"
    sections, gaps = mod.index_sections(text, "8-K", check=lambda: None)
    assert [row["section_id"] for row in sections] == ["item_1_01", "item_9_01"]


def test_unknown_form_keeps_text_and_exposes_no_guessed_index():
    text = "ITEM 1. Something\nWhole text is available"
    assert mod.index_sections(text, "F-1", check=lambda: None) == (
        [], [{"code": "section_index_unsupported", "section_id": None}])


def test_missing_sections_are_gaps_not_first_paragraphs():
    assert mod.index_sections("First paragraph only", "10-K", check=lambda: None) == (
        [], [{"code": "section_index_unavailable", "section_id": None}])


@pytest.mark.parametrize("custom", [False, True])
def test_default_public_reader_extraction_unchanged(monkeypatch, custom):
    body = b"<p>Legacy text</p><ix:hidden>retained by lifecycle</ix:hidden>"
    content_type = "text/html; charset=utf-8"
    reader, _, _, _ = _reader(monkeypatch, [Response(body, headers={"Content-Type": content_type})])
    calls = []

    def extractor(raw, header, *, check):
        calls.append((raw, header, check))
        check()
        return "Callback text", "text/plain"

    if custom:
        reader = public.PublicSourceReader(reader.limits, now=lambda: NOW, text_extractor=extractor)
    page = reader.read("https://ir.example.com/document")
    expected_text = "Callback text" if custom else "Legacy text\nretained by lifecycle"
    assert page.text == expected_text
    assert page.mime_type == ("text/plain" if custom else "text/html")
    assert page.body_sha256 == hashlib.sha256(body).hexdigest()
    assert page.text_sha256 == hashlib.sha256(expected_text.encode()).hexdigest()
    material = asdict(page)
    material.pop("capture_sha256")
    assert page.capture_sha256 == hashlib.sha256(json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    assert calls == ([(body, content_type, reader._remaining)] if custom else [])
