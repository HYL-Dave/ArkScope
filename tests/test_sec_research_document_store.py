"""Immutable document records, original objects, and canonical schema owners."""

import hashlib
import sqlite3

import pytest

from tests.test_sec_research_document_service import FILING_ID, owner, rig, service


def test_immutable_original_and_text_registration_and_repeat_capture(rig):
    body = b"<p>needle retained</p>"
    rig.enqueue(body)
    first = service(rig).refresh(FILING_ID)
    rig.enqueue(body)
    second = service(rig).refresh(FILING_ID)
    assert first["capture_id"] and second["capture_id"] != first["capture_id"]
    documents = owner("document_store").DocumentStore(rig.store)
    a, b = documents.capture(first["capture_id"]), documents.capture(second["capture_id"])
    assert a["original_sha256"] == b["original_sha256"] == hashlib.sha256(body).hexdigest()
    assert a["text_sha256"] == b["text_sha256"] == hashlib.sha256(b"needle retained").hexdigest()
    assert a["metadata"]["extraction_version"] == "sec-document-text-v3"
    with rig.store.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM sec_research_objects WHERE sha256=?", (a["text_sha256"],)).fetchone()[0] == 1
        assert not list(conn.execute("PRAGMA foreign_key_check"))


@pytest.mark.parametrize("table", ["document_directories", "documents", "document_sources", "document_attempts"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "REPLACE"])
def test_document_records_reject_mutation(rig, table, operation):
    rig.enqueue()
    assert service(rig).refresh(FILING_ID)["capture_id"]
    table = "sec_research_" + table
    with rig.store.connect() as conn:
        row = conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
        assert row
        statement = (f"UPDATE {table} SET {row.keys()[0]}={row.keys()[0]}" if operation == "UPDATE"
                     else f"DELETE FROM {table}" if operation == "DELETE"
                     else f"INSERT OR REPLACE INTO {table} SELECT * FROM {table} LIMIT 1")
        with pytest.raises(sqlite3.IntegrityError, match="sec_research_immutable"):
            conn.execute(statement)


def test_document_schema_mismatch_preserves_unrelated_tables(rig):
    from src.sec_research import schema
    owner("document_store")
    with rig.store.connect() as conn:
        conn.execute("CREATE TABLE prices(sentinel TEXT)")
        conn.execute("INSERT INTO prices VALUES ('retained')")
    rig.store.install()
    with rig.store.connect() as conn:
        assert conn.execute("SELECT sentinel FROM prices").fetchone()[0] == "retained"
        conn.execute("CREATE INDEX foreign_document_index ON sec_research_documents(filing_id)")
        before = list(conn.execute("SELECT * FROM sqlite_master"))
        with pytest.raises(ValueError, match="sec_research_schema_mismatch"):
            schema.install(conn)
        assert list(conn.execute("SELECT * FROM sqlite_master")) == before
        assert conn.execute("SELECT sentinel FROM prices").fetchone()[0] == "retained"


@pytest.mark.parametrize("which", ["original_sha256", "text_sha256", "directory", "catalog"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_missing_or_corrupt_bound_object_rejects_stored_capture(rig, which, damage):
    rig.enqueue()
    result = service(rig).refresh(FILING_ID)
    document = owner("document_store").DocumentStore(rig.store).capture(result["capture_id"])
    sha = (document[which] if which.endswith("sha256") else document["metadata"]["directory_sha256"]
           if which == "directory" else document["metadata"]["sources"][0]["object_sha256"])
    path = rig.store.paths.capture_root / "objects" / sha
    if damage == "missing":
        path.unlink()
    else:
        body = path.read_bytes()
        path.write_bytes(b"X" + body[1:])
    page = owner("document_queries").DocumentQueries(rig.store, rig.captures).read(
        FILING_ID, capture_id=result["capture_id"])
    assert page["status"] == "unavailable" and not page["coverage"]["complete"]
    assert not page["data"]["passages"]
