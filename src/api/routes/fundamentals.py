"""Fundamentals and SEC routes."""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from src.api.dependencies import get_dal
from src.tools.backends import provenance
from src.tools.data_access import DataAccessLayer
from src.tools.analysis_tools import get_fundamentals_analysis, get_sec_filings
from src.tools.schemas import FundamentalsResult

router = APIRouter(tags=["fundamentals"])


@router.get("/fundamentals/{ticker}")
def fundamentals(
    ticker: str,
    stored: bool = Query(
        False,
        description="Stored-only: return ONLY a local SEC annual-analysis "
        "financial_cache snapshot with NO external fetch and NO PG fallback. This "
        "cache may be empty until the full analysis path has run for the ticker. "
        "Default (false) runs the full analysis (SEC EDGAR → Financial Datasets fallback).",
    ),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get fundamentals for a ticker.

    Default = full analysis: stored snapshot → SEC EDGAR → Financial Datasets paid
    fallback (for agents / on-demand analysis; CAN trigger an external/paid fetch).

    ``stored=true`` = read-only: returns ONLY a local positive SEC annual-analysis
    financial_cache result and NEVER hits SEC/Financial Datasets or PG. Empty result
    (data_source 'none') when that cache is absent or expired.
    """
    if stored:
        from src.fundamentals.cache import read_cached_sec_fundamentals

        provenance.reset()
        cached, _negative = read_cached_sec_fundamentals(
            getattr(dal, "_backend", None),
            ticker,
            "annual",
        )
        if cached is not None:
            provenance.record("fundamentals", "local_cache")
            return {**cached.model_dump(), "source_path": "local_cache"}
        provenance.record("fundamentals", "none")
        empty = FundamentalsResult(ticker=ticker.upper())
        return {**empty.model_dump(), "source_path": "none"}
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
