"""Fail-closed cross-process ownership for lifecycle automation."""

from __future__ import annotations

import errno
import os
import secrets
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from src.ibkr_gateway_lock import lock_dir


_LOCK_FILE_NAME = "security_lifecycle_automation.lock"
_MAX_OWNER_ID_BYTES = 64


class LifecycleAutomationAlreadyRunning(RuntimeError):
    """Exclusive lifecycle execution ownership is held elsewhere."""

    code = "already_running"

    def __init__(self) -> None:
        super().__init__(self.code)


class LifecycleAutomationExecutionUnavailable(RuntimeError):
    """Cross-process lifecycle execution ownership cannot be proven."""

    code = "execution_lock_unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class LifecycleAutomationExecutionLease:
    execution_owner_id: str


def _new_execution_owner_id() -> str:
    owner_id = "slao_" + secrets.token_hex(16)
    if len(owner_id.encode("utf-8")) > _MAX_OWNER_ID_BYTES:
        raise LifecycleAutomationExecutionUnavailable()
    return owner_id


def _open_lock_file(path: Path) -> int:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if parent.is_symlink():
            raise LifecycleAutomationExecutionUnavailable()
        existing = path.lstat() if path.exists() else None
        if existing is not None and not stat.S_ISREG(existing.st_mode):
            raise LifecycleAutomationExecutionUnavailable()
        flags = os.O_RDWR | os.O_CREAT
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
    except LifecycleAutomationExecutionUnavailable:
        raise
    except OSError as exc:
        raise LifecycleAutomationExecutionUnavailable() from exc

    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise LifecycleAutomationExecutionUnavailable()
        os.fchmod(fd, 0o600)
        return fd
    except LifecycleAutomationExecutionUnavailable:
        os.close(fd)
        raise
    except OSError as exc:
        os.close(fd)
        raise LifecycleAutomationExecutionUnavailable() from exc


def _acquire_file_lock(fd: int):
    try:
        import fcntl
    except ImportError as exc:
        raise LifecycleAutomationExecutionUnavailable() from exc

    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fcntl
        except InterruptedError:
            continue
        except BlockingIOError as exc:
            raise LifecycleAutomationAlreadyRunning() from exc
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise LifecycleAutomationAlreadyRunning() from exc
            raise LifecycleAutomationExecutionUnavailable() from exc


@contextmanager
def lifecycle_automation_execution_lock(
) -> Iterator[LifecycleAutomationExecutionLease]:
    """Yield an owner ID only while a dedicated non-blocking flock is held."""

    fd = _open_lock_file(lock_dir() / _LOCK_FILE_NAME)
    fcntl = None
    held = False
    try:
        fcntl = _acquire_file_lock(fd)
        held = True
        yield LifecycleAutomationExecutionLease(_new_execution_owner_id())
    finally:
        if held and fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
        os.close(fd)


__all__ = [
    "LifecycleAutomationAlreadyRunning",
    "LifecycleAutomationExecutionLease",
    "LifecycleAutomationExecutionUnavailable",
    "lifecycle_automation_execution_lock",
]
