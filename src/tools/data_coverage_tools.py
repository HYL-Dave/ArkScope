"""Local market-data coverage diagnostics for ticker-level research.

This module is intentionally read-only and local-only. It answers whether the
local market mirror has data for a ticker and why a requested price date may be
missing; it never triggers provider fetches or PostgreSQL fallback.
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.market_data_admin import resolve_market_db_path


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _observed(d: date) -> date:
    if d.weekday() == 5:  # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, calendar.monthrange(year, month)[1])
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def _easter_date(year: int) -> date:
    # Gregorian computus.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _us_market_holidays(year: int) -> dict[date, str]:
    return {
        _observed(date(year, 1, 1)): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        _easter_date(year) - timedelta(days=2): "Good Friday",
        _last_weekday(year, 5, 0): "Memorial Day",
        _observed(date(year, 6, 19)): "Juneteenth National Independence Day",
        _observed(date(year, 7, 4)): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
        _observed(date(year, 12, 25)): "Christmas Day",
    }


def _market_day_status(d: date) -> dict:
    if d.weekday() >= 5:
        return {"is_trading_day": False, "reason": "weekend", "holiday": None}
    holiday = _us_market_holidays(d.year).get(d)
    if holiday:
        return {"is_trading_day": False, "reason": "us_market_holiday", "holiday": holiday}
    return {"is_trading_day": True, "reason": "regular_trading_day", "holiday": None}


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _one(conn: sqlite3.Connection, sql: str, params=()):
    return conn.execute(sql, params).fetchone()


def _price_interval(conn: sqlite3.Connection, ticker: str, interval: str) -> dict:
    row = _one(
        conn,
        """
        SELECT COUNT(*) AS count, MIN(datetime) AS earliest, MAX(datetime) AS latest
        FROM prices WHERE ticker=? AND interval=?
        """,
        (ticker, interval),
    )
    count = int(row["count"] or 0)
    latest = row["latest"]
    earliest = row["earliest"]
    return {
        "bar_count": count,
        "earliest_datetime": earliest,
        "latest_datetime": latest,
        "earliest_date": earliest[:10] if earliest else None,
        "latest_date": latest[:10] if latest else None,
    }


def _target_price_status(conn: sqlite3.Connection, ticker: str, target: date) -> dict:
    day = target.isoformat()
    market = _market_day_status(target)
    rows = conn.execute(
        """
        SELECT interval, COUNT(*) AS count
        FROM prices
        WHERE ticker=? AND substr(datetime, 1, 10)=?
        GROUP BY interval ORDER BY interval
        """,
        (ticker, day),
    ).fetchall()
    by_interval = {r["interval"]: int(r["count"]) for r in rows}
    total = sum(by_interval.values())
    if total:
        status, reason = "has_data", "local_bars_present"
    elif not market["is_trading_day"]:
        status, reason = "non_trading_day", market["reason"]
    else:
        status, reason = "missing_local_data", "trading_day_without_local_bars"
    return {
        "date": day,
        "status": status,
        "reason": reason,
        "holiday": market["holiday"],
        "bar_count": total,
        "intervals": by_interval,
    }


def _domain_summary(conn: sqlite3.Connection, table: str, ticker: str, date_col: str) -> dict:
    if not _table_exists(conn, table):
        return {"available": False, "row_count": 0, "earliest_date": None, "latest_date": None}
    row = _one(
        conn,
        f"SELECT COUNT(*) AS count, MIN({date_col}) AS earliest, MAX({date_col}) AS latest FROM {table} WHERE ticker=?",
        (ticker,),
    )
    count = int(row["count"] or 0)
    return {
        "available": count > 0,
        "row_count": count,
        "earliest_date": row["earliest"][:10] if row["earliest"] else None,
        "latest_date": row["latest"][:10] if row["latest"] else None,
    }


def _news_summary(conn: sqlite3.Connection, ticker: str) -> dict:
    out = _domain_summary(conn, "news", ticker, "published_at")
    out["latest_published_date"] = out.pop("latest_date")
    out["earliest_published_date"] = out.pop("earliest_date")
    if out["available"]:
        rows = conn.execute(
            "SELECT source, COUNT(*) AS count FROM news WHERE ticker=? GROUP BY source ORDER BY source",
            (ticker,),
        ).fetchall()
        out["source_breakdown"] = {r["source"]: int(r["count"]) for r in rows}
    else:
        out["source_breakdown"] = {}
    return out


def _sync_meta(conn: sqlite3.Connection) -> dict:
    if not _table_exists(conn, "market_sync_meta"):
        return {}
    rows = conn.execute(
        "SELECT domain, last_success, last_error, rows_added, updated_at FROM market_sync_meta ORDER BY domain"
    ).fetchall()
    return {
        r["domain"]: {
            "last_success": r["last_success"],
            "last_error": r["last_error"],
            "rows_added": r["rows_added"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    }


def get_ticker_data_coverage(ticker: str, target_date: Optional[str] = None) -> dict:
    """Explain local market-data coverage for one ticker.

    This is a diagnostic/scout tool: it reads the local market mirror only and
    reports whether missing price data is expected (weekend/US market holiday) or
    a local coverage gap. It never fetches or writes data.
    """
    t = ticker.strip().upper()
    path = resolve_market_db_path()
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not t:
        return {"ticker": "", "error": "ticker is required", "generated_at": generated_at}
    if not Path(path).exists():
        return {
            "ticker": t,
            "generated_at": generated_at,
            "market_db": {"path": path, "exists": False},
            "note": "local-only diagnostic; no provider fetch attempted",
        }

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        prices = {"available": False, "intervals": {}, "target_date": None}
        if _table_exists(conn, "prices"):
            intervals = {
                interval: _price_interval(conn, t, interval)
                for interval in ("15min", "1h", "1d")
            }
            prices = {
                "available": any(v["bar_count"] > 0 for v in intervals.values()),
                "intervals": intervals,
                "target_date": None,
            }
            try:
                target = _parse_date(target_date)
            except ValueError:
                target = None
                prices["target_date"] = {
                    "date": target_date,
                    "status": "invalid_target_date",
                    "reason": "target_date must be YYYY-MM-DD",
                    "holiday": None,
                    "bar_count": 0,
                    "intervals": {},
                }
            if target is not None:
                prices["target_date"] = _target_price_status(conn, t, target)
        return {
            "ticker": t,
            "generated_at": generated_at,
            "market_db": {"path": path, "exists": True},
            "prices": prices,
            "news": _news_summary(conn, t),
            "iv": _domain_summary(conn, "iv_history", t, "date"),
            "fundamentals": _domain_summary(conn, "fundamentals", t, "snapshot_date"),
            "sync": _sync_meta(conn),
            "note": "local-only diagnostic; no provider fetch attempted",
        }
    finally:
        conn.close()
