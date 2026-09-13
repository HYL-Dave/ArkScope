"""Original-byte objects with durable capacity accounting, never implicit pruning."""

from __future__ import annotations

from contextlib import contextmanager
import errno
import hashlib
import shutil
import sqlite3
import uuid

from src.market_data_direct import market_write_lock
from src.sec_research.capture_lock import CaptureDirectory, capture_writer, store_operation
from src.sec_research.config import _validate_capture_budget_bytes


METADATA_SPACE_MARGIN = 256 * 1024**2
MAX_OBJECT_BYTES = 128 * 1024**2


@contextmanager
def _storage_errors():
    try:
        yield
    except OSError as exc:
        code = "storage_space_insufficient" if exc.errno == errno.ENOSPC else "capture_store_write_failed"
        raise ValueError(code) from None
    except (sqlite3.Error, TimeoutError):
        raise ValueError("capture_store_write_failed") from None


class CaptureStore:
    def __init__(self, store, *, budget, free_bytes=None):
        self.store = store
        self.budget = budget
        self.free_bytes = free_bytes or (lambda path: shutil.disk_usage(path).free)

    @contextmanager
    def _write(self):
        with market_write_lock(), self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def status(self):
        with _storage_errors(), self.store.connect(readonly=True) as conn:
            totals = tuple(conn.execute("""SELECT
                (SELECT COALESCE(SUM(size_bytes),0) FROM sec_research_objects),
                (SELECT COALESCE(SUM(size_bytes),0) FROM sec_research_orphans),
                (SELECT COALESCE(SUM(size_bytes),0) FROM sec_research_reservations)""").fetchone())
        limit = _validate_capture_budget_bytes(self.budget())
        total = sum(totals)
        return dict(persisted_bytes=totals[0], orphan_bytes=totals[1], reserved_bytes=totals[2],
                    charged_bytes=total, budget_bytes=limit, remaining_bytes=max(0, limit-total),
                    over_budget=total > limit)

    def _recover(self, directory):
        # Owning the root lease proves that no live writer owns these reservations.
        # An absent entry may be an unlink whose parent fsync failed. Do not erase
        # its durable charge until the namespace itself has become durable.
        directory.sync()
        files = directory.files()
        with self._write() as conn:
            registered = {row[0] for row in conn.execute("SELECT object_key FROM sec_research_objects")}
            known_inodes = {inode for key, _, inode in files if key in registered}
            orphans = []
            for key, size, inode in files:
                if key in registered or inode in known_inodes:
                    continue
                known_inodes.add(inode)
                orphans.append((key, size))
            conn.execute("DELETE FROM sec_research_orphans")
            conn.executemany("INSERT INTO sec_research_orphans VALUES(?,?)", orphans)
            conn.execute("DELETE FROM sec_research_reservations")
        # The published inode is now durably charged. Alias verification and
        # directory durability must not hold the shared market writer lock.
        directory.recover_published_stages(files)

    def recover(self):
        with _storage_errors(), capture_writer(self.store.paths.capture_root) as directory:
            self._recover(directory)
        return self.status()

    def _admit(self, size):
        state = self.status()
        if state["charged_bytes"] + size > state["budget_bytes"] or (size == 0 and state["remaining_bytes"] == 0):
            raise ValueError("capture_budget_exceeded")
        root = self.store.paths.capture_root
        destination = root if root.exists() else root.parent
        if self.free_bytes(destination) < size + METADATA_SPACE_MARGIN:
            raise ValueError("storage_space_insufficient")

    def preflight(self):
        with _storage_errors(), capture_writer(self.store.paths.capture_root) as directory:
            self._recover(directory)
            self._admit(0)

    def _registered(self, sha):
        with self.store.connect(readonly=True) as conn:
            row = conn.execute("SELECT object_key,size_bytes FROM sec_research_objects WHERE sha256=?", (sha,)).fetchone()
            return tuple(row) if row is not None else None

    @staticmethod
    def _verify(directory, sha, size):
        body = directory.read("objects/" + sha, size)
        if hashlib.sha256(body).hexdigest() != sha:
            raise ValueError("capture_integrity_failed")
        return body

    @store_operation
    def read(self, sha):
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("capture_id_invalid")
        row = self._registered(sha)
        if row is None:
            raise ValueError("capture_not_found")
        if row[0] != "objects/" + sha or not 0 <= row[1] <= MAX_OBJECT_BYTES:
            raise ValueError("capture_integrity_failed")
        directory = None
        try:
            directory = CaptureDirectory(self.store.paths.capture_root)
            return self._verify(directory, sha, row[1])
        except OSError:
            raise ValueError("capture_integrity_failed") from None
        finally:
            if directory is not None:
                directory.close()

    def _register(self, sha, size, reservation):
        with self._write() as conn:
            conn.execute("INSERT INTO sec_research_objects VALUES(?,?,?)", (sha, "objects/" + sha, size))
            conn.execute("DELETE FROM sec_research_orphans WHERE object_key=?", ("objects/" + sha,))
            conn.execute("DELETE FROM sec_research_reservations WHERE reservation_id=?", (reservation,))

    def put(self, body):
        if type(body) is not bytes or len(body) > MAX_OBJECT_BYTES:
            raise ValueError("capture_body_invalid")
        sha = hashlib.sha256(body).hexdigest()
        with _storage_errors():
            with capture_writer(self.store.paths.capture_root) as directory:
                self._recover(directory)
                row = self._registered(sha)
                if row is not None:
                    if row[0] != "objects/" + sha or row[1] != len(body):
                        raise ValueError("capture_integrity_failed")
                    self._verify(directory, sha, row[1])
                    return sha
                existing = next((size for key, size, _ in directory.files() if key == "objects/" + sha), None)
                if existing is not None:
                    self._verify(directory, sha, existing)
                    self._register(sha, existing, "")
                    self._recover(directory)
                    return sha
                self._admit(len(body))
                reservation = uuid.uuid4().hex
                with self._write() as conn:
                    conn.execute("INSERT INTO sec_research_reservations VALUES(?,?)", (reservation, len(body)))
                directory.stage(reservation, body)
                directory.publish(reservation, sha)
                self._register(sha, len(body), reservation)
                directory.remove_stage(reservation)
                self._recover(directory)
                return sha
