"""Fundamentals and SEC routes."""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.analysis_tools import get_fundamentals_analysis, get_sec_filings

router = APIRouter(tags=["fundamentals"])


@router.get("/fundamentals/{ticker}")
def fundamentals(
    ticker: str,
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get fundamental analysis for a ticker."""
    result = get_fundamentals_analysis(dal, ticker=ticker)
    return result.model_dump()


@router.get("/sec/{ticker}")
def sec_filings(
    ticker: str,
    types: Optional[str] = Query(None, description="Comma-separated filing types (e.g. 10-K,10-Q)"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get SEC filing metadata for a ticker."""
    filing_types = None
    if types:
        filing_types = [t.strip() for t in types.split(",") if t.strip()]
    results = get_sec_filings(dal, ticker=ticker, filing_types=filing_types)
    return [f.model_dump() for f in results]