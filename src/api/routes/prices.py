"""Price routes."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_dal
from src.tools.data_access import DataAccessLayer
from src.tools.price_tools import (
    get_ticker_prices,
    get_price_change,
    get_sector_performance,
)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{ticker}")
def prices_for_ticker(
    ticker: str,
    interval: str = Query("15min", pattern="^(15min|1h|1d)$"),
    days: int = Query(30, ge=1, le=9999),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Get OHLCV price bars for a ticker."""
    result = get_ticker_prices(dal, ticker=ticker, interval=interval, days=days)
    return result.model_dump()


@router.get("/{ticker}/change")
def price_change(
    ticker: str,
    days: int = Query(7, ge=1, le=9999),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Calculate price change metrics over a period."""
    return get_price_change(dal, ticker=ticker, days=days)


@router.get("/sector/{sector}")
def sector_performance(
    sector: str,
    days: int = Query(7, ge=1, le=9999),
    dal: DataAccessLayer = Depends(get_dal),
):
    """Calculate average performance of all tickers in a sector."""
    return get_sector_performance(dal, sector=sector, days=days)