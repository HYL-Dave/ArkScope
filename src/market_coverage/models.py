from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class MarketScope(str, Enum):
    US_LISTED_EQUITY_PROXY = "us_listed_equity_proxy"


class CoverageSession(str, Enum):
    RTH = "rth"


class CalendarAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CalendarHealth(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class CalendarDayKind(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class CalendarSessionKind(str, Enum):
    REGULAR = "regular"
    EARLY_CLOSE = "early_close"


class CalendarHealthReason(str, Enum):
    FIXTURE_HORIZON_LOW = "fixture_horizon_low"
    DATE_UNREVIEWED = "date_unreviewed"
    CALENDAR_UNAVAILABLE = "calendar_unavailable"


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class CalendarDay:
    market_date: date
    availability: CalendarAvailability
    kind: CalendarDayKind
    open_at_utc: datetime | None = None
    close_at_utc: datetime | None = None
    session_kind: CalendarSessionKind | None = None
    reason_code: CalendarHealthReason | None = None
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        session_values = (self.open_at_utc, self.close_at_utc, self.session_kind)

        if self.kind is CalendarDayKind.OPEN:
            if self.availability is not CalendarAvailability.AVAILABLE:
                raise ValueError("an open calendar day must be available")
            if any(value is None for value in session_values):
                raise ValueError("an open calendar day requires session values")
            if self.reason_code is not None or self.diagnostic is not None:
                raise ValueError("an available calendar day cannot carry an error")

            open_at = self.open_at_utc
            close_at = self.close_at_utc
            assert open_at is not None
            assert close_at is not None
            if not _is_timezone_aware(open_at) or not _is_timezone_aware(close_at):
                raise ValueError("session datetimes must be timezone-aware")
            if open_at >= close_at:
                raise ValueError("session open must be before session close")
            return

        if any(value is not None for value in session_values):
            raise ValueError("a non-open calendar day cannot carry session values")

        if self.kind is CalendarDayKind.CLOSED:
            if self.availability is not CalendarAvailability.AVAILABLE:
                raise ValueError("a closed calendar day must be available")
            if self.reason_code is not None or self.diagnostic is not None:
                raise ValueError("a closed calendar day cannot carry an error")
            return

        if self.kind is CalendarDayKind.UNKNOWN:
            if self.availability is not CalendarAvailability.UNAVAILABLE:
                raise ValueError("an unknown calendar day must be unavailable")
            if self.reason_code is not CalendarHealthReason.CALENDAR_UNAVAILABLE:
                raise ValueError("an unavailable day requires calendar_unavailable")
            return

        raise ValueError(f"unsupported calendar day kind: {self.kind!r}")

    @classmethod
    def open(
        cls,
        *,
        market_date: date,
        open_at_utc: datetime,
        close_at_utc: datetime,
        session_kind: CalendarSessionKind,
    ) -> CalendarDay:
        return cls(
            market_date=market_date,
            availability=CalendarAvailability.AVAILABLE,
            kind=CalendarDayKind.OPEN,
            open_at_utc=open_at_utc,
            close_at_utc=close_at_utc,
            session_kind=session_kind,
        )

    @classmethod
    def closed(cls, market_date: date) -> CalendarDay:
        return cls(
            market_date=market_date,
            availability=CalendarAvailability.AVAILABLE,
            kind=CalendarDayKind.CLOSED,
        )

    @classmethod
    def unavailable(cls, market_date: date, *, diagnostic: str) -> CalendarDay:
        return cls(
            market_date=market_date,
            availability=CalendarAvailability.UNAVAILABLE,
            kind=CalendarDayKind.UNKNOWN,
            reason_code=CalendarHealthReason.CALENDAR_UNAVAILABLE,
            diagnostic=diagnostic,
        )


@dataclass(frozen=True)
class CalendarHealthAssessment:
    status: CalendarHealth
    reason_codes: tuple[CalendarHealthReason, ...]
    date_classifiable: bool
    reviewed_through: date
    forward_horizon_months: int

    def __post_init__(self) -> None:
        if self.forward_horizon_months < 0:
            raise ValueError("forward_horizon_months cannot be negative")
