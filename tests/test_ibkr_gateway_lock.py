"""Shared IBKR Gateway lock (PG-exit precursor) — the one mutex every IBKR consumer uses."""

from __future__ import annotations

import threading
import time

import pytest

import src.ibkr_gateway_lock as gw
from src.ibkr_gateway_lock import FileLock, ibkr_gateway_lock, lock_dir


@pytest.fixture(autouse=True)
def _isolated_lockdir(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))


def test_context_manager_acquires_and_releases():
    with ibkr_gateway_lock(timeout=2):
        assert gw.IBKR_THREAD_LOCK.locked()       # held inside
    assert not gw.IBKR_THREAD_LOCK.locked()       # released after


def test_second_acquire_times_out_while_held():
    # the in-process thread lock makes a concurrent acquire fail fast (raises TimeoutError).
    with ibkr_gateway_lock(timeout=2):
        with pytest.raises(TimeoutError):
            with ibkr_gateway_lock(timeout=0.2):
                pass


def test_scheduler_shares_the_same_objects():
    # data_scheduler must serialize on the SAME singletons (not its own copies) — that's the
    # whole point of the extraction.
    import src.service.data_scheduler as ds
    assert ds._IBKR_LOCK is gw.IBKR_THREAD_LOCK
    assert ds._IBKR_FLOCK is gw.IBKR_FILE_LOCK
    # and the moved infra is the shared one
    assert ds._FileLock is FileLock and ds._lock_dir is lock_dir


def test_thread_lock_released_even_if_file_lock_times_out(monkeypatch):
    # if the file lock can't be had, the thread lock must still be released (no wedge).
    monkeypatch.setattr(gw.IBKR_FILE_LOCK, "acquire", lambda timeout=0, poll=5.0: False)
    with pytest.raises(TimeoutError, match="another process"):
        with ibkr_gateway_lock(timeout=0.2):
            pass
    assert not gw.IBKR_THREAD_LOCK.locked()       # thread lock released despite the file-lock failure


def test_mutual_exclusion_serializes_two_threads():
    order = []
    def worker(tag):
        with ibkr_gateway_lock(timeout=5):
            order.append(f"{tag}-in")
            time.sleep(0.05)
            order.append(f"{tag}-out")
    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()
    # whichever ran first, its in/out are adjacent (no interleave) → serialized
    assert order in (["a-in", "a-out", "b-in", "b-out"], ["b-in", "b-out", "a-in", "a-out"])


def test_filelock_cross_process_dir_resolution(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "lk"))
    assert lock_dir() == tmp_path / "lk"
    fl = FileLock("probe")
    assert fl.acquire(timeout=1) is True
    assert (tmp_path / "lk" / "probe.lock").exists()
    fl.release()
