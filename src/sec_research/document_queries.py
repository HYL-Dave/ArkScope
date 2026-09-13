"""Stored-only document indexes and pinned UTF-8 passages."""

import base64
import binascii
from dataclasses import asdict
import json
import re

from .catalog import _primary_document
from .capture_lock import research_operation
from .document_store import DocumentStore
from .documents import parse_document_directory, parse_filing_id
from .queries import MAX_ENVELOPE_BYTES, _digest, _encode


_CURSOR_KEYS = {"v", "filing_id", "document_id", "capture_id", "filters_hash", "mode", "offset"}


def _capture_id(value):
    return isinstance(value, str) and re.fullmatch(r"secdoc_[0-9a-f]{64}", value) is not None


def _filters(section_id, query, max_chars):
    return _digest(dict(section_id=section_id, query=query, max_chars=max_chars))


def _decode(cursor):
    if (not isinstance(cursor, str) or not 1 <= len(cursor) <= 4096
            or re.fullmatch(r"[A-Za-z0-9_-]+", cursor) is None):
        raise ValueError("sec_research_cursor_invalid")
    try:
        token = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
        if (not isinstance(token, dict) or set(token) != _CURSOR_KEYS
                or type(token["v"]) is not int or token["v"] != 1
                or not _capture_id(token["capture_id"])
                or not isinstance(token["filing_id"], str) or not isinstance(token["document_id"], str)
                or not isinstance(token["filters_hash"], str)
                or re.fullmatch(r"[0-9a-f]{64}", token["filters_hash"]) is None
                or token["mode"] not in ("index", "text", "search")
                or type(token["offset"]) is not int or not 0 <= token["offset"] <= 128 * 1024**2
                or _encode(token) != cursor):
            raise ValueError
        return token
    except (ValueError, TypeError, UnicodeError, RecursionError, binascii.Error):
        raise ValueError("sec_research_cursor_invalid") from None


def validate_document_query(filing_id, *, document_id="primary", capture_id=None,
                            section_id=None, query=None, cursor=None, max_chars=6000):
    """Normalize/validate operands and closed cursor bindings before any storage I/O."""
    try:
        parse_filing_id(filing_id)
        if document_id != "primary":
            if (not isinstance(document_id, str) or not document_id.startswith("file:")
                    or _primary_document(document_id[5:], "") is None):
                raise ValueError
        if (not isinstance(document_id, str)
                or capture_id is not None and not _capture_id(capture_id)
                or section_id is not None and (not isinstance(section_id, str)
                    or re.fullmatch(r"[a-z0-9_]{1,100}", section_id) is None)
                or query is not None and (not isinstance(query, str) or not query)
                or type(max_chars) is not int or not 1 <= max_chars <= 20000):
            raise ValueError
        if query is not None:
            query.encode("utf-8")
    except (ValueError, UnicodeError):
        raise ValueError("sec_research_query_invalid") from None
    if cursor is not None:
        token = _decode(cursor)
        expected = "search" if query is not None else "text" if section_id is not None else None
        if (token["filing_id"] != filing_id or token["document_id"] != document_id
                or token["filters_hash"] != _filters(section_id, query, max_chars)
                or capture_id is not None and token["capture_id"] != capture_id
                or expected is not None and token["mode"] != expected
                or expected is None and token["mode"] not in {"text", "index"}):
            raise ValueError("sec_research_cursor_mismatch")
    return dict(document_id=document_id, capture_id=capture_id, section_id=section_id,
                query=query, cursor=cursor, max_chars=max_chars)


def _data():
    return dict(document=None, documents=[], sections=[], passages=[], text_start_cursor=None)


def _unavailable(code="stored_document_unavailable", *, gaps=None, observed_at=None):
    return {"status": "unavailable", "data": _data(), "gaps": gaps if gaps is not None else [{"code": code}],
            "observed_at": observed_at, "coverage": {"capture_id": None, "complete": False}, "next_cursor": None}


def _fits(envelope):
    return len(json.dumps(envelope, ensure_ascii=True, allow_nan=False).encode("ascii")) <= MAX_ENVELOPE_BYTES


class DocumentQueries:
    def __init__(self, store, captures):
        self.store, self.captures = store, captures
        self.documents = DocumentStore(store)

    def _open(self, filing_id, document_id, capture_id):
        if capture_id is None:
            attempt = self.documents.latest_attempt(filing_id, document_id)
            if attempt is None:
                return None, _unavailable()
            if attempt["capture_id"] is None:
                return None, _unavailable(gaps=attempt["gaps"], observed_at=attempt["observed_at"])
            capture_id = attempt["capture_id"]
        record = self.documents.capture(capture_id)
        if (record is None or record["filing_id"] != filing_id
                or document_id != record["document_id"] and not (
                    document_id == "primary" and record["primary_document"] is not None
                    and record["document_id"] == "file:" + record["primary_document"])):
            return None, _unavailable("document_capture_unavailable")
        metadata = record["metadata"]
        directory_body = self.captures.read(metadata["directory_sha256"])
        directory = parse_document_directory(directory_body, filing_id=filing_id)
        if [asdict(e) for e in directory.entries] != record["directory"]["entries"]:
            raise ValueError("document_integrity_failed")
        entry = next((e for e in directory.entries if e.document_id == record["document_id"]), None)
        if entry is None or entry.url != metadata["source_url"]:
            raise ValueError("document_integrity_failed")
        original = self.captures.read(record["original_sha256"])
        canonical = self.captures.read(record["text_sha256"])
        if len(original) != metadata["original_bytes"] or len(canonical) != metadata["text_bytes"]:
            raise ValueError("document_integrity_failed")
        for source in metadata["catalog_sources"]:
            self.captures.read(source["object_sha256"])
        canonical.decode("utf-8")
        for section in metadata["sections"]:
            start, end = section["start_byte"], section["end_byte"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(canonical):
                raise ValueError("document_integrity_failed")
            canonical[:start].decode("utf-8")
            canonical[start:end].decode("utf-8")
        return (record, canonical), None

    def read(self, filing_id, *, document_id="primary", capture_id=None, section_id=None,
             query=None, cursor=None, max_chars=6000, result_fits=None):
        validate_document_query(filing_id, document_id=document_id, capture_id=capture_id,
            section_id=section_id, query=query, cursor=cursor, max_chars=max_chars)
        token = _decode(cursor) if cursor is not None else None
        if token:
            capture_id = token["capture_id"]
        try:
            with research_operation(self.store.paths.capture_root):
                opened, unavailable = self._open(filing_id, document_id, capture_id)
                if unavailable is not None:
                    return unavailable
                record, canonical = opened
                return self._page(record, canonical, document_id=document_id, section_id=section_id,
                                  query=query, token=token, max_chars=max_chars, result_fits=result_fits)
        except Exception as error:
            if str(error) in {"sec_research_cursor_invalid", "sec_research_cursor_mismatch"}:
                raise
            return _unavailable()

    def _page(self, record, canonical, *, document_id, section_id, query, token, max_chars, result_fits=None):
        def fits(envelope):
            return _fits(envelope) and (result_fits is None or result_fits(envelope))
        metadata = record["metadata"]
        capture_id, filing_id = record["capture_id"], record["filing_id"]
        mode = token["mode"] if token else "search" if query is not None else "text" if section_id else "index"
        offset = token["offset"] if token else 0
        start, end = 0, len(canonical)
        sections = metadata["sections"]
        gaps = list(metadata["catalog_gaps"])
        data = _data()

        def cursor_at(position, *, cursor_mode=mode, section=section_id, term=query):
            return _encode({"v": 1, "filing_id": filing_id, "document_id": document_id,
                "capture_id": capture_id, "filters_hash": _filters(section, term, max_chars),
                "mode": cursor_mode, "offset": position})

        data["document"] = {"capture_id": capture_id, "filing_id": filing_id,
            "document_id": record["document_id"], "primary_document": record["primary_document"],
            **{key: metadata[key] for key in ("form", "source_url", "original_sha256", "text_sha256",
                "extraction_version", "mime_type", "text_bytes", "original_bytes", "directory_sha256")}}
        data["text_start_cursor"] = cursor_at(0, cursor_mode="text", section=None, term=None)
        coverage = {"capture_id": capture_id, "receipt_id": metadata["receipt_id"],
                    "mode": mode, "catalog_complete": not gaps, "complete": False}
        result = {"status": "ok", "data": data, "gaps": gaps, "observed_at": record["observed_at"],
                  "coverage": coverage, "next_cursor": None}

        def prepare(*, available=True, empty=False):
            coverage["complete"] = available and not gaps and result["next_cursor"] is None
            result["status"] = ("unavailable" if not available else "partial" if gaps
                                else "empty" if empty else "ok")
            return result

        def finish(*, available=True, empty=False):
            prepare(available=available, empty=empty)
            return result if fits(result) else _unavailable("document_envelope_too_large")

        if section_id is not None:
            selected = next((s for s in sections if s["section_id"] == section_id), None)
            if selected is None:
                gaps.append({"code": "section_unavailable", "section_id": section_id})
                return finish(available=False)
            start, end = selected["start_byte"], selected["end_byte"]
            data["sections"] = [selected]
        if mode == "index":
            gaps.extend(metadata["section_gaps"])
            entries = record["directory"]["entries"]
            total = len(entries) + len(sections)
            if token and not 0 <= offset < total:
                raise ValueError("sec_research_cursor_invalid")
            coverage.update(index_total=total, index_offset=offset)
            # Index entries are indivisible; each page admits at least one within the envelope ceiling.
            used = 0
            while offset < total:
                item = entries[offset] if offset < len(entries) else sections[offset - len(entries)]
                target = data["documents"] if offset < len(entries) else data["sections"]
                size = len(item["name"] if offset < len(entries) else item["label"])
                if used and used + size > max_chars:
                    break
                target.append(item)
                result["next_cursor"] = cursor_at(offset + 1) if offset + 1 < total else None
                if not fits(prepare()):
                    target.pop()
                    if not used:
                        gaps.append({"code": "document_index_entry_too_large"})
                        result["next_cursor"] = cursor_at(offset + 1) if offset + 1 < total else None
                        return finish(available=False)
                    break
                used += size
                offset += 1
            result["next_cursor"] = cursor_at(offset) if offset < total else None
            return finish()
        if not token:
            offset = start
        if not start <= offset <= end:
            raise ValueError("sec_research_cursor_invalid")
        try:
            canonical[start:offset].decode("utf-8")
            text = canonical[offset:end].decode("utf-8")
        except UnicodeError:
            raise ValueError("sec_research_cursor_invalid") from None

        def passage(left, right, match_start=None, match_end=None):
            return {"text": canonical[left:right].decode("utf-8"), "citation": {
                "filing_id": filing_id, "document_id": record["document_id"], "capture_id": capture_id,
                "accession": filing_id.split(":")[1], "source_url": metadata["source_url"],
                "original_sha256": record["original_sha256"], "text_sha256": record["text_sha256"],
                "extraction_version": metadata["extraction_version"], "start_byte": left, "end_byte": right,
                "match_start_byte": match_start, "match_end_byte": match_end}}

        def admit_passage(build, minimum, maximum):
            # The user cap remains in every cursor's filter identity. Only the
            # complete cited passage is sized against its final wrapped result.
            if build(maximum):
                return True
            low, high, best = minimum, maximum - 1, None
            while low <= high:
                middle = (low + high) // 2
                if build(middle):
                    best, low = middle, middle + 1
                else:
                    high = middle - 1
            if best is not None:
                build(best)
                return True
            build(maximum)
            return False

        if mode == "text":
            if not text:
                return finish(empty=True)
            def build_text(chars):
                next_offset = offset + len(text[:chars].encode("utf-8"))
                data["passages"] = [passage(offset, next_offset)]
                result["next_cursor"] = cursor_at(next_offset) if next_offset < end else None
                return fits(prepare())
            if not admit_passage(build_text, 1, min(max_chars, len(text))):
                skipped = data["passages"][0]["citation"]
                data["passages"] = []
                gaps.append({"code": "document_passage_too_large",
                             "start_byte": skipped["start_byte"], "end_byte": skipped["end_byte"]})
                return finish(available=False)
            return finish()
        if len(query) > max_chars:
            gaps.append({"code": "document_page_size_insufficient"})
            return finish(available=False)
        # One complete match and bounded context per page; continuation skips the matched term.
        match = text.find(query)
        if match < 0:
            return finish(empty=True)
        match_start = offset + len(text[:match].encode("utf-8"))
        match_end = match_start + len(query.encode("utf-8"))
        if text.find(query, match + len(query)) >= 0:
            result["next_cursor"] = cursor_at(match_end)
        def build_match(chars):
            context = chars - len(query)
            left_char = max(0, match - context // 2)
            right_char = min(len(text), left_char + chars)
            left = offset + len(text[:left_char].encode("utf-8"))
            right = offset + len(text[:right_char].encode("utf-8"))
            data["passages"] = [passage(left, right, match_start, match_end)]
            return fits(prepare())
        if not admit_passage(build_match, len(query), min(max_chars, len(text))):
            data["passages"] = []
            gaps.append({"code": "document_passage_too_large", "start_byte": match_start, "end_byte": match_end})
            return finish(available=False)
        return finish()
