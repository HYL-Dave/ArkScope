from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from dataclasses import replace

import pytest


_AT = "2026-08-25T01:00:00Z"
_LATER = "2026-08-25T02:00:00Z"
_FINGERPRINT = "a" * 64
_LISTING_AT = "2026-08-28T22:00:00Z"
_LISTING_LATER = "2026-08-28T23:00:00Z"
_LISTING_FIXTURES = Path(__file__).parent / "fixtures" / "listing_authority"


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
        "execution_revision": "trusted-lifecycle-execution-r1",
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


def _deadline_owner(*, at="2026-08-27T00:00:00Z", excerpt_prefix=""):
    from src.security_lifecycle_sec_evidence import SecSourceDeadline
    from src.service import security_lifecycle_automation_scheduler as scheduler

    cited_text = (
        "HAPN merger agreement may be terminated if the merger is not "
        "consummated by May 7, 2026."
    )
    excerpt = excerpt_prefix + cited_text
    evidence = _evidence("deadline", excerpt=excerpt)
    encoded = excerpt.encode("utf-8")
    cited = cited_text.encode("utf-8")
    start = encoded.index(cited)
    deadline = SecSourceDeadline(
        date="2026-05-07",
        evidence_id=evidence.evidence_id,
        span_start_byte=start,
        span_end_byte=start + len(cited),
        cited_text=cited_text,
        cited_text_sha256=hashlib.sha256(cited).hexdigest(),
        rule_id="sec.explicit_transaction_termination_date",
        rule_version="4",
    )
    blocker = scheduler._pending_event_monitoring(
        {
            "observation": {
                "kinds": [
                    {"event_type": "merger_agreement", "effective_date": None}
                ]
            }
        },
        (),
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "publisher": "available",
        },
        source_deadlines=(deadline,),
        at=at,
    )
    assert blocker is not None
    return evidence, blocker


def _cut_inside_multibyte_source_character(context):
    invalid_byte = "é".encode("utf-8")[1:2]
    context["source_deadline_span_start_byte"] = 1
    context["source_deadline_span_end_byte"] = 2
    context["source_deadline_cited_text_sha256"] = hashlib.sha256(
        invalid_byte
    ).hexdigest()


_BLOCKER_CITATION_MUTATIONS = {
    "partial_set": lambda c: c.pop("source_deadline_span_end_byte"),
    "missing_evidence": lambda c: c.__setitem__(
        "source_deadline_evidence_id", "missing"
    ),
    "out_of_range": lambda c: c.__setitem__(
        "source_deadline_span_end_byte", 999999
    ),
    "utf8_boundary": _cut_inside_multibyte_source_character,
    "forged_hash": lambda c: c.__setitem__(
        "source_deadline_cited_text_sha256", "f" * 64
    ),
    "wrong_rule_id": lambda c: c.__setitem__("source_deadline_rule_id", "sec.other"),
    "wrong_rule_version": lambda c: c.__setitem__(
        "source_deadline_rule_version", "3"
    ),
}


def _succeed(kernel, claim, *, evidence=(), facts=(), diagnostics=None, at=_LATER):
    return kernel.complete_run(
        run_id=claim.run_id,
        evidence=evidence,
        facts=facts,
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics=diagnostics or {"sec_attempts": 1},
        at=at,
    )


class _ListingProducerTransport:
    def __init__(self, adapter: str) -> None:
        self.adapter = adapter

    @staticmethod
    def _payload(source_url, body, content_type):
        from data_sources.listing_authority_transport import ListingHttpPayload

        return ListingHttpPayload(
            source_url=source_url,
            retrieved_at=_LISTING_AT,
            status_code=200,
            content_type=content_type,
            body=body,
        )

    def fetch_nasdaq(self, source_url, *, budget):
        from data_sources.listing_authority_transport import (
            NASDAQ_LISTED_URL,
            ListingTransportFailure,
        )

        if self.adapter == "massive_reference":
            raise ListingTransportFailure("nasdaq_transport_unavailable")
        budget.reserve_nasdaq_request(source_url)
        name = "nasdaqlisted.txt" if source_url == NASDAQ_LISTED_URL else "otherlisted.txt"
        body = (_LISTING_FIXTURES / name).read_bytes()
        budget.record_nasdaq_body(len(body))
        return self._payload(source_url, body, "text/plain")

    def fetch_massive_ticker(
        self, ticker, *, expected_active, market, api_key, budget
    ):
        from data_sources.listing_authority_transport import MASSIVE_TICKERS_URL

        del api_key
        budget.reserve_massive_request((ticker, expected_active, market))
        payload = json.loads((_LISTING_FIXTURES / "massive-active.json").read_bytes())
        payload["results"][0]["ticker"] = ticker
        body = json.dumps(payload, separators=(",", ":")).encode()
        budget.record_massive_body(len(body))
        source_url = (
            f"{MASSIVE_TICKERS_URL}?ticker={ticker}&active=true"
            f"&market={market}&limit=2"
        )
        return self._payload(source_url, body, "application/json")

    @staticmethod
    def diagnostics(budget):
        return budget.diagnostics()

    @staticmethod
    def close():
        return None


def _listing_producer_result(adapter: str):
    from data_sources.listing_authority_transport import ListingRequestBudget
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession
    from src.security_lifecycle_sec_evidence import IdentityContext

    session = ListingAuthoritySession(
        transport=_ListingProducerTransport(adapter),
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=_LISTING_AT,
        massive_api_key="fixture-key",
    )
    try:
        result = session.lookup(
            context=IdentityContext(
                case_id="slc_listing",
                cik="0000320193",
                issuer_name="Fixture Issuer",
                current_ticker="HAPN",
                ticker_aliases=("HAPN",),
                ibkr_conids=(),
                filing_date="2026-08-28",
                accession="0000320193-26-000001",
                filing_form="8-K",
                filing_items=("8.01",),
                event_kinds=("symbol_change",),
                primary_start="2026-07-29",
                primary_end="2026-10-12",
                widened_start="2026-04-30",
                widened_end="2026-12-26",
            ),
            candidate_tickers=("AAPL",),
            require_explicit_inactive=False,
        )
    finally:
        session.close()
    assert len(result.evidence) == 1
    assert result.evidence[0].adapter == adapter
    assert result.facts
    return result.evidence, result.facts


@pytest.mark.parametrize(
    "adapter", ("nasdaq_symbol_directory", "massive_reference")
)
def test_listing_adapter_output_is_accepted_by_real_fact_kernel(adapter):
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at=_LISTING_AT)
    evidence, facts = _listing_producer_result(adapter)

    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=evidence,
        facts=facts,
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics={"listing_records": len(evidence)},
        at=_LISTING_LATER,
    )

    assert result.status == "succeeded"
    assert conn.execute(
        "SELECT COUNT(*) FROM security_lifecycle_evidence "
        "WHERE automation_run_id=? AND adapter=?",
        (claim.run_id, adapter),
    ).fetchone()[0] == 1
    persisted = conn.execute(
        "SELECT source_locator_json FROM security_lifecycle_evidence "
        "WHERE automation_run_id=? AND adapter=?",
        (claim.run_id, adapter),
    ).fetchone()
    assert json.loads(persisted[0])["candidate_ticker"] == "AAPL"


def test_listing_facts_share_sec_and_ibkr_identity_vocabulary_in_real_kernel():
    from src.security_lifecycle_fact_kernel import AutomationFact

    conn, _store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at=_LISTING_AT)
    listing_evidence, listing_facts = _listing_producer_result("massive_reference")
    sec_evidence = _evidence(
        "listing-compatible",
        excerpt="AAPL continues as common_stock on NASDAQ.",
    )

    def sec_fact(fact_type: str, value: str) -> AutomationFact:
        encoded = sec_evidence.excerpt.encode()
        cited = value.encode()
        start = encoded.index(cited)
        return AutomationFact(
            evidence_id=sec_evidence.evidence_id,
            fact_type=fact_type,
            normalized_value=value,
            source_span_start=start,
            source_span_end=start + len(cited),
            cited_text_sha256=hashlib.sha256(cited).hexdigest(),
            extractor_rule_id=f"sec.fixture.{fact_type}",
            extractor_rule_version="1",
        )

    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(sec_evidence, *listing_evidence),
        facts=(
            sec_fact("successor_ticker", "AAPL"),
            sec_fact("security_class", "common_stock"),
            sec_fact("destination_venue", "NASDAQ"),
            *listing_facts,
        ),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics={"listing_records": 1},
        at=_LISTING_LATER,
    )

    assert result.conflicts == {}
    assert result.decision_tier == "verified_automatic"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        ("excerpt", "evidence_content_sha256"),
        ("span", "fact_citation"),
    ),
)
def test_listing_producer_mutations_fail_at_real_kernel_validator(mutation, expected):
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at=_LISTING_AT)
    evidence, facts = _listing_producer_result("massive_reference")
    if mutation == "excerpt":
        evidence = (
            replace(
                evidence[0],
                excerpt=evidence[0].excerpt.replace('"AAPL"', '"AAPX"', 1),
            ),
        )
    else:
        facts = (
            replace(facts[0], source_span_end=facts[0].source_span_end - 1),
            *facts[1:],
        )

    with pytest.raises(ValueError, match=f"^{expected}$"):
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=evidence,
            facts=facts,
            blockers=(),
            decision_tier="verified_automatic",
            action_readiness="transition_eligible",
            retry_at=None,
            diagnostics={"listing_records": 1},
            at=_LISTING_LATER,
        )

    assert store.get_automation_run(claim.run_id)["status"] == "running"
    assert conn.execute(
        "SELECT COUNT(*) FROM security_lifecycle_evidence WHERE automation_run_id=?",
        (claim.run_id,),
    ).fetchone()[0] == 0


@pytest.mark.parametrize(
    ("at", "expected_reason", "retry_at"),
    [
        (
            "2026-05-01T00:00:00Z",
            "event_completion_not_confirmed",
            "2026-05-08T00:00:00Z",
        ),
        ("2026-08-27T00:00:00Z", "not_confirmed_as_of", None),
    ],
)
def test_producer_deadline_citation_crosses_real_kernel(
    at, expected_reason, retry_at
):
    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at=at)
    sec_evidence, scheduler_blocker = _deadline_owner(at=at)

    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(sec_evidence,),
        facts=(),
        blockers=(scheduler_blocker,),
        decision_tier=None,
        action_readiness=None,
        retry_at=retry_at,
        diagnostics={"sec_attempts": 1},
        at=at,
    )

    stored = store.get_automation_run(result.run_id)["blockers"][0]
    stored_context = json.loads(stored["context_json"])
    assert stored_context["monitoring_reason"] == expected_reason
    expected_evidence_id = "sle_" + hashlib.sha256(
        f"{claim.run_id}\0{sec_evidence.evidence_id}\0{sec_evidence.content_sha256}".encode()
    ).hexdigest()[:32]
    assert stored_context["source_deadline_evidence_id"] == expected_evidence_id
    assert scheduler_blocker.context["source_deadline_evidence_id"] == (
        sec_evidence.evidence_id
    )


@pytest.mark.parametrize(
    ("mutation_name", "mutate"),
    tuple(_BLOCKER_CITATION_MUTATIONS.items()),
    ids=tuple(_BLOCKER_CITATION_MUTATIONS),
)
def test_blocker_citation_mutations_fail_atomically(mutation_name, mutate):
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at="2026-08-27T00:00:00Z")
    prefix = "é" if mutation_name == "utf8_boundary" else ""
    evidence, blocker = _deadline_owner(excerpt_prefix=prefix)
    context = dict(blocker.context)
    mutate(context)
    forged = replace(blocker, context=context)

    before = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "security_lifecycle_evidence",
            "security_lifecycle_automation_facts",
            "security_lifecycle_automation_run_blockers",
        )
    }
    with pytest.raises(ValueError) as exc_info:
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=(evidence,),
            facts=(_fact(evidence),),
            blockers=(forged,),
            decision_tier=None,
            action_readiness=None,
            retry_at=None,
            diagnostics={"sec_attempts": 1},
            at="2026-08-27T00:00:00Z",
        )

    assert str(exc_info.value) == "blocker_citation"
    assert store.get_automation_run(claim.run_id)["status"] == "running"
    assert {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    } == before


def test_blocker_citation_rejects_evidence_owned_by_another_run_atomically():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    conn, store, kernel, case_id = _context()
    evidence, producer_blocker = _deadline_owner()
    owner = _reserve(kernel, case_id, at="2026-08-27T00:00:00Z")
    kernel.complete_run(
        run_id=owner.run_id,
        evidence=(evidence,),
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
        retry_at="2026-08-28T00:00:00Z",
        diagnostics={"sec_attempts": 1},
        at="2026-08-27T00:00:00Z",
    )
    persisted_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_evidence "
        "WHERE automation_run_id=?",
        (owner.run_id,),
    ).fetchone()[0]

    claimant = _reserve(
        kernel,
        case_id,
        observation_fingerprint_sha256="b" * 64,
        at="2026-08-27T00:00:00Z",
    )
    context = dict(producer_blocker.context)
    context["source_deadline_evidence_id"] = persisted_id
    cross_run = replace(producer_blocker, context=context)
    before = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "security_lifecycle_evidence",
            "security_lifecycle_automation_facts",
            "security_lifecycle_automation_run_blockers",
        )
    }

    with pytest.raises(ValueError) as exc_info:
        kernel.complete_run(
            run_id=claimant.run_id,
            evidence=(),
            facts=(),
            blockers=(cross_run,),
            decision_tier=None,
            action_readiness=None,
            retry_at=None,
            diagnostics={"sec_attempts": 1},
            at="2026-08-27T00:00:00Z",
        )

    assert str(exc_info.value) == "blocker_citation"
    assert store.get_automation_run(claimant.run_id)["status"] == "running"
    assert {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    } == before


def test_blocker_citation_resolves_existing_evidence_owned_by_same_run():
    conn, store, kernel, case_id = _context()
    evidence, producer_blocker = _deadline_owner()
    claim = _reserve(kernel, case_id, at="2026-08-27T00:00:00Z")
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at="2026-08-27T00:00:00Z",
    )
    persisted_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_evidence "
        "WHERE automation_run_id=?",
        (claim.run_id,),
    ).fetchone()[0]
    retry = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-28T00:00:00Z",
        at="2026-08-28T00:00:00Z",
    )
    assert retry.run_id == claim.run_id
    context = dict(producer_blocker.context)
    context["source_deadline_evidence_id"] = persisted_id

    result = kernel.complete_run(
        run_id=retry.run_id,
        evidence=(),
        facts=(),
        blockers=(replace(producer_blocker, context=context),),
        decision_tier=None,
        action_readiness=None,
        retry_at=None,
        diagnostics={"sec_attempts": 2},
        at="2026-08-28T00:00:00Z",
    )

    assert result.status == "blocked"
    stored_context = json.loads(
        store.get_automation_run(retry.run_id)["blockers"][0]["context_json"]
    )
    assert stored_context["source_deadline_evidence_id"] == persisted_id


@pytest.mark.parametrize(
    "mutate",
    (
        lambda context: context.__setitem__("source_deadline", "2026-5-7"),
        lambda context: context.pop("as_of"),
        lambda context: context.__setitem__("as_of", "2026-5-7"),
    ),
    ids=("source_deadline_not_iso", "missing_final_as_of", "final_as_of_not_iso"),
)
def test_blocker_citation_requires_canonical_deadline_dates(mutate):
    _conn, store, kernel, case_id = _context()
    evidence, blocker = _deadline_owner()
    claim = _reserve(kernel, case_id, at="2026-08-27T00:00:00Z")
    context = dict(blocker.context)
    mutate(context)

    with pytest.raises(ValueError) as exc_info:
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=(evidence,),
            facts=(),
            blockers=(replace(blocker, context=context),),
            decision_tier=None,
            action_readiness=None,
            retry_at=None,
            diagnostics={"sec_attempts": 1},
            at="2026-08-27T00:00:00Z",
        )

    assert str(exc_info.value) == "blocker_citation"
    assert store.get_automation_run(claim.run_id)["status"] == "running"


def test_blocker_citation_free_event_monitoring_remains_valid():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at="2026-08-27T00:00:00Z")
    blocker = scheduler._pending_event_monitoring(
        {
            "observation": {
                "kinds": [
                    {"event_type": "merger_agreement", "effective_date": None}
                ]
            }
        },
        (),
        source_family_results={},
        source_deadlines=(),
        at="2026-08-27T00:00:00Z",
    )
    assert blocker is not None

    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(),
        facts=(),
        blockers=(blocker,),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-09-03T00:00:00Z",
        diagnostics={"sec_attempts": 1},
        at="2026-08-27T00:00:00Z",
    )

    assert result.status == "blocked"
    assert json.loads(store.get_automation_run(claim.run_id)["blockers"][0]["context_json"]) == {
        "monitoring_reason": "event_completion_not_confirmed",
        "next_check_at": "2026-09-03T00:00:00Z",
    }


def test_blocker_citation_any_deadline_field_triggers_complete_set_before_deadline():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at="2026-05-01T00:00:00Z")

    with pytest.raises(ValueError) as exc_info:
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=(),
            facts=(),
            blockers=(
                AutomationBlocker(
                    code="sec_evidence_insufficient",
                    retryable=True,
                    context={
                        "monitoring_reason": "event_completion_not_confirmed",
                        "next_check_at": "2026-05-08T00:00:00Z",
                        "source_deadline": "2026-05-07",
                    },
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at="2026-05-08T00:00:00Z",
            diagnostics={"sec_attempts": 1},
            at="2026-05-01T00:00:00Z",
        )

    assert str(exc_info.value) == "blocker_citation"
    assert store.get_automation_run(claim.run_id)["status"] == "running"


def test_blocker_citation_final_reason_requires_complete_deadline_set():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at="2026-08-27T00:00:00Z")

    with pytest.raises(ValueError) as exc_info:
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=(),
            facts=(),
            blockers=(
                AutomationBlocker(
                    code="sec_evidence_insufficient",
                    retryable=False,
                    context={
                        "monitoring_reason": "not_confirmed_as_of",
                        "as_of": "2026-05-07",
                    },
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at=None,
            diagnostics={"sec_attempts": 1},
            at="2026-08-27T00:00:00Z",
        )

    assert str(exc_info.value) == "blocker_citation"
    assert store.get_automation_run(claim.run_id)["status"] == "running"


def test_automation_run_key_binds_case_observation_policy_and_mode():
    from src.security_lifecycle_fact_kernel import (
        AutomationBlocker,
        _execution_run_key,
        automation_run_key,
    )

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
    execution = _execution_run_key(
        semantic_run_key=base,
        execution_revision="trusted-lifecycle-execution-r1",
        predecessor_failed_run_id=None,
    )
    replay_execution = _execution_run_key(
        semantic_run_key=base,
        execution_revision="trusted-lifecycle-execution-r1",
        predecessor_failed_run_id="slar_previous",
    )
    assert execution.startswith("lifecycle-automation-execution-v1:")
    assert execution != replay_execution

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


def test_current_policy_retries_a_failed_run_without_deleting_v1_history():
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION

    _conn, store, kernel, case_id = _context()
    failed_claim = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v1",
    )
    kernel.fail_run(
        run_id=failed_claim.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )

    assert AUTOMATION_POLICY_VERSION == "trusted-lifecycle-automation-v3"
    assert _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v1",
        at=_LATER,
    ).should_execute is False

    retry = _reserve(
        kernel,
        case_id,
        policy_version=AUTOMATION_POLICY_VERSION,
        at=_LATER,
    )
    assert retry.should_execute is True
    assert retry.run_id != failed_claim.run_id
    assert [
        tuple(row)
        for row in store.conn.execute(
            "SELECT policy_version,status FROM security_lifecycle_automation_runs "
            "ORDER BY created_at,run_id"
        )
        ] == [
            ("trusted-lifecycle-automation-v1", "failed"),
            ("trusted-lifecycle-automation-v3", "running"),
        ]


def test_failed_semantic_run_replays_once_per_execution_revision():
    _conn, store, kernel, case_id = _context()
    first = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    kernel.fail_run(
        run_id=first.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )

    replay = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    duplicate = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:01Z",
    )

    assert replay.should_execute is True
    assert replay.run_id != first.run_id
    assert duplicate.should_execute is False
    assert duplicate.run_id == replay.run_id
    assert store.get_automation_run(first.run_id)["status"] == "failed"

    first_row = store.get_automation_run(first.run_id)
    replay_row = store.get_automation_run(replay.run_id)
    assert first_row["run_key"].startswith("lifecycle-automation-execution-v1:")
    assert replay_row["run_key"].startswith("lifecycle-automation-execution-v1:")
    assert replay_row["run_key"] != first_row["run_key"]
    assert json.loads(replay_row["query_context_json"])["semantic_run_key"] == (
        json.loads(first_row["query_context_json"])["semantic_run_key"]
    )
    assert json.loads(replay_row["query_context_json"])["predecessor_failed_run_id"] == (
        first.run_id
    )


def test_successful_replay_prevents_later_revision_fanout():
    _conn, store, kernel, case_id = _context()
    first = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    kernel.fail_run(
        run_id=first.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )
    replay = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    evidence = _evidence()
    _succeed(
        kernel,
        replay,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        at="2026-08-26T01:00:00Z",
    )

    later = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r2",
        at="2026-08-27T00:00:00Z",
    )
    assert later.should_execute is False
    assert later.run_id == replay.run_id
    assert len(store.list_automation_runs(case_id)) == 2


def test_pre_execution_key_succeeded_row_remains_idempotent():
    _conn, store, kernel, case_id = _context()
    first = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    evidence = _evidence()
    _succeed(kernel, first, evidence=(evidence,), facts=(_fact(evidence),))

    row = store.get_automation_run(first.run_id)
    context = json.loads(row["query_context_json"])
    semantic_run_key = context.pop("semantic_run_key")
    context.pop("execution_revision")
    context.pop("latest_attempt_execution_revision")
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs "
        "SET run_key=?,query_context_json=? WHERE run_id=?",
        (
            semantic_run_key,
            json.dumps(context, separators=(",", ":"), sort_keys=True),
            first.run_id,
        ),
    )
    store.conn.commit()

    duplicate = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-27T00:00:00Z",
    )

    assert duplicate.should_execute is False
    assert duplicate.run_id == first.run_id
    assert len(store.list_automation_runs(case_id)) == 1


def test_legacy_failed_semantic_run_replays_once_at_current_execution_revision():
    _conn, store, kernel, case_id = _context()
    failed = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    row = store.get_automation_run(failed.run_id)
    context = json.loads(row["query_context_json"])
    del context["execution_revision"]
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), failed.run_id),
    )
    store.conn.commit()
    kernel.fail_run(
        run_id=failed.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )

    replay = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    duplicate = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:01Z",
    )
    assert replay.should_execute is True
    assert duplicate.should_execute is False
    assert duplicate.run_id == replay.run_id


def test_current_execution_revision_does_not_replay_failed_semantic_run_later():
    _conn, store, kernel, case_id = _context()
    failed = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
    )
    kernel.fail_run(
        run_id=failed.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )

    for at in ("2026-08-26T02:00:00Z", "2027-08-25T02:00:00Z"):
        claim = _reserve(
            kernel,
            case_id,
            policy_version="trusted-lifecycle-automation-v3",
            execution_revision="trusted-lifecycle-execution-r1",
            at=at,
        )
        assert claim.should_execute is False
        assert claim.run_id == failed.run_id
    assert len(store.list_automation_runs(case_id)) == 1


def test_latest_semantic_run_statuses_do_not_fan_out_execution_revisions():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    for status in ("queued", "running", "blocked", "succeeded", "cancelled"):
        _conn, store, kernel, case_id = _context()
        claim = _reserve(
            kernel,
            case_id,
            policy_version=f"trusted-lifecycle-{status}",
            execution_revision="trusted-lifecycle-execution-r0",
        )
        if status == "blocked":
            kernel.complete_run(
                run_id=claim.run_id,
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
                retry_at="2026-08-28T00:00:00Z",
                diagnostics={"sec_attempts": 1},
                at=_LATER,
            )
        elif status == "succeeded":
            evidence = _evidence(status)
            _succeed(kernel, claim, evidence=(evidence,), facts=(_fact(evidence),))
        elif status == "queued":
            store.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "status='queued',started_at=NULL WHERE run_id=?",
                (claim.run_id,),
            )
            store.conn.commit()
        elif status == "cancelled":
            store.conn.execute(
                "UPDATE security_lifecycle_automation_runs SET "
                "status='cancelled',finished_at=? WHERE run_id=?",
                (_LATER, claim.run_id),
            )
            store.conn.commit()

        later = _reserve(
            kernel,
            case_id,
            policy_version=f"trusted-lifecycle-{status}",
            execution_revision="trusted-lifecycle-execution-r1",
            at="2026-08-26T00:00:00Z",
        )
        assert later.should_execute is False
        assert later.run_id == claim.run_id
        assert len(store.list_automation_runs(case_id)) == 1


def test_due_retryable_blocked_semantic_run_reuses_its_execution_row():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    blocked = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    kernel.complete_run(
        run_id=blocked.run_id,
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
        retry_at="2026-08-26T00:00:00Z",
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    before = store.get_automation_run(blocked.run_id)
    original_run_key = before["run_key"]
    original_query_context_json = before["query_context_json"]

    retry = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    after = store.get_automation_run(retry.run_id)
    assert retry.should_execute is True
    assert retry.run_id == blocked.run_id
    assert after["run_key"] == original_run_key
    before_context = json.loads(original_query_context_json)
    after_context = json.loads(after["query_context_json"])
    assert before_context["execution_revision"] == "trusted-lifecycle-execution-r0"
    assert after_context["execution_revision"] == "trusted-lifecycle-execution-r0"
    assert before_context["latest_attempt_execution_revision"] == (
        "trusted-lifecycle-execution-r0"
    )
    assert after_context["latest_attempt_execution_revision"] == (
        "trusted-lifecycle-execution-r1"
    )
    assert {
        key: value
        for key, value in after_context.items()
        if key != "latest_attempt_execution_revision"
    } == {
        key: value
        for key, value in before_context.items()
        if key != "latest_attempt_execution_revision"
    }
    assert after["status"] == "running"
    assert len(store.list_automation_runs(case_id)) == 1


def test_cross_revision_due_blocked_failure_does_not_replay_same_attempt_revision():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    blocked = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    kernel.complete_run(
        run_id=blocked.run_id,
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
        retry_at="2026-08-26T00:00:00Z",
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )

    retry = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    retry_context = json.loads(
        store.get_automation_run(retry.run_id)["query_context_json"]
    )
    assert retry.should_execute is True
    assert retry.run_id == blocked.run_id
    assert retry_context["execution_revision"] == "trusted-lifecycle-execution-r0"
    assert retry_context["latest_attempt_execution_revision"] == (
        "trusted-lifecycle-execution-r1"
    )

    kernel.fail_run(
        run_id=retry.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at="2026-08-26T00:01:00Z",
    )
    same_deploy = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-27T00:00:00Z",
    )
    assert same_deploy.should_execute is False
    assert same_deploy.run_id == blocked.run_id
    assert len(store.list_automation_runs(case_id)) == 1


def test_semantic_run_lookup_never_cross_selects_cases_with_same_fingerprint():
    _conn, store, kernel, first_case_id = _context()
    second_case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0001409970-26-000132",
        ticker="HAPN2",
        at=_AT,
    )
    failed = _reserve(
        kernel,
        first_case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    kernel.fail_run(
        run_id=failed.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )

    second = _reserve(
        kernel,
        second_case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    second_context = json.loads(store.get_automation_run(second.run_id)["query_context_json"])
    assert second.should_execute is True
    assert second.run_id != failed.run_id
    assert "predecessor_failed_run_id" not in second_context


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
    assert json.loads(row["blockers"][0]["context_json"]) == {
        "fact_types": ["successor_ticker"]
    }


def test_explicit_source_conflict_survives_persistence_without_derived_fact_conflict():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()

    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        blockers=(
            AutomationBlocker(
                code="source_conflict",
                retryable=False,
                context={"source_families": ["regulator", "publisher"]},
            ),
        ),
        decision_tier="review_suggested",
        action_readiness="action_blocked",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )

    row = store.get_automation_run(claim.run_id)
    assert result.status == "succeeded"
    assert result.decision_tier == "review_suggested"
    assert result.action_readiness == "action_blocked"
    assert [item["blocker_code"] for item in row["blockers"]] == [
        "source_conflict"
    ]
    assert json.loads(row["blockers"][0]["context_json"]) == {
        "source_families": ["regulator", "publisher"]
    }


@pytest.mark.parametrize(
    "blocker_code",
    ("transition_approval_changed", "transition_approval_unavailable"),
)
def test_transition_revalidation_blockers_remain_citation_free(blocker_code):
    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()
    _succeed(kernel, claim, evidence=(evidence,), facts=(_fact(evidence),))

    kernel.defer_transition_revalidation(
        run_id=claim.run_id,
        blocker_code=blocker_code,
        at="2026-08-25T03:00:00Z",
    )

    blockers = store.get_automation_run(claim.run_id)["blockers"]
    assert [row["blocker_code"] for row in blockers] == [blocker_code]
    assert json.loads(blockers[0]["context_json"]) == {}


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


def test_terminal_finalization_rejects_changed_query_context_provenance():
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()
    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="not_applicable",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
        terminal_decision={
            "decision_tier": "verified_automatic",
            "action_readiness": "not_applicable",
        },
    )
    context = json.loads(store.get_automation_run(claim.run_id)["query_context_json"])
    context["terminal_decision_provenance_sha256"] = "f" * 64
    conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), claim.run_id),
    )
    conn.commit()

    with pytest.raises(ValueError, match="terminal_decision_provenance_changed"):
        kernel.complete_terminal_finalization(
            run_id=claim.run_id,
            decision_provenance_sha256=result.decision_provenance_sha256,
        )

    final_context = json.loads(
        store.get_automation_run(claim.run_id)["query_context_json"]
    )
    assert "terminal_finalized_decision_provenance_sha256" not in final_context


def test_terminal_finalization_rejects_changed_persisted_provenance():
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()
    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="not_applicable",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
        terminal_decision={
            "decision_tier": "verified_automatic",
            "action_readiness": "not_applicable",
        },
    )
    conn.execute(
        "UPDATE security_lifecycle_automation_facts "
        "SET extractor_rule_version='2' WHERE automation_run_id=?",
        (claim.run_id,),
    )
    conn.commit()

    with pytest.raises(ValueError, match="terminal_decision_provenance_changed"):
        kernel.complete_terminal_finalization(
            run_id=claim.run_id,
            decision_provenance_sha256=result.decision_provenance_sha256,
        )

    final_context = json.loads(
        store.get_automation_run(claim.run_id)["query_context_json"]
    )
    assert "terminal_finalized_decision_provenance_sha256" not in final_context


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
    from src.security_lifecycle_fact_kernel import automation_run_key

    _conn, store, kernel, case_id = _context()
    claim = _reserve(
        kernel,
        case_id,
        query_context={"z": [2, 1], "a": {"ticker": "HAPN"}},
        diagnostics={"sec_documents": 2, "sec_attempts": 3},
    )
    row = store.get_automation_run(claim.run_id)
    assert json.loads(row["query_context_json"]) == {
        "a": {"ticker": "HAPN"},
        "execution_revision": "trusted-lifecycle-execution-r1",
        "latest_attempt_execution_revision": "trusted-lifecycle-execution-r1",
        "input_evidence_set_sha256": (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        "semantic_run_key": automation_run_key(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            policy_version="trusted-lifecycle-v1",
            mode="historical",
            input_evidence_set_sha256=(
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
        ),
        "z": [2, 1],
    }
    assert row["diagnostics_json"] == '{"sec_attempts":3,"sec_documents":2}'

    for query_context, diagnostics in (
        ({"api_key": "secret"}, {}),
        ({"ticker": "HAPN\0"}, {}),
        ({"notes": "x" * 17000}, {}),
        ({"input_evidence_set_sha256": "1" * 64}, {}),
        ({"semantic_run_key": "spoofed"}, {}),
        ({"execution_revision": "spoofed"}, {}),
        ({"latest_attempt_execution_revision": "spoofed"}, {}),
        ({"predecessor_failed_run_id": "slar_spoofed"}, {}),
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
