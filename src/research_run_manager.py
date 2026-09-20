"""Server-owned AI Research run executor.

The route creates durable run metadata and schedules this executor in the
sidecar process. The browser attaches to stored events; it no longer owns the
provider stream lifecycle.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack, aclosing
import logging
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from src.agents.shared.events import AgentEvent
from src.agents.shared.output_boundary import output_scope
from src.agents.shared.output_events import protect_events
from src.anthropic_refusal import safe_refusal_details
from src.auth_drivers.runtime_binding import (
    RuntimeAuthBinding, RuntimeAuthUnavailable, activate_runtime_auth,
)
from src.research_tool_trace import accumulate_tool_calls
from src.research_errors import (
    ResearchFailure, ResearchRunPersistenceError,
    classify_research_failure, classify_sec_research_admission_failure,
)
from src.research_runs import ResearchRunStore
from src.research_threads import MAX_TOOL_CALLS_SENTINEL, ResearchThreadStore
from src.sec_research.capture_lock import research_operation
from src.sec_research.paths import SecResearchPaths

logger = logging.getLogger(__name__)

StreamFactory = Callable[..., AsyncIterator[AgentEvent] | Awaitable[AsyncIterator[AgentEvent]]]

_TASKS: dict[str, asyncio.Task] = {}


def _remove_task_if_current(run_id: str, task: asyncio.Task) -> None:
    # The public failure is reported by the store observation, not an unhandled
    # task traceback (which can contain provider or storage details).
    if not task.cancelled():
        failure = task.exception()
        if failure is not None and not isinstance(failure, ResearchRunPersistenceError):
            logger.error("research run %s exited unexpectedly before finalization", run_id)
    if _TASKS.get(run_id) is task:
        _TASKS.pop(run_id, None)


def _persist(run_store: ResearchRunStore, owning_run_id: str, operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except Exception:
        run_store.note_persistence_failure(owning_run_id)
        logger.error("research run %s could not be saved (run_persistence_failed)", owning_run_id)
        raise ResearchRunPersistenceError() from None


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
    binding: RuntimeAuthBinding | None = None,
) -> dict:
    out = {
        key: data[key]
        for key in (
            "provider",
            "model",
            "token_usage",
            "tools_used",
        )
        if key in data
    }
    if "stop_details" in data:
        out["stop_details"] = safe_refusal_details(data["stop_details"], binding=binding)
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
    auth_binding: RuntimeAuthBinding | None = None,
    stream_factory: Optional[StreamFactory] = None,
) -> None:
    """Execute one run and persist both replay events and terminal transcript."""
    run = run_store.get_run(run_id)
    if run is None or run.status != "queued":
        return
    with ExitStack() as lease:
        try:
            lease.enter_context(research_operation(SecResearchPaths.resolve().capture_root))
        except ValueError as exc:
            failure = classify_sec_research_admission_failure(exc)
            if failure is None:
                raise
            # No provider/result exists yet; this transaction publishes no refs.
            _persist(run_store, run_id, run_store.fail_queued_run_handoff,
                run_id=run_id, thread_store=thread_store,
                message=failure.detail,
                error_code=failure.code,
            )
            return
        with output_scope(inherit=True):
            await _execute_research_run(
                run_id=run_id, run_store=run_store, thread_store=thread_store,
                dal=dal, history=history, auth_binding=auth_binding, stream_factory=stream_factory,
            )


async def _execute_research_run(
    *,
    run_id: str,
    run_store: ResearchRunStore,
    thread_store: ResearchThreadStore,
    dal: Any,
    history: list[dict],
    auth_binding: RuntimeAuthBinding | None = None,
    stream_factory: Optional[StreamFactory] = None,
) -> None:
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
    claimed = _persist(
        run_store, run_id, run_store.mark_running_with_personalization, run_id, personalization,
    )
    if not claimed:
        return
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
    error_data: Optional[dict] = None
    t0 = time.monotonic()

    if stream_factory is None:
        from src.api.routes.query import _research_provider_stream
        stream_factory = _research_provider_stream

    try:
        if auth_binding is None:
            raise RuntimeAuthUnavailable("runtime_auth_binding_missing")
        if (auth_binding.provider, auth_binding.auth_mode, auth_binding.credential_id) != (
            run.provider, run.auth_mode or "api_key", run.credential_id,
        ):
            raise RuntimeAuthUnavailable("runtime_auth_binding_mismatch")
        with activate_runtime_auth(auth_binding):
            stream = await _maybe_await(stream_factory(
                provider=run.provider,
                question=run.question,
                model=run.model,
                effort=run.effort,
                dal=dal,
                history=history,
                **_pctx,
            ))
            async with aclosing(protect_events(stream)) as stream:
                async for event in stream:
                    etype = _etype(event)
                    data = dict(event.data or {})
                    if etype in ("tool_start", "tool_end"):
                        if _persist(run_store, run_id, run_store.append_running_event, run_id, etype, data) is None:
                            return
                        collected.append((etype, data))
                        continue
                    if etype == "done" and data.get("answer") == MAX_TOOL_CALLS_SENTINEL:
                        failure = classify_research_failure(data.get("answer"))
                        terminal_token_usage = data.get("token_usage")
                        error_data = _typed_error_event_data(
                            data, failure, personalization=personalization, binding=auth_binding,
                        )
                        break
                    if etype == "done":
                        # Replay and transcript carry the same prompt trace.
                        data = {**data, "personalization": dict(personalization)}
                        done_data = data
                        break
                    if etype == "error":
                        raw_detail = data.get("error") or data.get("message") or "research run failed"
                        failure = classify_research_failure(
                            raw_detail,
                            explicit_code=data.get("code"),
                            binding=auth_binding,
                        )
                        terminal_token_usage = data.get("token_usage")
                        error_data = _typed_error_event_data(
                            data, failure, personalization=personalization, binding=auth_binding,
                        )
                        break
                    if _persist(run_store, run_id, run_store.append_running_event, run_id, etype, data) is None:
                        return
    except asyncio.CancelledError:
        cancelled = classify_research_failure(
            "research run cancelled",
            explicit_code="run_cancelled",
        )
        try:
            _persist(run_store, run_id, run_store.terminalize_error_with_message,
                thread_store=thread_store,
                run_id=run_id,
                status="cancelled",
                error=cancelled.detail,
                error_code=cancelled.code,
                tool_calls=accumulate_tool_calls(collected),
                elapsed_seconds=round(time.monotonic() - t0, 3),
                personalization=personalization,
            )
        except ResearchRunPersistenceError:
            pass  # The write observation remains visible; cancellation still propagates.
        raise
    except ResearchRunPersistenceError:
        raise
    except Exception as exc:  # noqa: BLE001 — terminal error, not route crash
        failure = classify_research_failure(exc, binding=auth_binding)
        logger.error(
            "research run %s failed (%s): %s",
            run_id,
            failure.code,
            failure.detail,
        )
        done_data = None
        error_data = {
            "error": failure.detail,
            "code": failure.code,
            "personalization": dict(personalization),
        }

    elapsed = round(time.monotonic() - t0, 3)
    if done_data is not None:
        _persist(run_store, run_id, run_store.terminalize_success_with_message,
            thread_store=thread_store, run_id=run_id, done_data=done_data,
            tool_calls=accumulate_tool_calls(collected), elapsed_seconds=elapsed,
        )
    else:
        failure = failure or classify_research_failure("research run failed")
        _persist(run_store, run_id, run_store.terminalize_error_with_message,
            thread_store=thread_store, run_id=run_id, status="failed",
            error=failure.detail, error_code=failure.code, event_data=error_data,
            tool_calls=accumulate_tool_calls(collected), elapsed_seconds=elapsed,
            personalization=personalization, token_usage=terminal_token_usage,
        )


def schedule_research_run(
    *,
    run_id: str,
    run_store: ResearchRunStore,
    thread_store: ResearchThreadStore,
    dal: Any,
    history: list[dict],
    auth_binding: RuntimeAuthBinding | None = None,
) -> asyncio.Task:
    current = _TASKS.get(run_id)
    if current is not None and not current.done():
        return current

    task = asyncio.create_task(execute_research_run(
        run_id=run_id, run_store=run_store, thread_store=thread_store,
        dal=dal, history=history, auth_binding=auth_binding,
    ))
    _TASKS[run_id] = task
    task.add_done_callback(lambda completed: _remove_task_if_current(run_id, completed))
    return task


def cancel_research_run(run_id: str) -> bool:
    task = _TASKS.get(run_id)
    if task is None or task.done():
        if task is not None:
            _remove_task_if_current(run_id, task)
        return False
    if task.cancel():
        return True
    _remove_task_if_current(run_id, task)
    return False
