"""
POST /query endpoint for Agent-based natural language queries.

Supports both OpenAI Agents SDK and Anthropic SDK.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..dependencies import get_dal, get_thread_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])

TITLE_MAX = 60  # thread title = first question, truncated (matches the client reducer)


class QueryRequest(BaseModel):
    """Request body for POST /query."""
    question: str
    provider: str = "openai"  # "openai" | "anthropic"
    model: Optional[str] = None  # Override default model
    # C-2b persistence (optional): the AI 研究 surface sends a client-owned thread
    # id + an optional ticker context. The agent is prompted with the composed
    # question; the RAW question is what gets persisted (criterion #2).
    thread_id: Optional[str] = None
    ticker: Optional[str] = None


def _compose_agent_question(question: str, ticker: Optional[str]) -> str:
    """Server-side prompt framing — the agent sees the ticker context; the store
    keeps the raw question (so history is clean, not prefixed)."""
    t = (ticker or "").strip().upper()
    return f"針對 {t}：{question}" if t else question


def accumulate_tool_calls(events: list[tuple[str, dict]]) -> list[dict]:
    """Reconstruct the chronological tool_calls from the (type, data) stream of
    tool_start/tool_end events — server-side mirror of the client reducer, so a
    reloaded turn shows the real trace (NOT the deduped done.tools_used, #3).

    tool_start opens a row (name+input); tool_end completes the most-recent open
    row (result_preview); a tool_end with no open row (OpenAI name-only batch)
    appends an already-closed name-only row.
    """
    rows: list[dict] = []
    for etype, data in events:
        if etype == "tool_start":
            rows.append({"name": data.get("tool"), "input": data.get("input"), "result_preview": None, "_done": False})
        elif etype == "tool_end":
            target = next((r for r in reversed(rows) if not r["_done"]), None)
            if target is not None:
                target["result_preview"] = data.get("summary")
                target["_done"] = True
            else:
                rows.append({"name": data.get("tool"), "input": None, "result_preview": data.get("summary"), "_done": True})
    return [{"name": r["name"], "input": r["input"], "result_preview": r["result_preview"]} for r in rows]


def _persist_user_turn(store, *, thread_id, question, ticker, provider, model, title) -> None:
    """Best-effort: a persistence failure must never break the SSE answer (#4)."""
    try:
        store.ensure_thread(id=thread_id, title=title, ticker=(ticker or None), provider=provider, model=model)
        store.append_message(thread_id=thread_id, role="user", content=question, tickers=[ticker] if ticker else None)
    except Exception as e:  # noqa: BLE001 — best-effort by design
        logger.warning("research persist (user turn) failed, continuing: %s", e)


def _persist_assistant_turn(store, *, thread_id, done_data, collected, elapsed) -> None:
    """Best-effort assistant persistence on a `done` terminal (#3 tool_calls from
    the trace, #4 safe). accumulate_tool_calls runs INSIDE the guard (SF1)."""
    try:
        store.append_message(
            thread_id=thread_id, role="assistant",
            content=done_data.get("answer", "") or "",
            provider=done_data.get("provider"), model=done_data.get("model"),
            tools_used=done_data.get("tools_used"), tool_calls=accumulate_tool_calls(collected),
            token_usage=done_data.get("token_usage"), elapsed_seconds=elapsed,
        )
    except Exception as e:  # noqa: BLE001 — best-effort by design
        logger.warning("research persist (assistant turn) failed, continuing: %s", e)


def _persist_error_turn(store, *, thread_id, content, collected, provider, model, elapsed) -> None:
    """Best-effort persistence of a NON-`done` terminal (agent error / stream
    exception) as an is_error assistant turn — so reload doesn't show a dangling
    user question with no reply (MUST-FIX 2). Partial trace preserved."""
    try:
        store.append_message(
            thread_id=thread_id, role="assistant", content=content or "(error)",
            provider=provider, model=model, tool_calls=accumulate_tool_calls(collected),
            elapsed_seconds=elapsed, is_error=True,
        )
    except Exception as e:  # noqa: BLE001 — best-effort by design
        logger.warning("research persist (error turn) failed, continuing: %s", e)


class QueryResponse(BaseModel):
    """Response from POST /query."""
    answer: str
    tools_used: List[str]
    provider: str
    model: str


@router.post("/query", response_model=QueryResponse)
async def query_agent(
    request: QueryRequest,
    dal=Depends(get_dal),
) -> QueryResponse:
    """
    Execute a natural language query using an AI agent.

    The agent has access to all ArkScope tools (news, prices, options,
    signals, fundamentals) and will call them as needed to answer your question.

    Args:
        request: QueryRequest with question, provider, and optional model override

    Returns:
        QueryResponse with answer, tools_used, provider, and model

    Examples:
        - "What's the sentiment for NVDA this week?"
        - "How has the AI_CHIPS sector performed?"
        - "Give me AMD's IV analysis"
        - "Generate a morning brief"
    """
    provider = request.provider.lower()
    # No explicit model → the AI 研究 route (or the provider's default tier).
    model, effort = request.model, None
    if model is None and provider in ("openai", "anthropic"):
        from src.agents.config import resolve_research_route
        model, effort = resolve_research_route(provider)

    if provider == "openai":
        try:
            from src.agents.openai_agent import run_query
            result = await run_query(
                question=request.question,
                model=model,
                dal=dal,
                reasoning_effort=effort,
            )
        except ImportError as e:
            raise HTTPException(
                status_code=503,
                detail=f"OpenAI Agents SDK not available: {e}"
            )
        except Exception as e:
            logger.error(f"OpenAI agent error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    elif provider == "anthropic":
        try:
            from src.agents.anthropic_agent import run_query
            result = run_query(
                question=request.question,
                model=model,
                dal=dal,
                effort=effort,
            )
        except ImportError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Anthropic SDK not available: {e}"
            )
        except Exception as e:
            logger.error(f"Anthropic agent error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider}. Use 'openai' or 'anthropic'."
        )

    return QueryResponse(**result)


@router.post("/query/stream")
async def query_agent_stream(
    request: QueryRequest,
    dal=Depends(get_dal),
    store=Depends(get_thread_store),
):
    """
    Execute a query with Server-Sent Events for live progress.

    Returns a stream of SSE events as the agent processes the query.
    Each event has ``data: {"type": "...", "data": {...}}`` format.

    Event types:
        - thinking: API call started
        - text: Intermediate text from model
        - tool_start: Tool execution begins
        - tool_end: Tool execution finished
        - error: Error occurred
        - done: Final answer with full result
    """
    provider = request.provider.lower()
    # #2: the agent sees the ticker-framed question; the store keeps the raw one.
    agent_question = _compose_agent_question(request.question, request.ticker)
    # C-2b persistence gated on a valid client-owned thread id (#5). Invalid →
    # just don't persist (never error the stream — #4).
    from src.research_threads import build_thread_history, valid_thread_id
    persist = valid_thread_id(request.thread_id)

    async def event_generator():
        import time as _time

        # Multi-turn (C-2c): prior thread turns seed the agent. Fetch BEFORE
        # persisting this turn's user message so it isn't duplicated. full_thread
        # policy, no silent truncation (AI_RESEARCH_CONTEXT_MEMORY_PLAN.md §4).
        history = build_thread_history(store, request.thread_id) if persist else []
        # No explicit model → the AI 研究 route (or the provider's default tier).
        # Resolve BEFORE persisting so the thread records the model actually used.
        res_model, res_effort = request.model, None
        if res_model is None and provider in ("openai", "anthropic"):
            from src.agents.config import resolve_research_route
            res_model, res_effort = resolve_research_route(provider)
        if persist:
            _persist_user_turn(
                store, thread_id=request.thread_id, question=request.question,
                ticker=request.ticker, provider=provider, model=res_model,
                title=request.question[:TITLE_MAX],
            )
        collected: list[tuple[str, dict]] = []  # (#3) tool_start/tool_end trace
        done_data: Optional[dict] = None
        error_content: Optional[str] = None  # set on a non-done terminal (MUST-FIX 2)
        t0 = _time.monotonic()
        try:
            if provider == "openai":
                from src.agents.openai_agent.agent import run_query_stream
                stream = run_query_stream(question=agent_question, model=res_model, dal=dal, reasoning_effort=res_effort, history=history)
            elif provider == "anthropic":
                from src.agents.anthropic_agent.agent import run_query_stream
                stream = run_query_stream(question=agent_question, model=res_model, dal=dal, effort=res_effort, history=history)
            else:
                from src.agents.shared.events import AgentEvent, EventType
                error_content = f"Unknown provider: {provider}"  # so finally persists the error turn (no dangling user)
                yield AgentEvent(EventType.error, {"message": error_content}).to_sse()
                return

            async for event in stream:
                if persist:
                    etype = getattr(event.type, "value", event.type)
                    if etype in ("tool_start", "tool_end"):
                        collected.append((etype, event.data))
                    elif etype == "done":
                        done_data = event.data
                    elif etype == "error":
                        error_content = event.data.get("error") or event.data.get("message")
                yield event.to_sse()
        except Exception as e:
            from src.agents.shared.events import AgentEvent, EventType
            logger.error(f"Stream error: {e}")
            error_content = str(e)
            yield AgentEvent(EventType.error, {"message": str(e)}).to_sse()
        finally:
            # Persist the terminal turn. done → assistant; a non-done terminal
            # (agent error / stream exception) → an is_error turn so reload never
            # shows a dangling user question (MUST-FIX 2). Both best-effort (#4).
            # A pure client disconnect (no done, no error) leaves only the user
            # turn — see spec §6b (only resolved turns survive reload).
            if persist:
                elapsed = round(_time.monotonic() - t0, 3)
                if done_data is not None:
                    _persist_assistant_turn(store, thread_id=request.thread_id, done_data=done_data, collected=collected, elapsed=elapsed)
                elif error_content is not None:
                    _persist_error_turn(store, thread_id=request.thread_id, content=error_content, collected=collected, provider=provider, model=request.model, elapsed=elapsed)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/query/providers")
async def list_providers() -> dict:
    """
    List available agent providers and their status.

    Returns:
        Dict with provider names and availability status
    """
    providers = {}

    # Check OpenAI
    try:
        import agents
        providers["openai"] = {
            "available": True,
            "sdk_version": getattr(agents, "__version__", "unknown"),
        }
    except ImportError:
        providers["openai"] = {
            "available": False,
            "install": "pip install openai-agents",
        }

    # Check Anthropic
    try:
        import anthropic
        providers["anthropic"] = {
            "available": True,
            "sdk_version": getattr(anthropic, "__version__", "unknown"),
        }
    except ImportError:
        providers["anthropic"] = {
            "available": False,
            "install": "pip install anthropic",
        }

    return {"providers": providers}