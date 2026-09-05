from datetime import date, datetime, timezone

from tests.test_trading_day_coverage import _Calendar, _Fixtures, _session, _slots, _create_market_db
from src.market_coverage.service import TradingDayCoverageService


def test_late_local_history_stays_in_denominator_but_is_not_a_contract_failure(tmp_path):
    path = tmp_path / "market.db"
    first, second = date(2026, 9, 2), date(2026, 9, 3)
    a, b = _session(first), _session(second)
    _create_market_db(path, rows=tuple([("LIVE", at) for at in (*_slots(a), *_slots(b))] + [("FORMER", at) for at in _slots(b)]))
    service = TradingDayCoverageService(db_path=path, calendar_adapter=_Calendar({first: a, second: b}), fixtures=_Fixtures(), clock=lambda: datetime(2026, 9, 3, 23, tzinfo=timezone.utc))
    result = service.get_coverage(universe=["LIVE", "FORMER"], lookback_days=1, interval="15min").model_dump(mode="json")
    assert result["universe_count"] == 2
    assert result["scope_basis"] == "current_universe_retrospective"
    assert result["days"][1]["unknown_ticker_count"] == 1
    assert result["days"][1]["complete_ticker_count"] == 1
    assert result["history_gaps"] == [{
        "ticker": "FORMER", "reason": "before_first_local_bar", "first_local_bar_at": _slots(b)[0].isoformat(),
        "missing_dates": ["2026-09-02"], "partial_dates": [], "provider_issue_reason": None,
    }]


def test_partial_data_and_contract_failure_remain_distinct_from_history_start(tmp_path):
    path = tmp_path / "market.db"
    day = date(2026, 9, 3)
    prior = date(2026, 9, 2)
    session = _session(day)
    _create_market_db(path, rows=tuple(("PART", at) for at in _slots(session)[:2]),
                  provider_issues=(("MISSING", "15min", "security_definition_unavailable", "2026-09-03T22:00:00Z"),))
    service = TradingDayCoverageService(db_path=path, calendar_adapter=_Calendar({day: session, prior: _session(prior)}), fixtures=_Fixtures(), clock=lambda: datetime(2026, 9, 3, 23, tzinfo=timezone.utc))
    result = service.get_coverage(universe=["PART", "MISSING"], lookback_days=1, interval="15min")
    by_ticker = {item.ticker: item for item in result.history_gaps}
    assert by_ticker["PART"].partial_dates == ["2026-09-03"]
    assert by_ticker["PART"].provider_issue_reason is None
    assert by_ticker["MISSING"].provider_issue_reason.value == "security_definition_unavailable"
    assert by_ticker["MISSING"].reason == "no_local_history"
