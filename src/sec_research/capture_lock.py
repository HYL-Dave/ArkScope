"""Descriptor-bound capture I/O and an exclusive, crash-released writer lease."""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import asyncio
import errno
import hashlib
import os
from pathlib import Path
import re
import stat
import threading

from src.ibkr_gateway_lock import lock_dir


_operations = threading.local()


def _owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return os.getpid(), threading.get_ident(), task


def _check_root(root):
    # Missing stored roots (and parents) are valid, but existing symlinks are not.
    fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in root.parts[1:]:
            try:
                child = _directory(fd, part)
            except FileNotFoundError:
                return
            os.close(fd)
            fd = child
    finally:
        os.close(fd)


@contextmanager
def research_operation(root: Path, *, exclusive=False, create=False):
    """Crash-released maintenance exclusion, reentrant only in this thread/task.

    Order: operation -> issuer/document -> capture writer -> market -> SQLite.
    Active ownership is thread-local and keyed by process and async task, never
    inherited through Context copies. Shared-to-exclusive upgrades fail.
    """
    if not _supported():
        raise ValueError("capture_platform_unsupported")
    if type(exclusive) is not bool or type(create) is not bool:
        raise ValueError("sec_research_operation_invalid")
    root = Path(root).absolute()
    if ".." in root.parts:
        raise ValueError("capture_path_unsafe")
    owner = (root, _owner())
    if not hasattr(_operations, "held"):
        _operations.held = {}
    held = _operations.held
    inherited = held.get(owner)
    if inherited is not None and exclusive and not inherited:
        raise ValueError("sec_research_operation_busy")
    fd = parent = None
    registered = False
    acquired = False
    try:
        _check_root(root)
        if inherited is None:
            import fcntl
            path = lock_dir().absolute()
            parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
            for part in path.parts[1:]:
                try:
                    child = _directory(parent, part)
                except FileNotFoundError:
                    child = _directory(parent, part, create=True)
                os.close(parent)
                parent = child
            key = "sec-research-" + hashlib.sha256(str(root).encode()).hexdigest() + ".operation.lock"
            fd = os.open(key, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o600, dir_fd=parent)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("capture_path_unsafe")
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            held[owner] = exclusive
            registered = True
        if create:
            directory = CaptureDirectory(root, create=True)
            directory.close()
        acquired = True
    except BlockingIOError:
        if fd is not None:
            os.close(fd)
            fd = None
        raise ValueError("sec_research_operation_busy") from None
    except OSError as exc:
        raise _io_failure(exc) from None
    finally:
        if parent is not None:
            os.close(parent)
        if not acquired:
            if registered:
                del held[owner]
            if fd is not None:
                os.close(fd)
    try:
        yield
    finally:
        if registered:
            del held[owner]
        if fd is not None:
            os.close(fd)


def store_operation(function):
    """Protect a whole synchronous store/service/query operation, not each read."""
    @wraps(function)
    def protected(owner, *args, **kwargs):
        store = owner if hasattr(owner, "paths") else owner.store
        with research_operation(store.paths.capture_root):
            return function(owner, *args, **kwargs)
    return protected


def _io_failure(exc):
    if exc.errno == errno.ENOSPC:
        return ValueError("storage_space_insufficient")
    if exc.errno in (errno.ELOOP, errno.ENOTDIR, errno.ENOENT):
        return ValueError("capture_path_unsafe")
    return ValueError("capture_store_write_failed")


def _supported():
    return os.name == "posix" and hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd


def _directory(parent_fd, name, *, create=False):
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        # Also sync on retry: the preceding process may have died after mkdir.
        os.fsync(parent_fd)
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)


class CaptureDirectory:
    """All capture file operations are relative to already-validated directories."""

    def __init__(self, root: Path, *, create=False):
        if not _supported():
            raise ValueError("capture_platform_unsupported")
        self.root = Path(root).absolute()
        self.root_fd = None
        self.children = {}
        fd = os.open(self.root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for index, part in enumerate(self.root.parts[1:]):
                next_fd = _directory(fd, part, create=create and index == len(self.root.parts) - 2)
                os.close(fd)
                fd = next_fd
            self.root_fd = fd
            fd = None
            for name in ("objects", "staging"):
                self.children[name] = _directory(self.root_fd, name, create=create)
        except OSError as exc:
            self.close()
            raise _io_failure(exc) from None
        finally:
            if fd is not None:
                os.close(fd)

    def close(self):
        for fd in self.children.values():
            os.close(fd)
        self.children.clear()
        if self.root_fd is not None:
            os.close(self.root_fd)
            self.root_fd = None

    def assert_current(self):
        try:
            current = self.root.lstat()
            opened = os.fstat(self.root_fd)
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise ValueError("capture_path_unsafe")
            for name, fd in self.children.items():
                current = os.stat(name, dir_fd=self.root_fd, follow_symlinks=False)
                opened = os.fstat(fd)
                if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                    raise ValueError("capture_path_unsafe")
        except OSError:
            raise ValueError("capture_path_unsafe") from None

    def _key(self, key):
        parts = key.split("/")
        if len(parts) != 2 or parts[0] not in self.children or not parts[1] or any(c not in "0123456789abcdef" for c in parts[1]):
            raise ValueError("capture_path_unsafe")
        return self.children[parts[0]], parts[1]

    def read(self, key, size):
        parent, name = self._key(key)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                raise ValueError("capture_integrity_failed")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                body = handle.read(size + 1)
            if len(body) != size:
                raise ValueError("capture_integrity_failed")
            return body
        finally:
            os.close(fd)

    def stage(self, name, body):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.children["staging"])
        try:
            with os.fdopen(fd, "wb", closefd=False) as handle:
                handle.write(body)
                handle.flush()
                os.fsync(fd)
            os.fsync(self.children["staging"])
        finally:
            os.close(fd)

    def publish(self, stage, sha):
        self.assert_current()
        os.link(stage, sha, src_dir_fd=self.children["staging"],
                dst_dir_fd=self.children["objects"], follow_symlinks=False)
        os.fsync(self.children["objects"])

    def remove_stage(self, stage):
        os.unlink(stage, dir_fd=self.children["staging"])
        os.fsync(self.children["staging"])

    def files(self):
        self.assert_current()
        rows = []
        for category, fd in self.children.items():
            for name in sorted(os.listdir(fd)):
                key = category + "/" + name
                self._key(key)
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("capture_path_unsafe")
                rows.append((key, info.st_size, (info.st_dev, info.st_ino)))
        return rows

    def sync(self):
        """Resolve directory durability before retiring any absent-file charge."""
        self.assert_current()
        for fd in self.children.values():
            os.fsync(fd)
        os.fsync(self.root_fd)
        self.assert_current()

    @staticmethod
    def _identity(info):
        return [info.st_dev, info.st_ino, info.st_size, info.st_nlink,
                info.st_mtime_ns, info.st_ctime_ns]

    def recover_published_stages(self, files):
        """After accounting commits, remove only a proven publication alias."""
        by_inode = {}
        for key, size, inode in files:
            by_inode.setdefault(inode, []).append((key, size))
        for inode, entries in by_inode.items():
            if len(entries) == 1:
                continue
            if len(entries) != 2:
                raise ValueError("capture_path_unsafe")
            (object_key, size), (stage_key, stage_size) = sorted(entries)
            if (re.fullmatch(r"objects/[0-9a-f]{64}", object_key) is None
                    or re.fullmatch(r"staging/[0-9a-f]{32}", stage_key) is None
                    or size != stage_size):
                raise ValueError("capture_path_unsafe")
            self._remove_published_stage(object_key, stage_key, inode, size)

    def _remove_published_stage(self, object_key, stage_key, inode, size):
        self.assert_current()
        opened = []
        try:
            for key in (object_key, stage_key):
                parent, name = self._key(key)
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                opened.append((fd, parent, name))
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 2
                        or (info.st_dev, info.st_ino) != inode or info.st_size != size):
                    raise ValueError("capture_path_unsafe")
                if len(opened) == 1:
                    identity = self._identity(info)
                elif identity != self._identity(info):
                    raise ValueError("capture_path_unsafe")
            digest = hashlib.sha256()
            with os.fdopen(opened[0][0], "rb", closefd=False) as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
            self.assert_current()
            for fd, parent, name in opened:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if (not stat.S_ISREG(current.st_mode)
                        or identity != self._identity(os.fstat(fd))
                        or identity != self._identity(current)):
                    raise ValueError("capture_path_unsafe")
            if digest.hexdigest() != opened[0][2]:
                raise ValueError("capture_integrity_failed")
            _, parent, name = opened[1]
            os.unlink(name, dir_fd=parent)
            os.fsync(parent)
            self.assert_current()
        finally:
            for fd, _, _ in opened:
                os.close(fd)

    def inspect_owned(self, key):
        if re.fullmatch(r"(?:objects/[0-9a-f]{64}|staging/[0-9a-f]{32})", key) is None:
            raise ValueError("capture_path_unsafe")
        parent, name = self._key(key)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("capture_path_unsafe")
            digest = hashlib.sha256()
            with os.fdopen(fd, "rb", closefd=False) as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
            identity = self._identity(info)
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if identity != self._identity(os.fstat(fd)) or identity != self._identity(current):
                raise ValueError("capture_path_unsafe")
            return {"key": key, "size_bytes": info.st_size,
                    "sha256": digest.hexdigest(), "identity": identity}
        finally:
            os.close(fd)

    def inventory(self):
        """Strict admin inventory, not the writer's interrupted-hardlink recovery."""
        self.assert_current()
        if set(os.listdir(self.root_fd)) != {"objects", "staging"}:
            raise ValueError("capture_path_unsafe")
        result = [self.inspect_owned(key) for key, _, _ in self.files()]
        identities = [tuple(item["identity"][:2]) for item in result]
        if len(set(identities)) != len(identities):
            raise ValueError("capture_path_unsafe")
        self.assert_current()
        return sorted(result, key=lambda item: item["key"])

    def remove_owned(self, item):
        """Unlink only an approved descriptor-bound identity, then sync its parent."""
        self.assert_current()
        if self.inspect_owned(item["key"]) != item:
            raise ValueError("sec_research_preview_stale")
        parent, name = self._key(item["key"])
        os.unlink(name, dir_fd=parent)
        os.fsync(parent)
        self.assert_current()
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ValueError("capture_path_unsafe")

    def confirm_absent(self, key):
        self.sync()
        parent, name = self._key(key)
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ValueError("sec_research_preview_stale")


@contextmanager
def _lease(root: Path, name: str, busy_code: str):
    with research_operation(root):
        with _capture_lease(root, name, busy_code) as directory:
            yield directory


@contextmanager
def _capture_lease(root: Path, name: str, busy_code: str):
    directory = CaptureDirectory(root, create=True)
    fd = None
    lock_parent = None
    try:
        import fcntl
        try:
            # Coordination lives outside mutable capture content. As with the
            # market/governor locks, this configured namespace is trusted and
            # must not be replaced by cleanup or an operator while App runs.
            path = lock_dir().absolute()
            lock_parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
            for part in path.parts[1:]:
                next_fd = _directory(lock_parent, part, create=True)
                os.close(lock_parent)
                lock_parent = next_fd
            key = "sec-research-" + hashlib.sha256(str(directory.root).encode()).hexdigest() + name
            fd = os.open(key, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o600, dir_fd=lock_parent)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("capture_path_unsafe")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(busy_code) from None
        except OSError as exc:
            raise _io_failure(exc) from None
        directory.assert_current()
        yield directory
    finally:
        if fd is not None:
            os.close(fd)
        if lock_parent is not None:
            os.close(lock_parent)
        directory.close()


def capture_writer(root: Path):
    return _lease(root, ".writer.lock", "capture_store_busy")


def issuer_refresh(root: Path, cik: str):
    from src.sec_research.common import normalize_cik
    return _lease(root, ".refresh-" + normalize_cik(cik) + ".lock", "sec_research_refresh_busy")


def document_acquisition(root: Path):
    """One explicit acquisition per capture root, without holding the writer lease."""
    return _lease(root, ".document.lock", "document_acquisition_busy")
