"""Read-only price-backfill PLANNER (scheduler-hardening v1.1) — gap → bounded scope.

Pure, deterministic, side-effect-free: takes the output of
``market_data_direct.summarize_trading_day_coverage`` and decides WHAT a bounded backfill run
should fetch — a set of tickers + a window depth (``lookback_days``) — NOT a per-day list. This
matches the executor contract: ``backfill_prices_direct`` is window top-up (``tickers_arg`` +
``lookback_days`` → ``INSERT OR IGNORE`` over the contiguous complete-day window), and we keep
that idempotent heal path rather than adding a per-day fetch entry point.

A "gap" for a ticker = a day that is a COMPLETE trading day (``is_trading_day`` AND
``session_complete``) on which the ticker has zero local bars (it appears in that day's
``missing_tickers``). In-progress / non-trading days are NOT gaps. Known-unresolvable tickers
(e.g. an IBKR contract that won't resolve — ``LC``) are excluded via ``exclude_tickers`` so the
planner never schedules a doomed re-fetch. Partial/thin days are intentionally out of scope for
v1.1 (the unambiguous signal is zero-bar-on-a-complete-day; thin can be genuine provider limit).

No DB, no scheduler, no IBKR, no clock — ``today`` is passed in (deterministic). v1.3 wires this
into the scheduler; v1.4 surfaces it in Settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class BackfillPlan:
    tickers: List[str]                    # bounded set to fetch this run (≤ max_tickers)
    lookback_days: int                    # window depth: reaches the oldest SELECTED gap (≤ max_days)
    excluded: List[Dict[str, str]] = field(default_factory=list)   # [{ticker, reason}] — had gaps but skipped
    deferred: List[str] = field(default_factory=list)              # candidates beyond max_tickers (→ continuation)
    candidate_count: int = 0              # total tickers with ≥1 fillable gap (pre-budget)
    gap_days_by_ticker: Dict[str, int] = field(default_factory=dict)  # selected ticker → #missing complete days


def plan_price_backfill(
    coverage: Dict[str, Any],
    *,
    today: str,
    max_tickers: int = 30,
    max_days: int = 30,
    exclude_tickers: Optional[Dict[str, str]] = None,
) -> BackfillPlan:
    """Plan a bounded backfill from a coverage summary. ``today`` is the ISO reference date
    (``lookback_days`` is measured back from it). ``exclude_tickers`` maps a known-unresolvable
    ticker → reason (recorded in ``excluded``, never scheduled). Read-only; does not mutate
    ``coverage``."""
    exclude = dict(exclude_tickers or {})
    today_d = date.fromisoformat(today)

    # 1. invert complete-trading-day → missing_tickers into per-ticker gap dates.
    gaps: Dict[str, List[date]] = {}
    for day in coverage.get("days", []):
        if not (day.get("is_trading_day") and day.get("session_complete")):
            continue  # in-progress / non-trading days are not gaps
        d = date.fromisoformat(day["date"])
        for t in day.get("missing_tickers", []):
            gaps.setdefault(t, []).append(d)

    # 2. split into excluded (had gaps but unresolvable) vs candidates.
    excluded = [{"ticker": t, "reason": exclude[t]} for t in sorted(gaps) if t in exclude]
    candidates = {t: ds for t, ds in gaps.items() if t not in exclude}

    # 3. deterministic priority: most missing days first, then alphabetical.
    ranked = sorted(candidates, key=lambda t: (-len(candidates[t]), t))
    selected = ranked[:max(0, max_tickers)]
    deferred = ranked[max(0, max_tickers):]

    # 4. window depth: reach the oldest gap among SELECTED tickers, capped at max_days.
    lookback_days = 0
    if selected:
        oldest = min(d for t in selected for d in candidates[t])
        lookback_days = max(0, min(max_days, (today_d - oldest).days))

    return BackfillPlan(
        tickers=selected,
        lookback_days=lookback_days,
        excluded=excluded,
        deferred=deferred,
        candidate_count=len(candidates),
        gap_days_by_ticker={t: len(candidates[t]) for t in selected},
    )
