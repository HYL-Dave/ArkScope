"""Closed SEC references derived only from whole admitted tool evidence."""

import base64
import binascii
from dataclasses import fields
from decimal import Decimal, InvalidOperation
import json
import re
from urllib.parse import urlsplit

from .captures import MAX_OBJECT_BYTES
from .catalog import Filing, _accepted_at, _primary_document
from .common import accession_value, date_value, normalize_cik, text_value
from .documents import directory_url, parse_filing_id
from .facts import FactObservation
from .queries import MAX_ENVELOPE_BYTES, _canonical
from .store import _timestamp
from .tool_results import SEC_TOOL_NAMES, valid_envelope


MAX_CITATION_QUERY_BYTES = 8192
MAX_CITATION_BYTES = 6144
MAX_CITATION_PASSAGE_BYTES = 80000
MAX_RESULT_BYTES = MAX_ENVELOPE_BYTES + 4096
CITATION_GAP_CODES = frozenset({
    "sec_citation_invalid", "sec_citation_result_invalid", "sec_citation_query_invalid",
    "sec_citation_missing", "sec_citation_integrity_failed",
})
_SOURCE_FIELDS = {"snapshot_id", "source_sha256", "source_pointer", "source_url", "observed_at"}
_DOCUMENT_FIELDS = {"kind", "filing_id", "document_id", "capture_id", "accession", "source_url",
    "original_sha256", "text_sha256", "extraction_version", "start_byte", "end_byte",
    "match_start_byte", "match_end_byte"}
_FIELDS = {"document": _DOCUMENT_FIELDS, "fact": _SOURCE_FIELDS | {"kind", "cik", "fact_id"},
           "filing": _SOURCE_FIELDS | {"kind", "filing_id"}}
_PROVENANCE_FIELDS = {"snapshot_id", "source", "observed_at", "source_url", "object_sha256"}


class CitationError(ValueError):
    """A closed code only: never include source text, paths or failed operands."""

    def __init__(self, code):
        self.code = code if code in CITATION_GAP_CODES else "sec_citation_integrity_failed"
        super().__init__(self.code)


def _matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _url(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ValueError
    text_value(value, "")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc not in {"www.sec.gov", "data.sec.gov"}
            or not parsed.path.startswith("/") or parsed.query or parsed.fragment
            or any(char.isspace() for char in value)):
        raise ValueError


def _time(value):
    if _timestamp(value) != value:
        raise ValueError


def _document_identity(value):
    parse_filing_id(value["filing_id"])
    _url(value["source_url"])
    if (not _matches(value["capture_id"], r"secdoc_[0-9a-f]{64}")
            or not _matches(value["document_id"], r"file:[A-Za-z0-9_-][A-Za-z0-9_.-]{0,1023}")
            or not _matches(value["extraction_version"], r"sec-document-text-v[1-9][0-9]{0,5}")
            or any(not _matches(value[key], r"[0-9a-f]{64}") for key in ("original_sha256", "text_sha256"))):
        raise ValueError


def validate_citation(ref) -> dict:
    """Validate the closed union without normalization, storage or acquisition."""
    try:
        if not isinstance(ref, dict) or not isinstance(ref.get("kind"), str):
            raise ValueError
        kind = ref["kind"]
        if kind not in _FIELDS or set(ref) != _FIELDS[kind]:
            raise ValueError
        if len(_canonical(ref).encode("ascii")) > MAX_CITATION_BYTES:
            raise ValueError
        _url(ref["source_url"])
        if kind in {"document", "filing"}:
            _, accession = parse_filing_id(ref["filing_id"])
        if kind == "document":
            _document_identity(ref)
            if ref["accession"] != accession:
                raise ValueError
            start, end = ref["start_byte"], ref["end_byte"]
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= MAX_OBJECT_BYTES
                    or end - start > MAX_CITATION_PASSAGE_BYTES):
                raise ValueError
            left, right = ref["match_start_byte"], ref["match_end_byte"]
            if not (left is None and right is None) and (
                    type(left) is not int or type(right) is not int or not start <= left < right <= end):
                raise ValueError
        else:
            if (not _matches(ref["snapshot_id"], r"secsnapshot_[0-9a-f]{64}")
                    or not _matches(ref["source_sha256"], r"[0-9a-f]{64}")
                    or not isinstance(ref["source_pointer"], str)
                    or not 1 <= len(ref["source_pointer"]) <= 2048
                    or not ref["source_pointer"].startswith("/")
                    or re.search(r"~(?![01])", ref["source_pointer"])):
                raise ValueError
            text_value(ref["source_pointer"], "")
            _time(ref["observed_at"])
            if kind == "fact" and (normalize_cik(ref["cik"]) != ref["cik"]
                    or not _matches(ref["fact_id"], r"secfact_[0-9a-f]{64}")):
                raise ValueError
        return dict(ref)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise CitationError("sec_citation_invalid") from None


def encode_citation_query(ref) -> str:
    """Canonical ASCII JSON, sorted keys, compact separators, unpadded base64url."""
    raw = _canonical(validate_citation(ref)).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError
    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def decode_citation_query(token) -> dict:
    try:
        if (not isinstance(token, str) or not 1 <= len(token) <= MAX_CITATION_QUERY_BYTES
                or not _matches(token, r"[A-Za-z0-9_-]+")):
            raise ValueError
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        ref = validate_citation(_json(raw.decode("ascii")))
        if encode_citation_query(ref) != token:
            raise ValueError
        return ref
    except (ValueError, TypeError, UnicodeError, RecursionError, binascii.Error):
        raise CitationError("sec_citation_query_invalid") from None


def _tool_name(name):
    if not isinstance(name, str):
        return None
    name = name.removeprefix("mcp__ark__").removeprefix("tool_")
    return name if name in SEC_TOOL_NAMES else None


def _provenance(kind, row, source):
    if (not isinstance(source, dict) or set(source) != _PROVENANCE_FIELDS
            or not isinstance(source["source"], dict) or set(source["source"]) != {"sha256", "pointer"}
            or source["object_sha256"] != source["source"]["sha256"]):
        raise ValueError
    identity = {"cik": row["cik"], "fact_id": row["fact_id"]} if kind == "fact" else {"filing_id": row["filing_id"]}
    return validate_citation({"kind": kind, **identity, "snapshot_id": source["snapshot_id"],
        "source_sha256": source["source"]["sha256"], "source_pointer": source["source"]["pointer"],
        "source_url": source["source_url"], "observed_at": source["observed_at"]})


def _observation_shape(row, kind):
    model = FactObservation if kind == "fact" else Filing
    required = {field.name for field in fields(model)} - {"source"}
    if not isinstance(row, dict) or not required <= set(row) or normalize_cik(row["cik"]) != row["cik"]:
        raise ValueError
    accession_value(row["accession"], "")
    text_value(row["form"], "")
    date_value(row["filed_date"], "")
    if kind == "filing":
        if row["filing_id"] != row["cik"] + ":" + row["accession"]:
            raise ValueError
        # Native query rows are already normalized; malformed evidence is not repaired.
        if (date_value(row["report_date"], "", optional=True) != row["report_date"]
                or _accepted_at(row["accepted_at"], "") != row["accepted_at"]):
            raise ValueError
        document = _primary_document(row["primary_document"], "")
        url = None if document is None else directory_url(row["filing_id"]).removesuffix("index.json") + document
        if document != row["primary_document"] or row["primary_url"] != url:
            raise ValueError
    else:
        if not isinstance(row["value"], str) or not Decimal(row["value"]).is_finite():
            raise ValueError
        for key in ("namespace", "concept", "unit"):
            text_value(row[key], "")
        start = date_value(row["start"], "", optional=True)
        end = date_value(row["end"], "")
        if start != row["start"] or (start is not None and start > end):
            raise ValueError
        fiscal_year = row["fiscal_year"]
        if fiscal_year is not None and (type(fiscal_year) is not int or not 1 <= fiscal_year <= 9999):
            raise ValueError
        for key in ("fiscal_period", "frame"):
            text_value(row[key], "", optional=True)


def _document_data(data, coverage):
    if (not isinstance(data, dict) or set(data) != {"document", "documents", "sections", "passages", "text_start_cursor"}
            or any(not isinstance(data[key], list) for key in ("documents", "sections", "passages"))):
        raise ValueError
    document = data["document"]
    if document is None:
        if (any(data[key] for key in ("documents", "sections", "passages"))
                or data["text_start_cursor"] is not None or coverage.get("capture_id") is not None):
            raise ValueError
        return
    if not isinstance(document, dict) or set(document) != {
            "capture_id", "filing_id", "document_id", "primary_document", "form", "source_url",
            "original_sha256", "text_sha256", "extraction_version", "mime_type", "text_bytes",
            "original_bytes", "directory_sha256"}:
        raise ValueError
    _document_identity(document)
    for key in ("form", "mime_type"):
        text_value(document[key], "")
    _primary_document(document["primary_document"], "")
    if (not _matches(document["directory_sha256"], r"[0-9a-f]{64}")
            or any(type(document[key]) is not int or not 1 <= document[key] <= MAX_OBJECT_BYTES
                   for key in ("text_bytes", "original_bytes"))
            or coverage.get("capture_id") != document["capture_id"]
            or type(coverage.get("receipt_id")) is not int or not 1 <= coverage["receipt_id"] <= 2**63 - 1
            or not isinstance(data["text_start_cursor"], str)
            or not 1 <= len(data["text_start_cursor"]) <= 4096):
        raise ValueError
    root = directory_url(document["filing_id"]).removesuffix("index.json")
    for entry in data["documents"]:
        if not isinstance(entry, dict) or set(entry) != {"name", "document_id", "url", "size_bytes", "source"}:
            raise ValueError
        name = _primary_document(entry["name"], "")
        source = entry["source"]
        if (name is None or entry["document_id"] != "file:" + name or entry["url"] != root + name
                or entry["size_bytes"] is not None and (type(entry["size_bytes"]) is not int or entry["size_bytes"] < 0)
                or not isinstance(source, dict) or set(source) != {"sha256", "pointer"}
                or source["sha256"] != document["directory_sha256"]
                or not _matches(source["pointer"], r"/directory/item/(0|[1-9][0-9]*)")):
            raise ValueError
    for section in data["sections"]:
        if (not isinstance(section, dict) or set(section) != {"section_id", "label", "start_byte", "end_byte"}
                or not _matches(section["section_id"], r"[a-z0-9_]{1,100}")
                or type(section["start_byte"]) is not int or type(section["end_byte"]) is not int
                or not 0 <= section["start_byte"] < section["end_byte"] <= document["text_bytes"]):
            raise ValueError
        text_value(section["label"], "")


def sec_citations_from_envelope(tool_name, envelope) -> list[dict]:
    """Project whole query rows/passages; any malformed owned evidence fails closed."""
    name = _tool_name(tool_name)
    if name is None:
        return []
    try:
        if not valid_envelope(envelope) or len(_canonical(envelope).encode("ascii")) > MAX_RESULT_BYTES:
            raise ValueError
        if envelope["observed_at"] is not None:
            _time(envelope["observed_at"])
        data, refs = envelope["data"], []
        if name == "read_sec_filing":
            if data == [] and envelope["status"] in {"empty", "unavailable"}:
                return []
            _document_data(data, envelope["coverage"])
            if data["passages"] and envelope["status"] in {"empty", "unavailable"}:
                raise ValueError
            for passage in data["passages"]:
                if (not isinstance(passage, dict) or set(passage) != {"text", "citation"}
                        or not isinstance(passage["citation"], dict)
                        or set(passage["citation"]) != _DOCUMENT_FIELDS - {"kind"}
                        or not isinstance(passage["text"], str)):
                    raise ValueError
                ref = validate_citation({"kind": "document", **passage["citation"]})
                document = data["document"]
                if (not isinstance(document, dict) or any(document.get(key) != ref[key] for key in (
                        "capture_id", "filing_id", "document_id", "source_url", "original_sha256", "text_sha256", "extraction_version"))
                        or ref["end_byte"] > document["text_bytes"]
                        or len(passage["text"].encode("utf-8")) != ref["end_byte"] - ref["start_byte"]):
                    raise ValueError
                if ref["match_start_byte"] is not None:
                    raw = passage["text"].encode("utf-8")
                    for key in ("match_start_byte", "match_end_byte"):
                        raw[:ref[key] - ref["start_byte"]].decode("utf-8")
                refs.append(ref)
        else:
            if not isinstance(data, list) or data and envelope["status"] in {"empty", "unavailable"}:
                raise ValueError
            kind = "fact" if name == "get_sec_financial_facts" else "filing"
            for row in data:
                _observation_shape(row, kind)
                if kind == "fact":
                    refs.append(_provenance(kind, row, {key: row[key] for key in _PROVENANCE_FIELDS}))
                else:
                    sources = row["sources"]
                    if not isinstance(sources, list) or not sources:
                        raise ValueError
                    refs.extend(_provenance(kind, row, source) for source in sources)
        # Preserve query order, including every conflicting source variant.
        return list({_canonical(ref): ref for ref in refs}.values())
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, InvalidOperation):
        raise CitationError("sec_citation_result_invalid") from None


def _whole_result(name, result):
    if isinstance(result, str):
        if len(result.encode("utf-8")) > MAX_RESULT_BYTES:
            raise ValueError
        if result.startswith('<tool_output tool="'):
            header, separator, body = result.partition("\n")
            match = re.fullmatch(r'<tool_output tool="([A-Za-z0-9_]+)">', header)
            if not match or _tool_name(match[1]) != name or not separator or not body.endswith("\n</tool_output>"):
                raise ValueError
            result = body[:-len("\n</tool_output>")]
        return [_json(result)]
    if isinstance(result, dict) and "content" not in result:
        return [result]
    structured = None
    if isinstance(result, dict):
        if not set(result) <= {"content", "is_error", "isError", "structuredContent", "_meta"}:
            raise ValueError
        if result.get("is_error", False) is not False or result.get("isError", False) is not False:
            raise ValueError
        blocks = result["content"]
        structured = result.get("structuredContent")
    elif isinstance(result, list):
        blocks = result
    else:
        from mcp.types import CallToolResult
        if not isinstance(result, CallToolResult) or result.isError:
            raise ValueError
        blocks = result.content
        structured = result.structuredContent
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 100:
        raise ValueError
    envelopes, total = [], 0
    for block in blocks:
        if isinstance(block, dict):
            if not set(block) <= {"type", "text", "annotations", "_meta"} or block.get("type") != "text":
                raise ValueError
            text = block["text"]
        else:
            from mcp.types import TextContent
            if not isinstance(block, TextContent):
                raise ValueError
            text = block.text
        if not isinstance(text, str):
            raise ValueError
        total += len(text.encode("utf-8"))
        if total > MAX_RESULT_BYTES:
            raise ValueError
        envelopes.extend(_whole_result(name, text))
    if structured is not None and (len(envelopes) != 1 or _canonical(structured) != _canonical(envelopes[0])):
        raise ValueError
    return envelopes


def sec_citations_from_result(tool_name, result) -> list[dict]:
    """Accept owned wrappers, JSON and actual MCP text blocks, never previews/prose."""
    name = _tool_name(tool_name)
    if name is None:
        return []
    try:
        refs = [ref for envelope in _whole_result(name, result)
                for ref in sec_citations_from_envelope(name, envelope)]
        return list({_canonical(ref): ref for ref in refs}.values())
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise CitationError("sec_citation_result_invalid") from None


def citation_event_fields(tool_name, result) -> dict:
    """Optional trace projection; malformed evidence must not disappear silently."""
    try:
        refs = sec_citations_from_result(tool_name, result)
        return {"sec_citations": refs} if refs else {}
    except CitationError as error:
        return {"sec_citation_gaps": [error.code]}


def validate_citation_event_fields(tool_name, metadata) -> None:
    """Validate optional evidence fields after the caller's security admission."""
    present = {"sec_citations", "sec_citation_gaps"} & metadata.keys()
    if not present:
        return
    if _tool_name(tool_name) is None:
        raise CitationError("sec_citation_invalid")
    for key in present:
        values = metadata[key]
        if type(values) is not list:
            raise CitationError("sec_citation_invalid")
        for value in values:
            if key == "sec_citations":
                validate_citation(value)
            elif type(value) is not str or value not in CITATION_GAP_CODES:
                raise CitationError("sec_citation_invalid")


def read_sec_citation(store, captures, *, citation) -> dict:
    """Reopen one exact retained observation or passage, without any acquisition."""
    from .references import _ReferenceReader, _retained_errors

    ref = validate_citation(citation)
    try:
        with _retained_errors():
            reader = _ReferenceReader(store, captures)
            data, observed_at = reader.read(ref)
        return {"status": "ok", "data": data, "gaps": [], "observed_at": observed_at,
                "coverage": {"complete": True}, "next_cursor": None}
    except CitationError as error:
        return {"status": "unavailable", "data": None, "gaps": [{"code": error.code}],
                "observed_at": None, "coverage": {"complete": False}, "next_cursor": None}
