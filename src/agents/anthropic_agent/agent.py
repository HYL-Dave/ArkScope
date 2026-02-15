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
from ..shared.subagent import _EXTENDED_CONTEXT_BETA, _use_extended_context
from ..shared.token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# ── Claude Web Search server tool (Phase 10) ────────────────────

_CLAUDE_WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}

# ── Model capability detection ──────────────────────────────────

_ADAPTIVE_THINKING_MODELS = {"claude-opus-4-6"}
_EFFORT_MODELS = {"claude-opus-4-6", "claude-opus-4-5"}

# 各模型最大 output tokens（API 硬限制）
# 用於 thinking 模式自動設定 max_tokens
_MODEL_MAX_OUTPUT = {
    "claude-opus-4-6": 128000,
    "claude-opus-4-5": 64000,
    "claude-sonnet-4-5": 64000,
    "claude-haiku-4-5": 64000,
}


def _get_model_max_output(model: str) -> int:
    """Return the model's maximum output token limit."""
    for prefix, limit in _MODEL_MAX_OUTPUT.items():
        if model.startswith(prefix):
            return limit
    return 64000  # safe fallback


def _supports_adaptive_thinking(model: str) -> bool:
    """Opus 4.6 supports adaptive thinking (no budget_tokens needed)."""
    return any(model.startswith(m) for m in _ADAPTIVE_THINKING_MODELS)


def _supports_effort(model: str) -> bool:
    """Opus 4.5+ supports output_config.effort."""
    return any(model.startswith(m) for m in _EFFORT_MODELS)


def _build_thinking_param(model: str, thinking_enabled: bool, config) -> tuple:
    """Return (thinking_param, effective_max_tokens) based on model and config.

    設計決策 (Phase 8)：
    - max_tokens 和 budget_tokens 全自動推導，不需手動配置
    - effective_max_tokens = 模型最大 output (128K for Opus 4.6, 64K for others)
    - budget_tokens = effective_max_tokens - config.max_tokens
      (留 config.max_tokens 給 response，其餘全給 thinking，效果最好)
    - Adaptive 模式 (Opus 4.6) 不需要 budget_tokens，Claude 自動調配

    Args:
        model: Model ID string
        thinking_enabled: Whether thinking is enabled (runtime or config)
        config: AgentConfig instance

    Returns:
        (thinking_dict_or_None, effective_max_tokens)
    """
    if not thinking_enabled:
        return None, config.max_tokens

    # Thinking 開啟 → 用模型最大 output 作為 max_tokens
    effective_max_tokens = _get_model_max_output(model)

    if _supports_adaptive_thinking(model):
        # Opus 4.6: Claude 自動判斷思考深度，不需 budget
        return {"type": "adaptive"}, effective_max_tokens
    else:
        # 其他模型: 留 config.max_tokens 給 response，其餘全給 thinking
        budget = effective_max_tokens - config.max_tokens
        # 確保 budget 合理（至少 1024，且 < effective_max_tokens）
        budget = max(budget, 1024)
        budget = min(budget, effective_max_tokens - 1)
        return {
            "type": "enabled",
            "budget_tokens": budget,
        }, effective_max_tokens


async def run_query_stream(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    effort: Optional[str] = None,
    thinking: Optional[bool] = None,
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
        effort: Override Anthropic effort level (Opus 4.5+)
        thinking: Override thinking toggle (None = use config)

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

    # Conditionally add Claude web search server tool (Phase 10)
    if config.web_claude_search:
        tools.append({
            **_CLAUDE_WEB_SEARCH_TOOL,
            "max_uses": config.web_claude_max_uses,
        })

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

    # Build optional API params (effort + thinking)
    api_kwargs: Dict[str, Any] = {}

    effective_effort = effort if effort is not None else config.anthropic_effort
    if effective_effort and _supports_effort(model_name):
        api_kwargs["output_config"] = {"effort": effective_effort}

    thinking_on = thinking if thinking is not None else config.anthropic_thinking
    thinking_param, effective_max_tokens = _build_thinking_param(
        model_name, thinking_on, config,
    )
    if thinking_param:
        api_kwargs["thinking"] = thinking_param

    logger.info(
        f"Running Anthropic agent query: {question[:50]}... "
        f"effort={effective_effort} thinking={thinking_on}"
    )

    # 1M context beta: use beta.messages.stream for supported models
    use_beta = _use_extended_context(model_name, config.extended_context)
    if use_beta:
        logger.info(f"Using 1M context beta for {model_name}")

    # Tool use loop
    for turn in range(config.max_tool_calls):
        yield AgentEvent(EventType.thinking, {"turn": turn + 1, "model": model_name})

        stream_kwargs = dict(
            model=model_name,
            max_tokens=effective_max_tokens,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
            **api_kwargs,
        )

        if use_beta:
            stream_ctx = client.beta.messages.stream(
                betas=[_EXTENDED_CONTEXT_BETA],
                **stream_kwargs,
            )
        else:
            stream_ctx = client.messages.stream(**stream_kwargs)

        with stream_ctx as stream:
            response = stream.get_final_message()

        tracker.record_anthropic(response, model=model_name)
        logger.debug(
            f"Turn {turn + 1}: stop_reason={response.stop_reason} "
            f"tokens={tracker.last_input_tokens}+{tracker.turns[-1].output_tokens}"
        )

        # Emit thinking content events (extended thinking blocks)
        for block in response.content:
            if block.type == "thinking":
                yield AgentEvent(EventType.thinking_content, {
                    "thinking": block.thinking,
                })

        # Handle pause_turn (Claude web search server tool mid-turn pause)
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            logger.debug("pause_turn: Claude web search in progress, continuing...")
            continue

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

            yield AgentEvent(EventType.tool_start, {
                "tool": tool_name,
                "input": tool_input,
            })

            # Execute the tool
            result = execute_tool(tool_name, tool_input, dal)
            result_str = str(result)
            pad.log_tool_result(tool_name, result_data=result_str, tool_input=tool_input)

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
    effort: Optional[str] = None,
    thinking: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Run a natural language query using Anthropic SDK with tool use.

    Backward-compatible wrapper around run_query_stream() that collects
    all events and returns the final result dict.

    Args:
        question: The user's question
        model: Override model (default from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        effort: Override Anthropic effort level (Opus 4.5+)
        thinking: Override thinking toggle (None = use config)

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
        async for event in run_query_stream(
            question, model, dal, effort=effort, thinking=thinking,
        ):
            if event.type == EventType.done:
                result = event.data
        return result

    return asyncio.run(_collect())