"""Pure queue disposition for composed security-lifecycle cases."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from typing import Any

from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
from src.security_lifecycle_investigation import evidence_rows_sha256
from src.security_lifecycle_schema import EVIDENCE_SOURCE_FAMILIES


LIFECYCLE_DISPOSITIONS = frozenset(
    {
        "confirmed_monitoring",
        "confirmed_effective",
        "not_confirmed_yet",
        "exception_required",
    }
)
LIFECYCLE_QUEUE_BUCKETS = frozenset({"attention", "monitoring", "history"})
SOURCE_FAMILY_STATES = frozenset(
    {"confirmed", "present", "missing", "unavailable", "conflict"}
)
LIFECYCLE_DISPOSITION_REASONS = frozenset(
    {
        "awaiting_initial_automation",
        "automation_running",
        "waiting_effective_date",
        "waiting_market_confirmation",
        "waiting_transition_revalidation",
        "retryable_source_unavailable",
        "event_completion_not_confirmed",
        "not_confirmed_as_of",
        "source_missing",
        "source_conflict",
        "ambiguous_event",
        "nonretryable_provider_failure",
        "automation_failure",
        "resolved_no_change",
        "resolved_assessment",
        "transition_applied",
        "transition_reversed",
        "transition_cancelled",
        "transition_needs_review",
        "reviewed_inconclusive",
    }
)

_WAITING_READINESS = frozenset(
    {
        "waiting_effective_date",
        "waiting_market_confirmation",
        "waiting_transition_revalidation",
    }
)
_NO_CHANGE_OUTCOMES = frozenset({"no_tracked_security_change"})
_NONRETRYABLE_PROVIDER_BLOCKERS = frozenset(
    {
        "sec_identity_unconfigured",
        "sec_access_denied",
        "internal_news_schema_mismatch",
        "ibkr_entitlement_denied",
    }
)
_UNAVAILABLE_FAMILY_BY_BLOCKER = {
    "sec_identity_unconfigured": "regulator",
    "sec_governor_unavailable": "regulator",
    "sec_request_budget_exhausted": "regulator",
    "sec_rate_limited": "regulator",
    "sec_access_denied": "regulator",
    "sec_transport_unavailable": "regulator",
    "sec_document_unavailable": "regulator",
    "internal_news_unavailable": "publisher",
    "internal_news_schema_mismatch": "publisher",
    "ibkr_gateway_unavailable": "market_infrastructure",
    "ibkr_entitlement_denied": "market_infrastructure",
}


@dataclass(frozen=True)
class LifecycleDispositionProjection:
    disposition: str
    queue_bucket: str
    reason_code: str
    disposition_as_of: str | None
    last_checked_at: str | None
    next_check_at: str | None
    source_family_status: Mapping[str, str]


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(name)
    return value


def _rows(value: object, name: str) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(name)
    return tuple(_mapping(row, name) for row in value)


def _instant(value: object, name: str) -> datetime:
    text = str(value or "").strip()
    parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise ValueError(name) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(name)
    return parsed.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _date_start(value: object, name: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(name) from exc
    return f"{parsed.isoformat()}T00:00:00Z"


def _blocker_context(blocker: Mapping[str, object]) -> Mapping[str, object]:
    if "context" in blocker:
        context = blocker["context"]
        if not isinstance(context, Mapping):
            raise ValueError("automation_blocker_context")
        return context
    encoded = blocker.get("context_json")
    if encoded is None:
        return {}
    if not isinstance(encoded, str):
        raise ValueError("automation_blocker_context")
    try:
        decoded = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise ValueError("automation_blocker_context") from exc
    if not isinstance(decoded, Mapping):
        raise ValueError("automation_blocker_context")
    return decoded


def _blocker_code(blocker: Mapping[str, object]) -> str:
    code = str(blocker.get("blocker_code") or blocker.get("code") or "").strip()
    if not code:
        raise ValueError("automation_blocker_code")
    return code


def _retryable(blocker: Mapping[str, object]) -> bool:
    value = blocker.get("retryable")
    if isinstance(value, bool):
        return value
    if value in {0, 1}:
        return bool(value)
    raise ValueError("automation_blocker_retryable")


def _artifact_is_current(
    case: Mapping[str, object],
    artifact: Mapping[str, object],
    assessment: Mapping[str, object] | None = None,
) -> bool:
    if (
        artifact.get("approval_authority") == "automation_policy"
        and artifact.get("status") in {"applied", "reversed", "cancelled"}
        and assessment is None
    ):
        return False
    current_observation = str(
        case.get("observation_fingerprint_sha256") or ""
    ).strip()
    if not current_observation:
        return True
    preview_value = artifact.get("approved_preview")
    preview = preview_value if isinstance(preview_value, Mapping) else {}
    query_value = artifact.get("query_context")
    query = query_value if isinstance(query_value, Mapping) else {}
    observation_values = {
        str(value)
        for value in (
            artifact.get("observation_fingerprint_sha256"),
            artifact.get("approved_observation_fingerprint_sha256"),
            preview.get("observation_fingerprint_sha256"),
        )
        if value
    }
    if not observation_values or observation_values != {current_observation}:
        return False
    if assessment is None:
        return True

    assessment_id = str(assessment.get("assessment_id") or "")
    artifact_assessment_ids = {
        str(value)
        for value in (
            artifact.get("assessment_id"),
            preview.get("assessment_id"),
        )
        if value
    }
    if artifact_assessment_ids and artifact_assessment_ids != {assessment_id}:
        return False
    evidence_set = str(assessment.get("evidence_set_sha256") or "")
    artifact_evidence_sets = {
        str(value)
        for value in (
            artifact.get("evidence_set_sha256"),
            preview.get("evidence_set_sha256"),
        )
        if value
    }
    if evidence_set and artifact_evidence_sets and artifact_evidence_sets != {
        evidence_set
    }:
        return False
    if artifact.get("approval_authority") == "automation_policy":
        provenance = str(assessment.get("decision_provenance_sha256") or "")
        artifact_provenance = str(
            artifact.get("decision_provenance_sha256")
            or query.get("terminal_decision_provenance_sha256")
            or ""
        )
        if provenance and artifact_provenance and provenance != artifact_provenance:
            return False
    return True


def _current_input_evidence_set_sha256(case: Mapping[str, object]) -> str:
    evidence = _rows(case.get("evidence", ()), "evidence")
    return evidence_rows_sha256(
        (
            str(row.get("evidence_id") or ""),
            str(row.get("content_sha256") or ""),
        )
        for row in evidence
        if row.get("automation_run_id") is None
    )


def _run_is_current(
    case: Mapping[str, object], run: Mapping[str, object]
) -> bool:
    if not _artifact_is_current(case, run):
        return False
    if not str(case.get("observation_fingerprint_sha256") or "").strip():
        return True
    query_value = run.get("query_context")
    if not isinstance(query_value, Mapping):
        return False
    return query_value.get(
        "input_evidence_set_sha256"
    ) == _current_input_evidence_set_sha256(case)


def _latest_run(case: Mapping[str, object]) -> Mapping[str, object] | None:
    runs = _rows(case.get("automation_runs", ()), "automation_runs")
    return next((run for run in runs if _run_is_current(case, run)), None)


def _blockers(run: Mapping[str, object] | None) -> tuple[Mapping[str, object], ...]:
    if run is None:
        return ()
    rows = _rows(run.get("blockers", ()), "automation_blockers")
    for row in rows:
        _blocker_code(row)
        _retryable(row)
        _blocker_context(row)
    return rows


def _not_confirmed_disposition_as_of(
    blockers: Iterable[Mapping[str, object]],
) -> str:
    contexts = []
    for blocker in blockers:
        context = _blocker_context(blocker)
        if context.get("monitoring_reason") == "not_confirmed_as_of":
            contexts.append(context)
    if len(contexts) != 1:
        raise ValueError("disposition_as_of")
    try:
        return date.fromisoformat(str(contexts[0].get("as_of") or "")).isoformat()
    except ValueError as exc:
        raise ValueError("disposition_as_of") from exc


def _normalized_fact_value(fact: Mapping[str, object]) -> Any:
    if "normalized_value" in fact:
        return fact["normalized_value"]
    encoded = fact.get("normalized_value_json")
    if not isinstance(encoded, str):
        raise ValueError("automation_fact_value")
    try:
        return json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise ValueError("automation_fact_value") from exc


def _canonical_value(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("automation_fact_value") from exc


def _conflicting_families(
    case: Mapping[str, object],
    run: Mapping[str, object] | None,
    blockers: Iterable[Mapping[str, object]],
) -> set[str]:
    families: set[str] = set()
    for blocker in blockers:
        code = _blocker_code(blocker)
        if code == "ibkr_contract_ambiguous":
            families.add("market_infrastructure")
        if code != "source_conflict":
            continue
        context = _blocker_context(blocker)
        candidates: list[object] = []
        if "source_family" in context:
            candidates.append(context["source_family"])
        raw_many = context.get("source_families", ())
        if isinstance(raw_many, (list, tuple)):
            candidates.extend(raw_many)
        elif raw_many:
            raise ValueError("automation_blocker_context")
        for candidate in candidates:
            family = str(candidate or "")
            if family not in EVIDENCE_SOURCE_FAMILIES:
                raise ValueError("source_family")
            families.add(family)

    if run is None:
        return families
    run_id = str(run.get("run_id") or "")
    by_type: dict[str, dict[str, set[str]]] = {}
    for fact in _rows(case.get("automation_facts", ()), "automation_facts"):
        if str(fact.get("automation_run_id") or "") != run_id:
            continue
        family = str(fact.get("source_family") or "")
        if family not in EVIDENCE_SOURCE_FAMILIES:
            raise ValueError("source_family")
        fact_type = str(fact.get("fact_type") or "").strip()
        if not fact_type:
            raise ValueError("fact_type")
        canonical = _canonical_value(_normalized_fact_value(fact))
        values = by_type.setdefault(fact_type, {})
        values.setdefault(canonical, set()).add(family)
    for values in by_type.values():
        if len(values) > 1:
            for value_families in values.values():
                families.update(value_families)
    return families


def _source_family_status(
    case: Mapping[str, object],
    run: Mapping[str, object] | None,
    assessment: Mapping[str, object] | None,
    blockers: tuple[Mapping[str, object], ...],
) -> Mapping[str, str]:
    evidence = _rows(case.get("evidence", ()), "evidence")
    evidence_by_id: dict[str, Mapping[str, object]] = {}
    current_run_families: set[str] = set()
    manual_present = False
    run_id = "" if run is None else str(run.get("run_id") or "")
    for row in evidence:
        evidence_id = str(row.get("evidence_id") or "").strip()
        family = str(row.get("source_family") or "").strip()
        if not evidence_id:
            raise ValueError("evidence_id")
        if family not in EVIDENCE_SOURCE_FAMILIES:
            raise ValueError("source_family")
        evidence_by_id[evidence_id] = row
        if family == "manual":
            manual_present = True
        if run_id and str(row.get("automation_run_id") or "") == run_id:
            current_run_families.add(family)

    confirmed: set[str] = set()
    if assessment is not None:
        for citation in _rows(assessment.get("citations", ()), "assessment_citations"):
            if citation.get("reference_kind") != "evidence":
                continue
            evidence_id = str(citation.get("evidence_id") or "")
            row = evidence_by_id.get(evidence_id)
            if row is not None:
                confirmed.add(str(row["source_family"]))

    unavailable = {
        family
        for blocker in blockers
        for family in (_UNAVAILABLE_FAMILY_BY_BLOCKER.get(_blocker_code(blocker)),)
        if family is not None
    }
    conflicts = _conflicting_families(case, run, blockers)
    statuses: dict[str, str] = {}
    for family in sorted(EVIDENCE_SOURCE_FAMILIES):
        if family in conflicts:
            status = "conflict"
        elif family in unavailable:
            status = "unavailable"
        elif family in confirmed:
            status = "confirmed"
        elif family in current_run_families or (family == "manual" and manual_present):
            status = "present"
        else:
            status = "missing"
        statuses[family] = status
    return statuses


def next_lifecycle_recheck_at(
    run: Mapping[str, object] | None,
    assessment: Mapping[str, object] | None,
    transition: Mapping[str, object] | None = None,
) -> str | None:
    transition_execute_at: str | None = None
    if transition is not None:
        transition = _mapping(transition, "ticker_transition")
        if str(transition.get("status") or "") == "approved":
            execute_on = transition.get("execute_on")
            if execute_on:
                transition_execute_at = _date_start(
                    execute_on,
                    "transition_execute_on",
                )
                if not _automation_transition_is_stale(transition):
                    return transition_execute_at

    if run is None:
        return transition_execute_at
    run = _mapping(run, "automation_run")
    retry_at = run.get("retry_at")
    if retry_at:
        return _timestamp(_instant(retry_at, "automation_retry_at"))
    readiness = str(run.get("action_readiness") or "")
    if readiness == "waiting_effective_date":
        if assessment is None:
            return None
        assessment = _mapping(assessment, "current_assessment")
        effective_date = assessment.get("effective_date")
        return (
            None
            if not effective_date
            else _date_start(effective_date, "assessment_effective_date")
        )
    if readiness not in {
        "waiting_market_confirmation",
        "waiting_transition_revalidation",
    }:
        return None
    updated = _instant(run.get("updated_at"), "automation_updated_at")
    if readiness == "waiting_transition_revalidation":
        daily = _timestamp(updated + timedelta(days=1))
        return min(daily, transition_execute_at) if transition_execute_at else daily
    effective: date | None = None
    if assessment is not None:
        assessment = _mapping(assessment, "current_assessment")
        raw_effective = assessment.get("effective_date")
        if raw_effective:
            try:
                effective = date.fromisoformat(str(raw_effective))
            except ValueError as exc:
                raise ValueError("assessment_effective_date") from exc
    interval = timedelta(days=1 if effective and updated.date() <= effective + timedelta(days=7) else 7)
    return _timestamp(updated + interval)


def _last_checked_at(
    case: Mapping[str, object], run: Mapping[str, object] | None
) -> str | None:
    if run is not None:
        value = run.get("updated_at") or run.get("created_at")
        if value:
            return _timestamp(_instant(value, "automation_updated_at"))
    observation = case.get("observation")
    if isinstance(observation, Mapping):
        value = observation.get("last_observed_at")
        if value:
            return _timestamp(_instant(value, "observation_last_observed_at"))
    return None


def _automation_transition_is_stale(transition: Mapping[str, object] | None) -> bool:
    if transition is None or str(transition.get("status") or "") != "approved":
        return False
    if transition.get("approval_authority") != "automation_policy":
        return False
    return transition.get("automation_policy_version") != AUTOMATION_POLICY_VERSION


def _latest_automation_draft_requires_review(
    case: Mapping[str, object], run: Mapping[str, object] | None
) -> bool:
    if run is None or run.get("decision_tier") != "review_suggested":
        return False
    return any(
        assessment.get("author") == "automation"
        and assessment.get("status") == "draft"
        and assessment.get("stale") is not True
        and assessment.get("automation_run_id") == run.get("run_id")
        for assessment in _rows(case.get("assessment_history", ()), "assessment_history")
    )


def project_lifecycle_disposition(
    case: Mapping[str, object],
) -> LifecycleDispositionProjection:
    case = _mapping(case, "lifecycle_case")
    run = _latest_run(case)
    blockers = _blockers(run)
    assessment_value = case.get("current_assessment")
    assessment = (
        None
        if assessment_value is None
        else _mapping(assessment_value, "current_assessment")
    )
    if assessment is not None and assessment.get("stale") is True:
        assessment = None
    acknowledgement_value = case.get("current_acknowledgement")
    acknowledgement = (
        None
        if acknowledgement_value is None
        else _mapping(acknowledgement_value, "current_acknowledgement")
    )
    transition_value = case.get("ticker_transition")
    transition = (
        None
        if transition_value is None
        else _mapping(transition_value, "ticker_transition")
    )
    if transition is not None and not _artifact_is_current(
        case,
        transition,
        assessment,
    ):
        transition = None
    source_status = _source_family_status(case, run, assessment, blockers)
    last_checked_at = _last_checked_at(case, run)
    blocker_codes = {_blocker_code(row) for row in blockers}

    disposition: str
    bucket: str
    reason: str
    disposition_as_of: str | None = None
    if case.get("source_presence") != "present":
        disposition, bucket, reason = "exception_required", "attention", "source_missing"
    elif "source_conflict" in blocker_codes:
        disposition, bucket, reason = (
            "exception_required",
            "attention",
            "source_conflict",
        )
    elif blocker_codes & _NONRETRYABLE_PROVIDER_BLOCKERS:
        disposition, bucket, reason = (
            "exception_required",
            "attention",
            "nonretryable_provider_failure",
        )
    elif transition is not None and transition.get("status") in {
        "applied",
        "reversed",
        "cancelled",
    }:
        reason = {
            "applied": "transition_applied",
            "reversed": "transition_reversed",
            "cancelled": "transition_cancelled",
        }[str(transition["status"])]
        disposition, bucket = "confirmed_effective", "history"
    elif transition is not None and transition.get("status") == "needs_review":
        disposition, bucket, reason = (
            "exception_required",
            "attention",
            "transition_needs_review",
        )
    elif _automation_transition_is_stale(transition):
        disposition, bucket, reason = (
            "not_confirmed_yet",
            "monitoring",
            "waiting_transition_revalidation",
        )
    elif transition is not None and transition.get("status") == "approved":
        disposition, bucket, reason = (
            "confirmed_monitoring",
            "monitoring",
            "waiting_effective_date",
        )
    else:
        readiness = "" if run is None else str(run.get("action_readiness") or "")
        if assessment is not None and readiness in _WAITING_READINESS:
            disposition, bucket, reason = "confirmed_monitoring", "monitoring", readiness
        elif assessment is not None:
            outcomes = {str(value) for value in assessment.get("outcomes", ())}
            reason = (
                "resolved_no_change"
                if outcomes and outcomes <= _NO_CHANGE_OUTCOMES
                else "resolved_assessment"
            )
            disposition, bucket = "confirmed_effective", "history"
        elif acknowledgement is not None:
            disposition, bucket, reason = (
                "confirmed_effective",
                "history",
                "reviewed_inconclusive",
            )
        elif run is not None and run.get("status") in {"queued", "running"}:
            disposition, bucket, reason = (
                "not_confirmed_yet",
                "monitoring",
                "automation_running",
            )
        elif run is not None and run.get("status") == "blocked":
            monitoring_reasons = {
                str(_blocker_context(row).get("monitoring_reason") or "")
                for row in blockers
            }
            if "not_confirmed_as_of" in monitoring_reasons:
                disposition, bucket, reason = (
                    "not_confirmed_yet",
                    "history",
                    "not_confirmed_as_of",
                )
                disposition_as_of = _not_confirmed_disposition_as_of(blockers)
            elif "event_completion_not_confirmed" in monitoring_reasons:
                disposition, bucket, reason = (
                    "not_confirmed_yet",
                    "monitoring",
                    "event_completion_not_confirmed",
                )
            elif blockers and all(_retryable(row) for row in blockers):
                disposition, bucket, reason = (
                    "not_confirmed_yet",
                    "monitoring",
                    "retryable_source_unavailable",
                )
            elif "source_conflict" in blocker_codes:
                disposition, bucket, reason = (
                    "exception_required",
                    "attention",
                    "source_conflict",
                )
            elif blocker_codes & _NONRETRYABLE_PROVIDER_BLOCKERS:
                disposition, bucket, reason = (
                    "exception_required",
                    "attention",
                    "nonretryable_provider_failure",
                )
            elif "sec_evidence_insufficient" in blocker_codes:
                disposition, bucket, reason = (
                    "exception_required",
                    "attention",
                    "ambiguous_event",
                )
            else:
                disposition, bucket, reason = (
                    "exception_required",
                    "attention",
                    "automation_failure",
                )
        elif run is not None and run.get("status") == "failed":
            disposition, bucket, reason = (
                "exception_required",
                "attention",
                "automation_failure",
            )
        elif _latest_automation_draft_requires_review(case, run):
            disposition, bucket, reason = (
                "exception_required",
                "attention",
                "ambiguous_event",
            )
        else:
            disposition, bucket, reason = (
                "not_confirmed_yet",
                "monitoring",
                "awaiting_initial_automation",
            )

    if bucket == "monitoring":
        next_check_at = next_lifecycle_recheck_at(run, assessment, transition)
        if next_check_at is None and reason == "awaiting_initial_automation":
            observation = case.get("observation")
            if isinstance(observation, Mapping) and observation.get("last_observed_at"):
                next_check_at = _timestamp(
                    _instant(observation["last_observed_at"], "observation_last_observed_at")
                )
    else:
        next_check_at = None
    return LifecycleDispositionProjection(
        disposition=disposition,
        queue_bucket=bucket,
        reason_code=reason,
        disposition_as_of=disposition_as_of,
        last_checked_at=last_checked_at,
        next_check_at=next_check_at,
        source_family_status=source_status,
    )


__all__ = [
    "LIFECYCLE_DISPOSITION_REASONS",
    "LIFECYCLE_DISPOSITIONS",
    "LIFECYCLE_QUEUE_BUCKETS",
    "SOURCE_FAMILY_STATES",
    "LifecycleDispositionProjection",
    "next_lifecycle_recheck_at",
    "project_lifecycle_disposition",
]
