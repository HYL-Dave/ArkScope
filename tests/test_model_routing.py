from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import yaml
import pytest
from fastapi import HTTPException

from src.api.routes.config_routes import (
    CredentialCreate,
    CredentialUpdate,
    ModelRoutesUpdate,
    ModelTestRequest,
    ResearchRuntimeUpdate,
    RouteUpdate,
    add_credential,
    delete_credential,
    delete_research_runtime,
    model_catalog,
    run_provider_model_test,
    runtime_config,
    update_research_runtime,
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


def test_update_research_runtime_persists_to_profile_db(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod
    from src.research_runtime_config import ResearchRuntimeStore

    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", tmp_path / "user_profile.local.yaml")
    cfg_mod.get_agent_config.cache_clear()

    db = tmp_path / "profile_state.db"
    res = update_research_runtime(
        ResearchRuntimeUpdate(max_tool_calls=96, session_timeout_s=3600, per_tool_timeout_s=75),
        store=CredentialStore(db),
    )
    assert res["research_runtime"]["source"] == "db"
    assert res["research_runtime"]["max_tool_calls"] == 96
    assert res["research_runtime"]["session_timeout_s"] == 3600.0
    assert res["research_runtime"]["per_tool_timeout_s"] == 75.0
    assert ResearchRuntimeStore(db).get().max_tool_calls == 96

    rc = runtime_config(store=CredentialStore(db))
    assert rc["research_runtime"]["source"] == "db"
    assert rc["research_runtime"]["max_tool_calls"] == 96

    cfg_mod.get_agent_config.cache_clear()


def test_delete_research_runtime_reverts_to_profile_fallback(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod
    import yaml

    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    local = tmp_path / "user_profile.local.yaml"
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", local)
    local.write_text(yaml.safe_dump({"llm_preferences": {"max_tool_calls": 44}}), encoding="utf-8")
    cfg_mod.get_agent_config.cache_clear()

    db = tmp_path / "profile_state.db"
    update_research_runtime(
        ResearchRuntimeUpdate(max_tool_calls=96, session_timeout_s=3600, per_tool_timeout_s=75),
        store=CredentialStore(db),
    )
    res = delete_research_runtime(store=CredentialStore(db))
    assert res["deleted"] is True
    assert res["research_runtime"]["source"] == "profile"
    assert res["research_runtime"]["max_tool_calls"] == 44
    assert res["research_runtime"]["session_timeout_s"] == 900.0

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


# --- ④ import/export (yaml <-> DB) -------------------------------------------------

def test_import_routes_copies_yaml_into_db(make_route_store, tmp_path):
    from src.api.routes.config_routes import import_model_routes

    rs = make_route_store({"llm_preferences": {
        "ai_research_provider": "openai", "ai_research_model": "gpt-5.4-mini", "ai_research_effort": "low",
        "card_synthesis_provider": "anthropic",  # no model → incomplete → skipped
    }})
    assert rs.get("ai_research") is None  # explicit: nothing in DB until import is called

    res = import_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))

    assert "ai_research" in res["imported"]
    assert "card_synthesis" in res["skipped"]  # provider without model is not imported
    row = rs.get("ai_research")
    assert (row.provider, row.model, row.effort) == ("openai", "gpt-5.4-mini", "low")
    assert rs.get("card_synthesis") is None


def test_export_routes_writes_db_to_yaml_preserving_other_keys(make_route_store, tmp_path):
    from src.api.routes.config_routes import export_model_routes

    rs = make_route_store({"llm_preferences": {"reasoning_effort": "xhigh"}})  # unrelated key
    rs.set("ai_research", "openai", "gpt-5.4-mini", "low")

    res = export_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))

    assert "ai_research" in res["exported"]
    data = yaml.safe_load((tmp_path / "user_profile.local.yaml").read_text())
    assert data["llm_preferences"]["ai_research_model"] == "gpt-5.4-mini"   # route written back
    assert data["llm_preferences"]["ai_research_provider"] == "openai"
    assert data["llm_preferences"]["reasoning_effort"] == "xhigh"           # UNRELATED key preserved


# --- review fixes: source-label / import validation / safety coverage --------------

def test_task_route_whitespace_only_yaml_effort_resolves_to_default(make_route_store):
    from src.agents.config import task_route

    # yaml sets ONLY a whitespace effort (no provider/model) → resolves to pure built-in
    # defaults, so the source must be "default", not "profile" (the label must use the
    # STRIPPED effort, consistent with how effort itself is resolved).
    rs = make_route_store({"llm_preferences": {"ai_research_effort": "   "}})
    assert task_route("ai_research", route_store=rs).source == "default"


def test_import_skips_provider_model_mismatch(make_route_store, tmp_path):
    from src.api.routes.config_routes import import_model_routes

    rs = make_route_store({"llm_preferences": {
        "ai_research_provider": "openai", "ai_research_model": "claude-opus-4-8",  # claude model, openai provider
    }})
    res = import_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))
    assert "ai_research" in res["skipped"]      # same guard as the save path
    assert rs.get("ai_research") is None         # inconsistent route NOT persisted


def test_import_normalizes_unknown_effort_to_default(make_route_store, tmp_path):
    from src.api.routes.config_routes import import_model_routes

    rs = make_route_store({"llm_preferences": {
        "ai_research_provider": "openai", "ai_research_model": "gpt-5.4-mini", "ai_research_effort": "bogus",
    }})
    res = import_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))
    assert "ai_research" in res["imported"]
    assert rs.get("ai_research").effort == "default"  # unknown effort normalized, mirroring save


def test_task_route_db_error_degrades_to_yaml(make_route_store):
    import sqlite3
    from src.agents.config import task_route

    rs = make_route_store(_YAML_AI)  # yaml fallback present

    class BoomStore:  # a route store whose read raises — resolution must NOT propagate it
        def get(self, task):
            raise sqlite3.OperationalError("boom")

    route = task_route("ai_research", route_store=BoomStore())
    assert (route.provider, route.model, route.source) == ("openai", "gpt-5.4-mini", "profile")


def test_import_export_do_not_rewrite_env_override(make_route_store, tmp_path, monkeypatch):
    from src.api.routes.config_routes import export_model_routes, import_model_routes
    from src.agents.config import task_route

    rs = make_route_store({"llm_preferences": {
        "ai_research_provider": "openai", "ai_research_model": "gpt-5.4-mini", "ai_research_effort": "low"}})
    monkeypatch.setenv("ARKSCOPE_AI_RESEARCH_MODEL", "gpt-5.5")
    import_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))
    export_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))
    assert os.environ["ARKSCOPE_AI_RESEARCH_MODEL"] == "gpt-5.5"            # env never rewritten
    assert task_route("ai_research", route_store=rs).source == "env"        # env still wins


# --- ⑤ reset/delete (DELETE endpoint) + export mirrors DB absence ------------------

def test_delete_model_route_reverts_to_yaml(make_route_store, tmp_path):
    from src.api.routes.config_routes import delete_model_route

    rs = make_route_store(_YAML_AI)                          # yaml fallback present
    rs.set("ai_research", "anthropic", "claude-opus-4-8", "high")  # DB overrides it

    res = delete_model_route("ai_research", store=CredentialStore(tmp_path / "profile_state.db"))

    assert res["deleted"] is True
    assert rs.get("ai_research") is None                     # DB row gone
    # returns the now-resolved route → reverted to the yaml fallback
    assert res["route"]["source"] == "profile"
    assert res["route"]["model"] == "gpt-5.4-mini"


def test_delete_model_route_no_row_is_idempotent_returns_default(make_route_store, tmp_path):
    from src.api.routes.config_routes import delete_model_route

    rs = make_route_store(None)                              # no yaml, no DB
    res = delete_model_route("ai_research", store=CredentialStore(tmp_path / "profile_state.db"))
    assert res["deleted"] is False                           # nothing to delete
    assert res["route"]["source"] == "default"


def test_delete_model_route_unknown_task_400(tmp_path):
    from src.api.routes.config_routes import delete_model_route

    with pytest.raises(HTTPException) as ei:
        delete_model_route("not_a_task", store=CredentialStore(tmp_path / "profile_state.db"))
    assert ei.value.status_code == 400


def test_export_clears_keys_for_tasks_absent_from_db(make_route_store, tmp_path):
    from src.api.routes.config_routes import export_model_routes

    # yaml carries a STALE card_synthesis route + an unrelated key; DB has only ai_research
    rs = make_route_store({"llm_preferences": {
        "card_synthesis_provider": "openai", "card_synthesis_model": "gpt-5.5", "card_synthesis_effort": "high",
        "reasoning_effort": "xhigh",
    }})
    rs.set("ai_research", "openai", "gpt-5.4-mini", "low")

    res = export_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))

    assert "ai_research" in res["exported"]
    assert "card_synthesis" in res["cleared"]                # mirrored DB absence
    data = yaml.safe_load((tmp_path / "user_profile.local.yaml").read_text())
    assert data["llm_preferences"]["ai_research_model"] == "gpt-5.4-mini"   # DB route written
    assert "card_synthesis_provider" not in data["llm_preferences"]         # stale keys cleared
    assert "card_synthesis_model" not in data["llm_preferences"]
    assert "card_synthesis_effort" not in data["llm_preferences"]
    assert data["llm_preferences"]["reasoning_effort"] == "xhigh"           # unrelated key preserved


# --- ⑤ review fixes: yaml-helper robustness + audit symmetry -----------------------

def test_save_local_override_coerces_non_dict_section(make_route_store, tmp_path):
    from src.agents.config import save_local_override

    make_route_store(None)  # points _LOCAL_CONFIG_PATH at this tmp file
    # a hand-edited local yaml with an empty header → llm_preferences parses to None
    (tmp_path / "user_profile.local.yaml").write_text("llm_preferences:\nother:\n  keep: 1\n")

    save_local_override("llm_preferences", "ai_research_model", "gpt-5.4-mini")  # must NOT raise

    data = yaml.safe_load((tmp_path / "user_profile.local.yaml").read_text())
    assert data["llm_preferences"]["ai_research_model"] == "gpt-5.4-mini"
    assert data["other"]["keep"] == 1  # unrelated section preserved


def test_clear_local_overrides_drops_emptied_section_and_preserves_others(make_route_store, tmp_path):
    from src.agents.config import clear_local_overrides

    make_route_store({
        "llm_preferences": {"ai_research_model": "m", "ai_research_provider": "openai"},
        "other": {"keep": 1},
    })
    p = tmp_path / "user_profile.local.yaml"
    clear_local_overrides("llm_preferences", "ai_research_model", "ai_research_provider")
    data = yaml.safe_load(p.read_text())
    assert "llm_preferences" not in data   # emptied section dropped
    assert data["other"]["keep"] == 1      # unrelated section preserved


def test_clear_local_overrides_idempotent_and_safe_on_missing(make_route_store, tmp_path):
    from src.agents.config import clear_local_overrides

    make_route_store({"llm_preferences": {"ai_research_model": "m"}})
    p = tmp_path / "user_profile.local.yaml"
    clear_local_overrides("llm_preferences", "nope")          # nothing to remove → untouched
    assert yaml.safe_load(p.read_text())["llm_preferences"]["ai_research_model"] == "m"
    p.unlink()
    clear_local_overrides("llm_preferences", "ai_research_model")  # missing file → no raise


def test_export_audits_both_write_and_clear_branches(make_route_store, tmp_path, monkeypatch):
    import src.api.routes.config_routes as cr

    rs = make_route_store(None)
    rs.set("ai_research", "openai", "gpt-5.4-mini", "low")    # present → write branch
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cr, "require_profile_state_write",
                        lambda action, detail=None: calls.append((action, (detail or {}).get("task"))))

    cr.export_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))

    actions = {a for a, _ in calls}
    audited_tasks = {t for _, t in calls}
    assert "model_route_export" in actions          # write branch audited
    assert "model_route_export_clear" in actions    # destructive clear branch audited too
    assert {"card_synthesis", "card_translation"} <= audited_tasks


def test_export_cleared_reports_only_tasks_whose_keys_were_removed(make_route_store, tmp_path):
    from src.api.routes.config_routes import export_model_routes

    # yaml carries ONLY a stale card_synthesis route; the other two tasks have no keys; DB empty.
    rs = make_route_store({"llm_preferences": {
        "card_synthesis_provider": "openai", "card_synthesis_model": "gpt-5.5", "card_synthesis_effort": "high",
    }})

    res = export_model_routes(store=CredentialStore(tmp_path / "profile_state.db"))

    # 'cleared' must mean "keys actually removed", not "task has no DB row" — so it should NOT
    # overcount card_translation / ai_research (which had nothing to clear).
    assert res["cleared"] == ["card_synthesis"]
    assert res["exported"] == []


# ── P2.7 Task 3: discovery cache write-through (caller seam) ──────


def test_discover_models_success_writes_cache(monkeypatch, tmp_path):
    import src.model_credentials as mc

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    recorded = {}

    class _FakeCache:
        def __init__(self, *a, **k): ...
        def lifecycle_epoch(self, **kw):
            return 0  # round-5 MF1: the guard needs a captured epoch before any write
        def record_run(self, **kw):
            recorded.update(kw)

    monkeypatch.setattr(mc, "ModelDiscoveryCache", _FakeCache)

    class _Cred:  # round-4 MF5: scope needs auth_mode — carry auth_type
        id = "c1"
        provider = "openai"
        auth_type = "api_key"
        secret = "sk-x"

    monkeypatch.setattr(mc, "_resolve_api_credential", lambda *a, **k: _Cred())

    class _FakeModels:
        data = [type("M", (), {"id": "gpt-5.6-luna"})()]

    class _FakeClient:
        def __init__(self, **kw): ...
        class models:  # noqa: N801 - mirrors sdk attribute
            @staticmethod
            def list():
                return _FakeModels()

    monkeypatch.setattr("openai.OpenAI", _FakeClient)

    out = mc.discover_models("openai", "c1")
    assert out.status == "ok"
    assert recorded["status"] == "ok"
    assert recorded["provider"] == "openai"
    assert recorded["auth_mode"] == "api_key"
    assert recorded["credential_id"] == "c1"
    assert recorded["secret_fingerprint"] == mc.secret_fingerprint("sk-x")
    assert [m["id"] for m in recorded["models"]] == ["gpt-5.6-luna"]


def test_discover_models_failure_records_nothing(monkeypatch, tmp_path):
    import src.model_credentials as mc

    calls = []

    class _FakeCache:
        def __init__(self, *a, **k): ...
        def record_run(self, **kw):
            calls.append(kw)

    monkeypatch.setattr(mc, "ModelDiscoveryCache", _FakeCache)

    class _Cred:
        id = "c1"
        provider = "openai"
        auth_type = "api_key"
        secret = "sk-x"

    monkeypatch.setattr(mc, "_resolve_api_credential", lambda *a, **k: _Cred())

    class _Boom:
        def __init__(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr("openai.OpenAI", _Boom)
    out = mc.discover_models("openai", "c1")
    assert out.status == "error" and calls == []


def test_discovery_route_records_seed_only_for_oauth_all_seed(monkeypatch, tmp_path):
    # round-5 MF2: the OAuth branch of discover_provider_models must write a
    # seed_only run to the cache when the driver returns only seeds — otherwise
    # the picker's discovery nudge loops forever on that channel.
    from src.api.routes import config_routes as cr
    from src.model_credentials import DiscoveredModel, ModelDiscoveryResult

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    recorded = {}

    class _FakeCache:
        def __init__(self, *a, **k): ...
        def lifecycle_epoch(self, **kw):
            return 0
        def record_run(self, **kw):
            recorded.update(kw)

    monkeypatch.setattr(cr, "ModelDiscoveryCache", _FakeCache)

    class _OauthCred:
        id = 1
        provider = "anthropic"
        auth_type = "claude_code_oauth"

    class _FakeStore:
        db_path = str(tmp_path / "profile_state.db")

        def get(self, credential_id):
            return _OauthCred()

    class _FakeDriver:
        async def discover_models(self):
            return ModelDiscoveryResult(
                provider="anthropic", credential_id="local:1", status="ok",
                models=[DiscoveredModel(id="claude-opus-4-8", provider="anthropic",
                                        label="Opus 4.8", source="seed")],
            )

    monkeypatch.setattr(cr, "_credential_store", lambda store: _FakeStore())
    monkeypatch.setattr("src.auth_drivers.factory.build_driver",
                        lambda **kw: _FakeDriver())

    body = cr.ModelDiscoveryRequest(provider="anthropic", credential_id="local:1")
    out = cr.discover_provider_models(body, store=_FakeStore(), token_store=object())

    assert recorded["status"] == "seed_only"                      # the write-through
    assert recorded["provider"] == "anthropic"
    assert recorded["auth_mode"] == "claude_code_oauth"
    assert recorded["credential_id"] == "local:1"
    assert recorded["secret_fingerprint"] == "oauth"
    assert recorded["models"] == []                               # seeds are not entitlement rows
    assert out["status"] == "ok" and "models" in out              # old fields intact
    assert out["cache_state"] == "seed_only"                      # additive fields present
    assert out["cached_at"]
    assert out["cached"] is True                                   # round-2 MF2


def test_discovery_route_oauth_cache_write_failure_reports_uncached(monkeypatch, tmp_path):
    # Round-2 MF2: when record_run raises, the route must stay 200 (best-effort)
    # and must NOT claim cached-ness: cached False, no cache_state/cached_at.
    from src.api.routes import config_routes as cr
    from src.model_credentials import DiscoveredModel, ModelDiscoveryResult

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))

    class _BoomCache:
        def __init__(self, *a, **k): ...
        def lifecycle_epoch(self, **kw):
            return 0  # epoch capture succeeds; only the WRITE fails
        def record_run(self, **kw):
            raise RuntimeError("disk full")

    monkeypatch.setattr(cr, "ModelDiscoveryCache", _BoomCache)

    class _OauthCred:
        id = 1
        provider = "anthropic"
        auth_type = "claude_code_oauth"

    class _FakeStore:
        db_path = str(tmp_path / "profile_state.db")

        def get(self, credential_id):
            return _OauthCred()

    class _FakeDriver:
        async def discover_models(self):
            return ModelDiscoveryResult(
                provider="anthropic", credential_id="local:1", status="ok",
                models=[DiscoveredModel(id="claude-opus-4-8", provider="anthropic",
                                        label="Opus 4.8", source="seed")],
            )

    monkeypatch.setattr(cr, "_credential_store", lambda store: _FakeStore())
    monkeypatch.setattr("src.auth_drivers.factory.build_driver",
                        lambda **kw: _FakeDriver())

    body = cr.ModelDiscoveryRequest(provider="anthropic", credential_id="local:1")
    out = cr.discover_provider_models(body, store=_FakeStore(), token_store=object())

    assert out["status"] == "ok"          # discovery itself still succeeds
    assert out.get("cached") is not True
    assert "cache_state" not in out and "cached_at" not in out


def test_api_key_discovery_commit_skipped_after_concurrent_delete(tmp_path, monkeypatch):
    # F1 (review round 4): the api_key write site must honor the same lifecycle
    # guard — a delete landing between the provider listing and the cache commit
    # must not resurrect rows for the deleted credential.
    import src.model_credentials as mc
    from src.api.routes import config_routes as cr
    from src.auth_drivers.token_store import PlaintextTokenStore
    from src.model_discovery_cache import ModelDiscoveryCache

    store = CredentialStore(tmp_path / "profile_state.db")
    c = store.add(provider="openai", auth_type="api_key", alias="K",
                  secret="sk-test-" + "a" * 40, make_active=True)
    cid = f"local:{c.id}"
    tok = PlaintextTokenStore(tmp_path / "auth_tokens.json")
    cache = ModelDiscoveryCache(store.db_path)

    class _FakeModels:
        data = [type("M", (), {"id": "gpt-5.6-luna"})()]

    class _FakeClient:
        def __init__(self, **kw): ...

        class models:  # noqa: N801 - mirrors sdk attribute
            @staticmethod
            def list():
                cr.delete_credential(cid, store=store, token_store=tok)  # mid-flight lifecycle op
                return _FakeModels()

    monkeypatch.setattr("openai.OpenAI", _FakeClient)
    out = mc.discover_models("openai", cid, store=store)
    assert out.status == "ok"                                 # the listing itself succeeded
    assert out.cached is False                                # but the stale commit was skipped
    assert cache.delete_scope(provider="openai", credential_id=cid) == 0  # nothing resurrected
    assert store.get(cid) is None


def test_api_key_discovery_epoch_capture_failure_skips_cache_write(tmp_path, monkeypatch):
    # Round-5 MF1: a FAILED epoch capture must fail CLOSED — discovery still
    # succeeds, but the cache write is skipped entirely (expected_epoch=None
    # would mean "validation disabled", which is fail-open).
    import src.model_credentials as mc
    from src.model_discovery_cache import ModelDiscoveryCache

    store = CredentialStore(tmp_path / "profile_state.db")
    c = store.add(provider="openai", auth_type="api_key", alias="K",
                  secret="sk-test-" + "a" * 40, make_active=True)
    cid = f"local:{c.id}"

    class _FakeModels:
        data = [type("M", (), {"id": "old-account-model"})()]

    class _FakeClient:
        def __init__(self, **kw): ...

        class models:  # noqa: N801
            @staticmethod
            def list():
                return _FakeModels()

    monkeypatch.setattr("openai.OpenAI", _FakeClient)
    monkeypatch.setattr(ModelDiscoveryCache, "lifecycle_epoch",
                        lambda self, **kw: (_ for _ in ()).throw(RuntimeError("db locked")))
    out = mc.discover_models("openai", cid, store=store)
    assert out.status == "ok"            # discovery itself still succeeds
    assert out.cached is False           # but nothing may be cached without the guard
    monkeypatch.undo()
    scope = ModelDiscoveryCache(store.db_path).get(
        provider="openai", auth_mode="api_key", credential_id=cid,
        secret_fingerprint=mc.secret_fingerprint("sk-test-" + "a" * 40))
    assert scope.status == "never_discovered"   # the write truly did not land
