"""Source transport contracts through the real stdlib HTTP response parser."""

import gzip
import hashlib
import http.client
import io
import json
import xml.etree.ElementTree as ET

import pytest

from src.lifecycle_public_sources import SourceReadError
from tests.test_lifecycle_public_sources import Response, _reader, deny_real_network


class BufferedSocket:
    def __init__(self, message):
        self.message = message

    def makefile(self, mode):
        return io.BytesIO(self.message)


def _wire_reader(monkeypatch, payload, *headers, **limits):
    response = http.client.HTTPResponse(BufferedSocket(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\n"
        + b"\r\n".join(header.encode() for header in headers)
        + b"\r\nConnection: close\r\n\r\n" + payload
    ))
    response.begin()
    return _reader(monkeypatch, [response], **limits)[0]


@pytest.mark.parametrize("chunked", [False, True])
def test_complete_gzip_uses_encoded_length_and_preserves_decoded_document(monkeypatch, chunked):
    body = ("A complete issuer notice. " * 200 + "\u66f4\u540d\u672b\u6bb5").encode()
    encoded = gzip.compress(body)
    payload = (f"{len(encoded):x}\r\n".encode() + encoded + b"\r\n0\r\n\r\n") if chunked else encoded
    framing = "Transfer-Encoding: chunked" if chunked else f"Content-Length: {len(encoded)}"
    reader = _wire_reader(monkeypatch, payload, framing, "Content-Encoding: gzip")
    page = reader.read("https://ir.example.com/notice")
    assert page.text == body.decode()
    assert page.body_sha256 == hashlib.sha256(body).hexdigest()
    observation = reader.observations[-1]
    assert observation.received_body_bytes == len(encoded)
    assert observation.decoded_body_bytes == len(body)
    assert observation.result_code == "complete"
    assert observation.framing == ("chunked" if chunked else "content_length")


def test_identical_repeated_content_lengths_are_normalized_not_rejected(monkeypatch):
    body = b"Complete notice."
    reader = _wire_reader(monkeypatch, body, f"Content-Length: {len(body)}", f"Content-Length: {len(body)}")
    assert reader.read("https://ir.example.com/notice").text == body.decode()
    assert reader.observations[-1].declared_body_bytes == len(body)


def test_normalized_content_length_does_not_consume_bytes_after_the_document(monkeypatch):
    body = b"Complete notice."
    reader = _wire_reader(monkeypatch, body + b"unrelated trailing bytes", f"Content-Length: {len(body)}, {len(body)}")
    assert reader.read("https://ir.example.com/notice").text == body.decode()
    assert reader.observations[-1].received_body_bytes == len(body)


def test_chunked_optional_whitespace_is_decoded_by_the_wire_parser(monkeypatch):
    reader = _wire_reader(monkeypatch, b"10\r\nComplete notice.\r\n0\r\n\r\n", "Transfer-Encoding: chunked ")
    assert reader.read("https://ir.example.com/notice").text == "Complete notice."


def test_gzip_concatenated_members_do_not_drop_the_last_member(monkeypatch):
    encoded = gzip.compress(b"Issuer notice. ") + gzip.compress(b"Not delisted.")
    reader = _wire_reader(monkeypatch, encoded, f"Content-Length: {len(encoded)}", "Content-Encoding: gzip")
    assert reader.read("https://ir.example.com/notice").text == "Issuer notice. Not delisted."


def test_xml_timeout_is_not_reclassified_as_invalid_document():
    from src.lifecycle_public_sources import _page_text
    def timeout():
        raise SourceReadError("source_read_timeout")
    with pytest.raises(SourceReadError, match="^source_read_timeout$"):
        _page_text(b"<notice>Complete</notice>", "application/xml", check=timeout)


@pytest.mark.parametrize("headers", [
    ("Transfer-Encoding: chunked", "Content-Length: 200"),
    ("Content-Length: 16", "Content-Length: 17"),
    ("Transfer-Encoding: gzip, chunked",),
])
def test_ambiguous_framing_is_not_reported_as_a_short_document(monkeypatch, headers):
    reader = _wire_reader(monkeypatch, b"10\r\nComplete notice.\r\n0\r\n\r\n", *headers)
    with pytest.raises(SourceReadError, match="^source_framing_invalid$"):
        reader.read("https://ir.example.com/notice")
    assert reader.observations[-1].received_body_bytes == 0
    assert reader.observations[-1].result_code == "source_framing_invalid"


@pytest.mark.parametrize("payload", [b"10\r\nshort", b"10\r\nComplete notice.\r\n"])
def test_missing_chunk_terminator_is_transport_incomplete(monkeypatch, payload):
    reader = _wire_reader(monkeypatch, payload, "Transfer-Encoding: chunked")
    with pytest.raises(SourceReadError, match="^source_body_incomplete$"):
        reader.read("https://ir.example.com/notice")
    assert reader.observations[-1].result_code == "source_body_incomplete"


@pytest.mark.parametrize("change,reason", [
    (lambda value: value[:-8], "source_compression_incomplete"),
    (lambda value: value[:-8] + b"bad-crc!", "source_compression_invalid"),
    (lambda value: b"not gzip", "source_compression_invalid"),
])
def test_complete_wire_body_does_not_hide_damaged_gzip(monkeypatch, change, reason):
    payload = change(gzip.compress(b"Complete notice."))
    reader = _wire_reader(monkeypatch, payload, f"Content-Length: {len(payload)}", "Content-Encoding: gzip")
    with pytest.raises(SourceReadError, match=f"^{reason}$"):
        reader.read("https://ir.example.com/notice")


def test_decoded_size_budget_is_separate_and_never_returns_a_prefix(monkeypatch):
    body = b"A" * 100000
    encoded = gzip.compress(body)
    reader = _wire_reader(monkeypatch, encoded, f"Content-Length: {len(encoded)}", "Content-Encoding: gzip",
                          max_response_bytes=1000, max_decoded_bytes=99999)
    with pytest.raises(SourceReadError, match="^source_decoded_body_too_large$"):
        reader.read("https://ir.example.com/notice")
    assert reader.observations[-1].decoded_body_bytes == 100000
    reader = _wire_reader(monkeypatch, encoded, f"Content-Length: {len(encoded)}", "Content-Encoding: gzip",
                          max_response_bytes=1000, max_decoded_bytes=100000)
    assert reader.read("https://ir.example.com/notice").text == body.decode()


def test_source_diagnostics_do_not_contain_arbitrary_headers_or_body(monkeypatch):
    reader, _, _, _ = _reader(monkeypatch, [Response(status=403, headers={
        "Set-Cookie": "secret", "X-Debug": "private-token", "Content-Length": "1000",
    })])
    with pytest.raises(SourceReadError, match="^source_unavailable$"):
        reader.read("https://ir.example.com/notice")
    from dataclasses import asdict
    diagnostic = asdict(reader.observations[-1])
    assert diagnostic["status"] == 403
    assert diagnostic["received_body_bytes"] == 0
    assert diagnostic["result_code"] == "source_unavailable"
    assert not any(value in json.dumps(diagnostic) for value in ("secret", "private-token", "notice", "https://"))


def test_html_retains_paragraph_boundaries_and_tail_without_hidden_text(monkeypatch):
    body = b"<article><h1>Issuer notice</h1><p>First paragraph.</p><p hidden>Private script</p><p>Not delisted.</p></article>"
    reader, _, _, _ = _reader(monkeypatch, [Response(body, headers={"Content-Type": "text/html"})])
    assert reader.read("https://ir.example.com/notice").text == "Issuer notice\nFirst paragraph.\nNot delisted."


def test_form25_xml_preserves_security_class_and_named_fields(monkeypatch):
    body = b'''<?xml version="1.0"?><edgarSubmission xmlns="urn:sec:test">
      <issuerName>Example Inc.</issuerName><exchange>NASDAQ</exchange>
      <descriptionClassSecurity>8.25% Senior Notes due 2028</descriptionClassSecurity>
      <effectiveDate>2026-09-01</effectiveDate></edgarSubmission>'''
    reader, _, _, _ = _reader(monkeypatch, [Response(body, headers={"Content-Type": "application/xml"})])
    text = reader.read("https://ir.example.com/notice").text
    root = ET.fromstring(text)
    assert root.findtext("{urn:sec:test}descriptionClassSecurity") == "8.25% Senior Notes due 2028"
    assert root.findtext("{urn:sec:test}effectiveDate") == "2026-09-01"
    assert root.findtext("{urn:sec:test}issuerName") == "Example Inc."
    assert "common stock" not in text


def test_xml_normalization_preserves_record_boundaries_without_repeating_long_names():
    from src.lifecycle_public_sources import _page_text
    name = "longField" + "x" * 8192
    attributes = " ".join(f'a{index}="value{index}"' for index in range(256))
    body = (f'<root><{name} {attributes}>Before <child>not</child> delisted.</{name}>'
            '<security><class>notes</class><status>delisted</status></security>'
            '<security><class>common stock</class><status>active</status></security></root>').encode()
    text, _ = _page_text(body, "application/xml")
    assert len(text.encode()) <= len(body) * 2
    root = ET.fromstring(text)
    field = root.find(name)
    assert field.attrib["a255"] == "value255"
    assert "".join(field.itertext()) == "Before not delisted."
    assert [(record.findtext("class"), record.findtext("status")) for record in root.findall("security")] == [
        ("notes", "delisted"), ("common stock", "active"),
    ]


@pytest.mark.parametrize("body", [
    b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x>&secret;</x>',
    b'<!DOCTYPE x [<!ENTITY a "expanded">]><x>&a;</x>',
    b'<x><unclosed></x>',
])
def test_xml_dtd_entities_and_malformed_documents_are_rejected(monkeypatch, body):
    reader, _, _, _ = _reader(monkeypatch, [Response(body, headers={"Content-Type": "application/xml"})])
    with pytest.raises(SourceReadError, match="^source_document_invalid$"):
        reader.read("https://ir.example.com/notice")


def test_structured_json_is_retained_with_keys_not_misread_as_html(monkeypatch):
    body = json.dumps({"directory": {"item": [{"name": "primary_doc.xml", "size": 1024}]}}).encode()
    reader, _, _, _ = _reader(monkeypatch, [Response(body, headers={"Content-Type": "application/json"})])
    page = reader.read("https://ir.example.com/index.json")
    assert json.loads(page.text)["directory"]["item"][0]["name"] == "primary_doc.xml"


@pytest.mark.parametrize("body", [b'{"a":1,"a":2}', b'{"a": NaN}', b'{"a":'])
def test_invalid_or_ambiguous_json_is_not_converted_to_evidence(monkeypatch, body):
    reader, _, _, _ = _reader(monkeypatch, [Response(body, headers={"Content-Type": "application/json"})])
    with pytest.raises(SourceReadError, match="^source_document_invalid$"):
        reader.read("https://ir.example.com/index.json")
