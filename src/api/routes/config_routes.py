"""Config and overview routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_credential_store, get_dal, get_oauth_token_store
from src.api.permissions import require_profile_state_write
from src.agents.config import save_local_override, task_route
from src.model_credentials import (
    CredentialStore,
    discover_models,
    provider_credentials,
    test_model,
)
from src.model_routing import (
    Provider,
    TaskId,
    TaskRoute,
    catalog,
    is_seed_model,
    is_valid_effort,
    model_provider,
)
from src.tools.data_access import DataAccessLayer
from src.tools.analysis_tools import get_watchlist_overview, get_morning_brief

router = APIRouter(tags=["config"])
logger = logging.getLogger(__name__)


def _credential_store(store) -> CredentialStore:
    return store if isinstance(store, CredentialStore) else get_credential_store()


class RouteUpdate(BaseModel):
    provider: Provider
    model: str
    effort: str = "default"


class ModelRoutesUpdate(BaseModel):
    routes: dict[TaskId, RouteUpdate]


class ModelDiscoveryRequest(BaseModel):
    provider: Provider
    credential_id: str | None = None


class ModelTestRequest(BaseModel):
    provider: Provider
    model: str
    effort: str = "default"
    credential_id: str | None = None


class CredentialCreate(BaseModel):
    provider: Provider
    auth_type: str = "api_key"
    alias: str
    secret: str
    make_active: bool = True


class CredentialUpdate(BaseModel):
    alias: str | None = None
    secret: str | None = None
    active: bool | None = None


@router.get("/config/watchlist")
def watchlist(
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get watchlist tickers from user profile."""
    result = dal.get_watchlist()
    return result.model_dump()


@router.get("/config/sectors")
def sectors(
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get all sector definitions."""
    return dal.get_all_sectors()


@router.get("/config/strategy")
def strategy_weights(
    strategy: str = None,
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get strategy weights."""
    return dal.get_strategy_weights(strategy)


@router.get("/overview")
def overview(
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get watchlist overview with latest status for each ticker."""
    return get_watchlist_overview(dal)


@router.get("/morning-brief")
def morning_brief(
    dal: DataAccessLayer = Depends(get_dal),
):
    """Generate personalized morning briefing."""
    return get_morning_brief(dal)


@router.get("/config/runtime")
def runtime_config(store: CredentialStore = Depends(get_credential_store)):
    """What the agent will actually use — models, effort, and which API keys are
    present (booleans only, never the key values). Lets the UI answer "which
    provider/model/key is active" without exposing secrets.
    """
    import os

    from src.agents.config import get_agent_config
    from src.env_keys import ensure_env_loaded

    ensure_env_loaded()
    store = _credential_store(store)
    cfg = get_agent_config()

    def key_set(name: str) -> bool:
        return bool(os.environ.get(name))
    credentials = provider_credentials(store)

    return {
        "anthropic": {
            "model": cfg.anthropic_model,
            "model_advanced": cfg.anthropic_model_advanced,
            "effort": cfg.anthropic_effort,
            "thinking": cfg.anthropic_thinking,
            "key_set": key_set("ANTHROPIC_API_KEY")
            or any(c.available and c.can_test_models for c in credentials["anthropic"]),
            "credentials": [c.model_dump() for c in credentials["anthropic"]],
        },
        "openai": {
            "model": cfg.openai_model,
            "model_advanced": cfg.openai_model_advanced,
            "reasoning_effort": cfg.reasoning_effort,
            "key_set": key_set("OPENAI_API_KEY")
            or any(c.available and c.can_test_models for c in credentials["openai"]),
            "credentials": [c.model_dump() for c in credentials["openai"]],
        },
        # Per-task model routing (so the UI can show what each operation uses).
        "card_synthesis": task_route("card_synthesis").model_dump(),
        "card_translation": task_route("card_translation").model_dump(),
        "data_keys": {
            "finnhub": key_set("FINNHUB_API_KEY"),
            "polygon": key_set("POLYGON_API_KEY"),
            "financial_datasets": key_set("FINANCIAL_DATASETS_API_KEY"),
            "fred": key_set("FRED_API_KEY"),
            "tavily": key_set("TAVILY_API_KEY"),
        },
    }


@router.get("/config/model-catalog")
def model_catalog(store: CredentialStore = Depends(get_credential_store)):
    """Seed model catalog + current task routes for Settings.

    The catalog intentionally allows custom model IDs: official docs can lag
    account entitlements, and providers roll models independently.
    """
    store = _credential_store(store)
    return {
        **catalog().model_dump(),
        "routes": {
            "card_synthesis": task_route("card_synthesis").model_dump(),
            "card_translation": task_route("card_translation").model_dump(),
        },
        "credentials": {
            provider: [c.model_dump() for c in creds]
            for provider, creds in provider_credentials(store).items()
        },
        "custom_allowed": True,
    }


@router.get("/config/credentials")
def list_credentials(store: CredentialStore = Depends(get_credential_store)):
    """Masked provider credentials. Secret values are never returned."""
    store = _credential_store(store)
    return {
        "credentials": {
            provider: [c.model_dump() for c in creds]
            for provider, creds in provider_credentials(store).items()
        }
    }


@router.post("/config/credentials")
def add_credential(
    body: CredentialCreate,
    store: CredentialStore = Depends(get_credential_store),
):
    store = _credential_store(store)
    auth_type = body.auth_type.strip()
    # This route is for DIRECT API keys only. OAuth/setup-token modes carry a token
    # that must go to the token-store (not llm_credentials.secret), so they are
    # rejected here — use the dedicated OAuth import route.
    if auth_type in {"chatgpt_oauth", "claude_code_oauth", "oauth", "setup_token"}:
        raise HTTPException(status_code=400, detail=f"auth_type {auth_type!r} must use the OAuth import route, not this API-key endpoint")
    if auth_type != "api_key":
        raise HTTPException(status_code=400, detail=f"unsupported auth_type: {auth_type}")
    require_profile_state_write(
        "credential_add",
        {"provider": body.provider, "auth_type": auth_type, "alias": body.alias},
    )
    try:
        cred = store.add(
            provider=body.provider,
            auth_type=auth_type,  # type: ignore[arg-type]
            alias=body.alias,
            secret=body.secret,
            make_active=body.make_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "credential": next(
            c.model_dump()
            for c in provider_credentials(store)[body.provider]
            if c.id == f"local:{cred.id}"
        )
    }


class OAuthImport(BaseModel):
    provider: Provider
    auth_mode: str = "claude_code_oauth"
    alias: str
    token: str
    account_label: str | None = None
    expires_at: str | None = None
    make_active: bool = True


@router.post("/config/credentials/oauth/import")
def import_oauth_credential(
    body: OAuthImport,
    store: CredentialStore = Depends(get_credential_store),
    token_store=Depends(get_oauth_token_store),
):
    """Import a subscription OAuth/setup token. v1: anthropic + claude_code_oauth
    (Claude setup-token) ONLY. Creates a metadata row (secret NULL) then saves the
    token to the token-store; rolls the row back if the token-store write fails.
    The response returns masked metadata only — the token is NEVER echoed."""
    from src.auth_drivers import StoredTokenRecord
    from src.model_credentials import _normalize_auth_type

    store = _credential_store(store)
    provider = body.provider
    auth_mode = _normalize_auth_type(body.auth_mode.strip(), provider)
    # v1 scope: Claude setup-token only. (OpenAI chatgpt_oauth import = S3.)
    if not (provider == "anthropic" and auth_mode == "claude_code_oauth"):
        raise HTTPException(status_code=400, detail="v1 import supports only anthropic + claude_code_oauth (Claude setup-token)")
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    # NOTE: the token is deliberately NOT included in the write-gate detail.
    require_profile_state_write("oauth_credential_import", {"provider": provider, "auth_mode": auth_mode, "alias": body.alias})

    try:
        cred = store.add_oauth_credential(
            provider=provider, auth_mode=auth_mode, alias=body.alias,
            expires_at=body.expires_at, account_label=body.account_label, make_active=body.make_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    cid = f"local:{cred.id}"
    try:
        token_store.save(
            provider=provider, auth_mode=auth_mode, credential_id=cid,
            record=StoredTokenRecord(access_token=token, expires_at=body.expires_at, account_label=body.account_label),
        )
    except Exception:  # noqa: BLE001 — roll back so no half-built credential remains
        store.delete(cid)
        logger.warning("oauth token-store save failed for %s/%s; rolled back credential row", provider, auth_mode)
        raise HTTPException(status_code=502, detail="failed to store the token securely; nothing was saved")

    # masked metadata only — never the token / token-store payload
    return {
        "credential": next(
            c.model_dump()
            for c in provider_credentials(store)[provider]
            if c.id == cid
        )
    }


@router.put("/config/credentials/{credential_id}")
def update_credential(
    credential_id: str,
    body: CredentialUpdate,
    store: CredentialStore = Depends(get_credential_store),
):
    store = _credential_store(store)
    if not credential_id.startswith("local:"):
        raise HTTPException(status_code=400, detail="only local credentials are editable")
    require_profile_state_write(
        "credential_update",
        {"credential_id": credential_id, "active": body.active, "alias": body.alias},
    )
    cred = store.update(
        credential_id,
        alias=body.alias,
        secret=body.secret,
        active=body.active,
    )
    if not cred:
        raise HTTPException(status_code=404, detail="credential not found")
    return {
        "credential": next(
            c.model_dump()
            for c in provider_credentials(store)[cred.provider]
            if c.id == f"local:{cred.id}"
        )
    }


@router.delete("/config/credentials/{credential_id}")
def delete_credential(
    credential_id: str,
    store: CredentialStore = Depends(get_credential_store),
):
    store = _credential_store(store)
    if not credential_id.startswith("local:"):
        raise HTTPException(status_code=400, detail="only local credentials can be deleted")
    require_profile_state_write("credential_delete", {"credential_id": credential_id})
    if not store.delete(credential_id):
        raise HTTPException(status_code=404, detail="credential not found")
    return {"deleted": True, "id": credential_id}


@router.post("/config/model-discovery")
def discover_provider_models(
    body: ModelDiscoveryRequest,
    store: CredentialStore = Depends(get_credential_store),
):
    """Live model discovery for a selected provider credential.

    Uses direct API-key credentials only. OAuth/setup-token entries are visible
    in Settings as credential types but are not used for direct provider API
    calls until their provider-specific flow is implemented.
    """
    store = _credential_store(store)
    return discover_models(body.provider, body.credential_id, store).model_dump()


@router.post("/config/model-test")
def run_provider_model_test(
    body: ModelTestRequest,
    store: CredentialStore = Depends(get_credential_store),
):
    """Run a tiny explicit model test call for provider/model/effort access."""
    store = _credential_store(store)
    effort = body.effort.strip() or "default"
    warning = None
    if not is_valid_effort(body.provider, effort):
        warning = (
            f"Requested effort '{effort}' is not known for provider '{body.provider}'; "
            "testing with provider default."
        )
        effort = "default"
    result = test_model(
        body.provider,
        body.model.strip(),
        effort=effort,
        credential_id=body.credential_id,
        store=store,
    ).model_dump()
    if warning:
        result["warning"] = f"{warning} {result.get('warning') or ''}".strip()
    return result


@router.put("/config/model-routes")
def update_model_routes(body: ModelRoutesUpdate):
    """Persist per-task provider/model routing in user_profile.local.yaml."""
    if not body.routes:
        raise HTTPException(status_code=400, detail="no routes supplied")

    saved: dict[str, TaskRoute] = {}
    for task, update in body.routes.items():
        model = update.model.strip()
        if not model:
            raise HTTPException(status_code=400, detail=f"{task}: model is required")
        effort = update.effort.strip() or "default"
        warning = None
        if not is_valid_effort(update.provider, effort):
            warning = (
                f"Configured effort '{effort}' is not known for provider '{update.provider}'; "
                "saved provider default."
            )
            effort = "default"
        inferred = model_provider(model)
        if inferred and inferred != update.provider:
            raise HTTPException(
                status_code=400,
                detail=f"{task}: model '{model}' looks like {inferred}, not {update.provider}",
            )
        require_profile_state_write(
            "model_route_update",
            {"task": task, "provider": update.provider, "model": model, "effort": effort},
        )
        save_local_override("llm_preferences", f"{task}_provider", update.provider)
        save_local_override("llm_preferences", f"{task}_model", model)
        save_local_override("llm_preferences", f"{task}_effort", effort)
        saved[task] = TaskRoute(
            task=task,
            provider=update.provider,
            model=model,
            effort=effort,
            source="profile",
            custom=not is_seed_model(update.provider, model),
            warning=warning,
        )
    return {"routes": {k: v.model_dump() for k, v in saved.items()}}
