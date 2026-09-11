"""Source snapshots and caller transactions are owned by the current journal."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3
from threading import Event

import pytest

from src.lifecycle_investigation import adoption
from src.lifecycle_investigation.sources import capture_text
from src.security_lifecycle_provider_snapshot import instant
from tests.test_lifecycle_investigation_attended_concurrency import observe_source_work
from tests.test_lifecycle_investigation_review import context
from tests.test_lifecycle_investigation_store import running


def source(text):
    return capture_text(text, url="https://issuer.example/notice",
        retrieved_at="2026-09-08T00:00:00Z", coverage="full_text")


@pytest.mark.parametrize("write", [False, True])
def test_current_journal_wait_is_bounded_below_the_lease(tmp_path, write):
    _, store, identity, _ = running(tmp_path)
    row = store.read(identity)
    lease_seconds = (instant(row["lease_until"]) - instant(row["created_at"])).total_seconds()
    with store.connection(write=write) as conn:
        timeout_seconds = conn.execute("PRAGMA busy_timeout").fetchone()[0] / 1000
    assert 0 < timeout_seconds < lease_seconds


@pytest.mark.parametrize("competing_write", ["commit", "cancel", "busy"])
def test_current_journal_wait_preserves_cancellation_and_failure(tmp_path, monkeypatch, competing_write):
    c, store, identity, _ = running(tmp_path)
    connect, waiting = sqlite3.connect, Event()
    def scaled_connection(*args, **kwargs):
        kwargs["timeout"] *= 0.03
        conn = connect(*args, **kwargs)
        conn.set_trace_callback(lambda sql: waiting.set() if sql == "BEGIN IMMEDIATE" else None)
        return conn
    with connect(c["profile"]) as competing:
        competing.execute("BEGIN IMMEDIATE")
        if competing_write == "cancel":
            competing.execute("UPDATE lifecycle_investigation_jobs SET cancel_requested_at=? WHERE run_id=?", (c["now"][0], identity))
        monkeypatch.setattr(sqlite3, "connect", scaled_connection)
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(store.heartbeat, identity, owner="worker")
            assert waiting.wait(3)
            if competing_write == "busy":
                with pytest.raises(ValueError, match="^investigation_recording_unavailable$"):
                    future.result(timeout=2)
            else:
                competing.commit()
                assert future.result(timeout=2) is (competing_write == "cancel")
    assert store.read(identity)["calls"] == []


def test_current_source_read_decoding_releases_its_owned_read_transaction(tmp_path, monkeypatch):
    c, store, identity, _ = running(tmp_path)
    store.source(identity, owner="worker", source_id="source-1", payload=source("First retained source."))
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    observed = []
    def heartbeat():
        observed.append(store.heartbeat(identity, owner="worker"))
    observe_source_work(monkeypatch, heartbeat)
    assert store.read(identity)["sources"]["source-1"]["text"] == "First retained source."
    assert observed == [False]


def test_current_transaction_bound_adoption_read_retains_caller_atomicity(tmp_path, monkeypatch):
    c = context(tmp_path)
    observed = []
    def blocked_writer():
        with sqlite3.connect(c["profile"], timeout=0) as other:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("BEGIN IMMEDIATE")
        observed.append(True)
    observe_source_work(monkeypatch, blocked_writer, phase="finding")
    with c["investigation"].connection(write=True) as conn:
        assert adoption.read_on_connection(conn, c["run_id"])["finding"].action == "terminal_delisting"
        assert conn.in_transaction
    assert observed == [True]


def test_current_connection_reader_releases_source_cursor_before_decoding(tmp_path, monkeypatch):
    c, store, identity, _ = running(tmp_path)
    for index in (1, 2):
        store.source(identity, owner="worker", source_id=f"source-{index}", payload=source(f"Retained source {index}."))
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    observed = []
    observe_source_work(monkeypatch, lambda: observed.append(store.heartbeat(identity, owner="worker")))
    with sqlite3.connect(c["profile"]) as conn:
        conn.row_factory = sqlite3.Row
        result = store.read_on_connection(conn, identity)
        assert not conn.in_transaction
    assert len(result["sources"]) == 2 and observed == [False, False]


def test_current_source_read_keeps_snapshot_when_worker_adds_a_later_source(tmp_path, monkeypatch):
    c, store, identity, _ = running(tmp_path)
    store.source(identity, owner="worker", source_id="source-1", payload=source("First source."))
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    added = []
    def add_later():
        if not added:
            added.append(True)
            store.source(identity, owner="worker", source_id="source-2", payload=source("Later source."))
            store.step(identity, owner="worker", kind="source_captured", payload={"source_id": "source-2"})
    observe_source_work(monkeypatch, add_later)
    before = store.read(identity)
    assert before["phase"] == "queued" and before["steps"] == []
    assert set(before["sources"]) == {"source-1"}
    after = store.read(identity)
    assert after["phase"] == "source_captured"
    assert set(after["sources"]) == {"source-1", "source-2"}
