from dataclasses import asdict, replace
import hashlib
import json

import pytest

from tests.test_security_lifecycle_web_finding import source_page


@pytest.mark.parametrize("text", [
    "plain ASCII", "quoted \"value\" \\ tab\tline\n", "\u4e0b\u5e02 / \U00020000",
    "x" * 65535 + "\U00020000\"\\" + "\u4e2d" * 70000,
], ids=["ascii", "escapes", "unicode", "chunk_boundary"])
def test_streamed_page_fingerprints_are_byte_identical_to_legacy_json(text):
    from src.lifecycle_public_sources import _capture_digest, _page_material_digest

    page = source_page(text)
    material = asdict(page)
    expected = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    assert _page_material_digest(material) == expected(material)
    material.pop("capture_sha256")
    assert _capture_digest(page) == expected(material)
    assert _capture_digest(replace(page, text=text + "changed")) != _capture_digest(page)


def test_large_page_hash_never_serializes_the_whole_source_at_once(monkeypatch):
    from src import lifecycle_public_sources as sources

    page = source_page("\U00020000" * (512 * 1024))
    expected = page.capture_sha256
    original = json.dumps
    chunks = []

    def bounded(value, **kwargs):
        if isinstance(value, dict):
            assert len(value.get("text", "")) <= 65536
        if isinstance(value, str):
            assert len(value) <= 65536
            chunks.append(len(value))
        return original(value, **kwargs)

    monkeypatch.setattr(sources.json, "dumps", bounded)
    assert sources._capture_digest(page) == expected
    assert len([length for length in chunks if length == 65536]) == 8


def test_unicode_source_journal_avoids_escape_expansion_without_changing_old_digests(tmp_path):
    from src.lifecycle_journal_codec import canonical_json, digest_json
    from tests.test_lifecycle_web_store import setup_store, start

    _, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    text = "\u6539\u540d \U00020000\n" * 10000
    page = source_page(text)
    store.add_page(identity, owner="worker-1", source_id="source-1", page=page)
    material = asdict(page)
    with store.connection(write=True) as conn:
        row = conn.execute("SELECT page_json,page_sha256 FROM lifecycle_web_pages WHERE run_id=?", (identity,)).fetchone()
        assert len(row["page_json"].encode()) < len(text.encode()) * 1.2
        assert row["page_sha256"] == digest_json(material)
        assert json.loads(row["page_json"])["text"] == text
        # Both encodings use the same canonical digest; no migration or rewriting.
        conn.execute("INSERT INTO lifecycle_web_pages VALUES (?,?,?,?)", (identity, "source-2", canonical_json(material), digest_json(material)))
    pages = store.read(identity)["pages"]
    assert pages["source-1"] == pages["source-2"] == page


@pytest.mark.parametrize("field", ["page_sha256", "capture_sha256"])
def test_source_journal_still_rejects_changed_page_and_capture_fingerprints(tmp_path, field):
    from src.lifecycle_journal_codec import canonical_json, digest_json
    from src.lifecycle_web_schema import WebJournalError
    from tests.test_lifecycle_web_store import setup_store, start

    _, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    material = asdict(source_page("\u4e0b\u5e02 \U00020000"))
    if field == "capture_sha256":
        material[field] = "0" * 64
    digest = "0" * 64 if field == "page_sha256" else digest_json(material)
    with store.connection(write=True) as conn:
        conn.execute("INSERT INTO lifecycle_web_pages VALUES (?,?,?,?)", (identity, "source-1", canonical_json(material), digest))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(identity)


@pytest.mark.parametrize("cancel", [False, True])
def test_final_source_validation_does_not_block_heartbeat_or_cancellation(tmp_path, monkeypatch, cancel):
    import sqlite3
    from src import lifecycle_web_store as journal
    from tests.test_lifecycle_web_store import setup_store, completed

    path, store = setup_store(tmp_path)
    original, observed = journal.validate_finding, []

    def validate(*args, **kwargs):
        # A different connection must commit while potentially large source
        # validation is in progress, including in rollback-journal mode.
        with sqlite3.connect(path, timeout=0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
            if cancel:
                conn.execute("UPDATE lifecycle_web_runs SET cancel_requested_at=created_at")
        observed.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(journal, "validate_finding", validate)
    if cancel:
        with pytest.raises(journal.WebJournalError, match="^stop_requested$"):
            completed(store)
        with store.connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_results").fetchone()[0] == 0
    else:
        completed(store)
        with store.connection() as conn:
            assert conn.execute("SELECT status FROM lifecycle_web_runs").fetchone()[0] == "succeeded"
    assert observed == [True]


def test_final_source_decoding_does_not_keep_a_read_transaction_open(tmp_path, monkeypatch):
    import sqlite3
    from src.lifecycle_web_store import LifecycleWebStore
    from tests.test_lifecycle_web_store import setup_store, completed

    path, store = setup_store(tmp_path)
    original, observed = LifecycleWebStore._decode_page, []

    def decode(row):
        with sqlite3.connect(path, timeout=0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
        observed.append(True)
        return original(row)

    monkeypatch.setattr(store, "_decode_page", decode)
    completed(store)
    assert observed == [True]


def test_changed_source_snapshot_cannot_commit_a_previously_validated_finding(tmp_path, monkeypatch):
    from src import lifecycle_web_store as journal
    from tests.test_lifecycle_web_store import setup_store, completed

    _, store = setup_store(tmp_path)
    original = journal.validate_finding

    def validate(*args, **kwargs):
        result = original(*args, **kwargs)
        with store.connection() as conn:
            identity = conn.execute("SELECT run_id FROM lifecycle_web_runs").fetchone()[0]
        store.add_page(identity, owner="worker-1", source_id="source-2", page=source_page("New contrary information."))
        return result

    monkeypatch.setattr(journal, "validate_finding", validate)
    with pytest.raises(journal.WebJournalError, match="^web_journal_integrity$"):
        completed(store)
    with store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_results").fetchone()[0] == 0


@pytest.mark.parametrize("mime", ["text/plain", "application/json", "application/xml"])
def test_full_context_reuses_the_retained_text_without_a_second_source_copy(mime):
    from src.lifecycle_public_sources import _capture_digest
    from src.lifecycle_source_context import select_source_context
    from tests.test_security_lifecycle_web_finding import public_input

    text = "\U00020000" * 50000
    if mime == "application/json":
        text = json.dumps({"description": text}, ensure_ascii=False)
    elif mime == "application/xml":
        text = "<description>" + text + "</description>"
    page = replace(source_page(text), mime_type=mime)
    page = replace(page, capture_sha256=_capture_digest(page))
    material = select_source_context(public_input(), page).prompt_material(page)
    assert material["coverage"] == "full_text"
    assert material["passages"][0]["text"] is page.text
    assert material["passages"][0]["end_byte"] == len(text.encode())
