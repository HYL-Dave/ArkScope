"""Finnhub calendar ingestion for P1.2 (commit 3/6).

Three callable entry points the job runner wraps (commit 4):

  - ``fetch_finnhub_economic_events(dal, ...)`` — refresh
    ``cal_economic_events`` + revision log for a date window.
  - ``fetch_finnhub_earnings_events(dal, ...)`` — refresh
    ``cal_earnings_events`` per-symbol (unfiltered query under-samples
    the universe; see smoke §5.5).
  - ``fetch_finnhub_ipo_events(dal, ...)`` — refresh ``cal_ipo_events``
    for a date window.

All three follow the canonical/revision upsert contract from the
``MacroCalendarStore`` (see ``src/macro_calendar/store.py``):

  - First ingestion of a fingerprint → ``"inserted"`` (canonical row +
    baseline revision in one transaction).
  - Re-ingestion with changed tracked fields → ``"mutated"`` (canonical
    update + observed-state revision, same transaction).
  - Re-ingestion with identical tracked fields → ``"unchanged"`` (no
    write at all — not even a ``fetched_at`` bump).

No FastAPI / agent tool wiring lives here (that's commit 5/6).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from data_sources.finnhub_calendar_client import (
    FinnhubCalendarClient,
    FinnhubError,
)
from src.macro_calendar.store import MacroCalendarStore

logger = logging.getLogger(__name__)


@dataclass
class FinnhubIngestionStats:
    """Per-job counters returned to the job dispatcher."""

    events_inserted: int = 0
    events_mutated: int = 0
    events_unchanged: int = 0
    events_skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "events_inserted": self.events_inserted,
            "events_mutated": self.events_mutated,
            "events_unchanged": self.events_unchanged,
            "events_skipped": self.events_skipped,
            "errors": list(self.errors),
        }


def _record_action(stats: FinnhubIngestionStats, action: str) -> None:
    if action == "inserted":
        stats.events_inserted += 1
    elif action == "mutated":
        stats.events_mutated += 1
    elif action == "unchanged":
        stats.events_unchanged += 1


# ---------------------------------------------------------------------------
# Economic events
# ---------------------------------------------------------------------------


def fetch_finnhub_economic_events(
    dal: Any,
    *,
    date_from: date,
    date_to: date,
    client: Optional[FinnhubCalendarClient] = None,
    observed_at: Optional[datetime] = None,
) -> FinnhubIngestionStats:
    """Refresh cal_economic_events + revision log for [date_from, date_to].

    ``observed_at`` pins the revision timestamp (useful in tests and
    backfill runs); defaults to ``datetime.now(timezone.utc)`` inside
    the store if omitted.
    """
    stats = FinnhubIngestionStats()
    store = MacroCalendarStore(dal)
    if not store.is_available():
        stats.errors.append("DAL backend unavailable")
        return stats

    fh = client or FinnhubCalendarClient()
    try:
        events = fh.get_economic_events(date_from, date_to)
    except FinnhubError as exc:
        stats.errors.append(f"get_economic_events failed: {exc}")
        return stats

    for ev in events:
        try:
            payload: Dict[str, Any] = {
                "country": ev.country,
                "event_name": ev.event,
                "event_time": ev.event_time,
                "impact": ev.impact,
                "unit": ev.unit,
                "actual": ev.actual,
                "estimate": ev.estimate,
                "prev": ev.prev,
            }
            source_payload: Dict[str, Any] = {
                "country": ev.country,
                "event": ev.event,
                "time": ev.event_time.strftime("%Y-%m-%d %H:%M:%S"),
                "impact": ev.impact,
                "unit": ev.unit,
                "actual": ev.actual,
                "estimate": ev.estimate,
                "prev": ev.prev,
            }
            _, action = store.upsert_economic_event(
                payload,
                source_payload=source_payload,
                observed_at=observed_at,
            )
            _record_action(stats, action)
        except Exception as exc:
            stats.events_skipped += 1
            stats.errors.append(f"economic {ev.country}/{ev.event}: {exc}")
    return stats


# ---------------------------------------------------------------------------
# Earnings events
# ---------------------------------------------------------------------------


def fetch_finnhub_earnings_events(
    dal: Any,
    *,
    date_from: date,
    date_to: date,
    symbols: Optional[Iterable[str]] = None,
    client: Optional[FinnhubCalendarClient] = None,
    observed_at: Optional[datetime] = None,
) -> FinnhubIngestionStats:
    """Refresh cal_earnings_events for [date_from, date_to].

    When ``symbols`` is provided, one API call per symbol guarantees
    complete watchlist coverage (smoke §5.5: unfiltered query omitted
    AAPL from the same window that a symbol-filtered call returned it).
    Without symbols, a single unfiltered call is issued — acceptable for
    a "what's coming up broadly" view but unreliable for specific tickers.

    Cross-symbol deduplication: the same (symbol, year, quarter) row
    appearing in multiple per-symbol responses is written only once.
    """
    stats = FinnhubIngestionStats()
    store = MacroCalendarStore(dal)
    if not store.is_available():
        stats.errors.append("DAL backend unavailable")
        return stats

    fh = client or FinnhubCalendarClient()
    symbol_list: List[Optional[str]] = (
        sorted({str(s).upper() for s in symbols}) if symbols else [None]
    )

    seen: Set[Tuple[str, int, int]] = set()
    for sym in symbol_list:
        try:
            events = fh.get_earnings_events(date_from, date_to, symbol=sym)
        except FinnhubError as exc:
            stats.errors.append(f"get_earnings_events({sym}): {exc}")
            continue
        for ev in events:
            dedup_key = (ev.symbol, ev.year, ev.quarter)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            try:
                payload: Dict[str, Any] = {
                    "symbol": ev.symbol,
                    "report_date": ev.report_date,
                    "year": ev.year,
                    "quarter": ev.quarter,
                    "hour": ev.hour,
                    "eps_estimate": ev.eps_estimate,
                    "eps_actual": ev.eps_actual,
                    "revenue_estimate": ev.revenue_estimate,
                    "revenue_actual": ev.revenue_actual,
                }
                source_payload: Dict[str, Any] = {
                    "symbol": ev.symbol,
                    "date": ev.report_date.isoformat(),
                    "year": ev.year,
                    "quarter": ev.quarter,
                    "hour": ev.hour,
                    "epsEstimate": ev.eps_estimate,
                    "epsActual": ev.eps_actual,
                    "revenueEstimate": ev.revenue_estimate,
                    "revenueActual": ev.revenue_actual,
                }
                _, action = store.upsert_earnings_event(
                    payload,
                    source_payload=source_payload,
                    observed_at=observed_at,
                )
                _record_action(stats, action)
            except Exception as exc:
                stats.events_skipped += 1
                stats.errors.append(
                    f"earnings {ev.symbol} {ev.year}Q{ev.quarter}: {exc}"
                )
    return stats


# ---------------------------------------------------------------------------
# IPO events
# ---------------------------------------------------------------------------


def fetch_finnhub_ipo_events(
    dal: Any,
    *,
    date_from: date,
    date_to: date,
    client: Optional[FinnhubCalendarClient] = None,
    observed_at: Optional[datetime] = None,
) -> FinnhubIngestionStats:
    """Refresh cal_ipo_events + revision log for [date_from, date_to]."""
    stats = FinnhubIngestionStats()
    store = MacroCalendarStore(dal)
    if not store.is_available():
        stats.errors.append("DAL backend unavailable")
        return stats

    fh = client or FinnhubCalendarClient()
    try:
        events = fh.get_ipo_events(date_from, date_to)
    except FinnhubError as exc:
        stats.errors.append(f"get_ipo_events failed: {exc}")
        return stats

    for ev in events:
        try:
            payload: Dict[str, Any] = {
                "name": ev.name,
                "ipo_date": ev.ipo_date,
                "symbol": ev.symbol,
                "exchange": ev.exchange,
                "status": ev.status,
                "number_of_shares": ev.number_of_shares,
                "price": ev.price,
                "total_shares_value": ev.total_shares_value,
            }
            source_payload: Dict[str, Any] = {
                "name": ev.name,
                "date": ev.ipo_date.isoformat(),
                "symbol": ev.symbol,
                "exchange": ev.exchange,
                "status": ev.status,
                "numberOfShares": ev.number_of_shares,
                "price": ev.price,
                "totalSharesValue": ev.total_shares_value,
            }
            _, action = store.upsert_ipo_event(
                payload,
                source_payload=source_payload,
                observed_at=observed_at,
            )
            _record_action(stats, action)
        except Exception as exc:
            stats.events_skipped += 1
            stats.errors.append(f"IPO {ev.name}: {exc}")
    return stats