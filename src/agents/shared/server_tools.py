"""Single source of truth for provider-native (server-side) tools.

LOAD-BEARING: this module is consumed by BOTH

  - the agents' actual wiring (``anthropic_agent/agent.py`` and
    ``openai_agent/agent.py``) — they must iterate the helpers below
    to populate their tool lists.
  - the replay validator's ``_currently_wired_server_tools`` —
    introspects what the wiring would expose if all relevant flags
    were on, so fixtures with ``server:<kind>`` entries can be
    validated against current agent capabilities.

Adding, renaming, or removing a hosted server tool means editing
``anthropic_server_tools`` / ``openai_server_tools`` here. That single
edit propagates to both consumers atomically. If a future refactor
silently bypasses these helpers in the wiring path, the sentinel-based
safeguard tests in ``tests/test_replay.py`` will fail.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List, Optional, Set, Tuple


def anthropic_server_tools(config: Optional[Any]) -> List[Tuple[str, dict]]:
    """Return ``[(replay_kind, tool_def), ...]`` for every Anthropic
    hosted server tool that ``config`` enables.

    The ``tool_def`` is the dict appended to the Anthropic API request's
    ``tools`` array. The ``replay_kind`` is the canonical
    ``server:<kind>`` identifier the replay validator expects in
    fixtures.

    Returns an empty list when ``config`` is None or no flags are on.
    """
    if config is None:
        return []
    out: List[Tuple[str, dict]] = []
    if bool(getattr(config, "web_claude_search", False)):
        # Lazy import: avoids a circular at module load time. The
        # constant lives in the agent module to keep all Anthropic API
        # vocabulary co-located with the wiring.
        from src.agents.anthropic_agent.agent import _CLAUDE_WEB_SEARCH_TOOL
        max_uses = int(getattr(config, "web_claude_max_uses", 5) or 5)
        out.append((
            "server:web_search",
            {**_CLAUDE_WEB_SEARCH_TOOL, "max_uses": max_uses},
        ))
    return out


def openai_server_tools(config: Optional[Any]) -> List[Tuple[str, Any]]:
    """Return ``[(replay_kind, tool_instance), ...]`` for every OpenAI
    hosted server tool ``config`` enables.

    The ``tool_instance`` is the object the wiring appends to the
    OpenAI Agent's ``tools=`` parameter (e.g. a ``WebSearchTool()``
    instance). Returns an empty list when ``config`` is None, the SDK
    is not installed, or no flags are on.
    """
    if config is None:
        return []
    out: List[Tuple[str, Any]] = []
    if bool(getattr(config, "web_openai_search", False)):
        try:
            from agents import WebSearchTool  # noqa: F401 — import-only probe
            out.append(("server:web_search", WebSearchTool()))
        except ImportError:
            # SDK absent: capture / wiring both treat as "no hosted
            # tool wired." Replay validator will then reject fixtures
            # claiming ``server:web_search``.
            pass
    return out


def all_kinds_for_provider(provider: str) -> Set[str]:
    """Maximal set of replay kinds this provider could expose if all
    relevant config flags were on.

    The replay validator's ``_currently_wired_server_tools`` calls
    this helper. Any fixture claiming a ``server:<kind>`` not in this
    set fails validation — meaning either the live agent module has
    dropped the wiring (real regression) or the fixture is stale.

    Returns ``set()`` for unknown providers. Never raises.
    """
    probe = SimpleNamespace(
        web_claude_search=True,
        web_claude_max_uses=5,
        web_openai_search=True,
    )
    if provider == "anthropic":
        return {kind for kind, _ in anthropic_server_tools(probe)}
    if provider == "openai":
        return {kind for kind, _ in openai_server_tools(probe)}
    return set()