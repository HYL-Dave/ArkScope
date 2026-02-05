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