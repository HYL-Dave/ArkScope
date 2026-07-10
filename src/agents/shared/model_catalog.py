"""
Shared model catalog — CLI/discord view over the capability registry.

Used by both CLI (src/agents/cli.py) and Discord bot (src/monitor/discord_bot.py).
P2.7 convergence: model FACTS live in src/model_capabilities.py; this module
keeps only the CLI presentation layer (menu membership via `in_cli_catalog`,
nicknames, display copy) plus the effort helpers the CLI already imports.
CLI nicknames stay HERE by design — runtime helpers resolve through the
registry, which must never alias-match a bare "claude"/"opus"/"mini".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from src.model_capabilities import all_models, capability_for


@dataclass
class ModelEntry:
    """A model available for selection."""
    id: str
    provider: str  # "anthropic" or "openai"
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""


# CLI presentation (nicknames + menu copy) keyed by registry id. Membership in
# the menu itself comes from the registry's `in_cli_catalog` flag.
_CLI_PRESENTATION: dict[str, tuple[str, list, str]] = {
    "claude-opus-4-7": (
        "Opus 4.7",
        ["opus", "opus4.7", "opus-4.7", "o47", "claude-opus"],
        "Most intelligent — deep analysis & reasoning (128K output, $5/$25)",
    ),
    "claude-sonnet-4-6": (
        "Sonnet 4.6",
        ["sonnet", "sonnet4.6", "sonnet-4.6", "s46", "claude-sonnet", "claude"],
        "Fast + intelligent — financial analysis ($3/$15)",
    ),
    "gpt-5.5": (
        "GPT-5.5",
        ["gpt5", "gpt-5", "gpt5.5", "5.5"],
        "SOTA reasoning with configurable effort (default)",
    ),
    "gpt-5.4-mini": (
        "GPT-5.4 Mini",
        ["gpt5-mini", "gpt-5-mini", "5.4-mini", "mini"],
        "Fast + cost-efficient reasoning",
    ),
    "gpt-5.4-nano": (
        "GPT-5.4 Nano",
        ["gpt5-nano", "gpt-5-nano", "5.4-nano", "nano"],
        "Fastest, cheapest — simple tasks",
    ),
    "gpt-5.4": (
        "GPT-5.4 (legacy)",
        ["gpt5.4", "5.4"],
        "Legacy — fallback if gpt-5.5 unavailable",
    ),
    "gpt-5.2": (
        "GPT-5.2 (legacy)",
        ["gpt5.2", "5.2"],
        "Legacy — consider upgrading to gpt-5.5",
    ),
    "gpt-5.2-codex": (
        "GPT-5.2 Codex (legacy)",
        ["codex", "codex5.2", "5.2-codex"],
        "Legacy — codex removed in 5.4 family, use gpt-5.4 instead",
    ),
}


def _build_cli_catalog() -> List[ModelEntry]:
    entries: List[ModelEntry] = []
    for cap in all_models():
        if not cap.in_cli_catalog:
            continue
        name, aliases, description = _CLI_PRESENTATION.get(
            cap.id, (cap.label, [], cap.notes)
        )
        entries.append(ModelEntry(
            id=cap.id,
            provider=cap.provider,
            name=name,
            aliases=list(aliases),
            description=description,
        ))
    return entries


# Derived CLI view — membership pinned by tests against the registry flags.
MODEL_CATALOG: List[ModelEntry] = _build_cli_catalog()

# Effort level constants (wire vocabularies; unchanged)
VALID_ANTHROPIC_EFFORT = ("max", "xhigh", "high", "medium", "low")
VALID_REASONING_EFFORT = ("none", "minimal", "low", "medium", "high", "xhigh")

# Per-model Anthropic effort options — registry-derived (cli.py iterates
# .items() with prefix matching; the derived dict keeps that contract).
EFFORT_OPTIONS_BY_MODEL = {
    c.id: tuple(c.effort_options)
    for c in all_models("anthropic")
    if c.effort_options
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
    """Return valid effort options for the given model, or None if unsupported.

    Anthropic-only contract preserved: OpenAI ids and unknown models return
    None (OpenAI reasoning effort is validated elsewhere).
    """
    cap = capability_for(model)
    if cap is None or cap.provider != "anthropic" or not cap.effort_options:
        return None
    return tuple(cap.effort_options)
