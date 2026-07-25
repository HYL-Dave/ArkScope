from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from src.market_coverage.models import CalendarDay, CalendarSessionKind


UTC = timezone.utc
EASTERN = ZoneInfo("America/New_York")
INTERVAL = timedelta(minutes=15)


def _api() -> SimpleNamespace:
    from src.market_coverage.classifier import (
        SlotCoverageClassifier,
        expected_slot_starts,
    )
    from src.market_coverage.models import (
        CalendarHealth,
        CalendarHealthAssessment,
        CalendarHealthReason,
        CoverageDayReason,
        CoverageDayStatus,
        RthObservation,
        SlotCoverageStatus,
        TickerCoverageStatus,
    )

    return SimpleNamespace(
        CoverageDayReason=CoverageDayReason,
        CoverageDayStatus=CoverageDayStatus,
        RthObservation=RthObservation,
        CalendarHealth=CalendarHealth,
        CalendarHealthAssessment=CalendarHealthAssessment,
        CalendarHealthReason=CalendarHealthReason,
        SlotCoverageClassifier=SlotCoverageClassifier,
        SlotCoverageStatus=SlotCoverageStatus,
        TickerCoverageStatus=TickerCoverageStatus,
        expected_slot_starts=expected_slot_starts,
    )


def _regular_day() -> CalendarDay:
    return CalendarDay.open(
        market_date=date(2026, 7, 24),
        open_at_utc=datetime(2026, 7, 24, 13, 30, tzinfo=UTC),
        close_at_utc=datetime(2026, 7, 24, 20, 0, tzinfo=UTC),
        session_kind=CalendarSessionKind.REGULAR,
    )


def _early_close_day() -> CalendarDay:
    return CalendarDay.open(
        market_date=date(2026, 11, 27),
        open_at_utc=datetime(2026, 11, 27, 14, 30, tzinfo=UTC),
        close_at_utc=datetime(2026, 11, 27, 18, 0, tzinfo=UTC),
        session_kind=CalendarSessionKind.EARLY_CLOSE,
    )


def _fixture_slot_starts(
    day: CalendarDay,
    interval: timedelta = INTERVAL,
) -> tuple[datetime, ...]:
    assert day.open_at_utc is not None
    assert day.close_at_utc is not None
    starts: list[datetime] = []
    cursor = day.open_at_utc
    while cursor < day.close_at_utc:
        starts.append(cursor)
        cursor += interval
    return tuple(starts)


def _rows(
    api: SimpleNamespace,
    ticker: str,
    starts: tuple[datetime, ...],
) -> tuple[object, ...]:
    return tuple(
        api.RthObservation(ticker=ticker, observed_at=start) for start in starts
    )


def _classify(
    api: SimpleNamespace,
    *,
    day: CalendarDay,
    universe: tuple[str, ...],
    observations: tuple[object, ...] = (),
    now_et: datetime,
    calendar_health=None,
    interval: timedelta = INTERVAL,
):
    if calendar_health is None:
        if day.availability.value == "unavailable":
            calendar_health = api.CalendarHealthAssessment(
                status=api.CalendarHealth.UNAVAILABLE,
                reason_codes=(api.CalendarHealthReason.CALENDAR_UNAVAILABLE,),
                date_classifiable=False,
                reviewed_through=date(2027, 12, 31),
                forward_horizon_months=12,
            )
        else:
            calendar_health = api.CalendarHealthAssessment(
                status=api.CalendarHealth.OK,
                reason_codes=(),
                date_classifiable=True,
                reviewed_through=date(2027, 12, 31),
                forward_horizon_months=12,
            )
    return api.SlotCoverageClassifier().classify(
        calendar_day=day,
        calendar_health=calendar_health,
        universe=universe,
        observations=observations,
        interval=interval,
        now_et=now_et,
    )


def _ticker(result, ticker: str):
    assert result.ticker_coverages is not None
    return next(item for item in result.ticker_coverages if item.ticker == ticker)


def test_precedence_calendar_unavailable_is_unknown():
    api = _api()
    regular_day = _regular_day()
    unavailable_day = CalendarDay.unavailable(
        regular_day.market_date,
        diagnostic="offline calendar failed",
    )
    observations = _rows(api, "AAA", _fixture_slot_starts(regular_day))

    result = _classify(
        api,
        day=unavailable_day,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.UNKNOWN
    assert result.reason_code is api.CoverageDayReason.CALENDAR_UNAVAILABLE
    assert result.expected_slot_count is None
    assert result.observed_ticker_count is None
    assert result.complete_ticker_count is None
    assert result.partial_ticker_count is None
    assert result.unknown_ticker_count is None
    assert result.ticker_coverages is None
    assert result.unmatched_rth_row_count is None
    assert not hasattr(result, "closed_ticker_count")
    assert not hasattr(result, "unclassifiable_ticker_count")
    with pytest.raises(FrozenInstanceError):
        result.status = api.CoverageDayStatus.COMPLETE
    with pytest.raises(ValueError):
        replace(result, status=api.CoverageDayStatus.COMPLETE)

    from src.market_coverage.calendar import (
        CalendarHealthComposer,
        OfficialSessionFixtures,
        XnysCalendarAdapter,
    )

    unreviewed_day = date(2024, 12, 31)
    fixtures = OfficialSessionFixtures()
    unreviewed_resolution = XnysCalendarAdapter(fixtures=fixtures).session(
        unreviewed_day
    )
    unreviewed_health = CalendarHealthComposer(fixtures=fixtures).compose(
        requested_day=unreviewed_day,
        as_of=date(2026, 7, 26),
        resolution=unreviewed_resolution,
    )
    unreviewed = _classify(
        api,
        day=unreviewed_resolution,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
        calendar_health=unreviewed_health,
    )

    assert unreviewed.status is api.CoverageDayStatus.UNKNOWN
    assert unreviewed.reason_code is api.CoverageDayReason.DATE_UNREVIEWED
    assert unreviewed.expected_slot_count is None
    assert unreviewed.observed_ticker_count is None
    assert unreviewed.ticker_coverages is None
    assert unreviewed.unmatched_rth_row_count is None


def test_precedence_reviewed_closed_day_is_non_trading():
    api = _api()
    closed_day = CalendarDay.closed(date(2026, 7, 25))
    observations = (
        api.RthObservation(
            ticker="AAA",
            observed_at=datetime(2026, 7, 25, 14, 0, tzinfo=UTC),
        ),
    )

    result = _classify(
        api,
        day=closed_day,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 7, 25, 18, 0, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.NON_TRADING
    assert result.reason_code is None
    assert result.expected_slot_count is None
    assert result.observed_ticker_count is None
    assert result.complete_ticker_count is None
    assert result.partial_ticker_count is None
    assert result.unknown_ticker_count is None
    assert result.ticker_coverages is None
    assert result.unmatched_rth_row_count is None


def test_precedence_pre_close_buffer_is_in_progress():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    observations = _rows(api, "AAA", starts) + _rows(api, "BBB", starts)

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB"),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 29, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.IN_PROGRESS
    assert result.reason_code is None
    assert result.expected_slot_starts == starts
    assert result.expected_slot_count == len(starts)
    assert result.observed_ticker_count is None
    assert result.complete_ticker_count is None
    assert result.partial_ticker_count is None
    assert result.unknown_ticker_count is None
    assert result.ticker_coverages is None
    assert result.unmatched_rth_row_count is None


def test_precedence_completed_all_zero_is_unknown():
    api = _api()
    day = _regular_day()

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB"),
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.UNKNOWN
    assert result.reason_code is api.CoverageDayReason.NO_OBSERVATIONS
    assert result.observed_ticker_count == 0
    assert result.complete_ticker_count == 0
    assert result.partial_ticker_count == 0
    assert result.unknown_ticker_count == len(("AAA", "BBB"))
    assert result.unknown_tickers == ("AAA", "BBB")
    assert result.unmatched_rth_row_count == 0
    for ticker in result.ticker_coverages or ():
        assert ticker.status is api.TickerCoverageStatus.UNKNOWN
        assert ticker.observed_slot_count == 0
        assert all(
            slot.status is api.SlotCoverageStatus.UNKNOWN
            for slot in ticker.slots
        )


def test_precedence_observed_partial_ticker_is_partial():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    observations = _rows(api, "AAA", starts[:1]) + _rows(api, "BBB", starts)

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB"),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.PARTIAL
    assert result.partial_ticker_count == 1
    assert result.complete_ticker_count == 1
    assert result.unknown_ticker_count == 0
    assert tuple(item.ticker for item in result.partial_tickers) == ("AAA",)


def test_precedence_complete_observed_cohort_with_unknown_is_indeterminate():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB"),
        observations=_rows(api, "AAA", starts),
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.INDETERMINATE_TICKERS
    assert result.complete_ticker_count == 1
    assert result.partial_ticker_count == 0
    assert result.unknown_ticker_count == 1
    assert result.unknown_tickers == ("BBB",)


def test_precedence_all_tickers_complete_is_complete():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    observations = _rows(api, "AAA", starts) + _rows(api, "BBB", starts)

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB"),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.COMPLETE
    assert result.complete_ticker_count == len(("AAA", "BBB"))
    assert result.partial_ticker_count == 0
    assert result.unknown_ticker_count == 0
    assert result.observed_ticker_count == len(("AAA", "BBB"))
    assert {
        status.value for status in api.CoverageDayStatus
    } == {
        "unknown",
        "non_trading",
        "in_progress",
        "partial",
        "indeterminate_tickers",
        "complete",
    }
    assert not any(
        status.value.startswith("complete_") for status in api.CoverageDayStatus
    )


def test_regular_session_grid_uses_exact_half_open_slot_starts():
    api = _api()
    day = _regular_day()
    assert day.open_at_utc is not None
    assert day.close_at_utc is not None
    expected = _fixture_slot_starts(day)

    actual = api.expected_slot_starts(
        day.open_at_utc,
        day.close_at_utc,
        INTERVAL,
    )

    assert actual == expected
    assert actual[0] == day.open_at_utc
    assert actual[-1] == day.close_at_utc - INTERVAL
    assert day.close_at_utc not in actual
    assert len(actual) == (day.close_at_utc - day.open_at_utc) // INTERVAL
    result = _classify(
        api,
        day=day,
        universe=("AAA",),
        observations=_rows(api, "AAA", expected + (day.close_at_utc,)),
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )
    assert result.status is api.CoverageDayStatus.COMPLETE
    assert result.unmatched_rth_row_count == 0
    with pytest.raises(ValueError, match="divide"):
        api.expected_slot_starts(
            day.open_at_utc,
            day.close_at_utc,
            timedelta(minutes=20),
        )


def test_early_close_grid_uses_exact_half_open_slot_starts():
    api = _api()
    day = _early_close_day()
    assert day.open_at_utc is not None
    assert day.close_at_utc is not None
    expected = _fixture_slot_starts(day)

    actual = api.expected_slot_starts(
        day.open_at_utc,
        day.close_at_utc,
        INTERVAL,
    )

    assert actual == expected
    assert actual[0] == day.open_at_utc
    assert actual[-1] == day.close_at_utc - INTERVAL
    assert day.close_at_utc not in actual
    assert len(actual) == (day.close_at_utc - day.open_at_utc) // INTERVAL


def test_early_close_buffer_changes_only_at_1329_1330():
    api = _api()
    day = _early_close_day()
    starts = _fixture_slot_starts(day)
    observations = _rows(api, "AAA", starts)

    before = _classify(
        api,
        day=day,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 11, 27, 13, 29, tzinfo=EASTERN),
    )
    at_boundary = _classify(
        api,
        day=day,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 11, 27, 13, 30, tzinfo=EASTERN),
    )

    assert before.status is api.CoverageDayStatus.IN_PROGRESS
    assert at_boundary.status is api.CoverageDayStatus.COMPLETE
    with pytest.raises(ValueError, match="timezone-aware"):
        _classify(
            api,
            day=day,
            universe=("AAA",),
            observations=observations,
            now_et=datetime.combine(day.market_date, time(13, 30)),
        )


def test_partial_plus_unknown_stays_partial_and_preserves_unknowns():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    observations = _rows(api, "AAA", starts[:1]) + _rows(api, "CCC", starts)

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB", "CCC"),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.PARTIAL
    assert result.complete_ticker_count == 1
    assert result.partial_ticker_count == 1
    assert result.unknown_ticker_count == 1
    assert tuple(item.ticker for item in result.partial_tickers) == ("AAA",)
    assert result.unknown_tickers == ("BBB",)


def test_completed_day_count_equations_hold():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    observations = _rows(api, "AAA", starts) + _rows(api, "BBB", starts[:1])

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB", "CCC"),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.ticker_coverages is not None
    assert (
        result.complete_ticker_count
        + result.partial_ticker_count
        + result.unknown_ticker_count
        == len(("AAA", "BBB", "CCC"))
    )
    assert result.observed_ticker_count == (
        result.complete_ticker_count + result.partial_ticker_count
    )
    assert result.unknown_ticker_count == len(result.unknown_tickers)
    assert result.expected_slot_count == len(starts)
    assert all(
        ticker.expected_slot_count == result.expected_slot_count
        for ticker in result.ticker_coverages
    )
    with pytest.raises(FrozenInstanceError):
        result.ticker_coverages[0].ticker = "CHANGED"
    with pytest.raises(FrozenInstanceError):
        result.ticker_coverages[0].slots[0].status = api.SlotCoverageStatus.UNKNOWN
    with pytest.raises(ValueError):
        replace(result, status=api.CoverageDayStatus.COMPLETE)
    with pytest.raises(ValueError, match="non-negative"):
        replace(result, unmatched_rth_row_count=-1)
    with pytest.raises(TypeError, match="sequence"):
        _classify(
            api,
            day=day,
            universe="AAA",
            observations=observations,
            now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
        )
    with pytest.raises(TypeError, match="string"):
        api.RthObservation(ticker=b"AAA", observed_at=starts[0])
    with pytest.raises(TypeError, match="string"):
        replace(result.ticker_coverages[0], ticker=b"AAA")
    with pytest.raises(TypeError, match="market_date"):
        replace(
            result,
            market_date=datetime(2026, 7, 24, tzinfo=UTC),
        )


def test_in_window_off_grid_row_is_counted():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    off_grid = starts[0] + timedelta(minutes=1)
    observations = (
        _rows(api, "AAA", starts)
        + _rows(api, "AAA", (off_grid,))
        + _rows(api, "AAA", (off_grid,))
    )

    result = _classify(
        api,
        day=day,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.COMPLETE
    assert result.unmatched_rth_row_count == len((off_grid, off_grid))
    assert _ticker(result, "AAA").observed_slot_count == len(starts)


def test_off_grid_row_does_not_fill_nearest_slot():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    target = starts[-1]
    assert day.close_at_utc is not None
    nearest_but_off_grid = day.close_at_utc - timedelta(seconds=1)
    observations = _rows(api, "AAA", starts[:-1] + (nearest_but_off_grid,))

    result = _classify(
        api,
        day=day,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    ticker = _ticker(result, "AAA")
    assert result.status is api.CoverageDayStatus.PARTIAL
    assert result.unmatched_rth_row_count == 1
    assert ticker.observed_slot_count == len(starts) - 1
    target_slot = next(
        slot for slot in ticker.slots if slot.start_at_utc == target
    )
    assert target_slot.status is api.SlotCoverageStatus.UNKNOWN


def test_alias_collision_fills_one_slot_only():
    api = _api()
    day = _regular_day()
    start = _fixture_slot_starts(day)[0]
    canonical_row = api.RthObservation(ticker="AAA", observed_at=start)
    alias_row_after_canonicalization = api.RthObservation(
        ticker="AAA",
        observed_at=start.astimezone(EASTERN),
    )

    result = _classify(
        api,
        day=day,
        universe=("AAA",),
        observations=(canonical_row, alias_row_after_canonicalization),
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    ticker = _ticker(result, "AAA")
    assert result.status is api.CoverageDayStatus.PARTIAL
    assert ticker.observed_slot_count == 1
    assert sum(
        slot.status is api.SlotCoverageStatus.OBSERVED for slot in ticker.slots
    ) == 1
    assert result.unmatched_rth_row_count == 0


def test_extended_hours_rows_never_fill_rth_slots():
    api = _api()
    day = _regular_day()
    assert day.open_at_utc is not None
    assert day.close_at_utc is not None
    observations = _rows(
        api,
        "AAA",
        (
            day.open_at_utc - INTERVAL,
            day.close_at_utc,
            day.close_at_utc + INTERVAL,
        ),
    )

    result = _classify(
        api,
        day=day,
        universe=("AAA",),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    ticker = _ticker(result, "AAA")
    assert result.status is api.CoverageDayStatus.UNKNOWN
    assert ticker.status is api.TickerCoverageStatus.UNKNOWN
    assert ticker.observed_slot_count == 0
    assert result.unmatched_rth_row_count == 0


def test_uniform_truncation_is_partial():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    truncated = starts[:-1]
    universe = ("AAA", "BBB", "CCC")
    observations = tuple(
        observation
        for ticker in universe
        for observation in _rows(api, ticker, truncated)
    )

    result = _classify(
        api,
        day=day,
        universe=universe,
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.PARTIAL
    assert result.complete_ticker_count == 0
    assert result.partial_ticker_count == len(universe)
    assert result.unknown_ticker_count == 0
    assert all(
        ticker.observed_slot_count == len(truncated)
        for ticker in result.ticker_coverages or ()
    )


def test_single_complete_outlier_does_not_hide_truncation():
    api = _api()
    day = _regular_day()
    starts = _fixture_slot_starts(day)
    truncated = starts[:-1]
    observations = (
        _rows(api, "AAA", starts)
        + _rows(api, "BBB", truncated)
        + _rows(api, "CCC", truncated)
    )

    result = _classify(
        api,
        day=day,
        universe=("AAA", "BBB", "CCC"),
        observations=observations,
        now_et=datetime(2026, 7, 24, 16, 30, tzinfo=EASTERN),
    )

    assert result.status is api.CoverageDayStatus.PARTIAL
    assert result.complete_ticker_count == 1
    assert result.partial_ticker_count == len(("BBB", "CCC"))
    assert result.unknown_ticker_count == 0
    assert tuple(item.ticker for item in result.partial_tickers) == ("BBB", "CCC")
