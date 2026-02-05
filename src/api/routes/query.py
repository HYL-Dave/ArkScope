"""
POST /query endpoint for Agent-based natural language queries.

Supports both OpenAI Agents SDK and Anthropic SDK.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_dal

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    """Request body for POST /query."""
    question: str
    provider: str = "openai"  # "openai" | "anthropic"
    model: Optional[str] = None  # Override default model


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

    The agent has access to all MindfulRL tools (news, prices, options,
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

    if provider == "openai":
        try:
            from src.agents.openai_agent import run_query
            result = await run_query(
                question=request.question,
                model=request.model,
                dal=dal,
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
                model=request.model,
                dal=dal,
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