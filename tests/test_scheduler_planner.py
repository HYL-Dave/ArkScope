"""Scheduler-hardening v1.1 — read-only price-backfill PLANNER (pure; no DB/scheduler/IBKR).

Consumes summarize_trading_day_coverage output → a bounded BackfillPlan (tickers + window depth),
excluding non-trading/in-progress days and known-unresolvable tickers, capped by budget. Pure
function → hermetic. The executor (backfill_prices_direct) stays window top-up; the planner only
decides scope.
"""

from __future__ import annotations

from src.scheduler_planner import BackfillPlan, plan_price_backfill


def _day(date, *, trading=True, complete=True, status="complete_like", missing=None):
    return {"date": date, "is_trading_day": trading, "session_complete": complete if trading else None,
            "coverage_status": status, "missing_tickers": missing or [],
            "partial_tickers": [], "missing": len(missing or [])}


def _coverage(days):
    return {"interval": "15min", "universe_count": 5, "days": days, "provider_errors": []}


def test_selects_tickers_with_missing_complete_days():
    cov = _coverage([
        _day("2026-06-24", missing=["AAPL"]),
        _day("2026-06-23", missing=["AAPL", "NVDA"]),
        _day("2026-06-22", missing=[]),
    ])
    plan = plan_price_backfill(cov, today="2026-06-24")
    assert isinstance(plan, BackfillPlan)
    assert set(plan.tickers) == {"AAPL", "NVDA"}
    assert plan.candidate_count == 2
    assert plan.gap_days_by_ticker == {"AAPL": 2, "NVDA": 1}   # AAPL missing 6/24+6/23, NVDA 6/23


def test_lookback_reaches_oldest_selected_gap():
    cov = _coverage([
        _day("2026-06-24", missing=[]),
        _day("2026-06-20", missing=["NVDA"]),   # oldest gap 4 days before today
        _day("2026-06-18", missing=[]),
    ])
    plan = plan_price_backfill(cov, today="2026-06-24")
    assert plan.tickers == ["NVDA"]
    assert plan.lookback_days == 4   # 2026-06-24 − 2026-06-20


def test_non_trading_and_in_progress_days_are_not_gaps():
    cov = _coverage([
        _day("2026-06-24", trading=True, complete=False, status="in_progress", missing=["AAPL"]),  # today, open
        _day("2026-06-21", trading=False, status="non_trading", missing=[]),                        # weekend
        _day("2026-06-19", trading=False, status="non_trading", missing=[]),                        # holiday
    ])
    plan = plan_price_backfill(cov, today="2026-06-24")
    assert plan.tickers == [] and plan.candidate_count == 0     # in-progress ≠ gap
    assert plan.lookback_days == 0


def test_excludes_known_unresolvable_tickers():
    cov = _coverage([
        _day("2026-06-23", missing=["AAPL", "LC"]),
        _day("2026-06-22", missing=["LC"]),
    ])
    plan = plan_price_backfill(cov, today="2026-06-24", exclude_tickers={"LC": "contract not found"})
    assert plan.tickers == ["AAPL"]                            # LC excluded from work
    assert plan.excluded == [{"ticker": "LC", "reason": "contract not found"}]
    assert "LC" not in plan.gap_days_by_ticker


def test_max_tickers_caps_and_defers_rest():
    cov = _coverage([_day("2026-06-23", missing=["AAPL", "BRK B", "NVDA", "TSLA"])])
    plan = plan_price_backfill(cov, today="2026-06-24", max_tickers=2)
    assert len(plan.tickers) == 2 and len(plan.deferred) == 2
    assert set(plan.tickers) | set(plan.deferred) == {"AAPL", "BRK B", "NVDA", "TSLA"}
    assert plan.candidate_count == 4


def test_max_days_caps_lookback():
    cov = _coverage([_day("2026-05-01", missing=["NVDA"])])    # ~54 days before today
    plan = plan_price_backfill(cov, today="2026-06-24", max_days=14)
    assert plan.lookback_days == 14                            # capped, not 54


def test_no_gaps_is_empty_plan():
    cov = _coverage([_day("2026-06-24", missing=[]), _day("2026-06-23", missing=[])])
    plan = plan_price_backfill(cov, today="2026-06-24")
    assert plan.tickers == [] and plan.deferred == [] and plan.lookback_days == 0


def test_deterministic_selection_order():
    cov = _coverage([_day("2026-06-23", missing=["TSLA", "AAPL", "NVDA"])])
    p1 = plan_price_backfill(cov, today="2026-06-24", max_tickers=2)
    p2 = plan_price_backfill(cov, today="2026-06-24", max_tickers=2)
    assert p1.tickers == p2.tickers and p1.deferred == p2.deferred   # stable across calls
    # tie-break: most-gaps-first then alphabetical (all tie here → alphabetical)
    assert p1.tickers == ["AAPL", "NVDA"] and p1.deferred == ["TSLA"]


def test_pure_no_side_effects():
    import src.scheduler_planner as mod
    assert not hasattr(mod, "sqlite3") and not hasattr(mod, "psycopg2")
    cov = _coverage([_day("2026-06-23", missing=["AAPL"])])
    snapshot = str(cov)
    plan_price_backfill(cov, today="2026-06-24")
    assert str(cov) == snapshot   # input not mutated
