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
from src.research_errors import ResearchFailure, classify_research_failure
from src.research_runs import ResearchRunStore
from src.research_threads import MAX_TOOL_CALLS_SENTINEL, ResearchThreadStore

logger = logging.getLogger(__name__)

StreamFactory = Callable[..., AsyncIterator[AgentEvent] | Awaitable[AsyncIterator[AgentEvent]]]

_TASKS: dict[str, asyncio.Task] = {}


def _etype(event: AgentEvent) -> str:
    return getattr(event.type, "value", event.type)


async def _maybe_await(value):
    if hasattr(value, "__await__"):
        return await value
    return value


def _typed_error_event_data(
    data: dict,
    failure: ResearchFailure,
    *,
    personalization: Optional[dict] = None,
) -> dict:
    out = {
        key: data[key]
        for key in (
            "provider",
            "model",
            "token_usage",
            "tools_used",
            "stop_details",
        )
        if key in data
    }
    out["error"] = failure.detail
    out["code"] = failure.code
    if personalization is not None:
        out["personalization"] = dict(personalization)
    return out


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
    if run is None or run.status != "queued":
        return

    # Track A: resolve the profile/stance AT EXECUTION (stance was validated at
    # create). Resolution failure degrades to off — the trace must never claim
    # a stance the prompt did not actually receive.
    try:
        from src.api.personalization import resolve_personalization

        personalization_context, personalization = resolve_personalization(run.assistant_stance)
    except Exception:  # noqa: BLE001 — degrade to un-personalized, honestly
        personalization_context, personalization = "", {
            "profile_active": False, "assistant_stance": "off", "skill_mode": "off",
            "suggested_skills": [], "applied_skills": [], "context_snapshot": "",
        }
    run_store.mark_running_with_personalization(run_id, personalization)
    run = run_store.get_run(run_id)
    if run is None or run.status != "running" or run.personalization is None:
        return
    personalization = run.personalization
    snapshot = personalization.get("context_snapshot")
    personalization_context = snapshot if isinstance(snapshot, str) else ""
    _pctx = {"personalization_context": personalization_context} if personalization_context else {}
    collected: list[tuple[str, dict]] = []
    done_data: Optional[dict] = None
    failure: Optional[ResearchFailure] = None
    terminal_token_usage: Optional[dict] = None
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
            **_pctx,
        ))
        async for event in stream:
            etype = _etype(event)
            data = dict(event.data or {})
            if etype in ("tool_start", "tool_end"):
                run_store.append_event(run_id, etype, data)
                collected.append((etype, data))
                continue
            if etype == "done" and data.get("answer") == MAX_TOOL_CALLS_SENTINEL:
                failure = classify_research_failure(data.get("answer"))
                terminal_token_usage = data.get("token_usage")
                run_store.append_event(
                    run_id,
                    "error",
                    _typed_error_event_data(
                        data,
                        failure,
                        personalization=personalization,
                    ),
                )
                break
            if etype == "done":
                # Enrich BEFORE persisting: the replay event and the transcript
                # must carry the same trace the prompt actually received.
                data = {**data, "personalization": dict(personalization)}
                run_store.append_event(run_id, etype, data)
                done_data = data
                break
            if etype == "error":
                raw_detail = data.get("error") or data.get("message") or "research run failed"
                failure = classify_research_failure(
                    raw_detail,
                    explicit_code=data.get("code"),
                )
                terminal_token_usage = data.get("token_usage")
                run_store.append_event(
                    run_id,
                    "error",
                    _typed_error_event_data(
                        data,
                        failure,
                        personalization=personalization,
                    ),
                )
                break
            run_store.append_event(run_id, etype, data)
    except asyncio.CancelledError:
        cancelled = classify_research_failure(
            "research run cancelled",
            explicit_code="run_cancelled",
        )
        try:
            run_store.terminalize_error_with_message(
                thread_store=thread_store,
                run_id=run_id,
                status="cancelled",
                error=cancelled.detail,
                error_code=cancelled.code,
                tool_calls=accumulate_tool_calls(collected),
                elapsed_seconds=round(time.monotonic() - t0, 3),
                personalization=personalization,
            )
        except Exception:
            logger.exception("failed to persist atomic cancellation for research run %s", run_id)
        raise
    except Exception as exc:  # noqa: BLE001 — terminal error, not route crash
        failure = classify_research_failure(exc)
        logger.error(
            "research run %s failed (%s): %s",
            run_id,
            failure.code,
            failure.detail,
        )
        run_store.append_event(
            run_id,
            "error",
            {
                "error": failure.detail,
                "code": failure.code,
                "personalization": dict(personalization),
            },
        )

    elapsed = round(time.monotonic() - t0, 3)
    if done_data is not None:
        _persist_assistant_turn(
            thread_store, thread_id=run.thread_id, done_data=done_data,
            collected=collected, elapsed=elapsed, effort=run.effort,
            personalization=personalization,
            run_id=run_id,
        )
        run_store.mark_terminal(
            run_id, "succeeded",
            token_usage=done_data.get("token_usage") if isinstance(done_data, dict) else None,
        )
    else:
        failure = failure or classify_research_failure("research run failed")
        _persist_error_turn(
            thread_store, thread_id=run.thread_id, content=failure.detail, collected=collected,
            provider=run.provider, model=run.model, effort=run.effort, elapsed=elapsed,
            personalization=personalization,
            run_id=run_id,
            error_code=failure.code,
            token_usage=terminal_token_usage,
        )
        run_store.mark_terminal(
            run_id,
            "failed",
            error=failure.detail,
            error_code=failure.code,
            token_usage=terminal_token_usage,
        )


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
