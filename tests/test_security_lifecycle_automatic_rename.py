"""Provider-confirmed renames change collection scope, never removal intent."""

from dataclasses import replace
from datetime import date
import sqlite3

import pytest

from src.portfolio_state import PortfolioStore
from src.profile_state import ProfileStateStore
from src.security_lifecycle_decision_policy import evaluate_automation_decision
from src.security_lifecycle_investigation import observation_fingerprint
from src.security_lifecycle_listing_evidence import _evidence
from src.security_lifecycle_provider_authority import provider_transition_guard
from tests.test_security_lifecycle_provider_authority import FIGI, NOW, events, record, terminal_records
from tests.test_security_lifecycle_terminal_workflow import setup_workflow, workflow_worker
from tests.test_security_lifecycle_tracking_policy import assessment_rows, transition_rows


def rename_material(*, changed_on="2026-06-22", missing=None, conflicting_successor=False):
    rows = list(terminal_records())
    if missing is not None:
        rows.pop(missing)
    rows.append(record("massive_reference", "active", ticker="NEW", figi=FIGI))
    if conflicting_successor:
        rows.append(record("eodhd_symbol_directory", "inactive", ticker="NEW", expected=False))
    return tuple(_evidence(row) for row in rows) + (events((("OLD", "NEW", changed_on),)),)


def rename_workflow(tmp_path):
    c = setup_workflow(tmp_path, event_available=False, assess=False)
    c["material"] = rename_material()
    c["checks"].record(ticker="OLD", at=NOW, evidence=c["material"], diagnostics={})
    return c


def evaluate(material, sources=("manual_lists",)):
    calls = []

    def preview(request):
        calls.append(request)
        return {"eligible": True, "block_reasons": [], "transition_kind": request["transition_kind"]}

    decision = evaluate_automation_decision(case={"source": "listing_authority", "ticker": "OLD"},
        evidence=material, facts=(), current_date=date(2026, 9, 5), active_sources=sources, transition_preview=preview)
    return decision, calls


def test_exact_current_rename_requests_the_existing_transition_with_event_date():
    decision, calls = evaluate(rename_material())
    assert decision.decision_tier == "verified_automatic"
    assert decision.transition_requested
    assert decision.action_readiness == "transition_eligible"
    assert calls == [{"transition_kind": "symbol_continuation", "source_ticker": "OLD",
        "successor_ticker": "NEW", "effective_date": "2026-06-22", "outcomes": ("symbol_changed",)}]


@pytest.mark.parametrize("former_removed", (False, True))
def test_automatic_rename_moves_collection_without_resurrecting_removed_former(tmp_path, monkeypatch, former_removed):
    c = rename_workflow(tmp_path)
    if former_removed:
        c["tracking"].remove(c["tracking"].list_memberships()[0]["membership_id"], at=NOW)
    with sqlite3.connect(c["sa"]) as conn:
        sa_before = tuple(conn.iterdump())
    with sqlite3.connect(c["profile"]) as conn:
        removal_before = conn.execute("SELECT * FROM sa_tracking_events WHERE action='remove'").fetchall()
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    assert result["accepted"] == 1, result
    transition = transition_rows(c)[0]
    assert transition["kind"] == "symbol_continuation"
    assert transition["approval_authority"] == "automation_policy"
    applied = c["service"].execute_transition(transition["transition_id"],
        preview_sha256=transition["approved_preview_sha256"], trigger="scheduler", before_write=lambda: None)
    assert applied["status"] == "applied", applied
    assert c["sources"]() == {"LIVE": ("manual_lists",),
        "NEW": ("manual_lists",) if former_removed else ("manual_lists", "sa_alpha_picks_former")}
    assert ProfileStateStore(c["profile"]).get_ticker("OLD").lists == []
    assert ProfileStateStore(c["profile"]).get_ticker("NEW").lists == ["Manual"]
    c["tracking"].reconcile([c["observed"]], at=NOW)
    assert ("sa_alpha_picks_former" in c["sources"]()["NEW"]) is not former_removed
    with sqlite3.connect(c["sa"]) as conn:
        assert tuple(conn.iterdump()) == sa_before
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT * FROM sa_tracking_events WHERE action='remove'").fetchall() == removal_before
        assert conn.execute("SELECT source_ticker,successor_ticker FROM ticker_identity_links").fetchall() == [("OLD", "NEW")]
    repeated = c["service"].execute_transition(transition["transition_id"],
        preview_sha256=transition["approved_preview_sha256"], trigger="scheduler", before_write=lambda: None)
    assert repeated["status"] == "already_applied"


def test_check_only_does_not_approve_or_apply_an_automatic_rename(tmp_path, monkeypatch):
    c = rename_workflow(tmp_path)
    result = workflow_worker(c, monkeypatch, mutation_allowed=False).run(limit=1, mode="live")
    assert result["accepted"] == 1, result
    assert assessment_rows(c)[0]["outcomes"] == ["symbol_changed"]
    assert transition_rows(c) == []
    assert "OLD" in c["sources"]()
    assert "NEW" not in c["sources"]()


def test_v6_review_is_reassessed_once_without_rewriting_its_receipt(tmp_path, monkeypatch):
    from src import security_lifecycle_automation_worker as worker_module
    from src import security_lifecycle_decision_policy as policy
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore

    c = rename_workflow(tmp_path)
    previous_decision = replace(evaluate(c["material"])[0], decision_tier="review_suggested",
        action_readiness="not_applicable", transition_requested=False, rule_version="2")
    with monkeypatch.context() as previous:
        previous.setattr(worker_module, "AUTOMATION_POLICY_VERSION", "trusted-lifecycle-automation-v6")
        previous.setattr(policy, "AUTOMATION_POLICY_VERSION", "trusted-lifecycle-automation-v6")
        previous.setattr(policy, "RULE_VERSIONS", {**policy.RULE_VERSIONS, "lifecycle.provider_listing_status": "2"})
        previous.setattr(worker_module, "evaluate_automation_decision", lambda **kwargs: previous_decision)
        assert workflow_worker(c, previous).run(limit=1, mode="live")["drafted"] == 1
    with sqlite3.connect(c["profile"]) as conn:
        old_run = SecurityLifecycleInvestigationStore(conn).list_automation_runs(c["case_id"])[0]
    worker = workflow_worker(c, monkeypatch)
    assert worker.run(limit=1, mode="live")["accepted"] == 1
    assert worker.run(limit=1, mode="live")["skipped_current"] == 1
    with sqlite3.connect(c["profile"]) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        assert store.get_automation_run(old_run["run_id"]) == old_run
        assert {row["policy_version"] for row in store.list_automation_runs(c["case_id"])} == {
            "trusted-lifecycle-automation-v6", "trusted-lifecycle-automation-v7"}
    assert len(transition_rows(c)) == 1


def test_automatic_rename_uses_existing_reversal_without_erasing_a_tombstone(tmp_path, monkeypatch):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    c = rename_workflow(tmp_path)
    c["tracking"].remove(c["tracking"].list_memberships()[0]["membership_id"], at=NOW)
    before = c["sources"]()
    assert workflow_worker(c, monkeypatch).run(limit=1, mode="live")["accepted"] == 1
    transition = transition_rows(c)[0]
    assert c["service"].execute_transition(transition["transition_id"],
        preview_sha256=transition["approved_preview_sha256"], trigger="scheduler", before_write=lambda: None)["status"] == "applied"
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: NOW)
        assert store.reverse_readiness(transition["transition_id"])["reversible"]
        assert store.reverse(transition["transition_id"], trigger="attended_user")["status"] == "reversed"
    assert c["sources"]() == before
    c["tracking"].reconcile([c["observed"]], at=NOW)
    assert c["sources"]() == before


@pytest.mark.parametrize("sources", [(), ("portfolio_open",), ("manual_lists", "portfolio_open")])
def test_no_source_or_open_position_never_requests_unattended_rename(sources):
    decision, calls = evaluate(rename_material(), sources=sources)
    assert not decision.transition_requested
    assert calls == []
    if "portfolio_open" in sources:
        assert "portfolio_position_open" in decision.decision_issues


def test_historical_rename_stays_available_for_attended_review_only():
    decision, calls = evaluate(rename_material(changed_on="2024-01-01"))
    assert decision.decision_tier == "review_suggested"
    assert decision.outcomes == ("symbol_changed",)
    assert not decision.transition_requested
    assert calls == []


@pytest.mark.parametrize("missing", range(6))
def test_incomplete_old_listing_checks_do_not_authorize_unattended_rename(missing):
    decision, calls = evaluate(rename_material(missing=missing))
    assert not decision.transition_requested
    assert calls == []


def test_successor_active_inactive_conflict_cannot_establish_continuity():
    decision, calls = evaluate(rename_material(conflicting_successor=True))
    assert decision.outcomes != ("symbol_changed",)
    assert all(call["transition_kind"] != "symbol_continuation" for call in calls)


def test_exact_current_rename_passes_transaction_guard_without_human_acceptance(tmp_path):
    c = rename_workflow(tmp_path)
    observation = c["checks"].latest()["OLD"]["observation"]
    with sqlite3.connect(c["profile"]) as conn:
        assert provider_transition_guard(conn, ticker="OLD",
            observation_fingerprint_sha256=observation_fingerprint(observation), transition_kind="symbol_continuation",
            successor_ticker="NEW", effective_date="2026-06-22", at=NOW, human_accepted=False) == ()


@pytest.mark.parametrize("missing", range(6))
def test_transaction_guard_independently_rejects_incomplete_automatic_rename(tmp_path, missing):
    c = rename_workflow(tmp_path)
    c["checks"].record(ticker="OLD", at=NOW, evidence=rename_material(missing=missing), diagnostics={})
    observation = c["checks"].latest()["OLD"]["observation"]
    with sqlite3.connect(c["profile"]) as conn:
        assert provider_transition_guard(conn, ticker="OLD",
            observation_fingerprint_sha256=observation_fingerprint(observation), transition_kind="symbol_continuation",
            successor_ticker="NEW", effective_date="2026-06-22", at=NOW, human_accepted=False)


def test_historical_rename_guard_distinguishes_human_and_automatic_authority(tmp_path):
    c = rename_workflow(tmp_path)
    c["checks"].record(ticker="OLD", at=NOW, evidence=rename_material(changed_on="2024-01-01"), diagnostics={})
    observation = c["checks"].latest()["OLD"]["observation"]
    with sqlite3.connect(c["profile"]) as conn:
        arguments = dict(ticker="OLD", observation_fingerprint_sha256=observation_fingerprint(observation),
            transition_kind="symbol_continuation", successor_ticker="NEW", effective_date="2024-01-01", at=NOW)
        assert provider_transition_guard(conn, **arguments, human_accepted=False) == ("provider_legacy_event_review",)
        assert provider_transition_guard(conn, **arguments, human_accepted=True) == ()


@pytest.mark.parametrize("change", ["elapsed", "active_otc", "identity", "portfolio"])
def test_approved_rename_is_rechecked_before_writing(tmp_path, monkeypatch, change):
    c = rename_workflow(tmp_path)
    result = workflow_worker(c, monkeypatch).run(limit=1, mode="live")
    assert result["accepted"] == 1, result
    transition = transition_rows(c)[0]
    if change == "elapsed":
        c["now"][0] = "2026-09-10T01:00:00Z"
    elif change == "portfolio":
        portfolio = PortfolioStore(c["profile"])
        account = portfolio.ensure_manual_account()
        portfolio.upsert_manual_position(account_id=account.id, symbol="OLD", quantity=1)
    else:
        rows = list(terminal_records())
        if change == "active_otc":
            rows[2] = replace(rows[2], listing_status="active", composite_figi=FIGI)
        rows.append(record("massive_reference", "active", ticker="NEW",
            figi="BBG00HC114X0" if change == "identity" else FIGI))
        c["checks"].record(ticker="OLD", at="2026-09-05T01:01:00Z",
            evidence=tuple(_evidence(row) for row in rows) + (events((("OLD", "NEW", "2026-06-22"),)),), diagnostics={})
        c["now"][0] = "2026-09-05T01:01:00Z"
    applied = c["service"].execute_transition(transition["transition_id"],
        preview_sha256=transition["approved_preview_sha256"], trigger="scheduler", before_write=lambda: None)
    assert applied["status"] == "blocked", applied
    assert "OLD" in c["sources"]()
    assert "NEW" not in c["sources"]()
