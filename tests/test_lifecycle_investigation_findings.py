import pytest
import json
from pathlib import Path


NOTICE = ('Issuer Old Inc OLD common stock on NASDAQ (the "Company Stock").\n'
          'Trading in the Company Stock ceased on September 1, 2026, when the listing ended.')


def material(text=NOTICE):
    from src.lifecycle_investigation.sources import capture_text, source_passages
    source = capture_text(text, url="https://issuer.example/notice", retrieved_at="2026-09-08T00:00:00Z", coverage="full_text")
    passages = source_passages("source-1", source)
    return source, passages


def payload(passages):
    return {"version": 2, "source_ticker": "OLD", "issuer_name": "Issuer Old Inc", "security_class": "common stock", "venue": "NASDAQ",
        "event_kind": "listing_ended", "timing": "completed", "successor_ticker": None,
        "effective_date": "2026-09-01", "effective_date_text": "September 1, 2026",
        "announcement_date": None, "announcement_date_text": None, "summary": "The common stock no longer trades.",
        "contradictions": [], "unresolved_conditions": [], "limitations": [], "citations": [
            {"passage_id": passages[0]["passage_id"], "supports": ["security_identity"]},
            {"passage_id": passages[-1]["passage_id"], "supports": ["listing_ended", "effective_date"]}]}


def target():
    from src.lifecycle_investigation.target import Target
    return Target(ticker="OLD", issuer_name="Issuer Old Inc", security_class="common stock", venue="NASDAQ", as_of="2026-09-08")


def test_stock_definition_and_event_passages_jointly_support_finding():
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material()
    result = validate_finding(target(), payload(passages), {"source-1": source}, {p["passage_id"] for p in passages})
    assert result["action"] == "terminal_delisting", result
    assert result["block_reasons"] == []
    assert result["passages"][-1]["text"] == NOTICE.split("\n")[-1]


def test_debt_event_cannot_borrow_common_stock_identity():
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material(NOTICE.split("\n")[0] + "\nThe 8% senior notes were delisted on September 1, 2026.")
    result = validate_finding(target(), payload(passages), {"source-1": source}, {p["passage_id"] for p in passages})
    assert result["action"] is None
    assert "listing_change_not_supported" in result["block_reasons"]


@pytest.mark.parametrize("identity,alias,security_class,accepted", [
    ('Issuer Old Inc (the "Company") has OLD common stock listed on NASDAQ.', "Company senior notes", "common stock", False),
    ('Issuer Old Inc OLD common stock trades on NASDAQ (the "Exchange").', "senior notes on the Exchange", "common stock", False),
    ('Issuer Old Inc OLD common stock on NASDAQ and senior notes (the "Securities").', "Securities", "common stock", False),
    ('Issuer Old Inc OLD Class A common stock on NASDAQ; Class B common stock (the "Shares").', "Shares", "Class A common stock", False),
    ('Issuer Old Inc OLD common stock (the "Shares") on NASDAQ.', "Shares", "common stock", True),
    ('Issuer Old Inc OLD common stock, par value $0.001 per share ("Company Stock"), on NASDAQ.', "Company Stock", "common stock", True),
    ('Issuer Old Inc OLD common stock on NASDAQ (the "Company Stock").', "Company Stock", "common stock", True),
    ('Issuer Old Inc OLD Class A common stock (the "Class A Shares") on NASDAQ.', "Class A Shares", "Class A common stock", True),
])
@pytest.mark.parametrize("event", ("active_listing", "listing_ended"))
def test_only_security_qualified_definitions_bind_event_aliases(identity, alias, security_class, accepted, event):
    from src.lifecycle_investigation.findings import validate_finding
    state = "continue to trade on NASDAQ" if event == "active_listing" else "ceased trading on September 1, 2026"
    source, passages = material(identity + f"\nThe {alias} {state}.")
    value = {**payload(passages), "security_class": security_class, "event_kind": event}
    if event == "active_listing":
        value.update(effective_date=None, effective_date_text=None)
        value["citations"][-1]["supports"] = ["active_listing"]
    checked = validate_finding(target().model_copy(update={"security_class": security_class}), value,
        {"source-1": source}, {p["passage_id"] for p in passages})
    if accepted:
        assert checked["block_reasons"] == []
        assert checked["action"] == ("terminal_delisting" if event == "listing_ended" else None)
    else:
        assert checked["action"] is None
        assert ("active_listing_not_supported" if event == "active_listing" else "listing_change_not_supported") in checked["block_reasons"]


def test_unsupplied_or_changed_passage_never_authorizes_action():
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material()
    result = validate_finding(target(), payload(passages), {"source-1": source}, {passages[0]["passage_id"]})
    assert result["action"] is None and "source_citation_not_supplied" in result["block_reasons"]
    source["text"] = "changed"
    with pytest.raises(ValueError, match="source_integrity"):
        validate_finding(target(), payload(passages), {"source-1": source}, {p["passage_id"] for p in passages})


@pytest.mark.parametrize("kind,timing", [("acquisition_announced", "completed"), ("listing_ended", "scheduled")])
def test_announced_acquisition_or_planned_delisting_never_stops_collection(kind, timing):
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material()
    value = {**payload(passages), "event_kind": kind, "timing": timing}
    result = validate_finding(target(), value, {"source-1": source}, {p["passage_id"] for p in passages})
    assert result["action"] is None


def test_syndicated_local_and_web_copies_are_one_source():
    from src.lifecycle_investigation.sources import same_source
    source, _ = material()
    assert same_source(source, {**source, "corpus": "news"})
    assert same_source({**source, "syndication_key": "abc"}, {**source, "url": "https://copy.example/notice", "syndication_key": "abc"})


def test_common_share_synonym_and_omitted_legal_suffix_keep_the_same_instrument():
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material(NOTICE.replace("Issuer Old Inc", "Issuer Old").replace("common stock", "common shares"))
    result = validate_finding(target(), payload(passages), {"source-1": source}, {p["passage_id"] for p in passages})
    assert result["action"] == "terminal_delisting", result["block_reasons"]


@pytest.mark.parametrize("description,canonical", [
    ("Common Stock, $0.001 par value per share", "common stock"),
    ("common shares (par value $0.001 per share)", "common stock"),
    ("Class A common stock, $0.001 par value per share", "Class A common stock"),
])
@pytest.mark.parametrize("event", ("active_listing", "listing_ended"))
def test_par_value_does_not_change_common_stock_event_identity(description, canonical, event):
    from src.lifecycle_investigation.findings import validate_finding
    state = "continues to trade on NASDAQ" if event == "active_listing" else "ceased trading on September 1, 2026"
    source, passages = material(f"Issuer Old Inc OLD {description} on NASDAQ.\nOur {canonical} {state}.")
    value = {**payload(passages), "security_class": description, "event_kind": event}
    if event == "active_listing":
        value.update(effective_date=None, effective_date_text=None)
        value["citations"][-1]["supports"] = ["active_listing"]
    checked = validate_finding(target().model_copy(update={"security_class": canonical}), value,
        {"source-1": source}, {p["passage_id"] for p in passages})
    assert checked["block_reasons"] == [], checked
    assert checked["action"] == ("terminal_delisting" if event == "listing_ended" else None)
    assert checked["finding"]["security_class"] == description


@pytest.mark.parametrize("other_class", ("Class B common stock", "preferred shares", "senior notes"))
@pytest.mark.parametrize("event", ("active_listing", "listing_ended"))
def test_par_value_normalization_never_discards_security_class(other_class, event):
    from src.lifecycle_investigation.findings import validate_finding
    description = "Class A common stock, $0.001 par value per share"
    state = "continues to trade on NASDAQ" if event == "active_listing" else "ceased trading on September 1, 2026"
    source, passages = material(f"Issuer Old Inc OLD {description} on NASDAQ.\nThe {other_class} {state}.")
    value = {**payload(passages), "security_class": description, "event_kind": event}
    if event == "active_listing":
        value.update(effective_date=None, effective_date_text=None)
        value["citations"][-1]["supports"] = ["active_listing"]
    checked = validate_finding(target().model_copy(update={"security_class": "Class A common stock"}), value,
        {"source-1": source}, {p["passage_id"] for p in passages})
    assert checked["action"] is None
    assert ("active_listing_not_supported" if event == "active_listing" else "listing_change_not_supported") in checked["block_reasons"]


@pytest.mark.parametrize("instrument", ["preferred shares", "senior notes", "Class B common stock"])
def test_instrument_synonyms_cannot_cross_security_classes(instrument):
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material(NOTICE.replace("common stock", instrument))
    expected = target().model_copy(update={"security_class": "Class A common stock"})
    finding = {**payload(passages), "security_class": "Class A common stock"}
    assert validate_finding(expected, finding, {"source-1": source}, {p["passage_id"] for p in passages})["action"] is None


def test_target_event_passages_precede_navigation_and_query_is_effective():
    from src.lifecycle_investigation.sources import select_passages
    source, _ = material("\n".join(["NASDAQ trading news menu" for _ in range(100)]) + "\n" + NOTICE)
    selected = select_passages("source-1", source, ticker="OLD", issuer_name="Issuer Old Inc")
    assert any("Company Stock ceased" in p["text"] for p in selected["passages"])
    queried = select_passages("source-1", source, ticker="OLD", query="ceased")
    assert "ceased" in queried["passages"][0]["text"]


def test_small_fragmented_notice_initial_context_preserves_complete_document():
    from src.lifecycle_investigation.sources import capture_text, select_passages, source_passages
    fixture = json.loads((Path(__file__).parent / "fixtures/lifecycle_ta_full_notice_v2.json").read_text())
    source = capture_text(fixture["text"], url=fixture["url"], retrieved_at=fixture["retrieved_at"], coverage=fixture["coverage"])
    assert source["text_sha256"] == fixture["text_sha256"]
    complete = source_passages("source-1", source)
    assert len(complete) == 262
    selected = select_passages("source-1", source, ticker="TA", issuer_name="TravelCenters of America Inc.")
    assert selected["passages"] == complete
    assert selected["input_coverage"] == "full_text" and selected["next_offset"] is None
    assert any("May 15, 2023" in p["text"] for p in selected["passages"])
    # An explicit page request still works and never renumbers citations.
    page = select_passages("source-1", source, ticker="TA", query="Company Stock", limit=1)
    assert len(page["passages"]) == 1 and page["next_offset"] == 1
    assert page["passages"][0] in complete


def test_large_document_keeps_unselected_passages_inspectable_without_truncation():
    from src.lifecycle_investigation.sources import select_passages, source_passages
    source, _ = material("\n".join(["OLD NASDAQ common stock navigation" for _ in range(1000)]) + "\n" + NOTICE)
    first = select_passages("source-1", source, ticker="OLD")
    assert first["input_coverage"] == "selected_passages"
    assert first["next_offset"] == 12 and len(first["passages"]) == 12
    second = select_passages("source-1", source, ticker="OLD", offset=first["next_offset"])
    assert not ({p["passage_id"] for p in first["passages"]} & {p["passage_id"] for p in second["passages"]})
    queried = select_passages("source-1", source, ticker="OLD", query="ceased")
    assert "ceased" in queried["passages"][0]["text"]
    assert len(source_passages("source-1", source)) == 1002


def test_wrapped_event_sentence_binds_its_adjacent_date_but_not_a_new_sentence():
    from src.lifecycle_investigation.findings import validate_finding
    for ending, accepted in (("on", True), ("yesterday.", False)):
        source, passages = material(NOTICE.split("\n")[0] + f"\nTrading in the Company Stock ceased {ending}\nSeptember 1, 2026.")
        value = payload(passages)
        value["citations"].insert(1, {"passage_id": passages[1]["passage_id"], "supports": ["listing_ended"]})
        result = validate_finding(target(), value, {"source-1": source}, {p["passage_id"] for p in passages})
        assert (result["action"] == "terminal_delisting") is accepted, result["block_reasons"]


def test_future_scheduled_date_is_reportable_but_cannot_authorize_removal():
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material(NOTICE.replace("September 1, 2026", "September 10, 2026"))
    value = {**payload(passages), "timing": "scheduled", "effective_date": "2026-09-10", "effective_date_text": "September 10, 2026"}
    supplied = {p["passage_id"] for p in passages}
    result = validate_finding(target(), value, {"source-1": source}, supplied)
    assert result["action"] is None
    assert result["block_reasons"] == ["event_not_completed"]
    completed = validate_finding(target(), {**value, "timing": "completed"}, {"source-1": source}, supplied)
    assert "effective_date_not_supported" in completed["block_reasons"]


def test_unknown_exact_date_is_a_visible_limitation_not_a_material_conflict():
    from src.lifecycle_investigation.findings import validate_finding
    source, passages = material(NOTICE.replace(" on September 1, 2026", ""))
    value = {**payload(passages), "effective_date": None, "effective_date_text": None,
        "limitations": ["The source confirms trading ended but does not state its exact date."]}
    result = validate_finding(target(), value, {"source-1": source}, {p["passage_id"] for p in passages})
    assert result["action"] == "terminal_delisting"
    assert result["finding"]["limitations"] == value["limitations"]
    unresolved = validate_finding(target(), {**value, "unresolved_conditions": ["It may still trade OTC."]}, {"source-1": source}, {p["passage_id"] for p in passages})
    assert unresolved["action"] is None and "finding_incomplete" in unresolved["block_reasons"]


@pytest.mark.parametrize("variant", ("actual_public_fragments", "different_security", "unrelated_date"))
def test_real_ta_notice_requires_its_stock_definition_and_wrapped_event_date(variant):
    from src.lifecycle_investigation.sources import capture_text, source_passages
    from src.lifecycle_investigation.findings import validate_finding
    from src.lifecycle_investigation.target import Target
    fixture = json.loads((Path(__file__).parent / "fixtures/lifecycle_ta_wrapped_notice_v2.json").read_text())
    fragments = [row["text"] for row in fixture["fragments"]]
    if variant == "different_security":
        fragments[4] = fragments[4].replace("shares of Company Stock", "senior notes")
    if variant == "unrelated_date":
        fragments[4] += "."
    source = capture_text("\n".join(fragments), url=fixture["url"], retrieved_at=fixture["retrieved_at"], coverage="captured_document")
    passages = source_passages("source-1", source)
    value = {**payload(passages), "source_ticker": "TA", "issuer_name": "TravelCenters of America Inc.",
        "effective_date": "2023-05-15", "effective_date_text": "May 15, 2023", "citations": [
            *[{"passage_id": passages[i]["passage_id"], "supports": ["security_identity"]} for i in (0, 1, 2, 3, 6)],
            {"passage_id": passages[4]["passage_id"], "supports": ["listing_ended"]},
            {"passage_id": passages[5]["passage_id"], "supports": ["effective_date"]}]}
    checked = validate_finding(Target(ticker="TA", as_of="2026-09-08"), value, {"source-1": source}, {p["passage_id"] for p in passages})
    assert (checked["action"] == "terminal_delisting") is (variant == "actual_public_fragments"), checked
    if variant == "different_security":
        assert "listing_change_not_supported" in checked["block_reasons"]
    if variant == "unrelated_date":
        assert "effective_date_not_supported" in checked["block_reasons"]
