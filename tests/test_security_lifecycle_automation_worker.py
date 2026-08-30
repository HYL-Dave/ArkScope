from __future__ import annotations

import hashlib
import inspect
import json
import socket
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest


_AT = "2026-08-25T12:00:00Z"
_FINGERPRINTS = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)


def _case(index=1, *, ticker="OLD", terminal=False):
    from src.security_lifecycle_investigation import case_id_for

    source_ref = f"000000000{index}-26-00000{index}"
    cik = f"{index:010d}"
    kinds = (
        [{"event_type": "listing_removal_notice", "effective_date": "2026-09-01"}]
        if terminal
        else [{"event_type": "listing_status_review", "effective_date": "2026-08-25"}]
    )
    return {
        "case_id": case_id_for("sec_edgar", source_ref, ticker),
        "source": "sec_edgar",
        "source_ref": source_ref,
        "ticker": ticker,
        "source_presence": "present",
        "observation_fingerprint_sha256": _FINGERPRINTS[index - 1],
        "observation": {
            "ticker": ticker,
            "cik": cik,
            "issuer_name": f"Issuer {index}",
            "filing_date": "2026-08-20",
            "source": "sec_edgar",
            "source_ref": source_ref,
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "evidence_url": f"https://www.sec.gov/Archives/example/{index}.htm",
            "description": "Identity event.",
            "kinds": kinds,
        },
    }


def _fact(evidence, payload, key, fact_type, normalized_value=None):
    from src.security_lifecycle_fact_kernel import AutomationFact

    value = payload[key]
    token = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    encoded = evidence.excerpt.encode()
    start = encoded.index(token)
    return AutomationFact(
        evidence_id=evidence.evidence_id,
        fact_type=fact_type,
        normalized_value=value if normalized_value is None else normalized_value,
        source_span_start=start,
        source_span_end=start + len(token),
        cited_text_sha256=hashlib.sha256(token).hexdigest(),
        extractor_rule_id=f"fixture.{fact_type}",
        extractor_rule_version="1",
    )


def _evidence(case, *, family, payload, kind, locator):
    from src.security_lifecycle_fact_kernel import AutomationEvidence

    excerpt = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    evidence_id = f"{family}-{case['case_id'][-8:]}"
    return AutomationEvidence(
        evidence_id=evidence_id,
        source_family=family,
        adapter="sec_edgar" if family == "regulator" else "ibkr_contract",
        kind=kind,
        source_url=(
            case["observation"]["evidence_url"] if family == "regulator" else None
        ),
        title=f"{family} evidence",
        publisher="SEC EDGAR" if family == "regulator" else "Interactive Brokers",
        domain="sec.gov" if family == "regulator" else None,
        source_published_at=("2026-08-20" if family == "regulator" else None),
        retrieved_at=_AT,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_document_sha256=("d" * 64 if family == "regulator" else None),
        source_locator=locator,
        evidence_dedupe_key=f"{family}:{case['case_id']}:{kind}",
    )


def _listing_evidence(
    case,
    *,
    label,
    adapter,
    ticker,
    expected_active_state,
    market,
    status,
    directory=None,
    active=None,
    delisted_utc=None,
    fact_values=None,
    retrieved_at=_AT,
):
    from src.security_lifecycle_fact_kernel import AutomationEvidence

    normalized_facts = dict(fact_values or {})
    listing_status = (
        "active"
        if status == "found" and active is True
        else "inactive"
        if status == "found" and active is False
        else status
    )
    payload = {
        "listing_adapter": adapter,
        "listing_status": listing_status,
        **normalized_facts,
    }
    excerpt = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    locator = {
        "locator_kind": "listing_directory_snapshot",
        "adapter": adapter,
        "authority": "massive" if adapter == "massive_reference" else "nasdaq_trader",
        "candidate_ticker": ticker,
        "expected_active_state": expected_active_state,
        "market": market,
        "listing_status": listing_status,
        "directory": directory,
        "snapshot_complete": True,
    }
    if delisted_utc is not None:
        locator["delisted_utc"] = delisted_utc
    evidence = AutomationEvidence(
        evidence_id=f"listing-{label}-{case['case_id'][-8:]}",
        source_family="listing_authority",
        adapter=adapter,
        kind="listing_directory_snapshot",
        source_url=(
            f"https://api.massive.com/v3/reference/tickers/{ticker}"
            if adapter == "massive_reference"
            else "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
        ),
        title=f"{adapter} listing snapshot",
        publisher=("Massive" if adapter == "massive_reference" else "Nasdaq Trader"),
        domain=None,
        source_published_at=None,
        retrieved_at=retrieved_at,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_document_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_locator=locator,
        evidence_dedupe_key=f"listing:{label}:{case['case_id']}",
    )
    facts = tuple(_fact(evidence, payload, key, key) for key in normalized_facts)
    return evidence, facts


def _bundle(
    case,
    *,
    review_structure=None,
    terminal=False,
    market_absent=False,
    blocker=None,
    retry_at=None,
):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    if blocker is not None:
        return LifecycleAutomationEvidenceBundle(
            evidence=(),
            facts=(),
            blockers=(
                AutomationBlocker(
                    code=blocker,
                    retryable=retry_at is not None,
                    context={"attempts": 1},
                ),
            ),
            diagnostics={"sec_attempts": 1},
            retry_at=retry_at,
        )

    cik = case["observation"]["cik"]
    ticker = case["ticker"]
    successor = f"{ticker}2"
    if terminal:
        regulator_payload = {
            "effective_date": "2026-09-01",
            "issuer_cik": cik,
            "security_class": "common_stock",
            "source_ticker": ticker,
            "tracked_security_effect": "terminal_delisting",
        }
        regulator = _evidence(
            case,
            family="regulator",
            payload=regulator_payload,
            kind="regulator_excerpt",
            locator={"filing_chain_complete": True},
        )
        facts = list(
            _fact(regulator, regulator_payload, key, key) for key in regulator_payload
        )
        evidence = [regulator]
        if market_absent:
            for label, directory in (
                ("nasdaq-listed", "nasdaq_listed"),
                ("nasdaq-other", "other_listed"),
            ):
                absence, absence_facts = _listing_evidence(
                    case,
                    label=label,
                    adapter="nasdaq_symbol_directory",
                    ticker=ticker,
                    expected_active_state=True,
                    market="stocks",
                    status="not_found",
                    directory=directory,
                    retrieved_at="2026-09-01T12:00:00Z",
                )
                evidence.append(absence)
                facts.extend(absence_facts)
            inactive, inactive_facts = _listing_evidence(
                case,
                label="massive-inactive",
                adapter="massive_reference",
                ticker=ticker,
                expected_active_state=False,
                market="stocks",
                status="found",
                active=False,
                delisted_utc="2026-09-01T00:00:00Z",
                retrieved_at="2026-09-01T12:00:00Z",
                fact_values={
                    "issuer_cik": cik,
                    "security_class": "common_stock",
                    "source_ticker": ticker,
                },
            )
            evidence.append(inactive)
            facts.extend(inactive_facts)
            absence_payload = {
                "contract_status": "missing",
                "queried_ticker": ticker,
            }
            evidence.append(
                _evidence(
                    case,
                    family="market_infrastructure",
                    payload=absence_payload,
                    kind="market_infrastructure_snapshot",
                    locator={"contract_status": "missing"},
                )
            )
        else:
            active_listing, active_facts = _listing_evidence(
                case,
                label="nasdaq-active",
                adapter="nasdaq_symbol_directory",
                ticker=ticker,
                expected_active_state=True,
                market="stocks",
                status="found",
                directory="nasdaq_listed",
                active=True,
                fact_values={
                    "destination_venue": "NASDAQ",
                    "security_class": "common_stock",
                    "successor_ticker": ticker,
                },
            )
            evidence.append(active_listing)
            facts.extend(active_facts)
        return LifecycleAutomationEvidenceBundle(
            evidence=tuple(evidence),
            facts=tuple(facts),
            blockers=(),
            diagnostics={"sec_attempts": 1, "ibkr_requests": int(market_absent)},
            retry_at=None,
        )

    if review_structure is not None:
        regulator_payload = {
            "issuer_cik": cik,
            "source_ticker": ticker,
            "transaction_structure": {
                "kind": review_structure,
                "terms_status": "complete",
                "counterparty_name": "Buyer Corp.",
                "counterparty_ticker": "BUY",
                "counterparty_cik": "0000000123",
                "consideration_currency": "USD",
                "cash_per_security_decimal": "10.00",
                "exchange_ratio_decimal": "0.50",
            },
        }
        regulator = _evidence(
            case,
            family="regulator",
            payload=regulator_payload,
            kind="regulator_excerpt",
            locator={"filing_chain_complete": True},
        )
        return LifecycleAutomationEvidenceBundle(
            evidence=(regulator,),
            facts=tuple(
                _fact(regulator, regulator_payload, key, key)
                for key in regulator_payload
            ),
            blockers=(),
            diagnostics={"sec_attempts": 1},
            retry_at=None,
        )

    regulator_payload = {
        "destination_venue": "NASDAQ",
        "effective_date": "2026-08-25",
        "issuer_cik": cik,
        "security_class": "common_stock",
        "source_ticker": ticker,
        "source_venue": "NYSE",
        "successor_ticker": successor,
    }
    regulator = _evidence(
        case,
        family="regulator",
        payload=regulator_payload,
        kind="regulator_excerpt",
        locator={"filing_chain_complete": True},
    )
    market_snapshot = {
        "destination_venue": "NASDAQ",
        "security_class": "common_stock",
        "successor_ticker": successor,
    }
    market_payload = {
        "adapter_version": "2",
        "contract_status": "found",
        "market_data": {
            "fresh": True,
            "last": "10.00",
            "provider_time": _AT,
            "retrieved_at": _AT,
            "status": "live",
        },
        "snapshot": market_snapshot,
    }
    market = _evidence(
        case,
        family="market_infrastructure",
        payload=market_payload,
        kind="market_infrastructure_snapshot",
        locator=market_payload,
    )
    listing, listing_facts = _listing_evidence(
        case,
        label="nasdaq-active",
        adapter="nasdaq_symbol_directory",
        ticker=successor,
        expected_active_state=True,
        market="stocks",
        status="found",
        directory="nasdaq_listed",
        active=True,
        fact_values=market_snapshot,
    )
    return LifecycleAutomationEvidenceBundle(
        evidence=(regulator, listing, market),
        facts=(
            *(
                _fact(regulator, regulator_payload, key, key)
                for key in regulator_payload
            ),
            *listing_facts,
            *(_fact(market, market_snapshot, key, key) for key in market_snapshot),
        ),
        blockers=(),
        diagnostics={"sec_attempts": 1, "ibkr_requests": 1},
        retry_at=None,
    )


class _Harness:
    def __init__(self, tmp_path, cases):
        from src.security_lifecycle_investigation import (
            SecurityLifecycleInvestigationStore,
        )

        self.conn = sqlite3.connect(
            tmp_path / "profile_state.db",
            check_same_thread=False,
        )
        SecurityLifecycleInvestigationStore(self.conn)
        self.cases = list(cases)
        self.bundles = {case["case_id"]: _bundle(case) for case in cases}
        self.evidence_calls = []
        self.preview_calls = []
        self.preview_results = []
        self.approval_calls = []
        self.approval_error = None
        self.sources = {case["ticker"]: ("manual_lists",) for case in cases}
        self.now = _AT

    @contextmanager
    def profile_connection(self):
        yield self.conn

    def case_loader(self):
        return list(self.cases)

    def evidence_loader(self, case, *, mode, at, prior_material):
        del prior_material
        self.evidence_calls.append((case["case_id"], mode, at))
        value = self.bundles[case["case_id"]]
        if isinstance(value, BaseException):
            raise value
        return value

    def source_loader(self):
        return dict(self.sources)

    def transition_preview(self, *, case, request, sources):
        self.preview_calls.append((case["case_id"], dict(request), tuple(sources)))
        if self.preview_results:
            return self.preview_results.pop(0)
        return {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": request["transition_kind"],
        }

    def transition_approver(self, *, case, request, sources):
        store = _store(self)
        assessments = store.list_assessments(case["case_id"])
        proposals = store.list_proposals(case["case_id"])
        self.approval_calls.append(
            {
                "case_id": case["case_id"],
                "request": dict(request),
                "sources": tuple(sources),
                "assessment_status": assessments[0]["status"],
                "proposal_actions": tuple(
                    sorted(row["action_type"] for row in proposals)
                ),
            }
        )
        if self.approval_error is not None:
            raise self.approval_error
        return {
            "transition_id": "tit_automation_1",
            "status": "approved",
            "approval_authority": "automation_policy",
        }

    def clock(self):
        return self.now

    def worker(self, execution_owner_id="test-worker-owner", **overrides):
        from src.security_lifecycle_automation_worker import (
            LifecycleAutomationWorker,
        )

        kwargs = dict(
            case_loader=self.case_loader,
            profile_connection=self.profile_connection,
            evidence_loader=self.evidence_loader,
            source_loader=self.source_loader,
            transition_preview=self.transition_preview,
            clock=self.clock,
            execution_owner_id=execution_owner_id,
            **overrides,
        )
        if (
            "transition_approver"
            in inspect.signature(LifecycleAutomationWorker).parameters
        ):
            kwargs["transition_approver"] = self.transition_approver
        return LifecycleAutomationWorker(**kwargs)

    def worker_with_transition_approver(
        self,
        execution_owner_id="test-worker-owner",
        **overrides,
    ):
        from src.security_lifecycle_automation_worker import (
            LifecycleAutomationWorker,
        )

        return LifecycleAutomationWorker(
            case_loader=self.case_loader,
            profile_connection=self.profile_connection,
            evidence_loader=self.evidence_loader,
            source_loader=self.source_loader,
            transition_preview=self.transition_preview,
            transition_approver=self.transition_approver,
            clock=self.clock,
            execution_owner_id=execution_owner_id,
            **overrides,
        )


def _store(harness):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    return SecurityLifecycleInvestigationStore(harness.conn)


def _invalid_persistence_bundle(case, *, blockers=()):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )

    bundle = _bundle(case)
    evidence = bundle.evidence[0]
    excerpt = evidence.excerpt + "\n"
    invalid = replace(
        evidence,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
    )
    return LifecycleAutomationEvidenceBundle(
        evidence=(invalid, *bundle.evidence[1:]),
        facts=bundle.facts,
        blockers=tuple(blockers),
        diagnostics={"news_evidence_count": 20, "sec_attempts": 7},
        retry_at=("2026-08-26T12:00:00Z" if blockers else None),
    )


def _deadline_bundle(case, *, forge_citation=False):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )
    from src.security_lifecycle_fact_kernel import AutomationEvidence
    from src.security_lifecycle_sec_evidence import SecSourceDeadline
    from src.service import security_lifecycle_automation_scheduler as scheduler

    cited_text = (
        "The outside date was extended from August 23, 2026 to "
        "August 24, 2026."
    )
    encoded = cited_text.encode("utf-8")
    evidence = AutomationEvidence(
        evidence_id="source-deadline",
        source_family="regulator",
        adapter="sec_edgar",
        kind="regulator_excerpt",
        source_url=case["observation"]["evidence_url"],
        title="Deadline evidence",
        publisher="SEC EDGAR",
        domain="sec.gov",
        source_published_at="2026-08-20",
        retrieved_at=_AT,
        excerpt=cited_text,
        content_sha256=hashlib.sha256(encoded).hexdigest(),
        source_document_sha256="d" * 64,
        source_locator={"accession": case["source_ref"]},
        evidence_dedupe_key=f"deadline:{case['case_id']}",
    )
    deadline = SecSourceDeadline(
        date="2026-08-24",
        evidence_id=evidence.evidence_id,
        span_start_byte=0,
        span_end_byte=len(encoded),
        cited_text=cited_text,
        cited_text_sha256=hashlib.sha256(encoded).hexdigest(),
        rule_id="sec.explicit_transaction_termination_date",
        rule_version="4",
        kind="extension",
        supersedes_date="2026-08-23",
    )
    blocker = scheduler._pending_event_monitoring(
        case,
        (),
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "listing_authority": "available",
        },
        source_deadlines=(deadline,),
        at=_AT,
    )
    assert blocker is not None
    context = dict(blocker.context)
    if forge_citation:
        context["source_deadline_cited_text_sha256"] = "f" * 64
    return LifecycleAutomationEvidenceBundle(
        evidence=(evidence,),
        facts=(),
        blockers=(replace(blocker, context=context),),
        diagnostics={"news_evidence_count": 20, "sec_attempts": 7},
        retry_at=None,
    )


def _market_recheck_bundle(
    case, *, retrieved_at, market_status, fresh, include_regulator
):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )

    base = _bundle(case)
    regulator, listing, prior_market = base.evidence
    market_payload = json.loads(prior_market.excerpt)
    market_payload["market_data"].update(
        {
            "fresh": fresh,
            "provider_time": retrieved_at,
            "retrieved_at": retrieved_at,
            "status": market_status,
        }
    )
    excerpt = json.dumps(
        market_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    market = replace(
        prior_market,
        evidence_id=f"market-{market_status}-{retrieved_at}",
        retrieved_at=retrieved_at,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_locator=market_payload,
        evidence_dedupe_key=f"market:{case['case_id']}:{market_status}:{retrieved_at}",
    )
    market_facts = tuple(
        _fact(market, market_payload["snapshot"], key, key)
        for key in market_payload["snapshot"]
    )
    regulator_facts = tuple(
        fact for fact in base.facts if fact.evidence_id == regulator.evidence_id
    )
    listing_facts = tuple(
        fact for fact in base.facts if fact.evidence_id == listing.evidence_id
    )
    return LifecycleAutomationEvidenceBundle(
        evidence=(
            (regulator, listing, market) if include_regulator else (listing, market)
        ),
        facts=(
            (*regulator_facts, *listing_facts, *market_facts)
            if include_regulator
            else (*listing_facts, *market_facts)
        ),
        blockers=(),
        diagnostics={"ibkr_requests": 1, "sec_attempts": int(include_regulator)},
        retry_at=None,
    )


def _conflict_bundle(case, *, pending):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    base = _bundle(case)
    regulator, listing, prior_market = base.evidence
    market_payload = json.loads(prior_market.excerpt)
    market_payload["snapshot"]["successor_ticker"] = "OTHER"
    excerpt = json.dumps(
        market_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    market = replace(
        prior_market,
        evidence_id=f"market-conflict-{case['case_id']}",
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_locator=market_payload,
        evidence_dedupe_key=f"market-conflict:{case['case_id']}",
    )
    facts = (
        *(
            fact
            for fact in base.facts
            if fact.evidence_id in {regulator.evidence_id, listing.evidence_id}
        ),
        *(
            _fact(market, market_payload["snapshot"], key, key)
            for key in market_payload["snapshot"]
        ),
    )
    blockers = [
        AutomationBlocker(
            code="source_conflict",
            retryable=False,
            context={"fact_types": ["successor_ticker"]},
        )
    ]
    if pending:
        blockers.append(
            AutomationBlocker(
                code="sec_evidence_insufficient",
                retryable=True,
                context={
                    "monitoring_reason": "event_completion_not_confirmed",
                    "next_check_at": "2026-08-26T12:00:00Z",
                },
            )
        )
    return LifecycleAutomationEvidenceBundle(
        evidence=(regulator, listing, market),
        facts=facts,
        blockers=tuple(blockers),
        diagnostics={"ibkr_requests": 1, "sec_attempts": 1},
        retry_at=None,
    )


class _InjectedFinalizationCrash(BaseException):
    pass


class _InjectedEvidenceCrash(BaseException):
    pass


def test_base_exception_during_evidence_terminalizes_the_owned_running_run(
    tmp_path,
):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _InjectedEvidenceCrash()
    try:
        with pytest.raises(_InjectedEvidenceCrash):
            harness.worker().run()

        harness.bundles[case["case_id"]] = _bundle(case)
        recovered = harness.worker().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert recovered["skipped_current"] == 1
        assert len(harness.evidence_calls) == 1
        assert run["status"] == "failed"
        assert run["failure_code"] == "internal_error"
        assert json.loads(run["diagnostics_json"]) == {
            "interrupted_execution": 1,
        }
    finally:
        harness.conn.close()


def test_worker_selects_at_most_two_changed_present_cases_in_stable_order(tmp_path):
    cases = [_case(3), _case(1), _case(2)]
    harness = _Harness(tmp_path, cases)
    try:
        result = harness.worker().run(limit=99, mode="live")

        expected = sorted(case["case_id"] for case in cases)[:2]
        assert result["case_ids"] == expected
        assert result["selected"] == 2
        assert result["processed"] == 2
        assert [item[0] for item in harness.evidence_calls] == expected
        assert (
            harness.conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_automation_runs"
            ).fetchone()[0]
            == 2
        )
    finally:
        harness.conn.close()


def test_persist_value_errors_are_classified_as_persistence_failures():
    from src.security_lifecycle_automation_worker import _failure_code

    assert (
        _failure_code(ValueError("evidence_content_sha256"), phase="persist")
        == "persistence_failed"
    )
    assert (
        _failure_code(ValueError("fact_value_shape"), phase="evaluate")
        == "extractor_failed"
    )


def test_blocked_result_persistence_failure_is_not_source_payload_invalid(tmp_path):
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _invalid_persistence_bundle(
        case,
        blockers=(
            AutomationBlocker(
                code="sec_transport_unavailable",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
    )
    try:
        result = harness.worker().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert result["failed"] == 1
        assert run["status"] == "failed"
        assert run["failure_code"] == "persistence_failed"
    finally:
        harness.conn.close()


def test_failed_run_retains_acquired_provider_diagnostics(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _invalid_persistence_bundle(case)
    try:
        result = harness.worker().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert result["failed"] == 1
        assert json.loads(run["diagnostics_json"]) == {
            "failures": 1,
            "news_evidence_count": 20,
            "sec_attempts": 7,
        }
    finally:
        harness.conn.close()


def test_verified_result_persists_automation_assessment_acceptance_and_proposals(
    tmp_path,
):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    try:
        result = harness.worker().run()
        store = _store(harness)
        assessment = store.list_assessments(case["case_id"])[0]

        assert result["accepted"] == 1
        assert assessment["status"] == "accepted"
        assert assessment["author"] == "automation"
        assert assessment["acceptance_authority"] == "automation_policy"
        assert assessment["automation_method"] == "deterministic_rule"
        assert assessment["rule_id"] == "lifecycle.simple_symbol_continuation"
        assert assessment["decision_provenance_sha256"]
        assert {
            row["action_type"] for row in store.list_proposals(case["case_id"])
        } == {
            "notify",
            "remap_symbol",
        }
    finally:
        harness.conn.close()


def test_market_recheck_preserves_receipts_without_quote_acceptance_gate(
    tmp_path,
):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _market_recheck_bundle(
        case,
        retrieved_at=_AT,
        market_status="frozen",
        fresh=False,
        include_regulator=True,
    )
    try:
        first = harness.worker_with_transition_approver().run()
        first_run = _store(harness).list_automation_runs(case["case_id"])[0]
        assert first["accepted"] == 1
        assert first_run["action_readiness"] == "transition_eligible"
        assert len(harness.approval_calls) == 1

        harness.now = "2026-08-26T12:00:00Z"
        harness.bundles[case["case_id"]] = _market_recheck_bundle(
            case,
            retrieved_at=harness.now,
            market_status="live",
            fresh=True,
            include_regulator=False,
        )
        second = harness.worker_with_transition_approver().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert second["processed"] == 0
        assert second["accepted"] == 0
        assert second["skipped_current"] == 1
        assert run["action_readiness"] == "transition_eligible"
        assert len(harness.approval_calls) == 1
        receipts = harness.conn.execute(
            "SELECT source_locator_json FROM security_lifecycle_evidence "
            "WHERE automation_run_id=? AND source_family='market_infrastructure' "
            "ORDER BY retrieved_at",
            (run["run_id"],),
        ).fetchall()
        assert [json.loads(row[0])["market_data"]["status"] for row in receipts] == [
            "frozen",
        ]
    finally:
        harness.conn.close()


@pytest.mark.parametrize(
    "pending", (False, True), ids=("conflict_only", "conflict_plus_pending")
)
def test_source_conflict_crosses_worker_kernel_and_attention_projection(
    tmp_path,
    pending,
):
    from src.security_lifecycle_disposition import project_lifecycle_disposition
    from src.security_lifecycle_investigation import _automation_history

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _conflict_bundle(case, pending=pending)
    try:
        result = harness.worker().run()
        store = _store(harness)
        (
            automation_runs,
            automation_facts,
            _run_total,
            _fact_total,
        ) = _automation_history(store, case["case_id"])
        run = automation_runs[0]
        assessments = store.list_assessments(case["case_id"])
        projection = project_lifecycle_disposition(
            {
                **case,
                "automation_runs": automation_runs,
                "automation_facts": automation_facts,
                "evidence": store.list_evidence(case["case_id"]),
                "current_assessment": None,
                "current_acknowledgement": None,
                "assessment_history": assessments,
                "ticker_transition": None,
            }
        )

        assert result["failed"] == 0
        assert run["status"] == ("blocked" if pending else "succeeded")
        assert run["decision_tier"] == "review_suggested"
        assert run["action_readiness"] == "action_blocked"
        assert (projection.queue_bucket, projection.reason_code) == (
            "attention",
            "source_conflict",
        )
        assert len(assessments) == (0 if pending else 1)
    finally:
        harness.conn.close()


def test_transition_eligible_verified_result_approves_automation_transition(
    tmp_path,
):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    try:
        result = harness.worker_with_transition_approver().run()

        assert result["accepted"] == 1
        assert result["failed"] == 0
        assert harness.approval_calls == [
            {
                "case_id": case["case_id"],
                "request": {
                    "transition_kind": "symbol_continuation",
                    "source_ticker": "OLD",
                    "successor_ticker": "OLD2",
                    "effective_date": "2026-08-25",
                    "outcomes": ("symbol_changed", "venue_transfer"),
                },
                "sources": ("manual_lists",),
                "assessment_status": "accepted",
                "proposal_actions": ("notify", "remap_symbol"),
            }
        ]
    finally:
        harness.conn.close()


@pytest.mark.parametrize(
    "boundary",
    ("assessment", "acceptance", "proposal", "approval"),
)
def test_terminal_finalization_recovers_idempotently_after_each_boundary(
    tmp_path,
    monkeypatch,
    boundary,
):
    import src.security_lifecycle_automation_worker as worker_module
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    faulted = False

    def crash_after(callable_):
        def wrapped(*args, **kwargs):
            nonlocal faulted
            result = callable_(*args, **kwargs)
            if not faulted:
                faulted = True
                raise _InjectedFinalizationCrash(boundary)
            return result

        return wrapped

    if boundary == "assessment":
        monkeypatch.setattr(
            worker_module,
            "create_automation_assessment",
            crash_after(worker_module.create_automation_assessment),
        )
    elif boundary == "acceptance":
        monkeypatch.setattr(
            SecurityLifecycleInvestigationStore,
            "accept_assessment",
            crash_after(SecurityLifecycleInvestigationStore.accept_assessment),
        )
    elif boundary == "proposal":
        monkeypatch.setattr(
            SecurityLifecycleInvestigationStore,
            "generate_action_proposals",
            crash_after(SecurityLifecycleInvestigationStore.generate_action_proposals),
        )
    else:
        harness.transition_approver = crash_after(harness.transition_approver)

    try:
        with pytest.raises(_InjectedFinalizationCrash, match=boundary):
            harness.worker_with_transition_approver().run()

        recovered = harness.worker_with_transition_approver().run()
        store = _store(harness)
        run = store.list_automation_runs(case["case_id"])[0]
        context = json.loads(run["query_context_json"])

        assert recovered["accepted"] == 1
        assert len(store.list_automation_runs(case["case_id"])) == 1
        assert len(store.list_assessments(case["case_id"])) == 1
        assert store.list_assessments(case["case_id"])[0]["status"] == "accepted"
        assert len(store.list_proposals(case["case_id"])) == 2
        assert (
            context["terminal_finalized_decision_provenance_sha256"]
            == context["terminal_decision_provenance_sha256"]
        )
        expected_approval_calls = 2 if boundary == "approval" else 1
        assert len(harness.approval_calls) == expected_approval_calls

        settled = harness.worker_with_transition_approver().run()
        assert settled["processed"] == 0
        assert len(store.list_assessments(case["case_id"])) == 1
        assert len(store.list_proposals(case["case_id"])) == 2
    finally:
        harness.conn.close()


def test_human_accepted_automation_assessment_completes_pending_finalization(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_automation_worker as worker_module

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    original = worker_module.create_automation_assessment
    crashed = False

    def crash_after_assessment(*args, **kwargs):
        nonlocal crashed
        assessment_id = original(*args, **kwargs)
        if not crashed:
            crashed = True
            raise _InjectedFinalizationCrash("assessment")
        return assessment_id

    monkeypatch.setattr(
        worker_module,
        "create_automation_assessment",
        crash_after_assessment,
    )
    try:
        with pytest.raises(_InjectedFinalizationCrash, match="assessment"):
            harness.worker_with_transition_approver().run()

        store = _store(harness)
        assessment = store.list_assessments(case["case_id"])[0]
        store.accept_assessment(
            assessment["assessment_id"],
            observation_fingerprint_sha256=case[
                "observation_fingerprint_sha256"
            ],
            acceptance_authority="human",
            at="2026-08-25T12:01:00Z",
        )
        monkeypatch.setattr(
            worker_module,
            "create_automation_assessment",
            original,
        )

        recovered = harness.worker_with_transition_approver().run()
        persisted = store.get_assessment(assessment["assessment_id"])
        run = store.list_automation_runs(case["case_id"])[0]
        context = json.loads(run["query_context_json"])

        assert recovered["accepted"] == 1
        assert recovered["failed"] == 0
        assert persisted["status"] == "accepted"
        assert persisted["acceptance_authority"] == "human"
        assert len(store.list_assessments(case["case_id"])) == 1
        assert len(store.list_proposals(case["case_id"])) == 2
        assert (
            context["terminal_finalized_decision_provenance_sha256"]
            == context["terminal_decision_provenance_sha256"]
        )
        assert "terminal_finalization_failure" not in context
    finally:
        harness.conn.close()


def test_terminal_finalization_failure_uses_bounded_backoff_without_hot_loop(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    original = SecurityLifecycleInvestigationStore.generate_action_proposals

    def fail_proposals(*_args, **_kwargs):
        raise ValueError("private fixture detail")

    monkeypatch.setattr(
        SecurityLifecycleInvestigationStore,
        "generate_action_proposals",
        fail_proposals,
    )
    try:
        expected_retry_times = (
            "2026-08-25T12:15:00Z",
            "2026-08-25T13:15:00Z",
            "2026-08-25T19:15:00Z",
            None,
        )
        for attempt_count, expected_retry in enumerate(
            expected_retry_times,
            start=1,
        ):
            result = harness.worker_with_transition_approver().run()
            run = _store(harness).list_automation_runs(case["case_id"])[0]
            context = json.loads(run["query_context_json"])
            failure = context["terminal_finalization_failure"]

            assert result["failed"] == 1
            assert result["processed"] == 1
            assert run["status"] == "succeeded"
            assert run["failure_code"] is None
            assert failure == {
                "attempt_count": attempt_count,
                "code": "finalization_failed",
                "failed_at": harness.now,
                "retry_not_before": expected_retry,
            }
            assert "private fixture detail" not in json.dumps(context)

            immediate = harness.worker_with_transition_approver().run()
            assert immediate["processed"] == 0
            assert immediate["failed"] == 0
            if expected_retry is not None:
                harness.now = expected_retry

        harness.now = "2027-08-25T12:00:00Z"
        exhausted = harness.worker_with_transition_approver().run()
        assert exhausted["processed"] == 0
        assert exhausted["failed"] == 0
        assert len(_store(harness).list_automation_runs(case["case_id"])) == 1

        monkeypatch.setattr(
            SecurityLifecycleInvestigationStore,
            "generate_action_proposals",
            original,
        )
        attended = harness.worker_with_transition_approver(
            allow_new_attempt=True
        ).run()
        assert attended["accepted"] == 1
        assert attended["failed"] == 0
        assert len(_store(harness).list_automation_runs(case["case_id"])) == 1
    finally:
        harness.conn.close()


def test_due_terminal_finalization_retry_clears_failure_after_success(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )
    from src.scheduler_state import SchedulerStateStore
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    case = _case(1)
    profile_path = tmp_path / "profile_state.db"
    telemetry = JobRunsLocalStore(profile_path)
    scheduler_state = SchedulerStateStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    harness = _Harness(tmp_path, [case])
    original = SecurityLifecycleInvestigationStore.generate_action_proposals

    def fail_proposals(*_args, **_kwargs):
        raise ValueError("private fixture detail")

    monkeypatch.setattr(
        SecurityLifecycleInvestigationStore,
        "generate_action_proposals",
        fail_proposals,
    )
    try:
        failed = harness.worker_with_transition_approver().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]
        failure = json.loads(run["query_context_json"])[
            "terminal_finalization_failure"
        ]
        assert failed["failed"] == 1
        assert scheduler.record_security_lifecycle_automation_result(
            failed,
            now=datetime.fromisoformat("2026-08-25T12:00:00+00:00"),
        )

        harness.now = str(failure["retry_not_before"])
        monkeypatch.setattr(
            SecurityLifecycleInvestigationStore,
            "generate_action_proposals",
            original,
        )
        recovered = harness.worker_with_transition_approver().run()
        settled = _store(harness).list_automation_runs(case["case_id"])[0]
        context = json.loads(settled["query_context_json"])

        assert recovered["accepted"] == 1
        assert recovered["failed"] == 0
        assert scheduler.record_security_lifecycle_automation_result(
            recovered,
            now=datetime.fromisoformat("2026-08-25T12:15:00+00:00"),
        )
        assert "terminal_finalization_failure" not in context
        assert (
            context["terminal_finalized_decision_provenance_sha256"]
            == context["terminal_decision_provenance_sha256"]
        )
        assert [(row["status"], row["message"]) for row in telemetry.list_runs(
            job_name="security_lifecycle.automation",
            limit=10,
        )] == [
            ("succeeded", "security_lifecycle_automation_recovered"),
            ("failed", "security_lifecycle_automation_failure"),
        ]
        state = scheduler_state.get("security_lifecycle.automation")
        assert state is not None
        assert state["last_result"]["active_incident"] is None
    finally:
        harness.conn.close()


def test_approval_boundary_recovery_deduplicates_real_transition_and_mutates_no_profile(
    tmp_path,
):
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle_investigation import assessment_fingerprint
    from src.security_lifecycle_schema import create_profile_schema
    from src.ticker_identity_schema import create_ticker_identity_schema
    from src.ticker_identity_transition import (
        TickerIdentityTransitionStore,
        TransitionOptions,
        build_transition_preview,
    )

    profile_path = tmp_path / "profile_state.db"
    ProfileStateStore(profile_path)
    with sqlite3.connect(profile_path) as setup:
        create_profile_schema(setup)
        create_ticker_identity_schema(setup)
        setup.execute(
            "INSERT INTO watchlists "
            "(id,name,kind,position,archived_at,created_at,updated_at) "
            "VALUES (1,'Core','custom',0,NULL,?,?)",
            (_AT, _AT),
        )
        setup.execute(
            "INSERT INTO watchlist_memberships "
            "(list_id,ticker,position,archived_at,created_at,updated_at) "
            "VALUES (1,'OLD',0,NULL,?,?)",
            (_AT, _AT),
        )

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    crashed = False

    def profile_rows():
        return {
            table: harness.conn.execute(
                f'SELECT * FROM "{table}" ORDER BY rowid'
            ).fetchall()
            for table in (
                "ticker_meta",
                "ticker_tags",
                "universe_source_memberships",
                "watchlist_memberships",
            )
        }

    before_profile = profile_rows()

    def approve_then_crash(*, case, request, sources):
        nonlocal crashed
        store = _store(harness)
        assessment = store.project_case_state(
            case["case_id"],
            observation_fingerprint_sha256=case["observation_fingerprint_sha256"],
        )["current_assessment"]
        assert assessment is not None
        proposals = store.project_proposals(
            case["case_id"],
            observation_fingerprint_sha256=case["observation_fingerprint_sha256"],
        )
        assert all(
            proposal["assessment_fingerprint_sha256"]
            == assessment_fingerprint(assessment)
            for proposal in proposals
        )
        preview = build_transition_preview(
            harness.conn,
            case=case,
            assessment=assessment,
            proposals=proposals,
            observation_fingerprint_sha256=case["observation_fingerprint_sha256"],
            sources=sources,
            options=TransitionOptions(execute_on=str(request["effective_date"])),
        )
        result = TickerIdentityTransitionStore(
            harness.conn,
            clock=lambda: harness.now,
            id_factory=lambda prefix: f"{prefix}_recovery",
        ).approve_automation(
            preview=preview,
            approved_preview_sha256=str(preview["preview_sha256"]),
        )
        if not crashed:
            crashed = True
            raise _InjectedFinalizationCrash("approval")
        return result

    harness.transition_approver = approve_then_crash
    try:
        with pytest.raises(_InjectedFinalizationCrash, match="approval"):
            harness.worker_with_transition_approver().run()
        assert (
            harness.conn.execute(
                "SELECT COUNT(*) FROM ticker_identity_transitions"
            ).fetchone()[0]
            == 1
        )
        assert profile_rows() == before_profile

        recovered = harness.worker_with_transition_approver().run()
        store = _store(harness)
        assert recovered["accepted"] == 1
        assert (
            harness.conn.execute(
                "SELECT COUNT(*) FROM ticker_identity_transitions"
            ).fetchone()[0]
            == 1
        )
        assert len(store.list_assessments(case["case_id"])) == 1
        assert len(store.list_proposals(case["case_id"])) == 2
        assert profile_rows() == before_profile
    finally:
        harness.conn.close()


def test_nonmutating_and_review_suggested_results_never_approve_transition(
    tmp_path,
):
    terminal = _case(1, ticker="TERM", terminal=True)
    review = _case(2, ticker="MNA")
    harness = _Harness(tmp_path, [terminal, review])
    harness.bundles[terminal["case_id"]] = _bundle(terminal, terminal=True)
    harness.bundles[review["case_id"]] = _bundle(
        review,
        review_structure="cash",
    )
    try:
        result = harness.worker_with_transition_approver().run(limit=2)

        assert result["accepted"] == 0
        assert result["drafted"] == 2
        assert result["failed"] == 0
        assert harness.approval_calls == []
        terminal_assessment = _store(harness).list_assessments(terminal["case_id"])[0]
        assert terminal_assessment["status"] == "draft"
        assert terminal_assessment["outcomes"] == ["undetermined"]
    finally:
        harness.conn.close()


def test_transition_approval_drift_fails_closed_without_profile_mutation(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.approval_error = ValueError("transition_preview_changed")
    try:
        result = harness.worker_with_transition_approver().run()

        store = _store(harness)
        run = store.list_automation_runs(case["case_id"])[0]
        assessment = store.list_assessments(case["case_id"])[0]

        assert result["accepted"] == 1
        assert result["failed"] == 0
        assert len(harness.approval_calls) == 1
        assert harness.approval_calls[0]["assessment_status"] == "accepted"
        assert harness.approval_calls[0]["proposal_actions"] == (
            "notify",
            "remap_symbol",
        )
        assert (
            harness.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name='ticker_identity_transitions'"
            ).fetchone()[0]
            == 0
        )
        assert assessment["status"] == "accepted"
        assert run["status"] == "succeeded"
        assert run["action_readiness"] == "waiting_transition_revalidation"
        assert [row["blocker_code"] for row in run["blockers"]] == [
            "transition_approval_changed"
        ]

        immediate = harness.worker_with_transition_approver().run()
        assert immediate["processed"] == 0
        assert immediate["skipped_current"] == 1

        harness.approval_error = None
        harness.now = "2026-08-26T12:00:00Z"
        retried = harness.worker_with_transition_approver().run()
        run = store.list_automation_runs(case["case_id"])[0]
        assert retried["accepted"] == 1
        assert len(harness.approval_calls) == 2
        assert len(harness.evidence_calls) == 1
        assert len(store.list_assessments(case["case_id"])) == 1
        assert len(store.list_proposals(case["case_id"])) == 2
        assert run["action_readiness"] == "transition_eligible"
        assert run["blockers"] == []
    finally:
        harness.conn.close()


def test_transition_approval_unavailable_is_visible_and_retryable(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.approval_error = ConnectionError("transition store unavailable")
    try:
        result = harness.worker_with_transition_approver().run()

        store = _store(harness)
        run = store.list_automation_runs(case["case_id"])[0]
        assert result["accepted"] == 1
        assert result["failed"] == 0
        assert run["status"] == "succeeded"
        assert run["action_readiness"] == "waiting_transition_revalidation"
        assert [row["blocker_code"] for row in run["blockers"]] == [
            "transition_approval_unavailable"
        ]
        assert len(store.list_assessments(case["case_id"])) == 1
        assert len(store.list_proposals(case["case_id"])) == 2
    finally:
        harness.conn.close()


def test_review_suggested_persists_complete_automation_draft_without_accepting(
    tmp_path,
):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _bundle(case, review_structure="cash")
    try:
        result = harness.worker().run()
        store = _store(harness)
        draft = store.list_assessments(case["case_id"])[0]

        assert result["drafted"] == 1
        assert result["accepted"] == 0
        assert draft["status"] == "draft"
        assert draft["author"] == "automation"
        assert draft["acceptance_authority"] is None
        assert draft["outcomes"] == ["acquisition_cash"]
        assert draft["counterparty_name"] == "Buyer Corp."
        assert draft["cash_per_security_decimal"] == "10"
        assert store.list_proposals(case["case_id"]) == []
    finally:
        harness.conn.close()


def test_ineligible_transition_preview_downgrades_to_review_suggested(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.preview_results = [
        {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": "symbol_continuation",
        },
        {
            "eligible": False,
            "block_reasons": ("successor_hidden",),
            "transition_kind": "symbol_continuation",
        },
    ]
    try:
        harness.worker().run()
        store = _store(harness)
        run = store.list_automation_runs(case["case_id"])[0]
        draft = store.list_assessments(case["case_id"])[0]

        assert len(harness.preview_calls) == 2
        assert run["decision_tier"] == "review_suggested"
        assert run["action_readiness"] == "action_blocked"
        assert draft["status"] == "draft"
    finally:
        harness.conn.close()


def test_provider_blockers_remain_typed_and_retryable_without_partial_assessment(
    tmp_path,
):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _bundle(
        case,
        blocker="sec_transport_unavailable",
        retry_at="2026-08-25T13:00:00Z",
    )
    try:
        result = harness.worker().run()
        store = _store(harness)
        run = store.list_automation_runs(case["case_id"])[0]

        assert result["blocked"] == 1
        assert run["status"] == "blocked"
        assert run["retry_at"] == "2026-08-25T13:00:00Z"
        assert [row["blocker_code"] for row in run["blockers"]] == [
            "sec_transport_unavailable"
        ]
        assert store.list_assessments(case["case_id"]) == []
    finally:
        harness.conn.close()


def test_worker_keeps_preserved_retry_material_out_of_current_material(tmp_path):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    base = _bundle(case)
    first_blocker = AutomationBlocker(
        code="listing_directory_unavailable",
        retryable=True,
        context={"attempts": 1},
    )
    first_bundle = LifecycleAutomationEvidenceBundle(
        evidence=base.evidence,
        facts=base.facts,
        blockers=(first_blocker,),
        diagnostics={"listing_requests": 1},
        retry_at="2026-08-25T13:00:00Z",
    )
    regulator = base.evidence[0]
    fresh_regulator = replace(
        regulator,
        evidence_id=f"{regulator.evidence_id}-fresh",
        source_url=f"{regulator.source_url}?fresh=1",
        title=f"{regulator.title} fresh",
        evidence_dedupe_key=f"{regulator.evidence_dedupe_key}:fresh",
    )
    fresh_facts = tuple(
        replace(fact, evidence_id=fresh_regulator.evidence_id)
        for fact in base.facts
        if fact.evidence_id == regulator.evidence_id
    )
    calls = []

    def evidence_loader(current, *, mode, at, prior_material):
        calls.append((current["case_id"], mode, at, prior_material))
        if not (
            prior_material.evidence
            or prior_material.facts
            or prior_material.blockers
        ):
            return first_bundle
        preserved_evidence = tuple(
            {
                **dict(row),
                "source_locator": json.loads(row["source_locator_json"]),
            }
            for row in prior_material.evidence
        )
        preserved_facts = tuple(
            {
                **dict(row),
                "normalized_value": json.loads(row["normalized_value_json"]),
            }
            for row in prior_material.facts
        )
        return LifecycleAutomationEvidenceBundle(
            evidence=(fresh_regulator,),
            facts=fresh_facts,
            blockers=(
                AutomationBlocker(
                    code="sec_rate_limited",
                    retryable=True,
                    context={"attempts": 1},
                ),
            ),
            diagnostics={"sec_attempts": 1},
            retry_at="2026-08-25T14:00:00Z",
            preserved_evidence=preserved_evidence,
            preserved_facts=preserved_facts,
            refreshed_source_families=("regulator",),
        )

    harness.evidence_loader = evidence_loader
    try:
        first = harness.worker().run(limit=1)
        first_run = _store(harness).list_automation_runs(case["case_id"])[0]
        assert first_run["status"] == "blocked"
        assert first_run["retry_at"] == "2026-08-25T13:00:00Z"
        harness.now = "2026-08-25T13:00:00Z"
        second = harness.worker().run(limit=1)
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert first["blocked"] == 1, first
        assert second["blocked"] == 1, second
        assert first["failed"] == 0, first
        assert second["failed"] == 0, second
        assert len(calls) == 2
        assert calls[1][3] is not None
        assert run["status"] == "blocked"
        assert run["failure_code"] is None
    finally:
        harness.conn.close()


def test_mixed_provider_and_policy_blockers_do_not_enter_evaluation(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
        LifecycleAutomationWorker,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    base = _bundle(case)
    harness.bundles[case["case_id"]] = LifecycleAutomationEvidenceBundle(
        evidence=base.evidence,
        facts=base.facts,
        blockers=(
            AutomationBlocker(
                code="sec_rate_limited",
                retryable=True,
                context={},
            ),
            AutomationBlocker(
                code="listing_authority_conflict",
                retryable=False,
                context={},
            ),
        ),
        diagnostics={"sec_attempts": 1, "listing_requests": 1},
        retry_at=None,
    )
    evaluate_calls = []
    evaluate = LifecycleAutomationWorker._evaluate

    def tracked_evaluate(self, **kwargs):
        evaluate_calls.append(kwargs)
        return evaluate(self, **kwargs)

    monkeypatch.setattr(LifecycleAutomationWorker, "_evaluate", tracked_evaluate)
    try:
        result = harness.worker().run()
        store = _store(harness)
        run = store.list_automation_runs(case["case_id"])[0]

        assert result["blocked"] == 1
        assert evaluate_calls == []
        assert store.list_assessments(case["case_id"]) == []
        assert [row["blocker_code"] for row in run["blockers"]] == [
            "listing_authority_conflict",
            "sec_rate_limited",
        ]
    finally:
        harness.conn.close()


@pytest.mark.parametrize(
    "family",
    ("regulator", "listing_authority"),
)
def test_same_family_conflict_plus_unavailable_does_not_enter_evaluation(
    tmp_path,
    monkeypatch,
    family,
):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
        LifecycleAutomationWorker,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    if family == "regulator":
        base = _conflict_bundle(case, pending=False)
        blockers = (
            *base.blockers,
            AutomationBlocker(
                code="sec_rate_limited",
                retryable=True,
                context={},
            ),
        )
    else:
        base = _bundle(case)
        blockers = (
            AutomationBlocker(
                code="listing_authority_conflict",
                retryable=False,
                context={},
            ),
            AutomationBlocker(
                code="listing_directory_unavailable",
                retryable=True,
                context={},
            ),
        )
    harness.bundles[case["case_id"]] = LifecycleAutomationEvidenceBundle(
        evidence=base.evidence,
        facts=base.facts,
        blockers=blockers,
        diagnostics={"sec_attempts": 1, "listing_requests": 1},
        retry_at=None,
    )
    evaluate_calls = []
    evaluate = LifecycleAutomationWorker._evaluate

    def tracked_evaluate(self, **kwargs):
        evaluate_calls.append(kwargs)
        return evaluate(self, **kwargs)

    monkeypatch.setattr(LifecycleAutomationWorker, "_evaluate", tracked_evaluate)
    try:
        result = harness.worker().run()
        store = _store(harness)
        run = store.list_automation_runs(case["case_id"])[0]

        assert result["blocked"] == 1
        assert result["failed"] == 0
        assert evaluate_calls == []
        assert store.list_assessments(case["case_id"]) == []
        assert run["status"] == "blocked"
    finally:
        harness.conn.close()


@pytest.mark.parametrize(
    ("code", "retryable"),
    [
        ("listing_authority_conflict", False),
        ("listing_directory_unavailable", True),
        ("listing_directory_stale", True),
        ("listing_directory_schema_mismatch", True),
        ("massive_credential_missing", False),
        ("massive_access_denied", True),
        ("massive_rate_limited", True),
        ("massive_reference_unavailable", True),
        ("listing_status_unresolved", True),
    ],
)
def test_scheduler_blocker_strings_persist_through_fact_kernel_readback(
    tmp_path,
    code,
    retryable,
):
    from src.security_lifecycle_automation_worker import LifecycleAutomationEvidenceBundle
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    blockers, retry_at = scheduler._blockers([code], at=_AT)
    harness.bundles[case["case_id"]] = LifecycleAutomationEvidenceBundle(
        evidence=(),
        facts=(),
        blockers=blockers,
        diagnostics={},
        retry_at=retry_at,
    )
    try:
        result = harness.worker().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert result["blocked"] == 1
        assert run["status"] == "blocked"
        assert [(row["blocker_code"], bool(row["retryable"])) for row in run["blockers"]] == [
            (code, retryable)
        ]
        assert (run["retry_at"] is not None) is retryable
    finally:
        harness.conn.close()


def test_massive_credential_recovery_requires_saved_key_and_attended_case_run(
    tmp_path,
):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    blockers, retry_at = scheduler._blockers(
        ["massive_credential_missing"],
        at=harness.now,
    )
    harness.bundles[case["case_id"]] = LifecycleAutomationEvidenceBundle(
        evidence=(),
        facts=(),
        blockers=blockers,
        diagnostics={},
        retry_at=retry_at,
    )
    try:
        blocked = harness.worker().run()
        harness.now = "2027-08-25T12:00:00Z"
        unattended = harness.worker(allow_due_failed_retry=True).run()

        harness.bundles[case["case_id"]] = _bundle(case)
        attended = harness.worker(
            allow_new_attempt=True,
            target_case_id=case["case_id"],
        ).run()
        runs = _store(harness).list_automation_runs(case["case_id"])

        assert retry_at is None
        assert blocked["blocked"] == 1
        assert unattended["skipped_current"] == 1
        assert attended["accepted"] == 1
        assert [row["status"] for row in runs] == ["succeeded", "blocked"]
        assert json.loads(runs[0]["query_context_json"])["predecessor_run_id"] == (
            runs[1]["run_id"]
        )
    finally:
        harness.conn.close()


@pytest.mark.parametrize("conflict_kind", ("listing_state", "sec_listing_cik"))
def test_real_listing_conflict_producer_matches_policy_and_persists_nonretryable(
    tmp_path,
    monkeypatch,
    conflict_kind,
):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.security_lifecycle_decision_policy import evaluate_automation_decision
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = _case(1)
    base = _bundle(case)
    regulator, active_listing, _market = base.evidence
    regulator_facts = tuple(
        fact for fact in base.facts if fact.evidence_id == regulator.evidence_id
    )
    active_facts = tuple(
        fact for fact in base.facts if fact.evidence_id == active_listing.evidence_id
    )
    listing_evidence = [active_listing]
    listing_facts = list(active_facts)
    if conflict_kind == "listing_state":
        conflicting, conflicting_facts = _listing_evidence(
            case,
            label="nasdaq-inactive-conflict",
            adapter="nasdaq_symbol_directory",
            ticker=f"{case['ticker']}2",
            expected_active_state=True,
            market="stocks",
            status="found",
            directory="nasdaq_listed",
            active=False,
        )
    else:
        conflicting, conflicting_facts = _listing_evidence(
            case,
            label="massive-cik-conflict",
            adapter="massive_reference",
            ticker=f"{case['ticker']}2",
            expected_active_state=True,
            market="stocks",
            status="found",
            active=True,
            fact_values={
                "destination_venue": "NASDAQ",
                "issuer_cik": "0000000999",
                "security_class": "common_stock",
                "successor_ticker": f"{case['ticker']}2",
            },
        )
    listing_evidence.append(conflicting)
    listing_facts.extend(conflicting_facts)

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(regulator,),
            facts=regulator_facts,
            blockers=(),
            source_deadlines=(),
        ),
    )
    monkeypatch.setattr(
        scheduler,
        "_ibkr_evidence",
        lambda *_args, **_kwargs: (
            SimpleNamespace(evidence=(), blockers=(), requests_made=0),
            (),
        ),
    )
    monkeypatch.setattr(
        scheduler,
        "_pending_event_monitoring",
        lambda *_args, **_kwargs: None,
    )
    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at=_AT,
        listing_session=SimpleNamespace(
            lookup=lambda **_kwargs: SimpleNamespace(
                evidence=tuple(listing_evidence),
                facts=tuple(listing_facts),
                blockers=(),
                diagnostics={},
            )
        ),
    )

    assert [(row.code, row.retryable) for row in bundle.blockers] == [
        ("listing_authority_conflict", False)
    ]
    decision = evaluate_automation_decision(
        case={
            **case["observation"],
            "case_id": case["case_id"],
            "ticker": case["ticker"],
            "event_kinds": ("listing_status_review",),
        },
        evidence=bundle.evidence,
        facts=bundle.facts,
        current_date="2026-08-25",
        active_sources=("manual_lists",),
        transition_preview=lambda _request: {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": "symbol_continuation",
        },
    )
    assert decision.decision_issues == ("listing_authority_conflict",)

    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = bundle
    try:
        result = harness.worker().run()
        persisted = _store(harness).list_automation_runs(case["case_id"])[0]
        assert result["blocked"] == 1
        expected_blockers = [("listing_authority_conflict", False)]
        if conflict_kind == "sec_listing_cik":
            expected_blockers.append(("source_conflict", False))
        assert [
            (row["blocker_code"], bool(row["retryable"]))
            for row in persisted["blockers"]
        ] == expected_blockers
    finally:
        harness.conn.close()


def test_program_error_fails_run_without_network_classification(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_automation_worker as worker_module

    acquire_case = _case(1)
    assessment_case = _case(2)
    harness = _Harness(tmp_path, [acquire_case, assessment_case])
    harness.bundles[acquire_case["case_id"]] = TypeError("fixture programmer fault")
    create_assessment = worker_module.create_automation_assessment
    monkeypatch.setattr(
        worker_module,
        "create_automation_assessment",
        lambda **_kwargs: (_ for _ in ()).throw(
            TypeError("post-complete programmer fault")
        ),
    )
    try:
        result = harness.worker().run()
        store = _store(harness)
        runs = [
            store.list_automation_runs(case["case_id"])[0]
            for case in (acquire_case, assessment_case)
        ]

        assert result["failed"] == 2
        assert runs[0]["status"] == "failed"
        assert runs[0]["failure_code"] == "internal_error"
        assert runs[1]["status"] == "succeeded"
        assert runs[1]["failure_code"] is None
        terminal_context = json.loads(runs[1]["query_context_json"])
        assert terminal_context["terminal_decision_provenance_sha256"]
        assert "terminal_finalized_decision_provenance_sha256" not in terminal_context
        assert all(run["blockers"] == [] for run in runs)
        assert "network" not in json.dumps(result).lower()
        assert "fixture programmer fault" not in json.dumps(result)
        assert "post-complete programmer fault" not in json.dumps(result)
        assert all(
            store.list_assessments(case["case_id"]) == []
            for case in (acquire_case, assessment_case)
        )

        monkeypatch.setattr(
            worker_module,
            "create_automation_assessment",
            create_assessment,
        )
        recovered = harness.worker().run()
        recovered_run = store.list_automation_runs(assessment_case["case_id"])[0]
        recovered_context = json.loads(recovered_run["query_context_json"])
        assert recovered["accepted"] == 1
        assert (
            recovered_context["terminal_finalized_decision_provenance_sha256"]
            == recovered_context["terminal_decision_provenance_sha256"]
        )
        assert len(store.list_assessments(assessment_case["case_id"])) == 1
    finally:
        harness.conn.close()


def test_current_assessment_is_not_reprocessed(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    try:
        first = harness.worker().run()
        calls = list(harness.evidence_calls)
        second = harness.worker().run()

        assert first["accepted"] == 1
        assert first["result_version"] == 2
        assert first["case_outcomes"] == {case["case_id"]: "accepted"}
        assert second["processed"] == 0
        assert second["skipped_current"] == 1
        assert second["result_version"] == 2
        assert second["case_outcomes"] == {
            case["case_id"]: "skipped_current"
        }
        assert harness.evidence_calls == calls
        assert (
            harness.conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_automation_runs"
            ).fetchone()[0]
            == 1
        )
    finally:
        harness.conn.close()


def test_worker_records_execution_revision_without_replaying_current_failed_run(
    tmp_path,
):
    from src.security_lifecycle_automation_worker import (
        AUTOMATION_EXECUTION_REVISION,
    )
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _invalid_persistence_bundle(case)
    try:
        first = harness.worker().run()
        second = harness.worker().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]
        context = json.loads(run["query_context_json"])

        assert AUTOMATION_POLICY_VERSION == "trusted-lifecycle-automation-v4"
        assert context["execution_revision"] == "trusted-lifecycle-execution-r1"
        assert AUTOMATION_EXECUTION_REVISION == "trusted-lifecycle-execution-r1"
        assert first["failed"] == 1
        assert second["processed"] == 0
        assert second["skipped_current"] == 1
        assert len(_store(harness).list_automation_runs(case["case_id"])) == 1
    finally:
        harness.conn.close()


def test_worker_automatic_retry_authority_is_opt_in_and_due_only(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _invalid_persistence_bundle(case)
    try:
        first = harness.worker().run()
        harness.now = "2026-08-25T12:15:00Z"
        parked = harness.worker().run()
        due = harness.worker(allow_due_failed_retry=True).run()
        runs = _store(harness).list_automation_runs(case["case_id"])

        assert first["failed"] == 1
        assert parked["skipped_current"] == 1
        assert due["failed"] == 1
        assert len(runs) == 2
        assert json.loads(runs[0]["query_context_json"])["predecessor_run_id"] == (
            runs[1]["run_id"]
        )
    finally:
        harness.conn.close()


def test_source_payload_invalid_receives_exactly_one_automatic_retry(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = ValueError("malformed provider content")
    try:
        first = harness.worker().run()
        harness.now = "2026-08-25T13:00:00Z"
        retry = harness.worker(allow_due_failed_retry=True).run()
        harness.now = "2027-08-25T13:00:00Z"
        exhausted = harness.worker(allow_due_failed_retry=True).run()
        runs = _store(harness).list_automation_runs(case["case_id"])

        assert first["failed"] == retry["failed"] == 1
        assert exhausted["skipped_current"] == 1
        assert len(harness.evidence_calls) == 2
        assert len(runs) == 2
        assert {row["failure_code"] for row in runs} == {"source_payload_invalid"}
        assert json.loads(runs[0]["query_context_json"])["predecessor_run_id"] == (
            runs[1]["run_id"]
        )
    finally:
        harness.conn.close()


def test_due_acquisition_failure_retains_prior_provider_material(tmp_path):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    blockers, retry_at = scheduler._blockers(
        ["listing_directory_unavailable"],
        at=harness.now,
    )
    complete = _bundle(case)
    harness.bundles[case["case_id"]] = LifecycleAutomationEvidenceBundle(
        evidence=complete.evidence,
        facts=complete.facts,
        blockers=blockers,
        diagnostics={"listing_requests": 1},
        retry_at=retry_at,
    )

    def rows(table, order_by):
        return tuple(
            tuple(row)
            for row in harness.conn.execute(
                f"SELECT * FROM {table} ORDER BY {order_by}"
            )
        )

    try:
        first = harness.worker().run()
        before = {
            "evidence": rows("security_lifecycle_evidence", "evidence_id"),
            "facts": rows("security_lifecycle_automation_facts", "fact_id"),
            "blockers": rows(
                "security_lifecycle_automation_run_blockers", "blocker_code"
            ),
        }
        harness.now = str(retry_at)
        harness.bundles[case["case_id"]] = ValueError("malformed provider content")

        failed = harness.worker().run()
        after = {
            "evidence": rows("security_lifecycle_evidence", "evidence_id"),
            "facts": rows("security_lifecycle_automation_facts", "fact_id"),
            "blockers": rows(
                "security_lifecycle_automation_run_blockers", "blocker_code"
            ),
        }
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert first["blocked"] == failed["failed"] == 1
        assert after == before
        assert run["failure_code"] == "source_payload_invalid"
    finally:
        harness.conn.close()


def test_attended_worker_targets_exact_case_and_creates_new_attempt(tmp_path):
    cases = [_case(1), _case(2)]
    harness = _Harness(tmp_path, cases)
    try:
        initial = harness.worker().run(limit=2)
        before = {
            case["case_id"]: tuple(_store(harness).list_automation_runs(case["case_id"]))
            for case in cases
        }
        harness.now = "2026-08-25T13:00:00Z"

        attended = harness.worker(
            allow_new_attempt=True,
            target_case_id=cases[1]["case_id"],
        ).run(limit=2)
        after = {
            case["case_id"]: _store(harness).list_automation_runs(case["case_id"])
            for case in cases
        }

        assert initial["accepted"] == 2
        assert attended["selected"] == 1
        assert attended["case_ids"] == [cases[1]["case_id"]]
        assert after[cases[0]["case_id"]] == list(before[cases[0]["case_id"]])
        assert len(after[cases[1]["case_id"]]) == 2
        assert json.loads(after[cases[1]["case_id"]][0]["query_context_json"])[
            "predecessor_run_id"
        ] == before[cases[1]["case_id"]][0]["run_id"]
    finally:
        harness.conn.close()


def test_deadline_supersession_metadata_is_transient_through_worker_persistence(
    tmp_path,
):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _deadline_bundle(case)
    try:
        result = harness.worker().run()
        run = _store(harness).list_automation_runs(case["case_id"])[0]

        assert result["blocked"] == 1
        assert run["status"] == "blocked"
        assert len(run["blockers"]) == 1
        context = json.loads(run["blockers"][0]["context_json"])
        assert context["source_deadline"] == "2026-08-24"
        assert context["source_deadline_rule_version"] == "4"
        assert "kind" not in context
        assert "supersedes_date" not in context
        assert (
            harness.conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_automation_facts "
                "WHERE automation_run_id=?",
                (run["run_id"],),
            ).fetchone()[0]
            == 0
        )
    finally:
        harness.conn.close()


def test_forged_deadline_failure_replays_once_after_execution_revision_change(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_automation_worker as worker_module

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _deadline_bundle(
        case,
        forge_citation=True,
    )
    try:
        first_result = harness.worker().run()
        store = _store(harness)
        failed_run = store.list_automation_runs(case["case_id"])[0]
        failed_snapshot = store.get_automation_run(failed_run["run_id"])

        assert first_result["failed"] == 1
        assert failed_run["failure_code"] == "persistence_failed"
        assert json.loads(failed_run["diagnostics_json"]) == {
            "failures": 1,
            "news_evidence_count": 20,
            "sec_attempts": 7,
        }
        assert failed_run["blockers"] == []
        assert (
            harness.conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_evidence "
                "WHERE automation_run_id=?",
                (failed_run["run_id"],),
            ).fetchone()[0]
            == 0
        )

        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_EXECUTION_REVISION",
            "trusted-lifecycle-execution-r2",
        )
        replay_result = harness.worker().run()
        runs = store.list_automation_runs(case["case_id"])

        assert replay_result["selected"] == 1
        assert replay_result["failed"] == 1
        assert len(runs) == 2
        assert runs[0]["run_id"] != failed_run["run_id"]
        assert (
            json.loads(runs[0]["query_context_json"])["predecessor_run_id"]
            == failed_run["run_id"]
        )
        assert store.get_automation_run(failed_run["run_id"]) == failed_snapshot
    finally:
        harness.conn.close()


def test_execution_revision_does_not_change_decision_or_transition_authority(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_automation_worker as worker_module

    cases = [_case(1)]
    r0_path = tmp_path / "r0"
    r1_path = tmp_path / "r1"
    r0_path.mkdir()
    r1_path.mkdir()
    r0 = _Harness(r0_path, cases)
    r1 = _Harness(r1_path, cases)
    try:
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_EXECUTION_REVISION",
            "trusted-lifecycle-execution-r0",
        )
        r0.worker().run()
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_EXECUTION_REVISION",
            "trusted-lifecycle-execution-r1",
        )
        r1.worker().run()

        assessment_r0 = _store(r0).list_assessments(cases[0]["case_id"])[0]
        assessment_r1 = _store(r1).list_assessments(cases[0]["case_id"])[0]
        assert (
            assessment_r0["decision_provenance_sha256"]
            == assessment_r1["decision_provenance_sha256"]
        )
        assert assessment_r0["rule_id"] == assessment_r1["rule_id"]
        assert assessment_r0["rule_version"] == assessment_r1["rule_version"]
        with open("src/ticker_identity_transition.py", encoding="utf-8") as source:
            assert "execution_revision" not in source.read()
        assert "execution_revision" not in json.dumps(r1.approval_calls)
    finally:
        r0.conn.close()
        r1.conn.close()


def test_changed_observation_or_policy_reenters_and_stales_old_result(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_decision_policy as policy_module

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    try:
        harness.worker().run()
        store = _store(harness)
        store.add_evidence(
            case_id=case["case_id"],
            run_id=None,
            kind="manual_text",
            adapter="manual",
            excerpt="Supplemental issuer context.",
            source_url=None,
            title=None,
            publisher=None,
            domain=None,
            source_published_at=None,
            retrieved_at=None,
            mime_type="text/plain",
            document_status=None,
            at=_AT,
        )
        evidence_result = harness.worker().run()
        assert evidence_result["accepted"] == 1
        assert len(store.list_automation_runs(case["case_id"])) == 2

        case["observation_fingerprint_sha256"] = "e" * 64
        harness.worker().run()
        assert len(store.list_automation_runs(case["case_id"])) == 3

        import src.security_lifecycle_automation_worker as worker_module

        monkeypatch.setattr(
            policy_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v5",
        )
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v5",
        )
        harness.worker().run()

        runs = store.list_automation_runs(case["case_id"])
        history = store.list_assessments(case["case_id"])
        assert len(runs) == 4
        assert len(history) == 4
        assert history[0]["status"] == "accepted"
        assert all(row["status"] == "superseded" for row in history[1:])
    finally:
        harness.conn.close()


def test_v3_reprocesses_v2_draft_without_deleting_audit_history(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_automation_worker as worker_module
    import src.security_lifecycle_decision_policy as policy_module

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _bundle(case, review_structure="stock")
    try:
        monkeypatch.setattr(
            policy_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v2",
        )
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v2",
        )
        first = harness.worker().run()
        store = _store(harness)
        old = store.list_assessments(case["case_id"])[0]
        assert first["drafted"] == 1
        assert old["status"] == "draft"

        monkeypatch.setattr(
            policy_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v3",
        )
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v3",
        )
        second = harness.worker().run()

        runs = store.list_automation_runs(case["case_id"])
        assert second["processed"] == 1
        assert len(runs) == 2
        assert runs[0]["policy_version"] == "trusted-lifecycle-automation-v3"
        assert runs[0]["run_id"] != old["automation_run_id"]
        assert store.get_assessment(old["assessment_id"])["status"] == "draft"
        projected = store.project_case_state(
            case["case_id"],
            observation_fingerprint_sha256=case["observation_fingerprint_sha256"],
        )
        old_projection = next(
            row
            for row in projected["assessment_history"]
            if row["assessment_id"] == old["assessment_id"]
        )
        assert old_projection["stale"] is True
    finally:
        harness.conn.close()


def test_v3_reprocesses_human_accepted_v2_automation_without_rewriting_it(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_automation_worker as worker_module
    import src.security_lifecycle_decision_policy as policy_module

    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.bundles[case["case_id"]] = _bundle(case, review_structure="stock")
    try:
        monkeypatch.setattr(
            policy_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v2",
        )
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v2",
        )
        harness.worker().run()
        store = _store(harness)
        old = store.list_assessments(case["case_id"])[0]
        store.accept_assessment(
            old["assessment_id"],
            observation_fingerprint_sha256=case["observation_fingerprint_sha256"],
            acceptance_authority="human",
            at=_AT,
        )
        before = store.get_assessment(old["assessment_id"])

        monkeypatch.setattr(
            policy_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v3",
        )
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v3",
        )
        result = harness.worker().run()
        persisted = store.get_assessment(old["assessment_id"])

        assert result["processed"] == 1
        assert persisted["status"] == "accepted"
        for field in (
            "conclusion",
            "impact_summary",
            "decision_provenance_sha256",
            "evidence_set_sha256",
            "observation_fingerprint_sha256",
        ):
            assert persisted[field] == before[field]
        projected = store.project_case_state(
            case["case_id"],
            observation_fingerprint_sha256=case["observation_fingerprint_sha256"],
        )
        old_projection = next(
            row
            for row in projected["assessment_history"]
            if row["assessment_id"] == old["assessment_id"]
        )
        assert old_projection["stale"] is True
        assert (
            store.list_automation_runs(case["case_id"])[0]["policy_version"]
            == "trusted-lifecycle-automation-v3"
        )
    finally:
        harness.conn.close()


def test_worker_uses_only_injected_evidence_sources_and_paths(tmp_path, monkeypatch):
    from src.security_lifecycle_automation_worker import LifecycleAutomationWorker

    signature = inspect.signature(LifecycleAutomationWorker)
    for name in (
        "case_loader",
        "profile_connection",
        "evidence_loader",
        "source_loader",
        "transition_preview",
        "transition_approver",
        "clock",
    ):
        assert signature.parameters[name].default is inspect.Parameter.empty

    monkeypatch.setattr(
        socket,
        "socket",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("worker core attempted network access")
        ),
    )
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    try:
        assert harness.worker().run()["accepted"] == 1
    finally:
        harness.conn.close()


def test_worker_rechecks_pre_effective_terminal_when_effective_date_becomes_due(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_automation_worker import AUTOMATION_EXECUTION_REVISION
    from src.security_lifecycle_automation_worker import LifecycleAutomationWorker
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_disposition import next_lifecycle_recheck_at

    terminal = _case(1, ticker="TERM", terminal=True)
    unrelated = _case(2, ticker="OLD")
    harness = _Harness(tmp_path, [terminal, unrelated])
    evaluated_evidence_ids = []
    original_evaluate = LifecycleAutomationWorker._evaluate

    def tracked_evaluate(self, **kwargs):
        evaluated_evidence_ids.append(
            tuple(
                sorted(
                    str(getattr(row, "evidence_id", None) or row["evidence_id"])
                    for row in kwargs["evidence"]
                )
            )
        )
        return original_evaluate(self, **kwargs)

    monkeypatch.setattr(LifecycleAutomationWorker, "_evaluate", tracked_evaluate)
    harness.now = "2026-08-31T12:00:00Z"
    harness.bundles[terminal["case_id"]] = _bundle(terminal, terminal=True)
    try:
        first = harness.worker().run(limit=2)
        assert first["accepted"] == 1
        assert first["drafted"] == 1
        assert first["failed"] == 0
        store = _store(harness)
        terminal_run = store.list_automation_runs(terminal["case_id"])[0]
        assert terminal_run["action_readiness"] == "waiting_effective_date"
        terminal_assessment = store.list_assessments(terminal["case_id"])[0]
        assert terminal_assessment["status"] == "draft"
        assert terminal_assessment["outcomes"] == ["undetermined"]
        assert (
            next_lifecycle_recheck_at(terminal_run, terminal_assessment)
            == "2026-09-01T00:00:00Z"
        )
        first_query_context = json.loads(terminal_run["query_context_json"])
        assert terminal_run["policy_version"] == AUTOMATION_POLICY_VERSION
        assert (
            first_query_context["execution_revision"]
            == AUTOMATION_EXECUTION_REVISION
        )

        harness.evidence_calls.clear()
        evaluated_evidence_ids.clear()
        harness.now = "2026-09-01T12:00:00Z"
        harness.bundles[terminal["case_id"]] = replace(
            _bundle(
                terminal,
                terminal=True,
                market_absent=True,
            ),
            refreshed_source_families=(
                "listing_authority",
                "market_infrastructure",
                "regulator",
            ),
        )
        second = harness.worker().run(limit=2)

        assert second["processed"] == 1
        assert second["accepted"] == 1
        assert second["failed"] == 0
        assert second["skipped_current"] == 1
        assert harness.evidence_calls == [
            (terminal["case_id"], "live", "2026-09-01T12:00:00Z")
        ]
        expected_evidence_ids = tuple(
            sorted(
                row.evidence_id
                for row in harness.bundles[terminal["case_id"]].evidence
            )
        )
        assert evaluated_evidence_ids == [
            expected_evidence_ids,
            expected_evidence_ids,
        ]
        terminal_run = store.list_automation_runs(terminal["case_id"])[0]
        assert terminal_run["action_readiness"] == "transition_eligible"
        assert terminal_run["policy_version"] == AUTOMATION_POLICY_VERSION
        assert (
            json.loads(terminal_run["query_context_json"])["execution_revision"]
            == AUTOMATION_EXECUTION_REVISION
        )
        assert len(store.list_automation_runs(unrelated["case_id"])) == 1
        assert len(store.list_automation_runs(terminal["case_id"])) == 1
        assert len(store.list_assessments(terminal["case_id"])) == 2
    finally:
        harness.conn.close()


def test_base_exception_during_due_readiness_recheck_reaps_the_current_owner(
    tmp_path,
):
    terminal = _case(1, ticker="TERM", terminal=True)
    harness = _Harness(tmp_path, [terminal])
    harness.now = "2026-08-31T12:00:00Z"
    harness.bundles[terminal["case_id"]] = _bundle(terminal, terminal=True)
    try:
        first = harness.worker(execution_owner_id="initial-readiness-owner").run()
        assert first["drafted"] == 1

        store = _store(harness)
        waiting_run = store.list_automation_runs(terminal["case_id"])[0]
        assert waiting_run["status"] == "succeeded"
        assert waiting_run["action_readiness"] == "waiting_effective_date"
        assert json.loads(waiting_run["query_context_json"])[
            "execution_owner_id"
        ] == "initial-readiness-owner"

        harness.now = "2026-09-01T12:00:00Z"
        harness.bundles[terminal["case_id"]] = _InjectedEvidenceCrash(
            "due readiness recheck"
        )
        with pytest.raises(_InjectedEvidenceCrash, match="due readiness recheck"):
            harness.worker(execution_owner_id="due-readiness-owner").run()

        recovered_run = store.list_automation_runs(terminal["case_id"])[0]
        assert recovered_run["status"] == "failed"
        assert recovered_run["failure_code"] == "internal_error"
        assert json.loads(recovered_run["diagnostics_json"]) == {
            "interrupted_execution": 1,
        }
        assert json.loads(recovered_run["query_context_json"])[
            "execution_owner_id"
        ] == "due-readiness-owner"
    finally:
        harness.conn.close()
