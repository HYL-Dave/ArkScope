from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import sqlite3

import pytest


_AT = "2026-08-23T00:00:00Z"
_OBSERVATION_FINGERPRINT = "a" * 64
_EVIDENCE_FINGERPRINT = "b" * 64
_ASSESSMENT_FINGERPRINT = (
    "ec29e8f5c82f78f5f92898f846ee5a84c85e30281d4186e2ca2d4660f6b39e2f"
)


def _profile_connection(tmp_path, *, active_source: bool = True) -> sqlite3.Connection:
    from src.profile_state import ProfileStateStore

    path = tmp_path / "profile_state.db"
    ProfileStateStore(path)
    conn = sqlite3.connect(path)
    if active_source:
        conn.execute(
            "INSERT INTO watchlists "
            "(id,name,kind,position,archived_at,created_at,updated_at) "
            "VALUES (1,'Core','custom',0,NULL,?,?)",
            (_AT, _AT),
        )
        conn.execute(
            "INSERT INTO watchlist_memberships "
            "(list_id,ticker,position,archived_at,created_at,updated_at) "
            "VALUES (1,'OLD',3,NULL,?,?)",
            (_AT, _AT),
        )
        conn.commit()
    return conn


def _transition_connection(tmp_path, *, active_source: bool = True) -> sqlite3.Connection:
    from src.security_lifecycle_schema import create_profile_schema
    from src.ticker_identity_schema import create_ticker_identity_schema

    conn = _profile_connection(tmp_path, active_source=active_source)
    create_profile_schema(conn)
    create_ticker_identity_schema(conn)
    conn.execute(
        "INSERT INTO security_lifecycle_cases "
        "(case_id,source,source_ref,ticker,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            "slc_1",
            "sec_edgar",
            "0000000000-26-000001",
            "OLD",
            _AT,
            _AT,
        ),
    )
    conn.execute(
        "INSERT INTO security_lifecycle_assessments "
        "(assessment_id,case_id,revision,status,relevance,confidence,author,"
        "conclusion,impact_summary,successor_ticker,effective_date,"
        "observation_fingerprint_sha256,evidence_set_sha256,created_at,accepted_at,"
        "acceptance_authority) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "sla_1",
            "slc_1",
            1,
            "accepted",
            "direct_tracked_security",
            "high",
            "human",
            "The tracked security continues under NEW.",
            "Tracking should continue under the successor ticker.",
            "NEW",
            "2026-08-25",
            _OBSERVATION_FINGERPRINT,
            _EVIDENCE_FINGERPRINT,
            _AT,
            _AT,
            "human",
        ),
    )
    conn.commit()
    return conn


def _seed_automation_authority(conn: sqlite3.Connection) -> str:
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_fact_kernel import (
        persisted_decision_provenance_sha256,
    )

    conn.execute(
        "INSERT INTO security_lifecycle_automation_runs "
        "(run_id,case_id,mode,observation_fingerprint_sha256,policy_version,"
        "run_key,status,decision_tier,action_readiness,query_context_json,"
        "diagnostics_json,retry_at,failure_code,started_at,finished_at,created_at,"
        "updated_at) VALUES (?,?,?,?,?,?,'succeeded','verified_automatic',"
        "'transition_eligible','{}','{}',NULL,NULL,?,?,?,?)",
        (
            "slar_1",
            "slc_1",
            "live",
            _OBSERVATION_FINGERPRINT,
            AUTOMATION_POLICY_VERSION,
            "automation:slc_1:run-1",
            _AT,
            _AT,
            _AT,
            _AT,
        ),
    )
    provenance = persisted_decision_provenance_sha256(conn, "slar_1")
    conn.execute(
        "UPDATE security_lifecycle_assessments SET author='automation',"
        "automation_method='deterministic_rule',automation_run_id='slar_1',"
        "acceptance_authority='automation_policy',"
        "rule_id='lifecycle.simple_symbol_continuation',rule_version='1',"
        "decision_provenance_sha256=? WHERE assessment_id='sla_1'",
        (provenance,),
    )
    conn.execute(
        "INSERT INTO security_lifecycle_action_proposals "
        "(proposal_id,case_id,assessment_id,action_type,status,source_ticker,"
        "replacement_ticker,source_snapshot_json,reason,block_reason,"
        "assessment_fingerprint_sha256,proposal_dedupe_key,created_at,dismissed_at) "
        "VALUES ('slp_1','slc_1','sla_1','remap_symbol','proposed','OLD','NEW',"
        "'{}','Continue tracking the successor.',NULL,?,?,?,NULL)",
        (_ASSESSMENT_FINGERPRINT, "automation:slc_1:remap", _AT),
    )
    conn.commit()
    return provenance


def _id_factory():
    counters: dict[str, int] = {}

    def generate(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}_{counters[prefix]}"

    return generate


def _seed_transferable_state(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO universe_source_memberships "
        "(source_key,ticker,created_at,archived_at) VALUES (?,?,?,NULL)",
        ("legacy_config_seed", "OLD", _AT),
    )
    conn.executemany(
        "INSERT INTO ticker_tags (ticker,facet,value,source,created_at) "
        "VALUES (?,?,?,?,?)",
        [
            ("OLD", "theme", "AI", "user", _AT),
            ("OLD", "category", "Core", "legacy", _AT),
            ("OLD", "sector", "Technology", "provider:fundamentals", _AT),
        ],
    )
    conn.execute(
        "INSERT INTO ticker_meta (ticker,priority,hidden_at,updated_at) "
        "VALUES ('OLD','high',NULL,?)",
        (_AT,),
    )
    conn.commit()


def _rows_by_table(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    tables = (
        "ticker_identity_links",
        "ticker_identity_transition_activity",
        "ticker_identity_transition_attempts",
        "ticker_identity_transitions",
        "ticker_meta",
        "ticker_tags",
        "universe_source_memberships",
        "watchlist_memberships",
    )
    return {
        table: [
            tuple(row)
            for row in conn.execute(
                f'SELECT * FROM "{table}" ORDER BY rowid'
            ).fetchall()
        ]
        for table in tables
    }


def _profile_owned_rows(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    tables = (
        "ticker_meta",
        "ticker_tags",
        "universe_source_memberships",
        "watchlist_memberships",
    )
    return {
        table: [
            tuple(row)
            for row in conn.execute(
                f'SELECT * FROM "{table}" ORDER BY rowid'
            ).fetchall()
        ]
        for table in tables
    }


def _case() -> dict:
    return {
        "case_id": "slc_1",
        "source": "sec_edgar",
        "source_ref": "0000000000-26-000001",
        "ticker": "OLD",
    }


def _assessment(
    *,
    outcomes=("symbol_changed",),
    successor: str | None = "NEW",
    effective_date: str | None = "2026-08-25",
    status: str = "accepted",
    relevance: str = "direct_tracked_security",
    citations: list[dict] | None = None,
    stale: bool = False,
) -> dict:
    return {
        "assessment_id": "sla_1",
        "case_id": "slc_1",
        "revision": 1,
        "status": status,
        "relevance": relevance,
        "confidence": "high",
        "author": "human",
        "conclusion": "The tracked security continues under NEW.",
        "impact_summary": "Tracking should continue under the successor ticker.",
        "successor_ticker": successor,
        "effective_date": effective_date,
        "observation_fingerprint_sha256": _OBSERVATION_FINGERPRINT,
        "evidence_set_sha256": _EVIDENCE_FINGERPRINT,
        "outcomes": list(outcomes),
        "citations": citations
        if citations is not None
        else [
            {
                "reference_kind": "observation",
                "evidence_id": None,
                "cited_content_sha256": _OBSERVATION_FINGERPRINT,
            }
        ],
        "stale": stale,
    }


def _proposal(
    *,
    action_type: str = "remap_symbol",
    replacement: str | None = "NEW",
    proposal_id: str = "slp_1",
    status: str = "proposed",
    projected_block_reason: str | None = None,
) -> dict:
    return {
        "proposal_id": proposal_id,
        "case_id": "slc_1",
        "assessment_id": "sla_1",
        "action_type": action_type,
        "status": status,
        "source_ticker": "OLD",
        "replacement_ticker": replacement,
        "assessment_fingerprint_sha256": _ASSESSMENT_FINGERPRINT,
        "projected_block_reason": projected_block_reason,
    }


def _build(
    conn: sqlite3.Connection,
    *,
    assessment: dict | None = None,
    proposals: list[dict] | None = None,
    sources=("manual_lists",),
    execute_on: str = "2026-08-25",
    priority_resolution: str | None = None,
    unhide_successor: bool = False,
) -> dict:
    from src.ticker_identity_transition import TransitionOptions, build_transition_preview

    return build_transition_preview(
        conn,
        case=_case(),
        assessment=assessment or _assessment(),
        proposals=proposals if proposals is not None else [_proposal()],
        observation_fingerprint_sha256=_OBSERVATION_FINGERPRINT,
        sources=sources,
        options=TransitionOptions(
            execute_on=execute_on,
            priority_resolution=priority_resolution,
            unhide_successor=unhide_successor,
        ),
    )


@pytest.mark.parametrize(
    ("outcomes", "successor", "eligible_kind"),
    [
        (("symbol_changed",), "NEW", "symbol_continuation"),
        (("symbol_changed", "venue_transfer"), "NEW", "symbol_continuation"),
        (("venue_transfer",), None, None),
        (("symbol_or_venue_changed",), "NEW", None),
        (("acquisition_stock",), "NEW", None),
    ],
)
def test_preview_uses_the_closed_transition_eligibility_matrix(
    tmp_path, outcomes, successor, eligible_kind
):
    conn = _profile_connection(tmp_path)
    try:
        preview = _build(
            conn,
            assessment=_assessment(outcomes=outcomes, successor=successor),
            proposals=[_proposal(replacement=successor)],
        )
        assert preview["transition_kind"] == eligible_kind
        assert preview["eligible"] is (eligible_kind is not None)
    finally:
        conn.close()


def test_terminal_delisting_is_blocked_by_open_portfolio(tmp_path):
    conn = _profile_connection(tmp_path)
    try:
        preview = _build(
            conn,
            assessment=_assessment(outcomes=("listing_ended",), successor=None),
            proposals=[_proposal(action_type="notify", replacement=None)],
            sources=("manual_lists", "portfolio_open"),
        )
        assert preview["transition_kind"] == "terminal_delisting"
        assert preview["eligible"] is False
        assert preview["block_reasons"] == ["portfolio_position_open"]
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("assessment_changes", "sources", "execute_on", "expected_reason"),
    [
        ({"effective_date": None}, ("manual_lists",), "", "execution_date_required"),
        ({"status": "draft"}, ("manual_lists",), "2026-08-25", "assessment_not_accepted"),
        ({"stale": True}, ("manual_lists",), "2026-08-25", "stale_assessment"),
        ({"citations": []}, ("manual_lists",), "2026-08-25", "observation_citation_required"),
    ],
)
def test_preview_rejects_missing_or_stale_authority(
    tmp_path, assessment_changes, sources, execute_on, expected_reason
):
    conn = _profile_connection(tmp_path)
    try:
        assessment = _assessment()
        assessment.update(assessment_changes)
        preview = _build(
            conn,
            assessment=assessment,
            sources=sources,
            execute_on=execute_on,
        )
        assert expected_reason in preview["block_reasons"]
        assert preview["eligible"] is False
    finally:
        conn.close()


def test_preview_rejects_same_successor_and_absent_tracking_source(tmp_path):
    same = _profile_connection(tmp_path / "same")
    try:
        preview = _build(
            same,
            assessment=_assessment(successor="OLD"),
            proposals=[_proposal(replacement="OLD")],
        )
        assert preview["transition_kind"] is None
        assert preview["block_reasons"] == ["successor_not_distinct"]
    finally:
        same.close()

    absent = _profile_connection(tmp_path / "absent", active_source=False)
    try:
        preview = _build(absent, sources=())
        assert preview["transition_kind"] == "symbol_continuation"
        assert preview["block_reasons"] == ["no_active_tracking_source"]
    finally:
        absent.close()


def test_symbol_continuation_requires_a_current_matching_remap_proposal(tmp_path):
    conn = _profile_connection(tmp_path)
    try:
        missing = _build(
            conn,
            proposals=[_proposal(action_type="notify", replacement=None)],
        )
        assert missing["transition_kind"] == "symbol_continuation"
        assert missing["block_reasons"] == ["remap_proposal_missing"]

        stale = _build(
            conn,
            proposals=[_proposal(projected_block_reason="stale_assessment")],
        )
        assert stale["block_reasons"] == ["stale_assessment"]
    finally:
        conn.close()


def test_priority_and_hidden_successor_conflicts_need_explicit_resolution(tmp_path):
    conn = _profile_connection(tmp_path)
    try:
        conn.executemany(
            "INSERT INTO ticker_meta (ticker,priority,hidden_at,updated_at) "
            "VALUES (?,?,?,?)",
            [
                ("OLD", "high", None, _AT),
                ("NEW", "low", _AT, _AT),
            ],
        )
        conn.commit()

        blocked = _build(conn)
        assert blocked["block_reasons"] == [
            "priority_resolution_required",
            "successor_hidden",
        ]

        resolved = _build(
            conn,
            priority_resolution="source",
            unhide_successor=True,
        )
        assert resolved["eligible"] is True
        assert resolved["effects"]["priority"] == {
            "resolution": "source",
            "result_value": "high",
            "source_value": "high",
            "successor_value": "low",
            "write_successor": True,
        }
        assert resolved["effects"]["suppression"]["unhide_successor"] is True
    finally:
        conn.close()


def test_preview_lists_exact_profile_owned_effects_and_retained_facts(tmp_path):
    conn = _profile_connection(tmp_path)
    try:
        conn.executemany(
            "INSERT INTO watchlists "
            "(id,name,kind,position,archived_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            [
                (2, "Income", "custom", 1, None, _AT, _AT),
                (3, "Existing", "custom", 2, None, _AT, _AT),
                (4, "Archived list", "custom", 3, _AT, _AT, _AT),
            ],
        )
        conn.executemany(
            "INSERT INTO watchlist_memberships "
            "(list_id,ticker,position,archived_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            [
                (2, "OLD", 5, None, _AT, _AT),
                (2, "NEW", 2, _AT, _AT, _AT),
                (3, "OLD", 6, None, _AT, _AT),
                (3, "NEW", 1, None, _AT, _AT),
                (4, "OLD", 7, None, _AT, _AT),
            ],
        )
        conn.executemany(
            "INSERT INTO universe_source_memberships "
            "(source_key,ticker,created_at,archived_at) VALUES (?,?,?,?)",
            [
                ("legacy_config_seed", "OLD", _AT, None),
                ("legacy_config_seed", "NEW", _AT, _AT),
            ],
        )
        conn.executemany(
            "INSERT INTO ticker_tags (ticker,facet,value,source,created_at) "
            "VALUES (?,?,?,?,?)",
            [
                ("OLD", "theme", "AI", "user", _AT),
                ("OLD", "category", "Core", "legacy", _AT),
                ("OLD", "sector", "Technology", "provider:fundamentals", _AT),
                ("NEW", "theme", "AI", "user", _AT),
            ],
        )
        conn.execute(
            "INSERT INTO ticker_meta (ticker,priority,hidden_at,updated_at) "
            "VALUES ('OLD','high',NULL,?)",
            (_AT,),
        )
        conn.commit()

        preview = _build(
            conn,
            sources=(
                "sa_alpha_picks_current",
                "legacy_config_seed",
                "manual_lists",
            ),
        )

        assert preview["effects"]["watchlists"] == {
            "add": [
                {"list_id": 1, "list_name": "Core", "position": 3, "ticker": "NEW"}
            ],
            "archive": [
                {"list_id": 1, "list_name": "Core", "position": 3, "ticker": "OLD"},
                {"list_id": 2, "list_name": "Income", "position": 5, "ticker": "OLD"},
                {"list_id": 3, "list_name": "Existing", "position": 6, "ticker": "OLD"},
            ],
            "reactivate": [
                {"list_id": 2, "list_name": "Income", "position": 2, "ticker": "NEW"}
            ],
            "unchanged": [
                {"list_id": 3, "list_name": "Existing", "position": 1, "ticker": "NEW"}
            ],
        }
        assert preview["effects"]["legacy_config_seed"] == {
            "add": [],
            "archive": [{"source_key": "legacy_config_seed", "ticker": "OLD"}],
            "reactivate": [
                {"source_key": "legacy_config_seed", "ticker": "NEW"}
            ],
            "unchanged": [],
        }
        assert preview["effects"]["editable_tags_to_copy"] == [
            {
                "facet": "category",
                "source": "legacy",
                "ticker": "NEW",
                "value": "Core",
            }
        ]
        assert preview["effects"]["priority"]["result_value"] == "high"
        assert preview["effects"]["suppression"] == {
            "hide_source": True,
            "source_hidden": False,
            "successor_hidden": False,
            "unhide_successor": False,
        }
        assert preview["provider_owned_sources"] == ["sa_alpha_picks_current"]
        assert preview["caveats"] == [
            "provider_owned_sources_retained",
            "successor_already_tracked",
        ]
        assert preview["eligible"] is True
        assert conn.execute(
            "SELECT ticker,archived_at FROM watchlist_memberships "
            "WHERE list_id=2 ORDER BY ticker"
        ).fetchall() == [("NEW", _AT), ("OLD", None)]
        assert conn.execute(
            "SELECT ticker,archived_at FROM universe_source_memberships "
            "WHERE source_key='legacy_config_seed' ORDER BY ticker"
        ).fetchall() == [("NEW", _AT), ("OLD", None)]
    finally:
        conn.close()


def test_preview_is_canonical_and_hashes_every_authority_input(tmp_path):
    from src.ticker_identity_transition import profile_snapshot_sha256

    conn = _profile_connection(tmp_path)
    try:
        first = _build(
            conn,
            proposals=[
                _proposal(proposal_id="slp_2", action_type="notify", replacement=None),
                _proposal(proposal_id="slp_1"),
            ],
            sources=("manual_lists", "sa_alpha_picks_current"),
        )
        second = _build(
            conn,
            proposals=[
                _proposal(proposal_id="slp_1"),
                _proposal(proposal_id="slp_2", action_type="notify", replacement=None),
            ],
            sources=("sa_alpha_picks_current", "manual_lists"),
        )

        assert first == second
        assert first["proposal_ids"] == ["slp_1", "slp_2"]
        assert first["observation_fingerprint_sha256"] == _OBSERVATION_FINGERPRINT
        assert first["assessment_fingerprint_sha256"] == _ASSESSMENT_FINGERPRINT
        assert first["evidence_set_sha256"] == _EVIDENCE_FINGERPRINT
        assert profile_snapshot_sha256(first) == first["preview_sha256"]
        assert len(first["preview_sha256"]) == 64
    finally:
        conn.close()


def test_transition_approval_is_digest_bound_idempotent_and_due_on_its_date(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        preview = _build(conn)
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-24T01:00:00Z",
        )

        first = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        repeated = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )

        assert first["transition_id"] == repeated["transition_id"]
        assert first["status"] == "approved"
        assert first["approval_authority"] == "attended_user"
        assert first["automation_policy_version"] is None
        assert first["rule_id"] is None
        assert first["rule_version"] is None
        assert first["decision_provenance_sha256"] == _ASSESSMENT_FINGERPRINT
        assert first["proposal_ids"] == ["slp_1"]
        assert first["approved_preview"] == preview
        assert store.list_due(on_date="2026-08-24", limit=10) == []
        assert [
            item["transition_id"]
            for item in store.list_due(on_date="2026-08-25", limit=10)
        ] == [first["transition_id"]]
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transitions"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_automation_transition_approval_binds_policy_rule_and_provenance(tmp_path):
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.ticker_identity_transition import (
        TickerIdentityTransitionStore,
        build_automation_transition_preflight,
    )

    conn = _transition_connection(tmp_path)
    try:
        before_changes = conn.total_changes
        preflight = build_automation_transition_preflight(
            conn,
            case={
                **_case(),
                "observation_fingerprint_sha256": _OBSERVATION_FINGERPRINT,
            },
            request={
                "transition_kind": "symbol_continuation",
                "source_ticker": "OLD",
                "successor_ticker": "NEW",
                "effective_date": "2026-08-25",
                "outcomes": ("symbol_changed",),
            },
            sources=("manual_lists",),
        )
        assert preflight["eligible"] is True
        assert preflight["transition_kind"] == "symbol_continuation"
        assert conn.total_changes == before_changes

        provenance = _seed_automation_authority(conn)
        preview = _build(conn)
        approved = TickerIdentityTransitionStore(
            conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-24T01:00:00Z",
        ).approve_automation(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )

        assert approved["status"] == "approved"
        assert approved["approval_authority"] == "automation_policy"
        assert approved["automation_policy_version"] == AUTOMATION_POLICY_VERSION
        assert approved["rule_id"] == "lifecycle.simple_symbol_continuation"
        assert approved["rule_version"] == "1"
        assert approved["decision_provenance_sha256"] == provenance
    finally:
        conn.close()


def test_automation_transition_approval_rejects_incoherent_or_stale_authority(
    tmp_path,
):
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_automation_authority(conn)
        preview = _build(conn)
        store = TickerIdentityTransitionStore(conn)

        conn.execute(
            "UPDATE security_lifecycle_automation_runs SET policy_version='stale' "
            "WHERE run_id='slar_1'"
        )
        conn.commit()
        with pytest.raises(ValueError, match="automation_authority_changed"):
            store.approve_automation(
                preview=preview,
                approved_preview_sha256=preview["preview_sha256"],
            )

        conn.execute(
            "UPDATE security_lifecycle_automation_runs SET policy_version=? "
            "WHERE run_id='slar_1'",
            (AUTOMATION_POLICY_VERSION,),
        )
        conn.execute(
            "UPDATE security_lifecycle_assessments SET rule_version='999' "
            "WHERE assessment_id='sla_1'"
        )
        conn.commit()
        with pytest.raises(ValueError, match="automation_authority_changed"):
            store.approve_automation(
                preview=preview,
                approved_preview_sha256=preview["preview_sha256"],
            )

        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transitions"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_transition_approval_rejects_tampered_or_ineligible_preview_without_rows(
    tmp_path,
):
    from src.ticker_identity_transition import (
        TickerIdentityTransitionStore,
        profile_snapshot_sha256,
    )

    conn = _transition_connection(tmp_path)
    try:
        preview = _build(conn)
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-24T01:00:00Z",
        )

        with pytest.raises(ValueError, match="preview_digest"):
            store.approve(
                preview=preview,
                approved_preview_sha256="f" * 64,
            )

        ineligible = deepcopy(preview)
        ineligible["eligible"] = False
        ineligible["block_reasons"] = ["priority_resolution_required"]
        ineligible["preview_sha256"] = profile_snapshot_sha256(ineligible)
        with pytest.raises(ValueError, match="preview_ineligible"):
            store.approve(
                preview=ineligible,
                approved_preview_sha256=ineligible["preview_sha256"],
            )

        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transitions"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_transition_approval_rechecks_profile_digest_inside_its_write_lock(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        conn.execute(
            "UPDATE ticker_meta SET priority='low',updated_at=? WHERE ticker='OLD'",
            ("2026-08-24T00:59:59Z",),
        )
        conn.commit()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-24T01:00:00Z",
        )

        with pytest.raises(ValueError, match="preview_changed"):
            store.approve(
                preview=preview,
                approved_preview_sha256=preview["preview_sha256"],
            )

        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transitions"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_transition_approval_rechecks_assessment_authority_inside_write_lock(
    tmp_path,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        conn.execute(
            "UPDATE security_lifecycle_assessments "
            "SET status='superseded',superseded_at=? "
            "WHERE assessment_id='sla_1'",
            (_AT,),
        )
        conn.commit()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-24T01:00:00Z",
        )

        with pytest.raises(ValueError, match="preview_changed"):
            store.approve(
                preview=preview,
                approved_preview_sha256=preview["preview_sha256"],
            )

        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transitions"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_cancel_is_idempotent_before_apply_and_removes_transition_from_due_list(
    tmp_path,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        preview = _build(conn)
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-24T01:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )

        cancelled = store.cancel(transition["transition_id"])
        repeated = store.cancel(transition["transition_id"])

        assert cancelled["status"] == "cancelled"
        assert repeated == cancelled
        assert cancelled["cancelled_at"] == "2026-08-24T01:00:00Z"
        assert store.list_due(on_date="2026-08-25", limit=10) == []
    finally:
        conn.close()


def test_apply_commits_ordered_profile_effects_lineage_and_receipts_atomically(
    tmp_path,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )

        steps: list[str] = []
        applying = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
            _step_hook=steps.append,
        )
        result = applying.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="attended_user",
        )

        assert result["status"] == "applied"
        assert steps == [
            "successor_memberships",
            "editable_tags",
            "successor_priority",
            "identity_link",
            "source_membership_archives",
            "suppression",
            "transition_receipt",
            "attempt_receipt",
            "activity_receipt",
        ]
        assert conn.execute(
            "SELECT ticker,position,archived_at FROM watchlist_memberships "
            "WHERE list_id=1 ORDER BY ticker"
        ).fetchall() == [
            ("NEW", 3, None),
            ("OLD", 3, "2026-08-25T13:00:00Z"),
        ]
        assert conn.execute(
            "SELECT ticker,archived_at FROM universe_source_memberships "
            "WHERE source_key='legacy_config_seed' ORDER BY ticker"
        ).fetchall() == [
            ("NEW", None),
            ("OLD", "2026-08-25T13:00:00Z"),
        ]
        assert conn.execute(
            "SELECT facet,value,source FROM ticker_tags WHERE ticker='NEW' "
            "ORDER BY facet,source,value"
        ).fetchall() == [
            ("category", "Core", "legacy"),
            ("theme", "AI", "user"),
        ]
        assert conn.execute(
            "SELECT priority,hidden_at FROM ticker_meta WHERE ticker='NEW'"
        ).fetchone() == ("high", None)
        assert conn.execute(
            "SELECT hidden_at FROM ticker_meta WHERE ticker='OLD'"
        ).fetchone() == ("2026-08-25T13:00:00Z",)
        assert conn.execute(
            "SELECT source_ticker,successor_ticker,relationship,reversed_at "
            "FROM ticker_identity_links"
        ).fetchall() == [("OLD", "NEW", "symbol_continuation", None)]
        applied = applying.get(transition["transition_id"])
        assert applied["status"] == "applied"
        assert applied["before_snapshot_json"] is not None
        assert len(applied["after_snapshot_sha256"]) == 64

        repeated = applying.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )
        assert repeated["status"] == "already_applied"
        assert conn.execute(
            "SELECT status FROM ticker_identity_transition_attempts "
            "ORDER BY rowid"
        ).fetchall() == [("applied",), ("already_applied",)]
    finally:
        conn.close()


@pytest.mark.parametrize("fail_after", range(1, 10))
def test_apply_rolls_back_every_profile_and_receipt_mutation_on_failure(
    tmp_path,
    fail_after,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path / str(fail_after))
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        ids = _id_factory()
        approving = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = approving.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        before = _rows_by_table(conn)
        calls = 0

        def fail_at_step(_name: str) -> None:
            nonlocal calls
            calls += 1
            if calls == fail_after:
                raise RuntimeError("injected_failure")

        applying = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
            _step_hook=fail_at_step,
        )
        with pytest.raises(RuntimeError, match="injected_failure"):
                applying.apply(
                    transition["transition_id"],
                    current_preview=preview,
                    expected_preview_sha256=preview["preview_sha256"],
                    trigger="scheduler",
                )

        assert calls == fail_after
        assert _rows_by_table(conn) == before
        assert conn.in_transaction is False
    finally:
        conn.close()


def test_apply_rechecks_profile_state_inside_write_lock_and_never_overwrites_edit(
    tmp_path,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        assert len(preview["profile_state_sha256"]) == 64
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        conn.execute(
            "UPDATE ticker_meta SET priority='low',updated_at=? WHERE ticker='OLD'",
            ("2026-08-25T12:59:59Z",),
        )
        conn.commit()

        result = store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )

        assert result["status"] == "blocked"
        assert result["block_reasons"] == ["preview_changed"]
        assert store.get(transition["transition_id"])["status"] == "needs_review"
        assert conn.execute(
            "SELECT priority FROM ticker_meta WHERE ticker='OLD'"
        ).fetchone() == ("low",)
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_memberships WHERE ticker='NEW'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT status,block_reasons_json FROM ticker_identity_transition_attempts"
        ).fetchall() == [("blocked", '["preview_changed"]')]
    finally:
        conn.close()


def test_apply_rechecks_accepted_assessment_inside_write_lock(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        conn.execute(
            "UPDATE security_lifecycle_assessments "
            "SET status='superseded',superseded_at=? "
            "WHERE assessment_id='sla_1'",
            (_AT,),
        )
        conn.commit()

        result = store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )

        assert result["status"] == "blocked"
        assert result["block_reasons"] == ["preview_changed"]
        assert result["transition"]["status"] == "needs_review"
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_memberships WHERE ticker='NEW'"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_open_position_preserves_old_visibility_without_blocking_successor_tracking(
    tmp_path,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        conn.executescript(
            """
            CREATE TABLE portfolio_positions (id INTEGER PRIMARY KEY, symbol TEXT, quantity TEXT);
            CREATE TABLE research_threads (id INTEGER PRIMARY KEY, ticker TEXT, body TEXT);
            CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL);
            """
        )
        conn.execute("INSERT INTO portfolio_positions VALUES (1,'OLD','10')")
        conn.execute("INSERT INTO research_threads VALUES (1,'OLD','Historical work')")
        conn.execute("INSERT INTO ticker_aliases VALUES ('OLD','OLD')")
        conn.execute(
            "INSERT INTO ticker_notes (ticker,body,created_at,updated_at) "
            "VALUES ('OLD','Keep under the historical identity',?,?)",
            (_AT, _AT),
        )
        conn.commit()
        protected_tables = (
            "portfolio_positions",
            "research_threads",
            "security_lifecycle_assessments",
            "security_lifecycle_cases",
            "ticker_aliases",
            "ticker_notes",
        )
        protected_before = {
            table: conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            for table in protected_tables
        }
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed", "portfolio_open"),
        )
        assert preview["eligible"] is True
        assert preview["effects"]["suppression"]["hide_source"] is False
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        assert store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )["status"] == "applied"

        assert {
            table: conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            for table in protected_tables
        } == protected_before
        assert conn.execute(
            "SELECT hidden_at FROM ticker_meta WHERE ticker='OLD'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT archived_at FROM watchlist_memberships "
            "WHERE list_id=1 AND ticker='OLD'"
        ).fetchone() == ("2026-08-25T13:00:00Z",)
        assert conn.execute(
            "SELECT archived_at FROM watchlist_memberships "
            "WHERE list_id=1 AND ticker='NEW'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_tags WHERE ticker='NEW' "
            "AND source='provider:fundamentals'"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_terminal_delisting_archives_and_suppresses_without_creating_successor(
    tmp_path,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            assessment=_assessment(outcomes=("listing_ended",), successor=None),
            proposals=[_proposal(action_type="notify", replacement=None)],
            sources=("manual_lists", "legacy_config_seed"),
        )
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        result = store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="attended_user",
        )

        assert result["status"] == "applied"
        assert conn.execute(
            "SELECT COUNT(*) FROM watchlist_memberships WHERE ticker='NEW'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT archived_at FROM watchlist_memberships WHERE ticker='OLD'"
        ).fetchone() == ("2026-08-25T13:00:00Z",)
        assert conn.execute(
            "SELECT hidden_at FROM ticker_meta WHERE ticker='OLD'"
        ).fetchone() == ("2026-08-25T13:00:00Z",)
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_links"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_reversal_restores_exact_owned_rows_and_keeps_reversed_lineage(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        before = _profile_owned_rows(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="attended_user",
        )
        reversing = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-26T14:00:00Z",
        )

        result = reversing.reverse(
            transition["transition_id"],
            trigger="attended_user",
        )

        assert result["status"] == "reversed"
        assert _profile_owned_rows(conn) == before
        assert reversing.get(transition["transition_id"])["status"] == "reversed"
        assert conn.execute(
            "SELECT reversed_at FROM ticker_identity_links"
        ).fetchall() == [("2026-08-26T14:00:00Z",)]
        assert conn.execute(
            "SELECT status FROM ticker_identity_transition_attempts ORDER BY rowid"
        ).fetchall() == [("applied",), ("reversed",)]
        assert reversing.lineage_for_ticker("OLD")["successors"][0][
            "successor_ticker"
        ] == "NEW"
        assert reversing.lineage_for_ticker("NEW")["predecessors"][0][
            "source_ticker"
        ] == "OLD"
    finally:
        conn.close()


def test_reversal_blocks_after_user_edit_without_overwriting_the_edit(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )
        conn.execute(
            "UPDATE ticker_meta SET priority='low',updated_at=? WHERE ticker='NEW'",
            ("2026-08-26T13:59:59Z",),
        )
        conn.commit()
        before_reverse = _profile_owned_rows(conn)

        result = store.reverse(
            transition["transition_id"],
            trigger="attended_user",
        )

        assert result["status"] == "blocked"
        assert result["block_reasons"] == ["reverse_state_changed"]
        assert _profile_owned_rows(conn) == before_reverse
        assert store.get(transition["transition_id"])["status"] == "applied"
        assert conn.execute(
            "SELECT reversed_at FROM ticker_identity_links"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT observed_preview_sha256 "
            "FROM ticker_identity_transition_attempts WHERE status='blocked'"
        ).fetchone() == (preview["preview_sha256"],)
    finally:
        conn.close()


def test_reversal_blocks_when_successor_has_a_later_active_continuation(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(
            conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )
        conn.execute(
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
            "VALUES (?,?,?,?,?,?,'applied',?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,"
            "'attended_user',NULL,NULL,NULL,?)",
            (
                "tit_later",
                "slc_1",
                "sla_1",
                '["slp_later"]',
                "dedupe:later",
                "symbol_continuation",
                "NEW",
                "THIRD",
                "2026-08-26",
                None,
                0,
                "a" * 64,
                "b" * 64,
                "c" * 64,
                "{}",
                "{}",
                "d" * 64,
                "2026-08-26T00:00:00Z",
                "2026-08-26T00:00:00Z",
                "2026-08-26T00:00:00Z",
                "b" * 64,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_links "
            "(link_id,transition_id,source_ticker,successor_ticker,relationship,"
            "effective_date,created_at,reversed_at) VALUES (?,?,?,?,?,?,?,NULL)",
            (
                "til_later",
                "tit_later",
                "NEW",
                "THIRD",
                "symbol_continuation",
                "2026-08-26",
                "2026-08-26T00:00:00Z",
            ),
        )
        conn.commit()

        result = store.reverse(
            transition["transition_id"],
            trigger="attended_user",
        )

        assert result["status"] == "blocked"
        assert result["block_reasons"] == ["successor_has_later_transition"]
        assert store.get(transition["transition_id"])["status"] == "applied"
    finally:
        conn.close()


def test_apply_and_reverse_append_truthful_activity_in_same_transaction(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path / "success")
    try:
        _seed_transferable_state(conn)
        provenance = _seed_automation_authority(conn)
        preview = _build(
            conn,
            sources=(
                "manual_lists",
                "legacy_config_seed",
                "sa_alpha_picks_current",
            ),
        )
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve_automation(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        applied = store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )

        assert applied["status"] == "applied"
        activity = store.list_activity(limit=10)
        assert activity["count"] == 1
        assert activity["unacknowledged_count"] == 1
        applied_activity = activity["items"][0]
        assert applied_activity == {
            "activity_id": applied_activity["activity_id"],
            "transition_id": transition["transition_id"],
            "case_id": "slc_1",
            "activity_type": "applied",
            "source_ticker": "OLD",
            "successor_ticker": "NEW",
            "effective_date": "2026-08-25",
            "user_owned_changes": [
                {"change_type": "editable_tag_copied", "count": 2},
                {"change_type": "legacy_membership_added", "count": 1},
                {"change_type": "legacy_membership_archived", "count": 1},
                {"change_type": "priority_updated", "count": 1},
                {"change_type": "source_hidden", "count": 1},
                {"change_type": "watchlist_membership_added", "count": 1},
                {"change_type": "watchlist_membership_archived", "count": 1},
            ],
            "provider_owned_retained": ["sa_alpha_picks_current"],
            "state_sha256": applied["transition"]["after_snapshot_sha256"],
            "rule_id": "lifecycle.simple_symbol_continuation",
            "rule_version": "1",
            "decision_provenance_sha256": provenance,
            "occurred_at": "2026-08-25T13:00:00Z",
            "acknowledged_at": None,
            "created_at": "2026-08-25T13:00:00Z",
        }

        reversing = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-26T14:00:00Z",
        )
        reversed_result = reversing.reverse(
            transition["transition_id"],
            trigger="attended_user",
        )
        rows = reversing.list_activity(limit=10)["items"]
        before_snapshot = json.loads(
            str(reversed_result["transition"]["before_snapshot_json"])
        )
        restored_digest = hashlib.sha256(
            json.dumps(
                before_snapshot,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        assert [row["activity_type"] for row in rows] == ["reversed", "applied"]
        assert rows[0]["state_sha256"] == restored_digest
        assert rows[0]["user_owned_changes"] == applied_activity["user_owned_changes"]
        assert rows[0]["provider_owned_retained"] == ["sa_alpha_picks_current"]
        assert rows[0]["decision_provenance_sha256"] == provenance
    finally:
        conn.close()

    apply_conn = _transition_connection(tmp_path / "apply-rollback")
    try:
        _seed_transferable_state(apply_conn)
        preview = _build(
            apply_conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        store = TickerIdentityTransitionStore(
            apply_conn,
            id_factory=_id_factory(),
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        before = _profile_owned_rows(apply_conn)
        apply_conn.execute(
            "CREATE TRIGGER reject_transition_activity BEFORE INSERT ON "
            "ticker_identity_transition_activity BEGIN "
            "SELECT RAISE(ABORT, 'activity_rejected'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="activity_rejected"):
            store.apply(
                transition["transition_id"],
                current_preview=preview,
                expected_preview_sha256=preview["preview_sha256"],
                trigger="scheduler",
            )
        assert _profile_owned_rows(apply_conn) == before
        assert store.get(transition["transition_id"])["status"] == "approved"
        assert apply_conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transition_attempts"
        ).fetchone() == (0,)
    finally:
        apply_conn.close()

    reverse_conn = _transition_connection(tmp_path / "reverse-rollback")
    try:
        _seed_transferable_state(reverse_conn)
        preview = _build(
            reverse_conn,
            sources=("manual_lists", "legacy_config_seed"),
        )
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            reverse_conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )
        before_reverse = _profile_owned_rows(reverse_conn)
        reverse_conn.execute(
            "CREATE TRIGGER reject_reversed_activity BEFORE INSERT ON "
            "ticker_identity_transition_activity WHEN NEW.activity_type='reversed' "
            "BEGIN SELECT RAISE(ABORT, 'reverse_activity_rejected'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="reverse_activity_rejected"):
            store.reverse(transition["transition_id"], trigger="attended_user")
        assert _profile_owned_rows(reverse_conn) == before_reverse
        assert store.get(transition["transition_id"])["status"] == "applied"
        assert reverse_conn.execute(
            "SELECT activity_type FROM ticker_identity_transition_activity"
        ).fetchall() == [("applied",)]
    finally:
        reverse_conn.close()


def test_activity_acknowledgement_is_explicit_idempotent_and_preserves_reverse(
    tmp_path,
):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(conn, sources=("manual_lists", "legacy_config_seed"))
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )
        initial = store.list_activity(limit=10, unacknowledged_only=True)
        item = initial["items"][0]
        readiness = store.reverse_readiness(transition["transition_id"])

        acknowledged = store.acknowledge_activity(
            item["activity_id"],
            at="2026-08-26T08:00:00Z",
        )
        repeated = store.acknowledge_activity(
            item["activity_id"],
            at="2026-08-27T09:00:00Z",
        )

        assert acknowledged["acknowledged_at"] == "2026-08-26T08:00:00Z"
        assert repeated == acknowledged
        assert store.list_activity(
            limit=10,
            unacknowledged_only=True,
        )["items"] == []
        assert store.list_activity(limit=10)["items"] == [acknowledged]
        assert store.reverse_readiness(transition["transition_id"]) == readiness
        assert store.reverse(
            transition["transition_id"],
            trigger="attended_user",
        )["status"] == "reversed"
        all_activity = store.list_activity(limit=10)
        assert all_activity["count"] == 2
        assert all_activity["unacknowledged_count"] == 1
        assert [row["acknowledged_at"] for row in all_activity["items"]] == [
            None,
            "2026-08-26T08:00:00Z",
        ]
    finally:
        conn.close()


def test_reverse_readiness_reports_state_and_later_transition_blockers(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    conn = _transition_connection(tmp_path)
    try:
        _seed_transferable_state(conn)
        preview = _build(conn, sources=("manual_lists", "legacy_config_seed"))
        ids = _id_factory()
        store = TickerIdentityTransitionStore(
            conn,
            id_factory=ids,
            clock=lambda: "2026-08-25T13:00:00Z",
        )
        transition = store.approve(
            preview=preview,
            approved_preview_sha256=preview["preview_sha256"],
        )
        store.apply(
            transition["transition_id"],
            current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"],
            trigger="scheduler",
        )
        attempt_count = conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transition_attempts"
        ).fetchone()[0]

        ready = store.reverse_readiness(transition["transition_id"])

        assert ready == {
            "transition_id": transition["transition_id"],
            "reversible": True,
            "block_reasons": [],
            "expected_state_sha256": store.get(transition["transition_id"])[
                "after_snapshot_sha256"
            ],
            "observed_state_sha256": store.get(transition["transition_id"])[
                "after_snapshot_sha256"
            ],
        }
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transition_attempts"
        ).fetchone()[0] == attempt_count

        conn.execute(
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
            "VALUES (?,?,?,?,?,?,'applied',?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,"
            "'attended_user',NULL,NULL,NULL,?)",
            (
                "tit_later",
                "slc_1",
                "sla_1",
                '["slp_later"]',
                "dedupe:later-readiness",
                "symbol_continuation",
                "NEW",
                "THIRD",
                "2026-08-26",
                None,
                0,
                "a" * 64,
                "b" * 64,
                "c" * 64,
                "{}",
                "{}",
                "d" * 64,
                "2026-08-26T00:00:00Z",
                "2026-08-26T00:00:00Z",
                "2026-08-26T00:00:00Z",
                "b" * 64,
            ),
        )
        conn.execute(
            "INSERT INTO ticker_identity_links "
            "(link_id,transition_id,source_ticker,successor_ticker,relationship,"
            "effective_date,created_at,reversed_at) VALUES (?,?,?,?,?,?,?,NULL)",
            (
                "til_later",
                "tit_later",
                "NEW",
                "THIRD",
                "symbol_continuation",
                "2026-08-26",
                "2026-08-26T00:00:00Z",
            ),
        )
        conn.commit()
        assert store.reverse_readiness(transition["transition_id"])[
            "block_reasons"
        ] == ["successor_has_later_transition"]

        conn.execute(
            "UPDATE ticker_meta SET priority='low',updated_at=? WHERE ticker='NEW'",
            ("2026-08-26T13:59:59Z",),
        )
        conn.commit()
        blocked = store.reverse_readiness(transition["transition_id"])
        assert blocked["reversible"] is False
        assert blocked["block_reasons"] == [
            "reverse_state_changed",
            "successor_has_later_transition",
        ]
        assert blocked["observed_state_sha256"] != blocked["expected_state_sha256"]
        assert conn.execute(
            "SELECT COUNT(*) FROM ticker_identity_transition_attempts"
        ).fetchone()[0] == attempt_count
    finally:
        conn.close()
