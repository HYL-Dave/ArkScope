"""Provider credential status, model discovery, and live model tests.

Secrets stay outside the UI. This module reads API keys from the current
environment/config/.env, returns only masked labels, and only uses API-key
credentials for live discovery/tests. OAuth/setup-token credential types are
represented so the Settings UI can model them, but they are not treated as
direct API credentials until their provider-specific flow is implemented.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel

from src.env_keys import ensure_env_loaded, unquote_env_value
from src.model_routing import MODEL_CATALOG, Provider

CredentialAuthType = Literal["api_key", "api_key_pool", "chatgpt_oauth", "claude_code_oauth"]
DiscoveryStatus = Literal["ok", "missing_credential", "unsupported", "error"]

# Explicit modes (the target). Legacy generic values are normalized to these on
# read AND write (S1); they are NOT a stored long-term form.
_VALID_AUTH_MODES = frozenset({"api_key", "api_key_pool", "chatgpt_oauth", "claude_code_oauth"})


def _normalize_auth_type(auth_type: str, provider: str) -> str:
    """Map legacy/generic auth_type → an explicit mode (do NOT conflate the two
    OpenAI OAuth realities or the Anthropic setup-token path into a bare 'oauth').

    - ``setup_token`` → ``claude_code_oauth`` (Claude Agent SDK / claude -p).
    - ``oauth`` → provider-specific: anthropic ⇒ ``claude_code_oauth``,
      otherwise ⇒ ``chatgpt_oauth`` (the in-app ChatGPT-backend OAuth path).
    - explicit modes pass through unchanged.
    """
    if auth_type == "setup_token":
        return "claude_code_oauth"
    if auth_type == "oauth":
        return "claude_code_oauth" if provider == "anthropic" else "chatgpt_oauth"
    return auth_type


class ProviderCredential(BaseModel):
    id: str
    provider: Provider
    auth_type: CredentialAuthType
    label: str
    source: str
    available: bool
    masked: str | None = None
    active: bool = False
    editable: bool = False
    can_discover_models: bool = False
    can_test_models: bool = False
    notes: str = ""


class DiscoveredModel(BaseModel):
    id: str
    provider: Provider
    label: str
    source: Literal["provider_api", "seed"]


class ModelDiscoveryResult(BaseModel):
    provider: Provider
    credential_id: str | None
    status: DiscoveryStatus
    models: list[DiscoveredModel]
    error: str | None = None
    source_url: str | None = None


class ModelTestResult(BaseModel):
    provider: Provider
    credential_id: str | None
    model: str
    effort: str
    status: Literal["ok", "missing_credential", "error"]
    latency_ms: int | None = None
    error: str | None = None
    warning: str | None = None
    fallback_effort: str | None = None


class _ResolvedCredential(BaseModel):
    id: str
    provider: Provider
    auth_type: CredentialAuthType
    secret: str | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_credentials (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    auth_type  TEXT NOT NULL DEFAULT 'api_key',
    alias      TEXT NOT NULL,
    secret     TEXT,
    active     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at    TEXT,
    account_label TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_credentials_provider ON llm_credentials(provider);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_credential_db_path() -> str:
    return os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        Path(__file__).resolve().parents[1] / "data" / "profile_state.db"
    )


@dataclass
class StoredCredential:
    id: int
    provider: Provider
    auth_type: CredentialAuthType
    alias: str
    secret: str | None  # NULL for OAuth rows — the token lives in the token-store
    active: bool
    created_at: str
    updated_at: str
    # OAuth metadata (nullable; redacted display only — the live OAuth token does
    # NOT live in `secret` long-term, it goes to the token-store, S1-piece-2).
    expires_at: str | None = None
    account_label: str | None = None


class CredentialStore:
    """Local SQLite credential store.

    Secrets are intentionally never returned by API responses. This is a local
    desktop-app store, not an encrypted vault; a future pass can swap the secret
    column for OS keyring / encrypted storage without changing the Settings API
    shape.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or _default_credential_db_path())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")  # wait out brief write locks
        return conn

    def _ensure_schema(self) -> None:
        with self._write_lock, self._connect() as conn:
            # WAL is an optimization; it errors immediately if another
            # connection is open during concurrent first construction.
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(_SCHEMA)
            # Idempotent migration: add expires_at/account_label to a pre-existing
            # table (tolerant of the concurrent-first-construct race).
            cols = {r[1] for r in conn.execute("PRAGMA table_info(llm_credentials)").fetchall()}
            for col in ("expires_at", "account_label"):
                if col not in cols:
                    try:
                        conn.execute(f"ALTER TABLE llm_credentials ADD COLUMN {col} TEXT")
                    except sqlite3.OperationalError:
                        pass
            # Relax secret NOT NULL → nullable (OAuth rows store the real token in
            # the token-store, not here). SQLite can't ALTER a column constraint,
            # so rebuild only when an existing table still has secret NOT NULL.
            info = conn.execute("PRAGMA table_info(llm_credentials)").fetchall()
            secret_notnull = any(r[1] == "secret" and r[3] == 1 for r in info)
            if secret_notnull:
                conn.executescript(
                    """
                    CREATE TABLE llm_credentials_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT NOT NULL,
                        auth_type TEXT NOT NULL DEFAULT 'api_key',
                        alias TEXT NOT NULL,
                        secret TEXT,
                        active INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        expires_at TEXT,
                        account_label TEXT
                    );
                    INSERT INTO llm_credentials_new
                        (id, provider, auth_type, alias, secret, active, created_at, updated_at, expires_at, account_label)
                        SELECT id, provider, auth_type, alias, secret, active, created_at, updated_at, expires_at, account_label
                        FROM llm_credentials;
                    DROP TABLE llm_credentials;
                    ALTER TABLE llm_credentials_new RENAME TO llm_credentials;
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_credentials_provider ON llm_credentials(provider)")
            conn.commit()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _row(row: sqlite3.Row) -> StoredCredential:
        keys = row.keys()
        return StoredCredential(
            id=int(row["id"]),
            provider=row["provider"],
            # legacy oauth/setup_token rows normalize to explicit modes on read
            auth_type=_normalize_auth_type(row["auth_type"], row["provider"]),
            alias=row["alias"],
            secret=row["secret"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"] if "expires_at" in keys else None,
            account_label=row["account_label"] if "account_label" in keys else None,
        )

    def list(self, provider: Provider | None = None) -> list[StoredCredential]:
        where = "WHERE provider = ?" if provider else ""
        params = (provider,) if provider else ()
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM llm_credentials {where} ORDER BY provider, active DESC, id",
                params,
            ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, credential_id: str) -> StoredCredential | None:
        local_id = _parse_local_id(credential_id)
        if local_id is None:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM llm_credentials WHERE id = ?", (local_id,)).fetchone()
        return self._row(row) if row else None

    def add(
        self,
        *,
        provider: Provider,
        auth_type: CredentialAuthType,
        alias: str,
        secret: str,
        make_active: bool = True,
        expires_at: str | None = None,
        account_label: str | None = None,
    ) -> StoredCredential:
        # add() stores a single DIRECT API key ONLY. OAuth/setup-token modes must
        # go through add_oauth_credential() so a token can never land in
        # llm_credentials.secret (it belongs in the token-store). api_key_pool is
        # an env-compat READ representation only — a STORED local:N pool row is
        # unresolvable (_resolve_api_credential indexes an env var off the id),
        # so pool keys must be stored as individual api_key rows.
        auth_type = _normalize_auth_type(str(auth_type), provider)  # type: ignore[assignment]
        if auth_type == "api_key_pool":
            raise ValueError(
                "add() does not store api_key_pool rows; store each pooled key as "
                "its own api_key credential (the pool is an env-only read view)"
            )
        if auth_type != "api_key":
            raise ValueError(
                f"add() is for direct API keys; use add_oauth_credential() for {auth_type}"
            )
        alias = alias.strip() or f"{provider} key"
        secret = secret.strip()
        if not secret:
            raise ValueError("secret is required")
        now = _now()
        with self._write_lock, self._connect() as conn:
            if make_active:
                conn.execute("UPDATE llm_credentials SET active = 0 WHERE provider = ?", (provider,))
            cur = conn.execute(
                "INSERT INTO llm_credentials "
                "(provider, auth_type, alias, secret, active, created_at, updated_at, expires_at, account_label) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (provider, auth_type, alias, secret, 1 if make_active else 0, now, now, expires_at, account_label),
            )
            conn.commit()
            new_id = cur.lastrowid
        got = self.get(f"local:{new_id}")
        assert got is not None
        return got

    def add_oauth_credential(
        self,
        *,
        provider: Provider,
        auth_mode: CredentialAuthType,
        alias: str,
        make_active: bool = True,
        expires_at: str | None = None,
        account_label: str | None = None,
    ) -> StoredCredential:
        """Create an OAuth credential row carrying ONLY metadata — secret stays
        NULL. The real token lives in the token-store keyed by the returned
        credential_id (never in this DB). For chatgpt_oauth / claude_code_oauth."""
        auth_mode = _normalize_auth_type(str(auth_mode), provider)  # type: ignore[assignment]
        if auth_mode not in ("chatgpt_oauth", "claude_code_oauth"):
            raise ValueError(f"add_oauth_credential requires an OAuth mode, got: {auth_mode}")
        # Provider-specific matrix (matches the driver factory): reject a
        # provider's wrong OAuth mode rather than create an invalid row.
        _expected = {"chatgpt_oauth": "openai", "claude_code_oauth": "anthropic"}[auth_mode]
        if provider != _expected:
            raise ValueError(f"auth_mode {auth_mode!r} is not valid for provider {provider!r} (expected {_expected!r})")
        alias = alias.strip() or f"{provider} {auth_mode}"
        now = _now()
        with self._write_lock, self._connect() as conn:
            if make_active:
                conn.execute("UPDATE llm_credentials SET active = 0 WHERE provider = ?", (provider,))
            cur = conn.execute(
                "INSERT INTO llm_credentials "
                "(provider, auth_type, alias, secret, active, created_at, updated_at, expires_at, account_label) "
                "VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)",
                (provider, auth_mode, alias, 1 if make_active else 0, now, now, expires_at, account_label),
            )
            conn.commit()
            new_id = cur.lastrowid
        got = self.get(f"local:{new_id}")
        assert got is not None
        return got

    def update(
        self,
        credential_id: str,
        *,
        alias: str | None = None,
        secret: str | None = None,
        active: bool | None = None,
    ) -> StoredCredential | None:
        existing = self.get(credential_id)
        if not existing:
            return None
        # An OAuth row's token lives in the token-store, never here — reject any
        # attempt to write a secret onto it (alias/active updates are fine).
        if secret is not None and existing.auth_type not in ("api_key", "api_key_pool"):
            raise ValueError(
                f"cannot set secret on a {existing.auth_type} credential; "
                "its token lives in the token-store"
            )
        now = _now()
        with self._write_lock, self._connect() as conn:
            if active is True:
                conn.execute(
                    "UPDATE llm_credentials SET active = 0 WHERE provider = ?",
                    (existing.provider,),
                )
            sets = ["updated_at = ?"]
            params: list = [now]
            if alias is not None:
                clean_alias = alias.strip()
                if clean_alias:
                    sets.append("alias = ?")
                    params.append(clean_alias)
            if secret is not None:
                clean_secret = secret.strip()
                if clean_secret:
                    sets.append("secret = ?")
                    params.append(clean_secret)
            if active is not None:
                sets.append("active = ?")
                params.append(1 if active else 0)
            params.append(existing.id)
            conn.execute(f"UPDATE llm_credentials SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
        return self.get(credential_id)

    def delete(self, credential_id: str) -> bool:
        local_id = _parse_local_id(credential_id)
        if local_id is None:
            return False
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM llm_credentials WHERE id = ?", (local_id,))
            conn.commit()
            return cur.rowcount > 0


def _mask_secret(value: str) -> str:
    if len(value) <= 10:
        return "••••"
    return f"{value[:4]}…{value[-4:]}"


def _parse_local_id(credential_id: str | None) -> int | None:
    if not credential_id or not credential_id.startswith("local:"):
        return None
    try:
        return int(credential_id.split(":", 1)[1])
    except ValueError:
        return None


def valid_credential_id(credential_id: str | None) -> bool:
    """A local credential id must be ``local:<int>``. Use this (not a thread-id
    rule) to validate a credential id at the route boundary."""
    return _parse_local_id(credential_id) is not None


def _split_key_pool(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _seed_models(provider: Provider) -> list[DiscoveredModel]:
    return [
        DiscoveredModel(id=m.id, provider=provider, label=m.label, source="seed")
        for m in MODEL_CATALOG
        if m.provider == provider
    ]


def looks_like_effort_error(exc: Exception) -> bool:
    """Heuristic for provider errors caused by an unsupported effort parameter."""
    text = str(exc).lower()
    needles = (
        "effort",
        "reasoning_effort",
        "output_config",
        "thinking",
        "unsupported parameter",
        "unknown parameter",
        "invalid parameter",
        "extra inputs are not permitted",
    )
    return any(needle in text for needle in needles)


def provider_credentials(store: CredentialStore | None = None) -> dict[Provider, list[ProviderCredential]]:
    """Return masked credential inventory grouped by provider."""
    ensure_env_loaded()
    store = store or CredentialStore()
    out: dict[Provider, list[ProviderCredential]] = {"anthropic": [], "openai": []}

    local_by_provider: dict[Provider, list[ProviderCredential]] = {"anthropic": [], "openai": []}
    for row in store.list():
        can_use = row.auth_type in ("api_key", "api_key_pool")
        local_by_provider[row.provider].append(
            ProviderCredential(
                id=f"local:{row.id}",
                provider=row.provider,
                auth_type=row.auth_type,
                label=row.alias,
                source="profile_state.db",
                available=True,
                masked=_mask_secret(row.secret) if row.secret else None,  # OAuth rows have no secret here
                active=row.active,
                editable=True,
                can_discover_models=can_use,
                can_test_models=can_use,
                notes=(
                    "Local Settings credential. Stored in the ignored local SQLite profile DB."
                    if can_use
                    else "Stored for future auth flow support; not used as a direct API key in v0."
                ),
            )
        )
    out["anthropic"].extend(local_by_provider["anthropic"])
    out["openai"].extend(local_by_provider["openai"])

    def add_api_key(provider: Provider, env_name: str, label: str) -> None:
        value = os.environ.get(env_name, "").strip()
        has_local_active = any(c.active for c in local_by_provider[provider])
        out[provider].append(
            ProviderCredential(
                id=f"{provider}:{env_name}",
                provider=provider,
                auth_type="api_key",
                label=label,
                source=env_name,
                available=bool(value),
                masked=_mask_secret(value) if value else None,
                active=bool(value) and not has_local_active and not any(
                    c.active and c.provider == provider for c in out[provider]
                ),
                editable=False,
                can_discover_models=bool(value),
                can_test_models=bool(value),
                notes="Direct provider API key from environment/config/.env.",
            )
        )

    def add_key_pool(provider: Provider, env_name: str) -> None:
        for idx, value in enumerate(_split_key_pool(os.environ.get(env_name))):
            has_local_active = any(c.active for c in local_by_provider[provider])
            out[provider].append(
                ProviderCredential(
                    id=f"{provider}:{env_name}:{idx}",
                    provider=provider,
                    auth_type="api_key_pool",
                    label=f"{env_name}[{idx}]",
                    source=env_name,
                    available=True,
                    masked=_mask_secret(value),
                    active=not has_local_active and not any(
                        c.active and c.provider == provider for c in out[provider]
                    ),
                    editable=False,
                    can_discover_models=True,
                    can_test_models=True,
                    notes="Direct provider API key from a comma-separated key pool.",
                )
            )

    add_api_key("openai", "OPENAI_API_KEY", "OpenAI API key")
    add_key_pool("openai", "OPENAI_API_KEYS")
    add_api_key("anthropic", "ANTHROPIC_API_KEY", "Anthropic API key")
    add_key_pool("anthropic", "ANTHROPIC_API_KEYS")

    # Lone S3 signpost: OpenAI ChatGPT-OAuth has no import route yet, so — unlike
    # the Claude setup-token, which now lands as an import-created local: row via
    # the token-store — there is no live local: row to supersede it. The two
    # Anthropic env placeholders (ANTHROPIC_OAUTH_TOKEN / ANTHROPIC_SETUP_TOKEN)
    # were removed: they advertised env vars nothing reads while the real Claude
    # path is the token-store import (see add_oauth_credential / import route).
    for provider, env_name, auth_type, notes in [
        (
            "openai",
            "OPENAI_OAUTH_TOKEN",
            "chatgpt_oauth",
            "Planned ChatGPT-OAuth (S3); not read as a credential yet.",
        ),
    ]:
        value = os.environ.get(env_name, "").strip()
        out[provider].append(
            ProviderCredential(
                id=f"{provider}:{env_name}",
                provider=provider,  # type: ignore[arg-type]
                auth_type=auth_type,  # type: ignore[arg-type]
                label=env_name,
                source=env_name,
                available=bool(value),
                masked=_mask_secret(value) if value else None,
                active=False,
                editable=False,
                can_discover_models=False,
                can_test_models=False,
                notes=notes,
            )
        )

    return out


# env vars the importer reads, per provider: (single key, comma-pool). OAuth/
# setup-token env names are intentionally excluded — those are not api_key rows.
_IMPORT_ENV_KEYS: list[tuple[Provider, str, str, str]] = [
    ("openai", "OPENAI_API_KEY", "OPENAI_API_KEYS", "OpenAI"),
    ("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS", "Anthropic"),
]


def import_env_credentials(
    store: CredentialStore | None = None,
    *,
    env: dict[str, str] | None = None,
) -> dict[Provider, dict]:
    """Import api_key credentials from a .env-style mapping into named DB rows.

    For each provider, gather the single key (e.g. ``OPENAI_API_KEY``) FIRST then
    the comma-pool (``OPENAI_API_KEYS``), single-pass dedup by EXACT secret (first
    occurrence wins its alias), and ADD one ``api_key`` row per distinct secret —
    never a positional ``[idx]`` label, never a stored ``api_key_pool`` row. The
    single key gets the alias ``"<Provider> primary"``; surviving pool keys get
    ``"<Provider> pool N"`` in encounter order.

    Additive + idempotent: a secret already present for the provider is SKIPPED
    (row count and any user-edited alias/active are left untouched). At most ONE
    row per provider is set active, and only if the provider has no active row
    yet (existing active is never stolen).

    Returns a per-provider summary of {added: [aliases], skipped: int,
    activated: alias|None} — labels and counts only, NEVER any secret value.
    """
    if env is None:
        ensure_env_loaded()
        env = dict(os.environ)
    store = store or CredentialStore()

    existing = store.list()
    summary: dict[Provider, dict] = {}

    for provider, single_var, pool_var, label in _IMPORT_ENV_KEYS:
        # candidates in priority order: single var first, then pool entries.
        candidates: list[tuple[str, str | None]] = []
        single = unquote_env_value(env.get(single_var, ""))
        if single:
            candidates.append((single, f"{label} primary"))
        for sec in _split_key_pool(env.get(pool_var)):
            candidates.append((sec, None))  # alias assigned after dedup

        # single-pass dedup by exact secret — first occurrence keeps its alias.
        deduped: dict[str, str | None] = {}
        for sec, alias in candidates:
            if sec not in deduped:
                deduped[sec] = alias
        pool_n = 0
        for sec, alias in list(deduped.items()):
            if alias is None:
                pool_n += 1
                deduped[sec] = f"{label} pool {pool_n}"

        present = {c.secret for c in existing if c.provider == provider}
        has_active = any(c.active for c in existing if c.provider == provider)
        added: list[str] = []
        skipped = 0
        activated: str | None = None
        for sec, alias in deduped.items():
            if sec in present:
                skipped += 1
                continue
            make_active = not has_active and activated is None
            store.add(
                provider=provider,
                auth_type="api_key",
                alias=alias,
                secret=sec,
                make_active=make_active,
            )
            added.append(alias)
            if make_active:
                activated = alias
        summary[provider] = {"added": added, "skipped": skipped, "activated": activated}

    return summary


def _resolve_api_credential(
    provider: Provider,
    credential_id: str | None,
    store: CredentialStore | None = None,
) -> _ResolvedCredential | None:
    ensure_env_loaded()
    store = store or CredentialStore()
    local = store.get(credential_id) if credential_id else None
    if local and local.provider == provider and local.auth_type in ("api_key", "api_key_pool"):
        return _ResolvedCredential(
            id=f"local:{local.id}",
            provider=provider,
            auth_type=local.auth_type,
            secret=local.secret,
        )

    creds = provider_credentials(store)[provider]
    usable = [c for c in creds if c.available and c.can_test_models]
    selected = (
        next((c for c in usable if c.id == credential_id), None)
        if credential_id
        else next((c for c in usable if c.active), None) or (usable[0] if usable else None)
    )
    if not selected:
        return None

    if selected.auth_type == "api_key":
        secret = os.environ.get(selected.source, "").strip()
    elif selected.auth_type == "api_key_pool":
        try:
            idx = int(selected.id.rsplit(":", 1)[-1])
        except ValueError:
            return None
        secret = _split_key_pool(os.environ.get(selected.source))[idx]
    else:
        return None
    return _ResolvedCredential(
        id=selected.id,
        provider=provider,
        auth_type=selected.auth_type,
        secret=secret,
    )


def discover_models(
    provider: Provider,
    credential_id: str | None = None,
    store: CredentialStore | None = None,
) -> ModelDiscoveryResult:
    """Discover models for a provider/key when supported; fall back to seeds."""
    cred = _resolve_api_credential(provider, credential_id, store)
    if not cred or not cred.secret:
        return ModelDiscoveryResult(
            provider=provider,
            credential_id=credential_id,
            status="missing_credential",
            models=_seed_models(provider),
            error="No direct API-key credential is available for model discovery.",
        )

    try:
        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=cred.secret, timeout=15)
            data = client.models.list()
            models = [
                DiscoveredModel(id=item.id, provider="openai", label=item.id, source="provider_api")
                for item in data.data
            ]
            return ModelDiscoveryResult(
                provider=provider,
                credential_id=cred.id,
                status="ok",
                models=sorted(models, key=lambda m: m.id),
                source_url="https://platform.openai.com/docs/api-reference/models/list",
            )
        headers = {"x-api-key": cred.secret, "anthropic-version": "2023-06-01"}
        resp = httpx.get("https://api.anthropic.com/v1/models", headers=headers, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("data", [])
        models = [
            DiscoveredModel(
                id=item.get("id", ""),
                provider="anthropic",
                label=item.get("display_name") or item.get("id", ""),
                source="provider_api",
            )
            for item in items
            if item.get("id")
        ]
        return ModelDiscoveryResult(
            provider=provider,
            credential_id=cred.id,
            status="ok",
            models=sorted(models, key=lambda m: m.id),
            source_url="https://docs.anthropic.com/en/api/models-list",
        )
    except Exception as exc:  # pragma: no cover - live provider variability
        return ModelDiscoveryResult(
            provider=provider,
            credential_id=cred.id,
            status="error",
            models=_seed_models(provider),
            error=str(exc),
        )


def test_model(
    provider: Provider,
    model: str,
    effort: str = "default",
    credential_id: str | None = None,
    store: CredentialStore | None = None,
) -> ModelTestResult:
    """Run a tiny paid provider call to verify credential/model/effort access."""
    cred = _resolve_api_credential(provider, credential_id, store)
    if not cred or not cred.secret:
        return ModelTestResult(
            provider=provider,
            credential_id=credential_id,
            model=model,
            effort=effort,
            status="missing_credential",
            error="No direct API-key credential is available for this test.",
        )

    started = time.perf_counter()

    def ok_result(*, warning: str | None = None, fallback_effort: str | None = None) -> ModelTestResult:
        return ModelTestResult(
            provider=provider,
            credential_id=cred.id,
            model=model,
            effort=effort,
            status="ok",
            latency_ms=round((time.perf_counter() - started) * 1000),
            warning=warning,
            fallback_effort=fallback_effort,
        )

    def run_once(selected_effort: str) -> None:
        if provider == "openai":
            from openai import OpenAI

            kwargs = {}
            if selected_effort != "default":
                kwargs["reasoning_effort"] = selected_effort
            client = OpenAI(api_key=cred.secret, timeout=30)
            client.chat.completions.create(
                model=model,
                max_completion_tokens=16,
                messages=[{"role": "user", "content": "Reply with OK."}],
                **kwargs,
            )
            return

        from anthropic import Anthropic

        kwargs = {}
        if selected_effort != "default":
            kwargs["output_config"] = {"effort": selected_effort}
        client = Anthropic(api_key=cred.secret, timeout=30)
        client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with OK."}],
            **kwargs,
        )

    try:
        run_once(effort)
        return ok_result()
    except Exception as exc:  # pragma: no cover - live provider variability
        if effort != "default" and looks_like_effort_error(exc):
            try:
                run_once("default")
                return ok_result(
                    warning=(
                        f"Provider rejected effort '{effort}', but the model worked "
                        "after falling back to provider default."
                    ),
                    fallback_effort="default",
                )
            except Exception as fallback_exc:
                exc = fallback_exc
        return ModelTestResult(
            provider=provider,
            credential_id=cred.id,
            model=model,
            effort=effort,
            status="error",
            latency_ms=round((time.perf_counter() - started) * 1000),
            error=str(exc),
        )
