"""Keep financial acquisition inside the lifetime of its async caller."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context
from threading import Event


_stop = ContextVar("financial_acquisition_stop", default=None)


class FinancialReadStopped(RuntimeError):
    pass


def check_financial_work():
    signal = _stop.get()
    if signal is not None and signal.is_set():
        raise FinancialReadStopped("financial_read_cancelled")


async def invoke_financial_tool(call):
    """Stop new pages on cancellation, then join the bounded in-flight request.

    A synchronous HTTP request cannot be recalled. Returning before its worker
    stops would let later paid pages outlive the tool's cancellation or timeout.
    """
    signal, context = Event(), copy_context()

    def worker():
        token = _stop.set(signal)
        try:
            check_financial_work()
            return call()
        finally:
            _stop.reset(token)

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ark-financial")
    future = asyncio.get_running_loop().run_in_executor(pool, context.run, worker)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        signal.set()
        while not future.done():
            try:
                await asyncio.shield(future)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        # Consume the stopped worker's exception without replacing cancellation.
        if not future.cancelled():
            future.exception()
        raise
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
