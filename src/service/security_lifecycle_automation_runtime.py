"""Fail-closed cross-process ownership for lifecycle automation."""

from __future__ import annotations

import errno
import os
import secrets
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal

from src.ibkr_gateway_lock import lock_dir


_LOCK_FILE_NAME = "security_lifecycle_automation.lock"
_MAX_OWNER_ID_BYTES = 64

LifecycleAutomationStage = Literal[
    "preparing",
    "sec",
    "listing",
    "ibkr",
    "evaluate",
    "persist",
    "approve",
    "finalize",
]
LIFECYCLE_AUTOMATION_STAGE_ORDER: tuple[LifecycleAutomationStage, ...] = (
    "preparing",
    "sec",
    "listing",
    "ibkr",
    "evaluate",
    "persist",
    "approve",
    "finalize",
)
_STAGE_INDEX = {
    stage: index for index, stage in enumerate(LIFECYCLE_AUTOMATION_STAGE_ORDER)
}
_CONDITIONAL_STAGES = frozenset({"ibkr", "approve"})


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


@dataclass(frozen=True, slots=True)
class LifecycleAutomationProgressSnapshot:
    """One process-local, currently executing lifecycle case."""

    trigger: str
    request_id: str
    case_id: str
    started_at: datetime
    current_stage: LifecycleAutomationStage | None
    completed_stages: tuple[LifecycleAutomationStage, ...]
    skipped_stages: tuple[LifecycleAutomationStage, ...]


class LifecycleAutomationProgressRegistry:
    """Thread-safe process-local progress; never a durable execution lease."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[
            tuple[str, str], LifecycleAutomationProgressSnapshot
        ] = {}

    @staticmethod
    def _identity(request_id: str, case_id: str) -> tuple[str, str]:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("automation_progress_request_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("automation_progress_case_id")
        return request_id, case_id

    def begin(
        self,
        *,
        trigger: str,
        request_id: str,
        case_id: str,
        started_at: datetime,
    ) -> LifecycleAutomationProgressSnapshot:
        if not isinstance(trigger, str) or not trigger.strip():
            raise ValueError("automation_progress_trigger")
        if not isinstance(started_at, datetime):
            raise ValueError("automation_progress_started_at")
        identity = self._identity(request_id, case_id)
        snapshot = LifecycleAutomationProgressSnapshot(
            trigger=trigger,
            request_id=request_id,
            case_id=case_id,
            started_at=started_at,
            current_stage="preparing",
            completed_stages=(),
            skipped_stages=(),
        )
        with self._lock:
            if identity in self._entries:
                raise ValueError("automation_progress_exists")
            self._entries[identity] = snapshot
        return snapshot

    def advance(
        self,
        *,
        request_id: str,
        case_id: str,
        stage: LifecycleAutomationStage,
        skipped_stages: tuple[LifecycleAutomationStage, ...] = (),
    ) -> LifecycleAutomationProgressSnapshot:
        identity = self._identity(request_id, case_id)
        requested_skips = tuple(skipped_stages)
        with self._lock:
            current = self._entries.get(identity)
            if current is None or current.current_stage is None:
                raise ValueError("automation_progress_missing")
            target_index = _STAGE_INDEX.get(stage)
            current_index = _STAGE_INDEX[current.current_stage]
            if target_index is None or target_index <= current_index:
                raise ValueError("automation_progress_stage_order")

            expected_skips = LIFECYCLE_AUTOMATION_STAGE_ORDER[
                current_index + 1 : target_index
            ]
            if requested_skips != expected_skips:
                if requested_skips:
                    raise ValueError("automation_progress_stage_skip")
                raise ValueError("automation_progress_stage_order")
            if any(
                stage_name not in _CONDITIONAL_STAGES
                for stage_name in expected_skips
            ):
                raise ValueError("automation_progress_stage_skip")

            advanced = replace(
                current,
                current_stage=stage,
                completed_stages=current.completed_stages + (current.current_stage,),
                skipped_stages=current.skipped_stages + expected_skips,
            )
            self._entries[identity] = advanced
            return advanced

    def finish(
        self,
        *,
        request_id: str,
        case_id: str,
    ) -> LifecycleAutomationProgressSnapshot:
        identity = self._identity(request_id, case_id)
        with self._lock:
            current = self._entries.get(identity)
            if current is None:
                raise ValueError("automation_progress_missing")
            if current.current_stage != "finalize":
                raise ValueError("automation_progress_not_finalizing")
            finished = replace(
                current,
                current_stage=None,
                completed_stages=current.completed_stages + ("finalize",),
            )
            del self._entries[identity]
            return finished

    def clear(
        self,
        *,
        request_id: str,
        case_id: str,
    ) -> LifecycleAutomationProgressSnapshot | None:
        identity = self._identity(request_id, case_id)
        with self._lock:
            return self._entries.pop(identity, None)

    def snapshot(
        self,
        *,
        request_id: str | None = None,
        case_id: str | None = None,
    ) -> tuple[LifecycleAutomationProgressSnapshot, ...]:
        if request_id is not None and (
            not isinstance(request_id, str) or not request_id.strip()
        ):
            raise ValueError("automation_progress_request_id")
        if case_id is not None and (
            not isinstance(case_id, str) or not case_id.strip()
        ):
            raise ValueError("automation_progress_case_id")
        with self._lock:
            rows = tuple(
                row
                for row in self._entries.values()
                if (request_id is None or row.request_id == request_id)
                and (case_id is None or row.case_id == case_id)
            )
        return tuple(sorted(rows, key=lambda row: (row.request_id, row.case_id)))


_PROGRESS_REGISTRY = LifecycleAutomationProgressRegistry()


def lifecycle_automation_progress_registry() -> LifecycleAutomationProgressRegistry:
    """Return the process-local registry without reconstructing durable state."""

    return _PROGRESS_REGISTRY


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
    "LIFECYCLE_AUTOMATION_STAGE_ORDER",
    "LifecycleAutomationAlreadyRunning",
    "LifecycleAutomationExecutionLease",
    "LifecycleAutomationExecutionUnavailable",
    "LifecycleAutomationProgressRegistry",
    "LifecycleAutomationProgressSnapshot",
    "LifecycleAutomationStage",
    "lifecycle_automation_execution_lock",
    "lifecycle_automation_progress_registry",
]
