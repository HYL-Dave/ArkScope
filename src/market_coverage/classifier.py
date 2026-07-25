from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone

from .models import (
    CalendarAvailability,
    CalendarDay,
    CalendarDayKind,
    CalendarHealthAssessment,
    CalendarHealthReason,
    CoverageDayReason,
    CoverageDayStatus,
    DayCoverage,
    RthObservation,
    SlotCoverage,
    SlotCoverageStatus,
    TickerCoverage,
    TickerCoverageStatus,
)


_SESSION_SETTLE_BUFFER = timedelta(minutes=30)


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _as_utc(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if not _is_timezone_aware(value):
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def expected_slot_starts(
    open_at: datetime,
    close_at: datetime,
    interval: timedelta,
) -> tuple[datetime, ...]:
    open_at_utc = _as_utc(open_at, field_name="session open")
    close_at_utc = _as_utc(close_at, field_name="session close")
    if close_at_utc <= open_at_utc:
        raise ValueError("session open must be before session close")
    if not isinstance(interval, timedelta) or interval <= timedelta(0):
        raise ValueError("interval must be a positive timedelta")

    session_duration = close_at_utc - open_at_utc
    if session_duration % interval != timedelta(0):
        raise ValueError("interval must divide the session exactly")

    starts: list[datetime] = []
    cursor = open_at_utc
    while cursor < close_at_utc:
        starts.append(cursor)
        cursor += interval
    return tuple(starts)


class SlotCoverageClassifier:
    def classify(
        self,
        *,
        calendar_day: CalendarDay,
        calendar_health: CalendarHealthAssessment,
        universe: Sequence[str],
        observations: Iterable[RthObservation],
        interval: timedelta,
        now_et: datetime,
    ) -> DayCoverage:
        if not isinstance(calendar_day, CalendarDay):
            raise TypeError("calendar_day must be CalendarDay")
        if not isinstance(calendar_health, CalendarHealthAssessment):
            raise TypeError("calendar_health must be CalendarHealthAssessment")
        now_at_utc = _as_utc(now_et, field_name="now_et")
        canonical_universe = self._canonical_universe(universe)
        observation_rows = tuple(observations)
        if any(not isinstance(row, RthObservation) for row in observation_rows):
            raise TypeError("observations must contain RthObservation values")

        if not calendar_health.date_classifiable:
            if CalendarHealthReason.DATE_UNREVIEWED in calendar_health.reason_codes:
                reason = CoverageDayReason.DATE_UNREVIEWED
            elif (
                CalendarHealthReason.CALENDAR_UNAVAILABLE
                in calendar_health.reason_codes
            ):
                reason = CoverageDayReason.CALENDAR_UNAVAILABLE
            else:
                raise ValueError(
                    "unclassifiable calendar health requires a supported reason"
                )
            return DayCoverage(
                market_date=calendar_day.market_date,
                status=CoverageDayStatus.UNKNOWN,
                reason_code=reason,
                expected_slot_starts=None,
                ticker_coverages=None,
                unmatched_rth_row_count=None,
            )

        if (
            calendar_day.availability is CalendarAvailability.UNAVAILABLE
            or calendar_day.kind is CalendarDayKind.UNKNOWN
        ):
            raise ValueError(
                "classifiable calendar health cannot accompany an unavailable day"
            )

        if calendar_day.kind is CalendarDayKind.CLOSED:
            return DayCoverage(
                market_date=calendar_day.market_date,
                status=CoverageDayStatus.NON_TRADING,
                reason_code=None,
                expected_slot_starts=None,
                ticker_coverages=None,
                unmatched_rth_row_count=None,
            )

        if calendar_day.kind is not CalendarDayKind.OPEN:
            raise ValueError(f"unsupported calendar day kind: {calendar_day.kind!r}")
        open_at = calendar_day.open_at_utc
        close_at = calendar_day.close_at_utc
        assert open_at is not None
        assert close_at is not None
        starts = expected_slot_starts(open_at, close_at, interval)

        if now_at_utc < close_at + _SESSION_SETTLE_BUFFER:
            return DayCoverage(
                market_date=calendar_day.market_date,
                status=CoverageDayStatus.IN_PROGRESS,
                reason_code=None,
                expected_slot_starts=starts,
                ticker_coverages=None,
                unmatched_rth_row_count=None,
            )

        ticker_coverages, unmatched_count = self._classify_tickers(
            universe=canonical_universe,
            observations=observation_rows,
            starts=starts,
            open_at=open_at,
            close_at=close_at,
        )

        observed_ticker_count = sum(
            ticker.status is not TickerCoverageStatus.UNKNOWN
            for ticker in ticker_coverages
        )
        partial_ticker_count = sum(
            ticker.status is TickerCoverageStatus.PARTIAL
            for ticker in ticker_coverages
        )
        unknown_ticker_count = sum(
            ticker.status is TickerCoverageStatus.UNKNOWN
            for ticker in ticker_coverages
        )

        if observed_ticker_count == 0:
            status = CoverageDayStatus.UNKNOWN
            reason = CoverageDayReason.NO_OBSERVATIONS
        elif partial_ticker_count > 0:
            status = CoverageDayStatus.PARTIAL
            reason = None
        elif unknown_ticker_count > 0:
            status = CoverageDayStatus.INDETERMINATE_TICKERS
            reason = None
        else:
            status = CoverageDayStatus.COMPLETE
            reason = None

        return DayCoverage(
            market_date=calendar_day.market_date,
            status=status,
            reason_code=reason,
            expected_slot_starts=starts,
            ticker_coverages=ticker_coverages,
            unmatched_rth_row_count=unmatched_count,
        )

    @staticmethod
    def _canonical_universe(universe: Sequence[str]) -> tuple[str, ...]:
        if isinstance(universe, (str, bytes)):
            raise TypeError("universe must be a sequence of ticker strings")
        canonical: list[str] = []
        seen: set[str] = set()
        for ticker in universe:
            if not isinstance(ticker, str):
                raise TypeError("universe tickers must be strings")
            if not ticker or ticker != ticker.strip():
                raise ValueError("universe tickers must be non-empty canonical IDs")
            if ticker not in seen:
                seen.add(ticker)
                canonical.append(ticker)
        if not canonical:
            raise ValueError("universe must contain at least one canonical ticker")
        return tuple(canonical)

    @staticmethod
    def _classify_tickers(
        *,
        universe: tuple[str, ...],
        observations: tuple[RthObservation, ...],
        starts: tuple[datetime, ...],
        open_at: datetime,
        close_at: datetime,
    ) -> tuple[tuple[TickerCoverage, ...], int]:
        start_set = set(starts)
        universe_set = set(universe)
        observed_starts = {ticker: set() for ticker in universe}
        unmatched_count = 0

        for observation in observations:
            if observation.ticker not in universe_set:
                continue
            observed_at = _as_utc(
                observation.observed_at,
                field_name="observation timestamp",
            )
            if not open_at <= observed_at < close_at:
                continue
            if observed_at in start_set:
                observed_starts[observation.ticker].add(observed_at)
            else:
                unmatched_count += 1

        ticker_coverages = tuple(
            TickerCoverage(
                ticker=ticker,
                slots=tuple(
                    SlotCoverage(
                        start_at_utc=start,
                        status=(
                            SlotCoverageStatus.OBSERVED
                            if start in observed_starts[ticker]
                            else SlotCoverageStatus.UNKNOWN
                        ),
                    )
                    for start in starts
                ),
            )
            for ticker in universe
        )
        return ticker_coverages, unmatched_count
