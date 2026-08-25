from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest


_AT = "2026-08-25T01:00:00Z"
_LATER = "2026-08-25T02:00:00Z"
_FINGERPRINT = "a" * 64


def _context():
    from src.security_lifecycle_fact_kernel import SecurityLifecycleFactKernel
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore

    conn = sqlite3.connect(":memory:")
    store = SecurityLifecycleInvestigationStore(
        conn,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0001409970-26-000131",
        ticker="HAPN",
        at=_AT,
    )
    return conn, store, SecurityLifecycleFactKernel(store), case_id


def _reserve(kernel, case_id, **overrides):
    values = {
        "case_id": case_id,
        "observation_fingerprint_sha256": _FINGERPRINT,
        "policy_version": "trusted-lifecycle-v1",
        "mode": "historical",
        "query_context": {
            "case_id": case_id,
            "cik": "0001409970",
            "aliases": ["HAPN", "LC"],
        },
        "diagnostics": {"sec_attempts": 0, "sec_documents": 0},
        "at": _AT,
    }
    values.update(overrides)
    return kernel.reserve_run(**values)


def _evidence(
    suffix="a",
    *,
    excerpt="The issuer will change its ticker symbol from LC to HAPN.",
    family="regulator",
    adapter="sec_edgar",
    kind="regulator_excerpt",
):
    from src.security_lifecycle_fact_kernel import AutomationEvidence

    return AutomationEvidence(
        evidence_id=f"source-{suffix}",
        source_family=family,
        adapter=adapter,
        kind=kind,
        source_url=(
            f"https://www.sec.gov/Archives/{suffix}.htm"
            if adapter == "sec_edgar"
            else f"https://news.example/{suffix}"
        ),
        title=f"Evidence {suffix}",
        publisher="SEC EDGAR" if adapter == "sec_edgar" else "Reuters",
        domain="sec.gov" if adapter == "sec_edgar" else "news.example",
        source_published_at="2026-06-27",
        retrieved_at=_AT,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        source_document_sha256=("d" * 64 if adapter == "sec_edgar" else None),
        source_locator={"accession": f"accession-{suffix}"},
        evidence_dedupe_key=f"source:{suffix}",
    )


def _fact(evidence, value="HAPN", *, rule_version="1"):
    from src.security_lifecycle_fact_kernel import AutomationFact

    cited = value
    encoded = evidence.excerpt.encode()
    start = encoded.index(cited.encode())
    return AutomationFact(
        evidence_id=evidence.evidence_id,
        fact_type="successor_ticker",
        normalized_value=value,
        source_span_start=start,
        source_span_end=start + len(cited.encode()),
        cited_text_sha256=hashlib.sha256(cited.encode()).hexdigest(),
        extractor_rule_id="sec.symbol_change",
        extractor_rule_version=rule_version,
    )


def _succeed(kernel, claim, *, evidence=(), facts=(), diagnostics=None):
    return kernel.complete_run(
        run_id=claim.run_id,
        evidence=evidence,
        facts=facts,
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics=diagnostics or {"sec_attempts": 1},
        at=_LATER,
    )


def test_automation_run_key_binds_case_observation_policy_and_mode():
    from src.security_lifecycle_fact_kernel import AutomationBlocker, automation_run_key

    base = automation_run_key(
        case_id="case-a",
        observation_fingerprint_sha256="a" * 64,
        policy_version="policy-1",
        mode="live",
        input_evidence_set_sha256="0" * 64,
    )
    variants = {
        automation_run_key(
            case_id=case_id,
            observation_fingerprint_sha256=fingerprint,
            policy_version=policy,
            mode=mode,
            input_evidence_set_sha256=evidence_digest,
        )
        for case_id, fingerprint, policy, mode, evidence_digest in (
            ("case-b", "a" * 64, "policy-1", "live", "0" * 64),
            ("case-a", "b" * 64, "policy-1", "live", "0" * 64),
            ("case-a", "a" * 64, "policy-2", "live", "0" * 64),
            ("case-a", "a" * 64, "policy-1", "historical", "0" * 64),
            ("case-a", "a" * 64, "policy-1", "live", "1" * 64),
        )
    }
    assert base.startswith("lifecycle-automation-v1:")
    assert base not in variants
    assert len(variants) == 5

    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    assert claim.should_execute is True
    assert _reserve(kernel, case_id).should_execute is False
    blocked = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(),
        facts=(),
        blockers=(
            AutomationBlocker(
                code="ibkr_gateway_unavailable",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-08-25T03:00:00Z",
        diagnostics={"ibkr_requests": 1},
        at=_LATER,
    )
    assert blocked.status == "blocked"
    assert _reserve(kernel, case_id, at="2026-08-25T02:59:59Z").should_execute is False
    retry = _reserve(kernel, case_id, at="2026-08-25T03:00:00Z")
    assert retry.should_execute is True
    assert retry.run_id == claim.run_id
    assert store.get_automation_run(retry.run_id)["status"] == "running"


def test_evidence_and_facts_persist_atomically_or_not_at_all():
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()
    fact = _fact(evidence)
    conn.execute(
        "CREATE TRIGGER reject_automation_fact BEFORE INSERT ON "
        "security_lifecycle_automation_facts BEGIN SELECT RAISE(ABORT,'fault'); END"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="fault"):
        _succeed(kernel, claim, evidence=(evidence,), facts=(fact,))
    assert conn.execute("SELECT count(*) FROM security_lifecycle_evidence").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM security_lifecycle_automation_facts").fetchone()[0] == 0
    assert store.get_automation_run(claim.run_id)["status"] == "running"

    conn.execute("DROP TRIGGER reject_automation_fact")
    conn.commit()
    result = _succeed(kernel, claim, evidence=(evidence,), facts=(fact,))
    assert result.status == "succeeded"
    assert conn.execute("SELECT count(*) FROM security_lifecycle_evidence").fetchone()[0] == 1
    fact_row = conn.execute(
        "SELECT evidence_id,normalized_value_json FROM security_lifecycle_automation_facts"
    ).fetchone()
    evidence_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_evidence"
    ).fetchone()[0]
    assert tuple(fact_row) == (evidence_id, '"HAPN"')


def test_fact_span_and_cited_text_hash_must_match_verbatim_evidence():
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()
    fact = _fact(evidence)

    for invalid in (
        replace(fact, source_span_end=len(evidence.excerpt.encode()) + 1),
        replace(fact, cited_text_sha256="0" * 64),
    ):
        with pytest.raises(ValueError, match="fact_citation"):
            _succeed(kernel, claim, evidence=(evidence,), facts=(invalid,))
        assert conn.execute("SELECT count(*) FROM security_lifecycle_evidence").fetchone()[0] == 0
        assert store.get_automation_run(claim.run_id)["status"] == "running"


def test_each_fact_type_enforces_its_closed_value_shape_before_persistence():
    scalar_types = {
        "source_ticker",
        "successor_ticker",
        "source_venue",
        "destination_venue",
        "effective_date",
        "security_class",
        "issuer_cik",
        "tracked_security_effect",
    }
    invalid_values = [
        ("transaction_structure", "asset_acquisition"),
        *((fact_type, {"unexpected": "mapping"}) for fact_type in scalar_types),
    ]
    for fact_type, value in invalid_values:
        conn, _store, kernel, case_id = _context()
        try:
            claim = _reserve(kernel, case_id)
            evidence = _evidence()
            fact = replace(
                _fact(evidence),
                fact_type=fact_type,
                normalized_value=value,
            )
            with pytest.raises(ValueError, match="fact_value_shape"):
                _succeed(kernel, claim, evidence=(evidence,), facts=(fact,))
            assert conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_evidence"
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT COUNT(*) FROM security_lifecycle_automation_facts"
            ).fetchone()[0] == 0
        finally:
            conn.close()


def test_conflicting_current_facts_are_typed_and_never_majority_resolved():
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    first = _evidence("first")
    second = _evidence(
        "second",
        excerpt="The issuer will instead use ticker symbol OTHER.",
    )
    first_fact = _fact(first, "HAPN")
    second_fact = _fact(second, "OTHER")
    second_start = second.excerpt.encode().index(b"OTHER")
    second_fact = replace(
        second_fact,
        source_span_start=second_start,
        source_span_end=second_start + len(b"OTHER"),
        cited_text_sha256=hashlib.sha256(b"OTHER").hexdigest(),
    )

    result = _succeed(
        kernel,
        claim,
        evidence=(first, second),
        facts=(first_fact, second_fact),
    )

    assert result.status == "succeeded"
    assert result.decision_tier == "review_suggested"
    assert result.action_readiness == "action_blocked"
    assert result.conflicts == {"successor_ticker": ('"HAPN"', '"OTHER"')}
    row = store.get_automation_run(claim.run_id)
    assert row["decision_tier"] == "review_suggested"
    assert row["action_readiness"] == "action_blocked"
    assert [item["blocker_code"] for item in row["blockers"]] == ["source_conflict"]


def test_persisted_decision_provenance_recomputes_from_database_rows():
    from src.security_lifecycle_fact_kernel import (
        persisted_decision_provenance_sha256,
    )

    conn, _store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()
    fact = _fact(evidence)

    result = _succeed(kernel, claim, evidence=(evidence,), facts=(fact,))

    assert persisted_decision_provenance_sha256(conn, claim.run_id) == (
        result.decision_provenance_sha256
    )
    conn.execute(
        "UPDATE security_lifecycle_automation_facts "
        "SET extractor_rule_version='2' WHERE automation_run_id=?",
        (claim.run_id,),
    )
    conn.commit()
    assert persisted_decision_provenance_sha256(
        conn, claim.run_id
    ) != result.decision_provenance_sha256


def test_readiness_recheck_preserves_cited_history_and_recomputes_provenance():
    from src.security_lifecycle_fact_kernel import AutomationEvidence, AutomationFact

    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    regulator = _evidence()
    regulator_fact = _fact(regulator)
    first = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(regulator,),
        facts=(regulator_fact,),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    persisted_regulator_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_evidence "
        "WHERE automation_run_id=?",
        (claim.run_id,),
    ).fetchone()[0]
    assessment_id = store.create_assessment(
        case_id=case_id,
        relevance="direct_tracked_security",
        confidence="high",
        author="human",
        conclusion="The symbol will change.",
        impact_summary="Wait for the effective date.",
        outcomes=("symbol_changed",),
        citations=(
            {
                "reference_kind": "observation",
                "cited_content_sha256": _FINGERPRINT,
            },
            {"reference_kind": "evidence", "evidence_id": persisted_regulator_id},
        ),
        observation_fingerprint_sha256=_FINGERPRINT,
        successor_ticker="HAPN",
        effective_date="2026-08-26",
        at=_LATER,
    )

    assert kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-25T23:59:59Z",
    ).should_execute is False
    recheck = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-26T00:00:00Z",
    )
    assert recheck.should_execute is True
    assert store.get_assessment(assessment_id)["citations"][1]["evidence_id"] == (
        persisted_regulator_id
    )

    excerpt = '{"primaryExchange":"NASDAQ","secType":"STK","symbol":"HAPN"}'
    market = AutomationEvidence(
        evidence_id="market-a",
        source_family="market_infrastructure",
        adapter="ibkr_contract",
        kind="market_infrastructure_snapshot",
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        retrieved_at="2026-08-26T00:00:00Z",
        source_locator={"snapshot_kind": "contract"},
        evidence_dedupe_key="market:a",
    )
    start = excerpt.encode().index(b"HAPN")
    market_fact = AutomationFact(
        evidence_id=market.evidence_id,
        fact_type="successor_ticker",
        normalized_value="HAPN",
        source_span_start=start,
        source_span_end=start + len(b"HAPN"),
        cited_text_sha256=hashlib.sha256(b"HAPN").hexdigest(),
        extractor_rule_id="ibkr.contract_symbol",
        extractor_rule_version="1",
    )
    second = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(market,),
        facts=(market_fact,),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics={"ibkr_requests": 1},
        at="2026-08-26T00:01:00Z",
    )

    assert second.evidence_count == 2
    assert second.fact_count == 2
    assert second.decision_provenance_sha256 != first.decision_provenance_sha256
    assert conn.execute(
        "SELECT count(*) FROM security_lifecycle_assessment_evidence "
        "WHERE assessment_id=?",
        (assessment_id,),
    ).fetchone()[0] == 2


def test_source_family_set_is_derived_from_evidence_not_article_count():
    _conn, _store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    regulator = _evidence("regulator")
    publisher_a = _evidence(
        "publisher-a",
        family="publisher",
        adapter="internal_news",
        kind="publisher_excerpt",
    )
    publisher_b = _evidence(
        "publisher-b",
        family="publisher",
        adapter="internal_news",
        kind="publisher_excerpt",
    )

    result = _succeed(
        kernel,
        claim,
        evidence=(regulator, publisher_a, publisher_b),
        facts=(_fact(regulator),),
    )

    assert result.source_families == ("publisher", "regulator")
    assert result.corroboration_family_count == 2
    assert result.evidence_count == 3


def test_changed_observation_evidence_or_rule_version_changes_provenance():
    from src.security_lifecycle_fact_kernel import decision_provenance_sha256

    evidence = _evidence()
    fact = _fact(evidence)
    arguments = {
        "case_id": "case-a",
        "observation_fingerprint_sha256": "a" * 64,
        "policy_version": "policy-1",
        "mode": "historical",
        "evidence": (evidence,),
        "facts": (fact,),
    }
    base = decision_provenance_sha256(**arguments)
    changed_excerpt = replace(
        evidence,
        excerpt=evidence.excerpt + " Updated.",
        content_sha256=hashlib.sha256((evidence.excerpt + " Updated.").encode()).hexdigest(),
    )
    variants = {
        decision_provenance_sha256(
            **{**arguments, "observation_fingerprint_sha256": "b" * 64}
        ),
        decision_provenance_sha256(**{**arguments, "evidence": (changed_excerpt,)}),
        decision_provenance_sha256(
            **{**arguments, "facts": (replace(fact, extractor_rule_version="2"),)}
        ),
    }
    assert base not in variants
    assert len(variants) == 3

    _conn, store, kernel, case_id = _context()
    first = _reserve(kernel, case_id)
    _succeed(kernel, first, evidence=(evidence,), facts=(fact,))
    second = _reserve(
        kernel,
        case_id,
        observation_fingerprint_sha256="b" * 64,
        at="2026-08-25T03:00:00Z",
    )
    _succeed(kernel, second, evidence=(evidence,), facts=(fact,))
    assert second.run_id != first.run_id
    assert [row["run_id"] for row in store.list_automation_runs(case_id)] == [
        second.run_id,
        first.run_id,
    ]


def test_expected_provider_conditions_block_while_program_errors_do_not_masquerade():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    provider = _reserve(kernel, case_id)
    result = kernel.complete_run(
        run_id=provider.run_id,
        evidence=(),
        facts=(),
        blockers=(
            AutomationBlocker(
                code="sec_transport_unavailable",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-08-25T04:00:00Z",
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    assert result.status == "blocked"
    assert store.get_automation_run(provider.run_id)["failure_code"] is None

    program = _reserve(kernel, case_id, policy_version="trusted-lifecycle-v2")
    bad = replace(_evidence(), adapter="unknown")
    with pytest.raises(ValueError, match="evidence_adapter"):
        _succeed(kernel, program, evidence=(bad,))
    assert store.get_automation_run(program.run_id)["status"] == "running"
    failed = kernel.fail_run(
        run_id=program.run_id,
        failure_code="internal_error",
        diagnostics={"sec_attempts": 0},
        at=_LATER,
    )
    assert failed["status"] == "failed"
    assert failed["failure_code"] == "internal_error"
    assert failed["blockers"] == []


def test_query_context_and_diagnostics_are_canonical_bounded_and_secret_safe():
    _conn, store, kernel, case_id = _context()
    claim = _reserve(
        kernel,
        case_id,
        query_context={"z": [2, 1], "a": {"ticker": "HAPN"}},
        diagnostics={"sec_documents": 2, "sec_attempts": 3},
    )
    row = store.get_automation_run(claim.run_id)
    assert row["query_context_json"] == (
        '{"a":{"ticker":"HAPN"},'
        '"input_evidence_set_sha256":'
        '"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",'
        '"z":[2,1]}'
    )
    assert row["diagnostics_json"] == '{"sec_attempts":3,"sec_documents":2}'

    for query_context, diagnostics in (
        ({"api_key": "secret"}, {}),
        ({"ticker": "HAPN\0"}, {}),
        ({"notes": "x" * 17000}, {}),
        ({"input_evidence_set_sha256": "1" * 64}, {}),
        ({}, {"source_url": 1}),
        ({}, {"sec_attempts": "1"}),
    ):
        with pytest.raises(ValueError):
            _reserve(
                kernel,
                case_id,
                policy_version=hashlib.sha256(
                    repr((query_context, diagnostics)).encode()
                ).hexdigest()[:20],
                query_context=query_context,
                diagnostics=diagnostics,
            )
