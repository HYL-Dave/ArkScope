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

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from src.agents.config import get_agent_config
from src.api.dependencies import get_dal, get_profile_store
from src.api.permissions import require_profile_state_write
from src.macro_calendar import (
    ENV_USE_LOCAL_MACRO,
    USE_LOCAL_MACRO_KEY,
    get_macro_calendar_store,
)
from src.macro_calendar.local_store import read_macro_table_stats, resolve_macro_calendar_db_path
from src.service.macro_calendar_health import compute_macro_calendar_health

router = APIRouter(prefix="/macro", tags=["macro_calendar"])

_DISABLED_MSG = (
    "macro_calendar.enabled is false in config. Enable it in "
    "config/user_profile.yaml to activate the FRED + Finnhub calendar layer."
)


def _require_enabled() -> None:
    if not get_agent_config().macro_calendar_enabled:
        raise HTTPException(status_code=503, detail=_DISABLED_MSG)


# ---------------------------------------------------------------------------
# use_local_macro Settings (legacy PG-exit provenance) — mirrors /market-data/{status,settings}.
# Config endpoints: intentionally NOT gated by macro_calendar_enabled (you need them to
# configure the feature), matching market-data's ungated status/settings.
# ---------------------------------------------------------------------------

_TRUTHY = ("1", "true", "yes", "on")


class LocalMacroToggle(BaseModel):
    enabled: bool


def _macro_setting_enabled(store) -> bool:
    return (store.get_setting(USE_LOCAL_MACRO_KEY) or "").strip().lower() in _TRUTHY


@router.get("/status")
def macro_status(store=Depends(get_profile_store)):
    """Local macro/cal status (PURE READ; does not touch PG, does not create the local DB).

    Reports the persisted legacy ``use_local_macro`` value, the env override, and — when
    ``macro_calendar.db`` exists — per-table coverage (read-only).

    ``local_first_active`` is always true after N9: macro/calendar routing is local by
    default, creates ``macro_calendar.db`` on first use, and never falls back to PG.
    ``exists`` is the separate "DB built yet?" signal the UI composes with this."""
    path = resolve_macro_calendar_db_path()
    setting_on = _macro_setting_enabled(store)
    env_on = os.environ.get(ENV_USE_LOCAL_MACRO, "").strip().lower() in _TRUTHY
    return {
        "macro_db": path,
        "exists": os.path.exists(path),
        "tables": read_macro_table_stats(path),  # {} when absent (no DB created)
        "use_local_macro_setting": setting_on,
        "env_override": env_on,
        "local_first_active": True,
    }


@router.put("/settings")
def set_local_macro(body: LocalMacroToggle, store=Depends(get_profile_store)):
    """Persist the legacy ``use_local_macro`` value for provenance.

    Runtime routing is local by default after N9; this endpoint no longer provides
    a PG fallback lever. Until ingestion populates ``macro_calendar.db``, local
    reads simply return empty (status: ``local_first_active`` true, ``exists``
    possibly still false)."""
    require_profile_state_write("set_use_local_macro", {"enabled": body.enabled})
    store.set_setting(USE_LOCAL_MACRO_KEY, "true" if body.enabled else "false")
    return {"use_local_macro_setting": body.enabled}


def _parse_iso_datetime_impl(
    value: Optional[str], name: str, *, date_to_eod: bool
) -> Optional[datetime]:
    if value is None or value == "":
        return None
    s = value.strip()
    if len(s) == 10 and s.count("-") == 2:
        try:
            d = date.fromisoformat(s)
            if date_to_eod:
                return datetime(
                    d.year, d.month, d.day,
                    23, 59, 59, 999999, tzinfo=timezone.utc,
                )
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{name} must be ISO-8601 (YYYY-MM-DD or full timestamp): {exc}",
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_iso_datetime_start(value: Optional[str], name: str) -> Optional[datetime]:
    """Parse ISO date/datetime as a window START.

    Date-only inputs (YYYY-MM-DD) → start-of-day UTC (00:00:00Z) so
    ``from_date=D`` includes events from the very start of D.
    Timestamp inputs are honoured at the precision provided.
    """
    return _parse_iso_datetime_impl(value, name, date_to_eod=False)


def _parse_iso_datetime_end(value: Optional[str], name: str) -> Optional[datetime]:
    """Parse ISO date/datetime as a window END or as-of moment.

    Date-only inputs (YYYY-MM-DD) → end-of-day UTC (23:59:59.999999Z) per
    spec §6.1 so ``to_date=D`` and ``as_of=D`` cover the full UTC day D.
    Timestamp inputs are honoured at the precision provided.
    """
    return _parse_iso_datetime_impl(value, name, date_to_eod=True)


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
        description=(
            "ISO date or timestamp. Date inputs (YYYY-MM-DD) are read as "
            "end-of-day UTC; returns the revision visible at that moment."
        ),
    ),
    limit: int = Query(100, ge=1, le=1000),
    dal=Depends(get_dal),
):
    """List economic events filtered by country / impact / window."""
    _require_enabled()

    today = datetime.now(tz=timezone.utc)
    df = _parse_iso_datetime_start(from_date, "from_date") or (
        today - timedelta(days=7)
    )
    dt = _parse_iso_datetime_end(to_date, "to_date") or (today + timedelta(days=14))
    _validate_window(df, dt)

    rows = get_macro_calendar_store(dal).list_economic_events(
        date_from=df,
        date_to=dt,
        countries=_split_csv(country),
        impacts=_split_csv(impact),
        as_of=_parse_iso_datetime_end(as_of, "as_of"),
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

    rows = get_macro_calendar_store(dal).list_earnings_events(
        date_from=df,
        date_to=dt,
        symbols=_split_csv(symbol),
        as_of=_parse_iso_datetime_end(as_of, "as_of"),
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

    rows = get_macro_calendar_store(dal).list_ipo_events(
        date_from=df,
        date_to=dt,
        statuses=_split_csv(status),
        as_of=_parse_iso_datetime_end(as_of, "as_of"),
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

    payload = get_macro_calendar_store(dal).get_macro_observations(
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
