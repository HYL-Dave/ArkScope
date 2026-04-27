"""Macro/calendar API routes (P1.2 commit 5 + 6).

Endpoints:

  - ``GET /macro/health``               — pipeline health (commit 5)
  - ``GET /macro/economic-calendar``    — economic events with filters (commit 6)
  - ``GET /macro/earnings-calendar``    — earnings calendar (commit 6)
  - ``GET /macro/ipo-calendar``         — IPO pipeline (commit 6)
  - ``GET /macro/series/{series_id}``   — macro time series + as-of (commit 6)

All endpoints are gated on ``macro_calendar.enabled``. Read endpoints
support ``?as_of=`` for lookahead-safe replay (calendar uses
``cal_*_event_revisions``; macro series uses ALFRED's
``realtime_start``/``realtime_end`` window).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from src.agents.config import get_agent_config
from src.api.dependencies import get_dal
from src.macro_calendar.store import MacroCalendarStore
from src.service.macro_calendar_health import compute_macro_calendar_health

router = APIRouter(prefix="/macro", tags=["macro_calendar"])

_DISABLED_MSG = (
    "macro_calendar.enabled is false in config. Enable it in "
    "config/user_profile.yaml to activate the FRED + Finnhub calendar layer."
)


def _require_enabled() -> None:
    if not get_agent_config().macro_calendar_enabled:
        raise HTTPException(status_code=503, detail=_DISABLED_MSG)


def _parse_iso_datetime(value: Optional[str], name: str) -> Optional[datetime]:
    """Parse an optional ISO-8601 datetime/date param. Date-only inputs are
    treated as start-of-day UTC."""
    if value is None or value == "":
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = date.fromisoformat(value)
            dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"{name} must be ISO-8601 (YYYY-MM-DD or full timestamp): {exc}",
            )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_iso_date(value: Optional[str], name: str) -> Optional[date]:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"{name} must be ISO date YYYY-MM-DD: {exc}"
        )


def _validate_window(date_from: Any, date_to: Any) -> None:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise HTTPException(
            status_code=400,
            detail="to_date must be >= from_date",
        )


def _split_csv(value: Optional[str]) -> Optional[List[str]]:
    """Accept either repeated query params or a comma-separated string."""
    if value is None or value == "":
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
def macro_calendar_health(
    response: Response,
    strict: bool = Query(False, description="Return 503 when severity != ok."),
    dal=Depends(get_dal),
):
    """Pipeline health (jobs + table coverage). See ``compute_macro_calendar_health``."""
    _require_enabled()
    report = compute_macro_calendar_health(dal)
    if strict and report.get("severity") != "ok":
        response.status_code = 503
    return report


# ---------------------------------------------------------------------------
# Economic calendar
# ---------------------------------------------------------------------------


@router.get("/economic-calendar")
def economic_calendar(
    country: Optional[str] = Query(None, description="2-letter ISO (US, CN…); CSV ok"),
    impact: Optional[str] = Query(None, description="low|medium|high; CSV ok"),
    from_date: Optional[str] = Query(None, description="ISO date or full timestamp"),
    to_date: Optional[str] = Query(None, description="ISO date or full timestamp"),
    as_of: Optional[str] = Query(
        None,
        description="ISO timestamp; returns the revision visible at that moment",
    ),
    limit: int = Query(100, ge=1, le=1000),
    dal=Depends(get_dal),
):
    """List economic events filtered by country / impact / window."""
    _require_enabled()

    today = datetime.now(tz=timezone.utc)
    df = _parse_iso_datetime(from_date, "from_date") or (today - timedelta(days=7))
    dt = _parse_iso_datetime(to_date, "to_date") or (today + timedelta(days=14))
    _validate_window(df, dt)

    rows = MacroCalendarStore(dal).list_economic_events(
        date_from=df,
        date_to=dt,
        countries=_split_csv(country),
        impacts=_split_csv(impact),
        as_of=_parse_iso_datetime(as_of, "as_of"),
        limit=limit,
    )
    return {
        "count": len(rows),
        "date_from": df.isoformat(),
        "date_to": dt.isoformat(),
        "as_of": as_of,
        "events": rows,
    }


# ---------------------------------------------------------------------------
# Earnings calendar
# ---------------------------------------------------------------------------


@router.get("/earnings-calendar")
def earnings_calendar(
    symbol: Optional[str] = Query(None, description="Single symbol or CSV list"),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    as_of: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    dal=Depends(get_dal),
):
    _require_enabled()

    today = date.today()
    df = _parse_iso_date(from_date, "from_date") or today
    dt = _parse_iso_date(to_date, "to_date") or (today + timedelta(days=30))
    _validate_window(df, dt)

    rows = MacroCalendarStore(dal).list_earnings_events(
        date_from=df,
        date_to=dt,
        symbols=_split_csv(symbol),
        as_of=_parse_iso_datetime(as_of, "as_of"),
        limit=limit,
    )
    return {
        "count": len(rows),
        "date_from": df.isoformat(),
        "date_to": dt.isoformat(),
        "as_of": as_of,
        "events": rows,
    }


# ---------------------------------------------------------------------------
# IPO calendar
# ---------------------------------------------------------------------------


@router.get("/ipo-calendar")
def ipo_calendar(
    status: Optional[str] = Query(
        None, description="priced|filed|expected|withdrawn; CSV ok"
    ),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    as_of: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    dal=Depends(get_dal),
):
    _require_enabled()

    today = date.today()
    df = _parse_iso_date(from_date, "from_date") or (today - timedelta(days=30))
    dt = _parse_iso_date(to_date, "to_date") or (today + timedelta(days=90))
    _validate_window(df, dt)

    rows = MacroCalendarStore(dal).list_ipo_events(
        date_from=df,
        date_to=dt,
        statuses=_split_csv(status),
        as_of=_parse_iso_datetime(as_of, "as_of"),
        limit=limit,
    )
    return {
        "count": len(rows),
        "date_from": df.isoformat(),
        "date_to": dt.isoformat(),
        "as_of": as_of,
        "events": rows,
    }


# ---------------------------------------------------------------------------
# Macro series
# ---------------------------------------------------------------------------


@router.get("/series/{series_id}")
def macro_series(
    series_id: str,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    as_of: Optional[str] = Query(
        None,
        description="ISO date; returns the vintage that contained it (ALFRED replay)",
    ),
    limit: int = Query(1000, ge=1, le=10000),
    dal=Depends(get_dal),
):
    """Return macro time series + observations. ``?as_of=`` selects the
    vintage window that contained that date."""
    _require_enabled()

    df = _parse_iso_date(from_date, "from_date")
    dt = _parse_iso_date(to_date, "to_date")
    _validate_window(df, dt)

    payload = MacroCalendarStore(dal).get_macro_observations(
        series_id.upper(),
        date_from=df,
        date_to=dt,
        as_of=_parse_iso_date(as_of, "as_of"),
        limit=limit,
    )
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown macro series: {series_id}"
        )
    return payload