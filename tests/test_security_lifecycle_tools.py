from __future__ import annotations

import hashlib
import json
import sqlite3


_AT = "2026-08-20T00:00:00Z"


def _listing_locator(**overrides):
    locator = {
        "locator_kind": "listing_directory_snapshot",
        "adapter": "massive_reference",
        "authority": "massive",
        "directory": None,
        "candidate_ticker": "B",
        "expected_active_state": True,
        "listing_status": "active",
        "market": "stocks",
        "primary_exchange": "XNAS",
        "security_type": "CS",
        "issuer_cik": "0000000001",
        "composite_figi": None,
        "delisted_utc": None,
        "source_as_of": "2026-08-28",
        "provider_last_updated_utc": None,
        "snapshot_complete": True,
        "source_document_sha256": "b" * 64,
        "adapter_version": "listing-authority-v1",
    }
    locator.update(overrides)
    return locator


def _seed_all_evidence_families(store, case_id, fingerprint):
    from src.security_lifecycle_fact_kernel import (
        AutomationEvidence,
        AutomationFact,
        SecurityLifecycleFactKernel,
    )

    store.add_evidence(
        case_id=case_id,
        run_id=None,
        kind="manual_text",
        adapter="manual",
        excerpt="Attended issuer note.",
        source_url=None,
        title="Issuer note",
        publisher=None,
        domain=None,
        source_published_at=None,
        retrieved_at=None,
        mime_type="text/plain",
        document_status=None,
        at=_AT,
    )
    kernel = SecurityLifecycleFactKernel(store)
    claim = kernel.reserve_run(
        case_id=case_id,
        observation_fingerprint_sha256=fingerprint,
        policy_version="listing-projection-test-v1",
        mode="historical",
        execution_revision="listing-projection-test-r1",
        execution_owner_id="test-tools-owner",
        query_context={"case_id": case_id, "ticker": "EA"},
        diagnostics={},
        at=_AT,
    )

    def evidence(
        evidence_id,
        source_family,
        adapter,
        kind,
        excerpt,
        *,
        source_url=None,
        source_document_sha256=None,
        source_locator=None,
    ):
        return AutomationEvidence(
            evidence_id=evidence_id,
            source_family=source_family,
            adapter=adapter,
            kind=kind,
            excerpt=excerpt,
            content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
            source_url=source_url,
            title=f"{source_family} fixture",
            publisher=f"{source_family} fixture",
            domain="example.com",
            source_published_at="2026-08-28",
            retrieved_at=_AT,
            source_document_sha256=source_document_sha256,
            source_locator=source_locator or {},
            evidence_dedupe_key=f"projection:{evidence_id}",
        )

    listing_excerpt = json.dumps(
        {"listing_status": "active", "ticker": "B", "secret": "canonical-only"},
        separators=(",", ":"),
        sort_keys=True,
    )
    regulator_excerpt = "EA SEC filing prose."
    rows = (
        evidence(
            "evidence-regulator",
            "regulator",
            "sec_edgar",
            "regulator_excerpt",
            regulator_excerpt,
            source_url="https://www.sec.gov/Archives/example/ea.htm",
            source_document_sha256="a" * 64,
            source_locator={"accession": "0000712515-26-000042"},
        ),
        evidence(
            "evidence-listing",
            "listing_authority",
            "massive_reference",
            "listing_directory_snapshot",
            listing_excerpt,
            source_url="https://api.massive.com/v3/reference/tickers",
            source_document_sha256="b" * 64,
            source_locator=_listing_locator(),
        ),
        evidence(
            "evidence-ibkr",
            "market_infrastructure",
            "ibkr_contract",
            "market_infrastructure_snapshot",
            "IBKR exact contract snapshot.",
        ),
        evidence(
            "evidence-publisher",
            "publisher",
            "internal_news",
            "publisher_excerpt",
            "Legacy publisher reporting.",
        ),
        evidence(
            "evidence-general-web",
            "general_web",
            "hosted_search",
            "hosted_search_citation",
            "Inactive general web result.",
        ),
    )
    kernel.complete_run(
        run_id=claim.run_id,
        evidence=rows,
        facts=(AutomationFact(
            evidence_id="evidence-regulator",
            fact_type="source_ticker",
            normalized_value="EA",
            source_span_start=0,
            source_span_end=2,
            cited_text_sha256=hashlib.sha256(b"EA").hexdigest(),
            extractor_rule_id="projection.fixture",
            extractor_rule_version="1",
        ),),
        blockers=(),
        decision_tier="verified_automatic",
        action_readiness="not_applicable",
        retry_at=None,
        diagnostics={},
        at=_AT,
    )


def _databases(tmp_path, *, include_observation=True):
    from src.security_lifecycle import (
        LifecycleObservation,
        ObservationKind,
        SecurityLifecycleStore,
    )
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    market = sqlite3.connect(market_path)
    market_store = SecurityLifecycleStore(market)
    if include_observation:
        market_store.upsert_observation(
            LifecycleObservation(
                ticker="EA",
                cik="0000712515",
                issuer_name="Electronic Arts Inc.",
                filing_date="2026-08-04",
                source="sec_edgar",
                source_ref="0000712515-26-000042",
                filing_form="8-K",
                filing_items=("2.01",),
                evidence_url="https://www.sec.gov/Archives/example/ea.htm",
                description="Acquisition completed.",
                observed_at=_AT,
                kinds=(ObservationKind("acquisition_completed", "2026-08-04"),),
            )
        )
    market.close()

    profile = sqlite3.connect(profile_path)
    profile_store = SecurityLifecycleInvestigationStore(
        profile,
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:04d}",
    )
    case_id = profile_store.ensure_case(
        source="sec_edgar",
        source_ref="0000712515-26-000042",
        ticker="EA",
        at=_AT,
    )
    return market_path, profile_path, profile, profile_store, case_id


def _configure(monkeypatch, market_path, profile_path, *, sources=None):
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_path))
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    from src.tools import security_lifecycle_tools

    monkeypatch.setattr(
        security_lifecycle_tools,
        "_load_sources_by_ticker",
        lambda: ({"EA": ("manual_lists",)} if sources is None else sources),
    )
    return security_lifecycle_tools


def test_catalog_registry_and_both_generic_bridges_expose_exact_lifecycle_schemas(tmp_path, monkeypatch):
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    from src.agents.openai_agent.tools import create_openai_tools
    from src.tools.data_access import DataAccessLayer
    from src.tools.registry import create_default_registry

    market_path, profile_path, profile, _, _ = _databases(tmp_path)
    try:
        _configure(monkeypatch, market_path, profile_path)
        registry = create_default_registry()
        expected = {
            "list_security_lifecycle_cases": [
                "ticker",
                "workflow_state",
                "source_presence",
                "limit",
            ],
            "get_security_lifecycle_case": ["case_id"],
        }
        for name, parameters in expected.items():
            tool = registry.get(name)
            assert tool is not None
            assert tool.category == "analysis"
            assert tool.requires_dal is False
            assert [item.name for item in tool.parameters] == parameters
        anthropic = {item["name"]: item for item in get_anthropic_tools()}
        openai = {
            item.name.removeprefix("tool_"): item
            for item in create_openai_tools(DataAccessLayer())
        }
        assert expected.keys() <= anthropic.keys()
        assert expected.keys() <= openai.keys()
        for name, parameters in expected.items():
            assert list(anthropic[name]["input_schema"]["properties"]) == parameters
            assert list(openai[name].params_json_schema["properties"]) == parameters
    finally:
        profile.close()


def test_detail_tool_is_local_read_only_and_returns_source_missing_history(tmp_path, monkeypatch):
    market_path, profile_path, profile, store, case_id = _databases(
        tmp_path, include_observation=False
    )
    try:
        store.add_evidence(
            case_id=case_id,
            run_id=None,
            kind="manual_text",
            adapter="manual",
            excerpt="Reviewed issuer context.",
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
        tools = _configure(monkeypatch, market_path, profile_path, sources={})
        payload = tools.get_security_lifecycle_case(case_id)
        assert payload["status"] == "ok"
        assert payload["case"]["source_presence"] == "source_missing"
        assert payload["case"]["evidence"][0]["excerpt"] == "Reviewed issuer context."
        ordinary = tools.list_security_lifecycle_cases()
        assert ordinary["count"] == 0
        assert ordinary["data_integrity"] == {"source_missing_count": 1}
        missing = tools.list_security_lifecycle_cases(
            source_presence="source_missing"
        )
        assert missing["count"] == 1
        assert missing["cases"][0]["case_id"] == case_id
    finally:
        profile.close()


def test_active_case_projection_uses_closed_families_but_preserves_storage(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_investigation import observation_fingerprint
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService

    market_path, profile_path, profile, store, case_id = _databases(tmp_path)
    try:
        service = SecurityLifecycleReadService(
            market_db_path=str(market_path),
            profile_db_path=str(profile_path),
            source_loader=lambda: {"EA": ("manual_lists",)},
        )
        raw_case = service.get_case(case_id)
        _seed_all_evidence_families(
            store,
            case_id,
            observation_fingerprint(raw_case["observation"]),
        )
        tools = _configure(monkeypatch, market_path, profile_path)

        from src.tools.security_lifecycle_tools import (
            _provider_neutral_case,
            project_active_security_lifecycle_case,
        )

        raw_case = service.get_case(case_id)
        raw_listing = next(
            row
            for row in raw_case["evidence"]
            if row["source_family"] == "listing_authority"
        )
        raw_listing["synthetic_surplus"] = "surplus-secret"
        details = (
            project_active_security_lifecycle_case(raw_case),
            _provider_neutral_case(raw_case),
            tools.get_security_lifecycle_case(case_id)["case"],
        )
        expected_listing = {
            "evidence_id": raw_listing["evidence_id"],
            "source_family": "listing_authority",
            "kind": "listing_directory_snapshot",
            "source_url": "https://api.massive.com/v3/reference/tickers",
            "created_at": _AT,
            "listing": {
                "authority": "massive",
                "directory": None,
                "candidate_ticker": "B",
                "listing_status": "active",
                "market": "stocks",
                "primary_exchange": "XNAS",
                "source_as_of": "2026-08-28",
                "provider_last_updated_utc": None,
            },
        }
        for detail in details:
            assert {row["source_family"] for row in detail["evidence"]} == {
                "manual",
                "regulator",
                "listing_authority",
                "market_infrastructure",
            }
            assert detail["evidence_count"] == 4
            assert set(detail["source_family_status"]) <= {
                "regulator",
                "listing_authority",
                "market_infrastructure",
                "manual",
            }
            listing = next(
                row
                for row in detail["evidence"]
                if row["source_family"] == "listing_authority"
            )
            assert listing == expected_listing
            assert "canonical-only" not in json.dumps(detail)
            assert "surplus-secret" not in json.dumps(detail)
            regulator = next(
                row for row in detail["evidence"] if row["source_family"] == "regulator"
            )
            manual = next(
                row for row in detail["evidence"] if row["source_family"] == "manual"
            )
            assert regulator["excerpt"] == "EA SEC filing prose."
            assert manual["excerpt"] == "Attended issuer note."

        listed = tools.list_security_lifecycle_cases()["cases"][0]
        assert listed["evidence_count"] == 4
        assert set(listed["source_family_status"]) <= {
            "regulator",
            "listing_authority",
            "market_infrastructure",
            "manual",
        }
        raw_families = [row["source_family"] for row in store.list_evidence(case_id)]
        assert raw_families.count("publisher") == 1
        assert raw_families.count("general_web") == 1
        assert len(raw_families) == 6
    finally:
        profile.close()


def test_active_case_projection_omits_each_malformed_listing_row_independently():
    from src.tools.security_lifecycle_tools import (
        project_active_security_lifecycle_case,
    )

    regulator = {
        "evidence_id": "regulator-1",
        "source_family": "regulator",
        "kind": "regulator_excerpt",
        "excerpt": "SEC prose remains visible.",
        "created_at": _AT,
    }
    listing = {
        "evidence_id": "listing-1",
        "source_family": "listing_authority",
        "kind": "listing_directory_snapshot",
        "excerpt": '{"secret":"malformed-listing"}',
        "source_locator_json": json.dumps(_listing_locator()),
        "created_at": _AT,
    }
    base = {
        "evidence": [regulator, listing],
        "evidence_count": 2,
        "source_family_status": {"listing_authority": "present"},
    }
    invalid_locators = [
        _listing_locator(authority="arbitrary_provider"),
        _listing_locator(authority={"name": "massive"}),
        _listing_locator(listing_status="delisted"),
        _listing_locator(source_as_of="2026-99-99"),
        {key: value for key, value in _listing_locator().items() if key != "adapter"},
        _listing_locator(secret="must-not-be-forwarded"),
    ]
    for locator in invalid_locators:
        case = {
            **base,
            "evidence": [regulator, {
                **listing,
                "source_locator_json": json.dumps(locator),
            }],
        }
        projected = project_active_security_lifecycle_case(case)
        assert projected["evidence"] == [regulator]
        assert projected["evidence_count"] == 1
        assert "malformed-listing" not in json.dumps(projected)


def test_malformed_stored_listing_isolated_across_list_direct_and_provider_detail(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_investigation import observation_fingerprint
    from src.tools.security_lifecycle_tools import (
        SecurityLifecycleReadService,
        _provider_neutral_case,
        project_active_security_lifecycle_case,
    )

    market_path, profile_path, profile, store, case_id = _databases(tmp_path)
    service = SecurityLifecycleReadService(
        market_db_path=str(market_path),
        profile_db_path=str(profile_path),
        source_loader=lambda: {"EA": ("manual_lists",)},
    )
    try:
        initial = service.get_case(case_id)
        _seed_all_evidence_families(
            store,
            case_id,
            observation_fingerprint(initial["observation"]),
        )
        profile.execute(
            "UPDATE security_lifecycle_evidence SET source_locator_json=? "
            "WHERE source_family='listing_authority'",
            (json.dumps(_listing_locator(listing_status="delisted")),),
        )
        profile.commit()
        tools = _configure(monkeypatch, market_path, profile_path)

        raw = service.get_case(case_id)
        assert raw["evidence_count"] == 6
        assert any(
            row["source_family"] == "listing_authority"
            and "canonical-only" in row["excerpt"]
            for row in raw["evidence"]
        )
        details = (
            project_active_security_lifecycle_case(raw),
            _provider_neutral_case(raw),
            tools.get_security_lifecycle_case(case_id)["case"],
        )
        for detail in details:
            assert {row["source_family"] for row in detail["evidence"]} == {
                "regulator",
                "market_infrastructure",
                "manual",
            }
            assert detail["evidence_count"] == 3
            assert "canonical-only" not in json.dumps(detail)
            assert next(
                row for row in detail["evidence"] if row["source_family"] == "regulator"
            )["excerpt"] == "EA SEC filing prose."
        assert details[1]["truncation"]["evidence"] == {
            "total": 3,
            "returned": 3,
        }
        assert tools.list_security_lifecycle_cases()["cases"][0][
            "evidence_count"
        ] == 3
        assert len(store.list_evidence(case_id)) == 6
    finally:
        profile.close()


def test_case_detail_projects_original_evidence_with_derived_translations(
    tmp_path, monkeypatch
):
    from src.security_lifecycle_translation import (
        EvidenceTranslationResult,
        translate_evidence,
    )

    market_path, profile_path, profile, store, case_id = _databases(tmp_path)
    try:
        evidence_id = store.add_evidence(
            case_id=case_id,
            run_id=None,
            kind="manual_text",
            adapter="manual",
            excerpt="The issuer will trade under symbol EA2.",
            source_url=None,
            title="Issuer notice",
            publisher=None,
            domain=None,
            source_published_at=None,
            retrieved_at=None,
            mime_type="text/plain",
            document_status=None,
            at=_AT,
        )
        translate_evidence(
            store,
            evidence_id=evidence_id,
            locale="zh-Hant",
            translator=lambda _text, _locale: EvidenceTranslationResult(
                translated_text="發行人將以 EA2 代號交易。",
                provider="anthropic",
                model="claude-sonnet-5",
                harness="claude_subscription_structured_output",
            ),
            at=_AT,
        )
        tools = _configure(monkeypatch, market_path, profile_path)

        payload = tools.get_security_lifecycle_case(case_id)
        evidence = next(
            row
            for row in payload["case"]["evidence"]
            if row["evidence_id"] == evidence_id
        )

        assert evidence["excerpt"] == "The issuer will trade under symbol EA2."
        assert evidence["translations"] == [
            {
                "evidence_id": evidence_id,
                "evidence_content_sha256": hashlib.sha256(
                    b"The issuer will trade under symbol EA2."
                ).hexdigest(),
                "locale": "zh-Hant",
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "harness": "claude_subscription_structured_output",
                "translated_at": _AT,
            }
        ]
        assert "translated_text" not in json.dumps(evidence["translations"])
    finally:
        profile.close()


def test_lifecycle_tools_are_in_both_research_driver_allowlists():
    from src.auth_drivers.chatgpt_oauth_driver import _RESEARCH_READONLY_TOOLS as openai
    from src.auth_drivers.claude_code_sdk_driver import _RESEARCH_READONLY_TOOLS as anthropic

    expected = {"list_security_lifecycle_cases", "get_security_lifecycle_case"}
    assert expected <= openai
    assert expected <= anthropic
    assert len(openai) == 15
    assert len(anthropic) == 15


def test_read_service_exposes_derived_final_check_date_in_list_and_detail(
    monkeypatch,
):
    from src.tools import security_lifecycle_tools
    from src.security_lifecycle_investigation import observation_fingerprint

    case = {
        "case_id": "case-final-check",
        "source": "sec_edgar",
        "source_ref": "final-check-ref",
        "ticker": "EA",
        "source_presence": "present",
        "workflow_state": "unresolved",
        "observation": {
            "issuer_name": "Electronic Arts Inc.",
            "filing_date": "2026-04-01",
            "kinds": [],
            "last_observed_at": _AT,
        },
        "automation_runs": [
            {
                "run_id": "run-final-check",
                "status": "blocked",
                "action_readiness": None,
                    "retry_at": None,
                    "updated_at": "2026-08-27T12:00:00Z",
                    "created_at": "2026-08-27T12:00:00Z",
                    "query_context": {
                        "input_evidence_set_sha256": hashlib.sha256(b"").hexdigest(),
                    },
                    "blockers": [
                    {
                        "blocker_code": "sec_evidence_insufficient",
                        "retryable": False,
                        "context": {
                            "monitoring_reason": "not_confirmed_as_of",
                            "as_of": "2026-08-27",
                            "source_deadline": "2026-04-01",
                            "source_deadline_evidence_id": "sle_deadline",
                            "source_deadline_span_start_byte": 0,
                            "source_deadline_span_end_byte": 64,
                            "source_deadline_cited_text_sha256": "a" * 64,
                            "source_deadline_rule_id": (
                                "sec.explicit_transaction_termination_date"
                            ),
                            "source_deadline_rule_version": "4",
                        },
                    }
                ],
            }
        ],
        "automation_facts": [],
        "current_assessment": None,
    }
    case["automation_runs"][0]["observation_fingerprint_sha256"] = (
        observation_fingerprint(case["observation"])
    )
    monkeypatch.setattr(security_lifecycle_tools, "_store_exists", lambda *_: None)
    monkeypatch.setattr(
        security_lifecycle_tools, "_ticker_transitions_by_case", lambda _: {}
    )
    monkeypatch.setattr(
        security_lifecycle_tools,
        "compose_security_lifecycle",
        lambda *_: {"cases": [case]},
    )
    service = security_lifecycle_tools.SecurityLifecycleReadService(
        market_db_path="unused-market.db",
        profile_db_path="unused-profile.db",
        source_loader=lambda: {"EA": ("manual_lists",)},
    )

    listed = service.list_cases()
    detailed = service.get_case("case-final-check")

    assert listed["cases"][0]["disposition_as_of"] == "2026-08-27"
    assert detailed["disposition_as_of"] == "2026-08-27"
    assert detailed["disposition"] == "not_confirmed_yet"
    assert detailed["queue_bucket"] == "history"


def test_new_observation_keeps_old_terminal_run_and_transition_as_activity_only(
    monkeypatch,
):
    from src.tools import security_lifecycle_tools

    def case(case_id, ticker):
        return {
            "case_id": case_id,
            "source": "sec_edgar",
            "source_ref": f"{case_id}-current-observation",
            "ticker": ticker,
            "source_presence": "present",
            "workflow_state": "unresolved",
            "observation": {
                "ticker": ticker,
                "cik": "0000712515",
                "issuer_name": f"{ticker} Current Issuer",
                "filing_date": "2026-08-20",
                "source": "sec_edgar",
                "source_ref": f"{case_id}-current-observation",
                "filing_form": "8-K",
                "filing_items": ["2.01"],
                "evidence_url": "https://www.sec.gov/Archives/current.htm",
                "description": "A newer lifecycle observation.",
                "last_observed_at": "2026-08-27T00:00:00Z",
                "kinds": [
                    {"event_type": "listing_status_review", "effective_date": None}
                ],
            },
            "automation_runs": [
                {
                    "run_id": f"{case_id}-old-run",
                    "observation_fingerprint_sha256": "a" * 64,
                    "status": "blocked",
                    "action_readiness": None,
                    "retry_at": None,
                    "updated_at": "2026-08-26T12:00:00Z",
                    "created_at": "2026-08-26T12:00:00Z",
                    "blockers": [
                        {
                            "blocker_code": "sec_evidence_insufficient",
                            "retryable": False,
                            "context": {
                                "monitoring_reason": "not_confirmed_as_of",
                                "as_of": "2026-08-26",
                            },
                        }
                    ],
                }
            ],
            "automation_facts": [],
            "evidence": [],
            "current_assessment": None,
            "current_acknowledgement": None,
            "assessment_history": [],
            "acknowledgement_history": [],
            "proposals": [],
        }

    run_only = case("case-old-run", "RUN")
    transitioned = case("case-old-transition", "MOVE")
    old_transition = {
        "transition_id": "transition-old",
        "status": "applied",
        "approved_observation_fingerprint_sha256": "a" * 64,
        "approved_preview": {
            "observation_fingerprint_sha256": "a" * 64,
            "evidence_set_sha256": "b" * 64,
        },
        "decision_provenance_sha256": "c" * 64,
        "updated_at": "2026-08-26T12:00:00Z",
    }
    monkeypatch.setattr(security_lifecycle_tools, "_store_exists", lambda *_: None)
    monkeypatch.setattr(
        security_lifecycle_tools,
        "_ticker_transitions_by_case",
        lambda _: {transitioned["case_id"]: old_transition},
    )
    monkeypatch.setattr(
        security_lifecycle_tools,
        "compose_security_lifecycle",
        lambda *_: {"cases": [run_only, transitioned]},
    )
    service = security_lifecycle_tools.SecurityLifecycleReadService(
        market_db_path="unused-market.db",
        profile_db_path="unused-profile.db",
        source_loader=lambda: {"RUN": (), "MOVE": ()},
    )

    result = service.list_cases()
    assert result["queue_counts"] == {
        "attention": 0,
        "history": 0,
        "monitoring": 2,
    }
    assert {
        (row["case_id"], row["queue_bucket"], row["disposition_reason"])
        for row in result["cases"]
    } == {
        ("case-old-run", "monitoring", "awaiting_initial_automation"),
        ("case-old-transition", "monitoring", "awaiting_initial_automation"),
    }
    detail = service.get_case("case-old-transition")
    assert detail["ticker_transition"]["status"] == "applied"
    assert detail["automation_run_count"] == 1


def test_list_tool_is_local_read_only_stably_sorted_and_filters_ticker_prefixes(
    tmp_path, monkeypatch
):
    from src.security_lifecycle import LifecycleObservation, ObservationKind, SecurityLifecycleStore
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore

    market_path, profile_path, profile, _, _ = _databases(tmp_path)
    market = sqlite3.connect(market_path)
    market_store = SecurityLifecycleStore(market)
    market_store.upsert_observation(
        LifecycleObservation(
            ticker="OLD",
            cik=None,
            issuer_name="Older Issuer",
            filing_date="2026-07-01",
            source="sec_edgar",
            source_ref="older-ref",
            filing_form="25-NSE",
            filing_items=(),
            evidence_url="https://www.sec.gov/Archives/example/old.htm",
            description="Listing notice.",
            observed_at=_AT,
            kinds=(ObservationKind("listing_removal_notice", None),),
        )
    )
    market_store.upsert_observation(
        LifecycleObservation(
            ticker="ZETA",
            cik="0001851003",
            issuer_name="Zeta Global Holdings Corp.",
            filing_date="2026-07-15",
            source="sec_edgar",
            source_ref="zeta-ref",
            filing_form="25-NSE",
            filing_items=(),
            evidence_url="https://www.sec.gov/Archives/example/zeta.htm",
            description="Listing notice.",
            observed_at=_AT,
            kinds=(ObservationKind("listing_removal_notice", None),),
        )
    )
    market.close()
    second = SecurityLifecycleInvestigationStore(profile)
    second.ensure_case(
        source="sec_edgar", source_ref="older-ref", ticker="OLD", at=_AT
    )
    second.ensure_case(
        source="sec_edgar", source_ref="zeta-ref", ticker="ZETA", at=_AT
    )
    try:
        tools = _configure(
            monkeypatch,
            market_path,
            profile_path,
            sources={
                "EA": ("manual_lists",),
                "OLD": ("manual_lists",),
                "ZETA": ("manual_lists",),
            },
        )
        payload = tools.list_security_lifecycle_cases(limit=20)
        assert payload["status"] == "ok"
        assert [item["ticker"] for item in payload["cases"]] == [
            "EA",
            "ZETA",
            "OLD",
        ]
        assert all("evidence" not in item for item in payload["cases"])
        assert all("investigation_runs" not in item for item in payload["cases"])
        assert all(item["evidence_count"] == 0 for item in payload["cases"])
        assert payload["queue_counts"] == {
            "attention": 0,
            "monitoring": 3,
            "history": 0,
        }
        assert all(
            item["disposition"] == "not_confirmed_yet"
            and item["queue_bucket"] == "monitoring"
            and item["disposition_reason"] == "awaiting_initial_automation"
            for item in payload["cases"]
        )
        assert tools.list_security_lifecycle_cases(ticker="old", limit=20)["count"] == 1
        for prefix in ("z", "ze", "ZET"):
            filtered = tools.list_security_lifecycle_cases(ticker=prefix, limit=20)
            assert filtered["count"] == 1
            assert [item["ticker"] for item in filtered["cases"]] == ["ZETA"]
        assert tools.list_security_lifecycle_cases(
            workflow_state="unresolved", limit=1
        )["count"] == 3
    finally:
        profile.close()


def test_queue_filter_counts_before_bucket_and_limit_and_composes_with_ticker(
    tmp_path,
    monkeypatch,
):
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService

    service = SecurityLifecycleReadService(
        market_db_path=str(tmp_path / "unused-market.db"),
        profile_db_path=str(tmp_path / "unused-profile.db"),
        source_loader=lambda: {},
    )

    def row(ticker, bucket):
        return {
            "case_id": f"case-{ticker.lower()}",
            "source": "sec_edgar",
            "source_ref": f"ref-{ticker.lower()}",
            "ticker": ticker,
            "source_presence": "present",
            "workflow_state": "unresolved",
            "observation": {
                "issuer_name": ticker,
                "filing_date": _AT[:10],
                "kinds": [],
            },
            "current_assessment": None,
            "current_acknowledgement": None,
            "active_sources": [],
            "source_context": "available",
            "components": {},
            "investigation_runs": [],
            "automation_runs": [],
            "automation_facts": [],
            "evidence": [],
            "assessment_history": [],
            "acknowledgement_history": [],
            "proposals": [],
            "disposition": (
                "exception_required"
                if bucket == "attention"
                else "confirmed_effective"
                if bucket == "history"
                else "not_confirmed_yet"
            ),
            "queue_bucket": bucket,
            "disposition_reason": (
                "source_conflict"
                if bucket == "attention"
                else "resolved_assessment"
                if bucket == "history"
                else "awaiting_initial_automation"
            ),
            "disposition_as_of": None,
            "last_checked_at": None,
            "next_check_at": None,
            "source_family_status": {},
        }

    monkeypatch.setattr(
        service,
        "_cases",
        lambda: [
            row("CONFLICT", "attention"),
            row("PENDING", "monitoring"),
            row("WAITING", "monitoring"),
            row("WATCH", "monitoring"),
            row("DONE", "history"),
            row("ARCHIVED", "history"),
        ],
    )

    result = service.list_cases(queue_bucket="monitoring", limit=2)
    assert [item["ticker"] for item in result["cases"]] == ["PENDING", "WAITING"]
    assert result["count"] == 3
    assert result["queue_counts"] == {
        "attention": 1,
        "monitoring": 3,
        "history": 2,
    }

    filtered = service.list_cases(
        ticker="WA",
        queue_bucket="monitoring",
        limit=20,
    )
    assert [item["ticker"] for item in filtered["cases"]] == ["WAITING", "WATCH"]
    assert filtered["queue_counts"] == {
        "attention": 0,
        "monitoring": 2,
        "history": 0,
    }

    try:
        service.list_cases(queue_bucket="unknown")
    except ValueError as exc:
        assert str(exc) == "queue_bucket"
    else:
        raise AssertionError("unknown queue bucket was accepted")


def test_missing_case_is_typed_without_creating_either_database(tmp_path, monkeypatch):
    market_path = tmp_path / "absent-market.db"
    profile_path = tmp_path / "absent-profile.db"
    tools = _configure(monkeypatch, market_path, profile_path, sources={})
    payload = tools.get_security_lifecycle_case("slc_missing")
    assert payload == {
        "status": "unavailable",
        "error": {
            "code": "security_lifecycle_market_store_unavailable",
            "store": "market",
        },
    }
    assert not market_path.exists()
    assert not profile_path.exists()

    from src.security_lifecycle import SecurityLifecycleStore

    market_path = tmp_path / "market.db"
    market = sqlite3.connect(market_path)
    SecurityLifecycleStore(market)
    market.close()
    profile_path = tmp_path / "profile-without-lifecycle.db"
    profile = sqlite3.connect(profile_path)
    profile.execute("CREATE TABLE unrelated_state (value TEXT)")
    profile.commit()
    profile.close()
    before = profile_path.read_bytes()
    tools = _configure(monkeypatch, market_path, profile_path, sources={})
    payload = tools.list_security_lifecycle_cases()
    assert payload == {
        "status": "unavailable",
        "error": {
            "code": "security_lifecycle_profile_store_unavailable",
            "store": "profile",
        },
    }
    assert profile_path.read_bytes() == before


def test_tool_reads_issue_zero_network_calls(tmp_path, monkeypatch):
    market_path, profile_path, profile, _, case_id = _databases(tmp_path)
    calls: list[object] = []
    monkeypatch.setattr(
        "socket.create_connection",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    try:
        tools = _configure(monkeypatch, market_path, profile_path)
        assert tools.list_security_lifecycle_cases()["status"] == "ok"
        assert tools.get_security_lifecycle_case(case_id)["status"] == "ok"
        assert calls == []
    finally:
        profile.close()


def test_tool_reads_never_write_or_generate_action_proposals(tmp_path, monkeypatch):
    market_path, profile_path, profile, store, case_id = _databases(tmp_path)
    try:
        before = (
            hashlib.sha256(market_path.read_bytes()).hexdigest(),
            hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        )
        tools = _configure(monkeypatch, market_path, profile_path)
        assert tools.get_security_lifecycle_case(case_id)["status"] == "ok"
        after = (
            hashlib.sha256(market_path.read_bytes()).hexdigest(),
            hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        )
        assert after == before
        assert store.list_proposals(case_id) == []
    finally:
        profile.close()


def test_provider_neutral_case_exposes_only_closed_finalization_failure_fields():
    from src.tools.security_lifecycle_tools import _provider_neutral_case

    rendered = _provider_neutral_case(
        {
            "automation_runs": [
                {
                    "run_id": "slar_pending",
                    "created_at": "2026-08-25T12:00:00Z",
                    "status": "succeeded",
                    "query_context": {
                        "case_id": "private-case-context",
                        "terminal_finalization_failure": {
                            "attempt_count": 1,
                            "code": "finalization_failed",
                            "failed_at": "2026-08-25T12:00:00Z",
                            "retry_not_before": "2026-08-25T12:15:00Z",
                        },
                    },
                    "diagnostics": {"private": 1},
                    "blockers": [],
                }
            ],
            "source_family_status": {},
        }
    )

    run = rendered["automation_runs"][0]
    assert run["terminal_finalization_failure"] == {
        "attempt_count": 1,
        "code": "finalization_failed",
        "failed_at": "2026-08-25T12:00:00Z",
        "retry_not_before": "2026-08-25T12:15:00Z",
    }
    assert "query_context" not in run
    assert "diagnostics" not in run
    assert "private-case-context" not in json.dumps(rendered)


def test_tools_return_observation_and_profile_facts_without_provider_fields(tmp_path, monkeypatch):
    from src.tools.security_lifecycle_tools import _provider_neutral_case

    market_path, profile_path, profile, store, case_id = _databases(tmp_path)
    try:
        run_id = store.create_investigation_run(
            case_id=case_id,
            trigger="attended_user",
            adapter="manual",
            query_plan=(),
            at=_AT,
        )
        store.start_investigation_run(run_id, at=_AT)
        store.succeed_investigation_run(
            run_id,
            result_count=0,
            fetch_count=0,
            usage={},
            at=_AT,
        )
        for index in range(25):
            store.add_evidence(
                case_id=case_id,
                run_id=None,
                kind="manual_text",
                adapter="manual",
                excerpt=f"Evidence {index:02d} " + ("x" * 4000),
                source_url=None,
                title=None,
                publisher=None,
                domain=None,
                source_published_at=None,
                retrieved_at=None,
                mime_type="text/plain",
                document_status=None,
                at=f"2026-08-20T00:{index:02d}:00Z",
            )
        tools = _configure(monkeypatch, market_path, profile_path)
        payload = tools.get_security_lifecycle_case(case_id)
        rendered = json.dumps(payload, sort_keys=True)
        assert payload["case"]["issuer_name"] == "Electronic Arts Inc."
        assert payload["case"]["filing_date"] == "2026-08-04"
        assert payload["case"]["kinds"] == [
            {"event_type": "acquisition_completed", "effective_date": "2026-08-04"}
        ]
        assert payload["case"]["investigation_run_count"] == 1
        assert payload["case"]["evidence_count"] == 25
        assert payload["case"]["observation"]["ticker"] == "EA"
        assert payload["case"]["investigation_runs"][0]["status"] == "succeeded"
        assert len(payload["case"]["evidence"]) == 20
        assert max(len(item["excerpt"]) for item in payload["case"]["evidence"]) <= 2000
        assert payload["case"]["truncation"]["evidence"] == {
            "total": 25,
            "returned": 20,
        }
        assert "tavily" not in rendered
        assert "usage_json" not in rendered
        assert "query_plan_json" not in rendered
        assert "api_key" not in rendered

        ascending = list(range(25))
        newest_first = list(reversed(ascending))
        synthetic = _provider_neutral_case(
            {
                "investigation_runs": [
                    {
                        "run_id": f"run-{index:02d}",
                        "created_at": f"2026-08-20T00:{index:02d}:00Z",
                        "adapter": "tavily",
                    }
                    for index in newest_first
                ],
                "evidence": [
                        {
                            "evidence_id": f"evidence-{index:02d}",
                            "source_family": "manual",
                            "created_at": f"2026-08-20T00:{index:02d}:00Z",
                            "excerpt": "evidence",
                        }
                    for index in ascending
                ],
                "assessment_history": [
                    {
                        "assessment_id": f"assessment-{index:02d}",
                        "created_at": f"2026-08-20T00:{index:02d}:00Z",
                    }
                    for index in newest_first
                ],
                "acknowledgement_history": [
                    {
                        "acknowledgement_id": f"acknowledgement-{index:02d}",
                        "acknowledged_at": f"2026-08-20T00:{index:02d}:00Z",
                    }
                    for index in newest_first
                ],
                "proposals": [
                    {
                        "proposal_id": f"proposal-{index:02d}",
                        "created_at": f"2026-08-20T00:{index:02d}:00Z",
                    }
                    for index in ascending
                ],
            }
        )
        for collection, id_field in (
            ("investigation_runs", "run_id"),
            ("evidence", "evidence_id"),
            ("assessment_history", "assessment_id"),
            ("acknowledgement_history", "acknowledgement_id"),
            ("proposals", "proposal_id"),
        ):
            assert [row[id_field] for row in synthetic[collection]] == [
                f"{id_field.removesuffix('_id')}-{index:02d}"
                for index in range(5, 25)
            ]
    finally:
        profile.close()


def test_case_detail_projects_automation_runs_facts_and_typed_blockers(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_fact_kernel import (
        AutomationBlocker,
        AutomationEvidence,
        AutomationFact,
        SecurityLifecycleFactKernel,
    )

    market_path, profile_path, profile, store, case_id = _databases(tmp_path)
    excerpt = "EA may continue under ticker EA2."
    excerpt_digest = hashlib.sha256(excerpt.encode()).hexdigest()
    cited_digest = hashlib.sha256(b"EA2").hexdigest()

    def material(run_name):
        evidence = AutomationEvidence(
            evidence_id=f"evidence-{run_name}",
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
            content_sha256=excerpt_digest,
            source_document_sha256="d" * 64,
            source_locator={"accession": "0000712515-26-000042"},
            evidence_dedupe_key=f"sec:{run_name}",
        )
        fact = AutomationFact(
            evidence_id=evidence.evidence_id,
            fact_type="successor_ticker",
            normalized_value="EA2",
            source_span_start=29,
            source_span_end=32,
            cited_text_sha256=cited_digest,
            extractor_rule_id="sec.symbol_change",
            extractor_rule_version="1",
        )
        return evidence, fact

    try:
        from src.security_lifecycle_investigation import observation_fingerprint
        from src.security_lifecycle import read_market_observations

        fingerprint = observation_fingerprint(
            read_market_observations(str(market_path), limit=None)[0]
        )
        kernel = SecurityLifecycleFactKernel(store)
        blocked = kernel.reserve_run(
            case_id=case_id,
            observation_fingerprint_sha256=fingerprint,
            policy_version=AUTOMATION_POLICY_VERSION,
            mode="live",
            execution_revision="trusted-lifecycle-execution-r1",
            execution_owner_id="test-tools-owner",
            query_context={"case_id": case_id, "adapter": "sec_edgar"},
            diagnostics={},
            at=_AT,
        )
        blocked_evidence, blocked_fact = material("blocked")
        kernel.complete_run(
            run_id=blocked.run_id,
            evidence=(blocked_evidence,),
            facts=(blocked_fact,),
            blockers=(
                AutomationBlocker(
                    code="sec_rate_limited",
                    retryable=True,
                    context={"provider": "sec_edgar"},
                ),
            ),
            decision_tier=None,
            action_readiness=None,
            retry_at="2026-08-21T00:00:00Z",
            diagnostics={"sec_attempts": 2},
            at=_AT,
        )
        succeeded = kernel.reserve_run(
            case_id=case_id,
            observation_fingerprint_sha256=fingerprint,
            policy_version=AUTOMATION_POLICY_VERSION,
            mode="historical",
            execution_revision="trusted-lifecycle-execution-r1",
            execution_owner_id="test-tools-owner",
            query_context={"case_id": case_id, "adapter": "sec_edgar"},
            diagnostics={},
            at="2026-08-20T00:01:00Z",
        )
        succeeded_evidence, succeeded_fact = material("succeeded")
        kernel.complete_run(
            run_id=succeeded.run_id,
            evidence=(succeeded_evidence,),
            facts=(succeeded_fact,),
            blockers=(),
            decision_tier="review_suggested",
            action_readiness="action_blocked",
            retry_at=None,
            diagnostics={"sec_attempts": 1},
            at="2026-08-20T00:01:00Z",
        )
        translated_evidence_id = str(
            profile.execute(
                "SELECT evidence_id FROM security_lifecycle_evidence "
                "WHERE automation_run_id=?",
                (succeeded.run_id,),
            ).fetchone()[0]
        )
        profile.execute(
            "INSERT INTO security_lifecycle_evidence_translations "
            "(evidence_id,evidence_content_sha256,locale,translated_text,provider,"
            "model,harness,translated_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                translated_evidence_id,
                succeeded_evidence.content_sha256,
                "zh-Hant",
                "EA 將以 EA2 延續。",
                "anthropic",
                "claude-sonnet-5",
                "claude_subscription_structured_output",
                "2026-08-20T00:01:30Z",
            ),
        )
        profile.commit()

        assessment_id = store.create_assessment(
            case_id=case_id,
            relevance="direct_tracked_security",
            confidence="high",
            author="human",
            conclusion="EA continues under EA2.",
            impact_summary="Preserve the tracked identity.",
            outcomes=("symbol_changed",),
            citations=(
                {
                    "reference_kind": "observation",
                    "cited_content_sha256": fingerprint,
                },
            ),
            observation_fingerprint_sha256=fingerprint,
            successor_ticker="EA2",
            effective_date="2026-08-25",
            at="2026-08-20T00:02:00Z",
        )
        store.accept_assessment(
            assessment_id,
            observation_fingerprint_sha256=fingerprint,
            acceptance_authority="human",
            at="2026-08-20T00:02:00Z",
        )
        from src.ticker_identity_schema import create_ticker_identity_schema
        from src.ticker_identity_transition import profile_snapshot_sha256

        create_ticker_identity_schema(profile)
        preview = {
            "case_id": case_id,
            "source_ticker": "EA",
            "successor_ticker": "EA2",
        }
        preview["preview_sha256"] = profile_snapshot_sha256(preview)
        empty_snapshot = {
            "keys": {
                "ticker_meta": [],
                "ticker_tags": [],
                "universe_source_memberships": [],
                "watchlist_memberships": [],
            },
            "rows": {
                "ticker_meta": [],
                "ticker_tags": [],
                "universe_source_memberships": [],
                "watchlist_memberships": [],
            },
            "version": 1,
        }
        empty_state_sha256 = hashlib.sha256(
            json.dumps(
                empty_snapshot,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        profile.execute(
            "INSERT INTO ticker_identity_transitions "
            "(transition_id,case_id,assessment_id,proposal_ids_json,"
            "transition_dedupe_key,kind,status,source_ticker,successor_ticker,"
            "execute_on,priority_resolution,unhide_successor,"
            "approved_observation_fingerprint_sha256,"
            "approved_assessment_fingerprint_sha256,approved_preview_sha256,"
            "approved_preview_json,before_snapshot_json,after_snapshot_sha256,"
            "approved_at,updated_at,applied_at,cancelled_at,reversed_at,"
            "approval_authority,automation_policy_version,rule_id,rule_version,"
            "decision_provenance_sha256) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "tit_ea",
                case_id,
                assessment_id,
                "[]",
                "automation:ea",
                "symbol_continuation",
                "applied",
                "EA",
                "EA2",
                "2026-08-25",
                None,
                0,
                fingerprint,
                "a" * 64,
                preview["preview_sha256"],
                json.dumps(preview, sort_keys=True, separators=(",", ":")),
                json.dumps(empty_snapshot, sort_keys=True, separators=(",", ":")),
                empty_state_sha256,
                "2026-08-20T00:03:00Z",
                "2026-08-20T00:03:00Z",
                "2026-08-20T00:03:00Z",
                None,
                None,
                "automation_policy",
                "lifecycle.v1",
                "lifecycle.simple_symbol_continuation",
                "1",
                "c" * 64,
            ),
        )
        profile.execute(
            "INSERT INTO ticker_identity_transition_activity "
            "(activity_id,transition_id,activity_type,source_ticker,successor_ticker,"
            "effective_date,user_owned_changes_json,provider_owned_retained_json,"
            "state_sha256,rule_id,rule_version,decision_provenance_sha256,"
            "occurred_at,acknowledged_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?)",
            (
                "tiact_ea",
                "tit_ea",
                "applied",
                "EA",
                "EA2",
                "2026-08-25",
                '[{"change_type":"watchlist_membership_added","count":1}]',
                '["sa_alpha_picks_current"]',
                empty_state_sha256,
                "lifecycle.simple_symbol_continuation",
                "1",
                "c" * 64,
                "2026-08-20T00:03:00Z",
                "2026-08-20T00:03:00Z",
            ),
        )
        profile.commit()

        tools = _configure(monkeypatch, market_path, profile_path)
        payload = tools.get_security_lifecycle_case(case_id)
        case = payload["case"]
        rendered = json.dumps(
            {
                "automation_runs": case["automation_runs"],
                "automation_facts": case["automation_facts"],
                "ticker_transition": case["ticker_transition"],
            },
            sort_keys=True,
        )

        assert case["automation_run_count"] == 2
        assert case["automation_fact_count"] == 2
        assert case["automation_tier"] == "review_suggested"
        assert case["action_readiness"] == "action_blocked"
        assert case["truncation"]["automation_runs"] == {
            "total": 2,
            "returned": 2,
        }
        assert case["truncation"]["automation_facts"] == {
            "total": 2,
            "returned": 2,
        }
        assert {
            blocker["blocker_code"]
            for run in case["automation_runs"]
            for blocker in run["blockers"]
        } == {"sec_rate_limited"}
        assert all(
            fact["source_family"] == "regulator"
            and fact["normalized_value"] == "EA2"
            and fact["evidence_id"]
            and fact["cited_text_sha256"] == cited_digest
            and "fact_dedupe_key" not in fact
            for fact in case["automation_facts"]
        )
        assert all(
            "adapter" not in evidence and "source_locator_json" not in evidence
            for evidence in case["evidence"]
        )
        translated = next(
            evidence
            for evidence in case["evidence"]
            if evidence["evidence_id"] == translated_evidence_id
        )
        assert translated["translations"] == [
            {
                "evidence_id": translated_evidence_id,
                "evidence_content_sha256": succeeded_evidence.content_sha256,
                "locale": "zh-Hant",
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "harness": "claude_subscription_structured_output",
                "translated_at": "2026-08-20T00:01:30Z",
            }
        ]
        assert case["ticker_transition"]["approval_authority"] == (
            "automation_policy"
        )
        assert case["ticker_transition"]["rule_id"] == (
            "lifecycle.simple_symbol_continuation"
        )
        assert case["ticker_transition"]["reverse_readiness"]["reversible"] is True
        assert case["ticker_transition"]["activity_history"][0] == {
            "activity_id": "tiact_ea",
            "transition_id": "tit_ea",
            "case_id": case_id,
            "activity_type": "applied",
            "source_ticker": "EA",
            "successor_ticker": "EA2",
            "effective_date": "2026-08-25",
            "user_owned_changes": [
                {"change_type": "watchlist_membership_added", "count": 1}
            ],
            "provider_owned_retained": ["sa_alpha_picks_current"],
            "state_sha256": empty_state_sha256,
            "rule_id": "lifecycle.simple_symbol_continuation",
            "rule_version": "1",
            "decision_provenance_sha256": "c" * 64,
            "occurred_at": "2026-08-20T00:03:00Z",
            "acknowledged_at": None,
            "created_at": "2026-08-20T00:03:00Z",
        }
        assert "query_context" not in rendered
        assert "diagnostics" not in rendered
        assert "sec_edgar" not in rendered
        assert "source_locator" not in rendered
        assert "before_snapshot_json" not in rendered
        assert "user_owned_changes_json" not in rendered
    finally:
        profile.close()
