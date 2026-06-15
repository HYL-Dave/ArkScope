"""OAuth token storage — S1 piece-2 (skeleton; no login/refresh, no wiring).

The home for OAuth/subscription tokens. The credential row (llm_credentials)
stores only METADATA (auth_type, alias, expires_at, account_label); the real
token lives HERE, keyed by (provider, auth_mode, credential_id) — never in
CredentialStore.secret.

Keyring-first: use the OS keyring when a usable backend exists, else fall back to
a plaintext 0600 dev file — and the fallback is ALWAYS visible in status()
(`backend: "plaintext_dev"`) so the UI never implies secure storage when it isn't.
status() is redacted: it NEVER returns access_token / refresh_token.

Design: docs/design/LLM_AUTH_DRIVER_PLAN.md §7. This module is independent of
CredentialStore and the agent loops (api_key behavior is untouched).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class StoredTokenRecord:
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None  # ISO; None for non-expiring (e.g. setup-token status)
    plan_type: Optional[str] = None
    account_label: Optional[str] = None  # redacted display only (NOT raw email/PII)
    metadata: dict = field(default_factory=dict)  # provider extras (non-display)


def _token_key(provider: str, auth_mode: str, credential_id: str) -> str:
    return f"{provider}:{auth_mode}:{credential_id}"


def _redacted_status(record: Optional[StoredTokenRecord], backend: str) -> dict:
    """Status with NO secret material — only login-state + non-secret display."""
    if record is None:
        return {"logged_in": False, "backend": backend, "expires_at": None, "plan_type": None, "account_label": None}
    return {
        "logged_in": True,
        "backend": backend,
        "expires_at": record.expires_at,
        "plan_type": record.plan_type,
        "account_label": record.account_label,
    }


def _rec_to_json(r: StoredTokenRecord) -> str:
    return json.dumps(asdict(r))


def _rec_from_obj(d: dict) -> StoredTokenRecord:
    return StoredTokenRecord(
        access_token=d["access_token"],
        refresh_token=d.get("refresh_token"),
        expires_at=d.get("expires_at"),
        plan_type=d.get("plan_type"),
        account_label=d.get("account_label"),
        metadata=d.get("metadata") or {},
    )


class PlaintextTokenStore:
    """Dev fallback: a single 0600 JSON file. NOT secure storage — flagged in status."""

    backend = "plaintext_dev"

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_all(self, data: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def save(self, *, provider: str, auth_mode: str, credential_id: str, record: StoredTokenRecord) -> None:
        data = self._read_all()
        data[_token_key(provider, auth_mode, credential_id)] = asdict(record)
        self._write_all(data)

    def load(self, *, provider: str, auth_mode: str, credential_id: str) -> Optional[StoredTokenRecord]:
        raw = self._read_all().get(_token_key(provider, auth_mode, credential_id))
        return _rec_from_obj(raw) if raw else None

    def delete(self, *, provider: str, auth_mode: str, credential_id: str) -> bool:
        data = self._read_all()
        key = _token_key(provider, auth_mode, credential_id)
        if key in data:
            del data[key]
            self._write_all(data)
            return True
        return False

    def status(self, *, provider: str, auth_mode: str, credential_id: str) -> dict:
        return _redacted_status(self.load(provider=provider, auth_mode=auth_mode, credential_id=credential_id), self.backend)


# Thin keyring wrappers at module level so tests can monkeypatch them without a
# live Secret Service backend (which isn't available headless/CI).
def _kr_set(service: str, key: str, value: str) -> None:
    import keyring

    keyring.set_password(service, key, value)


def _kr_get(service: str, key: str) -> Optional[str]:
    import keyring

    return keyring.get_password(service, key)


def _kr_delete(service: str, key: str) -> bool:
    import keyring

    try:
        keyring.delete_password(service, key)
        return True
    except Exception:  # noqa: BLE001 — keyring raises a family of backend errors on missing
        return False


class KeyringTokenStore:
    """OS keyring backend (Secret Service / Keychain / Credential Vault)."""

    backend = "keyring"

    def __init__(self, service: str = "arkscope-llm-auth"):
        self.service = service

    @staticmethod
    def usable() -> bool:
        """True only when keyring resolves a real (non fail/null) backend."""
        try:
            import keyring
            from keyring.backends import fail

            kr = keyring.get_keyring()
            if isinstance(kr, fail.Keyring):
                return False
            try:
                from keyring.backends import null

                if isinstance(kr, null.Keyring):
                    return False
            except Exception:  # noqa: BLE001 — null backend may be absent
                pass
            return True
        except Exception:  # noqa: BLE001 — keyring not importable / no backend
            return False

    def save(self, *, provider: str, auth_mode: str, credential_id: str, record: StoredTokenRecord) -> None:
        _kr_set(self.service, _token_key(provider, auth_mode, credential_id), _rec_to_json(record))

    def load(self, *, provider: str, auth_mode: str, credential_id: str) -> Optional[StoredTokenRecord]:
        raw = _kr_get(self.service, _token_key(provider, auth_mode, credential_id))
        return _rec_from_obj(json.loads(raw)) if raw else None

    def delete(self, *, provider: str, auth_mode: str, credential_id: str) -> bool:
        return _kr_delete(self.service, _token_key(provider, auth_mode, credential_id))

    def status(self, *, provider: str, auth_mode: str, credential_id: str) -> dict:
        return _redacted_status(self.load(provider=provider, auth_mode=auth_mode, credential_id=credential_id), self.backend)


def _default_dev_path() -> str:
    return os.environ.get("ARKSCOPE_TOKEN_STORE_PATH") or str(
        Path(__file__).resolve().parents[2] / "data" / "auth_tokens.json"
    )


def get_token_store(*, prefer: str | None = None, dev_path: str | Path | None = None):
    """Keyring-first with a flagged plaintext dev fallback.

    Resolution: env ``ARKSCOPE_TOKEN_STORE`` (plaintext|keyring) > ``prefer`` >
    auto. Auto uses keyring iff a usable backend exists, else plaintext.
    """
    choice = (os.environ.get("ARKSCOPE_TOKEN_STORE") or prefer or "auto").lower()
    if choice == "plaintext":
        return PlaintextTokenStore(dev_path or _default_dev_path())
    if choice == "keyring":
        return KeyringTokenStore()
    if KeyringTokenStore.usable():
        return KeyringTokenStore()
    return PlaintextTokenStore(dev_path or _default_dev_path())
