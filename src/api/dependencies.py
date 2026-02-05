"""
Dependency injection for the API layer.

Provides a singleton DataAccessLayer and ToolRegistry
that all route handlers share.
"""

from __future__ import annotations

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