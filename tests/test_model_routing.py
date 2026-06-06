from __future__ import annotations

import yaml
import pytest
from fastapi import HTTPException

from src.api.routes.config_routes import (
    ModelRoutesUpdate,
    ModelTestRequest,
    RouteUpdate,
    model_catalog,
    run_provider_model_test,
    runtime_config,
    update_model_routes,
)


def test_model_catalog_exposes_seed_models():
    res = model_catalog()
    ids = {m["id"] for m in res["models"]}
    assert "claude-opus-4-8" in ids
    assert "gpt-5.5" in ids
    assert "default" in {x["id"] for x in res["effort_options"]["anthropic"]}
    assert "minimal" in {x["id"] for x in res["effort_options"]["openai"]}
    assert set(res["routes"]) == {"card_synthesis", "card_translation"}


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
        )
    )
    assert res["routes"]["card_synthesis"]["provider"] == "openai"
    assert res["routes"]["card_synthesis"]["model"] == "gpt-5.5"
    assert res["routes"]["card_synthesis"]["effort"] == "high"

    data = yaml.safe_load((tmp_path / "user_profile.local.yaml").read_text())
    assert data["llm_preferences"]["card_synthesis_provider"] == "openai"
    assert data["llm_preferences"]["card_synthesis_model"] == "gpt-5.5"
    assert data["llm_preferences"]["card_synthesis_effort"] == "high"
    assert runtime_config()["card_synthesis"]["provider"] == "openai"

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
        )
    )
    assert res["routes"]["card_translation"]["effort"] == "default"
    assert "future-effort" in res["routes"]["card_translation"]["warning"]

    cfg_mod.get_agent_config.cache_clear()


def test_model_test_missing_credential_returns_seed_error(monkeypatch):
    import src.model_credentials as creds_mod

    monkeypatch.setattr(creds_mod, "ensure_env_loaded", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
    res = run_provider_model_test(
        ModelTestRequest(provider="openai", model="gpt-5.5", effort="high")
    )
    assert res["status"] == "missing_credential"
    assert "No direct API-key credential" in res["error"]
