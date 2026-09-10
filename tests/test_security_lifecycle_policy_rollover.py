"""Policy rollover changes current presentation, never retained receipts."""

from dataclasses import replace
from datetime import datetime
import socket
import sqlite3

import pytest

from src import security_lifecycle_automation_worker as worker_module
from src import security_lifecycle_decision_policy as policy
from src.profile_state import ProfileStateStore
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
from src.security_lifecycle_listing_evidence import _evidence
from src.service import security_lifecycle_automation_scheduler as automation_scheduler
from src.service import ticker_identity_scheduler as scheduler
from src.ticker_identity_transition import TransitionOptions, TickerIdentityTransitionStore
from src.tools.security_lifecycle_tools import SecurityLifecycleReadService
from tests import test_security_lifecycle_terminal_workflow as workflow_fixtures
from tests.test_security_lifecycle_provider_authority import NOW, events, terminal_records
from tests.test_security_lifecycle_terminal_workflow import setup_workflow, workflow_worker
from tests.test_security_lifecycle_tracking_policy import transition_rows


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("policy_rollover_must_not_use_network")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def _v6_approval(c, monkeypatch):
    with monkeypatch.context() as previous:
        previous.setattr(worker_module, "AUTOMATION_POLICY_VERSION", "trusted-lifecycle-automation-v6")
        previous.setattr(policy, "AUTOMATION_POLICY_VERSION", "trusted-lifecycle-automation-v6")
        previous.setattr(policy, "RULE_VERSIONS", {**policy.RULE_VERSIONS, "lifecycle.provider_listing_status": "2"})
        assert workflow_worker(c, previous).run(limit=1, mode="live")["accepted"] == 1
        transition = transition_rows(c)[0]
        assert transition["status"] == "approved"
        return transition


def _run_due(c, monkeypatch):
    monkeypatch.setattr(scheduler, "_service", lambda: c["service"])
    monkeypatch.setattr(scheduler, "require_profile_state_write", lambda *args, **kwargs: None)
    return scheduler.run_due_ticker_identity_transitions(
        allow_automation_approved=True,
        transition_mutation_allowed=lambda: True,
        now=datetime.fromisoformat(c["now"][0].replace("Z", "+00:00")),
    )


def _reader(c):
    return SecurityLifecycleReadService(
        market_db_path=str(c["market"]), profile_db_path=str(c["profile"]), source_loader=c["sources"],
    )


def _current(c, *, review_id=None):
    result = _reader(c).list_current_reviews(at=c["now"][0], case_id=c["case_id"])
    matches = [row for row in result["items"] if review_id is None or row["review_id"] == review_id]
    assert len(matches) == 1
    return result, matches[0]


def _profile_snapshot(c):
    with sqlite3.connect(c["profile"]) as conn:
        return tuple(conn.iterdump())


@pytest.mark.parametrize("scheduler_first", (True, False))
def test_applied_rollover_replaces_obsolete_pending_projection_without_losing_receipts(
    tmp_path, monkeypatch, scheduler_first,
):
    c = setup_workflow(tmp_path, assess=False)
    initial_sources = c["sources"]()
    old = _v6_approval(c, monkeypatch)
    if scheduler_first:
        blocked = _run_due(c, monkeypatch)
        assert blocked["applied"] == 0
        assert blocked["needs_review"] == 1
        assert c["sources"]() == initial_sources

    worker = workflow_worker(c, monkeypatch)
    assert worker.run(limit=1, mode="live")["accepted"] == 1
    applied = _run_due(c, monkeypatch)
    assert applied["applied"] == 1
    assert applied["needs_review"] == (0 if scheduler_first else 1)
    assert worker.run(limit=1, mode="live")["skipped_current"] == 1
    transitions = transition_rows(c)
    assert len(transitions) == 2
    stale = next(row for row in transitions if row["transition_id"] == old["transition_id"])
    replacement = next(row for row in transitions if row["transition_id"] != old["transition_id"])
    assert stale["status"] == "needs_review"
    assert replacement["status"] == "applied"
    before = _profile_snapshot(c)

    result, row = _current(c)
    assert row["next_action"]["transition_id"] == replacement["transition_id"]
    assert row["next_action"]["state"] == "applied"
    assert row["next_action"]["current_effects_match"] is True
    assert row["next_action"]["can_reverse"] is True
    assert row["next_action"]["block_reasons"] == []
    assert row["reason"] == "removal_applied"
    assert row["bucket"] == "history"
    assert result["counts"] == {"attention": 0, "history": 1}
    assert row["collection"] == {"state": "not_tracking", "sources": []}
    assert _reader(c).get_current_review(row["review_id"], at=NOW)["item"] == row
    assert _profile_snapshot(c) == before

    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: NOW)
        assert store.reverse(row["next_action"]["transition_id"], trigger="attended_user")["status"] == "reversed"
    assert c["sources"]() == initial_sources


@pytest.mark.parametrize("attempted", (False, True))
def test_unreplaced_old_policy_approval_remains_actionable(tmp_path, monkeypatch, attempted):
    c = setup_workflow(tmp_path, assess=False)
    old = _v6_approval(c, monkeypatch)
    if attempted:
        assert _run_due(c, monkeypatch)["needs_review"] == 1
    _, row = _current(c)
    assert row["next_action"]["transition_id"] == old["transition_id"]
    assert row["next_action"]["state"] == ("blocked" if attempted else "approved")
    assert row["next_action"]["kind"] == ("recheck" if attempted else "resume")
    assert row["bucket"] == "attention"
    assert row["collection"]["state"] == "tracking"


def test_current_policy_pending_action_still_precedes_an_older_applied_receipt(tmp_path, monkeypatch):
    c = setup_workflow(tmp_path, assess=False)
    with monkeypatch.context() as previous:
        previous.setattr(policy, "AUTOMATION_POLICY_VERSION", "trusted-lifecycle-automation-v6")
        previous.setattr(policy, "RULE_VERSIONS", {**policy.RULE_VERSIONS, "lifecycle.provider_listing_status": "2"})
        old = _v6_approval(c, previous)
        assert _run_due(c, previous)["applied"] == 1
    profile = ProfileStateStore(c["profile"])
    profile.restore_ticker("OLD")
    profile.set_universe_hidden("OLD", False)
    assert workflow_worker(c, monkeypatch).run(limit=1, mode="live")["accepted"] == 1
    pending = next(row for row in transition_rows(c) if row["transition_id"] != old["transition_id"])
    result, row = _current(c)
    assert row["next_action"]["transition_id"] == pending["transition_id"]
    assert row["next_action"]["state"] == "approved"
    assert row["next_action"]["kind"] == "resume"
    assert row["reason"] == "action_pending"
    assert result["counts"] == {"attention": 1, "history": 0}


@pytest.mark.parametrize("old_policy,ended", (("current", "2025-01-15"), ("v6", "2025-02-01")))
def test_only_obsolete_policy_approvals_for_the_same_event_are_superseded(tmp_path, monkeypatch, old_policy, ended):
    records = tuple(replace(row, primary_exchange="XNYS", security_type="CS", issuer_cik="0000000001")
                    if row.delisted_utc else row for row in terminal_records())
    monkeypatch.setattr(workflow_fixtures, "terminal_records", lambda: records)
    c = setup_workflow(tmp_path, assess=False)
    if old_policy == "v6":
        pending = _v6_approval(c, monkeypatch)
    else:
        assert workflow_worker(c, monkeypatch).run(limit=1, mode="live")["accepted"] == 1
        pending = transition_rows(c)[0]
    _, original_review = _current(c)
    c["now"][0] = "2026-09-05T01:01:00Z"
    material = tuple(_evidence(replace(row, delisted_utc=ended) if row.delisted_utc else row)
                     for row in records) + (events(()),)
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=material, diagnostics={})
    worker = workflow_worker(c, monkeypatch)
    monkeypatch.setattr(worker, "_clock", lambda: c["now"][0])
    monkeypatch.setattr(automation_scheduler, "_clock", lambda: c["now"][0])
    assert worker.run(limit=1, mode="live")["accepted"] == 1
    replacement = next(row for row in transition_rows(c) if row["transition_id"] != pending["transition_id"])
    assert c["service"].execute_transition(
        replacement["transition_id"], preview_sha256=replacement["approved_preview_sha256"],
        trigger="scheduler", before_write=lambda: None,
    )["status"] == "applied"
    _, row = _current(c, review_id=original_review["review_id"])
    assert row["next_action"]["transition_id"] == pending["transition_id"]
    assert row["next_action"]["state"] == "approved"
    assert row["reason"] == "action_pending"


@pytest.mark.parametrize("execute_on,state", (("2025-01-15", "approved"), ("2026-09-06", "scheduled")))
def test_attended_pending_action_is_not_hidden_by_a_later_apply(tmp_path, execute_on, state):
    c = setup_workflow(tmp_path)
    options = TransitionOptions(execute_on=execute_on)
    preview = c["service"].preview_case(c["case_id"], options=options)
    attended = c["service"].approve_case(
        c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None,
    )
    fingerprint = observation_fingerprint(c["checks"].latest()["OLD"]["observation"])
    with sqlite3.connect(c["profile"]) as conn:
        investigation = SecurityLifecycleInvestigationStore(conn)
        assessment_id = investigation.create_assessment(
            case_id=c["case_id"], relevance="direct_tracked_security", confidence="high", author="human",
            conclusion="Confirmed the same listing event.", impact_summary="Retire tracking and retain history.",
            outcomes=("listing_ended",), effective_date=c["ended"],
            citations=[{"reference_kind": "observation", "cited_content_sha256": fingerprint}],
            observation_fingerprint_sha256=fingerprint, at=NOW,
        )
        investigation.accept_assessment(
            assessment_id, observation_fingerprint_sha256=fingerprint, acceptance_authority="human", at=NOW,
        )
        investigation.generate_action_proposals(
            case_id=c["case_id"], observation_fingerprint_sha256=fingerprint, sources_by_ticker=c["sources"](), at=NOW,
        )
    immediate = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=immediate)
    replacement = c["service"].approve_case(
        c["case_id"], options=immediate, preview_sha256=preview["preview_sha256"], before_write=lambda: None,
    )
    assert c["service"].execute_transition(
        replacement["transition_id"], preview_sha256=replacement["approved_preview_sha256"],
        trigger="scheduler", before_write=lambda: None,
    )["status"] == "applied"
    _, row = _current(c)
    assert row["next_action"]["transition_id"] == attended["transition_id"]
    assert row["next_action"]["state"] == state
    assert row["reason"] == ("action_pending" if state == "approved" else "action_scheduled")
