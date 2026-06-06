"""Config and overview routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.agents.config import save_local_override, task_route
from src.api.permissions import require_profile_state_write
from src.api.dependencies import get_dal
from src.model_credentials import (
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
def runtime_config():
    """What the agent will actually use — models, effort, and which API keys are
    present (booleans only, never the key values). Lets the UI answer "which
    provider/model/key is active" without exposing secrets.
    """
    import os

    from src.agents.config import get_agent_config
    from src.env_keys import ensure_env_loaded

    ensure_env_loaded()
    cfg = get_agent_config()

    def key_set(name: str) -> bool:
        return bool(os.environ.get(name))

    return {
        "anthropic": {
            "model": cfg.anthropic_model,
            "model_advanced": cfg.anthropic_model_advanced,
            "effort": cfg.anthropic_effort,
            "thinking": cfg.anthropic_thinking,
            "key_set": key_set("ANTHROPIC_API_KEY"),
            "credentials": [c.model_dump() for c in provider_credentials()["anthropic"]],
        },
        "openai": {
            "model": cfg.openai_model,
            "model_advanced": cfg.openai_model_advanced,
            "reasoning_effort": cfg.reasoning_effort,
            "key_set": key_set("OPENAI_API_KEY"),
            "credentials": [c.model_dump() for c in provider_credentials()["openai"]],
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
def model_catalog():
    """Seed model catalog + current task routes for Settings.

    The catalog intentionally allows custom model IDs: official docs can lag
    account entitlements, and providers roll models independently.
    """
    return {
        **catalog().model_dump(),
        "routes": {
            "card_synthesis": task_route("card_synthesis").model_dump(),
            "card_translation": task_route("card_translation").model_dump(),
        },
        "credentials": {
            provider: [c.model_dump() for c in creds]
            for provider, creds in provider_credentials().items()
        },
        "custom_allowed": True,
    }


@router.post("/config/model-discovery")
def discover_provider_models(body: ModelDiscoveryRequest):
    """Live model discovery for a selected provider credential.

    Uses direct API-key credentials only. OAuth/setup-token entries are visible
    in Settings as credential types but are not used for direct provider API
    calls until their provider-specific flow is implemented.
    """
    return discover_models(body.provider, body.credential_id).model_dump()


@router.post("/config/model-test")
def run_provider_model_test(body: ModelTestRequest):
    """Run a tiny explicit model test call for provider/model/effort access."""
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
