"""Immutable submissions snapshots; no traversal, acquisition or coverage claim."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from .common import (
    SourceError, SourceRef, accession_value, date_value, decode_object,
    json_pointer, normalize_cik, source_ref, text_value, validate_payload_cik,
)


@dataclass(frozen=True)
class Filing:
    filing_id: str
    cik: str
    accession: str
    form: str
    filed_date: str
    report_date: str | None
    accepted_at: str | None
    primary_document: str | None
    primary_url: str | None
    source: SourceRef


@dataclass(frozen=True)
class HistoricalFile:
    name: str
    filing_count: int | None
    filed_from: str | None
    filed_to: str | None
    source: SourceRef


@dataclass(frozen=True)
class CatalogSnapshot:
    cik: str
    sha256: str
    filings: tuple[Filing, ...]
    historical_files: tuple[HistoricalFile, ...]
    historical_name: str | None = None
    historical_files_observed: bool = False


def _historical_name(value, cik, pointer):
    if not isinstance(value, str) or not re.fullmatch(r"CIK" + cik + r"-submissions-[0-9]+\.json", value):
        raise SourceError("invalid_historical_file", pointer)
    return value


def _accepted_at(value, pointer):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value
    ):
        raise SourceError("invalid_timestamp", pointer)
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        raise SourceError("invalid_timestamp", pointer) from None


def _primary_document(value, pointer):
    if value is None or value == "":
        return None
    # A conservative literal basename avoids decoding or rewriting URL components.
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", value):
        raise SourceError("invalid_document", pointer)
    return value


def _filings(columns, *, cik, sha256, parts):
    if not isinstance(columns, dict):
        raise SourceError("invalid_columns", json_pointer(*parts))
    for name in ("accessionNumber", "filingDate", "form"):
        if name not in columns:
            raise SourceError("missing_column", json_pointer(*parts, name))
    for name, values in columns.items():
        if not isinstance(values, list):
            raise SourceError("invalid_column", json_pointer(*parts, name))
    count = len(columns["accessionNumber"])
    for name, values in columns.items():
        if len(values) != count:
            raise SourceError("misaligned_columns", json_pointer(*parts, name))

    result = []
    seen = {}
    for index in range(count):
        def pointer(name):
            return json_pointer(*parts, name, index)

        def optional(name):
            return columns[name][index] if name in columns else None

        accession = accession_value(columns["accessionNumber"][index], pointer("accessionNumber"))
        form = text_value(columns["form"][index], pointer("form"))
        filed = date_value(columns["filingDate"][index], pointer("filingDate"))
        report = date_value(optional("reportDate"), pointer("reportDate"), optional=True)
        accepted = _accepted_at(optional("acceptanceDateTime"), pointer("acceptanceDateTime"))
        document = _primary_document(optional("primaryDocument"), pointer("primaryDocument"))
        row = {name: values[index] for name, values in columns.items()}
        if accession in seen and seen[accession] != row:
            raise SourceError("conflicting_accession", pointer("accessionNumber"))
        seen[accession] = row
        url = None
        if document is not None:
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"
        result.append(Filing(
            filing_id=f"{cik}:{accession}", cik=cik, accession=accession, form=form,
            filed_date=filed, report_date=report, accepted_at=accepted,
            primary_document=document, primary_url=url,
            source=SourceRef(sha256, pointer("accessionNumber")),
        ))
    return tuple(result)


def _historical_files(value, *, cik, sha256):
    parts = ("filings", "files")
    if not isinstance(value, list):
        raise SourceError("invalid_historical_files", json_pointer(*parts))
    result = []
    for index, row in enumerate(value):
        pointer = json_pointer(*parts, index)
        if not isinstance(row, dict):
            raise SourceError("invalid_historical_file", pointer)
        name = _historical_name(row.get("name"), cik, pointer + "/name")
        count = row.get("filingCount")
        if count is not None and (type(count) is not int or count < 0):
            raise SourceError("invalid_count", pointer + "/filingCount")
        filed_from = date_value(row.get("filingFrom"), pointer + "/filingFrom", optional=True)
        filed_to = date_value(row.get("filingTo"), pointer + "/filingTo", optional=True)
        if filed_from is not None and filed_to is not None and filed_from > filed_to:
            raise SourceError("invalid_date_range", pointer + "/filingTo")
        result.append(HistoricalFile(name, count, filed_from, filed_to, SourceRef(sha256, pointer)))
    return tuple(result)


def parse_submissions(body: bytes, *, cik: str, historical_name: str | None = None) -> CatalogSnapshot:
    cik = normalize_cik(cik)
    payload = decode_object(body)
    validate_payload_cik(payload, cik, required=historical_name is None)
    sha256 = source_ref(body, "").sha256
    if historical_name is not None:
        historical_name = _historical_name(historical_name, cik, "")
        columns = {name: value for name, value in payload.items() if name != "cik"}
        filings = _filings(columns, cik=cik, sha256=sha256, parts=())
        return CatalogSnapshot(cik, sha256, filings, (), historical_name)
    container = payload.get("filings")
    if not isinstance(container, dict):
        raise SourceError("invalid_filings", "/filings")
    filings = _filings(container.get("recent"), cik=cik, sha256=sha256, parts=("filings", "recent"))
    historical = _historical_files(container.get("files", []), cik=cik, sha256=sha256)
    return CatalogSnapshot(
        cik, sha256, filings, historical,
        historical_files_observed="files" in container,
    )
