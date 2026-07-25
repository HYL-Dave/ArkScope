from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest


def test_calendar_adapter_returns_typed_regular_session():
    from src.market_coverage.calendar import XnysCalendarAdapter
    from src.market_coverage.models import (
        CalendarAvailability,
        CalendarDay,
        CalendarDayKind,
        CalendarSessionKind,
        CoverageSession,
        MarketScope,
    )

    market_date = date(2026, 7, 24)
    result = XnysCalendarAdapter().session(market_date)

    assert isinstance(result, CalendarDay)
    assert result.market_date == market_date
    assert result.availability is CalendarAvailability.AVAILABLE
    assert result.kind is CalendarDayKind.OPEN
    assert result.session_kind is CalendarSessionKind.REGULAR
    assert result.open_at_utc == datetime(2026, 7, 24, 13, 30, tzinfo=timezone.utc)
    assert result.close_at_utc == datetime(2026, 7, 24, 20, 0, tzinfo=timezone.utc)
    assert type(result.open_at_utc) is datetime
    assert type(result.close_at_utc) is datetime
    assert result.open_at_utc.tzinfo is timezone.utc
    assert result.close_at_utc.tzinfo is timezone.utc
    assert tuple(MarketScope) == (MarketScope.US_LISTED_EQUITY_PROXY,)
    assert MarketScope.US_LISTED_EQUITY_PROXY.value == "us_listed_equity_proxy"
    assert tuple(CoverageSession) == (CoverageSession.RTH,)
    assert CoverageSession.RTH.value == "rth"

    with pytest.raises(FrozenInstanceError):
        result.kind = CalendarDayKind.CLOSED
    with pytest.raises(ValueError, match="timezone-aware"):
        CalendarDay.open(
            market_date=market_date,
            open_at_utc=datetime(2026, 7, 24, 13, 30),
            close_at_utc=datetime(2026, 7, 24, 20, 0, tzinfo=timezone.utc),
            session_kind=CalendarSessionKind.REGULAR,
        )
    with pytest.raises(ValueError, match="before"):
        CalendarDay.open(
            market_date=market_date,
            open_at_utc=datetime(2026, 7, 24, 20, 0, tzinfo=timezone.utc),
            close_at_utc=datetime(2026, 7, 24, 13, 30, tzinfo=timezone.utc),
            session_kind=CalendarSessionKind.REGULAR,
        )


def test_calendar_adapter_returns_typed_early_close():
    from src.market_coverage.calendar import XnysCalendarAdapter
    from src.market_coverage.models import (
        CalendarAvailability,
        CalendarDay,
        CalendarDayKind,
        CalendarSessionKind,
    )

    market_date = date(2026, 11, 27)
    result = XnysCalendarAdapter().session(market_date)

    assert isinstance(result, CalendarDay)
    assert result.market_date == market_date
    assert result.availability is CalendarAvailability.AVAILABLE
    assert result.kind is CalendarDayKind.OPEN
    assert result.session_kind is CalendarSessionKind.EARLY_CLOSE
    assert result.open_at_utc == datetime(2026, 11, 27, 14, 30, tzinfo=timezone.utc)
    assert result.close_at_utc == datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)


def test_calendar_adapter_returns_closed_without_named_holiday_claim():
    from src.market_coverage.calendar import XnysCalendarAdapter
    from src.market_coverage.models import (
        CalendarAvailability,
        CalendarDay,
        CalendarDayKind,
    )

    market_date = date(2025, 1, 9)
    result = XnysCalendarAdapter().session(market_date)

    assert isinstance(result, CalendarDay)
    assert result.market_date == market_date
    assert result.availability is CalendarAvailability.AVAILABLE
    assert result.kind is CalendarDayKind.CLOSED
    assert result.open_at_utc is None
    assert result.close_at_utc is None
    assert result.session_kind is None
    assert result.reason_code is None
    assert result.diagnostic is None
    assert not hasattr(result, "holiday_name")

    reviewed_boundary = XnysCalendarAdapter().session(date(2025, 1, 1))
    assert reviewed_boundary.availability is CalendarAvailability.AVAILABLE
    assert reviewed_boundary.kind is CalendarDayKind.CLOSED


def test_calendar_adapter_failure_is_typed_unavailable():
    from src.market_coverage.calendar import XnysCalendarAdapter
    from src.market_coverage.models import (
        CalendarAvailability,
        CalendarDay,
        CalendarDayKind,
        CalendarHealthReason,
    )

    diagnostic = "Christmas market closed according to an unsafe exception"
    construction = {}

    def fail_to_construct_calendar(calendar_name, *, start, end):
        construction.update(calendar_name=calendar_name, start=start, end=end)
        raise RuntimeError(diagnostic)

    result = XnysCalendarAdapter(
        calendar_factory=fail_to_construct_calendar
    ).session(date(2026, 7, 24))

    assert isinstance(result, CalendarDay)
    assert result.availability is CalendarAvailability.UNAVAILABLE
    assert result.kind is CalendarDayKind.UNKNOWN
    assert result.reason_code is CalendarHealthReason.CALENDAR_UNAVAILABLE
    assert result.diagnostic == diagnostic
    assert result.open_at_utc is None
    assert result.close_at_utc is None
    assert result.session_kind is None
    assert construction == {
        "calendar_name": "XNYS",
        "start": "2025-01-01",
        "end": "2027-12-31",
    }


def test_fixture_review_membership_is_independent_of_forward_horizon():
    from src.market_coverage.calendar import OfficialSessionFixtures

    fixtures = OfficialSessionFixtures()
    reviewed_historical_date = date(2025, 1, 9)

    assert fixtures.forward_horizon_months(date(2027, 7, 1)) == 5
    assert fixtures.is_reviewed(reviewed_historical_date)


def test_forward_horizon_uses_calendar_month_boundaries():
    from src.market_coverage.calendar import OfficialSessionFixtures

    fixtures = OfficialSessionFixtures()

    assert fixtures.forward_horizon_months(date(2027, 6, 30)) == 6
    assert fixtures.forward_horizon_months(date(2027, 7, 1)) == 5
    assert fixtures.forward_horizon_months(date(2027, 12, 31)) == 0
    assert fixtures.forward_horizon_months(date(2028, 1, 1)) == 0


def test_calendar_health_is_ok_for_reviewed_dates_and_healthy_horizon():
    from src.market_coverage.calendar import (
        CalendarHealthComposer,
        OfficialSessionFixtures,
        XnysCalendarAdapter,
    )
    from src.market_coverage.models import CalendarHealth

    requested_day = date(2026, 7, 24)
    fixtures = OfficialSessionFixtures()
    resolution = XnysCalendarAdapter(fixtures=fixtures).session(requested_day)

    result = CalendarHealthComposer(fixtures=fixtures).compose(
        requested_day=requested_day,
        as_of=date(2027, 6, 30),
        resolution=resolution,
    )

    assert result.status is CalendarHealth.OK
    assert result.reason_codes == ()
    assert result.date_classifiable is True
    assert result.reviewed_through == date(2027, 12, 31)
    assert result.forward_horizon_months == 6
    with pytest.raises(FrozenInstanceError):
        result.status = CalendarHealth.DEGRADED


def test_low_horizon_is_degraded_without_erasing_reviewed_history():
    from src.market_coverage.calendar import (
        CalendarHealthComposer,
        OfficialSessionFixtures,
        XnysCalendarAdapter,
    )
    from src.market_coverage.models import CalendarHealth, CalendarHealthReason

    requested_day = date(2026, 7, 24)
    fixtures = OfficialSessionFixtures()
    resolution = XnysCalendarAdapter(fixtures=fixtures).session(requested_day)

    result = CalendarHealthComposer(fixtures=fixtures).compose(
        requested_day=requested_day,
        as_of=date(2027, 7, 1),
        resolution=resolution,
    )

    assert fixtures.is_reviewed(requested_day)
    assert result.status is CalendarHealth.DEGRADED
    assert result.reason_codes == (CalendarHealthReason.FIXTURE_HORIZON_LOW,)
    assert result.date_classifiable is True
    assert result.forward_horizon_months == 5


def test_unreviewed_date_is_degraded_and_unclassifiable():
    from src.market_coverage.calendar import (
        CalendarHealthComposer,
        OfficialSessionFixtures,
    )
    from src.market_coverage.models import (
        CalendarHealth,
        CalendarHealthReason,
    )

    requested_day = date(2024, 12, 31)
    fixtures = OfficialSessionFixtures()

    result = CalendarHealthComposer(fixtures=fixtures).compose(
        requested_day=requested_day,
        as_of=date(2026, 7, 26),
        resolution=None,
    )

    assert fixtures.is_reviewed(requested_day) is False
    assert result.status is CalendarHealth.DEGRADED
    assert result.reason_codes == (CalendarHealthReason.DATE_UNREVIEWED,)
    assert result.date_classifiable is False


def test_adapter_failure_makes_health_unavailable():
    from src.market_coverage.calendar import (
        CalendarHealthComposer,
        OfficialSessionFixtures,
        XnysCalendarAdapter,
    )
    from src.market_coverage.models import CalendarHealth, CalendarHealthReason

    def fail_to_construct_calendar(*args, **kwargs):
        raise RuntimeError("provider-looking text must remain diagnostic only")

    requested_day = date(2026, 7, 24)
    fixtures = OfficialSessionFixtures()
    resolution = XnysCalendarAdapter(
        fixtures=fixtures,
        calendar_factory=fail_to_construct_calendar,
    ).session(requested_day)

    result = CalendarHealthComposer(fixtures=fixtures).compose(
        requested_day=requested_day,
        as_of=date(2027, 7, 1),
        resolution=resolution,
    )

    assert result.status is CalendarHealth.UNAVAILABLE
    assert result.reason_codes == (CalendarHealthReason.CALENDAR_UNAVAILABLE,)
    assert result.date_classifiable is False
