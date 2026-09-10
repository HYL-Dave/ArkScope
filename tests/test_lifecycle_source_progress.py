import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time

import pytest

from tests.test_lifecycle_web_store import AT, completed, setup_store, start
from tests.test_security_lifecycle_web_finding import source_page


@pytest.mark.parametrize("write", [False, True])
def test_web_journal_wait_is_bounded_below_the_unchanged_lease(tmp_path, write):
    from src.lifecycle_web_store import LEASE_SECONDS

    _, store = setup_store(tmp_path)
    with store.connection(write=write) as conn:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 45_000
    assert LEASE_SECONDS == 60


@pytest.mark.parametrize("competing_write", ["commit", "cancel", "busy"])
def test_web_journal_wait_preserves_owner_cancellation_and_failure(tmp_path, monkeypatch, competing_write):
    from src.lifecycle_web_store import WebJournalError

    path, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    connect, waiting = sqlite3.connect, Event()

    def scaled_connection(*args, **kwargs):
        # Exercise real SQLite contention at 1/100 of the configured wait.
        kwargs["timeout"] *= 0.01
        conn = connect(*args, **kwargs)
        conn.set_trace_callback(lambda sql: waiting.set() if sql == "BEGIN IMMEDIATE" else None)
        return conn

    with connect(path) as competing:
        competing.execute("BEGIN IMMEDIATE")
        if competing_write == "cancel":
            competing.execute("UPDATE lifecycle_web_runs SET cancel_requested_at=? WHERE run_id=?", (AT, identity))
        monkeypatch.setattr(sqlite3, "connect", scaled_connection)
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(store.heartbeat, identity, owner="worker-1")
            assert waiting.wait(5)
            if competing_write == "busy":
                with pytest.raises(WebJournalError, match="^web_recording_unavailable$"):
                    future.result(timeout=2)
            else:
                time.sleep(0.15)
                competing.commit()
                assert future.result(timeout=2) is (competing_write == "cancel")
    assert store.read(identity)["calls"] == {}


def test_historical_projection_does_not_decode_running_source_bodies(tmp_path, monkeypatch):
    from src.lifecycle_web_projection import latest_web_runs
    from src.lifecycle_web_store import LifecycleWebStore

    path, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    store.add_page(identity, owner="worker-1", source_id="source-1", page=source_page("Retained source."))

    def forbidden(row):
        raise AssertionError("progress must not decode uncompleted source bodies")

    monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(forbidden))
    with sqlite3.connect(path) as conn:
        rows = latest_web_runs(conn, ["case-1"], at=AT)
    assert len(rows) == 1
    result = rows[0]
    assert result["status"] == "queued"
    assert result["finding"] is result["source_reading"] is result["source_requests"] is None
    assert result["model_submissions"] == 0


def test_source_read_decoding_releases_its_owned_read_transaction(tmp_path, monkeypatch):
    from src.lifecycle_web_store import LifecycleWebStore

    path, store = setup_store(tmp_path)
    identity = completed(store)
    original, observed = LifecycleWebStore._decode_page, []

    def decode(row):
        with sqlite3.connect(path, timeout=0) as conn:
            conn.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
        observed.append(True)
        return original(row)

    monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(decode))
    assert store.read(identity)["finding"].action == "terminal_delisting"
    assert observed == [True]


def test_source_read_validation_releases_its_owned_read_transaction(tmp_path, monkeypatch):
    from src import lifecycle_web_store as journal

    path, store = setup_store(tmp_path)
    identity = completed(store)
    original, observed = journal.validate_finding, []

    def validate(*args, **kwargs):
        with sqlite3.connect(path, timeout=0) as conn:
            conn.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
        observed.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(journal, "validate_finding", validate)
    assert store.read(identity)["finding"].action == "terminal_delisting"
    assert observed == [True]


def test_transaction_bound_adoption_read_retains_caller_atomicity(tmp_path, monkeypatch):
    from src import lifecycle_web_store as journal

    path, store = setup_store(tmp_path)
    identity = completed(store)
    original, observed = journal.validate_finding, []

    def validate(*args, **kwargs):
        with sqlite3.connect(path, timeout=0) as other:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
        observed.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(journal, "validate_finding", validate)
    with store.connection(write=True) as conn:
        assert store.read_on_connection(conn, identity)["finding"].action == "terminal_delisting"
        assert conn.in_transaction
    assert observed == [True]


def test_connection_reader_does_not_hold_page_cursor_during_decoding(tmp_path, monkeypatch):
    from src.lifecycle_web_store import LifecycleWebStore

    path, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    for index in (1, 2):
        store.add_page(identity, owner="worker-1", source_id=f"source-{index}", page=source_page("Retained source."))
    original, observed = LifecycleWebStore._decode_page, []

    def decode(row):
        with sqlite3.connect(path, timeout=0) as other:
            other.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
        observed.append(True)
        return original(row)

    monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(decode))
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        result = store.read_on_connection(conn, identity)
        assert not conn.in_transaction
    assert len(result["pages"]) == 2 and observed == [True, True]


def test_source_read_keeps_snapshot_when_worker_adds_a_later_source(tmp_path, monkeypatch):
    from src.lifecycle_web_store import LifecycleWebStore

    _, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    store.add_page(identity, owner="worker-1", source_id="source-1", page=source_page("First source."))
    original, added = LifecycleWebStore._decode_page, []

    def decode(row):
        if not added:
            added.append(True)
            store.add_page(identity, owner="worker-1", source_id="source-2", page=source_page("Later source."))
            store.set_phase(identity, owner="worker-1", phase="reading_sources")
        return original(row)

    monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(decode))
    before = store.read(identity)
    assert before["status"] == "queued" and set(before["pages"]) == {"source-1"}
    after = store.read(identity)
    assert after["status"] == "reading_sources" and set(after["pages"]) == {"source-1", "source-2"}


def test_terminal_historical_projection_still_validates_source_integrity(tmp_path, monkeypatch):
    from src.lifecycle_web_projection import latest_web_runs
    from src.lifecycle_web_store import LifecycleWebStore, WebJournalError

    path, store = setup_store(tmp_path)
    completed(store)

    def corrupted(row):
        raise WebJournalError("web_journal_integrity")

    monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(corrupted))
    with sqlite3.connect(path) as conn:
        with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
            latest_web_runs(conn, ["case-1"], at=AT)
