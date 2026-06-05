"""
Dependency injection for the API layer.

Provides a singleton DataAccessLayer and ToolRegistry
that all route handlers share.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from src.tools.data_access import DataAccessLayer
from src.tools.registry import ToolRegistry, create_default_registry


@lru_cache(maxsize=1)
def get_dal() -> DataAccessLayer:
    """Singleton DataAccessLayer instance. Auto-detects Supabase from .env."""
    return DataAccessLayer(db_dsn="auto")


@lru_cache(maxsize=1)
def get_registry() -> ToolRegistry:
    """Singleton ToolRegistry with all tools registered."""
    return create_default_registry()


@lru_cache(maxsize=1)
def get_profile_store():
    """Singleton local profile-state store (SQLite).

    Holds user research-universe state (followed / archived / notes) — local,
    never the remote PG. Path overridable via ``ARKSCOPE_PROFILE_DB``; defaults
    to ``<repo>/data/profile_state.db``.
    """
    from src.profile_state import ProfileStateStore

    return ProfileStateStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_card_store():
    """Singleton local store for generated §2 AI card runs (same local SQLite).

    Auto-cached generated cards live alongside profile state in the local DB,
    never the remote PG. Path overridable via ``ARKSCOPE_PROFILE_DB``.
    """
    from src.card_runs import CardRunStore

    return CardRunStore(_local_state_db_path())


def _local_state_db_path() -> str:
    return os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        Path(__file__).resolve().parents[2] / "data" / "profile_state.db"
    )