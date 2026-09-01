"""Deterministic SEC candidate admission projected from current run material."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping


SecAdmissionState = Literal[
    "pending",
    "admitted",
    "screened_out",
    "needs_review",
]
SecAdmissionReason = Literal[
    "awaiting_regulator_screening",
    "direct_listing_item",
    "direct_identity_filing",
    "material_tracked_security_fact",
    "no_material_tracked_security_fact",
    "identity_binding_missing",
    "regulator_screening_incomplete",
    "unknown_form",
]

SEC_ADMISSION_STATES = frozenset(
    {"pending", "admitted", "screened_out", "needs_review"}
)
SEC_ADMISSION_REASONS = frozenset(
    {
        "awaiting_regulator_screening",
        "direct_listing_item",
        "direct_identity_filing",
        "material_tracked_security_fact",
        "no_material_tracked_security_fact",
        "identity_binding_missing",
        "regulator_screening_incomplete",
        "unknown_form",
    }
)

_IDENTITY_FORMS = frozenset({"25", "25-NSE", "8-A12B", "8-K12B"})
_M_AND_A_FORMS = frozenset({"DEFM14A", "DEFA14A"})
_CURRENT_REPORT_FORMS = frozenset({"8-K", "8-K/A"})
_CONDITIONAL_ITEMS = frozenset({"1.01", "2.01", "5.01"})
_KNOWN_SUPPORT_ITEMS = frozenset(
    {"2.03", "3.02", "3.03", "5.03", "7.01", "8.01", "9.01"}
)
_SEC_PROVIDER_FAILURES = frozenset(
    {
        "sec_access_denied",
        "sec_document_unavailable",
        "sec_governor_unavailable",
        "sec_identity_unconfigured",
        "sec_rate_limited",
        "sec_request_budget_exhausted",
        "sec_transport_unavailable",
    }
)


@dataclass(frozen=True)
class SecAdmissionDecision:
    state: SecAdmissionState
    reason: SecAdmissionReason


def _text(value: object) -> str:
    return str(value or "").strip()


def _latest_matching_run(
    runs: Iterable[Mapping[str, object]], fingerprint: str
) -> Mapping[str, object] | None:
    return next(
        (
            run
            for run in runs
            if _text(run.get("observation_fingerprint_sha256")) == fingerprint
        ),
        None,
    )


def _run_facts(
    facts: Iterable[Mapping[str, object]], run_id: str
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        fact
        for fact in facts
        if _text(fact.get("automation_run_id")) == run_id
        and fact.get("source_family") == "regulator"
    )


def _exact_ticker_binding(
    facts: Iterable[Mapping[str, object]], ticker: str
) -> bool:
    return any(
        fact.get("fact_type") == "source_ticker"
        and _text(fact.get("normalized_value")).upper() == ticker
        for fact in facts
    )


def _material_fact(
    facts: Iterable[Mapping[str, object]], ticker: str
) -> bool:
    rows = tuple(facts)
    if any(row.get("fact_type") == "tracked_security_effect" for row in rows):
        return True

    by_evidence: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        evidence_id = _text(row.get("evidence_id"))
        if evidence_id:
            by_evidence.setdefault(evidence_id, []).append(row)
    material_with_binding = {
        "successor_ticker",
        "destination_venue",
        "effective_date",
    }
    return any(
        _exact_ticker_binding(group, ticker)
        and any(row.get("fact_type") in material_with_binding for row in group)
        for group in by_evidence.values()
    )


def _blocker_codes(run: Mapping[str, object]) -> frozenset[str]:
    raw = run.get("blockers", ())
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return frozenset()
    return frozenset(
        _text(row.get("blocker_code"))
        for row in raw
        if isinstance(row, Mapping) and _text(row.get("blocker_code"))
    )


def _screening_complete(run: Mapping[str, object]) -> bool:
    if run.get("status") not in {"succeeded", "blocked"}:
        return False
    diagnostics = run.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return False
    candidate_count = diagnostics.get("sec_candidate_document_count")
    completed_count = diagnostics.get("sec_completed_document_count")
    if (
        type(candidate_count) is not int
        or type(completed_count) is not int
        or candidate_count <= 0
        or completed_count != candidate_count
    ):
        return False
    return not bool(_blocker_codes(run).intersection(_SEC_PROVIDER_FAILURES))


def classify_sec_admission(
    *,
    observation: Mapping[str, object],
    observation_fingerprint_sha256: str,
    automation_runs: Iterable[Mapping[str, object]],
    automation_facts: Iterable[Mapping[str, object]],
) -> SecAdmissionDecision:
    """Classify one discovered lifecycle observation without mutating authority."""
    form = _text(observation.get("filing_form")).upper()
    ticker = _text(observation.get("ticker")).upper()
    items = frozenset(_text(item) for item in observation.get("filing_items", ()))
    known = (
        form in _IDENTITY_FORMS
        or form in _M_AND_A_FORMS
        or form in _CURRENT_REPORT_FORMS
    )
    if not known:
        return SecAdmissionDecision("needs_review", "unknown_form")
    if form in _CURRENT_REPORT_FORMS and "3.01" in items:
        return SecAdmissionDecision("admitted", "direct_listing_item")

    fingerprint = _text(observation_fingerprint_sha256)
    current_run = _latest_matching_run(automation_runs, fingerprint)
    if current_run is None:
        return SecAdmissionDecision("pending", "awaiting_regulator_screening")
    run_id = _text(current_run.get("run_id"))
    facts = _run_facts(automation_facts, run_id)
    if form in _IDENTITY_FORMS and _exact_ticker_binding(facts, ticker):
        return SecAdmissionDecision("admitted", "direct_identity_filing")
    if _material_fact(facts, ticker):
        if form in _IDENTITY_FORMS and not _exact_ticker_binding(facts, ticker):
            return SecAdmissionDecision("needs_review", "identity_binding_missing")
        return SecAdmissionDecision("admitted", "material_tracked_security_fact")
    if not _screening_complete(current_run):
        return SecAdmissionDecision("needs_review", "regulator_screening_incomplete")
    if form in _IDENTITY_FORMS:
        return SecAdmissionDecision("needs_review", "identity_binding_missing")

    # Support-only current-report items and conditional filings share the same
    # completed-screening result: neither enters the operational queue without
    # cited material tied to the tracked security.
    return SecAdmissionDecision(
        "screened_out",
        "no_material_tracked_security_fact",
    )


def project_sec_candidate(
    *,
    case_id: str,
    observation: Mapping[str, object],
    decision: SecAdmissionDecision,
) -> dict[str, object]:
    """Return the closed operator-facing audit projection for one candidate."""
    return {
        "case_id": _text(case_id),
        "ticker": _text(observation.get("ticker")).upper(),
        "issuer_name": _text(observation.get("issuer_name")),
        "filing_form": _text(observation.get("filing_form")).upper(),
        "filing_items": sorted(
            {_text(item) for item in observation.get("filing_items", ()) if _text(item)}
        ),
        "filing_date": _text(observation.get("filing_date")),
        "evidence_url": _text(observation.get("evidence_url")),
        "admission_state": decision.state,
        "admission_reason": decision.reason,
    }


__all__ = [
    "SEC_ADMISSION_REASONS",
    "SEC_ADMISSION_STATES",
    "SecAdmissionDecision",
    "SecAdmissionReason",
    "SecAdmissionState",
    "classify_sec_admission",
    "project_sec_candidate",
]
