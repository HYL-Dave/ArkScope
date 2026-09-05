from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.market_coverage.models import CoverageHistoryGapV2, ProviderSyncIssueReason


def coverage(*, tickers=("NEW",), reason=None):
    return SimpleNamespace(
        generated_at_et="2026-09-05T09:00:00-04:00", interval="15min", lookback_days=15,
        observation_health=SimpleNamespace(status="ok"),
        calendar_health=SimpleNamespace(status="ok"), days=[],
        history_gaps=[CoverageHistoryGapV2(ticker=ticker, reason="no_local_history", first_local_bar_at=None,
                         missing_dates=["2026-08-24"], partial_dates=["2026-08-25"], provider_issue_reason=reason) for ticker in tickers],
    )


def test_repair_plan_is_bound_to_exact_tickers_window_and_current_gaps():
    from src.market_coverage.repair import preview_price_repair, validate_price_repair
    plan = preview_price_repair(coverage())
    assert plan["tickers"] == ["NEW"]
    assert plan["lookback_days"] == 15
    assert plan["provider"] == "ibkr"
    assert plan["fallback_allowed"] is False
    validate_price_repair(coverage(), plan["preview_sha256"])
    with pytest.raises(ValueError, match="price_repair_preview_changed"):
        validate_price_repair(coverage(tickers=("OTHER",)), plan["preview_sha256"])


def test_repair_plan_excludes_unresolved_security_definitions_and_unavailable_reads():
    from src.market_coverage.repair import preview_price_repair
    plan = preview_price_repair(coverage(reason=ProviderSyncIssueReason.SECURITY_DEFINITION_UNAVAILABLE))
    assert plan["tickers"] == []
    assert plan["blocked_tickers"] == ["NEW"]
    unavailable = coverage()
    unavailable.observation_health.status = "unavailable"
    with pytest.raises(ValueError, match="price_coverage_unavailable"):
        preview_price_repair(unavailable)


@pytest.mark.parametrize("status,reason", (("unavailable", None), ("degraded", "date_unreviewed"), ("ok", "calendar_unavailable")))
def test_unverified_calendar_cannot_claim_no_repair_needed(status, reason):
    from src.market_coverage.repair import preview_price_repair
    value = coverage(tickers=())
    value.calendar_health.status = status
    value.days = [SimpleNamespace(status_reason_code=reason)]
    with pytest.raises(ValueError, match="price_coverage_unavailable"):
        preview_price_repair(value)


def test_low_future_calendar_horizon_does_not_block_reviewed_historical_repair():
    from src.market_coverage.repair import preview_price_repair
    value = coverage()
    value.calendar_health.status = "degraded"
    assert preview_price_repair(value)["tickers"] == ["NEW"]
