"""Local-only fundamentals cache helpers.

S-H2 makes the generic LocalMarketDatabaseBackend financial-cache path local-only.
This helper still matters because stored fundamentals must also bypass plain
PG DatabaseBackend rows and return an honest miss when no local SQLite cache exists.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Mapping
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


def _local_cache_reader(backend: Any):
    if backend is None:
        return None
    market = getattr(backend, "_market", None)
    if market is not None and hasattr(market, "get_financial_cache"):
        return market.get_financial_cache
    module = type(backend).__module__
    if module == "src.tools.backends.db_backend":
        return None
    if hasattr(backend, "get_financial_cache"):
        return backend.get_financial_cache
    return None


def read_cached_sec_fundamentals(
    backend: Any,
    ticker: str,
    period: str = "annual",
) -> Tuple[Optional[FundamentalsResult], bool]:
    """Return (cached_result, negative_cached) from local cache only."""
    reader = _local_cache_reader(backend)
    if reader is None:
        return None, False
    cache_key = fundamentals_analysis_cache_key(ticker, period)
    try:
        payload = reader(cache_key)
    except Exception as exc:  # noqa: BLE001 - cache read must not break callers.
        logger.debug("local fundamentals cache read failed for %s: %s", cache_key, exc)
        return None, False
    if not payload:
        return None, False
    if isinstance(payload, dict) and payload.get("_negative"):
        return None, True
    try:
        result = FundamentalsResult.model_validate(payload)
    except Exception:  # noqa: BLE001 - stale/incompatible cache shape is a miss.
        return None, False
    if not result.snapshot_date and result.data_source == "none":
        return None, False
    return result, False
