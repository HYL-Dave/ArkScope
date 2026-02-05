"""
OpenAI Agents SDK integration for MindfulRL.

Usage:
    from src.agents.openai_agent import run_query

    result = await run_query("What's the sentiment for NVDA?")
    print(result["answer"])
    print(result["tools_used"])
"""

from .agent import run_query, run_query_sync

__all__ = ["run_query", "run_query_sync"]