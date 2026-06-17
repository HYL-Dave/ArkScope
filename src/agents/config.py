"""
Agent configuration with model selection.

Models can be configured via:
1. Default values in AgentConfig
2. config/user_profile.yaml under llm_preferences
3. Runtime override via model parameter in queries
4. CLI flags (--model, --reasoning)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Literal, Optional

import yaml
from pydantic import BaseModel

from src.env_keys import ensure_env_loaded
from src.model_routing import (
    Provider,
    TaskId,
    TaskRoute,
    default_model_for,
    is_valid_effort,
    is_seed_model,
    model_provider,
)

# Valid reasoning effort levels for GPT-5.x / o-series
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


class AgentConfig(BaseModel):
    """Agent model and behavior configuration."""

    # OpenAI models — default tier = everyday/cheaper, advanced = frontier
    openai_model: str = "gpt-5.4"
    openai_model_advanced: str = "gpt-5.5"

    # Anthropic models — default tier = everyday/cheaper, advanced = frontier
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_model_advanced: str = "claude-opus-4-8"

    # Per-task model routing (minimal; full Settings UI later). Empty string =
    # derive from the defaults in task_model(). Env (ARKSCOPE_CARD_*_MODEL) wins.
    card_synthesis_provider: str = ""  # "" → anthropic unless model infers otherwise
    card_synthesis_model: str = ""    # "" → anthropic_model_advanced (Opus-class)
    card_synthesis_effort: str = ""   # "" → provider default
    card_translation_provider: str = ""  # "" → anthropic unless model infers otherwise
    card_translation_model: str = ""  # "" → a fast model (Sonnet)
    card_translation_effort: str = ""  # "" → provider default

    # Reasoning (GPT-5.x / o-series)
    reasoning_effort: ReasoningEffort = "xhigh"

    # Anthropic effort (Opus 4.5+, no beta header needed)
    # None = don't send (server default "high")
    anthropic_effort: Optional[str] = None

    # Anthropic extended thinking (Phase 8)
    # 開啟後根據模型自動選擇模式：
    #   Opus 4.7: adaptive (Claude 自動判斷思考深度，不需 budget)
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

    # 1M extended context beta (Anthropic only, Opus 4.7 + Sonnet 4.5)
    extended_context: bool = False

    # Subagent model overrides (Phase 6)
    # Keys: subagent names (code_analyst, deep_researcher, data_summarizer, reviewer)
    # Values: model IDs to override the default
    subagent_models: Dict[str, str] = {}
    # Subagent max_turns overrides
    # Keys: subagent names, Values: max tool call turns
    subagent_max_turns: Dict[str, int] = {}

    # Server-side compaction L2 (Phase 7a)
    # Anthropic: beta compact-2026-01-12, Opus 4.7 + Sonnet 4.6, context_management param
    # OpenAI: CompactionSession for within-run context compaction
    # Both work on top of L1 client-side compaction (ContextManager)
    server_compaction: bool = False

    # Data freshness in system prompt (default: off, preserves prompt cache hit rate)
    freshness_in_prompt: bool = False

    # Web search providers (Phase 10)
    # Each can be independently enabled/disabled for cost control
    web_tavily: bool = True           # Tavily search + fetch (free 1000 credits/month)
    web_claude_search: bool = False   # Claude server-side web search ($10/1K, off by default)
    web_openai_search: bool = True    # OpenAI SDK WebSearchTool (included in API cost)
    web_playwright: bool = True       # Playwright headless browser (free, local)
    web_claude_max_uses: int = 5      # Max web searches per conversation (Claude only)

    # Seeking Alpha Alpha Picks (Phase 11c)
    sa_enabled: bool = False
    sa_cache_hours: int = 24
    sa_detail_cache_days: int = 7
    sa_comments_cache_days: int = 7
    sa_comments_backfill_per_full_scan: int = 10
    sa_comments_backfill_per_backfill_scan: int = 50

    # Phase D analysis pipeline scaffold
    analysis_pipeline_enabled: bool = False

    # Free macro/calendar layer (FRED + Finnhub calendars).
    # Gates registration of fetch_fred_series / fetch_fred_release_dates jobs
    # so an environment without FRED_API_KEY doesn't get them surfaced via
    # /jobs/status. Calendar tables in sql/013 always exist; the flag only
    # controls the ingestion jobs.
    macro_calendar_enabled: bool = False

    # P1.4 Phase B client-side compaction (separate from server_compaction).
    # When False (default), the legacy ContextManager path runs unchanged.
    # When True, ContextManager delegates Layers 0-3 to ContextCompressor.
    # Loaded from a top-level compaction: section in user_profile.yaml.
    compaction_enabled: bool = False
    compaction_layer_0_budget_chars: int = 8000
    compaction_layer_2_threshold_chars: int = 100_000
    compaction_layer_3_threshold_chars: int = 150_000
    compaction_overflow_dir: str = "data/overflow"
    # Layer 5 (LLM full compact, commit 5). Default OFF — explicit opt-in.
    # /compact CLI command bypasses this flag and the threshold but still
    # honours compaction_enabled, summary_caller availability, and the
    # circuit breaker.
    compaction_layer_5_enabled: bool = False
    compaction_layer_5_threshold_chars: int = 250_000
    compaction_layer_5_model_anthropic: str = "claude-sonnet-4-6"


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
        agent_model: "gpt-5.5"
        agent_model_advanced: "gpt-5.5"
        anthropic_model: "claude-opus-4-7"
        anthropic_model_advanced: "claude-opus-4-7"
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
    if "card_synthesis_provider" in llm_prefs:
        config.card_synthesis_provider = llm_prefs["card_synthesis_provider"]
    if "card_synthesis_model" in llm_prefs:
        config.card_synthesis_model = llm_prefs["card_synthesis_model"]
    if "card_synthesis_effort" in llm_prefs:
        config.card_synthesis_effort = llm_prefs["card_synthesis_effort"]
    if "card_translation_provider" in llm_prefs:
        config.card_translation_provider = llm_prefs["card_translation_provider"]
    if "card_translation_model" in llm_prefs:
        config.card_translation_model = llm_prefs["card_translation_model"]
    if "card_translation_effort" in llm_prefs:
        config.card_translation_effort = llm_prefs["card_translation_effort"]
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

    # Server-side compaction (Phase 7a)
    if "server_compaction" in llm_prefs:
        config.server_compaction = llm_prefs["server_compaction"]

    # Seeking Alpha overrides (Phase 11c)
    sa_prefs = profile.get("seeking_alpha", {})
    if "enabled" in sa_prefs:
        config.sa_enabled = sa_prefs["enabled"]
    if "comments_cache_days" in sa_prefs:
        config.sa_comments_cache_days = sa_prefs["comments_cache_days"]
    if "comments_backfill_per_full_scan" in sa_prefs:
        config.sa_comments_backfill_per_full_scan = sa_prefs["comments_backfill_per_full_scan"]
    if "comments_backfill_per_backfill_scan" in sa_prefs:
        config.sa_comments_backfill_per_backfill_scan = sa_prefs["comments_backfill_per_backfill_scan"]
    if "cache_hours" in sa_prefs:
        config.sa_cache_hours = sa_prefs["cache_hours"]
    if "detail_cache_days" in sa_prefs:
        config.sa_detail_cache_days = sa_prefs["detail_cache_days"]

    # Phase D analysis pipeline
    analysis_prefs = profile.get("analysis_pipeline", {})
    if "enabled" in analysis_prefs:
        config.analysis_pipeline_enabled = analysis_prefs["enabled"]

    # Free macro/calendar layer
    mc_prefs = profile.get("macro_calendar", {})
    if "enabled" in mc_prefs:
        config.macro_calendar_enabled = mc_prefs["enabled"]

    # Context management overrides
    ctx_prefs = profile.get("context_management", {})
    if "threshold_ratio" in ctx_prefs:
        config.context_threshold_ratio = ctx_prefs["threshold_ratio"]
    if "keep_recent_turns" in ctx_prefs:
        config.context_keep_recent_turns = ctx_prefs["keep_recent_turns"]
    if "preview_chars" in ctx_prefs:
        config.context_preview_chars = ctx_prefs["preview_chars"]

    # P1.4 client-side compaction overrides (top-level "compaction:" section)
    compaction_prefs = profile.get("compaction", {})
    if "enabled" in compaction_prefs:
        config.compaction_enabled = compaction_prefs["enabled"]
    if "layer_0_budget_chars" in compaction_prefs:
        config.compaction_layer_0_budget_chars = compaction_prefs["layer_0_budget_chars"]
    if "layer_2_threshold_chars" in compaction_prefs:
        config.compaction_layer_2_threshold_chars = compaction_prefs["layer_2_threshold_chars"]
    if "layer_3_threshold_chars" in compaction_prefs:
        config.compaction_layer_3_threshold_chars = compaction_prefs["layer_3_threshold_chars"]
    if "overflow_dir" in compaction_prefs:
        config.compaction_overflow_dir = compaction_prefs["overflow_dir"]
    # Layer 5 opt-in (commit 5)
    if "layer_5_enabled" in compaction_prefs:
        config.compaction_layer_5_enabled = compaction_prefs["layer_5_enabled"]
    if "layer_5_threshold_chars" in compaction_prefs:
        config.compaction_layer_5_threshold_chars = compaction_prefs["layer_5_threshold_chars"]
    if "layer_5_model_anthropic" in compaction_prefs:
        config.compaction_layer_5_model_anthropic = compaction_prefs["layer_5_model_anthropic"]

    return config


# Per-task model routing. Resolution: env override → user_profile → built-in
# default. Lets card synthesis stay Opus-class while translation (and future
# chat/deep-research) route to cheaper/faster models, without a full Settings UI.
_DEFAULT_TRANSLATION_MODEL = "claude-sonnet-4-6"
_TASK_ENV = {
    "card_synthesis": (
        "ARKSCOPE_CARD_SYNTHESIS_PROVIDER",
        "ARKSCOPE_CARD_SYNTHESIS_MODEL",
        "ARKSCOPE_CARD_SYNTHESIS_EFFORT",
    ),
    "card_translation": (
        "ARKSCOPE_CARD_TRANSLATION_PROVIDER",
        "ARKSCOPE_CARD_TRANSLATION_MODEL",
        "ARKSCOPE_CARD_TRANSLATION_EFFORT",
    ),
}


def _clean_provider(value: str | None) -> Provider | None:
    if value in ("anthropic", "openai"):
        return value
    return None


def _configured_task_values(config: AgentConfig, task: TaskId) -> tuple[str, str, str]:
    if task == "card_synthesis":
        return (
            config.card_synthesis_provider,
            config.card_synthesis_model,
            config.card_synthesis_effort,
        )
    if task == "card_translation":
        return (
            config.card_translation_provider,
            config.card_translation_model,
            config.card_translation_effort,
        )
    raise ValueError(f"unknown task: {task}")


def task_route(task: TaskId) -> TaskRoute:
    """Resolve provider + model for a per-task LLM operation.

    Resolution is env override → user_profile.local/user_profile → built-in
    default. If only a model is provided, known model prefixes infer provider
    (``claude-*`` → Anthropic, ``gpt-*``/``o*`` → OpenAI).
    """
    ensure_env_loaded()
    config = get_agent_config()
    profile_provider, profile_model, profile_effort = _configured_task_values(config, task)
    env_provider_key, env_model_key, env_effort_key = _TASK_ENV[task]
    env_provider = _clean_provider(os.environ.get(env_provider_key))
    env_model = (os.environ.get(env_model_key) or "").strip()
    env_effort = (os.environ.get(env_effort_key) or "").strip()

    provider = env_provider or _clean_provider(profile_provider)
    model = env_model or profile_model.strip()
    effort = env_effort or profile_effort.strip() or "default"
    source = (
        "env"
        if env_provider or env_model or env_effort
        else "profile"
        if provider or model or profile_effort
        else "default"
    )

    if not provider and model:
        provider = model_provider(model)
    if not provider:
        provider = "anthropic"

    if not model:
        if task == "card_synthesis" and provider == "anthropic":
            model = config.anthropic_model_advanced
        elif task == "card_synthesis" and provider == "openai":
            model = config.openai_model_advanced
        elif task == "card_translation" and provider == "anthropic":
            model = _DEFAULT_TRANSLATION_MODEL
        else:
            model = default_model_for(provider, task)

    warning = None
    if not is_valid_effort(provider, effort):
        warning = (
            f"Configured effort '{effort}' is not known for provider '{provider}'; "
            "using provider default."
        )
        effort = "default"

    return TaskRoute(
        task=task,
        provider=provider,
        model=model,
        effort=effort,
        source=source,
        custom=not is_seed_model(provider, model),
        warning=warning,
    )


def task_model(task: TaskId) -> str:
    """Resolve the model id for a per-task LLM operation."""
    return task_route(task).model


def task_provider(task: TaskId) -> Provider:
    """Resolve the provider for a per-task LLM operation."""
    return task_route(task).provider
