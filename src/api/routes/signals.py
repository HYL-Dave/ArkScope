"""Signal detection routes."""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.signal_tools import (
    detect_anomalies,
    detect_event_chains,
    synthesize_signal,
)

router = APIRouter(prefix="/signals", tags=["signals"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_as_of_date(raw: Optional[str]) -> Optional[str]:
    """Validate YYYY-MM-DD format and that it parses to a real date."""
    if raw is None:
        return None
    if not _DATE_RE.match(raw):
        raise HTTPException(422, f"as_of_date must be YYYY-MM-DD, got: {raw!r}")
    try:
        date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(422, f"as_of_date is not a valid date: {raw!r}")
    return raw


@router.get("/{ticker}")
def signal_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    strategy: Optional[str] = Query(None),
    as_of_date: Optional[str] = Query(None, description="Anchor date YYYY-MM-DD (default: latest in data)"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Synthesize a multi-factor trading signal for a ticker."""
    result = synthesize_signal(
        dal, ticker=ticker, days=days, strategy=strategy,
        as_of_date=_validate_as_of_date(as_of_date),
    )
    return result.model_dump()


@router.get("/{ticker}/anomalies")
def anomalies_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    as_of_date: Optional[str] = Query(None, description="Anchor date YYYY-MM-DD (default: latest in data)"),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Detect sentiment and volume anomalies for a ticker."""
    return detect_anomalies(
        dal, ticker=ticker, days=days, as_of_date=_validate_as_of_date(as_of_date),
    )


@router.get("/{ticker}/event-chains")
def event_chains_for_ticker(
    ticker: str,
    days: int = Query(30, ge=1, le=9999),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Detect event chain patterns for a ticker."""
    return detect_event_chains(dal, ticker=ticker, days=days)