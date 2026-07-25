from __future__ import annotations

import calendar as calendar_module
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from functools import lru_cache
from importlib import resources
from typing import Any, Callable

import exchange_calendars

from .models import (
    CalendarAvailability,
    CalendarDay,
    CalendarHealth,
    CalendarHealthAssessment,
    CalendarHealthReason,
    CalendarSessionKind,
)


_FIXTURE_RESOURCE = "official_nyse_sessions_v1.json"
_MINIMUM_HEALTHY_FORWARD_MONTHS = 6


@dataclass(frozen=True)
class _OfficialSessionManifest:
    calendar_name: str
    reviewed_from: date
    reviewed_through: date


@lru_cache(maxsize=1)
def _load_official_session_manifest() -> _OfficialSessionManifest:
    resource = resources.files(__package__).joinpath(_FIXTURE_RESOURCE)
    with resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return _OfficialSessionManifest(
        calendar_name=str(payload["calendar"]),
        reviewed_from=date.fromisoformat(payload["reviewed_from"]),
        reviewed_through=date.fromisoformat(payload["reviewed_through"]),
    )


def _add_calendar_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar_module.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


@dataclass(frozen=True)
class OfficialSessionFixtures:
    _manifest: _OfficialSessionManifest = field(
        default_factory=_load_official_session_manifest,
        init=False,
        repr=False,
    )

    @property
    def calendar_name(self) -> str:
        return self._manifest.calendar_name

    @property
    def reviewed_from(self) -> date:
        return self._manifest.reviewed_from

    @property
    def reviewed_through(self) -> date:
        return self._manifest.reviewed_through

    def is_reviewed(self, day: date) -> bool:
        return self.reviewed_from <= day <= self.reviewed_through

    def forward_horizon_months(self, as_of: date) -> int:
        if as_of >= self.reviewed_through:
            return 0

        months = (
            (self.reviewed_through.year - as_of.year) * 12
            + self.reviewed_through.month
            - as_of.month
        )
        if _add_calendar_months(as_of, months) > self.reviewed_through:
            months -= 1
        return max(0, months)


def _as_utc_datetime(value: object) -> datetime:
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        value = to_pydatetime()
    if not isinstance(value, datetime):
        raise TypeError("calendar timestamp did not convert to datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("calendar timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _as_calendar_date(value: object) -> date:
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        value = to_pydatetime()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError("calendar session label did not convert to date")


class XnysCalendarAdapter:
    def __init__(
        self,
        *,
        fixtures: OfficialSessionFixtures | None = None,
        calendar_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._fixtures = fixtures or OfficialSessionFixtures()
        self._calendar_factory = calendar_factory or exchange_calendars.get_calendar
        self._calendar: Any | None = None

    def _get_calendar(self) -> Any:
        if self._calendar is None:
            self._calendar = self._calendar_factory(
                self._fixtures.calendar_name,
                start=self._fixtures.reviewed_from.isoformat(),
                end=self._fixtures.reviewed_through.isoformat(),
            )
        return self._calendar

    def session(self, day: date) -> CalendarDay:
        try:
            calendar = self._get_calendar()
            day_label = day.isoformat()
            if self._fixtures.is_reviewed(day):
                first_session = _as_calendar_date(calendar.first_session)
                last_session = _as_calendar_date(calendar.last_session)
                if day < first_session or day > last_session:
                    return CalendarDay.closed(day)
            if not calendar.is_session(day_label):
                return CalendarDay.closed(day)

            session_label = calendar.date_to_session(day_label)
            session_kind = (
                CalendarSessionKind.EARLY_CLOSE
                if session_label in calendar.early_closes
                else CalendarSessionKind.REGULAR
            )
            return CalendarDay.open(
                market_date=day,
                open_at_utc=_as_utc_datetime(calendar.session_open(session_label)),
                close_at_utc=_as_utc_datetime(calendar.session_close(session_label)),
                session_kind=session_kind,
            )
        except Exception as exc:
            return CalendarDay.unavailable(day, diagnostic=str(exc))


class CalendarHealthComposer:
    def __init__(self, *, fixtures: OfficialSessionFixtures | None = None) -> None:
        self._fixtures = fixtures or OfficialSessionFixtures()

    def compose(
        self,
        *,
        requested_day: date,
        as_of: date,
        resolution: CalendarDay | None,
    ) -> CalendarHealthAssessment:
        if resolution is not None and resolution.market_date != requested_day:
            raise ValueError("calendar resolution date does not match requested date")

        forward_horizon = self._fixtures.forward_horizon_months(as_of)
        if (
            resolution is not None
            and resolution.availability is CalendarAvailability.UNAVAILABLE
        ):
            return CalendarHealthAssessment(
                status=CalendarHealth.UNAVAILABLE,
                reason_codes=(CalendarHealthReason.CALENDAR_UNAVAILABLE,),
                date_classifiable=False,
                reviewed_through=self._fixtures.reviewed_through,
                forward_horizon_months=forward_horizon,
            )

        reason_codes: list[CalendarHealthReason] = []
        date_classifiable = self._fixtures.is_reviewed(requested_day)
        if date_classifiable and resolution is None:
            raise ValueError("a reviewed date requires a calendar resolution")
        if not date_classifiable:
            reason_codes.append(CalendarHealthReason.DATE_UNREVIEWED)
        if forward_horizon < _MINIMUM_HEALTHY_FORWARD_MONTHS:
            reason_codes.append(CalendarHealthReason.FIXTURE_HORIZON_LOW)

        return CalendarHealthAssessment(
            status=CalendarHealth.DEGRADED if reason_codes else CalendarHealth.OK,
            reason_codes=tuple(reason_codes),
            date_classifiable=date_classifiable,
            reviewed_through=self._fixtures.reviewed_through,
            forward_horizon_months=forward_horizon,
        )
