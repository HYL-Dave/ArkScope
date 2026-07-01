"""Local-only fundamentals cache helpers.

The generic LocalMarketDatabaseBackend.get_financial_cache path can still PG-fallback
to migrate legacy cache rows. S-B needs a stricter contract for fundamentals:
read local SQLite cache only, then return an honest miss.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from src.tools.schemas import FundamentalsResult

logger = logging.getLogger(__name__)


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
