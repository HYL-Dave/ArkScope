"""
Read routes for the AI 研究 surface (Layer C-2b): list persisted threads and a
thread's messages, so the web app can hydrate on reload.

Local-first: served from the local ResearchThreadStore (profile_state.db family),
never the remote PG. Writes happen as a best-effort side effect of POST
/query/stream (see query.py), not here — these are read-only.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.agents.config import resolve_research_route
from src.api.routes.query import _compose_agent_question, TITLE_MAX
from src.auth_drivers.live_resolver import resolve_live_auth
from src.research_run_manager import cancel_research_run, schedule_research_run
from src.research_runs import ACTIVE_STATUSES, ResearchRun, ResearchRunEvent
from src.research_threads import ResearchMessage, ResearchThread, valid_thread_id

from ..dependencies import get_dal, get_run_store, get_thread_store

router = APIRouter(tags=["research"])
_RUN_EVENT_PAGE_SIZE = 500


class ResearchRunCreate(BaseModel):
    thread_id: str | None = None
    question: str
    ticker: str | None = None
    provider: str
    model: str | None = None
    effort: str | None = None
    retry_last_failed: bool = False


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
        "auth_mode": run.auth_mode,
        "credential_id": run.credential_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error": run.error,
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


def _thread_dict(t: ResearchThread, *, run_store=None) -> dict:
    out = {
        "id": t.id, "title": t.title, "ticker": t.ticker,
        "provider": t.provider, "model": t.model,
        "created_at": t.created_at, "updated_at": t.updated_at,
    }
    if run_store is not None:
        out["active_run"] = _run_dict(run_store.latest_active_for_thread(t.id))
    return out


def _message_dict(m: ResearchMessage) -> dict:
    return {
        "role": m.role, "content": m.content, "provider": m.provider, "model": m.model,
        "tools_used": m.tools_used, "tool_calls": m.tool_calls,
        "token_usage": m.token_usage, "tickers": m.tickers,
        "elapsed_seconds": m.elapsed_seconds, "is_error": m.is_error, "created_at": m.created_at,
    }


@router.get("/research/threads")
def list_research_threads(
    limit: int = Query(50, ge=1, le=200),
    store=Depends(get_thread_store),
    run_store=Depends(get_run_store),
) -> dict:
    """Persisted threads, newest-activity first (for the left-pane list)."""
    if not hasattr(run_store, "latest_active_for_thread"):
        run_store = None  # handler-direct tests may omit this dependency
    return {"threads": [_thread_dict(t, run_store=run_store) for t in store.list_threads(limit=limit)]}


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
) -> dict:
    """Delete one persisted thread and its messages from the local store.

    DELETE is idempotent for a valid id: a stale UI row or already-deleted
    thread returns deleted=false instead of surfacing a product-level error.
    """
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")
    return {"thread_id": thread_id, "deleted": store.delete_thread(thread_id)}


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

    thread_id = request.thread_id or str(uuid.uuid4())
    if not valid_thread_id(thread_id):
        raise HTTPException(status_code=422, detail="invalid thread_id")
    if run_store.latest_active_for_thread(thread_id) is not None:
        raise HTTPException(status_code=409, detail="thread already has an active research run")

    from src.research_threads import build_thread_history

    history = (
        build_thread_history(
            thread_store,
            thread_id,
            exclude_last_failed_pair=request.retry_last_failed,
        )
        if thread_store.get_thread(thread_id) is not None
        else []
    )
    model, effort = request.model, request.effort
    if model is None:
        model, effort = resolve_research_route(provider)
    auth_mode, credential_id = _resolve_auth_metadata(provider)
    agent_question = _compose_agent_question(question, request.ticker)

    thread_store.ensure_thread(
        id=thread_id,
        title=question[:TITLE_MAX],
        ticker=(request.ticker or None),
        provider=provider,
        model=model,
    )
    thread_store.append_message(
        thread_id=thread_id,
        role="user",
        content=question,
        tickers=[request.ticker] if request.ticker else None,
    )
    run = run_store.create_run(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        question=agent_question,
        ticker=(request.ticker or None),
        provider=provider,
        model=model,
        effort=effort,
        auth_mode=auth_mode,
        credential_id=credential_id,
    )
    schedule_research_run(
        run_id=run.id,
        run_store=run_store,
        thread_store=thread_store,
        dal=dal,
        history=history,
    )
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
) -> dict:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status in ACTIVE_STATUSES:
        if not cancel_research_run(run_id):
            run_store.append_event(run_id, "error", {"error": "research run cancelled"})
            run_store.mark_terminal(run_id, "cancelled", error="research run cancelled")
    return {"run": _run_dict(run_store.get_run(run_id))}
