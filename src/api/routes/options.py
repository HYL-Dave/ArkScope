"""Option-pricing routes."""

from fastapi import APIRouter, Query

from src.tools.options_tools import calculate_greeks

router = APIRouter(prefix="/options", tags=["options"])


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
