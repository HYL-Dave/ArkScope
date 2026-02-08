"""
OpenAI Agents SDK agent implementation.

Uses GPT-5.2 with configurable reasoning effort for tool calling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..config import get_agent_config, ReasoningEffort
from ..shared.prompts import SYSTEM_PROMPT
from ..shared.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


def _build_agent(
    model_name: str,
    tools: list,
    reasoning_effort: ReasoningEffort = "high",
):
    """Build an Agent with ModelSettings including reasoning config."""
    from agents import Agent, ModelSettings
    from openai.types.shared import Reasoning

    return Agent(
        name="MindfulRL Assistant",
        instructions=SYSTEM_PROMPT,
        model=model_name,
        tools=tools,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=reasoning_effort),
        ),
    )


async def run_query(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    reasoning_effort: Optional[ReasoningEffort] = None,
) -> Dict[str, Any]:
    """
    Run a natural language query using OpenAI Agents SDK.

    Args:
        question: The user's question
        model: Override model (default: gpt-5.2 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)

    Returns:
        Dict with:
            answer: str - The agent's response
            tools_used: List[str] - Names of tools called
            provider: str - "openai"
            model: str - Model used
    """
    try:
        from agents import Runner
    except ImportError:
        raise ImportError(
            "OpenAI Agents SDK not installed. Run: pip install openai-agents"
        )

    from .tools import create_openai_tools

    # Get or create DAL
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer(db_dsn="auto")

    # Get config
    config = get_agent_config()
    model_name = model or config.openai_model
    effort = reasoning_effort or config.reasoning_effort

    # Create tools bound to DAL
    tools = create_openai_tools(dal)

    # Create agent with reasoning settings
    agent = _build_agent(model_name, tools, reasoning_effort=effort)

    # Run query
    logger.info(
        f"Running OpenAI agent: model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    result = await Runner.run(
        agent,
        input=question,
        max_turns=config.max_tool_calls,
    )

    # Extract tools used and token usage from result
    tracker = TokenTracker()
    tools_used = []
    if hasattr(result, "raw_responses"):
        tracker.record_openai_result(result, model=model_name)
        for response in result.raw_responses:
            if hasattr(response, "output"):
                for item in response.output:
                    if hasattr(item, "name"):
                        tools_used.append(item.name)

    logger.info(f"OpenAI agent done: {tracker}")

    return {
        "answer": str(result.final_output) if result.final_output else "",
        "tools_used": list(set(tools_used)),
        "provider": "openai",
        "model": model_name,
        "token_usage": tracker.summary(),
    }


def run_query_sync(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    reasoning_effort: Optional[ReasoningEffort] = None,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for run_query().

    Args:
        question: The user's question
        model: Override model (default: gpt-5.2 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)

    Returns:
        Dict with answer, tools_used, provider, model
    """
    try:
        from agents import Runner
    except ImportError:
        raise ImportError(
            "OpenAI Agents SDK not installed. Run: pip install openai-agents"
        )

    from .tools import create_openai_tools

    # Get or create DAL
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer(db_dsn="auto")

    # Get config
    config = get_agent_config()
    model_name = model or config.openai_model
    effort = reasoning_effort or config.reasoning_effort

    # Create tools bound to DAL
    tools = create_openai_tools(dal)

    # Create agent with reasoning settings
    agent = _build_agent(model_name, tools, reasoning_effort=effort)

    # Run query synchronously
    logger.info(
        f"Running OpenAI agent (sync): model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    result = Runner.run_sync(
        agent,
        input=question,
        max_turns=config.max_tool_calls,
    )

    # Extract tools used and token usage
    tracker = TokenTracker()
    tools_used = []
    if hasattr(result, "raw_responses"):
        tracker.record_openai_result(result, model=model_name)
        for response in result.raw_responses:
            if hasattr(response, "output"):
                for item in response.output:
                    if hasattr(item, "name"):
                        tools_used.append(item.name)

    logger.info(f"OpenAI agent done (sync): {tracker}")

    return {
        "answer": str(result.final_output) if result.final_output else "",
        "tools_used": list(set(tools_used)),
        "provider": "openai",
        "model": model_name,
        "token_usage": tracker.summary(),
    }