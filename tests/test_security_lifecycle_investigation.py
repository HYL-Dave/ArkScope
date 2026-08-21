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
        at=_LATER,
    )


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
        projected = store.project_proposals(
            case_id,
            observation_fingerprint_sha256=_FINGERPRINT,
        )
        assert {
            proposal["projected_block_reason"] for proposal in projected
        } == {"stale_assessment"}
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
            adapter="tavily",
            query_plan=["EA delisting"],
            at=_AT,
        )
        store.start_investigation_run(run_id, at=_AT)
        store.fail_investigation_run(
            run_id,
            failure_code="network_error",
            usage={"requests": 0},
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


def test_open_portfolio_position_blocks_hide_and_remap_proposals(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        assessment = _draft(
            store,
            case_id,
            outcomes=("symbol_changed", "listing_ended"),
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
        assert "remap_symbol" not in actions
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
                outcomes=("acquisition_stock",),
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


def test_successful_zero_result_run_can_support_inconclusive_acknowledgement(tmp_path):
    conn, store, case_id = _context(tmp_path)
    try:
        run_id = store.create_investigation_run(
            case_id=case_id,
            trigger="attended_user",
            adapter="tavily",
            query_plan=["EA listing status"],
            at=_AT,
        )
        store.start_investigation_run(run_id, at=_AT)
        store.succeed_investigation_run(
            run_id,
            result_count=0,
            fetch_count=0,
            usage={"search_requests": 1},
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
