from __future__ import annotations

import pytest
import yaml

from src.research_runtime_config import ResearchRuntimeStore, resolve_research_runtime


@pytest.fixture()
def store(tmp_path):
    return ResearchRuntimeStore(tmp_path / "profile_state.db")


def _isolated_profile(monkeypatch, tmp_path, prefs: dict | None = None):
    from src.agents import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    local = tmp_path / "user_profile.local.yaml"
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", local)
    if prefs is not None:
        local.write_text(yaml.safe_dump({"llm_preferences": prefs}), encoding="utf-8")
    cfg_mod.get_agent_config.cache_clear()
    return cfg_mod


def test_defaults_when_no_db_or_profile(store, monkeypatch, tmp_path):
    cfg_mod = _isolated_profile(monkeypatch, tmp_path)
    try:
        got = resolve_research_runtime(store=store)
        assert got.max_tool_calls == 60
        assert got.session_timeout_s == 900.0
        assert got.per_tool_timeout_s == 45.0
        assert got.source == "default"
    finally:
        cfg_mod.get_agent_config.cache_clear()


def test_yaml_profile_is_fallback_until_db_row_exists(store, monkeypatch, tmp_path):
    cfg_mod = _isolated_profile(
        monkeypatch,
        tmp_path,
        {
            "max_tool_calls": 22,
            "claude_subscription_timeout_s": 1200,
            "research_per_tool_timeout_s": 12,
        },
    )
    try:
        got = resolve_research_runtime(store=store)
        assert (got.max_tool_calls, got.session_timeout_s, got.per_tool_timeout_s) == (22, 1200.0, 12.0)
        assert got.source == "profile"

        store.set(max_tool_calls=88, session_timeout_s=2400, per_tool_timeout_s=30)
        got = resolve_research_runtime(store=store)
        assert (got.max_tool_calls, got.session_timeout_s, got.per_tool_timeout_s) == (88, 2400.0, 30.0)
        assert got.source == "db"
    finally:
        cfg_mod.get_agent_config.cache_clear()


def test_real_env_overrides_db(store, monkeypatch, tmp_path):
    cfg_mod = _isolated_profile(monkeypatch, tmp_path)
    store.set(max_tool_calls=88, session_timeout_s=2400, per_tool_timeout_s=30)
    monkeypatch.setenv("ARKSCOPE_RESEARCH_MAX_TOOL_CALLS", "11")
    monkeypatch.setenv("ARKSCOPE_RESEARCH_SESSION_TIMEOUT_S", "3600")
    monkeypatch.setenv("ARKSCOPE_RESEARCH_PER_TOOL_TIMEOUT_S", "9")
    try:
        got = resolve_research_runtime(store=store)
        assert (got.max_tool_calls, got.session_timeout_s, got.per_tool_timeout_s) == (11, 3600.0, 9.0)
        assert got.source == "env"
        assert got.db_saved is True
    finally:
        cfg_mod.get_agent_config.cache_clear()


def test_delete_reverts_to_yaml_fallback(store, monkeypatch, tmp_path):
    cfg_mod = _isolated_profile(monkeypatch, tmp_path, {"max_tool_calls": 33})
    store.set(max_tool_calls=88, session_timeout_s=2400, per_tool_timeout_s=30)
    try:
        assert store.delete() is True
        got = resolve_research_runtime(store=store)
        assert got.max_tool_calls == 33
        assert got.session_timeout_s == 900.0
        assert got.per_tool_timeout_s == 45.0
        assert got.source == "profile"
        assert store.delete() is False
    finally:
        cfg_mod.get_agent_config.cache_clear()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_tool_calls": 0, "session_timeout_s": 900, "per_tool_timeout_s": 45},
        {"max_tool_calls": 60, "session_timeout_s": -1, "per_tool_timeout_s": 45},
        {"max_tool_calls": 60, "session_timeout_s": 900, "per_tool_timeout_s": 0},
    ],
)
def test_store_rejects_invalid_runtime_values(store, kwargs):
    with pytest.raises(ValueError):
        store.set(**kwargs)
