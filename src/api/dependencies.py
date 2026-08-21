"""
Dependency injection for the API layer.

Provides a singleton DataAccessLayer and ToolRegistry
that all route handlers share.
"""

from __future__ import annotations

import hmac
import os
import socket
import sqlite3
import threading
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from functools import lru_cache
from pathlib import Path

from src.tools.data_access import DataAccessLayer
from src.tools.registry import ToolRegistry, create_default_registry


@lru_cache(maxsize=1)
def get_dal() -> DataAccessLayer:
    """Singleton DataAccessLayer instance. Auto-detects Supabase from .env."""
    return DataAccessLayer()


@lru_cache(maxsize=1)
def get_registry() -> ToolRegistry:
    """Singleton ToolRegistry with all tools registered."""
    return create_default_registry()


def get_security_lifecycle_read_service():
    """Read-only composition of the market and profile lifecycle stores."""
    from src.market_data_admin import resolve_market_db_path
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService

    return SecurityLifecycleReadService(
        market_db_path=resolve_market_db_path(),
        profile_db_path=_local_state_db_path(),
    )


def get_security_lifecycle_store():
    """Request-owned profile-side investigation store."""
    from fastapi import HTTPException

    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore
    from src.security_lifecycle_schema import (
        LifecycleSchemaMismatch,
        verify_profile_connection,
    )

    path = Path(_local_state_db_path())
    conn = None
    try:
        if not path.is_file():
            raise LifecycleSchemaMismatch("profile lifecycle schema is absent")
        conn = sqlite3.connect(
            f"file:{path.resolve()}?mode=rw",
            uri=True,
            timeout=10.0,
            check_same_thread=False,
        )
        verify_profile_connection(conn)
    except (OSError, sqlite3.Error, LifecycleSchemaMismatch):
        if conn is not None:
            conn.close()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "security_lifecycle_profile_store_unavailable",
                "store": "profile",
            },
        ) from None
    try:
        yield SecurityLifecycleInvestigationStore(conn)
    finally:
        conn.close()


class _LifecycleTavilyClient:
    def __init__(self, *, api_key_loader=None, transport=None):
        self._api_key_loader = api_key_loader or (
            lambda: os.environ.get("TAVILY_API_KEY", "")
        )
        self._transport = transport or self._request

    @staticmethod
    def _request(**kwargs):
        import requests

        return requests.post(**kwargs)

    def search(self, **kwargs):
        from src.security_lifecycle_search import LifecycleSearchFailure

        api_key = str(self._api_key_loader() or "").strip()
        if not api_key:
            raise LifecycleSearchFailure("credential_missing")
        payload = {
            "query": kwargs.get("query"),
            "topic": kwargs.get("topic"),
            "max_results": kwargs.get("max_results"),
            "include_answer": False,
            "include_raw_content": False,
            "include_usage": True,
        }
        payload = {key: value for key, value in payload.items() if value is not None}

        try:
            response = self._transport(
                url="https://api.tavily.com/search",
                json=payload,
                timeout=(5.0, 30.0),
                allow_redirects=False,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-Client-Source": "arkscope-lifecycle",
                },
            )
        except LifecycleSearchFailure:
            raise
        except Exception:
            raise LifecycleSearchFailure("network_error") from None
        status_code = int(getattr(response, "status_code", 0))
        failure_codes = {
            400: "extract_failed",
            401: "credential_missing",
            403: "permission_denied",
            429: "rate_limited",
            432: "usage_limit_reached",
            433: "usage_limit_reached",
        }
        if status_code in failure_codes:
            raise LifecycleSearchFailure(failure_codes[status_code])
        if 300 <= status_code < 400:
            raise LifecycleSearchFailure("unsupported_content")
        if status_code != 200:
            raise LifecycleSearchFailure("network_error")
        try:
            result = response.json()
        except Exception:
            raise LifecycleSearchFailure("extract_failed") from None
        if not isinstance(result, dict):
            raise LifecycleSearchFailure("extract_failed")
        return result


def _lifecycle_https_pool(target):
    import urllib3

    if not target.addresses:
        raise ValueError("resolved_address_required")
    return urllib3.HTTPSConnectionPool(
        host=target.addresses[0],
        port=target.port,
        timeout=urllib3.Timeout(connect=5.0, read=15.0),
        retries=False,
        cert_reqs="CERT_REQUIRED",
        assert_hostname=target.hostname,
        server_hostname=target.hostname,
    )


def _lifecycle_fetch_transport(
    *, target, max_bytes: int, redirect_guard, pool_factory=None
):
    from urllib.parse import urljoin, urlsplit

    import urllib3

    from src.security_lifecycle_search import LifecycleSearchFailure

    current = target
    create_pool = pool_factory or _lifecycle_https_pool
    for _ in range(6):
        pool = None
        response = None
        next_url = None
        try:
            pool = create_pool(current)
            parsed = urlsplit(current.url)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            rendered_host = (
                f"[{current.hostname}]"
                if ":" in current.hostname
                else current.hostname
            )
            host_header = (
                rendered_host
                if current.port == 443
                else f"{rendered_host}:{current.port}"
            )
            try:
                response = pool.urlopen(
                    "GET",
                    path,
                    redirect=False,
                    preload_content=False,
                    retries=False,
                    headers={
                        "Host": host_header,
                        "User-Agent": "ArkScope lifecycle evidence reader",
                    },
                )
            except (OSError, urllib3.exceptions.HTTPError):
                raise LifecycleSearchFailure("network_error") from None
            status_code = int(response.status)
            if status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise LifecycleSearchFailure("extract_failed")
                next_url = urljoin(current.url, location)
            elif status_code == 429:
                raise LifecycleSearchFailure("rate_limited")
            elif status_code >= 400:
                raise LifecycleSearchFailure("network_error")
            else:
                content_type = response.headers.get("Content-Type", "").split(
                    ";", 1
                )[0]
                if content_type not in {
                    "text/html",
                    "text/plain",
                    "application/xhtml+xml",
                }:
                    return None
                chunks = []
                size = 0
                for chunk in response.stream(8192):
                    if not chunk:
                        continue
                    remaining = max_bytes - size
                    if remaining <= 0:
                        break
                    chunks.append(chunk[:remaining])
                    size += min(len(chunk), remaining)
                    if size >= max_bytes:
                        break
                return {
                    "url": current.url,
                    "_resolved_target": current,
                    "content": b"".join(chunks).decode("utf-8", errors="replace"),
                    "mime_type": content_type,
                }
        finally:
            if response is not None:
                response.release_conn()
            if pool is not None:
                pool.close()
        if next_url is not None:
            current = redirect_guard(next_url)
            continue
    raise LifecycleSearchFailure("unsupported_content")


def get_security_lifecycle_search_adapter():
    """Injected attended Tavily adapter; construction performs no I/O."""
    from src.security_lifecycle_search import TavilyLifecycleSearchAdapter

    return TavilyLifecycleSearchAdapter(
        client=_LifecycleTavilyClient(),
        fetch_transport=_lifecycle_fetch_transport,
    )


def get_security_lifecycle_resolver():
    """Resolve public-search hosts at the explicit investigation boundary."""
    def resolve(host: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(row[4][0])
                    for row in socket.getaddrinfo(
                        host,
                        443,
                        type=socket.SOCK_STREAM,
                    )
                }
            )
        )

    return resolve


@lru_cache(maxsize=1)
def get_profile_store():
    """Singleton local profile-state store (SQLite).

    Holds user research-universe state (followed / archived / notes) — local,
    in the local profile store. Path overridable via ``ARKSCOPE_PROFILE_DB``; defaults
    to ``<repo>/data/profile_state.db``.
    """
    from src.profile_state import ProfileStateStore

    return ProfileStateStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_card_store():
    """Singleton local store for generated §2 AI card runs (same local SQLite).

    Auto-cached generated cards live alongside profile state in the local DB,
    in the local profile store. Path overridable via ``ARKSCOPE_PROFILE_DB``.
    """
    from src.card_runs import CardRunStore

    return CardRunStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_investor_profile_store():
    """Singleton Investor Profile store (same local SQLite as profile state).

    Track A personalization: durable investor profile + assistant stance live
    in the local profile database. Path overridable via
    ``ARKSCOPE_PROFILE_DB``.
    """
    from src.investor_profile import InvestorProfileStore

    return InvestorProfileStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_investor_calibration_store():
    """Singleton Investor Profile calibration journal/proposal store.

    Track A.5 calibration messages and inert proposals live in the same local
    profile DB as the approved investor profile. Raw calibration text is never
    research history and never a prompt input. Construction only asserts the
    startup-owned v2 schema; it never migrates or reconciles state.
    """
    from src.investor_profile_calibration import CalibrationStore

    return CalibrationStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_portfolio_store():
    """Singleton local portfolio/holdings store (same local SQLite profile DB)."""
    from src.portfolio_state import PortfolioStore

    return PortfolioStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_portfolio_observation_store():
    """Singleton append-only Portfolio capture observation store."""
    from src.portfolio_observations import PortfolioObservationStore

    return PortfolioObservationStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_portfolio_activity_store():
    """Singleton provider-free portfolio activity projection store."""
    from src.portfolio_activity import PortfolioActivityStore

    return PortfolioActivityStore(_local_state_db_path())


@lru_cache(maxsize=1)
def get_portfolio_capture_service():
    """Singleton Portfolio capture coordinator shared by routes and scheduler."""
    from src.portfolio_capture import PortfolioCaptureService
    from src.portfolio_capture_ibkr import read_ibkr_capture

    return PortfolioCaptureService(
        observations=get_portfolio_observation_store(),
        portfolio=get_portfolio_store(),
        reader=read_ibkr_capture,
        provider_readiness=_ibkr_capture_readiness,
        write_allowed=_portfolio_capture_write_allowed,
    )


def _ibkr_capture_readiness():
    from src.data_provider_config import (
        ProviderConfigMissing,
        require_provider_configured,
    )
    from src.portfolio_capture_types import ProviderReadiness

    try:
        require_provider_configured("ibkr", get_data_provider_store())
    except ProviderConfigMissing as exc:
        detail = exc.as_dict()
        return ProviderReadiness(
            configured=False,
            code=detail["code"],
            status=detail["status"],
            provider=detail["provider"],
            field=detail["field"],
        )
    return ProviderReadiness(configured=True)


def _portfolio_capture_write_allowed(action: str, detail: dict) -> bool:
    from src.api.permissions import require_profile_state_write

    require_profile_state_write(action, detail)
    return True


@lru_cache(maxsize=1)
def get_thread_store():
    """Singleton local store for AI 研究 conversation threads/messages (same local
    SQLite). Threads live alongside profile state in the local database."""
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
def get_research_history_store():
    """Singleton read-only Research history projection over local state."""
    from src.research_history import ResearchHistoryStore
    from src.research_runs import ResearchRunStore
    from src.research_threads import ResearchThreadStore

    db_path = _local_state_db_path()
    ResearchThreadStore(db_path)
    ResearchRunStore(db_path)
    return ResearchHistoryStore(db_path)


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
def get_oauth_observation_store():
    """Singleton no-create view over bounded OAuth lifecycle observations."""
    from src.auth_drivers.oauth_status import OAuthObservationStore

    return OAuthObservationStore(_local_state_db_path())


class OAuthAccountSyncService:
    """One bounded account read per credential, shared by concurrent callers."""

    def __init__(
        self,
        *,
        observation_store,
        token_store,
        adapter,
        anthropic_adapter=None,
        wait_timeout_seconds: float = 35.0,
    ):
        self.observation_store = observation_store
        self.token_store = token_store
        self.adapter = adapter
        self.anthropic_adapter = anthropic_adapter
        self.wait_timeout_seconds = wait_timeout_seconds
        self._inflight: dict[str, Future] = {}
        self._inflight_guard = threading.Lock()

    def sync(self, *, credential_id: str, provider: str, auth_mode: str):
        from src.auth_drivers.oauth_status import cached_account_usage

        with self._inflight_guard:
            future = self._inflight.get(credential_id)
            leader = future is None
            if future is None:
                future = Future()
                self._inflight[credential_id] = future

        if not leader:
            try:
                return future.result(timeout=self.wait_timeout_seconds)
            except FutureTimeoutError:
                cached = cached_account_usage(credential_id, self.observation_store)
                return cached.model_copy(
                    update={"sync_status": "failed", "sync_error_code": "sync_busy"}
                )

        try:
            result = self._sync_once(
                credential_id=credential_id,
                provider=provider,
                auth_mode=auth_mode,
            )
            future.set_result(result)
            return result
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self._inflight_guard:
                if self._inflight.get(credential_id) is future:
                    self._inflight.pop(credential_id, None)

    def _sync_once(self, *, credential_id: str, provider: str, auth_mode: str):
        from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError
        from src.auth_drivers.codex_account_usage import CodexAccountUsageError
        from src.auth_drivers.chatgpt_oauth_login import oauth_credential_lock
        from src.auth_drivers.oauth_status import cached_account_usage

        cached = cached_account_usage(credential_id, self.observation_store)
        if provider == "openai" and auth_mode == "chatgpt_oauth":
            account_adapter = self.adapter
        elif (
            provider == "anthropic"
            and auth_mode == "claude_code_oauth"
            and self.anthropic_adapter is not None
        ):
            account_adapter = self.anthropic_adapter
        else:
            return cached.model_copy(
                update={
                    "sync_status": "unsupported",
                    "sync_error_code": "unsupported_auth_mode",
                }
            )
        try:
            record = self.token_store.load(
                provider=provider,
                auth_mode=auth_mode,
                credential_id=credential_id,
            )
        except Exception:  # noqa: BLE001 - token-store diagnostics are secret-adjacent
            return cached.model_copy(
                update={
                    "sync_status": "failed",
                    "sync_error_code": "token_store_unavailable",
                }
            )
        if record is None or not getattr(record, "access_token", None):
            return cached.model_copy(
                update={"sync_status": "failed", "sync_error_code": "missing_token"}
            )
        try:
            observation = account_adapter.read_account_usage(
                credential_id=credential_id,
                record=record,
            )
        except (AnthropicAccountUsageError, CodexAccountUsageError) as exc:
            return cached.model_copy(
                update={"sync_status": "failed", "sync_error_code": exc.code}
            )
        except Exception:  # noqa: BLE001 - never expose raw adapter/storage diagnostics
            return cached.model_copy(
                update={
                    "sync_status": "failed",
                    "sync_error_code": "adapter_unavailable",
                }
            )
        try:
            with oauth_credential_lock(credential_id):
                current = self.token_store.load(
                    provider=provider,
                    auth_mode=auth_mode,
                    credential_id=credential_id,
                )
                if current is None or not self._same_token_generation(record, current):
                    return cached.model_copy(
                        update={
                            "snapshot": None,
                            "sync_status": "failed",
                            "sync_error_code": "credential_changed_during_sync",
                        }
                    )
                snapshot = self.observation_store.record_account_snapshot(
                    credential_id=credential_id,
                    provider=provider,
                    auth_mode=auth_mode,
                    observation=observation,
                )
        except Exception as exc:  # noqa: BLE001 - no lock/storage diagnostic leaves this layer
            error_code = getattr(exc, "error_code", None)
            return cached.model_copy(
                update={
                    "sync_status": "failed",
                    "sync_error_code": (
                        "sync_busy" if error_code == "oauth_lock_busy" else "adapter_unavailable"
                    ),
                }
            )
        return cached.model_copy(
            update={
                "snapshot": snapshot,
                "sync_status": "succeeded",
                "sync_error_code": None,
            }
        )

    @staticmethod
    def _same_token_generation(before, after) -> bool:
        def values(record):
            metadata = getattr(record, "metadata", None) or {}
            return (
                str(getattr(record, "access_token", None) or ""),
                str(getattr(record, "refresh_token", None) or ""),
                str(metadata.get("account_id") or ""),
                str(metadata.get("id_token") or ""),
            )

        return all(
            hmac.compare_digest(left, right)
            for left, right in zip(values(before), values(after))
        )


@lru_cache(maxsize=1)
def get_oauth_account_sync_service():
    """Singleton account sync coordinator; constructing it starts no process."""
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageAdapter
    from src.auth_drivers.codex_account_usage import CodexAccountUsageAdapter

    return OAuthAccountSyncService(
        observation_store=get_oauth_observation_store(),
        token_store=get_oauth_token_store(),
        adapter=CodexAccountUsageAdapter(),
        anthropic_adapter=AnthropicAccountUsageAdapter(),
    )


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
        observation_store=get_oauth_observation_store(),
        account_sync=get_oauth_account_sync_service(),
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
