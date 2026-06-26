"""Shared IBKR Gateway lock — one TWS/Gateway session at a time, across the whole app.

Extracted from ``data_scheduler`` (PG-exit precursor) so EVERY IBKR consumer serializes on the
SAME mutex: the scheduler's ``run_source`` (ibkr sources), the standalone direct price backfill
(``market_data_direct.backfill_prices_direct``), and the future intraday-behavior operation. The
Gateway is single-session — two concurrent ``reqHistoricalData`` storms (e.g. a manual backfill
racing a scheduled IV pull) corrupt each other; this lock makes that impossible whether the
callers are in one process (threads) or two (sidecar + CLI).

Two layers, both required:
- ``IBKR_THREAD_LOCK`` (in-process ``threading.Lock``) — one IBKR op per sidecar process.
- ``IBKR_FILE_LOCK`` (``flock`` on ``data/locks/ibkr_gateway.lock``) — one IBKR op across
  processes (the sidecar vs the daily_update CLI), since a threading.Lock can't see across them.

``ibkr_gateway_lock()`` is the context manager for standalone callers; the scheduler uses the two
singletons directly to keep its distinct skip-reason telemetry. The two paths share the SAME
objects, so they're mutually exclusive. NOTE: these locks are NOT re-entrant — a caller already
holding the gateway lock (e.g. the scheduler running a direct-backfill adapter) must NOT acquire
it again; pass that through explicitly rather than nesting.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Default acquire timeout: one slow IBKR job must not wedge the others forever (matches the
# scheduler's historical _IBKR_LOCK_TIMEOUT_S).
DEFAULT_GATEWAY_TIMEOUT_S = 1800


def lock_dir() -> Path:
    """Lock-file directory (env-overridable so tests never collide with a live sidecar's
    locks). Identical resolution to the former data_scheduler._lock_dir + market_write_lock,
    so the SAME ``ibkr_gateway.lock`` / ``local_refresh.lock`` files are used everywhere."""
    return Path(os.environ.get("ARKSCOPE_LOCK_DIR") or (_REPO_ROOT / "data" / "locks"))


class FileLock:
    """flock(2) twin of a threading.Lock: serializes one PROCESS against another (a
    threading.Lock cannot see across processes). The kernel releases flock when the fd closes
    OR the process dies, so a crashed run never wedges the lock.

    Each instance is only ever acquired while its threading twin is held, so the instance
    itself needs no thread-safety. Non-POSIX (no fcntl) degrades to in-process-only locking
    with a one-time warning. (Moved verbatim from data_scheduler in the PG-exit lock extraction.)
    """

    _warned = False

    def __init__(self, name: str):
        self._name = name
        self._fh = None

    def acquire(self, timeout: float = 0.0, poll: float = 5.0) -> bool:
        """timeout 0 → single non-blocking try; >0 → poll until the deadline."""
        try:
            import fcntl
        except ImportError:  # non-POSIX
            if not FileLock._warned:
                logger.warning("fcntl unavailable — cross-process locks degraded "
                               "to in-process only")
                FileLock._warned = True
            return True
        path = lock_dir() / f"{self._name}.lock"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(path, "a+")
        except OSError as e:
            # A broken lock dir must not brick collection: degrade, don't skip.
            logger.warning(f"file lock {path.name} unavailable ({e}); "
                           "cross-process exclusion degraded for this run")
            return True
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fh = fh
                return True
            except OSError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    fh.close()
                    return False
                time.sleep(min(poll, max(0.1, remaining)))

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:  # noqa: BLE001 — close below still drops the lock
            pass
        try:
            self._fh.close()
        finally:
            self._fh = None


# The ONE Gateway mutex (in-process + cross-process), shared by every IBKR consumer.
IBKR_THREAD_LOCK = threading.Lock()        # one Gateway op at a time within this process
IBKR_FILE_LOCK = FileLock("ibkr_gateway")  # one Gateway session across processes


@contextmanager
def ibkr_gateway_lock(timeout: float = DEFAULT_GATEWAY_TIMEOUT_S):
    """Hold the shared IBKR Gateway lock (thread + cross-process) for the duration. Raises
    ``TimeoutError`` if either layer can't be acquired within ``timeout`` (caller decides
    whether that's fatal or a skip). NOT re-entrant — do not call while already holding it."""
    if not IBKR_THREAD_LOCK.acquire(timeout=timeout):
        raise TimeoutError("IBKR gateway busy (in-process lock timeout)")
    file_held = False
    try:
        if not IBKR_FILE_LOCK.acquire(timeout=timeout):
            raise TimeoutError("IBKR gateway busy in another process (file lock timeout)")
        file_held = True
        yield
    finally:
        if file_held:
            IBKR_FILE_LOCK.release()
        IBKR_THREAD_LOCK.release()
