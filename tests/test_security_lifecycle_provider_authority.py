from dataclasses import replace
from datetime import date
import hashlib
import json

import pytest

from src.security_lifecycle_listing_evidence import ListingRecord, _evidence


NOW = "2026-09-05T01:00:00Z"
FIGI = "BBG001YKDND6"


def record(adapter, state, *, ticker="OLD", market="stocks", directory=None, expected=True, figi=None, ended=None):
    return ListingRecord(
        authority={"massive_reference": "massive", "nasdaq_symbol_directory": "nasdaq_trader", "eodhd_symbol_directory": "eodhd"}[adapter],
        adapter=adapter, directory=directory, ticker=ticker, listing_status=state,
        expected_active=expected, market=market, primary_exchange=None, security_type=None,
        issuer_cik=None, composite_figi=figi, delisted_utc=ended, source_as_of="2026-09-04",
        provider_last_updated_utc=None, snapshot_complete=True,
        source_url="https://example.com/status", source_document_sha256="a" * 64, retrieved_at=NOW,
    )


def terminal_records():
    return (
        record("massive_reference", "inactive", expected=False, figi=FIGI, ended="2025-01-15"),
        record("massive_reference", "not_found"),
        record("massive_reference", "not_found", market="otc"),
        record("eodhd_symbol_directory", "inactive", expected=False),
        record("nasdaq_symbol_directory", "not_found", directory="nasdaq_listed"),
        record("nasdaq_symbol_directory", "not_found", directory="other_listed"),
    )


def events(rows=()):
    from src.security_lifecycle_provider_authority import ticker_event_evidence
    from data_sources.lifecycle_provider_census_transport import MassiveTickerEventsResult

    return ticker_event_evidence("OLD", MassiveTickerEventsResult(FIGI, rows, "https://api.massive.com/vX/reference/tickers/BBG001YKDND6/events", "b" * 64, 100, latest_ticker=rows[-1][1] if rows else "OLD"), at=NOW)


def classify(records=None, event_rows=()):
    from src.security_lifecycle_provider_authority import classify_provider_listing

    return classify_provider_listing(ticker="OLD", evidence=tuple(_evidence(row) for row in (records or terminal_records())) + (events(event_rows),), today=date(2026, 9, 5))


def test_terminal_requires_positive_delisting_and_all_independent_veto_checks():
    result = classify()
    assert result.state == "terminal"
    assert result.effective_date == "2025-01-15"
    assert result.successor_ticker is None


@pytest.mark.parametrize("missing", range(6))
def test_omitting_any_terminal_component_never_means_delisted(missing):
    rows = terminal_records()
    assert classify(rows[:missing] + rows[missing + 1:]).state == "unresolved"


def test_otc_continuation_vetoes_terminal_even_when_three_sources_report_delisted():
    rows = list(terminal_records())
    rows[2] = replace(rows[2], listing_status="active", composite_figi=FIGI)
    assert classify(tuple(rows)).state == "unresolved"
    assert "active_listing_present" in classify(tuple(rows)).reasons


def test_active_control_and_unknown_are_not_both_called_delisted():
    rows = (record("massive_reference", "active", figi=FIGI), record("eodhd_symbol_directory", "active"), record("nasdaq_symbol_directory", "active", directory="nasdaq_listed"))
    assert classify(rows).state == "active"
    missing = tuple(replace(row, snapshot_complete=False) for row in terminal_records())
    assert classify(missing).state == "unresolved"


def test_same_figi_ticker_event_prevents_terminal_and_requires_active_successor():
    timeline = (("OLD", "NEW", "2026-06-22"),)
    assert classify(event_rows=timeline).state == "unresolved"
    rows = (*terminal_records(), record("massive_reference", "active", ticker="NEW", figi=FIGI))
    result = classify(rows, timeline)
    assert result.state == "continuation"
    assert result.successor_ticker == "NEW"
    bad = (*terminal_records(), record("massive_reference", "active", ticker="NEW", figi="BBG00HC114X0"))
    assert classify(bad, timeline).state == "unresolved"


def test_unavailable_event_check_is_not_evidence_of_no_successor():
    from src.security_lifecycle_provider_authority import classify_provider_listing

    result = classify_provider_listing(ticker="OLD", evidence=tuple(_evidence(row) for row in terminal_records()), today=date(2026, 9, 5))
    assert result.state == "unresolved"
    assert "successor_check_unavailable" in result.reasons


@pytest.mark.parametrize("field,value", [
    ("composite_figi", "BBG00HC114X0"),
    ("expected_active_state", True),
    ("snapshot_complete", False),
])
def test_listing_identity_and_query_assertions_must_be_bound_to_the_evidence(field, value):
    from src.security_lifecycle_provider_authority import evidence_dict, validate_provider_material

    material = evidence_dict(_evidence(terminal_records()[0]))
    validate_provider_material(material)
    material["source_locator"][field] = value
    with pytest.raises(ValueError, match="provider_evidence_binding"):
        validate_provider_material(material)


def test_largest_admitted_ticker_timeline_fits_real_kernel_evidence_contract():
    from datetime import timedelta
    from data_sources.lifecycle_provider_census_transport import CensusRequestBudget, LifecycleProviderCensusTransport, MAX_MASSIVE_EVENT_ENTRIES
    from src.security_lifecycle_fact_kernel import _normalize_evidence
    from src.security_lifecycle_provider_authority import ticker_event_evidence
    from tests.test_lifecycle_provider_census_transport import FakeSession, json_response

    tickers = [f"T{index:015d}" for index in range(MAX_MASSIVE_EVENT_ENTRIES)]
    timeline = [{"type": "ticker_change", "date": (date(2025, 1, 1) + timedelta(days=index)).isoformat(),
                 "ticker_change": {"ticker": ticker}} for index, ticker in enumerate(tickers)]
    session = FakeSession([json_response({"status": "OK", "results": {"events": timeline}})])
    result = LifecycleProviderCensusTransport(session=session).fetch_massive_ticker_events(
        stable_id=FIGI, api_key="test-key", budget=CensusRequestBudget(),
    )
    evidence = ticker_event_evidence(tickers[0], result, at=NOW)
    normalized = _normalize_evidence((evidence,))[0]
    assert len(json.loads(normalized.source_locator_json)["events"]) == MAX_MASSIVE_EVENT_ENTRIES - 1
    assert len(normalized.source_locator_json.encode()) <= 4096
    assert len(normalized.excerpt.encode()) <= 16000
    assert len(session.calls) == 1


def test_provider_policy_requests_terminal_only_after_open_position_and_preview_guards():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision

    evidence = tuple(_evidence(row) for row in terminal_records()) + (events(),)
    called = []
    def preview(request):
        called.append(request)
        return {"eligible": True, "block_reasons": [], "transition_kind": request["transition_kind"]}
    decision = evaluate_automation_decision(case={"source": "listing_authority", "ticker": "OLD"}, evidence=evidence, facts=(), current_date="2026-09-05", active_sources=("sa_alpha_picks_former",), transition_preview=preview)
    assert decision.transition_requested is True
    assert decision.outcomes == ("listing_ended",)
    assert called[0]["successor_ticker"] is None
    called.clear()
    blocked = evaluate_automation_decision(case={"source": "listing_authority", "ticker": "OLD"}, evidence=evidence, facts=(), current_date="2026-09-05", active_sources=("portfolio_open",), transition_preview=preview)
    assert blocked.transition_requested is False
    assert "portfolio_position_open" in blocked.decision_issues
    assert called == []
