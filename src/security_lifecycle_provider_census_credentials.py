"""Profile-only credential lookup for the detached lifecycle provider census."""

from __future__ import annotations

from collections.abc import Mapping

from src.data_provider_config import DataProviderConfigStore, ProviderConfigMissing


_CENSUS_PROVIDERS = frozenset(("massive", "eodhd"))
_CREDENTIAL_FIELDS = frozenset(("api_key",))


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
