"""
Anthropic SDK integration for MindfulRL.

Usage:
    from src.agents.anthropic_agent import run_query

    result = run_query("What's the sentiment for NVDA?")
    print(result["answer"])
    print(result["tools_used"])
"""

from .agent import run_query

__all__ = ["run_query"]