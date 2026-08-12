from __future__ import annotations

import sqlite3


def test_sec_cik_lookup_loads_the_official_ticker_map_once(monkeypatch):
    from data_sources.sec_edgar_source import SECEdgarDataSource

    source = SECEdgarDataSource(user_agent="ArkScope test@example.com")
    source._cik_cache = {}
    calls = []
    monkeypatch.setattr(
        source,
        "_make_request",
        lambda url: calls.append(url) or {
            "0": {"cik_str": 712515, "ticker": "EA", "title": "Electronic Arts Inc."},
            "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        },
    )
    try:
        assert source.get_cik("ea") == "0000712515"
        assert source.get_cik("AAPL") == "0000320193"
        assert source.get_cik("MISSING") is None
        assert calls == ["https://www.sec.gov/files/company_tickers.json"]
    finally:
        source.close()


def _recent_payload(*, forms, dates, accessions, documents, descriptions, items):
    return {
        "name": "Electronic Arts Inc.",
        "tickers": ["EA"],
        "exchanges": ["Nasdaq"],
        "filings": {
            "recent": {
                "form": forms,
                "filingDate": dates,
                "accessionNumber": accessions,
                "primaryDocument": documents,
                "primaryDocDescription": descriptions,
                "items": items,
            }
        },
    }


def test_sec_metadata_emits_review_events_without_calling_them_confirmed():
    from src.collectors.sec_corporate_actions import parse_submission_events

    payload = _recent_payload(
        forms=["8-K", "25-NSE"],
        dates=["2026-08-04", "2026-08-05"],
        accessions=["0000712515-26-000042", "0001354457-26-000999"],
        documents=["ea-20260804.htm", "ea-form25.htm"],
        descriptions=["Current report", "Notification of removal from listing"],
        items=["2.01,3.01", ""],
    )
    documents = {
        "https://www.sec.gov/Archives/edgar/data/712515/000071251526000042/ea-20260804.htm": (
            "<html><body>Item 2.01. The Company became a wholly owned subsidiary "
            "of Oak-Eagle, LLC in connection with the completion of the Merger. "
            "Item 3.01. Nasdaq will file Form 25.</body></html>"
        )
    }

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=payload,
        document_loader=documents.get,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert [(event.event_type, event.lifecycle_state) for event in batch.events] == [
        ("listing_removal_notice", "pending_delisting"),
        ("listing_status_review", "review_required"),
        ("acquisition_completed", "review_required"),
    ]
    assert all(event.lifecycle_state != "inactive_confirmed" for event in batch.events)
    assert batch.relationships[0].target_ticker == "EA"
    assert batch.relationships[0].target_name == "Electronic Arts Inc."
    assert batch.relationships[0].acquirer_name == "Oak-Eagle, LLC"
    assert batch.relationships[0].status == "candidate"
    assert "wholly owned subsidiary" in batch.relationships[0].evidence_excerpt


def test_ambiguous_item_201_does_not_invent_a_counterparty():
    from src.collectors.sec_corporate_actions import parse_submission_events

    payload = _recent_payload(
        forms=["8-K"],
        dates=["2026-08-04"],
        accessions=["0000712515-26-000042"],
        documents=["ea-20260804.htm"],
        descriptions=["Current report"],
        items=["2.01"],
    )

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=payload,
        document_loader=lambda _url: (
            "Item 2.01. The registrant completed a disposition of certain assets."
        ),
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert batch.events == ()
    assert batch.relationships == ()


def test_item_301_alone_is_a_review_signal_not_delisting_proof():
    from src.collectors.sec_corporate_actions import parse_submission_events

    payload = _recent_payload(
        forms=["8-K"],
        dates=["2026-08-04"],
        accessions=["0000712515-26-000043"],
        documents=["ea-20260804.htm"],
        descriptions=["Current report"],
        items=["3.01"],
    )
    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=payload,
        document_loader=lambda _url: (_ for _ in ()).throw(
            AssertionError("3.01 metadata should not need a filing-body request")
        ),
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )
    assert len(batch.events) == 1
    assert batch.events[0].event_type == "listing_status_review"
    assert batch.events[0].lifecycle_state == "review_required"


class _FakeSEC:
    def __init__(self):
        self.documents = []

    def get_cik(self, ticker):
        return {"EA": "0000712515", "MISSING": None}[ticker]

    def fetch_submissions(self, cik):
        assert cik == "0000712515"
        return _recent_payload(
            forms=["8-K"],
            dates=["2026-08-04"],
            accessions=["0000712515-26-000042"],
            documents=["ea-20260804.htm"],
            descriptions=["Current report"],
            items=["2.01,3.01"],
        )

    def fetch_filing_document_text(self, url, max_bytes=0):
        self.documents.append((url, max_bytes))
        return (
            "The Company became a wholly owned subsidiary of Oak-Eagle, LLC "
            "upon completion of the merger."
        )


def test_run_incremental_persists_partial_results_without_touching_profile_state(
    tmp_path,
):
    from src.collectors.sec_corporate_actions import run_incremental
    from src.security_lifecycle import read_security_lifecycle

    db_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    profile_path.write_bytes(b"profile-sentinel")
    progress = []

    result = run_incremental(
        tickers_arg="EA,MISSING",
        progress_cb=lambda done, total, current: progress.append(
            (done, total, current)
        ),
        client=_FakeSEC(),
        db_path=str(db_path),
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert result == {
        "status": "partial",
        "tickers_scanned": 2,
        "events_observed": 2,
        "relationships_observed": 1,
        "review_required": 2,
        "errors": {"MISSING": "cik_unavailable"},
    }
    assert progress == [(1, 2, "EA"), (2, 2, "MISSING")]
    assert profile_path.read_bytes() == b"profile-sentinel"
    snapshot = read_security_lifecycle(str(db_path))
    assert len(snapshot["events"]) == 2
    assert len(snapshot["relationships"]) == 1


def test_scheduler_registers_sec_source_and_preserves_adapter_partial(monkeypatch, tmp_path):
    import src.collectors.sec_corporate_actions as collector
    import src.service.data_scheduler as scheduler

    assert scheduler.SOURCES["sec_corporate_actions"].adapter == (
        "src.collectors.sec_corporate_actions",
        "run_incremental",
    )
    assert scheduler.SOURCES["sec_corporate_actions"].default_interval_min == 1440
    assert scheduler.SOURCES["sec_corporate_actions"].universe_tickers is True
    monkeypatch.setattr(scheduler, "_resolve_price_scope", lambda: ["EA"])
    monkeypatch.setattr(
        collector,
        "run_incremental",
        lambda **_kwargs: {
            "status": "partial",
            "tickers_scanned": 1,
            "events_observed": 0,
            "relationships_observed": 0,
            "review_required": 0,
            "errors": {"EA": "submissions_unavailable"},
        },
    )

    result = scheduler.run_source("sec_corporate_actions", trigger_source="api")
    assert result["status"] == "partial"
    assert result["collect"]["errors"] == {"EA": "submissions_unavailable"}
