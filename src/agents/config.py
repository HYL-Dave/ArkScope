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
    anthropic_model: str = "claude-opus-4-6"
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
    max_tool_calls: int = 60
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
    # Code generation backend: api | codex | codex-apikey | claude | claude-apikey
    code_backend: str = "api"

    # 1M extended context beta (Anthropic only, Opus 4.6 + Sonnet 4.5)
    extended_context: bool = False

    # Subagent model overrides (Phase 6)
    # Keys: subagent names (code_analyst, deep_researcher, data_summarizer, reviewer)
    # Values: model IDs to override the default
    subagent_models: Dict[str, str] = {}
    # Subagent max_turns overrides
    # Keys: subagent names, Values: max tool call turns
    subagent_max_turns: Dict[str, int] = {}

    # Server-side compaction L2 (Phase 7a)
    # Anthropic: beta compact-2026-01-12, Opus 4.6 + Sonnet 4.6, context_management param
    # OpenAI: CompactionSession for within-run context compaction
    # Both work on top of L1 client-side compaction (ContextManager)
    server_compaction: bool = False

    # Data freshness in system prompt (default: off, preserves prompt cache hit rate)
    freshness_in_prompt: bool = False

    # RL Pipeline integration (Phase 1c)
    # When enabled, rl_model_status / rl_prediction / rl_backtest_report tools
    # return real model data. When disabled, they return informational messages.
    rl_pipeline_enabled: bool = False
    rl_models_dir: str = "trained_models"

    # Web search providers (Phase 10)
    # Each can be independently enabled/disabled for cost control
    web_tavily: bool = True           # Tavily search + fetch (free 1000 credits/month)
    web_claude_search: bool = False   # Claude server-side web search ($10/1K, off by default)
    web_openai_search: bool = True    # OpenAI SDK WebSearchTool (included in API cost)
    web_playwright: bool = True       # Playwright headless browser (free, local)
    web_codex_research: bool = True   # Codex CLI deep research (--search, uses API key)
    web_claude_max_uses: int = 5      # Max web searches per conversation (Claude only)

    # Seeking Alpha Alpha Picks (Phase 11c)
    sa_enabled: bool = False
    sa_cache_hours: int = 24
    sa_detail_cache_days: int = 7
    sa_comments_cache_days: int = 7


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
        anthropic_model: "claude-opus-4-6"
        anthropic_model_advanced: "claude-opus-4-6"
        reasoning_effort: "xhigh"
        max_tool_calls: 60
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

    # Freshness in prompt
    if "freshness_in_prompt" in llm_prefs:
        config.freshness_in_prompt = llm_prefs["freshness_in_prompt"]

    # RL Pipeline
    rl_prefs = profile.get("rl_pipeline", {})
    if "enabled" in rl_prefs:
        config.rl_pipeline_enabled = rl_prefs["enabled"]
    if "models_dir" in rl_prefs:
        config.rl_models_dir = rl_prefs["models_dir"]

    # Code generation overrides
    if "code_model" in llm_prefs:
        config.code_model = llm_prefs["code_model"]
    if "code_max_retries" in llm_prefs:
        config.code_max_retries = llm_prefs["code_max_retries"]
    if "code_backend" in llm_prefs:
        config.code_backend = llm_prefs["code_backend"]

    # 1M extended context beta
    if "extended_context" in llm_prefs:
        config.extended_context = llm_prefs["extended_context"]

    # Subagent model overrides
    if "subagent_models" in llm_prefs:
        config.subagent_models = llm_prefs["subagent_models"]
    if "subagent_max_turns" in llm_prefs:
        config.subagent_max_turns = llm_prefs["subagent_max_turns"]

    # Web search overrides (Phase 10)
    web_prefs = profile.get("web_search", {})
    if "tavily" in web_prefs:
        config.web_tavily = web_prefs["tavily"]
    if "claude_search" in web_prefs:
        config.web_claude_search = web_prefs["claude_search"]
    if "claude_search_max_uses" in web_prefs:
        config.web_claude_max_uses = web_prefs["claude_search_max_uses"]
    if "openai_search" in web_prefs:
        config.web_openai_search = web_prefs["openai_search"]
    if "playwright" in web_prefs:
        config.web_playwright = web_prefs["playwright"]
    if "codex_research" in web_prefs:
        config.web_codex_research = web_prefs["codex_research"]

    # Server-side compaction (Phase 7a)
    if "server_compaction" in llm_prefs:
        config.server_compaction = llm_prefs["server_compaction"]

    # Seeking Alpha overrides (Phase 11c)
    sa_prefs = profile.get("seeking_alpha", {})
    if "enabled" in sa_prefs:
        config.sa_enabled = sa_prefs["enabled"]
    if "comments_cache_days" in sa_prefs:
        config.sa_comments_cache_days = sa_prefs["comments_cache_days"]
    if "cache_hours" in sa_prefs:
        config.sa_cache_hours = sa_prefs["cache_hours"]
    if "detail_cache_days" in sa_prefs:
        config.sa_detail_cache_days = sa_prefs["detail_cache_days"]

    # Context management overrides
    ctx_prefs = profile.get("context_management", {})
    if "threshold_ratio" in ctx_prefs:
        config.context_threshold_ratio = ctx_prefs["threshold_ratio"]
    if "keep_recent_turns" in ctx_prefs:
        config.context_keep_recent_turns = ctx_prefs["keep_recent_turns"]
    if "preview_chars" in ctx_prefs:
        config.context_preview_chars = ctx_prefs["preview_chars"]

    return config