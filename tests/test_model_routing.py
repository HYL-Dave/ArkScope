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


def test_update_model_routes_persists_local_yaml(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod

    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_PROVIDER", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_MODEL", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_TRANSLATION_PROVIDER", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_TRANSLATION_MODEL", raising=False)
    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", tmp_path / "user_profile.local.yaml")
    cfg_mod.get_agent_config.cache_clear()

    res = update_model_routes(
        ModelRoutesUpdate(
            routes={
                "card_synthesis": RouteUpdate(provider="openai", model="gpt-5.5", effort="high"),
                "card_translation": RouteUpdate(provider="anthropic", model="claude-sonnet-4-6"),
            }
        ),
        store=CredentialStore(tmp_path / "profile_state.db"),  # isolate: no active OAuth cred
    )
    assert res["routes"]["card_synthesis"]["provider"] == "openai"
    assert res["routes"]["card_synthesis"]["model"] == "gpt-5.5"
    assert res["routes"]["card_synthesis"]["effort"] == "high"

    data = yaml.safe_load((tmp_path / "user_profile.local.yaml").read_text())
    assert data["llm_preferences"]["card_synthesis_provider"] == "openai"
    assert data["llm_preferences"]["card_synthesis_model"] == "gpt-5.5"
    assert data["llm_preferences"]["card_synthesis_effort"] == "high"
    assert runtime_config(store=CredentialStore(tmp_path / "profile_state.db"))["card_synthesis"]["provider"] == "openai"

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
def test_route_capability_warnings_claude_oauth_effort_dropped():
    from src.model_routing import route_capability_warnings

    w = route_capability_warnings("anthropic", "claude-opus-4-8", "high", auth_mode="claude_code_oauth")
    assert len(w) == 1 and "not be applied" in w[0].lower() and "high" in w[0]


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


def test_save_route_warns_when_claude_oauth_active_drops_effort(tmp_path, monkeypatch):
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
    assert w and "not be applied" in w.lower() and "high" in w  # effort-dropped surfaced, not hidden
    assert res["routes"]["ai_research"]["effort"] == "high"  # still saved (the driver derives at run time)
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
