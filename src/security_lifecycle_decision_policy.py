"""Pure decision policy for cited security-lifecycle facts."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from src.security_lifecycle_fact_kernel import normalize_automation_fact_value


AUTOMATION_POLICY_VERSION = "trusted-lifecycle-automation-v3"
RULE_VERSIONS = {
    "lifecycle.insufficient_identity_facts": "1",
    "lifecycle.ma_review": "1",
    "lifecycle.no_identity_change": "1",
    "lifecycle.simple_symbol_continuation": "1",
    "lifecycle.source_conflict": "1",
    "lifecycle.terminal_delisting": "1",
    "lifecycle.venue_transfer": "1",
}

_MA_OUTCOMES = {
    "cash": "acquisition_cash",
    "stock": "acquisition_stock",
    "mixed": "acquisition_mixed",
    "unknown": "acquisition_terms_unknown",
    "asset_acquisition": "acquisition_terms_unknown",
    "spin_off": "issuer_security_change",
    "security_class_change": "issuer_security_change",
}


@dataclass(frozen=True)
class AutomationDecision:
    decision_tier: Literal["verified_automatic", "review_suggested"]
    action_readiness: Literal[
        "not_applicable",
        "waiting_effective_date",
        "waiting_market_confirmation",
        "transition_eligible",
        "action_blocked",
    ]
    relevance: str
    confidence: str
    outcomes: tuple[str, ...]
    conclusion: str
    impact_summary: str
    successor_ticker: str | None
    destination_venue: str | None
    effective_date: str | None
    counterparty_name: str | None
    counterparty_ticker: str | None
    counterparty_cik: str | None
    consideration_currency: str | None
    cash_per_security_decimal: str | None
    exchange_ratio_decimal: str | None
    rule_id: str
    rule_version: str
    decision_issues: tuple[str, ...]
    transition_requested: bool


@dataclass(frozen=True)
class _Evidence:
    evidence_id: str
    source_family: str
    source_locator: Mapping[str, Any]


@dataclass(frozen=True)
class _Fact:
    evidence_id: str
    source_family: str
    fact_type: str
    value: Any
    canonical_value: str


def _field(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _text(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _ticker(value: object) -> str | None:
    result = _text(value)
    return None if result is None else result.upper()


def _venue(value: object) -> str | None:
    result = _text(value)
    return None if result is None else result.upper()


def _cik(value: object) -> str | None:
    result = _text(value)
    if result is None or not result.isdigit() or len(result) > 10:
        return None
    return result.zfill(10)


def _iso_date(value: object) -> str | None:
    result = _text(value)
    if result is None:
        return None
    try:
        return date.fromisoformat(result).isoformat()
    except ValueError:
        return None


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalized_fact_value(fact_type: str, value: Any) -> Any:
    value = normalize_automation_fact_value(fact_type, value)
    if fact_type in {"source_ticker", "successor_ticker"}:
        return _ticker(value)
    if fact_type in {"source_venue", "destination_venue"}:
        return _venue(value)
    if fact_type == "issuer_cik":
        return _cik(value)
    if fact_type == "effective_date":
        return _iso_date(value)
    if fact_type in {"security_class", "tracked_security_effect"}:
        result = _text(value)
        return None if result is None else result.lower()
    return value


def _locator(value: object) -> Mapping[str, Any]:
    raw = _field(value, "source_locator")
    if raw is None:
        raw = _field(value, "source_locator_json")
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("evidence_source_locator") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("evidence_source_locator")
    return dict(raw)


def _evidence_rows(values: Iterable[object]) -> tuple[_Evidence, ...]:
    rows: dict[str, _Evidence] = {}
    for value in values:
        evidence_id = _text(
            _field(value, "evidence_id", _field(value, "local_id"))
        )
        family = _text(_field(value, "source_family"))
        if evidence_id is None or family is None:
            raise ValueError("evidence_identity")
        row = _Evidence(evidence_id, family, _locator(value))
        if evidence_id in rows and rows[evidence_id] != row:
            raise ValueError("duplicate_evidence_identity")
        rows[evidence_id] = row
    return tuple(rows[key] for key in sorted(rows))


def _fact_value(value: object) -> Any:
    raw = _field(value, "normalized_value", None)
    if raw is not None:
        return raw
    raw_json = _field(value, "normalized_value_json", None)
    if raw_json is None:
        raw = _field(value, "value", None)
        if raw is None:
            raise ValueError("fact_normalized_value")
        return raw
    try:
        return json.loads(str(raw_json))
    except json.JSONDecodeError as exc:
        raise ValueError("fact_normalized_value") from exc


def _fact_rows(
    values: Iterable[object],
    evidence: tuple[_Evidence, ...],
) -> tuple[_Fact, ...]:
    families = {row.evidence_id: row.source_family for row in evidence}
    rows: list[_Fact] = []
    for item in values:
        evidence_id = _text(
            _field(item, "evidence_id", _field(item, "local_evidence_id"))
        )
        fact_type = _text(_field(item, "fact_type"))
        if evidence_id not in families or fact_type is None:
            raise ValueError("fact_evidence_identity")
        normalized = _normalized_fact_value(fact_type, _fact_value(item))
        if normalized is None:
            raise ValueError("fact_normalized_value")
        rows.append(
            _Fact(
                evidence_id=evidence_id,
                source_family=families[evidence_id],
                fact_type=fact_type,
                value=normalized,
                canonical_value=_canonical(normalized),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.fact_type,
                row.canonical_value,
                row.source_family,
                row.evidence_id,
            ),
        )
    )


def _values(
    facts: tuple[_Fact, ...],
    fact_type: str,
    *,
    family: str | None = None,
) -> tuple[Any, ...]:
    found = {
        row.canonical_value: row.value
        for row in facts
        if row.fact_type == fact_type
        and (family is None or row.source_family == family)
    }
    return tuple(found[key] for key in sorted(found))


def _one(
    facts: tuple[_Fact, ...],
    fact_type: str,
    *,
    family: str | None = None,
) -> Any:
    found = _values(facts, fact_type, family=family)
    return found[0] if len(found) == 1 else None


def _conflicts(facts: tuple[_Fact, ...]) -> tuple[str, ...]:
    return tuple(
        fact_type
        for fact_type in sorted({row.fact_type for row in facts})
        if len(_values(facts, fact_type)) > 1
    )


def _terms(value: object) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("fact_value_shape")
    return value


def _term(terms: Mapping[str, Any], name: str) -> str | None:
    return _text(terms.get(name))


def _decision(
    *,
    decision_tier: Literal["verified_automatic", "review_suggested"],
    action_readiness: Literal[
        "not_applicable",
        "waiting_effective_date",
        "waiting_market_confirmation",
        "transition_eligible",
        "action_blocked",
    ],
    relevance: str,
    confidence: str,
    outcomes: tuple[str, ...],
    conclusion: str,
    impact_summary: str,
    rule_id: str,
    successor_ticker: str | None = None,
    destination_venue: str | None = None,
    effective_date: str | None = None,
    terms: Mapping[str, Any] | None = None,
    decision_issues: Iterable[str] = (),
    transition_requested: bool = False,
) -> AutomationDecision:
    transaction = terms or {}
    return AutomationDecision(
        decision_tier=decision_tier,
        action_readiness=action_readiness,
        relevance=relevance,
        confidence=confidence,
        outcomes=outcomes,
        conclusion=conclusion,
        impact_summary=impact_summary,
        successor_ticker=successor_ticker,
        destination_venue=destination_venue,
        effective_date=effective_date,
        counterparty_name=_term(transaction, "counterparty_name"),
        counterparty_ticker=_ticker(transaction.get("counterparty_ticker")),
        counterparty_cik=_cik(transaction.get("counterparty_cik")),
        consideration_currency=(
            _text(transaction.get("consideration_currency")) or None
        ),
        cash_per_security_decimal=_term(
            transaction, "cash_per_security_decimal"
        ),
        exchange_ratio_decimal=_term(transaction, "exchange_ratio_decimal"),
        rule_id=rule_id,
        rule_version=RULE_VERSIONS[rule_id],
        decision_issues=tuple(sorted(set(decision_issues))),
        transition_requested=transition_requested,
    )


def _insufficient(*, issues: Iterable[str]) -> AutomationDecision:
    return _decision(
        decision_tier="review_suggested",
        action_readiness="action_blocked",
        relevance="undetermined",
        confidence="unknown",
        outcomes=("undetermined",),
        conclusion="Available evidence does not establish the tracked security outcome.",
        impact_summary="Review the cited evidence and missing identity facts.",
        rule_id="lifecycle.insufficient_identity_facts",
        decision_issues=issues,
    )


def _preview(
    evaluator: Callable[[Mapping[str, object]], Mapping[str, object] | None],
    request: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    result = evaluator(request)
    if not isinstance(result, Mapping):
        return False, ("preview:unavailable",)
    expected_kind = request["transition_kind"]
    if result.get("transition_kind") != expected_kind:
        return False, ("preview:kind_mismatch",)
    reasons = tuple(
        sorted(
            {
                str(value)
                for value in result.get("block_reasons", ())
                if str(value)
            }
        )
    )
    if result.get("eligible") is True and not reasons:
        return True, ()
    return False, tuple(f"preview:{reason}" for reason in reasons) or (
        "preview:ineligible",
    )


def _regulator_chain_complete(evidence: tuple[_Evidence, ...]) -> bool:
    return any(
        row.source_family == "regulator"
        and row.source_locator.get("filing_chain_complete") is True
        for row in evidence
    )


def _market_contract_missing(evidence: tuple[_Evidence, ...]) -> bool:
    return any(
        row.source_family == "market_infrastructure"
        and row.source_locator.get("contract_status") == "missing"
        for row in evidence
    )


def evaluate_automation_decision(
    *,
    case: Mapping[str, object],
    evidence: Iterable[object],
    facts: Iterable[object],
    current_date: date | str,
    active_sources: Iterable[str],
    transition_preview: Callable[
        [Mapping[str, object]], Mapping[str, object] | None
    ],
) -> AutomationDecision:
    """Evaluate cited facts without opening a database, provider, or model."""

    evidence_rows = _evidence_rows(evidence)
    fact_rows = _fact_rows(facts, evidence_rows)
    case_ticker = _ticker(case.get("ticker"))
    case_cik = _cik(case.get("cik"))
    if case_ticker is None:
        return _insufficient(issues=("case_ticker_missing",))
    if isinstance(current_date, str):
        try:
            today = date.fromisoformat(current_date)
        except ValueError as exc:
            raise ValueError("current_date") from exc
    elif isinstance(current_date, date):
        today = current_date
    else:
        raise ValueError("current_date")
    sources = frozenset(str(value) for value in active_sources)

    conflicts = _conflicts(fact_rows)
    if conflicts:
        return _decision(
            decision_tier="review_suggested",
            action_readiness="action_blocked",
            relevance="direct_tracked_security",
            confidence="low",
            outcomes=("undetermined",),
            conclusion="Current cited sources contain incompatible identity facts.",
            impact_summary="No value was selected by source count or confidence.",
            successor_ticker=(
                None
                if "successor_ticker" in conflicts
                else _one(fact_rows, "successor_ticker")
            ),
            destination_venue=(
                None
                if "destination_venue" in conflicts
                else _one(fact_rows, "destination_venue")
            ),
            effective_date=(
                None
                if "effective_date" in conflicts
                else _one(fact_rows, "effective_date")
            ),
            rule_id="lifecycle.source_conflict",
            decision_issues=(
                f"source_conflict:{fact_type}" for fact_type in conflicts
            ),
        )

    regulator_source = _one(fact_rows, "source_ticker", family="regulator")
    regulator_successor = _one(
        fact_rows, "successor_ticker", family="regulator"
    )
    regulator_source_venue = _one(
        fact_rows, "source_venue", family="regulator"
    )
    regulator_destination = _one(
        fact_rows, "destination_venue", family="regulator"
    )
    regulator_date = _one(fact_rows, "effective_date", family="regulator")
    regulator_class = _one(fact_rows, "security_class", family="regulator")
    regulator_cik = _one(fact_rows, "issuer_cik", family="regulator")
    regulator_effect = _one(
        fact_rows, "tracked_security_effect", family="regulator"
    )
    transaction = _terms(
        _one(fact_rows, "transaction_structure", family="regulator")
    )
    transaction_kind = _text(transaction.get("kind"))
    terms_status = _text(transaction.get("terms_status"))
    if terms_status == "not_extracted":
        transaction_issues = ("transaction_terms_not_extracted",)
        transaction_impact = (
            "Counterparty and consideration terms were not deterministically extracted."
        )
    elif terms_status == "partial":
        transaction_issues = ("transaction_terms_partial",)
        transaction_impact = (
            "Only some counterparty or consideration terms were deterministically extracted."
        )
    else:
        transaction_issues = ()
        transaction_impact = "Known transaction terms are prefilled."

    if regulator_effect == "terminal_delisting":
        missing = []
        if regulator_source is None:
            missing.append("regulator_source_ticker_missing")
        if regulator_date is None:
            missing.append("regulator_effective_date_missing")
        if regulator_class is None:
            missing.append("regulator_security_class_missing")
        if regulator_cik is None or case_cik is None:
            missing.append("regulator_issuer_cik_missing")
        elif regulator_cik != case_cik:
            missing.append("issuer_cik_mismatch")
        if regulator_source != case_ticker:
            missing.append("case_ticker_mismatch")
        if regulator_successor is not None:
            missing.append("successor_present")
        if not _regulator_chain_complete(evidence_rows):
            missing.append("regulator_filing_chain_incomplete")
        if missing:
            return _insufficient(issues=missing)

        assert regulator_date is not None
        if today < date.fromisoformat(regulator_date):
            readiness = "waiting_effective_date"
            issues: tuple[str, ...] = ()
            requested = False
        elif not _market_contract_missing(evidence_rows):
            readiness = "waiting_market_confirmation"
            issues = ()
            requested = False
        elif "portfolio_open" in sources:
            readiness = "action_blocked"
            issues = ("portfolio_position_open",)
            requested = False
        else:
            request = {
                "transition_kind": "terminal_delisting",
                "source_ticker": regulator_source,
                "successor_ticker": None,
                "effective_date": regulator_date,
                "outcomes": ("listing_ended",),
            }
            eligible, issues = _preview(transition_preview, request)
            readiness = "transition_eligible" if eligible else "action_blocked"
            requested = eligible
        return _decision(
            decision_tier="verified_automatic",
            action_readiness=readiness,
            relevance="direct_tracked_security",
            confidence="high",
            outcomes=("listing_ended",),
            conclusion=(
                f"The cited regulator record ends listing of {regulator_source} "
                f"effective {regulator_date}."
            ),
            impact_summary=(
                "Notify now; profile action waits for its effective date and "
                "market confirmation."
            ),
            effective_date=regulator_date,
            rule_id="lifecycle.terminal_delisting",
            decision_issues=issues,
            transition_requested=requested,
        )

    if regulator_effect in {
        "no_identity_change",
        "asset_acquisition_no_registrant_change",
    }:
        missing = []
        if regulator_source is None:
            missing.append("regulator_source_ticker_missing")
        elif regulator_source != case_ticker:
            missing.append("case_ticker_mismatch")
        if regulator_cik is None or case_cik is None:
            missing.append("regulator_issuer_cik_missing")
        elif regulator_cik != case_cik:
            missing.append("issuer_cik_mismatch")
        if missing:
            return _insufficient(issues=missing)
        return _decision(
            decision_tier="verified_automatic",
            action_readiness="not_applicable",
            relevance="issuer_related",
            confidence="high",
            outcomes=("no_tracked_security_change",),
            conclusion="The cited event does not change the tracked security identity.",
            impact_summary=(
                "Keep tracking the existing symbol; no transition is proposed."
                + (f" {transaction_impact}" if transaction_kind is not None else "")
            ),
            rule_id="lifecycle.no_identity_change",
            terms=transaction,
            decision_issues=transaction_issues,
        )

    if transaction_kind is not None:
        return _decision(
            decision_tier="review_suggested",
            action_readiness="action_blocked",
            relevance="direct_tracked_security",
            confidence="medium",
            outcomes=(
                _MA_OUTCOMES.get(
                    transaction_kind,
                    "acquisition_terms_unknown",
                ),
            ),
            conclusion=(
                f"The cited filing describes a {transaction_kind.replace('_', ' ')} "
                "transaction requiring review."
            ),
            impact_summary=(
                f"{transaction_impact} No ticker transition is authorized "
                "automatically."
            ),
            successor_ticker=regulator_successor,
            destination_venue=regulator_destination,
            effective_date=regulator_date,
            terms=transaction,
            rule_id="lifecycle.ma_review",
            decision_issues=("human_review_required", *transaction_issues),
        )

    required_regulator = {
        "source_ticker": regulator_source,
        "successor_ticker": regulator_successor,
        "effective_date": regulator_date,
        "security_class": regulator_class,
        "issuer_cik": regulator_cik,
    }
    missing_regulator = tuple(
        f"regulator_{name}_missing"
        for name, value in required_regulator.items()
        if value is None
    )
    if missing_regulator:
        return _insufficient(issues=("regulator_identity_facts_missing",))
    if case_cik is None or regulator_cik != case_cik:
        return _insufficient(issues=("issuer_cik_mismatch",))

    assert regulator_source is not None
    assert regulator_successor is not None
    assert regulator_date is not None
    if case_ticker not in {regulator_source, regulator_successor}:
        return _insufficient(issues=("case_ticker_mismatch",))

    market_successor = _one(
        fact_rows, "successor_ticker", family="market_infrastructure"
    )
    market_destination = _one(
        fact_rows, "destination_venue", family="market_infrastructure"
    )
    market_class = _one(
        fact_rows, "security_class", family="market_infrastructure"
    )
    market_matches = (
        market_successor == regulator_successor
        and market_destination is not None
        and market_class == regulator_class
        and (
            regulator_destination is None
            or market_destination == regulator_destination
        )
    )
    destination = regulator_destination or market_destination
    venue_changed = (
        regulator_source_venue is not None
        and destination is not None
        and regulator_source_venue != destination
    )

    if regulator_source == regulator_successor and venue_changed:
        if not market_matches:
            return _decision(
                decision_tier="review_suggested",
                action_readiness="action_blocked",
                relevance="direct_tracked_security",
                confidence="medium",
                outcomes=("venue_transfer",),
                conclusion="Regulator evidence indicates a venue transfer.",
                impact_summary="Market-infrastructure corroboration is still required.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.venue_transfer",
                decision_issues=("market_corroboration_missing",),
            )
        return _decision(
            decision_tier="verified_automatic",
            action_readiness="not_applicable",
            relevance="direct_tracked_security",
            confidence="high",
            outcomes=("venue_transfer",),
            conclusion=(
                f"{regulator_source} moves from {regulator_source_venue} to "
                f"{destination} without changing symbol."
            ),
            impact_summary="Notify the venue change and keep tracking the same symbol.",
            successor_ticker=regulator_successor,
            destination_venue=destination,
            effective_date=regulator_date,
            rule_id="lifecycle.venue_transfer",
        )

    if regulator_source != regulator_successor:
        outcomes = ("symbol_changed",) + (
            ("venue_transfer",) if venue_changed else ()
        )
        if not market_matches:
            return _decision(
                decision_tier="review_suggested",
                action_readiness="action_blocked",
                relevance="direct_tracked_security",
                confidence="medium",
                outcomes=outcomes,
                conclusion=(
                    f"Regulator evidence indicates {regulator_source} will become "
                    f"{regulator_successor}."
                ),
                impact_summary="Market-infrastructure corroboration is still required.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.simple_symbol_continuation",
                decision_issues=("market_corroboration_missing",),
            )
        if case_ticker == regulator_successor:
            return _decision(
                decision_tier="verified_automatic",
                action_readiness="not_applicable",
                relevance="direct_tracked_security",
                confidence="high",
                outcomes=outcomes,
                conclusion=(
                    f"The tracked security continued from {regulator_source} to "
                    f"{regulator_successor}."
                ),
                impact_summary=(
                    "The case already uses the successor symbol; no A-to-A "
                    "transition is created."
                ),
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.simple_symbol_continuation",
            )
        request = {
            "transition_kind": "symbol_continuation",
            "source_ticker": regulator_source,
            "successor_ticker": regulator_successor,
            "effective_date": regulator_date,
            "outcomes": outcomes,
        }
        eligible, issues = _preview(transition_preview, request)
        if eligible:
            return _decision(
                decision_tier="verified_automatic",
                action_readiness="transition_eligible",
                relevance="direct_tracked_security",
                confidence="high",
                outcomes=outcomes,
                conclusion=(
                    f"The tracked security will continue from {regulator_source} "
                    f"to {regulator_successor}."
                ),
                impact_summary="The cited identity transition is eligible for scheduling.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.simple_symbol_continuation",
                transition_requested=True,
            )
        return _decision(
            decision_tier="review_suggested",
            action_readiness="action_blocked",
            relevance="direct_tracked_security",
            confidence="medium",
            outcomes=outcomes,
            conclusion=(
                f"Regulator and market evidence indicate {regulator_source} will "
                f"become {regulator_successor}."
            ),
            impact_summary="The current transition preview is not eligible.",
            successor_ticker=regulator_successor,
            destination_venue=destination,
            effective_date=regulator_date,
            rule_id="lifecycle.simple_symbol_continuation",
            decision_issues=issues,
        )

    return _insufficient(issues=("identity_change_not_established",))


__all__ = [
    "AUTOMATION_POLICY_VERSION",
    "RULE_VERSIONS",
    "AutomationDecision",
    "evaluate_automation_decision",
]
