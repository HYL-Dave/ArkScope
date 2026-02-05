"""
Agent SDK integration for MindfulRL.

Supports both OpenAI Agents SDK and Anthropic SDK for natural language
queries against the tools layer.

Usage:
    # OpenAI Agent
    from src.agents.openai_agent import run_query as run_openai_query
    result = await run_openai_query("What's the sentiment for NVDA?")

    # Anthropic Agent
    from src.agents.anthropic_agent import run_query as run_anthropic_query
    result = await run_anthropic_query("What's AMD's IV percentile?")
"""

from .config import AgentConfig, get_agent_config

__all__ = ["AgentConfig", "get_agent_config"]