"""Local financial reads and separately authorized, named acquisition."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, ValidationError

from src.api.dependencies import get_dal
from src.api.permissions import require_db_write
from src.fundamentals.contracts import FinancialQuery, Period, Provider, ReadContract, StatementKind
from src.fundamentals.coverage import financial_coverage
from src.fundamentals.read_service import read_financials
from src.tools.data_access import DataAccessLayer


router = APIRouter(tags=["fundamentals"])


@router.get("/fundamentals/coverage")
def coverage(period: Period = "annual", source: Literal["auto", "seeking_alpha", "financial_datasets"] = "auto",
             currency: Annotated[str, Query(pattern=r"^[A-Z]{3}$")] = "USD",
             offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 25,
             dal: DataAccessLayer = Depends(get_dal)):
    return financial_coverage(dal, period=period, source=source, currency=currency, offset=offset, limit=limit)


@router.get("/fundamentals/{ticker}")
def fundamentals(ticker: str, stored: Annotated[bool, Query(deprecated=True)] = True,
                 period: Period = "annual", source: Literal["auto", "seeking_alpha", "financial_datasets"] = "auto",
                 currency: str = "USD", statement: StatementKind | None = None, end_month: str | None = None,
                 observation_id: str | None = None, read_id: str | None = None,
                 period_offset: int = 0, period_limit: int = 4, max_age_seconds: int | None = None,
                 freshness: Literal["stored"] = "stored", dal: DataAccessLayer = Depends(get_dal)):
    """Read retained statements. Both values of the deprecated stored alias are local-only."""
    try:
        query = FinancialQuery(ticker=ticker, period=period, source=source, currency=currency,
            statement=statement, end_month=end_month, observation_id=observation_id, read_id=read_id,
            period_offset=period_offset, period_limit=period_limit, max_age_seconds=max_age_seconds)
    except ValidationError:
        raise HTTPException(422, detail={"code": "financial_query_invalid"}) from None
    result = read_financials(dal, query)
    codes = {gap.code for gap in result.read_gaps}
    if "financial_read_changed" in codes:
        raise HTTPException(409, detail={"code": "financial_read_changed", "read_id": read_id})
    invalid = codes & {"financial_observation_scope_required", "financial_read_id_required"}
    if invalid:
        raise HTTPException(422, detail={"code": next(iter(invalid))})
    return result.model_dump()


class RefreshRequest(ReadContract):
    source: Provider
    period: Period = "annual"
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


@router.post("/fundamentals/{ticker}/refresh")
def refresh_financials(ticker: str, body: RefreshRequest, dal: DataAccessLayer = Depends(get_dal)):
    try:
        query = FinancialQuery(ticker=ticker, **body.model_dump(), freshness="refresh")
    except ValidationError:
        raise HTTPException(422, detail={"code": "financial_query_invalid"}) from None
    require_db_write("financial_refresh", {"ticker": query.ticker, "source": query.source})
    return read_financials(dal, query).model_dump()
