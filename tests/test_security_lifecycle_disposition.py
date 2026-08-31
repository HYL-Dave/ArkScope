from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

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


_ROOT = Path(__file__).resolve().parents[1]
_DISPOSITION_SOURCE = _ROOT / "src/security_lifecycle_disposition.py"
_SCHEMA_SOURCE = _ROOT / "src/security_lifecycle_schema.py"
_AUTOMATION_RUNTIME_SOURCE = (
    _ROOT / "src/service/security_lifecycle_automation_runtime.py"
)
_AUTOMATION_SCHEDULER_SOURCE = (
    _ROOT / "src/service/security_lifecycle_automation_scheduler.py"
)
_FRONTEND_API_SOURCE = _ROOT / "apps/arkscope-web/src/api.ts"
_TYPESCRIPT_STRING = re.compile(r'"(?:\\.|[^"\\])*"')


class _UnsupportedVocabularyExpression(ValueError):
    pass


def _python_string_members(
    node: ast.AST,
    known: dict[str, frozenset[str]],
) -> frozenset[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return frozenset({node.value})
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        members: set[str] = set()
        for item in node.elts:
            members.update(_python_string_members(item, known))
        return frozenset(members)
    if isinstance(node, ast.Name):
        if node.id not in known:
            raise _UnsupportedVocabularyExpression(node.id)
        return known[node.id]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"frozenset", "set", "tuple"}
        and len(node.args) == 1
        and not node.keywords
    ):
        return _python_string_members(node.args[0], known)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Literal"
    ):
        return _python_string_members(node.slice, known)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _python_string_members(node.left, known) | _python_string_members(
            node.right, known
        )
    raise _UnsupportedVocabularyExpression(ast.dump(node, include_attributes=False))


def _python_string_authority(path: Path, name: str) -> frozenset[str]:
    known: dict[str, frozenset[str]] = {}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        target: ast.AST | None = None
        value: ast.AST | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        try:
            known[target.id] = _python_string_members(value, known)
        except _UnsupportedVocabularyExpression:
            known.pop(target.id, None)
    assert name in known, f"closed Python vocabulary not found: {path}:{name}"
    return known[name]


def _typescript_literal_members(body: str, *, separator: str) -> frozenset[str]:
    literals = _TYPESCRIPT_STRING.findall(body)
    remainder = _TYPESCRIPT_STRING.sub("", body)
    assert literals, "closed TypeScript vocabulary has no string literals"
    assert re.fullmatch(rf"[\s{re.escape(separator)}]*", remainder), (
        f"unsupported TypeScript vocabulary expression: {body.strip()}"
    )
    return frozenset(json.loads(literal) for literal in literals)


def _typescript_string_union(source: str, name: str) -> frozenset[str]:
    declaration = re.search(rf"\bexport\s+type\s+{re.escape(name)}\s*=", source)
    assert declaration is not None, f"closed TypeScript union not found: {name}"
    end = source.find(";", declaration.end())
    assert end >= 0, f"unterminated TypeScript union: {name}"
    return _typescript_literal_members(
        source[declaration.end() : end], separator="|"
    )


def _typescript_string_array(source: str, name: str) -> frozenset[str]:
    declaration = re.search(
        rf"\bconst\s+{re.escape(name)}\b[^=]*=\s*\[", source
    )
    assert declaration is not None, f"closed TypeScript array not found: {name}"
    end = source.find("];", declaration.end())
    assert end >= 0, f"unterminated TypeScript array: {name}"
    return _typescript_literal_members(
        source[declaration.end() : end], separator=","
    )


def _vocabulary_mismatches(
    backend: dict[str, frozenset[str]],
    frontend: dict[str, frozenset[str]],
) -> dict[str, dict[str, list[str]]]:
    return {
        name: {
            "backend_only": sorted(backend[name] - frontend[name]),
            "frontend_only": sorted(frontend[name] - backend[name]),
        }
        for name in backend
        if backend[name] != frontend[name]
    }


def test_backend_and_frontend_lifecycle_vocabularies_have_exact_parity():
    frontend_source = _FRONTEND_API_SOURCE.read_text(encoding="utf-8")
    backend = {
        "automation_stages": _python_string_authority(
            _AUTOMATION_RUNTIME_SOURCE, "LifecycleAutomationStage"
        ),
        "failure_reasons": _python_string_authority(
            _AUTOMATION_SCHEDULER_SOURCE, "_REASONS"
        ),
        "disposition_reasons": _python_string_authority(
            _DISPOSITION_SOURCE, "LIFECYCLE_DISPOSITION_REASONS"
        ),
        "disposition_values": _python_string_authority(
            _DISPOSITION_SOURCE, "LIFECYCLE_DISPOSITIONS"
        ),
        "queue_buckets": _python_string_authority(
            _DISPOSITION_SOURCE, "LIFECYCLE_QUEUE_BUCKETS"
        ),
        "blocker_codes": _python_string_authority(
            _SCHEMA_SOURCE, "AUTOMATION_BLOCKER_CODES"
        ),
        "automation_triggers": _python_string_authority(
            _AUTOMATION_RUNTIME_SOURCE, "LifecycleAutomationTrigger"
        ),
        "source_family_states": _python_string_authority(
            _DISPOSITION_SOURCE, "SOURCE_FAMILY_STATES"
        ),
    }
    frontend = {
        "automation_stages": _typescript_string_union(
            frontend_source, "SecurityLifecycleAutomationStage"
        ),
        "failure_reasons": _typescript_string_union(
            frontend_source, "SecurityLifecycleAutomationFailureReason"
        ),
        "disposition_reasons": _typescript_string_union(
            frontend_source, "SecurityLifecycleDispositionReason"
        ),
        "disposition_values": _typescript_string_union(
            frontend_source, "SecurityLifecycleDisposition"
        ),
        "queue_buckets": _typescript_string_union(
            frontend_source, "SecurityLifecycleQueueBucket"
        ),
        "blocker_codes": _typescript_string_union(
            frontend_source, "SecurityLifecycleAutomationBlockerCode"
        ),
        "automation_triggers": _typescript_string_union(
            frontend_source, "SecurityLifecycleAutomationTrigger"
        ),
        "source_family_states": _typescript_string_union(
            frontend_source, "SecurityLifecycleSourceFamilyState"
        ),
    }

    assert backend["automation_stages"] == _python_string_authority(
        _AUTOMATION_RUNTIME_SOURCE, "LIFECYCLE_AUTOMATION_STAGE_ORDER"
    )
    assert backend["automation_stages"] == frontend["automation_stages"]
    assert frontend["automation_stages"] == _typescript_string_array(
        frontend_source, "AUTOMATION_STAGES"
    )
    assert backend["failure_reasons"] == frontend["failure_reasons"]
    assert frontend["failure_reasons"] == _typescript_string_array(
        frontend_source, "AUTOMATION_REASONS"
    )
    assert backend["automation_triggers"] == _python_string_authority(
        _AUTOMATION_RUNTIME_SOURCE, "_LIFECYCLE_AUTOMATION_TRIGGERS"
    )
    assert backend == frontend, _vocabulary_mismatches(backend, frontend)


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
    query_context: dict | None = None,
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
        "query_context": query_context or {},
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
    observation_fingerprint_sha256: str | None = None,
) -> dict:
    history = list(assessment_history)
    if current_assessment is not None and not history:
        history = [current_assessment]
    case = {
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
    if observation_fingerprint_sha256 is not None:
        case["observation_fingerprint_sha256"] = observation_fingerprint_sha256
    return case


def _manual_evidence_digest(*rows: tuple[str, str]) -> str:
    payload = "".join(
        f"{evidence_id}\t{content_sha256}\n"
        for evidence_id, content_sha256 in sorted(rows)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_unresolved_terminal_finalization_failure_preempts_accepted_history():
    failure = {
        "attempt_count": 2,
        "code": "finalization_failed",
        "failed_at": "2026-08-26T01:00:00Z",
        "retry_not_before": "2026-08-26T02:00:00Z",
    }
    got = project_lifecycle_disposition(
        _case(
            current_assessment=_assessment(),
            automation_runs=(
                _run(
                    status="succeeded",
                    decision_tier="verified_automatic",
                    query_context={"terminal_finalization_failure": failure},
                ),
            ),
        )
    )

    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "exception_required",
        "attention",
        "automation_finalization_failure",
    )
    assert got.next_check_at is None


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
    assert got.disposition_as_of is None


def _not_confirmed_as_of_context(**overrides: object) -> dict:
    return {
        "monitoring_reason": "not_confirmed_as_of",
        "as_of": "2026-08-27",
        "source_deadline": "2026-04-01",
        "source_deadline_evidence_id": "sle_deadline",
        "source_deadline_span_start_byte": 0,
        "source_deadline_span_end_byte": 64,
        "source_deadline_cited_text_sha256": "a" * 64,
        "source_deadline_rule_id": "sec.explicit_transaction_termination_date",
        "source_deadline_rule_version": "4",
    } | overrides


def test_not_confirmed_as_of_projects_the_actual_completed_check_date():
    fixture = _case(
        automation_runs=(
            _run(
                blockers=(
                    _blocker(
                        "sec_evidence_insufficient",
                        retryable=False,
                        context=_not_confirmed_as_of_context(),
                    ),
                ),
            ),
        ),
    )

    got = project_lifecycle_disposition(fixture)

    assert (
        got.disposition,
        got.queue_bucket,
        got.reason_code,
        got.disposition_as_of,
    ) == (
        "not_confirmed_yet",
        "history",
        "not_confirmed_as_of",
        "2026-08-27",
    )
    assert got.next_check_at is None


@pytest.mark.parametrize(
    "contexts",
    [
        (_not_confirmed_as_of_context(as_of=None),),
        (_not_confirmed_as_of_context(as_of="2026-08-27T12:00:00Z"),),
        (
            _not_confirmed_as_of_context(as_of="2026-08-27"),
            _not_confirmed_as_of_context(as_of="2026-08-28"),
        ),
    ],
)
def test_not_confirmed_as_of_requires_one_valid_completed_check_date(contexts):
    fixture = _case(
        automation_runs=(
            _run(
                blockers=tuple(
                    _blocker(
                        f"sec_evidence_insufficient_{index}",
                        retryable=False,
                        context=context,
                    )
                    for index, context in enumerate(contexts)
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="^disposition_as_of$"):
        project_lifecycle_disposition(fixture)


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


def test_stale_automation_transition_rechecks_before_later_execute_on():
    assert next_lifecycle_recheck_at(
        _run(
            action_readiness="waiting_transition_revalidation",
            updated_at="2026-08-26T00:00:00Z",
        ),
        None,
        {
            "status": "approved",
            "execute_on": "2026-09-05",
            "approval_authority": "automation_policy",
            "automation_policy_version": "trusted-lifecycle-automation-old",
        },
    ) == "2026-08-27T00:00:00Z"


def test_latest_run_uses_the_current_manual_evidence_digest():
    observation = "a" * 64
    current_content = "b" * 64
    current_digest = _manual_evidence_digest(("manual-current", current_content))
    stale_run = _run(
        blockers=(
            _blocker(
                "sec_evidence_insufficient",
                retryable=False,
                context=_not_confirmed_as_of_context(),
            ),
        ),
    )
    stale_run.update(
        {
            "run_id": "run-stale",
            "observation_fingerprint_sha256": observation,
            "query_context": {"input_evidence_set_sha256": "c" * 64},
        }
    )
    current_run = _run(status="running")
    current_run.update(
        {
            "run_id": "run-current",
            "observation_fingerprint_sha256": observation,
            "query_context": {"input_evidence_set_sha256": current_digest},
        }
    )

    got = project_lifecycle_disposition(
        _case(
            observation_fingerprint_sha256=observation,
            automation_runs=(stale_run, current_run),
            evidence=(
                {
                    "evidence_id": "manual-current",
                    "content_sha256": current_content,
                    "automation_run_id": None,
                    "source_family": "manual",
                },
                {
                    "evidence_id": "automation-output",
                    "content_sha256": "d" * 64,
                    "automation_run_id": "run-stale",
                    "source_family": "publisher",
                },
            ),
        )
    )

    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "not_confirmed_yet",
        "monitoring",
        "automation_running",
    )


def test_stale_automation_assessment_prevents_applied_transition_from_masking_fresh_run():
    observation = "a" * 64
    current_run = _run(status="running")
    current_run.update(
        {
            "observation_fingerprint_sha256": observation,
            "query_context": {
                "input_evidence_set_sha256": _manual_evidence_digest()
            },
        }
    )
    stale_assessment = _assessment(stale=True)
    stale_assessment.update(
        {
            "observation_fingerprint_sha256": observation,
            "evidence_set_sha256": "b" * 64,
            "decision_provenance_sha256": "c" * 64,
        }
    )

    got = project_lifecycle_disposition(
        _case(
            observation_fingerprint_sha256=observation,
            current_assessment=stale_assessment,
            automation_runs=(current_run,),
            ticker_transition={
                "status": "applied",
                "approval_authority": "automation_policy",
                "observation_fingerprint_sha256": observation,
                "decision_provenance_sha256": "c" * 64,
                "approved_preview": {
                    "assessment_id": "assessment-current",
                    "evidence_set_sha256": "b" * 64,
                    "observation_fingerprint_sha256": observation,
                },
            },
        )
    )

    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "not_confirmed_yet",
        "monitoring",
        "automation_running",
    )


def _automation_transition_fixture(
    *,
    assessment_id: str = "assessment-current",
    evidence_set_sha256: str = "b" * 64,
    decision_provenance_sha256: str = "c" * 64,
) -> dict:
    observation = "a" * 64
    return {
        "status": "applied",
        "approval_authority": "automation_policy",
        "observation_fingerprint_sha256": observation,
        "decision_provenance_sha256": decision_provenance_sha256,
        "approved_preview": {
            "assessment_id": assessment_id,
            "evidence_set_sha256": evidence_set_sha256,
            "observation_fingerprint_sha256": observation,
        },
    }


def _current_automation_assessment() -> dict:
    assessment = _assessment()
    assessment.update(
        {
            "observation_fingerprint_sha256": "a" * 64,
            "evidence_set_sha256": "b" * 64,
            "decision_provenance_sha256": "c" * 64,
        }
    )
    return assessment


def test_exact_current_automation_transition_remains_visible():
    got = project_lifecycle_disposition(
        _case(
            observation_fingerprint_sha256="a" * 64,
            current_assessment=_current_automation_assessment(),
            ticker_transition=_automation_transition_fixture(),
        )
    )

    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "confirmed_effective",
        "history",
        "transition_applied",
    )


@pytest.mark.parametrize(
    "transition",
    [
        _automation_transition_fixture(assessment_id="assessment-stale"),
        _automation_transition_fixture(evidence_set_sha256="d" * 64),
        _automation_transition_fixture(decision_provenance_sha256="e" * 64),
    ],
    ids=("assessment-id", "evidence-set", "decision-provenance"),
)
def test_stale_automation_transition_artifact_does_not_mask_current_run(transition):
    current_run = _run(status="running")
    current_run.update(
        {
            "observation_fingerprint_sha256": "a" * 64,
            "query_context": {
                "input_evidence_set_sha256": _manual_evidence_digest()
            },
        }
    )

    got = project_lifecycle_disposition(
        _case(
            observation_fingerprint_sha256="a" * 64,
            current_assessment=_current_automation_assessment(),
            automation_runs=(current_run,),
            ticker_transition=transition,
        )
    )

    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "confirmed_effective",
        "history",
        "resolved_assessment",
    )


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
        "manual": "present",
        "listing_authority": "missing",
    }
    assert set(got.source_family_status.values()) <= SOURCE_FAMILY_STATES


def test_ibkr_missing_is_present_evidence_while_ambiguity_is_conflict():
    missing = project_lifecycle_disposition(
        _case(
            automation_runs=(
                _run(blockers=(_blocker("ibkr_contract_missing", retryable=True),)),
            ),
            evidence=(
                {
                    "evidence_id": "market-missing",
                    "source_family": "market_infrastructure",
                    "automation_run_id": "run-current",
                },
            ),
        )
    )
    ambiguous = project_lifecycle_disposition(
        _case(
            automation_runs=(
                _run(
                    blockers=(
                        _blocker("ibkr_contract_ambiguous", retryable=False),
                    )
                ),
            ),
        )
    )

    assert missing.source_family_status["market_infrastructure"] == "present"
    assert ambiguous.source_family_status["market_infrastructure"] == "conflict"


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
    assert got.source_family_status["regulator"] == "missing"
    assert got.source_family_status["market_infrastructure"] == "missing"
    assert "publisher" not in got.source_family_status


def test_legacy_publisher_rows_and_blockers_do_not_affect_active_source_projection():
    got = project_lifecycle_disposition(
        _case(
            automation_runs=(
                _run(
                    blockers=(
                        _blocker("internal_news_unavailable", retryable=True),
                    )
                ),
            ),
            evidence=(
                {
                    "evidence_id": "publisher-old",
                    "source_family": "publisher",
                    "automation_run_id": "run-current",
                },
            ),
        )
    )

    assert set(got.source_family_status) == {
        "regulator",
        "listing_authority",
        "market_infrastructure",
        "manual",
    }
    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "not_confirmed_yet",
        "monitoring",
        "awaiting_initial_automation",
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("listing_directory_unavailable", "unavailable"),
        ("massive_reference_unavailable", "unavailable"),
        ("listing_authority_conflict", "conflict"),
    ],
)
def test_listing_blockers_project_to_listing_authority_component(code, expected):
    got = project_lifecycle_disposition(
        _case(
            automation_runs=(
                _run(
                    blockers=(
                        _blocker(
                            code,
                            retryable=code != "listing_authority_conflict",
                        ),
                    )
                ),
            )
        )
    )

    assert got.source_family_status["listing_authority"] == expected
    if code == "listing_authority_conflict":
        assert (got.queue_bucket, got.reason_code) == ("attention", "source_conflict")


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


def test_pre_effective_undetermined_draft_is_successful_monitoring():
    draft = _assessment(
        outcomes=("undetermined",),
        effective_date="2026-09-05",
        status="draft",
    )
    got = project_lifecycle_disposition(
        _case(
            assessment_history=(draft,),
            automation_runs=(
                _run(
                    status="succeeded",
                    action_readiness="waiting_effective_date",
                    decision_tier="verified_automatic",
                ),
            ),
        )
    )

    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        "confirmed_monitoring",
        "monitoring",
        "waiting_effective_date",
    )
    assert got.next_check_at == "2026-09-05T00:00:00Z"


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
