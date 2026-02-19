"""
Shared utilities for agent implementations.

Contains:
- prompts.py: System prompts shared across providers
- token_tracker.py: Per-turn and cumulative token usage tracking
- scratchpad.py: JSONL-based decision logging for agent sessions
- context_manager.py: Smart context compaction for long sessions
- events.py: Agent event types for streaming progress
"""

from .context_manager import ContextManager
from .events import AgentEvent, EventType
from .prompts import SYSTEM_PROMPT
from .scratchpad import ChatHistory, Scratchpad
from .skills import SKILL_REGISTRY, SkillDefinition, expand_skill, list_skills
from .subagent import SUBAGENT_REGISTRY, SubagentConfig, dispatch_subagent
from .token_tracker import TokenTracker, TurnUsage

__all__ = [
    "AgentEvent",
    "ChatHistory",
    "ContextManager",
    "EventType",
    "SKILL_REGISTRY",
    "SkillDefinition",
    "SUBAGENT_REGISTRY",
    "SYSTEM_PROMPT",
    "Scratchpad",
    "SubagentConfig",
    "TokenTracker",
    "TurnUsage",
    "dispatch_subagent",
    "expand_skill",
    "list_skills",
]