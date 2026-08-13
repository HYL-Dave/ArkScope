"""Telemetry-free execution authority for the six macro-calendar jobs."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from src.macro_calendar.write_lock import (
    MacroCalendarWriterLease,
    _claim_writer_lease,
    macro_calendar_writer,
)


MACRO_JOB_NAMES = frozenset(
    {
        "fetch_fred_series",
        "fetch_fred_release_dates",
        "fetch_economic_calendar_recent",
        "fetch_economic_calendar_backfill",
        "fetch_earnings_calendar",
        "fetch_ipo_calendar",
    }
)


def is_macro_job(job_name: str) -> bool:
    return job_name in MACRO_JOB_NAMES


def _watchlist_tickers(dal: Any) -> List[str]:
    watchlist = dal.get_watchlist(include_sectors=False)
    return list(getattr(watchlist, "tickers", []) or [])


def _normalize_tickers(raw: Any) -> List[str]:
    if raw is None:
        return []
    values = (
        [part.strip() for part in raw.split(",")]
        if isinstance(raw, str)
        else [str(part).strip() for part in raw]
    )
    normalized: List[str] = []
    seen: set[str] = set()
    for ticker in values:
        upper = ticker.upper()
        if not upper or upper in seen:
            continue
        seen.add(upper)
        normalized.append(upper)
    return normalized


def _parse_iso_date_param(raw: Any, name: str) -> Optional[date]:
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be ISO date (YYYY-MM-DD): {exc}")


def _validate_date_window(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise ValueError(
            f"to_date ({date_to.isoformat()}) must be >= "
            f"from_date ({date_from.isoformat()})"
        )


def _fetch_fred_release_dates(dal: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    from src.macro_calendar.fred_ingestion import fetch_fred_release_dates

    release_ids = params.get("release_ids")
    limit_raw = params.get("limit")
    limit = int(limit_raw) if limit_raw is not None else None
    if limit is not None and limit <= 0:
        raise ValueError("limit must be >= 1")
    return fetch_fred_release_dates(
        dal,
        release_ids=release_ids,
        limit=limit,
    ).to_dict()


def _fetch_fred_series(dal: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    from src.macro_calendar.fred_ingestion import fetch_fred_series

    return fetch_fred_series(
        dal,
        series_ids=params.get("series_ids"),
        full_refresh=bool(params.get("full_refresh", False)),
    ).to_dict()


def _fetch_economic_calendar_recent(
    dal: Any, params: Dict[str, Any]
) -> Dict[str, Any]:
    from src.macro_calendar.finnhub_ingestion import fetch_finnhub_economic_events

    today = date.today()
    date_from = _parse_iso_date_param(params.get("from_date"), "from_date") or (
        today - timedelta(days=7)
    )
    date_to = _parse_iso_date_param(params.get("to_date"), "to_date") or (
        today + timedelta(days=14)
    )
    _validate_date_window(date_from, date_to)
    return fetch_finnhub_economic_events(
        dal,
        date_from=date_from,
        date_to=date_to,
    ).to_dict()


def _fetch_economic_calendar_backfill(
    dal: Any, params: Dict[str, Any]
) -> Dict[str, Any]:
    from src.macro_calendar.finnhub_ingestion import fetch_finnhub_economic_events

    today = date.today()
    explicit_from = _parse_iso_date_param(params.get("from_date"), "from_date")
    if explicit_from is None:
        years_back = int(params.get("years_back", 1))
        if years_back <= 0:
            raise ValueError("years_back must be >= 1")
        date_from = today - timedelta(days=years_back * 365)
    else:
        date_from = explicit_from
    date_to = _parse_iso_date_param(params.get("to_date"), "to_date") or today
    _validate_date_window(date_from, date_to)
    return fetch_finnhub_economic_events(
        dal,
        date_from=date_from,
        date_to=date_to,
    ).to_dict()


def _fetch_earnings_calendar(dal: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    from src.macro_calendar.finnhub_ingestion import fetch_finnhub_earnings_events

    today = date.today()
    date_from = _parse_iso_date_param(params.get("from_date"), "from_date") or today
    date_to = _parse_iso_date_param(params.get("to_date"), "to_date") or (
        today + timedelta(days=30)
    )
    _validate_date_window(date_from, date_to)
    explicit = _normalize_tickers(params.get("symbols"))
    symbols: Optional[List[str]] = explicit or (_watchlist_tickers(dal) or None)
    return fetch_finnhub_earnings_events(
        dal,
        date_from=date_from,
        date_to=date_to,
        symbols=symbols,
    ).to_dict()


def _fetch_ipo_calendar(dal: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    from src.macro_calendar.finnhub_ingestion import fetch_finnhub_ipo_events

    today = date.today()
    date_from = _parse_iso_date_param(params.get("from_date"), "from_date") or (
        today - timedelta(days=30)
    )
    date_to = _parse_iso_date_param(params.get("to_date"), "to_date") or (
        today + timedelta(days=90)
    )
    _validate_date_window(date_from, date_to)
    return fetch_finnhub_ipo_events(
        dal,
        date_from=date_from,
        date_to=date_to,
    ).to_dict()


_DISPATCH: Dict[str, Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = {
    "fetch_fred_release_dates": _fetch_fred_release_dates,
    "fetch_fred_series": _fetch_fred_series,
    "fetch_economic_calendar_recent": _fetch_economic_calendar_recent,
    "fetch_economic_calendar_backfill": _fetch_economic_calendar_backfill,
    "fetch_earnings_calendar": _fetch_earnings_calendar,
    "fetch_ipo_calendar": _fetch_ipo_calendar,
}


def execute_macro_job(
    job_name: str,
    dal: Any,
    params: Dict[str, Any],
    *,
    writer_lease: MacroCalendarWriterLease | None = None,
) -> Dict[str, Any]:
    """Execute one reviewed macro job while holding the shared writer lock."""

    try:
        execute = _DISPATCH[job_name]
    except KeyError as exc:
        raise KeyError(f"unknown macro job: {job_name}") from exc

    if writer_lease is not None:
        _claim_writer_lease(writer_lease)
        return execute(dal, dict(params))

    with macro_calendar_writer() as acquired:
        _claim_writer_lease(acquired)
        return execute(dal, dict(params))
