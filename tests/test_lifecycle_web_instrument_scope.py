import pytest

from src.security_lifecycle_web_contract import PublicInvestigationInput
from src.security_lifecycle_web_finding import WebFinding, strict_schema, validate_finding
from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input, source_page


IDENTITY = "Issuer Old Inc Class A common stock (OLD) is listed on NASDAQ."


def citation(quote, supports, source_id="source-1"):
    return {"source_id": source_id, "quote": quote, "supports": supports}


@pytest.mark.parametrize("other_class", ["senior notes", "preferred stock", "call options"])
@pytest.mark.parametrize("same_source", [False, True])
def test_other_instrument_delisting_never_combines_with_stock_identity(other_class, same_source):
    event = f"Issuer Old Inc {other_class} (OLDX) were delisted from NASDAQ effective September 1, 2026."
    source_id = "source-1" if same_source else "source-2"
    pages = {"source-1": source_page(IDENTITY + "\n" + event if same_source else IDENTITY)}
    if not same_source:
        pages[source_id] = source_page(event, "https://ir.example.com/other-security")
    payload = finding_payload(citations=[citation(IDENTITY, ["security_identity"]),
        citation(event, ["listing_ended", "effective_date"], source_id)])
    result = validate_finding(public_input(), payload, pages)
    assert result.action is None
    assert {"listing_change_not_supported", "effective_date_not_supported"} <= set(result.block_reasons)
    assert "security_identity_not_supported" not in result.block_reasons
    assert len(result.passages) == 2


def test_other_instrument_date_cannot_complete_a_stock_listing_event():
    stock = "Issuer Old Inc Class A common stock (OLD) was delisted from NASDAQ."
    notes = "Issuer Old Inc senior notes (OLDN) were delisted effective September 1, 2026."
    payload = finding_payload(citations=[citation(stock, ["security_identity", "listing_ended"]),
        citation(notes, ["effective_date"], "source-2")])
    result = validate_finding(public_input(), payload, {"source-1": source_page(stock),
        "source-2": source_page(notes, "https://ir.example.com/notes")})
    assert result.action is None and "effective_date_not_supported" in result.block_reasons
    assert "listing_change_not_supported" not in result.block_reasons


def test_other_instrument_rename_cannot_supply_a_stock_continuation():
    notes = "Issuer Old Inc senior notes change symbol from OLD to NEW effective September 1, 2026."
    payload = finding_payload(event_kind="symbol_continuation", successor_ticker="NEW",
        citations=[citation(IDENTITY, ["security_identity"]),
                   citation(notes, ["same_security_continuation", "effective_date"], "source-2")])
    result = validate_finding(public_input(), payload, {"source-1": source_page(IDENTITY),
        "source-2": source_page(notes, "https://ir.example.com/notes")})
    assert result.action is None
    assert "same_security_continuation_not_supported" in result.block_reasons


@pytest.mark.parametrize("other_class,blocked", [("senior notes", False), ("Class A common stock", True)])
def test_only_target_instrument_active_otc_evidence_vetoes_stock_removal(other_class, blocked):
    symbol = "OLD" if blocked else "OLDN"
    otc = f"Issuer Old Inc {other_class} ({symbol}) remains actively traded OTC."
    payload = finding_payload(citations=[citation(NOTICE, ["security_identity", "listing_ended", "effective_date"]),
        citation(otc, ["active_otc"], "source-2")])
    result = validate_finding(public_input(), payload, {"source-1": source_page(NOTICE),
        "source-2": source_page(otc, "https://otc.example.com/notice")})
    assert ("active_listing_conflict" in result.block_reasons) is blocked
    assert result.action == (None if blocked else "terminal_delisting")


@pytest.mark.parametrize("security_class", ["Class A common stock", "senior notes", "call options", "ETF shares"])
def test_binding_follows_the_requested_instrument_not_a_stock_only_allowlist(security_class):
    request = PublicInvestigationInput.model_validate({**public_input().model_dump(), "security_class": security_class})
    notice = NOTICE.replace("Class A common stock", security_class)
    payload = finding_payload(security_class=security_class,
        citations=[citation(notice, ["security_identity", "listing_ended", "effective_date"])])
    result = validate_finding(request, payload, {"source-1": source_page(notice)})
    assert result.action == "terminal_delisting" and not result.block_reasons


def test_identity_and_target_event_can_be_separate_exact_quotes_in_the_same_source():
    event = "The Class A common stock was delisted effective September 1, 2026."
    payload = finding_payload(citations=[citation(IDENTITY, ["security_identity"]),
        citation(event, ["listing_ended", "effective_date"])])
    result = validate_finding(public_input(), payload, {"source-1": source_page(IDENTITY + "\n" + event)})
    assert result.action == "terminal_delisting" and not result.block_reasons


def test_unbound_same_class_event_from_another_issuer_does_not_supply_stock_change():
    other = "Other Issuer Class A common stock (OTHER) was delisted from NASDAQ effective September 1, 2026."
    payload = finding_payload(citations=[citation(IDENTITY, ["security_identity"]),
        citation(other, ["listing_ended", "effective_date"], "source-2")])
    result = validate_finding(public_input(), payload, {"source-1": source_page(IDENTITY),
        "source-2": source_page(other, "https://other.example.com/notice")})
    assert result.action is None and "listing_change_not_supported" in result.block_reasons


@pytest.mark.parametrize("bad_quote", [
    "Issuer Old Inc Class A common stock (OLD) ... effective September 1, 2026.",
    "Issuer Old Inc Class A common stock (OLD)\nwas delisted from NASDAQ effective September 1, 2026.",
])
def test_live_style_shortened_or_reformatted_quotes_are_not_repaired(bad_quote):
    result = validate_finding(public_input(), finding_payload(citations=[citation(bad_quote,
        ["security_identity", "listing_ended", "effective_date"])]), {"source-1": source_page(NOTICE)})
    assert result.action is None and "source_citation_mismatch" in result.block_reasons


def test_live_style_date_phrase_is_rejected_while_bare_verbatim_date_is_accepted():
    pages = {"source-1": source_page(NOTICE)}
    rejected = validate_finding(public_input(), finding_payload(effective_date_text="effective September 1, 2026"), pages)
    assert rejected.action is None and "effective_date_not_supported" in rejected.block_reasons
    accepted = validate_finding(public_input(), finding_payload(), pages)
    assert accepted.action == "terminal_delisting"


def test_model_schema_explains_exact_citations_and_bare_verbatim_dates():
    schema = strict_schema(WebFinding)
    quote = schema["$defs"]["FindingCitation"]["properties"]["quote"]["description"]
    assert "contiguous" in quote and "ellipsis" in quote and "whitespace" in quote
    for field in ("effective_date_text", "announcement_date_text"):
        description = schema["properties"][field]["description"]
        assert "bare calendar date" in description and "not a whole sentence" in description
