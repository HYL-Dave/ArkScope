from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendar import (
    CalendarHealthComposer,
    OfficialSessionFixtures,
    XnysCalendarAdapter,
)
from .classifier import SlotCoverageClassifier
from .models import (
    CalendarDay,
    CalendarDayKind,
    CalendarHealth,
    CalendarHealthAssessment,
    ClosureReasonCode,
    CoverageCalendarHealthV2,
    CoverageDayReason,
    CoverageDayStatus,
    CoverageDayV2,
    CoverageObservationHealthV2,
    DayCoverage,
    ObservationHealth,
    ObservationReadResult,
    PartialTickerCoverageV2,
    TradingDayCoverageV2,
)
from .observations import RthObservationReader


_EASTERN = ZoneInfo("America/New_York")
_SUPPORTED_INTERVAL = "15min"
_INTERVAL_DURATION = timedelta(minutes=15)


def _current_et() -> datetime:
    return datetime.now(_EASTERN)


def _canonical_universe(universe: Sequence[str]) -> tuple[str, ...]:
    if isinstance(universe, (str, bytes)):
        raise TypeError("universe must be a sequence of ticker strings")

    canonical: list[str] = []
    seen: set[str] = set()
    for raw_ticker in universe:
        if not isinstance(raw_ticker, str):
            raise TypeError("universe tickers must be strings")
        ticker = raw_ticker.strip().upper()
        if not ticker:
            raise ValueError("universe tickers must be non-empty")
        if ticker not in seen:
            seen.add(ticker)
            canonical.append(ticker)
    if not canonical:
        raise ValueError("universe must contain at least one ticker")
    return tuple(canonical)


def _resolve_now_et(clock: Callable[[], datetime]) -> datetime:
    resolved = clock()
    if not isinstance(resolved, datetime):
        raise TypeError("clock must return a datetime")
    if resolved.tzinfo is None or resolved.utcoffset() is None:
        return resolved.replace(tzinfo=_EASTERN)
    return resolved.astimezone(_EASTERN)


def _requested_dates(*, as_of: date, lookback_days: int) -> tuple[date, ...]:
    return tuple(as_of - timedelta(days=offset) for offset in range(lookback_days + 1))


def _compose_calendar_health(
    assessments: tuple[CalendarHealthAssessment, ...],
) -> CoverageCalendarHealthV2:
    if not assessments:
        raise ValueError("calendar health requires at least one requested date")

    reviewed_through = assessments[0].reviewed_through
    forward_horizon = assessments[0].forward_horizon_months
    if any(item.reviewed_through != reviewed_through for item in assessments):
        raise ValueError("calendar assessments disagree on reviewed horizon")
    if any(item.forward_horizon_months != forward_horizon for item in assessments):
        raise ValueError("calendar assessments disagree on forward horizon")

    if any(item.status is CalendarHealth.UNAVAILABLE for item in assessments):
        status = CalendarHealth.UNAVAILABLE
    elif any(item.status is CalendarHealth.DEGRADED for item in assessments):
        status = CalendarHealth.DEGRADED
    else:
        status = CalendarHealth.OK

    reasons = []
    seen_reasons = set()
    for assessment in assessments:
        for reason in assessment.reason_codes:
            if reason not in seen_reasons:
                seen_reasons.add(reason)
                reasons.append(reason)

    return CoverageCalendarHealthV2(
        status=status,
        reason_codes=reasons,
        reviewed_through=reviewed_through.isoformat(),
        forward_horizon_months=forward_horizon,
    )


def _observation_unavailable(market_date: date) -> DayCoverage:
    return DayCoverage(
        market_date=market_date,
        status=CoverageDayStatus.UNKNOWN,
        reason_code=CoverageDayReason.OBSERVATION_UNAVAILABLE,
        expected_slot_starts=None,
        ticker_coverages=None,
        unmatched_rth_row_count=None,
    )


def _project_day(
    *,
    calendar_day: CalendarDay,
    calendar_health: CalendarHealthAssessment,
    coverage: DayCoverage,
) -> CoverageDayV2:
    closure_reason = None
    if coverage.status is CoverageDayStatus.NON_TRADING:
        closure_reason = (
            ClosureReasonCode.WEEKEND
            if coverage.market_date.weekday() >= 5
            else ClosureReasonCode.MARKET_CLOSED
        )

    has_session_facts = (
        calendar_health.date_classifiable
        and calendar_day.kind is CalendarDayKind.OPEN
    )
    open_at = calendar_day.open_at_utc if has_session_facts else None
    close_at = calendar_day.close_at_utc if has_session_facts else None
    session_kind = calendar_day.session_kind if has_session_facts else None

    return CoverageDayV2(
        date=coverage.market_date.isoformat(),
        coverage_status=coverage.status,
        status_reason_code=coverage.reason_code,
        closure_reason_code=closure_reason,
        session_kind=session_kind,
        session_open_at_utc=open_at.isoformat() if open_at is not None else None,
        session_close_at_utc=close_at.isoformat() if close_at is not None else None,
        expected_slot_count=coverage.expected_slot_count,
        observed_ticker_count=coverage.observed_ticker_count,
        complete_ticker_count=coverage.complete_ticker_count,
        partial_ticker_count=coverage.partial_ticker_count,
        unknown_ticker_count=coverage.unknown_ticker_count,
        partial_tickers=[
            PartialTickerCoverageV2(
                ticker=ticker.ticker,
                observed_slot_count=ticker.observed_slot_count,
                expected_slot_count=ticker.expected_slot_count,
            )
            for ticker in coverage.partial_tickers
        ],
        unknown_tickers=list(coverage.unknown_tickers),
        unmatched_rth_row_count=coverage.unmatched_rth_row_count,
    )


class TradingDayCoverageService:
    def __init__(
        self,
        *,
        db_path: str | Path,
        fixtures: OfficialSessionFixtures | None = None,
        calendar_adapter: XnysCalendarAdapter | None = None,
        calendar_health_composer: CalendarHealthComposer | None = None,
        observation_reader: RthObservationReader | None = None,
        classifier: SlotCoverageClassifier | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        fixture_authority = (
            OfficialSessionFixtures() if fixtures is None else fixtures
        )
        self._calendar = (
            XnysCalendarAdapter(fixtures=fixture_authority)
            if calendar_adapter is None
            else calendar_adapter
        )
        self._calendar_health = (
            CalendarHealthComposer(fixtures=fixture_authority)
            if calendar_health_composer is None
            else calendar_health_composer
        )
        self._observations = (
            RthObservationReader(db_path)
            if observation_reader is None
            else observation_reader
        )
        self._classifier = (
            SlotCoverageClassifier() if classifier is None else classifier
        )
        self._clock = _current_et if clock is None else clock

    def get_coverage(
        self,
        *,
        universe: Sequence[str],
        interval: str,
        lookback_days: int,
    ) -> TradingDayCoverageV2:
        if interval != _SUPPORTED_INTERVAL:
            raise ValueError("Coverage v2 supports interval=15min only")
        if (
            not isinstance(lookback_days, int)
            or isinstance(lookback_days, bool)
            or not 1 <= lookback_days <= 120
        ):
            raise ValueError("lookback_days must be an integer from 1 through 120")

        now_et = _resolve_now_et(self._clock)
        canonical_universe = _canonical_universe(universe)
        requested_dates = _requested_dates(
            as_of=now_et.date(),
            lookback_days=lookback_days,
        )
        calendar_days = tuple(
            self._calendar.session(market_date)
            for market_date in requested_dates
        )
        calendar_health = tuple(
            self._calendar_health.compose(
                requested_day=market_date,
                as_of=now_et.date(),
                resolution=calendar_day,
            )
            for market_date, calendar_day in zip(
                requested_dates,
                calendar_days,
                strict=True,
            )
        )

        readable_sessions = tuple(
            calendar_day
            for calendar_day, health in zip(
                calendar_days,
                calendar_health,
                strict=True,
            )
            if health.date_classifiable
            and calendar_day.kind is CalendarDayKind.OPEN
        )
        observation_result = self._observations.read(
            universe=canonical_universe,
            sessions=readable_sessions,
            interval=interval,
        )
        days = self._classify_days(
            calendar_days=calendar_days,
            calendar_health=calendar_health,
            observations=observation_result,
            universe=canonical_universe,
            now_et=now_et,
        )

        return TradingDayCoverageV2(
            lookback_days=lookback_days,
            universe_count=len(canonical_universe),
            generated_at_et=now_et.isoformat(),
            calendar_health=_compose_calendar_health(calendar_health),
            observation_health=CoverageObservationHealthV2(
                status=observation_result.health.status,
                reason_code=observation_result.health.reason_code,
            ),
            days=days,
            provider_errors=list(observation_result.provider_errors),
        )

    def _classify_days(
        self,
        *,
        calendar_days: tuple[CalendarDay, ...],
        calendar_health: tuple[CalendarHealthAssessment, ...],
        observations: ObservationReadResult,
        universe: tuple[str, ...],
        now_et: datetime,
    ) -> list[CoverageDayV2]:
        projected: list[CoverageDayV2] = []
        for calendar_day, health in zip(
            calendar_days,
            calendar_health,
            strict=True,
        ):
            if (
                observations.health.status is ObservationHealth.UNAVAILABLE
                and health.date_classifiable
                and calendar_day.kind is CalendarDayKind.OPEN
            ):
                coverage = _observation_unavailable(calendar_day.market_date)
            else:
                coverage = self._classifier.classify(
                    calendar_day=calendar_day,
                    calendar_health=health,
                    universe=universe,
                    observations=observations.observations_for(
                        calendar_day.market_date
                    ),
                    interval=_INTERVAL_DURATION,
                    now_et=now_et,
                )
            projected.append(
                _project_day(
                    calendar_day=calendar_day,
                    calendar_health=health,
                    coverage=coverage,
                )
            )
        return projected
