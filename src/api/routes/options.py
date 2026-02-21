"""Options / IV routes."""

from fastapi import APIRouter, Depends, Query
from typing import List

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.options_tools import (
    get_iv_analysis,
    get_iv_history_data,
    scan_mispricing,
    calculate_greeks,
)

router = APIRouter(prefix="/options", tags=["options"])


@router.get("/{ticker}")
def iv_analysis(
    ticker: str,
    dal: DataAccessLayer = Depends(get_dal),
):
    """Full IV environment analysis: rank, percentile, VRP, signal."""
    result = get_iv_analysis(dal, ticker=ticker)
    return result.model_dump()


@router.get("/{ticker}/history")
def iv_history(
    ticker: str,
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get raw IV history data points."""
    points = get_iv_history_data(dal, ticker=ticker)
    return [p.model_dump() for p in points]


@router.get("/greeks/calculate")
def greeks(
    S: float = Query(..., description="Spot price"),
    K: float = Query(..., description="Strike price"),
    T: float = Query(..., description="Time to expiry in years"),
    r: float = Query(0.05, description="Risk-free rate"),
    sigma: float = Query(..., description="Volatility"),
    option_type: str = Query("C", pattern="^[CP]$"),
    model: str = Query("american", pattern="^(american|black_scholes)$",
                        description="Pricing model: 'american' (BS2002) or 'black_scholes'"),
    q: float = Query(0.0, description="Continuous dividend yield"),
):
    """Calculate option Greeks (American BS2002 or European BS)."""
    return calculate_greeks(
        S=S, K=K, T=T, r=r, sigma=sigma, option_type=option_type,
        model=model, dividend_yield=q,
    )