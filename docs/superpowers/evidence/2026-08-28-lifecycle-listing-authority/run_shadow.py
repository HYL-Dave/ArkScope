"""Run the fixture-only listing-authority decision shadow."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlencode


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
FIXTURE = ROOT / "tests/fixtures/listing_authority/shadow-cases.json"
sys.path.insert(0, str(ROOT))


def _load_test_helpers():
    path = ROOT / "tests/test_security_lifecycle_decision_policy.py"
    spec = importlib.util.spec_from_file_location("listing_policy_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("listing_policy_helpers_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = _load_test_helpers()


def _load_kernel_test_helpers():
    path = ROOT / "tests/test_security_lifecycle_fact_kernel.py"
    spec = importlib.util.spec_from_file_location("listing_kernel_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("listing_kernel_helpers_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


K = _load_kernel_test_helpers()
LISTING_FIXTURES = ROOT / "tests/fixtures/listing_authority"
AT = "2026-08-28T22:00:00Z"


def _replace(value, old: str, new: str):
    if isinstance(value, str):
        return new if value == old else value
    if isinstance(value, tuple):
        return tuple(_replace(item, old, new) for item in value)
    if isinstance(value, list):
        return [_replace(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _replace(item, old, new) for key, item in value.items()}
    return value


def _fixture(name: str) -> dict:
    if name in {
        "otc_symbol_continuation",
        "terminal_delisting",
        "nasdaq_absence_only",
    }:
        return H._listing_fixture(name)
    if name == "nms_symbol_continuation":
        return _replace(H._listing_fixture(name), "NASDAQ", "NYSE")
    if name == "same_symbol_venue_transfer":
        base = _replace(H._listing_fixture(name), "SAME", "QBTS")
        return _replace(base, "0001409970", "0001907982")
    if name == "historical_hapn":
        base = H._listing_fixture("nms_symbol_continuation")
        base = _replace(base, "OLD", "LC")
        base = _replace(base, "NEW", "HAPN")
        base["case"] = {**base["case"], "ticker": "HAPN"}
        return base
    if name == "historical_ccl":
        base = _replace(H._listing_fixture("completed_acquirer_active"), "KEEP", "CCL")
        base["case"] = {
            **base["case"],
            "ticker": "CCL",
            "issuer_name": "Carnival Corporation & plc",
            "event_kinds": ("acquisition_completed",),
        }
        return base
    if name == "historical_blbd":
        listing, listing_facts = H._active_listing(
            "nasdaq-blbd", "BLBD", cik="0001589526"
        )
        return {
            "case": {
                **H._case(ticker="BLBD", kinds=("merger_agreement",)),
                "cik": "0001589526",
            },
            "evidence": (H._evidence("sec", "regulator"), listing),
            "facts": (
                H._fact("sec", "source_ticker", "BLBD"),
                H._fact("sec", "issuer_cik", "0001589526"),
                H._fact("sec", "security_class", "common_stock"),
                H._fact(
                    "sec",
                    "transaction_structure",
                    {
                        "kind": "asset_acquisition",
                        "terms_status": "complete",
                        "counterparty_name": "Example Assets LLC",
                        "counterparty_ticker": None,
                        "counterparty_cik": None,
                    },
                ),
                H._fact("sec", "tracked_security_effect", "no_identity_change"),
            ) + listing_facts,
        }
    if name == "listing_cik_conflict":
        base = _fixture("nms_symbol_continuation")
        massive, massive_facts = H._active_listing(
            "massive-conflict",
            "NEW",
            adapter="massive_reference",
            market="stocks",
            venue="NASDAQ",
            cik="0000000001",
        )
        return {
            **base,
            "evidence": base["evidence"] + (massive,),
            "facts": base["facts"] + massive_facts,
        }
    raise KeyError(name)


def _read_bound_payload(binding: dict) -> bytes:
    filename = binding.get("filename")
    expected = binding.get("sha256")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise AssertionError("shadow_payload_filename_invalid")
    if not isinstance(expected, str) or len(expected) != 64:
        raise AssertionError("shadow_payload_digest_invalid")
    path = (LISTING_FIXTURES / filename).resolve()
    if path.parent != LISTING_FIXTURES.resolve():
        raise AssertionError("shadow_payload_outside_fixture_root")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise AssertionError(f"shadow_payload_digest_mismatch:{filename}")
    return body


def _identity_context(item: dict):
    from src.security_lifecycle_sec_evidence import IdentityContext

    query = item["listing_query"]
    source_ticker = query["source_ticker"]
    return IdentityContext(
        case_id=f"offline-{item['fixture']}",
        current_ticker=source_ticker,
        ticker_aliases=(source_ticker,),
        ibkr_conids=(),
        cik=query["issuer_cik"],
        issuer_name="Offline fixture issuer",
        filing_date="2026-08-28",
        accession="offline-accession",
        filing_form="8-K",
        filing_items=("3.01",),
        event_kinds=("listing_status_review",),
        primary_start="2026-08-21",
        primary_end="2026-09-04",
        widened_start="2026-07-29",
        widened_end="2026-09-27",
    )


class FakeProductionListingTransport:
    """Production-interface transport backed only by digest-bound repository bytes."""

    def __init__(
        self,
        item: dict,
        *,
        nasdaq_failure: bool = False,
        malformed_massive_binding: dict | None = None,
    ) -> None:
        self.item = item
        self.nasdaq_failure = nasdaq_failure
        self.malformed_massive_binding = malformed_massive_binding
        self.calls: list[str] = []
        self.payloads: list[dict] = []
        self.closed = False

    def _bound_payload(self, binding: dict) -> bytes:
        body = _read_bound_payload(binding)
        digest = hashlib.sha256(body).hexdigest()
        self.payloads.append(
            {
                "filename": binding["filename"],
                "configured_sha256": binding["sha256"],
                "transport_body_sha256": digest,
                "transport_returned_exact_repository_bytes": digest
                == binding["sha256"],
            }
        )
        return body

    def fetch_nasdaq(self, source_url, *, budget):
        from data_sources.listing_authority_transport import (
            NASDAQ_LISTED_URL,
            OTHER_LISTED_URL,
            ListingHttpPayload,
            ListingTransportFailure,
        )

        components = {
            NASDAQ_LISTED_URL: "nasdaq_listed",
            OTHER_LISTED_URL: "other_listed",
        }
        component = components.get(source_url)
        if component is None:
            raise AssertionError("shadow_nasdaq_url")
        self.calls.append(f"nasdaq:{component}")
        budget.reserve_nasdaq_request(source_url)
        if self.nasdaq_failure:
            raise ListingTransportFailure("nasdaq_transport_unavailable")
        bindings = [
            binding
            for binding in self.item["listing_payloads"]
            if binding["adapter"] == "nasdaq_symbol_directory"
            and binding["component"] == component
        ]
        if len(bindings) != 1:
            raise AssertionError(f"shadow_nasdaq_binding:{self.item['id']}:{component}")
        body = self._bound_payload(bindings[0])
        budget.record_nasdaq_body(len(body))
        return ListingHttpPayload(
            source_url=source_url,
            retrieved_at=AT,
            status_code=200,
            content_type="text/plain",
            body=body,
        )

    def fetch_massive_ticker(
        self,
        ticker,
        *,
        expected_active,
        market,
        api_key,
        budget,
    ):
        from data_sources.listing_authority_transport import (
            MASSIVE_TICKERS_URL,
            ListingHttpPayload,
        )

        if api_key != "shadow-fixture-key":
            raise AssertionError("shadow_massive_key_authority")
        active = "true" if expected_active else "false"
        identity = (ticker, expected_active, market)
        self.calls.append(f"massive:{ticker}:{active}:{market}")
        budget.reserve_massive_request(identity)
        if self.malformed_massive_binding is not None:
            binding = self.malformed_massive_binding
        else:
            bindings = [
                binding
                for binding in self.item["listing_payloads"]
                if binding["adapter"] == "massive_reference"
                and binding["expected_active"] is expected_active
                and binding["market"] == market
            ]
            if len(bindings) != 1:
                raise AssertionError(
                    f"shadow_massive_binding:{self.item['id']}:{identity}"
                )
            binding = bindings[0]
        body = self._bound_payload(binding)
        budget.record_massive_body(len(body))
        source_url = f"{MASSIVE_TICKERS_URL}?{urlencode((('ticker', ticker), ('active', active), ('market', market), ('limit', '2')))}"
        return ListingHttpPayload(
            source_url=source_url,
            retrieved_at=AT,
            status_code=200,
            content_type="application/json",
            body=body,
        )

    @staticmethod
    def diagnostics(budget):
        return budget.diagnostics()

    def close(self) -> None:
        self.closed = True


def _session_lookup(
    item: dict,
    *,
    nasdaq_failure: bool = False,
    malformed_massive_binding: dict | None = None,
    repeat: bool = False,
):
    from data_sources.listing_authority_transport import ListingRequestBudget
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession

    transport = FakeProductionListingTransport(
        item,
        nasdaq_failure=nasdaq_failure,
        malformed_massive_binding=malformed_massive_binding,
    )
    budget = ListingRequestBudget.lifecycle()
    require_explicit_inactive = item["fixture"] in {
        "terminal_delisting",
        "nasdaq_absence_only",
    }
    session = ListingAuthoritySession(
        transport=transport,
        budget=budget,
        retrieved_at=AT,
        massive_api_key=(
            None if item["id"] == "MISS" else "shadow-fixture-key"
        ),
    )
    query = item["listing_query"]
    result = session.lookup(
        context=_identity_context(item),
        candidate_tickers=(query["ticker"],),
        require_explicit_inactive=require_explicit_inactive,
    )
    before_repeat = (tuple(transport.calls), dict(budget.diagnostics()))
    repeated_byte_identical = False
    if repeat:
        repeated = session.lookup(
            context=_identity_context(item),
            candidate_tickers=(query["ticker"],),
            require_explicit_inactive=require_explicit_inactive,
        )
        repeated_byte_identical = repeated == result
        assert (tuple(transport.calls), dict(budget.diagnostics())) == before_repeat
    session.close()
    assert transport.closed is True
    return result, {
        "calls": transport.calls,
        "payloads": transport.payloads,
        "diagnostics": dict(budget.diagnostics()),
        "blockers": list(result.blockers),
        "require_explicit_inactive": require_explicit_inactive,
        "lookup_calls": 1 + int(repeat),
        "repeated_lookup_additional_requests": (
            len(transport.calls) - len(before_repeat[0]) if repeat else None
        ),
        "repeated_lookup_byte_identical": (
            repeated_byte_identical if repeat else None
        ),
    }


def _listing_material(item: dict):
    primary, session = _session_lookup(item, repeat=item["id"] == "OTC-A")
    evidence = primary.evidence
    facts = primary.facts
    blockers = primary.blockers
    sessions = [session]
    if item["id"] == "CONFLICT":
        supplemental, supplemental_session = _session_lookup(
            item,
            nasdaq_failure=True,
        )
        massive_ids = {
            row.evidence_id
            for row in supplemental.evidence
            if row.adapter == "massive_reference"
        }
        evidence = evidence + tuple(
            row for row in supplemental.evidence if row.evidence_id in massive_ids
        )
        facts = facts + tuple(
            row for row in supplemental.facts if row.evidence_id in massive_ids
        )
        sessions.append(supplemental_session)
    return evidence, facts, blockers, sessions


def _persist_listing(item: dict, root: Path) -> tuple[tuple[dict, ...], tuple[dict, ...], dict]:
    from src.security_lifecycle_fact_kernel import (
        AutomationBlocker,
        SecurityLifecycleFactKernel,
    )
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore

    name = item["fixture"]
    query = item["listing_query"]
    source_ticker = query["source_ticker"]
    cik = query["issuer_cik"]
    listing_rows, listing_facts, blocker_codes, sessions = _listing_material(item)
    anchor_evidence = ()
    anchor_facts = ()
    if not listing_facts:
        anchor = K._evidence(f"listing-{name}")
        anchor_evidence = (anchor,)
        anchor_facts = (K._fact(anchor),)
    path = root / f"{name}.db"
    connection = sqlite3.connect(path)
    try:
        store = SecurityLifecycleInvestigationStore(
            connection,
            id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
        )
        case_id = store.ensure_case(
            source="sec_edgar",
            source_ref=f"offline-{name}",
            ticker=source_ticker,
            at=AT,
        )
        kernel = SecurityLifecycleFactKernel(store)
        claim = kernel.reserve_run(
            case_id=case_id,
            execution_owner_id="listing-authority-shadow",
            observation_fingerprint_sha256=hashlib.sha256(name.encode()).hexdigest(),
            policy_version="trusted-lifecycle-automation-v4",
            mode="historical",
            execution_revision="trusted-lifecycle-execution-r1",
            query_context={"case_id": case_id, "cik": cik, "aliases": [source_ticker]},
            diagnostics={"listing_records": len(listing_rows)},
            at=AT,
        )
        blockers = tuple(
            AutomationBlocker(
                code=code,
                retryable=code != "massive_credential_missing",
                context={},
            )
            for code in blocker_codes
        )
        completed = kernel.complete_run(
            run_id=claim.run_id,
            evidence=listing_rows + anchor_evidence,
            facts=listing_facts + anchor_facts,
            blockers=blockers,
            decision_tier=None if blockers else "verified_automatic",
            action_readiness=None if blockers else "not_applicable",
            retry_at=(
                "2026-08-29T22:00:00Z"
                if blockers and all(blocker.retryable for blocker in blockers)
                else None
            ),
            diagnostics={"listing_records": len(listing_rows)},
            at=AT,
        )
        assert completed.status == ("blocked" if blockers else "succeeded")
        evidence = tuple(
            row
            for row in store.list_evidence(case_id)
            if row["source_family"] == "listing_authority"
        )
        listing_evidence_ids = {row["evidence_id"] for row in evidence}
        facts = tuple(
            dict(row)
            for row in connection.execute(
                "SELECT * FROM security_lifecycle_automation_facts "
                "WHERE automation_run_id=? ORDER BY fact_id",
                (claim.run_id,),
            )
            if row["evidence_id"] in listing_evidence_ids
        )
        assert len(evidence) == len(listing_rows)
        assert len(facts) == len(listing_facts)
        payloads = [payload for row in sessions for payload in row["payloads"]]
        document_sha256 = sorted(
            {
                json.loads(row["source_locator_json"])["source_document_sha256"]
                for row in evidence
            }
        )
        assert set(document_sha256) <= {
            payload["transport_body_sha256"] for payload in payloads
        }
        return evidence, facts, {
            "strict_record_count": len(listing_rows),
            "kernel_evidence_count": len(evidence),
            "kernel_fact_count": len(facts),
            "kernel_non_listing_anchor_fact_count": len(anchor_facts),
            "kernel_status": completed.status,
            "session_blockers": list(blocker_codes),
            "adapters": sorted({row["adapter"] for row in evidence}),
            "document_sha256": document_sha256,
            "payloads": payloads,
            "sessions": sessions,
        }
    finally:
        connection.close()


def _parser_blocker_probe(item: dict):
    malformed = {
        "adapter": "massive_reference",
        "expected_active": False,
        "market": "stocks",
        "filename": "nasdaqlisted.txt",
        "sha256": "09c5739cb35b5318d62cbb539acdd109bf07569bd0c9a1fa08cf335189a10b4a",
    }
    result, session = _session_lookup(
        item,
        nasdaq_failure=True,
        malformed_massive_binding=malformed,
    )
    assert result.blockers == (
        "listing_directory_unavailable",
        "massive_reference_unavailable",
    )
    return session


def _budget_within_limits(diagnostics: dict) -> bool:
    from data_sources.listing_authority_transport import (
        MAX_MASSIVE_REQUESTS,
        MAX_MASSIVE_TOTAL_BYTES,
        MAX_NASDAQ_REQUESTS,
        MAX_NASDAQ_TOTAL_BYTES,
    )

    return (
        0 <= diagnostics["nasdaq_request_count"] <= MAX_NASDAQ_REQUESTS
        and 0 <= diagnostics["nasdaq_body_bytes"] <= MAX_NASDAQ_TOTAL_BYTES
        and 0 <= diagnostics["massive_request_count"] <= MAX_MASSIVE_REQUESTS
        and 0 <= diagnostics["massive_body_bytes"] <= MAX_MASSIVE_TOTAL_BYTES
    )


def _publisher_injection():
    evidence = (
        H._evidence("publisher-injected", "publisher"),
        H._evidence("web-injected", "general_web"),
    )
    facts = tuple(
        H._fact(evidence_id, fact_type, value)
        for evidence_id in ("publisher-injected", "web-injected")
        for fact_type, value in (
            ("successor_ticker", "WRONG"),
            ("destination_venue", "WRONG"),
            ("issuer_cik", "0000000001"),
        )
    )
    return evidence, facts


def run() -> dict:
    from src.security_lifecycle_decision_policy import evaluate_automation_decision

    authority = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = []
    total_preview_calls = 0
    budget_witnesses = []
    real_session_lookup_calls = 0
    with TemporaryDirectory(prefix="arkscope-listing-shadow-") as directory:
      root = Path(directory)
      for item in authority["cases"]:
        fixture = _fixture(item["fixture"])
        listing_evidence, listing_facts, listing_authority = _persist_listing(item, root)
        for ordinal, session in enumerate(listing_authority["sessions"], start=1):
            real_session_lookup_calls += session["lookup_calls"]
            budget_witnesses.append(
                {
                    "case": item["id"],
                    "session": ordinal,
                    **session["diagnostics"],
                }
            )
        base_evidence = tuple(
            row for row in fixture["evidence"] if row["source_family"] != "listing_authority"
        )
        base_facts = tuple(
            row
            for row in fixture["facts"]
            if row["evidence_id"]
            in {evidence["evidence_id"] for evidence in base_evidence}
        )
        calls = []

        def preview(request):
            calls.append(dict(request))
            return {
                "eligible": True,
                "block_reasons": (),
                "transition_kind": request["transition_kind"],
            }

        kwargs = {
            "case": fixture["case"],
            "evidence": base_evidence + listing_evidence,
            "facts": base_facts + listing_facts,
            "current_date": date(2026, 8, 28),
            "active_sources": ("manual_lists",),
            "transition_preview": preview,
        }
        baseline = evaluate_automation_decision(**kwargs)
        assert len(calls) == item["preview_calls"], (item["id"], calls)
        total_preview_calls += len(calls)

        injected_evidence, injected_facts = _publisher_injection()
        injected_calls = []

        def injected_preview(request):
            injected_calls.append(dict(request))
            return {
                "eligible": True,
                "block_reasons": (),
                "transition_kind": request["transition_kind"],
            }

        injected = evaluate_automation_decision(
            **{
                **kwargs,
                "evidence": base_evidence + listing_evidence + injected_evidence,
                "facts": base_facts + listing_facts + injected_facts,
                "transition_preview": injected_preview,
            }
        )
        assert injected == baseline
        assert injected_calls == calls
        rows.append(
            {
                "case": item["id"],
                "fixture": item["fixture"],
                "decision": asdict(baseline),
                "preview_calls": len(calls),
                "publisher_injection_inert": True,
                "listing_authority": listing_authority,
                "historical_sec_fact_authority": "frozen_repository_helper_no_provider_bytes",
            }
        )

      items_by_id = {item["id"]: item for item in authority["cases"]}
      parser_probe = _parser_blocker_probe(items_by_id["TERM"])
      real_session_lookup_calls += parser_probe["lookup_calls"]
      budget_witnesses.append(
          {
              "case": "PARSER-BLOCKER-PROBE",
              "session": 1,
              **parser_probe["diagnostics"],
          }
      )

    by_id = {row["case"]: row for row in rows}
    assert by_id["HAPN"]["decision"]["transition_requested"] is False
    assert by_id["QBTS"]["decision"]["outcomes"] == ("venue_transfer",)
    assert by_id["CCL"]["decision"]["outcomes"] == (
        "no_tracked_security_change",
    )
    assert by_id["BLBD"]["decision"]["outcomes"] == (
        "no_tracked_security_change",
    )
    assert by_id["NMS-A"]["decision"]["action_readiness"] == "transition_eligible"
    assert by_id["OTC-A"]["decision"]["destination_venue"] == "OTC"
    assert by_id["TERM"]["decision"]["outcomes"] == ("listing_ended",)
    assert by_id["MISS"]["decision"]["action_readiness"] == "waiting_market_confirmation"
    assert by_id["CONFLICT"]["decision"]["decision_issues"] == (
        "listing_authority_conflict",
    )
    term_session = by_id["TERM"]["listing_authority"]["sessions"][0]
    assert term_session["require_explicit_inactive"] is True
    assert "massive:OLD:false:stocks" in term_session["calls"]
    nms_session = by_id["NMS-A"]["listing_authority"]["sessions"][0]
    assert nms_session["require_explicit_inactive"] is False
    assert all(not call.startswith("massive:") for call in nms_session["calls"])
    otc_session = by_id["OTC-A"]["listing_authority"]["sessions"][0]
    assert otc_session["calls"] == [
        "nasdaq:nasdaq_listed",
        "nasdaq:other_listed",
        "massive:NEW:true:stocks",
        "massive:NEW:true:otc",
    ]
    assert otc_session["repeated_lookup_additional_requests"] == 0
    assert otc_session["repeated_lookup_byte_identical"] is True
    miss_session = by_id["MISS"]["listing_authority"]["sessions"][0]
    assert miss_session["blockers"] == ["massive_credential_missing"]
    assert all(
        payload["transport_returned_exact_repository_bytes"]
        for row in rows
        for payload in row["listing_authority"]["payloads"]
    )
    assert all(_budget_within_limits(row) for row in budget_witnesses)
    session_contract = {
        "transport": "fake_production_interface_exact_repository_bytes",
        "session": "real_listing_authority_session",
        "real_session_lookup_calls": real_session_lookup_calls,
        "provider_calls": 0,
        "terminal_requiredness": {
            "candidate_ticker": "OLD",
            "massive_expected_active": False,
            "massive_market": "stocks",
            "require_explicit_inactive": True,
        },
        "nms_requiredness": {
            "candidate_ticker": "NEW",
            "massive_requested": False,
            "require_explicit_inactive": False,
        },
        "otc_fallback_order": otc_session["calls"],
        "deduplication": {
            "case": "OTC-A",
            "repeated_lookup_additional_requests": otc_session[
                "repeated_lookup_additional_requests"
            ],
            "repeated_lookup_byte_identical": otc_session[
                "repeated_lookup_byte_identical"
            ],
        },
        "blocker_normalization": {
            "missing_credential": miss_session["blockers"][0],
            "parser_failure": parser_probe["blockers"][1],
        },
        "request_budgets": {
            "all_within_limits": True,
            "witnesses": budget_witnesses,
        },
    }
    return {
        "schema_version": 3,
        "fixture_authority": str(FIXTURE.relative_to(ROOT)),
        "policy_version": "trusted-lifecycle-automation-v4",
        "case_count": len(rows),
        "transition_preview_calls": total_preview_calls,
        "non_transition_preview_calls": 0,
        "publisher_injection_inert_count": len(rows),
        "listing_material_path": "repository_fixture_bytes_to_fake_production_transport_to_real_listing_authority_session_to_real_fact_kernel_temporary_sqlite_to_policy",
        "listing_payload_bytes": "exact_repository_bytes_no_substitution_mutation_or_reserialization_before_real_session_parser_input",
        "historical_sec_limitation": "Historical SEC facts use frozen repository helpers because this packet contains no provider bytes or calls.",
        "session_contract": session_contract,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = run()
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({"cases": payload["case_count"], "preview_calls": payload["transition_preview_calls"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
