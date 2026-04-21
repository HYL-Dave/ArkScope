"""Research report read routes."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Annotated
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import get_dal
from src.tools.report_tools import get_report, list_reports

router = APIRouter(prefix="/reports", tags=["reports"])


def _normalize_report_value(value):
    """Convert pandas/NumPy-ish values into JSON/Pydantic-safe primitives."""
    if value is None:
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, list):
        return [_normalize_report_value(item) for item in value]

    if isinstance(value, dict):
        return {key: _normalize_report_value(item) for key, item in value.items()}

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    try:
        if value != value:
            return None
    except Exception:
        pass

    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            extracted = item_method()
        except Exception:
            extracted = value
        if extracted is not value:
            return _normalize_report_value(extracted)

    return value


def _normalize_report_record(record: dict) -> dict:
    """Normalize one report row before feeding it into Pydantic."""
    return {key: _normalize_report_value(value) for key, value in record.items()}


class ReportListItem(BaseModel):
    """One report entry returned by GET /reports."""

    id: Optional[int] = None
    title: str
    tickers: List[str] = Field(default_factory=list)
    report_type: Optional[str] = None
    summary: Optional[str] = None
    conclusion: Optional[str] = None
    confidence: Optional[float] = None
    model: Optional[str] = None
    file_path: Optional[str] = None
    tool_calls: Optional[int] = None
    duration_seconds: Optional[float] = None
    created_at: Optional[str] = None
    date: Optional[str] = None


class ReportListResponse(BaseModel):
    """Response body for GET /reports."""

    count: int
    reports: List[ReportListItem]


class ReportDetailResponse(BaseModel):
    """Response body for GET /reports/{report_id}."""

    id: Optional[int] = None
    title: Optional[str] = None
    tickers: List[str] = Field(default_factory=list)
    report_type: Optional[str] = None
    summary: Optional[str] = None
    conclusion: Optional[str] = None
    confidence: Optional[float] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    file_path: str
    tools_used: Optional[object] = None
    tool_calls: Optional[int] = None
    duration_seconds: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    created_at: Optional[str] = None
    content: str


@router.get("", response_model=ReportListResponse)
def reports_list(
    ticker: Annotated[Optional[str], Query()] = None,
    days: Annotated[int, Query(ge=1, le=3650)] = 30,
    report_type: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    dal=Depends(get_dal),
):
    """List saved reports with optional filters."""
    reports = list_reports(
        dal,
        ticker=ticker,
        days=days,
        report_type=report_type,
        limit=limit,
    )
    items = [ReportListItem(**_normalize_report_record(report)) for report in reports]
    return ReportListResponse(count=len(items), reports=items)


@router.get("/{report_id}", response_model=ReportDetailResponse)
def report_detail(
    report_id: int,
    dal=Depends(get_dal),
):
    """Read one saved report by DB identifier."""
    result = get_report(dal, report_id=report_id)
    error = result.get("error")
    if error:
        text = str(error)
        if "not found" in text.lower():
            raise HTTPException(status_code=404, detail=text)
        raise HTTPException(status_code=500, detail=text)
    return ReportDetailResponse(**_normalize_report_record(result))
