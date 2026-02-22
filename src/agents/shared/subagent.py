"""
Subagent dispatch — specialized agents for focused subtasks (Phase 6).

The main agent can delegate tasks to subagents via the `delegate_to_subagent` tool.
Each subagent has its own model, system prompt, tool subset, and token tracker.
Subagents start from clean state and return structured JSON results.

Subagent communication: only structured JSON results, no message history sharing.
"""

from __future__ import annotations

import json
import logging
from copy import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 1M context beta ────────────────────────────────────────────

_EXTENDED_CONTEXT_MODELS = {"claude-opus-4-6", "claude-sonnet-4-6"}
_EXTENDED_CONTEXT_BETA = "context-1m-2025-08-07"


def _use_extended_context(model: str, enabled: bool) -> bool:
    """Check if extended context (1M) should be used for this model."""
    return enabled and any(model.startswith(m) for m in _EXTENDED_CONTEXT_MODELS)


# ── Provider detection ─────────────────────────────────────────

def _detect_provider(model: str) -> str:
    """Auto-detect provider from model name prefix."""
    if model.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return "anthropic"


# ── Tool filtering ─────────────────────────────────────────────

def _filter_anthropic_tools(
    all_tools: List[Dict[str, Any]],
    allowed_names: List[str],
) -> List[Dict[str, Any]]:
    """Filter Anthropic tool schemas to only include allowed names."""
    allowed = set(allowed_names)
    return [t for t in all_tools if t["name"] in allowed]


def _filter_openai_tools(all_tools: List, allowed_names: List[str]) -> List:
    """Filter OpenAI @function_tool objects to only include allowed names.

    Handles the tool_ prefix convention used by OpenAI SDK wrappers.
    """
    allowed = set(allowed_names)
    allowed_prefixed = {f"tool_{n}" for n in allowed_names}
    return [
        t for t in all_tools
        if getattr(t, "name", "") in allowed | allowed_prefixed
    ]


# ── SubagentConfig ─────────────────────────────────────────────

@dataclass
class SubagentConfig:
    """Definition of a specialized subagent."""

    name: str
    description: str
    model: str
    system_prompt: str
    tool_names: List[str] = field(default_factory=list)
    max_turns: int = 8
    # Provider-specific reasoning config
    reasoning_effort: Optional[str] = None   # OpenAI (e.g. "xhigh")
    anthropic_effort: Optional[str] = None   # Anthropic (e.g. "max")
    anthropic_thinking: bool = False
    # 1M context beta (Anthropic only, Opus 4.6 + Sonnet 4.5)
    extended_context: bool = False


# ── Subagent system prompts ────────────────────────────────────

_CODE_ANALYST_PROMPT = """\
You are a quantitative code analyst in the MindfulRL trading system.
Your job is to write and execute Python code for financial data analysis.

You handle two types of tasks:
1. Directed calculations: "Calculate 30-day Sharpe ratio for NVDA" — execute specific formulas
2. Autonomous analysis: "Find anomalies in this price data" — design the analytical \
approach yourself, choose appropriate statistical methods, and implement them

You can retrieve data with available tools (prices, fundamentals, web search for
methodology references) and then analyze it with execute_python_analysis.

Use execute_python_analysis with the `task` parameter for auto code generation,
or provide direct `code` for precise control.

Available packages: numpy, pandas, scipy, json, math, statistics, datetime.
Always print results clearly to stdout. Handle edge cases (NaN, missing data,
insufficient samples) gracefully.
"""

_DEEP_RESEARCHER_PROMPT = """\
You are a deep research analyst in the MindfulRL trading system.
Your job is to perform thorough, multi-tool investigation of a specific topic.

When given a research task:
1. Gather data from multiple sources (news, prices, fundamentals, options, signals)
2. Cross-reference findings for consistency
3. Identify contradictions and data gaps
4. Synthesize a comprehensive analysis with confidence assessment

Return structured, actionable findings — not surface-level summaries.
"""

_DATA_SUMMARIZER_PROMPT = """\
You are a data summarization specialist in the MindfulRL trading system.
Your job is to efficiently retrieve data and produce concise summaries.

Given a summarization task:
1. Retrieve the requested data using available tools
2. Extract key metrics and patterns
3. Return a concise, structured summary

Prioritize speed and conciseness. Focus on actionable insights.
"""

_REVIEWER_PROMPT = """\
You are a critical analysis reviewer in the MindfulRL trading system.
Your job is to find flaws, gaps, and risks in analysis conclusions.

You receive analysis conclusions and supporting data via context. Your task:
1. Identify logical jumps or unsupported inferences in the conclusions
2. Point out risk factors that were overlooked or underweighted
3. Question data sufficiency: sample size, time range, missing sources
4. Check for common analytical traps: value trap, recency bias,
   survivorship bias, confirmation bias
5. Suggest a confidence adjustment based on your findings

You may use web search to fact-check specific claims or find counter-evidence.

Return structured JSON:
{
  "issues": [{"description": "...", "severity": "high|medium|low"}],
  "confidence_adjustment": -0.15,  // float between -0.3 and +0.1
  "recommendation": "proceed|revise|reject",
  "reasoning": "Brief overall assessment"
}
"""

# ── Predefined subagent registry ───────────────────────────────

SUBAGENT_REGISTRY: Dict[str, SubagentConfig] = {
    "code_analyst": SubagentConfig(
        name="code_analyst",
        description=(
            "Quantitative Python analysis: directed calculations (Sharpe, "
            "correlations, regressions) and autonomous analysis design "
            "(anomaly detection, pattern recognition, custom models)."
        ),
        model="gpt-5.2-codex",
        system_prompt=_CODE_ANALYST_PROMPT,
        tool_names=[
            "execute_python_analysis",
            "get_ticker_prices",
            "get_price_change",
            "get_fundamentals_analysis",
            "tavily_search",
        ],
        max_turns=8,
        reasoning_effort="xhigh",
    ),
    "deep_researcher": SubagentConfig(
        name="deep_researcher",
        description=(
            "Performs thorough multi-source investigation: cross-referencing "
            "news sentiment, price action, fundamentals, IV/options data, "
            "and event signals to produce comprehensive analysis."
        ),
        model="gpt-5.2",
        system_prompt=_DEEP_RESEARCHER_PROMPT,
        tool_names=[
            "get_ticker_news",
            "get_news_sentiment_summary",
            "search_news_by_keyword",
            "get_ticker_prices",
            "get_price_change",
            "get_sector_performance",
            "get_iv_analysis",
            "detect_anomalies",
            "detect_event_chains",
            "synthesize_signal",
            "get_fundamentals_analysis",
            "get_sec_filings",
            "tavily_search",
            "web_browse",
        ],
        max_turns=10,
        reasoning_effort="xhigh",
    ),
    "data_summarizer": SubagentConfig(
        name="data_summarizer",
        description=(
            "Fast data retrieval and summarization: watchlist overviews, "
            "sector comparisons, multi-ticker screening, and news digests. "
            "Optimized for speed and conciseness."
        ),
        model="claude-sonnet-4-6",
        system_prompt=_DATA_SUMMARIZER_PROMPT,
        tool_names=[
            "get_ticker_news",
            "get_news_sentiment_summary",
            "get_price_change",
            "get_sector_performance",
            "get_watchlist_overview",
            "get_morning_brief",
            "get_fundamentals_analysis",
        ],
        max_turns=6,
        anthropic_thinking=True,  # adaptive — model decides when to think
    ),
    "reviewer": SubagentConfig(
        name="reviewer",
        description=(
            "Critical analysis reviewer: examines conclusions for logical "
            "flaws, overlooked risks, data gaps, and common analytical biases. "
            "Returns structured confidence adjustment."
        ),
        model="claude-opus-4-6",
        system_prompt=_REVIEWER_PROMPT,
        tool_names=[
            "tavily_search",
            "get_ticker_news",
        ],
        max_turns=4,
        anthropic_thinking=True,
        anthropic_effort="max",
    ),
}

# Maximum context_json chars to pass to subagent (prevent context explosion)
_MAX_CONTEXT_CHARS = 5000


# ── Model override ─────────────────────────────────────────────

def _apply_config_overrides(config: SubagentConfig) -> SubagentConfig:
    """Apply model and max_turns overrides from AgentConfig if present.

    Returns a copy with overrides applied (original registry unchanged).
    """
    from ..config import get_agent_config
    agent_config = get_agent_config()

    override_model = agent_config.subagent_models.get(config.name)
    override_turns = agent_config.subagent_max_turns.get(config.name)

    # Check if any override actually changes a value
    model_changed = override_model and override_model != config.model
    turns_changed = override_turns and override_turns != config.max_turns

    if not model_changed and not turns_changed:
        return config

    overridden = copy(config)
    if model_changed:
        overridden.model = override_model
        logger.info(
            f"Subagent '{config.name}' model overridden: "
            f"{config.model} → {override_model}"
        )
    if turns_changed:
        overridden.max_turns = override_turns
        logger.info(
            f"Subagent '{config.name}' max_turns overridden: "
            f"{config.max_turns} → {override_turns}"
        )
    return overridden


# ── Dispatch ───────────────────────────────────────────────────

def dispatch_subagent(
    subagent_name: str,
    task: str,
    context_json: str = "",
    dal: Any = None,
) -> Dict[str, Any]:
    """
    Dispatch a task to a specialized subagent.

    Runs a complete agent loop (clean state) using the subagent's configured
    model, system prompt, and tool subset.

    Args:
        subagent_name: Key in SUBAGENT_REGISTRY
        task: Natural language task description
        context_json: Optional JSON string with context data
        dal: DataAccessLayer instance

    Returns:
        Dict with: subagent, answer, tools_used, model, provider,
        token_usage, error
    """
    if subagent_name not in SUBAGENT_REGISTRY:
        available = ", ".join(sorted(SUBAGENT_REGISTRY.keys()))
        return {
            "subagent": subagent_name,
            "answer": "",
            "tools_used": [],
            "model": "",
            "provider": "",
            "token_usage": {},
            "error": f"Unknown subagent: {subagent_name}. Available: {available}",
        }

    config = SUBAGENT_REGISTRY[subagent_name]

    # Apply model override from AgentConfig (user_profile.yaml or CLI runtime)
    config = _apply_config_overrides(config)

    provider = _detect_provider(config.model)

    # Build subagent input
    subagent_input = f"Task: {task}"
    if context_json:
        preview = context_json[:_MAX_CONTEXT_CHARS]
        if len(context_json) > _MAX_CONTEXT_CHARS:
            preview += f"\n... [{len(context_json) - _MAX_CONTEXT_CHARS} chars truncated]"
        subagent_input += f"\n\nContext data:\n{preview}"

    logger.info(
        f"Dispatching to subagent '{subagent_name}' "
        f"(model={config.model}, provider={provider}, max_turns={config.max_turns})"
    )

    try:
        if provider == "openai":
            result = _run_openai_subagent(config, subagent_input, dal)
        else:
            result = _run_anthropic_subagent(config, subagent_input, dal)

        return {
            "subagent": subagent_name,
            "answer": result.get("answer", ""),
            "tools_used": result.get("tools_used", []),
            "model": config.model,
            "provider": provider,
            "token_usage": result.get("token_usage", {}),
            "error": None,
        }
    except Exception as e:
        logger.error(f"Subagent '{subagent_name}' failed: {e}", exc_info=True)
        return {
            "subagent": subagent_name,
            "answer": "",
            "tools_used": [],
            "model": config.model,
            "provider": provider,
            "token_usage": {},
            "error": str(e),
        }


# ── Anthropic subagent runner ──────────────────────────────────

def _run_anthropic_subagent(
    config: SubagentConfig,
    question: str,
    dal: Any,
) -> Dict[str, Any]:
    """Run a subagent using the Anthropic SDK (simplified messages loop)."""
    from anthropic import Anthropic

    from ..anthropic_agent.agent import (
        _build_thinking_param,
        _prepare_cached_system,
        _prepare_cached_tools,
        _supports_effort,
    )
    from ..anthropic_agent.tools import execute_tool, get_anthropic_tools
    from ..config import get_agent_config
    from ..shared.token_tracker import TokenTracker

    agent_config = get_agent_config()
    client = Anthropic()

    # Filter tools to subagent's allowed subset
    all_tools = get_anthropic_tools()
    tools = _filter_anthropic_tools(all_tools, config.tool_names)

    # Conditionally add Claude web search server tool (Phase 10)
    if agent_config.web_claude_search:
        from ..anthropic_agent.agent import _CLAUDE_WEB_SEARCH_TOOL
        tools.append({
            **_CLAUDE_WEB_SEARCH_TOOL,
            "max_uses": agent_config.web_claude_max_uses,
        })

    # Apply prompt caching: cache_control on tools (last) + system prompt
    tools = _prepare_cached_tools(tools)
    cached_system = _prepare_cached_system(config.system_prompt)

    messages: List[dict] = [{"role": "user", "content": question}]
    tools_used: List[str] = []
    tracker = TokenTracker()

    # Build API kwargs (effort + thinking)
    api_kwargs: Dict[str, Any] = {}

    if config.anthropic_effort and _supports_effort(config.model):
        api_kwargs["output_config"] = {"effort": config.anthropic_effort}

    thinking_param, effective_max_tokens = _build_thinking_param(
        config.model, config.anthropic_thinking, agent_config,
    )
    if thinking_param:
        api_kwargs["thinking"] = thinking_param

    # Determine stream function (standard vs 1M beta)
    use_beta = _use_extended_context(config.model, config.extended_context)

    for turn in range(config.max_turns):
        if use_beta:
            stream_ctx = client.beta.messages.stream(
                model=config.model,
                max_tokens=effective_max_tokens,
                system=cached_system,
                tools=tools,
                messages=messages,
                betas=[_EXTENDED_CONTEXT_BETA],
                **api_kwargs,
            )
        else:
            stream_ctx = client.messages.stream(
                model=config.model,
                max_tokens=effective_max_tokens,
                system=cached_system,
                tools=tools,
                messages=messages,
                **api_kwargs,
            )

        with stream_ctx as stream:
            response = stream.get_final_message()

        tracker.record_anthropic(response, model=config.model)

        # Handle pause_turn (Claude web search server tool mid-turn pause)
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        if response.stop_reason != "tool_use":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            return {
                "answer": final_text,
                "tools_used": list(set(tools_used)),
                "token_usage": tracker.summary(),
            }

        # Process tool calls
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_results = []
        for tool_use in tool_use_blocks:
            tools_used.append(tool_use.name)
            logger.debug(f"Subagent tool call: {tool_use.name}")
            result = execute_tool(tool_use.name, tool_use.input, dal)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": "Subagent reached maximum tool calls.",
        "tools_used": list(set(tools_used)),
        "token_usage": tracker.summary(),
    }


# ── OpenAI subagent runner ─────────────────────────────────────

def _run_openai_subagent(
    config: SubagentConfig,
    question: str,
    dal: Any,
) -> Dict[str, Any]:
    """Run a subagent using the OpenAI Agents SDK (Runner.run_sync)."""
    from agents import Agent, ModelSettings, Runner
    from openai.types.shared import Reasoning

    from ..config import get_agent_config
    from ..openai_agent.agent import _get_openai_max_output
    from ..openai_agent.tools import create_openai_tools
    from ..shared.token_tracker import TokenTracker

    agent_config = get_agent_config()

    # Create and filter tools
    all_tools = create_openai_tools(dal)
    tools = _filter_openai_tools(all_tools, config.tool_names)

    # Build reasoning settings
    effort = config.reasoning_effort or agent_config.reasoning_effort
    if effort == "none":
        effective_max_tokens = agent_config.max_tokens
    else:
        effective_max_tokens = _get_openai_max_output(config.model)

    agent = Agent(
        name=f"MindfulRL Subagent: {config.name}",
        instructions=config.system_prompt,
        model=config.model,
        tools=tools,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=effort),
            max_tokens=effective_max_tokens,
        ),
    )

    result = Runner.run_sync(
        agent,
        input=question,
        max_turns=config.max_turns,
        auto_previous_response_id=True,
    )

    # Extract tools used and token usage
    tracker = TokenTracker()
    tools_used: List[str] = []
    if hasattr(result, "raw_responses"):
        tracker.record_openai_result(result, model=config.model)
        for response in result.raw_responses:
            if hasattr(response, "output"):
                for item in response.output:
                    if hasattr(item, "name"):
                        tools_used.append(item.name)

    answer = str(result.final_output) if result.final_output else ""
    return {
        "answer": answer,
        "tools_used": list(set(tools_used)),
        "token_usage": tracker.summary(),
    }