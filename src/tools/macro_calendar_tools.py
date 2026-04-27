"""Agent tools for the macro/calendar layer (P1.2 commit 6).

Two tools:

  - ``get_economic_calendar(country, importance, days_back, days_forward,
    as_of, limit)`` — list recent + upcoming economic events.
  - ``get_macro_value(series_id, observation_date, as_of)`` — point-in-time
    macro lookup with FRED/ALFRED vintage replay.

Both tools are read-only, gated on ``macro_calendar.enabled`` (callers
get a one-line "feature disabled" string when it's off so the agent
can keep planning), and degrade to a clear text message when the DAL
backend can't reach PostgreSQL.

Output is intentionally a Markdown-ish string. The agent reads it,
not a downstream pipeline — keeping the surface as text avoids forcing
the registry to ship a structured-output channel just for two tools.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from src.agents.config import get_agent_config
from src.macro_calendar.store import MacroCalendarStore

logger = logging.getLogger(__name__)


_DISABLED_MSG = (
    "macro_calendar layer is disabled. Set macro_calendar.enabled=true in "
    "config/user_profile.yaml to use this tool."
)
_BACKEND_MSG = (
    "macro_calendar tools require the PostgreSQL DAL backend; the current "
    "DAL has no _get_conn (probably FileBackend)."
)


# ---------------------------------------------------------------------------
# get_economic_calendar
# ---------------------------------------------------------------------------


def get_economic_calendar(
    dal: Any,
    country: Optional[str] = None,
    importance: Optional[str] = None,
    days_back: int = 7,
    days_forward: int = 14,
    as_of: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Return a Markdown summary of economic-calendar events in a window.

    Args:
        dal: DAL whose ``_backend`` exposes ``_get_conn``.
        country: ISO 2-letter (e.g. "US"). CSV like "US,CN" supported.
        importance: "low" / "medium" / "high". CSV supported.
        days_back: window start = today - days_back (default 7).
        days_forward: window end = today + days_forward (default 14).
        as_of: ISO timestamp. When set, returns the revision that was
               visible at that moment via cal_economic_event_revisions
               (lookahead-safe replay). Events first observed AFTER as_of
               are excluded entirely.
        limit: hard cap on rows (1..500, default 50).
    """
    if not get_agent_config().macro_calendar_enabled:
        return _DISABLED_MSG
    store = MacroCalendarStore(dal)
    if not store.is_available():
        return _BACKEND_MSG

    try:
        days_back = max(0, int(days_back))
        days_forward = max(0, int(days_forward))
        limit = max(1, min(500, int(limit)))
    except (TypeError, ValueError) as exc:
        return f"Invalid integer parameter: {exc}"

    now = datetime.now(tz=timezone.utc)
    date_from = now - timedelta(days=days_back)
    date_to = now + timedelta(days=days_forward)
    as_of_dt = _parse_iso_dt(as_of)
    if as_of and as_of_dt is None:
        return f"Invalid as_of timestamp: {as_of!r}; expected ISO-8601."

    rows = store.list_economic_events(
        date_from=date_from,
        date_to=date_to,
        countries=_split_csv(country),
        impacts=_split_csv(importance, lower=True),
        as_of=as_of_dt,
        limit=limit,
    )
    return _format_economic_rows(
        rows,
        date_from=date_from,
        date_to=date_to,
        country=country,
        importance=importance,
        as_of=as_of_dt,
    )


# ---------------------------------------------------------------------------
# get_macro_value
# ---------------------------------------------------------------------------


def get_macro_value(
    dal: Any,
    series_id: str,
    observation_date: str,
    as_of: Optional[str] = None,
) -> str:
    """Point-in-time macro lookup. Returns a one-line value summary.

    Args:
        dal: DAL with PostgreSQL backend.
        series_id: FRED series id (e.g. "CPIAUCNS"). Case-insensitive.
        observation_date: ISO YYYY-MM-DD — the date the value REFERS to
                          (e.g. "2024-03-01" for March 2024 CPI).
        as_of: ISO YYYY-MM-DD — the date the caller wants to "be" when
               reading. Picks the ALFRED vintage window that contained
               this date. Default = current vintage.
    """
    if not get_agent_config().macro_calendar_enabled:
        return _DISABLED_MSG
    store = MacroCalendarStore(dal)
    if not store.is_available():
        return _BACKEND_MSG

    sid = (series_id or "").strip().upper()
    if not sid:
        return "series_id is required."
    obs = _parse_iso_date(observation_date)
    if obs is None:
        return f"observation_date must be ISO YYYY-MM-DD: {observation_date!r}"
    as_of_d: Optional[date] = None
    if as_of is not None and as_of != "":
        as_of_d = _parse_iso_date(as_of)
        if as_of_d is None:
            return f"as_of must be ISO YYYY-MM-DD: {as_of!r}"

    payload = store.get_macro_observations(
        sid,
        date_from=obs,
        date_to=obs,
        as_of=as_of_d,
        limit=1,
    )
    if payload is None:
        return f"Unknown macro series: {sid}"

    title = payload.get("title") or sid
    units = payload.get("units") or ""
    obs_rows = payload.get("observations") or []
    if not obs_rows:
        if as_of_d is not None:
            return (
                f"{sid} ({title}) has no observation for {obs.isoformat()} "
                f"as of {as_of_d.isoformat()} — value was unknown at that "
                f"vintage (e.g. observation hadn't been published yet)."
            )
        return (
            f"{sid} ({title}) has no observation for {obs.isoformat()} in "
            f"the current vintage."
        )

    row = obs_rows[0]
    value = row.get("value")
    rt_start = row.get("realtime_start")
    rt_end = row.get("realtime_end")
    value_str = "missing" if value is None else f"{value} {units}".strip()
    return (
        f"{sid} ({title}) on {obs.isoformat()}: {value_str} "
        f"(vintage {rt_start} → {rt_end})"
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_economic_rows(
    rows: list,
    *,
    date_from: datetime,
    date_to: datetime,
    country: Optional[str],
    importance: Optional[str],
    as_of: Optional[datetime],
) -> str:
    if not rows:
        suffix = f" as of {as_of.isoformat()}" if as_of else ""
        filt: list = []
        if country:
            filt.append(f"country={country}")
        if importance:
            filt.append(f"impact={importance}")
        filt_str = " (" + ", ".join(filt) + ")" if filt else ""
        return (
            f"No economic events in {date_from.date().isoformat()} → "
            f"{date_to.date().isoformat()}{filt_str}{suffix}."
        )

    header = (
        f"Economic calendar — {len(rows)} event(s), "
        f"{date_from.date().isoformat()} → {date_to.date().isoformat()}"
    )
    if as_of is not None:
        header += f" as of {as_of.isoformat()}"
    if country:
        header += f", country={country}"
    if importance:
        header += f", impact={importance}"

    lines = [header, ""]
    for r in rows:
        et = r.get("event_time")
        et_str = et.isoformat() if hasattr(et, "isoformat") else str(et)
        impact_label = (r.get("impact") or "").upper() or "—"
        actual = r.get("actual")
        estimate = r.get("estimate")
        prev = r.get("prev")
        unit = (r.get("unit") or "").strip()
        unit_suffix = f" {unit}" if unit else ""

        actual_s = "—" if actual is None else f"{actual}{unit_suffix}"
        est_s = "—" if estimate is None else f"{estimate}{unit_suffix}"
        prev_s = "—" if prev is None else f"{prev}{unit_suffix}"

        lines.append(
            f"- [{impact_label}] {r.get('country')} | {et_str} | "
            f"{r.get('event_name')} | "
            f"actual={actual_s} | est={est_s} | prev={prev_s}"
        )
    return "\n".join(lines)


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None or value == "":
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            d = date.fromisoformat(str(value))
            dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _split_csv(value: Optional[str], *, lower: bool = False) -> Optional[list]:
    if value is None or value == "":
        return None
    out = [v.strip() for v in str(value).split(",") if v.strip()]
    if lower:
        out = [v.lower() for v in out]
    return out or None