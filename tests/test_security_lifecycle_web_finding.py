from dataclasses import replace
from datetime import datetime, timezone
import hashlib

import pytest

from src.lifecycle_public_sources import PublicSourcePage, _capture_digest
from src.security_lifecycle_web_contract import PublicInvestigationInput


def public_input():
    return PublicInvestigationInput(ticker="OLD", issuer_name="Issuer Old Inc", security_class="Class A common stock",
                                    venue="NASDAQ", issuer_cik="0000012345", question="listing_status", as_of="2026-09-06")


def source_page(text, url="https://ir.example.com/notice"):
    digest = hashlib.sha256(text.encode()).hexdigest()
    page = PublicSourcePage(url, (), digest, digest, text, "text/plain", "2026-09-06T01:00:00+00:00")
    return replace(page, capture_sha256=_capture_digest(page))


NOTICE = "Issuer Old Inc Class A common stock (OLD) was delisted from NASDAQ effective September 1, 2026."


def finding_payload(**changes):
    return {
        "source_ticker": "OLD", "issuer_name": "Issuer Old Inc", "security_class": "Class A common stock", "venue": "NASDAQ",
        "event_kind": "listing_ended", "timing": "completed", "successor_ticker": None,
        "effective_date": "2026-09-01", "effective_date_text": "September 1, 2026",
        "summary": "The old NASDAQ listing ended; no claim is made about a replacement.",
        "contradictions": [], "unresolved_conditions": [],
        "citations": [{"source_id": "source-1", "quote": NOTICE,
                       "supports": ["security_identity", "listing_ended", "effective_date"]}],
        **changes,
    }


def test_web_finding_requires_real_source_identity_date_and_citation():
    from src.security_lifecycle_web_finding import validate_finding

    result = validate_finding(public_input(), finding_payload(), {"source-1": source_page(NOTICE)})
    assert result.action == "terminal_delisting" and result.block_reasons == ()
    assert result.passages[0].excerpt == NOTICE
    assert result.passages[0].source_document_sha256 == source_page(NOTICE).body_sha256
    assert result.independent_source_count is None


@pytest.mark.parametrize("url", [
    "https://financial-news.example.com/completed-listing-event",
    "https://ir.example.com/completed-listing-event",
    "https://www.sec.gov/Archives/edgar/data/12345/completed-listing-event.htm",
])
def test_completed_notice_is_reviewable_without_a_required_publisher_or_sec_source(url):
    from src.security_lifecycle_web_finding import validate_finding

    result = validate_finding(public_input(), finding_payload(), {"source-1": source_page(NOTICE, url)})
    assert result.action == "terminal_delisting" and result.block_reasons == ()
    assert result.passages[0].source_url == url


def test_newer_completed_reporting_can_resolve_an_older_sec_announcement():
    from src.security_lifecycle_web_finding import validate_finding

    announcement = "Issuer Old Inc announced on August 20, 2026 that a proposed acquisition remains subject to closing conditions."
    pages = {
        "source-1": source_page(announcement, "https://www.sec.gov/Archives/edgar/data/12345/proposal.htm"),
        "source-2": source_page(NOTICE, "https://financial-news.example.com/completed-event"),
    }
    payload = finding_payload(announcement_date="2026-08-20", announcement_date_text="August 20, 2026",
        citations=[{"source_id": "source-1", "quote": announcement, "supports": ["announcement_date", "acquisition_announced"]},
                   {"source_id": "source-2", "quote": NOTICE, "supports": ["security_identity", "listing_ended", "effective_date"]}])
    result = validate_finding(public_input(), payload, pages)
    assert result.action == "terminal_delisting" and result.block_reasons == ()
    assert result.finding.effective_date != result.finding.announcement_date


def test_filing_date_and_announcement_alone_do_not_supply_completed_listing_evidence():
    from src.security_lifecycle_web_finding import validate_finding

    notice = "Filed September 1, 2026. Issuer Old Inc Class A common stock (OLD) on NASDAQ is subject to a proposed acquisition; trading continues pending closing."
    payload = finding_payload(citations=[{"source_id": "source-1", "quote": notice,
        "supports": ["security_identity", "announcement_date", "acquisition_announced"]}])
    result = validate_finding(public_input(), payload, {"source-1": source_page(notice, "https://www.sec.gov/Archives/edgar/data/12345/proposal.htm")})
    assert result.action is None
    assert {"effective_date_not_supported", "listing_change_not_supported"} <= set(result.block_reasons)


@pytest.mark.parametrize("change,reason", [
    ({"source_ticker": "OTHER"}, "security_identity_mismatch"),
    ({"issuer_name": "Other Issuer"}, "security_identity_mismatch"),
    ({"security_class": "preferred stock"}, "security_identity_mismatch"),
    ({"venue": "NYSE"}, "security_identity_mismatch"),
    ({"effective_date": "2026-09-02"}, "effective_date_not_supported"),
    ({"effective_date": None, "effective_date_text": None}, "effective_date_missing"),
    ({"contradictions": ["A newer notice says trading continues."]}, "material_contradiction"),
    ({"unresolved_conditions": ["The share class is unclear."]}, "finding_incomplete"),
    ({"event_kind": "acquisition_announced"}, "event_not_actionable"),
    ({"event_kind": "trading_suspended"}, "event_not_actionable"),
    ({"timing": "unknown"}, "event_timing_unknown"),
])
@pytest.mark.parametrize("unread", [0, 1])
def test_incomplete_web_finding_is_readable_but_has_no_action(change, reason, unread):
    from src.security_lifecycle_web_finding import validate_finding

    result = validate_finding(public_input(), finding_payload(**change), {"source-1": source_page(NOTICE)}, unread_source_count=unread)
    assert result.action is None and reason in result.block_reasons
    assert result.finding.summary


@pytest.mark.parametrize("change,reason", [
    ({"source_id": "source-999"}, "source_citation_unavailable"),
    ({"quote": "An invented search snippet."}, "source_citation_mismatch"),
])
def test_search_snippets_and_unknown_source_ids_cannot_support_action(change, reason):
    from src.security_lifecycle_web_finding import validate_finding

    payload = finding_payload()
    payload["citations"][0].update(change)
    result = validate_finding(public_input(), payload, {"source-1": source_page(NOTICE)})
    assert result.action is None and reason in result.block_reasons


def test_short_ticker_match_without_issuer_and_share_class_never_authorizes():
    from src.security_lifecycle_web_finding import validate_finding

    text = "OLD was delisted effective September 1, 2026. Technical analysis is not an issuer."
    payload = finding_payload(citations=[{"source_id": "source-1", "quote": text,
                                         "supports": ["security_identity", "listing_ended", "effective_date"]}])
    result = validate_finding(public_input(), payload, {"source-1": source_page(text)})
    assert result.action is None and "security_identity_not_supported" in result.block_reasons


def test_web_continuation_is_not_inferred_from_acquirer_or_common_issuer_alone():
    from src.security_lifecycle_web_finding import validate_finding

    notice = "Issuer Old Inc Class A common stock will change its NASDAQ symbol from OLD to NEW effective September 8, 2026. The security is unchanged."
    payload = finding_payload(event_kind="symbol_continuation", timing="scheduled", successor_ticker="NEW",
                              effective_date="2026-09-08", effective_date_text="September 8, 2026",
                              citations=[{"source_id": "source-1", "quote": notice,
                                          "supports": ["security_identity", "same_security_continuation", "effective_date"]}])
    result = validate_finding(public_input(), payload, {"source-1": source_page(notice)})
    assert result.action == "symbol_continuation" and result.block_reasons == ()
    payload["citations"][0]["supports"] = ["security_identity", "acquisition_announced", "effective_date"]
    result = validate_finding(public_input(), payload, {"source-1": source_page(notice)})
    assert result.action is None and "same_security_continuation_not_supported" in result.block_reasons


def test_positive_active_otc_citation_vetoes_removal_even_if_summary_ignores_it():
    from src.security_lifecycle_web_finding import validate_finding

    otc = "Issuer Old Inc Class A common stock (OLD) continues trading on OTC."
    payload = finding_payload()
    payload["citations"].append({"source_id": "source-2", "quote": otc, "supports": ["active_otc"]})
    result = validate_finding(public_input(), payload, {"source-1": source_page(NOTICE), "source-2": source_page(otc, "https://otc.example.com/OLD")})
    assert result.action is None and "active_listing_conflict" in result.block_reasons


def test_syndicated_passages_are_not_counted_as_independent_sources():
    from src.security_lifecycle_web_finding import validate_finding

    payload = finding_payload()
    payload["citations"].append({**payload["citations"][0], "source_id": "source-2"})
    result = validate_finding(public_input(), payload, {"source-1": source_page(NOTICE), "source-2": source_page(NOTICE, "https://news.example.com/notice")})
    assert len(result.passages) == 2 and result.unique_passage_count == 1
    assert result.independent_source_count is None


@pytest.mark.parametrize("unread", [1, 2])
def test_unread_supplement_does_not_block_an_otherwise_supported_attended_finding(unread):
    from src.security_lifecycle_web_finding import validate_finding

    result = validate_finding(public_input(), finding_payload(), {"source-1": source_page(NOTICE)}, unread_source_count=unread)
    assert result.action == "terminal_delisting" and result.block_reasons == ()
    assert result.passages[0].excerpt == NOTICE and len(result.passages) == 1


def test_unread_source_cannot_be_cited_or_replace_all_missing_evidence():
    from src.security_lifecycle_web_finding import validate_finding

    for pages in ({}, {"source-2": source_page("Only an unrelated supplement was readable.")}):
        result = validate_finding(public_input(), finding_payload(), pages, unread_source_count=1)
        assert result.action is None
        assert {"source_citation_unavailable", "source_passage_missing"} <= set(result.block_reasons)


def test_tampered_document_metadata_cannot_supply_valid_passage():
    from src.security_lifecycle_web_finding import validate_finding

    page = replace(source_page(NOTICE), url="https://www.sec.gov/not-the-original")
    result = validate_finding(public_input(), finding_payload(), {"source-1": page})
    assert result.action is None and "source_integrity" in result.block_reasons


@pytest.mark.parametrize("missing", ["security_class", "venue"])
def test_unknown_identity_detail_must_be_sourced_not_guessed_or_reentered_by_user(missing):
    from src.security_lifecycle_web_contract import PublicInvestigationInput
    from src.security_lifecycle_web_finding import validate_finding
    request = PublicInvestigationInput.model_validate({**public_input().model_dump(), missing: None})
    result = validate_finding(request, finding_payload(), {"source-1": source_page(NOTICE)})
    assert result.action == "terminal_delisting"
    payload = finding_payload(**{missing: "invented class or venue"})
    result = validate_finding(request, payload, {"source-1": source_page(NOTICE)})
    assert result.action is None and "security_identity_not_supported" in result.block_reasons
