"""
Anthropic SDK agent implementation.

Provides run_query() and run_query_stream() for natural language queries
against the tools layer. Uses the standard tool_use flow with message loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..config import get_agent_config
from ..shared.context_manager import ContextManager
from ..shared.events import AgentEvent, EventType
from ..shared.prompts import SYSTEM_PROMPT
from ..shared.scratchpad import Scratchpad
from ..shared.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


async def run_query_stream(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
) -> AsyncGenerator[AgentEvent, None]:
    """
    Run a natural language query, yielding events as the agent progresses.

    Yields AgentEvent instances for each step: thinking, text, tool_start,
    tool_end, and finally done. Consumers can use these for live progress
    display or SSE streaming.

    Args:
        question: The user's question
        model: Override model (default from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)

    Yields:
        AgentEvent for each step of the agent loop
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError(
            "Anthropic SDK not installed. Run: pip install anthropic"
        )

    from .tools import get_anthropic_tools, execute_tool

    # Get or create DAL
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer(db_dsn="auto")

    # Get config
    config = get_agent_config()
    model_name = model or config.anthropic_model

    # Initialize client
    client = Anthropic()

    # Get tool definitions
    tools = get_anthropic_tools()

    # Initial message
    messages: List[dict] = [{"role": "user", "content": question}]
    tools_used: List[str] = []
    tracker = TokenTracker()
    pad = Scratchpad(query=question, provider="anthropic", model=model_name)
    ctx = ContextManager(
        model=model_name,
        threshold_ratio=config.context_threshold_ratio,
        keep_recent_turns=config.context_keep_recent_turns,
        preview_chars=config.context_preview_chars,
    )

    logger.info(f"Running Anthropic agent query: {question[:50]}...")

    # Tool use loop
    for turn in range(config.max_tool_calls):
        yield AgentEvent(EventType.thinking, {"turn": turn + 1, "model": model_name})

        response = client.messages.create(
            model=model_name,
            max_tokens=config.max_tokens,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        tracker.record_anthropic(response, model=model_name)
        logger.debug(
            f"Turn {turn + 1}: stop_reason={response.stop_reason} "
            f"tokens={tracker.last_input_tokens}+{tracker.turns[-1].output_tokens}"
        )

        # Check if we're done
        if response.stop_reason != "tool_use":
            # Extract final text response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            pad.log_final_answer(
                final_text,
                token_usage=tracker.summary(),
                tools_used=list(set(tools_used)),
            )
            pad.close()
            yield AgentEvent(EventType.done, {
                "answer": final_text,
                "tools_used": list(set(tools_used)),
                "provider": "anthropic",
                "model": model_name,
                "token_usage": tracker.summary(),
            })
            return

        # Process tool calls
        tool_use_blocks = [
            block for block in response.content
            if block.type == "tool_use"
        ]

        if not tool_use_blocks:
            break

        # Emit intermediate text (model thinking before tool calls)
        for block in response.content:
            if hasattr(block, "text") and block.text.strip():
                yield AgentEvent(EventType.text, {"content": block.text.strip()})

        # Execute tools and collect results
        tool_results = []
        for tool_use in tool_use_blocks:
            tool_name = tool_use.name
            tool_input = tool_use.input
            tool_id = tool_use.id

            logger.info(f"Executing tool: {tool_name}")
            tools_used.append(tool_name)
            pad.log_tool_call(tool_name, tool_input, token_usage=tracker.summary())

            yield AgentEvent(EventType.tool_start, {
                "tool": tool_name,
                "input": tool_input,
            })

            # Execute the tool
            result = execute_tool(tool_name, tool_input, dal)
            result_str = str(result)
            pad.log_tool_result(tool_name, result_summary=result_str[:200], chars=len(result_str))

            yield AgentEvent(EventType.tool_end, {
                "tool": tool_name,
                "summary": result_str[:200],
                "chars": len(result_str),
            })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result,
            })

        # Add assistant response and tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Compact old tool results if context is growing too large
        if ctx.should_compact(tracker):
            messages, compact_stats = ctx.compact_messages(messages)
            logger.info(f"Context compacted: {compact_stats}")

    # Max turns reached
    logger.warning(f"Max tool calls ({config.max_tool_calls}) reached")
    pad.log_max_turns(token_usage=tracker.summary(), tools_used=list(set(tools_used)))
    pad.close()
    yield AgentEvent(EventType.done, {
        "answer": "Maximum tool calls reached. Please try a simpler query.",
        "tools_used": list(set(tools_used)),
        "provider": "anthropic",
        "model": model_name,
        "token_usage": tracker.summary(),
    })


def run_query(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run a natural language query using Anthropic SDK with tool use.

    Backward-compatible wrapper around run_query_stream() that collects
    all events and returns the final result dict.

    Args:
        question: The user's question
        model: Override model (default from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)

    Returns:
        Dict with:
            answer: str - The agent's response
            tools_used: List[str] - Names of tools called
            provider: str - "anthropic"
            model: str - Model used
            token_usage: dict - Token usage summary
    """
    async def _collect() -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        async for event in run_query_stream(question, model, dal):
            if event.type == EventType.done:
                result = event.data
        return result

    return asyncio.run(_collect())