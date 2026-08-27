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
    assert (c.ai_research_provider, c.ai_research_model, c.ai_research_effort) == (
        "openai", "gpt-5.6-luna", "xhigh",
    )


def test_fresh_research_uses_complete_provider_specific_routes(clean_env):
    clean_env.setattr(cfg, "get_agent_config", lambda: AgentConfig())  # fresh, unconfigured
    assert resolve_research_route("openai") == ("gpt-5.6-luna", "xhigh")
    assert resolve_research_route("anthropic") == ("claude-sonnet-5", "xhigh")


def test_fresh_install_task_routes_have_complete_explicit_efforts(clean_env, tmp_path):
    from src.agents import config as config_module
    from src.agents.config import task_route
    from src.model_route_store import ModelRouteStore

    clean_env.setattr(config_module, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    clean_env.setattr(config_module, "_LOCAL_CONFIG_PATH", tmp_path / "missing.local.yaml")
    config_module.get_agent_config.cache_clear()
    store = ModelRouteStore(tmp_path / "profile_state.db")

    assert (task_route("card_synthesis", route_store=store).model, task_route("card_synthesis", route_store=store).effort) == ("claude-opus-5", "high")
    assert (task_route("card_translation", route_store=store).model, task_route("card_translation", route_store=store).effort) == ("claude-sonnet-5", "medium")
    assert (task_route("ai_research", route_store=store).model, task_route("ai_research", route_store=store).effort) == ("gpt-5.6-luna", "xhigh")
    config_module.get_agent_config.cache_clear()


def test_matching_legacy_research_route_with_default_effort_stays_ambiguous(clean_env):
    class RouteStore:
        def get(self, task):
            return type("Route", (), {
                "provider": "openai", "model": "gpt-5.4-mini", "effort": "default",
            })()

    clean_env.setattr(cfg, "get_agent_config", lambda: AgentConfig())
    assert resolve_research_route("openai", route_store=RouteStore()) == ("gpt-5.4-mini", None)


def test_catalog_tasks_include_ai_research():
    # B2: the seed catalog must expose ai_research so Settings (which loops
    # catalog.tasks) renders the AI 研究 route row.
    from src.model_routing import catalog
    assert "ai_research" in [t.id for t in catalog().tasks]


def test_config_routes_expose_ai_research_route(tmp_path):
    # B2: /config/model-catalog + /config/runtime must return an ai_research
    # route (the UI reads routes[task.id] for each catalog task).
    from src.api.routes import config_routes as cr
    from src.model_credentials import CredentialStore
    store = CredentialStore(tmp_path / "p.db")
    assert "ai_research" in cr.model_catalog(store=store)["routes"]
    assert "ai_research" in cr.runtime_config(store=store)


def test_configured_route_for_matching_provider(clean_env):
    c = AgentConfig()
    c.ai_research_provider = "openai"
    c.ai_research_model = "gpt-5.4-mini"
    c.ai_research_effort = "low"
    clean_env.setattr(cfg, "get_agent_config", lambda: c)
    assert resolve_research_route("openai") == ("gpt-5.4-mini", "low")  # honored (provider matches)
    assert resolve_research_route("anthropic") == ("claude-sonnet-5", "xhigh")
