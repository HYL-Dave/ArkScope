"""Mispricing scan route."""

from fastapi import APIRouter, Depends, Query
from typing import List

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.options_tools import scan_mispricing

router = APIRouter(prefix="/scan", tags=["scan"])


@router.get("/mispricing")
def mispricing_scan(
    tickers: str = Query(..., description="Comma-separated ticker list"),
    threshold: float = Query(10.0, ge=1.0, le=100.0),
    min_confidence: str = Query("MEDIUM", pattern="^(HIGH|MEDIUM|LOW)$"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Scan for mispriced options across multiple tickers."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    results = scan_mispricing(
        dal, tickers=ticker_list,
        mispricing_threshold_pct=threshold,
        min_confidence=min_confidence,
    )
    return [r.model_dump() for r in results]