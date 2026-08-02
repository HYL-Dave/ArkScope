"""Qualified local valuation-price selection contracts."""

from __future__ import annotations

import hashlib
import math
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest


_ET = ZoneInfo("America/New_York")


def _make_prices_db(path: Path, rows=()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE prices ("
        "ticker TEXT NOT NULL, datetime TEXT NOT NULL, "
        "interval TEXT NOT NULL, close)"
    )
    conn.executemany(
        "INSERT INTO prices (ticker, datetime, interval, close) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return path


def _tree_snapshot(root: Path) -> tuple:
    records = []
    for path in [root, *sorted(root.rglob("*"))]:
        relative = "." if path == root else path.relative_to(root).as_posix()
        if path.is_symlink():
            records.append((relative, "symlink", os.readlink(path)))
        elif path.is_file():
            records.append(
                (relative, "file", hashlib.sha256(path.read_bytes()).hexdigest())
            )
        elif path.is_dir():
            records.append((relative, "dir"))
        else:
            records.append((relative, "other"))
    return tuple(records)


def _assert_unavailable(result, required_market_date: str | None) -> None:
    assert result.model_dump() == {
        "available": False,
        "source": None,
        "interval": None,
        "required_market_date": required_market_date,
        "market_date": None,
        "timestamp": None,
        "price": None,
        "empty_reason": "no_qualified_price",
    }
    assert "error" not in result.model_dump()


def _assert_available(
    result,
    *,
    market_date: str,
    timestamp: str,
    price: float,
) -> None:
    assert result.model_dump() == {
        "available": True,
        "source": "local_market_db",
        "interval": "15min",
        "required_market_date": market_date,
        "market_date": market_date,
        "timestamp": timestamp,
        "price": price,
        "empty_reason": None,
    }


def test_before_completion_uses_previous_market_date(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    db = _make_prices_db(
        tmp_path / "market.db",
        [
            ("AAPL", "2026-06-22T20:00:00+0000", "15min", 101.0),
            ("AAPL", "2026-06-23T19:45:00+0000", "15min", 999.0),
        ],
    )

    result = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 16, 29, 59, tzinfo=_ET),
    )

    _assert_available(
        result,
        market_date="2026-06-22",
        timestamp="2026-06-22T20:00:00+00:00",
        price=101.0,
    )


def test_after_completion_accepts_today(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    db = _make_prices_db(
        tmp_path / "market.db",
        [("AAPL", "2026-06-23T20:00:00+0000", "15min", 102.5)],
    )

    result = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 16, 30, tzinfo=_ET),
    )

    _assert_available(
        result,
        market_date="2026-06-23",
        timestamp="2026-06-23T20:00:00+00:00",
        price=102.5,
    )


def test_weekend_and_holiday_select_previous_completed_session(tmp_path, monkeypatch):
    import src.market_sessions as market_sessions
    from src.valuation_price import get_valuation_price_basis

    db = _make_prices_db(
        tmp_path / "market.db",
        [
            ("AAPL", "2026-06-26T20:00:00+0000", "15min", 103.0),
            ("AAPL", "2026-06-29T20:00:00+0000", "15min", 999.0),
        ],
    )
    weekend = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 27, 12, 0, tzinfo=_ET),
    )
    _assert_available(
        weekend,
        market_date="2026-06-26",
        timestamp="2026-06-26T20:00:00+00:00",
        price=103.0,
    )

    real_status = market_sessions._market_day_status

    def synthetic_holiday(day: date) -> dict:
        if day == date(2026, 6, 29):
            return {
                "is_trading_day": False,
                "reason": "synthetic_holiday",
                "holiday": "Synthetic Holiday",
            }
        return real_status(day)

    monkeypatch.setattr(market_sessions, "_market_day_status", synthetic_holiday)
    holiday = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 29, 17, 0, tzinfo=_ET),
    )
    _assert_available(
        holiday,
        market_date="2026-06-26",
        timestamp="2026-06-26T20:00:00+00:00",
        price=103.0,
    )


def test_one_row_qualifies_without_slot_completeness(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    db = _make_prices_db(
        tmp_path / "market.db",
        [("AAPL", "2026-06-23T14:30:00+0000", "15min", 104.0)],
    )

    result = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
    )

    _assert_available(
        result,
        market_date="2026-06-23",
        timestamp="2026-06-23T14:30:00+00:00",
        price=104.0,
    )


def test_missing_required_date_does_not_fallback_to_older_bar(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    db = _make_prices_db(
        tmp_path / "market.db",
        [("AAPL", "2026-06-22T20:00:00+0000", "15min", 105.0)],
    )

    result = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
    )

    _assert_unavailable(result, "2026-06-23")


def test_missing_store_is_typed_unavailable_and_no_create(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    db = tmp_path / "missing" / "nested" / "market.db"
    before = _tree_snapshot(tmp_path)
    result = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
    )

    _assert_unavailable(result, "2026-06-23")
    assert _tree_snapshot(tmp_path) == before
    assert not db.parent.exists()


def test_unreadable_schema_and_query_failures_are_typed_sanitized(
    tmp_path,
    monkeypatch,
):
    import src.market_sessions as market_sessions
    import src.valuation_price as valuation_price

    directory = tmp_path / "directory.db"
    directory.mkdir()
    broken = tmp_path / "broken.db"
    broken.symlink_to(tmp_path / "private-missing-target.db")
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"private junk marker")
    missing_table = tmp_path / "missing-table.db"
    sqlite3.connect(missing_table).close()
    missing_columns = tmp_path / "missing-columns.db"
    conn = sqlite3.connect(missing_columns)
    conn.execute(
        "CREATE TABLE prices (ticker TEXT, datetime TEXT, interval TEXT)"
    )
    conn.commit()
    conn.close()

    for path in (directory, broken, junk, missing_table, missing_columns):
        before = _tree_snapshot(tmp_path)
        result = valuation_price.get_valuation_price_basis(
            "AAPL",
            db_path=str(path),
            now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
        )
        _assert_unavailable(result, "2026-06-23")
        assert _tree_snapshot(tmp_path) == before
        assert "private" not in repr(result)

    valid = _make_prices_db(tmp_path / "valid.db")

    def fail_query(*_args, **_kwargs):
        raise sqlite3.OperationalError("private query path marker")

    with monkeypatch.context() as patcher:
        patcher.setattr(valuation_price.sqlite3, "connect", fail_query)
        result = valuation_price.get_valuation_price_basis(
            "AAPL",
            db_path=str(valid),
            now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
        )
    _assert_unavailable(result, "2026-06-23")
    assert "private" not in repr(result)

    def fail_calendar(_day: date) -> dict:
        raise RuntimeError("private calendar marker")

    with monkeypatch.context() as patcher:
        patcher.setattr(market_sessions, "_market_day_status", fail_calendar)
        result = valuation_price.get_valuation_price_basis(
            "AAPL",
            db_path=str(valid),
            now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
        )
    _assert_unavailable(result, None)
    assert "private" not in repr(result)


def test_et_market_date_not_raw_utc_date_owns_selection(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    db = _make_prices_db(
        tmp_path / "market.db",
        [
            ("AAPL", "2026-06-23T00:15:00+0000", "15min", 999.0),
            ("AAPL", "2026-06-24T00:15:00+0000", "15min", 106.0),
        ],
    )

    result = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
    )

    _assert_available(
        result,
        market_date="2026-06-23",
        timestamp="2026-06-24T00:15:00+00:00",
        price=106.0,
    )


def test_invalid_close_values_do_not_qualify(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    invalid = (None, "NaN", "Infinity", "not-a-number", 0, -1, -math.inf)
    rows = [
        (
            "AAPL",
            f"2026-06-23T{14 + index:02d}:00:00+0000",
            "15min",
            value,
        )
        for index, value in enumerate(invalid)
    ]
    db = _make_prices_db(tmp_path / "market.db", rows)

    result = get_valuation_price_basis(
        "AAPL",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
    )

    _assert_unavailable(result, "2026-06-23")


def test_alias_resolves_to_canonical_price_rows(tmp_path):
    from src.valuation_price import get_valuation_price_basis

    db = _make_prices_db(
        tmp_path / "market.db",
        [("HAPN", "2026-06-23T20:00:00+0000", "15min", 107.0)],
    )
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO ticker_aliases (alias, canonical) VALUES ('LC', 'HAPN')"
    )
    conn.commit()
    conn.close()

    result = get_valuation_price_basis(
        " lc ",
        db_path=str(db),
        now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET),
    )

    _assert_available(
        result,
        market_date="2026-06-23",
        timestamp="2026-06-23T20:00:00+00:00",
        price=107.0,
    )
