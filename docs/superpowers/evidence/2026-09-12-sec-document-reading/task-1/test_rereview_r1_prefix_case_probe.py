"""New resolver risk: distinct XHTML prefixes must not share bindings."""

import xml.etree.ElementTree as ET

from src.sec_research.document_text import extract_document_text


INLINE = "http://www.xbrl.org/2013/inlineXBRL"


def test_case_distinct_nested_prefix_does_not_rebind_inline_namespace():
    body = (
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        f'xmlns:ix="{INLINE}"><body><div xmlns:IX="urn:unrelated">'
        '<ix:header><ix:hidden>HIDDEN FACT</ix:hidden></ix:header>'
        '<p><IX:hidden>Visible unrelated</IX:hidden></p></div>'
        '<p>Visible tail</p></body></html>'
    ).encode()
    root = ET.fromstring(body)
    assert root.find(f".//{{{INLINE}}}hidden").text == "HIDDEN FACT"
    assert root.find(".//{urn:unrelated}hidden").text == "Visible unrelated"
    text, mime = extract_document_text(body, "application/xhtml+xml", check=lambda: None)
    assert mime == "application/xhtml+xml"
    assert text == "Visible unrelated\nVisible tail"


def test_case_distinct_namespace_declarations_are_not_conflicting():
    body = (
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        f'xmlns:ix="{INLINE}" xmlns:IX="urn:unrelated">'
        '<body><ix:header><ix:hidden>HIDDEN FACT</ix:hidden></ix:header>'
        '<p><IX:hidden>Visible unrelated</IX:hidden></p></body></html>'
    ).encode()
    root = ET.fromstring(body)
    assert root.find(f".//{{{INLINE}}}hidden").text == "HIDDEN FACT"
    assert root.find(".//{urn:unrelated}hidden").text == "Visible unrelated"
    assert extract_document_text(body, "application/xhtml+xml", check=lambda: None) == (
        "Visible unrelated", "application/xhtml+xml"
    )
