from __future__ import annotations

import base64
import json
import logging
import sqlite3
from datetime import datetime, timezone


_NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
_PAST = "2026-08-08T10:00:00+00:00"
_FUTURE = "2026-08-08T18:00:00+00:00"


class _TokenStore:
    def __init__(self, records=None, *, error: Exception | None = None):
        self.records = records or {}
        self.error = error

    def load(self, *, provider: str, auth_mode: str, credential_id: str):
        if self.error is not None:
            raise self.error
        return self.records.get((provider, auth_mode, credential_id))

    def save(self, *, provider: str, auth_mode: str, credential_id: str, record):
        if self.error is not None:
            raise self.error
        self.records[(provider, auth_mode, credential_id)] = record


def _access_token_expiring_at(value: str) -> str:
    expiry = int(datetime.fromisoformat(value).timestamp())
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": expiry}).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    return f"h.{payload}.s"


def _clean_provider_env(monkeypatch) -> None:
    monkeypatch.setattr("src.model_credentials.ensure_env_loaded", lambda: None)
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_API_KEYS",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEYS",
    ):
        monkeypatch.delenv(key, raising=False)


def test_expired_chatgpt_token_projects_refresh_required_and_not_available(tmp_path, monkeypatch):
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import StoredTokenRecord
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    row = store.add_oauth_credential(
        provider="openai",
        auth_mode="chatgpt_oauth",
        alias="ChatGPT Plus",
        expires_at=_FUTURE,
    )
    credential_id = f"local:{row.id}"
    tokens = _TokenStore({
        ("openai", "chatgpt_oauth", credential_id): StoredTokenRecord(
            access_token="access-secret",
            refresh_token="refresh-secret",
            expires_at=_PAST,
        )
    })

    cred = provider_credentials(
        store,
        token_store=tokens,
        observation_store=OAuthObservationStore(store.db_path),
        now=_NOW,
    )["openai"][0]

    assert cred.lifecycle_state == "refresh_required"
    assert cred.lifecycle_error_code is None
    assert cred.available is False
    assert cred.expires_at == _PAST


def test_expired_chatgpt_token_without_refresh_projects_reauth_required(tmp_path, monkeypatch):
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import StoredTokenRecord
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    row = store.add_oauth_credential(
        provider="openai", auth_mode="chatgpt_oauth", alias="ChatGPT Plus"
    )
    credential_id = f"local:{row.id}"
    tokens = _TokenStore({
        ("openai", "chatgpt_oauth", credential_id): StoredTokenRecord(
            access_token="access-secret", expires_at=_PAST
        )
    })

    cred = provider_credentials(
        store,
        token_store=tokens,
        observation_store=OAuthObservationStore(store.db_path),
        now=_NOW,
    )["openai"][0]

    assert cred.lifecycle_state == "reauth_required"
    assert cred.lifecycle_error_code == "missing_refresh_token"
    assert cred.available is False


def test_missing_chatgpt_token_projects_reauth_required(tmp_path, monkeypatch):
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    store.add_oauth_credential(
        provider="openai", auth_mode="chatgpt_oauth", alias="ChatGPT Plus"
    )

    cred = provider_credentials(
        store,
        token_store=_TokenStore(),
        observation_store=OAuthObservationStore(store.db_path),
        now=_NOW,
    )["openai"][0]

    assert cred.lifecycle_state == "reauth_required"
    assert cred.lifecycle_error_code == "missing_token"
    assert cred.available is False


def test_unreadable_token_store_projects_unverifiable_without_guessing_reauth(tmp_path, monkeypatch):
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    store.add_oauth_credential(
        provider="openai", auth_mode="chatgpt_oauth", alias="ChatGPT Plus"
    )

    cred = provider_credentials(
        store,
        token_store=_TokenStore(error=RuntimeError("keyring unavailable access-secret")),
        observation_store=OAuthObservationStore(store.db_path),
        now=_NOW,
    )["openai"][0]

    assert cred.lifecycle_state == "unverifiable"
    assert cred.lifecycle_error_code == "token_store_unavailable"
    assert cred.available is False
    assert "access-secret" not in str(cred.model_dump())


def test_retryable_refresh_failure_projects_separately_from_reauth_required(tmp_path, monkeypatch):
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import StoredTokenRecord
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    row = store.add_oauth_credential(
        provider="openai", auth_mode="chatgpt_oauth", alias="ChatGPT Plus"
    )
    credential_id = f"local:{row.id}"
    observations = OAuthObservationStore(store.db_path)
    observations.record_refresh_error(
        credential_id=credential_id,
        provider="openai",
        auth_mode="chatgpt_oauth",
        error_code="transport_error",
        detail="temporary network failure",
        observed_at="2026-08-08T11:59:00+00:00",
    )
    tokens = _TokenStore({
        ("openai", "chatgpt_oauth", credential_id): StoredTokenRecord(
            access_token="access-secret",
            refresh_token="refresh-secret",
            expires_at=_FUTURE,
        )
    })

    cred = provider_credentials(
        store,
        token_store=tokens,
        observation_store=observations,
        now=_NOW,
    )["openai"][0]

    assert cred.lifecycle_state == "refresh_failed_retryable"
    assert cred.lifecycle_error_code == "transport_error"
    assert cred.available is False

    observations.record_refresh_error(
        credential_id=credential_id,
        provider="openai",
        auth_mode="chatgpt_oauth",
        error_code="invalid_grant",
        detail="provider rejected refresh",
        observed_at="2026-08-08T12:00:00+00:00",
    )
    terminal = provider_credentials(
        store,
        token_store=tokens,
        observation_store=observations,
        now=_NOW,
    )["openai"][0]
    assert (terminal.lifecycle_state, terminal.lifecycle_error_code, terminal.available) == (
        "reauth_required",
        "invalid_grant",
        False,
    )


def test_successful_refresh_projection_uses_token_store_expiry_not_credential_db(tmp_path, monkeypatch):
    from src.auth_drivers.chatgpt_oauth_login import refresh_if_needed
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import StoredTokenRecord
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    row = store.add_oauth_credential(
        provider="openai",
        auth_mode="chatgpt_oauth",
        alias="ChatGPT Plus",
        expires_at=_PAST,
    )
    credential_id = f"local:{row.id}"
    observations = OAuthObservationStore(store.db_path)
    tokens = _TokenStore({
        ("openai", "chatgpt_oauth", credential_id): StoredTokenRecord(
            access_token="old-access-secret",
            refresh_token="old-refresh-secret",
            expires_at=_PAST,
        )
    })

    refresh_if_needed(
        credential_id=credential_id,
        token_store=tokens,
        observation_store=observations,
        now=_NOW,
        refresh=lambda **_kwargs: {
            "access_token": _access_token_expiring_at(_FUTURE),
            "refresh_token": "new-refresh-secret",
        },
    )

    cred = provider_credentials(
        store,
        token_store=tokens,
        observation_store=observations,
        now=_NOW,
    )["openai"][0]

    assert cred.lifecycle_state == "ready"
    assert cred.lifecycle_error_code is None
    assert cred.available is True
    assert cred.expires_at == _FUTURE
    assert store.get(credential_id).expires_at == _PAST
    status = observations.read_refresh_status(credential_id)
    assert status is not None
    assert status.last_refresh_attempt_at == _NOW.isoformat()
    assert status.last_refresh_success_at == _NOW.isoformat()


def test_api_key_and_environment_availability_remain_unchanged(tmp_path, monkeypatch):
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-environment-key")
    store = CredentialStore(tmp_path / "profile.db")
    local = store.add(
        provider="openai",
        auth_type="api_key",
        alias="OpenAI key",
        secret="sk-openai-local-key",
    )

    inventory = provider_credentials(store)
    local_view = next(c for c in inventory["openai"] if c.id == f"local:{local.id}")
    env_view = next(c for c in inventory["anthropic"] if c.id == "anthropic:ANTHROPIC_API_KEY")

    assert (local_view.available, local_view.can_discover_models, local_view.can_test_models) == (
        True,
        True,
        True,
    )
    assert (env_view.available, env_view.can_discover_models, env_view.can_test_models) == (
        True,
        True,
        True,
    )
    assert local_view.lifecycle_state is None
    assert env_view.lifecycle_state is None


def test_refresh_telemetry_keeps_only_latest_bounded_nonsecret_witness(tmp_path):
    from src.auth_drivers.oauth_status import MAX_REFRESH_DETAIL_LENGTH, OAuthObservationStore

    missing = tmp_path / "missing" / "profile.db"
    no_create = OAuthObservationStore(missing)
    assert no_create.read_refresh_status("local:1") is None
    assert not missing.parent.exists()

    db_path = tmp_path / "profile.db"
    observations = OAuthObservationStore(db_path)
    observations.record_refresh_attempt(
        credential_id="local:7",
        provider="openai",
        auth_mode="chatgpt_oauth",
        observed_at="2026-08-08T11:55:00+00:00",
    )
    observations.record_refresh_error(
        credential_id="local:7",
        provider="openai",
        auth_mode="chatgpt_oauth",
        error_code="transport_error",
        detail="access_token=SECRET-ACCESS account_id=RAW-ACCOUNT " + "x" * 1000,
        observed_at="2026-08-08T11:56:00+00:00",
    )
    observations.record_refresh_error(
        credential_id="local:7",
        provider="openai",
        auth_mode="chatgpt_oauth",
        error_code="protocol_incompatible",
        detail="latest bounded detail",
        observed_at="2026-08-08T11:57:00+00:00",
    )

    status = observations.read_refresh_status("local:7")
    assert status is not None
    assert status.last_refresh_attempt_at == "2026-08-08T11:55:00+00:00"
    assert status.last_refresh_error_code == "protocol_incompatible"
    assert status.last_refresh_error_detail == "latest bounded detail"
    assert len(status.last_refresh_error_detail or "") <= MAX_REFRESH_DETAIL_LENGTH
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM oauth_refresh_status").fetchone() == (1,)
        stored = " ".join(str(value) for value in conn.execute(
            "SELECT * FROM oauth_refresh_status WHERE credential_id = ?", ("local:7",)
        ).fetchone())
    finally:
        conn.close()
    assert "SECRET-ACCESS" not in stored
    assert "RAW-ACCOUNT" not in stored


def test_chatgpt_db_expiry_is_ignored_while_claude_manual_expiry_remains_owned(tmp_path, monkeypatch):
    import pytest

    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import StoredTokenRecord
    from src.model_credentials import CredentialStore, provider_credentials

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    chatgpt = store.add_oauth_credential(
        provider="openai",
        auth_mode="chatgpt_oauth",
        alias="ChatGPT Plus",
        expires_at=_FUTURE,
    )
    claude = store.add_oauth_credential(
        provider="anthropic",
        auth_mode="claude_code_oauth",
        alias="Claude Max",
        expires_at=_FUTURE,
    )
    chatgpt_id = f"local:{chatgpt.id}"
    claude_id = f"local:{claude.id}"
    tokens = _TokenStore({
        ("openai", "chatgpt_oauth", chatgpt_id): StoredTokenRecord(
            access_token="chatgpt-access",
            refresh_token="chatgpt-refresh",
            expires_at=_PAST,
        ),
        ("anthropic", "claude_code_oauth", claude_id): StoredTokenRecord(
            access_token="claude-access",
            expires_at=_PAST,
        ),
    })

    inventory = provider_credentials(
        store,
        token_store=tokens,
        observation_store=OAuthObservationStore(store.db_path),
        now=_NOW,
    )
    chatgpt_view = next(c for c in inventory["openai"] if c.id == chatgpt_id)
    claude_view = next(c for c in inventory["anthropic"] if c.id == claude_id)

    assert (chatgpt_view.expires_at, chatgpt_view.lifecycle_state) == (
        _PAST,
        "refresh_required",
    )
    assert (claude_view.expires_at, claude_view.lifecycle_state, claude_view.available) == (
        _FUTURE,
        "ready",
        True,
    )
    with pytest.raises(ValueError, match="owned by the token store"):
        store.update(chatgpt_id, expires_at="2027-01-01T00:00:00+00:00")
    assert store.get(chatgpt_id).expires_at == _FUTURE


def test_lifecycle_api_payload_and_logs_exclude_secrets_and_raw_account_ids(
    tmp_path, monkeypatch, caplog
):
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import StoredTokenRecord
    from src.api.routes.config_routes import list_credentials
    from src.model_credentials import CredentialStore

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    row = store.add_oauth_credential(
        provider="openai",
        auth_mode="chatgpt_oauth",
        alias="ChatGPT Plus",
        account_label="Plus",
    )
    credential_id = f"local:{row.id}"
    observations = OAuthObservationStore(store.db_path)
    observations.record_refresh_error(
        credential_id=credential_id,
        provider="openai",
        auth_mode="chatgpt_oauth",
        error_code="transport_error",
        detail="Bearer ACCESS-SENTINEL account_id=ACCOUNT-SENTINEL refresh_token=REFRESH-SENTINEL",
        observed_at="2026-08-08T11:59:00+00:00",
    )
    tokens = _TokenStore({
        ("openai", "chatgpt_oauth", credential_id): StoredTokenRecord(
            access_token="ACCESS-SENTINEL",
            refresh_token="REFRESH-SENTINEL",
            expires_at="2000-01-01T00:00:00+00:00",
            metadata={"account_id": "ACCOUNT-SENTINEL", "id_token": "ID-SENTINEL"},
        )
    })

    with caplog.at_level(logging.DEBUG):
        payload = list_credentials(
            store=store,
            token_store=tokens,
            observation_store=observations,
        )
    rendered = str(payload) + caplog.text

    assert payload["credentials"]["openai"][0]["lifecycle_state"] == "refresh_failed_retryable"
    for secret in ("ACCESS-SENTINEL", "REFRESH-SENTINEL", "ACCOUNT-SENTINEL", "ID-SENTINEL"):
        assert secret not in rendered


def test_refreshable_active_oauth_remains_runtime_resolvable_while_not_available(tmp_path, monkeypatch):
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.auth_drivers.token_store import StoredTokenRecord
    from src.model_credentials import CredentialStore, provider_credentials, resolve_active_credential

    _clean_provider_env(monkeypatch)
    store = CredentialStore(tmp_path / "profile.db")
    row = store.add_oauth_credential(
        provider="openai",
        auth_mode="chatgpt_oauth",
        alias="ChatGPT Plus",
        make_active=True,
    )
    credential_id = f"local:{row.id}"
    observations = OAuthObservationStore(store.db_path)
    tokens = _TokenStore({
        ("openai", "chatgpt_oauth", credential_id): StoredTokenRecord(
            access_token="access-secret",
            refresh_token="refresh-secret",
            expires_at=_PAST,
        )
    })

    credential = provider_credentials(
        store,
        token_store=tokens,
        observation_store=observations,
        now=_NOW,
    )["openai"][0]
    resolved = resolve_active_credential(
        "openai",
        store,
        token_store=tokens,
        observation_store=observations,
        now=_NOW,
    )

    assert credential.lifecycle_state == "refresh_required"
    assert credential.available is False
    assert resolved is not None
    assert (resolved.credential_id, resolved.auth_mode, resolved.secret_fingerprint) == (
        credential_id,
        "chatgpt_oauth",
        "oauth",
    )
