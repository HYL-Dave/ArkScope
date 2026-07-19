"""
Seeking Alpha Alpha Picks client.

Reads portfolio data from DAL (persisted by Chrome extension via native messaging).
The extension handles DOM scraping; this client handles cache TTL and provides
the interface consumed by sa_tools.py.

Usage:
    client = SAAlphaPicksClient(dal=dal)
    portfolio = client.get_portfolio()         # cached, stale warning if old
    detail = client.get_pick_detail("NVDA")    # cached detail report
    result = client.refresh_portfolio()        # returns current state + hint
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

_REFRESH_HINT = (
    "Data is managed by the SA Alpha Picks Chrome extension. "
    "Click the extension icon in Chrome toolbar to refresh."
)


class SAAlphaPicksClient:
    """Client for SA Alpha Picks data (extension-backed)."""

    def __init__(
        self,
        dal=None,
        cache_hours: int = 24,
        detail_cache_days: int = 7,
    ):
        self._dal = dal
        self._cache_hours = cache_hours
        self._detail_cache_days = detail_cache_days

    def get_portfolio(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Alpha Picks portfolio from DAL cache.

        Returns current + closed picks with freshness metadata.
        Adds stale_warning if cache is older than cache_hours.
        """
        if self._dal is None:
            return {"error": "DAL not configured"}

        meta = self._dal.get_sa_refresh_meta()
        current = self._dal.get_sa_portfolio(portfolio_status="current")
        closed = self._dal.get_sa_portfolio(portfolio_status="closed")

        # Check staleness
        stale_warning = self._check_staleness(meta)

        is_partial = not (
            meta.get("current", {}).get("ok", False)
            and meta.get("closed", {}).get("ok", False)
        )

        result = {
            "current": current,
            "closed": closed,
            "freshness": meta,
            "is_partial": is_partial,
        }
        if stale_warning:
            result["stale_warning"] = stale_warning
        if not current and not closed:
            result["refresh_hint"] = _REFRESH_HINT
        return result

    def get_pick_detail(
        self, symbol: str, picked_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get detail for a specific pick from DAL cache.

        Returns:
            - Pick dict with detail_report if available
            - Pick dict with detail_report=None if pick exists but no detail
            - None if pick not found (triggers closed-only hint in tool layer)
        """
        if self._dal is None:
            return None

        cached = self._dal.get_sa_pick_detail(symbol, picked_date)
        if not cached:
            return None  # Preserves None contract for sa_tools.py hint logic

        # Check detail staleness
        if cached.get("detail_report") and cached.get("detail_fetched_at"):
            fetched_at = cached["detail_fetched_at"]
            if isinstance(fetched_at, str):
                fetched_at = datetime.fromisoformat(
                    fetched_at.replace("Z", "+00:00")
                )
            now = datetime.now(tz=timezone.utc)
            age_days = (now - fetched_at).days
            if age_days > self._detail_cache_days:
                cached["detail_stale_warning"] = (
                    f"Detail report is {age_days}d old "
                    f"(limit: {self._detail_cache_days}d). "
                    "Click SA extension in Chrome to refresh."
                )

        return cached

    def refresh_portfolio(self) -> Dict[str, Any]:
        """Return current state from DAL + refresh hint.

        Actual refresh is done by Chrome extension. This method reads
        whatever the extension has most recently written to DAL.
        """
        if self._dal is None:
            return {"error": "DAL not configured"}

        meta = self._dal.get_sa_refresh_meta()
        current_meta = meta.get("current", {})
        closed_meta = meta.get("closed", {})

        current = self._dal.get_sa_portfolio(portfolio_status="current")
        closed = self._dal.get_sa_portfolio(portfolio_status="closed")

        is_partial = not (
            current_meta.get("ok", False) and closed_meta.get("ok", False)
        )

        result = {
            "current": current,
            "closed": closed,
            "freshness": meta,
            "is_partial": is_partial,
            "refresh_hint": _REFRESH_HINT,
        }
        return result

    def _check_staleness(self, meta: Dict) -> Optional[str]:
        """Check if any scope's cache is older than cache_hours."""
        now = datetime.now(tz=timezone.utc)
        for scope in ("current", "closed"):
            scope_meta = meta.get(scope, {})
            last_success = scope_meta.get("last_success_at")
            if not last_success:
                continue
            if isinstance(last_success, str):
                last_success = datetime.fromisoformat(
                    last_success.replace("Z", "+00:00")
                )
            age_hours = (now - last_success).total_seconds() / 3600
            if age_hours > self._cache_hours:
                return (
                    f"Data is {age_hours:.0f}h old (limit: {self._cache_hours}h). "
                    "Click SA extension in Chrome to refresh."
                )
        return None
