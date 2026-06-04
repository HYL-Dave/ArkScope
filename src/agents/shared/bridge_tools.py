"""Bridge-only tool surface (LOAD-BEARING for replay validator commit 3).

Tools that each provider's bridge layer exposes to the model WITHOUT
registering them in the canonical ``ToolRegistry``. Today the only
such tool is ``delegate_to_subagent`` — both bridges build it manually
because subagent dispatch has no DAL implementation.

This module is the third source consulted by the replay validator's
unified resolver (see ``shared/replay.py`` validate path):

    1. ``ToolRegistry``                       → live canonical registry tools
    2. ``shared/server_tools.py``             → server:* hosted tools
    3. ``shared/bridge_tools.py`` (THIS FILE) → bridge-only tools

Spec authority: ``docs/design/P0_1_FULL_V1_SPEC.md`` §2.3 resolver
contract — pinning is REQUIRED-RESOLUTION through these three sources,
NEVER skip-lookup.

Each entry carries the FULL accepted parameter set + the REQUIRED subset
so the validator can detect bridge-tool argument drift (e.g. Phase C
renames ``task`` → ``prompt``). Schemas are mirrored from
``anthropic_agent/tools.py`` (input_schema) and
``openai_agent/tools.py`` (function signature defaults).

Forward safeguard: ``tests/test_replay.py`` reimports each bridge's
tool list, subtracts ``ToolRegistry.list_names()`` plus server-tool
kinds, asserts the residual NAME set equals this helper's. New
bridge-only tools added without updating this helper fail that test.
"""
from __future__ import annotations

from typing import Dict, Set


# Bridge tools by provider. The shape mirrors a minimised
# ``ToolDefinition``: ``parameters`` is the FULL accepted key set;
# ``required`` is the strict subset.
#
# Both providers must agree on the schema for a name that exists on
# both surfaces — Phase C must not let one provider's
# ``delegate_to_subagent`` accept different args than the other's.
# Keeping them as separate per-provider entries (rather than one
# shared dict) preserves the option of provider-specific bridge tools
# in future cycles without breaking the resolver contract.
_BRIDGE_TOOL_SPECS_BY_PROVIDER: Dict[str, Dict[str, Dict[str, Set[str]]]] = {
    "anthropic": {
        "delegate_to_subagent": {
            "parameters": {"subagent", "task", "context_json"},
            "required": {"subagent", "task"},
        },
    },
    "openai": {
        "delegate_to_subagent": {
            "parameters": {"subagent", "task", "context_json"},
            "required": {"subagent", "task"},
        },
    },
}


def anthropic_bridge_tool_specs() -> Dict[str, Dict[str, Set[str]]]:
    """Bridge-only tool specs for the Anthropic provider.

    Returns a fresh shallow copy so callers can mutate the outer dict
    without poisoning the module-level table.
    """
    return {name: dict(spec) for name, spec in _BRIDGE_TOOL_SPECS_BY_PROVIDER["anthropic"].items()}


def openai_bridge_tool_specs() -> Dict[str, Dict[str, Set[str]]]:
    """Bridge-only tool specs for the OpenAI provider."""
    return {name: dict(spec) for name, spec in _BRIDGE_TOOL_SPECS_BY_PROVIDER["openai"].items()}


def all_bridge_specs_for_provider(provider: str) -> Dict[str, Dict[str, Set[str]]]:
    """Return ``{name: {"parameters": set, "required": set}, ...}`` for
    bridge-only tools wired into ``provider``'s bridge surface.

    Returns ``{}`` for unknown providers — the validator treats that as
    "no bridge tools exposed," which means a name reaching the bridge
    branch of the unified resolver is unresolved (``unknown_tool``).
    """
    if provider == "anthropic":
        return anthropic_bridge_tool_specs()
    if provider == "openai":
        return openai_bridge_tool_specs()
    return {}
