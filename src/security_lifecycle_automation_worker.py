"""Bounded orchestration for deterministic security-lifecycle automation."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, ContextManager

from src.security_lifecycle_decision_policy import (
    AUTOMATION_POLICY_VERSION,
    AutomationDecision,
    evaluate_automation_decision,
)
from src.security_lifecycle_fact_kernel import (
    AutomationBlocker,
    SecurityLifecycleFactKernel,
)
from src.security_lifecycle_investigation import (
    SecurityLifecycleInvestigationStore,
    create_automation_assessment,
)
from src.security_lifecycle_disposition import next_lifecycle_recheck_at
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    LifecycleWritesUnavailable,
)


AUTOMATION_EXECUTION_REVISION = "trusted-lifecycle-execution-r1"
_MAX_CASES_PER_TICK = 2
_DECISION_FIELDS = tuple(AutomationDecision.__dataclass_fields__)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LifecycleAutomationEvidenceBundle:
    evidence: tuple[object, ...]
    facts: tuple[object, ...]
    blockers: tuple[AutomationBlocker, ...]
    diagnostics: Mapping[str, int]
    retry_at: str | None


def _instant(value: str) -> datetime:
    text = str(value or "").strip()
    parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
    parsed = datetime.fromisoformat(parseable)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("automation_clock")
    return parsed.astimezone(timezone.utc)


def _field(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _fact_value(value: object) -> Any:
    normalized = _field(value, "normalized_value")
    if normalized is not None:
        return normalized
    encoded = _field(value, "normalized_value_json")
    if encoded is None:
        return None
    return json.loads(str(encoded))


def _blocker_code(value: object) -> str:
    return str(_field(value, "code", _field(value, "blocker_code", "")) or "")


def _case_context(case: Mapping[str, object]) -> dict[str, object]:
    observation = case.get("observation")
    source = observation if isinstance(observation, Mapping) else case
    return {
        **dict(source),
        "case_id": str(case["case_id"]),
        "ticker": str(case["ticker"]),
        "cik": source.get("cik"),
    }


def _query_context(case: Mapping[str, object], *, mode: str) -> dict[str, object]:
    observation = case.get("observation")
    source = observation if isinstance(observation, Mapping) else case
    kinds = source.get("kinds", ())
    return {
        "case_id": str(case["case_id"]),
        "cik": source.get("cik"),
        "filing_date": source.get("filing_date"),
        "mode": mode,
        "source": str(case["source"]),
        "source_ref": str(case["source_ref"]),
        "ticker": str(case["ticker"]),
        "event_kinds": sorted(
            {
                str(item.get("event_type"))
                for item in kinds
                if isinstance(item, Mapping) and item.get("event_type")
            }
        ),
    }


def _decision_context(decision: AutomationDecision) -> dict[str, object]:
    return {
        name: (
            list(value)
            if name in {"outcomes", "decision_issues"}
            else value
        )
        for name in _DECISION_FIELDS
        for value in (getattr(decision, name),)
    }


def _persisted_terminal_decision(
    run: Mapping[str, object],
) -> tuple[AutomationDecision, str]:
    raw_context = run.get("query_context_json")
    if not isinstance(raw_context, str):
        raise ValueError("terminal_query_context")
    try:
        context = json.loads(raw_context)
    except json.JSONDecodeError as exc:
        raise ValueError("terminal_query_context") from exc
    if not isinstance(context, Mapping):
        raise ValueError("terminal_query_context")
    raw_decision = context.get("terminal_decision")
    provenance = context.get("terminal_decision_provenance_sha256")
    if not isinstance(raw_decision, Mapping) or set(raw_decision) != set(
        _DECISION_FIELDS
    ):
        raise ValueError("terminal_decision")
    values = dict(raw_decision)
    for name in ("outcomes", "decision_issues"):
        sequence = values.get(name)
        if not isinstance(sequence, list) or not all(
            isinstance(value, str) for value in sequence
        ):
            raise ValueError("terminal_decision")
        values[name] = tuple(sequence)
    if type(values.get("transition_requested")) is not bool:
        raise ValueError("terminal_decision")
    decision = AutomationDecision(**values)
    if _decision_context(decision) != dict(raw_decision):
        raise ValueError("terminal_decision")
    if not isinstance(provenance, str) or len(provenance) != 64:
        raise ValueError("terminal_decision_provenance")
    return decision, provenance


def _transition_request(
    case: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    outcomes = tuple(str(value) for value in _field(decision, "outcomes", ()))
    if outcomes == ("listing_ended",):
        transition_kind = "terminal_delisting"
    elif "symbol_changed" in outcomes:
        transition_kind = "symbol_continuation"
    else:
        raise ValueError("automation_transition_request")
    return {
        "transition_kind": transition_kind,
        "source_ticker": str(case.get("ticker") or "").upper(),
        "successor_ticker": _field(decision, "successor_ticker"),
        "effective_date": _field(decision, "effective_date"),
        "outcomes": outcomes,
    }


def _persisted_material(
    conn: sqlite3.Connection,
    run_id: str,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    evidence = tuple(
        dict(row)
        for row in conn.execute(
            "SELECT * FROM security_lifecycle_evidence "
            "WHERE automation_run_id=? ORDER BY evidence_id",
            (run_id,),
        )
    )
    facts = tuple(
        dict(row)
        for row in conn.execute(
            "SELECT * FROM security_lifecycle_automation_facts "
            "WHERE automation_run_id=? ORDER BY fact_id",
            (run_id,),
        )
    )
    return evidence, facts


def _failure_code(exc: Exception, *, phase: str) -> str:
    if isinstance(exc, (TypeError, AttributeError)):
        return "internal_error"
    if isinstance(exc, (LifecycleSchemaMismatch, LifecycleWritesUnavailable)):
        return "profile_schema_mismatch"
    if isinstance(exc, sqlite3.Error):
        return "persistence_failed"
    if isinstance(exc, ValueError):
        if phase == "persist":
            return "persistence_failed"
        return "source_payload_invalid" if phase == "acquire" else "extractor_failed"
    return "internal_error"


@contextmanager
def _owned_profile_context(
    connection_factory: Callable[[], ContextManager[sqlite3.Connection]],
    *,
    execution_owner_id: str,
    at: str,
) -> Iterator[tuple[SecurityLifecycleInvestigationStore, SecurityLifecycleFactKernel]]:
    with connection_factory() as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        kernel = SecurityLifecycleFactKernel(store)
        active_failure = False
        try:
            yield store, kernel
        except BaseException:
            active_failure = True
            raise
        finally:
            try:
                kernel.reconcile_running_runs(
                    execution_owner_id=execution_owner_id,
                    at=at,
                )
            except Exception as exc:
                if not active_failure:
                    raise
                logger.warning(
                    "security lifecycle owner cleanup failed code=%s",
                    type(exc).__name__,
                )


class LifecycleAutomationWorker:
    def __init__(
        self,
        *,
        case_loader: Callable[[], Iterable[Mapping[str, object]]],
        profile_connection: Callable[[], ContextManager[sqlite3.Connection]],
        evidence_loader: Callable[..., LifecycleAutomationEvidenceBundle],
        source_loader: Callable[[], Mapping[str, Iterable[str]]],
        transition_preview: Callable[..., Mapping[str, object]],
        transition_approver: Callable[..., Mapping[str, object]],
        clock: Callable[[], str],
        execution_owner_id: str,
    ):
        dependencies = {
            "case_loader": case_loader,
            "profile_connection": profile_connection,
            "evidence_loader": evidence_loader,
            "source_loader": source_loader,
            "transition_preview": transition_preview,
            "transition_approver": transition_approver,
            "clock": clock,
        }
        if any(not callable(value) for value in dependencies.values()):
            raise TypeError("automation_worker_dependency")
        if (
            type(execution_owner_id) is not str
            or not execution_owner_id
            or "\0" in execution_owner_id
            or len(execution_owner_id.encode("utf-8")) > 64
        ):
            raise ValueError("execution_owner_id")
        self._case_loader = case_loader
        self._profile_connection = profile_connection
        self._evidence_loader = evidence_loader
        self._source_loader = source_loader
        self._transition_preview = transition_preview
        self._transition_approver = transition_approver
        self._clock = clock
        self._execution_owner_id = execution_owner_id

    @staticmethod
    def _due_recheck(
        store: SecurityLifecycleInvestigationStore,
        assessment: Mapping[str, object] | None,
        *,
        case_id: str,
        now: datetime,
    ) -> tuple[dict[str, object], str] | None:
        candidate = assessment
        if candidate is None:
            runs = store.list_automation_runs(case_id)
            if not runs:
                return None
            latest_run_id = str(runs[0]["run_id"])
            candidate = next(
                (
                    row
                    for row in store.list_assessments(case_id)
                    if str(row.get("automation_run_id") or "") == latest_run_id
                ),
                None,
            )
        if candidate is None or candidate.get("author") != "automation":
            return None
        run_id = str(candidate.get("automation_run_id") or "")
        if not run_id:
            return None
        run = store.get_automation_run(run_id)
        due_at = next_lifecycle_recheck_at(run, candidate)
        if due_at is None or now < _instant(due_at):
            return None
        return run, due_at

    def _evaluate(
        self,
        *,
        case: Mapping[str, object],
        evidence: Iterable[object],
        facts: Iterable[object],
        current_date: date,
        sources: tuple[str, ...],
    ) -> AutomationDecision:
        def preview(request: Mapping[str, object]) -> Mapping[str, object]:
            return self._transition_preview(
                case=case,
                request=request,
                sources=sources,
            )

        return evaluate_automation_decision(
            case=_case_context(case),
            evidence=evidence,
            facts=facts,
            current_date=current_date,
            active_sources=sources,
            transition_preview=preview,
        )

    def _process_claim(
        self,
        *,
        store: SecurityLifecycleInvestigationStore,
        kernel: SecurityLifecycleFactKernel,
        case: Mapping[str, object],
        run_id: str,
        mode: str,
        at: str,
        now: datetime,
        sources: tuple[str, ...],
        transition_revalidation: bool = False,
        finalization_only: bool = False,
    ) -> str:
        phase = "acquire"
        failure_diagnostics: Mapping[str, int] = {}
        terminal_provenance: str | None = None
        try:
            if transition_revalidation:
                phase = "approve"
                state = store.project_case_state(
                    str(case["case_id"]),
                    observation_fingerprint_sha256=str(
                        case["observation_fingerprint_sha256"]
                    ),
                )
                assessment = state["current_assessment"]
                if not isinstance(assessment, Mapping):
                    raise ValueError("automation_assessment_not_current")
                approved = self._transition_approver(
                    case=case,
                    request=_transition_request(case, assessment),
                    sources=sources,
                )
                if (
                    not isinstance(approved, Mapping)
                    or approved.get("status") != "approved"
                    or approved.get("approval_authority") != "automation_policy"
                ):
                    raise ValueError("automation_transition_approval_changed")
                kernel.complete_transition_revalidation(run_id=run_id, at=at)
                return "accepted"
            if finalization_only:
                phase = "finalize"
                run = store.get_automation_run(run_id)
                if run.get("status") != "succeeded":
                    raise ValueError("automation_run_not_succeeded")
                decision, terminal_provenance = _persisted_terminal_decision(run)
            else:
                bundle = self._evidence_loader(case, mode=mode, at=at)
                if not isinstance(bundle, LifecycleAutomationEvidenceBundle):
                    raise TypeError("automation_evidence_bundle")
                failure_diagnostics = bundle.diagnostics
                existing_evidence, existing_facts = _persisted_material(
                    store.conn,
                    run_id,
                )
                all_evidence = (*existing_evidence, *bundle.evidence)
                all_facts = (*existing_facts, *bundle.facts)
                blockers = bundle.blockers
                blocker_codes = {_blocker_code(value) for value in blockers}
                policy_blocker_codes = {
                    "listing_authority_conflict",
                    "source_conflict",
                }

                decision: AutomationDecision | None = None
                if not blockers or blocker_codes.intersection(policy_blocker_codes):
                    phase = "evaluate"
                    decision = self._evaluate(
                        case=case,
                        evidence=all_evidence,
                        facts=all_facts,
                        current_date=now.date(),
                        sources=sources,
                    )
                    if (
                        "source_conflict" in blocker_codes
                        and decision.rule_id != "lifecycle.source_conflict"
                    ):
                        raise ValueError("source_conflict_decision")
                    if decision.transition_requested:
                        decision = self._evaluate(
                            case=case,
                            evidence=all_evidence,
                            facts=all_facts,
                            current_date=now.date(),
                            sources=sources,
                        )

                if blockers and not blocker_codes.intersection(policy_blocker_codes):
                    phase = "persist"
                    kernel.complete_run(
                        run_id=run_id,
                        evidence=bundle.evidence,
                        facts=bundle.facts,
                        blockers=blockers,
                        decision_tier=None,
                        action_readiness=None,
                        retry_at=bundle.retry_at,
                        diagnostics=bundle.diagnostics,
                        at=at,
                    )
                    return "blocked"

                assert decision is not None
                phase = "persist"
                completed = kernel.complete_run(
                    run_id=run_id,
                    evidence=bundle.evidence,
                    facts=bundle.facts,
                    blockers=blockers,
                    decision_tier=decision.decision_tier,
                    action_readiness=decision.action_readiness,
                    retry_at=(
                        None
                        if blocker_codes.intersection(policy_blocker_codes)
                        else bundle.retry_at
                    ),
                    diagnostics=bundle.diagnostics,
                    at=at,
                    terminal_decision=_decision_context(decision),
                )
                if completed.status == "blocked":
                    return "blocked"
                terminal_provenance = completed.decision_provenance_sha256

            phase = "finalize"
            assert terminal_provenance is not None
            assessment_id = create_automation_assessment(
                store=store,
                run_id=run_id,
                decision=decision,
                observation_fingerprint_sha256=str(
                    case["observation_fingerprint_sha256"]
                ),
                at=at,
            )
            if (
                decision.action_readiness == "waiting_effective_date"
                and decision.outcomes == ("undetermined",)
            ):
                kernel.complete_terminal_finalization(
                    run_id=run_id,
                    decision_provenance_sha256=terminal_provenance,
                )
                return "drafted"
            if decision.decision_tier == "verified_automatic":
                assessment = store.get_assessment(assessment_id)
                if assessment["status"] == "draft":
                    store.accept_assessment(
                        assessment_id,
                        observation_fingerprint_sha256=str(
                            case["observation_fingerprint_sha256"]
                        ),
                        acceptance_authority="automation_policy",
                        at=at,
                    )
                elif not (
                    assessment["status"] == "accepted"
                    and assessment["acceptance_authority"]
                    in {"automation_policy", "human"}
                ):
                    raise ValueError("automation_assessment_not_accepted")
                proposals = store.generate_action_proposals(
                    case_id=str(case["case_id"]),
                    observation_fingerprint_sha256=str(
                        case["observation_fingerprint_sha256"]
                    ),
                    sources_by_ticker={str(case["ticker"]): sources},
                    at=at,
                )
                if proposals.get("block_reason") is not None:
                    raise ValueError("automation_proposals_blocked")
                if decision.transition_requested:
                    phase = "approve"
                    approved = self._transition_approver(
                        case=case,
                        request=_transition_request(case, decision),
                        sources=sources,
                    )
                    if (
                        not isinstance(approved, Mapping)
                        or approved.get("status") != "approved"
                        or approved.get("approval_authority") != "automation_policy"
                    ):
                        raise ValueError("automation_transition_approval_changed")
                phase = "finalize"
                kernel.complete_terminal_finalization(
                    run_id=run_id,
                    decision_provenance_sha256=terminal_provenance,
                )
                return "accepted"

            kernel.complete_terminal_finalization(
                run_id=run_id,
                decision_provenance_sha256=terminal_provenance,
            )
            return "drafted"
        except Exception as exc:
            if phase == "approve":
                blocker_code = (
                    "transition_approval_changed"
                    if isinstance(exc, ValueError)
                    else "transition_approval_unavailable"
                )
                try:
                    kernel.defer_transition_revalidation(
                        run_id=run_id,
                        blocker_code=blocker_code,
                        at=at,
                    )
                except (KeyError, ValueError, RuntimeError, sqlite3.Error):
                    return "failed"
                if terminal_provenance is not None:
                    try:
                        kernel.complete_terminal_finalization(
                            run_id=run_id,
                            decision_provenance_sha256=terminal_provenance,
                        )
                    except (KeyError, ValueError, RuntimeError, sqlite3.Error):
                        return "failed"
                return "accepted"
            if phase == "finalize":
                try:
                    kernel.record_terminal_finalization_failure(
                        run_id=run_id,
                        code="finalization_failed",
                        at=at,
                    )
                except (KeyError, ValueError, RuntimeError, sqlite3.Error):
                    pass
                return "failed"
            failure_code = _failure_code(exc, phase=phase)
            diagnostics = dict(failure_diagnostics)
            diagnostics["failures"] = diagnostics.get("failures", 0) + 1
            try:
                kernel.fail_run(
                    run_id=run_id,
                    failure_code=failure_code,
                    diagnostics=diagnostics,
                    at=at,
                )
            except (KeyError, ValueError, RuntimeError, sqlite3.Error):
                if diagnostics != {"failures": 1}:
                    try:
                        kernel.fail_run(
                            run_id=run_id,
                            failure_code=failure_code,
                            diagnostics={"failures": 1},
                            at=at,
                        )
                    except (KeyError, ValueError, RuntimeError, sqlite3.Error):
                        pass
            return "failed"

    def run(self, limit: int = 2, mode: str = "live") -> dict[str, object]:
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit")
        bounded_limit = min(limit, _MAX_CASES_PER_TICK)
        at = str(self._clock())
        now = _instant(at)
        sources_by_ticker = self._source_loader()
        if not isinstance(sources_by_ticker, Mapping):
            raise TypeError("source_loader")
        raw_cases = tuple(self._case_loader())
        cases = sorted(
            (
                case
                for case in raw_cases
                if isinstance(case, Mapping)
                and case.get("source_presence") == "present"
            ),
            key=lambda item: str(item.get("case_id") or ""),
        )
        summary: dict[str, object] = {
            "case_ids": [],
            "selected": 0,
            "processed": 0,
            "accepted": 0,
            "drafted": 0,
            "blocked": 0,
            "failed": 0,
            "skipped_current": 0,
        }

        with _owned_profile_context(
            self._profile_connection,
            execution_owner_id=self._execution_owner_id,
            at=at,
        ) as (store, kernel):
            for case in cases:
                if int(summary["selected"]) >= bounded_limit:
                    break
                case_id = store.ensure_case(
                    source=str(case["source"]),
                    source_ref=str(case["source_ref"]),
                    ticker=str(case["ticker"]),
                    at=at,
                )
                if case_id != str(case["case_id"]):
                    raise ValueError("case_identity")
                fingerprint = str(case["observation_fingerprint_sha256"])
                state = store.project_case_state(
                    case_id,
                    observation_fingerprint_sha256=fingerprint,
                )
                current = state["current_assessment"]
                if current is not None and current.get("author") != "automation":
                    summary["skipped_current"] = int(summary["skipped_current"]) + 1
                    continue
                claim = kernel.reserve_run(
                    case_id=case_id,
                    observation_fingerprint_sha256=fingerprint,
                    policy_version=AUTOMATION_POLICY_VERSION,
                    mode=mode,
                    execution_revision=AUTOMATION_EXECUTION_REVISION,
                    execution_owner_id=self._execution_owner_id,
                    query_context=_query_context(case, mode=mode),
                    diagnostics={},
                    at=at,
                )
                transition_revalidation = False
                finalization_only = (
                    claim.should_execute and claim.status == "succeeded"
                )
                if not claim.should_execute:
                    due = self._due_recheck(
                        store,
                        current,
                        case_id=case_id,
                        now=now,
                    )
                    if due is not None:
                        run, due_at = due
                        transition_revalidation = (
                            run.get("action_readiness")
                            == "waiting_transition_revalidation"
                        )
                        claim = kernel.reserve_readiness_recheck(
                            run_id=str(run["run_id"]),
                            due_at=due_at,
                            at=at,
                            execution_owner_id=self._execution_owner_id,
                        )
                        finalization_only = False
                if not claim.should_execute:
                    summary["skipped_current"] = int(summary["skipped_current"]) + 1
                    continue
                cast_ids = summary["case_ids"]
                assert isinstance(cast_ids, list)
                cast_ids.append(case_id)
                summary["selected"] = int(summary["selected"]) + 1
                sources = tuple(
                    sorted(
                        {
                            str(value)
                            for value in sources_by_ticker.get(str(case["ticker"]), ())
                        }
                    )
                )
                outcome = self._process_claim(
                    store=store,
                    kernel=kernel,
                    case=case,
                    run_id=claim.run_id,
                    mode=mode,
                    at=at,
                    now=now,
                    sources=sources,
                    transition_revalidation=transition_revalidation,
                    finalization_only=finalization_only,
                )
                summary["processed"] = int(summary["processed"]) + 1
                summary[outcome] = int(summary[outcome]) + 1
        return summary


__all__ = [
    "LifecycleAutomationEvidenceBundle",
    "LifecycleAutomationWorker",
]
