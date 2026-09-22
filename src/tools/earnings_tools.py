"""Stored earnings-release observations and complete US trading-session windows.

No provider requests, price refresh, database installation, or trading forecast.
The calendar's release day/session bucket is not an exact announcement timestamp.
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from src.macro_calendar.local_store import EarningsRevisionDateUnavailable, MacroCalendarLocalStore
from src.market_coverage.calendar import XnysCalendarAdapter

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

_DRIFT_WINDOW = 5
_CALENDAR_READ_LIMIT = 1000


def _finite(value: Any) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _sessions(calendar: XnysCalendarAdapter, start: date, count: int, step: int) -> list[date]:
    result = []
    day = start
    for _ in range(366):
        day += timedelta(days=step)
        session = calendar.session(day)
        if session.kind.value == "unknown":
            return []
        if session.kind.value == "open":
            result.append(day)
            if len(result) == count:
                return result
    return []


def _compute_move(
    closes: list[float], dates: list[str], idx: int,
    *, calendar: XnysCalendarAdapter | None = None, now: datetime | None = None,
) -> dict[str, Any] | None:
    if idx < 0 or idx >= len(dates) or len(closes) != len(dates):
        return None
    calendar = calendar or XnysCalendarAdapter()
    now = now or datetime.now(timezone.utc)
    try:
        reaction_day = date.fromisoformat(dates[idx])
    except ValueError:
        return None
    counts = Counter(dates)
    prices = {day: close for day, close in zip(dates, closes)
              if counts[day] == 1 and _finite(close) and close > 0}

    def complete(day: date) -> bool:
        session = calendar.session(day)
        return (session.kind.value == "open" and session.close_at_utc is not None
                and session.close_at_utc <= now and day.isoformat() in prices)

    prior = _sessions(calendar, reaction_day, _DRIFT_WINDOW + 1, -1)
    following = _sessions(calendar, reaction_day, _DRIFT_WINDOW, 1)
    if not prior or not complete(reaction_day) or not complete(prior[0]):
        return None

    def change(start: date, end: date) -> float | None:
        value = (prices[end.isoformat()] / prices[start.isoformat()] - 1) * 100
        return round(value, 2) if math.isfinite(value) else None

    pre_complete = len(prior) == 6 and all(complete(day) for day in prior)
    post_complete = len(following) == 5 and all(complete(day) for day in following)
    move = change(prior[0], reaction_day)
    if move is None:
        return None
    return {
        "earnings_day_move_pct": move,
        "pre_drift_5d_pct": change(prior[-1], prior[0]) if pre_complete else None,
        "post_drift_5d_pct": change(reaction_day, following[-1]) if post_complete else None,
        "window_gaps": {key: "five_session_window_incomplete" for key, complete_window in
                        (("pre", pre_complete), ("post", post_complete)) if not complete_window},
        "price_window": {"baseline_session": prior[0].isoformat(),
                         "pre_start": prior[-1].isoformat() if pre_complete else None,
                         "post_end": following[-1].isoformat() if post_complete else None},
    }


def get_earnings_impact(dal: "DataAccessLayer", ticker: str, quarters: int = 4) -> dict[str, Any]:
    """Describe retained release reactions; missing inputs never trigger a fetch.

    Uses the stored Finnhub release calendar and XNYS sessions for US equities.
    Daily bars are observations, not certified official or split-adjusted closes.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return {"ticker": ticker, "error_code": "invalid_ticker", "error": "A nonempty ticker is required."}
    if isinstance(quarters, bool) or not isinstance(quarters, int) or not 1 <= quarters < _CALENDAR_READ_LIMIT:
        return {"ticker": ticker, "error_code": "invalid_quarters", "error": "quarters must be between 1 and 999"}
    now = datetime.now(timezone.utc)
    try:
        events = MacroCalendarLocalStore(read_only=True).list_earnings_events(
            date_from=date(1900, 1, 1), date_to=now.date(), symbols=[ticker],
            as_of=now, limit=_CALENDAR_READ_LIMIT)
    except (OSError, sqlite3.Error, EarningsRevisionDateUnavailable):
        return {"ticker": ticker, "error_code": "earnings_calendar_unavailable",
                "error": "A readable release-calendar revision is required; no update was requested."}
    if len(events) == _CALENDAR_READ_LIMIT:
        return {"ticker": ticker, "error_code": "earnings_calendar_read_limit",
                "error": "Calendar result is not complete; refusing to select a truncated history."}
    if not events:
        return {"ticker": ticker, "error_code": "earnings_calendar_empty",
                "error": "No retained release dates; the fiscal period end is not a substitute."}
    events = list(reversed(events))[:quarters]
    lookback = (now.date() - date.fromisoformat(events[-1]["report_date"])).days + 32
    try:
        prices = dal.get_prices(ticker, interval="1d", days=lookback)
    except Exception:
        return {"ticker": ticker, "error_code": "earnings_prices_unavailable", "error": "Stored daily prices could not be read."}
    dates = [bar.datetime[:10] for bar in prices.bars]
    closes = [bar.close for bar in prices.bars]
    calendar = XnysCalendarAdapter()
    historical_moves, gaps = [], []
    for event in events:
        evidence = {"earnings_id": event["earnings_id"], "release_date": event["report_date"],
                    "fiscal_year": event["year"], "fiscal_quarter": event["quarter"],
                    "release_hour": event["hour"], "observed_at": event["as_of_observed_at"],
                    "calendar_source": "finnhub", "release_time_precision": "day_and_session_bucket"}

        def gap(code: str) -> None:
            gaps.append({**evidence, "code": code})

        if not (_finite(event["eps_actual"]) or _finite(event["revenue_actual"])):
            gap("actual_release_unconfirmed")
            continue
        if event["hour"] not in {"bmo", "amc", "dmh"}:
            gap("release_timing_unknown")
            continue
        day = date.fromisoformat(event["report_date"])
        session = calendar.session(day)
        if session.kind.value != "open":
            gap("release_session_not_open" if session.kind.value == "closed" else "exchange_calendar_unavailable")
            continue
        if event["hour"] == "amc":
            next_days = _sessions(calendar, day, 1, 1)
            if not next_days:
                gap("exchange_calendar_unavailable")
                continue
            day = next_days[0]
        if calendar.session(day).close_at_utc > now:
            gap("reaction_session_incomplete")
            continue
        idx = dates.index(day.isoformat()) if day.isoformat() in dates else -1
        moves = _compute_move(closes, dates, idx, calendar=calendar, now=now)
        if moves is None:
            gap("reaction_session_price_missing")
            continue
        actual, estimate = event["eps_actual"], event["eps_estimate"]
        surprise, beat_miss = None, None
        if _finite(actual) and _finite(estimate):
            delta = actual - estimate
            if math.isfinite(delta):
                beat_miss = "beat" if delta > 0 else "miss" if delta < 0 else "meet"
                if estimate != 0:
                    value = delta / abs(estimate) * 100
                    surprise = round(value, 2) if math.isfinite(value) else None
        historical_moves.append({**evidence, "reaction_session": day.isoformat(),
            "actual_eps": actual, "estimate_eps": estimate, "surprise_pct": surprise,
            "beat_miss": beat_miss, **moves})

    def mean(values: list[float]) -> float | None:
        return round(sum(value / len(values) for value in values), 2) if values else None

    moves = [item["earnings_day_move_pct"] for item in historical_moves]
    pre = [item["pre_drift_5d_pct"] for item in historical_moves if item["pre_drift_5d_pct"] is not None]
    post = [item["post_drift_5d_pct"] for item in historical_moves if item["post_drift_5d_pct"] is not None]
    up = sum(move > 0 for move in moves)
    beats = [item for item in historical_moves if item["beat_miss"] == "beat"]
    misses = [item for item in historical_moves if item["beat_miss"] == "miss"]
    return {
        "ticker": ticker, "quarters_analyzed": len(moves), "quarters_requested": quarters,
        "historical_moves": historical_moves, "event_gaps": gaps, "as_of": now.isoformat(),
        "status": "partial" if gaps or len(events) < quarters or any(item["window_gaps"] for item in historical_moves) else "complete",
        "summary": {"sample_size": len(moves), "avg_absolute_move_pct": mean([abs(move) for move in moves]),
            "max_move_pct": max(moves) if moves else None, "min_move_pct": min(moves) if moves else None,
            "up_count": up, "down_count": sum(move < 0 for move in moves),
            "up_ratio": round(up / len(moves), 2) if moves else None,
            "avg_pre_drift_5d_pct": mean(pre), "pre_sample_size": len(pre),
            "avg_post_drift_5d_pct": mean(post), "post_sample_size": len(post)},
        "surprise_analysis": {"beats": len(beats), "misses": len(misses),
            "meets": sum(item["beat_miss"] == "meet" for item in historical_moves),
            "beat_up_ratio": mean([float(item["earnings_day_move_pct"] > 0) for item in beats]),
            "miss_down_ratio": mean([float(item["earnings_day_move_pct"] < 0) for item in misses])},
        "methodology": {"calendar": "XNYS", "scope": "US_equity_sessions", "window_unit": "trading_sessions",
            "reaction": "previous_session_close_to_reaction_session_close", "price_source": "local_daily_bars",
            "refresh_requested": False},
        "limitations": ["descriptive_not_a_forecast_or_causal_attribution", "release_timestamp_unverified",
            "calendar_history_may_be_incomplete", "daily_close_coverage_and_adjustment_basis_unverified",
            "during_market_release_window_includes_pre_release_trading"],
    }
