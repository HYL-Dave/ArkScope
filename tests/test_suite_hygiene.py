from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_PROFILE_DB = (_PROJECT_ROOT / "data" / "profile_state.db").resolve()
_COLLECTION_PROFILE_DB = os.environ.get("ARKSCOPE_PROFILE_DB")


def test_profile_db_is_isolated_before_test_collection() -> None:
    assert _COLLECTION_PROFILE_DB
    assert Path(_COLLECTION_PROFILE_DB).resolve() != _PROJECT_PROFILE_DB


def test_sqlite_guard_rejects_the_project_profile_database() -> None:
    with pytest.raises(RuntimeError, match="production profile DB"):
        sqlite3.connect(_PROJECT_PROFILE_DB)


def test_operator_local_agent_config_is_not_test_authority() -> None:
    from src.agents import config as config_module

    assert (
        config_module._LOCAL_CONFIG_PATH.resolve()
        != (_PROJECT_ROOT / "config" / "user_profile.local.yaml").resolve()
    )
    config = config_module.get_agent_config()
    assert (config.ai_research_model, config.ai_research_effort) == (
        "gpt-5.6-luna",
        "xhigh",
    )
