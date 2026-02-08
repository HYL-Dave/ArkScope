"""
Anthropic SDK agent implementation.

Provides run_query() for natural language queries against the tools layer.
Uses the standard tool_use flow with message loop.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..config import get_agent_config
from ..shared.prompts import SYSTEM_PROMPT
from ..shared.scratchpad import Scratchpad
from ..shared.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


def run_query(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run a natural language query using Anthropic SDK with tool use.

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
    messages = [{"role": "user", "content": question}]
    tools_used: List[str] = []
    tracker = TokenTracker()
    pad = Scratchpad(query=question, provider="anthropic", model=model_name)

    logger.info(f"Running Anthropic agent query: {question[:50]}...")

    # Tool use loop
    for turn in range(config.max_tool_calls):
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
            return {
                "answer": final_text,
                "tools_used": list(set(tools_used)),
                "provider": "anthropic",
                "model": model_name,
                "token_usage": tracker.summary(),
            }

        # Process tool calls
        tool_use_blocks = [
            block for block in response.content
            if block.type == "tool_use"
        ]

        if not tool_use_blocks:
            # No tool calls, but stop_reason was tool_use - shouldn't happen
            break

        # Execute tools and collect results
        tool_results = []
        for tool_use in tool_use_blocks:
            tool_name = tool_use.name
            tool_input = tool_use.input
            tool_id = tool_use.id

            logger.info(f"Executing tool: {tool_name}")
            tools_used.append(tool_name)
            pad.log_tool_call(tool_name, tool_input, token_usage=tracker.summary())

            # Execute the tool
            result = execute_tool(tool_name, tool_input, dal)
            pad.log_tool_result(tool_name, result_summary=str(result)[:200], chars=len(str(result)))

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result,
            })

        # Add assistant response and tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # Max turns reached
    logger.warning(f"Max tool calls ({config.max_tool_calls}) reached")
    pad.log_max_turns(token_usage=tracker.summary(), tools_used=list(set(tools_used)))
    pad.close()
    return {
        "answer": "Maximum tool calls reached. Please try a simpler query.",
        "tools_used": list(set(tools_used)),
        "provider": "anthropic",
        "model": model_name,
        "token_usage": tracker.summary(),
    }