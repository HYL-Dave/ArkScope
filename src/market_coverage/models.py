from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
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


class SlotCoverageStatus(str, Enum):
    OBSERVED = "observed"
    UNKNOWN = "unknown"


class TickerCoverageStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CoverageDayStatus(str, Enum):
    UNKNOWN = "unknown"
    NON_TRADING = "non_trading"
    IN_PROGRESS = "in_progress"
    PARTIAL = "partial"
    INDETERMINATE_TICKERS = "indeterminate_tickers"
    COMPLETE = "complete"


class CoverageDayReason(str, Enum):
    CALENDAR_UNAVAILABLE = "calendar_unavailable"
    DATE_UNREVIEWED = "date_unreviewed"
    OBSERVATION_UNAVAILABLE = "observation_unavailable"
    NO_OBSERVATIONS = "no_observations"


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _require_utc(value: datetime, *, field_name: str) -> None:
    if not _is_timezone_aware(value):
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must have zero UTC offset")


@dataclass(frozen=True)
class RthObservation:
    ticker: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.ticker or self.ticker != self.ticker.strip():
            raise ValueError("observation ticker must be a non-empty canonical ID")
        if not _is_timezone_aware(self.observed_at):
            raise ValueError("observation timestamp must be timezone-aware")


@dataclass(frozen=True)
class SlotCoverage:
    start_at_utc: datetime
    status: SlotCoverageStatus

    def __post_init__(self) -> None:
        _require_utc(self.start_at_utc, field_name="slot start")
        if not isinstance(self.status, SlotCoverageStatus):
            raise TypeError("slot status must be SlotCoverageStatus")


@dataclass(frozen=True)
class TickerCoverage:
    ticker: str
    slots: tuple[SlotCoverage, ...]

    def __post_init__(self) -> None:
        if not self.ticker or self.ticker != self.ticker.strip():
            raise ValueError("ticker must be a non-empty canonical ID")
        if not isinstance(self.slots, tuple) or not self.slots:
            raise ValueError("ticker coverage requires a non-empty slot tuple")
        if any(not isinstance(slot, SlotCoverage) for slot in self.slots):
            raise TypeError("ticker slots must contain SlotCoverage values")

        starts = tuple(slot.start_at_utc for slot in self.slots)
        if starts != tuple(sorted(starts)) or len(starts) != len(set(starts)):
            raise ValueError("ticker slots must have unique ordered starts")

    @property
    def expected_slot_count(self) -> int:
        return len(self.slots)

    @property
    def observed_slot_count(self) -> int:
        return sum(
            slot.status is SlotCoverageStatus.OBSERVED for slot in self.slots
        )

    @property
    def status(self) -> TickerCoverageStatus:
        if self.observed_slot_count == self.expected_slot_count:
            return TickerCoverageStatus.COMPLETE
        if self.observed_slot_count > 0:
            return TickerCoverageStatus.PARTIAL
        return TickerCoverageStatus.UNKNOWN


@dataclass(frozen=True)
class DayCoverage:
    market_date: date
    status: CoverageDayStatus
    reason_code: CoverageDayReason | None
    expected_slot_starts: tuple[datetime, ...] | None
    ticker_coverages: tuple[TickerCoverage, ...] | None
    unmatched_rth_row_count: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.market_date, date):
            raise TypeError("market_date must be a date")
        if not isinstance(self.status, CoverageDayStatus):
            raise TypeError("day status must be CoverageDayStatus")
        if self.reason_code is not None and not isinstance(
            self.reason_code,
            CoverageDayReason,
        ):
            raise TypeError("day reason must be CoverageDayReason")

        self._validate_expected_slots()
        self._validate_ticker_coverages()

        if self.status is CoverageDayStatus.NON_TRADING:
            self._require_absent_classification()
            if self.reason_code is not None:
                raise ValueError("non-trading coverage cannot carry a reason")
            return

        if self.status is CoverageDayStatus.IN_PROGRESS:
            if self.expected_slot_starts is None:
                raise ValueError("in-progress coverage requires expected slots")
            if self.ticker_coverages is not None:
                raise ValueError("in-progress coverage cannot classify tickers")
            if self.unmatched_rth_row_count is not None:
                raise ValueError("in-progress coverage cannot count unmatched rows")
            if self.reason_code is not None:
                raise ValueError("in-progress coverage cannot carry a reason")
            return

        if self.status is CoverageDayStatus.UNKNOWN and self.ticker_coverages is None:
            self._require_absent_classification()
            if self.reason_code not in {
                CoverageDayReason.CALENDAR_UNAVAILABLE,
                CoverageDayReason.DATE_UNREVIEWED,
                CoverageDayReason.OBSERVATION_UNAVAILABLE,
            }:
                raise ValueError("unclassifiable coverage requires a typed reason")
            return

        self._validate_completed_classification()

    def _validate_expected_slots(self) -> None:
        if self.expected_slot_starts is None:
            return
        if (
            not isinstance(self.expected_slot_starts, tuple)
            or not self.expected_slot_starts
        ):
            raise ValueError("expected slots must be a non-empty tuple")
        for start in self.expected_slot_starts:
            _require_utc(start, field_name="expected slot start")
        if self.expected_slot_starts != tuple(sorted(self.expected_slot_starts)):
            raise ValueError("expected slot starts must be ordered")
        if len(self.expected_slot_starts) != len(set(self.expected_slot_starts)):
            raise ValueError("expected slot starts must be unique")

    def _validate_ticker_coverages(self) -> None:
        if self.ticker_coverages is None:
            return
        if not isinstance(self.ticker_coverages, tuple) or not self.ticker_coverages:
            raise ValueError("completed coverage requires ticker classifications")
        if any(
            not isinstance(ticker, TickerCoverage)
            for ticker in self.ticker_coverages
        ):
            raise TypeError("ticker_coverages must contain TickerCoverage values")

        ticker_ids = tuple(ticker.ticker for ticker in self.ticker_coverages)
        if len(ticker_ids) != len(set(ticker_ids)):
            raise ValueError("ticker classifications must be unique")
        if self.expected_slot_starts is None:
            raise ValueError("ticker classifications require expected slots")
        for ticker in self.ticker_coverages:
            starts = tuple(slot.start_at_utc for slot in ticker.slots)
            if starts != self.expected_slot_starts:
                raise ValueError("every ticker must use the day's expected slots")

    def _require_absent_classification(self) -> None:
        if self.expected_slot_starts is not None:
            raise ValueError("unclassifiable coverage cannot carry expected slots")
        if self.ticker_coverages is not None:
            raise ValueError("unclassifiable coverage cannot classify tickers")
        if self.unmatched_rth_row_count is not None:
            raise ValueError("unclassifiable coverage cannot count unmatched rows")

    def _validate_completed_classification(self) -> None:
        if self.expected_slot_starts is None or self.ticker_coverages is None:
            raise ValueError("completed-session coverage requires slot facts")
        if (
            not isinstance(self.unmatched_rth_row_count, int)
            or isinstance(self.unmatched_rth_row_count, bool)
            or self.unmatched_rth_row_count < 0
        ):
            raise ValueError("unmatched_rth_row_count must be a non-negative integer")

        observed_count = self.observed_ticker_count
        partial_count = self.partial_ticker_count
        unknown_count = self.unknown_ticker_count
        assert observed_count is not None
        assert partial_count is not None
        assert unknown_count is not None

        if observed_count == 0:
            derived_status = CoverageDayStatus.UNKNOWN
            derived_reason = CoverageDayReason.NO_OBSERVATIONS
        elif partial_count > 0:
            derived_status = CoverageDayStatus.PARTIAL
            derived_reason = None
        elif unknown_count > 0:
            derived_status = CoverageDayStatus.INDETERMINATE_TICKERS
            derived_reason = None
        else:
            derived_status = CoverageDayStatus.COMPLETE
            derived_reason = None

        if self.status is not derived_status or self.reason_code is not derived_reason:
            raise ValueError("day status and reason must match ticker slot facts")

    @property
    def expected_slot_count(self) -> int | None:
        if self.expected_slot_starts is None:
            return None
        return len(self.expected_slot_starts)

    @property
    def observed_ticker_count(self) -> int | None:
        if self.ticker_coverages is None:
            return None
        return sum(
            ticker.status is not TickerCoverageStatus.UNKNOWN
            for ticker in self.ticker_coverages
        )

    @property
    def complete_ticker_count(self) -> int | None:
        if self.ticker_coverages is None:
            return None
        return sum(
            ticker.status is TickerCoverageStatus.COMPLETE
            for ticker in self.ticker_coverages
        )

    @property
    def partial_ticker_count(self) -> int | None:
        if self.ticker_coverages is None:
            return None
        return sum(
            ticker.status is TickerCoverageStatus.PARTIAL
            for ticker in self.ticker_coverages
        )

    @property
    def unknown_ticker_count(self) -> int | None:
        if self.ticker_coverages is None:
            return None
        return sum(
            ticker.status is TickerCoverageStatus.UNKNOWN
            for ticker in self.ticker_coverages
        )

    @property
    def partial_tickers(self) -> tuple[TickerCoverage, ...]:
        if self.ticker_coverages is None:
            return ()
        return tuple(
            ticker
            for ticker in self.ticker_coverages
            if ticker.status is TickerCoverageStatus.PARTIAL
        )

    @property
    def unknown_tickers(self) -> tuple[str, ...]:
        if self.ticker_coverages is None:
            return ()
        return tuple(
            ticker.ticker
            for ticker in self.ticker_coverages
            if ticker.status is TickerCoverageStatus.UNKNOWN
        )


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
            if (
                open_at.utcoffset() != timedelta(0)
                or close_at.utcoffset() != timedelta(0)
            ):
                raise ValueError("session datetimes must have zero UTC offset")
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

        if self.status is CalendarHealth.OK:
            if self.reason_codes or not self.date_classifiable:
                raise ValueError(
                    "ok health requires no reasons and a classifiable date"
                )
            return

        if self.status is CalendarHealth.UNAVAILABLE:
            if (
                self.reason_codes
                != (CalendarHealthReason.CALENDAR_UNAVAILABLE,)
                or self.date_classifiable
            ):
                raise ValueError(
                    "unavailable health requires calendar_unavailable and an "
                    "unclassifiable date"
                )
            return

        if self.status is CalendarHealth.DEGRADED:
            if not self.reason_codes:
                raise ValueError("degraded health requires at least one reason")
            if CalendarHealthReason.CALENDAR_UNAVAILABLE in self.reason_codes:
                raise ValueError("degraded health cannot be calendar_unavailable")
            has_unreviewed_date = (
                CalendarHealthReason.DATE_UNREVIEWED in self.reason_codes
            )
            if self.date_classifiable is has_unreviewed_date:
                raise ValueError(
                    "date_unreviewed must exactly match an unclassifiable date"
                )
            return

        raise ValueError(f"unsupported calendar health status: {self.status!r}")
