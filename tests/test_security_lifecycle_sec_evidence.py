from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit


_FIXTURE = Path(__file__).parent / "fixtures" / "security_lifecycle_automation_sec.json"
_REAL_SOURCE_ROOT = (
    Path(__file__).parent.parent
    / "docs/superpowers/evidence/2026-08-25-trusted-lifecycle-automation-real-source-canary"
)
_REAL_CASE_ACCESSIONS = {
    "HAPN": "0001409970-26-000087",
    "QBTS": "0001907982-26-000099",
    "CCL": "0001104659-26-057200",
    "BLBD": "0001589526-26-000044",
}


def _case(name: str) -> dict:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert payload["fixture_kind"] == "synthetic_sec_source_shape"
    return payload["cases"][name]


def _submissions(case: dict, *, filings: list[dict] | None = None) -> dict:
    rows = filings or [case["filing"]]
    fields = (
        "form",
        "filingDate",
        "accessionNumber",
        "primaryDocument",
        "primaryDocDescription",
        "items",
        "cik",
        "ticker",
    )
    recent = {field: [row.get(field, "") for row in rows] for field in fields}
    return {
        "cik": case["observation"]["cik"],
        "name": case["observation"]["issuer_name"],
        "filings": {"recent": recent},
    }


class _FixtureTransport:
    def __init__(
        self,
        case: dict,
        *,
        filings: list[dict] | None = None,
        documents: list[tuple[int, str]] | None = None,
    ):
        self.case = case
        self.submissions = _submissions(case, filings=filings)
        self.documents = list(
            documents
            or [(200, case["document"])] * len(filings or [case["filing"]])
        )
        self.calls: list[tuple[str, object]] = []

    def get_json(self, url: str, *, budget=None, **_kwargs):
        encoded = json.dumps(self.submissions, separators=(",", ":")).encode()
        if budget is not None:
            budget.reserve_attempt()
            budget.record_body(len(encoded))
        self.calls.append(("json", budget))
        return self.submissions

    def get(self, url: str, *, budget=None, document=False, max_bytes=None, **_kwargs):
        from data_sources.sec_transport import SecResponse

        assert document is True
        status, document_body = self.documents.pop(0)
        body = document_body.encode()
        if budget is not None:
            budget.reserve_document(max_bytes or budget.max_document_bytes)
            budget.reserve_attempt()
            available = budget.available_body_bytes(max_bytes or len(body))
            if len(body) > available:
                from data_sources.sec_transport import SecTransportFailure

                raise SecTransportFailure("sec_request_budget_exhausted")
            budget.record_body(len(body))
        self.calls.append(("document", budget))
        return SecResponse(status, body, "utf-8")


def _context(name: str):
    from src.security_lifecycle_sec_evidence import build_identity_context

    case = _case(name)
    return build_identity_context(
        case_id=case["case_id"],
        observation=case["observation"],
        ticker_aliases=case["aliases"],
        ibkr_conids=case["conids"],
    )


def _collect(name: str):
    from src.security_lifecycle_sec_evidence import collect_sec_evidence

    case = _case(name)
    transport = _FixtureTransport(case)
    result = collect_sec_evidence(
        context=_context(name),
        transport=transport,
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )
    return case, transport, result


def _real_case(name: str) -> dict:
    legacy = json.loads(
        (
            Path(__file__).parent
            / "fixtures/security_lifecycle_legacy_37.json"
        ).read_text(encoding="utf-8")
    )["rows"]
    accession = _REAL_CASE_ACCESSIONS[name]
    rows = [
        row
        for row in legacy
        if row["ticker"] == name and row["source_ref"] == accession
    ]
    assert rows
    row = rows[0]
    current_ticker = "LC" if name == "HAPN" else name
    items = json.loads(row["filing_items_json"])
    event_kinds = sorted({candidate["event_type"] for candidate in rows})
    primary_document = Path(urlsplit(row["evidence_url"]).path).name
    source_file = f"{name}-{accession}.html"
    return {
        "case_id": f"real-source:{name}:{accession}",
        "observation": {
            "ticker": current_ticker,
            "cik": row["cik"],
            "issuer_name": row["issuer_name"],
            "filing_date": row["filing_date"],
            "source_ref": accession,
            "filing_form": row["filing_form"],
            "filing_items": items,
            "event_kinds": event_kinds,
        },
        "aliases": [current_ticker],
        "conids": [],
        "filing": {
            "form": row["filing_form"],
            "filingDate": row["filing_date"],
            "accessionNumber": accession,
            "primaryDocument": primary_document,
            "primaryDocDescription": row["description"],
            "items": ",".join(items),
            "cik": row["cik"],
            "ticker": current_ticker,
        },
        "document": (
            _REAL_SOURCE_ROOT / "sec-source-bytes" / source_file
        ).read_text(encoding="utf-8"),
    }


def _collect_real(name: str):
    from src.security_lifecycle_sec_evidence import (
        build_identity_context,
        collect_sec_evidence,
    )

    case = _real_case(name)
    context = build_identity_context(
        case_id=case["case_id"],
        observation=case["observation"],
        ticker_aliases=case["aliases"],
        ibkr_conids=case["conids"],
    )
    result = collect_sec_evidence(
        context=context,
        transport=_FixtureTransport(case),
        retrieved_at="2026-08-25T10:27:41.545726Z",
    )
    return case, result


def _values(result, fact_type: str) -> set[str]:
    return {fact.value for fact in result.facts if fact.fact_type == fact_type}


def test_identity_context_uses_cik_aliases_and_bounded_dates_never_ticker_alone():
    from src.security_lifecycle_sec_evidence import select_filing_chain

    context = _context("HAPN")
    assert context.cik == "0001409970"
    assert context.ticker_aliases == ("HAPN", "LC")
    assert context.ibkr_conids == (112233,)
    assert context.primary_start == "2026-05-28"
    assert context.primary_end == "2026-08-11"

    case = _case("HAPN")
    good = dict(case["filing"], ticker="LC")
    wrong_identity = dict(
        case["filing"],
        accessionNumber="0009999999-26-000001",
        cik="0009999999",
        ticker="HAPN",
    )
    selected = select_filing_chain(context, _submissions(case, filings=[wrong_identity, good]))
    assert [item.accession for item in selected.filings] == [good["accessionNumber"]]


def test_chain_uses_primary_window_and_at_most_one_120_day_widening():
    from src.security_lifecycle_sec_evidence import select_filing_chain

    context = _context("HAPN")
    case = _case("HAPN")
    anchor = date.fromisoformat(context.filing_date)

    primary = dict(case["filing"], filingDate=str(anchor + timedelta(days=40)))
    result = select_filing_chain(context, _submissions(case, filings=[primary]))
    assert result.window == "primary"
    assert result.widen_count == 0

    widened = dict(case["filing"], filingDate=str(anchor + timedelta(days=90)))
    result = select_filing_chain(context, _submissions(case, filings=[widened]))
    assert result.window == "widened_120_day"
    assert result.widen_count == 1

    outside = dict(case["filing"], filingDate=str(anchor + timedelta(days=121)))
    result = select_filing_chain(context, _submissions(case, filings=[outside]))
    assert result.filings == ()
    assert result.window == "widened_120_day"
    assert result.widen_count == 1
    assert result.blockers == ("sec_evidence_insufficient",)


def test_chain_admits_only_reviewed_identity_forms_and_same_cik():
    from src.security_lifecycle_sec_evidence import select_filing_chain

    context = _context("HAPN")
    case = _case("HAPN")
    base = case["filing"]

    def row(form, accession, *, items="", cik="0001409970"):
        return dict(
            base,
            form=form,
            accessionNumber=accession,
            primaryDocument=f"{accession}.htm",
            items=items,
            cik=cik,
        )

    rows = [
        row("25-NSE", "a"),
        row("8-K/A", "b", items="3.01"),
        row("8-A12B", "c"),
        row("8-K12B", "d"),
        row("DEFM14A", "e"),
        row("8-K", "f", items="2.01"),
        row("8-K", "g", items="5.02"),
        row("10-K", "h"),
        row("25", "i", cik="0009999999"),
    ]
    selected = select_filing_chain(context, _submissions(case, filings=rows))
    assert {item.accession for item in selected.filings} == {"a", "b", "c", "d", "e", "f"}


def test_primary_documents_emit_bounded_verbatim_evidence_and_exact_cited_facts():
    from src.security_lifecycle_sec_evidence import collect_sec_evidence

    case, transport, result = _collect("HAPN")
    assert result.blockers == ()
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert len(evidence.excerpt.encode("utf-8")) <= 4096
    assert evidence.content_sha256 == hashlib.sha256(evidence.excerpt.encode()).hexdigest()
    assert evidence.document_sha256 == hashlib.sha256(case["document"].encode()).hexdigest()
    assert evidence.source_locator["accession"] == case["filing"]["accessionNumber"]
    assert evidence.source_locator["rule_version"] == "3"
    assert transport.calls[0][1] is transport.calls[1][1]

    for fact in result.facts:
        assert fact.evidence_id == evidence.evidence_id
        cited = evidence.excerpt.encode()[fact.span_start_byte : fact.span_end_byte]
        assert cited.decode() == fact.cited_text
        assert fact.cited_text_sha256 == hashlib.sha256(cited).hexdigest()

    delayed = dict(case)
    delayed["document"] = (
        "<html><body><p>" + ("Background material " * 400) + "</p><p>"
        "CIK 0001409970. The same common stock will transfer from the New York "
        "Stock Exchange to the Nasdaq Global Select Market and begin trading "
        "under the new ticker symbol HAPN, replacing LC, effective June 27, 2026."
        "</p></body></html>"
    )
    delayed_result = collect_sec_evidence(
        context=_context("HAPN"),
        transport=_FixtureTransport(delayed),
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )
    assert _values(delayed_result, "successor_ticker") == {"HAPN"}
    assert all(len(item.excerpt.encode()) <= 4096 for item in delayed_result.evidence)
    assert all("Background material" not in item.excerpt for item in delayed_result.evidence)


def test_sec_adapter_canonicalizes_boundary_excerpt_before_kernel_validation():
    from src.security_lifecycle_fact_kernel import _normalize_evidence
    from src.security_lifecycle_sec_evidence import collect_sec_evidence

    case = _case("HAPN")
    case["document"] = "<html><body>" + ("x" * 4095) + " tail</body></html>"
    result = collect_sec_evidence(
        context=_context("HAPN"),
        transport=_FixtureTransport(case),
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )

    normalized = _normalize_evidence(result.evidence)
    assert len(result.evidence) == 1
    assert len(result.evidence[0].excerpt.encode("utf-8")) == 4095
    assert normalized[0].excerpt == result.evidence[0].excerpt


def test_hapn_fixture_extracts_symbol_and_venue_change_without_a_to_a_transition():
    _case_data, _transport, result = _collect("HAPN")
    assert _values(result, "source_ticker") == {"LC"}
    assert _values(result, "successor_ticker") == {"HAPN"}
    assert _values(result, "source_venue") == {"NYSE"}
    assert _values(result, "destination_venue") == {"NASDAQ"}
    assert _values(result, "effective_date") == {"2026-06-27"}
    assert _values(result, "tracked_security_effect") == {"symbol_and_venue_change"}
    assert ("HAPN", "HAPN") not in result.symbol_transitions
    assert result.symbol_transitions == (("LC", "HAPN"),)


def test_first_discovery_emits_declared_successor_absent_from_aliases():
    from src.security_lifecycle_sec_evidence import (
        build_identity_context,
        collect_sec_evidence,
    )

    case = _case("HAPN")
    context = build_identity_context(
        case_id=case["case_id"],
        observation={**case["observation"], "ticker": "LC"},
        ticker_aliases=("LC",),
        ibkr_conids=(),
    )
    result = collect_sec_evidence(
        context=context,
        transport=_FixtureTransport(case),
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )

    assert context.ticker_aliases == ("LC",)
    assert _values(result, "source_ticker") == {"LC"}
    assert _values(result, "successor_ticker") == {"HAPN"}
    assert result.symbol_transitions == (("LC", "HAPN"),)


def test_qbts_fixture_extracts_venue_only_with_unchanged_symbol():
    _case_data, _transport, result = _collect("QBTS")
    assert _values(result, "source_ticker") == {"QBTS"}
    assert _values(result, "successor_ticker") == {"QBTS"}
    assert _values(result, "source_venue") == {"NYSE"}
    assert _values(result, "destination_venue") == {"NASDAQ"}
    assert _values(result, "tracked_security_effect") == {"venue_change_only"}
    assert result.symbol_transitions == ()


def test_ccl_fixture_extracts_no_tracked_security_identity_change():
    _case_data, _transport, result = _collect("CCL")
    assert _values(result, "source_ticker") == {"CCL"}
    assert _values(result, "successor_ticker") == set()
    transaction = next(
        fact.value for fact in result.facts if fact.fact_type == "transaction_structure"
    )
    assert transaction == {
        "kind": "corporate_unification",
        "terms_status": "not_extracted",
    }
    assert _values(result, "tracked_security_effect") == {"no_identity_change"}
    assert result.symbol_transitions == ()


def test_blbd_fixture_extracts_asset_acquisition_without_registrant_change():
    _case_data, _transport, result = _collect("BLBD")
    assert _values(result, "source_ticker") == {"BLBD"}
    assert _values(result, "successor_ticker") == set()
    transaction = next(
        fact.value for fact in result.facts if fact.fact_type == "transaction_structure"
    )
    assert transaction == {
        "kind": "asset_acquisition",
        "terms_status": "not_extracted",
    }
    assert _values(result, "tracked_security_effect") == {
        "asset_acquisition_no_registrant_change"
    }
    assert result.symbol_transitions == ()


def test_real_hapn_first_discovery_extracts_declared_identity_facts():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision

    case, result = _collect_real("HAPN")

    assert case["aliases"] == ["LC"]
    assert _values(result, "issuer_cik") == {"0001409970"}
    assert _values(result, "source_ticker") == {"LC"}
    assert _values(result, "successor_ticker") == {"HAPN"}
    assert _values(result, "source_venue") == {"NYSE"}
    assert _values(result, "destination_venue") == {"NASDAQ"}
    assert _values(result, "effective_date") == {"2026-06-22"}
    assert _values(result, "tracked_security_effect") == {
        "symbol_and_venue_change"
    }
    assert result.symbol_transitions == (("LC", "HAPN"),)

    canary = json.loads(
        (_REAL_SOURCE_ROOT / "canary-report.json").read_text(encoding="utf-8")
    )
    preview_calls = []

    def preview(request):
        preview_calls.append(request)
        return {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": "symbol_continuation",
        }

    decision = evaluate_automation_decision(
        case={"ticker": "LC", "cik": case["observation"]["cik"]},
        evidence=(*result.evidence, *canary["ibkr"]["evidence"]),
        facts=(*result.facts, *canary["ibkr"]["facts"]),
        current_date="2026-08-25",
        active_sources=("manual_lists",),
        transition_preview=preview,
    )
    assert decision.decision_tier == "verified_automatic"
    assert decision.action_readiness == "waiting_market_confirmation"
    assert decision.rule_id == "lifecycle.simple_symbol_continuation"
    assert decision.successor_ticker == "HAPN"
    assert decision.destination_venue == "NASDAQ"
    assert decision.effective_date == "2026-06-22"
    assert decision.transition_requested is False
    assert preview_calls == []


def test_real_qbts_extracts_symbol_continuity_and_venue_transfer():
    _case_data, result = _collect_real("QBTS")

    assert _values(result, "issuer_cik") == {"0001907982"}
    assert _values(result, "source_ticker") == {"QBTS"}
    assert _values(result, "successor_ticker") == {"QBTS"}
    assert _values(result, "source_venue") == {"NYSE"}
    assert _values(result, "destination_venue") == {"NASDAQ"}
    assert _values(result, "effective_date") == {"2026-07-27"}
    assert _values(result, "tracked_security_effect") == {"venue_change_only"}
    assert result.symbol_transitions == ()


def test_real_ccl_unification_resolves_no_tracked_security_change():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision

    case, result = _collect_real("CCL")
    transaction = next(
        fact.value for fact in result.facts if fact.fact_type == "transaction_structure"
    )

    assert _values(result, "issuer_cik") == {"0000815097"}
    assert _values(result, "source_ticker") == {"CCL"}
    assert _values(result, "successor_ticker") == set()
    assert _values(result, "effective_date") == set()
    assert transaction == {
        "kind": "corporate_unification",
        "terms_status": "not_extracted",
    }
    assert _values(result, "tracked_security_effect") == {"no_identity_change"}
    decision = evaluate_automation_decision(
        case={
            "ticker": "CCL",
            "cik": case["observation"]["cik"],
        },
        evidence=result.evidence,
        facts=result.facts,
        current_date="2026-08-25",
        active_sources=("manual_lists",),
        transition_preview=lambda _request: None,
    )
    assert decision.decision_tier == "verified_automatic"
    assert decision.rule_id == "lifecycle.no_identity_change"
    assert decision.transition_requested is False


def test_real_blbd_asset_purchase_prefills_counterparty_without_identity_change():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision

    case, result = _collect_real("BLBD")
    transaction = next(
        fact.value for fact in result.facts if fact.fact_type == "transaction_structure"
    )

    assert _values(result, "issuer_cik") == {"0001589526"}
    assert _values(result, "source_ticker") == {"BLBD"}
    assert _values(result, "successor_ticker") == set()
    assert _values(result, "effective_date") == set()
    assert transaction == {
        "kind": "asset_acquisition",
        "terms_status": "partial",
        "counterparty_name": "Detroit Chassis LLC",
    }
    assert _values(result, "tracked_security_effect") == {
        "asset_acquisition_no_registrant_change"
    }
    decision = evaluate_automation_decision(
        case={
            "ticker": "BLBD",
            "cik": case["observation"]["cik"],
        },
        evidence=result.evidence,
        facts=result.facts,
        current_date="2026-08-25",
        active_sources=("manual_lists",),
        transition_preview=lambda _request: None,
    )
    assert decision.decision_tier == "verified_automatic"
    assert decision.rule_id == "lifecycle.no_identity_change"
    assert decision.transition_requested is False


def test_complete_explicit_form25_chain_emits_terminal_delisting_while_partial_chain_does_not():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision
    from src.security_lifecycle_sec_evidence import (
        build_identity_context,
        collect_sec_evidence,
    )

    base = _case("HAPN")
    form25 = {
        **base["filing"],
        "form": "25-NSE",
        "filingDate": "2026-08-20",
        "accessionNumber": "0001409970-26-000200",
        "primaryDocument": "form25-nse.htm",
        "primaryDocDescription": "Form 25-NSE",
        "items": "",
        "ticker": "DROP",
    }
    document = (
        "<html><body><p>CIK 0001409970. The DROP common stock will be removed "
        "from listing on the Nasdaq Capital Market effective September 1, 2026."
        "</p></body></html>"
    )
    case = {
        **base,
        "filing": form25,
        "document": document,
        "observation": {
            **base["observation"],
            "ticker": "DROP",
            "filing_date": "2026-08-20",
            "source_ref": form25["accessionNumber"],
            "filing_form": "25-NSE",
            "filing_items": [],
            "event_kinds": ["listing_status_review"],
        },
    }
    context = build_identity_context(
        case_id=case["case_id"],
        observation=case["observation"],
        ticker_aliases=("DROP",),
    )
    complete = collect_sec_evidence(
        context=context,
        transport=_FixtureTransport(case),
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )
    assert _values(complete, "tracked_security_effect") == {"terminal_delisting"}
    assert {row.source_locator["filing_chain_complete"] for row in complete.evidence} == {
        True
    }
    decision = evaluate_automation_decision(
        case={"ticker": "DROP", "cik": "0001409970"},
        evidence=complete.evidence,
        facts=complete.facts,
        current_date="2026-08-25",
        active_sources=("manual_lists",),
        transition_preview=lambda _request: None,
    )
    assert decision.rule_id == "lifecycle.terminal_delisting"
    assert decision.action_readiness == "waiting_effective_date"

    second = {
        **form25,
        "accessionNumber": "0001409970-26-000201",
        "primaryDocument": "form25-nse-amendment.htm",
    }
    partial = collect_sec_evidence(
        context=context,
        transport=_FixtureTransport(
            case,
            filings=[form25, second],
            documents=[(200, document), (503, "temporarily unavailable")],
        ),
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )
    assert "sec_document_unavailable" in partial.blockers
    assert _values(partial, "tracked_security_effect") == set()
    assert {row.source_locator["filing_chain_complete"] for row in partial.evidence} == {
        False
    }

    no_date = collect_sec_evidence(
        context=context,
        transport=_FixtureTransport(
            {
                **case,
                "document": (
                    "<html><body><p>CIK 0001409970. The DROP common stock will be "
                    "removed from listing on the Nasdaq Capital Market.</p></body></html>"
                ),
            }
        ),
        retrieved_at="2026-08-25T01:02:03.123456Z",
    )
    assert {row.source_locator["filing_chain_complete"] for row in no_date.evidence} == {
        True
    }
    assert _values(no_date, "tracked_security_effect") == set()


def test_incompatible_current_values_emit_typed_conflicts_not_majority():
    from dataclasses import replace

    from src.security_lifecycle_sec_evidence import detect_fact_conflicts

    _case_data, _transport, result = _collect("HAPN")
    successor = next(f for f in result.facts if f.fact_type == "successor_ticker")
    facts = (*result.facts, successor, replace(successor, value="WRONG"))
    assert detect_fact_conflicts(facts) == {
        "successor_ticker": ("HAPN", "WRONG")
    }


def test_chain_stops_at_shared_request_document_and_byte_budgets():
    from data_sources.sec_transport import SecRequestBudget
    from src.security_lifecycle_sec_evidence import collect_sec_evidence

    case = _case("HAPN")
    duplicate = dict(
        case["filing"],
        accessionNumber="0001409970-26-000132",
        primaryDocument="lc-20260628.htm",
    )
    transport = _FixtureTransport(case, filings=[case["filing"], duplicate])
    budget = SecRequestBudget(
        max_attempts=3,
        max_documents=1,
        max_document_bytes=1_048_576,
        max_total_bytes=12 * 1_048_576,
    )
    result = collect_sec_evidence(
        context=_context("HAPN"),
        transport=transport,
        retrieved_at="2026-08-25T01:02:03.123456Z",
        budget=budget,
    )
    assert result.blockers == ("sec_request_budget_exhausted",)
    assert len(result.evidence) == 1
    assert [kind for kind, _budget in transport.calls] == ["json", "document"]
    assert {id(shared) for _kind, shared in transport.calls} == {id(budget)}


def test_explicit_outside_date_is_hash_cited_and_conflicts_fail_closed():
    from src.security_lifecycle_sec_evidence import collect_sec_evidence

    case = _case("BLBD")
    sentence = (
        "The merger agreement may be terminated if the merger is not "
        "consummated by October 15, 2026 (the Outside Date)."
    )
    case["document"] = case["document"].replace(
        "</body>", f"<p>{sentence}</p></body>"
    )
    result = collect_sec_evidence(
        context=_context("BLBD"),
        transport=_FixtureTransport(case),
        retrieved_at="2026-08-26T00:00:00Z",
    )

    assert len(result.source_deadlines) == 1
    deadline = result.source_deadlines[0]
    assert deadline.date == "2026-10-15"
    assert deadline.rule_id == "sec.explicit_transaction_termination_date"
    assert deadline.rule_version == "3"
    assert deadline.cited_text == sentence
    assert hashlib.sha256(deadline.cited_text.encode()).hexdigest() == (
        deadline.cited_text_sha256
    )
    evidence = next(row for row in result.evidence if row.evidence_id == deadline.evidence_id)
    cited = evidence.excerpt.encode()[deadline.span_start_byte : deadline.span_end_byte]
    assert cited.decode() == sentence

    conflicting = _case("BLBD")
    conflicting["document"] = conflicting["document"].replace(
        "</body>",
        "<p>The transaction may be terminated if it has not closed by "
        "October 15, 2026 (the Outside Date).</p>"
        "<p>The termination date is 2026-11-01.</p></body>",
    )
    rejected = collect_sec_evidence(
        context=_context("BLBD"),
        transport=_FixtureTransport(conflicting),
        retrieved_at="2026-08-26T00:00:00Z",
    )
    assert rejected.source_deadlines == ()
    assert "sec_evidence_insufficient" in rejected.blockers
