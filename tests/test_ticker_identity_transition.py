from __future__ import annotations

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
