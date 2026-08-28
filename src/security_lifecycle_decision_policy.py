"""Pure decision policy for cited security-lifecycle facts."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

from src.security_lifecycle_fact_kernel import normalize_automation_fact_value


AUTOMATION_POLICY_VERSION = "trusted-lifecycle-automation-v4"
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
    retrieved_at: str | None


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
        evidence_id = _text(_field(value, "evidence_id", _field(value, "local_id")))
        family = _text(_field(value, "source_family"))
        if evidence_id is None or family is None:
            raise ValueError("evidence_identity")
        locator = _locator(value)
        retrieved_at = _text(_field(value, "retrieved_at"))
        if retrieved_at is None:
            market_data = locator.get("market_data")
            if isinstance(market_data, Mapping):
                retrieved_at = _text(market_data.get("retrieved_at"))
        row = _Evidence(evidence_id, family, locator, retrieved_at)
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
        cash_per_security_decimal=_term(transaction, "cash_per_security_decimal"),
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
        sorted({str(value) for value in result.get("block_reasons", ()) if str(value)})
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


def _market_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _listing_delisted_date(value: object) -> date | None:
    normalized_date = _iso_date(value)
    if normalized_date is not None:
        return date.fromisoformat(normalized_date)
    timestamp = _market_timestamp(value)
    return None if timestamp is None else timestamp.date()


def _listing_snapshot(row: _Evidence) -> Mapping[str, Any] | None:
    if row.source_family != "listing_authority":
        return None
    nested = row.source_locator.get("listing_directory_snapshot")
    snapshot = nested if isinstance(nested, Mapping) else row.source_locator
    kind = _text(snapshot.get("locator_kind"))
    if kind not in {None, "listing_directory_snapshot"}:
        return None
    if _text(snapshot.get("adapter")) is None:
        return None
    return snapshot


def _listing_expected_state(value: object) -> str | None:
    if value is True:
        return "active"
    if value is False:
        return "inactive"
    text = _text(value)
    return None if text is None else text.lower()


def _listing_component(row: _Evidence) -> tuple[str, str, str, str] | None:
    snapshot = _listing_snapshot(row)
    if snapshot is None:
        return None
    adapter = _text(snapshot.get("adapter"))
    ticker = _ticker(snapshot.get("candidate_ticker"))
    expected = _listing_expected_state(snapshot.get("expected_active_state"))
    market = _text(snapshot.get("market"))
    if None in {adapter, ticker, expected, market}:
        return None
    assert adapter is not None
    assert ticker is not None
    assert expected is not None
    assert market is not None
    return adapter.lower(), ticker, expected, market.lower()


def _listing_records(
    evidence: tuple[_Evidence, ...], ticker: str
) -> tuple[_Evidence, ...]:
    """Select current listing material independently within each component."""

    def current(rows: list[_Evidence]) -> tuple[_Evidence, ...]:
        timestamps = tuple((row, _market_timestamp(row.retrieved_at)) for row in rows)
        if len(rows) == 1:
            return tuple(rows)
        if all(value is not None for _row, value in timestamps):
            latest = max(value for _row, value in timestamps if value is not None)
            return tuple(row for row, value in timestamps if value == latest)
        # Unknown recency cannot safely supersede another record.
        return tuple(rows)

    candidate = _ticker(ticker)
    grouped: dict[tuple[str, str, str, str], list[_Evidence]] = {}
    for row in evidence:
        component = _listing_component(row)
        if component is None or component[1] != candidate:
            continue
        grouped.setdefault(component, []).append(row)

    selected: list[_Evidence] = []
    for component in sorted(grouped):
        rows = grouped[component]
        if component[0] != "nasdaq_symbol_directory":
            selected.extend(current(rows))
            continue
        by_directory: dict[str | None, list[_Evidence]] = {}
        for row in rows:
            directory = _text((_listing_snapshot(row) or {}).get("directory"))
            by_directory.setdefault(directory, []).append(row)
        for directory in sorted(by_directory, key=lambda value: value or ""):
            selected.extend(current(by_directory[directory]))
    return tuple(sorted(selected, key=lambda row: row.evidence_id))


def _listing_status(row: _Evidence) -> str | None:
    snapshot = _listing_snapshot(row)
    if snapshot is None:
        return None
    durable = _text(snapshot.get("listing_status"))
    if durable is not None:
        normalized = durable.lower()
        return (
            normalized
            if normalized in {"active", "inactive", "not_found", "unverified"}
            else None
        )

    # Compatibility for persisted v4-predecessor/test locators only.
    legacy = _text(snapshot.get("status", snapshot.get("result")))
    if legacy is None:
        return None
    normalized = legacy.lower()
    if normalized == "found":
        if snapshot.get("active") is True:
            return "active"
        if snapshot.get("active") is False:
            return "inactive"
        return None
    return normalized if normalized in {"not_found", "unverified"} else None


def _listing_row_active(row: _Evidence) -> bool:
    return _listing_status(row) == "active"


def _listing_active(evidence: tuple[_Evidence, ...], ticker: str) -> bool:
    return any(_listing_row_active(row) for row in _listing_records(evidence, ticker))


def _listing_active_successor_present(
    evidence: tuple[_Evidence, ...], source_ticker: str
) -> bool:
    source = _ticker(source_ticker)
    return any(
        component is not None and component[1] != source and _listing_row_active(row)
        for row in _selected_listing_rows(evidence)
        for component in (_listing_component(row),)
    )


def _listing_active_rows(
    evidence: tuple[_Evidence, ...],
    ticker: str,
    *,
    adapter: str | None = None,
    market: str | None = None,
) -> tuple[_Evidence, ...]:
    return tuple(
        row
        for row in _listing_records(evidence, ticker)
        for component in (_listing_component(row),)
        if component is not None
        and _listing_row_active(row)
        and (adapter is None or component[0] == adapter.lower())
        and (market is None or component[3] == market.lower())
    )


def _facts_for_evidence(
    facts: tuple[_Fact, ...], evidence: tuple[_Evidence, ...]
) -> tuple[_Fact, ...]:
    evidence_ids = {row.evidence_id for row in evidence}
    return tuple(row for row in facts if row.evidence_id in evidence_ids)


def _listing_explicit_inactive(
    evidence: tuple[_Evidence, ...], ticker: str, today: date
) -> bool:
    for row in _listing_records(evidence, ticker):
        component = _listing_component(row)
        snapshot = _listing_snapshot(row)
        if component is None or snapshot is None:
            continue
        delisted = _listing_delisted_date(snapshot.get("delisted_utc"))
        if (
            component[0] == "massive_reference"
            and _listing_status(row) == "inactive"
            and delisted is not None
            and delisted <= today
        ):
            return True
    return False


def _listing_not_found(
    evidence: tuple[_Evidence, ...], ticker: str, authority: str
) -> bool:
    expected = authority.lower()
    return any(
        component is not None
        and component[0] == expected
        and _listing_status(row) == "not_found"
        for row in _listing_records(evidence, ticker)
        for component in (_listing_component(row),)
    )


def _nasdaq_not_found_complete(evidence: tuple[_Evidence, ...], ticker: str) -> bool:
    directories = {
        _text((_listing_snapshot(row) or {}).get("directory"))
        for row in _listing_records(evidence, ticker)
        for component in (_listing_component(row),)
        if component is not None
        and component[0] == "nasdaq_symbol_directory"
        and component[2] == "active"
        and component[3] == "stocks"
        and _listing_status(row) == "not_found"
    }
    return directories == {"nasdaq_listed", "other_listed"}


def _listing_conflicts(evidence: tuple[_Evidence, ...], ticker: str) -> tuple[str, ...]:
    rows = _listing_records(evidence, ticker)
    grouped: dict[tuple[str, str, str, str], list[_Evidence]] = {}
    for row in rows:
        component = _listing_component(row)
        if component is not None:
            grouped.setdefault(component, []).append(row)
    for component_rows in grouped.values():
        states = {
            (
                _listing_status(row),
                _text((_listing_snapshot(row) or {}).get("delisted_utc")),
            )
            for row in component_rows
        }
        if len(states) > 1:
            return ("listing_authority_conflict",)
    if any(_listing_row_active(row) for row in rows) and any(
        _listing_status(row) == "inactive" for row in rows
    ):
        return ("listing_authority_conflict",)
    active_components = {
        component
        for row in rows
        for component in (_listing_component(row),)
        if component is not None and _listing_row_active(row)
    }
    if any(
        component[0] == "nasdaq_symbol_directory" for component in active_components
    ) and any(
        component[0] == "massive_reference" and component[3] == "otc"
        for component in active_components
    ):
        return ("listing_authority_conflict",)
    return ()


def _selected_listing_rows(evidence: tuple[_Evidence, ...]) -> tuple[_Evidence, ...]:
    tickers = {
        component[1]
        for row in evidence
        for component in (_listing_component(row),)
        if component is not None
    }
    selected = {
        row.evidence_id: row
        for ticker in tickers
        for row in _listing_records(evidence, ticker)
    }
    return tuple(selected[key] for key in sorted(selected))


def _current_decision_material(
    evidence: tuple[_Evidence, ...],
    facts: tuple[_Fact, ...],
) -> tuple[tuple[_Evidence, ...], tuple[_Fact, ...]]:
    listing = _selected_listing_rows(evidence)
    market = tuple(
        row
        for row in evidence
        if row.source_family == "market_infrastructure"
        and row.source_locator.get("contract_status") == "found"
    )
    timestamps = tuple((row, _market_timestamp(row.retrieved_at)) for row in market)
    if len(market) <= 1:
        selected_market = market
    elif any(value is None for _row, value in timestamps):
        selected_market = ()
    else:
        latest = max(value for _row, value in timestamps if value is not None)
        selected_market = tuple(row for row, value in timestamps if value == latest)
    selected_ids = {
        row.evidence_id for row in evidence if row.source_family == "regulator"
    }
    selected_ids.update(row.evidence_id for row in listing)
    selected_ids.update(row.evidence_id for row in selected_market)
    current_evidence = tuple(row for row in evidence if row.evidence_id in selected_ids)
    return current_evidence, tuple(
        row for row in facts if row.evidence_id in selected_ids
    )


def evaluate_automation_decision(
    *,
    case: Mapping[str, object],
    evidence: Iterable[object],
    facts: Iterable[object],
    current_date: date | str,
    active_sources: Iterable[str],
    transition_preview: Callable[[Mapping[str, object]], Mapping[str, object] | None],
) -> AutomationDecision:
    """Evaluate cited facts without opening a database, provider, or model."""

    all_evidence_rows = _evidence_rows(evidence)
    all_fact_rows = _fact_rows(facts, all_evidence_rows)
    evidence_rows, fact_rows = _current_decision_material(
        all_evidence_rows,
        all_fact_rows,
    )
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

    listing_tickers = {
        component[1]
        for row in evidence_rows
        for component in (_listing_component(row),)
        if component is not None
    }
    listing_issues = tuple(
        issue
        for ticker in sorted(listing_tickers)
        for issue in _listing_conflicts(evidence_rows, ticker)
    )
    if listing_issues:
        return _decision(
            decision_tier="review_suggested",
            action_readiness="action_blocked",
            relevance="direct_tracked_security",
            confidence="low",
            outcomes=("undetermined",),
            conclusion="Current listing authority contains incompatible records.",
            impact_summary="No listing state was selected by source count.",
            rule_id="lifecycle.source_conflict",
            decision_issues=listing_issues,
        )

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
            decision_issues=(f"source_conflict:{fact_type}" for fact_type in conflicts),
        )

    regulator_source = _one(fact_rows, "source_ticker", family="regulator")
    regulator_successor = _one(fact_rows, "successor_ticker", family="regulator")
    regulator_source_venue = _one(fact_rows, "source_venue", family="regulator")
    regulator_destination = _one(fact_rows, "destination_venue", family="regulator")
    regulator_date = _one(fact_rows, "effective_date", family="regulator")
    regulator_class = _one(fact_rows, "security_class", family="regulator")
    regulator_cik = _one(fact_rows, "issuer_cik", family="regulator")
    regulator_effect = _one(fact_rows, "tracked_security_effect", family="regulator")
    transaction = _terms(_one(fact_rows, "transaction_structure", family="regulator"))
    transaction_kind = _text(transaction.get("kind"))
    terms_status = _text(transaction.get("terms_status"))
    if terms_status == "not_extracted":
        transaction_issues = ("transaction_terms_not_extracted",)
        transaction_impact = (
            "Counterparty and consideration terms were not deterministically extracted."
        )
    elif terms_status == "partial":
        transaction_issues = ("transaction_terms_partial",)
        transaction_impact = "Only some counterparty or consideration terms were deterministically extracted."
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
        if _listing_active_successor_present(evidence_rows, regulator_source):
            return _decision(
                decision_tier="review_suggested",
                action_readiness="action_blocked",
                relevance="direct_tracked_security",
                confidence="low",
                outcomes=("undetermined",),
                conclusion="Current listing authority presents an active successor.",
                impact_summary="Terminal action is blocked by the positive successor.",
                effective_date=regulator_date,
                rule_id="lifecycle.source_conflict",
                decision_issues=("successor_present",),
            )
        if today < date.fromisoformat(regulator_date):
            readiness = "waiting_effective_date"
            issues: tuple[str, ...] = ()
            requested = False
            outcomes = ("undetermined",)
        elif not _nasdaq_not_found_complete(evidence_rows, regulator_source):
            readiness = "waiting_market_confirmation"
            issues = ("nasdaq_not_found_incomplete",)
            requested = False
            outcomes = ("undetermined",)
        elif not _listing_explicit_inactive(evidence_rows, regulator_source, today):
            readiness = "waiting_market_confirmation"
            issues = ("massive_explicit_inactive_missing",)
            requested = False
            outcomes = ("undetermined",)
        elif "portfolio_open" in sources:
            readiness = "action_blocked"
            issues = ("portfolio_position_open",)
            requested = False
            outcomes = ("undetermined",)
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
            outcomes = ("listing_ended",) if eligible else ("undetermined",)
        return _decision(
            decision_tier="verified_automatic",
            action_readiness=readiness,
            relevance="direct_tracked_security",
            confidence="high",
            outcomes=outcomes,
            conclusion=(
                (
                    f"The cited regulator record and current listing authorities "
                    f"establish that listing of {regulator_source} ended."
                )
                if outcomes == ("listing_ended",)
                else (
                    "Current directory absence does not establish an explicit "
                    "terminal listing state."
                )
            ),
            impact_summary=(
                "Keep the case in Monitoring until explicit listing authority "
                "supports terminal action."
                if outcomes == ("undetermined",)
                else "Notify now; profile action follows the eligible preview."
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
        if regulator_class is None:
            missing.append("regulator_security_class_missing")
        if missing:
            return _insufficient(issues=missing)
        listing_rows = _listing_active_rows(evidence_rows, case_ticker)
        listing_facts = _facts_for_evidence(fact_rows, listing_rows)
        listing_ticker = _one(listing_facts, "successor_ticker")
        listing_class = _one(listing_facts, "security_class")
        if (
            not listing_rows
            or listing_ticker != case_ticker
            or listing_class != regulator_class
        ):
            return _insufficient(issues=("listing_active_missing",))
        if regulator_date is not None and today < date.fromisoformat(regulator_date):
            return _decision(
                decision_tier="verified_automatic",
                action_readiness="waiting_effective_date",
                relevance="issuer_related",
                confidence="high",
                outcomes=("undetermined",),
                conclusion="The deterministic issuer effect is not yet effective.",
                impact_summary="Keep the case in Monitoring until the effective date.",
                effective_date=regulator_date,
                rule_id="lifecycle.no_identity_change",
            )
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

    if "acquisition_completed" in {
        str(value) for value in case.get("event_kinds", ())
    } and _listing_active(evidence_rows, case_ticker):
        return _insufficient(issues=("regulator_role_effect_missing",))

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

    massive_otc_rows = _listing_active_rows(
        evidence_rows,
        regulator_successor,
        adapter="massive_reference",
        market="otc",
    )
    otc_destination = (
        regulator_destination.startswith("OTC")
        if regulator_destination is not None
        else bool(massive_otc_rows)
    )
    if otc_destination:
        listing_rows = massive_otc_rows
        listing_issue = "massive_otc_active_missing"
    else:
        listing_rows = _listing_active_rows(
            evidence_rows,
            regulator_successor,
            adapter="nasdaq_symbol_directory",
        )
        listing_issue = "listing_active_missing"
    listing_facts = _facts_for_evidence(fact_rows, listing_rows)
    listing_successor = _one(listing_facts, "successor_ticker")
    listing_destination = _one(listing_facts, "destination_venue")
    listing_class = _one(listing_facts, "security_class")
    listing_matches = (
        bool(listing_rows)
        and listing_successor == regulator_successor
        and listing_destination is not None
        and listing_class == regulator_class
        and (
            regulator_destination is None
            or listing_destination == regulator_destination
        )
    )
    destination = regulator_destination or listing_destination
    venue_changed = (
        regulator_source_venue is not None
        and destination is not None
        and regulator_source_venue != destination
    )

    if regulator_source == regulator_successor and venue_changed:
        if not listing_matches:
            return _decision(
                decision_tier="review_suggested",
                action_readiness="action_blocked",
                relevance="direct_tracked_security",
                confidence="medium",
                outcomes=("venue_transfer",),
                conclusion="Regulator evidence indicates a venue transfer.",
                impact_summary="Current destination listing authority is still required.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.venue_transfer",
                decision_issues=(listing_issue,),
            )
        if today < date.fromisoformat(regulator_date):
            return _decision(
                decision_tier="verified_automatic",
                action_readiness="waiting_effective_date",
                relevance="direct_tracked_security",
                confidence="high",
                outcomes=("venue_transfer",),
                conclusion="Regulator and listing evidence indicate a venue transfer.",
                impact_summary="Notify when the deterministic effective date arrives.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.venue_transfer",
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
        outcomes = ("symbol_changed",) + (("venue_transfer",) if venue_changed else ())
        if not listing_matches:
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
                impact_summary="Current destination listing authority is still required.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.simple_symbol_continuation",
                decision_issues=(listing_issue,),
            )
        if today < date.fromisoformat(regulator_date):
            return _decision(
                decision_tier="verified_automatic",
                action_readiness="waiting_effective_date",
                relevance="direct_tracked_security",
                confidence="high",
                outcomes=outcomes,
                conclusion=(
                    f"Regulator and listing evidence indicate {regulator_source} "
                    f"will become {regulator_successor}."
                ),
                impact_summary="Wait for the deterministic effective date.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.simple_symbol_continuation",
            )
        if "portfolio_open" in sources:
            return _decision(
                decision_tier="review_suggested",
                action_readiness="action_blocked",
                relevance="direct_tracked_security",
                confidence="high",
                outcomes=outcomes,
                conclusion=(
                    f"The tracked security will continue from {regulator_source} "
                    f"to {regulator_successor}."
                ),
                impact_summary="An open portfolio position blocks automatic mutation.",
                successor_ticker=regulator_successor,
                destination_venue=destination,
                effective_date=regulator_date,
                rule_id="lifecycle.simple_symbol_continuation",
                decision_issues=("portfolio_position_open",),
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
