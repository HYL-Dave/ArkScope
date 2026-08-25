from __future__ import annotations

import hashlib
import inspect
import json
import socket
import sqlite3
from contextlib import contextmanager


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
            case["observation"]["evidence_url"]
            if family == "regulator"
            else None
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
        facts = tuple(
            _fact(regulator, regulator_payload, key, key)
            for key in regulator_payload
        )
        evidence = [regulator]
        if market_absent:
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
        return LifecycleAutomationEvidenceBundle(
            evidence=tuple(evidence),
            facts=facts,
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
    market_payload = {
        "destination_venue": "NASDAQ",
        "security_class": "common_stock",
        "successor_ticker": successor,
    }
    market = _evidence(
        case,
        family="market_infrastructure",
        payload=market_payload,
        kind="market_infrastructure_snapshot",
        locator={"snapshot": market_payload},
    )
    return LifecycleAutomationEvidenceBundle(
        evidence=(regulator, market),
        facts=(
            *(
                _fact(regulator, regulator_payload, key, key)
                for key in regulator_payload
            ),
            *(
                _fact(market, market_payload, key, key)
                for key in market_payload
            ),
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

    def evidence_loader(self, case, *, mode, at):
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

    def worker(self):
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
        )
        if "transition_approver" in inspect.signature(
            LifecycleAutomationWorker
        ).parameters:
            kwargs["transition_approver"] = self.transition_approver
        return LifecycleAutomationWorker(**kwargs)

    def worker_with_transition_approver(self):
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
        )


def _store(harness):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    return SecurityLifecycleInvestigationStore(harness.conn)


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
        assert harness.conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_automation_runs"
        ).fetchone()[0] == 2
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
        assert {row["action_type"] for row in store.list_proposals(case["case_id"])} == {
            "notify",
            "remap_symbol",
        }
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

        assert result["accepted"] == 1
        assert result["drafted"] == 1
        assert result["failed"] == 0
        assert harness.approval_calls == []
    finally:
        harness.conn.close()


def test_transition_approval_drift_fails_closed_without_profile_mutation(tmp_path):
    case = _case(1)
    harness = _Harness(tmp_path, [case])
    harness.approval_error = ValueError("transition_preview_changed")
    try:
        result = harness.worker_with_transition_approver().run()

        assert result["accepted"] == 0
        assert result["failed"] == 1
        assert len(harness.approval_calls) == 1
        assert harness.approval_calls[0]["assessment_status"] == "accepted"
        assert harness.approval_calls[0]["proposal_actions"] == (
            "notify",
            "remap_symbol",
        )
        assert harness.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name='ticker_identity_transitions'"
        ).fetchone()[0] == 0
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


def test_program_error_fails_run_without_network_classification(
    tmp_path,
    monkeypatch,
):
    import src.security_lifecycle_automation_worker as worker_module

    acquire_case = _case(1)
    assessment_case = _case(2)
    harness = _Harness(tmp_path, [acquire_case, assessment_case])
    harness.bundles[acquire_case["case_id"]] = TypeError(
        "fixture programmer fault"
    )
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
        assert {run["status"] for run in runs} == {"failed"}
        assert {run["failure_code"] for run in runs} == {"internal_error"}
        assert all(run["blockers"] == [] for run in runs)
        assert "network" not in json.dumps(result).lower()
        assert "fixture programmer fault" not in json.dumps(result)
        assert "post-complete programmer fault" not in json.dumps(result)
        assert all(
            store.list_assessments(case["case_id"]) == []
            for case in (acquire_case, assessment_case)
        )
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
        assert second["processed"] == 0
        assert second["skipped_current"] == 1
        assert harness.evidence_calls == calls
        assert harness.conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_automation_runs"
        ).fetchone()[0] == 1
    finally:
        harness.conn.close()


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
            "trusted-lifecycle-automation-v2",
        )
        monkeypatch.setattr(
            worker_module,
            "AUTOMATION_POLICY_VERSION",
            "trusted-lifecycle-automation-v2",
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


def test_worker_rechecks_due_action_readiness_without_reprocessing_unrelated_cases(
    tmp_path,
):
    terminal = _case(1, ticker="TERM", terminal=True)
    unrelated = _case(2, ticker="OLD")
    harness = _Harness(tmp_path, [terminal, unrelated])
    harness.now = "2026-08-31T12:00:00Z"
    harness.bundles[terminal["case_id"]] = _bundle(terminal, terminal=True)
    try:
        first = harness.worker().run(limit=2)
        assert first["accepted"] == 2
        store = _store(harness)
        terminal_run = store.list_automation_runs(terminal["case_id"])[0]
        assert terminal_run["action_readiness"] == "waiting_effective_date"

        harness.evidence_calls.clear()
        harness.now = "2026-09-01T12:00:00Z"
        harness.bundles[terminal["case_id"]] = _bundle(
            terminal,
            terminal=True,
            market_absent=True,
        )
        second = harness.worker().run(limit=2)

        assert second["processed"] == 1
        assert second["accepted"] == 1
        assert [row[0] for row in harness.evidence_calls] == [terminal["case_id"]]
        terminal_run = store.list_automation_runs(terminal["case_id"])[0]
        assert terminal_run["action_readiness"] == "transition_eligible"
        assert len(store.list_automation_runs(unrelated["case_id"])) == 1
        assert len(store.list_assessments(terminal["case_id"])) == 2
    finally:
        harness.conn.close()
