"""
Shared utilities for agent implementations.

Contains:
- prompts.py: System prompts shared across providers
- token_tracker.py: Per-turn and cumulative token usage tracking
- scratchpad.py: JSONL-based decision logging for agent sessions
- context_manager.py: Smart context compaction for long sessions
"""

from .context_manager import ContextManager
from .prompts import SYSTEM_PROMPT
from .scratchpad import Scratchpad
from .token_tracker import TokenTracker, TurnUsage

__all__ = ["ContextManager", "SYSTEM_PROMPT", "Scratchpad", "TokenTracker", "TurnUsage"]