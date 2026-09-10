"""Automatic renames preserve archived successor membership intent."""

from datetime import date
import json
import socket
import sqlite3

import pytest

from src.profile_state import ProfileStateStore
from src.security_lifecycle_decision_policy import evaluate_automation_decision
from src.security_lifecycle_investigation import observation_fingerprint
from src.ticker_identity_transition import (
    TickerIdentityTransitionStore,
    TransitionOptions,
    build_automation_transition_preflight,
    profile_snapshot_sha256,
)
from tests.test_security_lifecycle_automatic_rename import (
    NOW,
    assessment_rows,
    rename_workflow,
    transition_rows,
    workflow_worker,
)


MEMBERSHIP_KINDS = ("manual_lists", "legacy_config_seed")
OPTIONS = TransitionOptions(execute_on="2026-06-22")


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("rename_suppression_test_must_not_use_network")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def _archive_successor(c, kind, *, overlapping=True):
    if kind == "manual_lists":
        profile = ProfileStateStore(c["profile"])
        if overlapping:
            watchlist = next(row for row in profile.list_watchlists() if row.name == "Manual")
        else:
            watchlist = profile.create_list("Unrelated", kind="custom")
        profile.add_member(watchlist.id, "NEW")
        profile.archive_ticker("NEW")
    else:
        with sqlite3.connect(c["profile"]) as conn:
            if overlapping:
                conn.execute(
                    "INSERT INTO universe_source_memberships "
                    "(source_key,ticker,created_at,archived_at) VALUES (?,?,?,NULL)",
                    ("legacy_config_seed", "OLD", NOW),
                )
            conn.execute(
                "INSERT INTO universe_source_memberships "
                "(source_key,ticker,created_at,archived_at) VALUES (?,?,?,?)",
                ("legacy_config_seed", "NEW", NOW, NOW),
            )


def _successor_archived_at(c, kind, *, overlapping=True):
    with sqlite3.connect(c["profile"]) as conn:
        if kind == "manual_lists":
            row = conn.execute(
                "SELECT m.archived_at FROM watchlist_memberships m "
                "JOIN watchlists w ON w.id=m.list_id WHERE m.ticker='NEW' AND w.name=?",
                ("Manual" if overlapping else "Unrelated",),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT archived_at FROM universe_source_memberships "
                "WHERE source_key='legacy_config_seed' AND ticker='NEW'",
            ).fetchone()
    assert row is not None
    return row[0]


def _owned_state(c):
    tables = (
        "watchlists", "watchlist_memberships", "universe_source_memberships",
        "ticker_meta", "ticker_tags", "sa_tracking_memberships", "sa_tracking_events",
        "ticker_identity_links", "ticker_identity_transition_activity",
    )
    with sqlite3.connect(c["profile"]) as conn:
        return {
            table: conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in tables
        }


@pytest.mark.parametrize("kind", MEMBERSHIP_KINDS)
def test_automation_preflight_blocks_archived_successor_membership(tmp_path, kind):
    c = rename_workflow(tmp_path)
    _archive_successor(c, kind)
    observation = c["checks"].latest()["OLD"]["observation"]
    case = {
        "case_id": c["case_id"], "source": "listing_authority", "ticker": "OLD",
        "observation_fingerprint_sha256": observation_fingerprint(observation),
    }
    sources = c["sources"]()["OLD"]
    previews = []
    with sqlite3.connect(c["profile"]) as conn:
        changes = conn.total_changes

        def preview(request):
            result = build_automation_transition_preflight(
                conn, case=case, request=request, sources=sources, at=NOW,
            )
            previews.append(result)
            return result

        decision = evaluate_automation_decision(
            case=case, evidence=c["material"], facts=(), current_date=date(2026, 9, 5),
            active_sources=sources, transition_preview=preview,
        )
        assert conn.total_changes == changes
    assert len(previews) == 1
    preflight = previews[0]
    assert preflight["effects"]["suppression"]["successor_hidden"] is False
    effect = "watchlists" if kind == "manual_lists" else "legacy_config_seed"
    assert preflight["effects"][effect]["reactivate"]
    assert preflight["eligible"] is False
    assert preflight["block_reasons"] == ["provider_continuation_review"]
    assert preflight["preview_sha256"] == profile_snapshot_sha256(preflight)
    assert decision.action_readiness == "action_blocked"
    assert decision.decision_issues == ("preview:provider_continuation_review",)
    assert decision.transition_requested is False


@pytest.mark.parametrize("kind", MEMBERSHIP_KINDS)
def test_worker_cannot_reactivate_archived_successor_membership(tmp_path, monkeypatch, kind):
    c = rename_workflow(tmp_path)
    _archive_successor(c, kind)
    before = _owned_state(c)
    sources = c["sources"]()
    archived_at = _successor_archived_at(c, kind)
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    transitions = transition_rows(c)
    # Follow any approved work through the real apply path to expose resurrection.
    for transition in transitions:
        c["service"].execute_transition(
            transition["transition_id"], preview_sha256=transition["approved_preview_sha256"],
            trigger="scheduler", before_write=lambda: None,
        )
    assert _successor_archived_at(c, kind) == archived_at
    assert _owned_state(c) == before
    assert c["sources"]() == sources
    assert result["failed"] == 0
    assert transitions == []
    assert assessment_rows(c)[0]["outcomes"] == ["symbol_changed"]


@pytest.mark.parametrize("kind", MEMBERSHIP_KINDS)
def test_automatic_approval_rechecks_archived_successor_membership(tmp_path, monkeypatch, kind):
    c = rename_workflow(tmp_path)
    assert workflow_worker(c, monkeypatch, mutation_allowed=False).run(limit=1, mode="live")["accepted"] == 1
    _archive_successor(c, kind)
    before = _owned_state(c)
    preview = c["service"].preview_case(c["case_id"], options=OPTIONS)
    assert preview["eligible"] is True  # An attended review may approve these effects.
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: NOW)
        with pytest.raises(ValueError, match="^preview_changed$"):
            store.approve_automation(
                preview=preview, approved_preview_sha256=preview["preview_sha256"],
            )
        assert not conn.in_transaction
    assert transition_rows(c) == []
    assert _owned_state(c) == before


@pytest.mark.parametrize("kind", MEMBERSHIP_KINDS)
@pytest.mark.parametrize("trigger", ["scheduler", "attended_user"])
def test_preexisting_automatic_approval_cannot_reactivate_successor(tmp_path, monkeypatch, kind, trigger):
    c = rename_workflow(tmp_path)
    assert workflow_worker(c, monkeypatch).run(limit=1, mode="live")["accepted"] == 1
    transition = transition_rows(c)[0]
    _archive_successor(c, kind)
    preview = c["service"].preview_case(c["case_id"], options=OPTIONS)
    assert preview["eligible"] is True
    before = _owned_state(c)
    with sqlite3.connect(c["profile"]) as conn:
        # Model an unsafe pre-fix approval with real policy authority and a matching
        # archived-membership snapshot. A stale-hash veto alone cannot protect it.
        conn.execute(
            "UPDATE ticker_identity_transitions SET approved_preview_sha256=?,"
            "approved_preview_json=? WHERE transition_id=?",
            (preview["preview_sha256"], json.dumps(preview), transition["transition_id"]),
        )
        conn.commit()
        store = TickerIdentityTransitionStore(conn, clock=lambda: NOW)
        result = store.apply(
            transition["transition_id"], current_preview=preview,
            expected_preview_sha256=preview["preview_sha256"], trigger=trigger,
        )
        assert not conn.in_transaction
    assert result["status"] == "blocked"
    assert result["block_reasons"] == ["provider_continuation_review"]
    assert result["transition"]["status"] == "needs_review"
    assert _owned_state(c) == before


@pytest.mark.parametrize("kind", MEMBERSHIP_KINDS)
def test_automatic_apply_rereads_membership_not_replayed_effects(tmp_path, monkeypatch, kind):
    c = rename_workflow(tmp_path)
    assert workflow_worker(c, monkeypatch).run(limit=1, mode="live")["accepted"] == 1
    transition = transition_rows(c)[0]
    preview = json.loads(transition["approved_preview_json"])
    _archive_successor(c, kind)
    before = _owned_state(c)
    with sqlite3.connect(c["profile"]) as conn:
        result = TickerIdentityTransitionStore(conn, clock=lambda: NOW).apply(
            transition["transition_id"], current_preview=preview,
            expected_preview_sha256=transition["approved_preview_sha256"], trigger="scheduler",
        )
    assert result["status"] == "blocked"
    assert result["block_reasons"] == ["provider_continuation_review"]
    assert _owned_state(c) == before


@pytest.mark.parametrize("kind", MEMBERSHIP_KINDS)
def test_attended_review_can_explicitly_reactivate_successor_membership(tmp_path, monkeypatch, kind):
    c = rename_workflow(tmp_path)
    _archive_successor(c, kind)
    assert workflow_worker(c, monkeypatch, mutation_allowed=False).run(limit=1, mode="live")["accepted"] == 1
    preview = c["service"].preview_case(c["case_id"], options=OPTIONS)
    assert preview["eligible"] is True
    assert preview["effects"]["suppression"]["successor_hidden"] is False
    approved = c["service"].approve_case(
        c["case_id"], options=OPTIONS, preview_sha256=preview["preview_sha256"], before_write=lambda: None,
    )
    assert approved["approval_authority"] == "attended_user"
    result = c["service"].execute_transition(
        approved["transition_id"], preview_sha256=preview["preview_sha256"],
        trigger="attended_user", before_write=lambda: None,
    )
    assert result["status"] == "applied"
    assert _successor_archived_at(c, kind) is None
    assert "OLD" not in c["sources"]()
    assert kind in c["sources"]()["NEW"]


@pytest.mark.parametrize("kind", MEMBERSHIP_KINDS)
def test_unrelated_archived_membership_does_not_block_automatic_rename(tmp_path, monkeypatch, kind):
    c = rename_workflow(tmp_path)
    _archive_successor(c, kind, overlapping=False)
    archived_at = _successor_archived_at(c, kind, overlapping=False)
    assert workflow_worker(c, monkeypatch).run(limit=1, mode="live")["accepted"] == 1
    transition = transition_rows(c)[0]
    result = c["service"].execute_transition(
        transition["transition_id"], preview_sha256=transition["approved_preview_sha256"],
        trigger="scheduler", before_write=lambda: None,
    )
    assert result["status"] == "applied"
    assert _successor_archived_at(c, kind, overlapping=False) == archived_at
    assert "OLD" not in c["sources"]()
    assert ProfileStateStore(c["profile"]).get_ticker("NEW").lists == ["Manual"]
