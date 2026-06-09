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
    stored: bool = Query(
        False,
        description="Stored-only: return ONLY the local-first/PG fundamentals snapshot "
        "with NO external fetch. Default (false) runs the full analysis "
        "(stored → SEC EDGAR → Financial Datasets fallback).",
    ),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get fundamentals for a ticker.

    Default = full analysis: stored snapshot → SEC EDGAR → Financial Datasets paid
    fallback (for agents / on-demand analysis; CAN trigger an external/paid fetch).

    ``stored=true`` = read-only: returns ONLY the stored snapshot via the DAL
    (local market DB first, PG fallback) and NEVER hits SEC/Financial Datasets — for
    read-only UI surfaces (the detail-page 數據 tab) that must not trigger a provider
    fetch. Empty result (data_source 'none') when nothing is stored locally/PG.
    """
    if stored:
        result = dal.get_fundamentals(ticker)
        if result.snapshot_date:
            result.data_source = "ibkr"  # stored IBKR snapshot origin (mirrors analysis step 1)
        return result.model_dump()
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