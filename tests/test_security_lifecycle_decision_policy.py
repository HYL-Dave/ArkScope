from __future__ import annotations

from datetime import date

import pytest


_CIK = "0001409970"


def _case(*, ticker="LC", kinds=("listing_status_review",)):
    return {
        "case_id": "slc_case",
        "ticker": ticker,
        "cik": _CIK,
        "issuer_name": "Hapn Holdings, Inc.",
        "filing_date": "2026-06-02",
        "event_kinds": kinds,
    }


def _evidence(evidence_id, family):
    row = {"evidence_id": evidence_id, "source_family": family}
    if family == "market_infrastructure":
        row["source_locator"] = {
            "contract_status": "found",
            "market_data": {
                "status": "live",
                "last": "12.57",
                "provider_time": "2026-08-25T01:01:00Z",
                "retrieved_at": "2026-08-25T01:02:03Z",
                "fresh": True,
            },
        }
    return row


def _fact(evidence_id, fact_type, value):
    return {
        "evidence_id": evidence_id,
        "fact_type": fact_type,
        "normalized_value": value,
    }


def _listing_evidence(
    evidence_id,
    *,
    adapter,
    ticker,
    expected_active_state,
    market,
    listing_status,
    directory=None,
    retrieved_at="2026-08-25T01:02:03Z",
    delisted_utc=None,
):
    snapshot = {
        "locator_kind": "listing_directory_snapshot",
        "adapter": adapter,
        "candidate_ticker": ticker,
        "expected_active_state": expected_active_state,
        "market": market,
        "listing_status": listing_status,
        "directory": directory,
    }
    if delisted_utc is not None:
        snapshot["delisted_utc"] = delisted_utc
    return {
        "evidence_id": evidence_id,
        "source_family": "listing_authority",
        "source_locator": snapshot,
        "retrieved_at": retrieved_at,
    }


def _active_listing(
    evidence_id,
    ticker,
    *,
    adapter="nasdaq_symbol_directory",
    market="stocks",
    venue="NASDAQ",
    cik=None,
    security_class=None,
    current_ticker=None,
    retrieved_at="2026-08-25T01:02:03Z",
):
    evidence = _listing_evidence(
        evidence_id,
        adapter=adapter,
        ticker=ticker,
        expected_active_state=True,
        market=market,
        listing_status="active",
        directory=("nasdaq_listed" if adapter == "nasdaq_symbol_directory" else None),
        retrieved_at=retrieved_at,
    )
    if ticker == current_ticker:
        facts = [
            _fact(evidence_id, "source_ticker", ticker),
            _fact(evidence_id, "source_venue", venue),
        ]
    else:
        facts = [
            _fact(evidence_id, "successor_ticker", ticker),
            _fact(evidence_id, "destination_venue", venue),
        ]
    if security_class is None and adapter == "massive_reference":
        security_class = "common_stock"
    if security_class is not None:
        facts.append(_fact(evidence_id, "security_class", security_class))
    if cik is not None:
        facts.append(_fact(evidence_id, "issuer_cik", cik))
    return evidence, tuple(facts)


def _not_found_listing(evidence_id, ticker, *, directory):
    return _listing_evidence(
        evidence_id,
        adapter="nasdaq_symbol_directory",
        ticker=ticker,
        expected_active_state=True,
        market="stocks",
        listing_status="not_found",
        directory=directory,
    )


def _massive_inactive(evidence_id, ticker, *, cik=_CIK):
    evidence = _listing_evidence(
        evidence_id,
        adapter="massive_reference",
        ticker=ticker,
        expected_active_state=False,
        market="stocks",
        listing_status="inactive",
        delisted_utc="2026-08-24T00:00:00Z",
    )
    return evidence, (
        _fact(evidence_id, "source_ticker", ticker),
        _fact(evidence_id, "issuer_cik", cik),
        _fact(evidence_id, "security_class", "common_stock"),
    )


def _legacy_listing_shape(row):
    if row["source_family"] != "listing_authority":
        return row
    locator = dict(row["source_locator"])
    status = locator.pop("listing_status")
    if status == "active":
        locator.update({"status": "found", "active": True})
    elif status == "inactive":
        locator.update({"status": "found", "active": False})
    else:
        locator["status"] = status
    return {**row, "source_locator": locator}


def _eligible_preview(request):
    return {
        "eligible": True,
        "block_reasons": (),
        "transition_kind": request["transition_kind"],
    }


def _listing_fixture(name):
    nms, nms_facts = _active_listing("nasdaq", "NEW")
    otc, otc_facts = _active_listing(
        "massive-otc",
        "NEW",
        adapter="massive_reference",
        market="otc",
        venue="OTC",
        cik=_CIK,
    )
    same, same_facts = _active_listing("nasdaq-same", "SAME", current_ticker="SAME")
    unchanged, unchanged_facts = _active_listing(
        "nasdaq-unchanged", "KEEP", current_ticker="KEEP"
    )
    terminal_sec = {
        **_evidence("sec", "regulator"),
        "source_locator": {"filing_chain_complete": True},
    }
    terminal_facts = (
        _fact("sec", "source_ticker", "OLD"),
        _fact("sec", "effective_date", "2026-08-24"),
        _fact("sec", "security_class", "common_stock"),
        _fact("sec", "issuer_cik", _CIK),
        _fact("sec", "tracked_security_effect", "terminal_delisting"),
    )
    massive_inactive, massive_inactive_facts = _massive_inactive(
        "massive-inactive", "OLD"
    )
    fixtures = {
        "nms_symbol_continuation": {
            "case": _case(ticker="OLD"),
            "evidence": (_evidence("sec", "regulator"), nms),
            "facts": _identity_facts(
                source="OLD",
                successor="NEW",
                source_venue="NASDAQ",
                destination_venue="NASDAQ",
                effective_date="2026-08-24",
            )[:7]
            + nms_facts,
        },
        "otc_symbol_continuation": {
            "case": _case(ticker="OLD"),
            "evidence": (_evidence("sec", "regulator"), otc),
            "facts": _identity_facts(
                source="OLD",
                successor="NEW",
                source_venue="NASDAQ",
                destination_venue="OTC",
                effective_date="2026-08-24",
            )[:7]
            + otc_facts,
        },
        "same_symbol_venue_transfer": {
            "case": _case(ticker="SAME"),
            "evidence": (_evidence("sec", "regulator"), same),
            "facts": _identity_facts(
                source="SAME",
                successor="SAME",
                source_venue="NYSE",
                destination_venue="NASDAQ",
                effective_date="2026-08-24",
            )[:7]
            + same_facts,
        },
        "terminal_delisting": {
            "case": _case(ticker="OLD", kinds=("listing_removal_notice",)),
            "evidence": (
                terminal_sec,
                _not_found_listing("nasdaq-listed", "OLD", directory="nasdaq_listed"),
                _not_found_listing("nasdaq-other", "OLD", directory="other_listed"),
                massive_inactive,
            ),
            "facts": terminal_facts + massive_inactive_facts,
        },
        "nasdaq_absence_only": {
            "case": _case(ticker="OLD", kinds=("listing_removal_notice",)),
            "evidence": (
                terminal_sec,
                _not_found_listing("nasdaq-listed", "OLD", directory="nasdaq_listed"),
                _not_found_listing("nasdaq-other", "OLD", directory="other_listed"),
            ),
            "facts": terminal_facts,
        },
        "ibkr_conflict": {
            "case": _case(ticker="OLD"),
            "evidence": (
                _evidence("sec", "regulator"),
                nms,
                _evidence("ibkr-conflict", "market_infrastructure"),
            ),
            "facts": _identity_facts(
                source="OLD",
                successor="NEW",
                source_venue="NASDAQ",
                destination_venue="NASDAQ",
                effective_date="2026-08-24",
            )[:7]
            + nms_facts
            + (
                _fact("ibkr-conflict", "successor_ticker", "NEW"),
                _fact("ibkr-conflict", "destination_venue", "NYSE"),
                _fact("ibkr-conflict", "security_class", "common_stock"),
            ),
        },
        "completed_acquirer_active": {
            "case": _case(ticker="KEEP", kinds=("acquisition_completed",)),
            "evidence": (_evidence("sec", "regulator"), unchanged),
            "facts": (
                _fact("sec", "source_ticker", "KEEP"),
                _fact("sec", "issuer_cik", _CIK),
                _fact("sec", "security_class", "common_stock"),
                _fact("sec", "effective_date", "2026-08-24"),
                _fact("sec", "tracked_security_effect", "no_identity_change"),
            )
            + unchanged_facts,
        },
        "active_without_sec_role": {
            "case": _case(ticker="KEEP", kinds=("acquisition_completed",)),
            "evidence": (_evidence("sec", "regulator"), unchanged),
            "facts": (
                _fact("sec", "source_ticker", "KEEP"),
                _fact("sec", "issuer_cik", _CIK),
                _fact("sec", "security_class", "common_stock"),
                _fact("sec", "effective_date", "2026-08-24"),
            )
            + unchanged_facts,
        },
    }
    return fixtures[name]


def _evaluate_fixture(name, *, add_evidence=(), add_facts=()):
    fixture = _listing_fixture(name)
    return _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"] + tuple(add_evidence),
        facts=fixture["facts"] + tuple(add_facts),
        transition_preview=_eligible_preview,
    )


@pytest.mark.parametrize(
    ("fixture_name", "tier", "readiness", "outcomes"),
    [
        (
            "nms_symbol_continuation",
            "verified_automatic",
            "transition_eligible",
            ("symbol_changed",),
        ),
        (
            "otc_symbol_continuation",
            "verified_automatic",
            "transition_eligible",
            ("symbol_changed", "venue_transfer"),
        ),
        (
            "same_symbol_venue_transfer",
            "verified_automatic",
            "not_applicable",
            ("venue_transfer",),
        ),
        (
            "terminal_delisting",
            "verified_automatic",
            "transition_eligible",
            ("listing_ended",),
        ),
        (
            "nasdaq_absence_only",
            "verified_automatic",
            "waiting_market_confirmation",
            ("undetermined",),
        ),
        (
            "ibkr_conflict",
            "review_suggested",
            "action_blocked",
            ("undetermined",),
        ),
        (
            "completed_acquirer_active",
            "verified_automatic",
            "not_applicable",
            ("no_tracked_security_change",),
        ),
        (
            "active_without_sec_role",
            "review_suggested",
            "action_blocked",
            ("undetermined",),
        ),
    ],
)
def test_listing_authority_decision_matrix(fixture_name, tier, readiness, outcomes):
    decision = _evaluate_fixture(fixture_name)

    assert decision.decision_tier == tier
    assert decision.action_readiness == readiness
    assert decision.outcomes == outcomes


def test_missing_sec_destination_uses_current_massive_otc_authority():
    fixture = _listing_fixture("otc_symbol_continuation")
    facts = tuple(
        fact
        for fact in fixture["facts"]
        if not (
            fact["evidence_id"] == "sec" and fact["fact_type"] == "destination_venue"
        )
    )

    decision = _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"],
        facts=facts,
        transition_preview=_eligible_preview,
    )

    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "transition_eligible"
    assert decision.destination_venue == "OTC"
    assert decision.transition_requested is True


def test_selected_nasdaq_and_massive_otc_active_authorities_conflict():
    from src.security_lifecycle_decision_policy import (
        listing_authority_conflict_codes,
    )

    fixture = _listing_fixture("otc_symbol_continuation")
    nasdaq, _nasdaq_facts = _active_listing("nasdaq-conflict", "NEW")
    facts = tuple(
        fact
        for fact in fixture["facts"]
        if not (
            fact["evidence_id"] == "sec" and fact["fact_type"] == "destination_venue"
        )
    )

    decision = _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"] + (nasdaq,),
        facts=facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("conflicting authorities must not preview")
        ),
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.outcomes == ("undetermined",)
    assert decision.decision_issues == ("listing_authority_conflict",)
    assert listing_authority_conflict_codes(
        case=fixture["case"],
        evidence=fixture["evidence"] + (nasdaq,),
        facts=facts,
    ) == decision.decision_issues


@pytest.mark.parametrize(
    ("fixture_name", "removed_evidence", "removed_fact", "issue"),
    [
        (
            "nms_symbol_continuation",
            "nasdaq",
            None,
            "listing_active_missing",
        ),
        (
            "otc_symbol_continuation",
            "massive-otc",
            None,
            "massive_otc_active_missing",
        ),
        (
            "same_symbol_venue_transfer",
            "nasdaq-same",
            None,
            "listing_active_missing",
        ),
        (
            "terminal_delisting",
            "nasdaq-other",
            None,
            "nasdaq_not_found_incomplete",
        ),
        (
            "terminal_delisting",
            "massive-inactive",
            None,
            "massive_explicit_inactive_missing",
        ),
        (
            "completed_acquirer_active",
            "nasdaq-unchanged",
            None,
            "listing_active_missing",
        ),
        (
            "completed_acquirer_active",
            None,
            "tracked_security_effect",
            "regulator_role_effect_missing",
        ),
    ],
)
def test_listing_authority_positive_paths_fail_when_one_material_gate_is_removed(
    fixture_name, removed_evidence, removed_fact, issue
):
    fixture = _listing_fixture(fixture_name)
    evidence = tuple(
        row for row in fixture["evidence"] if row["evidence_id"] != removed_evidence
    )
    evidence_ids = {row["evidence_id"] for row in evidence}
    facts = tuple(
        row
        for row in fixture["facts"]
        if row["evidence_id"] in evidence_ids and row["fact_type"] != removed_fact
    )

    decision = _evaluate(
        case=fixture["case"],
        evidence=evidence,
        facts=facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("a missing gate must not preview a transition")
        ),
    )

    assert decision.transition_requested is False
    assert issue in decision.decision_issues


def test_nasdaq_not_found_never_proves_terminal_without_massive_explicit_inactive():
    decision = _evaluate_fixture("nasdaq_absence_only")

    assert decision.outcomes == ("undetermined",)
    assert decision.action_readiness == "waiting_market_confirmation"
    assert decision.transition_requested is False


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("directory", "invented_listed"),
        ("expected_active_state", False),
        ("market", "otc"),
    ),
)
def test_terminal_requires_exact_nasdaq_absence_component_identity(field, value):
    fixture = _listing_fixture("terminal_delisting")
    evidence = [
        {
            **row,
            "source_locator": {**row["source_locator"], field: value},
        }
        if row["evidence_id"] == "nasdaq-listed"
        else row
        for row in fixture["evidence"]
    ]
    if field != "market":
        evidence.append(
            _listing_evidence(
                "nasdaq-decoy",
                adapter="nasdaq_symbol_directory",
                ticker="OLD",
                expected_active_state=True,
                market="decoy",
                listing_status="not_found",
                directory="decoy_listed",
            )
        )
    evidence = tuple(_legacy_listing_shape(row) for row in evidence)

    decision = _evaluate(
        case=fixture["case"],
        evidence=evidence,
        facts=fixture["facts"],
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("an inexact Nasdaq component must not preview")
        ),
    )

    assert decision.action_readiness == "waiting_market_confirmation"
    assert decision.outcomes == ("undetermined",)
    assert decision.decision_issues == ("nasdaq_not_found_incomplete",)
    assert decision.transition_requested is False


def test_arbitrary_nasdaq_market_labels_do_not_complete_terminal_absence():
    fixture = _listing_fixture("terminal_delisting")
    markets = {"nasdaq-listed": "alpha", "nasdaq-other": "beta"}
    evidence = tuple(
        {
            **row,
            "source_locator": {
                **row["source_locator"],
                "market": markets[row["evidence_id"]],
            },
        }
        if row["evidence_id"] in markets
        else row
        for row in fixture["evidence"]
    )
    evidence = tuple(_legacy_listing_shape(row) for row in evidence)

    decision = _evaluate(
        case=fixture["case"],
        evidence=evidence,
        facts=fixture["facts"],
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("arbitrary market labels must not preview")
        ),
    )

    assert decision.action_readiness == "waiting_market_confirmation"
    assert decision.outcomes == ("undetermined",)
    assert decision.decision_issues == ("nasdaq_not_found_incomplete",)


def test_ibkr_missing_never_proves_terminal():
    fixture = _listing_fixture("nasdaq_absence_only")
    ibkr_missing = {
        **_evidence("ibkr-missing", "market_infrastructure"),
        "source_locator": {"contract_status": "missing"},
    }
    decision = _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"] + (ibkr_missing,),
        facts=fixture["facts"],
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("IBKR missing must not preview terminal action")
        ),
    )

    assert decision.outcomes == ("undetermined",)
    assert decision.transition_requested is False


def test_terminal_delisting_fails_closed_when_a_current_successor_is_active():
    successor, successor_facts = _active_listing("nasdaq-successor", "NEW")
    decision = _evaluate_fixture(
        "terminal_delisting",
        add_evidence=(successor,),
        add_facts=successor_facts,
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.outcomes == ("undetermined",)
    assert decision.decision_issues == ("successor_present",)
    assert decision.transition_requested is False


def test_terminal_delisting_requires_non_future_massive_delisted_time():
    fixture = _listing_fixture("terminal_delisting")
    evidence = tuple(
        {
            **row,
            "source_locator": {
                **row["source_locator"],
                "delisted_utc": "2026-09-30T00:00:00Z",
            },
        }
        if row["evidence_id"] == "massive-inactive"
        else row
        for row in fixture["evidence"]
    )
    decision = _evaluate(
        case=fixture["case"],
        evidence=evidence,
        facts=fixture["facts"],
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("future delisting evidence must not preview terminal action")
        ),
    )

    assert decision.action_readiness == "waiting_market_confirmation"
    assert decision.outcomes == ("undetermined",)
    assert decision.decision_issues == ("massive_explicit_inactive_missing",)
    assert decision.transition_requested is False


def test_quote_freshness_is_inert_for_v4_acceptance():
    fixture = _listing_fixture("nms_symbol_continuation")
    stale_ibkr = {
        **_evidence("ibkr-stale", "market_infrastructure"),
        "source_locator": {
            "contract_status": "found",
            "market_data": {"status": "frozen", "fresh": False},
        },
    }
    ibkr_facts = (
        _fact("ibkr-stale", "successor_ticker", "NEW"),
        _fact("ibkr-stale", "destination_venue", "NASDAQ"),
        _fact("ibkr-stale", "security_class", "common_stock"),
    )
    baseline = _evaluate_fixture("nms_symbol_continuation")
    stale = _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"] + (stale_ibkr,),
        facts=fixture["facts"] + ibkr_facts,
        transition_preview=_eligible_preview,
    )

    assert baseline.action_readiness == "transition_eligible"
    assert stale.action_readiness == "transition_eligible"
    assert stale == baseline


def test_publisher_evidence_cannot_change_v4_decision():
    baseline = _evaluate_fixture("nms_symbol_continuation")
    injected_evidence = (
        _evidence("publisher", "publisher"),
        _evidence("web", "general_web"),
        _evidence("manual", "manual"),
    )
    injected_facts = tuple(
        _fact(evidence_id, fact_type, value)
        for evidence_id in ("publisher", "web", "manual")
        for fact_type, value in (
            ("successor_ticker", "WRONG"),
            ("destination_venue", "NYSE"),
            ("issuer_cik", "0000000001"),
        )
    )

    with_injection = _evaluate_fixture(
        "nms_symbol_continuation",
        add_evidence=injected_evidence,
        add_facts=injected_facts,
    )

    assert with_injection == baseline


def test_massive_sec_cik_conflict_fails_closed():
    from src.security_lifecycle_decision_policy import (
        listing_authority_conflict_codes,
    )

    fixture = _listing_fixture("nms_symbol_continuation")
    massive, massive_facts = _active_listing(
        "massive",
        "NEW",
        adapter="massive_reference",
        market="stocks",
        venue="NASDAQ",
        cik="0000000001",
    )
    evidence = fixture["evidence"] + (massive,)
    facts = fixture["facts"] + massive_facts
    decision = _evaluate(
        case=fixture["case"],
        evidence=evidence,
        facts=facts,
        transition_preview=_eligible_preview,
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.outcomes == ("undetermined",)
    assert decision.decision_issues == ("listing_authority_conflict",)
    assert listing_authority_conflict_codes(
        case=fixture["case"],
        evidence=evidence,
        facts=facts,
    ) == decision.decision_issues


def test_equal_time_disagreement_inside_one_listing_component_fails_closed():
    active, active_facts = _active_listing("nasdaq-active", "NEW")
    not_found = _listing_evidence(
        "nasdaq-missing",
        adapter="nasdaq_symbol_directory",
        ticker="NEW",
        expected_active_state=True,
        market="stocks",
        listing_status="not_found",
        directory="nasdaq_listed",
    )
    decision = _evaluate_fixture(
        "nms_symbol_continuation",
        add_evidence=(active, not_found),
        add_facts=active_facts,
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.decision_issues == ("listing_authority_conflict",)


def test_newer_listing_record_supersedes_only_its_own_component():
    from src.security_lifecycle_decision_policy import (
        _evidence_rows,
        _listing_records,
    )

    evidence = _evidence_rows(
        (
            _listing_evidence(
                "nasdaq-old",
                adapter="nasdaq_symbol_directory",
                ticker="NEW",
                expected_active_state=True,
                market="stocks",
                listing_status="active",
                directory="nasdaq_listed",
                retrieved_at="2026-08-25T00:00:00Z",
            ),
            _listing_evidence(
                "nasdaq-new",
                adapter="nasdaq_symbol_directory",
                ticker="NEW",
                expected_active_state=True,
                market="stocks",
                listing_status="not_found",
                directory="nasdaq_listed",
                retrieved_at="2026-08-25T02:00:00Z",
            ),
            _listing_evidence(
                "massive-current",
                adapter="massive_reference",
                ticker="NEW",
                expected_active_state=True,
                market="stocks",
                listing_status="active",
                retrieved_at="2026-08-25T01:00:00Z",
            ),
        )
    )

    assert tuple(row.evidence_id for row in _listing_records(evidence, "NEW")) == (
        "massive-current",
        "nasdaq-new",
    )


def test_legacy_listing_status_and_active_shape_remains_narrowly_compatible():
    from src.security_lifecycle_decision_policy import (
        _evidence_rows,
        _listing_row_active,
    )

    legacy = {
        **_listing_evidence(
            "legacy-active",
            adapter="nasdaq_symbol_directory",
            ticker="NEW",
            expected_active_state=True,
            market="stocks",
            listing_status="active",
            directory="nasdaq_listed",
        ),
    }
    legacy["source_locator"].pop("listing_status")
    legacy["source_locator"].update({"status": "found", "active": True})

    assert _listing_row_active(_evidence_rows((legacy,))[0]) is True


def _identity_facts(
    *,
    source="LC",
    successor="HAPN",
    source_venue="NYSE",
    destination_venue="NASDAQ",
    effective_date="2026-06-27",
):
    return (
        _fact("sec", "source_ticker", source),
        _fact("sec", "successor_ticker", successor),
        _fact("sec", "source_venue", source_venue),
        _fact("sec", "destination_venue", destination_venue),
        _fact("sec", "effective_date", effective_date),
        _fact("sec", "security_class", "common_stock"),
        _fact("sec", "issuer_cik", _CIK),
        _fact("ibkr", "successor_ticker", successor),
        _fact("ibkr", "destination_venue", destination_venue),
        _fact("ibkr", "security_class", "common_stock"),
    )


def _evaluate(
    *,
    case=None,
    evidence=None,
    facts=None,
    current_date=date(2026, 8, 25),
    active_sources=("manual_lists",),
    transition_preview=None,
):
    from src.security_lifecycle_decision_policy import evaluate_automation_decision

    selected_case = case or _case()
    selected_facts = tuple(facts or _identity_facts())
    selected_evidence = evidence
    if selected_evidence is None:
        successor = next(
            (
                row["normalized_value"]
                for row in selected_facts
                if row["evidence_id"] == "sec"
                and row["fact_type"] == "successor_ticker"
            ),
            "HAPN",
        )
        venue = next(
            (
                row["normalized_value"]
                for row in selected_facts
                if row["evidence_id"] == "sec"
                and row["fact_type"] == "destination_venue"
            ),
            "NASDAQ",
        )
        listing, listing_facts = _active_listing(
            "nasdaq",
            successor,
            venue=venue,
            current_ticker=selected_case["ticker"],
        )
        selected_evidence = (
            _evidence("sec", "regulator"),
            listing,
            _evidence("ibkr", "market_infrastructure"),
        )
        selected_facts += listing_facts
    return evaluate_automation_decision(
        case=selected_case,
        evidence=selected_evidence,
        facts=selected_facts,
        current_date=current_date,
        active_sources=active_sources,
        transition_preview=transition_preview or (lambda _request: None),
    )


def test_simple_symbol_continuation_requires_regulator_listing_and_eligible_preview():
    preview_calls = []

    def preview(request):
        preview_calls.append(request)
        return {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": "symbol_continuation",
        }

    decision = _evaluate(transition_preview=preview)

    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "transition_eligible"
    assert decision.relevance == "direct_tracked_security"
    assert decision.confidence == "high"
    assert decision.outcomes == ("symbol_changed", "venue_transfer")
    assert decision.successor_ticker == "HAPN"
    assert decision.destination_venue == "NASDAQ"
    assert decision.effective_date == "2026-06-27"
    assert decision.rule_id == "lifecycle.simple_symbol_continuation"
    assert decision.rule_version == "1"
    assert decision.decision_issues == ()
    assert decision.transition_requested is True
    assert preview_calls == [
        {
            "transition_kind": "symbol_continuation",
            "source_ticker": "LC",
            "successor_ticker": "HAPN",
            "effective_date": "2026-06-27",
            "outcomes": ("symbol_changed", "venue_transfer"),
        }
    ]

    no_listing = _evaluate(
        evidence=(_evidence("sec", "regulator"),),
        facts=tuple(fact for fact in _identity_facts() if fact["evidence_id"] == "sec"),
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("preview must not run")
        ),
    )
    assert no_listing.decision_tier == "review_suggested"
    assert no_listing.action_readiness == "action_blocked"
    assert "listing_active_missing" in no_listing.decision_issues
    assert no_listing.transition_requested is False

    ineligible = _evaluate(
        transition_preview=lambda _request: {
            "eligible": False,
            "block_reasons": ("successor_hidden",),
            "transition_kind": "symbol_continuation",
        }
    )
    assert ineligible.decision_tier == "review_suggested"
    assert ineligible.action_readiness == "action_blocked"
    assert ineligible.decision_issues == ("preview:successor_hidden",)


def test_ambiguous_ibkr_recency_is_inert_when_listing_authority_is_current():
    valid_market = {
        **_evidence("ibkr-valid", "market_infrastructure"),
        "retrieved_at": "2026-08-25T01:02:03Z",
    }
    unknown_time_market = _evidence("ibkr-unknown", "market_infrastructure")
    unknown_time_market["source_locator"]["market_data"].pop("retrieved_at")
    ibkr_facts = tuple(
        {
            **fact,
            "evidence_id": (
                "ibkr-valid" if fact["evidence_id"] == "ibkr" else fact["evidence_id"]
            ),
        }
        for fact in _identity_facts()
        if fact["evidence_id"] == "ibkr"
    )
    fixture = _listing_fixture("nms_symbol_continuation")

    decision = _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"]
        + (
            valid_market,
            unknown_time_market,
        ),
        facts=fixture["facts"] + ibkr_facts,
        transition_preview=_eligible_preview,
    )

    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "transition_eligible"
    assert decision.transition_requested is True


def test_latest_equal_time_agreeing_positive_ibkr_receipts_are_all_preserved():
    from src.security_lifecycle_decision_policy import (
        _current_decision_material,
        _evidence_rows,
        _fact_rows,
    )

    evidence = _evidence_rows(
        (
            _evidence("sec", "regulator"),
            {
                **_evidence("ibkr-a", "market_infrastructure"),
                "retrieved_at": "2026-08-25T01:02:03Z",
            },
            {
                **_evidence("ibkr-b", "market_infrastructure"),
                "retrieved_at": "2026-08-25T01:02:03Z",
            },
        )
    )
    facts = _fact_rows(
        (
            _fact("sec", "issuer_cik", _CIK),
            _fact("ibkr-a", "successor_ticker", "HAPN"),
            _fact("ibkr-b", "successor_ticker", "HAPN"),
        ),
        evidence,
    )

    current_evidence, current_facts = _current_decision_material(evidence, facts)

    assert [row.evidence_id for row in current_evidence] == [
        "ibkr-a",
        "ibkr-b",
        "sec",
    ]
    assert [(row.evidence_id, row.fact_type) for row in current_facts] == [
        ("sec", "issuer_cik"),
        ("ibkr-a", "successor_ticker"),
        ("ibkr-b", "successor_ticker"),
    ]


@pytest.mark.parametrize(
    ("fact_type", "disagreeing_value"),
    (
        ("successor_ticker", "OTHER"),
        ("security_class", "preferred_stock"),
        ("destination_venue", "NYSE"),
    ),
)
def test_latest_equal_time_disagreeing_positive_ibkr_receipts_fail_closed(
    fact_type, disagreeing_value
):
    fixture = _listing_fixture("nms_symbol_continuation")
    receipts = tuple(
        {
            **_evidence(evidence_id, "market_infrastructure"),
            "retrieved_at": "2026-08-25T01:02:03Z",
        }
        for evidence_id in ("ibkr-a", "ibkr-b")
    )
    agreeing = {
        "successor_ticker": "NEW",
        "security_class": "common_stock",
        "destination_venue": "NASDAQ",
    }
    ibkr_facts = tuple(
        _fact(
            evidence_id,
            name,
            disagreeing_value
            if evidence_id == "ibkr-b" and name == fact_type
            else value,
        )
        for evidence_id in ("ibkr-a", "ibkr-b")
        for name, value in agreeing.items()
    )

    decision = _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"] + receipts,
        facts=fixture["facts"] + ibkr_facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("disagreeing tied receipts must not preview")
        ),
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.outcomes == ("undetermined",)
    assert decision.decision_issues == (f"source_conflict:{fact_type}",)
    assert decision.transition_requested is False


def test_case_already_keyed_by_successor_accepts_without_a_to_a_transition():
    decision = _evaluate(
        case=_case(ticker="HAPN"),
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("A-to-A preview must not run")
        ),
    )

    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "not_applicable"
    assert decision.successor_ticker == "HAPN"
    assert decision.rule_id == "lifecycle.simple_symbol_continuation"
    assert decision.transition_requested is False


def test_retained_old_listing_source_role_is_not_aligned_as_current_destination():
    from src.security_lifecycle_decision_policy import (
        _evidence_rows,
        _fact_rows,
        _facts_with_current_listing_destination_role,
    )

    retained_old, retained_old_facts = _active_listing(
        "nasdaq-old-source",
        "OLD",
        venue="NYSE",
        current_ticker="OLD",
        retrieved_at="2026-08-24T01:02:03Z",
    )
    current_nasdaq, current_nasdaq_facts = _active_listing(
        "nasdaq-current",
        "NEW",
        current_ticker="NEW",
    )
    current_massive, current_massive_facts = _active_listing(
        "massive-current",
        "NEW",
        adapter="massive_reference",
        current_ticker="NEW",
        cik=_CIK,
    )
    evidence = (
        _evidence("sec", "regulator"),
        retained_old,
        current_nasdaq,
        current_massive,
    )
    facts = (
        _identity_facts(
            source="OLD",
            successor="NEW",
            source_venue="NYSE",
            destination_venue="NASDAQ",
        )[:7]
        + retained_old_facts
        + current_nasdaq_facts
        + current_massive_facts
    )
    evidence_rows = _evidence_rows(evidence)
    fact_rows = _fact_rows(facts, evidence_rows)

    aligned = _facts_with_current_listing_destination_role(fact_rows, "NEW")
    aligned_types = {
        (row.evidence_id, row.fact_type, row.value)
        for row in aligned
        if row.source_family == "listing_authority"
    }
    assert ("nasdaq-old-source", "source_ticker", "OLD") in aligned_types
    assert ("nasdaq-old-source", "source_venue", "NYSE") in aligned_types
    assert ("nasdaq-old-source", "successor_ticker", "OLD") not in aligned_types
    for evidence_id in ("nasdaq-current", "massive-current"):
        assert (evidence_id, "successor_ticker", "NEW") in aligned_types
        assert (evidence_id, "destination_venue", "NASDAQ") in aligned_types

    decision = _evaluate(
        case=_case(ticker="NEW"),
        evidence=evidence,
        facts=facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("already-keyed successor must not preview")
        ),
    )

    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "not_applicable"
    assert decision.decision_issues == ()
    assert decision.successor_ticker == "NEW"
    assert decision.destination_venue == "NASDAQ"
    assert decision.transition_requested is False


def test_venue_transfer_accepts_ordinary_nasdaq_listing_without_security_class():
    facts = _identity_facts(source="QBTS", successor="QBTS")[:7]
    listing, listing_facts = _active_listing(
        "nasdaq-qbts", "QBTS", current_ticker="QBTS"
    )
    assert all(fact["fact_type"] != "security_class" for fact in listing_facts)
    decision = _evaluate(
        case=_case(ticker="QBTS"),
        evidence=(_evidence("sec", "regulator"), listing),
        facts=facts + listing_facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("venue transfer must not preview a ticker mutation")
        ),
    )

    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "not_applicable"
    assert decision.outcomes == ("venue_transfer",)
    assert decision.rule_id == "lifecycle.venue_transfer"
    assert decision.successor_ticker == "QBTS"
    assert decision.destination_venue == "NASDAQ"
    assert decision.transition_requested is False
    assert "keep tracking" in decision.impact_summary.lower()


def test_no_identity_change_accepts_ordinary_nasdaq_listing_without_security_class():
    transaction = {
        "kind": "asset_acquisition",
        "terms_status": "complete",
        "counterparty_name": "Example Assets LLC",
        "counterparty_ticker": None,
        "counterparty_cik": None,
    }
    facts = (
        _fact("sec", "source_ticker", "BLBD"),
        _fact("sec", "issuer_cik", "0001589526"),
        _fact("sec", "security_class", "common_stock"),
        _fact("sec", "transaction_structure", transaction),
        _fact("sec", "tracked_security_effect", "no_identity_change"),
    )
    listing, listing_facts = _active_listing(
        "nasdaq-blbd",
        "BLBD",
        cik="0001589526",
        current_ticker="BLBD",
    )
    assert all(fact["fact_type"] != "security_class" for fact in listing_facts)
    decision = _evaluate(
        case={**_case(ticker="BLBD", kinds=("merger_agreement",)), "cik": "0001589526"},
        evidence=(_evidence("sec", "regulator"), listing),
        facts=facts + listing_facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("no-change decision must not preview a transition")
        ),
    )

    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "not_applicable"
    assert decision.relevance == "issuer_related"
    assert decision.outcomes == ("no_tracked_security_change",)
    assert decision.counterparty_name == "Example Assets LLC"
    assert decision.rule_id == "lifecycle.no_identity_change"
    assert decision.transition_requested is False


def test_missing_regulator_security_class_is_typed_and_never_previews():
    fixture = _listing_fixture("nms_symbol_continuation")
    facts = tuple(
        fact
        for fact in fixture["facts"]
        if not (fact["evidence_id"] == "sec" and fact["fact_type"] == "security_class")
    )

    decision = _evaluate(
        case=fixture["case"],
        evidence=fixture["evidence"],
        facts=facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("missing SEC class must fail before preview")
        ),
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.decision_issues == ("regulator_security_class_missing",)
    assert decision.transition_requested is False


def test_positive_listing_security_class_conflict_fails_before_preview():
    fixture = _listing_fixture("nms_symbol_continuation")
    listing, listing_facts = _active_listing(
        "nasdaq-etf",
        "NEW",
        security_class="exchange_traded_fund",
    )

    decision = _evaluate(
        case=fixture["case"],
        evidence=(_evidence("sec", "regulator"), listing),
        facts=tuple(fact for fact in fixture["facts"] if fact["evidence_id"] == "sec")
        + listing_facts,
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("conflicting positive class must fail before preview")
        ),
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.decision_issues == ("listing_authority_conflict",)
    assert decision.transition_requested is False


def test_terminal_delisting_separates_conclusion_from_action_readiness():
    regulator_evidence = {
        **_evidence("sec", "regulator"),
        "source_locator": {"filing_chain_complete": True},
    }
    regulator_facts = (
        _fact("sec", "source_ticker", "OLD"),
        _fact("sec", "effective_date", "2026-09-01"),
        _fact("sec", "security_class", "common_stock"),
        _fact("sec", "issuer_cik", _CIK),
        _fact("sec", "tracked_security_effect", "terminal_delisting"),
    )
    massive, massive_facts = _massive_inactive("massive-inactive", "OLD")
    terminal_authority = (
        _not_found_listing("nasdaq-listed", "OLD", directory="nasdaq_listed"),
        _not_found_listing("nasdaq-other", "OLD", directory="other_listed"),
        massive,
    )
    before = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(regulator_evidence,),
        facts=regulator_facts,
        current_date=date(2026, 8, 31),
    )
    assert before.decision_tier == "verified_automatic"
    assert before.action_readiness == "waiting_effective_date"
    assert before.outcomes == ("undetermined",)
    assert before.transition_requested is False

    after = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(regulator_evidence,),
        facts=regulator_facts,
        current_date=date(2026, 9, 1),
    )
    assert after.decision_tier == "verified_automatic"
    assert after.action_readiness == "waiting_market_confirmation"
    assert after.transition_requested is False

    confirmed = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(
            regulator_evidence,
            *terminal_authority,
            {
                **_evidence("news", "publisher"),
                "source_locator": {"last": "12.57"},
            },
            {
                **_evidence("ibkr", "market_infrastructure"),
                "source_locator": {"contract_status": "missing"},
            },
        ),
        facts=regulator_facts + massive_facts,
        current_date=date(2026, 9, 1),
        active_sources=("manual_lists",),
        transition_preview=lambda _request: {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": "terminal_delisting",
        },
    )
    assert confirmed.decision_tier == "verified_automatic"
    assert confirmed.action_readiness == "transition_eligible"
    assert confirmed.rule_id == "lifecycle.terminal_delisting"
    assert confirmed.transition_requested is True

    frozen_contract = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(
            regulator_evidence,
            *terminal_authority,
            {
                **_evidence("ibkr", "market_infrastructure"),
                "source_locator": {
                    "contract_status": "found",
                    "market_data": {
                        "status": "frozen",
                        "last": "12.57",
                        "provider_time": "2026-09-01T00:00:00Z",
                        "retrieved_at": "2026-09-01T00:01:00Z",
                        "fresh": False,
                    },
                },
            },
        ),
        facts=regulator_facts + massive_facts,
        current_date=date(2026, 9, 1),
        transition_preview=lambda request: {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": request["transition_kind"],
        },
    )
    assert frozen_contract.decision_tier == "verified_automatic"
    assert frozen_contract.action_readiness == "transition_eligible"
    assert frozen_contract.transition_requested is True

    portfolio_open = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(
            regulator_evidence,
            *terminal_authority,
            {
                **_evidence("ibkr", "market_infrastructure"),
                "source_locator": {"contract_status": "missing"},
            },
        ),
        facts=regulator_facts + massive_facts,
        current_date=date(2026, 9, 1),
        active_sources=("portfolio_open",),
    )
    assert portfolio_open.decision_tier == "verified_automatic"
    assert portfolio_open.action_readiness == "action_blocked"
    assert portfolio_open.outcomes == ("undetermined",)
    assert portfolio_open.decision_issues == ("portfolio_position_open",)

    preview_blocked = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(regulator_evidence, *terminal_authority),
        facts=regulator_facts + massive_facts,
        current_date=date(2026, 9, 1),
        transition_preview=lambda request: {
            "eligible": False,
            "block_reasons": ("successor_hidden",),
            "transition_kind": request["transition_kind"],
        },
    )
    assert preview_blocked.decision_tier == "verified_automatic"
    assert preview_blocked.action_readiness == "action_blocked"
    assert preview_blocked.outcomes == ("undetermined",)
    assert preview_blocked.decision_issues == ("preview:successor_hidden",)
    assert preview_blocked.transition_requested is False


def test_ma_structures_are_review_suggested_with_complete_prefill():
    structures = {
        "cash": "acquisition_cash",
        "stock": "acquisition_stock",
        "mixed": "acquisition_mixed",
        "unknown": "acquisition_terms_unknown",
        "asset_acquisition": "acquisition_terms_unknown",
        "spin_off": "issuer_security_change",
        "security_class_change": "issuer_security_change",
    }
    for structure, outcome in structures.items():
        terms = {
            "kind": structure,
            "terms_status": "complete",
            "counterparty_name": "Buyer Corp.",
            "counterparty_ticker": "BUY",
            "counterparty_cik": "0000000123",
            "consideration_currency": "USD",
            "cash_per_security_decimal": "12.50",
            "exchange_ratio_decimal": "0.75",
        }
        decision = _evaluate(
            case=_case(ticker="TGT", kinds=("merger_agreement",)),
            evidence=(_evidence("sec", "regulator"),),
            facts=(
                _fact("sec", "source_ticker", "TGT"),
                _fact("sec", "issuer_cik", _CIK),
                _fact("sec", "transaction_structure", terms),
            ),
        )
        assert decision.decision_tier == "review_suggested"
        assert decision.action_readiness == "action_blocked"
        assert decision.outcomes == (outcome,)
        assert decision.counterparty_name == "Buyer Corp."
        assert decision.counterparty_ticker == "BUY"
        assert decision.counterparty_cik == "0000000123"
        assert decision.consideration_currency == "USD"
        assert decision.cash_per_security_decimal == "12.50"
        assert decision.exchange_ratio_decimal == "0.75"
        assert decision.rule_id == "lifecycle.ma_review"
        assert decision.transition_requested is False

    not_extracted = _evaluate(
        case=_case(ticker="TGT", kinds=("merger_agreement",)),
        evidence=(_evidence("sec", "regulator"),),
        facts=(
            _fact("sec", "source_ticker", "TGT"),
            _fact("sec", "issuer_cik", _CIK),
            _fact(
                "sec",
                "transaction_structure",
                {"kind": "asset_acquisition", "terms_status": "not_extracted"},
            ),
        ),
    )
    assert not_extracted.decision_tier == "review_suggested"
    assert not_extracted.counterparty_name is None
    assert not_extracted.cash_per_security_decimal is None
    assert "transaction_terms_not_extracted" in not_extracted.decision_issues
    assert "not deterministically extracted" in not_extracted.impact_summary


def test_conflicting_facts_are_review_suggested_and_never_majority_resolved():
    facts = _identity_facts() + (
        _fact("second-sec", "successor_ticker", "OTHER"),
        _fact("third-sec", "successor_ticker", "HAPN"),
    )
    decision = _evaluate(
        evidence=(
            _evidence("sec", "regulator"),
            _evidence("second-sec", "regulator"),
            _evidence("third-sec", "regulator"),
            _evidence("ibkr", "market_infrastructure"),
        ),
        facts=facts,
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.rule_id == "lifecycle.source_conflict"
    assert decision.decision_issues == ("source_conflict:successor_ticker",)
    assert decision.successor_ticker is None
    assert decision.transition_requested is False


def test_publisher_and_manual_evidence_never_authorize_identity_mutation():
    facts = tuple(
        {**fact, "evidence_id": "news"}
        for fact in _identity_facts()
        if fact["evidence_id"] == "sec"
    )
    decision = _evaluate(
        evidence=(
            _evidence("news", "publisher"),
            _evidence("manual", "manual"),
        ),
        facts=facts + (_fact("manual", "successor_ticker", "HAPN"),),
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("non-authoritative evidence must not preview a mutation")
        ),
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.rule_id == "lifecycle.insufficient_identity_facts"
    assert "regulator_identity_facts_missing" in decision.decision_issues
    assert decision.transition_requested is False


def test_policy_output_is_deterministic_and_uses_closed_rule_identity():
    from src.security_lifecycle_decision_policy import (
        AUTOMATION_POLICY_VERSION,
        RULE_VERSIONS,
    )

    fixture = _listing_fixture("nms_symbol_continuation")
    evidence = fixture["evidence"]
    facts = fixture["facts"]
    preview = lambda _request: {
        "eligible": True,
        "block_reasons": (),
        "transition_kind": "symbol_continuation",
    }

    first = _evaluate(
        case=fixture["case"],
        evidence=evidence,
        facts=facts,
        transition_preview=preview,
    )
    second = _evaluate(
        case=fixture["case"],
        evidence=tuple(reversed(evidence)),
        facts=tuple(reversed(facts)),
        transition_preview=preview,
    )

    assert first == second
    assert AUTOMATION_POLICY_VERSION == "trusted-lifecycle-automation-v4"
    assert RULE_VERSIONS == {
        "lifecycle.insufficient_identity_facts": "1",
        "lifecycle.ma_review": "1",
        "lifecycle.no_identity_change": "1",
        "lifecycle.simple_symbol_continuation": "1",
        "lifecycle.source_conflict": "1",
        "lifecycle.terminal_delisting": "1",
        "lifecycle.venue_transfer": "1",
    }


def test_missing_regulator_facts_do_not_invent_a_conclusion():
    decision = _evaluate(
        evidence=(_evidence("ibkr", "market_infrastructure"),),
        facts=(
            _fact("ibkr", "successor_ticker", "HAPN"),
            _fact("ibkr", "destination_venue", "NASDAQ"),
        ),
    )

    assert decision.decision_tier == "review_suggested"
    assert decision.action_readiness == "action_blocked"
    assert decision.relevance == "undetermined"
    assert decision.confidence == "unknown"
    assert decision.outcomes == ("undetermined",)
    assert decision.successor_ticker is None
    assert decision.destination_venue is None
    assert decision.rule_id == "lifecycle.insufficient_identity_facts"
    assert decision.decision_issues == ("regulator_identity_facts_missing",)
    assert decision.transition_requested is False
