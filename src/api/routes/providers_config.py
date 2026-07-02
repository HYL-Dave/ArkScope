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

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_data_provider_store
from src.api.permissions import require_profile_state_write
from src.data_provider_config import (
    PROVIDER_FIELDS,
    DataProviderConfigStore,
    apply_env,
    effective_source,
    guarded_change_detail,
    importable_env_vars,
    mask_value,
    normalize_import_value,
    provider_default_available,
    run_connection_test,
    unapply_env,
)
from src.env_keys import ensure_env_loaded

router = APIRouter(tags=["providers"])

_TESTABLE = {"ibkr", "polygon", "finnhub", "fred", "sec_edgar"}


def get_data_provider_store_lenient() -> DataProviderConfigStore | None:
    try:
        return get_data_provider_store()
    except Exception as e:  # noqa: BLE001
        from src.provider_config_runtime import mark_provider_config_setup_required

        mark_provider_config_setup_required(str(e))
        return None


def _empty_view_with_setup() -> dict:
    from src.provider_config_runtime import provider_config_setup_state

    providers = {
        provider: {
            "fields": [],
            "testable": provider in _TESTABLE,
            "default_available": provider_default_available(provider),
        }
        for provider in PROVIDER_FIELDS
    }
    return {"providers": providers, "setup": provider_config_setup_state().as_dict()}


def _view(store: DataProviderConfigStore) -> dict:
    from src.provider_config_runtime import provider_config_setup_state

    stored = store.get_all()
    providers = {}
    for provider, fields in PROVIDER_FIELDS.items():
        rows = []
        for f in fields:
            raw = (stored.get(provider) or {}).get(f.field)
            source = effective_source(f.env_var)
            imports = importable_env_vars(f)
            import_source = None
            if source == "config/.env":
                import_source = f.env_var
            elif source == "missing":
                ensure_env_loaded()
                for candidate in f.import_aliases:
                    if candidate and os.getenv(candidate):
                        import_source = candidate
                        break
            rows.append({
                "field": f.field,
                "label": f.label,
                "secret": f.secret,
                "env_var": f.env_var,
                "app_value_set": bool(raw),
                "app_value_masked": mask_value(raw, f.secret) if raw else None,
                # where the EFFECTIVE process value comes from right now
                "effective_source": source,
                "needs_import": import_source is not None and source != "app",
                "import_source": import_source,
                "importable_env_vars": list(imports),
                "defaulted": f.defaulted and bool(raw),
                "guarded": f.guarded,
                "guard_reason": f.guard_reason,
            })
        providers[provider] = {
            "fields": rows,
            "testable": provider in _TESTABLE,
            # key-free + extension-free providers are available by default
            "default_available": provider_default_available(provider),
        }
    return {"providers": providers, "setup": provider_config_setup_state().as_dict()}


@router.get("/providers/config")
def providers_config(
    store: DataProviderConfigStore | None = Depends(get_data_provider_store_lenient),
):
    """Per-provider configurable fields with masked app values + effective source."""
    if store is None:
        return _empty_view_with_setup()
    return _view(store)


class ProviderConfigUpdate(BaseModel):
    # field name → new value; null/"" clears the app override (falls back to
    # config/.env, or unset)
    fields: dict[str, str | None]
    confirm_guarded: dict[str, bool] = Field(default_factory=dict)


class ProviderConfigImportEnv(BaseModel):
    source_env_var: str | None = None
    confirm_guarded: bool = False


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
    current_fields = store.get_all().get(provider) or {}
    for field, value in body.fields.items():
        value = (value or "").strip()
        current = current_fields.get(field)
        if by_name[field].guarded and (value or None) != (current or None):
            if not body.confirm_guarded.get(field):
                raise HTTPException(
                    status_code=409,
                    detail=guarded_change_detail(provider, field, by_name[field]),
                )
        store.set_field(provider, field, value or None)
        if not value:
            unapply_env(by_name[field].env_var)
    apply_env(store)
    from src.provider_config_runtime import clear_provider_config_setup_required

    clear_provider_config_setup_required()
    return _view(store)["providers"][provider]


@router.post("/providers/config/{provider}/{field}/import-env")
def import_provider_config_field(
    provider: str,
    field: str,
    body: ProviderConfigImportEnv,
    store: DataProviderConfigStore = Depends(get_data_provider_store),
):
    defs = PROVIDER_FIELDS.get(provider)
    if defs is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")
    by_name = {f.field: f for f in defs}
    fdef = by_name.get(field)
    if fdef is None:
        raise HTTPException(status_code=400, detail=f"unknown field {field!r}")
    ensure_env_loaded()
    candidates = importable_env_vars(fdef)
    source_env_var = body.source_env_var or fdef.env_var
    if source_env_var not in candidates:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "provider_config_import_source_invalid",
                "provider": provider,
                "field": field,
                "source_env_var": source_env_var,
            },
        )
    raw = (os.getenv(source_env_var) or "").strip()
    if not raw:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "provider_config_import_source_missing",
                "provider": provider,
                "field": field,
                "source_env_var": source_env_var,
            },
        )
    current = (store.get_all().get(provider) or {}).get(field)
    value = normalize_import_value(fdef, source_env_var, raw)
    if fdef.guarded and value != (current or "") and not body.confirm_guarded:
        raise HTTPException(
            status_code=409,
            detail=guarded_change_detail(provider, field, fdef),
        )
    require_profile_state_write("import_provider_config_env", {
        "provider": provider,
        "field": field,
        "source_env_var": source_env_var,
    })
    store.set_field(provider, field, value)
    apply_env(store)
    from src.provider_config_runtime import clear_provider_config_setup_required

    clear_provider_config_setup_required()
    return _view(store)["providers"][provider]


@router.post("/providers/test/{provider}")
def test_provider(provider: str):
    """Run one explicit, cheap, timeout-bounded connection test."""
    from src.provider_config_runtime import require_provider_config_ready

    require_provider_config_ready("provider_test")
    if provider not in PROVIDER_FIELDS:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")
    return {"provider": provider, **run_connection_test(provider)}
