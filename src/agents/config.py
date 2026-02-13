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
from typing import Dict, Literal, Optional

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

    # Code generation model (empty = auto, uses anthropic_model_advanced)
    code_model: str = ""
    code_max_retries: int = 3

    # 1M extended context beta (Anthropic only, Opus 4.6 + Sonnet 4.5)
    extended_context: bool = False

    # Subagent model overrides (Phase 6)
    # Keys: subagent names (code_analyst, deep_researcher, data_summarizer)
    # Values: model IDs to override the default
    subagent_models: Dict[str, str] = {}


_LOCAL_CONFIG_PATH = Path("config/user_profile.local.yaml")
_MAIN_CONFIG_PATH = Path("config/user_profile.yaml")


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base (override wins). Returns new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_user_profile() -> dict:
    """Load user_profile.yaml, then deep-merge user_profile.local.yaml on top."""
    base = {}
    if _MAIN_CONFIG_PATH.exists():
        with open(_MAIN_CONFIG_PATH) as f:
            base = yaml.safe_load(f) or {}

    if _LOCAL_CONFIG_PATH.exists():
        with open(_LOCAL_CONFIG_PATH) as f:
            local = yaml.safe_load(f) or {}
        base = _deep_merge(base, local)

    return base


def save_local_override(section: str, key: str, value) -> None:
    """Save a single setting to user_profile.local.yaml (persists across sessions).

    Args:
        section: Top-level YAML key (e.g. "llm_preferences")
        key: Setting key within section (e.g. "subagent_models")
        value: Setting value

    The local file is deep-merged on top of the main config, so only
    overridden settings need to be stored here.
    """
    local = {}
    if _LOCAL_CONFIG_PATH.exists():
        with open(_LOCAL_CONFIG_PATH) as f:
            local = yaml.safe_load(f) or {}

    if section not in local:
        local[section] = {}
    local[section][key] = value

    _LOCAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCAL_CONFIG_PATH, "w") as f:
        yaml.dump(local, f, default_flow_style=False, allow_unicode=True)

    # Clear cached config so next call picks up the change
    get_agent_config.cache_clear()


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

    # Code generation overrides
    if "code_model" in llm_prefs:
        config.code_model = llm_prefs["code_model"]
    if "code_max_retries" in llm_prefs:
        config.code_max_retries = llm_prefs["code_max_retries"]

    # 1M extended context beta
    if "extended_context" in llm_prefs:
        config.extended_context = llm_prefs["extended_context"]

    # Subagent model overrides
    if "subagent_models" in llm_prefs:
        config.subagent_models = llm_prefs["subagent_models"]

    # Context management overrides
    ctx_prefs = profile.get("context_management", {})
    if "threshold_ratio" in ctx_prefs:
        config.context_threshold_ratio = ctx_prefs["threshold_ratio"]
    if "keep_recent_turns" in ctx_prefs:
        config.context_keep_recent_turns = ctx_prefs["keep_recent_turns"]
    if "preview_chars" in ctx_prefs:
        config.context_preview_chars = ctx_prefs["preview_chars"]

    return config