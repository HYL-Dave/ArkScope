"""Current local fundamentals-cache helpers."""

from __future__ import annotations

import copy
import json
import logging
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from src.tools.schemas import FundamentalsResult

logger = logging.getLogger(__name__)


DETAILED_FINANCIALS_DYNAMIC_FIELDS = (
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "ev_to_ebitda",
    "ev_to_revenue",
    "fcf_yield",
    "peg_ratio",
)

CALCULATOR_DYNAMIC_FIELDS = (
    "market_cap",
    "enterprise_value",
    "price_to_earnings_ratio",
    "price_to_book_ratio",
    "price_to_sales_ratio",
    "enterprise_value_to_ebitda_ratio",
    "enterprise_value_to_revenue_ratio",
    "free_cash_flow_yield",
    "peg_ratio",
)

_DETAILED_FINANCIALS_STATIC_KEYS = frozenset({
    "version",
    "ticker",
    "period",
    "years_for_growth",
    "data_source",
    "report_date",
    "static_metrics",
    "tech_metrics",
    "valuation_inputs",
})
_FORBIDDEN_STATIC_KEYS = frozenset({
    "price",
    "timestamp",
    "market_date",
    "valuation_price_basis",
    *DETAILED_FINANCIALS_DYNAMIC_FIELDS,
    *CALCULATOR_DYNAMIC_FIELDS,
})


def detailed_financials_cache_key(ticker: str) -> str:
    return f"detailed_financials:v2:sec_edgar:{ticker.strip().upper()}:annual:y2"


def _contains_forbidden_static_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_STATIC_KEYS or "price" in normalized:
                return True
            if _contains_forbidden_static_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_static_key(item) for item in value)
    return False


def validate_detailed_financials_static_payload(
    payload: object,
    *,
    ticker: str,
) -> Optional[dict[str, object]]:
    """Return a defensive copy of an exact v2 SEC-static payload, else ``None``."""
    if not isinstance(payload, dict) or set(payload) != _DETAILED_FINANCIALS_STATIC_KEYS:
        return None
    expected_ticker = ticker.strip().upper()
    if (
        payload.get("version") != 2
        or payload.get("ticker") != expected_ticker
        or payload.get("period") != "annual"
        or payload.get("years_for_growth") != 2
        or payload.get("data_source") != "sec_edgar"
    ):
        return None
    if payload.get("report_date") is not None and not isinstance(
        payload.get("report_date"), str
    ):
        return None
    for section in ("static_metrics", "tech_metrics", "valuation_inputs"):
        if not isinstance(payload.get(section), dict):
            return None
    if _contains_forbidden_static_key(payload):
        return None
    try:
        return copy.deepcopy(payload)
    except Exception:
        return None


def fundamentals_analysis_cache_key(ticker: str, period: str = "annual") -> str:
    return f"fundamentals_analysis:sec_edgar:{ticker.strip().upper()}:{period}:v1"


def validate_positive_annual_sec_payload(
    payload: object,
    *,
    ticker: str,
) -> Optional[FundamentalsResult]:
    """Validate one positive annual SEC payload shared by stored projections."""
    if not isinstance(payload, dict) or payload.get("_negative"):
        return None
    try:
        result = FundamentalsResult.model_validate(payload)
    except Exception:
        return None
    expected_ticker = ticker.strip().upper()
    if (
        result.ticker.strip().upper() != expected_ticker
        or result.data_source != "sec_edgar"
        or not result.snapshot_date
    ):
        return None
    return result


def _parse_aware_datetime(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def stored_annual_sec_fundamentals(
    conn: sqlite3.Connection,
    *,
    now_utc: Optional[datetime] = None,
) -> dict[str, dict[str, object]]:
    """Project positive, unexpired annual SEC analysis rows by ticker."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    try:
        rows = conn.execute(
            "SELECT cache_key, source, data, expires_at "
            "FROM financial_cache ORDER BY cache_key"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}

    prefix = "fundamentals_analysis:sec_edgar:"
    suffix = ":annual:v1"
    projected: dict[str, dict[str, object]] = {}
    for cache_key, source, raw_payload, expires_at in rows:
        if (
            not isinstance(cache_key, str)
            or not cache_key.startswith(prefix)
            or not cache_key.endswith(suffix)
            or source != "sec_edgar"
        ):
            continue
        ticker = cache_key[len(prefix):-len(suffix)]
        if not ticker or fundamentals_analysis_cache_key(ticker) != cache_key:
            continue
        expiry = _parse_aware_datetime(expires_at)
        if expiry is None or expiry <= now:
            continue
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, (str, bytes)) else raw_payload
        except (TypeError, ValueError):
            continue
        result = validate_positive_annual_sec_payload(payload, ticker=ticker)
        if result is not None:
            projected[ticker] = result.model_dump()
    return projected


def read_cached_sec_fundamentals(
    backend: Any,
    ticker: str,
    period: str = "annual",
) -> Tuple[Optional[FundamentalsResult], bool]:
    """Return (cached_result, negative_cached) from local cache only."""
    if backend is None:
        return None, False
    cache_key = fundamentals_analysis_cache_key(ticker, period)
    try:
        payload = backend.get_financial_cache(cache_key)
    except Exception as exc:  # noqa: BLE001 - cache read must not break callers.
        logger.debug("local fundamentals cache read failed for %s: %s", cache_key, exc)
        return None, False
    if not payload:
        return None, False
    if isinstance(payload, dict) and payload.get("_negative"):
        return None, True
    return validate_positive_annual_sec_payload(payload, ticker=ticker), False
