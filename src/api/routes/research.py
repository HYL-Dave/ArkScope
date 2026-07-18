"""Local-first AI Research thread lifecycle and durable run routes."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.agents.config import resolve_research_route
from src.api.routes.query import _compose_agent_question, TITLE_MAX
from src.auth_drivers.live_resolver import resolve_live_auth
from src.research_errors import (
    classify_research_failure,
    public_research_error_code,
    sanitize_research_detail,
)
from src.research_run_manager import cancel_research_run, schedule_research_run
from src.research_runs import (
    ACTIVE_STATUSES,
    ResearchRun,
    ResearchRunEvent,
    ResearchRunUnavailableError,
)
from src.research_threads import (
    ResearchMessage,
    ResearchThread,
    ResearchThreadActiveError,
    valid_thread_id,
)

from ..dependencies import (
    get_dal,
    get_research_history_store,
    get_run_store,
    get_thread_store,
)

router = APIRouter(tags=["research"])
_RUN_EVENT_PAGE_SIZE = 500
_SCHEDULE_FAILURE_MESSAGE = "research run could not be scheduled"
logger = logging.getLogger(__name__)


class ResearchRunCreate(BaseModel):
    thread_id: str | None = None
    question: str
    ticker: str | None = None
    provider: str
    model: str | None = None
    effort: str | None = None
    retry_last_failed: bool = False
    # Track A: per-run Assistant Stance override (invalid → 400 at create).
    assistant_stance: str | None = None


class ResearchThreadPatch(BaseModel):
    title: str | None = None
    archived: bool | None = None


def _run_dict(run: ResearchRun | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "thread_id": run.thread_id,
        "status": run.status,
        "question": run.question,
        "ticker": run.ticker,
        "provider": run.provider,
        "model": run.model,
        "effort": run.effort,
        "assistant_stance": run.assistant_stance,
        "auth_mode": run.auth_mode,
        "credential_id": run.credential_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error": sanitize_research_detail(run.error) if run.error is not None else None,
        "error_code": public_research_error_code(run.error_code),
        "token_usage": run.token_usage,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _event_dict(event: ResearchRunEvent) -> dict:
    return {
        "run_id": event.run_id,
        "seq": event.seq,
        "type": event.type,
        "data": event.data,
        "created_at": event.created_at,
    }


_MISSING = object()


def _thread_dict(t: ResearchThread, *, active_run=_MISSING) -> dict:
    out = {
        "id": t.id, "title": t.title, "ticker": t.ticker,
        "provider": t.provider, "model": t.model,
        "created_at": t.created_at, "updated_at": t.updated_at,
        "archived_at": t.archived_at,
    }
    if hasattr(t, "latest_run_status"):
        out["latest_run_status"] = t.latest_run_status
    if active_run is not _MISSING:
        out["active_run"] = _run_dict(active_run)
    return out


def _message_dict(m: ResearchMessage) -> dict:
    content = sanitize_research_detail(m.content) if m.is_error else m.content
    return {
        "role": m.role, "content": content, "provider": m.provider, "model": m.model,
        "effort": m.effort,
        "run_id": m.run_id,
        "error_code": public_research_error_code(m.error_code),
        "error": content if m.is_error else None,
        "tools_used": m.tools_used, "tool_calls": m.tool_calls,
        "token_usage": m.token_usage, "tickers": m.tickers,
        "elapsed_seconds": m.elapsed_seconds, "is_error": m.is_error, "created_at": m.created_at,
        "personalization": m.personalization,
    }


@router.get("/research/threads")
def list_research_threads(
    q: str | None = None,
    ticker: str | None = None,
    updated_from: str | None = None,
    updated_before: str | None = None,
    run_state: str = "all",
    archived: str = "current",
    limit: int = 50,
    offset: int = 0,
    store=Depends(get_thread_store),
    history_store=Depends(get_research_history_store),
    run_store=Depends(get_run_store),
) -> dict:
    """Bounded history page with filters applied before count and pagination."""
    if not hasattr(history_store, "query_threads"):
        from src.research_history import ResearchHistoryStore

        history_store = ResearchHistoryStore(store.db_path)
    if not hasattr(run_store, "latest_active_for_threads"):
        from src.research_runs import ResearchRunStore

        run_store = ResearchRunStore(store.db_path)

    try:
        page = history_store.query_threads(
            q=q,
            ticker=ticker,
            updated_from=updated_from,
            updated_before=updated_before,
            run_state=run_state,
            archive_mode=archived,
            limit=limit,
            offset=offset,
            run_store=run_store,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    active_runs = {run.thread_id: run for run in page.active_runs}
    return {
        "threads": [
            _thread_dict(thread, active_run=active_runs.get(thread.id))
            for thread in page.threads
        ],
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
    }


def _resolve_run_store(run_store, thread_store):
    if hasattr(run_store, "latest_active_for_thread") and hasattr(
        run_store, "latest_active_for_threads"
    ):
        return run_store
    from src.research_runs import ResearchRunStore

    return ResearchRunStore(thread_store.db_path)


def _thread_with_active_run(thread: ResearchThread, run_store) -> dict:
    active_runs = run_store.latest_active_for_threads([thread.id])
    return _thread_dict(thread, active_run=active_runs.get(thread.id))


@router.get("/research/threads/{thread_id}")
def get_research_thread(
    thread_id: str,
    store=Depends(get_thread_store),
    run_store=Depends(get_run_store),
) -> dict:
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")
    thread = store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread not found")
    run_store = _resolve_run_store(run_store, store)
    return {"thread": _thread_with_active_run(thread, run_store)}


@router.patch("/research/threads/{thread_id}")
def patch_research_thread(
    thread_id: str,
    request: ResearchThreadPatch,
    store=Depends(get_thread_store),
    run_store=Depends(get_run_store),
) -> dict:
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")
    if request.title is None and request.archived is None:
        raise HTTPException(status_code=422, detail="at least one field is required")

    title = None
    if request.title is not None:
        title = request.title.strip()
        if not title or len(title) > TITLE_MAX:
            raise HTTPException(
                status_code=422,
                detail=f"title must contain 1 to {TITLE_MAX} characters",
            )

    run_store = _resolve_run_store(run_store, store)
    try:
        updated = store.update_thread_lifecycle(
            thread_id,
            title=title,
            archived=request.archived,
        )
    except ResearchThreadActiveError as exc:
        raise HTTPException(
            status_code=409,
            detail="active research run prevents archiving this thread",
        ) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return {"thread": _thread_with_active_run(updated, run_store)}


@router.get("/research/threads/{thread_id}/selection")
def get_research_thread_selection(
    thread_id: str,
    store=Depends(get_thread_store),
    run_store=Depends(get_run_store),
) -> dict | None:
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")
    if store.get_thread(thread_id) is None:
        raise HTTPException(status_code=404, detail="thread not found")
    run_store = _resolve_run_store(run_store, store)
    if not hasattr(run_store, "latest_successful_for_thread"):
        from src.research_runs import ResearchRunStore

        run_store = ResearchRunStore(store.db_path)
    selection = run_store.latest_successful_for_thread(thread_id)
    if selection is None:
        return None
    return {
        "provider": selection.provider,
        "model": selection.model,
        "effort": selection.effort,
    }


@router.get("/research/threads/{thread_id}/messages")
def list_research_messages(
    thread_id: str,
    store=Depends(get_thread_store),
) -> dict:
    """A thread's messages in order (for hydrating a restored conversation)."""
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")
    if store.get_thread(thread_id) is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return {"thread_id": thread_id, "messages": [_message_dict(m) for m in store.list_messages(thread_id)]}


@router.delete("/research/threads/{thread_id}")
def delete_research_thread(
    thread_id: str,
    store=Depends(get_thread_store),
    run_store=Depends(get_run_store),
) -> dict:
    """Delete one persisted thread and its messages from the local store.

    DELETE is idempotent for a valid id: a stale UI row or already-deleted
    thread returns deleted=false instead of surfacing a product-level error.
    """
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")
    try:
        deleted = store.delete_thread(thread_id)
    except ResearchThreadActiveError as exc:
        raise HTTPException(
            status_code=409,
            detail="active research run prevents deleting this thread",
        ) from exc
    return {"thread_id": thread_id, "deleted": deleted}


def _resolve_auth_metadata(provider: str) -> tuple[str | None, str | None]:
    res = resolve_live_auth(provider)
    if res.source == "db_api_key":
        return "api_key", res.credential_id
    if res.source == "oauth_driver_unwired":
        if provider == "openai":
            return "chatgpt_oauth", res.credential_id
        if provider == "anthropic":
            return "claude_code_oauth", res.credential_id
    return None, res.credential_id


@router.post("/research/runs")
async def create_research_run(
    request: ResearchRunCreate,
    dal=Depends(get_dal),
    thread_store=Depends(get_thread_store),
    run_store=Depends(get_run_store),
) -> dict:
    provider = request.provider.lower().strip()
    if provider not in ("openai", "anthropic"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")
    # Track A: reject invalid stance overrides at CREATE — a queued run must
    # never fail later on a value the client could have been told about now.
    from src.api.personalization import resolve_personalization

    resolve_personalization(request.assistant_stance)

    thread_id = request.thread_id or str(uuid.uuid4())
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")

    existing_thread = thread_store.get_thread(thread_id)
    model, effort = request.model, request.effort
    if model is None:
        model, effort = resolve_research_route(provider)
    if effort in (None, ""):
        effort = "default"
    auth_mode, credential_id = _resolve_auth_metadata(provider)
    agent_question = _compose_agent_question(question, request.ticker)

    try:
        run, history = run_store.create_run_with_user_message(
            thread_store=thread_store,
            new_thread_title=(
                question[:TITLE_MAX] if existing_thread is None else None
            ),
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            question=agent_question,
            user_content=question,
            user_tickers=[request.ticker] if request.ticker else None,
            ticker=(request.ticker or None),
            provider=provider,
            model=model,
            effort=effort,
            auth_mode=auth_mode,
            credential_id=credential_id,
            assistant_stance=request.assistant_stance,
            retry_last_failed=request.retry_last_failed,
        )
    except ResearchRunUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        schedule_research_run(
            run_id=run.id,
            run_store=run_store,
            thread_store=thread_store,
            dal=dal,
            history=history,
        )
    except Exception:
        logger.exception("failed to schedule research run %s", run.id)
        try:
            run_store.fail_queued_run_handoff(
                run_id=run.id,
                thread_store=thread_store,
                message=_SCHEDULE_FAILURE_MESSAGE,
            )
        except Exception:
            logger.exception("failed to persist research scheduling failure %s", run.id)
        raise HTTPException(
            status_code=503,
            detail=_SCHEDULE_FAILURE_MESSAGE,
        ) from None
    return {"run": _run_dict(run)}


@router.get("/research/runs/{run_id}")
def get_research_run(
    run_id: str,
    run_store=Depends(get_run_store),
) -> dict:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run": _run_dict(run)}


@router.get("/research/runs/{run_id}/events")
def list_research_run_events(
    run_id: str,
    after: int = Query(0, ge=0),
    run_store=Depends(get_run_store),
) -> dict:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    events = run_store.list_events(run_id, after=after, limit=_RUN_EVENT_PAGE_SIZE + 1)
    has_more = len(events) > _RUN_EVENT_PAGE_SIZE
    events = events[:_RUN_EVENT_PAGE_SIZE]
    return {
        "run": _run_dict(run),
        "events": [_event_dict(e) for e in events],
        "has_more": has_more,
    }


@router.post("/research/runs/{run_id}/cancel")
def cancel_research_run_route(
    run_id: str,
    run_store=Depends(get_run_store),
    thread_store=Depends(get_thread_store),
) -> dict:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status in ACTIVE_STATUSES:
        if not cancel_research_run(run_id):
            failure = classify_research_failure(
                "research run cancelled",
                explicit_code="run_cancelled",
            )
            run_store.terminalize_error_with_message(
                thread_store=thread_store,
                run_id=run_id,
                status="cancelled",
                error=failure.detail,
                error_code=failure.code,
            )
    return {"run": _run_dict(run_store.get_run(run_id))}
