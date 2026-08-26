from __future__ import annotations

import json

import pytest

from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
from src.security_lifecycle_disposition import (
    LIFECYCLE_DISPOSITION_REASONS,
    LIFECYCLE_DISPOSITIONS,
    LIFECYCLE_QUEUE_BUCKETS,
    SOURCE_FAMILY_STATES,
    next_lifecycle_recheck_at,
    project_lifecycle_disposition,
)


def _blocker(code: str, *, retryable: bool, context: dict | None = None) -> dict:
    return {
        "blocker_code": code,
        "retryable": retryable,
        "context": context or {},
    }


def _run(
    *,
    status: str = "blocked",
    action_readiness: str | None = None,
    blockers: tuple[dict, ...] = (),
    retry_at: str | None = None,
    updated_at: str = "2026-08-26T00:00:00Z",
    policy_version: str = AUTOMATION_POLICY_VERSION,
    decision_tier: str | None = None,
) -> dict:
    return {
        "run_id": "run-current",
        "status": status,
        "action_readiness": action_readiness,
        "blockers": list(blockers),
        "retry_at": retry_at,
        "updated_at": updated_at,
        "created_at": updated_at,
        "policy_version": policy_version,
        "decision_tier": decision_tier,
    }


def _assessment(
    *,
    outcomes: tuple[str, ...] = ("symbol_changed",),
    effective_date: str | None = None,
    stale: bool = False,
    status: str = "accepted",
) -> dict:
    return {
        "assessment_id": "assessment-current",
        "status": status,
        "author": "automation",
        "stale": stale,
        "outcomes": list(outcomes),
        "effective_date": effective_date,
        "citations": [],
        "automation_run_id": "run-current",
        "created_at": "2026-08-26T00:00:00Z",
    }


def _case(
    *,
    source_presence: str = "present",
    current_assessment: dict | None = None,
    current_acknowledgement: dict | None = None,
    assessment_history: tuple[dict, ...] = (),
    automation_runs: tuple[dict, ...] = (),
    ticker_transition: dict | None = None,
    evidence: tuple[dict, ...] = (),
    automation_facts: tuple[dict, ...] = (),
) -> dict:
    history = list(assessment_history)
    if current_assessment is not None and not history:
        history = [current_assessment]
    return {
        "case_id": "case-1",
        "source_presence": source_presence,
        "observation": {"last_observed_at": "2026-08-25T12:00:00Z"},
        "current_assessment": current_assessment,
        "current_acknowledgement": current_acknowledgement,
        "assessment_history": history,
        "automation_runs": list(automation_runs),
        "ticker_transition": ticker_transition,
        "evidence": list(evidence),
        "automation_facts": list(automation_facts),
    }


@pytest.mark.parametrize(
    ("fixture", "disposition", "bucket", "reason"),
    [
        (_case(), "not_confirmed_yet", "monitoring", "awaiting_initial_automation"),
        (
            _case(automation_runs=(_run(status="running"),)),
            "not_confirmed_yet",
            "monitoring",
            "automation_running",
        ),
        (
            _case(
                current_assessment=_assessment(effective_date="2026-09-05"),
                automation_runs=(_run(action_readiness="waiting_effective_date"),),
            ),
            "confirmed_monitoring",
            "monitoring",
            "waiting_effective_date",
        ),
        (
            _case(
                current_assessment=_assessment(effective_date="2026-08-24"),
                automation_runs=(_run(action_readiness="waiting_market_confirmation"),),
            ),
            "confirmed_monitoring",
            "monitoring",
            "waiting_market_confirmation",
        ),
        (
            _case(
                automation_runs=(
                    _run(
                        blockers=(
                            _blocker("sec_transport_unavailable", retryable=True),
                        ),
                        retry_at="2026-08-27T00:00:00Z",
                    ),
                )
            ),
            "not_confirmed_yet",
            "monitoring",
            "retryable_source_unavailable",
        ),
        (
            _case(
                automation_runs=(
                    _run(
                        blockers=(
                            _blocker(
                                "sec_evidence_insufficient",
                                retryable=True,
                                context={"monitoring_reason": "event_completion_not_confirmed"},
                            ),
                        )
                    ),
                )
            ),
            "not_confirmed_yet",
            "monitoring",
            "event_completion_not_confirmed",
        ),
        (
            _case(
                automation_runs=(
                    _run(
                        blockers=(
                            _blocker("source_conflict", retryable=False),
                        )
                    ),
                )
            ),
            "exception_required",
            "attention",
            "source_conflict",
        ),
        (
            _case(automation_runs=(_run(status="failed"),)),
            "exception_required",
            "attention",
            "automation_failure",
        ),
        (
            _case(current_assessment=_assessment(outcomes=("no_tracked_security_change",))),
            "confirmed_effective",
            "history",
            "resolved_no_change",
        ),
        (
            _case(current_assessment=_assessment()),
            "confirmed_effective",
            "history",
            "resolved_assessment",
        ),
        (
            _case(
                ticker_transition={
                    "status": "approved",
                    "execute_on": "2026-09-05",
                    "automation_policy_version": AUTOMATION_POLICY_VERSION,
                }
            ),
            "confirmed_monitoring",
            "monitoring",
            "waiting_effective_date",
        ),
        (
            _case(ticker_transition={"status": "applied"}),
            "confirmed_effective",
            "history",
            "transition_applied",
        ),
        (
            _case(ticker_transition={"status": "needs_review"}),
            "exception_required",
            "attention",
            "transition_needs_review",
        ),
        (
            _case(
                assessment_history=(_assessment(stale=True),),
                automation_runs=(_run(status="succeeded"),),
            ),
            "not_confirmed_yet",
            "monitoring",
            "awaiting_initial_automation",
        ),
        (
            _case(current_acknowledgement={"acknowledgement_id": "ack-1"}),
            "confirmed_effective",
            "history",
            "reviewed_inconclusive",
        ),
        (
            _case(
                automation_runs=(
                    _run(
                        blockers=(
                            _blocker(
                                "sec_evidence_insufficient",
                                retryable=False,
                                context={
                                    "monitoring_reason": "not_confirmed_as_of",
                                    "as_of": "2026-10-15",
                                },
                            ),
                        )
                    ),
                )
            ),
            "confirmed_effective",
            "history",
            "not_confirmed_as_of",
        ),
    ],
)
def test_disposition_projection_is_exhaustive(fixture, disposition, bucket, reason):
    got = project_lifecycle_disposition(fixture)
    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        disposition,
        bucket,
        reason,
    )
    assert got.disposition in LIFECYCLE_DISPOSITIONS
    assert got.queue_bucket in LIFECYCLE_QUEUE_BUCKETS
    assert got.reason_code in LIFECYCLE_DISPOSITION_REASONS


def test_source_missing_precedes_old_accepted_assessment():
    got = project_lifecycle_disposition(
        _case(
            source_presence="source_missing",
            current_assessment=_assessment(),
        )
    )
    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "exception_required",
        "attention",
        "source_missing",
    )


def test_stale_automation_transition_is_monitoring_until_current_revalidation():
    got = project_lifecycle_disposition(
        _case(
            ticker_transition={
                "status": "approved",
                "execute_on": "2026-08-27",
                "approval_authority": "automation_policy",
                "automation_policy_version": "trusted-lifecycle-automation-old",
            }
        )
    )
    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "not_confirmed_yet",
        "monitoring",
        "waiting_transition_revalidation",
    )
    assert got.next_check_at == "2026-08-27T00:00:00Z"


def test_source_family_status_uses_current_run_citations_and_typed_families():
    assessment = _assessment()
    assessment["citations"] = [
        {
            "reference_kind": "evidence",
            "evidence_id": "market-current",
            "cited_content_sha256": "a" * 64,
        }
    ]
    got = project_lifecycle_disposition(
        _case(
            current_assessment=assessment,
            automation_runs=(
                _run(
                    blockers=(
                        _blocker("sec_transport_unavailable", retryable=True),
                    ),
                ),
            ),
            evidence=(
                {
                    "evidence_id": "sec-current",
                    "source_family": "regulator",
                    "automation_run_id": "run-current",
                },
                {
                    "evidence_id": "market-current",
                    "source_family": "market_infrastructure",
                    "automation_run_id": "run-current",
                },
                {
                    "evidence_id": "publisher-old",
                    "source_family": "publisher",
                    "automation_run_id": "run-old",
                },
                {
                    "evidence_id": "manual-current",
                    "source_family": "manual",
                    "automation_run_id": None,
                },
            ),
        )
    )
    assert got.source_family_status == {
        "regulator": "unavailable",
        "market_infrastructure": "confirmed",
        "publisher": "missing",
        "general_web": "missing",
        "manual": "present",
    }
    assert set(got.source_family_status.values()) <= SOURCE_FAMILY_STATES


def test_conflicting_current_fact_values_mark_only_their_source_families():
    got = project_lifecycle_disposition(
        _case(
            automation_runs=(
                _run(blockers=(_blocker("source_conflict", retryable=False),)),
            ),
            automation_facts=(
                {
                    "automation_run_id": "run-current",
                    "source_family": "regulator",
                    "fact_type": "successor_ticker",
                    "normalized_value": "AAA",
                },
                {
                    "automation_run_id": "run-current",
                    "source_family": "publisher",
                    "fact_type": "successor_ticker",
                    "normalized_value": "BBB",
                },
            ),
        )
    )
    assert got.source_family_status["regulator"] == "conflict"
    assert got.source_family_status["publisher"] == "conflict"
    assert got.source_family_status["market_infrastructure"] == "missing"


def test_invalid_blocker_context_json_fails_closed():
    blocker = _blocker("sec_evidence_insufficient", retryable=True)
    blocker.pop("context")
    blocker["context_json"] = json.dumps(["not", "a", "mapping"])
    with pytest.raises(ValueError, match="automation_blocker_context"):
        project_lifecycle_disposition(
            _case(automation_runs=(_run(blockers=(blocker,)),))
        )


def test_market_recheck_is_daily_for_first_seven_days_then_weekly():
    assert next_lifecycle_recheck_at(
        _run(
            action_readiness="waiting_market_confirmation",
            updated_at="2026-08-26T00:00:00Z",
        ),
        _assessment(effective_date="2026-08-24"),
    ) == "2026-08-27T00:00:00Z"
    assert next_lifecycle_recheck_at(
        _run(
            action_readiness="waiting_market_confirmation",
            updated_at="2026-09-10T00:00:00Z",
        ),
        _assessment(effective_date="2026-08-24"),
    ) == "2026-09-17T00:00:00Z"


def test_effective_date_is_the_first_due_time():
    assert next_lifecycle_recheck_at(
        _run(action_readiness="waiting_effective_date"),
        _assessment(effective_date="2026-09-05"),
    ) == "2026-09-05T00:00:00Z"


def test_retry_at_transition_execute_on_and_unprocessed_due_time_are_preserved():
    assert next_lifecycle_recheck_at(
        _run(retry_at="2026-08-28T01:02:03Z"),
        None,
    ) == "2026-08-28T01:02:03Z"
    assert next_lifecycle_recheck_at(
        None,
        None,
        {"status": "approved", "execute_on": "2026-09-05"},
    ) == "2026-09-05T00:00:00Z"
    assert project_lifecycle_disposition(_case()).next_check_at == "2026-08-25T12:00:00Z"
