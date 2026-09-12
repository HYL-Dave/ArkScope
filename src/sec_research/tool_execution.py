"""SEC-only owned workers with cooperative cancellation and per-call budgets."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Event, Lock

from . import runtime
from .tool_results import active_budget, result_fits, serialize_sec_result, unavailable


class _Stop:
    def __init__(self):
        self.event, self.lock, self.readers = Event(), Lock(), []

    def __call__(self):
        if self.event.is_set():
            raise ValueError("cancelled")

    def track(self, reader):
        stop = getattr(reader, "request_stop", None) or getattr(reader, "close", None)
        if not callable(stop):
            return
        with self.lock:
            self.readers.append(stop)
            stopped = self.event.is_set()
        if stopped:
            self._stop_reader(stop)

    @staticmethod
    def _stop_reader(stop):
        try:
            stop()
        except Exception:
            pass

    def request_stop(self):
        self.event.set()
        with self.lock:
            readers = list(self.readers)
        for stop in readers:
            self._stop_reader(stop)


async def invoke_sec_tool(name, arguments, *, timeout_s=None) -> dict:
    """Return complete result evidence only after the owned worker has finished."""
    try:
        budget = active_budget()
    except Exception:
        return unavailable("sec_result_unavailable")
    stop = _Stop()
    context = copy_context()

    def worker():
        fits = lambda envelope: len(serialize_sec_result(envelope, name)) <= budget
        token = result_fits.set(fits)
        try:
            stop()
            result = runtime.build_tool_service().invoke(name, arguments, check=stop)
            return result if fits(result) else unavailable("sec_result_too_large")
        except Exception:
            return unavailable("sec_result_unavailable")
        finally:
            result_fits.reset(token)

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ark-sec")
    future = asyncio.get_running_loop().run_in_executor(pool, context.run, worker)
    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout=timeout_s)
    except (asyncio.CancelledError, asyncio.TimeoutError) as exc:
        stop.request_stop()
        # Shield the owned worker even from repeated cancellation of this task.
        while not future.done():
            try:
                await asyncio.shield(future)
            except asyncio.CancelledError:
                continue
        future.result()
        if isinstance(exc, asyncio.CancelledError):
            raise
        return unavailable("sec_result_timeout")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
