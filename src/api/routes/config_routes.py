"""Config and overview routes."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import (
    get_credential_store,
    get_dal,
    get_oauth_login_manager,
    get_oauth_token_store,
)
from src.api.permissions import require_profile_state_write
from src.agents.config import save_local_override, task_route
from src.env_keys import env_file_path
from src.model_credentials import (
    CredentialStore,
    discover_models,
    export_env_credentials,
    import_env_credentials,
    provider_credentials,
    test_model,
    write_env_export,
)
from src.model_routing import (
    Provider,
    TaskId,
    TaskRoute,
    catalog,
    is_seed_model,
    is_valid_effort,
    model_provider,
    route_capability_warnings,
)
from src.tools.data_access import DataAccessLayer
from src.tools.analysis_tools import get_watchlist_overview, get_morning_brief

router = APIRouter(tags=["config"])
logger = logging.getLogger(__name__)


def _credential_apply_enabled() -> bool:
    """Code-enforced apply boundary. Real credential writes — a non-dry-run
    import into the profile DB, and writing an export file — are REFUSED unless
    ``ARKSCOPE_CREDENTIAL_APPLY_ENABLED`` is truthy. The spec's permission engine
    is still a no-op audit log (src/api/permissions.py), so this flag is the
    actual gate that keeps the apply step explicit/opt-in; dry-run previews stay
    allowed so the user can inspect before enabling."""
    return os.environ.get("ARKSCOPE_CREDENTIAL_APPLY_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def _credential_store(store) -> CredentialStore:
    return store if isinstance(store, CredentialStore) else get_credential_store()


def _run_coro(coro):
    """Drive an async driver method from a SYNC route handler. The ONE place this
    pattern lives — sync FastAPI routes run in a threadpool (no running loop), so
    asyncio.run is safe here. Do not scatter asyncio.run across routes."""
    import asyncio

    return asyncio.run(coro)


def _active_auth_mode(provider: str, store: CredentialStore) -> str | None:
    """The active credential's auth_type for ``provider`` (None if none / unresolvable).
    Best-effort: never let a capability lookup break a route save."""
    try:
        active = next((c for c in store.list(provider) if c.active), None)
        return active.auth_type if active else None
    except Exception:  # noqa: BLE001
        return None


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
        "ai_research": task_route("ai_research").model_dump(),
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
            "ai_research": task_route("ai_research").model_dump(),
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


class ImportEnvRequest(BaseModel):
    dry_run: bool = False


@router.post("/config/credentials/import-env")
def import_env_route(
    body: ImportEnvRequest,
    store: CredentialStore = Depends(get_credential_store),
):
    """Import api_key credentials from the process env (config/.env) into named
    DB rows (explode pools, dedup by secret). ``dry_run=True`` previews without
    writing. Returns counts/labels per provider only — never a secret."""
    store = _credential_store(store)
    if not body.dry_run:
        if not _credential_apply_enabled():
            raise HTTPException(
                status_code=403,
                detail="credential apply is disabled; preview with dry_run=true, or set ARKSCOPE_CREDENTIAL_APPLY_ENABLED=1 to enable the real import",
            )
        require_profile_state_write("credential_import_env", {"dry_run": False})
    summary = import_env_credentials(store, dry_run=body.dry_run)
    return {"dry_run": body.dry_run, "providers": summary}


class ExportEnvRequest(BaseModel):
    path: str


@router.post("/config/credentials/export-env")
def export_env_route(
    body: ExportEnvRequest,
    store: CredentialStore = Depends(get_credential_store),
):
    """Write the api_key credentials to a portable .env file (0600). REFUSES to
    overwrite the live config/.env — that file holds non-credential keys (data
    sources, DB) this export does not emit, so writing there would destroy them.
    Returns counts/labels only — never a secret (the file holds the secrets)."""
    store = _credential_store(store)
    path = body.path.strip()
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    # never write THROUGH a symlink — it would clobber the link target with the
    # export's real secrets (and relax it to 0600). Refuse any symlink path.
    if os.path.islink(path):
        raise HTTPException(status_code=400, detail="refusing to write the export through a symlink; choose a regular file path")
    # realpath (not abspath) so a symlink whose target is config/.env — or a
    # ../-relative path — is also refused; abspath would let it write through.
    if os.path.realpath(path) == os.path.realpath(str(env_file_path())):
        raise HTTPException(
            status_code=400,
            detail="refusing to overwrite the live config/.env (it holds non-credential keys); choose a separate export path",
        )
    if not _credential_apply_enabled():
        raise HTTPException(
            status_code=403,
            detail="credential export is disabled; set ARKSCOPE_CREDENTIAL_APPLY_ENABLED=1 to enable writing the export file",
        )
    require_profile_state_write("credential_export_env", {"path": path})
    return write_env_export(path, store=store)


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


class OAuthManualComplete(BaseModel):
    state: str
    code: str | None = None
    redirect_url: str | None = None


class OAuthStartRequest(BaseModel):
    # Default FALSE: ChatGPT OAuth execution isn't wired yet (AI 研究 fail-closes when
    # it's active), so logging in must NOT auto-switch the active credential. The user
    # can opt in. Carried into the pending login state so the loopback callback honors it.
    make_active: bool = False


@router.post("/config/credentials/openai/oauth/start")
def start_openai_oauth(body: OAuthStartRequest | None = None, manager=Depends(get_oauth_login_manager)):
    """Begin an in-app ChatGPT (OpenAI subscription) OAuth login. Returns the
    authorize URL + state for the browser; the loopback callback (or the manual
    copy-code fallback) completes it. COMPATIBILITY/EXPERIMENTAL path — the
    ChatGPT/Codex backend is not the public OpenAI API. The token never appears in
    any response; only masked metadata is returned on completion (via /status)."""
    # Gate the credential-creating intent here (request context); the async loopback
    # completion fulfills this gated start. The detail is token-free by construction.
    require_profile_state_write("oauth_login_start", {"provider": "openai", "auth_mode": "chatgpt_oauth"})
    return manager.begin(make_active=body.make_active if body else False)


@router.get("/config/credentials/openai/oauth/status")
def openai_oauth_status(state: str, manager=Depends(get_oauth_login_manager)):
    """Poll a login started by /start: {status: pending|success|error|unknown,
    credential: <masked metadata>|null, detail: <message>|null}. No token."""
    return manager.status(state)


@router.post("/config/credentials/openai/oauth/complete-manual")
def complete_openai_oauth_manual(body: OAuthManualComplete, manager=Depends(get_oauth_login_manager)):
    """Copy-code fallback — ONLY for when the localhost callback never arrived. The
    user pastes the authorization code (or the full redirect URL); this completes the
    SAME login. It does NOT change the auth mode, store, or validation, and it MUST
    NOT mask an OAuth/token error (a bad/expired/forged state → 400, no fallback)."""
    from src.auth_drivers.chatgpt_oauth_login import (
        ChatGPTOAuthLoginError,
        extract_code_from_redirect_url,
    )

    require_profile_state_write("oauth_login_complete_manual", {"provider": "openai", "auth_mode": "chatgpt_oauth"})
    code = (body.code or "").strip() or None
    if body.redirect_url:
        try:
            parsed = extract_code_from_redirect_url(body.redirect_url)
        except ChatGPTOAuthLoginError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if parsed.get("state") and parsed["state"] != body.state:
            raise HTTPException(status_code=400, detail="the redirect URL's state does not match this login")
        code = parsed["code"]
    if not code:
        raise HTTPException(status_code=400, detail="code or redirect_url is required")
    try:
        return {"credential": manager.complete_manual(state=body.state, code=code)}
    except ChatGPTOAuthLoginError as exc:
        # state/PKCE/exchange failures FAIL — never a silent fallback. The message is
        # already redacted at the source; map to a 400.
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/config/credentials/{credential_id}/probe")
def probe_oauth_credential(
    credential_id: str,
    store: CredentialStore = Depends(get_credential_store),
    token_store=Depends(get_oauth_token_store),
):
    """Run the OAuth probe for a stored credential and return redacted ProbeResults
    (the token is NEVER echoed):
      - anthropic claude_code_oauth → P3 (claude -p works + raw SDK rejects the token);
      - openai chatgpt_oauth → P1/P2 (api.openai.com rejects + ChatGPT-backend floor)."""
    from src.model_credentials import valid_credential_id

    store = _credential_store(store)
    if not valid_credential_id(credential_id):  # must be local:<int>, not a thread-id rule
        raise HTTPException(status_code=422, detail="invalid credential_id (expected local:<int>)")
    cred = store.get(credential_id)
    if cred is None or cred.auth_type not in ("chatgpt_oauth", "claude_code_oauth"):
        raise HTTPException(status_code=404, detail="OAuth credential not found")
    record = token_store.load(provider=cred.provider, auth_mode=cred.auth_type, credential_id=credential_id)
    if record is None or not record.access_token:
        raise HTTPException(status_code=404, detail="no stored token for this credential")

    if cred.provider == "anthropic" and cred.auth_type == "claude_code_oauth":
        from src.auth_drivers.claude_oauth_probe import run_claude_code_oauth_probe

        return run_claude_code_oauth_probe(record.access_token)
    if cred.provider == "openai" and cred.auth_type == "chatgpt_oauth":
        from src.auth_drivers.chatgpt_oauth_probe import run_chatgpt_oauth_probe

        return run_chatgpt_oauth_probe(record.access_token)
    raise HTTPException(status_code=400, detail="probe supports anthropic claude_code_oauth or openai chatgpt_oauth")


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
    token_store=Depends(get_oauth_token_store),
):
    """Live model discovery for a selected provider credential — PER auth_mode.

    api_key/api_key_pool → the provider's standard API (`/models`). An OAuth
    credential is dispatched through its driver instead (the standard provider-API
    path can't use an OAuth token): openai chatgpt_oauth → the live ChatGPT/Codex
    backend list (S3 step 1); anthropic claude_code_oauth → the honest seed
    candidate list. The token is loaded by the driver from the token-store.
    """
    store = _credential_store(store)
    cred = store.get(body.credential_id) if body.credential_id else None
    if cred is not None and cred.auth_type in ("chatgpt_oauth", "claude_code_oauth"):
        # API-boundary guard: the requested provider must match the credential's
        # provider — never silently return another provider's models.
        if cred.provider != body.provider:
            raise HTTPException(
                status_code=400,
                detail=f"credential {body.credential_id} is provider {cred.provider!r}, not {body.provider!r}",
            )
        from src.auth_drivers.factory import build_driver

        driver = build_driver(
            provider=cred.provider, auth_mode=cred.auth_type, credential=cred, token_store=token_store,
        )
        return _run_coro(driver.discover_models()).model_dump()
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
def update_model_routes(
    body: ModelRoutesUpdate,
    store: CredentialStore = Depends(get_credential_store),
):
    """Persist per-task provider/model routing in user_profile.local.yaml.

    Validation is auth-mode-aware (S3 step 2): a saved model/effort is checked against
    the ACTIVE credential's auth_mode for that provider — e.g. effort is dropped on the
    Claude subscription, and the ChatGPT-backend model set differs from the API-key
    catalog. These are non-blocking WARNINGS (the catalog allows custom ids); only a
    provider/model-prefix mismatch is a hard 400.
    """
    if not body.routes:
        raise HTTPException(status_code=400, detail="no routes supplied")
    store = _credential_store(store)

    saved: dict[str, TaskRoute] = {}
    for task, update in body.routes.items():
        model = update.model.strip()
        if not model:
            raise HTTPException(status_code=400, detail=f"{task}: model is required")
        effort = update.effort.strip() or "default"
        warnings: list[str] = []
        if not is_valid_effort(update.provider, effort):
            warnings.append(
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
        # auth-mode-aware capability warnings (effort-dropped on subscription, OAuth
        # model set differs from the api_key catalog). Best-effort, never blocks.
        warnings.extend(
            route_capability_warnings(
                update.provider, model, effort, auth_mode=_active_auth_mode(update.provider, store),
            )
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
            warning=" ".join(warnings) or None,
        )
    return {"routes": {k: v.model_dump() for k, v in saved.items()}}
