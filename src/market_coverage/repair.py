"""Explicit bounded price repair; a local coverage read never starts collection."""

from datetime import datetime
import hashlib
import json

from src.market_coverage.models import CalendarHealth, CoverageDayReason, ObservationHealth, ProviderSyncIssueReason


def repair_coverage_available(coverage):
    return (
        coverage.observation_health.status == ObservationHealth.OK
        and coverage.calendar_health.status != CalendarHealth.UNAVAILABLE
        and not any(day.status_reason_code in {
            CoverageDayReason.CALENDAR_UNAVAILABLE, CoverageDayReason.DATE_UNREVIEWED,
            CoverageDayReason.OBSERVATION_UNAVAILABLE,
        } for day in coverage.days)
    )


def preview_price_repair(coverage):
    if not repair_coverage_available(coverage):
        raise ValueError("price_coverage_unavailable")
    blocked, tickers, gaps = [], [], []
    for row in coverage.history_gaps:
        if row.provider_issue_reason == ProviderSyncIssueReason.SECURITY_DEFINITION_UNAVAILABLE:
            blocked.append(row.ticker)
            continue
        tickers.append(row.ticker)
        gaps.append({"ticker": row.ticker, "missing_dates": row.missing_dates, "partial_dates": row.partial_dates})
    payload = {"provider": "ibkr", "fallback_allowed": False, "interval": coverage.interval,
               "lookback_days": coverage.lookback_days, "as_of_date": datetime.fromisoformat(coverage.generated_at_et).date().isoformat(),
               "tickers": sorted(tickers), "blocked_tickers": sorted(blocked), "gaps": sorted(gaps, key=lambda row: row["ticker"])}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**payload, "preview_sha256": digest}


def validate_price_repair(coverage, approved_digest):
    plan = preview_price_repair(coverage)
    if plan["preview_sha256"] != approved_digest:
        raise ValueError("price_repair_preview_changed")
    return plan
