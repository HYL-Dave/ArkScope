"""Focused offline probes for concrete Task 1 review doubts only."""

import pytest

from src.sec_research.document_text import extract_document_text, index_sections


@pytest.mark.parametrize("mime", ["text/html", "application/xhtml+xml"])
def test_namespace_aliased_ixbrl_does_not_publish_hidden_facts(mime):
    body = (
        b'<html xmlns="http://www.w3.org/1999/xhtml" '
        b'xmlns:inl="http://www.xbrl.org/2013/inlineXBRL"><body>'
        b'<inl:header><inl:hidden>'
        b'<inl:nonNumeric name="Example" contextRef="c">HIDDEN FACT</inl:nonNumeric>'
        b'</inl:hidden></inl:header>'
        b'<p>Visible <inl:nonNumeric name="Example" contextRef="c">fact</inl:nonNumeric>.</p>'
        b'</body></html>'
    )
    text, actual_mime = extract_document_text(body, mime, check=lambda: None)
    assert actual_mime == mime
    assert text == "Visible fact."


def test_duplicate_inside_toc_does_not_authorize_later_toc_only_item():
    text = (
        "TABLE OF CONTENTS\n"
        "ITEM 1. BUSINESS\n"
        "ITEM 1. BUSINESS\n"
        "ITEM 1A. RISK FACTORS\n"
        "10\n"
        "ITEM 2. PROPERTIES\n"
        "11\n"
    )
    sections, gaps = index_sections(text, "10-K", check=lambda: None)
    assert not sections, (sections, gaps)
    assert {"code": "section_ambiguous", "section_id": "item_1a"} in gaps
