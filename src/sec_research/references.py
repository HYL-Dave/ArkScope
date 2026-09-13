"""Read-only verification and transitive retained SEC source identities."""

from contextlib import closing, contextmanager
from collections.abc import Iterator
from dataclasses import asdict
import hashlib
import sqlite3

from . import schema
from .captures import CaptureStore, MAX_OBJECT_BYTES
from .catalog import parse_submissions
from .citations import CitationError, _json, _time, validate_citation, validate_citation_event_fields
from .document_store import DocumentStore
from .documents import parse_document_directory, parse_filing_id
from .facts import parse_companyfacts
from .queries import _canonical
from .store import MAX_SNAPSHOT_ROWS, _json as store_json


@contextmanager
def _retained_errors():
    try:
        yield
    except CitationError:
        raise
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError,
            AttributeError, OverflowError, RecursionError):
        raise CitationError("sec_citation_integrity_failed") from None


def _require(condition):
    if not condition:
        raise CitationError("sec_citation_integrity_failed")


def iter_research_sec_citations(profile_connection: sqlite3.Connection) -> Iterator[dict]:
    """Yield validated refs from every retained message and event JSON root.

    The caller owns an explicitly query-only connection and its read snapshot.
    Legacy absent fields are valid; malformed JSON/fields and recorded gaps fail
    closed. No active-thread join, preview parsing, or source acquisition occurs.
    """
    with _retained_errors():
        _require(profile_connection.execute("PRAGMA query_only").fetchone()[0] == 1)
        for record in profile_connection.execute(
            "SELECT tool_calls_json FROM research_messages WHERE tool_calls_json IS NOT NULL ORDER BY id"
        ):
            calls = _json(record[0])
            _require(type(calls) is list)
            for call in calls:
                _require(type(call) is dict)
                yield from _profile_citations(call.get("name"), call)
        for record in profile_connection.execute(
            "SELECT data_json FROM research_run_events ORDER BY run_id, seq"
        ):
            data = _json(record[0])
            _require(type(data) is dict)
            yield from _profile_citations(data.get("tool"), data)


def _profile_citations(name, data):
    validate_citation_event_fields(name, data)
    _require(not data.get("sec_citation_gaps"))
    for ref in data.get("sec_citations", []):
        yield validate_citation(ref)


def _range(raw, start, end):
    _require(type(start) is int and type(end) is int and 0 <= start < end <= len(raw))
    # The whole buffer is verified UTF-8 before checking individual boundaries.
    for offset in (start, end):
        _require(offset == len(raw) or raw[offset] & 0xC0 != 0x80)


class _ReferenceReader:
    """Execution-local verifier shared by reopening and maintenance closure."""

    def __init__(self, store, captures, *, retain_closure=False):
        self.store, self.captures = store, captures
        self.retain_closure = retain_closure
        self.snapshots, self.receipts = {}, {}
        self.capture_ids, self.directory_ids, self.objects = set(), set(), set()
        self.fact_ids, self.filing_ids = set(), set()
        self.fact_observations, self.filing_observations = [], []
        with store.connect(readonly=True) as conn:
            schema.verify(conn)

    def _object(self, sha):
        with self.store.connect(readonly=True) as conn:
            row = conn.execute("SELECT object_key,size_bytes FROM sec_research_objects WHERE sha256=?", (sha,)).fetchone()
        if row is None:
            raise CitationError("sec_citation_missing")
        _require(row["object_key"] == "objects/" + sha and type(row["size_bytes"]) is int
                 and 0 <= row["size_bytes"] <= MAX_OBJECT_BYTES)
        body = self.captures.read(sha)
        self.objects.add(sha)
        return body

    def _rows(self, metadata, *, pointer=None, filing_id=None):
        table = "sec_research_facts" if metadata["kind"] == "facts" else "sec_research_filings"
        where, params = "snapshot_id=?", [metadata["snapshot_id"]]
        if pointer is not None:
            where += " AND source_pointer=?"
            params.append(pointer)
        if filing_id is not None:
            where += " AND filing_id=?"
            params.append(filing_id)
        with self.store.connect(readonly=True) as conn:
            for record in conn.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY ordinal LIMIT ?",
                                       (*params, MAX_SNAPSHOT_ROWS + 1)):
                row = dict(record)
                ordinal = row.pop("ordinal")
                row["source"] = {"sha256": row.pop("source_sha256"), "pointer": row.pop("source_pointer")}
                row.update(observed_at=metadata["observed_at"], source_url=metadata["source_url"],
                           object_sha256=metadata["object_sha256"])
                yield ordinal, row

    def _snapshot(self, cik, snapshot_id):
        if snapshot_id in self.snapshots:
            result = self.snapshots[snapshot_id]
            _require(result["cik"] == cik)
            return result
        metadata = self.store.snapshot(cik, snapshot_id)
        if metadata is None:
            raise CitationError("sec_citation_missing")
        kind, sha = metadata["kind"], metadata["object_sha256"]
        _require(kind in {"catalog", "facts"} and type(metadata["row_count"]) is int
                 and 0 <= metadata["row_count"] <= MAX_SNAPSHOT_ROWS)
        _time(metadata["observed_at"])
        identity = store_json([cik, kind, metadata["historical_name"], sha]).encode("utf-8")
        _require(snapshot_id == "secsnapshot_" + hashlib.sha256(identity).hexdigest())
        body = self._object(sha)
        if kind == "facts":
            parsed = parse_companyfacts(body, cik=cik)
            observations, history = parsed.facts, []
            history_observed = False
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            _require(metadata["historical_name"] is None)
        else:
            parsed = parse_submissions(body, cik=cik, historical_name=metadata["historical_name"])
            observations = parsed.filings
            history = [asdict(row) for row in parsed.historical_files]
            history_observed = parsed.historical_files_observed
            url = "https://data.sec.gov/submissions/" + (metadata["historical_name"] or f"CIK{cik}.json")
        _require(parsed.sha256 == sha and metadata["source_url"] == url
                 and len(observations) == metadata["row_count"]
                 and metadata["historical_files"] == history
                 and metadata["historical_files_observed"] == history_observed)
        count = 0
        with closing(self._rows(metadata)) as rows:
            for ordinal, row in rows:
                _require(ordinal == count and count < len(observations))
                expected = {**asdict(observations[count]), "snapshot_id": snapshot_id,
                    "observed_at": metadata["observed_at"], "source_url": url, "object_sha256": sha}
                _require(row == expected)
                if self.retain_closure:
                    key = "fact_id" if kind == "facts" else "filing_id"
                    ids = self.fact_ids if kind == "facts" else self.filing_ids
                    identities = self.fact_observations if kind == "facts" else self.filing_observations
                    ids.add(row[key])
                    identities.append({"snapshot_id": snapshot_id, "ordinal": ordinal, key: row[key]})
                count += 1
        _require(count == len(observations))
        # Only compact verified metadata survives this source. Parsed bytes and
        # observation payloads are released before the next snapshot is opened.
        compact = {key: value for key, value in metadata.items()
                   if key not in {"historical_files", "historical_files_observed"}}
        self.snapshots[snapshot_id] = compact
        return compact

    def _receipt(self, cik, receipt_id):
        receipt = self.store.receipt(cik, receipt_id)
        if receipt is None:
            raise CitationError("sec_citation_missing")
        with self.store.connect(readonly=True) as conn:
            raw = conn.execute("SELECT source_snapshots FROM sec_research_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()[0]
        bindings = _json(raw)
        _require(bindings == receipt["source_snapshots"] and set(bindings) == set(receipt["completed"]))
        for binding in bindings.values():
            _time(binding["observed_at"])
        if self.retain_closure and receipt_id not in self.receipts:
            for locator, binding in bindings.items():
                metadata = self._snapshot(cik, binding["snapshot_id"])
                expected_kind = "facts" if locator == "companyfacts" else "catalog"
                history = None if locator in {"submissions", "companyfacts"} else locator
                _require(metadata["kind"] == expected_kind and metadata["historical_name"] == history)
        self.receipts[receipt_id] = cik
        return receipt

    def _observation_receipts(self, ref, metadata):
        # References omit receipt IDs. Retain every matching observation binding;
        # first-publication timestamps also support receipt-free fact-ID queries.
        original_observation = metadata["observed_at"] == ref["observed_at"]
        if original_observation and not self.retain_closure:
            return
        found = False
        with self.store.connect(readonly=True) as conn:
            for row in conn.execute("""
                SELECT DISTINCT r.receipt_id FROM sec_research_receipts r,
                    json_each(r.source_snapshots) binding
                WHERE r.cik=? AND json_extract(binding.value, '$.snapshot_id')=?
                    AND json_extract(binding.value, '$.observed_at')=?
                ORDER BY r.receipt_id""", (metadata["cik"], ref["snapshot_id"], ref["observed_at"])):
                receipt = self._receipt(metadata["cik"], row[0])
                locator = "companyfacts" if metadata["kind"] == "facts" else metadata["historical_name"] or "submissions"
                _require(receipt["source_snapshots"].get(locator) == {
                    "snapshot_id": ref["snapshot_id"], "observed_at": ref["observed_at"]})
                found = True
                if not self.retain_closure:
                    return
        _require(found or original_observation)

    def _observation(self, ref):
        cik = ref["cik"] if ref["kind"] == "fact" else parse_filing_id(ref["filing_id"])[0]
        metadata = self._snapshot(cik, ref["snapshot_id"])
        _require(metadata["kind"] == ("facts" if ref["kind"] == "fact" else "catalog")
                 and metadata["object_sha256"] == ref["source_sha256"]
                 and metadata["source_url"] == ref["source_url"])
        with closing(self._rows(metadata, pointer=ref["source_pointer"])) as rows:
            selected = next(rows, None)
            _require(selected is not None and next(rows, None) is None)
            _, row = selected
        key = "fact_id" if ref["kind"] == "fact" else "filing_id"
        _require(row is not None and row[key] == ref[key] and row["source"]["sha256"] == ref["source_sha256"])
        self._observation_receipts(ref, metadata)
        return {"citation": ref, "observation": {**row, "observed_at": ref["observed_at"]}}, ref["observed_at"]

    def _document(self, ref):
        record = DocumentStore(self.store).capture(ref["capture_id"])
        if record is None:
            raise CitationError("sec_citation_missing")
        metadata, directory = record["metadata"], record["directory"]
        cik, accession = parse_filing_id(record["filing_id"])
        _require(ref["accession"] == accession)
        for key in ("filing_id", "document_id", "source_url", "original_sha256", "text_sha256", "extraction_version"):
            _require(ref[key] == metadata[key])
        _time(record["observed_at"])
        receipt = self._receipt(cik, metadata["receipt_id"])
        sources = metadata["catalog_sources"]
        _require(isinstance(sources, list) and all(isinstance(s, dict) for s in sources)
                 and len({s["snapshot_id"] for s in sources}) == len(sources)
                 and len({s["locator"] for s in sources}) == len(sources))
        expected_sources = []
        supplied = metadata["sources"]
        _require(isinstance(supplied, list) and supplied)
        supplied_rows = {(row["snapshot_id"], row["source"]["pointer"]): row for row in supplied}
        _require(len(supplied_rows) == len(supplied))
        for locator, binding in receipt["source_snapshots"].items():
            if locator == "companyfacts":
                continue
            info = self._snapshot(cik, binding["snapshot_id"])
            _require(info["kind"] == "catalog" and info["historical_name"] == (None if locator == "submissions" else locator))
            expected_sources.append({"locator": locator, "snapshot_id": info["snapshot_id"],
                "object_sha256": info["object_sha256"], "observed_at": binding["observed_at"], "source_url": info["source_url"]})
            with closing(self._rows(info, filing_id=ref["filing_id"])) as rows:
                for _, row in rows:
                    row["observed_at"] = binding["observed_at"]
                    supplied_row = supplied_rows.pop((row["snapshot_id"], row["source"]["pointer"]), None)
                    _require(row == supplied_row and row["form"] == metadata["form"]
                             and row["primary_document"] == metadata["primary_document"])
        _require(sorted(sources, key=_canonical) == sorted(expected_sources, key=_canonical)
                 and not supplied_rows)
        parsed = parse_document_directory(self._object(metadata["directory_sha256"]), filing_id=ref["filing_id"])
        _require(directory["source_url"] == parsed.url and directory["entries"] == [asdict(entry) for entry in parsed.entries])
        entry = next((entry for entry in parsed.entries if entry.document_id == ref["document_id"]), None)
        _require(entry is not None and entry.url == ref["source_url"])
        original_bytes = len(self._object(ref["original_sha256"]))
        _require(type(metadata["original_bytes"]) is int and original_bytes == metadata["original_bytes"])
        canonical = self._object(ref["text_sha256"])
        _require(type(metadata["text_bytes"]) is int and len(canonical) == metadata["text_bytes"])
        canonical.decode("utf-8")
        for section in metadata["sections"]:
            _range(canonical, section["start_byte"], section["end_byte"])
        _range(canonical, ref["start_byte"], ref["end_byte"])
        if ref["match_start_byte"] is not None:
            _range(canonical, ref["match_start_byte"], ref["match_end_byte"])
        self.capture_ids.add(ref["capture_id"])
        self.directory_ids.add(record["directory_id"])
        document = {"capture_id": ref["capture_id"], "accession": accession,
                    **{key: metadata[key] for key in ("filing_id", "document_id", "form", "source_url",
                        "original_sha256", "text_sha256", "extraction_version", "mime_type")}}
        return {"citation": ref, "document": document,
                "text": canonical[ref["start_byte"]:ref["end_byte"]].decode("utf-8")}, record["observed_at"]

    def read(self, ref):
        return self._document(ref) if ref["kind"] == "document" else self._observation(ref)

    def closure(self):
        return {"capture_ids": sorted(self.capture_ids), "directory_ids": sorted(self.directory_ids),
            "snapshot_ids": sorted(self.snapshots), "receipt_ids": sorted(self.receipts),
            "fact_ids": sorted(self.fact_ids), "filing_ids": sorted(self.filing_ids),
            "fact_observations": sorted(self.fact_observations, key=lambda row: (row["snapshot_id"], row["ordinal"])),
            "filing_observations": sorted(self.filing_observations, key=lambda row: (row["snapshot_id"], row["ordinal"])),
            "object_sha256s": sorted(self.objects), "object_keys": ["objects/" + sha for sha in sorted(self.objects)]}


def sec_reference_closure(store, *, citations) -> dict:
    """Sorted exact roots for later export/cleanup; missing/corrupt nodes raise.

    Captures retain their directory, all catalog sources, and every source in
    their receipt (including companyfacts). Snapshots retain all observations.
    This function neither enumerates profile history nor authorizes deletion.
    """
    with _retained_errors():
        reader = _ReferenceReader(store, CaptureStore(store, budget=None), retain_closure=True)
        for citation in citations:
            reader.read(validate_citation(citation))
        return reader.closure()
