"""Config and overview routes."""

from fastapi import APIRouter, Depends

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.analysis_tools import get_watchlist_overview, get_morning_brief

router = APIRouter(tags=["config"])


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

    from src.agents.config import get_agent_config, task_model
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
        },
        "openai": {
            "model": cfg.openai_model,
            "model_advanced": cfg.openai_model_advanced,
            "reasoning_effort": cfg.reasoning_effort,
            "key_set": key_set("OPENAI_API_KEY"),
        },
        # Per-task model routing (so the UI can show what each operation uses).
        "card_synthesis": {"provider": "anthropic", "model": task_model("card_synthesis")},
        "card_translation": {"provider": "anthropic", "model": task_model("card_translation")},
        "data_keys": {
            "finnhub": key_set("FINNHUB_API_KEY"),
            "polygon": key_set("POLYGON_API_KEY"),
            "financial_datasets": key_set("FINANCIAL_DATASETS_API_KEY"),
            "fred": key_set("FRED_API_KEY"),
            "tavily": key_set("TAVILY_API_KEY"),
        },
    }