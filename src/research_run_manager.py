"""Server-owned AI Research run executor.

The route creates durable run metadata and schedules this executor in the
sidecar process. The browser attaches to stored events; it no longer owns the
provider stream lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from src.agents.shared.events import AgentEvent
from src.api.routes.query import accumulate_tool_calls, _persist_assistant_turn, _persist_error_turn
from src.research_runs import ResearchRunStore
from src.research_threads import ResearchThreadStore

logger = logging.getLogger(__name__)

StreamFactory = Callable[..., AsyncIterator[AgentEvent] | Awaitable[AsyncIterator[AgentEvent]]]

_TASKS: dict[str, asyncio.Task] = {}


def _etype(event: AgentEvent) -> str:
    return getattr(event.type, "value", event.type)


async def _maybe_await(value):
    if hasattr(value, "__await__"):
        return await value
    return value


async def execute_research_run(
    *,
    run_id: str,
    run_store: ResearchRunStore,
    thread_store: ResearchThreadStore,
    dal: Any,
    history: list[dict],
    stream_factory: Optional[StreamFactory] = None,
) -> None:
    """Execute one run and persist both replay events and terminal transcript."""
    run = run_store.get_run(run_id)
    if run is None:
        return
    run_store.mark_running(run_id)
    run = run_store.get_run(run_id)
    assert run is not None
    collected: list[tuple[str, dict]] = []
    done_data: Optional[dict] = None
    error_content: Optional[str] = None
    t0 = time.monotonic()

    if stream_factory is None:
        from src.api.routes.query import _research_provider_stream
        stream_factory = _research_provider_stream

    try:
        stream = await _maybe_await(stream_factory(
            provider=run.provider,
            question=run.question,
            model=run.model,
            effort=run.effort,
            dal=dal,
            history=history,
        ))
        async for event in stream:
            etype = _etype(event)
            data = event.data or {}
            run_store.append_event(run_id, etype, data)
            if etype in ("tool_start", "tool_end"):
                collected.append((etype, data))
            elif etype == "done":
                done_data = data
                break
            elif etype == "error":
                error_content = data.get("error") or data.get("message") or "research run failed"
                break
    except asyncio.CancelledError:
        run_store.append_event(run_id, "error", {"error": "research run cancelled"})
        run_store.mark_terminal(run_id, "cancelled", error="research run cancelled")
        _persist_error_turn(
            thread_store, thread_id=run.thread_id, content="research run cancelled",
            collected=collected, provider=run.provider, model=run.model,
            elapsed=round(time.monotonic() - t0, 3),
        )
        raise
    except Exception as exc:  # noqa: BLE001 — terminal error, not route crash
        logger.exception("research run %s failed", run_id)
        error_content = str(exc)
        run_store.append_event(run_id, "error", {"error": error_content})

    elapsed = round(time.monotonic() - t0, 3)
    if done_data is not None:
        _persist_assistant_turn(
            thread_store, thread_id=run.thread_id, done_data=done_data,
            collected=collected, elapsed=elapsed,
        )
        run_store.mark_terminal(
            run_id, "succeeded",
            token_usage=done_data.get("token_usage") if isinstance(done_data, dict) else None,
        )
    else:
        content = error_content or "research run failed"
        _persist_error_turn(
            thread_store, thread_id=run.thread_id, content=content, collected=collected,
            provider=run.provider, model=run.model, elapsed=elapsed,
        )
        run_store.mark_terminal(run_id, "failed", error=content)


def schedule_research_run(
    *,
    run_id: str,
    run_store: ResearchRunStore,
    thread_store: ResearchThreadStore,
    dal: Any,
    history: list[dict],
) -> asyncio.Task:
    task = asyncio.create_task(execute_research_run(
        run_id=run_id, run_store=run_store, thread_store=thread_store,
        dal=dal, history=history,
    ))
    _TASKS[run_id] = task
    task.add_done_callback(lambda _t: _TASKS.pop(run_id, None))
    return task


def cancel_research_run(run_id: str) -> bool:
    task = _TASKS.get(run_id)
    if task is None:
        return False
    task.cancel()
    return True
