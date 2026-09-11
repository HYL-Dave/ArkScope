"""Immutable durable document records over Store."""

import json

from . import schema
from .catalog import _primary_document
from .documents import parse_filing_id
from .queries import _digest
from .store import _bounded_json, _timestamp


def _identity(prefix, metadata):
    return prefix + _digest(metadata)


def _attempt(row):
    if row is None:
        return None
    result = dict(row)
    details = json.loads(result.pop("details"))
    required = {"outcome", "gaps", "requests", "acquisition_id"}
    if (not isinstance(details, dict)
            or set(details) not in (required, required | {"invalidation_primary_document"})
            or details["outcome"] not in {"interrupted", "no_dispatch", "failed", "complete"}
            or not isinstance(details["gaps"], list) or not isinstance(details["requests"], list)
            or (result["capture_id"] is None) != (result["status"] == "unavailable")):
        raise ValueError("document_integrity_failed")
    invalidation = details.get("invalidation_primary_document")
    if invalidation is not None and _primary_document(invalidation, "") != invalidation:
        raise ValueError("document_integrity_failed")
    return {**result, **details, "invalidation_primary_document": invalidation}


class DocumentStore:
    def __init__(self, store):
        self.store = store

    def capture(self, capture_id):
        with self.store.connect(readonly=True) as conn:
            schema.verify(conn)
            row = conn.execute("SELECT * FROM sec_research_documents WHERE capture_id=?", (capture_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            metadata = json.loads(result["metadata"])
            if not isinstance(metadata, dict) or _identity("secdoc_", metadata) != capture_id:
                raise ValueError("document_integrity_failed")
            if any(result[key] != metadata[key] for key in result if key not in {"capture_id", "metadata"}):
                raise ValueError("document_integrity_failed")
            directory = conn.execute("SELECT * FROM sec_research_document_directories WHERE directory_id=?",
                                     (result["directory_id"],)).fetchone()
            if directory is None:
                raise ValueError("document_integrity_failed")
            directory_metadata = json.loads(directory["metadata"])
            if (not isinstance(directory_metadata, dict)
                    or _identity("secdir_", directory_metadata) != result["directory_id"]
                    or any(directory[key] != directory_metadata[key] for key in directory.keys()
                           if key not in {"directory_id", "metadata"})
                    or directory["object_sha256"] != metadata["directory_sha256"]
                    or directory["filing_id"] != result["filing_id"]
                    or directory["receipt_id"] != metadata["receipt_id"]):
                raise ValueError("document_integrity_failed")
            sources = {row["snapshot_id"]: json.loads(row["provenance"]) for row in conn.execute(
                "SELECT * FROM sec_research_document_sources WHERE capture_id=?", (capture_id,))}
            if sources != {s["snapshot_id"]: s for s in metadata["catalog_sources"]}:
                raise ValueError("document_integrity_failed")
        cik, _ = parse_filing_id(result["filing_id"])
        receipt = self.store.receipt(cik, metadata["receipt_id"])
        if receipt is None:
            raise ValueError("document_integrity_failed")
        bindings = {k: v for k, v in receipt["source_snapshots"].items() if k != "companyfacts"}
        if set(bindings) != {s["locator"] for s in sources.values()}:
            raise ValueError("document_integrity_failed")
        for source in sources.values():
            binding = bindings[source["locator"]]
            snapshot = self.store.bound_snapshot(cik, source["locator"], binding)
            if (source["snapshot_id"] != binding["snapshot_id"]
                    or source["observed_at"] != binding["observed_at"]
                    or source["object_sha256"] != snapshot["object_sha256"]):
                raise ValueError("document_integrity_failed")
        result["metadata"] = metadata
        result["directory"] = directory_metadata
        return result

    def publish(self, *, directory, metadata):
        """Objects already exist and are verified; insert all associations atomically."""
        _bounded_json([directory, metadata])
        directory_id = _identity("secdir_", directory)
        metadata = {**metadata, "directory_id": directory_id}
        capture_id = _identity("secdoc_", metadata)
        with self.store._write() as conn:
            conn.execute("INSERT INTO sec_research_document_directories VALUES(?,?,?,?,?,?)", (
                directory_id, directory["filing_id"], directory["receipt_id"], directory["object_sha256"],
                directory["observed_at"], _bounded_json(directory)))
            conn.execute("INSERT INTO sec_research_documents VALUES(?,?,?,?,?,?,?,?,?)", (
                capture_id, directory_id, metadata["filing_id"], metadata["document_id"],
                metadata["primary_document"], metadata["original_sha256"], metadata["text_sha256"],
                metadata["observed_at"], _bounded_json(metadata)))
            for source in metadata["catalog_sources"]:
                conn.execute("INSERT INTO sec_research_document_sources VALUES(?,?,?)", (
                    capture_id, source["snapshot_id"], _bounded_json(source)))
        return capture_id

    def record_attempt(self, filing_id, document_id, *, observed_at, status="unavailable",
                       resolved_document_id=None, primary_document=None, capture_id=None,
                       acquisition_id, outcome, gaps, requests, invalidation_primary_document=None):
        parse_filing_id(filing_id)
        observed_at = _timestamp(observed_at)
        details = _bounded_json(dict(acquisition_id=acquisition_id, outcome=outcome, gaps=gaps, requests=requests,
                                     invalidation_primary_document=invalidation_primary_document))
        with self.store._write() as conn:
            inserted = conn.execute("""INSERT INTO sec_research_document_attempts
                (filing_id, document_id, resolved_document_id, primary_document, capture_id, status, observed_at, details)
                VALUES(?,?,?,?,?,?,?,?)""", (filing_id, document_id, resolved_document_id, primary_document,
                                             capture_id, status, observed_at, details))
            return _attempt(conn.execute("SELECT * FROM sec_research_document_attempts WHERE attempt_id=?",
                                         (inserted.lastrowid,)).fetchone())

    def invalidation_primary_document(self, filing_id, document_id):
        """Retain only the most recently established alias, never dispatch authority."""
        with self.store.connect(readonly=True) as conn:
            schema.verify(conn)
            row = conn.execute("""SELECT primary_document FROM sec_research_document_attempts
                WHERE filing_id=? AND resolved_document_id='file:' || primary_document
                ORDER BY attempt_id DESC LIMIT 1""", (filing_id,)).fetchone()
        if row is None or document_id not in ("primary", "file:" + row["primary_document"]):
            return None
        return row["primary_document"]

    def latest_attempt(self, filing_id, document_id):
        with self.store.connect(readonly=True) as conn:
            schema.verify(conn)
            return _attempt(conn.execute("""SELECT * FROM sec_research_document_attempts
                WHERE filing_id=? AND (document_id=? OR resolved_document_id=?
                    OR (?='primary' AND resolved_document_id='file:' || primary_document)
                    OR (?='primary' AND json_extract(details, '$.invalidation_primary_document') IS NOT NULL)
                    OR ?='file:' || json_extract(details, '$.invalidation_primary_document'))
                ORDER BY attempt_id DESC LIMIT 1""",
                (filing_id, document_id, document_id, document_id, document_id, document_id)).fetchone())
