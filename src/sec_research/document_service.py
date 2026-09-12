"""Explicit durable SEC document acquisition."""

from dataclasses import asdict
import hashlib
import uuid

from src.lifecycle_public_sources import SourceReadError, SourceReadLimits, validate_source_read_report

from .capture_lock import document_acquisition
from .common import SourceError
from .document_store import DocumentStore
from .document_text import EXTRACTION_VERSION, extract_document_text, index_sections
from .documents import directory_url, parse_document_directory, parse_filing_id
from .queries import open_query, read_bound_sources, validate_query
from .store import _timestamp


_ERROR_CODES = frozenset({
    "capture_budget_exceeded", "storage_space_insufficient", "capture_store_write_failed",
    "capture_store_busy", "capture_integrity_failed", "capture_path_unsafe", "capture_not_found",
    "document_acquisition_busy", "document_not_in_directory", "document_integrity_failed",
    "sec_research_schema_mismatch", "sec_research_receipt_binding_invalid",
    "source_body_incomplete", "source_body_too_large", "source_compression_incomplete",
    "source_compression_invalid", "source_decoded_body_too_large", "source_dns_busy",
    "source_dns_unavailable", "source_document_invalid", "source_encoding_unsupported",
    "source_format_unsupported", "source_framing_invalid", "source_observation_time",
    "source_rate_limited", "source_read_cancelled", "source_read_report_invalid",
    "source_read_timeout", "source_redirect_limit", "source_request_budget_exhausted",
    "source_response_invalid", "source_text_empty", "source_transport_unavailable",
    "source_unavailable", "unsafe_source_address", "unsafe_source_url",
    "source_document_complexity", "source_text_too_large", "sec_identity_unavailable",
    "sec_identity_invalid", "sec_governor_unavailable", "source_read_cleanup_failed",
})


def _error_code(error):
    code = str(error)
    return code if code in _ERROR_CODES else "document_acquisition_failed"


def _failure_outcome(requests):
    if any(request["dispatch_state"] == "dispatched" for request in requests):
        return "failed"
    if any(request["dispatch_state"] == "unknown" for request in requests):
        return "interrupted"
    return "no_dispatch"


def _catalog(store, filing_id):
    cik, _ = parse_filing_id(filing_id)
    context = open_query(store, cik, kind="filings", filters=validate_query(cik, "filings"))
    bound = read_bound_sources(store, context, kind="catalog",
                               row_filter=lambda row: row["filing_id"] == filing_id)
    gaps = list(bound.gaps)
    if gaps:
        return None, gaps
    recent = bound.sources.get("submissions")
    if recent is None:
        gaps.append({"code": "submissions_unavailable"})
    elif not recent[0]["historical_files_observed"]:
        gaps.append({"code": "historical_files_unobserved"})
    required = {h["name"] for h in recent[0]["historical_files"]} if recent else set()
    if context.receipt:
        required.update(s for s in context.receipt["pending"] if s != "companyfacts")
        source_gaps = sum(g.get("source") != "companyfacts" for g in context.receipt["gaps"])
        if source_gaps:
            gaps.append({"code": "catalog_source_gaps", "count": source_gaps})
    if required - bound.sources.keys():
        gaps.append({"code": "catalog_sources_pending", "count": len(required - bound.sources.keys())})
    rows = [row for _, rows in bound.sources.values() for row in rows]
    variants = {(r["primary_document"], r["form"]) for r in rows}
    if not rows or len(variants) != 1:
        return None, [*gaps, {"code": "filing_metadata_conflict" if rows else "filing_unavailable"}]
    primary, form = next(iter(variants))
    return {"receipt_id": context.receipt["receipt_id"], "primary_document": primary,
            "form": form, "sources": rows, "catalog_sources": [
                {"locator": locator, "snapshot_id": meta["snapshot_id"],
                 "object_sha256": meta["object_sha256"], "observed_at": meta["observed_at"],
                 "source_url": meta["source_url"]} for locator, (meta, _) in bound.sources.items()]}, gaps


class DocumentService:
    def __init__(self, store, captures, *, reader_factory, clock):
        self.store, self.captures = store, captures
        self.documents = DocumentStore(store)
        self.reader_factory, self.clock = reader_factory, clock

    def _read(self, operation, url, extractor, requests, check):
        check()
        self.captures.preflight()
        check()
        observed = []

        def observe(actual_url, body, content_type):
            check()
            observed.append((actual_url, body, content_type))

        def extract(body, content_type, *, check):
            reader_check = check
            def combined_check():
                reader_check()
                outer_check()
            return extractor(body, content_type, check=combined_check)

        outer_check = check
        metadata = operation == "directory"
        limits = SourceReadLimits(max_requests=1, max_redirects=0,
            max_response_bytes=(16 if metadata else 32) * 1024**2,
            max_decoded_bytes=(16 if metadata else 128) * 1024**2, timeout_seconds=60)
        reader = self.reader_factory(limits, document_observer=observe, text_extractor=extract)
        evidence = {"operation": operation, "url": url, "request_count": None,
                    "dispatch_state": "unknown", "report": None, "gaps": []}
        requests.append(evidence)
        try:
            page = reader.read(url)
        finally:
            # Snapshot dispatch independently before validation or cleanup can fail.
            # Reporting failures must not replace the original read exception.
            try:
                count = reader.request_count
                if type(count) is not int or not 0 <= count < 2**53:
                    raise SourceReadError("source_read_report_invalid")
                evidence["request_count"] = count
                evidence["dispatch_state"] = "dispatched" if count else "not_dispatched"
                evidence["report"] = validate_source_read_report({"requests": count,
                    "observations": [asdict(row) for row in reader.observations]}, max_requests=1)
            except Exception:
                evidence["gaps"].append({"code": "source_read_report_invalid"})
            finally:
                try:
                    reader.request_stop()
                except Exception:
                    evidence["gaps"].append({"code": "source_read_cleanup_failed"})
        if evidence["gaps"]:
            raise SourceReadError(evidence["gaps"][0]["code"])
        report = evidence["report"]
        check()
        if (len(observed) != 1 or observed[0][0] != url or page.url != url or page.redirect_chain
                or hashlib.sha256(observed[0][1]).hexdigest() != page.body_sha256
                or hashlib.sha256(page.text.encode("utf-8")).hexdigest() != page.text_sha256
                or report["requests"] != 1 or len(report["observations"]) != 1
                or report["observations"][0]["result_code"] != "complete"
                or report["observations"][0]["decoded_body_bytes"] != len(observed[0][1])
                or report["observations"][0]["received_body_bytes"] > limits.max_response_bytes
                or len(observed[0][1]) > limits.decoded_byte_limit):
            raise ValueError("document_integrity_failed")
        return page, observed[0][1]

    def refresh(self, filing_id, document_id="primary", check=None):
        from .document_queries import validate_document_query

        validate_document_query(filing_id, document_id=document_id)
        check = check or (lambda: None)
        observed_at = _timestamp(self.clock())
        observation_id = uuid.uuid4().hex
        requests, gaps = [], []
        resolved = primary = None
        invalidation_primary = None
        started = False

        def record(*, capture_id=None, outcome, failure_gaps=None):
            return self.documents.record_attempt(filing_id, document_id, observed_at=observed_at,
                resolved_document_id=resolved, primary_document=primary, capture_id=capture_id,
                acquisition_id=observation_id,
                invalidation_primary_document=invalidation_primary,
                status=("partial" if gaps else "ok") if capture_id else "unavailable",
                outcome=outcome, gaps=gaps if failure_gaps is None else failure_gaps, requests=requests)

        try:
            with document_acquisition(self.store.paths.capture_root):
                invalidation_primary = self.documents.invalidation_primary_document(filing_id, document_id)
                # A crash after this append cannot expose an older successful observation as latest.
                record(outcome="interrupted", failure_gaps=[{"code": "document_acquisition_interrupted"}])
                started = True
                try:
                    check()
                    authority, gaps = _catalog(self.store, filing_id)
                    if authority is None:
                        return record(outcome="no_dispatch")
                    primary = authority["primary_document"]
                    resolved = "file:" + primary if document_id == "primary" and primary else document_id
                    if resolved == "primary":
                        gaps.append({"code": "primary_document_unavailable"})
                        return record(outcome="no_dispatch")
                    record(outcome="interrupted", failure_gaps=[{"code": "document_acquisition_interrupted"}])
                    parsed = []

                    def directory_extractor(body, content_type, *, check):
                        check()
                        try:
                            parsed.append(parse_document_directory(body, filing_id=filing_id))
                        except SourceError:
                            raise SourceReadError("source_document_invalid") from None
                        check()
                        return "directory", "application/json"

                    directory_page, directory_body = self._read("directory", directory_url(filing_id),
                        directory_extractor, requests, check)
                    directory = parsed[0]
                    entry = next((e for e in directory.entries if e.document_id == resolved), None)
                    if entry is None:
                        raise ValueError("document_not_in_directory")
                    if self.captures.put(directory_body) != directory.sha256:
                        raise ValueError("document_integrity_failed")
                    structure = []

                    def document_extractor(body, content_type, *, check):
                        return extract_document_text(body, content_type, check=check,
                                                     structure_observer=structure.append)

                    page, original = self._read("document", entry.url, document_extractor, requests, check)
                    sections, section_gaps = index_sections(page.text, authority["form"], check=check,
                                                           toc_ranges=structure[0]["toc_ranges"])
                    section_gaps.extend(structure[0]["structure_gaps"])
                    canonical = page.text.encode("utf-8")
                    directory_record = {"filing_id": filing_id, "receipt_id": authority["receipt_id"],
                        "object_sha256": directory.sha256, "observed_at": _timestamp(directory_page.retrieved_at),
                        "observation_id": observation_id, "entries": [asdict(e) for e in directory.entries],
                        "source_url": directory.url, "request": requests[0]}
                    metadata = {**authority, "filing_id": filing_id, "document_id": resolved,
                        "original_sha256": page.body_sha256, "text_sha256": page.text_sha256,
                        "observed_at": _timestamp(page.retrieved_at), "refresh_observed_at": observed_at,
                        "directory_sha256": directory.sha256, "source_url": entry.url,
                        "observation_id": observation_id, "extraction_version": EXTRACTION_VERSION,
                        **structure[0],
                        "mime_type": page.mime_type, "sections": sections, "section_gaps": section_gaps,
                        "catalog_gaps": gaps, "requests": requests, "text_bytes": len(canonical),
                        "original_bytes": len(original)}
                    # All parsing and hashing precede publication; partial object writes never publish a document.
                    check()
                    for body, digest in ((directory_body, directory.sha256), (original, page.body_sha256),
                                         (canonical, page.text_sha256)):
                        check()
                        if hashlib.sha256(body).hexdigest() != digest or self.captures.put(body) != digest:
                            raise ValueError("document_integrity_failed")
                        if self.captures.read(digest) != body:
                            raise ValueError("document_integrity_failed")
                    for source in authority["catalog_sources"]:
                        self.captures.read(source["object_sha256"])
                    check()
                    capture_id = self.documents.publish(directory=directory_record, metadata=metadata)
                    return record(capture_id=capture_id, outcome="complete")
                except Exception as error:
                    failures = [gap for request in requests for gap in request["gaps"]]
                    for gap in [*failures, {"code": _error_code(error)}]:
                        if gap not in gaps:
                            gaps.append(gap)
                    return record(outcome=_failure_outcome(requests))
        except Exception as error:
            # Lease/storage failure must not append while another acquisition owns this root.
            return {"attempt_id": None, "filing_id": filing_id, "document_id": document_id,
                "resolved_document_id": resolved, "primary_document": primary, "acquisition_id": observation_id,
                "invalidation_primary_document": invalidation_primary,
                "capture_id": None, "status": "unavailable",
                "observed_at": observed_at, "outcome": "interrupted" if started else "no_dispatch",
                "gaps": [{"code": _error_code(error)}], "requests": requests}
