"""Pure accession-bound directory parsing."""

from dataclasses import dataclass
import re

from .catalog import _primary_document
from .common import (
    SourceError, SourceRef, accession_value, decode_object, json_pointer,
    normalize_cik, source_ref, text_value,
)


MAX_DIRECTORY_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class DocumentEntry:
    name: str
    document_id: str
    url: str
    size_bytes: int | None
    source: SourceRef


@dataclass(frozen=True)
class DocumentDirectory:
    filing_id: str
    cik: str
    accession: str
    url: str
    sha256: str
    entries: tuple[DocumentEntry, ...]


def parse_filing_id(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{10}:[0-9]{10}-[0-9]{2}-[0-9]{6}", value):
        raise SourceError("invalid_filing_id")
    cik, accession = value.split(":")
    try:
        return normalize_cik(cik), accession_value(accession, "")
    except SourceError:
        raise SourceError("invalid_filing_id") from None


def directory_url(filing_id: str) -> str:
    cik, accession = parse_filing_id(filing_id)
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/index.json"


def _size(value, pointer: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        try:
            value = int(value)
        except ValueError:
            raise SourceError("invalid_size", pointer) from None
    if type(value) is not int or value < 0:
        raise SourceError("invalid_size", pointer)
    return value


def parse_document_directory(body: bytes, *, filing_id: str) -> DocumentDirectory:
    cik, accession = parse_filing_id(filing_id)
    if not isinstance(body, bytes):
        raise SourceError("invalid_source")
    if len(body) > MAX_DIRECTORY_BYTES:
        raise SourceError("directory_too_large")
    payload = decode_object(body)
    directory = payload.get("directory")
    if not isinstance(directory, dict):
        raise SourceError("invalid_directory", "/directory")
    url = directory_url(filing_id)
    root = url.removesuffix("index.json")
    if directory.get("name") != root.removeprefix("https://www.sec.gov").rstrip("/"):
        raise SourceError("directory_mismatch", "/directory/name")
    items = directory.get("item")
    if not isinstance(items, list):
        raise SourceError("invalid_directory_items", "/directory/item")
    sha256 = source_ref(body, "").sha256
    entries, seen = [], {}
    for index, item in enumerate(items):
        pointer = json_pointer("directory", "item", index)
        if not isinstance(item, dict):
            raise SourceError("invalid_directory_item", pointer)
        name = _primary_document(item.get("name"), pointer + "/name")
        if name is None:
            raise SourceError("invalid_document", pointer + "/name")
        kind = text_value(item.get("type"), pointer + "/type")
        size = _size(item.get("size"), pointer + "/size")
        if name in seen:
            if seen[name] != item:
                raise SourceError("conflicting_document", pointer + "/name")
            continue
        seen[name] = item
        if kind.lower() in {"dir", "directory"}:
            continue
        entries.append(DocumentEntry(name, "file:" + name, root + name, size, SourceRef(sha256, pointer)))
    return DocumentDirectory(filing_id, cik, accession, url, sha256, tuple(entries))
