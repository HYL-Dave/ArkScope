"""
Data-provider config routes — app-managed keys / connection settings + tests.

GET returns MASKED values only (secrets never leave the machine readably); PUT
saves/clears one provider's fields and re-applies the env bridge so every call
site — in-process os.getenv users AND scheduler-spawned collectors — sees the
change immediately, no restart. POST /providers/test/{provider} runs one explicit
cheap probe (IBKR = TCP socket to the configured host:port; key providers = one
free API call; SEC EDGAR = key-less reachability; paid FD = no live call).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_data_provider_store
from src.api.permissions import require_profile_state_write
from src.data_provider_config import (
    PROVIDER_FIELDS,
    DataProviderConfigStore,
    apply_env,
    effective_source,
    mask_value,
    run_connection_test,
    unapply_env,
)

router = APIRouter(tags=["providers"])

_TESTABLE = {"ibkr", "polygon", "finnhub", "fred", "sec_edgar"}


def _view(store: DataProviderConfigStore) -> dict:
    stored = store.get_all()
    providers = {}
    for provider, fields in PROVIDER_FIELDS.items():
        rows = []
        for f in fields:
            raw = (stored.get(provider) or {}).get(f.field)
            rows.append({
                "field": f.field,
                "label": f.label,
                "secret": f.secret,
                "env_var": f.env_var,
                "app_value_set": bool(raw),
                "app_value_masked": mask_value(raw, f.secret) if raw else None,
                # where the EFFECTIVE process value comes from right now
                "effective_source": effective_source(f.env_var),
            })
        providers[provider] = {
            "fields": rows,
            "testable": provider in _TESTABLE,
            # key-free + extension-free providers are available by default
            "default_available": not fields and provider != "seeking_alpha",
        }
    return {"providers": providers}


@router.get("/providers/config")
def providers_config(store: DataProviderConfigStore = Depends(get_data_provider_store)):
    """Per-provider configurable fields with masked app values + effective source."""
    return _view(store)


class ProviderConfigUpdate(BaseModel):
    # field name → new value; null/"" clears the app override (falls back to
    # config/.env, or unset)
    fields: dict[str, str | None]


@router.put("/providers/config/{provider}")
def put_provider_config(
    provider: str,
    body: ProviderConfigUpdate,
    store: DataProviderConfigStore = Depends(get_data_provider_store),
):
    """Save/clear one provider's app-managed fields and re-apply the env bridge."""
    defs = PROVIDER_FIELDS.get(provider)
    if defs is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")
    if not defs:
        raise HTTPException(status_code=400,
                            detail=f"{provider} has no configurable fields")
    by_name = {f.field: f for f in defs}
    unknown = [k for k in body.fields if k not in by_name]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown fields {unknown}")
    require_profile_state_write("set_provider_config", {
        "provider": provider, "fields": list(body.fields.keys()),  # names only, never values
    })
    for field, value in body.fields.items():
        value = (value or "").strip()
        store.set_field(provider, field, value or None)
        if not value:
            unapply_env(by_name[field].env_var)
    apply_env(store)
    return _view(store)["providers"][provider]


@router.post("/providers/test/{provider}")
def test_provider(provider: str):
    """Run one explicit, cheap, timeout-bounded connection test."""
    if provider not in PROVIDER_FIELDS:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")
    return {"provider": provider, **run_connection_test(provider)}
