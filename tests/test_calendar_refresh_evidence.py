"""Calendar evidence, not insertion count, determines acquisition outcomes."""

from datetime import date, datetime, timezone
import json
import sqlite3
from unittest.mock import Mock

import pytest
import requests

from data_sources.finnhub_calendar_client import FinnhubCalendarClient, FinnhubError
from src.macro_calendar import finnhub_ingestion as ingestion
from src.macro_calendar.execution import normalize_macro_collection_result
from src.macro_calendar.local_store import MacroCalendarLocalStore


START = date(2026, 10, 1)
END = date(2026, 10, 31)
BEFORE = datetime(2026, 9, 20, tzinfo=timezone.utc)
AFTER = datetime(2026, 9, 21, tzinfo=timezone.utc)
ROW = {"symbol": "AAPL", "date": "2026-10-29", "year": 2026, "quarter": 4}
ENDPOINTS = (
    ("economic", "economicCalendar"),
    ("earnings", "earningsCalendar"),
    ("ipo", "ipoCalendar"),
)


def client_for(body):
    client = FinnhubCalendarClient(api_key="offline-only", inter_call_delay_s=0)
    client._get = Mock(return_value=body)
    return client


@pytest.mark.parametrize("endpoint,envelope", ENDPOINTS)
@pytest.mark.parametrize("body", [None, [], {}, {"error": "synthetic-secret"}])
def test_missing_or_error_envelope_is_not_an_empty_calendar(endpoint, envelope, body):
    with pytest.raises(FinnhubError, match="finnhub_calendar_response_invalid") as failure:
        getattr(client_for(body), f"get_{endpoint}_events")(START, END)
    assert "synthetic-secret" not in str(failure.value)


@pytest.mark.parametrize("endpoint,envelope", ENDPOINTS)
@pytest.mark.parametrize("rows", [None, {}, "", 0])
def test_non_array_envelope_is_rejected(endpoint, envelope, rows):
    with pytest.raises(FinnhubError, match="finnhub_calendar_response_invalid"):
        getattr(client_for({envelope: rows}), f"get_{endpoint}_events")(START, END)


@pytest.mark.parametrize("endpoint,envelope", ENDPOINTS)
def test_valid_empty_response_has_observed_zero_rows(endpoint, envelope):
    result = getattr(client_for({envelope: []}), f"get_{endpoint}_events")(START, END)
    assert result.events == ()
    assert result.rows_received == result.rows_rejected == 0


@pytest.mark.parametrize("bad", [{}, {"symbol": "AAPL", "date": "2026-10-29"}, None, 4])
def test_bad_rows_do_not_hide_valid_rows_or_claim_complete_response(bad):
    result = client_for({"earningsCalendar": [ROW, bad]}).get_earnings_events(START, END)
    assert len(result.events) == 1
    assert result.events[0].symbol == "AAPL"
    assert result.rows_received == 2
    assert result.rows_rejected == 1


@pytest.mark.parametrize("field,value", [("quarter", True), ("quarter", 1.5), ("year", True), ("year", 2026.5)])
def test_period_identity_is_not_silently_coerced(field, value):
    result = client_for({"earningsCalendar": [{**ROW, field: value}]}).get_earnings_events(START, END)
    assert result.events == ()
    assert result.rows_received == result.rows_rejected == 1


@pytest.mark.parametrize("rows,expected_status,inserted,rejected,response_state", [
    ([], "succeeded", 0, 0, "empty"),
    ([ROW], "succeeded", 1, 0, "data"),
    ([ROW, {}], "partial", 1, 1, "partial"),
    ([{}], "failed", 0, 1, "rejected"),
])
def test_real_client_store_and_job_receipt(tmp_path, monkeypatch, rows, expected_status, inserted, rejected, response_state):
    store = MacroCalendarLocalStore(tmp_path / "calendar.db")
    monkeypatch.setattr(ingestion, "get_macro_calendar_store", lambda dal: store)
    raw = ingestion.fetch_finnhub_earnings_events(
        object(), date_from=START, date_to=END, symbols=["aapl"],
        client=client_for({"earningsCalendar": rows}),
    ).to_dict()
    result = normalize_macro_collection_result("fetch_earnings_calendar", raw)
    assert result["status"] == expected_status
    assert result["events_inserted"] == inserted
    assert result["events_skipped"] == rejected
    receipt, = result["requests"]
    assert receipt["dataset"] == "earnings"
    assert receipt["symbol"] == "AAPL"
    assert receipt["from_date"] == START.isoformat()
    assert receipt["to_date"] == END.isoformat()
    assert receipt["response_state"] == response_state
    assert receipt["rows_received"] == len(rows)
    assert receipt["rows_accepted"] == inserted
    assert receipt["rows_rejected"] == rejected
    assert datetime.fromisoformat(receipt["checked_at"]).tzinfo is not None
    assert len(store.list_earnings_events(date_from=START, date_to=END)) == inserted


def test_refusal_receipt_does_not_pretend_observed_empty_or_store_provider_text(tmp_path, monkeypatch):
    store = MacroCalendarLocalStore(tmp_path / "calendar.db")
    monkeypatch.setattr(ingestion, "get_macro_calendar_store", lambda dal: store)
    raw = ingestion.fetch_finnhub_earnings_events(
        object(), date_from=START, date_to=END, symbols=["AAPL"],
        client=client_for({"error": "synthetic-secret"}),
    ).to_dict()
    result = normalize_macro_collection_result("fetch_earnings_calendar", raw)
    assert result["status"] == "failed"
    receipt, = result["requests"]
    assert receipt["response_state"] == "failed"
    assert receipt["rows_received"] is None
    assert receipt["error_code"] == "finnhub_calendar_response_invalid"
    assert "synthetic-secret" not in json.dumps(result)


@pytest.mark.parametrize("failure,code", [
    (401, "finnhub_unauthorized"), (403, "finnhub_forbidden"),
    (429, "finnhub_rate_limited"), (500, "finnhub_http_failed"),
    ("transport", "finnhub_transport_failed"), ("json", "finnhub_calendar_response_invalid"),
])
def test_provider_failure_codes_survive_without_provider_text(tmp_path, monkeypatch, failure, code):
    store = MacroCalendarLocalStore(tmp_path / "calendar.db")
    monkeypatch.setattr(ingestion, "get_macro_calendar_store", lambda dal: store)
    session = Mock()
    response = session.get.return_value
    response.status_code = failure if isinstance(failure, int) else 200
    response.text = "synthetic-secret"
    if failure == "transport":
        session.get.side_effect = requests.Timeout("synthetic-secret")
    if failure == "json":
        response.json.side_effect = ValueError("synthetic-secret")
    client = FinnhubCalendarClient(api_key="offline-only", session=session, inter_call_delay_s=0)
    raw = ingestion.fetch_finnhub_earnings_events(
        object(), date_from=START, date_to=END, symbols=["AAPL"], client=client,
    ).to_dict()
    result = normalize_macro_collection_result("fetch_earnings_calendar", raw)
    assert result["status"] == "failed"
    assert result["requests"][0]["error_code"] == code
    assert result["requests"][0]["rows_received"] is None
    assert "synthetic-secret" not in json.dumps(result)


def payload(day="2026-10-29"):
    return {"symbol": "AAPL", "report_date": date.fromisoformat(day),
            "year": 2026, "quarter": 4, "hour": "amc", "eps_estimate": 1.5}


def test_rescheduled_date_is_a_revision_and_does_not_rewrite_history(tmp_path):
    store = MacroCalendarLocalStore(tmp_path / "calendar.db")
    eid, action = store.upsert_earnings_event(payload(), source_payload={}, observed_at=BEFORE)
    assert action == "inserted"
    eid2, action = store.upsert_earnings_event(payload("2026-10-30"), source_payload={}, observed_at=AFTER)
    assert (eid2, action) == (eid, "mutated")
    assert store.read_earnings_event_as_of(eid, BEFORE)["report_date"] == "2026-10-29"
    assert store.read_earnings_event_as_of(eid, AFTER)["report_date"] == "2026-10-30"
    assert store.list_earnings_events(date_from=START, date_to=END)[0]["report_date"] == "2026-10-30"
    for when, included, excluded in [(BEFORE, "2026-10-29", "2026-10-30"), (AFTER, "2026-10-30", "2026-10-29")]:
        rows = store.list_earnings_events(date_from=date.fromisoformat(included), date_to=date.fromisoformat(included), as_of=when)
        assert len(rows) == 1 and rows[0]["report_date"] == included
        assert store.list_earnings_events(date_from=date.fromisoformat(excluded), date_to=date.fromisoformat(excluded), as_of=when) == []


def test_identical_date_objects_and_strings_do_not_generate_extra_revisions(tmp_path):
    db = tmp_path / "calendar.db"
    store = MacroCalendarLocalStore(db)
    store.upsert_earnings_event(payload(), source_payload={}, observed_at=BEFORE)
    assert store.upsert_earnings_event({**payload(), "report_date": "2026-10-29"}, source_payload={}, observed_at=AFTER)[1] == "unchanged"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cal_earnings_event_revisions").fetchone()[0] == 1


def test_conflicting_revision_date_is_rejected_without_mutation(tmp_path):
    store = MacroCalendarLocalStore(tmp_path / "calendar.db")
    with pytest.raises(ValueError, match="earnings_revision_date_mismatch"):
        store.upsert_earnings_event(payload(), source_payload={"date": "2026-10-30"}, observed_at=BEFORE)
    assert store.list_earnings_events(date_from=START, date_to=END) == []


def test_unknown_historical_date_cannot_borrow_the_current_date(tmp_path):
    db = tmp_path / "calendar.db"
    store = MacroCalendarLocalStore(db)
    eid, _ = store.upsert_earnings_event(payload(), source_payload={}, observed_at=BEFORE)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE cal_earnings_event_revisions SET source_payload='{}'")
    with pytest.raises(ValueError, match="earnings_revision_date_unavailable"):
        store.read_earnings_event_as_of(eid, BEFORE)
    with pytest.raises(ValueError, match="earnings_revision_date_unavailable"):
        store.list_earnings_events(date_from=START, date_to=END, as_of=BEFORE)
    assert store.list_earnings_events(date_from=START, date_to=END)[0]["report_date"] == "2026-10-29"


def test_as_of_limit_and_sort_use_observed_dates_before_canonical_reschedule(tmp_path):
    store = MacroCalendarLocalStore(tmp_path / "calendar.db")
    store.upsert_earnings_event(payload("2026-10-20"), source_payload={}, observed_at=BEFORE)
    store.upsert_earnings_event({**payload("2026-10-25"), "symbol": "MSFT"}, source_payload={}, observed_at=BEFORE)
    store.upsert_earnings_event(payload("2026-11-01"), source_payload={}, observed_at=AFTER)
    early = store.list_earnings_events(date_from=START, date_to=END, as_of=BEFORE, limit=1)
    late = store.list_earnings_events(date_from=START, date_to=END, as_of=AFTER, limit=1)
    assert [(row["symbol"], row["report_date"]) for row in early] == [("AAPL", "2026-10-20")]
    assert [(row["symbol"], row["report_date"]) for row in late] == [("MSFT", "2026-10-25")]


def test_repeated_calendar_check_records_request_without_rewriting_data_version(tmp_path, monkeypatch):
    db = tmp_path / "calendar.db"
    store = MacroCalendarLocalStore(db)
    monkeypatch.setattr(ingestion, "get_macro_calendar_store", lambda dal: store)
    client = client_for({"earningsCalendar": [ROW]})
    first = ingestion.fetch_finnhub_earnings_events(object(), date_from=START, date_to=END,
                                                   symbols=["AAPL"], client=client, observed_at=BEFORE)
    second = ingestion.fetch_finnhub_earnings_events(object(), date_from=START, date_to=END,
                                                    symbols=["AAPL"], client=client, observed_at=AFTER)
    assert first.events_inserted == second.events_unchanged == 1
    assert len(first.requests) == len(second.requests) == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cal_earnings_event_revisions").fetchone()[0] == 1
    assert store.read_earnings_event_as_of(1, AFTER)["observed_at"].startswith("2026-09-20")
