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
    raw_rows: tuple[tuple[str, str], ...] = (),
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
        conn.executemany(
            "INSERT INTO prices "
            "(ticker, datetime, interval, open, high, low, close, volume) "
            "VALUES (?, ?, '15min', 1, 1, 1, 1, 1)",
            raw_rows,
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


def _assert_market_unreadable(
    api: SimpleNamespace,
    path: Path,
    session: CalendarDay,
) -> None:
    result = _read(api, path, session)
    assert result.health.status is api.ObservationHealth.UNAVAILABLE
    assert (
        result.health.reason_code
        is api.ObservationHealthReason.MARKET_DB_UNREADABLE
    )
    assert result.sessions == ()
    assert result.provider_errors == ()


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
    session = _est_session(date(2026, 1, 5))
    path = tmp_path / "unreadable-market.db"
    original = b"this is not a sqlite database"
    path.write_bytes(original)

    _assert_market_unreadable(api, path, session)
    assert path.read_bytes() == original

    malformed_timestamp_path = tmp_path / "malformed-timestamp.db"
    _create_market_db(
        malformed_timestamp_path,
        raw_rows=(("AAA", "2026-01-05T15:not-a-time+0000"),),
    )
    _assert_market_unreadable(api, malformed_timestamp_path, session)

    noncanonical_timestamp_path = tmp_path / "noncanonical-timestamp.db"
    _create_market_db(
        noncanonical_timestamp_path,
        raw_rows=(("AAA", "2026-01-05T15:00:00-0500"),),
    )
    _assert_market_unreadable(api, noncanonical_timestamp_path, session)

    incompatible_provider_path = tmp_path / "incompatible-provider-meta.db"
    _create_market_db(incompatible_provider_path)
    conn = sqlite3.connect(incompatible_provider_path)
    try:
        conn.execute(
            "CREATE TABLE provider_sync_meta "
            "(ticker TEXT, interval TEXT, last_error TEXT)"
        )
        conn.commit()
    finally:
        conn.close()
    _assert_market_unreadable(api, incompatible_provider_path, session)

    malformed_provider_path = tmp_path / "malformed-provider-meta.db"
    _create_market_db(malformed_provider_path)
    conn = sqlite3.connect(malformed_provider_path)
    try:
        conn.execute(
            "CREATE TABLE provider_sync_meta ("
            "ticker TEXT, interval TEXT, last_error TEXT, updated_at TEXT)"
        )
        conn.execute(
            "INSERT INTO provider_sync_meta VALUES ('AAA', '15min', '', 'now')"
        )
        conn.commit()
    finally:
        conn.close()
    _assert_market_unreadable(api, malformed_provider_path, session)

    valid_path = tmp_path / "caller-error.db"
    _create_market_db(valid_path)
    with pytest.raises(ValueError, match="universe ticker"):
        api.RthObservationReader(valid_path).read(
            universe=("",),
            sessions=(session,),
            interval="15min",
        )


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
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE provider_sync_meta ("
            "ticker TEXT, interval TEXT, last_error TEXT, updated_at TEXT)"
        )
        conn.execute(
            "INSERT INTO provider_sync_meta VALUES ('AAA', '1d', '', 'now')"
        )
        conn.commit()
    finally:
        conn.close()

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
            ("AAA", datetime(2026, 1, 5, 14, 45, tzinfo=UTC)),
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
    ) == (
        first.open_at_utc,
        datetime(2026, 1, 5, 14, 45, tzinfo=UTC),
    )
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
    prices_query = prices_queries[0]
    assert "substr(" not in prices_query.lower()
    assert "upper(" not in prices_query.lower()
    assert "trim(" not in prices_query.lower()
    planner = real_connect(f"file:{path}?mode=ro", uri=True)
    try:
        plan_details = tuple(
            row[3]
            for row in planner.execute(
                f"EXPLAIN QUERY PLAN {prices_query}"
            )
        )
    finally:
        planner.close()
    search_details = tuple(
        detail.upper()
        for detail in plan_details
        if detail.upper().startswith("SEARCH PRICES")
    )
    assert any(
        " USING " in detail
        and "TICKER=?" in detail
        and "DATETIME>?" in detail
        and "DATETIME<?" in detail
        for detail in search_details
    )
    assert all(
        not detail.upper().startswith("SCAN PRICES") for detail in plan_details
    )


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


def test_reader_maps_aliases_to_canonical_tickers(tmp_path, monkeypatch):
    api = _api()
    path = tmp_path / "market.db"
    session = _est_session(date(2026, 1, 5))
    assert session.open_at_utc is not None
    _create_market_db(
        path,
        rows=(
            ("\tbrk b\t", session.open_at_utc),
            ("\tBrK.B\t", session.open_at_utc),
            ("BRK B", session.open_at_utc),
            ("UNRELATED", session.open_at_utc),
        ),
        aliases=(("\tBrK.B\t", "\tbrk b\t"),),
        provider_issues=(
            ("\tBrK.B\t", "15min", "contract unavailable", "2026-01-06T00:00:00Z"),
        ),
    )
    statements: list[str] = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(api.module.sqlite3, "connect", traced_connect)

    result = api.RthObservationReader(path).read(
        universe=("BRK B",),
        sessions=(session,),
        interval="15min",
    )
    monkeypatch.setattr(api.module.sqlite3, "connect", real_connect)

    rows = result.observations_for(session.market_date)
    assert tuple(row.ticker for row in rows) == ("BRK B", "BRK B", "BRK B")
    assert tuple(row.observed_at for row in rows) == (
        session.open_at_utc,
        session.open_at_utc,
        session.open_at_utc,
    )
    assert len(result.provider_errors) == 1
    assert result.provider_errors[0].ticker == "BRK B"
    assert result.provider_errors[0].last_error == "contract unavailable"
    provider_queries = [
        statement
        for statement in statements
        if statement.lstrip().lower().startswith("select")
        and " from provider_sync_meta" in statement.lower()
    ]
    assert len(provider_queries) == 1
    assert "upper(" not in provider_queries[0].lower()
    assert "trim(" not in provider_queries[0].lower()

    chain_path = tmp_path / "alias-chain.db"
    _create_market_db(
        chain_path,
        rows=(
            ("OLD", session.open_at_utc),
            ("MID", session.open_at_utc),
        ),
        aliases=(("OLD", "MID"), ("MID", "NEW")),
        provider_issues=(
            ("OLD", "15min", "old contract", "2026-01-06T00:00:00Z"),
        ),
    )
    chain_result = api.RthObservationReader(chain_path).read(
        universe=("OLD",),
        sessions=(session,),
        interval="15min",
    )
    assert tuple(
        row.ticker for row in chain_result.observations_for(session.market_date)
    ) == ("NEW", "NEW")
    assert tuple(issue.ticker for issue in chain_result.provider_errors) == (
        "NEW",
    )

    incompatible_alias_path = tmp_path / "incompatible-aliases.db"
    _create_market_db(incompatible_alias_path)
    conn = sqlite3.connect(incompatible_alias_path)
    try:
        conn.execute("CREATE TABLE ticker_aliases (alias TEXT)")
        conn.commit()
    finally:
        conn.close()
    _assert_market_unreadable(api, incompatible_alias_path, session)

    malformed_alias_path = tmp_path / "malformed-aliases.db"
    _create_market_db(malformed_alias_path, aliases=(("", "AAA"),))
    _assert_market_unreadable(api, malformed_alias_path, session)

    colliding_alias_path = tmp_path / "colliding-aliases.db"
    _create_market_db(colliding_alias_path)
    conn = sqlite3.connect(colliding_alias_path)
    try:
        conn.execute("CREATE TABLE ticker_aliases (alias TEXT, canonical TEXT)")
        conn.executemany(
            "INSERT INTO ticker_aliases VALUES (?, ?)",
            ((" alias ", "AAA"), ("ALIAS", "BBB")),
        )
        conn.commit()
    finally:
        conn.close()
    _assert_market_unreadable(api, colliding_alias_path, session)

    cycle_path = tmp_path / "cyclic-aliases.db"
    _create_market_db(cycle_path, aliases=(("AAA", "BBB"), ("BBB", "AAA")))
    _assert_market_unreadable(api, cycle_path, session)

    self_cycle_path = tmp_path / "self-cyclic-aliases.db"
    _create_market_db(self_cycle_path, aliases=(("AAA", "AAA"),))
    _assert_market_unreadable(api, self_cycle_path, session)


def test_query_only_rejects_accidental_writes(tmp_path, monkeypatch):
    api = _api()
    path = tmp_path / "market.db"
    _create_market_db(path)
    real_connect = sqlite3.connect
    connect_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def recording_connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(api.module.sqlite3, "connect", recording_connect)

    conn = api.open_read_only_market_db(path)
    try:
        assert len(connect_calls) == 1
        connect_args, connect_kwargs = connect_calls[0]
        assert len(connect_args) == 1
        assert isinstance(connect_args[0], str)
        assert connect_args[0].startswith("file:")
        assert "mode=ro" in connect_args[0]
        assert connect_kwargs.get("uri") is True
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
