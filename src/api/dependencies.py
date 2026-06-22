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


@lru_cache(maxsize=1)
def get_thread_store():
    """Singleton local store for AI 研究 conversation threads/messages (same local
    SQLite). Threads live alongside profile state in the local DB, never PG."""
    from src.research_threads import ResearchThreadStore

    return ResearchThreadStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_run_store():
    """Singleton local store for server-owned AI 研究 runs/events.

    On process boot, any queued/running rows from a previous sidecar lifetime are
    terminalized as interrupted so the UI never shows stale work as still live.
    """
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore

    store = ResearchRunStore(_local_state_db_path())
    store.reconcile_interrupted(thread_store=ResearchThreadStore(_local_state_db_path()))
    return store


@lru_cache(maxsize=1)
def get_credential_store():
    """Singleton local LLM credential store (same ignored local SQLite DB)."""
    from src.model_credentials import CredentialStore

    return CredentialStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_oauth_token_store():
    """Singleton OAuth token store for LLM subscription auth (keyring-first, with
    a flagged plaintext dev fallback). Holds the real OAuth/setup tokens — NEVER
    the credential DB. See src/auth_drivers/token_store.py."""
    from src.auth_drivers import get_token_store

    return get_token_store()


@lru_cache(maxsize=1)
def get_oauth_login_manager():
    """Singleton in-app ChatGPT-OAuth login orchestrator. Holds in-memory login
    state (pending PKCE/state + results) across the start→status→complete requests,
    so it MUST be a process singleton. Writes the resulting credential through the
    same two-store split (CredentialStore metadata + token-store secret)."""
    from src.auth_drivers.chatgpt_oauth_manager import OAuthLoginManager

    return OAuthLoginManager(
        credential_store=get_credential_store(),
        token_store=get_oauth_token_store(),
    )


@lru_cache(maxsize=1)
def get_data_provider_store():
    """Singleton DATA-provider config store (API keys / IBKR host+port — same
    ignored local SQLite DB). Values are injected into os.environ via apply_env."""
    from src.data_provider_config import DataProviderConfigStore

    return DataProviderConfigStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_consensus_cache():
    """Singleton daily cache of analyst consensus (Finnhub) — a local DATA cache
    (its own data/cache/ SQLite), NOT user state. Overridable via
    ``ARKSCOPE_CONSENSUS_DB``."""
    from src.analyst_consensus import AnalystConsensusCache

    path = os.environ.get("ARKSCOPE_CONSENSUS_DB") or str(
        Path(__file__).resolve().parents[2] / "data" / "cache" / "analyst_consensus.db"
    )
    return AnalystConsensusCache(path)


def _local_state_db_path() -> str:
    return os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        Path(__file__).resolve().parents[2] / "data" / "profile_state.db"
    )
