"""Real profile transactions, source projection and later SA observations."""

from dataclasses import replace
import sqlite3

import pytest

from src.active_universe import build_active_universe_snapshot
from src.profile_state import ProfileStateStore
from src.portfolio_state import PortfolioStore
from src.sa_tracking_memberships import SaTrackingMembershipStore
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
from src.security_lifecycle_provider_store import ProviderCheckStore
from src.security_lifecycle_listing_evidence import _evidence
from src.security_lifecycle_schema import create_profile_schema, create_market_schema
from src.ticker_identity_schema import create_ticker_identity_schema
from src.ticker_identity_service import TickerIdentityService
from src.ticker_identity_transition import TransitionOptions, TickerIdentityTransitionStore
from tests.test_security_lifecycle_provider_authority import NOW, record, terminal_records, events


def setup_workflow(tmp_path, *, ticker="OLD", ended="2025-01-15", event_available=True, assess=True):
    from src import sa_capture_store
    profile, market, sa = (tmp_path / name for name in ("profile_state.db", "market_data.db", "sa_capture.db"))
    ProfileStateStore(profile).import_lists([{"name": "Manual", "kind": "custom", "tickers": [ticker, "LIVE"]}])
    PortfolioStore(profile)
    with sqlite3.connect(profile) as conn:
        create_profile_schema(conn)
        create_ticker_identity_schema(conn)
        SaTrackingMembershipStore.install(conn)
    with sqlite3.connect(market) as conn:
        create_market_schema(conn)
    sa_capture_store.connect(str(sa)).close()
    tracking = SaTrackingMembershipStore(profile)
    observed = {"lineage_id": 1, "ticker": ticker, "picked_date": "2023-01-01", "portfolio_status": "closed", "observed_at": NOW}
    tracking.reconcile([observed], at=NOW, bootstrap_actor="attended_user")
    from tests.test_security_lifecycle_provider_authority import FIGI
    # Synthetic responses preserve the archived known-case identifiers; they are
    # not new live observations and cannot authorize a production cutover.
    stable_id = {"ARCH": "BBG00DZS69M1", "LTHM": "BBG00MFLBVG0", "TA": "BBG000F71CC6"}.get(ticker, FIGI)
    material = tuple(_evidence(replace(
        row, ticker=ticker,
        composite_figi=stable_id if row.composite_figi else None,
        delisted_utc=ended if row.adapter == "massive_reference" and row.listing_status == "inactive" else row.delisted_utc,
    )) for row in terminal_records())
    if event_available:
        from data_sources.lifecycle_provider_census_transport import MassiveTickerEventsResult
        from src.security_lifecycle_provider_authority import ticker_event_evidence
        material += (ticker_event_evidence(ticker, MassiveTickerEventsResult(stable_id, (), f"https://api.massive.com/vX/reference/tickers/{stable_id}/events", "b" * 64, 100, latest_ticker=ticker), at=NOW),)
    checks = ProviderCheckStore(profile)
    checks.record(ticker=ticker, at=NOW, evidence=material, diagnostics={}, blockers=() if event_available else ("massive_not_found",))
    observation = checks.latest()[ticker]["observation"]
    fingerprint = observation_fingerprint(observation)
    with sqlite3.connect(profile) as conn:
        investigation = SecurityLifecycleInvestigationStore(conn)
        case_id = investigation.ensure_case(source="listing_authority", source_ref=f"listing:{ticker}", ticker=ticker, at=NOW)
        if assess:
            assessment_id = investigation.create_assessment(case_id=case_id, relevance="direct_tracked_security", confidence="high", author="human",
                conclusion="Reviewed explicit delisting with current trading checks; no acquirer alias is authorized.", impact_summary="Stop collection, preserve history.",
                outcomes=("listing_ended",), citations=[{"reference_kind": "observation", "cited_content_sha256": fingerprint}],
                observation_fingerprint_sha256=fingerprint, effective_date=ended, at=NOW)
            investigation.accept_assessment(assessment_id, observation_fingerprint_sha256=fingerprint, acceptance_authority="human", at=NOW)
            investigation.generate_action_proposals(case_id=case_id, observation_fingerprint_sha256=fingerprint, sources_by_ticker={ticker: ("manual_lists", "sa_alpha_picks_former")}, at=NOW)
    now = [NOW]
    def sources():
        return build_active_universe_snapshot(profile_db=profile, sa_db=sa).sources_by_ticker
    service = TickerIdentityService(market_db_path=str(market), profile_db_path=str(profile), source_loader=sources, clock=lambda: now[0])
    return dict(profile=profile, market=market, sa=sa, tracking=tracking, checks=checks, case_id=case_id, service=service, now=now,
                sources=sources, observed=observed, material=material, ended=ended)


@pytest.mark.parametrize("ticker,ended", [("ARCH", "2025-01-15"), ("LTHM", "2024-01-05"), ("TA", "2023-05-16")])
def test_reviewed_legacy_delisting_stops_shared_scope_and_sa_sync_cannot_resurrect(tmp_path, ticker, ended):
    c = setup_workflow(tmp_path, ticker=ticker, ended=ended, event_available=False)
    assert ticker in c["sources"]()
    preview = c["service"].preview_case(c["case_id"], options=TransitionOptions(execute_on=ended))
    assert preview["eligible"], preview["block_reasons"]
    approved = c["service"].approve_case(c["case_id"], options=TransitionOptions(execute_on=ended), preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    applied = c["service"].execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert applied["status"] == "applied"
    assert ticker not in c["sources"]()
    c["tracking"].reconcile([{**c["observed"], "observed_at": "2026-09-06T01:00:00Z"}], at="2026-09-06T01:00:00Z", bootstrap_actor="attended_user")
    assert ticker not in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT count(*) FROM ticker_identity_links").fetchone()[0] == 0
        assert conn.execute("SELECT action,actor FROM sa_tracking_events ORDER BY event_id DESC LIMIT 1").fetchone() == ("remove", "lifecycle_transition")
        assert conn.execute("SELECT count(*) FROM watchlist_memberships WHERE ticker=?", (ticker,)).fetchone()[0] == 1


@pytest.mark.parametrize("change", ["elapsed", "active_otc"])
def test_even_a_replayed_preview_cannot_apply_after_listing_authority_changes(tmp_path, change):
    c = setup_workflow(tmp_path)
    preview = c["service"].preview_case(c["case_id"], options=TransitionOptions(execute_on=c["ended"]))
    approved = c["service"].approve_case(c["case_id"], options=TransitionOptions(execute_on=c["ended"]), preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    if change == "elapsed":
        c["now"][0] = "2026-09-10T01:00:00Z"
    else:
        c["checks"].record(ticker="OLD", at="2026-09-05T01:01:00Z", evidence=[_evidence(record("massive_reference", "active", market="otc"))], diagnostics={})
        c["now"][0] = "2026-09-05T01:01:00Z"
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: c["now"][0])
        result = store.apply(approved["transition_id"], current_preview=preview, expected_preview_sha256=preview["preview_sha256"], trigger="attended_user")
    assert result["status"] == "blocked"
    assert "OLD" in c["sources"]()


def test_a_new_open_position_vetoes_even_an_approved_provider_terminal(tmp_path):
    c = setup_workflow(tmp_path)
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    approved = c["service"].approve_case(c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    portfolio = PortfolioStore(c["profile"])
    account = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(account_id=account.id, symbol="OLD", quantity=1)
    assert c["service"].preview_case(c["case_id"], options=options)["eligible"] is False
    result = c["service"].execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert result["status"] == "blocked"
    assert "portfolio_open" in c["sources"]()["OLD"]


@pytest.mark.parametrize("former_removed", (False, True))
def test_terminal_suppresses_dual_current_source_and_reverse_restores_exact_intent(tmp_path, former_removed):
    c = setup_workflow(tmp_path)
    both = {**c["observed"], "current_observed": True}
    c["tracking"].reconcile((both,), at=NOW)
    if former_removed:
        member_id = c["tracking"].list_memberships()[0]["membership_id"]
        c["tracking"].remove(member_id, at=NOW)
    before = c["sources"]()
    assert "sa_alpha_picks_current" in before["OLD"]
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    assert preview["eligible"], preview["block_reasons"]
    approved = c["service"].approve_case(c["case_id"], options=options,
        preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    result = c["service"].execute_transition(approved["transition_id"],
        preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert result["status"] == "applied"
    assert c["tracking"].active_sources() == {}
    c["tracking"].reconcile((both,), at=NOW)
    assert c["tracking"].active_sources() == {}
    with sqlite3.connect(c["profile"]) as conn:
        transitions = TickerIdentityTransitionStore(conn, clock=lambda: NOW)
        readiness = transitions.reverse_readiness(approved["transition_id"])
        assert readiness["reversible"], readiness
        reversed_result = transitions.reverse(approved["transition_id"], trigger="attended_user")
        assert reversed_result["status"] == "reversed"
    assert c["sources"]() == before


@pytest.mark.parametrize("event_available", (True, False))
def test_actual_worker_and_transition_service_require_proof_before_automatic_retirement(tmp_path, monkeypatch, event_available):
    from contextlib import contextmanager
    from src.security_lifecycle_automation_worker import LifecycleAutomationWorker
    from src.security_lifecycle_investigation import compose_security_lifecycle
    from src.service import security_lifecycle_automation_scheduler as scheduler
    c = setup_workflow(tmp_path, event_available=event_available, assess=False)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: c["profile"])
    monkeypatch.setattr(scheduler, "_market_path", lambda: c["market"])
    monkeypatch.setattr(scheduler, "_load_sources", c["sources"])
    monkeypatch.setattr(scheduler, "_clock", lambda: NOW)
    @contextmanager
    def connection():
        with sqlite3.connect(c["profile"]) as conn:
            yield conn
    monkeypatch.setattr(scheduler, "_profile_connection", connection)
    def evidence(case, **kwargs):
        return c["checks"].bundle(case, at=kwargs["at"])
    worker = LifecycleAutomationWorker(
        case_loader=scheduler._load_cases,
        profile_connection=connection, evidence_loader=evidence, source_loader=c["sources"],
        transition_preview=scheduler._transition_preview, transition_approver=scheduler._transition_approver,
        transition_mutation_allowed=lambda: True, clock=lambda: NOW, execution_owner_id="integration-worker")
    result = worker.run(limit=1, mode="live")
    with sqlite3.connect(c["profile"]) as conn:
        conn.row_factory = sqlite3.Row
        transitions = [dict(row) for row in conn.execute("SELECT * FROM ticker_identity_transitions")]
    assert result["failed"] == 0, result
    if not event_available:
        assert transitions == []
        assert "OLD" in c["sources"]()
        from src.tools.security_lifecycle_tools import SecurityLifecycleReadService
        detail = SecurityLifecycleReadService(
            market_db_path=str(c["market"]), profile_db_path=str(c["profile"]), source_loader=c["sources"],
        ).get_case_detail(c["case_id"])
        assert detail["disposition_reason"] == "ambiguous_event"
        assert detail["current_blockers"] == [{
            "blocker_code": "listing_status_unresolved", "retryable": False,
            "operator_detail": {"code": "listing_checks", "missing_checks": ["continuation"],
                                "provider_issues": [{"provider": "massive", "reason": "not_found"}],
                                "manual_review_required": True},
        }]
        c["checks"].record(ticker="OLD", at="2026-09-05T01:01:00Z", evidence=[_evidence(record("massive_reference", "active"))], diagnostics={})
        updated = SecurityLifecycleReadService(
            market_db_path=str(c["market"]), profile_db_path=str(c["profile"]), source_loader=c["sources"],
        ).get_case_detail(c["case_id"])
        assert updated["current_blockers"] == []
        return
    assert result["accepted"] == 1, result
    assert len(transitions) == 1, result
    transition = transitions[0]
    assert transition["approval_authority"] == "automation_policy"
    applied = c["service"].execute_transition(transition["transition_id"], preview_sha256=transition["approved_preview_sha256"],
        trigger="scheduler", before_write=lambda: None)
    assert applied["status"] == "applied", applied
    assert "OLD" not in c["sources"]()
