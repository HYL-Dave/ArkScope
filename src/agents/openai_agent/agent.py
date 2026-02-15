"""
OpenAI Agents SDK agent implementation.

Uses GPT-5.2 with configurable reasoning effort for tool calling.
Provides run_query(), run_query_sync(), and run_query_stream().
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..config import get_agent_config, ReasoningEffort
from ..shared.events import AgentEvent, EventType
from ..shared.prompts import SYSTEM_PROMPT
from ..shared.scratchpad import Scratchpad
from ..shared.token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# ── Model output limits ────────────────────────────────────────
# GPT-5.x 全系列 max output tokens = 128K
# max_output_tokens 包含 reasoning tokens + visible output（跟 Anthropic max_tokens 相同概念）
# 不設此值時 API 預設未文件化，可能僅 2K-4K，對高 reasoning effort 不夠
_OPENAI_MODEL_MAX_OUTPUT = {
    "gpt-5.2": 128000,
    "gpt-5-mini": 128000,
    # Codex series (agentic coding optimized, same output limits)
    "gpt-5.2-codex": 128000,
    "gpt-5.3-codex": 128000,
}
_OPENAI_DEFAULT_MAX_OUTPUT = 128000


def _get_openai_max_output(model: str) -> int:
    """Return the model's maximum output token limit."""
    for prefix, limit in _OPENAI_MODEL_MAX_OUTPUT.items():
        if model.startswith(prefix):
            return limit
    return _OPENAI_DEFAULT_MAX_OUTPUT


def _build_agent(
    model_name: str,
    tools: list,
    reasoning_effort: ReasoningEffort = "high",
    max_tokens: int = 16384,
):
    """Build an Agent with ModelSettings including reasoning config.

    設計決策（與 Anthropic thinking 模式一致）：
    - reasoning_effort != "none" → max_tokens = 模型 max output (128K)
      reasoning tokens 從 max_output_tokens 扣，需要足夠空間
    - reasoning_effort == "none" → max_tokens = config.max_tokens (16384)
      不消耗 reasoning tokens，只需 visible output 空間
    """
    from agents import Agent, ModelSettings
    from openai.types.shared import Reasoning

    # 自動決定 effective_max_tokens
    if reasoning_effort == "none":
        effective_max_tokens = max_tokens
    else:
        effective_max_tokens = _get_openai_max_output(model_name)

    return Agent(
        name="MindfulRL Assistant",
        instructions=SYSTEM_PROMPT,
        model=model_name,
        tools=tools,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=reasoning_effort),
            max_tokens=effective_max_tokens,
        ),
    )


async def run_query(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    reasoning_effort: Optional[ReasoningEffort] = None,
    max_tool_calls: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run a natural language query using OpenAI Agents SDK.

    Args:
        question: The user's question
        model: Override model (default: gpt-5.2 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)
        max_tool_calls: Override max tool calls (default from AgentConfig)

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
    agent = _build_agent(model_name, tools, reasoning_effort=effort, max_tokens=config.max_tokens)

    # Run query
    logger.info(
        f"Running OpenAI agent: model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    pad = Scratchpad(query=question, provider="openai", model=model_name)

    effective_max_turns = max_tool_calls or config.max_tool_calls
    result = await Runner.run(
        agent,
        input=question,
        max_turns=effective_max_turns,
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
                        pad.log_tool_call(item.name, getattr(item, "arguments", {}))

    answer = str(result.final_output) if result.final_output else ""
    pad.log_final_answer(answer, token_usage=tracker.summary(), tools_used=list(set(tools_used)))
    pad.close()

    logger.info(f"OpenAI agent done: {tracker}")

    return {
        "answer": answer,
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
    max_tool_calls: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for run_query().

    Args:
        question: The user's question
        model: Override model (default: gpt-5.2 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)
        max_tool_calls: Override max tool calls (default from AgentConfig)

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
    agent = _build_agent(model_name, tools, reasoning_effort=effort, max_tokens=config.max_tokens)

    # Run query synchronously
    logger.info(
        f"Running OpenAI agent (sync): model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    pad = Scratchpad(query=question, provider="openai", model=model_name)

    effective_max_turns = max_tool_calls or config.max_tool_calls
    result = Runner.run_sync(
        agent,
        input=question,
        max_turns=effective_max_turns,
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
                        pad.log_tool_call(item.name, getattr(item, "arguments", {}))

    answer = str(result.final_output) if result.final_output else ""
    pad.log_final_answer(answer, token_usage=tracker.summary(), tools_used=list(set(tools_used)))
    pad.close()

    logger.info(f"OpenAI agent done (sync): {tracker}")

    return {
        "answer": answer,
        "tools_used": list(set(tools_used)),
        "provider": "openai",
        "model": model_name,
        "token_usage": tracker.summary(),
    }


async def run_query_stream(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    reasoning_effort: Optional[ReasoningEffort] = None,
) -> AsyncGenerator[AgentEvent, None]:
    """
    Run a query yielding events for progress tracking.

    OpenAI Agents SDK handles the tool loop internally (black box),
    so we can only emit events before and after the run. Tool events
    are extracted post-run from raw_responses.

    Args:
        question: The user's question
        model: Override model (default: gpt-5.2 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)

    Yields:
        AgentEvent for thinking, tool_end (post-run), and done
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
    agent = _build_agent(model_name, tools, reasoning_effort=effort, max_tokens=config.max_tokens)

    logger.info(
        f"Running OpenAI agent (stream): model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    yield AgentEvent(EventType.thinking, {"turn": 1, "model": model_name})

    pad = Scratchpad(query=question, provider="openai", model=model_name)

    result = await Runner.run(
        agent,
        input=question,
        max_turns=config.max_tool_calls,
    )

    # Extract tools used and token usage from result
    tracker = TokenTracker()
    tools_used: List[str] = []
    if hasattr(result, "raw_responses"):
        tracker.record_openai_result(result, model=model_name)
        for response in result.raw_responses:
            if hasattr(response, "output"):
                for item in response.output:
                    if hasattr(item, "name"):
                        tools_used.append(item.name)
                        pad.log_tool_call(item.name, getattr(item, "arguments", {}))
                        yield AgentEvent(EventType.tool_end, {"tool": item.name})

    answer = str(result.final_output) if result.final_output else ""
    pad.log_final_answer(answer, token_usage=tracker.summary(), tools_used=list(set(tools_used)))
    pad.close()

    logger.info(f"OpenAI agent done (stream): {tracker}")

    yield AgentEvent(EventType.done, {
        "answer": answer,
        "tools_used": list(set(tools_used)),
        "provider": "openai",
        "model": model_name,
        "token_usage": tracker.summary(),
    })