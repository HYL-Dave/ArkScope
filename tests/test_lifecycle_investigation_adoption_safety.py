"""Attended current investigations keep the generic writer's safety contracts."""

from dataclasses import replace
import json
import sqlite3

import pytest

from src.profile_state import ProfileStateStore
from src.ticker_identity_transition import TickerIdentityTransitionStore
from tests.test_lifecycle_investigation_review import context, prepare, confirm, rows


def test_current_review_preparation_never_creates_a_human_assessment_or_tracking_change(tmp_path):
    c = context(tmp_path)
    before = rows(c)
    packet = prepare(c)
    assert packet["ready"], packet["block_reasons"]
    assert packet["lane"] == "investigation" and packet["action"] == "terminal_delisting"
    assert packet["web"]["run_id"] == c["run_id"]
    assert rows(c) == before
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
@pytest.mark.parametrize("kind", ["terminal_delisting", "symbol_continuation"])
def test_current_confirmation_uses_existing_atomic_writer_without_requiring_provider_success(tmp_path, provider, auth, kind):
    c = context(tmp_path, provider=provider, auth=auth, kind=kind)
    packet = prepare(c)
    assert packet["ready"], packet["block_reasons"]
    result = confirm(c, packet)
    assert result["status"] == "applied" and result["current_effects_match"] is True
    assert ("NEW" in c["sources"]()) == (kind == "symbol_continuation")
    assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        author, authority = conn.execute("SELECT author,acceptance_authority FROM security_lifecycle_assessments").fetchone()
        assert (author, authority) == ("human", "human")
        linked = conn.execute("SELECT run_id,actor,packet_sha256 FROM lifecycle_investigation_acceptances").fetchone()
        assert linked == (c["run_id"], "attended_user", packet["packet_sha256"])
        receipt = json.loads(conn.execute("SELECT approved_preview_json FROM ticker_identity_transitions").fetchone()[0])
        assert receipt["review_confirmation"]["packet"]["web"]["execution"]["auth_mode"] == auth
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_investigation_runs").fetchone()[0] == 0
    before = rows(c)
    assert confirm(c, packet)["status"] == "already_applied"
    assert rows(c) == before


@pytest.mark.parametrize("change", ["membership", "new_observation", "future_lease", "open_position"])
def test_current_confirmation_rejects_changed_material_without_partial_human_adoption(tmp_path, change):
    c = context(tmp_path)
    packet = prepare(c)
    if change == "membership":
        ProfileStateStore(c["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["OLD"]}])
    elif change == "new_observation":
        c["checks"].record(ticker="OLD", at="2026-09-08T01:01:00Z", evidence=(), diagnostics={}, blockers=("massive_unavailable",))
        c["now"][0] = "2026-09-08T01:01:00Z"
    elif change == "future_lease":
        c["now"][0] = "2026-09-12T01:00:00Z"
    else:
        # Use the same authoritative open-position source as ordinary review.
        c["service"]._read_service.sources_by_ticker = lambda: {"OLD": ("manual_lists", "portfolio_open"), "LIVE": ("manual_lists",)}
    before = rows(c)
    with pytest.raises((ValueError, RuntimeError), match="review_changed|web_review_ineligible"):
        confirm(c, packet)
    assert rows(c) == before and "OLD" in c["sources"]()


def test_current_active_otc_veto_is_not_lost_when_other_provider_requests_failed(tmp_path):
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record
    c = context(tmp_path)
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=[_evidence(record("massive_reference", "active", market="otc"))],
                       diagnostics={}, blockers=("massive_unavailable",))
    packet = prepare(c)
    assert packet["ready"] is False and "web_active_listing_conflict" in packet["block_reasons"]
    assert "OLD" in c["sources"]()


def test_future_current_action_is_scheduled_and_rechecked_before_applying(tmp_path):
    c = context(tmp_path, future=True)
    packet = prepare(c)
    result = confirm(c, packet)
    assert result["status"] == "scheduled" and "OLD" in c["sources"]()
    c["now"][0] = "2026-09-09T15:00:00Z"
    with sqlite3.connect(c["profile"]) as conn:
        digest = conn.execute("SELECT approved_preview_sha256 FROM ticker_identity_transitions WHERE transition_id=?", (result["transition_id"],)).fetchone()[0]
    applied = c["service"].execute_transition(result["transition_id"], preview_sha256=digest, before_write=lambda: None)
    assert applied["status"] == "applied" and "OLD" not in c["sources"]()


def test_current_adoption_cannot_survive_an_approval_failure_in_a_partial_transaction(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet = prepare(c)
    before = rows(c)
    def fail(*args, **kwargs):
        raise RuntimeError("approval_failed")
    monkeypatch.setattr(TickerIdentityTransitionStore, "_approve", fail)
    with pytest.raises(RuntimeError, match="approval_failed"):
        confirm(c, packet)
    assert rows(c) == before


def test_unrelated_sa_refresh_and_other_ticker_edits_do_not_block_current_review(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    ProfileStateStore(c["profile"]).import_lists([{"name": "Other", "kind": "custom", "tickers": ["OTHER"]}])
    c["tracking"].reconcile(({**c["observed"], "observed_at": "2026-09-08T01:01:00Z"},), at="2026-09-08T01:01:00Z")
    assert confirm(c, packet)["status"] == "applied"
    assert set(c["sources"]()) == {"LIVE", "OTHER"}


@pytest.mark.parametrize("mutation", ["strip_confirmation", "edit_finding", "automation"])
def test_central_writer_rejects_forged_current_authority_even_with_recomputed_preview_digest(tmp_path, mutation):
    from src.ticker_identity_transition import profile_snapshot_sha256
    c = context(tmp_path, future=True)
    packet = prepare(c)
    result = confirm(c, packet)
    c["now"][0] = "2026-09-09T15:00:00Z"
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: c["now"][0])
        transition = store.get(result["transition_id"])
        preview = transition["approved_preview"]
        if mutation == "strip_confirmation":
            preview.pop("review_confirmation")
        elif mutation == "edit_finding":
            conn.execute("UPDATE security_lifecycle_assessments SET effective_date='2026-08-01' WHERE assessment_id=?", (transition["assessment_id"],))
        preview["preview_sha256"] = profile_snapshot_sha256(preview)
        blockers = store._provider_guard(preview, at=c["now"][0], automation=mutation == "automation")
        assert "web_acceptance_required" in blockers or "web_acceptance_invalid" in blockers
    assert "OLD" in c["sources"]()


def test_stale_provider_state_after_current_approval_blocks_the_real_due_writer(tmp_path):
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record
    c = context(tmp_path, future=True)
    packet = prepare(c)
    result = confirm(c, packet)
    with sqlite3.connect(c["profile"]) as conn:
        digest = conn.execute("SELECT approved_preview_sha256 FROM ticker_identity_transitions WHERE transition_id=?", (result["transition_id"],)).fetchone()[0]
    c["now"][0] = "2026-09-09T15:00:00Z"
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=[_evidence(replace(record("massive_reference", "active", market="otc"), retrieved_at=c["now"][0]))], diagnostics={})
    result = c["service"].execute_transition(result["transition_id"], preview_sha256=digest, before_write=lambda: None)
    assert result["status"] == "blocked" and "OLD" in c["sources"]()


def test_current_applied_receipt_can_reverse_without_erasing_investigation_or_reenrolling_on_sa_refresh(tmp_path):
    c = context(tmp_path)
    result = confirm(c, prepare(c))
    c["tracking"].reconcile(({**c["observed"], "observed_at": "2026-09-08T01:01:00Z"},), at="2026-09-08T01:01:00Z")
    assert "OLD" not in c["sources"]()
    reversed_result = c["service"].reverse_transition(result["transition_id"], before_write=lambda: None)
    assert reversed_result["status"] == "reversed"
    assert "OLD" in c["sources"]() and c["investigation"].read(c["run_id"])["status"] == "succeeded"


def test_current_due_writer_rejects_evidence_added_after_attended_adoption(tmp_path):
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore
    c = context(tmp_path, future=True)
    packet = prepare(c)
    result = confirm(c, packet)
    with sqlite3.connect(c["profile"]) as conn:
        digest = conn.execute("SELECT approved_preview_sha256 FROM ticker_identity_transitions WHERE transition_id=?", (result["transition_id"],)).fetchone()[0]
        SecurityLifecycleInvestigationStore(conn).add_evidence(case_id=packet["case_id"], run_id=None,
            kind="manual_text", adapter="manual", excerpt="New contradictory evidence", source_url=None,
            title=None, publisher=None, domain=None, source_published_at=None, retrieved_at=None,
            mime_type=None, document_status=None, at=c["now"][0])
    c["now"][0] = "2026-09-09T15:00:00Z"
    outcome = c["service"].execute_transition(result["transition_id"], preview_sha256=digest, before_write=lambda: None)
    assert outcome["status"] == "blocked"
    assert "OLD" in c["sources"]()
