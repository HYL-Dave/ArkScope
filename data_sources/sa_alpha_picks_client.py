"""
Seeking Alpha Alpha Picks client.

Reads portfolio data from DAL (persisted by Chrome extension via native messaging).
The extension handles DOM scraping; this client handles cache TTL, ticker sync,
and provides the interface consumed by sa_tools.py.

Usage:
    client = SAAlphaPicksClient(dal=dal)
    portfolio = client.get_portfolio()         # cached, stale warning if old
    detail = client.get_pick_detail("NVDA")    # cached detail report
    result = client.refresh_portfolio()        # returns current state + hint
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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
        return cached

    def refresh_portfolio(self, sync_tickers: bool = False) -> Dict[str, Any]:
        """Return current state from DAL + refresh hint.

        Actual refresh is done by Chrome extension. This method reads
        whatever the extension has most recently written to DAL.

        Args:
            sync_tickers: If True and data exists, sync tickers to collection.
                Normally ticker sync is done by native host on refresh success.
                This is a fallback for manual trigger.
        """
        if self._dal is None:
            return {"error": "DAL not configured"}

        meta = self._dal.get_sa_refresh_meta()
        current_meta = meta.get("current", {})
        closed_meta = meta.get("closed", {})

        has_data = current_meta.get("ok") or closed_meta.get("ok")

        # Fallback ticker sync (normally done by native host)
        if sync_tickers and has_data:
            try:
                current = self._dal.get_sa_portfolio(portfolio_status="current")
                if current:
                    self.sync_tickers_to_collection(current)
            except Exception as e:
                logger.warning("Ticker sync failed: %s", e)

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

    def sync_tickers_to_collection(self, picks: List[Dict]) -> None:
        """Sync current + non-stale picks symbols to tickers_core.json tier3.

        Public method — called by native host on refresh success and
        by refresh_portfolio() as fallback.

        Behavior:
        - Replaces (not appends) sa_alpha_picks_auto with current picks only.
          When a pick moves to removed, it drops out of the auto bucket.
        - Deduplicates: excludes tickers already present in tier1/tier2.
        """
        current_symbols = {
            p["symbol"]
            for p in picks
            if p.get("portfolio_status") == "current"
            and not p.get("is_stale", False)
            and p.get("symbol")
        }

        if not current_symbols:
            return

        tickers_path = Path("config/tickers_core.json")
        if not tickers_path.exists():
            logger.warning("tickers_core.json not found, skipping ticker sync")
            return

        try:
            with open(tickers_path) as f:
                tickers_config = json.load(f)

            # Collect tickers already in tier1 and tier2 (no need to duplicate)
            existing_tickers = set()
            for tier_key in ("tier1_core", "tier2_extended"):
                tier = tickers_config.get(tier_key, {})
                for group in tier.values():
                    if isinstance(group, dict) and "tickers" in group:
                        existing_tickers.update(group["tickers"])

            # Only add tickers not already covered by higher tiers
            new_symbols = sorted(current_symbols - existing_tickers)

            if "tier3_user_watchlist" not in tickers_config:
                tickers_config["tier3_user_watchlist"] = {}

            tier3 = tickers_config["tier3_user_watchlist"]

            tier3["sa_alpha_picks_auto"] = {
                "tickers": new_symbols,
                "description": "Auto-synced from SA Alpha Picks (current only, excludes tier1/tier2)",
            }

            tmp_path = tickers_path.with_suffix(".json.tmp")
            with open(tmp_path, "w") as f:
                json.dump(tickers_config, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, tickers_path)

            logger.info(
                "Synced %d SA Alpha Picks symbols to tickers_core.json", len(merged)
            )
        except Exception as e:
            logger.error("Failed to sync tickers: %s", e)
            raise
