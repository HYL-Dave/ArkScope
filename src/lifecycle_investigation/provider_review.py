"""Keep deterministic listing decisions usable without launching an LLM."""

from contextlib import contextmanager
from dataclasses import asdict
from uuid import uuid4

from src.lifecycle_investigation.target import Target
from src.security_lifecycle_automation_worker import LifecycleAutomationWorker
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, case_id_for, observation_fingerprint
from src.security_lifecycle_provider_authority import classify_provider_listing
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_provider_store import ProviderCheckStore
from src.security_lifecycle_review import now
from src.ticker_identity_transition import build_automation_transition_preflight


def _decision(service, ticker, conn):
    Target(ticker=ticker, as_of=now(service)[:10])
    check = ProviderCheckStore.latest_for_connection(conn, ticker)
    if check is None:
        return None, None
    decision = classify_provider_listing(ticker=ticker, evidence=check["evidence"],
        today=instant(now(service)).date(), provider_codes=check["blockers"])
    action = ("symbol_continuation" if decision.state == "continuation" else
        "terminal_delisting" if decision.state == "terminal" else None)
    return {**asdict(decision), "action": action, "check_sha256": check["digest"]}, check


def provider_decision(service, ticker, *, conn=None):
    if conn is not None:
        return _decision(service, ticker, conn)[0]
    with service._profile_connection(write=False) as conn:
        value, _ = _decision(service, ticker, conn)
    return value


def prepare_provider_review(service, ticker, *, check_sha256, options, before_write):
    before_write()
    sources = service._read_service.sources_by_ticker()
    if sources is None:
        raise ValueError("tracking_state_unavailable")
    if not sources.get(ticker):
        raise ValueError("target_not_tracked")
    with service._profile_connection(write=False) as conn:
        decision, check = _decision(service, ticker, conn)
    if decision is None or decision["check_sha256"] != check_sha256:
        raise ValueError("provider_snapshot_changed")
    if decision["action"] is None:
        raise ValueError("provider_review_ineligible")
    observation = check["observation"]
    case = {key: observation[key] for key in ("source", "source_ref", "ticker")}
    case.update(case_id=case_id_for(**case), observation=observation, source_presence="present",
        observation_fingerprint_sha256=observation_fingerprint(observation))

    @contextmanager
    def connection():
        before_write()
        with service._profile_connection(write=True) as conn:
            yield conn

    def evidence(case, **kwargs):
        before_write()
        return ProviderCheckStore(service.profile_db_path).bundle(case, at=kwargs["at"])

    def preview(*, case, request, sources):
        with service._profile_connection(write=False) as conn:
            return build_automation_transition_preflight(conn, case=case, request=request, sources=sources, at=now(service))

    def forbidden_approval(**kwargs):
        raise ValueError("provider_review_ineligible")

    # Reuse the existing rule/fact/assessment owners. This path has no provider
    # transport and cannot approve a transition, regardless of scheduler policy.
    worker = LifecycleAutomationWorker(case_loader=lambda: (case,), profile_connection=connection,
        evidence_loader=evidence, source_loader=service._read_service.sources_by_ticker,
        transition_preview=preview, transition_approver=forbidden_approval,
        transition_mutation_allowed=lambda: False, clock=lambda: now(service),
        execution_owner_id="provider-review-" + uuid4().hex, target_case_id=case["case_id"])
    result = worker.run(limit=1, mode="live")
    if result["failed"]:
        raise ValueError("provider_review_unavailable")
    before_write()
    with service._profile_connection(write=False) as conn:
        current, _ = _decision(service, ticker, conn)
        if current is None or current["check_sha256"] != check_sha256:
            raise ValueError("provider_snapshot_changed")
        assessments = SecurityLifecycleInvestigationStore(conn).list_assessments(case["case_id"])
    if not assessments:
        raise ValueError("provider_review_unavailable")
    assessment = max(assessments, key=lambda item: item["revision"])
    return service.prepare_review(case["case_id"], assessment_id=assessment["assessment_id"], options=options)
