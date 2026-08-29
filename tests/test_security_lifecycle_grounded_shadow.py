"""Offline shadow evaluation for the four reviewed lifecycle cases."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


_FIXTURES = Path(__file__).parent / "fixtures"
_MANIFEST = _FIXTURES / "security_lifecycle_grounded_shadow.json"
_SOURCE_SHAPES = _FIXTURES / "security_lifecycle_automation_sec.json"
_LEGACY = _FIXTURES / "security_lifecycle_legacy_37.json"
_AT = "2026-08-25T01:02:03.123456Z"


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _listing_material(name: str, snapshot: dict) -> tuple[dict, tuple[dict, ...]]:
    evidence_id = f"listing-{name.lower()}"
    evidence = {
        "evidence_id": evidence_id,
        "source_family": "listing_authority",
        "source_locator": {
            "locator_kind": "listing_directory_snapshot",
            "adapter": snapshot["adapter"],
            "candidate_ticker": snapshot["candidate_ticker"],
            "expected_active_state": snapshot["expected_active_state"],
            "market": snapshot["market"],
            "listing_status": "active" if snapshot["active"] else "not_found",
        },
        "retrieved_at": _AT,
    }
    facts = tuple(
        {
            "evidence_id": evidence_id,
            "fact_type": fact_type,
            "normalized_value": value,
        }
        for fact_type, value in (
            ("successor_ticker", snapshot["candidate_ticker"]),
            ("destination_venue", snapshot["venue"]),
            ("security_class", snapshot["security_class"]),
            ("issuer_cik", snapshot["issuer_cik"]),
        )
    )
    return evidence, facts


def _submissions(case: dict) -> dict:
    filing = case["filing"]
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
    return {
        "cik": case["observation"]["cik"],
        "name": case["observation"]["issuer_name"],
        "filings": {
            "recent": {field: [filing.get(field, "")] for field in fields}
        },
    }


class _SecTransport:
    def __init__(self, case: dict):
        self.case = case

    def get_json(self, _url: str, *, budget=None, **_kwargs):
        payload = _submissions(self.case)
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        if budget is not None:
            budget.reserve_attempt()
            budget.record_body(len(encoded))
        return payload

    def get(self, _url: str, *, budget=None, max_bytes=None, **_kwargs):
        from data_sources.sec_transport import SecResponse

        body = self.case["document"].encode()
        if budget is not None:
            budget.reserve_document(max_bytes or budget.max_document_bytes)
            budget.reserve_attempt()
            budget.record_body(len(body))
        return SecResponse(200, body, "utf-8")


class _IbkrGateway:
    def __init__(self, snapshot: dict, request_count: int):
        detail = SimpleNamespace(
            contract=SimpleNamespace(
                symbol=snapshot["symbol"],
                localSymbol=snapshot["local_symbol"],
                conId=snapshot["con_id"],
                secType=snapshot["security_type"],
                primaryExchange=snapshot["primary_exchange"],
                currency=snapshot["currency"],
            ),
            validExchanges=snapshot["valid_exchanges"],
        )
        self.responses = [[detail] for _ in range(request_count)]
        self.requests = 0

    def isConnected(self):
        return True

    def reqContractDetails(self, _contract):
        self.requests += 1
        return self.responses.pop(0)

    def reqMktData(
        self,
        _contract,
        _generic_tick_list,
        _snapshot,
        _regulatory_snapshot,
    ):
        self.requests += 1
        return SimpleNamespace(
            marketDataType=1,
            last=12.57,
            time=datetime.fromisoformat("2026-08-25T01:01:00+00:00"),
        )

    def sleep(self, _seconds):
        return None


@contextmanager
def _ibkr_lock(_timeout: float):
    yield


def _shadow(name: str):
    from src.security_lifecycle_decision_policy import evaluate_automation_decision
    from src.security_lifecycle_ibkr_evidence import (
        contract_snapshot_facts,
        read_ibkr_contract_evidence,
    )
    from src.security_lifecycle_sec_evidence import (
        build_identity_context,
        collect_sec_evidence,
    )

    source_case = _payload(_SOURCE_SHAPES)["cases"][name]
    manifest_case = _payload(_MANIFEST)["cases"][name]
    context = build_identity_context(
        case_id=source_case["case_id"],
        observation=source_case["observation"],
        ticker_aliases=source_case["aliases"],
        ibkr_conids=source_case["conids"],
    )
    sec = collect_sec_evidence(
        context=context,
        transport=_SecTransport(source_case),
        retrieved_at=_AT,
    )
    evidence = list(sec.evidence)
    facts = list(sec.facts)
    listing_evidence, listing_facts = _listing_material(
        name, manifest_case["listing_snapshot"]
    )
    evidence.append(listing_evidence)
    facts.extend(listing_facts)
    snapshot = manifest_case["market_snapshot"]
    if snapshot is not None:
        request_count = len(context.ibkr_conids) + len(context.ticker_aliases)
        gateway = _IbkrGateway(snapshot, request_count)
        market = read_ibkr_contract_evidence(
            gateway=gateway,
            gateway_lock=_ibkr_lock,
            context=context,
            retrieved_at=_AT,
        )
        regulator_successors = tuple(
            fact.value for fact in sec.facts if fact.fact_type == "successor_ticker"
        )
        evidence.extend(market.evidence)
        facts.extend(
            fact
            for row in market.evidence
            for fact in contract_snapshot_facts(
                row,
                regulator_successors=regulator_successors,
            )
        )

    preview_calls = []

    def preview(request):
        preview_calls.append(dict(request))
        raise AssertionError("grounded cases must not request a ticker transition")

    decision = evaluate_automation_decision(
        case={
            "case_id": source_case["case_id"],
            "ticker": source_case["observation"]["ticker"],
            "cik": source_case["observation"]["cik"],
            "issuer_name": source_case["observation"]["issuer_name"],
            "filing_date": source_case["observation"]["filing_date"],
            "event_kinds": source_case["observation"]["event_kinds"],
        },
        evidence=evidence,
        facts=facts,
        current_date="2026-08-25",
        active_sources=("manual_lists",),
        transition_preview=preview,
    )
    return decision, sec, tuple(evidence), tuple(facts), preview_calls


def _assert_expected(name: str) -> None:
    expected = _payload(_MANIFEST)["cases"][name]["expected"]
    decision, sec, evidence, facts, preview_calls = _shadow(name)
    assert sec.blockers == ()
    assert evidence
    assert facts
    assert decision.decision_tier == expected["decision_tier"]
    assert decision.action_readiness == expected["action_readiness"]
    assert decision.outcomes == tuple(expected["outcomes"])
    assert decision.rule_id == expected["rule_id"]
    assert decision.successor_ticker == expected["successor_ticker"]
    assert decision.transition_requested is expected["transition_requested"]
    assert preview_calls == []


def test_shadow_manifest_binds_reviewed_case_identity_and_discloses_a_to_b_n1():
    manifest = _payload(_MANIFEST)
    legacy_rows = _payload(_LEGACY)["rows"]
    actual = {
        (
            row["ticker"],
            row["cik"],
            row["source_ref"],
            row["evidence_url"],
            row["event_type"],
        )
        for row in legacy_rows
    }
    for ticker, case in manifest["cases"].items():
        for row in case["snapshot_rows"]:
            assert (
                ticker,
                row["cik"],
                row["source_ref"],
                row["evidence_url"],
                row["event_type"],
            ) in actual

    assert manifest["source_text_provenance"] == (
        "synthetic_source_shape_not_captured_provider_bytes"
    )
    assert manifest["market_snapshot_provenance"] == (
        "synthetic_ibkr_contract_shape"
    )
    assert manifest["listing_snapshot_provenance"] == (
        "synthetic_nasdaq_directory_shape"
    )
    assert all(case["listing_snapshot"] for case in manifest["cases"].values())
    assert manifest["network_calls"] == 0
    assert manifest["historical_a_to_b_coverage"] == 1
    assert [
        ticker
        for ticker, case in manifest["cases"].items()
        if case["historical_identity_change"]
    ] == ["HAPN"]


def test_hapn_shadow_accepts_symbol_and_venue_change_without_hapn_to_hapn():
    decision, sec, _evidence, _facts, _preview_calls = _shadow("HAPN")
    assert sec.symbol_transitions == (("LC", "HAPN"),)
    _assert_expected("HAPN")
    assert decision.successor_ticker == "HAPN"


def test_qbts_shadow_accepts_venue_transfer_without_symbol_transition():
    decision, sec, _evidence, _facts, _preview_calls = _shadow("QBTS")
    assert sec.symbol_transitions == ()
    _assert_expected("QBTS")
    assert decision.outcomes == ("venue_transfer",)


def test_ccl_shadow_accepts_no_tracked_security_identity_change():
    decision, sec, _evidence, _facts, _preview_calls = _shadow("CCL")
    assert sec.symbol_transitions == ()
    _assert_expected("CCL")
    assert decision.outcomes == ("no_tracked_security_change",)


def test_blbd_shadow_accepts_asset_acquisition_without_registrant_identity_change():
    decision, sec, _evidence, _facts, _preview_calls = _shadow("BLBD")
    assert sec.symbol_transitions == ()
    _assert_expected("BLBD")
    assert decision.outcomes == ("no_tracked_security_change",)
