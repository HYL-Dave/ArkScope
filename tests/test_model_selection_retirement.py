"""Retiring a selection must not silently select or bill a replacement."""

import sqlite3
import asyncio

import pytest

from src.agents import config
from src.model_capabilities import capability_for, model_execution_admission_detail
from src.model_route_store import ModelRouteStore
from src.model_routing import catalog, task_route_admission_detail


@pytest.mark.parametrize("model,provider", [
    ("gpt-5.3-codex-spark", "openai"), ("claude-opus-5", "anthropic"),
])
def test_retired_saved_selection_is_unset_without_falling_back(tmp_path, model, provider):
    store = ModelRouteStore(tmp_path / "profile.db")
    store.set("card_translation", provider, model, "high")
    route = config.task_route("card_translation", route_store=store)
    assert (route.provider, route.model, route.source) == (provider, "", "db")
    assert route.warning == "model_required"
    assert task_route_admission_detail(provider, route.model, route.effort) == {
        "code": "model_required", "field": "model",
    }
    # Reading must not modify persisted authority or historic provenance.
    assert store.get("card_translation").model == model


def test_explicitly_empty_saved_route_never_uses_yaml_or_provider_default(tmp_path):
    store = ModelRouteStore(tmp_path / "profile.db")
    store.set("card_translation", "openai", "", "default")
    route = config.task_route("card_translation", route_store=store)
    assert (route.provider, route.model) == ("openai", "")
    assert model_execution_admission_detail(route.model) == {
        "code": "model_required", "field": "model",
    }


@pytest.mark.parametrize("selected", ["", "gpt-5.3-codex-spark"])
@pytest.mark.parametrize("requested_provider", ["openai", "anthropic"])
def test_unset_research_cannot_switch_to_a_provider_default(tmp_path, selected, requested_provider):
    store = ModelRouteStore(tmp_path / "profile.db")
    store.set("ai_research", "openai", selected, "default")
    model, effort = config.resolve_research_route(requested_provider, route_store=store)
    assert (model, effort) == ("", None)
    assert model_execution_admission_detail(model)["code"] == "model_required"


@pytest.mark.parametrize("model", [
    "gpt-5.3-codex-spark-20260919", "gpt-5.3-codex-spark-2026-09-19",
])
def test_dated_spark_is_retired_not_an_unknown_custom_model(tmp_path, model):
    assert model_execution_admission_detail(model, task="card_translation") == {
        "code": "model_retired", "field": "model",
    }
    store = ModelRouteStore(tmp_path / "profile.db")
    store.set("card_translation", "openai", model, "high")
    assert config.task_route("card_translation", route_store=store).model == ""
    assert store.clear_retired_selections() == ["card_translation"]


def test_retired_spark_does_not_classify_unreviewed_siblings():
    assert capability_for("gpt-5.3-codex-spark-2") is None
    assert capability_for("gpt-5.3-codex-sparkling") is None


def test_explicit_retirement_cleanup_preserves_provider_and_unrelated_rows(tmp_path):
    path = tmp_path / "profile.db"
    store = ModelRouteStore(path)
    store.set("card_translation", "openai", "gpt-5.3-codex-spark", "xhigh")
    saved = store.set("ai_research", "openai", "gpt-5.6-luna", "max")
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE history (model TEXT)")
        conn.execute("INSERT INTO history VALUES ('gpt-5.3-codex-spark')")
    assert store.clear_retired_selections() == ["card_translation"]
    cleared = store.get("card_translation")
    assert (cleared.provider, cleared.model) == ("openai", "")
    assert store.get("ai_research") == saved
    assert store.clear_retired_selections() == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT model FROM history").fetchone()[0] == "gpt-5.3-codex-spark"


@pytest.mark.parametrize("model,provider", [
    ("gpt-6-sol", "openai"), ("gpt-6-luna", "openai"),
    ("claude-opus-5-5", "anthropic"),
])
def test_new_models_are_admitted_current_options(model, provider):
    assert model in catalog().current_model_ids
    assert task_route_admission_detail(provider, model, "high", task="card_translation") is None
    cap = capability_for(model)
    assert cap is not None and cap.max_output == 128_000
    assert cap.supports_tool_calling and cap.supports_structured_output


def test_opus55_does_not_inherit_retirement_or_forced_tool_choice():
    from src.card_synthesis import _anthropic_fixed_task_tool, _anthropic_fixed_task_tool_choice
    assert model_execution_admission_detail("claude-opus-5") == {
        "code": "model_retired", "field": "model",
    }
    assert capability_for("claude-opus-5-5").thinking_mode == "adaptive_always_on"
    assert _anthropic_fixed_task_tool_choice("claude-opus-5-5", "emit_result") == {"type": "auto"}
    assert _anthropic_fixed_task_tool(
        model="claude-opus-5-5", name="emit_result", description="Result",
        schema={"type": "object"},
    )["strict"] is True


def test_unset_canary_refuses_before_credential_resolution(monkeypatch):
    from src import model_task_canary

    monkeypatch.setattr(
        model_task_canary, "resolve_active_credential",
        lambda *args, **kwargs: pytest.fail("unset canary reached credential resolution"),
    )
    result = asyncio.run(model_task_canary.dispatch_task_model_test(
        task="card_translation", provider="openai", model="", effort="default",
        store=object(), token_store=object(),
    ))
    assert result.status == "unsupported"
    assert result.error_code == "model_required"


@pytest.mark.parametrize("toggle", [True, False])
def test_opus55_wire_cannot_disable_thinking(toggle):
    from types import SimpleNamespace
    from src.agents.anthropic_agent.agent import _build_thinking_param

    param, max_tokens = _build_thinking_param(
        "claude-opus-5-5", toggle, SimpleNamespace(max_tokens=8192),
    )
    assert param is None
    assert max_tokens == 128_000
