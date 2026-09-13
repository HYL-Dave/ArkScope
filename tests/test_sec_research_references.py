"""Fail-closed maintenance roots, without any cleanup or profile iteration."""

from copy import deepcopy
import json

import pytest

from src.sec_research.document_store import DocumentStore
from tests.test_sec_research_citations import evidence, publish_facts, fact_ref, bind_sources, FACT_URL, LATER
from tests.test_sec_research_document_service import CIK, FILING_ID, NOW, bind_catalog, owner, rig
from src.sec_research.queries import StoredQueries


def test_reference_closure_retains_directory_catalog_and_fact_objects(evidence):
    api, r = owner("references"), evidence.rig
    ref = evidence.document_ref
    doc = DocumentStore(r.store).capture(ref["capture_id"])
    result = api.sec_reference_closure(r.store, citations=[ref])
    snapshots = sorted(binding["snapshot_id"] for binding in evidence.receipt["source_snapshots"].values())
    hashes = {ref["original_sha256"], ref["text_sha256"], doc["metadata"]["directory_sha256"],
              *[r.store.snapshot(CIK, sid)["object_sha256"] for sid in snapshots]}
    assert result["capture_ids"] == [ref["capture_id"]]
    assert result["directory_ids"] == [doc["directory_id"]]
    assert result["snapshot_ids"] == snapshots
    assert result["receipt_ids"] == [evidence.receipt["receipt_id"]]
    assert result["fact_ids"] == [evidence.fact_ref["fact_id"]]
    assert result["filing_ids"] == [FILING_ID]
    assert result["object_sha256s"] == sorted(hashes)
    assert result["object_keys"] == ["objects/" + sha for sha in sorted(hashes)]
    assert len(result["filing_observations"]) == 2
    assert result["fact_observations"] == [{"snapshot_id": evidence.fact_ref["snapshot_id"],
        "ordinal": 0, "fact_id": evidence.fact_ref["fact_id"]}]
    assert api.sec_reference_closure(r.store, citations=[ref, ref]) == result


def test_closure_is_sorted_independent_of_reference_order_and_includes_unbound_fact_ids(evidence):
    api, r = owner("references"), evidence.rig
    sid = publish_facts(r, "77")
    row = r.store.snapshot_observations(CIK, sid)[0]
    exact = StoredQueries(r.store).facts(CIK, fact_ids=[row["fact_id"]])
    refs = [evidence.document_ref, fact_ref(exact["data"][0]), *evidence.filing_refs]
    result = api.sec_reference_closure(r.store, citations=refs)
    assert sid in result["snapshot_ids"] and row["fact_id"] in result["fact_ids"]
    assert api.sec_reference_closure(r.store, citations=reversed(refs)) == result
    assert all(value == [] for value in api.sec_reference_closure(r.store, citations=[]).values())


@pytest.mark.parametrize("node", ["directory", "catalog", "fact", "original", "text"])
def test_missing_or_corrupt_retained_object_fails_closure_and_exact_read(evidence, node):
    api, r = owner("references"), evidence.rig
    doc = DocumentStore(r.store).capture(evidence.document_ref["capture_id"])
    assert doc["original_sha256"] != doc["text_sha256"]
    sha = {"directory": doc["metadata"]["directory_sha256"],
           "catalog": doc["metadata"]["catalog_sources"][0]["object_sha256"],
           "fact": evidence.fact_ref["source_sha256"],
           "original": doc["original_sha256"], "text": doc["text_sha256"]}[node]
    r.store.paths.object_path("objects/" + sha).write_bytes(b"PRIVATE corrupt retained bytes")
    with pytest.raises(owner("citations").CitationError, match="^sec_citation_integrity_failed$"):
        api.sec_reference_closure(r.store, citations=[evidence.document_ref])
    page = owner("citations").read_sec_citation(r.store, r.captures, citation=evidence.document_ref)
    assert page["status"] == ("ok" if node == "fact" else "unavailable")
    assert "PRIVATE" not in json.dumps(page)


def corrupt_row(store, table, sql, params):
    """Change a disposable immutable row while restoring the canonical trigger."""
    with store.connect() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        name = f"sec_research_{table}_no_update"
        trigger = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        conn.execute(f"DROP TRIGGER {name}")
        conn.execute(sql, params)
        conn.execute(trigger)


@pytest.mark.parametrize("node", ["fact_value", "filing_pointer", "receipt_binding", "catalog_provenance"])
def test_corrupt_metadata_cannot_become_citation_or_maintenance_authority(evidence, node):
    api, r = owner("references"), evidence.rig
    if node == "fact_value":
        corrupt_row(r.store, "facts", "UPDATE sec_research_facts SET value=? WHERE fact_id=?",
                    ("999", evidence.fact_ref["fact_id"]))
    elif node == "filing_pointer":
        corrupt_row(r.store, "filings", "UPDATE sec_research_filings SET source_pointer=?", ("/wrong",))
    elif node == "receipt_binding":
        bindings = deepcopy(evidence.receipt["source_snapshots"])
        bindings["companyfacts"]["snapshot_id"] = "secsnapshot_" + "0" * 64
        corrupt_row(r.store, "receipts", "UPDATE sec_research_receipts SET source_snapshots=? WHERE receipt_id=?",
                    (json.dumps(bindings), evidence.receipt["receipt_id"]))
    else:
        corrupt_row(r.store, "document_sources", "UPDATE sec_research_document_sources SET provenance=?", ("{}",))
    with pytest.raises(owner("citations").CitationError):
        api.sec_reference_closure(r.store, citations=[evidence.document_ref])


def test_duplicate_catalog_provenance_is_rejected_even_with_matching_document_identity(evidence):
    r = evidence.rig
    documents = DocumentStore(r.store)
    doc = documents.capture(evidence.document_ref["capture_id"])
    metadata = deepcopy(doc["metadata"])
    metadata["catalog_sources"].append(deepcopy(metadata["catalog_sources"][0]))
    from src.sec_research.document_store import _identity
    new_id = _identity("secdoc_", metadata)
    corrupt_row(r.store, "documents", "UPDATE sec_research_documents SET capture_id=?,metadata=? WHERE capture_id=?",
                (new_id, json.dumps(metadata), doc["capture_id"]))
    corrupt_row(r.store, "document_sources", "UPDATE sec_research_document_sources SET capture_id=?", (new_id,))
    with pytest.raises(owner("citations").CitationError):
        owner("references").sec_reference_closure(r.store, citations=[evidence.document_ref | {"capture_id": new_id}])


def test_closure_aggregate_exceeds_per_object_budget_with_bounded_source_processing(rig, monkeypatch):
    import gc
    import tracemalloc
    from src.sec_research import captures
    from src.sec_research.facts import parse_companyfacts

    api = owner("references")
    per_object_limit = 64 * 1024
    monkeypatch.setattr(captures, "MAX_OBJECT_BYTES", per_object_limit)
    monkeypatch.setattr(api, "MAX_OBJECT_BYTES", per_object_limit)
    sid = publish_facts(rig)
    original = rig.captures.read(rig.store.snapshot(CIK, sid)["object_sha256"])
    original = original.replace(b'"10-K"', json.dumps("F" * 32768).encode())
    refs, total = [], 0
    for index in range(60):
        body = original.replace(b'"fy":2025', f'"fy":{2000 + index}'.encode())
        assert len(body) < per_object_limit
        parsed = parse_companyfacts(body, cik=CIK)
        sid = rig.store.publish(parsed, object_sha256=rig.captures.put(body), observed_at=NOW, source_url=FACT_URL)
        fact = parsed.facts[0]
        refs.append({"kind": "fact", "cik": CIK, "fact_id": fact.fact_id, "snapshot_id": sid,
            "source_sha256": parsed.sha256, "source_pointer": fact.source.pointer,
            "source_url": FACT_URL, "observed_at": NOW})
        total += len(body)
    assert total > 30 * per_object_limit
    del original, parsed, fact, body
    gc.collect()
    tracemalloc.start()
    try:
        result = api.sec_reference_closure(rig.store, citations=iter(refs))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result["snapshot_ids"] == sorted(ref["snapshot_id"] for ref in refs)
    assert len(result["fact_observations"]) == 60 and len(result["object_keys"]) == 60
    assert peak < 12 * per_object_limit, f"parsed source payloads accumulated: peak={peak}"


@pytest.mark.parametrize("kind", ["fact", "filing", "document"])
def test_exact_read_is_not_invalidated_by_later_unrelated_receipt_members(evidence, kind):
    api, r = owner("citations"), evidence.rig
    ref = {"fact": evidence.fact_ref, "filing": evidence.filing_refs[0], "document": evidence.document_ref}[kind]
    bindings = deepcopy(evidence.receipt["source_snapshots"])
    if kind == "fact":
        locator = "CIK0000320193-submissions-002.json"
        sid = bind_catalog(r.store, r.captures, history=locator, primary="other.htm", bind=False)
    else:
        locator = "companyfacts"
        sid = publish_facts(r, "999")
    bindings[locator] = {"snapshot_id": sid, "observed_at": LATER}
    bind_sources(r, bindings, observed_at=LATER)
    sha = r.store.snapshot(CIK, sid)["object_sha256"]
    r.store.paths.object_path("objects/" + sha).write_bytes(b"unrelated corrupt source")
    assert api.read_sec_citation(r.store, r.captures, citation=ref)["status"] == "ok"
    if kind != "document":
        with pytest.raises(api.CitationError):
            owner("references").sec_reference_closure(r.store, citations=[ref])
