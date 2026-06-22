from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import yaml
import pytest
from fastapi import HTTPException

from src.api.routes.config_routes import (
    CredentialCreate,
    CredentialUpdate,
    ModelRoutesUpdate,
    ModelTestRequest,
    RouteUpdate,
    add_credential,
    delete_credential,
    model_catalog,
    run_provider_model_test,
    runtime_config,
    update_credential,
    update_model_routes,
)
from src.model_credentials import CredentialStore, provider_credentials


def test_model_catalog_exposes_seed_models(tmp_path):
    store = CredentialStore(tmp_path / "profile_state.db")
    res = model_catalog(store=store)
    ids = {m["id"] for m in res["models"]}
    assert "claude-opus-4-8" in ids
    assert "gpt-5.5" in ids
    assert "default" in {x["id"] for x in res["effort_options"]["anthropic"]}
    assert "minimal" in {x["id"] for x in res["effort_options"]["openai"]}
    assert set(res["routes"]) == {"card_synthesis", "card_translation", "ai_research"}


def test_update_model_routes_persists_to_profile_db(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod
    from src.model_route_store import ModelRouteStore

    for t in ("CARD_SYNTHESIS", "CARD_TRANSLATION"):
        for f in ("PROVIDER", "MODEL", "EFFORT"):
            monkeypatch.delenv(f"ARKSCOPE_{t}_{f}", raising=False)
    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", tmp_path / "user_profile.local.yaml")
    cfg_mod.get_agent_config.cache_clear()

    db = tmp_path / "profile_state.db"
    res = update_model_routes(
        ModelRoutesUpdate(
            routes={
                "card_synthesis": RouteUpdate(provider="openai", model="gpt-5.5", effort="high"),
                "card_translation": RouteUpdate(provider="anthropic", model="claude-sonnet-4-6"),
            }
        ),
        store=CredentialStore(db),  # route store shares this profile DB
    )
    assert res["routes"]["card_synthesis"]["provider"] == "openai"
    assert res["routes"]["card_synthesis"]["model"] == "gpt-5.5"
    assert res["routes"]["card_synthesis"]["effort"] == "high"
    assert res["routes"]["card_synthesis"]["source"] == "db"

    # persisted to the profile DB as an atomic row, NOT user_profile.local.yaml
    row = ModelRouteStore(db).get("card_synthesis")
    assert (row.provider, row.model, row.effort) == ("openai", "gpt-5.5", "high")
    assert not (tmp_path / "user_profile.local.yaml").exists()  # yaml untouched by a save

    # resolution reads it back as DB authority
    rc = runtime_config(store=CredentialStore(db))
    assert rc["card_synthesis"]["provider"] == "openai"
    assert rc["card_synthesis"]["source"] == "db"

    cfg_mod.get_agent_config.cache_clear()


def test_update_model_routes_rejects_provider_model_mismatch():
    with pytest.raises(HTTPException) as exc:
        update_model_routes(
            ModelRoutesUpdate(
                routes={
                    "card_synthesis": RouteUpdate(provider="anthropic", model="gpt-5.5"),
                }
            )
        )
    assert exc.value.status_code == 400


# --- Step 2: auth-mode-aware capability / route validation -------------------
def test_route_capability_warnings_claude_oauth_effort_supported():
    from src.model_routing import route_capability_warnings

    w = route_capability_warnings("anthropic", "claude-opus-4-8", "high", auth_mode="claude_code_oauth")
    assert w == []


def test_route_capability_warnings_claude_oauth_default_effort_silent():
    from src.model_routing import route_capability_warnings

    # default/no effort → nothing is "dropped", so no warning.
    assert route_capability_warnings("anthropic", "claude-opus-4-8", "default", auth_mode="claude_code_oauth") == []
    assert route_capability_warnings("anthropic", "claude-opus-4-8", "", auth_mode="claude_code_oauth") == []


def test_route_capability_warnings_chatgpt_oauth_points_at_discovery():
    from src.model_routing import route_capability_warnings

    w = route_capability_warnings("openai", "gpt-5.4-mini", "default", auth_mode="chatgpt_oauth")
    assert len(w) == 1 and "discovery" in w[0].lower() and "gpt-5.4-mini" in w[0]


def test_route_capability_warnings_api_key_and_none_are_silent():
    from src.model_routing import route_capability_warnings

    assert route_capability_warnings("openai", "gpt-5.5", "high", auth_mode="api_key") == []
    assert route_capability_warnings("anthropic", "claude-opus-4-8", "high", auth_mode=None) == []


def test_save_route_claude_oauth_active_preserves_effort_without_drop_warning(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", tmp_path / "user_profile.local.yaml")
    cfg_mod.get_agent_config.cache_clear()
    store = CredentialStore(tmp_path / "profile_state.db")
    store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth", alias="claude", make_active=True)

    res = update_model_routes(
        ModelRoutesUpdate(routes={"ai_research": RouteUpdate(provider="anthropic", model="claude-opus-4-8", effort="high")}),
        store=store,
    )
    w = res["routes"]["ai_research"]["warning"]
    assert w is None
    assert res["routes"]["ai_research"]["effort"] == "high"
    cfg_mod.get_agent_config.cache_clear()


def test_save_route_chatgpt_oauth_active_points_at_discovery(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", tmp_path / "user_profile.local.yaml")
    cfg_mod.get_agent_config.cache_clear()
    store = CredentialStore(tmp_path / "profile_state.db")
    store.add_oauth_credential(provider="openai", auth_mode="chatgpt_oauth", alias="cg", make_active=True)

    res = update_model_routes(
        ModelRoutesUpdate(routes={"ai_research": RouteUpdate(provider="openai", model="gpt-5.4-mini")}),
        store=store,
    )
    assert "discovery" in (res["routes"]["ai_research"]["warning"] or "").lower()
    cfg_mod.get_agent_config.cache_clear()


def test_invalid_effort_falls_back_to_default(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", tmp_path / "user_profile.local.yaml")
    cfg_mod.get_agent_config.cache_clear()

    res = update_model_routes(
        ModelRoutesUpdate(
            routes={
                "card_translation": RouteUpdate(
                    provider="anthropic",
                    model="claude-sonnet-4-6",
                    effort="future-effort",
                ),
            }
        ),
        store=CredentialStore(tmp_path / "profile_state.db"),  # isolate
    )
    assert res["routes"]["card_translation"]["effort"] == "default"
    assert "future-effort" in res["routes"]["card_translation"]["warning"]

    cfg_mod.get_agent_config.cache_clear()


def test_model_test_missing_credential_returns_seed_error(tmp_path, monkeypatch):
    import src.model_credentials as creds_mod

    store = CredentialStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(creds_mod, "ensure_env_loaded", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
    res = run_provider_model_test(
        ModelTestRequest(provider="openai", model="gpt-5.5", effort="high"),
        store=store,
    )
    assert res["status"] == "missing_credential"
    assert "No direct API-key credential" in res["error"]


def test_local_credential_crud_and_active_selection(tmp_path, monkeypatch):
    import src.model_credentials as creds_mod

    store = CredentialStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(creds_mod, "ensure_env_loaded", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEYS", raising=False)

    created = add_credential(
        CredentialCreate(
            provider="anthropic",
            alias="primary claude",
            secret="sk-ant-test-123456",
            make_active=True,
        ),
        store=store,
    )["credential"]
    assert created["editable"] is True
    assert created["active"] is True
    assert created["masked"].startswith("sk-a")
    assert "123456" not in created["masked"]

    updated = update_credential(
        created["id"],
        CredentialUpdate(alias="renamed claude", active=True),
        store=store,
    )["credential"]
    assert updated["label"] == "renamed claude"
    assert updated["active"] is True

    creds = provider_credentials(store)["anthropic"]
    assert any(c.id == created["id"] and c.active for c in creds)

    deleted = delete_credential(created["id"], store=store)
    assert deleted["deleted"] is True
    assert not any(c.id == created["id"] for c in provider_credentials(store)["anthropic"])


def test_credential_store_concurrent_first_init_does_not_lock(tmp_path):
    db = tmp_path / "profile_state.db"

    def init_once():
        return len(CredentialStore(db).list())

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(lambda _: init_once(), range(12))) == [0] * 12


# --- model-route DB authority — resolution: real env > DB > yaml > default ----------

_YAML_AI = {"llm_preferences": {
    "ai_research_provider": "openai",
    "ai_research_model": "gpt-5.4-mini",
    "ai_research_effort": "xhigh",
}}


@pytest.fixture()
def make_route_store(monkeypatch, tmp_path):
    """Hermetic route resolution + a ModelRouteStore on the same tmp profile DB.
    Clears the AgentConfig cache on teardown so a tmp-yaml config can't leak."""
    from src.agents import config as cfg_mod
    from src.model_route_store import ModelRouteStore

    def setup(local_yaml: dict | None = None) -> "ModelRouteStore":
        for t in ("CARD_SYNTHESIS", "CARD_TRANSLATION", "AI_RESEARCH"):
            for f in ("PROVIDER", "MODEL", "EFFORT"):
                monkeypatch.delenv(f"ARKSCOPE_{t}_{f}", raising=False)
        monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
        local_path = tmp_path / "user_profile.local.yaml"
        if local_yaml is not None:
            local_path.write_text(yaml.safe_dump(local_yaml))
        monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", local_path)
        cfg_mod.get_agent_config.cache_clear()
        return ModelRouteStore(tmp_path / "profile_state.db")

    yield setup
    cfg_mod.get_agent_config.cache_clear()


def test_task_route_db_wins_over_yaml(make_route_store):
    from src.agents.config import task_route

    rs = make_route_store(_YAML_AI)
    rs.set("ai_research", "anthropic", "claude-opus-4-8", "high")
    route = task_route("ai_research", route_store=rs)
    assert (route.provider, route.model, route.effort, route.source) == (
        "anthropic", "claude-opus-4-8", "high", "db")


def test_task_route_db_is_atomic_not_field_merged_with_yaml(make_route_store):
    # A DB route is used as a UNIT — yaml is NOT merged field-by-field beneath it
    # (that would re-introduce the half-applied-route problem the schema avoids).
    from src.agents.config import task_route

    rs = make_route_store(_YAML_AI)            # yaml: openai / gpt-5.4-mini / xhigh
    rs.set("ai_research", "anthropic", "claude-opus-4-8")  # effort omitted → "default"
    route = task_route("ai_research", route_store=rs)
    assert route.model == "claude-opus-4-8"    # DB model, NOT yaml's gpt-5.4-mini
    assert route.effort == "default"           # DB effort, NOT yaml's xhigh


def test_task_route_yaml_fallback_when_db_empty(make_route_store):
    from src.agents.config import task_route

    rs = make_route_store(_YAML_AI)            # DB empty → fall back to yaml
    route = task_route("ai_research", route_store=rs)
    assert (route.provider, route.model, route.effort, route.source) == (
        "openai", "gpt-5.4-mini", "xhigh", "profile")


def test_task_route_default_when_no_db_no_yaml(make_route_store):
    from src.agents.config import task_route

    rs = make_route_store(None)
    assert task_route("ai_research", route_store=rs).source == "default"


def test_task_route_real_env_overrides_db(make_route_store, monkeypatch):
    from src.agents.config import task_route

    rs = make_route_store(None)
    rs.set("ai_research", "anthropic", "claude-opus-4-8", "high")
    monkeypatch.setenv("ARKSCOPE_AI_RESEARCH_PROVIDER", "openai")
    monkeypatch.setenv("ARKSCOPE_AI_RESEARCH_MODEL", "gpt-5.5")
    route = task_route("ai_research", route_store=rs)
    assert (route.provider, route.model, route.source) == ("openai", "gpt-5.5", "env")
