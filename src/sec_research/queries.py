"""Read-only queries pinned to immutable receipts and exact source snapshots."""

from dataclasses import dataclass
from contextlib import closing
from datetime import date
import base64
import binascii
import hashlib
import json
import re
import sqlite3

from .common import normalize_cik
from .store import MAX_SNAPSHOT_ROWS


MAX_CURSOR_BYTES = 4096
MAX_ENVELOPE_BYTES = 256 * 1024
MAX_QUERY_ROWS = 100000
MAX_QUERY_BYTES = 64 * 1024 * 1024
MAX_QUERY_SOURCES = 1024
_CURSOR_KEYS = {"v", "cik", "kind", "filters_hash", "receipt_id", "bindings_digest", "offset"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("ascii")).hexdigest()


def _encode(value):
    return base64.urlsafe_b64encode(_canonical(value).encode("ascii")).decode("ascii").rstrip("=")


def _decode(token):
    if (not isinstance(token, str) or not 1 <= len(token) <= MAX_CURSOR_BYTES
            or re.fullmatch(r"[A-Za-z0-9_-]+", token) is None):
        raise ValueError("sec_research_cursor_invalid")
    try:
        value = json.loads(base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True))
        if (not isinstance(value, dict) or set(value) != _CURSOR_KEYS
                or type(value["v"]) is not int or value["v"] != 1
                or type(value["receipt_id"]) is not int or not 1 <= value["receipt_id"] <= 2**63 - 1
                or type(value["offset"]) is not int or not 1 <= value["offset"] <= 2**63 - 1
                or value["kind"] not in ("filings", "facts")
                or not isinstance(value["cik"], str) or normalize_cik(value["cik"]) != value["cik"]
                or any(not isinstance(value[key], str) or re.fullmatch(r"[0-9a-f]{64}", value[key]) is None
                       for key in ("filters_hash", "bindings_digest"))
                or _encode(value) != token):
            raise ValueError
        return value
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        raise ValueError("sec_research_cursor_invalid") from None


def query_date(value):
    """Validate an optional ISO calendar date; failures use the closed query code."""
    if value is None:
        return None
    try:
        if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError("sec_research_query_invalid") from None


@dataclass(frozen=True)
class QueryContext:
    cik: str
    kind: str
    filters_hash: str
    receipt: dict | None
    bindings_digest: str
    offset: int = 0


def open_query(store, cik, *, kind, filters, cursor=None):
    """Pin normalized filters (including limit) to one durable receipt.

    Caller owns domain filter validation. Storage errors propagate to its closed
    unavailable adapter; malformed/mismatched cursors are ValueError codes.
    """
    cik = normalize_cik(cik)
    if kind not in ("filings", "facts") or type(filters.get("limit")) is not int or not 1 <= filters["limit"] <= 100:
        raise ValueError("sec_research_query_invalid")
    filters_hash = _digest(filters)
    token = _decode(cursor) if cursor is not None else None
    if token and (token["cik"] != cik or token["kind"] != kind or token["filters_hash"] != filters_hash):
        raise ValueError("sec_research_cursor_mismatch")
    receipt = store.receipt(cik, token["receipt_id"]) if token else store.latest_receipt(cik)
    bindings_digest = _digest(receipt["source_snapshots"] if receipt else {})
    if token and (receipt is None or token["bindings_digest"] != bindings_digest):
        raise ValueError("sec_research_cursor_mismatch")
    return QueryContext(cik, kind, filters_hash, receipt, bindings_digest, token["offset"] if token else 0)


@dataclass(frozen=True)
class BoundSources:
    sources: dict
    gaps: list
    row_count: int
    encoded_bytes: int


def read_bound_sources(store, context, *, kind, row_filter=None):
    """Stream/filter bound sources into an aggregate-bounded observation set.

    Observation time belongs to the receipt's capture, which may be newer than
    the first publication of identical bytes. Rows retain full source references.
    The byte ceiling measures admitted encoded metadata/rows, not Python RSS.
    Exhaustion stops traversal with a typed gap; callers must preserve that gap.
    """
    if kind not in ("catalog", "facts"):
        raise ValueError("sec_research_kind_invalid")
    sources = {}
    row_count = encoded_bytes = 0

    def result(bound=None):
        gaps = [{"code": "query_budget_exceeded", "bound": bound}] if bound else []
        return BoundSources(sources, gaps, row_count, encoded_bytes)

    if context.receipt is None:
        return result()
    bindings = context.receipt["source_snapshots"]
    for locator in sorted(bindings, key=lambda name: (name != "submissions", name)):
        if (locator == "companyfacts") != (kind == "facts"):
            continue
        if len(sources) >= MAX_QUERY_SOURCES:
            return result("sources")
        binding = bindings[locator]
        if locator not in context.receipt["completed"]:
            raise ValueError("sec_research_receipt_binding_invalid")
        metadata = store.bound_snapshot(context.cik, locator, binding)
        if not 0 <= metadata["row_count"] <= MAX_SNAPSHOT_ROWS:
            raise ValueError("sec_research_receipt_binding_invalid")
        metadata["observed_at"] = binding["observed_at"]
        size = len(_canonical(metadata).encode("ascii"))
        if encoded_bytes + size > MAX_QUERY_BYTES:
            return result("bytes")
        encoded_bytes += size
        rows = []
        sources[locator] = (metadata, rows)
        seen = 0
        with closing(store.iter_snapshot_observations(context.cik, binding["snapshot_id"])) as observations:
            for row in observations:
                seen += 1
                if seen > metadata["row_count"]:
                    raise ValueError("sec_research_receipt_binding_invalid")
                if row_filter is not None and not row_filter(row):
                    continue
                if row_count >= MAX_QUERY_ROWS:
                    return result("rows")
                row["observed_at"] = binding["observed_at"]
                size = len(_canonical(row).encode("ascii"))
                if encoded_bytes + size > MAX_QUERY_BYTES:
                    return result("bytes")
                rows.append(row)
                encoded_bytes += size
                row_count += 1
        if seen != metadata["row_count"]:
            raise ValueError("sec_research_receipt_binding_invalid")
    return result()


def _cursor(context, offset):
    return _encode({"v": 1, "cik": context.cik, "kind": context.kind,
                    "filters_hash": context.filters_hash, "receipt_id": context.receipt["receipt_id"],
                    "bindings_digest": context.bindings_digest, "offset": offset})


def unavailable_envelope():
    """Storage failure boundary with no exception, path or provider payload text."""
    return {"status": "unavailable", "data": [], "gaps": [{"code": "stored_source_unavailable"}],
            "observed_at": None, "coverage": {"receipt_id": None, "complete": False}, "next_cursor": None}


def page_envelope(context, rows, *, limit, gaps, available, coverage=None):
    """Page already filtered/sorted whole rows within count and encoded byte bounds.

    Domain callers provide bounded typed gaps and coverage metadata. A record
    that cannot fit alone is skipped with a counted gap, so continuations advance.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("sec_research_query_invalid")
    if context.offset and context.offset >= len(rows):
        raise ValueError("sec_research_cursor_invalid")
    receipt = context.receipt
    base_coverage = {**(coverage or {}), "receipt_id": receipt["receipt_id"] if receipt else None,
                     "bindings_digest": context.bindings_digest, "selection_total": len(rows)}

    def envelope(data, page_gaps, offset):
        complete = available and not page_gaps
        status = ("unavailable" if not available else "partial" if page_gaps
                  else "ok" if data else "empty")
        return {"status": status, "data": data, "gaps": page_gaps,
                "observed_at": receipt["observed_at"] if receipt else None,
                "coverage": {**base_coverage, "complete": complete},
                "next_cursor": _cursor(context, offset) if offset < len(rows) else None}

    data, used, skipped = [], 0, 0
    offset = context.offset

    def page_gaps():
        return [*gaps, *([{"code": "observation_too_large", "count": skipped}] if skipped else [])]

    while offset < len(rows) and len(data) < limit:
        row = rows[offset]
        size = len(json.dumps(row, ensure_ascii=True, allow_nan=False).encode("ascii"))
        candidate = envelope([], page_gaps(), offset + 1)
        candidate["status"] = "unavailable" if not available else "partial" if page_gaps() else "ok"
        overhead = len(json.dumps(candidate, ensure_ascii=True).encode("ascii"))
        addition = size + (2 if data else 0)
        if overhead + used + addition > MAX_ENVELOPE_BYTES:
            if data:
                break
            skipped += 1
            offset += 1
            continue
        data.append(row)
        used += addition
        offset += 1
    result = envelope(data, page_gaps(), offset)
    if len(json.dumps(result, ensure_ascii=True).encode("ascii")) > MAX_ENVELOPE_BYTES:
        return unavailable_envelope()
    return result


class StoredQueries:
    def __init__(self, store):
        self.store = store

    def filings(self, cik, *, forms=None, filed_from=None, filed_to=None,
                include_amendments=True, cursor=None, limit=20):
        cik = normalize_cik(cik)
        if (type(limit) is not int or not 1 <= limit <= 100 or type(include_amendments) is not bool
                or forms is not None and (not isinstance(forms, (list, tuple))
                or any(not isinstance(form, str) or not form.strip() for form in forms))):
            raise ValueError("sec_research_query_invalid")
        forms = sorted({form.strip().upper() for form in forms}) if forms else None
        filed_from, filed_to = query_date(filed_from), query_date(filed_to)
        if filed_from and filed_to and filed_from > filed_to:
            raise ValueError("sec_research_query_invalid")
        filters = {"forms": forms, "filed_from": filed_from, "filed_to": filed_to,
                   "include_amendments": include_amendments, "limit": limit}
        allowed = set(forms or [])
        if include_amendments:
            allowed.update(form + "/A" for form in forms or [] if not form.endswith("/A"))

        def selected(row):
            return not (not include_amendments and row["form"].endswith("/A")
                        or forms and row["form"] not in allowed
                        or filed_from and row["filed_date"] < filed_from
                        or filed_to and row["filed_date"] > filed_to)

        try:
            context = open_query(self.store, cik, kind="filings", filters=filters, cursor=cursor)
            bound = read_bound_sources(self.store, context, kind="catalog", row_filter=selected)
        except (sqlite3.Error, OSError, json.JSONDecodeError):
            return unavailable_envelope()
        except ValueError as exc:
            if str(exc) in {"sec_research_schema_mismatch", "sec_research_receipt_binding_invalid"}:
                return unavailable_envelope()
            raise
        sources, gaps = bound.sources, list(bound.gaps)
        recent = sources.get("submissions")
        if recent is None:
            gaps.append({"code": "submissions_unavailable"})
        elif not recent[0]["historical_files_observed"]:
            gaps.append({"code": "historical_files_unobserved"})
        required = {item["name"] for item in recent[0]["historical_files"]} if recent else set()
        if context.receipt:
            required.update(source for source in context.receipt["pending"] if source != "companyfacts")
            source_gaps = sum(gap.get("source") != "companyfacts" for gap in context.receipt["gaps"])
            if source_gaps:
                gaps.append({"code": "catalog_source_gaps", "count": source_gaps})
        missing = required - sources.keys()
        if missing:
            gaps.append({"code": "catalog_sources_pending", "count": len(missing)})

        # Compare filing metadata independently of provenance; retain all sources
        # for identical observations and all variants for conflicting metadata.
        merged, identities, provenance_keys = {}, {}, {}
        for _, rows in sources.values():
            for original in rows:
                row = dict(original)
                provenance = {key: row.pop(key) for key in (
                    "snapshot_id", "source", "observed_at", "source_url", "object_sha256")}
                key = _canonical(row)
                identities.setdefault(row["filing_id"], set()).add(key)
                if key not in merged:
                    merged[key] = {**row, "sources": []}
                    provenance_keys[key] = set()
                provenance_key = _canonical(provenance)
                if provenance_key not in provenance_keys[key]:
                    merged[key]["sources"].append(provenance)
                    provenance_keys[key].add(provenance_key)
        conflicts = sum(len(variants) > 1 for variants in identities.values())
        if conflicts:
            gaps.append({"code": "filing_metadata_conflict", "count": conflicts})
        selection = []
        for row in merged.values():
            row["sources"].sort(key=_canonical)
            selection.append(row)
        selection.sort(key=lambda row: (row["accession"], row["filing_id"], _canonical(row)))
        selection.sort(key=lambda row: row["filed_date"], reverse=True)
        return page_envelope(context, selection, limit=limit, gaps=gaps, available=bool(sources),
                             coverage={"catalog_sources": len(sources), "admitted_rows": bound.row_count,
                                       "admitted_bytes": bound.encoded_bytes})
