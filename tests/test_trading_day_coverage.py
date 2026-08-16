from __future__ import annotations

import builtins
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import importlib
from pathlib import Path
import sqlite3
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.market_coverage.classifier import expected_slot_starts
from src.market_coverage.models import CalendarDay, CalendarSessionKind


UTC = timezone.utc
EASTERN = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]

_PRICES_SCHEMA = """
CREATE TABLE prices (
    ticker TEXT NOT NULL,
    datetime TEXT NOT NULL,
    interval TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, datetime, interval)
);
"""

_TOP_LEVEL_FIELDS = {
    "version",
    "market_scope",
    "coverage_session",
    "interval",
    "lookback_days",
    "universe_count",
    "generated_at_et",
    "calendar_health",
    "observation_health",
    "days",
    "provider_errors",
}
_DAY_FIELDS = {
    "date",
    "coverage_status",
    "status_reason_code",
    "closure_reason_code",
    "session_kind",
    "session_open_at_utc",
    "session_close_at_utc",
    "expected_slot_count",
    "observed_ticker_count",
    "complete_ticker_count",
    "partial_ticker_count",
    "unknown_ticker_count",
    "partial_tickers",
    "unknown_tickers",
    "unmatched_rth_row_count",
}
_RETIRED_FIELDS = {
    "max_observed_bar_count",
    "full",
    "well_covered",
    "covered",
    "missing",
    "missing_tickers",
    "session_complete",
    "thin",
    "complete_like",
}


def _service_type():
    service_path = ROOT / "src" / "market_coverage" / "service.py"
    assert service_path.is_file(), "Coverage v2 requires TradingDayCoverageService"
    module = importlib.import_module("src.market_coverage.service")
    service_type = getattr(module, "TradingDayCoverageService", None)
    assert service_type is not None, "Coverage v2 requires TradingDayCoverageService"
    return service_type


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    assert isinstance(value, dict)
    return value


def _stored_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S%z")


def _create_market_db(
    path: Path,
    *,
    rows: tuple[tuple[str, datetime], ...] = (),
    aliases: tuple[tuple[str, str], ...] = (),
    provider_issues: tuple[tuple[str, str, str, str], ...] = (),
) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_PRICES_SCHEMA)
        conn.executemany(
            "INSERT INTO prices "
            "(ticker, datetime, interval, open, high, low, close, volume) "
            "VALUES (?, ?, '15min', 1, 1, 1, 1, 1)",
            ((ticker, _stored_timestamp(observed_at)) for ticker, observed_at in rows),
        )
        if aliases:
            conn.execute(
                "CREATE TABLE ticker_aliases "
                "(alias TEXT PRIMARY KEY, canonical TEXT NOT NULL)"
            )
            conn.executemany(
                "INSERT INTO ticker_aliases (alias, canonical) VALUES (?, ?)",
                aliases,
            )
        if provider_issues:
            conn.execute(
                "CREATE TABLE provider_sync_meta ("
                "ticker TEXT NOT NULL, interval TEXT NOT NULL, "
                "last_error TEXT, updated_at TEXT)"
            )
            conn.executemany(
                "INSERT INTO provider_sync_meta "
                "(ticker, interval, last_error, updated_at) VALUES (?, ?, ?, ?)",
                provider_issues,
            )
        conn.commit()
    finally:
        conn.close()


def _session(
    market_date: date,
    *,
    close_time: time = time(16, 0),
    kind: CalendarSessionKind = CalendarSessionKind.REGULAR,
) -> CalendarDay:
    open_at_et = datetime.combine(market_date, time(9, 30), tzinfo=EASTERN)
    close_at_et = datetime.combine(market_date, close_time, tzinfo=EASTERN)
    return CalendarDay.open(
        market_date=market_date,
        open_at_utc=open_at_et.astimezone(UTC),
        close_at_utc=close_at_et.astimezone(UTC),
        session_kind=kind,
    )


def _slots(session: CalendarDay) -> tuple[datetime, ...]:
    assert session.open_at_utc is not None
    assert session.close_at_utc is not None
    return expected_slot_starts(
        session.open_at_utc,
        session.close_at_utc,
        timedelta(minutes=15),
    )


class _Calendar:
    def __init__(self, days: dict[date, CalendarDay]) -> None:
        self._days = days
        self.requested_days: list[date] = []

    def session(self, market_date: date) -> CalendarDay:
        self.requested_days.append(market_date)
        return self._days[market_date]


class _Fixtures:
    reviewed_from = date(2025, 1, 1)
    reviewed_through = date(2027, 12, 31)

    def __init__(
        self,
        *,
        reviewed_days: set[date] | None = None,
        forward_horizon_months: int = 12,
    ) -> None:
        self._reviewed_days = reviewed_days
        self._forward_horizon_months = forward_horizon_months

    def is_reviewed(self, market_date: date) -> bool:
        if self._reviewed_days is not None:
            return market_date in self._reviewed_days
        return self.reviewed_from <= market_date <= self.reviewed_through

    def forward_horizon_months(self, as_of: date) -> int:
        return self._forward_horizon_months


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.value


def _coverage(
    path: Path,
    *,
    calendar: _Calendar,
    clock: _Clock,
    universe: tuple[str, ...] = ("AAA",),
    fixtures: _Fixtures | None = None,
    lookback_days: int = 1,
) -> dict[str, Any]:
    service = _service_type()(
        db_path=path,
        calendar_adapter=calendar,
        fixtures=_Fixtures() if fixtures is None else fixtures,
        clock=clock,
    )
    return _dump(
        service.get_coverage(
            universe=universe,
            interval="15min",
            lookback_days=lookback_days,
        )
    )


def _day(payload: dict[str, Any], market_date: date) -> dict[str, Any]:
    return next(day for day in payload["days"] if day["date"] == market_date.isoformat())


def _exact_payload() -> dict[str, Any]:
    return {
        "version": 2,
        "market_scope": "us_listed_equity_proxy",
        "coverage_session": "rth",
        "interval": "15min",
        "lookback_days": 1,
        "universe_count": 1,
        "generated_at_et": "2026-07-13T17:00:00-04:00",
        "calendar_health": {
            "status": "ok",
            "reason_codes": [],
            "reviewed_through": "2027-12-31",
            "forward_horizon_months": 12,
        },
        "observation_health": {"status": "ok", "reason_code": None},
        "days": [],
        "provider_errors": [],
    }


def test_service_dedupes_aliases_and_orders_requested_window(tmp_path):
    newest = date(2026, 7, 10)
    oldest = date(2026, 7, 9)
    sessions = {day: _session(day) for day in (oldest, newest)}
    rows = tuple(
        (ticker, slot)
        for session in sessions.values()
        for slot in _slots(session)
        for ticker in ("BRK.B", "BRK B")
    )
    path = tmp_path / "market.db"
    _create_market_db(path, rows=rows, aliases=(("BRK.B", "BRK B"),))
    for universe in (("BRK.B",), ("BRK.B", "BRK B")):
        calendar = _Calendar(sessions)
        clock = _Clock(datetime(2026, 7, 10, 17, 0, tzinfo=EASTERN))

        result = _coverage(
            path,
            calendar=calendar,
            clock=clock,
            universe=universe,
        )

        assert clock.calls == 1
        assert calendar.requested_days == [newest, oldest]
        assert result["universe_count"] == 1
        assert [item["date"] for item in result["days"]] == [
            newest.isoformat(),
            oldest.isoformat(),
        ]
        assert [item["coverage_status"] for item in result["days"]] == [
            "complete",
            "complete",
        ]


def test_service_emits_exact_v2_contract_without_retired_fields(tmp_path):
    monday = date(2026, 7, 13)
    sunday = date(2026, 7, 12)
    path = tmp_path / "market.db"
    _create_market_db(path)
    result = _coverage(
        path,
        calendar=_Calendar({monday: _session(monday), sunday: CalendarDay.closed(sunday)}),
        clock=_Clock(datetime(2026, 7, 13, 17, 0, tzinfo=EASTERN)),
    )

    assert set(result) == _TOP_LEVEL_FIELDS
    assert set(result["calendar_health"]) == {
        "status",
        "reason_codes",
        "reviewed_through",
        "forward_horizon_months",
    }
    assert set(result["observation_health"]) == {"status", "reason_code"}
    assert all(set(day) == _DAY_FIELDS for day in result["days"])
    assert result["version"] == 2
    assert result["market_scope"] == "us_listed_equity_proxy"
    assert result["coverage_session"] == "rth"
    serialized = repr(result)
    assert not any(retired in serialized for retired in _RETIRED_FIELDS)


def test_empty_active_universe_returns_honest_unknown_coverage(tmp_path):
    monday = date(2026, 7, 13)
    sunday = date(2026, 7, 12)
    path = tmp_path / "market.db"
    _create_market_db(path)

    result = _coverage(
        path,
        calendar=_Calendar({monday: _session(monday), sunday: CalendarDay.closed(sunday)}),
        clock=_Clock(datetime(2026, 7, 13, 17, 0, tzinfo=EASTERN)),
        universe=(),
    )
    trading_day = _day(result, monday)

    assert result["universe_count"] == 0
    assert result["observation_health"] == {"status": "ok", "reason_code": None}
    assert result["provider_errors"] == []
    assert trading_day["coverage_status"] == "unknown"
    assert trading_day["status_reason_code"] == "no_observations"
    assert trading_day["observed_ticker_count"] == 0
    assert trading_day["complete_ticker_count"] == 0
    assert trading_day["partial_ticker_count"] == 0
    assert trading_day["unknown_ticker_count"] == 0
    assert trading_day["partial_tickers"] == []
    assert trading_day["unknown_tickers"] == []


def test_regular_session_uses_exact_rth_slots_despite_extended_rows(tmp_path):
    monday = date(2026, 7, 13)
    sunday = date(2026, 7, 12)
    session = _session(monday)
    assert session.open_at_utc is not None
    assert session.close_at_utc is not None
    rows = tuple(("AAA", slot) for slot in _slots(session)) + (
        ("BBB", session.open_at_utc - timedelta(minutes=15)),
        ("BBB", session.close_at_utc),
    )
    path = tmp_path / "market.db"
    _create_market_db(path, rows=rows)

    result = _coverage(
        path,
        calendar=_Calendar({monday: session, sunday: CalendarDay.closed(sunday)}),
        clock=_Clock(datetime(2026, 7, 13, 17, 0, tzinfo=EASTERN)),
        universe=("AAA", "BBB"),
    )
    day = _day(result, monday)

    assert day["expected_slot_count"] == len(_slots(session))
    assert day["coverage_status"] == "indeterminate_tickers"
    assert day["complete_ticker_count"] == 1
    assert day["unknown_tickers"] == ["BBB"]
    assert day["unmatched_rth_row_count"] == 0


def test_early_close_session_uses_derived_fourteen_slot_grid(tmp_path):
    friday = date(2026, 11, 27)
    thursday = date(2026, 11, 26)
    session = _session(
        friday,
        close_time=time(13, 0),
        kind=CalendarSessionKind.EARLY_CLOSE,
    )
    assert session.open_at_utc is not None
    assert session.close_at_utc is not None
    interval = timedelta(minutes=15)
    expected_count = int((session.close_at_utc - session.open_at_utc) / interval)
    expected_starts = tuple(
        session.open_at_utc + offset * interval for offset in range(expected_count)
    )
    path = tmp_path / "market.db"
    _create_market_db(path, rows=tuple(("AAA", slot) for slot in expected_starts))

    result = _coverage(
        path,
        calendar=_Calendar({friday: session, thursday: CalendarDay.closed(thursday)}),
        clock=_Clock(datetime(2026, 11, 27, 13, 30, tzinfo=EASTERN)),
    )
    day = _day(result, friday)

    assert expected_starts[0] == session.open_at_utc
    assert expected_starts[-1] + interval == session.close_at_utc
    assert day["expected_slot_count"] == len(expected_starts)
    assert day["coverage_status"] == "complete"
    assert day["session_kind"] == "early_close"


def test_provider_errors_remain_separate_diagnostics(tmp_path):
    monday = date(2026, 7, 13)
    sunday = date(2026, 7, 12)
    path = tmp_path / "market.db"
    _create_market_db(
        path,
        provider_issues=(("AAA", "15min", "contract unavailable", "2026-07-13T20:00:00Z"),),
    )

    result = _coverage(
        path,
        calendar=_Calendar({monday: _session(monday), sunday: CalendarDay.closed(sunday)}),
        clock=_Clock(datetime(2026, 7, 13, 17, 0, tzinfo=EASTERN)),
    )
    day = _day(result, monday)

    assert day["coverage_status"] == "unknown"
    assert day["status_reason_code"] == "no_observations"
    assert "provider_errors" not in day
    assert result["provider_errors"] == [
        {
            "ticker": "AAA",
            "interval": "15min",
            "last_error": "contract unavailable",
            "reason_code": "unknown",
            "updated_at": "2026-07-13T20:00:00Z",
        }
    ]


def test_calendar_unavailable_returns_unknown_days(tmp_path):
    monday = date(2026, 7, 13)
    sunday = date(2026, 7, 12)
    path = tmp_path / "market.db"
    _create_market_db(path)

    result = _coverage(
        path,
        calendar=_Calendar(
            {
                monday: CalendarDay.unavailable(monday, diagnostic="calendar failed"),
                sunday: CalendarDay.closed(sunday),
            }
        ),
        clock=_Clock(datetime(2026, 7, 13, 17, 0, tzinfo=EASTERN)),
    )
    day = _day(result, monday)

    assert result["calendar_health"] == {
        "status": "unavailable",
        "reason_codes": ["calendar_unavailable"],
        "reviewed_through": "2027-12-31",
        "forward_horizon_months": 12,
    }
    assert day["coverage_status"] == "unknown"
    assert day["status_reason_code"] == "calendar_unavailable"
    assert day["expected_slot_count"] is None
    assert day["observed_ticker_count"] is None


def test_unreviewed_date_is_unknown_while_reviewed_dates_classify(tmp_path):
    reviewed = date(2026, 7, 9)
    unreviewed = date(2026, 7, 10)
    reviewed_session = _session(reviewed)
    unreviewed_session = _session(unreviewed)
    path = tmp_path / "market.db"
    _create_market_db(
        path,
        rows=tuple(("AAA", slot) for slot in _slots(reviewed_session)),
    )

    result = _coverage(
        path,
        calendar=_Calendar({reviewed: reviewed_session, unreviewed: unreviewed_session}),
        fixtures=_Fixtures(reviewed_days={reviewed}),
        clock=_Clock(datetime(2026, 7, 10, 17, 0, tzinfo=EASTERN)),
    )

    assert result["calendar_health"]["status"] == "degraded"
    assert result["calendar_health"]["reason_codes"] == ["date_unreviewed"]
    assert _day(result, reviewed)["coverage_status"] == "complete"
    assert _day(result, unreviewed)["coverage_status"] == "unknown"
    assert _day(result, unreviewed)["status_reason_code"] == "date_unreviewed"


def test_low_fixture_horizon_degrades_health_without_erasing_reviewed_days(tmp_path):
    newest = date(2026, 7, 10)
    oldest = date(2026, 7, 9)
    sessions = {day: _session(day) for day in (oldest, newest)}
    path = tmp_path / "market.db"
    _create_market_db(
        path,
        rows=tuple(
            ("AAA", slot)
            for session in sessions.values()
            for slot in _slots(session)
        ),
    )

    result = _coverage(
        path,
        calendar=_Calendar(sessions),
        fixtures=_Fixtures(forward_horizon_months=5),
        clock=_Clock(datetime(2026, 7, 10, 17, 0, tzinfo=EASTERN)),
    )

    assert result["calendar_health"]["status"] == "degraded"
    assert result["calendar_health"]["reason_codes"] == ["fixture_horizon_low"]
    assert all(day["coverage_status"] == "complete" for day in result["days"])


def test_missing_market_db_is_unavailable_not_empty(tmp_path):
    monday = date(2026, 7, 13)
    sunday = date(2026, 7, 12)
    missing = tmp_path / "missing-market.db"

    result = _coverage(
        missing,
        calendar=_Calendar({monday: _session(monday), sunday: CalendarDay.closed(sunday)}),
        clock=_Clock(datetime(2026, 7, 13, 17, 0, tzinfo=EASTERN)),
    )
    day = _day(result, monday)

    assert result["observation_health"] == {
        "status": "unavailable",
        "reason_code": "market_db_missing",
    }
    assert day["coverage_status"] == "unknown"
    assert day["status_reason_code"] == "observation_unavailable"
    assert day["observed_ticker_count"] is None
    assert not missing.exists()


def test_readable_empty_market_db_is_ok_with_unknown_days(tmp_path):
    monday = date(2026, 7, 13)
    sunday = date(2026, 7, 12)
    session = _session(monday)
    path = tmp_path / "market.db"
    _create_market_db(path)

    result = _coverage(
        path,
        calendar=_Calendar({monday: session, sunday: CalendarDay.closed(sunday)}),
        clock=_Clock(datetime(2026, 7, 13, 17, 0, tzinfo=EASTERN)),
    )
    day = _day(result, monday)

    assert result["observation_health"] == {"status": "ok", "reason_code": None}
    assert day["coverage_status"] == "unknown"
    assert day["status_reason_code"] == "no_observations"
    assert day["expected_slot_count"] == len(_slots(session))
    assert day["observed_ticker_count"] == 0
    assert day["unknown_ticker_count"] == 1


def test_route_rejects_unreviewed_interval_with_typed_422(monkeypatch):
    import src.api.routes.market_data as market_routes
    import src.universe_scope as universe_scope

    monkeypatch.setattr(universe_scope, "resolve_active_universe", lambda: ["AAA"])
    monkeypatch.setattr(
        market_routes,
        "summarize_trading_day_coverage",
        lambda *args, **kwargs: {"version": 1},
        raising=False,
    )
    app = FastAPI()
    app.include_router(market_routes.router)

    response = TestClient(app).get(
        "/market-data/trading-days",
        params={"lookback_days": 1, "interval": "1d"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == [
        {
            "type": "literal_error",
            "loc": ["query", "interval"],
            "msg": "Input should be '15min'",
            "input": "1d",
            "ctx": {"expected": "'15min'"},
        }
    ]


def test_route_wires_active_universe_and_v2_service(tmp_path, monkeypatch):
    import src.api.routes.market_data as market_routes
    import src.universe_scope as universe_scope

    expected = _exact_payload()
    calls: dict[str, Any] = {}

    class FakeService:
        def __init__(self, *, db_path):
            calls["db_path"] = db_path

        def get_coverage(self, *, universe, interval, lookback_days):
            calls["request"] = (tuple(universe), interval, lookback_days)
            return expected

    db_path = str(tmp_path / "market.db")
    monkeypatch.setattr(universe_scope, "resolve_active_universe", lambda: ["AAA"])
    monkeypatch.setattr(market_routes, "resolve_market_db_path", lambda: db_path)
    monkeypatch.setattr(market_routes, "TradingDayCoverageService", FakeService, raising=False)
    monkeypatch.setattr(
        market_routes,
        "summarize_trading_day_coverage",
        lambda *args, **kwargs: {"version": 1},
        raising=False,
    )

    result = market_routes.market_data_trading_days(lookback_days=1, interval="15min")

    assert _dump(result) == expected
    assert calls == {
        "db_path": db_path,
        "request": (("AAA",), "15min", 1),
    }


def test_route_preserves_sanitized_active_universe_503(monkeypatch):
    import src.api.routes.market_data as market_routes
    import src.universe_scope as universe_scope
    from src.active_universe import ActiveUniverseUnavailable

    calls = {"scope": 0, "db": 0, "service": 0}
    unavailable = ActiveUniverseUnavailable(
        {
            "manual_lists": "source_db_unreadable",
            "sa_alpha_picks_current": "source_db_missing",
        }
    )

    def fail_scope():
        calls["scope"] += 1
        raise unavailable

    def db_path():
        calls["db"] += 1
        return "/unused/market.db"

    class BombService:
        def __init__(self, **kwargs):
            calls["service"] += 1
            raise AssertionError("service must not run without an active universe")

    monkeypatch.setattr(universe_scope, "resolve_active_universe", fail_scope)
    monkeypatch.setattr(market_routes, "resolve_market_db_path", db_path)
    monkeypatch.setattr(market_routes, "TradingDayCoverageService", BombService, raising=False)

    with pytest.raises(HTTPException) as caught:
        market_routes.market_data_trading_days(lookback_days=1, interval="15min")

    assert caught.value.status_code == 503
    assert caught.value.detail == unavailable.as_dict()
    assert calls == {"scope": 1, "db": 0, "service": 0}


def test_route_registered():
    import src.api.routes.market_data as market_routes

    assert "/market-data/trading-days" in {
        route.path for route in market_routes.router.routes
    }


def test_route_coverage_path_is_pure_local_read_without_provider_or_scheduler(
    tmp_path,
    monkeypatch,
):
    import src.api.routes.market_data as market_routes
    import src.universe_scope as universe_scope

    path = tmp_path / "market.db"
    _create_market_db(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(universe_scope, "resolve_active_universe", lambda: ["AAA"])
    monkeypatch.setattr(market_routes, "resolve_market_db_path", lambda: str(path))

    forbidden_prefixes = (
        "ib_insync",
        "src.collectors",
        "src.scheduler_planner",
        "src.service.data_scheduler",
    )
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        assert not name.startswith(forbidden_prefixes), name
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = _dump(
        market_routes.market_data_trading_days(
            lookback_days=1,
            interval="15min",
        )
    )

    assert result["version"] == 2
    assert set(result) == _TOP_LEVEL_FIELDS
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
