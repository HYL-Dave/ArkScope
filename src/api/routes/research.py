"""
Read routes for the AI 研究 surface (Layer C-2b): list persisted threads and a
thread's messages, so the web app can hydrate on reload.

Local-first: served from the local ResearchThreadStore (profile_state.db family),
never the remote PG. Writes happen as a best-effort side effect of POST
/query/stream (see query.py), not here — these are read-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.research_threads import ResearchMessage, ResearchThread, valid_thread_id

from ..dependencies import get_thread_store

router = APIRouter(tags=["research"])


def _thread_dict(t: ResearchThread) -> dict:
    return {
        "id": t.id, "title": t.title, "ticker": t.ticker,
        "provider": t.provider, "model": t.model,
        "created_at": t.created_at, "updated_at": t.updated_at,
    }


def _message_dict(m: ResearchMessage) -> dict:
    return {
        "role": m.role, "content": m.content, "provider": m.provider, "model": m.model,
        "tools_used": m.tools_used, "tool_calls": m.tool_calls,
        "token_usage": m.token_usage, "tickers": m.tickers,
        "elapsed_seconds": m.elapsed_seconds, "created_at": m.created_at,
    }


@router.get("/research/threads")
def list_research_threads(
    limit: int = Query(50, ge=1, le=200),
    store=Depends(get_thread_store),
) -> dict:
    """Persisted threads, newest-activity first (for the left-pane list)."""
    return {"threads": [_thread_dict(t) for t in store.list_threads(limit=limit)]}


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
