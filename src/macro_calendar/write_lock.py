"""Fail-closed process and file lock for every macro-calendar writer."""

from __future__ import annotations

import math
import os
import stat
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.ibkr_gateway_lock import lock_dir


_THREAD_LOCK = threading.Lock()
_LEASE_AUTHORITY = object()
_LOCK_FILE_NAME = "macro_calendar_writer.lock"


class MacroCalendarBusy(RuntimeError):
    """Raised when exclusive macro-calendar writer ownership is unavailable."""

    code = "macro_calendar_busy"

    def __init__(self, reason: str | None = None) -> None:
        super().__init__(self.code)
        self.reason = reason


class MacroCalendarWriterLease:
    """Single-use proof that this thread owns both writer-lock layers."""

    __slots__ = (
        "_active",
        "_authority",
        "_claimed",
        "_owner_pid",
        "_owner_thread",
    )

    def __init__(self, authority: object) -> None:
        if authority is not _LEASE_AUTHORITY:
            raise MacroCalendarBusy("foreign writer lease")
        self._authority = authority
        self._owner_pid = os.getpid()
        self._owner_thread = threading.get_ident()
        self._active = True
        self._claimed = False


def _claim_writer_lease(lease: MacroCalendarWriterLease) -> None:
    if type(lease) is not MacroCalendarWriterLease:  # noqa: E721 - exact authority
        raise MacroCalendarBusy("foreign writer lease")
    if lease._authority is not _LEASE_AUTHORITY:
        raise MacroCalendarBusy("foreign writer lease")
    if not lease._active:
        raise MacroCalendarBusy("released writer lease")
    if lease._owner_pid != os.getpid() or lease._owner_thread != threading.get_ident():
        raise MacroCalendarBusy("writer lease belongs to another process or thread")
    if lease._claimed:
        raise MacroCalendarBusy("writer lease already used")
    lease._claimed = True


def _timeout_seconds(value: float) -> float:
    if isinstance(value, bool):
        raise MacroCalendarBusy("invalid writer-lock timeout")
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise MacroCalendarBusy("invalid writer-lock timeout") from exc
    if not math.isfinite(timeout) or timeout < 0:
        raise MacroCalendarBusy("invalid writer-lock timeout")
    return timeout


def _acquire_thread_lock(timeout: float) -> bool:
    try:
        if timeout == 0:
            return _THREAD_LOCK.acquire(blocking=False)
        return _THREAD_LOCK.acquire(timeout=timeout)
    except (OverflowError, ValueError) as exc:
        raise MacroCalendarBusy("invalid writer-lock timeout") from exc


def _open_lock_file(path: Path) -> int:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise MacroCalendarBusy("writer-lock directory cannot be created") from exc
    if parent.is_symlink():
        raise MacroCalendarBusy("writer-lock directory is a symlink")
    try:
        existing = path.lstat()
    except FileNotFoundError:
        existing = None
    except OSError as exc:
        raise MacroCalendarBusy("writer lock cannot be inspected") from exc
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise MacroCalendarBusy("writer lock is not a regular file")

    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise MacroCalendarBusy("writer lock cannot be opened") from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise MacroCalendarBusy("writer lock is not a regular file")
        os.fchmod(fd, 0o600)
        return fd
    except MacroCalendarBusy:
        os.close(fd)
        raise
    except OSError as exc:
        os.close(fd)
        raise MacroCalendarBusy("writer lock cannot be validated") from exc


def _acquire_file_lock(fd: int, timeout: float) -> None:
    try:
        import fcntl
    except ImportError as exc:
        raise MacroCalendarBusy("fcntl is unavailable") from exc

    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except (BlockingIOError, InterruptedError):
            if timeout == 0 or time.monotonic() >= deadline:
                raise MacroCalendarBusy("writer file lock is busy")
            time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))
        except OSError as exc:
            raise MacroCalendarBusy("writer file lock failed") from exc


@contextmanager
def macro_calendar_writer(
    timeout_seconds: float = 0.0,
) -> Iterator[MacroCalendarWriterLease]:
    """Hold both writer-lock layers and yield one same-thread, single-use lease."""

    timeout = _timeout_seconds(timeout_seconds)
    deadline = time.monotonic() + timeout
    if not _acquire_thread_lock(timeout):
        raise MacroCalendarBusy("writer thread lock is busy")

    fd: int | None = None
    file_held = False
    lease: MacroCalendarWriterLease | None = None
    try:
        path = lock_dir() / _LOCK_FILE_NAME
        fd = _open_lock_file(path)
        remaining = 0.0 if timeout == 0 else max(0.0, deadline - time.monotonic())
        _acquire_file_lock(fd, remaining)
        file_held = True
        lease = MacroCalendarWriterLease(_LEASE_AUTHORITY)
        yield lease
    except MacroCalendarBusy:
        raise
    except BaseException:
        raise
    finally:
        if lease is not None:
            lease._active = False
        try:
            if fd is not None:
                if file_held:
                    try:
                        import fcntl

                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                os.close(fd)
        finally:
            _THREAD_LOCK.release()
