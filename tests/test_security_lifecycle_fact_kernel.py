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
        "execution_owner_id": "test-kernel-owner",
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


def _rehydrated_prior_material(prior):
    evidence = tuple(
        {**dict(row), "source_locator": json.loads(row["source_locator_json"])}
        for row in prior.evidence
    )
    facts = tuple(
        {
            **dict(row),
            "normalized_value": json.loads(row["normalized_value_json"]),
        }
        for row in prior.facts
    )
    return evidence, facts


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
            "listing_authority": "available",
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


def _symbol_decision(ticker, *, readiness):
    return {
        "decision_tier": "verified_automatic",
        "action_readiness": readiness,
        "relevance": "direct_tracked_security",
        "confidence": "high",
        "outcomes": ("symbol_changed",),
        "conclusion": f"The tracked security continues under ticker {ticker}.",
        "impact_summary": "Preserve tracking intent under the successor ticker.",
        "successor_ticker": ticker,
        "destination_venue": "NASDAQ",
        "effective_date": "2026-08-26",
        "counterparty_name": None,
        "counterparty_ticker": None,
        "counterparty_cik": None,
        "consideration_currency": None,
        "cash_per_security_decimal": None,
        "exchange_ratio_decimal": None,
        "rule_id": "lifecycle.simple_symbol_continuation",
        "rule_version": "1",
        "decision_issues": (),
        "transition_requested": True,
    }


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
@pytest.mark.parametrize(
    "adapter", ("nasdaq_symbol_directory", "massive_reference")
)
def test_listing_producer_mutations_fail_at_real_kernel_validator(
    adapter, mutation, expected
):
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id, at=_LISTING_AT)
    evidence, facts = _listing_producer_result(adapter)
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
    assert conn.execute(
        "SELECT COUNT(*) FROM security_lifecycle_automation_facts "
        "WHERE automation_run_id=?",
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
        execution_owner_id="test-kernel-recheck-owner",
    )
    assert retry.run_id == claim.run_id
    prior = kernel.prior_material(retry.run_id)
    retained_evidence, retained_facts = _rehydrated_prior_material(prior)
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
        retained_evidence=retained_evidence,
        retained_facts=retained_facts,
        refreshed_source_families=(),
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
        predecessor_run_id=None,
    )
    replay_execution = _execution_run_key(
        semantic_run_key=base,
        execution_revision="trusted-lifecycle-execution-r1",
        predecessor_run_id="slar_previous",
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

    assert AUTOMATION_POLICY_VERSION == "trusted-lifecycle-automation-v4"
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
            (AUTOMATION_POLICY_VERSION, "running"),
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
    assert json.loads(replay_row["query_context_json"])["predecessor_run_id"] == (
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


def test_due_failed_retry_requires_explicit_authority_and_preserves_predecessor():
    _conn, store, kernel, case_id = _context()
    failed = _reserve(kernel, case_id)
    kernel.fail_run(
        run_id=failed.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at="2026-08-25T02:00:00Z",
    )
    failed_snapshot = store.get_automation_run(failed.run_id)

    parked = _reserve(
        kernel,
        case_id,
        at="2026-08-25T02:15:00Z",
    )
    retry = _reserve(
        kernel,
        case_id,
        at="2026-08-25T02:15:00Z",
        allow_due_failed_retry=True,
    )

    assert parked.should_execute is False
    assert parked.run_id == failed.run_id
    assert retry.should_execute is True
    assert retry.run_id != failed.run_id
    retry_context = json.loads(
        store.get_automation_run(retry.run_id)["query_context_json"]
    )
    assert retry_context["predecessor_run_id"] == failed.run_id
    assert store.get_automation_run(failed.run_id) == failed_snapshot


@pytest.mark.parametrize("terminal_status", ("failed", "blocked", "succeeded"))
def test_attended_new_attempt_preserves_each_terminal_predecessor(terminal_status):
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    predecessor = _reserve(kernel, case_id)
    if terminal_status == "failed":
        kernel.fail_run(
            run_id=predecessor.run_id,
            failure_code="extractor_failed",
            diagnostics={"failures": 1},
            at=_LATER,
        )
    elif terminal_status == "blocked":
        kernel.complete_run(
            run_id=predecessor.run_id,
            evidence=(),
            facts=(),
            blockers=(
                AutomationBlocker(
                    code="massive_credential_missing",
                    retryable=False,
                    context={"provider": "massive"},
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at=None,
            diagnostics={"listing_requests": 0},
            at=_LATER,
        )
    else:
        evidence = _evidence("attended-completed")
        _succeed(
            kernel,
            predecessor,
            evidence=(evidence,),
            facts=(_fact(evidence),),
        )
    predecessor_snapshot = store.get_automation_run(predecessor.run_id)

    without_authority = _reserve(
        kernel,
        case_id,
        at="2026-08-25T03:00:00Z",
    )
    attended = _reserve(
        kernel,
        case_id,
        at="2026-08-25T03:00:00Z",
        allow_new_attempt=True,
    )

    assert without_authority.should_execute is False
    assert without_authority.run_id == predecessor.run_id
    assert attended.should_execute is True
    assert attended.run_id != predecessor.run_id
    attended_context = json.loads(
        store.get_automation_run(attended.run_id)["query_context_json"]
    )
    assert attended_context["predecessor_run_id"] == predecessor.run_id
    assert store.get_automation_run(predecessor.run_id) == predecessor_snapshot


def test_retry_count_comes_from_predecessor_chain_not_caller_context():
    _conn, store, kernel, case_id = _context()
    first = _reserve(kernel, case_id)
    kernel.fail_run(
        run_id=first.run_id,
        failure_code="persistence_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T02:00:00Z",
    )
    second = _reserve(
        kernel,
        case_id,
        allow_due_failed_retry=True,
        at="2026-08-25T02:15:00Z",
    )
    kernel.fail_run(
        run_id=second.run_id,
        failure_code="persistence_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T02:16:00Z",
    )
    third = _reserve(
        kernel,
        case_id,
        allow_due_failed_retry=True,
        at="2026-08-25T03:16:00Z",
        query_context={
            "case_id": case_id,
            "cik": "0001409970",
            "aliases": ["HAPN", "LC"],
            "automatic_retry_attempt_count": 0,
        },
    )
    kernel.fail_run(
        run_id=third.run_id,
        failure_code="persistence_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T03:17:00Z",
    )

    context = json.loads(
        store.get_automation_run(third.run_id)["query_context_json"]
    )
    assert context["automatic_retry"] == {
        "class": "persistence_failed",
        "retry_not_before": "2026-08-25T09:17:00Z",
    }


def test_persistence_failure_allows_exactly_three_automatic_attempts():
    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    failures_and_due_times = (
        ("2026-08-25T02:00:00Z", "2026-08-25T02:15:00Z"),
        ("2026-08-25T02:16:00Z", "2026-08-25T03:16:00Z"),
        ("2026-08-25T03:17:00Z", "2026-08-25T09:17:00Z"),
    )
    for failed_at, due_at in failures_and_due_times:
        kernel.fail_run(
            run_id=claim.run_id,
            failure_code="persistence_failed",
            diagnostics={"failures": 1},
            at=failed_at,
        )
        claim = _reserve(
            kernel,
            case_id,
            allow_due_failed_retry=True,
            at=due_at,
        )
        assert claim.should_execute is True

    kernel.fail_run(
        run_id=claim.run_id,
        failure_code="persistence_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T09:18:00Z",
    )
    exhausted = _reserve(
        kernel,
        case_id,
        allow_due_failed_retry=True,
        at="2027-08-25T09:18:00Z",
    )
    context = json.loads(
        store.get_automation_run(claim.run_id)["query_context_json"]
    )

    assert exhausted.should_execute is False
    assert exhausted.run_id == claim.run_id
    assert context["automatic_retry"] == {
        "class": "persistence_failed",
        "retry_not_before": None,
    }
    assert len(store.list_automation_runs(case_id)) == 4


@pytest.mark.parametrize(
    ("failure_code", "due_at"),
    (
        ("source_payload_invalid", "2026-08-25T03:00:00Z"),
        ("internal_error", "2026-08-25T03:00:00Z"),
    ),
)
def test_single_retry_classes_allow_exactly_one_due_automatic_attempt(
    failure_code,
    due_at,
):
    _conn, store, kernel, case_id = _context()
    first = _reserve(kernel, case_id)
    kernel.fail_run(
        run_id=first.run_id,
        failure_code=failure_code,
        diagnostics={"failures": 1},
        at="2026-08-25T02:00:00Z",
    )
    retry = _reserve(
        kernel,
        case_id,
        allow_due_failed_retry=True,
        at=due_at,
    )
    kernel.fail_run(
        run_id=retry.run_id,
        failure_code=failure_code,
        diagnostics={"failures": 1},
        at="2026-08-25T03:01:00Z",
    )

    exhausted = _reserve(
        kernel,
        case_id,
        allow_due_failed_retry=True,
        at="2027-08-25T03:01:00Z",
    )
    retry_context = json.loads(
        store.get_automation_run(retry.run_id)["query_context_json"]
    )
    assert exhausted.should_execute is False
    assert exhausted.run_id == retry.run_id
    assert retry_context["automatic_retry"] == {
        "class": failure_code,
        "retry_not_before": None,
    }
    assert len(store.list_automation_runs(case_id)) == 2


@pytest.mark.parametrize(
    "failure_code",
    ("extractor_failed", "profile_schema_mismatch"),
)
def test_manual_only_failure_classes_never_gain_automatic_retry(failure_code):
    _conn, store, kernel, case_id = _context()
    failed = _reserve(kernel, case_id)
    kernel.fail_run(
        run_id=failed.run_id,
        failure_code=failure_code,
        diagnostics={"failures": 1},
        at="2026-08-25T02:00:00Z",
    )

    automatic = _reserve(
        kernel,
        case_id,
        allow_due_failed_retry=True,
        at="2027-08-25T02:00:00Z",
    )
    attended = _reserve(
        kernel,
        case_id,
        allow_new_attempt=True,
        at="2027-08-25T02:00:00Z",
    )
    context = json.loads(
        store.get_automation_run(failed.run_id)["query_context_json"]
    )

    assert automatic.should_execute is False
    assert attended.should_execute is True
    assert "automatic_retry" not in context


def test_reconciled_internal_error_receives_one_hour_retry_authority():
    _conn, store, kernel, case_id = _context()
    running = _reserve(kernel, case_id)

    assert kernel.reconcile_running_runs(
        at="2026-08-25T02:00:00Z",
        execution_owner_id="test-kernel-owner",
    ) == (running.run_id,)
    failed = store.get_automation_run(running.run_id)
    context = json.loads(failed["query_context_json"])
    assert context["automatic_retry"] == {
        "class": "internal_error",
        "retry_not_before": "2026-08-25T03:00:00Z",
    }
    assert failed["retry_at"] is None


def _poison_run_with_predecessor_cycle(store, run_id):
    context = json.loads(store.get_automation_run(run_id)["query_context_json"])
    context["predecessor_run_id"] = run_id
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), run_id),
    )
    store.conn.commit()


def test_reconcile_reclaims_healthy_rows_despite_one_unclassifiable_row():
    _conn, store, kernel, poisoned_case_id = _context()
    healthy_case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0001409970-26-000132",
        ticker="HAPN",
        at=_AT,
    )
    poisoned = _reserve(kernel, poisoned_case_id)
    healthy = _reserve(
        kernel,
        healthy_case_id,
        observation_fingerprint_sha256="b" * 64,
    )
    _poison_run_with_predecessor_cycle(store, poisoned.run_id)

    reconciled = kernel.reconcile_running_runs(at=_LATER)

    assert reconciled == (healthy.run_id,)
    assert store.get_automation_run(healthy.run_id)["status"] == "failed"


def test_reconcile_records_the_unclassifiable_row_rather_than_skipping_silently():
    _conn, store, kernel, case_id = _context()
    poisoned = _reserve(kernel, case_id)
    _poison_run_with_predecessor_cycle(store, poisoned.run_id)

    assert kernel.reconcile_running_runs(at=_LATER) == ()

    recorded = store.get_automation_run(poisoned.run_id)
    context = json.loads(recorded["query_context_json"])
    assert recorded["status"] == "failed"
    assert recorded["failure_code"] == "internal_error"
    assert json.loads(recorded["diagnostics_json"]) == {
        "interrupted_execution": 1,
        "reconciliation_unclassifiable": 1,
    }
    assert "automatic_retry" not in context


def test_reconcile_propagates_unrelated_value_error_and_rolls_back(monkeypatch):
    from src import security_lifecycle_fact_kernel as fact_kernel

    _conn, store, kernel, first_case_id = _context()
    second_case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0001409970-26-000132",
        ticker="HAPN",
        at=_AT,
    )
    first = _reserve(kernel, first_case_id)
    second = _reserve(
        kernel,
        second_case_id,
        observation_fingerprint_sha256="b" * 64,
    )
    real_retry_for_failure = fact_kernel._automatic_retry_for_failure

    def retry_for_failure(conn, *, run_id, failure_code, failed_at):
        if run_id == second.run_id:
            raise ValueError("injected_reconciliation_programming_error")
        return real_retry_for_failure(
            conn,
            run_id=run_id,
            failure_code=failure_code,
            failed_at=failed_at,
        )

    monkeypatch.setattr(
        fact_kernel,
        "_automatic_retry_for_failure",
        retry_for_failure,
    )

    with pytest.raises(
        ValueError,
        match="injected_reconciliation_programming_error",
    ):
        kernel.reconcile_running_runs(at=_LATER)

    assert store.get_automation_run(first.run_id)["status"] == "running"
    assert store.get_automation_run(second.run_id)["status"] == "running"


def test_legacy_failed_predecessor_field_remains_chain_readable():
    _conn, store, kernel, case_id = _context()
    first = _reserve(kernel, case_id, execution_revision="execution-r0")
    kernel.fail_run(
        run_id=first.run_id,
        failure_code="persistence_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T02:00:00Z",
    )
    second = _reserve(
        kernel,
        case_id,
        execution_revision="execution-r1",
        at="2026-08-25T03:00:00Z",
    )
    kernel.fail_run(
        run_id=second.run_id,
        failure_code="persistence_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T03:01:00Z",
    )
    context = json.loads(
        store.get_automation_run(second.run_id)["query_context_json"]
    )
    context["predecessor_failed_run_id"] = context.pop("predecessor_run_id")
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), second.run_id),
    )
    store.conn.commit()

    third = _reserve(
        kernel,
        case_id,
        execution_revision="execution-r1",
        allow_due_failed_retry=True,
        at="2026-08-25T04:01:00Z",
    )
    assert third.should_execute is True
    assert json.loads(
        store.get_automation_run(third.run_id)["query_context_json"]
    )["predecessor_run_id"] == second.run_id


def _two_failed_attended_attempts(kernel, case_id):
    first = _reserve(kernel, case_id)
    kernel.fail_run(
        run_id=first.run_id,
        failure_code="extractor_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T02:00:00Z",
    )
    second = _reserve(
        kernel,
        case_id,
        allow_new_attempt=True,
        at="2026-08-25T03:00:00Z",
    )
    kernel.fail_run(
        run_id=second.run_id,
        failure_code="extractor_failed",
        diagnostics={"failures": 1},
        at="2026-08-25T04:00:00Z",
    )
    return first, second


def test_predecessor_chain_rejects_a_different_input_evidence_snapshot():
    from src.security_lifecycle_fact_kernel import automation_run_key

    _conn, store, kernel, case_id = _context()
    first, _second = _two_failed_attended_attempts(kernel, case_id)
    context = json.loads(
        store.get_automation_run(first.run_id)["query_context_json"]
    )
    context["input_evidence_set_sha256"] = "b" * 64
    context["semantic_run_key"] = automation_run_key(
        case_id=case_id,
        observation_fingerprint_sha256=_FINGERPRINT,
        policy_version="trusted-lifecycle-v1",
        mode="historical",
        input_evidence_set_sha256="b" * 64,
    )
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), first.run_id),
    )
    store.conn.commit()

    with pytest.raises(ValueError, match="automation_predecessor_semantic_identity"):
        _reserve(
            kernel,
            case_id,
            allow_new_attempt=True,
            at="2026-08-25T05:00:00Z",
        )


def test_predecessor_chain_rejects_a_noncanonical_semantic_run_key():
    _conn, store, kernel, case_id = _context()
    first, _second = _two_failed_attended_attempts(kernel, case_id)
    context = json.loads(
        store.get_automation_run(first.run_id)["query_context_json"]
    )
    context["semantic_run_key"] = "lifecycle-automation-v1:" + "f" * 64
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), first.run_id),
    )
    store.conn.commit()

    with pytest.raises(ValueError, match="automation_predecessor_semantic_run_key"):
        _reserve(
            kernel,
            case_id,
            allow_new_attempt=True,
            at="2026-08-25T05:00:00Z",
        )


def test_legacy_predecessor_missing_semantic_metadata_fails_closed():
    _conn, store, kernel, case_id = _context()
    first, second = _two_failed_attended_attempts(kernel, case_id)
    first_context = json.loads(
        store.get_automation_run(first.run_id)["query_context_json"]
    )
    first_context.pop("input_evidence_set_sha256")
    second_context = json.loads(
        store.get_automation_run(second.run_id)["query_context_json"]
    )
    second_context["predecessor_failed_run_id"] = second_context.pop(
        "predecessor_run_id"
    )
    store.conn.executemany(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (
            (
                json.dumps(first_context, separators=(",", ":"), sort_keys=True),
                first.run_id,
            ),
            (
                json.dumps(second_context, separators=(",", ":"), sort_keys=True),
                second.run_id,
            ),
        ),
    )
    store.conn.commit()

    with pytest.raises(
        ValueError,
        match="automation_predecessor_input_evidence_set_sha256",
    ):
        _reserve(
            kernel,
            case_id,
            allow_new_attempt=True,
            at="2026-08-25T05:00:00Z",
        )


def test_malformed_legacy_predecessor_field_fails_closed():
    _conn, store, kernel, case_id = _context()
    _first, second = _two_failed_attended_attempts(kernel, case_id)
    context = json.loads(
        store.get_automation_run(second.run_id)["query_context_json"]
    )
    context.pop("predecessor_run_id")
    context["predecessor_failed_run_id"] = {"run_id": "slar_malformed"}
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), second.run_id),
    )
    store.conn.commit()

    with pytest.raises(ValueError, match="automation_predecessor_chain"):
        _reserve(
            kernel,
            case_id,
            allow_new_attempt=True,
            at="2026-08-25T05:00:00Z",
        )


def _over_long_running_attempt(kernel, case_id):
    claim = _reserve(kernel, case_id)
    boundary_run_id = claim.run_id
    for ordinal in range(32):
        kernel.fail_run(
            run_id=claim.run_id,
            failure_code="extractor_failed",
            diagnostics={"ordinal": ordinal},
            at=f"2026-08-25T02:{ordinal:02d}:00Z",
        )
        claim = _reserve(
            kernel,
            case_id,
            allow_new_attempt=True,
            at=f"2026-08-25T02:{ordinal:02d}:30Z",
        )
    return claim, boundary_run_id


def test_over_long_predecessor_chain_exhausts_retries_without_raising():
    _conn, store, kernel, case_id = _context()
    claim, _boundary_run_id = _over_long_running_attempt(kernel, case_id)

    failed = kernel.fail_run(
        run_id=claim.run_id,
        failure_code="internal_error",
        diagnostics={"failures": 1},
        at="2026-08-25T02:32:00Z",
    )

    context = json.loads(failed["query_context_json"])
    assert failed["status"] == "failed"
    assert failed["failure_code"] == "internal_error"
    assert context["automatic_retry"] == {
        "class": "internal_error",
        "retry_not_before": None,
    }
    assert store.get_automation_run(claim.run_id)["status"] != "running"


def test_unattended_admission_parks_an_exhausted_over_long_failure():
    _conn, store, kernel, case_id = _context()
    claim, _boundary_run_id = _over_long_running_attempt(kernel, case_id)
    failed = kernel.fail_run(
        run_id=claim.run_id,
        failure_code="internal_error",
        diagnostics={"failures": 1},
        at="2026-08-25T02:32:00Z",
    )

    parked = _reserve(
        kernel,
        case_id,
        allow_due_failed_retry=True,
        at="2099-08-25T02:32:00Z",
    )

    assert parked.should_execute is False
    assert parked.run_id == failed["run_id"]
    assert parked.status == "failed"
    assert len(store.list_automation_runs(case_id)) == 33


def test_per_case_run_button_cannot_grow_an_unbounded_predecessor_chain():
    _conn, store, kernel, case_id = _context()
    claim, _boundary_run_id = _over_long_running_attempt(kernel, case_id)
    kernel.fail_run(
        run_id=claim.run_id,
        failure_code="extractor_failed",
        diagnostics={"ordinal": 32},
        at="2026-08-25T02:32:00Z",
    )

    with pytest.raises(ValueError, match="automation_predecessor_chain_limit"):
        _reserve(
            kernel,
            case_id,
            allow_new_attempt=True,
            at="2026-08-25T02:32:30Z",
        )
    assert len(store.list_automation_runs(case_id)) == 33


def _corrupt_attempt_chain_boundary(
    store,
    *,
    boundary_run_id,
    case_id,
    corruption,
):
    from src.security_lifecycle_fact_kernel import automation_run_key

    if corruption == "missing_row":
        store.conn.execute(
            "DELETE FROM security_lifecycle_automation_runs WHERE run_id=?",
            (boundary_run_id,),
        )
        store.conn.commit()
        return

    context = json.loads(
        store.get_automation_run(boundary_run_id)["query_context_json"]
    )
    if corruption == "malformed_field":
        context["predecessor_run_id"] = {"run_id": "slar_malformed"}
    elif corruption == "cycle":
        context["predecessor_run_id"] = boundary_run_id
    elif corruption == "semantic_run_key":
        context["semantic_run_key"] = "lifecycle-automation-v1:" + "f" * 64
    elif corruption == "semantic_identity":
        context["input_evidence_set_sha256"] = "b" * 64
        context["semantic_run_key"] = automation_run_key(
            case_id=case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
            policy_version="trusted-lifecycle-v1",
            mode="historical",
            input_evidence_set_sha256="b" * 64,
        )
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (
            json.dumps(context, separators=(",", ":"), sort_keys=True),
            boundary_run_id,
        ),
    )
    store.conn.commit()


@pytest.mark.parametrize(
    ("corruption", "error"),
    (
        ("missing_row", "automation_predecessor_chain"),
        ("malformed_field", "automation_predecessor_chain"),
        ("cycle", "automation_predecessor_cycle"),
        ("semantic_run_key", "automation_predecessor_semantic_run_key"),
        ("semantic_identity", "automation_predecessor_semantic_identity"),
    ),
)
def test_over_long_chain_validates_boundary_corruption_before_exhaustion(
    corruption,
    error,
):
    _conn, store, kernel, case_id = _context()
    running, boundary_run_id = _over_long_running_attempt(kernel, case_id)
    _corrupt_attempt_chain_boundary(
        store,
        boundary_run_id=boundary_run_id,
        case_id=case_id,
        corruption=corruption,
    )

    with pytest.raises(ValueError) as exc_info:
        kernel.fail_run(
            run_id=running.run_id,
            failure_code="internal_error",
            diagnostics={"failures": 1},
            at="2026-08-25T02:32:00Z",
        )

    assert exc_info.value.args == (error,)
    assert store.get_automation_run(running.run_id)["status"] == "running"


@pytest.mark.parametrize(
    ("corruption", "error"),
    (
        ("cycle", "automation_predecessor_cycle"),
        ("missing_row", "automation_predecessor_chain"),
        ("malformed_field", "automation_predecessor_chain"),
        ("malformed_context", "query_context"),
        ("semantic_run_key", "automation_predecessor_semantic_run_key"),
    ),
)
def test_failure_recovery_preserves_fail_closed_predecessor_validation(
    corruption,
    error,
):
    _conn, store, kernel, case_id = _context()
    running = _reserve(kernel, case_id)
    context = json.loads(
        store.get_automation_run(running.run_id)["query_context_json"]
    )
    if corruption == "cycle":
        context["predecessor_run_id"] = running.run_id
    elif corruption == "missing_row":
        context["predecessor_run_id"] = "slar_missing"
    elif corruption == "malformed_field":
        context["predecessor_run_id"] = {"run_id": "slar_malformed"}
    elif corruption == "semantic_run_key":
        context["semantic_run_key"] = "lifecycle-automation-v1:" + "f" * 64
    query_context_json = (
        "[]"
        if corruption == "malformed_context"
        else json.dumps(context, separators=(",", ":"), sort_keys=True)
    )
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (query_context_json, running.run_id),
    )
    store.conn.commit()

    with pytest.raises(ValueError, match=error):
        kernel.fail_run(
            run_id=running.run_id,
            failure_code="internal_error",
            diagnostics={"failures": 1},
            at=_LATER,
        )
    assert store.get_automation_run(running.run_id)["status"] == "running"


def test_failure_recovery_preserves_fail_closed_semantic_identity_validation():
    from src.security_lifecycle_fact_kernel import automation_run_key

    _conn, store, kernel, case_id = _context()
    predecessor = _reserve(kernel, case_id)
    kernel.fail_run(
        run_id=predecessor.run_id,
        failure_code="extractor_failed",
        diagnostics={"failures": 1},
        at=_LATER,
    )
    running = _reserve(
        kernel,
        case_id,
        allow_new_attempt=True,
        at="2026-08-25T03:00:00Z",
    )
    predecessor_context = json.loads(
        store.get_automation_run(predecessor.run_id)["query_context_json"]
    )
    predecessor_context["input_evidence_set_sha256"] = "b" * 64
    predecessor_context["semantic_run_key"] = automation_run_key(
        case_id=case_id,
        observation_fingerprint_sha256=_FINGERPRINT,
        policy_version="trusted-lifecycle-v1",
        mode="historical",
        input_evidence_set_sha256="b" * 64,
    )
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (
            json.dumps(
                predecessor_context,
                separators=(",", ":"),
                sort_keys=True,
            ),
            predecessor.run_id,
        ),
    )
    store.conn.commit()

    with pytest.raises(ValueError, match="automation_predecessor_semantic_identity"):
        kernel.fail_run(
            run_id=running.run_id,
            failure_code="internal_error",
            diagnostics={"failures": 1},
            at="2026-08-25T04:00:00Z",
        )
    assert store.get_automation_run(running.run_id)["status"] == "running"


def test_predecessor_cycle_fails_closed_before_creating_attended_attempt():
    _conn, store, kernel, case_id = _context()
    failed = _reserve(kernel, case_id)
    kernel.fail_run(
        run_id=failed.run_id,
        failure_code="extractor_failed",
        diagnostics={"failures": 1},
        at=_LATER,
    )
    context = json.loads(
        store.get_automation_run(failed.run_id)["query_context_json"]
    )
    context["predecessor_run_id"] = failed.run_id
    store.conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (json.dumps(context, separators=(",", ":"), sort_keys=True), failed.run_id),
    )
    store.conn.commit()
    corrupted_snapshot = store.get_automation_run(failed.run_id)

    with pytest.raises(ValueError, match="automation_predecessor_cycle"):
        _reserve(
            kernel,
            case_id,
            allow_new_attempt=True,
            at="2026-08-25T03:00:00Z",
        )
    assert store.list_automation_runs(case_id) == [corrupted_snapshot]


def test_attended_attempt_does_not_change_policy_or_decision_provenance():
    _conn, store, kernel, case_id = _context()
    first = _reserve(kernel, case_id, policy_version="policy-stable")
    evidence = _evidence("policy-stable")
    first_result = _succeed(
        kernel,
        first,
        evidence=(evidence,),
        facts=(_fact(evidence),),
    )
    first_snapshot = store.get_automation_run(first.run_id)
    second = _reserve(
        kernel,
        case_id,
        policy_version="policy-stable",
        allow_new_attempt=True,
        at="2026-08-25T03:00:00Z",
    )
    second_result = _succeed(
        kernel,
        second,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        at="2026-08-25T04:00:00Z",
    )

    assert store.get_automation_run(first.run_id) == first_snapshot
    assert store.get_automation_run(second.run_id)["policy_version"] == "policy-stable"
    assert (
        first_result.decision_provenance_sha256
        == second_result.decision_provenance_sha256
    )


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
    assert after_context["due_refresh_contract"] == "2026-08-26T00:00:00Z"
    assert {
        key: value
        for key, value in after_context.items()
        if key not in {"due_refresh_contract", "latest_attempt_execution_revision"}
    } == {
        key: value
        for key, value in before_context.items()
        if key != "latest_attempt_execution_revision"
    }
    assert after["status"] == "running"
    assert len(store.list_automation_runs(case_id)) == 1


def test_due_blocked_family_replacement_is_atomic_and_retains_regulator():
    from src.security_lifecycle_fact_kernel import AutomationBlocker
    from src.security_lifecycle_schema import EVIDENCE_SOURCE_FAMILIES

    conn, store, kernel, case_id = _context()
    regulator = _evidence("retained-regulator")
    listing = replace(
        _evidence(
            "stale-listing",
            family="listing_authority",
            adapter="nasdaq_symbol_directory",
            kind="listing_directory_snapshot",
        ),
        source_document_sha256="e" * 64,
    )
    market = _evidence(
        "stale-market",
        family="market_infrastructure",
        adapter="ibkr_contract",
        kind="market_infrastructure_snapshot",
    )
    blocked = _reserve(kernel, case_id)
    kernel.complete_run(
        run_id=blocked.run_id,
        evidence=(regulator, listing, market),
        facts=(_fact(regulator), _fact(listing), _fact(market)),
        blockers=(
            AutomationBlocker(
                code="listing_directory_unavailable",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-08-26T00:00:00Z",
        diagnostics={"listing_requests": 1},
        at=_LATER,
    )
    retry = _reserve(kernel, case_id, at="2026-08-26T00:00:00Z")
    prior = kernel.prior_material(retry.run_id)
    retained_evidence = tuple(
        {**dict(row), "source_locator": json.loads(row["source_locator_json"])}
        for row in prior.evidence
        if row["source_family"] == "regulator"
    )
    retained_ids = {row["evidence_id"] for row in retained_evidence}
    retained_facts = tuple(
        {
            **dict(row),
            "normalized_value": json.loads(row["normalized_value_json"]),
        }
        for row in prior.facts
        if row["evidence_id"] in retained_ids
    )
    refreshed_families = tuple(
        sorted(EVIDENCE_SOURCE_FAMILIES - {"regulator"})
    )
    replacement = replace(
        _evidence(
            "fresh-listing",
            family="listing_authority",
            adapter="nasdaq_symbol_directory",
            kind="listing_directory_snapshot",
        ),
        source_document_sha256="f" * 64,
    )

    def rows(table, order_by):
        return tuple(
            tuple(row)
            for row in conn.execute(
                f"SELECT * FROM {table} WHERE automation_run_id=? ORDER BY {order_by}",
                (retry.run_id,),
            )
        )

    before = {
        "evidence": rows("security_lifecycle_evidence", "evidence_id"),
        "facts": rows("security_lifecycle_automation_facts", "fact_id"),
        "blockers": rows(
            "security_lifecycle_automation_run_blockers",
            "blocker_code",
        ),
    }
    conn.execute(
        "CREATE TRIGGER fail_lifecycle_replacement "
        "BEFORE INSERT ON security_lifecycle_evidence "
        "WHEN NEW.source_family='listing_authority' "
        "BEGIN SELECT RAISE(ABORT,'injected replacement failure'); END"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="injected replacement failure"):
        kernel.complete_run(
            run_id=retry.run_id,
            evidence=(replacement,),
            facts=(_fact(replacement),),
            blockers=(
                AutomationBlocker(
                    code="listing_directory_unavailable",
                    retryable=True,
                    context={"attempts": 2},
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at="2026-08-27T00:00:00Z",
            diagnostics={"listing_requests": 2},
            at="2026-08-26T00:00:00Z",
            retained_evidence=retained_evidence,
            retained_facts=retained_facts,
            refreshed_source_families=refreshed_families,
        )

    assert {
        "evidence": rows("security_lifecycle_evidence", "evidence_id"),
        "facts": rows("security_lifecycle_automation_facts", "fact_id"),
        "blockers": rows(
            "security_lifecycle_automation_run_blockers",
            "blocker_code",
        ),
    } == before

    conn.execute("DROP TRIGGER fail_lifecycle_replacement")
    conn.commit()
    completed = kernel.complete_run(
        run_id=retry.run_id,
        evidence=(replacement,),
        facts=(_fact(replacement),),
        blockers=(
            AutomationBlocker(
                code="listing_directory_unavailable",
                retryable=True,
                context={"attempts": 2},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-08-27T00:00:00Z",
        diagnostics={"listing_requests": 2},
        at="2026-08-26T00:00:00Z",
        retained_evidence=retained_evidence,
        retained_facts=retained_facts,
        refreshed_source_families=refreshed_families,
    )

    final_rows = conn.execute(
        "SELECT evidence_id,source_family FROM security_lifecycle_evidence "
        "WHERE automation_run_id=? ORDER BY source_family,evidence_id",
        (retry.run_id,),
    ).fetchall()
    assert completed.status == "blocked"
    assert [row[1] for row in final_rows] == ["listing_authority", "regulator"]
    assert next(row[0] for row in final_rows if row[1] == "regulator") in retained_ids
    stale_ids = {
        row["evidence_id"]
        for row in prior.evidence
        if row["source_family"] != "regulator"
    }
    assert stale_ids.isdisjoint({row[0] for row in final_rows})


def test_retained_material_requires_explicit_refresh_contract():
    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    fresh = _evidence("fresh-contract")
    fabricated = _evidence("fabricated-retained")

    with pytest.raises(ValueError, match="refreshed_source_families"):
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=(fresh,),
            facts=(_fact(fresh),),
            blockers=(),
            decision_tier="verified_automatic",
            action_readiness="transition_eligible",
            retry_at=None,
            diagnostics={"sec_attempts": 1},
            at=_LATER,
            retained_evidence=(fabricated,),
            retained_facts=(_fact(fabricated),),
            refreshed_source_families=None,
        )

    assert store.get_automation_run(claim.run_id)["status"] == "running"
    assert store.list_evidence(case_id) == []


def test_existing_run_material_requires_explicit_refresh_contract():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    conn, store, kernel, case_id = _context()
    original = _evidence("existing-contract")
    claim = _reserve(kernel, case_id)
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(original,),
        facts=(_fact(original),),
        blockers=(
            AutomationBlocker(
                code="listing_directory_unavailable",
                retryable=True,
                context={},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-08-26T00:00:00Z",
        diagnostics={"listing_requests": 1},
        at=_LATER,
    )
    retry = _reserve(kernel, case_id, at="2026-08-26T00:00:00Z")
    before = tuple(
        tuple(row)
        for row in conn.execute(
            "SELECT * FROM security_lifecycle_evidence "
            "WHERE automation_run_id=? ORDER BY evidence_id",
            (retry.run_id,),
        )
    )
    replacement = _evidence("replacement-without-contract")

    with pytest.raises(ValueError, match="refreshed_source_families"):
        kernel.complete_run(
            run_id=retry.run_id,
            evidence=(replacement,),
            facts=(_fact(replacement),),
            blockers=(
                AutomationBlocker(
                    code="listing_directory_unavailable",
                    retryable=True,
                    context={},
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at="2026-08-27T00:00:00Z",
            diagnostics={"listing_requests": 2},
            at="2026-08-26T00:00:00Z",
            refreshed_source_families=None,
        )

    after = tuple(
        tuple(row)
        for row in conn.execute(
            "SELECT * FROM security_lifecycle_evidence "
            "WHERE automation_run_id=? ORDER BY evidence_id",
            (retry.run_id,),
        )
    )
    assert after == before
    assert store.get_automation_run(retry.run_id)["status"] == "running"


def test_massive_credential_blocker_cannot_be_persisted_as_retryable():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)

    with pytest.raises(ValueError, match="blocker_retryable"):
        kernel.complete_run(
            run_id=claim.run_id,
            evidence=(),
            facts=(),
            blockers=(
                AutomationBlocker(
                    code="massive_credential_missing",
                    retryable=True,
                    context={"provider": "massive"},
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at="2026-08-26T00:00:00Z",
            diagnostics={"listing_requests": 0},
            at=_LATER,
        )

    assert store.get_automation_run(claim.run_id)["status"] == "running"


def test_legacy_retryable_massive_blocker_requires_attended_new_attempt():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(),
        facts=(),
        blockers=(
            AutomationBlocker(
                code="massive_credential_missing",
                retryable=False,
                context={"provider": "massive"},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at=None,
        diagnostics={"listing_requests": 0},
        at=_LATER,
    )
    conn.execute(
        "UPDATE security_lifecycle_automation_run_blockers SET retryable=1 "
        "WHERE automation_run_id=? AND blocker_code='massive_credential_missing'",
        (claim.run_id,),
    )
    conn.execute(
        "UPDATE security_lifecycle_automation_runs SET retry_at=? WHERE run_id=?",
        ("2026-08-26T00:00:00Z", claim.run_id),
    )
    conn.commit()
    legacy_snapshot = store.get_automation_run(claim.run_id)

    unattended = _reserve(kernel, case_id, at="2026-08-26T00:00:00Z")

    assert unattended.should_execute is False
    assert unattended.run_id == claim.run_id
    assert store.get_automation_run(claim.run_id) == legacy_snapshot

    attended = _reserve(
        kernel,
        case_id,
        at="2026-08-26T00:00:00Z",
        allow_new_attempt=True,
    )
    assert attended.should_execute is True
    assert attended.run_id != claim.run_id
    attended_context = json.loads(
        store.get_automation_run(attended.run_id)["query_context_json"]
    )
    assert attended_context["predecessor_run_id"] == claim.run_id
    assert store.get_automation_run(claim.run_id) == legacy_snapshot


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


def test_legacy_run_without_material_indexes_uses_its_complete_persisted_set():
    from src.security_lifecycle_fact_kernel import (
        persisted_decision_evidence_ids,
        persisted_decision_provenance_sha256,
    )

    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence("legacy-material-index")
    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    persisted_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_evidence "
        "WHERE automation_run_id=?",
        (claim.run_id,),
    ).fetchone()[0]
    context = json.loads(store.get_automation_run(claim.run_id)["query_context_json"])
    context.pop("material_evidence_ids")
    context.pop("terminal_evidence_ids")
    conn.execute(
        "UPDATE security_lifecycle_automation_runs SET query_context_json=? "
        "WHERE run_id=?",
        (
            json.dumps(context, separators=(",", ":"), sort_keys=True),
            claim.run_id,
        ),
    )
    conn.commit()

    assert persisted_decision_evidence_ids(conn, claim.run_id) == (persisted_id,)
    assert persisted_decision_provenance_sha256(conn, claim.run_id) == (
        result.decision_provenance_sha256
    )
    recheck = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-26T00:00:00Z",
        execution_owner_id="legacy-material-owner",
    )
    prior = kernel.prior_material(recheck.run_id)
    assert {row["evidence_id"] for row in prior.evidence} == {persisted_id}
    assert {row["evidence_id"] for row in prior.facts} == {persisted_id}


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


def test_fail_run_rejects_succeeded_run_with_current_automation_assessment():
    conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
    evidence = _evidence()
    result = _succeed(kernel, claim, evidence=(evidence,), facts=(_fact(evidence),))
    persisted_evidence_id = store.list_evidence(case_id)[0]["evidence_id"]
    store.create_assessment(
        case_id=case_id,
        relevance="direct_tracked_security",
        confidence="high",
        author="automation",
        conclusion="The deterministic evidence confirms a symbol change.",
        impact_summary="The tracked symbol requires review.",
        outcomes=("symbol_changed",),
        citations=(
            {
                "reference_kind": "observation",
                "cited_content_sha256": _FINGERPRINT,
            },
            {
                "reference_kind": "evidence",
                "evidence_id": persisted_evidence_id,
            },
        ),
        observation_fingerprint_sha256=_FINGERPRINT,
        automation_method="deterministic_rule",
        automation_run_id=claim.run_id,
        rule_id="lifecycle.simple_symbol_continuation",
        rule_version="1",
        decision_provenance_sha256=result.decision_provenance_sha256,
        at=_LATER,
    )

    with pytest.raises(ValueError, match="automation_run_has_current_assessment"):
        kernel.fail_run(
            run_id=claim.run_id,
            failure_code="internal_error",
            diagnostics={"failures": 1},
            at="2026-08-25T03:00:00Z",
        )

    persisted = store.get_automation_run(claim.run_id)
    assert persisted["status"] == "succeeded"
    assert persisted["failure_code"] is None
    conn.close()


@pytest.mark.parametrize(
    "value",
    (
        {
            "attempt_count": 1,
            "code": "provider_private_error",
            "failed_at": "2026-08-25T01:00:00Z",
            "retry_not_before": "2026-08-25T01:15:00Z",
        },
        {
            "attempt_count": 1,
            "code": "finalization_failed",
            "failed_at": "2026-08-25T01:00:00Z",
            "retry_not_before": "2026-08-25T01:15:00Z",
            "detail": "must not persist",
        },
        {
            "attempt_count": 0,
            "code": "finalization_failed",
            "failed_at": "2026-08-25T01:00:00Z",
            "retry_not_before": "2026-08-25T01:15:00Z",
        },
        {
            "attempt_count": 1,
            "code": "finalization_failed",
            "failed_at": "2026-08-25T01:00:00Z",
            "retry_not_before": None,
        },
        {
            "attempt_count": 4,
            "code": "finalization_failed",
            "failed_at": "2026-08-25T01:00:00Z",
            "retry_not_before": "2026-08-25T07:00:00Z",
        },
    ),
)
def test_terminal_finalization_failure_validator_is_closed(value):
    from src.security_lifecycle_fact_kernel import (
        normalize_terminal_finalization_failure,
    )

    with pytest.raises(ValueError, match="terminal_finalization_failure"):
        normalize_terminal_finalization_failure(value)


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

    with pytest.raises(ValueError, match="execution_owner_id"):
        kernel.reserve_readiness_recheck(
            run_id=claim.run_id,
            due_at="2026-08-26T00:00:00Z",
            at="2026-08-26T00:00:00Z",
            execution_owner_id="invalid owner",
        )
    assert store.get_automation_run(claim.run_id)["status"] == "succeeded"
    assert kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-25T23:59:59Z",
        execution_owner_id="early-readiness-owner",
    ).should_execute is False
    assert json.loads(store.get_automation_run(claim.run_id)["query_context_json"])[
        "execution_owner_id"
    ] == "test-kernel-owner"
    recheck = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-26T00:00:00Z",
        execution_owner_id="due-readiness-owner",
    )
    assert recheck.should_execute is True
    assert json.loads(store.get_automation_run(claim.run_id)["query_context_json"])[
        "execution_owner_id"
    ] == "due-readiness-owner"
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
    prior = kernel.prior_material(claim.run_id)
    retained_evidence, retained_facts = _rehydrated_prior_material(prior)
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
        retained_evidence=retained_evidence,
        retained_facts=retained_facts,
        refreshed_source_families=("market_infrastructure",),
    )

    assert second.evidence_count == 2
    assert second.fact_count == 2
    assert second.decision_provenance_sha256 != first.decision_provenance_sha256
    assert conn.execute(
        "SELECT count(*) FROM security_lifecycle_assessment_evidence "
        "WHERE assessment_id=?",
        (assessment_id,),
    ).fetchone()[0] == 2


def test_readiness_recheck_replaces_active_family_and_keeps_cited_history():
    conn, store, kernel, case_id = _context()
    original = _evidence("append-original")
    claim = _reserve(kernel, case_id)
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(original,),
        facts=(_fact(original),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    persisted_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_evidence "
        "WHERE automation_run_id=?",
        (claim.run_id,),
    ).fetchone()[0]
    assessment_id = store.create_assessment(
        case_id=case_id,
        relevance="direct_tracked_security",
        confidence="high",
        author="human",
        conclusion="Preserve the evidence used by this assessment.",
        impact_summary="The readiness recheck may add newer evidence.",
        outcomes=("symbol_changed",),
        citations=(
            {
                "reference_kind": "observation",
                "cited_content_sha256": _FINGERPRINT,
            },
            {"reference_kind": "evidence", "evidence_id": persisted_id},
        ),
        observation_fingerprint_sha256=_FINGERPRINT,
        at=_LATER,
    )
    retry = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-26T00:00:00Z",
        execution_owner_id="append-readiness-owner",
    )
    fresh = _evidence("append-fresh")

    result = kernel.complete_run(
        run_id=retry.run_id,
        evidence=(fresh,),
        facts=(_fact(fresh),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics={"sec_attempts": 2},
        at="2026-08-26T00:01:00Z",
        refreshed_source_families=("regulator",),
    )

    assert result.evidence_count == 1
    assert result.fact_count == 1
    assert conn.execute(
        "SELECT evidence_id FROM security_lifecycle_assessment_evidence "
        "WHERE assessment_id=? AND reference_kind='evidence'",
        (assessment_id,),
    ).fetchone()[0] == persisted_id
    assert conn.execute(
        "SELECT COUNT(*) FROM security_lifecycle_evidence "
        "WHERE automation_run_id=?",
        (retry.run_id,),
    ).fetchone()[0] == 2
    assert "readiness_recheck_due_at" not in json.loads(
        store.get_automation_run(retry.run_id)["query_context_json"]
    )


def test_due_blocked_retry_rejects_fresh_rows_without_family_ownership():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    original = _evidence("blocked-append-original")
    claim = _reserve(kernel, case_id)
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(original,),
        facts=(_fact(original),),
        blockers=(
            AutomationBlocker(
                code="listing_directory_unavailable",
                retryable=True,
                context={},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-08-26T00:00:00Z",
        diagnostics={"listing_requests": 1},
        at=_LATER,
    )
    retry = _reserve(kernel, case_id, at="2026-08-26T00:00:00Z")
    fresh = _evidence("blocked-append-fresh")

    with pytest.raises(ValueError, match="refreshed_source_families"):
        kernel.complete_run(
            run_id=retry.run_id,
            evidence=(fresh,),
            facts=(_fact(fresh),),
            blockers=(),
            decision_tier="verified_automatic",
            action_readiness="transition_eligible",
            retry_at=None,
            diagnostics={"sec_attempts": 1},
            at="2026-08-26T00:01:00Z",
            refreshed_source_families=(),
        )

    assert store.get_automation_run(retry.run_id)["status"] == "running"


def test_refresh_contract_rejects_an_unowned_prior_material_row():
    _conn, store, kernel, case_id = _context()
    first = _evidence("append-complete-first")
    second = _evidence("append-complete-second")
    claim = _reserve(kernel, case_id)
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(first, second),
        facts=(_fact(first), _fact(second)),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    retry = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-26T00:00:00Z",
        execution_owner_id="append-complete-owner",
    )
    prior = kernel.prior_material(retry.run_id)
    retained_evidence, retained_facts = _rehydrated_prior_material(prior)
    kept_ids = {retained_evidence[0]["evidence_id"]}

    with pytest.raises(ValueError, match="unowned_existing_source_family"):
        kernel.complete_run(
            run_id=retry.run_id,
            evidence=(),
            facts=(),
            blockers=(),
            decision_tier="verified_automatic",
            action_readiness="transition_eligible",
            retry_at=None,
            diagnostics={"sec_attempts": 0},
            at="2026-08-26T00:01:00Z",
            retained_evidence=retained_evidence[:1],
            retained_facts=tuple(
                row for row in retained_facts if row["evidence_id"] in kept_ids
            ),
            refreshed_source_families=(),
        )

    assert store.get_automation_run(retry.run_id)["status"] == "running"


def test_citation_pinned_history_is_not_current_decision_material():
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, kernel, case_id = _context()
    claim = _reserve(
        kernel,
        case_id,
        policy_version=AUTOMATION_POLICY_VERSION,
    )
    old = _evidence("citation-history-old")
    old_decision = _symbol_decision("HAPN", readiness="waiting_effective_date")
    first = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(old,),
        facts=(_fact(old, "HAPN"),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
        terminal_decision=old_decision,
    )
    old_assessment_id = create_automation_assessment(
        store=store,
        run_id=claim.run_id,
        decision=old_decision,
        observation_fingerprint_sha256=_FINGERPRINT,
        at=_LATER,
    )
    old_evidence_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_assessment_evidence "
        "WHERE assessment_id=? AND reference_kind='evidence'",
        (old_assessment_id,),
    ).fetchone()[0]

    retry = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-26T00:00:00Z",
        execution_owner_id="citation-history-owner",
    )
    fresh = _evidence(
        "citation-history-fresh",
        excerpt="The issuer will change its ticker symbol from HAPN to NEXT.",
    )
    fresh_decision = _symbol_decision("NEXT", readiness="waiting_effective_date")

    current = kernel.complete_run(
        run_id=retry.run_id,
        evidence=(fresh,),
        facts=(_fact(fresh, "NEXT"),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 2},
        at="2026-08-26T00:01:00Z",
        terminal_decision=fresh_decision,
        refreshed_source_families=("regulator",),
    )
    new_assessment_id = create_automation_assessment(
        store=store,
        run_id=retry.run_id,
        decision=fresh_decision,
        observation_fingerprint_sha256=_FINGERPRINT,
        at="2026-08-26T00:01:00Z",
    )
    new_evidence_ids = {
        row[0]
        for row in conn.execute(
            "SELECT evidence_id FROM security_lifecycle_assessment_evidence "
            "WHERE assessment_id=? AND reference_kind='evidence'",
            (new_assessment_id,),
        )
    }

    assert first.decision_provenance_sha256 != current.decision_provenance_sha256
    assert current.conflicts == {}
    assert current.source_families == ("regulator",)
    assert current.evidence_count == current.fact_count == 1
    assert old_evidence_id not in new_evidence_ids
    assert len(new_evidence_ids) == 1
    assert (
        store.get_assessment(new_assessment_id)["decision_provenance_sha256"]
        == current.decision_provenance_sha256
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM security_lifecycle_evidence "
        "WHERE automation_run_id=?",
        (retry.run_id,),
    ).fetchone()[0] == 2
    next_recheck = kernel.reserve_readiness_recheck(
        run_id=retry.run_id,
        due_at="2026-08-27T00:00:00Z",
        at="2026-08-27T00:00:00Z",
        execution_owner_id="citation-history-next-owner",
    )
    next_prior = kernel.prior_material(next_recheck.run_id)
    assert {row["evidence_id"] for row in next_prior.evidence} == new_evidence_ids


def test_readiness_blocker_retry_replaces_current_family_without_deleting_citation():
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_fact_kernel import AutomationBlocker
    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, kernel, case_id = _context()
    claim = _reserve(
        kernel,
        case_id,
        policy_version=AUTOMATION_POLICY_VERSION,
    )
    old = _evidence("readiness-blocked-old")
    old_decision = _symbol_decision("HAPN", readiness="waiting_effective_date")
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=(old,),
        facts=(_fact(old, "HAPN"),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="waiting_effective_date",
        retry_at=None,
        diagnostics={"sec_attempts": 1},
        at=_LATER,
        terminal_decision=old_decision,
    )
    assessment_id = create_automation_assessment(
        store=store,
        run_id=claim.run_id,
        decision=old_decision,
        observation_fingerprint_sha256=_FINGERPRINT,
        at=_LATER,
    )
    cited_id = conn.execute(
        "SELECT evidence_id FROM security_lifecycle_assessment_evidence "
        "WHERE assessment_id=? AND reference_kind='evidence'",
        (assessment_id,),
    ).fetchone()[0]

    readiness = kernel.reserve_readiness_recheck(
        run_id=claim.run_id,
        due_at="2026-08-26T00:00:00Z",
        at="2026-08-26T00:00:00Z",
        execution_owner_id="readiness-blocked-owner",
    )
    prior = kernel.prior_material(readiness.run_id)
    preserved_evidence, preserved_facts = _rehydrated_prior_material(prior)
    blocked = kernel.complete_run(
        run_id=readiness.run_id,
        evidence=(),
        facts=(),
        blockers=(
            AutomationBlocker(
                code="sec_rate_limited",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
        decision_tier=None,
        action_readiness=None,
        retry_at="2026-08-27T00:00:00Z",
        diagnostics={"sec_attempts": 1},
        at="2026-08-26T00:01:00Z",
        preserved_evidence=preserved_evidence,
        preserved_facts=preserved_facts,
        refreshed_source_families=(),
    )
    assert blocked.status == "blocked"

    retry = _reserve(
        kernel,
        case_id,
        policy_version=AUTOMATION_POLICY_VERSION,
        at="2026-08-27T00:00:00Z",
    )
    assert retry.run_id == readiness.run_id
    fresh = _evidence(
        "readiness-blocked-fresh",
        excerpt="The issuer will change its ticker symbol from HAPN to NEXT.",
    )
    fresh_decision = _symbol_decision("NEXT", readiness="transition_eligible")
    recovered = kernel.complete_run(
        run_id=retry.run_id,
        evidence=(fresh,),
        facts=(_fact(fresh, "NEXT"),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics={"sec_attempts": 2},
        at="2026-08-27T00:01:00Z",
        terminal_decision=fresh_decision,
        refreshed_source_families=("regulator",),
    )

    assert recovered.status == "succeeded"
    assert recovered.conflicts == {}
    assert conn.execute(
        "SELECT COUNT(*) FROM security_lifecycle_evidence WHERE evidence_id=?",
        (cited_id,),
    ).fetchone()[0] == 1


def test_rowless_due_retry_still_requires_explicit_family_refresh_contract():
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    _conn, store, kernel, case_id = _context()
    claim = _reserve(kernel, case_id)
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
        retry_at="2026-08-26T00:00:00Z",
        diagnostics={"sec_attempts": 1},
        at=_LATER,
    )
    retry = _reserve(kernel, case_id, at="2026-08-26T00:00:00Z")
    fresh = _evidence("rowless-due-refresh")

    with pytest.raises(ValueError, match="refreshed_source_families"):
        kernel.complete_run(
            run_id=retry.run_id,
            evidence=(fresh,),
            facts=(_fact(fresh),),
            blockers=(),
            decision_tier="verified_automatic",
            action_readiness="transition_eligible",
            retry_at=None,
            diagnostics={"sec_attempts": 2},
            at="2026-08-26T00:01:00Z",
            refreshed_source_families=None,
        )

    assert store.get_automation_run(retry.run_id)["status"] == "running"
    completed = kernel.complete_run(
        run_id=retry.run_id,
        evidence=(fresh,),
        facts=(_fact(fresh),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="transition_eligible",
        retry_at=None,
        diagnostics={"sec_attempts": 2},
        at="2026-08-26T00:01:00Z",
        refreshed_source_families=("regulator",),
    )
    assert completed.status == "succeeded"


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
        "execution_owner_id": "test-kernel-owner",
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
        ({"execution_owner_id": "spoofed"}, {}),
        ({"latest_attempt_execution_revision": "spoofed"}, {}),
        ({"predecessor_run_id": "slar_spoofed"}, {}),
        ({"predecessor_failed_run_id": "slar_spoofed"}, {}),
        ({"automatic_retry": {"class": "internal_error"}}, {}),
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


def test_reservation_persists_a_reserved_owner_without_changing_run_identity():
    first_conn, first_store, first_kernel, first_case_id = _context()
    second_conn, second_store, second_kernel, second_case_id = _context()
    try:
        first = _reserve(
            first_kernel,
            first_case_id,
            execution_owner_id="lifecycle-owner-a",
        )
        second = _reserve(
            second_kernel,
            second_case_id,
            execution_owner_id="lifecycle-owner-b",
        )

        first_context = json.loads(
            first_store.get_automation_run(first.run_id)["query_context_json"]
        )
        second_context = json.loads(
            second_store.get_automation_run(second.run_id)["query_context_json"]
        )
        assert first.run_key == second.run_key
        assert first_context["execution_owner_id"] == "lifecycle-owner-a"
        assert second_context["execution_owner_id"] == "lifecycle-owner-b"

        with pytest.raises(ValueError, match="reserved_query_context"):
            _reserve(
                first_kernel,
                first_case_id,
                policy_version="reserved-owner-spoof",
                execution_owner_id="lifecycle-owner-a",
                query_context={"execution_owner_id": "caller-owner"},
            )
    finally:
        first_conn.close()
        second_conn.close()


def test_reconciliation_is_owner_scoped_and_only_terminalizes_running_rows():
    conn, store, kernel, first_case_id = _context()
    second_case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0001409970-26-000132",
        ticker="HAPN",
        at=_AT,
    )
    third_case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0001409970-26-000133",
        ticker="HAPN",
        at=_AT,
    )
    first = _reserve(
        kernel,
        first_case_id,
        execution_owner_id="lifecycle-owner-a",
    )
    second = _reserve(
        kernel,
        second_case_id,
        observation_fingerprint_sha256="b" * 64,
        execution_owner_id="lifecycle-owner-b",
    )
    succeeded = _reserve(
        kernel,
        third_case_id,
        observation_fingerprint_sha256="c" * 64,
        execution_owner_id="lifecycle-owner-c",
    )
    succeeded_evidence = _evidence("succeeded")
    _succeed(
        kernel,
        succeeded,
        evidence=(succeeded_evidence,),
        facts=(_fact(succeeded_evidence),),
    )
    succeeded_before = store.get_automation_run(succeeded.run_id)
    try:
        reconciled = kernel.reconcile_running_runs(
            execution_owner_id="lifecycle-owner-a",
            at=_LATER,
        )

        assert reconciled == (first.run_id,)
        assert store.get_automation_run(first.run_id)["status"] == "failed"
        assert store.get_automation_run(second.run_id)["status"] == "running"
        assert store.get_automation_run(succeeded.run_id) == succeeded_before

        remaining = kernel.reconcile_running_runs(at=_LATER)
        first_after = store.get_automation_run(first.run_id)
        second_after = store.get_automation_run(second.run_id)
        assert remaining == (second.run_id,)
        assert first_after["failure_code"] == "internal_error"
        assert json.loads(first_after["diagnostics_json"]) == {
            "interrupted_execution": 1,
        }
        assert second_after["status"] == "failed"
        assert second_after["failure_code"] == "internal_error"
        assert store.get_automation_run(succeeded.run_id) == succeeded_before
    finally:
        conn.close()
