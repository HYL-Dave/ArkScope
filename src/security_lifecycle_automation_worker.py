"""Bounded orchestration for deterministic security-lifecycle automation."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    LifecycleWritesUnavailable,
)


_MAX_CASES_PER_TICK = 2
_MARKET_RECHECK_INTERVAL = timedelta(days=1)


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


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


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


def _terminal_delisting(facts: Iterable[object]) -> bool:
    return any(
        str(_field(fact, "fact_type") or "") == "tracked_security_effect"
        and _fact_value(fact) == "terminal_delisting"
        for fact in facts
    )


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
        if phase == "approve":
            return "persistence_failed"
        return "source_payload_invalid" if phase == "acquire" else "extractor_failed"
    return "internal_error"


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
        self._case_loader = case_loader
        self._profile_connection = profile_connection
        self._evidence_loader = evidence_loader
        self._source_loader = source_loader
        self._transition_preview = transition_preview
        self._transition_approver = transition_approver
        self._clock = clock

    @staticmethod
    def _due_recheck(
        store: SecurityLifecycleInvestigationStore,
        assessment: Mapping[str, object],
        *,
        now: datetime,
    ) -> tuple[dict[str, object], str] | None:
        if assessment.get("author") != "automation":
            return None
        run_id = str(assessment.get("automation_run_id") or "")
        if not run_id:
            return None
        run = store.get_automation_run(run_id)
        readiness = str(run.get("action_readiness") or "")
        if readiness == "waiting_effective_date":
            effective_date = assessment.get("effective_date")
            if not effective_date:
                return None
            due_at = f"{effective_date}T00:00:00Z"
        elif readiness == "waiting_market_confirmation":
            due_at = _utc_timestamp(
                _instant(str(run["updated_at"])) + _MARKET_RECHECK_INTERVAL
            )
        else:
            return None
        if now < _instant(due_at):
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
    ) -> str:
        phase = "acquire"
        try:
            bundle = self._evidence_loader(case, mode=mode, at=at)
            if not isinstance(bundle, LifecycleAutomationEvidenceBundle):
                raise TypeError("automation_evidence_bundle")
            existing_evidence, existing_facts = _persisted_material(
                store.conn,
                run_id,
            )
            all_evidence = (*existing_evidence, *bundle.evidence)
            all_facts = (*existing_facts, *bundle.facts)
            blockers = bundle.blockers
            blocker_codes = {_blocker_code(value) for value in blockers}
            if blocker_codes == {"ibkr_contract_missing"} and _terminal_delisting(
                all_facts
            ):
                blockers = ()
            if blockers:
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

            phase = "evaluate"
            decision = self._evaluate(
                case=case,
                evidence=all_evidence,
                facts=all_facts,
                current_date=now.date(),
                sources=sources,
            )
            if decision.transition_requested:
                decision = self._evaluate(
                    case=case,
                    evidence=all_evidence,
                    facts=all_facts,
                    current_date=now.date(),
                    sources=sources,
                )

            phase = "persist"
            kernel.complete_run(
                run_id=run_id,
                evidence=bundle.evidence,
                facts=bundle.facts,
                blockers=(),
                decision_tier=decision.decision_tier,
                action_readiness=decision.action_readiness,
                retry_at=None,
                diagnostics=bundle.diagnostics,
                at=at,
            )
            assessment_id = create_automation_assessment(
                store=store,
                run_id=run_id,
                decision=decision,
                observation_fingerprint_sha256=str(
                    case["observation_fingerprint_sha256"]
                ),
                at=at,
            )
            if decision.decision_tier == "verified_automatic":
                store.accept_assessment(
                    assessment_id,
                    observation_fingerprint_sha256=str(
                        case["observation_fingerprint_sha256"]
                    ),
                    acceptance_authority="automation_policy",
                    at=at,
                )
                store.generate_action_proposals(
                    case_id=str(case["case_id"]),
                    observation_fingerprint_sha256=str(
                        case["observation_fingerprint_sha256"]
                    ),
                    sources_by_ticker={str(case["ticker"]): sources},
                    at=at,
                )
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
                        raise RuntimeError("automation_transition_approval")
                return "accepted"
            return "drafted"
        except Exception as exc:
            failure_code = _failure_code(exc, phase=phase)
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

        with self._profile_connection() as conn:
            store = SecurityLifecycleInvestigationStore(conn)
            kernel = SecurityLifecycleFactKernel(store)
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
                due = (
                    None
                    if current is None
                    else self._due_recheck(store, current, now=now)
                )
                if current is not None and due is None:
                    summary["skipped_current"] = int(summary["skipped_current"]) + 1
                    continue
                if due is not None:
                    run, due_at = due
                    claim = kernel.reserve_readiness_recheck(
                        run_id=str(run["run_id"]),
                        due_at=due_at,
                        at=at,
                    )
                else:
                    claim = kernel.reserve_run(
                        case_id=case_id,
                        observation_fingerprint_sha256=fingerprint,
                        policy_version=AUTOMATION_POLICY_VERSION,
                        mode=mode,
                        query_context=_query_context(case, mode=mode),
                        diagnostics={},
                        at=at,
                    )
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
                )
                summary["processed"] = int(summary["processed"]) + 1
                summary[outcome] = int(summary[outcome]) + 1
        return summary


__all__ = [
    "LifecycleAutomationEvidenceBundle",
    "LifecycleAutomationWorker",
]
