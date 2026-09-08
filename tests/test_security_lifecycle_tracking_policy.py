"""Independent listing authority across parsing, receipts, worker and writes."""

from dataclasses import replace
from datetime import date
import json
import socket
import sqlite3

import pytest

from src.security_lifecycle_listing_evidence import _evidence
from src.security_lifecycle_provider_authority import classify_provider_listing, ticker_event_evidence
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
from src.ticker_identity_transition import TransitionOptions
from tests.test_security_lifecycle_provider_authority import NOW, FIGI, events, record, terminal_records
from tests.test_security_lifecycle_terminal_workflow import setup_workflow, workflow_worker


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("tracking_policy_test_must_not_use_network")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def classify(material, codes=()):
    return classify_provider_listing(ticker="OLD", evidence=material, today=date(2026, 9, 5), provider_codes=codes)


def parsed_candidate():
    from data_sources.lifecycle_provider_census_transport import CensusRequestBudget, LifecycleProviderCensusTransport
    from tests.test_lifecycle_provider_census_transport import FakeSession, json_response
    session = FakeSession([json_response({"status": "OK", "results": {"events": [
        {"type": "ticker_change", "date": "2026-06-22", "ticker_change": {"ticker": "NEW"}},
    ]}})])
    transport = LifecycleProviderCensusTransport(session=session)
    result = transport.fetch_massive_ticker_events(stable_id=FIGI, api_key="test-only", budget=CensusRequestBudget())
    assert result.events == ()
    assert result.latest_ticker == "NEW"
    assert len(session.calls) == 1
    transport.close()
    return ticker_event_evidence("OLD", result, at=NOW)


def assessment_rows(c):
    with sqlite3.connect(c["profile"]) as conn:
        return SecurityLifecycleInvestigationStore(conn).list_assessments(c["case_id"])


def transition_rows(c):
    with sqlite3.connect(c["profile"]) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM ticker_identity_transitions")]


@pytest.mark.parametrize("ended", ["2024-01-05", "2023-05-16"])
def test_historical_no_timeline_retirement_requires_attended_approval(tmp_path, monkeypatch, ended):
    c = setup_workflow(tmp_path, ended=ended, event_available=False, assess=False)
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    assert result["drafted"] == 1, result
    assert result["accepted"] == 0
    assert transition_rows(c) == []
    assessment = assessment_rows(c)[0]
    assert assessment["outcomes"] == ["listing_ended"]
    assert assessment["effective_date"] == ended
    assert assessment["status"] == "draft"
    options = TransitionOptions(execute_on=ended)
    with pytest.raises(ValueError, match="accepted_assessment_required"):
        c["service"].preview_case(c["case_id"], options=options)
    with sqlite3.connect(c["profile"]) as conn:
        investigation = SecurityLifecycleInvestigationStore(conn)
        investigation.accept_assessment(assessment["assessment_id"], observation_fingerprint_sha256=assessment["observation_fingerprint_sha256"],
                                        acceptance_authority="human", at=NOW)
        investigation.generate_action_proposals(case_id=c["case_id"], observation_fingerprint_sha256=assessment["observation_fingerprint_sha256"],
                                                sources_by_ticker=c["sources"](), at=NOW)
    preview = c["service"].preview_case(c["case_id"], options=options)
    assert preview["eligible"], preview["block_reasons"]
    approved = c["service"].approve_case(c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    result = c["service"].execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert result["status"] == "applied"
    assert "OLD" not in c["sources"]()


def test_candidate_timeline_survives_old_listing_retirement_without_alias(tmp_path, monkeypatch):
    c = setup_workflow(tmp_path, event_available=False, assess=False)
    c["checks"].record(ticker="OLD", at=NOW, evidence=(*c["material"], parsed_candidate()), diagnostics={})
    before = c["checks"].latest()["OLD"]
    decision = classify(before["evidence"])
    assert decision.listing_state == "inactive"
    assert decision.continuation_state == "candidate"
    assert decision.candidate_tickers == ("NEW",)
    assert decision.successor_ticker is None
    assert decision.listing_end_date == "2025-01-15"
    assert decision.continuation_effective_date is None
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    assert result["accepted"] == 1, result
    transition = transition_rows(c)[0]
    assert transition["kind"] == "terminal_delisting"
    result = c["service"].execute_transition(transition["transition_id"], preview_sha256=transition["approved_preview_sha256"],
                                           trigger="scheduler", before_write=lambda: None)
    assert result["status"] == "applied"
    assert "OLD" not in c["sources"]()
    assert "NEW" not in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT count(*) FROM ticker_identity_links").fetchone()[0] == 0
    after = c["checks"].latest()["OLD"]
    assert after == before
    assert classify(after["evidence"]).candidate_tickers == ("NEW",)


def test_multiple_timelines_are_not_reported_as_unavailable():
    material = tuple(_evidence(row) for row in terminal_records()) + (events(), parsed_candidate())
    result = classify(material)
    assert result.listing_state == "inactive"
    assert result.state == "terminal"
    assert result.continuation_state == "ambiguous"
    assert result.continuation_reasons == ("successor_ambiguous",)
    assert result.candidate_tickers == ("NEW",)
    assert result.successor_ticker is None


@pytest.mark.parametrize("missing", range(6))
def test_timeline_failure_never_excuses_missing_required_listing_material(tmp_path, monkeypatch, missing):
    c = setup_workflow(tmp_path, event_available=False, assess=False)
    rows = c["material"]
    c["checks"].record(ticker="OLD", at=NOW, evidence=rows[:missing] + rows[missing + 1:], diagnostics={}, blockers=("massive_timeline_not_found",))
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    assert result["blocked"] == 1, result
    assert transition_rows(c) == []
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("code", ["massive_rate_limited", "massive_credential_missing", "eodhd_access_denied", "nasdaq_unavailable", "unclassified_failure"])
def test_unattributed_provider_failure_still_blocks_complete_material(tmp_path, monkeypatch, code):
    c = setup_workflow(tmp_path, event_available=False, assess=False)
    c["checks"].record(ticker="OLD", at=NOW, evidence=c["material"], diagnostics={}, blockers=(code,))
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    assert result["blocked"] == 1, result
    assert transition_rows(c) == []
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("code", ["massive_timeline_not_found", "massive_timeline_rate_limited", "massive_successor_rate_limited"])
def test_scoped_continuation_failure_is_retained_without_vetoing_listing_retirement(tmp_path, monkeypatch, code):
    c = setup_workflow(tmp_path, event_available=False, assess=False)
    timeline = (events((("OLD", "NEW", "2026-06-22"),)),) if code.startswith("massive_successor_") else ()
    c["checks"].record(ticker="OLD", at=NOW, evidence=(*c["material"], *timeline), diagnostics={}, blockers=(code,))
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    assert result["accepted"] == 1, result
    assert c["checks"].latest()["OLD"]["blockers"] == [code]
    assert len(transition_rows(c)) == 1


@pytest.mark.parametrize("change", ["otc", "identity", "stale", "incomplete", "future", "invalid_date"])
def test_human_acceptance_cannot_bypass_real_listing_vetoes(tmp_path, change):
    c = setup_workflow(tmp_path, event_available=False)
    rows = list(terminal_records())
    if change == "otc":
        rows[2] = replace(rows[2], listing_status="active", composite_figi=FIGI)
    elif change == "identity":
        rows[3] = replace(rows[3], composite_figi="BBG00HC114X0")
    elif change == "stale":
        rows[3] = replace(rows[3], retrieved_at="2026-08-01T00:00:00Z")
    elif change == "incomplete":
        rows[3] = replace(rows[3], snapshot_complete=False)
    else:
        rows[0] = replace(rows[0], delisted_utc="2026-09-06" if change == "future" else "not-a-date")
    c["checks"].record(ticker="OLD", at=NOW, evidence=tuple(_evidence(row) for row in rows), diagnostics={}, blockers=("massive_not_found",))
    row = c["checks"].latest()["OLD"]
    from src.security_lifecycle_provider_authority import provider_transition_guard
    with sqlite3.connect(c["profile"]) as conn:
        blockers = provider_transition_guard(conn, ticker="OLD", observation_fingerprint_sha256=observation_fingerprint(row["observation"]),
            transition_kind="terminal_delisting", successor_ticker=None, effective_date=c["ended"], at=NOW, human_accepted=True)
    assert blockers
    assert "OLD" in c["sources"]()


def test_confirmed_continuation_keeps_dates_distinct_and_stays_attended():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision
    material = tuple(_evidence(row) for row in (*terminal_records(), record("massive_reference", "active", ticker="NEW", figi=FIGI)))
    material += (events((("OLD", "NEW", "2026-06-22"),)),)
    result = classify(material)
    assert result.listing_end_date == "2025-01-15"
    assert result.continuation_effective_date == "2026-06-22"
    assert result.successor_ticker == "NEW"
    assert result.candidate_tickers == ()
    decision = evaluate_automation_decision(case={"source": "listing_authority", "ticker": "OLD"}, evidence=material, facts=(),
        current_date="2026-09-05", active_sources=("manual_lists",), transition_preview=lambda request: pytest.fail("rename_must_stay_attended"))
    assert decision.decision_tier == "review_suggested"
    assert decision.outcomes == ("symbol_changed",)
    assert decision.effective_date == "2026-06-22"
    assert not decision.transition_requested


def test_old_reason_string_cannot_substitute_for_listing_authority(tmp_path, monkeypatch):
    from src import security_lifecycle_provider_authority as authority
    c = setup_workflow(tmp_path, event_available=False)
    row = c["checks"].latest()["OLD"]
    kwargs = dict(ticker="OLD", observation_fingerprint_sha256=observation_fingerprint(row["observation"]),
                  transition_kind="terminal_delisting", successor_ticker=None, effective_date=c["ended"], at=NOW, human_accepted=True)
    with sqlite3.connect(c["profile"]) as conn:
        assert authority.provider_transition_guard(conn, **kwargs) == ()
        unresolved = authority.ProviderListingDecision("unresolved", listing_reasons=("successor_check_unavailable",), listing_end_date=c["ended"])
        monkeypatch.setattr(authority, "classify_provider_listing", lambda **kw: unresolved)
        assert authority.provider_transition_guard(conn, **kwargs) == ("provider_terminal_not_confirmed",)


def test_unknown_transition_kind_cannot_pass_the_provider_guard(tmp_path):
    from src.security_lifecycle_provider_authority import provider_transition_guard
    c = setup_workflow(tmp_path, event_available=False)
    row = c["checks"].latest()["OLD"]
    with sqlite3.connect(c["profile"]) as conn:
        assert provider_transition_guard(conn, ticker="OLD", observation_fingerprint_sha256=observation_fingerprint(row["observation"]),
            transition_kind="acquisition_pending", successor_ticker=None, effective_date=c["ended"], at=NOW, human_accepted=True) == ("provider_transition_kind_invalid",)


def test_new_policy_reenters_old_blocked_snapshot_once_without_rewriting_it(tmp_path, monkeypatch):
    from src.security_lifecycle_fact_kernel import AutomationBlocker, SecurityLifecycleFactKernel
    from src.security_lifecycle_automation_worker import AUTOMATION_EXECUTION_REVISION
    from tests.test_security_lifecycle_provider_snapshot import _FIXTURE, insert_snapshot, legacy_row
    c = setup_workflow(tmp_path, event_available=False, assess=False)
    frozen = legacy_row(next(row for row in _FIXTURE["checks"] if row["name"] == "missing_timeline_with_transport_blocker"))
    with sqlite3.connect(c["profile"]) as conn:
        insert_snapshot(conn, frozen)
    old_snapshot = c["checks"].latest()["OLD"]
    assert old_snapshot["state"] == "unresolved"
    assert old_snapshot["blockers"] == ["massive_not_found"]
    fingerprint = observation_fingerprint(old_snapshot["observation"])
    with sqlite3.connect(c["profile"]) as conn:
        investigation = SecurityLifecycleInvestigationStore(conn)
        kernel = SecurityLifecycleFactKernel(investigation)
        claim = kernel.reserve_run(case_id=c["case_id"], observation_fingerprint_sha256=fingerprint,
            policy_version="trusted-lifecycle-automation-v5", mode="live", execution_revision=AUTOMATION_EXECUTION_REVISION,
            execution_owner_id="old-worker", query_context={}, diagnostics={}, at=NOW)
        kernel.complete_run(run_id=claim.run_id, evidence=old_snapshot["evidence"], facts=(),
            blockers=(AutomationBlocker("listing_status_unresolved", False, {"reasons": ["successor_check_unavailable"]}),),
            decision_tier=None, action_readiness=None, retry_at=None, diagnostics={}, at=NOW)
        old_run = investigation.get_automation_run(claim.run_id)
    worker = workflow_worker(c, monkeypatch)
    result = worker.run(limit=1, mode="live")
    assert result["accepted"] == 1, result
    assert worker.run(limit=1, mode="live")["skipped_current"] == 1
    with sqlite3.connect(c["profile"]) as conn:
        investigation = SecurityLifecycleInvestigationStore(conn)
        runs = investigation.list_automation_runs(c["case_id"])
        assert len(runs) == 2
        assert {row["policy_version"] for row in runs} == {"trusted-lifecycle-automation-v5", "trusted-lifecycle-automation-v6"}
        assert investigation.get_automation_run(claim.run_id) == old_run
        conn.row_factory = sqlite3.Row
        assert dict(conn.execute("SELECT * FROM security_lifecycle_provider_checks WHERE check_id=?", (frozen["check_id"],)).fetchone()) == frozen
    assert c["checks"].latest()["OLD"] == old_snapshot


def test_policy_change_does_not_replay_an_applied_retirement(tmp_path, monkeypatch):
    from src import security_lifecycle_automation_worker as worker_module
    from src import security_lifecycle_decision_policy as policy
    c = setup_workflow(tmp_path, assess=False)
    with monkeypatch.context() as previous:
        previous.setattr(worker_module, "AUTOMATION_POLICY_VERSION", "trusted-lifecycle-automation-v5")
        previous.setattr(policy, "AUTOMATION_POLICY_VERSION", "trusted-lifecycle-automation-v5")
        previous.setattr(policy, "RULE_VERSIONS", {**policy.RULE_VERSIONS, "lifecycle.provider_listing_status": "1"})
        assert workflow_worker(c, previous).run(limit=1, mode="live")["accepted"] == 1
        transition = transition_rows(c)[0]
        assert c["service"].execute_transition(transition["transition_id"], preview_sha256=transition["approved_preview_sha256"],
            trigger="scheduler", before_write=lambda: None)["status"] == "applied"
    before = transition_rows(c)
    with sqlite3.connect(c["profile"]) as conn:
        receipts = conn.execute("SELECT * FROM sa_tracking_events").fetchall()
    assert "OLD" not in c["sources"]()
    worker = workflow_worker(c, monkeypatch)
    result = worker.run(limit=1, mode="live")
    assert result["failed"] == 0, result
    assert transition_rows(c) == before
    assert worker.run(limit=1, mode="live")["skipped_current"] == 1
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT * FROM sa_tracking_events").fetchall() == receipts


def test_untracked_old_listing_is_reported_without_requesting_a_new_mutation():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision
    result = evaluate_automation_decision(case={"source": "listing_authority", "ticker": "OLD"},
        evidence=tuple(_evidence(row) for row in terminal_records()), facts=(), current_date="2026-09-05", active_sources=(),
        transition_preview=lambda request: pytest.fail("no_tracking_effect_to_preview"))
    assert result.outcomes == ("listing_ended",)
    assert result.action_readiness == "not_applicable"
    assert not result.transition_requested


def test_iterable_sources_do_not_lose_the_open_position_veto():
    from src.security_lifecycle_decision_policy import evaluate_automation_decision
    result = evaluate_automation_decision(case={"source": "listing_authority", "ticker": "OLD"},
        evidence=tuple(_evidence(row) for row in terminal_records()), facts=(), current_date="2026-09-05",
        active_sources=iter(("manual_lists", "portfolio_open")),
        transition_preview=lambda request: pytest.fail("open_position_was_lost"))
    assert "portfolio_position_open" in result.decision_issues
    assert not result.transition_requested


def test_listing_end_timestamp_uses_utc_before_the_future_date_guard():
    rows = list(terminal_records())
    rows[0] = replace(rows[0], delisted_utc="2026-09-05T23:30:00-02:00")
    result = classify(tuple(_evidence(row) for row in rows))
    assert result.listing_state == "unresolved"
    assert "delisting_date_future" in result.listing_reasons


def test_malformed_identity_material_is_reviewable_not_a_classifier_crash():
    rows = list(terminal_records())
    rows[3] = replace(rows[3], issuer_cik=["0000000001"])
    result = classify(tuple(_evidence(row) for row in rows))
    assert result.listing_state == "unresolved"
    assert "listing_identity_conflict" in result.listing_reasons
