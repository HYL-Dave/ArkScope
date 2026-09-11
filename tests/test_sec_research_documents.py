"""Observed filenames, exact accession binding and immutable directory provenance."""

from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from src.sec_research.common import SourceError
from src.sec_research import documents as mod


FILING_ID = "0000320193:0000950170-26-000001"
DIRECTORY_PATH = "/Archives/edgar/data/320193/000095017026000001"
ROOT_URL = "https://www.sec.gov" + DIRECTORY_PATH + "/"


def directory(items, *, path=DIRECTORY_PATH):
    return json.dumps({"directory": {"name": path, "item": items}}).encode()


@pytest.mark.parametrize("name,path", [
    ("../other.htm", DIRECTORY_PATH), ("/other.htm", DIRECTORY_PATH),
    ("a/b.htm", DIRECTORY_PATH), ("a\\b.htm", DIRECTORY_PATH),
    ("%2e%2e.htm", DIRECTORY_PATH), ("a%252f.htm", DIRECTORY_PATH),
    ("a.htm?x=1", DIRECTORY_PATH), ("a.htm#x", DIRECTORY_PATH),
    ("https:other.htm", DIRECTORY_PATH), ("a\n.htm", DIRECTORY_PATH),
    ("a b.htm", DIRECTORY_PATH), (".", DIRECTORY_PATH), ("..", DIRECTORY_PATH),
    ("primary.htm", "/Archives/edgar/data/320193/000095017026000002"),
    ("primary.htm", "/Archives/edgar/data/1/000095017026000001"),
    ("primary.htm", "https://www.sec.gov" + DIRECTORY_PATH),
])
def test_directory_rejects_escape_and_cross_accession(name, path):
    with pytest.raises(SourceError):
        mod.parse_document_directory(directory([{"name": name, "type": "text.htm"}], path=path),
                                     filing_id=FILING_ID)


def test_directory_keeps_actual_document_ids_and_unknown_size():
    raw = directory([
        {"name": "report.htm", "type": "text.htm", "size": "123"},
        {"name": "exhibit.xml", "type": "text.xml", "size": ""},
        {"name": "notes.txt", "type": "text.txt"},
        {"name": "zero.txt", "type": "text.txt", "size": 0},
        {"name": "unknown.pdf", "type": "text.pdf", "size": None},
        {"name": "subdirectory", "type": "dir", "size": ""},
    ])
    result = mod.parse_document_directory(raw, filing_id=FILING_ID)
    assert [(row.document_id, row.size_bytes) for row in result.entries] == [
        ("file:report.htm", 123), ("file:exhibit.xml", None), ("file:notes.txt", None),
        ("file:zero.txt", 0), ("file:unknown.pdf", None),
    ]
    assert result.sha256 == hashlib.sha256(raw).hexdigest()
    assert result.url == ROOT_URL + "index.json"
    assert (result.filing_id, result.cik, result.accession) == (
        FILING_ID, "0000320193", "0000950170-26-000001")
    for index, row in enumerate(result.entries):
        assert row.url == ROOT_URL + row.name
        assert row.source.pointer == f"/directory/item/{index}"
        assert row.source.sha256 == result.sha256
        with pytest.raises(FrozenInstanceError):
            row.name = "changed.htm"
    with pytest.raises(FrozenInstanceError):
        result.entries = ()


def test_accession_filer_prefix_need_not_equal_issuer():
    assert mod.parse_filing_id(FILING_ID) == ("0000320193", "0000950170-26-000001")
    assert mod.directory_url(FILING_ID) == ROOT_URL + "index.json"


@pytest.mark.parametrize("value", [
    None, 1, "", "320193:0000950170-26-000001", "0000000000:0000950170-26-000001",
    FILING_ID + "\n", " " + FILING_ID, "cik:" + FILING_ID,
    "0000320193:000095017026000001", FILING_ID + ":primary", ROOT_URL,
])
def test_filing_id_requires_exact_catalog_identity(value):
    with pytest.raises(SourceError, match="invalid_filing_id"):
        mod.parse_filing_id(value)


@pytest.mark.parametrize("payload,pointer", [
    ({}, "/directory"), ({"directory": []}, "/directory"),
    ({"directory": {"name": DIRECTORY_PATH}}, "/directory/item"),
    ({"directory": {"name": DIRECTORY_PATH, "item": {}}}, "/directory/item"),
    ({"directory": {"name": DIRECTORY_PATH, "item": [None]}}, "/directory/item/0"),
    ({"directory": {"name": DIRECTORY_PATH, "item": [{}]}}, "/directory/item/0/name"),
    ({"directory": {"name": DIRECTORY_PATH, "item": [{"name": "a.htm"}]}}, "/directory/item/0/type"),
])
def test_malformed_directory_is_not_observed_empty(payload, pointer):
    with pytest.raises(SourceError) as caught:
        mod.parse_document_directory(json.dumps(payload).encode(), filing_id=FILING_ID)
    assert caught.value.pointer == pointer


def test_only_observed_empty_list_can_return_empty_entries():
    result = mod.parse_document_directory(directory([]), filing_id=FILING_ID)
    assert result.entries == ()
    assert result.sha256 == hashlib.sha256(directory([])).hexdigest()


@pytest.mark.parametrize("size", [True, -1, 1.5, "-1", "1.0", " ", {}, "1" * 5000])
def test_invalid_advisory_size_rejects_directory(size):
    with pytest.raises(SourceError) as caught:
        mod.parse_document_directory(directory([{"name": "a.htm", "type": "text.htm", "size": size}]),
                                     filing_id=FILING_ID)
    assert caught.value.pointer == "/directory/item/0/size"


def test_duplicate_conflicts_cannot_authorize_a_document():
    first = {"name": "a.htm", "type": "text.htm", "size": 2}
    with pytest.raises(SourceError) as caught:
        mod.parse_document_directory(directory([first, {**first, "size": 3}]), filing_id=FILING_ID)
    assert (caught.value.code, caught.value.pointer) == ("conflicting_document", "/directory/item/1/name")
    result = mod.parse_document_directory(directory([first, first]), filing_id=FILING_ID)
    assert len(result.entries) == 1
    assert result.entries[0].source.pointer == "/directory/item/0"


@pytest.mark.parametrize("raw,code", [
    (b'{"directory":{},"directory":{}}', "duplicate_key"),
    (b'{"directory":NaN}', "invalid_number"), (b'{', "invalid_json"),
])
def test_directory_uses_exact_json_decoder(raw, code):
    with pytest.raises(SourceError) as caught:
        mod.parse_document_directory(raw, filing_id=FILING_ID)
    assert caught.value.code == code


def test_directory_metadata_bound_rejects_before_decode(monkeypatch):
    monkeypatch.setattr(mod, "MAX_DIRECTORY_BYTES", 16)
    with pytest.raises(SourceError, match="directory_too_large"):
        mod.parse_document_directory(b" " * 17, filing_id=FILING_ID)
