from __future__ import annotations

from datetime import date


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
    return {"evidence_id": evidence_id, "source_family": family}


def _fact(evidence_id, fact_type, value):
    return {
        "evidence_id": evidence_id,
        "fact_type": fact_type,
        "normalized_value": value,
    }


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

    return evaluate_automation_decision(
        case=case or _case(),
        evidence=evidence
        or (_evidence("sec", "regulator"), _evidence("ibkr", "market_infrastructure")),
        facts=facts or _identity_facts(),
        current_date=current_date,
        active_sources=active_sources,
        transition_preview=transition_preview or (lambda _request: None),
    )


def test_simple_symbol_continuation_requires_regulator_market_and_eligible_preview():
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

    no_market = _evaluate(
        evidence=(_evidence("sec", "regulator"),),
        facts=tuple(fact for fact in _identity_facts() if fact["evidence_id"] == "sec"),
        transition_preview=lambda _request: (_ for _ in ()).throw(
            AssertionError("preview must not run")
        ),
    )
    assert no_market.decision_tier == "review_suggested"
    assert no_market.action_readiness == "action_blocked"
    assert "market_corroboration_missing" in no_market.decision_issues
    assert no_market.transition_requested is False

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


def test_venue_transfer_is_verified_non_mutating_and_keeps_tracking():
    facts = _identity_facts(source="QBTS", successor="QBTS")
    decision = _evaluate(
        case=_case(ticker="QBTS"),
        facts=facts,
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


def test_explicit_no_identity_change_resolves_without_transition():
    transaction = {
        "kind": "asset_acquisition",
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
    decision = _evaluate(
        case={**_case(ticker="BLBD", kinds=("merger_agreement",)), "cik": "0001589526"},
        evidence=(_evidence("sec", "regulator"),),
        facts=facts,
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
    before = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(regulator_evidence,),
        facts=regulator_facts,
        current_date=date(2026, 8, 31),
    )
    assert before.decision_tier == "verified_automatic"
    assert before.action_readiness == "waiting_effective_date"
    assert before.outcomes == ("listing_ended",)
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
            {
                **_evidence("ibkr", "market_infrastructure"),
                "source_locator": {"contract_status": "missing"},
            },
        ),
        facts=regulator_facts,
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

    portfolio_open = _evaluate(
        case=_case(ticker="OLD", kinds=("listing_removal_notice",)),
        evidence=(
            regulator_evidence,
            {
                **_evidence("ibkr", "market_infrastructure"),
                "source_locator": {"contract_status": "missing"},
            },
        ),
        facts=regulator_facts,
        current_date=date(2026, 9, 1),
        active_sources=("portfolio_open",),
    )
    assert portfolio_open.decision_tier == "verified_automatic"
    assert portfolio_open.action_readiness == "action_blocked"
    assert portfolio_open.decision_issues == ("portfolio_position_open",)


def test_ma_structures_are_review_suggested_with_complete_prefill():
    structures = {
        "cash": "acquisition_cash",
        "stock": "acquisition_stock",
        "mixed": "acquisition_mixed",
        "unknown": "acquisition_terms_unknown",
        "asset_acquisition": "acquisition_terms_unknown",
        "future_structure": "acquisition_terms_unknown",
        "spin_off": "issuer_security_change",
        "security_class_change": "issuer_security_change",
    }
    for structure, outcome in structures.items():
        terms = {
            "kind": structure,
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

    evidence = (
        _evidence("sec", "regulator"),
        _evidence("ibkr", "market_infrastructure"),
    )
    facts = _identity_facts()
    preview = lambda _request: {
        "eligible": True,
        "block_reasons": (),
        "transition_kind": "symbol_continuation",
    }

    first = _evaluate(evidence=evidence, facts=facts, transition_preview=preview)
    second = _evaluate(
        evidence=tuple(reversed(evidence)),
        facts=tuple(reversed(facts)),
        transition_preview=preview,
    )

    assert first == second
    assert AUTOMATION_POLICY_VERSION == "trusted-lifecycle-automation-v1"
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
