"""Slice B1 — the AI 研究 (ai_research) model route.

resolve_research_route(provider) gives the model + effort the Research surface
should use when the request specifies none: a configured ai_research route when
its provider MATCHES the request, else the request provider's default-tier model
(today's behavior). 'default'/empty effort → None (agent uses its own default).
"""

from __future__ import annotations

import typing

import pytest

import src.agents.config as cfg
from src.agents.config import AgentConfig, resolve_research_route
from src.model_routing import TaskId

_RESEARCH_ENV = (
    "ARKSCOPE_AI_RESEARCH_PROVIDER",
    "ARKSCOPE_AI_RESEARCH_MODEL",
    "ARKSCOPE_AI_RESEARCH_EFFORT",
)


@pytest.fixture()
def clean_env(monkeypatch):
    for k in _RESEARCH_ENV:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_ai_research_is_a_task():
    assert "ai_research" in typing.get_args(TaskId)


def test_agentconfig_has_ai_research_fields():
    c = AgentConfig()
    assert c.ai_research_provider == "" and c.ai_research_model == "" and c.ai_research_effort == ""


def test_unconfigured_uses_provider_default_tier(clean_env):
    clean_env.setattr(cfg, "get_agent_config", lambda: AgentConfig())  # fresh, unconfigured
    assert resolve_research_route("openai") == ("gpt-5.4", None)         # openai default tier
    assert resolve_research_route("anthropic") == ("claude-sonnet-4-6", None)  # anthropic default tier


def test_configured_route_for_matching_provider(clean_env):
    c = AgentConfig()
    c.ai_research_provider = "openai"
    c.ai_research_model = "gpt-5.4-mini"
    c.ai_research_effort = "low"
    clean_env.setattr(cfg, "get_agent_config", lambda: c)
    assert resolve_research_route("openai") == ("gpt-5.4-mini", "low")  # honored (provider matches)
    assert resolve_research_route("anthropic") == ("claude-sonnet-4-6", None)  # mismatch → default tier
