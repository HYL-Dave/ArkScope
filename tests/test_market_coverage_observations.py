from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from src.market_coverage.models import CalendarDay, CalendarSessionKind


UTC = timezone.utc
EASTERN = ZoneInfo("America/New_York")

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


def _api() -> SimpleNamespace:
    from src.market_coverage import observations as observations_module
    from src.market_coverage.classifier import SlotCoverageClassifier
    from src.market_coverage.models import (
        CalendarHealth,
        CalendarHealthAssessment,
        ObservationHealth,
        ObservationHealthReason,
    )
    from src.market_coverage.observations import (
        RthObservationReader,
        _open_read_only_market_db,
    )

    return SimpleNamespace(
        CalendarHealth=CalendarHealth,
        CalendarHealthAssessment=CalendarHealthAssessment,
        ObservationHealth=ObservationHealth,
        ObservationHealthReason=ObservationHealthReason,
        RthObservationReader=RthObservationReader,
        SlotCoverageClassifier=SlotCoverageClassifier,
        module=observations_module,
        open_read_only_market_db=_open_read_only_market_db,
    )


def _est_session(market_date: date) -> CalendarDay:
    open_at_et = datetime.combine(market_date, time(9, 30), tzinfo=EASTERN)
    close_at_et = datetime.combine(market_date, time(16, 0), tzinfo=EASTERN)
    return CalendarDay.open(
        market_date=market_date,
        open_at_utc=open_at_et.astimezone(UTC),
        close_at_utc=close_at_et.astimezone(UTC),
        session_kind=CalendarSessionKind.REGULAR,
    )


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
                "provider TEXT NOT NULL, ticker TEXT NOT NULL, "
                "interval TEXT NOT NULL, last_error TEXT, updated_at TEXT NOT NULL)"
            )
            conn.executemany(
                "INSERT INTO provider_sync_meta "
                "(provider, ticker, interval, last_error, updated_at) "
                "VALUES ('ibkr', ?, ?, ?, ?)",
                provider_issues,
            )
        conn.commit()
    finally:
        conn.close()


def _read(api: SimpleNamespace, path: Path, *sessions: CalendarDay):
    return api.RthObservationReader(path).read(
        universe=("AAA",),
        sessions=sessions,
        interval="15min",
    )


def _database_proof(path: Path) -> dict[str, object]:
    stat = path.stat()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = tuple(conn.execute("PRAGMA integrity_check"))
        foreign_keys = tuple(conn.execute("PRAGMA foreign_key_check"))
    finally:
        conn.close()
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "integrity": integrity,
        "foreign_keys": foreign_keys,
    }


def test_missing_market_db_is_typed_unavailable(tmp_path):
    api = _api()
    path = tmp_path / "missing-market.db"

    result = _read(api, path, _est_session(date(2026, 1, 5)))

    assert result.health.status is api.ObservationHealth.UNAVAILABLE
    assert result.health.reason_code is api.ObservationHealthReason.MARKET_DB_MISSING
    assert result.sessions == ()
    assert result.provider_errors == ()
    assert not path.exists()


def test_unreadable_market_db_is_typed_unavailable(tmp_path):
    api = _api()
    path = tmp_path / "unreadable-market.db"
    original = b"this is not a sqlite database"
    path.write_bytes(original)

    result = _read(api, path, _est_session(date(2026, 1, 5)))

    assert result.health.status is api.ObservationHealth.UNAVAILABLE
    assert (
        result.health.reason_code
        is api.ObservationHealthReason.MARKET_DB_UNREADABLE
    )
    assert result.sessions == ()
    assert path.read_bytes() == original


def test_missing_prices_schema_is_typed_unavailable(tmp_path):
    api = _api()
    no_table_path = tmp_path / "no-prices.db"
    sqlite3.connect(no_table_path).close()
    missing_column_path = tmp_path / "malformed-prices.db"
    conn = sqlite3.connect(missing_column_path)
    try:
        conn.execute("CREATE TABLE prices (ticker TEXT, datetime TEXT)")
        conn.commit()
    finally:
        conn.close()

    for path in (no_table_path, missing_column_path):
        result = _read(api, path, _est_session(date(2026, 1, 5)))
        assert result.health.status is api.ObservationHealth.UNAVAILABLE
        assert (
            result.health.reason_code
            is api.ObservationHealthReason.PRICES_SCHEMA_MISSING
        )
        assert result.sessions == ()


def test_readable_empty_prices_table_is_ok(tmp_path):
    api = _api()
    path = tmp_path / "empty-market.db"
    session = _est_session(date(2026, 1, 5))
    _create_market_db(path)

    result = _read(api, path, session)

    assert result.health.status is api.ObservationHealth.OK
    assert result.health.reason_code is None
    assert result.observations_for(session.market_date) == ()
    assert tuple(item.market_date for item in result.sessions) == (
        session.market_date,
    )
    assert result.provider_errors == ()


def test_reader_is_read_only_and_preserves_database_bytes(tmp_path):
    api = _api()
    path = tmp_path / "market.db"
    session = _est_session(date(2026, 1, 5))
    assert session.open_at_utc is not None
    _create_market_db(path, rows=(("AAA", session.open_at_utc),))
    before = _database_proof(path)

    result = _read(api, path, session)

    after = _database_proof(path)
    assert result.health.status is api.ObservationHealth.OK
    assert len(result.observations_for(session.market_date)) == 1
    assert after == before


def test_reader_assigns_rows_by_utc_session_window_not_date_prefix(
    tmp_path,
    monkeypatch,
):
    api = _api()
    path = tmp_path / "market.db"
    first = _est_session(date(2026, 1, 5))
    second = _est_session(date(2026, 1, 6))
    assert first.open_at_utc is not None
    assert second.open_at_utc is not None
    est_post_market = datetime(2026, 1, 5, 19, 15, tzinfo=EASTERN)
    utc_date_boundary_row = est_post_market.astimezone(UTC)
    assert utc_date_boundary_row.date() == second.market_date
    _create_market_db(
        path,
        rows=(
            ("AAA", first.open_at_utc),
            ("AAA", utc_date_boundary_row),
            ("AAA", second.open_at_utc),
        ),
    )
    statements: list[str] = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(api.module.sqlite3, "connect", traced_connect)

    result = _read(api, path, first, second)

    assert tuple(
        row.observed_at for row in result.observations_for(first.market_date)
    ) == (first.open_at_utc,)
    assert tuple(
        row.observed_at for row in result.observations_for(second.market_date)
    ) == (second.open_at_utc,)
    prices_queries = [
        statement
        for statement in statements
        if statement.lstrip().lower().startswith("select")
        and " from prices" in statement.lower()
    ]
    assert len(prices_queries) == 1
    assert "substr(" not in prices_queries[0].lower()


def test_reader_excludes_extended_hours_rows(tmp_path):
    api = _api()
    path = tmp_path / "market.db"
    session = _est_session(date(2026, 1, 5))
    assert session.open_at_utc is not None
    assert session.close_at_utc is not None
    _create_market_db(
        path,
        rows=(
            ("AAA", session.open_at_utc.replace(minute=29, second=59)),
            ("AAA", session.open_at_utc),
            ("AAA", session.close_at_utc),
            ("AAA", session.close_at_utc.replace(minute=1)),
        ),
    )

    result = _read(api, path, session)

    assert tuple(
        row.observed_at for row in result.observations_for(session.market_date)
    ) == (session.open_at_utc,)


def test_reader_retains_in_window_off_grid_rows(tmp_path):
    api = _api()
    path = tmp_path / "market.db"
    session = _est_session(date(2026, 1, 5))
    off_grid = datetime(2026, 1, 5, 15, 59, 59, tzinfo=UTC)
    _create_market_db(path, rows=(("AAA", off_grid),))

    result = _read(api, path, session)
    rows = result.observations_for(session.market_date)

    assert tuple(row.observed_at for row in rows) == (off_grid,)
    health = api.CalendarHealthAssessment(
        market_date=session.market_date,
        status=api.CalendarHealth.OK,
        reason_codes=(),
        date_classifiable=True,
        reviewed_through=date(2027, 12, 31),
        forward_horizon_months=12,
    )
    classified = api.SlotCoverageClassifier().classify(
        calendar_day=session,
        calendar_health=health,
        universe=("AAA",),
        observations=rows,
        interval=timedelta(minutes=15),
        now_et=datetime(2026, 1, 5, 17, 0, tzinfo=EASTERN),
    )
    assert classified.unmatched_rth_row_count == 1


def test_reader_maps_aliases_to_canonical_tickers(tmp_path):
    api = _api()
    path = tmp_path / "market.db"
    session = _est_session(date(2026, 1, 5))
    assert session.open_at_utc is not None
    _create_market_db(
        path,
        rows=(
            ("BRK B", session.open_at_utc),
            ("BRK.B", session.open_at_utc),
            ("UNRELATED", session.open_at_utc),
        ),
        aliases=(("BRK.B", "BRK B"),),
        provider_issues=(
            ("BRK.B", "15min", "contract unavailable", "2026-01-06T00:00:00Z"),
        ),
    )

    result = api.RthObservationReader(path).read(
        universe=("BRK B",),
        sessions=(session,),
        interval="15min",
    )

    rows = result.observations_for(session.market_date)
    assert tuple(row.ticker for row in rows) == ("BRK B", "BRK B")
    assert tuple(row.observed_at for row in rows) == (
        session.open_at_utc,
        session.open_at_utc,
    )
    assert len(result.provider_errors) == 1
    assert result.provider_errors[0].ticker == "BRK B"
    assert result.provider_errors[0].last_error == "contract unavailable"


def test_query_only_rejects_accidental_writes(tmp_path):
    api = _api()
    path = tmp_path / "market.db"
    _create_market_db(path)

    conn = api.open_read_only_market_db(path)
    try:
        assert conn.execute("PRAGMA query_only").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TEMP TABLE accidental_write (value TEXT)")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute(
                "INSERT INTO prices (ticker, datetime, interval) "
                "VALUES ('AAA', '2026-01-05T14:30:00+0000', '15min')"
            )
    finally:
        conn.close()
