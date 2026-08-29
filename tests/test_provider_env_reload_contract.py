"""Contracts for the real provider fallback reload boundary."""

from __future__ import annotations

import os

import pytest

import src.data_provider_config as data_provider_config
import src.env_keys as env_keys
from src.data_provider_config import DataProviderConfigStore


@pytest.mark.parametrize(
    ("env_var", "should_reload"),
    [
        pytest.param("MASSIVE_API_KEY", False, id="massive-current-name"),
        pytest.param("POLYGON_API_KEY", False, id="polygon-legacy-name"),
        pytest.param("FINNHUB_API_KEY", True, id="allowed-provider-control"),
    ],
)
def test_unapply_env_crosses_the_real_fallback_reload_guard(
    monkeypatch,
    tmp_path,
    env_var: str,
    should_reload: bool,
):
    env_file = tmp_path / ".env"
    env_file.write_text(f"{env_var}=file-secret\n", encoding="utf-8")
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.setattr(env_keys, "_loaded_keys", set())
    monkeypatch.setattr(data_provider_config, "_APP_APPLIED", {env_var})
    monkeypatch.setenv(env_var, "app-secret")

    store = DataProviderConfigStore(tmp_path / "profile.db")
    store.set_setting("provider_env_fallback", "true")

    data_provider_config.unapply_env(env_var, store)

    if should_reload:
        assert os.environ[env_var] == "file-secret"
        assert env_var in env_keys.keys_loaded_from_file()
    else:
        assert env_var not in os.environ
        assert env_var not in env_keys.keys_loaded_from_file()
