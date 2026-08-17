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


# ============================================================
# Form 25 class-of-securities classification
# ============================================================
#
# A Form 25 removes one named class of securities, not the issuer. The excerpts
# below were captured on 2026-08-18 from the real filings that this collector
# already stored, so the parser is exercised against the shapes SEC actually
# serves: the exchange-filed notice rendered through `xslF25X02`, and the
# issuer-filed HTML notice. Both place the class immediately before the
# `(Description of class of securities)` caption.

_EXCHANGE_RENDERED_NOTE_FORM25 = (
    "<html><body>FORM 25 NOTIFICATION OF REMOVAL FROM LISTING AND/OR "
    "REGISTRATION UNDER SECTION 12(b) OF THE SECURITIES EXCHANGE ACT OF 1934. "
    "Commission File Number 001-33977 Issuer: VISA INC. Exchange: NEW YORK "
    "STOCK EXCHANGE LLC (Exact name of Issuer as specified in its charter, and "
    "name of Exchange where security is listed and/or registered) Address: PO "
    "Box 8999 San Francisco CALIFORNIA 94128 Telephone number: (650) 432-3200 "
    "(Address, including zip code, and telephone number, including area code, "
    "of Issuer's principal executive offices) 1.500% Senior Notes due 2026 "
    "(Description of class of securities) Please place an X in the box to "
    "designate the rule provision relied upon to strike the class of "
    "securities from listing and registration:</body></html>"
)

_ISSUER_HTML_COMMON_STOCK_FORM25 = (
    "<html><body>UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, "
    "D.C. 20549 _______________ FORM 25 NOTIFICATION OF REMOVAL FROM LISTING "
    "AND/OR REGISTRATION UNDER SECTION 12(b) OF THE SECURITIES EXCHANGE ACT OF "
    "1934 _______________ Commission File Number 001-41468 D-Wave Quantum Inc. "
    "New York Stock Exchange (Exact name of Issuer as specified in its charter, "
    "and name of Exchange where security is listed and/or registered) "
    "_______________ 2650 East Bayshore Road Palo Alto, California 94303 "
    "(650) 285-2881 (Address, including zip code, and telephone number, "
    "including area code, of Issuer’s principal executive offices) "
    "_______________ Common stock, par value $0.0001 per share "
    "(Description of class of securities) _______________ Please place an X in "
    "the box to designate the rule provision relied upon to strike the class "
    "of securities from listing and registration:</body></html>"
)

_RAW_XML_NOTE_FORM25 = (
    '<?xml version="1.0"?><notificationOfRemoval><schemaVersion>X0203'
    "</schemaVersion><exchange><cik>0000876661</cik><entityName>NEW YORK STOCK "
    "EXCHANGE LLC</entityName></exchange><issuer><cik>0000059478</cik>"
    "<entityName>ELI LILLY &amp; Co</entityName></issuer>"
    "<descriptionClassSecurity>1.625% Notes Due 2026</descriptionClassSecurity>"
    "<ruleProvision>17 CFR 240.12d2-2(a)(2)</ruleProvision>"
    "</notificationOfRemoval>"
)


def _form25_payload(*, document="form25.htm", description=""):
    return _recent_payload(
        forms=["25-NSE"],
        dates=["2026-08-04"],
        accessions=["0000712515-26-000042"],
        documents=[document],
        descriptions=[description],
        items=[""],
    )


_FORM25_URL = (
    "https://www.sec.gov/Archives/edgar/data/712515/000071251526000042/form25.htm"
)


def test_form25_for_a_matured_note_does_not_flag_the_issuer_equity():
    """A bond removal must not mark the issuer's common ticker as delisting."""
    from src.collectors.sec_corporate_actions import parse_submission_events

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=_form25_payload(),
        document_loader={_FORM25_URL: _EXCHANGE_RENDERED_NOTE_FORM25}.get,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert batch.events == ()


def test_form25_for_common_stock_still_flags_pending_delisting():
    """Removing the common stock stays a pending-delisting observation."""
    from src.collectors.sec_corporate_actions import parse_submission_events

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=_form25_payload(),
        document_loader={_FORM25_URL: _ISSUER_HTML_COMMON_STOCK_FORM25}.get,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert [(event.event_type, event.lifecycle_state) for event in batch.events] == [
        ("listing_removal_notice", "pending_delisting")
    ]


def test_form25_records_the_class_of_securities_as_evidence():
    """A flagged row must say which class the notice removes."""
    from src.collectors.sec_corporate_actions import parse_submission_events

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=_form25_payload(),
        document_loader={_FORM25_URL: _ISSUER_HTML_COMMON_STOCK_FORM25}.get,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert (
        batch.events[0].description
        == "SEC notification of removal from listing or registration. Class of "
        "securities: Common stock, par value $0.0001 per share."
    )


def test_form25_class_evidence_survives_a_terse_filing_description():
    """SEC commonly supplies `25` as the document description; the stored rows
    for QBTS and HAPN show exactly that. The class must survive it."""
    from src.collectors.sec_corporate_actions import parse_submission_events

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=_form25_payload(description="25"),
        document_loader={_FORM25_URL: _ISSUER_HTML_COMMON_STOCK_FORM25}.get,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert (
        batch.events[0].description
        == "25 Class of securities: Common stock, par value $0.0001 per share."
    )


def test_form25_with_an_undetermined_class_does_not_claim_one():
    """An unreadable body must not invent a class of securities."""
    from src.collectors.sec_corporate_actions import parse_submission_events

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=_form25_payload(),
        document_loader=lambda _url: None,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert (
        batch.events[0].description
        == "SEC notification of removal from listing or registration."
    )


def test_form25_fetch_failure_does_not_lose_the_rest_of_the_ticker():
    """Reading the Form 25 body is new network work. A failure there must stay
    local to that filing: `run_incremental` catches per ticker, so a raised
    loader would otherwise discard every other event for the same issuer."""
    from src.collectors.sec_corporate_actions import parse_submission_events

    payload = _recent_payload(
        forms=["25-NSE", "8-K"],
        dates=["2026-08-04", "2026-08-03"],
        accessions=["0000712515-26-000042", "0000712515-26-000043"],
        documents=["form25.htm", "ea-20260803.htm"],
        descriptions=["", "Current report"],
        items=["", "3.01"],
    )

    def loader(url):
        raise RuntimeError("sec_request_failed")

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=payload,
        document_loader=loader,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert [(event.event_type, event.lifecycle_state) for event in batch.events] == [
        ("listing_removal_notice", "pending_delisting"),
        ("listing_status_review", "review_required"),
    ]
    assert (
        batch.events[0].description
        == "SEC notification of removal from listing or registration."
    )


def test_form25_with_an_unreadable_document_still_flags_pending_delisting():
    """An unavailable filing body is undetermined, never a silent dismissal."""
    from src.collectors.sec_corporate_actions import parse_submission_events

    batch = parse_submission_events(
        ticker="EA",
        cik="0000712515",
        submissions=_form25_payload(),
        document_loader=lambda _url: None,
        observed_at="2026-08-05T12:00:00Z",
        start_date="2026-08-01",
    )

    assert [(event.event_type, event.lifecycle_state) for event in batch.events] == [
        ("listing_removal_notice", "pending_delisting")
    ]


def test_form25_classifier_reads_the_class_verbatim_from_every_served_shape():
    from src.collectors.sec_corporate_actions import classify_form25_security

    exchange = classify_form25_security(_EXCHANGE_RENDERED_NOTE_FORM25)
    assert exchange.description == "1.500% Senior Notes due 2026"
    assert exchange.covers_other_security is True

    issuer = classify_form25_security(_ISSUER_HTML_COMMON_STOCK_FORM25)
    assert issuer.description == "Common stock, par value $0.0001 per share"
    assert issuer.covers_other_security is False

    raw_xml = classify_form25_security(_RAW_XML_NOTE_FORM25)
    assert raw_xml.description == "1.625% Notes Due 2026"
    assert raw_xml.covers_other_security is True


def test_form25_classifier_is_undetermined_when_the_class_is_absent():
    from src.collectors.sec_corporate_actions import classify_form25_security

    for document in (None, "", "<html><body>FORM 25</body></html>"):
        result = classify_form25_security(document)
        assert result.description == ""
        assert result.covers_other_security is False


def _seed_removal_notice(db_path, *, ticker, source_ref, url):
    from src.security_lifecycle import LifecycleObservation, SecurityLifecycleStore

    conn = sqlite3.connect(str(db_path))
    try:
        SecurityLifecycleStore(conn).upsert_observation(
            LifecycleObservation(
                ticker=ticker,
                cik="0000712515",
                issuer_name=f"{ticker} Inc.",
                event_type="listing_removal_notice",
                lifecycle_state="pending_delisting",
                filing_date="2026-06-15",
                effective_date=None,
                source="sec_edgar",
                source_ref=source_ref,
                filing_form="25-NSE",
                filing_items=(),
                evidence_url=url,
                description="SEC notification of removal from listing or registration.",
                observed_at="2026-06-16T12:00:00Z",
            )
        )
        conn.commit()
    finally:
        conn.close()


def _seeded_removal_db(tmp_path):
    db_path = tmp_path / "market_data.db"
    _seed_removal_notice(
        db_path, ticker="V", source_ref="note-1", url="https://sec.example/v-note"
    )
    _seed_removal_notice(
        db_path, ticker="QBTS", source_ref="equity-1", url="https://sec.example/qbts"
    )
    _seed_removal_notice(
        db_path, ticker="ZZZ", source_ref="gone-1", url="https://sec.example/missing"
    )
    return db_path


_SEEDED_DOCUMENTS = {
    "https://sec.example/v-note": _EXCHANGE_RENDERED_NOTE_FORM25,
    "https://sec.example/qbts": _ISSUER_HTML_COMMON_STOCK_FORM25,
}


def test_reclassify_reports_other_security_rows_without_deleting_by_default(tmp_path):
    from src.collectors.sec_corporate_actions import (
        reclassify_stored_form25_observations,
    )
    from src.security_lifecycle import read_security_lifecycle

    db_path = _seeded_removal_db(tmp_path)

    result = reclassify_stored_form25_observations(
        db_path=str(db_path), document_loader=_SEEDED_DOCUMENTS.get
    )

    assert result["applied"] is False
    assert result["examined"] == 3
    assert result["removed"] == 0
    assert result["undetermined"] == 1
    assert [(row["ticker"], row["security_class"]) for row in result["other_security"]] == [
        ("V", "1.500% Senior Notes due 2026")
    ]
    assert len(read_security_lifecycle(str(db_path))["events"]) == 3


def test_reclassify_deletes_only_the_other_security_rows_when_applied(tmp_path):
    from src.collectors.sec_corporate_actions import (
        reclassify_stored_form25_observations,
    )
    from src.security_lifecycle import read_security_lifecycle

    db_path = _seeded_removal_db(tmp_path)

    result = reclassify_stored_form25_observations(
        db_path=str(db_path), document_loader=_SEEDED_DOCUMENTS.get, apply=True
    )

    assert result["applied"] is True
    assert result["removed"] == 1
    remaining = read_security_lifecycle(str(db_path))["events"]
    assert sorted(row["ticker"] for row in remaining) == ["QBTS", "ZZZ"]


def test_reclassify_survives_a_failing_document_fetch(tmp_path):
    """One unreachable filing must not abort the pass or delete anything extra."""
    from src.collectors.sec_corporate_actions import (
        reclassify_stored_form25_observations,
    )

    db_path = _seeded_removal_db(tmp_path)

    def loader(url):
        if url == "https://sec.example/qbts":
            raise RuntimeError("sec_request_failed")
        return _SEEDED_DOCUMENTS.get(url)

    result = reclassify_stored_form25_observations(
        db_path=str(db_path), document_loader=loader
    )

    assert result["examined"] == 3
    assert result["unreadable"] == 1
    assert result["undetermined"] == 1
    assert [row["ticker"] for row in result["other_security"]] == ["V"]


def test_reclassify_never_touches_other_event_types(tmp_path):
    from src.collectors.sec_corporate_actions import (
        reclassify_stored_form25_observations,
    )
    from src.security_lifecycle import LifecycleObservation, SecurityLifecycleStore
    from src.security_lifecycle import read_security_lifecycle

    db_path = _seeded_removal_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    try:
        SecurityLifecycleStore(conn).upsert_observation(
            LifecycleObservation(
                ticker="V",
                cik="0000712515",
                issuer_name="V Inc.",
                event_type="merger_agreement",
                lifecycle_state="review_required",
                filing_date="2026-06-15",
                effective_date=None,
                source="sec_edgar",
                source_ref="note-1",
                filing_form="8-K",
                filing_items=("1.01",),
                evidence_url="https://sec.example/v-note",
                description="SEC Item 1.01 contains merger or acquisition language.",
                observed_at="2026-06-16T12:00:00Z",
            )
        )
        conn.commit()
    finally:
        conn.close()

    result = reclassify_stored_form25_observations(
        db_path=str(db_path), document_loader=_SEEDED_DOCUMENTS.get, apply=True
    )

    assert result["examined"] == 3
    assert result["removed"] == 1
    remaining = read_security_lifecycle(str(db_path))["events"]
    assert sorted(
        (row["ticker"], row["event_type"]) for row in remaining
    ) == [
        ("QBTS", "listing_removal_notice"),
        ("V", "merger_agreement"),
        ("ZZZ", "listing_removal_notice"),
    ]


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
