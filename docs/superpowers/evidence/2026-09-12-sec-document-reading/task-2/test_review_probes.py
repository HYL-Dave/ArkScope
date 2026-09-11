"""Task2 review probes for early alias failures and request accounting only."""

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_sec_research_document_service import (
    CIK, FILING_ID, HISTORY, NOW, Response, bind_catalog, owner, rig, service,
)


def test_review_source_provenance():
    root = Path(__file__).resolve().parents[4]
    evidence = Path(__file__).with_name("final-inverse-hashes.json")
    blobs = {
        "src/sec_research/capture_lock.py": "222fcbcc",
        "src/sec_research/document_queries.py": "3b839324",
        "src/sec_research/document_service.py": "985a2b69",
        "src/sec_research/document_store.py": "5b2d559a",
        "src/sec_research/schema.py": "9857a35a",
        "tests/test_sec_research_document_queries.py": "1859cd88",
        "tests/test_sec_research_document_service.py": "4056bd10",
        "tests/test_sec_research_document_store.py": "00f8730b",
    }
    for item in json.loads(evidence.read_text())["baseline"]:
        body = (root / item["path"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == item["sha256"], item["path"]
        blob = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        assert blob.startswith(blobs[item["path"]]), item["path"]


@pytest.mark.parametrize("requested,other", [
    ("primary", "file:actual.htm"), ("file:actual.htm", "primary"),
])
@pytest.mark.parametrize("failure", ["conflict", "early_cancel"])
def test_review_early_failure_blocks_both_current_aliases(rig, requested, other, failure):
    rig.enqueue()
    first = service(rig).refresh(FILING_ID)
    reader = owner("document_queries").DocumentQueries(rig.store, rig.captures)
    pinned = reader.read(FILING_ID, capture_id=first["capture_id"], query="needle")
    previous_requests = len(rig.requests)
    check = None
    if failure == "conflict":
        recent = rig.store.latest_receipt(CIK)["source_snapshots"]["submissions"]
        sid = bind_catalog(rig.store, rig.captures, history=HISTORY, bind=False, primary="other.htm")
        bindings = {"submissions": recent, HISTORY: {"snapshot_id": sid, "observed_at": NOW}}
        rig.store.record_receipt(CIK, status="ok", completed=list(bindings), pending=[], gaps=[],
                                 observed_at=NOW, source_snapshots=bindings)
    else:
        from src.lifecycle_public_sources import SourceReadError
        def check():
            raise SourceReadError("source_read_cancelled")
    failed = service(rig).refresh(FILING_ID, requested, check=check)
    assert failed["capture_id"] is None and failed["outcome"] == "no_dispatch"
    assert len(rig.requests) == previous_requests
    assert reader.read(FILING_ID, capture_id=first["capture_id"], query="needle") == pinned
    assert reader.read(FILING_ID, document_id=requested)["status"] == "unavailable"
    other_page = reader.read(FILING_ID, document_id=other)
    assert other_page["status"] == "unavailable", {
        "requested": requested, "other": other, "failure": failure,
        "actual_status": other_page["status"],
        "reused_old_capture": other_page["data"]["document"]["capture_id"] == first["capture_id"],
    }


def test_review_invalid_report_does_not_erase_dispatched_request(rig):
    rig.enqueue()
    rig.queue[0] = Response(b"fixture error", status=600)
    result = service(rig).refresh(FILING_ID)
    assert result["capture_id"] is None
    assert rig.readers[0].request_count == len(rig.requests) == 1
    assert rig.readers[0].observations[0].status == 600
    assert result["outcome"] == "failed", result
    assert sum(row["report"]["requests"] for row in result["requests"]) == 1
