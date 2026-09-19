"""Independent task route owners; all configuration lives in temporary profiles."""

from dataclasses import replace
import sqlite3
from types import SimpleNamespace
from typing import get_args

import pytest
from fastapi import HTTPException

from src.agents import config
from src.api.routes import config_routes
from src.model_capabilities import capability_for
from src.model_credentials import CredentialStore
from src.model_effective import task_auth_executable, task_capability_ok
from src.model_route_store import ModelRouteStore
from src.model_routing import TaskId, catalog, task_route_admission_detail


TASK = "lifecycle_investigation"
OTHERS = ('card_synthesis', 'ai_research')


@pytest.fixture
def stores(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(config, "ensure_env_loaded", lambda: None)
    for task in (*OTHERS, TASK):
        for field in ("provider", "model", "effort"):
            monkeypatch.delenv(f"ARKSCOPE_{task}_{field}".upper(), raising=False)
    config.get_agent_config.cache_clear()
    credentials = CredentialStore(tmp_path / "profile.db")
    return credentials, ModelRouteStore(credentials.db_path)


def test_investigation_task_catalog_has_its_own_recommended_route(stores):
    credentials, routes = stores
    assert TASK in get_args(TaskId)
    task = next(item for item in catalog().tasks if item.id == TASK)
    assert (task.label, task.default_provider, task.recommended_model) == (
        "Lifecycle Investigation", "anthropic", "claude-sonnet-5",
    )
    result = config_routes.model_catalog(store=credentials)
    assert set(result["routes"]) == set(result["effective"]["tasks"]) == {*OTHERS, TASK}
    assert result["routes"][TASK]["effort"] == "high"
    assert routes.get_all() == {}  # Reading Settings does not save a draft.


def test_investigation_catalog_does_not_offer_unimplemented_custom_models():
    tasks = {task.id: task for task in catalog().tasks}
    assert tasks[TASK].supports_custom_models is False
    assert tasks["ai_research"].supports_custom_models is True


def test_investigation_route_store_failure_projects_an_actionable_gap(tmp_path, monkeypatch):
    from tests.test_lifecycle_investigation_review import context

    c = context(tmp_path)
    service = c["preflight"]

    def unavailable():
        from src.model_routing import ModelRouteUnavailable
        raise ModelRouteUnavailable()

    monkeypatch.setattr(service, "route_loader", unavailable)
    packet = service.prepare("OLD")
    assert packet["available"] is False
    assert packet["reason"] == "model_route_unavailable"
    assert packet["execution"] is None


def test_investigation_route_save_reset_and_other_tasks_are_independent(stores):
    credentials, routes = stores
    for task in OTHERS:
        routes.set(task, "openai", "gpt-5.6-luna", "xhigh")
    before = routes.get_all()
    request = config_routes.ModelRoutesUpdate.model_validate({"routes": {
        TASK: {"provider": "anthropic", "model": "claude-opus-5", "effort": "high"},
    }})
    saved = config_routes.update_model_routes(request, store=credentials)
    assert saved["routes"][TASK]["source"] == "db"
    assert {task: routes.get(task) for task in OTHERS} == before
    routes.set("ai_research", "anthropic", "claude-sonnet-5", "low")
    assert config.task_route(TASK, route_store=routes).model == "claude-opus-5"
    runtime = config_routes.runtime_config(store=credentials)
    assert runtime[TASK]["model"] == "claude-opus-5"
    assert runtime["ai_research"]["model"] == "claude-sonnet-5"
    reset = config_routes.delete_model_route(TASK, store=credentials)
    assert reset["deleted"] is True
    assert reset["route"]["model"] == "claude-sonnet-5"
    assert reset["route"]["effort"] == "high"
    assert routes.get("ai_research").effort == "low"


@pytest.mark.parametrize("auth_mode", ["api_key", "claude_code_oauth"])
def test_investigation_xhigh_save_reads_back_without_revalidating_unchanged_spark(stores, monkeypatch, auth_mode):
    credentials, routes = stores
    spark = routes.set("card_synthesis", "openai", "gpt-5.3-codex-spark", "xhigh")
    monkeypatch.setattr(config_routes, "_active_auth_mode", lambda *args: auth_mode)
    monkeypatch.setattr(config_routes, "resolve_active_credential", lambda *args, **kwargs: pytest.fail("unchanged Spark must not require entitlement lookup"))
    request = config_routes.ModelRoutesUpdate.model_validate({"routes": {
        TASK: {"provider": "anthropic", "model": "claude-sonnet-5", "effort": "xhigh"},
    }})
    saved = config_routes.update_model_routes(request, store=credentials)
    assert saved["routes"][TASK]["effort"] == "xhigh"
    assert config.task_route(TASK, route_store=routes).effort == "xhigh"
    assert routes.get("card_synthesis") == spark


def test_multi_task_route_save_api_rolls_back_on_late_sql_failure(stores):
    credentials, routes = stores
    routes.set("card_synthesis", "anthropic", "claude-sonnet-5", "high")
    before = routes.get_all()
    with sqlite3.connect(credentials.db_path) as conn:
        conn.execute("""CREATE TRIGGER reject_route BEFORE INSERT ON model_route
            WHEN NEW.task = 'lifecycle_investigation'
            BEGIN SELECT RAISE(ABORT, 'synthetic route failure'); END""")
    request = config_routes.ModelRoutesUpdate.model_validate({"routes": {
        "card_synthesis": {"provider": "anthropic", "model": "claude-sonnet-5", "effort": "xhigh"},
        TASK: {"provider": "anthropic", "model": "claude-sonnet-5", "effort": "xhigh"},
    }})
    with pytest.raises(sqlite3.IntegrityError, match="synthetic route failure"):
        config_routes.update_model_routes(request, store=credentials)
    assert routes.get_all() == before


def test_investigation_does_not_borrow_research_or_generic_model_defaults(stores, monkeypatch):
    _, routes = stores
    monkeypatch.setattr(config, "get_agent_config", lambda: config.AgentConfig(
        ai_research_provider="openai", ai_research_model="gpt-5.6-sol",
        ai_research_effort="max", anthropic_model="claude-opus-5",
    ))
    monkeypatch.setenv("ARKSCOPE_AI_RESEARCH_MODEL", "gpt-5.6-terra")
    route = config.task_route(TASK, route_store=routes)
    assert (route.provider, route.model, route.effort, route.source) == (
        "anthropic", "claude-sonnet-5", "high", "default",
    )


def test_investigation_route_read_error_is_not_a_billing_fallback(stores):
    class BrokenStore:
        def get(self, task):
            raise OSError("database unavailable")

    with pytest.raises(ValueError, match="^model_route_unavailable$"):
        config.task_route(TASK, route_store=BrokenStore())
    with pytest.raises(ValueError, match="^model_route_unavailable$"):
        config.task_route("ai_research", route_store=BrokenStore())


def test_investigation_route_explicit_import_export_roundtrip(stores, monkeypatch):
    credentials, routes = stores
    prefs = {f"{TASK}_provider": "anthropic", f"{TASK}_model": "claude-sonnet-5",
             f"{TASK}_effort": "high", "ai_research_provider": "openai",
             "ai_research_model": "gpt-5.6-luna", "ai_research_effort": "low"}
    monkeypatch.setattr(config_routes, "_load_user_profile", lambda: {"llm_preferences": prefs})
    imported = config_routes.import_model_routes(store=credentials)
    assert set(imported["imported"]) == {TASK, "ai_research"}
    assert routes.get(TASK).model == "claude-sonnet-5"
    config_routes.export_model_routes(store=credentials)
    profile = config._load_user_profile()["llm_preferences"]
    assert {key: profile[key] for key in prefs} == prefs
    routes.delete(TASK)
    cleared = config_routes.export_model_routes(store=credentials)
    assert cleared["cleared"] == [TASK]
    assert not any(key.startswith(TASK) for key in config._load_user_profile()["llm_preferences"])
    assert config._load_user_profile()["llm_preferences"]["ai_research_model"] == "gpt-5.6-luna"


@pytest.mark.parametrize(("provider", "auth_mode", "model"), [
    ("anthropic", "api_key", "claude-sonnet-5"),
    ("anthropic", "claude_code_oauth", "claude-sonnet-5"),
    ("openai", "api_key", "gpt-5.6-luna"),
    ("openai", "chatgpt_oauth", "gpt-5.6-luna"),
])
def test_investigation_all_four_channels_share_task_admission(provider, auth_mode, model):
    from src.security_lifecycle_web_contract import validate_selection

    cap = capability_for(model)
    assert task_capability_ok(TASK, cap)
    assert task_auth_executable(TASK, provider, auth_mode, cap)
    assert task_route_admission_detail(provider, model, "high", task=TASK, auth_mode=auth_mode) is None
    assert validate_selection(provider, auth_mode, model, "local:7").model == model


def test_investigation_requires_tools_and_structured_output_without_changing_research():
    cap = replace(capability_for("gpt-5.6-luna"), supports_structured_output=False)
    assert not task_capability_ok(TASK, cap)
    assert task_capability_ok("ai_research", cap)
    assert not task_capability_ok(TASK, replace(cap, supports_tool_calling=False))


@pytest.mark.parametrize(("model", "code"), [
    ("gpt-5.3-codex-spark", "model_retired"),
    ("claude-fable-5", "model_retired"),
    ("gpt-unknown-custom", "model_not_in_registry"),
])
def test_investigation_save_rejects_unsupported_models_before_writing(stores, model, code):
    credentials, routes = stores
    provider = "anthropic" if model.startswith("claude-") else "openai"
    request = config_routes.ModelRoutesUpdate.model_validate({"routes": {
        TASK: {"provider": provider, "model": model, "effort": "high"},
    }})
    with pytest.raises(HTTPException) as caught:
        config_routes.update_model_routes(request, store=credentials)
    assert caught.value.detail["code"] == code
    assert routes.get_all() == {}


def test_investigation_import_does_not_accept_models_save_would_reject(stores, monkeypatch):
    credentials, routes = stores
    monkeypatch.setattr(config_routes, "_load_user_profile", lambda: {"llm_preferences": {
        f"{TASK}_provider": "openai", f"{TASK}_model": "gpt-unknown-custom", f"{TASK}_effort": "high",
    }})
    assert TASK in config_routes.import_model_routes(store=credentials)["skipped"]
    assert routes.get(TASK) is None


def test_current_preflight_factory_uses_dedicated_profile_route(tmp_path, monkeypatch):
    from src.api import dependencies
    from src.api.routes.lifecycle_investigation import get_preflight
    from src import market_data_admin, sa_capture_store

    requested = []
    monkeypatch.setattr(config, "task_route", lambda task, **kwargs: requested.append(task))
    monkeypatch.setattr(dependencies, "get_credential_store", lambda: object())
    monkeypatch.setattr(market_data_admin, "resolve_market_db_path", lambda: tmp_path / "market.db")
    monkeypatch.setattr(sa_capture_store, "resolve_sa_db_path", lambda: tmp_path / "sa.db")
    preflight = get_preflight(service=object())
    preflight.route_loader()
    assert requested == [TASK]


def test_runtime_selection_checks_new_task_not_borrowed_research(monkeypatch):
    from src import security_lifecycle_web_contract as contract

    seen = []
    original = contract.model_execution_admission_detail

    def guard(model, **kwargs):
        seen.append(kwargs["task"])
        return original(model, **kwargs)

    monkeypatch.setattr(contract, "model_execution_admission_detail", guard)
    contract.validate_selection("anthropic", "claude_code_oauth", "claude-sonnet-5", "local:7")
    assert seen == [TASK]


def test_unknown_discovered_models_stay_visible_but_not_executable_for_investigation(stores):
    from src.model_discovery_cache import ModelDiscoveryCache
    from src.model_effective import ActiveCredential, effective_model_view_v2

    credentials, _ = stores
    cache = ModelDiscoveryCache(credentials.db_path)
    active = ActiveCredential("openai", "local:7", "api_key", "test-fingerprint")
    route = SimpleNamespace(provider="openai", model="gpt-unknown-custom", effort="high")
    view = effective_model_view_v2(cache=cache, routes={TASK: route}, credentials={"openai": active, "anthropic": None})
    models = view["tasks"][TASK]["providers"]["openai"]["models"]
    unknown = next(row for row in models if row["id"] == route.model)
    assert unknown["eligible"] is False
    assert unknown["reason_code"] == "model_not_in_registry"
