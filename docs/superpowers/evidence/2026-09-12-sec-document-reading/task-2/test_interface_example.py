"""Generate parent integration examples from disposable real-owner fixtures."""

import json
import os
from pathlib import Path

from tests.test_sec_research_document_service import FILING_ID, owner, rig, service


def test_emit_interface_examples(rig):
    rig.enqueue()
    refreshed = service(rig).refresh(FILING_ID)
    reads = owner("document_queries").DocumentQueries(rig.store, rig.captures)
    index = reads.read(FILING_ID, capture_id=refreshed["capture_id"])
    text = reads.read(FILING_ID, cursor=index["data"]["text_start_cursor"])
    search = reads.read(FILING_ID, capture_id=refreshed["capture_id"], query="needle", max_chars=80)
    assert refreshed["status"] == index["status"] == text["status"] == search["status"] == "ok"
    assert text["data"]["passages"][0]["text"] == "Item 1. Business\nneedle one needle two"
    destination = Path(os.environ["ARKSCOPE_OFFLINE_TEST_WORKSPACE"]) / "interface-examples.json"
    destination.write_text(json.dumps({"refresh": refreshed, "index": index, "text": text,
                                      "search": search}, ensure_ascii=True, indent=2) + "\n")
