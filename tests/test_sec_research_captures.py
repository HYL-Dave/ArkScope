"""Durable object publication uses small fixtures, never the default 100 GiB."""

import errno
import hashlib
import importlib.util
import multiprocessing
import shutil
import sqlite3
import os
from contextlib import contextmanager

import pytest


def test_capture_store_implementation_exists():
    assert importlib.util.find_spec("src.sec_research.captures") is not None


@pytest.fixture
def captures(tmp_path):
    from src.sec_research.captures import CaptureStore
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store
    store = Store(SecResearchPaths.from_market_db(tmp_path / "market.db"))
    store.install()
    budget = [100]
    captures = CaptureStore(store, budget=lambda: budget[0], free_bytes=lambda _: 2**40)
    captures.test_budget = budget
    return captures


def test_exact_bytes_reopen_and_deduplicate(captures):
    body = b'{"value":1234567890123456789.123}'
    sha = captures.put(body)
    assert sha == hashlib.sha256(body).hexdigest()
    assert captures.put(body) == sha
    assert captures.read(sha) == body
    assert captures.status()["persisted_bytes"] == len(body)
    assert captures.status()["charged_bytes"] == len(body)


def test_reduced_budget_blocks_growth_not_pinned_reads(captures):
    digest = captures.put(b"complete")
    captures.test_budget[0] = 1
    assert captures.read(digest) == b"complete"
    assert captures.put(b"complete") == digest
    with pytest.raises(ValueError, match="capture_budget_exceeded"):
        captures.put(b"new")
    assert captures.status()["over_budget"] is True


def test_capacity_rejected_before_any_stage_write(captures):
    captures.test_budget[0] = 2
    with pytest.raises(ValueError, match="capture_budget_exceeded"):
        captures.put(b"123")
    assert list((captures.store.paths.capture_root / "staging").iterdir()) == []
    assert captures.status()["charged_bytes"] == 0


def test_first_capture_fsyncs_directory_ancestry_before_register(captures, monkeypatch):
    observed = set()
    fsync = os.fsync
    def sync(fd):
        info = os.fstat(fd)
        observed.add((info.st_dev, info.st_ino))
        fsync(fd)
    monkeypatch.setattr(os, "fsync", sync)
    register = captures._register
    def check(*args):
        for path in (captures.store.paths.capture_root.parent, captures.store.paths.capture_root):
            info = path.stat()
            assert (info.st_dev, info.st_ino) in observed
        register(*args)
    monkeypatch.setattr(captures, "_register", check)
    captures.put(b"data")


def test_status_uses_one_sqlite_snapshot(captures, monkeypatch):
    from contextlib import contextmanager
    original = captures.store.connect
    queries = []
    @contextmanager
    def connection(*args, **kwargs):
        with original(*args, **kwargs) as conn:
            conn.set_trace_callback(queries.append)
            yield conn
    monkeypatch.setattr(captures.store, "connect", connection)
    captures.status()
    totals = [sql for sql in queries if "SUM(size_bytes)" in sql]
    assert len(totals) == 1 or "BEGIN" in queries


def test_status_reservation_conversion_uses_one_snapshot(captures, monkeypatch):
    from contextlib import contextmanager
    register = captures._register
    monkeypatch.setattr(captures, "_register", lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("interrupt")))
    with pytest.raises(ValueError):
        captures.put(b"data")
    monkeypatch.setattr(captures, "_register", register)
    original = captures.store.connect
    converted = False
    class Cursor:
        def __init__(self, cursor):
            self.cursor = cursor
        def fetchone(self):
            nonlocal converted
            value = self.cursor.fetchone()
            if not converted:
                converted = True
                captures.put(b"data")
            return value
    class Connection:
        def __init__(self, conn):
            self.conn = conn
        def execute(self, sql, *args):
            cursor = self.conn.execute(sql, *args)
            return Cursor(cursor) if "SUM(size_bytes)" in sql and not converted else cursor
    @contextmanager
    def connect(*args, **kwargs):
        with original(*args, **kwargs) as conn:
            yield Connection(conn) if kwargs.get("readonly") else conn
    monkeypatch.setattr(captures.store, "connect", connect)
    assert captures.status()["charged_bytes"] == 4
    assert converted


@pytest.mark.parametrize("target", ["root", "objects", "staging"])
def test_directory_enospc_is_capacity_failure(captures, monkeypatch, target):
    original = os.mkdir
    def mkdir(name, *args, **kwargs):
        if name == (captures.store.paths.capture_root.name if target == "root" else target):
            raise OSError(errno.ENOSPC, "private detail")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(os, "mkdir", mkdir)
    with pytest.raises(ValueError, match="^storage_space_insufficient$"):
        captures.put(b"data")


@pytest.mark.parametrize("operation", ["preflight", "recover"])
def test_public_capture_operations_normalize_raw_failures(captures, monkeypatch, operation):
    if operation == "preflight":
        monkeypatch.setattr(captures, "free_bytes", lambda _: (_ for _ in ()).throw(OSError(errno.EIO, "private detail")))
    else:
        monkeypatch.setattr(captures, "_recover", lambda _: (_ for _ in ()).throw(sqlite3.OperationalError("private detail")))
    with pytest.raises(ValueError, match="^capture_store_write_failed$"):
        getattr(captures, operation)()


def test_directory_sync_failure_then_retry_never_publishes_missing_bytes(captures, monkeypatch):
    original = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(errno.EIO, "private detail")))
    with pytest.raises(ValueError, match="^capture_store_write_failed$"):
        captures.put(b"data")
    assert captures._registered(hashlib.sha256(b"data").hexdigest()) is None
    monkeypatch.setattr(os, "fsync", original)
    digest = captures.put(b"data")
    assert captures.read(digest) == b"data"


def test_partial_stage_write_remains_charged_after_recovery(captures, monkeypatch):
    import src.sec_research.captures as module
    original = module.CaptureDirectory.stage
    def partial(directory, name, body):
        original(directory, name, body[:2])
        raise OSError(errno.ENOSPC, "private detail")
    monkeypatch.setattr(module.CaptureDirectory, "stage", partial)
    with pytest.raises(ValueError, match="storage_space_insufficient"):
        captures.put(b"four")
    assert captures.status()["charged_bytes"] == 4
    assert captures.recover()["charged_bytes"] == 2
    assert captures.status()["orphan_bytes"] == 2


def test_post_register_cleanup_failure_preserves_readable_object(captures, monkeypatch):
    import src.sec_research.captures as module
    monkeypatch.setattr(module.CaptureDirectory, "remove_stage", lambda *a: (_ for _ in ()).throw(OSError(errno.EIO, "private detail")))
    with pytest.raises(ValueError, match="capture_store_write_failed"):
        captures.put(b"data")
    digest = hashlib.sha256(b"data").hexdigest()
    assert captures.read(digest) == b"data"
    assert captures.recover()["charged_bytes"] == 4


def test_disk_space_is_independent_of_configured_budget(captures):
    captures.free_bytes = lambda _: 0
    with pytest.raises(ValueError, match="storage_space_insufficient"):
        captures.preflight()
    with pytest.raises(ValueError, match="storage_space_insufficient"):
        captures.put(b"data")


def test_corrupt_existing_object_never_overwritten_or_read(captures):
    digest = captures.put(b"complete")
    path = captures.store.paths.object_path("objects/" + digest)
    path.write_bytes(b"corrupt!")
    with pytest.raises(ValueError, match="capture_integrity_failed"):
        captures.put(b"complete")
    with pytest.raises(ValueError, match="capture_integrity_failed"):
        captures.read(digest)
    assert path.read_bytes() == b"corrupt!"


def test_publication_never_replaces_a_racing_destination(captures, monkeypatch):
    import src.sec_research.captures as module
    body = b"requested"
    digest = hashlib.sha256(body).hexdigest()
    target = captures.store.paths.object_path("objects/" + digest)
    original = module.CaptureDirectory.stage
    def inject(directory, stage, data):
        original(directory, stage, data)
        target.write_bytes(b"existing")
    monkeypatch.setattr(module.CaptureDirectory, "stage", inject)
    with pytest.raises(ValueError, match="capture_store_write_failed"):
        captures.put(body)
    assert target.read_bytes() == b"existing"
    assert captures._registered(digest) is None


def test_interrupted_stage_remains_charged_after_recovery(captures, monkeypatch):
    import src.sec_research.captures as module
    original = module.CaptureDirectory.publish
    monkeypatch.setattr(module.CaptureDirectory, "publish", lambda *a: (_ for _ in ()).throw(OSError(errno.ENOSPC, "private detail")))
    with pytest.raises(ValueError, match="storage_space_insufficient"):
        captures.put(b"stage")
    assert captures.status()["charged_bytes"] == 5
    monkeypatch.setattr(module.CaptureDirectory, "publish", original)
    assert captures.recover()["orphan_bytes"] == 5
    assert captures.status()["reserved_bytes"] == 0
    captures.test_budget[0] = 5
    with pytest.raises(ValueError, match="capture_budget_exceeded"):
        captures.preflight()


def test_published_uncommitted_object_is_not_lost(captures, monkeypatch):
    original = captures._register
    monkeypatch.setattr(captures, "_register", lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("private database detail")))
    with pytest.raises(ValueError, match="capture_store_write_failed"):
        captures.put(b"orphan")
    monkeypatch.setattr(captures, "_register", original)
    status = captures.recover()
    # The stage and object hard link consume one body allocation, not two.
    assert status["charged_bytes"] == 6
    digest = captures.put(b"orphan")
    assert captures.read(digest) == b"orphan"
    assert captures.status()["persisted_bytes"] == 6


def test_missing_object_is_not_an_empty_capture(captures):
    digest = captures.put(b"data")
    captures.store.paths.object_path("objects/" + digest).unlink()
    with pytest.raises(ValueError, match="capture_integrity_failed"):
        captures.read(digest)


def test_local_reads_create_no_new_capture_files(captures):
    assert not captures.store.paths.capture_root.exists()
    assert captures.status()["charged_bytes"] == 0
    assert not captures.store.paths.capture_root.exists()


def _interrupted_writer(path, staged, release):
    from src.sec_research.captures import CaptureStore, CaptureDirectory
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store
    original = CaptureDirectory.publish

    def pause(directory, stage, sha):
        staged.set()
        release.wait(20)
        return original(directory, stage, sha)

    CaptureDirectory.publish = pause
    CaptureStore(Store(SecResearchPaths.from_market_db(path)), budget=lambda: 10,
                 free_bytes=lambda _: 2**40).put(b"staged")


def test_live_worker_cannot_be_recovered_but_dead_worker_can(captures):
    context = multiprocessing.get_context("fork")
    staged, release = context.Event(), context.Event()
    process = context.Process(target=_interrupted_writer,
                              args=(captures.store.paths.market_db_path, staged, release))
    process.start()
    try:
        assert staged.wait(10)
        legacy_lock = captures.store.paths.capture_root / ".writer.lock"
        legacy_lock.unlink(missing_ok=True)
        legacy_lock.write_bytes(b"replacement must not change coordination identity")
        with pytest.raises(ValueError, match="capture_store_busy"):
            captures.recover()
        assert captures.status()["reserved_bytes"] == 6
        process.terminate()
        process.join(10)
        assert not process.is_alive()
        assert captures.recover()["charged_bytes"] == 6
        assert captures.status()["orphan_bytes"] == 6
        assert captures.status()["reserved_bytes"] == 0
    finally:
        if process.is_alive():
            process.terminate()
        process.join(10)


def test_capture_reopens_after_database_and_root_move(captures, tmp_path):
    from src.sec_research.captures import CaptureStore
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store
    digest = captures.put(b"portable")
    destination = tmp_path / "new"
    destination.mkdir()
    paths = SecResearchPaths.from_market_db(destination / "renamed.db")
    shutil.copy2(captures.store.paths.market_db_path, paths.market_db_path)
    shutil.copytree(captures.store.paths.capture_root, paths.capture_root)
    moved = CaptureStore(Store(paths), budget=lambda: 1)
    assert moved.read(digest) == b"portable"
    assert moved.status()["over_budget"] is True


def interrupted_publication(captures, monkeypatch, phase="before_register", body=b"publication"):
    from src.sec_research.capture_lock import CaptureDirectory

    def fail(*args):
        raise sqlite3.OperationalError("fixture publication interruption")

    with monkeypatch.context() as patch:
        if phase == "before_register":
            patch.setattr(captures, "_register", fail)
        else:
            method = "publish" if phase == "before_publish" else "remove_stage"
            patch.setattr(CaptureDirectory, method, fail)
        with pytest.raises(ValueError, match="^capture_store_write_failed$"):
            captures.put(body)
    root = captures.store.paths.capture_root
    sha = hashlib.sha256(body).hexdigest()
    stages = list((root / "staging").iterdir())
    assert len(stages) == 1
    return sha, root / "objects" / sha, stages[0]


def test_publication_recovery_after_registration_retains_exact_read_and_single_charge(captures, monkeypatch):
    sha, target, stage = interrupted_publication(captures, monkeypatch, "after_register")
    assert target.stat().st_nlink == 2
    assert captures.read(sha) == b"publication"
    for _ in range(2):
        state = captures.recover()
        assert not stage.exists(), "registered publication still has its redundant staging name"
        assert target.stat().st_nlink == 1
        assert captures.read(sha) == b"publication"
        assert (state["persisted_bytes"], state["orphan_bytes"], state["reserved_bytes"]) == (11, 0, 0)
        assert state["charged_bytes"] == 11


@pytest.mark.parametrize("fault", ["accounting_commit", "unlink", "stage_fsync"])
def test_publication_recovery_failure_preserves_charge_and_retry_converges(captures, monkeypatch, fault):
    _, target, stage = interrupted_publication(captures, monkeypatch)
    connect, unlink, fsync = captures.store.connect, os.unlink, os.fsync
    parent = stage.parent.stat()

    @contextmanager
    def fail_commit(*args, **kwargs):
        with connect(*args, **kwargs) as conn:
            if not kwargs.get("readonly"):
                conn.set_authorizer(lambda action, name, *_: sqlite3.SQLITE_DENY
                    if action == sqlite3.SQLITE_TRANSACTION and name == "COMMIT" else sqlite3.SQLITE_OK)
            yield conn

    def check_accounting():
        with connect(readonly=True) as conn:
            assert [tuple(row) for row in conn.execute("SELECT * FROM sec_research_orphans")] == [
                ("objects/" + target.name, 11)]
            assert conn.execute("SELECT COUNT(*) FROM sec_research_reservations").fetchone()[0] == 0

    def fail_unlink(name, *args, **kwargs):
        if name == stage.name:
            check_accounting()
            raise OSError(errno.EIO, "fixture unlink failure after accounting commit")
        return unlink(name, *args, **kwargs)

    def fail_fsync(fd):
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == (parent.st_dev, parent.st_ino) and not stage.exists():
            check_accounting()
            raise OSError(errno.EIO, "fixture post-unlink directory durability failure")
        return fsync(fd)

    with monkeypatch.context() as patch:
        if fault == "accounting_commit":
            patch.setattr(captures.store, "connect", fail_commit)
        elif fault == "unlink":
            patch.setattr(os, "unlink", fail_unlink)
        else:
            patch.setattr(os, "fsync", fail_fsync)
        with pytest.raises(ValueError, match="^capture_store_write_failed$"):
            captures.recover()
        assert target.read_bytes() == b"publication"
        assert stage.exists() is (fault != "stage_fsync")
        state = captures.status()
        assert state["charged_bytes"] == 11
        assert (state["orphan_bytes"], state["reserved_bytes"]) == (
            (0, 11) if fault == "accounting_commit" else (11, 0))
        # Retrying an unresolved failure must not acknowledge durability or erase its charge.
        with pytest.raises(ValueError, match="^capture_store_write_failed$"):
            captures.recover()
        assert captures.status()["charged_bytes"] == 11
    for _ in range(2):
        state = captures.recover()
        assert not stage.exists(), "retry did not converge to a single published name"
        assert target.read_bytes() == b"publication" and target.stat().st_nlink == 1
        assert (state["orphan_bytes"], state["reserved_bytes"], state["charged_bytes"]) == (11, 0, 11)


def _published_writer(path, published, release):
    from src.sec_research.captures import CaptureStore
    from src.sec_research.paths import SecResearchPaths
    from src.sec_research.store import Store

    captures = CaptureStore(Store(SecResearchPaths(path)), budget=lambda: 100, free_bytes=lambda _: 2**40)
    register = captures._register

    def pause(*args):
        published.set()
        release.wait(20)
        return register(*args)

    captures._register = pause
    captures.put(b"publication")


def test_publication_recovery_excludes_live_worker_then_recovers_dead_worker(captures):
    context = multiprocessing.get_context("fork")
    published, release = context.Event(), context.Event()
    process = context.Process(target=_published_writer,
        args=(captures.store.paths.market_db_path, published, release))
    process.start()
    try:
        assert published.wait(10)
        target = captures.store.paths.capture_root / "objects" / hashlib.sha256(b"publication").hexdigest()
        assert target.stat().st_nlink == 2
        with pytest.raises(ValueError, match="^capture_store_busy$"):
            captures.recover()
        assert captures.status()["reserved_bytes"] == 11
        process.terminate()
        process.join(10)
        assert not process.is_alive()
        state = captures.recover()
        assert list((captures.store.paths.capture_root / "staging").iterdir()) == []
        assert target.read_bytes() == b"publication" and target.stat().st_nlink == 1
        assert (state["orphan_bytes"], state["reserved_bytes"], state["charged_bytes"]) == (11, 0, 11)
    finally:
        if process.is_alive():
            process.terminate()
        process.join(10)
