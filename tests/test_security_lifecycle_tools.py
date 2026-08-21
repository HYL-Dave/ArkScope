from __future__ import annotations

import hashlib
import json
import sqlite3


_AT = "2026-08-20T00:00:00Z"


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


def test_lifecycle_tools_are_in_both_research_driver_allowlists():
    from src.auth_drivers.chatgpt_oauth_driver import _RESEARCH_READONLY_TOOLS as openai
    from src.auth_drivers.claude_code_sdk_driver import _RESEARCH_READONLY_TOOLS as anthropic

    expected = {"list_security_lifecycle_cases", "get_security_lifecycle_case"}
    assert expected <= openai
    assert expected <= anthropic
    assert len(openai) == 15
    assert len(anthropic) == 15


def test_list_tool_is_local_read_only_and_stably_sorted(tmp_path, monkeypatch):
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
    market.close()
    second = SecurityLifecycleInvestigationStore(profile)
    second.ensure_case(
        source="sec_edgar", source_ref="older-ref", ticker="OLD", at=_AT
    )
    try:
        tools = _configure(
            monkeypatch,
            market_path,
            profile_path,
            sources={"EA": ("manual_lists",), "OLD": ("manual_lists",)},
        )
        payload = tools.list_security_lifecycle_cases(limit=20)
        assert payload["status"] == "ok"
        assert [item["ticker"] for item in payload["cases"]] == ["EA", "OLD"]
        assert all("evidence" not in item for item in payload["cases"])
        assert all("investigation_runs" not in item for item in payload["cases"])
        assert all(item["evidence_count"] == 0 for item in payload["cases"])
        assert tools.list_security_lifecycle_cases(ticker="old", limit=20)["count"] == 1
        assert tools.list_security_lifecycle_cases(
            workflow_state="unresolved", limit=1
        )["count"] == 2
    finally:
        profile.close()


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


def test_tools_return_observation_and_profile_facts_without_provider_fields(tmp_path, monkeypatch):
    from src.tools.security_lifecycle_tools import _provider_neutral_case

    market_path, profile_path, profile, store, case_id = _databases(tmp_path)
    try:
        run_id = store.create_investigation_run(
            case_id=case_id,
            trigger="attended_user",
            adapter="tavily",
            query_plan=("EA listing",),
            at=_AT,
        )
        store.start_investigation_run(run_id, at=_AT)
        store.succeed_investigation_run(
            run_id,
            result_count=0,
            fetch_count=0,
            usage={"search_requests": 1},
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
