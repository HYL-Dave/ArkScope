"""
Shared model catalog — canonical model list, matching, and effort constants.

Used by both CLI (src/agents/cli.py) and Discord bot (src/monitor/discord_bot.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModelEntry:
    """A model available for selection."""
    id: str
    provider: str  # "anthropic" or "openai"
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""


# Canonical model list — update here when new models are available
MODEL_CATALOG: List[ModelEntry] = [
    ModelEntry(
        id="claude-opus-4-6",
        provider="anthropic",
        name="Opus 4.6",
        aliases=["opus", "opus4.6", "opus-4.6", "o46", "claude-opus"],
        description="Most intelligent — deep analysis & reasoning (128K output, $5/$25)",
    ),
    ModelEntry(
        id="claude-sonnet-4-6",
        provider="anthropic",
        name="Sonnet 4.6",
        aliases=["sonnet", "sonnet4.6", "sonnet-4.6", "s46", "claude-sonnet", "claude"],
        description="Fast + intelligent — financial analysis (64K output, $3/$15)",
    ),
    ModelEntry(
        id="gpt-5.2",
        provider="openai",
        name="GPT-5.2",
        aliases=["gpt5", "gpt-5", "gpt5.2", "5.2"],
        description="SOTA reasoning with configurable effort",
    ),
    # Codex series — optimized for agentic coding
    ModelEntry(
        id="gpt-5.2-codex",
        provider="openai",
        name="GPT-5.2 Codex",
        aliases=["codex", "codex5.2", "5.2-codex"],
        description="Agentic coding — long-horizon, refactors, migrations",
    ),
    # gpt-5.3-codex: API not yet available (Codex CLI only), add when released
]

# Effort level constants
VALID_ANTHROPIC_EFFORT = ("max", "high", "medium", "low")
VALID_REASONING_EFFORT = ("none", "minimal", "low", "medium", "high", "xhigh")

# Per-model Anthropic effort options (prefix match)
EFFORT_OPTIONS_BY_MODEL = {
    "claude-opus-4-6": ("max", "high", "medium", "low"),
    "claude-sonnet-4-6": ("high", "medium", "low"),
}


def find_model(query: str) -> Optional[ModelEntry]:
    """Find a model by ID, name, or alias (case-insensitive)."""
    q = query.lower().strip()
    for m in MODEL_CATALOG:
        if q == m.id.lower() or q == m.name.lower():
            return m
        if q in [a.lower() for a in m.aliases]:
            return m
    # Partial match on id
    for m in MODEL_CATALOG:
        if q in m.id.lower():
            return m
    return None


def get_effort_options(model: str) -> Optional[tuple]:
    """Return valid effort options for the given model, or None if unsupported."""
    for prefix, options in EFFORT_OPTIONS_BY_MODEL.items():
        if model.startswith(prefix):
            return options
    return None
