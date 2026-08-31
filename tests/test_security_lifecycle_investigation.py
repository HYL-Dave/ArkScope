from __future__ import annotations

import json
import sqlite3

import pytest


_AT = "2026-08-20T00:00:00Z"
_LATER = "2026-08-20T01:00:00Z"
_FINGERPRINT = "a" * 64
_CHANGED_FINGERPRINT = "b" * 64


def _context(tmp_path):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    conn = sqlite3.connect(tmp_path / "profile_state.db")
    store = SecurityLifecycleInvestigationStore(
        conn,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0000712515-26-000042",
        ticker="EA",
        at=_AT,
    )
    return conn, store, case_id


def _manual_evidence(store, case_id, *, excerpt="Official issuer notice."):
    return store.add_evidence(
        case_id=case_id,
        run_id=None,
        kind="manual_text",
        adapter="manual",
        excerpt=excerpt,
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


@pytest.mark.parametrize(
    "adapter", ("nasdaq_symbol_directory", "massive_reference")
)
def test_investigation_store_accepts_listing_adapter_shape_for_readback(
    tmp_path, adapter
):
    from src.security_lifecycle_fact_kernel import SecurityLifecycleFactKernel

    conn, store, case_id = _context(tmp_path)
    try:
        claim = SecurityLifecycleFactKernel(store).reserve_run(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            policy_version="trusted-lifecycle-v1",
            mode="historical",
            execution_revision="trusted-lifecycle-execution-r1",
            execution_owner_id="test-investigation-owner",
            query_context={"case_id": case_id, "ticker": "EA"},
            diagnostics={"listing_records": 0},
            at=_AT,
        )
        document_sha256 = "d" * 64
        evidence_id = store.add_evidence(
            case_id=case_id,
            run_id=None,
            kind="listing_directory_snapshot",
            adapter=adapter,
            excerpt='{"listing_status":"active","ticker":"EA"}',
            source_url="https://listing.example/reference",
            title="Exact listing lookup",
            publisher="Listing authority",
            domain="listing.example",
            source_published_at="2026-08-20",
            retrieved_at=_AT,
            mime_type=None,
            document_status=None,
            at=_AT,
            source_family="listing_authority",
            automation_run_id=claim.run_id,
            source_document_sha256=document_sha256,
            source_locator={
                "authority": "nasdaq_trader"
                if adapter == "nasdaq_symbol_directory"
                else "massive",
                "candidate_ticker": "EA",
                "listing_status": "active",
            },
            evidence_dedupe_key=f"listing:{adapter}:EA",
        )

        persisted = store.get_evidence(evidence_id)
        assert persisted["source_family"] == "listing_authority"
        assert persisted["kind"] == "listing_directory_snapshot"
        assert persisted["adapter"] == adapter
        assert persisted["source_document_sha256"] == document_sha256
        assert json.loads(persisted["source_locator_json"])["candidate_ticker"] == "EA"
    finally:
        conn.close()


def _draft(
    store,
    case_id,
    *,
    relevance="direct_tracked_security",
    outcomes=("listing_ended",),
    citations=None,
    successor_ticker=None,
    cash=None,
    ratio=None,
    fingerprint=_FINGERPRINT,
):
    return store.create_assessment(
        case_id=case_id,
        relevance=relevance,
        confidence="medium",
        author="human",
        conclusion="The filing affects the tracked security.",
        impact_summary="Review the tracked membership before taking action.",
        outcomes=outcomes,
        citations=citations
        if citations is not None
        else [
            {
                "reference_kind": "observation",
                "cited_content_sha256": fingerprint,
            }
        ],
        observation_fingerprint_sha256=fingerprint,
        successor_ticker=successor_ticker,
        cash_per_security_decimal=cash,
        exchange_ratio_decimal=ratio,
        at=_AT,
    )


def _accept(store, assessment_id, *, fingerprint=_FINGERPRINT):
    return store.accept_assessment(
        assessment_id,
        observation_fingerprint_sha256=fingerprint,
        acceptance_authority="human",
        at=_LATER,
    )


def _automation_run(
    store,
    case_id,
    *,
    decision_tier="verified_automatic",
    action_readiness="transition_eligible",
    mode="historical",
):
    import hashlib

    from src.security_lifecycle_fact_kernel import (
        AutomationEvidence,
        AutomationFact,
        SecurityLifecycleFactKernel,
    )
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION

    kernel = SecurityLifecycleFactKernel(store)
    claim = kernel.reserve_run(
        case_id=case_id,
        observation_fingerprint_sha256=_FINGERPRINT,
        policy_version=AUTOMATION_POLICY_VERSION,
        mode=mode,
        execution_revision="trusted-lifecycle-execution-r1",
        execution_owner_id="test-investigation-owner",
        query_context={"case_id": case_id, "ticker": "EA"},
        diagnostics={"sec_attempts": 0},
        at=_AT,
    )
    excerpt = "The tracked security will continue under ticker EA2."
    evidence = AutomationEvidence(
        evidence_id="sec-evidence",
        source_family="regulator",
        adapter="sec_edgar",
        kind="regulator_excerpt",
        source_url="https://www.sec.gov/Archives/example/ea-8k.htm",
        title="EA filing",
        publisher="SEC EDGAR",
        domain="sec.gov",
        source_published_at="2026-08-20",
        retrieved_at=_AT,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_document_sha256="d" * 64,
        source_locator={"accession": "0000712515-26-000042"},
        evidence_dedupe_key=f"sec:{mode}",
    )
    start = excerpt.encode().index(b"EA2")
    fact = AutomationFact(
        evidence_id=evidence.evidence_id,
        fact_type="successor_ticker",
        normalized_value="EA2",
        source_span_start=start,
        source_span_end=start + 3,
        cited_text_sha256=hashlib.sha256(b"EA2").hexdigest(),
        extractor_rule_id="sec.symbol_change",
        extractor_rule_version="1",
    )
    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(evidence,),
        facts=(fact,),
        blockers=(),
        decision_tier=decision_tier,
        action_readiness=action_readiness,
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    return claim, result


def _automation_decision(*, tier="verified_automatic", readiness="transition_eligible"):
    return {
        "decision_tier": tier,
        "action_readiness": readiness,
        "relevance": "direct_tracked_security",
        "confidence": "high" if tier == "verified_automatic" else "medium",
        "outcomes": ("symbol_changed",),
        "conclusion": "The tracked security continues under ticker EA2.",
        "impact_summary": "Preserve tracking intent under the successor ticker.",
        "successor_ticker": "EA2",
        "destination_venue": "NASDAQ",
        "effective_date": "2026-08-25",
        "counterparty_name": None,
        "counterparty_ticker": None,
        "counterparty_cik": None,
        "consideration_currency": None,
        "cash_per_security_decimal": None,
        "exchange_ratio_decimal": None,
        "rule_id": "lifecycle.simple_symbol_continuation",
        "rule_version": "1",
        "decision_issues": (),
        "transition_requested": tier == "verified_automatic",
    }


def _composed_context(tmp_path):
    from src.security_lifecycle import (
        LifecycleObservation,
        ObservationKind,
        SecurityLifecycleStore,
    )
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        observation_fingerprint,
    )

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    market = sqlite3.connect(market_path)
    market_store = SecurityLifecycleStore(market)
    market_store.upsert_observation(
        LifecycleObservation(
            ticker="EA",
            cik="0000712515",
            issuer_name="Electronic Arts Inc.",
            filing_date="2026-08-04",
            source="sec_edgar",
            source_ref="0000712515-26-000042",
            filing_form="8-K",
            filing_items=("2.01", "3.01"),
            evidence_url="https://www.sec.gov/Archives/example/ea-8k.htm",
            description="Completion of acquisition and listing review.",
            observed_at=_AT,
            kinds=(
                ObservationKind("acquisition_completed", "2026-08-04"),
                ObservationKind("listing_status_review", None),
            ),
        )
    )
    observation = market_store.get_observation(
        "sec_edgar", "0000712515-26-000042", "EA"
    )
    fingerprint = observation_fingerprint(observation)
    market.close()

    profile = sqlite3.connect(profile_path)
    investigation_store = SecurityLifecycleInvestigationStore(
        profile,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    case_id = investigation_store.ensure_case(
        source="sec_edgar",
        source_ref="0000712515-26-000042",
        ticker="EA",
        at=_AT,
    )
    return (
        profile,
        investigation_store,
        case_id,
        market_path,
        profile_path,
        fingerprint,
    )


def test_accepting_assessment_requires_conclusion_citation_and_human_author(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        missing_citation = _draft(store, case_id, citations=[])
        with pytest.raises(ValueError, match="citation"):
            _accept(store, missing_citation)

        evidence_id = _manual_evidence(store, case_id)
        evidence_only = _draft(
            store,
            case_id,
            citations=[
                {
                    "reference_kind": "evidence",
                    "evidence_id": evidence_id,
                }
            ],
        )
        with pytest.raises(ValueError, match="observation_citation_required"):
            _accept(store, evidence_only)

        undetermined = _draft(
            store,
            case_id,
            relevance="undetermined",
            outcomes=("undetermined",),
        )
        with pytest.raises(ValueError, match="conclusive"):
            _accept(store, undetermined)

        with pytest.raises(ValueError, match="author"):
            store.create_assessment(
                case_id=case_id,
                relevance="direct_tracked_security",
                confidence="high",
                author="model",
                conclusion="Unsupported model conclusion.",
                impact_summary="Must not be accepted.",
                outcomes=("listing_ended",),
                citations=[
                    {
                        "reference_kind": "observation",
                        "cited_content_sha256": _FINGERPRINT,
                    }
                ],
                observation_fingerprint_sha256=_FINGERPRINT,
                at=_AT,
            )

        accepted = _accept(store, _draft(store, case_id))
        assert accepted["status"] == "accepted"
        assert accepted["author"] == "human"
        assert accepted["acceptance_authority"] == "human"
        assert accepted["automation_method"] is None
        assert accepted["automation_run_id"] is None
        assert accepted["decision_provenance_sha256"] is None
    finally:
        conn.close()


def test_acknowledgement_becomes_stale_when_evidence_is_added(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        _manual_evidence(store, case_id)
        acknowledgement = store.acknowledge_case(
            case_id=case_id,
            reason="evidence_insufficient",
            note="No conclusive successor evidence.",
            author="human",
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_AT,
        )
        before = store.project_case_state(
            case_id, observation_fingerprint_sha256=_FINGERPRINT
        )
        assert before["workflow_state"] == "reviewed_inconclusive"
        assert before["current_acknowledgement"]["stale"] is False

        _manual_evidence(store, case_id, excerpt="A later exchange notice.")
        after = store.project_case_state(
            case_id, observation_fingerprint_sha256=_FINGERPRINT
        )
        assert after["workflow_state"] == "evidence_ready"
        assert after["acknowledgement_history"][0]["acknowledgement_id"] == acknowledgement
        assert after["acknowledgement_history"][0]["stale"] is True
    finally:
        conn.close()


def test_acknowledgement_becomes_stale_when_source_fingerprint_changes(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        _manual_evidence(store, case_id)
        store.acknowledge_case(
            case_id=case_id,
            reason="evidence_insufficient",
            note=None,
            author="human",
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_AT,
        )
        current = store.project_case_state(
            case_id, observation_fingerprint_sha256=_FINGERPRINT
        )
        changed = store.project_case_state(
            case_id, observation_fingerprint_sha256=_CHANGED_FINGERPRINT
        )
        assert current["workflow_state"] == "reviewed_inconclusive"
        assert changed["workflow_state"] == "evidence_ready"
        assert changed["current_acknowledgement"] is None
        assert changed["acknowledgement_history"][0]["stale"] is True
    finally:
        conn.close()


def test_acknowledgement_requires_manual_evidence_or_a_succeeded_run(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        with pytest.raises(ValueError, match="investigation evidence"):
            store.acknowledge_case(
                case_id=case_id,
                reason="evidence_insufficient",
                note=None,
                author="human",
                observation_fingerprint_sha256=_FINGERPRINT,
                at=_AT,
            )
        _manual_evidence(store, case_id)
        acknowledgement_id = store.acknowledge_case(
            case_id=case_id,
            reason="evidence_insufficient",
            note=None,
            author="human",
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_AT,
        )
        assert acknowledgement_id.startswith("slk_")
    finally:
        conn.close()


def test_active_universe_unavailable_blocks_proposals_without_blocking_evidence(
    tmp_path,
):
    conn, store, case_id = _context(tmp_path)
    try:
        evidence_id = _manual_evidence(store, case_id)
        assessment_id = _draft(
            store,
            case_id,
            citations=[
                {
                    "reference_kind": "observation",
                    "cited_content_sha256": _FINGERPRINT,
                },
                {
                    "reference_kind": "evidence",
                    "evidence_id": evidence_id,
                }
            ],
        )
        _accept(store, assessment_id)
        result = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker=None,
            at=_LATER,
        )
        assert result == {
            "proposals": [],
            "block_reason": "source_context_unavailable",
        }
        assert len(store.list_evidence(case_id)) == 1
        assert store.list_proposals(case_id) == []
    finally:
        conn.close()


def test_conflicting_evidence_cannot_automatically_accept_a_conclusion(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        _manual_evidence(store, case_id, excerpt="Issuer says trading will continue.")
        _manual_evidence(store, case_id, excerpt="Exchange notice says trading ended.")
        draft = _draft(
            store,
            case_id,
            relevance="undetermined",
            outcomes=("undetermined",),
        )
        with pytest.raises(ValueError, match="conclusive"):
            _accept(store, draft)
        state = store.project_case_state(
            case_id, observation_fingerprint_sha256=_FINGERPRINT
        )
        assert state["workflow_state"] == "evidence_ready"
        assert state["current_assessment"] is None
        assert store.list_proposals(case_id) == []
    finally:
        conn.close()


def test_decimal_assessment_fields_are_canonical_strings_not_floats(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        with pytest.raises((TypeError, ValueError), match="decimal"):
            _draft(store, case_id, cash=10.5)
        for oversized in ("1e10000", "1e-10000"):
            with pytest.raises(ValueError, match="decimal"):
                _draft(store, case_id, cash=oversized)
        assessment_id = _draft(store, case_id, cash="10.5000", ratio="0.2500")
        assessment = store.get_assessment(assessment_id)
        assert assessment["cash_per_security_decimal"] == "10.5"
        assert assessment["exchange_ratio_decimal"] == "0.25"
        json.dumps(assessment)
    finally:
        conn.close()


def test_draft_accept_and_supersede_preserve_version_history(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        first = _draft(store, case_id)
        assert store.get_assessment(first)["status"] == "draft"
        _accept(store, first)
        original_proposals = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker={"EA": ("manual_lists",)},
            at=_LATER,
        )["proposals"]
        assert original_proposals
        second = _draft(
            store,
            case_id,
            outcomes=("symbol_changed",),
            successor_ticker="EA2",
        )
        _accept(store, second)
        history = store.list_assessments(case_id)
        assert [(item["revision"], item["status"]) for item in history] == [
            (2, "accepted"),
            (1, "superseded"),
        ]
        assert history[1]["accepted_at"] == _LATER
        assert history[1]["superseded_at"] == _LATER
        assert [item["acceptance_authority"] for item in history] == [
            "human",
            "human",
        ]
        projected = store.project_proposals(
            case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
        )
        assert {
            proposal["projected_block_reason"] for proposal in projected
        } == {"stale_assessment"}
    finally:
        conn.close()


def test_automation_policy_acceptance_requires_verified_current_run_and_matching_provenance(
    tmp_path,
):
    import inspect

    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, case_id = _context(tmp_path)
    try:
        claim, _result = _automation_run(store, case_id)
        assessment_id = create_automation_assessment(
            store=store,
            run_id=claim.run_id,
            decision=_automation_decision(),
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_LATER,
        )
        parameter = inspect.signature(store.accept_assessment).parameters[
            "acceptance_authority"
        ]
        assert parameter.default is inspect.Parameter.empty
        with pytest.raises(TypeError):
            store.accept_assessment(
                assessment_id,
                observation_fingerprint_sha256=_FINGERPRINT,
                at=_LATER,
            )

        conn.execute(
            "UPDATE security_lifecycle_automation_runs "
            "SET decision_tier='review_suggested',action_readiness='action_blocked' "
            "WHERE run_id=?",
            (claim.run_id,),
        )
        conn.commit()
        with pytest.raises(ValueError, match="automation_run_not_verified"):
            store.accept_assessment(
                assessment_id,
                observation_fingerprint_sha256=_FINGERPRINT,
                acceptance_authority="automation_policy",
                at=_LATER,
            )

        conn.execute(
            "UPDATE security_lifecycle_automation_runs "
            "SET decision_tier='verified_automatic',"
            "action_readiness='transition_eligible' WHERE run_id=?",
            (claim.run_id,),
        )
        conn.execute(
            "UPDATE security_lifecycle_automation_facts "
            "SET extractor_rule_version='2' WHERE automation_run_id=?",
            (claim.run_id,),
        )
        conn.commit()
        with pytest.raises(ValueError, match="automation_provenance_stale"):
            store.accept_assessment(
                assessment_id,
                observation_fingerprint_sha256=_FINGERPRINT,
                acceptance_authority="automation_policy",
                at=_LATER,
            )

        conn.execute(
            "UPDATE security_lifecycle_automation_facts "
            "SET extractor_rule_version='1' WHERE automation_run_id=?",
            (claim.run_id,),
        )
        conn.commit()
        accepted = store.accept_assessment(
            assessment_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            acceptance_authority="automation_policy",
            at=_LATER,
        )
        assert accepted["status"] == "accepted"
        assert accepted["author"] == "automation"
        assert accepted["acceptance_authority"] == "automation_policy"
        assert accepted["automation_run_id"] == claim.run_id
    finally:
        conn.close()


@pytest.mark.parametrize("tamper", ("assessment-field", "citation"))
def test_automation_assessment_reuse_rejects_changed_persisted_material(
    tmp_path,
    tamper,
):
    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, case_id = _context(tmp_path)
    try:
        claim, _result = _automation_run(store, case_id)
        assessment_id = create_automation_assessment(
            store=store,
            run_id=claim.run_id,
            decision=_automation_decision(),
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_LATER,
        )
        if tamper == "assessment-field":
            conn.execute(
                "UPDATE security_lifecycle_assessments SET conclusion=? "
                "WHERE assessment_id=?",
                ("Persisted conclusion changed.", assessment_id),
            )
        else:
            conn.execute(
                "UPDATE security_lifecycle_assessment_evidence "
                "SET cited_content_sha256=? "
                "WHERE assessment_id=? AND reference_kind='observation'",
                ("0" * 64, assessment_id),
            )
        conn.commit()

        with pytest.raises(ValueError, match="automation_assessment_changed"):
            create_automation_assessment(
                store=store,
                run_id=claim.run_id,
                decision=_automation_decision(),
                observation_fingerprint_sha256=_FINGERPRINT,
                at="2026-08-25T03:00:00Z",
            )
        assert len(store.list_assessments(case_id)) == 1
    finally:
        conn.close()


def test_human_accepts_unchanged_automation_draft_without_rewriting_author(tmp_path):
    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, case_id = _context(tmp_path)
    try:
        claim, _result = _automation_run(
            store,
            case_id,
            decision_tier="review_suggested",
            action_readiness="action_blocked",
        )
        assessment_id = create_automation_assessment(
            store=store,
            run_id=claim.run_id,
            decision=_automation_decision(
                tier="review_suggested",
                readiness="action_blocked",
            ),
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_LATER,
        )
        before = store.get_assessment(assessment_id)

        accepted = store.accept_assessment(
            assessment_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            acceptance_authority="human",
            at=_LATER,
        )

        assert accepted["status"] == "accepted"
        assert accepted["author"] == "automation"
        assert accepted["acceptance_authority"] == "human"
        assert accepted["revision"] == before["revision"]
        assert accepted["automation_method"] == "deterministic_rule"
        assert accepted["automation_run_id"] == claim.run_id
        assert accepted["rule_id"] == before["rule_id"]
        assert accepted["rule_version"] == before["rule_version"]
        assert accepted["decision_provenance_sha256"] == before[
            "decision_provenance_sha256"
        ]
    finally:
        conn.close()


def test_automation_assessment_stales_on_policy_rule_or_fact_provenance_change(
    tmp_path,
):
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, case_id = _context(tmp_path)
    try:
        claim, _result = _automation_run(store, case_id)
        assessment_id = create_automation_assessment(
            store=store,
            run_id=claim.run_id,
            decision=_automation_decision(),
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_LATER,
        )
        store.accept_assessment(
            assessment_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            acceptance_authority="automation_policy",
            at=_LATER,
        )
        assert store.project_case_state(
            case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
        )["current_assessment"]["assessment_id"] == assessment_id

        conn.execute(
            "UPDATE security_lifecycle_automation_runs SET policy_version='old' "
            "WHERE run_id=?",
            (claim.run_id,),
        )
        conn.commit()
        assert store.project_case_state(
            case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
        )["current_assessment"] is None

        conn.execute(
            "UPDATE security_lifecycle_automation_runs SET policy_version=? "
            "WHERE run_id=?",
            (AUTOMATION_POLICY_VERSION, claim.run_id),
        )
        conn.execute(
            "UPDATE security_lifecycle_assessments SET rule_version='0' "
            "WHERE assessment_id=?",
            (assessment_id,),
        )
        conn.commit()
        assert store.project_case_state(
            case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
        )["current_assessment"] is None

        conn.execute(
            "UPDATE security_lifecycle_assessments SET rule_version='1' "
            "WHERE assessment_id=?",
            (assessment_id,),
        )
        conn.execute(
            "UPDATE security_lifecycle_automation_facts "
            "SET extractor_rule_version='2' WHERE automation_run_id=?",
            (claim.run_id,),
        )
        conn.commit()
        state = store.project_case_state(
            case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
        )
        assert state["current_assessment"] is None
        assert state["assessment_history"][0]["stale"] is True
    finally:
        conn.close()


def test_proposal_specs_match_persisted_automatic_proposals(tmp_path):
    from src.security_lifecycle_investigation import derive_action_proposal_specs

    conn, store, case_id = _context(tmp_path)
    try:
        assessment_id = _draft(
            store,
            case_id,
            outcomes=("symbol_changed",),
            successor_ticker="EA2",
        )
        assessment = _accept(store, assessment_id)
        sources = ("manual_lists", "portfolio_open")
        specs = derive_action_proposal_specs(
            case={"ticker": "EA"},
            assessment=assessment,
            sources=sources,
        )
        persisted = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker={"EA": sources},
            at=_LATER,
        )["proposals"]

        assert [
            {
                "action_type": item["action_type"],
                "replacement_ticker": item["replacement_ticker"],
                "block_reason": item["block_reason"],
            }
            for item in persisted
        ] == list(specs)
    finally:
        conn.close()


def test_explicit_reopen_restores_active_review_without_deleting_history(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        _manual_evidence(store, case_id)
        acknowledgement_id = store.acknowledge_case(
            case_id=case_id,
            reason="evidence_insufficient",
            note="Investigated but unresolved.",
            author="human",
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_AT,
        )
        store.reopen_acknowledgement(acknowledgement_id, at=_LATER)
        state = store.project_case_state(
            case_id, observation_fingerprint_sha256=_FINGERPRINT
        )
        assert state["workflow_state"] == "evidence_ready"
        assert state["current_acknowledgement"] is None
        assert state["acknowledgement_history"][0]["reopened_at"] == _LATER
    finally:
        conn.close()


def test_failed_run_alone_cannot_acknowledge_a_case(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        run_id = store.create_investigation_run(
            case_id=case_id,
            trigger="attended_user",
            adapter="manual",
            query_plan=[],
            at=_AT,
        )
        store.start_investigation_run(run_id, at=_AT)
        store.fail_investigation_run(
            run_id,
            failure_code="adapter_unavailable",
            usage={},
            at=_LATER,
        )
        with pytest.raises(ValueError, match="investigation evidence"):
            store.acknowledge_case(
                case_id=case_id,
                reason="evidence_insufficient",
                note=None,
                author="human",
                observation_fingerprint_sha256=_FINGERPRINT,
                at=_LATER,
            )
    finally:
        conn.close()


def test_inconclusive_acknowledgement_leaves_no_assessment_or_proposal(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        _manual_evidence(store, case_id)
        store.acknowledge_case(
            case_id=case_id,
            reason="evidence_insufficient",
            note=None,
            author="human",
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_AT,
        )
        assert store.list_assessments(case_id) == []
        assert store.list_proposals(case_id) == []
        assert store.project_case_state(
            case_id, observation_fingerprint_sha256=_FINGERPRINT
        )["workflow_state"] == "reviewed_inconclusive"
    finally:
        conn.close()


def test_investigation_writes_are_confined_to_lifecycle_profile_tables(tmp_path):
    conn = sqlite3.connect(tmp_path / "profile_state.db")
    conn.execute("CREATE TABLE watchlists (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE ticker_meta (ticker TEXT PRIMARY KEY, hidden_at TEXT)")
    conn.execute("CREATE TABLE portfolio_positions (id INTEGER PRIMARY KEY, symbol TEXT)")
    conn.execute("INSERT INTO watchlists VALUES (1, 'Core')")
    conn.execute("INSERT INTO ticker_meta VALUES ('EA', NULL)")
    conn.execute("INSERT INTO portfolio_positions VALUES (1, 'EA')")
    conn.commit()
    protected_tables = ("portfolio_positions", "ticker_meta", "watchlists")
    before_non_lifecycle = {
        table: {
            "schema": conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()[0],
            "rows": [
                tuple(row)
                for row in conn.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                ).fetchall()
            ],
        }
        for table in protected_tables
    }
    try:
        from src.security_lifecycle_investigation import (
            SecurityLifecycleInvestigationStore,
        )

        store = SecurityLifecycleInvestigationStore(
            conn, id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}"
        )
        case_id = store.ensure_case(
            source="sec_edgar", source_ref="ref", ticker="EA", at=_AT
        )
        _manual_evidence(store, case_id)
        _accept(store, _draft(store, case_id))
        store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker={"EA": ("manual_lists",)},
            at=_LATER,
        )
        after_non_lifecycle = {
            table: {
                "schema": conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()[0],
                "rows": [
                    tuple(row)
                    for row in conn.execute(
                        f'SELECT * FROM "{table}" ORDER BY rowid'
                    ).fetchall()
                ],
            }
            for table in protected_tables
        }
        assert after_non_lifecycle == before_non_lifecycle
    finally:
        conn.close()


def test_issuer_related_assessment_proposes_notify_and_keep_tracking(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        assessment = _draft(
            store,
            case_id,
            relevance="issuer_related",
            outcomes=("issuer_security_change",),
        )
        _accept(store, assessment)
        result = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker={"EA": ("manual_lists",)},
            at=_LATER,
        )
        assert {item["action_type"] for item in result["proposals"]} == {
            "notify",
            "keep_tracking",
        }
        assert all(json.loads(item["source_snapshot_json"]) == ["manual_lists"] for item in result["proposals"])
    finally:
        conn.close()


def test_open_portfolio_position_keeps_safe_remap_and_requests_position_review(
    tmp_path,
):
    conn, store, case_id = _context(tmp_path)
    try:
        assessment = _draft(
            store,
            case_id,
            outcomes=("symbol_changed",),
            successor_ticker="EA2",
        )
        _accept(store, assessment)
        result = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker={"EA": ("manual_lists", "portfolio_open")},
            at=_LATER,
        )
        actions = {item["action_type"] for item in result["proposals"]}
        assert "review_portfolio_position" in actions
        assert "notify" in actions
        assert "hide_from_active_universe" not in actions
        assert "remap_symbol" in actions
        review = next(
            item
            for item in result["proposals"]
            if item["action_type"] == "review_portfolio_position"
        )
        assert review["block_reason"] == "portfolio_position_open"
    finally:
        conn.close()


def test_run_lifecycle_is_attended_and_uses_the_closed_status_vocabulary(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        with pytest.raises(ValueError, match="trigger"):
            store.create_investigation_run(
                case_id=case_id,
                trigger="scheduled",
                adapter="manual",
                query_plan=[],
                at=_AT,
            )
        with pytest.raises(ValueError, match="adapter"):
            store.create_investigation_run(
                case_id=case_id,
                trigger="attended_user",
                adapter="tavily",
                query_plan=[],
                at=_AT,
            )
        run_id = store.create_investigation_run(
            case_id=case_id,
            trigger="attended_user",
            adapter="manual",
            query_plan=[],
            at=_AT,
        )
        assert store.get_investigation_run(run_id)["status"] == "queued"
        store.start_investigation_run(run_id, at=_AT)
        store.succeed_investigation_run(
            run_id,
            result_count=0,
            fetch_count=0,
            usage={},
            at=_LATER,
        )
        assert store.get_investigation_run(run_id)["status"] == "succeeded"
        with pytest.raises(ValueError, match="terminal"):
            store.start_investigation_run(run_id, at=_LATER)
    finally:
        conn.close()


def test_stale_assessment_blocks_existing_and_new_proposals(tmp_path):
    from src.security_lifecycle_investigation import compose_security_lifecycle

    conn, store, case_id, market_path, profile_path, fingerprint = (
        _composed_context(tmp_path)
    )
    try:
        _accept(
            store,
            _draft(
                store,
                case_id,
                outcomes=("symbol_changed",),
                successor_ticker="EA2",
                fingerprint=fingerprint,
            ),
            fingerprint=fingerprint,
        )
        created = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=fingerprint,
            sources_by_ticker={"EA": ("manual_lists",)},
            at=_LATER,
        )
        assert created["proposals"]
        assert "remap_symbol" in {
            proposal["action_type"] for proposal in created["proposals"]
        }
        current = compose_security_lifecycle(str(market_path), str(profile_path))[
            "cases"
        ][0]
        assert current["workflow_state"] == "resolved"
        assert current["proposals"][0]["projected_block_reason"] is None

        _manual_evidence(store, case_id, excerpt="Later evidence changed the set.")
        stale = compose_security_lifecycle(str(market_path), str(profile_path))[
            "cases"
        ][0]
        assert stale["workflow_state"] == "evidence_ready"
        assert stale["current_assessment"] is None
        assert stale["assessment_history"][0]["stale"] is True
        assert stale["proposals"][0]["projected_block_reason"] == "stale_assessment"

        projected = store.project_proposals(
            case_id, observation_fingerprint_sha256=_CHANGED_FINGERPRINT
        )
        assert projected
        assert {item["projected_block_reason"] for item in projected} == {
            "stale_assessment"
        }
        blocked = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=fingerprint,
            sources_by_ticker={"EA": ("manual_lists",)},
            at=_LATER,
        )
        assert blocked == {"proposals": [], "block_reason": "stale_assessment"}
    finally:
        conn.close()


def test_operator_detail_is_a_closed_dto_and_rejects_unknown_codes(tmp_path):
    from src.security_lifecycle_fact_kernel import (
        AutomationBlocker,
        SecurityLifecycleFactKernel,
    )
    from src.security_lifecycle_investigation import (
        compose_security_lifecycle,
        project_automation_blocker,
    )
    from src.tools.security_lifecycle_tools import (
        project_active_security_lifecycle_case,
    )

    conn, store, case_id, market_path, profile_path, fingerprint = (
        _composed_context(tmp_path)
    )
    try:
        kernel = SecurityLifecycleFactKernel(store)
        claim = kernel.reserve_run(
            case_id=case_id,
            observation_fingerprint_sha256=fingerprint,
            policy_version="trusted-lifecycle-v1",
            mode="historical",
            execution_revision="trusted-lifecycle-execution-r1",
            execution_owner_id="test-operator-detail-owner",
            query_context={"case_id": case_id, "ticker": "EA"},
            diagnostics={"ibkr_requests": 0},
            at=_AT,
        )
        context = {
            "code": "candidate_budget_exceeded",
            "candidate_count": 9,
            "query_limit": 8,
            "internal_candidate_hash": "a" * 64,
            "internal_case_id": case_id,
            "future_key": {"must": "not escape"},
        }
        assert project_automation_blocker(
            {
                "blocker_code": "sec_rate_limited",
                "retryable": True,
                "context": context,
            }
        ) == {
            "blocker_code": "sec_rate_limited",
            "retryable": True,
        }
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=(),
            facts=(),
            blockers=(
                AutomationBlocker(
                    code="market_confirmation_missing",
                    retryable=True,
                    context=context,
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at="2026-08-21T00:00:00Z",
            diagnostics={"ibkr_requests": 0},
            at=_LATER,
        )

        internal_case = compose_security_lifecycle(
            str(market_path),
            str(profile_path),
        )["cases"][0]
        assert internal_case["automation_runs"][0]["blockers"][0]["context"] == (
            context
        )
        blocker = project_active_security_lifecycle_case(internal_case)[
            "automation_runs"
        ][0]["blockers"][0]
        assert blocker == {
            "blocker_code": "market_confirmation_missing",
            "retryable": True,
            "operator_detail": {
                "code": "candidate_budget_exceeded",
                "candidate_count": 9,
                "query_limit": 8,
                "provider_contacted": False,
            },
        }

        conn.execute(
            "UPDATE security_lifecycle_automation_run_blockers "
            "SET context_json=? WHERE automation_run_id=?",
            (
                json.dumps(
                    {
                        **context,
                        "code": "future_operator_detail",
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                claim.run_id,
            ),
        )
        conn.commit()

        rejected = project_active_security_lifecycle_case(
            compose_security_lifecycle(str(market_path), str(profile_path))["cases"][0]
        )["automation_runs"][0]["blockers"][0]
        assert rejected == {
            "blocker_code": "market_confirmation_missing",
            "retryable": True,
        }

        invalid_details = (
            {**context, "provider_contacted": True},
            {**context, "candidate_count": "9"},
            {**context, "query_limit": "8"},
        )
        for invalid_detail in invalid_details:
            conn.execute(
                "UPDATE security_lifecycle_automation_run_blockers "
                "SET context_json=? WHERE automation_run_id=?",
                (
                    json.dumps(
                        invalid_detail,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    claim.run_id,
                ),
            )
            conn.commit()
            rejected = project_active_security_lifecycle_case(
                compose_security_lifecycle(
                    str(market_path),
                    str(profile_path),
                )["cases"][0]
            )["automation_runs"][0]["blockers"][0]
            assert rejected == {
                "blocker_code": "market_confirmation_missing",
                "retryable": True,
            }
    finally:
        conn.close()


@pytest.mark.parametrize(
    "outcomes",
    [
        ("venue_transfer",),
        ("acquisition_stock",),
        ("acquisition_mixed",),
    ],
)
def test_non_continuation_outcomes_never_emit_symbol_remap(tmp_path, outcomes):
    conn, store, case_id = _context(tmp_path)
    try:
        assessment = _draft(
            store,
            case_id,
            outcomes=outcomes,
            successor_ticker="EA2",
        )
        _accept(store, assessment)
        result = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker={"EA": ("manual_lists",)},
            at=_LATER,
        )
        assert "remap_symbol" not in {
            item["action_type"] for item in result["proposals"]
        }
    finally:
        conn.close()


def test_same_symbol_venue_transfer_proposes_notify_and_keep_tracking(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        assessment = _draft(
            store,
            case_id,
            outcomes=("venue_transfer",),
            successor_ticker=None,
        )
        _accept(store, assessment)
        result = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker={"EA": ("manual_lists",)},
            at=_LATER,
        )
        assert {item["action_type"] for item in result["proposals"]} == {
            "keep_tracking",
            "notify",
        }
    finally:
        conn.close()


def test_successful_zero_result_run_can_support_inconclusive_acknowledgement(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        run_id = store.create_investigation_run(
            case_id=case_id,
            trigger="attended_user",
            adapter="manual",
            query_plan=[],
            at=_AT,
        )
        store.start_investigation_run(run_id, at=_AT)
        store.succeed_investigation_run(
            run_id,
            result_count=0,
            fetch_count=0,
            usage={},
            at=_LATER,
        )
        acknowledgement_id = store.acknowledge_case(
            case_id=case_id,
            reason="evidence_insufficient",
            note="No public result found.",
            author="human",
            observation_fingerprint_sha256=_FINGERPRINT,
            at=_LATER,
        )
        assert acknowledgement_id.startswith("slk_")
    finally:
        conn.close()


def test_unrelated_assessment_proposes_no_action_without_profile_mutation(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        sources = {"EA": ("manual_lists", "sa_alpha_picks_current")}
        assessment = _draft(
            store,
            case_id,
            relevance="unrelated",
            outcomes=("no_tracked_security_change",),
        )
        _accept(store, assessment)
        result = store.generate_action_proposals(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            sources_by_ticker=sources,
            at=_LATER,
        )
        assert [item["action_type"] for item in result["proposals"]] == ["no_action"]
        dismissed = store.dismiss_proposal(
            result["proposals"][0]["proposal_id"],
            at=_LATER,
        )
        assert dismissed["status"] == "dismissed"
        assert dismissed["dismissed_at"] == _LATER
        with pytest.raises(ValueError, match="proposal_not_proposed"):
            store.dismiss_proposal(dismissed["proposal_id"], at=_LATER)
        assert sources == {"EA": ("manual_lists", "sa_alpha_picks_current")}
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_action_proposals").fetchone()[0] == 1
    finally:
        conn.close()
