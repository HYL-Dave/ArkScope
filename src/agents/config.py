"""
Agent configuration with model selection.

Models can be configured via:
1. Default values in AgentConfig
2. config/user_profile.yaml under llm_preferences
3. Runtime override via model parameter in queries
4. CLI flags (--model, --reasoning)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel

# Valid reasoning effort levels for GPT-5.x / o-series
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


class AgentConfig(BaseModel):
    """Agent model and behavior configuration."""

    # OpenAI models
    openai_model: str = "gpt-5.2"
    openai_model_advanced: str = "gpt-5.2"

    # Anthropic models
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    anthropic_model_advanced: str = "claude-opus-4-6"

    # Reasoning (GPT-5.x / o-series)
    reasoning_effort: ReasoningEffort = "xhigh"

    # Anthropic effort (Opus 4.5+, no beta header needed)
    # None = don't send (server default "high")
    anthropic_effort: Optional[str] = None

    # Anthropic extended thinking (Phase 8)
    # 開啟後根據模型自動選擇模式：
    #   Opus 4.6: adaptive (Claude 自動判斷思考深度，不需 budget)
    #   其他模型: enabled + budget_tokens (自動推導)
    # max_tokens 和 budget_tokens 全自動：
    #   effective_max_tokens = 模型最大 output (128K/64K)
    #   budget_tokens = effective_max_tokens - config.max_tokens (留 max_tokens 給 response)
    # 這樣不需手動配置，且效果最好
    anthropic_thinking: bool = False

    # Limits
    max_tool_calls: int = 20
    max_tokens: int = 16384

    # Context management (Phase 3)
    # Compact old tool results when input_tokens > model_context_limit * ratio
    context_threshold_ratio: float = 0.7
    # Number of recent turns to always preserve fully (each turn = assistant + tool_result)
    context_keep_recent_turns: int = 2
    # Characters to keep as preview in compacted results
    context_preview_chars: int = 200

    # Behavior
    temperature: float = 0.0  # Deterministic for tool calling


def _load_user_profile() -> dict:
    """Load user_profile.yaml if exists."""
    paths = [
        Path("config/user_profile.local.yaml"),
        Path("config/user_profile.yaml"),
    ]
    for p in paths:
        if p.exists():
            with open(p) as f:
                return yaml.safe_load(f) or {}
    return {}


@lru_cache(maxsize=1)
def get_agent_config() -> AgentConfig:
    """
    Get agent configuration, merging defaults with user_profile.yaml.

    user_profile.yaml can override under llm_preferences:
        agent_model: "gpt-5.2"
        agent_model_advanced: "gpt-5.2"
        anthropic_model: "claude-sonnet-4-5-20250929"
        anthropic_model_advanced: "claude-opus-4-6"
        reasoning_effort: "xhigh"
        max_tool_calls: 20
        max_tokens: 16384
        anthropic_effort: "high"
        anthropic_thinking: false
    """
    config = AgentConfig()

    profile = _load_user_profile()
    llm_prefs = profile.get("llm_preferences", {})

    # Override from profile
    if "agent_model" in llm_prefs:
        config.openai_model = llm_prefs["agent_model"]
    if "agent_model_advanced" in llm_prefs:
        config.openai_model_advanced = llm_prefs["agent_model_advanced"]
    if "anthropic_model" in llm_prefs:
        config.anthropic_model = llm_prefs["anthropic_model"]
    if "anthropic_model_advanced" in llm_prefs:
        config.anthropic_model_advanced = llm_prefs["anthropic_model_advanced"]
    if "reasoning_effort" in llm_prefs:
        config.reasoning_effort = llm_prefs["reasoning_effort"]
    if "max_tool_calls" in llm_prefs:
        config.max_tool_calls = llm_prefs["max_tool_calls"]
    if "max_tokens" in llm_prefs:
        config.max_tokens = llm_prefs["max_tokens"]

    # Anthropic effort/thinking overrides
    if "anthropic_effort" in llm_prefs:
        config.anthropic_effort = llm_prefs["anthropic_effort"]
    if "anthropic_thinking" in llm_prefs:
        config.anthropic_thinking = llm_prefs["anthropic_thinking"]

    # Context management overrides
    ctx_prefs = profile.get("context_management", {})
    if "threshold_ratio" in ctx_prefs:
        config.context_threshold_ratio = ctx_prefs["threshold_ratio"]
    if "keep_recent_turns" in ctx_prefs:
        config.context_keep_recent_turns = ctx_prefs["keep_recent_turns"]
    if "preview_chars" in ctx_prefs:
        config.context_preview_chars = ctx_prefs["preview_chars"]

    return config