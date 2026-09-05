"""Profile-only credential lookup for lifecycle provider observations."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import sqlite3

from src.data_provider_config import DataProviderConfigStore, ProviderConfigMissing


_CENSUS_PROVIDERS = frozenset(("massive", "eodhd"))
_CREDENTIAL_FIELDS = frozenset(("api_key",))


class ReadOnlyProviderCredentialStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    def get_all(self) -> dict[str, dict[str, str]]:
        try:
            with sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True) as conn:
                conn.execute("PRAGMA query_only=ON")
                rows = conn.execute(
                    "SELECT provider, field, value FROM data_provider_config WHERE provider IN (?, ?)",
                    ("massive", "eodhd"),
                ).fetchall()
        except sqlite3.Error:
            raise ValueError("profile_credential_store_unavailable") from None
        result = {}
        for provider, field, value in rows:
            result.setdefault(provider, {})[field] = value
        return result


def resolve_census_credential(
    store: DataProviderConfigStore,
    provider: str,
) -> str:
    """Return one exact profile-backed key without consulting process state."""
    if provider not in _CENSUS_PROVIDERS:
        raise ValueError("census_credential_provider")

    provider_fields = store.get_all().get(provider)
    if not isinstance(provider_fields, Mapping) or set(provider_fields) != set(
        _CREDENTIAL_FIELDS
    ):
        raise ProviderConfigMissing(provider, "api_key")
    api_key = provider_fields.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ProviderConfigMissing(provider, "api_key")
    return api_key.strip()


__all__ = ["resolve_census_credential"]
