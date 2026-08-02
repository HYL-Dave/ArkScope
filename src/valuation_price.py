"""Read-only selection of a qualified local price for valuation."""

from __future__ import annotations

import logging
import math
import os
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

from src.market_data_admin import resolve_market_db_path
from src.market_sessions import EXCHANGE_TZ, latest_completed_market_date
from src.tools.schemas import ValuationPriceBasis


logger = logging.getLogger(__name__)

_REQUIRED_PRICE_COLUMNS = frozenset({"ticker", "datetime", "interval", "close"})


def _unavailable(required_market_date: date | None) -> ValuationPriceBasis:
    return ValuationPriceBasis(
        available=False,
        source=None,
        interval=None,
        required_market_date=(
            required_market_date.isoformat() if required_market_date else None
        ),
        market_date=None,
        timestamp=None,
        price=None,
        empty_reason="no_qualified_price",
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _parse_aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    elif len(text) >= 5 and text[-5] in "+-" and text[-4:].isdigit():
        text = f"{text[:-2]}:{text[-2:]}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _positive_finite_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def get_valuation_price_basis(
    ticker: str,
    *,
    db_path: str | None = None,
    now_et: datetime | None = None,
) -> ValuationPriceBasis:
    """Select the latest valid 15-minute close on the required ET market date."""
    normalized_ticker = (ticker or "").strip().upper()
    try:
        required_market_date = latest_completed_market_date(now_et)
    except Exception:  # Calendar failures are a typed absence at this boundary.
        logger.warning("Valuation price calendar lookup failed")
        return _unavailable(None)

    if required_market_date is None or not normalized_ticker:
        return _unavailable(required_market_date)

    conn: sqlite3.Connection | None = None
    try:
        path = os.fspath(db_path or resolve_market_db_path())
        if not os.path.lexists(path):
            return _unavailable(required_market_date)

        absolute_path = os.path.abspath(path)
        uri = f"file:{quote(absolute_path, safe='/')}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("PRAGMA query_only=ON")

        if not _table_exists(conn, "prices"):
            return _unavailable(required_market_date)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(prices)")}
        if not _REQUIRED_PRICE_COLUMNS.issubset(columns):
            return _unavailable(required_market_date)

        canonical_ticker = normalized_ticker
        if _table_exists(conn, "ticker_aliases"):
            alias = conn.execute(
                "SELECT canonical FROM ticker_aliases WHERE alias=?",
                (normalized_ticker,),
            ).fetchone()
            if alias:
                canonical_ticker = str(alias[0]).strip().upper()

        exchange_tz = ZoneInfo(EXCHANGE_TZ)
        start_et = datetime.combine(required_market_date, time.min, exchange_tz)
        end_et = start_et + timedelta(days=1)
        start_utc = (start_et.astimezone(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%S+0000"
        )
        end_utc = (end_et.astimezone(timezone.utc) + timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%S+0000"
        )
        rows = conn.execute(
            "SELECT datetime, close FROM prices "
            "WHERE ticker=? AND interval='15min' AND datetime>=? AND datetime<?",
            (canonical_ticker, start_utc, end_utc),
        ).fetchall()

        selected_timestamp: datetime | None = None
        selected_price: float | None = None
        for timestamp_value, close_value in rows:
            timestamp = _parse_aware_timestamp(timestamp_value)
            price = _positive_finite_float(close_value)
            if timestamp is None or price is None:
                continue
            if timestamp.astimezone(exchange_tz).date() != required_market_date:
                continue
            if selected_timestamp is None or timestamp > selected_timestamp:
                selected_timestamp = timestamp
                selected_price = price

        if selected_timestamp is None or selected_price is None:
            return _unavailable(required_market_date)

        market_date = required_market_date.isoformat()
        return ValuationPriceBasis(
            available=True,
            source="local_market_db",
            interval="15min",
            required_market_date=market_date,
            market_date=market_date,
            timestamp=selected_timestamp.astimezone(timezone.utc).isoformat(),
            price=selected_price,
            empty_reason=None,
        )
    except Exception:
        logger.warning("Valuation price store lookup failed")
        return _unavailable(required_market_date)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.warning("Valuation price store close failed")
