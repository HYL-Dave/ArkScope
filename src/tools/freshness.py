"""
Data Freshness Registry — track health/freshness of all data sources.

Provides:
- FreshnessRegistry: process-level singleton with 5-min cache
- SourceHealth: per-source health status
- check_data_freshness(): tool function for agent queries
- get_registry() / reset_for_tests(): singleton management
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Staleness thresholds (hours)
_DEFAULT_THRESHOLDS = {
    "news": 24,
    "prices": 48,      # 考慮週末
    "iv_history": 48,   # 考慮週末
}

_CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class SourceHealth:
    """Health status for one data source."""

    source: str
    latest_data_at: Optional[datetime] = None
    record_count_recent: int = 0
    expected_frequency: str = "daily"
    is_stale: bool = False
    stale_reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class FreshnessRegistry:
    """Track freshness of all data sources.

    Uses db_backend.query_health_stats() for DB queries.
    Internal cache (5 min) avoids repeated scans.
    Thread-safe via _scan_lock.
    """

    def __init__(
        self,
        db_backend=None,
        thresholds: Optional[Dict[str, int]] = None,
    ) -> None:
        self._backend = db_backend
        self._thresholds = thresholds or _DEFAULT_THRESHOLDS
        self._scan_lock = threading.Lock()
        self._cache: Dict[str, SourceHealth] = {}
        self._cache_ts: float = 0.0

    def scan(self, force: bool = False) -> Dict[str, SourceHealth]:
        """Scan all data sources and return health status.

        Uses 5-min cache. Pass force=True to bypass cache.
        """
        if not force and (time.time() - self._cache_ts < _CACHE_TTL_SECONDS):
            return self._cache

        with self._scan_lock:
            # Double-check after acquiring lock
            if not force and (time.time() - self._cache_ts < _CACHE_TTL_SECONDS):
                return self._cache

            result: Dict[str, SourceHealth] = {}
            if self._backend is None:
                self._cache = result
                self._cache_ts = time.time()
                return result

            try:
                stats = self._backend.query_health_stats()
            except Exception as e:
                logger.warning("FreshnessRegistry.scan() failed: %s", e)
                err_msg = f"query failed: {e}"
                for src in ("news", "prices", "iv_history", "fundamentals_cache"):
                    result[src] = SourceHealth(
                        source=src, is_stale=True, stale_reason=err_msg,
                    )
                self._cache = result
                self._cache_ts = time.time()
                return result

            result["news"] = self._parse_news(stats.get("news", {}))
            result["prices"] = self._parse_prices(stats.get("prices", {}))
            result["iv_history"] = self._parse_iv(stats.get("iv_history", {}))
            result["fundamentals_cache"] = self._parse_financial_cache(
                stats.get("financial_cache", {})
            )

            self._cache = result
            self._cache_ts = time.time()
            return result

    def get_all_freshness(self) -> Dict[str, SourceHealth]:
        """Return cached scan results (does not trigger new scan)."""
        return self._cache

    def get_freshness(self, source: str) -> Optional[SourceHealth]:
        """Return health for a specific source."""
        return self._cache.get(source)

    def format_summary(self) -> str:
        """One-line summary for system prompt injection."""
        if not self._cache:
            return ""

        parts = []
        for key in ("news", "prices", "iv_history", "fundamentals_cache"):
            h = self._cache.get(key)
            if not h:
                continue
            if key == "news":
                parts.append(self._fmt_news(h))
            elif key == "prices":
                parts.append(self._fmt_prices(h))
            elif key == "iv_history":
                parts.append(self._fmt_iv(h))
            elif key == "fundamentals_cache":
                parts.append(self._fmt_cache(h))

        if not parts:
            return ""

        summary = " | ".join(parts)
        stale_sources = [
            h.source for h in self._cache.values() if h.is_stale
        ]
        if stale_sources:
            summary += "\nStale data may affect analysis accuracy. Use check_data_freshness for details."
        return summary

    def format_detailed(self) -> str:
        """Multi-line detailed report for tool output."""
        if not self._cache:
            return "No data sources scanned yet."

        lines = ["=== Data Freshness Report ===", ""]
        now = datetime.now(timezone.utc)

        for key in ("news", "prices", "iv_history", "fundamentals_cache"):
            h = self._cache.get(key)
            if not h:
                continue

            status = "STALE" if h.is_stale else "OK"
            lines.append(f"[{status}] {h.source}")

            if h.latest_data_at:
                age = now - h.latest_data_at
                hours = age.total_seconds() / 3600
                lines.append(f"  Latest: {h.latest_data_at.strftime('%Y-%m-%d %H:%M UTC')} ({hours:.0f}h ago)")

            if h.record_count_recent:
                lines.append(f"  Recent records (7d): {h.record_count_recent}")

            if h.is_stale:
                lines.append(f"  Reason: {h.stale_reason}")

            for dk, dv in h.details.items():
                lines.append(f"  {dk}: {dv}")

            lines.append("")

        return "\n".join(lines)

    # ── Parsing helpers ───────────────────────────────────────

    def _parse_news(self, stat: Dict[str, Any]) -> SourceHealth:
        h = SourceHealth(source="news", expected_frequency="daily")
        if stat.get("error"):
            h.is_stale = True
            h.stale_reason = f"query failed: {stat['error']}"
            return h

        rows = stat.get("rows", [])
        if not rows:
            h.is_stale = True
            h.stale_reason = "no news data found"
            return h

        # rows: list of (source, latest, recent_count)
        now = datetime.now(timezone.utc)
        latest_overall = None
        total_recent = 0
        source_details = []

        for row in rows:
            src, latest, recent_count = row[0], row[1], row[2]
            total_recent += recent_count or 0
            source_details.append(f"{src}: {recent_count or 0} recent")
            if latest:
                ts = latest if isinstance(latest, datetime) else _parse_ts(latest)
                if ts and (latest_overall is None or ts > latest_overall):
                    latest_overall = ts

        h.latest_data_at = latest_overall
        h.record_count_recent = total_recent
        h.details["sources"] = ", ".join(source_details)

        threshold_hours = self._thresholds.get("news", 24)
        if latest_overall:
            age_hours = (now - latest_overall).total_seconds() / 3600
            if age_hours > threshold_hours:
                h.is_stale = True
                h.stale_reason = f"latest news is {age_hours:.0f}h old (threshold: {threshold_hours}h)"

        return h

    def _parse_prices(self, stat: Dict[str, Any]) -> SourceHealth:
        h = SourceHealth(source="prices", expected_frequency="daily")
        if stat.get("error"):
            h.is_stale = True
            h.stale_reason = f"query failed: {stat['error']}"
            return h

        rows = stat.get("rows", [])
        if not rows or not rows[0] or not rows[0][0]:
            h.is_stale = True
            h.stale_reason = "no price data found"
            return h

        latest = rows[0][0]
        ts = latest if isinstance(latest, datetime) else _parse_ts(latest)
        h.latest_data_at = ts

        threshold_hours = self._thresholds.get("prices", 48)
        if ts:
            now = datetime.now(timezone.utc)
            age_hours = (now - ts).total_seconds() / 3600
            if age_hours > threshold_hours:
                h.is_stale = True
                h.stale_reason = f"latest price is {age_hours:.0f}h old (threshold: {threshold_hours}h)"

        return h

    def _parse_iv(self, stat: Dict[str, Any]) -> SourceHealth:
        h = SourceHealth(source="iv_history", expected_frequency="daily")
        if stat.get("error"):
            h.is_stale = True
            h.stale_reason = f"query failed: {stat['error']}"
            return h

        rows = stat.get("rows", [])
        if not rows or not rows[0] or not rows[0][0]:
            h.is_stale = True
            h.stale_reason = "no IV data found"
            return h

        latest = rows[0][0]
        ts = latest if isinstance(latest, datetime) else _parse_ts(latest)
        h.latest_data_at = ts

        threshold_hours = self._thresholds.get("iv_history", 48)
        if ts:
            now = datetime.now(timezone.utc)
            age_hours = (now - ts).total_seconds() / 3600
            if age_hours > threshold_hours:
                h.is_stale = True
                h.stale_reason = f"latest IV is {age_hours:.0f}h old (threshold: {threshold_hours}h)"

        return h

    def _parse_financial_cache(self, stat: Dict[str, Any]) -> SourceHealth:
        h = SourceHealth(source="fundamentals_cache", expected_frequency="quarterly")
        if stat.get("error"):
            h.is_stale = True
            h.stale_reason = f"query failed: {stat['error']}"
            return h

        rows = stat.get("rows", [])
        total_cached = 0
        total_expired = 0
        source_details = []

        for row in rows:
            src, cached, expired = row[0], row[1], row[2]
            total_cached += cached or 0
            total_expired += expired or 0
            source_details.append(f"{src}: {cached or 0} cached, {expired or 0} expired")

        h.record_count_recent = total_cached
        h.details["cached"] = total_cached
        h.details["expired"] = total_expired
        if source_details:
            h.details["sources"] = "; ".join(source_details)
        # Fundamentals: don't judge stale (quarterly nature), just report counts

        return h

    # ── Format helpers ────────────────────────────────────────

    @staticmethod
    def _fmt_news(h: SourceHealth) -> str:
        if h.is_stale:
            return f"News: STALE ({h.stale_reason})"
        age = ""
        if h.latest_data_at:
            hours = (datetime.now(timezone.utc) - h.latest_data_at).total_seconds() / 3600
            age = f"{hours:.0f}h ago"
        sources = h.details.get("sources", "")
        parts = [p for p in [age, sources] if p]
        return f"News: fresh ({', '.join(parts)})" if parts else "News: fresh"

    @staticmethod
    def _fmt_prices(h: SourceHealth) -> str:
        if h.is_stale:
            return f"Prices: STALE ({h.stale_reason})"
        if h.latest_data_at:
            return f"Prices: fresh (1d bars to {h.latest_data_at.strftime('%Y-%m-%d')})"
        return "Prices: fresh"

    @staticmethod
    def _fmt_iv(h: SourceHealth) -> str:
        if h.is_stale:
            return f"IV: STALE ({h.stale_reason})"
        if h.latest_data_at:
            return f"IV: fresh ({h.latest_data_at.strftime('%Y-%m-%d')})"
        return "IV: fresh"

    @staticmethod
    def _fmt_cache(h: SourceHealth) -> str:
        cached = h.details.get("cached", 0)
        expired = h.details.get("expired", 0)
        if expired > 0:
            return f"Fundamentals: {cached} cached ({expired} expired)"
        return f"Fundamentals: {cached} cached"


# ── Singleton management ──────────────────────────────────────

_registry_instance: Optional[FreshnessRegistry] = None
_registry_lock = threading.Lock()
_registry_backend_id: Optional[int] = None


def get_registry(db_backend=None) -> Optional[FreshnessRegistry]:
    """Get or create the process-level singleton FreshnessRegistry.

    Thread-safe. If db_backend changes (different instance), rebuilds.
    """
    global _registry_instance, _registry_backend_id
    if db_backend is None:
        return _registry_instance

    backend_id = id(db_backend)
    if _registry_instance is not None and _registry_backend_id == backend_id:
        return _registry_instance

    with _registry_lock:
        # Double-check under lock
        if _registry_instance is not None and _registry_backend_id == backend_id:
            return _registry_instance
        _registry_instance = FreshnessRegistry(db_backend=db_backend)
        _registry_backend_id = backend_id
        return _registry_instance


def reset_for_tests() -> None:
    """Reset singleton + cache for test isolation. Test-only, do NOT call at runtime."""
    global _registry_instance, _registry_backend_id
    with _registry_lock:
        _registry_instance = None
        _registry_backend_id = None


# ── Tool function ─────────────────────────────────────────────

def check_data_freshness(dal) -> str:
    """Check health and freshness of all data sources.

    Returns detailed report of each source's status.
    Requires database backend; returns informational message for file backend.
    """
    try:
        from src.tools.backends.db_backend import DatabaseBackend
    except ImportError:
        return "Data freshness check requires database backend (psycopg2 not available)."

    if not hasattr(dal, "_backend") or not isinstance(dal._backend, DatabaseBackend):
        return (
            "Data freshness check requires database backend. "
            "File-based backend does not support health queries."
        )

    registry = get_registry(db_backend=dal._backend)
    if registry is None:
        return "Failed to initialize freshness registry."

    registry.scan(force=True)
    return registry.format_detailed()


# ── Utility ───────────────────────────────────────────────────

def _parse_ts(value) -> Optional[datetime]:
    """Parse a timestamp value to datetime. Handles str, date, datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    # date object (no time)
    from datetime import date
    if isinstance(date, type) and isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    # String
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return None
