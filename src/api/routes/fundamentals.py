"""Fundamentals routes."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_dal
from src.tools.backends import provenance
from src.tools.data_access import DataAccessLayer
from src.tools.analysis_tools import get_fundamentals_analysis
from src.tools.schemas import FundamentalsResult

router = APIRouter(tags=["fundamentals"])


@router.get("/fundamentals/{ticker}")
def fundamentals(
    ticker: str,
    stored: bool = Query(
        False,
        description="Stored-only: return ONLY a local SEC annual-analysis "
        "financial_cache snapshot with no external fetch. This "
        "cache may be empty until the full analysis path has run for the ticker. "
        "Default (false) runs the full analysis (SEC EDGAR → Financial Datasets fallback).",
    ),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get fundamentals for a ticker.

    Default = full analysis: stored snapshot → SEC EDGAR → Financial Datasets paid
    fallback (for agents / on-demand analysis; CAN trigger an external/paid fetch).

    ``stored=true`` = read-only: returns ONLY a local positive SEC annual-analysis
    financial_cache result and never hits SEC or Financial Datasets. Empty result
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
