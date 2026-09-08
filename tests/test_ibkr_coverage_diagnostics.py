"""IBKR last-attempt diagnostics are independent of stored price coverage."""

from datetime import date, datetime, timedelta
import sqlite3

import pytest

from src.market_data_direct import _ensure_provider_sync_tables, _upsert_provider_meta
from src.market_coverage.models import CalendarDay
from tests.test_trading_day_coverage import (
    EASTERN, _Calendar, _Clock, _coverage, _create_market_db, _session, _slots,
)


@pytest.fixture
def covered_market(tmp_path):
    day = date(2026, 9, 3)
    session = _session(day)
    path = tmp_path / "market.db"
    _create_market_db(path, rows=tuple(("LIVE", at) for at in _slots(session)))
    with sqlite3.connect(path) as conn:
        _ensure_provider_sync_tables(conn)

    def read():
        return _coverage(
            path, universe=("LIVE",),
            calendar=_Calendar({day: session, day - timedelta(days=1): CalendarDay.closed(day - timedelta(days=1))}),
            clock=_Clock(datetime(2026, 9, 3, 17, tzinfo=EASTERN)),
        )

    return path, read


def insert_issue(path, provider, code, *, updated_at="2026-09-03T20:30:00+00:00", ticker="LIVE", interval="15min"):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO provider_sync_meta (provider,ticker,interval,last_error,updated_at) VALUES (?,?,?,?,?)",
            (provider, ticker, interval, code, updated_at),
        )


@pytest.mark.parametrize("code,reason", [
    ("security_definition_unavailable", "security_definition_unavailable"),
    ("ibkr_contract_qualification_failed", "provider_request_failed"),
    ("ibkr_historical_data_request_failed", "provider_request_failed"),
])
def test_ibkr_diagnostic_timestamp_survives_complete_coverage(covered_market, code, reason):
    path, read = covered_market
    insert_issue(path, "ibkr", code, updated_at="2020-01-01T00:00:00+00:00")
    before = path.read_bytes()

    result = read()

    assert result["days"][0]["coverage_status"] == "complete"
    assert result["history_gaps"] == []
    assert result["provider_errors"] == [{
        "ticker": "LIVE", "interval": "15min", "last_error": code,
        "reason_code": reason, "updated_at": "2020-01-01T00:00:00+00:00",
    }]
    assert path.read_bytes() == before
    assert read()["provider_errors"] == result["provider_errors"]


@pytest.mark.parametrize("provider", ["polygon", "", "IBKR"])
def test_other_provider_errors_are_not_attributed_to_ibkr(covered_market, provider):
    path, read = covered_market
    insert_issue(path, provider, "security_definition_unavailable")

    assert read()["provider_errors"] == []


def test_matching_ibkr_error_is_not_replaced_by_other_provider_or_scope(covered_market):
    path, read = covered_market
    insert_issue(path, "ibkr", "ibkr_contract_qualification_failed")
    insert_issue(path, "polygon", "security_definition_unavailable", updated_at="2026-09-04T00:00:00Z")
    insert_issue(path, "ibkr", "security_definition_unavailable", interval="1d")
    insert_issue(path, "ibkr", "security_definition_unavailable", ticker="OTHER")

    issues = read()["provider_errors"]

    assert [(issue["ticker"], issue["last_error"]) for issue in issues] == [
        ("LIVE", "ibkr_contract_qualification_failed"),
    ]


def test_missing_provider_identity_is_not_assumed_to_be_ibkr(covered_market):
    path, read = covered_market
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE provider_sync_meta")
        conn.execute("CREATE TABLE provider_sync_meta (ticker,interval,last_error,updated_at)")
        conn.execute("INSERT INTO provider_sync_meta VALUES ('LIVE','15min','security_definition_unavailable','2026-09-03T20:30:00Z')")
    before = path.read_bytes()

    result = read()

    assert result["provider_errors"] == []
    assert result["days"][0]["coverage_status"] == "complete"
    assert path.read_bytes() == before


def test_normal_success_clears_only_matching_provider_telemetry(covered_market):
    path, read = covered_market
    insert_issue(path, "ibkr", "security_definition_unavailable")
    insert_issue(path, "polygon", "security_definition_unavailable")
    with sqlite3.connect(path) as conn:
        _upsert_provider_meta(
            conn, provider="ibkr", ticker="LIVE", interval="15min",
            last_bar_datetime="2026-09-03T19:45:00+0000", rows_added=0, error=None,
        )

    assert read()["provider_errors"] == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT last_error FROM provider_sync_meta WHERE provider='polygon'").fetchone() == (
            "security_definition_unavailable",
        )
